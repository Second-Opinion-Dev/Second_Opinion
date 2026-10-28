#!/usr/bin/env python3
"""Score selected TAI measurements against their own prior daily history.

This is a provisional, history-only baseline. It does not infer causes, diagnose
faults, compare plants, or establish accuracy. Read docs/history_detector/HANDOFF.md.
"""

import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


SERIES_COLUMNS = [
    'InstallationCodeOrigin', 'MeasurementPointID', 'SubProcessCodeOrigin',
    'ProcessCode', 'Product', 'ProductBalance', 'InstallationCodeDestination',
    'SubProcessDestination', 'Unit',
]
QUALITY_FLAGS = [
    'flag_blank_value', 'flag_invalid_value', 'flag_invalid_date',
    'flag_unknown_point', 'flag_unknown_origin',
]
METADATA_COLUMNS = [
    'MeasurementPointID', 'ProductDescription', 'QuantityDescription',
    'ParameterDescription', 'Unit', 'InputType', 'StateDescription', 'source_file',
]
MEASUREMENTS = {
    'influent_volume': {
        'ProductDescription': 'Influent', 'QuantityDescription': 'Volume',
        'ParameterDescription': 'Niet van toepassing', 'Unit': 'm3', 'InputType': 'scada',
    },
    'oxygen': {
        'ProductDescription': 'Actief slib', 'QuantityDescription': '(massa)Concentratie',
        'ParameterDescription': 'zuurstof', 'Unit': 'mg/l', 'InputType': 'scada',
        'StateDescription': 'niet van toepassing',
    },
    'ammonium': {
        'ProductDescription': 'Actief slib', 'QuantityDescription': '(massa)Concentratie',
        'ParameterDescription': 'ammonium', 'Unit': 'mg/l', 'InputType': 'scada',
        'StateDescription': 'uitgedrukt in Stikstof',
    },
}
VALUE_COLUMNS = SERIES_COLUMNS + [
    'SubProcessDescription', 'Date', 'Value', 'source_file', 'source_row', 'parsed_date', 'parsed_value',
] + QUALITY_FLAGS
RULES = ['rule_stuck', 'rule_dropout', 'rule_negative']
RULE_REASONS = {'rule_stuck': 'stuck', 'rule_dropout': 'dropout', 'rule_negative': 'negative'}
SCALE_FACTOR = 1.4826


@dataclass(frozen=True)
class DetectorConfig:
    """Scoring settings. Alert thresholds are chosen separately; see Thresholds."""
    window_days: int = 28
    minimum_history: int = 14
    # Spread never falls below this share of the typical level, so tiny absolute
    # changes on small or quiet meters cannot produce extreme scores.
    scale_floor_fraction: float = 0.05
    # Values beyond median ± clip_limit × spread enter later history clipped, so a
    # sustained fault does not quickly become the new normal. 0 disables clipping.
    clip_limit: float = 3.5
    stuck_days: int = 7
    rules: bool = True
    # All current groups (volume, concentrations) cannot be negative.
    nonnegative: bool = True

    def validate(self) -> None:
        if self.window_days < 1 or not 1 <= self.minimum_history <= self.window_days:
            raise ValueError('minimum history must be between 1 and the window length')
        if not math.isfinite(self.scale_floor_fraction) or self.scale_floor_fraction < 0:
            raise ValueError('scale floor fraction must be finite and non-negative')
        if not math.isfinite(self.clip_limit) or self.clip_limit < 0:
            raise ValueError('clip limit must be finite and non-negative')
        if self.stuck_days < 2:
            raise ValueError('stuck days must be at least 2')


@dataclass(frozen=True)
class Thresholds:
    """Separate alert thresholds for readings above and below the typical value."""
    above: float
    below: float
    method: str = 'fixed'

    def validate(self) -> None:
        for value in (self.above, self.below):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('thresholds must be finite positive numbers')


@dataclass(frozen=True)
class SeriesThresholds:
    """Per-series thresholds; series without their own use the fallback."""
    table: pd.DataFrame  # SERIES_COLUMNS + threshold_above, threshold_below
    fallback: Thresholds


