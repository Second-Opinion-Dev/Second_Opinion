#!/usr/bin/env python3
"""Score selected TAI measurements against their own prior daily history.

This is a provisional, history-only baseline. It does not infer causes, diagnose
faults, compare plants, or establish accuracy. Read history_detector/HANDOFF.md.
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
    'ParameterDescription', 'Unit', 'InputType', 'source_file',
]
VALUE_COLUMNS = SERIES_COLUMNS + [
    'SubProcessDescription', 'Date', 'Value', 'source_file', 'source_row', 'parsed_date', 'parsed_value',
] + QUALITY_FLAGS


@dataclass(frozen=True)
class DetectorConfig:
    window_days: int = 28
    minimum_history: int = 14
    threshold: float = 3.5

    def validate(self) -> None:
        if self.window_days < 1 or not 1 <= self.minimum_history <= self.window_days:
            raise ValueError('minimum history must be between 1 and the window length')
        if not math.isfinite(self.threshold) or self.threshold <= 0:
            raise ValueError('threshold must be a finite positive number')


def select_points(metadata: pd.DataFrame) -> pd.DataFrame:
    """Select the proposed exploratory slice; its semantics are unconfirmed."""
    missing = set(METADATA_COLUMNS) - set(metadata.columns)
    if missing:
        raise ValueError(f'Missing point metadata columns: {sorted(missing)}')
    if metadata['MeasurementPointID'].eq('').any():
        raise ValueError('Point metadata contains blank point identifiers')
    if metadata['MeasurementPointID'].duplicated().any():
        raise ValueError('Point metadata contains duplicate identifiers; resolve before scoring')
    selected = metadata[
        metadata['ProductDescription'].str.strip().str.casefold().eq('influent')
        & metadata['QuantityDescription'].str.strip().str.casefold().eq('volume')
        & metadata['ParameterDescription'].str.strip().str.casefold().eq('niet van toepassing')
        & metadata['Unit'].str.strip().eq('m3')
        & metadata['InputType'].str.strip().str.casefold().eq('scada')
    ].copy()
    return selected


def score_series(frame: pd.DataFrame, config: DetectorConfig) -> pd.DataFrame:
    """Score a single context with only valid, unambiguous earlier dates.

    Same-date rows are quarantined as a group. All eligible observations,
    including previously flagged values, enter later windows; no imputation occurs.
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
    same_day = valid_date & result.duplicated('_date', keep=False)
    result['history_days'] = pd.Series(pd.NA, index=result.index, dtype='Int64')
    result['history_median'] = np.nan
    result['history_mad'] = np.nan
    result['anomaly_score'] = np.nan
    result['anomaly_flag'] = pd.Series(pd.NA, index=result.index, dtype='boolean')
    result['direction'] = ''
    result['score_status'] = 'unscored_quality_flag'
    result.loc[~valid_date, 'score_status'] = 'unscored_invalid_date'
    result.loc[valid_date & ~finite, 'score_status'] = 'unscored_invalid_value'
    result.loc[same_day, 'score_status'] = 'unscored_ambiguous_same_day'
    eligible = valid_date & finite & valid_flag & ~same_day
    ordered = result.loc[eligible].sort_values('_date', kind='stable')
    history = deque()
    window = pd.Timedelta(days=config.window_days)
    for index, day, number in ordered[['_date', '_number']].itertuples(index=True, name=None):
        # Interval [day - window, day): the current observation never enters its own baseline.
        while history and history[0][0] < day - window:
            history.popleft()
        values = np.asarray([entry[1] for entry in history], dtype=float)
        result.at[index, 'history_days'] = len(values)
        if len(values) < config.minimum_history:
            result.at[index, 'score_status'] = 'unscored_insufficient_history'
        else:
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            result.at[index, 'history_median'] = median
            result.at[index, 'history_mad'] = mad
            if mad == 0:
                result.at[index, 'score_status'] = 'unscored_zero_mad'
            else:
                score = abs(float(number) - median) / (1.4826 * mad)
                result.at[index, 'anomaly_score'] = score
                result.at[index, 'anomaly_flag'] = score >= config.threshold
                result.at[index, 'score_status'] = 'scored'
                result.at[index, 'direction'] = 'above' if number > median else ('below' if number < median else 'at')
        history.append((day, float(number)))
    explanations = {
        'unscored_quality_flag': 'Input quality flag requires review.',
        'unscored_invalid_date': 'The observation has no valid date.',
        'unscored_invalid_value': 'The observation has no finite numerical value.',
        'unscored_ambiguous_same_day': 'Multiple observations share this series and date.',
        'unscored_insufficient_history': 'Insufficient valid prior days in the history window.',
        'unscored_zero_mad': 'Prior values have zero median absolute deviation.',
    }
    result['explanation'] = result['score_status'].map(explanations).fillna(
        'Compare the observed value with its prior median and robust spread.'
    )
    return result.drop(columns=['_date', '_number'])


