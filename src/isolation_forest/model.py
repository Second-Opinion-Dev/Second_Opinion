#!/usr/bin/env python3
"""Retrospective Isolation Forest on leakage-safe history-detector features."""

from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest


SERIES = ['InstallationCodeOrigin', 'MeasurementPointID', 'SubProcessCodeOrigin',
          'ProcessCode', 'Product', 'ProductBalance', 'InstallationCodeDestination',
          'SubProcessDestination', 'Unit']
RULES = ['rule_stuck', 'rule_dropout', 'rule_negative']
FEATURES = ['signed_deviation_log', 'day_change_log', 'prior_deviation_log_mean',
            'relative_level_log', 'is_zero', 'repeat_days_log']
REQUIRED = SERIES + ['parsed_date', 'parsed_value', 'history_median', 'history_scale',
                     'anomaly_score', 'anomaly_flag', 'repeat_days', 'score_status',
                     'source_file', 'source_row'] + RULES


@dataclass(frozen=True)
class Config:
    train_end: str = '2023-12-31'
    validation_end: str = '2024-12-31'
    test_end: str = '2025-12-31'
    validation_flag_fraction: float = 0.01
    # Each plant has its own operator, so the comparison budget applies per plant per day.
    plant_daily_budget: int = 1
    seed: int = 42
    trees: int = 100
    max_samples: int = 256

    def validate(self):
        dates = [pd.Timestamp(self.train_end), pd.Timestamp(self.validation_end),
                 pd.Timestamp(self.test_end)]
        if not dates[0] < dates[1] < dates[2]:
            raise ValueError('Split endpoints must be strictly increasing')
        if not 0 < self.validation_flag_fraction < 1:
            raise ValueError('Validation flag fraction must be between 0 and 1')
        if self.plant_daily_budget < 1 or self.trees < 1 or self.max_samples < 1:
            raise ValueError('Budget, trees and max_samples must be positive')


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Construct features with current and strictly prior data from one series.

    Input is output from the history detector. A previous day must have been
    scored; the prior mean deviation needs at least three scored, unambiguous
    days in [day-7, day). No feature depends on the detector's alert threshold.
    Missingness is never filled with normal-looking values.
    """
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing history detector columns: {sorted(missing)}')
    out = frame.copy().reset_index(drop=True)
    out['_date'] = pd.to_datetime(out['parsed_date'], errors='coerce').dt.normalize()
    numeric_fields = ['parsed_value', 'history_median', 'history_scale', 'anomaly_score', 'repeat_days']
    for field in numeric_fields:
        out[field] = pd.to_numeric(out[field], errors='coerce')
    out['_duplicate'] = out['_date'].notna() & out.duplicated(SERIES + ['_date'], keep=False)
    out['_valid'] = (out['score_status'].eq('scored') & out['_date'].notna()
                     & np.isfinite(out[numeric_fields]).all(axis=1) & out['history_scale'].gt(0)
                     & out['repeat_days'].ge(1) & ~out['_duplicate'])
    out['ai_status'] = 'unscored_history_detector'
    out.loc[out['_duplicate'], 'ai_status'] = 'unscored_ambiguous_same_day'
    out.loc[out['score_status'].eq('scored') & ~out['_valid'] & ~out['_duplicate'],
            'ai_status'] = 'unscored_invalid_history_features'
    for name in FEATURES:
        out[name] = np.nan

    # Per-series processing ensures no identifiers or neighbouring plants are model features.
    for _, group in out.groupby(SERIES, sort=False, dropna=False):
        ordered = group.sort_values('_date', kind='stable', na_position='last')
        previous_date = ordered['_date'].shift()
        previous_value = ordered['parsed_value'].shift()
        previous_valid = ordered['_valid'].shift(fill_value=False)
        prior_day = ((ordered['_date'] - previous_date).dt.days.eq(1) & previous_valid)
        good = ordered['_valid']
        value, median, scale = ordered['parsed_value'], ordered['history_median'], ordered['history_scale']
        signed = (value - median) / scale
        change = (value - previous_value) / scale
        # Level relative to the typical value; the spread guards against a zero median.
        relative = (value - median) / np.maximum(median.abs(), scale)

        # A date-based window with closed='left' excludes the current day.
        valid_rows = ordered.loc[good]
        deviation = pd.Series(np.log1p(np.abs(signed.loc[good])).to_numpy(), index=valid_rows['_date'])
        prior = deviation.rolling('7D', closed='left', min_periods=3).mean()
        prior.index = valid_rows.index
        have_prior = pd.Series(False, index=ordered.index)
        have_prior.loc[prior.index] = prior.notna().to_numpy()
        computed = (good & prior_day & have_prior & np.isfinite(signed) & np.isfinite(change)
                    & np.isfinite(relative))
        out.loc[ordered.index[good & ~prior_day], 'ai_status'] = 'unscored_missing_prior_day'
        out.loc[ordered.index[good & prior_day & ~have_prior], 'ai_status'] = 'unscored_insufficient_prior_days'
        out.loc[ordered.index[good & prior_day & have_prior & ~computed], 'ai_status'] = 'unscored_nonfinite_features'
        idx = ordered.index[computed]
        out.loc[idx, 'signed_deviation_log'] = np.sign(signed.loc[idx]) * np.log1p(np.abs(signed.loc[idx]))
        out.loc[idx, 'day_change_log'] = np.sign(change.loc[idx]) * np.log1p(np.abs(change.loc[idx]))
        out.loc[idx, 'prior_deviation_log_mean'] = prior.loc[idx]
        out.loc[idx, 'relative_level_log'] = np.sign(relative.loc[idx]) * np.log1p(np.abs(relative.loc[idx]))
        out.loc[idx, 'is_zero'] = value.loc[idx].eq(0).astype(float)
        out.loc[idx, 'repeat_days_log'] = np.log(ordered.loc[idx, 'repeat_days'])
        out.loc[idx, 'ai_status'] = 'eligible'
    return out.drop(columns=['_valid', '_duplicate'])


def split_labels(dates: pd.Series, config: Config) -> pd.Series:
    config.validate()
    labels = pd.Series('outside_split', index=dates.index, dtype='str')
    labels.loc[dates.notna() & (dates <= pd.Timestamp(config.train_end))] = 'train'
    labels.loc[(dates > pd.Timestamp(config.train_end)) & (dates <= pd.Timestamp(config.validation_end))] = 'validation'
    labels.loc[(dates > pd.Timestamp(config.validation_end)) & (dates <= pd.Timestamp(config.test_end))] = 'test'
    return labels


def fit_model(frame: pd.DataFrame, config: Config):
    config.validate()
    eligible = frame['ai_status'].eq('eligible')
    train = frame.loc[eligible & frame['split'].eq('train'), FEATURES]
    val = frame.loc[eligible & frame['split'].eq('validation'), FEATURES]
    if len(train) < max(30, config.max_samples) or len(val) < 30:
        raise ValueError('Not enough eligible training or validation rows')
    if not np.isfinite(train.to_numpy()).all() or not np.isfinite(val.to_numpy()).all():
        raise ValueError('Non-finite model features')
    model = IsolationForest(n_estimators=config.trees, max_samples=config.max_samples,
                            random_state=config.seed, n_jobs=1, contamination='auto')
    model.fit(train)
    # Higher means more unusual. Never use the model's default decision threshold.
    validation_scores = -model.score_samples(val)
    threshold = float(np.quantile(validation_scores, 1 - config.validation_flag_fraction))
    return model, threshold


def select_daily_budget(frame: pd.DataFrame, scores: list[str], budget: int) -> pd.Series:
    """Select at most K eligible rows per plant per day, ranked by scores in order.

    Each plant has its own operator, so plants never compete for one shared
    budget. Ties break on source file, then numeric source row.
    """
    if budget < 1:
        raise ValueError('Daily review budget must be positive')
    mask = frame['ai_status'].eq('eligible') & frame['_date'].notna() & frame[scores].notna().all(axis=1)
    candidates = frame.loc[mask].assign(_row=pd.to_numeric(frame.loc[mask, 'source_row'], errors='coerce'))
    candidates = candidates.sort_values(
        ['_date', 'InstallationCodeOrigin', *scores, 'source_file', '_row'],
        ascending=[True, True, *[False] * len(scores), True, True], kind='stable')
    selected = candidates.groupby(['_date', 'InstallationCodeOrigin'], sort=False).head(budget).index
    return pd.Series(frame.index.isin(selected), index=frame.index, dtype=bool)


def evaluate(frame: pd.DataFrame, config: Config) -> dict:
    """Describe workloads, overlap and coverage; this is not accuracy."""
    test = frame.loc[frame['split'].eq('test')]
    eligible = test['ai_status'].eq('eligible')
    a = test['baseline_budget_selected']
    b = test['ai_budget_selected']
    return {
        'test_rows': int(len(test)), 'test_same_eligible_rows': int(eligible.sum()),
        'test_unscored_by_ai_reason': {str(k): int(v) for k, v in test.loc[~eligible, 'ai_status'].value_counts().items()},
        'test_history_status_counts': {str(k): int(v) for k, v in test['score_status'].value_counts().items()},
        'test_baseline_default_flags_on_same_eligible': int(test.loc[eligible, 'anomaly_flag'].astype(str).str.lower().eq('true').sum()),
        'test_baseline_rule_hits_on_same_eligible': int(test.loc[eligible, '_rule_any'].sum()),
        'test_ai_fixed_threshold_flags_on_same_eligible': int(test.loc[eligible, 'ai_flag'].fillna(False).sum()),
        'test_budget_days': int(test.loc[eligible, '_date'].nunique()),
        'test_baseline_budget_selected': int(a.sum()), 'test_ai_budget_selected': int(b.sum()),
        'test_both_budget_selected': int((a & b).sum()),
        'test_baseline_only_budget_selected': int((a & ~b).sum()),
        'test_ai_only_budget_selected': int((b & ~a).sum()),
        'review_budget_per_plant_per_day_assumed': config.plant_daily_budget,
        'interpretation': 'Descriptive counts and rankings only; no labelled accuracy, false-alarm rate or savings.',
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_selection(frame: pd.DataFrame, info: dict) -> None:
    """Reject a mixed or incomplete cohort; one forest is fitted per input run."""
    selection = info.get('selection')
    required = {'ProductDescription', 'QuantityDescription', 'ParameterDescription', 'Unit', 'InputType'}
    if not isinstance(selection, dict) or not required.issubset(selection):
        raise ValueError('History run selection is missing required cohort metadata')
    for field, expected in selection.items():
        if field not in frame:
            raise ValueError(f'History output is missing selection field: {field}')
        actual = frame[field].astype(str).str.strip()
        matches = actual.eq(expected) if field == 'Unit' else actual.str.casefold().eq(str(expected).casefold())
        if not matches.all():
            raise ValueError(f'History output mixes measurement definitions in {field}')


def run(history_dir: Path, output: Path, config: Config) -> None:
    config.validate()
    history_dir, output = history_dir.resolve(), output.resolve()
    if history_dir == output or history_dir in output.parents or output in history_dir.parents:
        raise ValueError('Input and output must be separate')
    info_path, input_path = history_dir / 'run_info.json', history_dir / 'history_scores.csv.gz'
    if not info_path.is_file() or not input_path.is_file():
        raise ValueError('Completed history detector output is required')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be a new or empty private directory')
    info = json.loads(info_path.read_text(encoding='utf-8'))
    if info.get('status') not in ('provisional_unvalidated', 'smoke_run_partial'):
        raise ValueError('Unexpected history output status')
    source = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    if len(source) != info.get('counts', {}).get('selected_rows'):
        raise ValueError('History output row count does not match its completion marker')
    validate_selection(source, info)
    data = add_features(source)
    data['split'] = split_labels(data['_date'], config)
    model, threshold = fit_model(data, config)
    eligible = data['ai_status'].eq('eligible')
    data['ai_score'] = np.nan
    data.loc[eligible, 'ai_score'] = -model.score_samples(data.loc[eligible, FEATURES])
    data['ai_flag'] = pd.Series(pd.NA, index=data.index, dtype='boolean')
    data.loc[eligible, 'ai_flag'] = data.loc[eligible, 'ai_score'].ge(threshold)
    # The baseline ranks rule hits (stuck, dropout, negative) first, then the robust score.
    data['_rule_any'] = data[RULES].apply(lambda s: s.astype(str).str.lower().eq('true')).any(axis=1).astype(float)
    data['baseline_budget_selected'] = select_daily_budget(data, ['_rule_any', 'anomaly_score'], config.plant_daily_budget)
    data['ai_budget_selected'] = select_daily_budget(data, ['ai_score'], config.plant_daily_budget)
    # Explicitly preserve baseline evidence; feature values are not causal explanations.
    data['ai_explanation'] = np.where(eligible,
        'Isolation Forest ranked the history-derived feature combination; inspect deviation, daily change, recent deviations, level, zeros and repeats.',
        'Not scored by AI; see ai_status and the original history-detector status.')
    results = evaluate(data, config)
    versions = {'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__,
                'scikit_learn': sklearn.__version__, 'joblib': joblib.__version__}
    output.mkdir(parents=True, exist_ok=True)
    bundle = {'model': model, 'threshold': threshold, 'config': asdict(config),
              'feature_order': FEATURES, 'versions': versions,
              'measurement': info.get('measurement', 'influent_volume'),
              'history_config': info.get('config'), 'history_selection': info.get('selection')}
    joblib.dump(bundle, output / 'isolation_forest.joblib')
    data.drop(columns=['_date', '_rule_any']).to_csv(output / 'scored_records.csv.gz', index=False, compression='gzip')
    manifest = {'status': 'provisional_unvalidated', 'config': asdict(config), 'feature_order': FEATURES,
                'threshold': threshold, 'versions': versions, 'history_config': info.get('config'),
                'measurement': info.get('measurement', 'influent_volume'),
                'history_selection': info.get('selection'), 'history_input_sha256': sha256(input_path),
                'history_info_sha256': sha256(info_path),
                'split_counts': {str(k): int(v) for k, v in data['split'].value_counts().items()},
                'eligible_by_split': {str(k): int(v) for k, v in data.loc[eligible, 'split'].value_counts().items()},
                'evaluation': results,
                'caveats': ['Historical daily data; observation availability time is unconfirmed.',
                            'Selection and meaning require confirmation by the data provider.',
                            'No expert-reviewed labels: no measured real-world accuracy or false-alarm rate.',
                            'Per-plant daily budget is an assumption; selection is descriptive, not safe suppression.',
                            'Saved models must be loaded only from trusted local sources.']}
    (output / 'run_info.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Completed retrospective Isolation Forest scoring; outputs and aggregate results are local.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--train-end', default=Config.train_end)
    parser.add_argument('--validation-end', default=Config.validation_end)
    parser.add_argument('--test-end', default=Config.test_end)
    parser.add_argument('--validation-flag-fraction', type=float, default=Config.validation_flag_fraction)
    parser.add_argument('--plant-daily-budget', type=int, default=Config.plant_daily_budget,
                        help='Readings selected per plant per day in the descriptive comparison')
    parser.add_argument('--seed', type=int, default=Config.seed)
    args = parser.parse_args()
    run(args.history_dir, args.output, Config(args.train_end, args.validation_end, args.test_end,
        args.validation_flag_fraction, args.plant_daily_budget, args.seed))


if __name__ == '__main__':
    main()
