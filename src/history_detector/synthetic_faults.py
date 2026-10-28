#!/usr/bin/env python3
"""Compare detector settings on artificial faults injected into copies of held-out data.

Each sampled series is copied, one artificial fault is written into the copy in
the held-out year, and every detector variant scores the same copy with
thresholds frozen on unmodified data. Results describe recovery of synthetic
faults only; they are not real-world accuracy or false-alarm rates.
"""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:  # imported from the repository root, e.g. by tests
    from history_detector.history_detector import (
        LEGACY_CONFIG, LEGACY_THRESHOLDS, SCALE_FACTOR, SERIES_COLUMNS, DetectorConfig, apply_thresholds,
        build_cases, calibrate_thresholds, config_for, load_selected, score_all, score_series,
        threshold_summary)
except ModuleNotFoundError:  # run as a script from this folder
    from history_detector import (
        LEGACY_CONFIG, LEGACY_THRESHOLDS, SCALE_FACTOR, SERIES_COLUMNS, DetectorConfig, apply_thresholds,
        build_cases, calibrate_thresholds, config_for, load_selected, score_all, score_series,
        threshold_summary)

# Fault length in days and how each one changes the copied values.
FAULT_DAYS = {'spike': 1, 'dropout': 3, 'stuck': 10, 'drift': 28}
SPIKE_SPREADS = 6.0   # one-day jump of six robust spreads
DRIFT_SPREADS = 4.0   # linear drift reaching four robust spreads after 28 days
# Rows this long before the held-out year give every window and rule a full history.
WARMUP_DAYS = 60


def variants(calibration_end: str, target_flag_rate: float, measurement: str) -> dict:
    revised = config_for(DetectorConfig(), measurement)
    return {
        'legacy': (config_for(LEGACY_CONFIG, measurement), None),
        'revised': (revised, (calibration_end, target_flag_rate)),
        'revised_no_clip': (replace(revised, clip_limit=0.0), (calibration_end, target_flag_rate)),
    }


def eligible_positions(dates: pd.Series, length: int, test_start, test_end) -> np.ndarray:
    """Start positions whose next `length` rows are consecutive days inside the held-out year."""
    days = dates.to_numpy(dtype='datetime64[D]')
    starts = []
    for i in range(len(days) - length + 1):
        if days[i] < np.datetime64(test_start) or days[i + length - 1] > np.datetime64(test_end):
            continue
        if (days[i + length - 1] - days[i]).astype(int) == length - 1:
            starts.append(i)
    return np.asarray(starts, dtype=int)


def inject(series: pd.DataFrame, kind: str, start: int, spread: float) -> pd.DataFrame:
    """Return a copy with one artificial fault; the original rows are not modified."""
    copy = series.copy()
    length = FAULT_DAYS[kind]
    rows = copy.index[start:start + length]
    values = pd.to_numeric(copy.loc[rows, 'parsed_value'])
    if kind == 'spike':
        values = values + SPIKE_SPREADS * spread
    elif kind == 'dropout':
        values = values * 0.0
    elif kind == 'stuck':
        values = pd.Series(values.iloc[0], index=rows)
    elif kind == 'drift':
        values = values + np.linspace(DRIFT_SPREADS * spread / length, DRIFT_SPREADS * spread, length)
    copy.loc[rows, 'parsed_value'] = values.to_numpy(dtype=float).astype(str)
    return copy


def untouched_summary(scored: pd.DataFrame, test_start: str, test_end: str) -> dict:
    """Review workload on the unmodified held-out year, per meter-year."""
    dates = pd.to_datetime(scored['parsed_date'], errors='coerce')
    test = scored.loc[dates.between(test_start, test_end)].copy()
    meters = test['MeasurementPointID'].nunique()
    _, cases = build_cases(test)
    return {
        'meters': meters, 'readings': int(len(test)),
        'review_flagged_readings': int(test['review_flag'].fillna(False).sum()),
        'review_flag_rate': float(test['review_flag'].fillna(False).mean()),
        'cases': int(len(cases)),
        'cases_per_meter_year': float(len(cases) / meters) if meters else None,
        'cases_by_reason': {} if cases.empty else
            {str(k): int(v) for k, v in cases['reasons'].str.split(';').explode().value_counts().items()},
    }