# Reproduces the original detector: no floor, no clipping, no rules, fixed 3.5.
LEGACY_CONFIG = DetectorConfig(scale_floor_fraction=0.0, clip_limit=0.0, rules=False)
LEGACY_THRESHOLDS = Thresholds(3.5, 3.5, 'fixed')
# A calibrated threshold never flags readings within this many spreads of the median.
MINIMUM_THRESHOLD = 2.0
# Series need this many scored calibration readings for their own thresholds.
MINIMUM_CALIBRATION_ROWS = 100


def select_points(metadata: pd.DataFrame, measurement: str = 'influent_volume') -> pd.DataFrame:
    """Select the proposed exploratory slice; its semantics are unconfirmed."""
    missing = set(METADATA_COLUMNS) - set(metadata.columns)
    if missing:
        raise ValueError(f'Missing point metadata columns: {sorted(missing)}')
    if metadata['MeasurementPointID'].eq('').any():
        raise ValueError('Point metadata contains blank point identifiers')
    if metadata['MeasurementPointID'].duplicated().any():
        raise ValueError('Point metadata contains duplicate identifiers; resolve before scoring')
    if measurement not in MEASUREMENTS:
        raise ValueError(f'Unknown measurement group: {measurement}')
    mask = pd.Series(True, index=metadata.index)
    for field, expected in MEASUREMENTS[measurement].items():
        # Match units exactly; never silently mix or convert units.
        actual = metadata[field].str.strip()
        mask &= actual.eq(expected) if field == 'Unit' else actual.str.casefold().eq(expected.casefold())
    return metadata.loc[mask].copy()


