import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from isolation_forest.model import (Config, FEATURES, SERIES, add_features, fit_model,
                                    select_daily_budget, split_labels, validate_selection)
from history_detector.history_detector import (DetectorConfig, MEASUREMENTS, QUALITY_FLAGS,
                                               Thresholds, score_series, select_points)


def raw_fixture(days=40, start='2022-01-01', point='fixture-point'):
    """Artificial records, never derived from partner data."""
    dates = pd.date_range(start, periods=days, freq='D')
    frame = pd.DataFrame({column: ['fixture'] * days for column in SERIES})
    frame['MeasurementPointID'] = point
    frame['Unit'] = 'm3'
    frame['parsed_date'] = dates.astype(str)
    frame['parsed_value'] = [str(10 + (i % 9)) for i in range(days)]
    frame['source_file'] = 'fixture.csv.gz'
    frame['source_row'] = [str(i + 2) for i in range(days)]
    for column in QUALITY_FLAGS:
        frame[column] = 'False'
    return frame


def fixture(days=40, start='2022-01-01', point='fixture-point'):
    return score_series(raw_fixture(days, start, point), DetectorConfig(), Thresholds(3.5, 3.5))


class FeaturesTest(unittest.TestCase):
    def test_causal_features_ignore_future_and_other_points(self):
        original = fixture()
        first = add_features(original)
        changed = original.copy()
        changed.loc[changed.index[-1], 'parsed_value'] = '999999'
        second = add_features(changed)
        pd.testing.assert_frame_equal(first.loc[:38, FEATURES], second.loc[:38, FEATURES])
        other = fixture(point='another-point')
        combined = add_features(pd.concat([original, other], ignore_index=True))
        pd.testing.assert_frame_equal(first[FEATURES], combined.loc[:39, FEATURES])

    def test_unscored_zero_mad_gap_and_ambiguous_days_stay_unscored(self):
        frame = fixture()
        # Original history status must never be silently promoted to AI normal.
        frame.loc[25, 'score_status'] = 'unscored_zero_mad'
        frame.loc[25, 'anomaly_flag'] = pd.NA
        frame.loc[29, 'parsed_value'] = ''
        frame.loc[29, 'anomaly_flag'] = pd.NA
        frame.loc[30, 'parsed_date'] = 'not-a-date'
        duplicate = frame.loc[[35]].copy()
        duplicate['source_row'] = '999'
        result = add_features(pd.concat([frame, duplicate], ignore_index=True))
        self.assertEqual(result.loc[25, 'ai_status'], 'unscored_history_detector')
        self.assertEqual(result.loc[26, 'ai_status'], 'unscored_missing_prior_day')
        self.assertEqual(result.loc[29, 'ai_status'], 'unscored_invalid_history_features')
        self.assertEqual(result.loc[30, 'ai_status'], 'unscored_invalid_history_features')
        self.assertEqual(result.loc[35, 'ai_status'], 'unscored_ambiguous_same_day')
        self.assertEqual(result.loc[40, 'ai_status'], 'unscored_ambiguous_same_day')
        self.assertEqual(result.loc[36, 'ai_status'], 'unscored_missing_prior_day')
        self.assertTrue(result.loc[[25, 26, 29, 30, 35, 36, 40], FEATURES].isna().all().all())

    def test_history_detector_excludes_duplicate_dates_and_zero_spread(self):
        original = raw_fixture()
        duplicated = pd.concat([original, original.iloc[[20]]], ignore_index=True)
        scored = score_series(duplicated, DetectorConfig())
        self.assertEqual(scored.loc[20, 'score_status'], 'unscored_ambiguous_same_day')
        self.assertEqual(scored.loc[40, 'score_status'], 'unscored_ambiguous_same_day')
        constant = original.copy()
        constant['parsed_value'] = '0'
        constant_result = score_series(constant, DetectorConfig(), Thresholds(3.5, 3.5))
        self.assertEqual(constant_result.loc[14, 'score_status'], 'unscored_zero_spread')
        self.assertTrue(pd.isna(constant_result.loc[14, 'anomaly_flag']))

    def test_zero_and_repeat_features_and_threshold_free_history(self):
        frame = raw_fixture(40)
        frame.loc[30, 'parsed_value'] = '0'
        frame.loc[34:37, 'parsed_value'] = '12'
        low = add_features(score_series(frame, DetectorConfig(), Thresholds(1.0, 1.0)))
        high = add_features(score_series(frame, DetectorConfig(), Thresholds(50.0, 50.0)))
        # Features must not change with the detector's alert threshold.
        pd.testing.assert_frame_equal(low[FEATURES], high[FEATURES])
        self.assertEqual(low.loc[30, 'is_zero'], 1.0)
        self.assertAlmostEqual(low.loc[37, 'repeat_days_log'], np.log(4))


