#!/usr/bin/env python3
"""Generate a fully simulated Z-info table export with injected anomalies.

Nothing here is derived from real measurements. The output has the same three-table
schema as the TAI export (Installations, MeasurementPoints, MeasurementValues, gzipped
CSV, one file per plant) so the preparation stage can read it. Installation codes use the
reserved prefix ZZ, so simulated identifiers cannot be mistaken for real ones.

Anomalies and data-quality faults are injected on purpose and recorded in a separate
ground_truth/ folder, never inside the three tables. See docs/simulation/README.md.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import gzip
import io
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter

GENERATOR_VERSION = 1
TABLES = ('Installations', 'MeasurementPoints', 'MeasurementValues')
INSTALLATION_COLUMNS = ['Installation', 'Installation Description', 'Installation Type', 'Installation Recursive Key']
POINT_COLUMNS = [
    'MeasurementPointID', 'MeasurementObjectDescription', 'Product', 'ProductDescription', 'Quantity',
    'QuantityDescription', 'Parameter', 'ParameterDescription', 'Unit', 'State', 'StateDescription',
    'ComponentID', 'InputType',
]
VALUE_COLUMNS = [
    'InstallationCodeOrigin', 'MeasurementPointID', 'SubProcessCodeOrigin', 'ProcessCode',
    'SubProcessDescription', 'Product', 'ProductBalance', 'InstallationCodeDestination',
    'SubProcessDestination', 'Date', 'Value', 'Unit',
]
COUNTRY = 'ZZ'
UNKNOWN_ORIGIN = 'ZZ.99.UNK'
MAX_CORE_POINTS, MAX_FILLER_POINTS = 16, 6
PROTECTED_DAYS = 50  # clean days kept at the start of every series so a history exists

# Row labels. 1-8 are value anomalies, 20-26 are data-quality faults.
VALUE_ANOMALIES = {1: 'spike', 2: 'level_shift', 3: 'drift', 4: 'stuck', 5: 'dropout', 6: 'negative',
                   7: 'scale_error', 8: 'noise_burst'}
QUALITY_FAULTS = {20: 'blank_value', 21: 'invalid_value', 22: 'invalid_date', 23: 'duplicate_exact',
                  24: 'duplicate_conflict', 25: 'unknown_point', 26: 'unknown_origin'}
LABEL_NAMES = {**VALUE_ANOMALIES, **QUALITY_FAULTS}
# Share of an anomalous series' episodes by type, and their length in days (inclusive range).
EPISODE_MIX = [(1, 0.40, (1, 2)), (2, 0.10, (6, 45)), (3, 0.06, (15, 60)), (4, 0.08, (7, 40)),
               (5, 0.16, (1, 12)), (6, 0.06, (1, 4)), (7, 0.08, (1, 6)), (8, 0.06, (5, 25))]
# Per-row probability of each data-quality fault (before --quality-scale).
QUALITY_RATES = {20: 0.0030, 21: 0.0012, 22: 0.0005, 23: 0.0015, 24: 0.0010, 25: 0.0005, 26: 0.0005}
DUPLICATE_RATE = QUALITY_RATES[23] + QUALITY_RATES[24]
BAD_VALUES = ['n.v.t.', 'NaN', 'ERROR', '#N/A', '--', 'onbekend', '12,5']
BAD_DATES = ['2023-02-30', '', '31-13-2022', 'onbekend', '0000-00-00']
SCALE_FACTORS = [10.0, 100.0, 1000.0, 0.1, 0.01, 0.001]

# Process families: ProcessCode, description, maximum units. Numbered units give SubProcessCodeOrigin.
FAMILIES = {
    'PLANT': ('RW', 'Totale installatie', 1, 'PL'),
    'INL': ('INL', 'Influentgemaal (één pomp)', 2, 'IN'),
    'AAT': ('AAT', 'Beluchtingstank', 8, 'AT'),
    'NBT': ('NBT', 'Nabezinktank', 4, 'NB'),
    'SLB': ('SLB', 'Slibverwerking (één straat)', 2, 'SL'),
    'GIS': ('GIS', 'Slibgisting', 2, 'GI'),
    'EFF': ('EFF', 'Effluentlozing', 1, 'EF'),
    'DS-': ('DS-', 'Dosering', 2, 'DS'),
    'ENE': ('ENE', 'Energievoorziening', 1, 'EN'),
}


@dataclass(frozen=True)
class Kind:
    """One type of measurement point and the model behind its simulated series."""
    key: str
    label: str
    product: tuple
    quantity: tuple
    parameter: tuple
    state: tuple
    unit: str
    input_type: str
    family: str
    tag: str
    median: float
    spread: float          # sigma of the per-point base level (log scale; absolute for mode 'temp')
    seasonal: float        # annual amplitude (log scale; degrees for mode 'temp'), peaking on peak_doy
    peak_doy: int
    rain: float            # response to the plant's rain-driven wetness (log scale)
    weekend: float         # log-scale weekend effect
    phi: float             # day-to-day autocorrelation of the noise
    noise: float           # marginal sd of the noise (log scale; absolute for mode 'temp')
    decimals: int = 2
    nonneg: bool = True
    weight: float = 0.0    # expected points per average plant; 0 for core groups
    core: str = ''         # history-detector measurement group this kind belongs to
    mode: str = 'mult'     # 'mult', 'temp', 'rain'
    zero_frac: float = 0.0
    cap: float = 0.0
    scales: bool = False   # level scales with plant size
    dest_prob: float = 0.0


NVT = ('NVT', 'Niet van toepassing')
NVT_STATE = ('NVT', 'niet van toepassing')
STATE_N = ('N', 'uitgedrukt in Stikstof')
STATE_P = ('P', 'uitgedrukt in Fosfor')
STATE_O2 = ('O2', 'uitgedrukt in Zuurstof')
CONC = ('CONC', '(massa)Concentratie')
VOL = ('VOL', 'Volume')
TEMP = ('TEMP', 'Temperatuur')
INFLUENT, EFFLUENT, ACTIVE = ('INFLU', 'Influent'), ('EFFLU', 'Effluent'), ('ACTSL', 'Actief slib')


def _kind(key, label, product, quantity, parameter, state, unit, input_type, family, tag, median, spread,
          seasonal, peak_doy, rain, weekend, phi, noise, **extra):
    return Kind(key, label, product, quantity, parameter, state, unit, input_type, family, tag, median, spread,
                seasonal, peak_doy, rain, weekend, phi, noise, **extra)


KINDS = [
    # Core groups: the six measurement groups of the history detector, with the same metadata fields.
    _kind('influent_volume', 'Debiet influent', INFLUENT, VOL, NVT, NVT_STATE, 'm3', 'scada', 'INL', 'Q',
          9000, 0.35, 0.07, 30, 0.22, -0.04, 0.55, 0.06, decimals=0, scales=True, core='influent_volume'),
    _kind('oxygen', 'Zuurstof beluchtingstank', ACTIVE, CONC, ('O2', 'zuurstof'), NVT_STATE, 'mg/l', 'scada',
          'AAT', 'O', 1.4, 0.30, -0.10, 200, 0.0, 0.0, 0.80, 0.20, core='oxygen'),
    _kind('ammonium', 'Ammonium beluchtingstank', ACTIVE, CONC, ('NH4', 'ammonium'), STATE_N, 'mg/l', 'scada',
          'AAT', 'A', 0.9, 0.70, 0.30, 30, -0.10, 0.0, 0.80, 0.35, core='ammonium'),
    _kind('nitrate', 'Nitraat beluchtingstank', ACTIVE, CONC, ('NO3', 'nitraat'), STATE_N, 'mg/l', 'scada',
          'AAT', 'N', 4.2, 0.40, 0.12, 200, -0.06, 0.0, 0.85, 0.18, core='nitrate'),
    _kind('suspended_solids', 'Slibgehalte beluchtingstank', ACTIVE, CONC, ('OBD', 'Onopgeloste bestandsdelen'),
          NVT_STATE, 'g/l', 'scada', 'AAT', 'S', 3.8, 0.25, 0.04, 60, 0.0, 0.0, 0.97, 0.10,
          core='suspended_solids'),
    _kind('temperature', 'Temperatuur beluchtingstank', ACTIVE, TEMP, NVT, NVT_STATE, 'oC', 'scada', 'AAT', 'T',
          15.0, 1.2, 5.5, 200, 0.0, 0.0, 0.90, 0.5, decimals=1, nonneg=False, mode='temp', core='temperature'),
    # Fillers: other points a plant reports, including near-misses the group filters must reject.
    _kind('effluent_volume', 'Debiet effluent', EFFLUENT, VOL, NVT, NVT_STATE, 'm3', 'scada', 'EFF', 'Q',
          8800, 0.35, 0.03, 30, 0.20, -0.03, 0.55, 0.06, decimals=0, weight=1.1, scales=True),
    _kind('effluent_ntot', 'Totaal stikstof effluent', EFFLUENT, CONC, ('NTOT', 'stikstof totaal'), STATE_N,
          'mg/l', 'handmatig', 'EFF', 'A', 5.5, 0.35, 0.25, 40, -0.05, 0.0, 0.70, 0.25, weight=1.2),
    _kind('effluent_ptot', 'Totaal fosfor effluent', EFFLUENT, CONC, ('PTOT', 'fosfor totaal'), STATE_P,
          'mg/l', 'handmatig', 'EFF', 'A', 0.6, 0.45, 0.0, 40, 0.0, 0.0, 0.70, 0.35, weight=1.0),
    _kind('effluent_cod', 'CZV effluent', EFFLUENT, CONC, ('CZV', 'chemisch zuurstofverbruik'), STATE_O2,
          'mg/l', 'handmatig', 'EFF', 'A', 38, 0.30, 0.0, 40, 0.0, 0.0, 0.70, 0.22, decimals=1, weight=0.9),
    _kind('effluent_bod', 'BZV effluent', EFFLUENT, CONC, ('BZV', 'biochemisch zuurstofverbruik'), STATE_O2,
          'mg/l', 'handmatig', 'EFF', 'A', 3.5, 0.30, 0.0, 40, 0.0, 0.0, 0.60, 0.30, decimals=1, weight=0.9),
    _kind('effluent_ss', 'Zwevende stof effluent', EFFLUENT, CONC, ('OBD', 'Onopgeloste bestandsdelen'),
          NVT_STATE, 'mg/l', 'handmatig', 'EFF', 'A', 6.0, 0.30, 0.0, 40, 0.0, 0.0, 0.60, 0.35, decimals=1,
          weight=0.9),
    _kind('influent_cod', 'CZV influent', INFLUENT, CONC, ('CZV', 'chemisch zuurstofverbruik'), STATE_O2,
          'mg/l', 'handmatig', 'INL', 'A', 520, 0.30, -0.05, 40, -0.22, -0.05, 0.60, 0.22, decimals=0,
          weight=0.9),
    _kind('influent_ntot', 'Totaal stikstof influent', INFLUENT, CONC, ('NTOT', 'stikstof totaal'), STATE_N,
          'mg/l', 'handmatig', 'INL', 'A', 48, 0.30, 0.0, 40, -0.18, -0.04, 0.60, 0.18, decimals=1, weight=0.8),
    _kind('influent_ptot', 'Totaal fosfor influent', INFLUENT, CONC, ('PTOT', 'fosfor totaal'), STATE_P,
          'mg/l', 'handmatig', 'INL', 'A', 7.2, 0.30, 0.0, 40, -0.18, -0.04, 0.60, 0.20, weight=0.8),
    _kind('influent_bod', 'BZV influent', INFLUENT, CONC, ('BZV', 'biochemisch zuurstofverbruik'), STATE_O2,
          'mg/l', 'handmatig', 'INL', 'A', 210, 0.30, 0.0, 40, -0.20, -0.05, 0.60, 0.25, decimals=0,
          weight=0.8),
    _kind('influent_ss', 'Zwevende stof influent', INFLUENT, CONC, ('OBD', 'Onopgeloste bestandsdelen'),
          NVT_STATE, 'mg/l', 'handmatig', 'INL', 'A', 240, 0.30, 0.0, 40, -0.10, -0.05, 0.55, 0.30, decimals=0,
          weight=0.8),
    _kind('influent_temperature', 'Temperatuur influent', INFLUENT, TEMP, NVT, NVT_STATE, 'oC', 'scada', 'INL',
          'T', 14.5, 1.0, 5.0, 205, 0.0, 0.0, 0.90, 0.45, decimals=1, nonneg=False, mode='temp', weight=0.7),
    _kind('influent_ph', 'Zuurgraad influent', INFLUENT, ('PH', 'Zuurgraad'), NVT, NVT_STATE, '-', 'scada',
          'INL', 'P', 7.4, 0.02, 0.0, 40, 0.0, 0.0, 0.70, 0.02, weight=0.8),
    _kind('influent_conductivity', 'Geleidbaarheid influent', INFLUENT, ('GELV', 'Geleidbaarheid'), NVT,
          NVT_STATE, 'mS/m', 'scada', 'INL', 'G', 85, 0.25, 0.0, 40, -0.25, 0.0, 0.70, 0.08, decimals=1,
          weight=0.6),
    _kind('return_sludge_flow', 'Retourslibdebiet', ('RETSL', 'Retourslib'), VOL, NVT, NVT_STATE, 'm3',
          'scada', 'NBT', 'Q', 6500, 0.35, 0.0, 40, 0.15, 0.0, 0.60, 0.08, decimals=0, weight=1.0, scales=True),
    _kind('surplus_sludge_flow', 'Overschotslibdebiet', ('OVSL', 'Overschotslib'), VOL, NVT, NVT_STATE, 'm3',
          'scada', 'SLB', 'Q', 160, 0.35, 0.0, 40, 0.0, 0.0, 0.50, 0.30, decimals=1, weight=0.9, scales=True,
          dest_prob=0.35),
    _kind('sludge_dry_matter', 'Drogestofgehalte slib', ('SLIB', 'Slib'), CONC, ('DS', 'droge stof'), NVT_STATE,
          '%', 'handmatig', 'SLB', 'D', 4.2, 0.30, 0.0, 40, 0.0, 0.0, 0.90, 0.08, weight=0.8),
    _kind('sludge_production', 'Slibproductie', ('SLIB', 'Slib'), ('MASS', 'Massa'), ('DS', 'droge stof'),
          NVT_STATE, 'ton', 'scada', 'SLB', 'M', 6.5, 0.35, 0.0, 40, 0.0, 0.0, 0.50, 0.25, weight=0.8,
          scales=True, dest_prob=0.4),
    _kind('biogas_production', 'Biogasproductie', ('BIOGS', 'Biogas'), VOL, NVT, NVT_STATE, 'Nm3', 'scada',
          'GIS', 'Q', 2400, 0.40, 0.04, 200, 0.0, 0.0, 0.80, 0.10, decimals=0, weight=0.6, scales=True),
    _kind('electricity_use', 'Elektriciteitsverbruik', ('ELEKT', 'Elektriciteit'), ('ENER', 'Energie'), NVT,
          NVT_STATE, 'kWh', 'scada', 'ENE', 'E', 11000, 0.40, 0.0, 40, 0.0, -0.02, 0.70, 0.07, decimals=0,
          weight=1.0, scales=True),
    _kind('blower_power', 'Vermogen beluchting', ('LUCHT', 'Lucht'), ('POW', 'Vermogen'), NVT, NVT_STATE, 'kW',
          'scada', 'AAT', 'P', 220, 0.40, -0.08, 200, 0.0, 0.0, 0.70, 0.12, decimals=1, weight=0.9,
          scales=True),
    _kind('airflow', 'Luchtdebiet beluchting', ('LUCHT', 'Lucht'), VOL, NVT, NVT_STATE, 'Nm3/h', 'scada', 'AAT',
          'L', 6500, 0.40, 0.0, 40, 0.0, 0.0, 0.70, 0.12, decimals=0, weight=0.7, scales=True),
    _kind('fecl3_dosing', 'Dosering ijzerchloride', ('FECL3', 'IJzerchloride'), VOL, NVT, NVT_STATE, 'l',
          'scada', 'DS-', 'D', 900, 0.40, 0.0, 40, 0.0, 0.0, 0.85, 0.30, decimals=0, weight=0.7, scales=True,
          zero_frac=0.12),
    _kind('polymer_dosing', 'Dosering polymeer', ('POLYM', 'Polymeer'), ('MASS', 'Massa'), NVT, NVT_STATE, 'kg',
          'scada', 'DS-', 'D', 85, 0.40, 0.0, 40, 0.0, 0.0, 0.85, 0.30, decimals=1, weight=0.6, scales=True,
          zero_frac=0.08),
    _kind('rainfall', 'Neerslag', ('NEERS', 'Neerslag'), ('HGT', 'Hoogte'), NVT, NVT_STATE, 'mm', 'scada',
          'PLANT', 'R', 0, 0, 0, 0, 0, 0, 0, 0, decimals=1, weight=0.5, mode='rain'),
    _kind('basin_level', 'Waterniveau bezinktank', ('WATER', 'Water'), ('NIV', 'Niveau'), NVT, NVT_STATE, 'm',
          'scada', 'NBT', 'L', 2.4, 0.15, 0.0, 40, 0.0, 0.0, 0.90, 0.06, weight=0.8),
    _kind('sludge_volume_index', 'Slibvolume-index', ACTIVE, ('VERH', 'Verhouding'), ('SVI', 'slibvolume-index'),
          NVT_STATE, 'ml/g', 'handmatig', 'AAT', 'V', 120, 0.25, 0.0, 40, 0.0, 0.0, 0.95, 0.18, decimals=0,
          weight=0.6),
    _kind('pump_hours', 'Bedrijfsuren pomp', INFLUENT, ('TIJD', 'Tijd'), ('BU', 'bedrijfsuren'), NVT_STATE,
          'uur', 'scada', 'INL', 'H', 14, 0.35, 0.0, 40, 0.10, 0.0, 0.60, 0.15, decimals=1, weight=0.8,
          cap=24.0),
    _kind('digester_temperature', 'Temperatuur gistingstank', ('SLIB', 'Slib'), TEMP, NVT, NVT_STATE, 'oC',
          'scada', 'GIS', 'T', 35.5, 0.6, 0.25, 200, 0.0, 0.0, 0.90, 0.25, decimals=1, nonneg=False,
          mode='temp', weight=0.4),
    _kind('effluent_temperature', 'Temperatuur effluent', EFFLUENT, TEMP, NVT, NVT_STATE, 'oC', 'scada', 'EFF',
          'T', 15.0, 1.0, 5.0, 205, 0.0, 0.0, 0.90, 0.45, decimals=1, nonneg=False, mode='temp', weight=0.5),
    # Near-misses of the core groups: same quantity, different metadata, so the exact filters must skip them.
    _kind('oxygen_manual', 'Zuurstof handmatig', ACTIVE, CONC, ('O2', 'zuurstof'), NVT_STATE, 'mg/l',
          'handmatig', 'AAT', 'O', 1.6, 0.30, -0.10, 200, 0.0, 0.0, 0.50, 0.30, weight=0.35),
    _kind('ammonium_as_ammonium', 'Ammonium als NH4', ACTIVE, CONC, ('NH4', 'ammonium'),
          ('NH4', 'uitgedrukt in Ammonium'), 'mg/l', 'scada', 'AAT', 'A', 1.1, 0.70, 0.30, 30, -0.10, 0.0, 0.80,
          0.35, weight=0.3),
    _kind('nitrate_manual', 'Nitraat handmatig', ACTIVE, CONC, ('NO3', 'nitraat'), STATE_N, 'mg/l', 'handmatig',
          'AAT', 'N', 4.2, 0.40, 0.12, 200, -0.06, 0.0, 0.50, 0.25, weight=0.3),
    _kind('suspended_solids_mgl', 'Slibgehalte in mg/l', ACTIVE, CONC, ('OBD', 'Onopgeloste bestandsdelen'),
          NVT_STATE, 'mg/l', 'scada', 'AAT', 'S', 3800, 0.25, 0.04, 60, 0.0, 0.0, 0.97, 0.10, decimals=0,
          weight=0.3),
    _kind('influent_volume_hourly', 'Debiet influent per uur', INFLUENT, VOL, NVT, NVT_STATE, 'm3/h', 'scada',
          'INL', 'Q', 380, 0.35, 0.07, 30, 0.22, -0.04, 0.55, 0.06, decimals=0, weight=0.3, scales=True),
]
CORE_KINDS = [i for i, k in enumerate(KINDS) if k.core]


@dataclass(frozen=True)
class Config:
    seed: int
    start: str
    end: str
    n_days: int
    plants: int
    anomaly_rate: float
    quality_scale: float
    output: str
    plant_codes: tuple


@dataclass(frozen=True)
class Plant:
    index: int
    code: str
    region: int
    tag: str
    size: float
    tanks: int
    core_counts: tuple
    empty: bool
    legacy_encoding: bool


@dataclass(frozen=True)
class Point:
    kind_index: int
    k: int
    point_id: str
    family: str
    unit_no: int
    destination: str
    destination_sub: str
    balance: str


def stream_rng(*key) -> np.random.Generator:
    return np.random.default_rng([int(part) for part in key])


def ar1(rng, n, phi, sd):
    """Stationary AR(1) noise with marginal standard deviation sd."""
    start = rng.normal(0.0, sd)
    shocks = rng.normal(0.0, sd * math.sqrt(1.0 - phi * phi), n)
    return lfilter([1.0], [1.0, -phi], shocks, zi=[phi * start])[0]


def build_plants(seed, n_plants, n_days):
    rng = stream_rng(seed, 0)
    n_regions = min(6, n_plants)
    letters = rng.permutation(26 ** 3)[:n_plants]
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    plants = []
    empty = set(rng.choice(n_plants, size=2, replace=False).tolist()) if n_plants >= 50 else set()
    for i in range(n_plants):
        region = 1 + i * n_regions // n_plants
        code = f'{COUNTRY}.{region:02d}.' + ''.join(alphabet[(letters[i] // 26 ** p) % 26] for p in (2, 1, 0))
        number = (i * 48271 + 11) % 26 ** 4
        tag = 'SIM' + ''.join(alphabet[(number // 26 ** p) % 26] for p in (3, 2, 1, 0))
        size = float(np.clip(rng.lognormal(0.0, 0.55), 0.3, 3.5))
        tanks = int(np.clip(round(2 * size ** 0.6 + rng.normal(0, 0.7)), 1, 8))
        core = {
            'influent_volume': 1 + int(size > 1.6) + int(rng.random() < 0.2),
            'oxygen': tanks + int(rng.integers(0, tanks + 1)),
            'ammonium': max(1, tanks // 2 + int(rng.integers(0, 2))),
            'nitrate': max(1, tanks // 2 + int(rng.integers(0, 2))),
            'suspended_solids': tanks,
            'temperature': 1 + int(rng.integers(0, 3)),
        }
        counts = tuple(min(core[KINDS[j].core], MAX_CORE_POINTS) for j in CORE_KINDS)
        plants.append(Plant(i, code, region, tag, size, tanks, counts, i in empty, bool(rng.random() < 0.04)))
    return plants


def presence_mask(seed, plant, kind_index, k, n_days):
    """Days on which a point reports. Late starts, early ends and gaps are all missing rows."""
    rng = stream_rng(seed, plant, kind_index, k, 0)
    start = int(rng.beta(1.2, 1.8) * (n_days - 200)) if rng.random() < 0.22 and n_days > 260 else 0
    end = int(rng.uniform(start + 150, n_days)) if rng.random() < 0.10 and n_days > start + 160 else n_days
    present = np.zeros(n_days, dtype=bool)
    present[start:end] = True
    for _ in range(rng.poisson(1.2)):
        s = int(rng.integers(start, max(start + 1, end)))
        present[s:s + int(min(90, 1 + rng.lognormal(1.8, 0.9)))] = False
    present &= rng.random(n_days) > 0.004
    return present


def point_cap(kind_index):
    return MAX_CORE_POINTS if KINDS[kind_index].core else MAX_FILLER_POINTS


def filler_draws(seed, plants):
    """Per plant and kind: expected point count at multiplier 1, and the rounding draw."""
    mean = np.zeros((len(plants), len(KINDS)))
    draw = np.zeros_like(mean)
    for p in plants:
        for j, kind in enumerate(KINDS):
            if kind.core:
                continue
            rng = stream_rng(seed, p.index, j, 99, 9)
            mean[p.index, j] = kind.weight * p.size ** 0.7 * rng.uniform(0.4, 1.6)
            draw[p.index, j] = rng.random()
    return mean, draw


def plan_counts(cfg, plants, target_clean_rows):
    """Choose how many fillers each plant has so the clean row count meets the target.

    Presence masks depend only on (plant, kind, k), so counting rows here is exact and
    changing the multiplier never shifts any series.
    """
    P, J = len(plants), len(KINDS)
    cumulative = np.zeros((P, J, MAX_CORE_POINTS + 1), dtype=np.int64)
    for p in plants:
        if p.empty:
            continue
        for j in range(J):
            for k in range(point_cap(j)):
                cumulative[p.index, j, k + 1] = presence_mask(cfg.seed, p.index, j, k, cfg.n_days).sum()
    cumulative = np.cumsum(cumulative, axis=2)
    mean, draw = filler_draws(cfg.seed, plants)
    core_counts = np.zeros((P, J), dtype=np.int64)
    for p in plants:
        for position, j in enumerate(CORE_KINDS):
            core_counts[p.index, j] = p.core_counts[position]
    caps = np.array([point_cap(j) for j in range(J)])

    def counts_for(multiplier):
        counts = np.minimum(np.floor(mean * multiplier + draw), caps).astype(np.int64)
        counts = np.where(core_counts > 0, core_counts, counts)
        counts[[p.index for p in plants if p.empty]] = 0
        return counts

    def rows_for(counts):
        return int(np.take_along_axis(cumulative, counts[:, :, None], axis=2).sum())

    low, high = 0.0, 30.0
    if rows_for(counts_for(low)) >= target_clean_rows:
        return counts_for(low), low
    for _ in range(30):
        middle = (low + high) / 2
        if rows_for(counts_for(middle)) < target_clean_rows:
            low = middle
        else:
            high = middle
    best = min((low, high), key=lambda m: abs(rows_for(counts_for(m)) - target_clean_rows))
    return counts_for(best), best


def make_points(cfg, plant, counts):
    """Point definitions for one plant, in file order. Identical in planning and generation."""
    points = []
    for j, kind in enumerate(KINDS):
        family = FAMILIES[kind.family]
        units = {'AAT': plant.tanks, 'NBT': max(1, plant.tanks // 2 + 1)}.get(kind.family, family[2])
        for k in range(int(counts[j])):
            rng = stream_rng(cfg.seed, plant.index, j, k, 2)
            suffix = ('PV', 'AV', 'M1')[(j + k) % 3]
            point_id = f'{plant.region:02d}.{plant.tag}.{kind.tag}{j:02d}{k:02d}.{suffix}'
            destination = destination_sub = ''
            balance = 'Input' if kind.product[0] == 'INFLU' else 'Output' if kind.product[0] == 'EFFLU' else 'Intern'
            if kind.dest_prob and rng.random() < kind.dest_prob and cfg.plants > 1:
                other = (plant.index + 1 + int(rng.integers(0, min(5, cfg.plants - 1)))) % cfg.plants
                destination, destination_sub, balance = cfg.plant_codes[other], 'RWZI.SLB001', 'Output'
            points.append(Point(j, k, point_id, kind.family, 1 + k % units, destination, destination_sub, balance))
    return points


def subprocess_fields(point):
    code, description, _, _ = FAMILIES[point.family]
    if point.family == 'PLANT':
        return 'RWZI', code, description
    return f'RWZI.{code}{point.unit_no:03d}', code, f'{description} {point.unit_no}'


class PlantSignals:
    """Rain and calendar signals shared by every point of a plant."""

    def __init__(self, cfg, plant, dates):
        self.n = cfg.n_days
        self.doy = dates.day_of_year.to_numpy()
        self.weekend = (dates.day_of_week.to_numpy() >= 5).astype(float)
        rng = stream_rng(cfg.seed, plant.index, 98, 0, 3)
        wet_day = rng.random(self.n) < 0.30 + 0.08 * np.cos(2 * np.pi * (self.doy - 330) / 365.25)
        self.rain = np.round(rng.gamma(0.6, 9.0, self.n) * wet_day, 1)
        self.wet = lfilter([1.0], [1.0, -0.55], self.rain / 8.0)


def clean_series(kind, rng, signals, size):
    n = signals.n
    if kind.mode == 'rain':
        return np.round(signals.rain * rng.uniform(0.9, 1.1), kind.decimals)
    cycle = np.cos(2 * np.pi * (signals.doy - kind.peak_doy) / 365.25)
    if kind.mode == 'temp':
        y = kind.median + rng.normal(0, kind.spread) + kind.seasonal * cycle + ar1(rng, n, kind.phi, kind.noise)
    else:
        base = kind.median * math.exp(rng.normal(0, kind.spread)) * (size if kind.scales else 1.0)
        log_y = (math.log(base) + kind.seasonal * rng.uniform(0.7, 1.3) * cycle
                 + kind.rain * rng.uniform(0.7, 1.3) * signals.wet + kind.weekend * signals.weekend
                 + ar1(rng, n, kind.phi, kind.noise))
        y = np.exp(log_y)
        if kind.zero_frac:
            off = ar1(rng, n, 0.95, 1.0)
            y[off < np.quantile(off, kind.zero_frac)] = 0.0
        if kind.cap:
            y = np.minimum(y, kind.cap)
    return np.round(y, kind.decimals) + 0.0


def inject_anomalies(rng, kind, y, present, fraction, first_day):
    """Overwrite stretches of y with anomalies. Returns y, labels, episode ids and episode records."""
    n = len(y)
    label = np.zeros(n, dtype=np.int8)
    episode_id = np.zeros(n, dtype=np.int32)
    records = []
    days = np.flatnonzero(present)
    lowest = first_day + PROTECTED_DAYS
    if fraction <= 0 or len(days) < PROTECTED_DAYS + 30 or lowest >= n - 30:
        return y, label, episode_id, records
    observed = y[days]
    median = float(np.median(observed))
    # Spread of the series around its own 28-day running median, like the detector's baseline.
    deviation = observed - pd.Series(observed).rolling(28, min_periods=14).median().to_numpy()
    robust = 1.4826 * float(np.nanmedian(np.abs(deviation)))
    scale = max(robust, 0.05 * abs(median), 0.15 * float(np.std(observed)), 1e-6)
    original = y.copy()
    y = y.copy()
    codes = [c for c, _, _ in EPISODE_MIX if c != 6 or kind.nonneg]
    weights = np.array([w for c, w, _ in EPISODE_MIX if c in codes])
    weights = weights / weights.sum()
    lengths = {c: span for c, _, span in EPISODE_MIX}
    wanted = fraction * len(days)
    covered, attempts = 0, 0
    while covered < wanted and attempts < 300:
        attempts += 1
        code = int(rng.choice(codes, p=weights))
        low, high = lengths[code]
        length = int(rng.integers(low, high + 1))
        if lowest >= n - length:
            continue
        start = int(rng.integers(lowest, n - length))
        end = start + length
        if label[max(0, start - 3):end + 3].any():
            continue
        sign = 1.0 if rng.random() < 0.5 else -1.0
        segment = slice(start, end)
        magnitude = ''
        if code == 1:
            k = rng.uniform(4, 14)
            y[segment] = original[segment] + sign * k * scale
            magnitude = f'{sign * k:+.1f} spreads'
        elif code == 2:
            k = rng.uniform(3, 8)
            y[segment] = original[segment] + sign * k * scale
            magnitude = f'{sign * k:+.1f} spreads'
        elif code == 3:
            k = rng.uniform(4, 10)
            y[segment] = original[segment] + sign * k * scale * np.linspace(0.0, 1.0, length)
            magnitude = f'{sign * k:+.1f} spreads at peak'
        elif code == 4:
            y[segment] = y[start]
            magnitude = f'frozen at {y[start]:g}'
        elif code == 5:
            y[segment] = 0.0
            magnitude = 'zero'
        elif code == 6:
            y[segment] = -original[segment] * rng.uniform(0.05, 1.0, length)
            magnitude = 'sign flipped'
        elif code == 7:
            factor = float(rng.choice(SCALE_FACTORS))
            y[segment] = original[segment] * factor
            magnitude = f'x{factor:g}'
        else:
            k = rng.uniform(2.5, 5)
            y[segment] = original[segment] + rng.normal(0, k * scale, length)
            magnitude = f'noise sd {k:.1f} spreads'
        if kind.nonneg and code in (1, 2, 3, 8):
            y[segment] = np.maximum(y[segment], 0.05 * original[segment])
        y[segment] = np.round(y[segment], kind.decimals) + 0.0
        if code == 4:
            y[segment] = y[start]
        rows = int(present[segment].sum())
        label[segment] = code
        if rows:
            covered += rows
            records.append((code, start, end - 1, rows, magnitude))
    return y, label, episode_id, records


def to_strings(values, decimals):
    if decimals == 0:
        return np.round(values).astype(np.int64).astype(str).tolist()
    return (np.round(values, decimals) + 0.0).astype(str).tolist()


def quote(text):
    return '"' + text.replace('"', '""') + '"'


def fault_codes(rng, label, scale):
    """Draw a data-quality fault for rows that carry no value anomaly."""
    draw = rng.random(len(label))
    faults = np.zeros(len(label), dtype=np.int8)
    upper = 0.0
    for code, rate in QUALITY_RATES.items():
        lower, upper = upper, upper + rate * scale
        faults[(label == 0) & (draw >= lower) & (draw < upper)] = code
    return faults


def render_series(rng, plant, point, kind, y, label, episode, days, date_text, fault_scale):
    """Turn one series into CSV lines and the labels of the lines, with faults applied."""
    origin = plant.code
    sub, process, description = subprocess_fields(point)
    fields = [origin, point.point_id, sub, process, description, kind.product[1], point.balance,
              point.destination, point.destination_sub]
    prefix = ','.join(quote(f) for f in fields) + ','
    tail = quote(kind.unit)
    values = to_strings(y, kind.decimals)
    dates = [date_text[d] for d in days]
    lines = [f'{prefix}"{d}","{v}",{tail}' for d, v in zip(dates, values)]
    faults = fault_codes(rng, label, fault_scale)
    label = label.copy()
    for i in np.flatnonzero(faults):
        code = int(faults[i])
        if code == 20:
            lines[i] = f'{prefix}"{dates[i]}","",{tail}'
        elif code == 21:
            lines[i] = f'{prefix}"{dates[i]}","{BAD_VALUES[int(rng.integers(len(BAD_VALUES)))]}",{tail}'
        elif code == 22:
            bad = BAD_DATES[int(rng.integers(len(BAD_DATES)))]
            lines[i] = f'{prefix}"{bad}","{values[i]}",{tail}'
        elif code == 25:
            other = fields.copy()
            other[1] = point.point_id + '.UNK'
            lines[i] = ','.join(quote(f) for f in other) + f',"{dates[i]}","{values[i]}",{tail}'
        elif code == 26:
            other = fields.copy()
            other[0] = UNKNOWN_ORIGIN
            lines[i] = ','.join(quote(f) for f in other) + f',"{dates[i]}","{values[i]}",{tail}'
        if code < 23 or code > 24:
            label[i] = code
    inserted = np.flatnonzero((faults == 23) | (faults == 24))
    if len(inserted):
        conflict = to_strings(y[inserted] * rng.uniform(0.85, 1.15, len(inserted)), kind.decimals)
        out, previous = [], 0
        for position, i in enumerate(inserted):
            out.extend(lines[previous:i + 1])
            if faults[i] == 23:
                out.append(lines[i])
            else:
                out.append(f'{prefix}"{dates[i]}","{conflict[position]}",{tail}')
            previous = i + 1
        out.extend(lines[previous:])
        lines = out
        label = np.insert(label, inserted + 1, faults[inserted])
        episode = np.insert(episode, inserted + 1, 0)
    return lines, label, episode


def object_description(kind, point):
    unit = '' if point.family == 'PLANT' else f' {point.unit_no}'
    return f'{kind.label}{unit}'


def point_row(kind, point):
    return [point.point_id, object_description(kind, point), kind.product[0], kind.product[1], kind.quantity[0],
            kind.quantity[1], kind.parameter[0], kind.parameter[1], kind.unit, kind.state[0], kind.state[1],
            FAMILIES[kind.family][3], kind.input_type]


def write_gzip(path, text, encoding):
    data = text.encode(encoding, errors='replace')
    with open(path, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=9, mtime=0, filename='') as out:
        out.write(data)


def csv_text(header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\n')
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def generate_plant(job):
    cfg, plant, counts = job
    out = Path(cfg.output)
    encoding = 'cp1252' if plant.legacy_encoding else 'utf-8'
    dates = pd.date_range(cfg.start, periods=cfg.n_days, freq='D')
    date_text = dates.strftime('%Y-%m-%d').tolist()
    iso = date_text
    signals = PlantSignals(cfg, plant, dates)
    points = make_points(cfg, plant, counts)
    write_gzip(out / 'extracted' / 'MeasurementPoints' / f'{plant.code}.csv.gz',
               csv_text(POINT_COLUMNS, [point_row(KINDS[p.kind_index], p) for p in points]), encoding)

    header = ','.join(quote(c) for c in VALUE_COLUMNS)
    chunks, label_rows, episodes = [header + '\n'], [], []
    next_row, episode_counter = 2, 0
    totals, per_kind = Counter(), {}
    series_with_anomaly = 0
    for point in points:
        kind = KINDS[point.kind_index]
        present = presence_mask(cfg.seed, plant.index, point.kind_index, point.k, cfg.n_days)
        days = np.flatnonzero(present)
        if not len(days):
            continue
        rng = stream_rng(cfg.seed, plant.index, point.kind_index, point.k, 1)
        y = clean_series(kind, rng, signals, plant.size)
        fraction = 0.0 if rng.random() < 0.2 else float(rng.beta(2.0, 10.8) * cfg.anomaly_rate / 0.125)
        y, label, episode_id, records = inject_anomalies(rng, kind, y, present, fraction, int(days[0]))
        for code, first, last, rows, magnitude in records:
            episode_counter += 1
            episode_id[first:last + 1] = episode_counter
            episodes.append((plant.code, f'{plant.code}.csv.gz', point.point_id, kind.key, LABEL_NAMES[code],
                             iso[first], iso[last], rows, magnitude, episode_counter))
        series_with_anomaly += bool(records)
        lines, row_label, row_episode = render_series(
            rng, plant, point, kind, y[days], label[days], episode_id[days], days, date_text, cfg.quality_scale)
        chunks.append('\n'.join(lines) + '\n')
        flagged = np.flatnonzero(row_label)
        if len(flagged):
            label_rows.append(np.column_stack([flagged + next_row, row_label[flagged], row_episode[flagged]]))
        counts_here = Counter(row_label[flagged].tolist())
        totals.update(counts_here)
        stats = per_kind.setdefault(kind.key, [0, 0])
        stats[0] += len(lines)
        stats[1] += int(len(flagged))
        totals['rows'] += len(lines)
        next_row += len(lines)
    write_gzip(out / 'extracted' / 'MeasurementValues' / f'{plant.code}.csv.gz', ''.join(chunks), encoding)

    if label_rows:
        table = pd.DataFrame(np.vstack(label_rows), columns=['source_row', 'label', 'episode_id'])
        table['anomaly_type'] = table['label'].map(LABEL_NAMES)
        table['category'] = np.where(table['label'] < 20, 'value', 'quality')
        table = table[['source_row', 'anomaly_type', 'category', 'episode_id']]
    else:
        table = pd.DataFrame(columns=['source_row', 'anomaly_type', 'category', 'episode_id'])
    write_gzip(out / 'ground_truth' / 'row_labels' / f'{plant.code}.csv.gz', table.to_csv(index=False, lineterminator='\n'), 'utf-8')
    return {'plant': plant.code, 'totals': dict(totals), 'per_kind': per_kind, 'episodes': episodes,
            'points': len(points), 'series_with_anomaly': series_with_anomaly}


def write_installations(cfg, plants, out):
    rng = stream_rng(cfg.seed, 0, 1)
    rows = []
    regions = sorted({p.region for p in plants})
    for region in regions:
        rows.append((f'{COUNTRY}.{region:02d}', f'Gesimuleerde regio {region:02d}', 'Regio', f'{COUNTRY}.{region:02d}'))
    for p in plants:
        rows.append((p.code, f'Gesimuleerde RWZI {p.index + 1:03d}', 'RWZI', p.code))
    extra = round(0.212 * len(plants))
    numbering = Counter()
    for _ in range(extra):
        parent = plants[int(rng.integers(len(plants)))]
        numbering[parent.region] += 1
        rows.append((f'{COUNTRY}.{parent.region:02d}.G{numbering[parent.region]:02d}',
                     f'Gesimuleerd gemaal {parent.index + 1:03d}', 'Gemaal', parent.code))
    for row in rows:
        write_gzip(out / 'extracted' / 'Installations' / f'{row[0]}.csv.gz', csv_text(INSTALLATION_COLUMNS, [row]),
                   'utf-8')
    return len(rows)


def run(output, seed=20260101, plants=335, target_rows=25_000_000, start='2021-01-01', end='2025-12-31',
        anomaly_rate=0.105, quality_scale=1.0, workers=1, log=print):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; select a new directory')
    if plants < 1 or target_rows < 1 or not 0 <= anomaly_rate < 0.5 or quality_scale < 0:
        raise ValueError('Invalid sizes or rates')
    dates = pd.date_range(start, end, freq='D')
    if len(dates) < 120:
        raise ValueError('The date range must cover at least 120 days')
    for sub in (*(f'extracted/{t}' for t in TABLES), 'ground_truth/row_labels'):
        (output / sub).mkdir(parents=True, exist_ok=True)
    roster = build_plants(seed, plants, len(dates))
    cfg = Config(seed, start, end, len(dates), plants, anomaly_rate, quality_scale, str(output),
                 tuple(p.code for p in roster))
    counts, multiplier = plan_counts(cfg, roster, target_rows / (1.0 + DUPLICATE_RATE * quality_scale))
    log(f'Planned {int(counts.sum())} points across {plants} plants (filler multiplier {multiplier:.3f})')
    installations = write_installations(cfg, roster, output)
    jobs = [(cfg, p, counts[p.index]) for p in roster]
    results = []
    if workers > 1:
        with Pool(workers) as pool:
            for result in pool.imap_unordered(generate_plant, jobs):
                results.append(result)
                if len(results) % 20 == 0:
                    log(f'{len(results)}/{plants} plants written')
    else:
        for job in jobs:
            results.append(generate_plant(job))
    return finish(cfg, results, installations, multiplier, output)


def finish(cfg, results, installations, multiplier, output):
    results.sort(key=lambda r: r['plant'])
    totals, per_kind = Counter(), {}
    for r in results:
        totals.update(r['totals'])
        for key, (rows, flagged) in r['per_kind'].items():
            stats = per_kind.setdefault(key, [0, 0])
            stats[0] += rows
            stats[1] += flagged
    episodes = pd.DataFrame([e for r in results for e in r['episodes']],
                            columns=['plant', 'source_file', 'MeasurementPointID', 'measurement_kind',
                                     'anomaly_type', 'start_date', 'end_date', 'rows', 'magnitude', 'episode_id'])
    write_gzip(Path(output) / 'ground_truth' / 'episodes.csv.gz', episodes.to_csv(index=False, lineterminator='\n'), 'utf-8')
    rows = totals.pop('rows')
    by_type = {LABEL_NAMES[c]: n for c, n in sorted(totals.items())}
    value_rows = sum(n for c, n in totals.items() if c < 20)
    quality_rows = sum(n for c, n in totals.items() if c >= 20)
    manifest = {
        'synthetic': True,
        'generator_version': GENERATOR_VERSION,
        'note': 'Fully simulated. No real measurement, point, plant or installation is represented.',
        'seed': cfg.seed, 'start': cfg.start, 'end': cfg.end, 'days': cfg.n_days, 'plants': cfg.plants,
        'installations': installations, 'filler_multiplier': round(multiplier, 4),
        'points': sum(r['points'] for r in results),
        'series_with_value_anomaly': sum(r['series_with_anomaly'] for r in results),
        'rows': rows, 'value_anomaly_rows': value_rows, 'quality_fault_rows': quality_rows,
        'anomalous_share': round((value_rows + quality_rows) / rows, 5),
        'value_anomaly_share': round(value_rows / rows, 5),
        'rows_by_label': by_type,
        'rows_by_kind': {k: {'rows': v[0], 'labelled': v[1]} for k, v in sorted(per_kind.items())},
        'parameters': {'anomaly_rate': cfg.anomaly_rate, 'quality_scale': cfg.quality_scale},
    }
    (Path(output) / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=Path('data/tai'),
                        help='New or empty directory; the tables go to <output>/extracted (default: where the pipeline and dashboard look)')
    parser.add_argument('--seed', type=int, default=20260101)
    parser.add_argument('--plants', type=int, default=335)
    parser.add_argument('--target-rows', type=int, default=25_000_000, help='Approximate rows in MeasurementValues')
    parser.add_argument('--start', default='2021-01-01')
    parser.add_argument('--end', default='2025-12-31')
    parser.add_argument('--anomaly-rate', type=float, default=0.105,
                        help='Target share of rows inside value-anomaly episodes (default 0.105)')
    parser.add_argument('--quality-scale', type=float, default=1.0, help='Multiplier on data-quality fault rates')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    manifest = run(args.output, args.seed, args.plants, args.target_rows, args.start, args.end,
                   args.anomaly_rate, args.quality_scale, args.workers)
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('rows_by_kind',)}, indent=2))


if __name__ == '__main__':
    main()