def score_series(frame: pd.DataFrame, config: DetectorConfig,
                 thresholds: Thresholds | None = None) -> pd.DataFrame:
    """Score a single context with only valid, unambiguous earlier dates.

    Same-date valid rows are quarantined as a group. Eligible observations enter
    later windows, clipped to the robust range when clipping is enabled; no
    imputation occurs. Flags are added only when thresholds are supplied.
    """
    config.validate()
    result = frame.copy()
    result['_date'] = pd.to_datetime(result['parsed_date'], errors='coerce').dt.normalize()
    result['_number'] = pd.to_numeric(result['parsed_value'], errors='coerce')
    valid_flag = pd.Series(True, index=result.index)
    for col in QUALITY_FLAGS:
        # Accept only explicit False; an absent or unrecognised flag is unsafe.
        valid_flag &= result[col].astype(str).str.strip().str.casefold().eq('false')
    finite = pd.Series(np.isfinite(result['_number'].to_numpy(dtype=float)), index=result.index)
    valid_date = result['_date'].notna()
    candidate = valid_date & finite & valid_flag
    # Only otherwise-valid rows make a day ambiguous; a blank or flagged row does not.
    same_day = candidate & result['_date'].where(candidate).duplicated(keep=False)
    status = pd.Series('unscored_quality_flag', index=result.index, dtype=object)
    status[~valid_date] = 'unscored_invalid_date'
    status[valid_date & ~finite] = 'unscored_invalid_value'
    status[same_day] = 'unscored_ambiguous_same_day'
    eligible = candidate & ~same_day
    ordered = result.loc[eligible].sort_values('_date', kind='stable')

    n = len(ordered)
    out = {name: np.full(n, np.nan) for name in ('median', 'mad', 'scale', 'signed')}
    days_out = np.zeros(n, dtype=int)
    repeat_out = np.zeros(n, dtype=int)
    rule_out = {name: np.zeros(n, dtype=bool) for name in RULES}
    status_out = np.empty(n, dtype=object)
    history = deque()  # (day, value used as history, raw value)
    window = pd.Timedelta(days=config.window_days)
    previous_day = previous_value = None
    run_length, run_varied = 0, False
    dates = ordered['_date'].to_numpy()
    numbers = ordered['_number'].to_numpy(dtype=float)
    for i in range(n):
        day, number = pd.Timestamp(dates[i]), float(numbers[i])
        # Interval [day - window, day): the current observation never enters its own baseline.
        while history and history[0][0] < day - window:
            history.popleft()
        values = np.fromiter((entry[1] for entry in history), dtype=float, count=len(history))
        days_out[i] = len(values)
        enough = len(values) >= config.minimum_history
        median = mad = scale = np.nan
        if enough:
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            scale = max(SCALE_FACTOR * mad, config.scale_floor_fraction * abs(median))
            out['median'][i], out['mad'][i], out['scale'][i] = median, mad, scale

        if previous_day is not None and (day - previous_day).days == 1 and number == previous_value:
            run_length += 1
        else:
            # A run counts as stuck only if the meter varied before the run began.
            run_length, run_varied = 1, bool(enough and mad > 0)
        repeat_out[i] = run_length
        if config.rules:
            rule_out['rule_stuck'][i] = run_length >= config.stuck_days and run_varied
            rule_out['rule_dropout'][i] = (number == 0 and enough
                                           and not any(entry[2] == 0 for entry in history))
            rule_out['rule_negative'][i] = config.nonnegative and number < 0

        if not enough:
            status_out[i] = 'unscored_insufficient_history'
        elif scale == 0:
            status_out[i] = 'unscored_zero_spread'
        else:
            out['signed'][i] = (number - median) / scale
            status_out[i] = 'scored'
        stored = number
        if config.clip_limit and enough and scale > 0:
            stored = min(max(number, median - config.clip_limit * scale), median + config.clip_limit * scale)
        history.append((day, stored, number))
        previous_day, previous_value = day, number

    index = ordered.index
    status[index] = status_out
    result['history_days'] = pd.Series(pd.NA, index=result.index, dtype='Int64')
    result.loc[index, 'history_days'] = days_out
    for name, column in (('median', 'history_median'), ('mad', 'history_mad'), ('scale', 'history_scale')):
        result[column] = np.nan
        result.loc[index, column] = out[name]
    signed = pd.Series(np.nan, index=result.index)
    signed[index] = out['signed']
    result['anomaly_score'] = signed.abs()
    result['direction'] = np.select([signed > 0, signed < 0, signed == 0], ['above', 'below', 'at'], '')
    result['repeat_days'] = pd.Series(pd.NA, index=result.index, dtype='Int64')
    result.loc[index, 'repeat_days'] = repeat_out
    for name in RULES:
        result[name] = pd.Series(pd.NA, index=result.index, dtype='boolean')
        result.loc[index, name] = rule_out[name]
    result['score_status'] = status
    result = result.drop(columns=['_date', '_number'])
    return apply_thresholds(result, thresholds) if thresholds is not None else result


def row_thresholds(frame: pd.DataFrame, thresholds: Thresholds | SeriesThresholds) -> pd.DataFrame:
    """Return the above/below threshold that applies to each row."""
    if isinstance(thresholds, Thresholds):
        thresholds.validate()
        return pd.DataFrame({'threshold_above': thresholds.above, 'threshold_below': thresholds.below},
                            index=frame.index)
    thresholds.fallback.validate()
    keys = frame[SERIES_COLUMNS].astype(str)
    table = thresholds.table.astype({column: str for column in SERIES_COLUMNS})
    merged = keys.merge(table, on=SERIES_COLUMNS, how='left', validate='many_to_one')
    merged.index = frame.index
    return pd.DataFrame({
        'threshold_above': merged['threshold_above'].fillna(thresholds.fallback.above),
        'threshold_below': merged['threshold_below'].fillna(thresholds.fallback.below)})