class ModelTest(unittest.TestCase):
    def test_split_fit_reproducibility_and_reload(self):
        artificial = pd.concat([fixture(80, '2022-01-01'), fixture(80, '2024-01-01'),
                                fixture(80, '2025-01-01')], ignore_index=True)
        data = add_features(artificial)
        config = Config(trees=10, max_samples=30)
        data['split'] = split_labels(data['_date'], config)
        model1, threshold1 = fit_model(data, config)
        changed_test = data.copy()
        changed_test.loc[changed_test['split'].eq('test'), FEATURES] = 1e8
        model2, threshold2 = fit_model(changed_test, config)
        eligible = data.loc[data.ai_status.eq('eligible'), FEATURES]
        np.testing.assert_allclose(model1.score_samples(eligible), model2.score_samples(eligible))
        self.assertEqual(threshold1, threshold2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trusted.joblib'
            joblib.dump({'model': model1, 'threshold': threshold1, 'feature_order': FEATURES}, path)
            reloaded = joblib.load(path)
            np.testing.assert_allclose(model1.score_samples(eligible), reloaded['model'].score_samples(eligible))
            self.assertEqual(threshold1, reloaded['threshold'])

    def test_daily_budget_ties_and_eligible_population(self):
        frame = pd.DataFrame({'_date': pd.to_datetime(['2025-01-01'] * 4 + ['2025-01-02'] * 2),
                              'InstallationCodeOrigin': ['plant'] * 6,
                              'ai_status': ['eligible'] * 5 + ['unscored_history_detector'],
                              'source_file': ['b', 'a', 'c', 'd', 'e', 'f'],
                              'source_row': ['1'] * 6,
                              'candidate': [1, 1, 0.1, 0, 0.2, 99]})
        chosen = select_daily_budget(frame, ['candidate'], 1)
        self.assertEqual(chosen.tolist(), [False, True, False, False, True, False])

    def test_budget_is_per_plant_and_ties_break_on_numeric_row(self):
        frame = pd.DataFrame({'_date': pd.to_datetime(['2025-01-01'] * 4),
                              'InstallationCodeOrigin': ['big', 'big', 'small', 'small'],
                              'ai_status': ['eligible'] * 4, 'source_file': ['a'] * 4,
                              'source_row': ['10', '9', '3', '2'],
                              'rule': [0.0, 0.0, 0.0, 1.0], 'candidate': [50, 50, 9, 1]})
        chosen = select_daily_budget(frame, ['candidate'], 1)
        self.assertEqual(chosen.tolist(), [False, True, True, False])  # row 9 before row 10
        chosen = select_daily_budget(frame, ['rule', 'candidate'], 1)
        self.assertEqual(chosen.tolist(), [False, True, False, True])  # rule hit first


class MeasurementSelectionTest(unittest.TestCase):
    def test_three_independent_cohorts_exclude_wrong_unit_state_and_input(self):
        rows = []
        for name, definition in MEASUREMENTS.items():
            row = {'MeasurementPointID': name, 'source_file': 'fixture',
                   'StateDescription': 'niet van toepassing', **definition}
            rows.append(row)
        oxygen_wrong_unit = dict(rows[1], MeasurementPointID='wrong-unit', Unit='%')
        ammonium_wrong_state = dict(rows[2], MeasurementPointID='wrong-state',
                                    StateDescription='uitgedrukt in stikstof / opgeloste fractie')
        oxygen_manual = dict(rows[1], MeasurementPointID='manual', InputType='hand')
        volume_other_state = dict(rows[0], MeasurementPointID='volume-other-state', StateDescription='other')
        metadata = pd.DataFrame(rows + [oxygen_wrong_unit, ammonium_wrong_state, oxygen_manual, volume_other_state])
        for name in MEASUREMENTS:
            selected = select_points(metadata, name)
            expected = [name, 'volume-other-state'] if name == 'influent_volume' else [name]
            self.assertEqual(selected.MeasurementPointID.tolist(), expected)
        self.assertEqual(select_points(metadata).MeasurementPointID.tolist(), ['influent_volume', 'volume-other-state'])
        with self.assertRaises(ValueError):
            select_points(metadata, 'other')
        with self.assertRaises(ValueError):
            select_points(pd.concat([metadata, metadata.iloc[[0]]], ignore_index=True))

    def test_forest_rejects_mixed_measurements_and_preserves_legacy_selection(self):
        info = {'selection': MEASUREMENTS['oxygen']}
        frame = pd.DataFrame([MEASUREMENTS['oxygen']])
        validate_selection(frame, info)
        wrong = frame.copy()
        wrong.loc[0, 'ParameterDescription'] = 'ammonium'
        with self.assertRaises(ValueError):
            validate_selection(wrong, info)
        wrong = frame.copy()
        wrong.loc[0, 'StateDescription'] = 'different basis'
        with self.assertRaises(ValueError):
            validate_selection(wrong, info)
        validate_selection(pd.DataFrame([MEASUREMENTS['influent_volume']]),
                           {'selection': MEASUREMENTS['influent_volume']})


if __name__ == '__main__':
    unittest.main()