def run(prepared: Path, output: Path, measurement: str, seed: int, sample: int,
        test_start: str, test_end: str, calibration_end: str, target_flag_rate: float,
        max_points: int | None = None) -> None:
    prepared, output = prepared.resolve(), output.resolve()
    if prepared == output or prepared in output.parents or output in prepared.parents:
        raise ValueError('Prepared inputs and output must be separate directories')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; choose a new path')
    frame = load_selected(prepared, measurement, max_points)
    settings = {}
    for name, (config, calibration) in variants(calibration_end, target_flag_rate, measurement).items():
        scored = score_all(frame, config)
        thresholds = LEGACY_THRESHOLDS if calibration is None else calibrate_thresholds(scored, *calibration)
        settings[name] = {'config': config, 'thresholds': thresholds,
                          'untouched': untouched_summary(apply_thresholds(scored, thresholds), test_start, test_end)}
        print(f'{name}: scored unmodified data', flush=True)

    rng = np.random.default_rng(seed)
    warmup_start = pd.Timestamp(test_start) - pd.Timedelta(days=WARMUP_DAYS)
    groups = list(frame.groupby(SERIES_COLUMNS, dropna=False, sort=True))
    order = rng.permutation(len(groups))
    records, used = [], 0
    for position in order:
        if used >= sample:
            break
        _, series = groups[position]
        series = series.assign(_date=pd.to_datetime(series['parsed_date'], errors='coerce'),
                               _value=pd.to_numeric(series['parsed_value'], errors='coerce'))
        series = series.loc[series['_date'].ge(warmup_start) & series['_date'].le(test_end)
                            & series['_value'].notna()].sort_values('_date')
        series = series.loc[~series['_date'].duplicated(keep=False)]
        before = series.loc[series['_date'].lt(test_start), '_value']
        if len(before) < 28:
            continue
        level = float(before.median())
        spread = SCALE_FACTOR * float((before - level).abs().median())
        series = series.drop(columns=['_date', '_value'])
        dates = pd.to_datetime(series['parsed_date'])
        used += 1
        for kind, length in FAULT_DAYS.items():
            if kind in ('spike', 'drift') and spread == 0:
                continue
            if kind == 'dropout' and level <= 0:
                continue
            starts = eligible_positions(dates, length, test_start, test_end)
            if len(starts) == 0:
                continue
            start = int(rng.choice(starts))
            faulty = inject(series, kind, start, spread)
            fault_start, fault_end = dates.iloc[start], dates.iloc[start + length - 1]
            for name, setting in settings.items():
                result = score_series(faulty, setting['config'], setting['thresholds'])
                in_window = pd.to_datetime(result['parsed_date']).between(fault_start, fault_end)
                hits = result.loc[in_window & result['review_flag'].fillna(False).astype(bool)]
                first = pd.to_datetime(hits['parsed_date']).min() if len(hits) else None
                records.append({
                    'variant': name, 'fault': kind, 'series': used, 'fault_start': f'{fault_start:%Y-%m-%d}',
                    'fault_days': length, 'detected': bool(len(hits)),
                    'days_to_first_flag': None if first is None else int((first - fault_start).days),
                    'flagged_days_in_fault': int(len(hits)),
                    'reasons': ';'.join(sorted({p for r in hits['flag_reason'] for p in r.split(';') if p})),
                })
    if not records:
        raise ValueError('No series were eligible for fault injection')
    results = pd.DataFrame(records)
    summary = (results.groupby(['variant', 'fault'])
               .agg(injected=('detected', 'size'), detected=('detected', 'sum'),
                    median_days_to_first_flag=('days_to_first_flag', 'median'))
               .reset_index())
    summary['detection_rate'] = summary['detected'] / summary['injected']
    output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / 'injections.csv', index=False)
    report = {
        'status': 'synthetic_faults_only' if max_points is None else 'smoke_run_partial',
        'max_points': max_points,
        'measurement': measurement, 'seed': seed, 'series_sampled': used,
        'held_out_period': [test_start, test_end], 'warmup_days': WARMUP_DAYS,
        'faults': {'days': FAULT_DAYS, 'spike_spreads': SPIKE_SPREADS, 'drift_spreads': DRIFT_SPREADS,
                   'spread_basis': 'robust spread of the series in the warm-up period before the held-out year'},
        'variants': {name: {'config': asdict(s['config']), 'thresholds': threshold_summary(s['thresholds']),
                            'untouched_held_out': s['untouched']} for name, s in settings.items()},
        'detection': summary.to_dict(orient='records'),
        'interpretation': ('Recovery of artificial faults in copies of held-out data, and workload on '
                           'unmodified held-out data. Not real-world precision, recall or false-alarm rates.'),
    }
    (output / 'summary.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    print(summary.to_string(index=False))
    print('Synthetic fault comparison complete. Outputs are private.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New or empty private output directory')
    parser.add_argument('--measurement', default='influent_volume')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--sample', type=int, default=100, help='Number of series to inject faults into')
    parser.add_argument('--test-start', default='2025-01-01')
    parser.add_argument('--test-end', default='2025-12-31')
    parser.add_argument('--calibration-end', default='2023-12-31')
    parser.add_argument('--target-flag-rate', type=float, default=0.01)
    parser.add_argument('--max-points', type=int,
                        help='Smoke run on the first N selected points only; output is marked partial')
    args = parser.parse_args()
    run(args.prepared, args.output, args.measurement, args.seed, args.sample, args.test_start,
        args.test_end, args.calibration_end, args.target_flag_rate, args.max_points)


if __name__ == '__main__':
    main()