def apply_thresholds(frame: pd.DataFrame, thresholds: Thresholds | SeriesThresholds) -> pd.DataFrame:
    """Add statistical flags, the combined review flag, reasons and explanations."""
    result = frame.copy()
    limits = row_thresholds(result, thresholds)
    result['threshold_above'], result['threshold_below'] = limits['threshold_above'], limits['threshold_below']
    scored = result['score_status'].eq('scored')
    score = pd.to_numeric(result['anomaly_score'], errors='coerce')
    high = scored & result['direction'].eq('above') & score.ge(result['threshold_above'])
    low = scored & result['direction'].eq('below') & score.ge(result['threshold_below'])
    result['anomaly_flag'] = pd.Series(pd.NA, index=result.index, dtype='boolean')
    result.loc[scored, 'anomaly_flag'] = (high | low)[scored]
    rules = result[RULES].astype('boolean')
    rule_any = rules.fillna(False).any(axis=1)
    # Rows never assessed (invalid, ambiguous) keep a blank review flag, not False.
    assessed = scored | rules.notna().all(axis=1)
    result['review_flag'] = pd.Series(pd.NA, index=result.index, dtype='boolean')
    result.loc[assessed, 'review_flag'] = (high | low | rule_any)[assessed]
    reasons = {RULE_REASONS[name]: rules[name].fillna(False).to_numpy(dtype=bool) for name in RULES}
    reasons.update({'unusual_high': high.to_numpy(dtype=bool), 'unusual_low': low.to_numpy(dtype=bool)})
    text = pd.Series('', index=result.index, dtype=object)
    for name, mask in reasons.items():
        text = text + np.where(mask, name + ';', '')
    result['flag_reason'] = text.str.rstrip(';')
    explanations = {
        'unscored_quality_flag': 'Input quality flag requires review.',
        'unscored_invalid_date': 'The observation has no valid date.',
        'unscored_invalid_value': 'The observation has no finite numerical value.',
        'unscored_ambiguous_same_day': 'Multiple valid observations share this series and date.',
        'unscored_insufficient_history': 'Insufficient valid prior days in the history window.',
        'unscored_zero_spread': 'Prior values are constant at zero; no robust spread is available.',
        'scored': 'Compare the observed value with its prior median and robust spread.',
    }
    result['explanation'] = result['score_status'].map(explanations).fillna('')
    rule_text = {'stuck': 'Value repeated on consecutive days after a varying history.',
                 'dropout': 'Zero after a prior window without zeros.',
                 'negative': 'Negative value for a quantity that cannot be negative.'}
    for name, message in rule_text.items():
        mask = reasons[name]
        result.loc[mask, 'explanation'] = message + ' ' + result.loc[mask, 'explanation']
    return result


def direction_thresholds(rows: pd.DataFrame, target_flag_rate: float) -> tuple[float, float] | None:
    """Thresholds that flag about half the target rate of `rows` in each direction.

    Splitting by direction gives a heavy upward tail (for example wet-weather
    influent) a higher threshold than drops. Never below MINIMUM_THRESHOLD.
    """
    per_direction = max(1, int(round(target_flag_rate / 2 * len(rows))))
    chosen = []
    for direction in ('above', 'below'):
        scores = np.sort(pd.to_numeric(rows.loc[rows['direction'].eq(direction), 'anomaly_score']).to_numpy())[::-1]
        if len(scores) == 0:
            return None
        chosen.append(max(float(scores[min(per_direction, len(scores)) - 1]), MINIMUM_THRESHOLD))
    return chosen[0], chosen[1]


def calibrate_thresholds(frame: pd.DataFrame, calibration_end: str, target_flag_rate: float) -> SeriesThresholds:
    """Choose above/below thresholds per series on its own scored rows up to calibration_end.

    Each meter is then flagged on about the target share of its calibration days,
    so erratic meters cannot set the bar for calm ones. Series with fewer than
    MINIMUM_CALIBRATION_ROWS use the median of the other series' thresholds.
    """
    if not 0 < target_flag_rate < 1:
        raise ValueError('target flag rate must be between 0 and 1')
    dates = pd.to_datetime(frame['parsed_date'], errors='coerce').dt.normalize()
    rows = frame.loc[frame['score_status'].eq('scored') & dates.le(pd.Timestamp(calibration_end))]
    records = []
    for key, group in rows.groupby(SERIES_COLUMNS, dropna=False, sort=True):
        chosen = direction_thresholds(group, target_flag_rate) if len(group) >= MINIMUM_CALIBRATION_ROWS else None
        if chosen is not None:
            records.append({**dict(zip(SERIES_COLUMNS, key)), 'threshold_above': chosen[0],
                            'threshold_below': chosen[1], 'calibration_rows': len(group)})
    if not records:
        raise ValueError(f'No series has {MINIMUM_CALIBRATION_ROWS} scored calibration rows; use a fixed threshold')
    table = pd.DataFrame(records)
    fallback = Thresholds(float(table['threshold_above'].median()), float(table['threshold_below'].median()),
                          'median_of_series')
    return SeriesThresholds(table, fallback)