def run(prepared: Path, output: Path, config: DetectorConfig) -> None:
    config.validate()
    prepared, output = prepared.resolve(), output.resolve()
    if prepared == output or prepared in output.parents or output in prepared.parents:
        raise ValueError('Prepared inputs and output must be separate directories')
    if not (prepared / 'summary.json').is_file():
        raise ValueError('Preparation summary missing; pipeline may be incomplete')
    summary = json.loads((prepared / 'summary.json').read_text(encoding='utf-8'))
    if summary.get('file_limit_per_table') is not None:
        raise ValueError('Partial preparation output is not a full detector input')
    metadata_path = prepared / 'point_metadata.csv.gz'
    value_dir = prepared / 'cleaned' / 'MeasurementValues'
    if not metadata_path.is_file() or not value_dir.is_dir():
        raise ValueError('Prepared point metadata or measurement values are missing')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; choose a new path')
    metadata = pd.read_csv(metadata_path, dtype=str, keep_default_na=False)
    selected = select_points(metadata)
    if selected.empty:
        raise ValueError('No points match the exploratory selection')
    selected_ids = set(selected['MeasurementPointID'])
    file_for_point = dict(zip(selected['MeasurementPointID'], selected['source_file']))
    meta_units = dict(zip(selected['MeasurementPointID'], selected['Unit']))
    selected_metadata = selected.set_index('MeasurementPointID')
    files = sorted(value_dir.glob('*.csv.gz'))
    if not files:
        raise ValueError('No prepared measurement files found')
    output.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    output_path = output / 'history_scores.csv.gz'
    has_header = False
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
        for column in ('ProductDescription', 'QuantityDescription', 'ParameterDescription', 'InputType'):
            frame[column] = frame['MeasurementPointID'].map(selected_metadata[column])
        parts = [score_series(group, config) for _, group in
                 frame.groupby(SERIES_COLUMNS, dropna=False, sort=False)]
        scored = pd.concat(parts).sort_index()
        scored.to_csv(output_path, mode='at' if has_header else 'wt',
                      header=not has_header, index=False, compression='gzip')
        has_header = True
        counts['selected_rows'] += len(scored)
        counts.update(scored['score_status'].value_counts().to_dict())
        counts['flagged'] += int(scored['anomaly_flag'].fillna(False).sum())
    if not has_header:
        raise ValueError('Selected points have no observations; output is incomplete')
    run_info = {
        'status': 'provisional_unvalidated',
        'input_preparation_summary': str(prepared / 'summary.json'),
        'selection': {'ProductDescription': 'Influent', 'QuantityDescription': 'Volume',
                      'ParameterDescription': 'Niet van toepassing', 'Unit': 'm3', 'InputType': 'scada'},
        'selection_semantics': 'exploratory; not confirmed as comparable incoming flow',
        'config': asdict(config), 'scale_factor': 1.4826,
        'counts': dict(counts), 'pandas_version': pd.__version__, 'numpy_version': np.__version__,
        'limitations': ['No peer comparison or model evaluation performed.',
                        'Threshold is provisional and not calibrated to operator workload.',
                        'Dates and input availability require partner confirmation.',
                        'Flags are not diagnoses or verified anomalies.'],
    }
    (output / 'run_info.json').write_text(json.dumps(run_info, indent=2), encoding='utf-8')
    print('Historical scoring complete. Outputs are private and provisional.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True, help='Completed full TAI preparation directory')
    parser.add_argument('--output', type=Path, required=True, help='New or empty private output directory')
    parser.add_argument('--window-days', type=int, default=28)
    parser.add_argument('--minimum-history', type=int, default=14)
    parser.add_argument('--threshold', type=float, default=3.5,
                        help='Provisional robust score threshold, not validated')
    args = parser.parse_args()
    run(args.prepared, args.output, DetectorConfig(args.window_days, args.minimum_history, args.threshold))


if __name__ == '__main__':
    main()