def build_cases(frame: pd.DataFrame, gap_days: int = 1) -> tuple[pd.Series, pd.DataFrame]:
    """Group review-flagged days per series into cases; return case ids and a case table.

    Consecutive flagged days, allowing up to gap_days unflagged or missing days
    between them, form one case. A case is a review prompt, not a confirmed event.
    """
    case_ids = pd.Series('', index=frame.index, dtype=object)
    flagged = frame.loc[frame['review_flag'].fillna(False).astype(bool)].copy()
    if flagged.empty:
        return case_ids, pd.DataFrame()
    flagged['_date'] = pd.to_datetime(flagged['parsed_date'], errors='coerce').dt.normalize()
    flagged['_score'] = pd.to_numeric(flagged['anomaly_score'], errors='coerce')
    flagged = flagged.sort_values(SERIES_COLUMNS + ['_date'], kind='stable')
    new_series = flagged[SERIES_COLUMNS].ne(flagged[SERIES_COLUMNS].shift()).any(axis=1)
    gap = flagged['_date'].diff().dt.days.gt(gap_days + 1)
    flagged['_case'] = (new_series | gap).cumsum()
    rows, members = [], []
    for _, case in flagged.groupby('_case', sort=False):
        peak = case.loc[case['_score'].idxmax()] if case['_score'].notna().any() else case.iloc[0]
        reasons = sorted({part for text in case['flag_reason'] for part in text.split(';') if part})
        first = case.iloc[0]
        rows.append({
            'case_id': f"{first['MeasurementPointID']}:{first['_date']:%Y-%m-%d}",
            **{column: first[column] for column in SERIES_COLUMNS},
            'SubProcessDescription': first.get('SubProcessDescription', ''),
            'start_date': f"{case['_date'].min():%Y-%m-%d}", 'end_date': f"{case['_date'].max():%Y-%m-%d}",
            'flagged_days': len(case), 'peak_date': f"{peak['_date']:%Y-%m-%d}",
            'peak_value': peak['parsed_value'], 'peak_score': peak['_score'],
            'peak_direction': peak['direction'], 'peak_median': peak['history_median'],
            'reasons': ';'.join(reasons),
            'priority_tier': 1 if set(reasons) & set(RULE_REASONS.values()) else 2,
        })
        members.append(case.index)
    cases = pd.DataFrame(rows)
    repeat = cases.groupby('case_id').cumcount()
    cases.loc[repeat.gt(0), 'case_id'] += ':' + repeat[repeat.gt(0)].astype(str)
    for case_id, index in zip(cases['case_id'], members):
        case_ids[index] = case_id
    return case_ids, rank_cases(cases)


def rank_cases(cases: pd.DataFrame) -> pd.DataFrame:
    """Rank cases within each plant: rule hits, then longer cases, then higher peak score.

    The order is a documented review priority, not a probability or severity.
    """
    ordered = cases.sort_values(
        ['InstallationCodeOrigin', 'priority_tier', 'flagged_days', 'peak_score', 'start_date', 'case_id'],
        ascending=[True, True, False, False, False, True], na_position='last', kind='stable').copy()
    ordered['plant_rank'] = ordered.groupby('InstallationCodeOrigin').cumcount() + 1
    return ordered.reset_index(drop=True)


def load_selected(prepared: Path, measurement: str, max_points: int | None = None) -> pd.DataFrame:
    """Load every prepared row for the selected points, with provenance checks.

    max_points keeps the first N selected point IDs and reads only their files;
    it is for quick smoke runs, never for reported results.
    """
    if not (prepared / 'summary.json').is_file():
        raise ValueError('Preparation summary missing; pipeline may be incomplete')
    summary = json.loads((prepared / 'summary.json').read_text(encoding='utf-8'))
    if summary.get('file_limit_per_table') is not None:
        raise ValueError('Partial preparation output is not a full detector input')
    metadata_path = prepared / 'point_metadata.csv.gz'
    value_dir = prepared / 'cleaned' / 'MeasurementValues'
    if not metadata_path.is_file() or not value_dir.is_dir():
        raise ValueError('Prepared point metadata or measurement values are missing')
    metadata = pd.read_csv(metadata_path, dtype=str, keep_default_na=False)
    selected = select_points(metadata, measurement)
    if selected.empty:
        raise ValueError('No points match the exploratory selection')
    if max_points is not None:
        selected = selected.sort_values('MeasurementPointID').head(max_points)
    selected_ids = set(selected['MeasurementPointID'])
    file_for_point = dict(zip(selected['MeasurementPointID'], selected['source_file']))
    meta_units = dict(zip(selected['MeasurementPointID'], selected['Unit']))
    selected_metadata = selected.set_index('MeasurementPointID')
    files = sorted(value_dir.glob('*.csv.gz'))
    if max_points is not None:
        needed = {Path(name).name for name in selected['source_file']}
        files = [path for path in files if path.name in needed]
    if not files:
        raise ValueError('No prepared measurement files found')
    frames = []
    for path in files:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=VALUE_COLUMNS)
        frame = frame.loc[frame['MeasurementPointID'].isin(selected_ids)].copy()
        if frame.empty:
            continue
        # Global uniqueness and per-file alignment prevent fragmented histories.
        expected = frame['MeasurementPointID'].map(file_for_point).str.replace(
            'MeasurementPoints/', 'MeasurementValues/', regex=False)
        if not frame['source_file'].eq(expected).all():
            raise ValueError('A selected point occurs outside its matching metadata file')
        if not frame['Unit'].eq(frame['MeasurementPointID'].map(meta_units)).all():
            raise ValueError('Value and point metadata units differ; review before scoring')
        for column in ('ProductDescription', 'QuantityDescription', 'ParameterDescription', 'InputType', 'StateDescription'):
            frame[column] = frame['MeasurementPointID'].map(selected_metadata[column])
        frames.append(frame)
    if not frames:
        raise ValueError('Selected points have no observations; output is incomplete')
    return pd.concat(frames, ignore_index=True)


def score_all(frame: pd.DataFrame, config: DetectorConfig) -> pd.DataFrame:
    """Score every series separately; no data crosses between series."""
    parts = [score_series(group, config) for _, group in
             frame.groupby(SERIES_COLUMNS, dropna=False, sort=False)]
    return pd.concat(parts).sort_index()


def threshold_summary(thresholds: Thresholds | SeriesThresholds) -> dict:
    if isinstance(thresholds, Thresholds):
        return {'method': thresholds.method, 'above': thresholds.above, 'below': thresholds.below}
    table = thresholds.table
    quantiles = lambda column: {f'p{int(q * 100)}': float(table[column].quantile(q)) for q in (0.1, 0.5, 0.9)}
    return {'method': 'per_series', 'series_with_own_thresholds': len(table),
            'above': quantiles('threshold_above'), 'below': quantiles('threshold_below'),
            'fallback': asdict(thresholds.fallback), 'minimum_threshold': MINIMUM_THRESHOLD,
            'minimum_calibration_rows': MINIMUM_CALIBRATION_ROWS}


def run(prepared: Path, output: Path, config: DetectorConfig, measurement: str = 'influent_volume',
        fixed_threshold: float | None = None, calibration_end: str = '2023-12-31',
        target_flag_rate: float = 0.01, case_gap_days: int = 1, max_points: int | None = None) -> None:
    config.validate()
    prepared, output = prepared.resolve(), output.resolve()
    if prepared == output or prepared in output.parents or output in prepared.parents:
        raise ValueError('Prepared inputs and output must be separate directories')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; choose a new path')
    scored = score_all(load_selected(prepared, measurement, max_points), config)
    if fixed_threshold is not None:
        thresholds = Thresholds(fixed_threshold, fixed_threshold, 'fixed')
    else:
        thresholds = calibrate_thresholds(scored, calibration_end, target_flag_rate)
    scored = apply_thresholds(scored, thresholds)
    scored['case_id'], cases = build_cases(scored, case_gap_days)
    output.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output / 'history_scores.csv.gz', index=False, compression='gzip')
    cases.to_csv(output / 'cases.csv.gz', index=False, compression='gzip')
    if isinstance(thresholds, SeriesThresholds):
        thresholds.table.to_csv(output / 'thresholds.csv', index=False)
    counts = Counter({'selected_rows': len(scored)})
    counts.update(scored['score_status'].value_counts().to_dict())
    counts['flagged'] = int(scored['anomaly_flag'].fillna(False).sum())
    counts['review_flagged'] = int(scored['review_flag'].fillna(False).sum())
    for name in RULES:
        counts[name] = int(scored[name].fillna(False).sum())
    counts['cases'] = len(cases)
    run_info = {
        'status': 'provisional_unvalidated' if max_points is None else 'smoke_run_partial',
        'max_points': max_points,
        'input_preparation_summary': str(prepared / 'summary.json'),
        'measurement': measurement,
        'selection': MEASUREMENTS[measurement],
        'selection_semantics': 'exploratory; exact operational meaning not confirmed by TAI',
        'config': asdict(config), 'scale_factor': SCALE_FACTOR,
        'thresholds': threshold_summary(thresholds),
        'calibration': None if fixed_threshold is not None else {
            'calibration_end': calibration_end, 'target_flag_rate': target_flag_rate,
            'note': 'Per-series workload assumption split equally between directions; not an observed prevalence.'},
        'case_gap_days': case_gap_days,
        'counts': dict(counts), 'pandas_version': pd.__version__, 'numpy_version': np.__version__,
        'limitations': ['No peer comparison; each series uses only its own history.',
                        'Threshold target rate is a workload assumption, not a validated false-alarm rate.',
                        'Rules and scores are review prompts, not diagnoses or verified anomalies.',
                        'Dates and input availability require partner confirmation.'],
    }
    (output / 'run_info.json').write_text(json.dumps(run_info, indent=2), encoding='utf-8')
    print('Historical scoring complete. Outputs are private and provisional.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True, help='Completed full TAI preparation directory')
    parser.add_argument('--output', type=Path, required=True, help='New or empty private output directory')
    parser.add_argument('--window-days', type=int, default=28)
    parser.add_argument('--minimum-history', type=int, default=14)
    parser.add_argument('--measurement', choices=sorted(MEASUREMENTS), default='influent_volume',
                        help='Exploratory metadata group; defaults to the original influent volume slice')
    parser.add_argument('--scale-floor-fraction', type=float, default=0.05,
                        help='Minimum spread as a share of the absolute median; 0 disables')
    parser.add_argument('--clip-limit', type=float, default=3.5,
                        help='Clip values entering later history to median ± limit × spread; 0 disables')
    parser.add_argument('--stuck-days', type=int, default=7)
    parser.add_argument('--no-rules', action='store_true', help='Disable stuck, dropout and negative rules')
    parser.add_argument('--calibration-end', default='2023-12-31',
                        help='Last date used to choose thresholds')
    parser.add_argument('--target-flag-rate', type=float, default=0.01,
                        help='Share of calibration readings flagged, split between above and below')
    parser.add_argument('--threshold', type=float,
                        help='Fixed threshold for both directions instead of calibration')
    parser.add_argument('--case-gap-days', type=int, default=1,
                        help='Unflagged days allowed inside one case')
    parser.add_argument('--max-points', type=int,
                        help='Smoke run on the first N selected points only; output is marked partial')
    args = parser.parse_args()
    config = DetectorConfig(args.window_days, args.minimum_history, args.scale_floor_fraction,
                            args.clip_limit, args.stuck_days, not args.no_rules)
    run(args.prepared, args.output, config, args.measurement, args.threshold,
        args.calibration_end, args.target_flag_rate, args.case_gap_days, args.max_points)


if __name__ == '__main__':
    main()
