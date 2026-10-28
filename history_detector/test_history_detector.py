"""Focused checks of the history detector on explicitly artificial fixtures."""
import unittest

import numpy as np
import pandas as pd

from history_detector.history_detector import (LEGACY_CONFIG, QUALITY_FLAGS, SERIES_COLUMNS,
                                               DetectorConfig, Thresholds, apply_thresholds,
                                               build_cases, calibrate_thresholds, score_series)
from history_detector.synthetic_faults import FAULT_DAYS, eligible_positions, inject

FIXED = Thresholds(3.5, 3.5)


def series(values, start='2022-01-01', dates=None, point='fixture-point'):
    """Artificial records, never derived from partner data. None marks a blank value."""
    dates = pd.date_range(start, periods=len(values), freq='D') if dates is None else pd.to_datetime(dates)
    frame = pd.DataFrame({column: ['fixture'] * len(values) for column in SERIES_COLUMNS})
    frame['MeasurementPointID'] = point
    frame['Unit'] = 'm3'
    frame['parsed_date'] = dates.strftime('%Y-%m-%d')
    frame['parsed_value'] = ['' if v is None else repr(float(v)) for v in values]
    frame['source_file'] = 'fixture.csv.gz'
    frame['source_row'] = [str(i + 2) for i in range(len(values))]
    for column in QUALITY_FLAGS:
        frame[column] = 'False'
    frame.loc[[v is None for v in values], 'flag_blank_value'] = 'True'
    return frame


def varying(days, base=100.0):
    return [base + (i % 5) for i in range(days)]


class WindowTest(unittest.TestCase):
    def test_window_includes_lower_boundary_and_excludes_current_day(self):
        config = DetectorConfig(window_days=3, minimum_history=1, scale_floor_fraction=0, clip_limit=0, rules=False)
        result = score_series(series([1, 2, 3, 4, 100]), config)
        self.assertEqual(result['history_days'].tolist(), [0, 1, 2, 3, 3])
        self.assertEqual(result.loc[4, 'history_median'], 3.0)  # days 1-3; day 0 has left the window
        gapped = score_series(series([1, 2, 9], dates=['2022-01-01', '2022-01-02', '2022-01-05']), config)
        self.assertEqual(gapped.loc[2, 'history_days'], 1)  # [Jan 2, Jan 5) keeps only Jan 2

    def test_future_values_do_not_change_earlier_scores(self):
        values = varying(40)
        first = score_series(series(values), DetectorConfig(), FIXED)
        values[-1] = 1e9
        second = score_series(series(values), DetectorConfig(), FIXED)
        pd.testing.assert_series_equal(first['anomaly_score'].iloc[:-1], second['anomaly_score'].iloc[:-1])


class SpreadTest(unittest.TestCase):
    def test_floor_scores_constant_history_and_legacy_leaves_it_unscored(self):
        values = [100.0] * 20 + [130.0]
        revised = score_series(series(values), DetectorConfig(rules=False), FIXED)
        self.assertEqual(revised.loc[20, 'score_status'], 'scored')
        self.assertAlmostEqual(revised.loc[20, 'history_scale'], 5.0)
        self.assertAlmostEqual(revised.loc[20, 'anomaly_score'], 6.0)
        legacy = score_series(series(values), LEGACY_CONFIG, FIXED)
        self.assertEqual(legacy.loc[20, 'score_status'], 'unscored_zero_spread')
        zeros = score_series(series([0.0] * 20), DetectorConfig(), FIXED)
        self.assertEqual(zeros.loc[19, 'score_status'], 'unscored_zero_spread')

    def test_floor_limits_scores_on_tiny_meters(self):
        values = [4.0 + 0.01 * (i % 3) for i in range(30)] + [5.0]
        floored = score_series(series(values), DetectorConfig(rules=False), FIXED)
        unfloored = score_series(series(values), LEGACY_CONFIG, FIXED)
        self.assertLess(floored.loc[30, 'anomaly_score'], 6)
        self.assertGreater(unfloored.loc[30, 'anomaly_score'], 50)

    def test_clipping_keeps_a_sustained_shift_flagged_for_longer(self):
        values = varying(30) + [200.0] * 40
        clipped = score_series(series(values), DetectorConfig(rules=False), FIXED)
        unclipped = score_series(series(values), DetectorConfig(rules=False, clip_limit=0), FIXED)
        flagged = lambda frame: int(frame['anomaly_flag'].iloc[30:].fillna(False).sum())
        self.assertGreater(flagged(clipped), flagged(unclipped))
        # The raw value is always reported; only later history is clipped.
        self.assertEqual(clipped['parsed_value'].tolist(), series(values)['parsed_value'].tolist())


class RuleTest(unittest.TestCase):
    def test_stuck_after_varying_history_but_not_for_a_quiet_meter(self):
        result = score_series(series(varying(30) + [103.0] * 8), DetectorConfig(), FIXED)
        self.assertEqual(result['rule_stuck'].iloc[30:].tolist(), [False] * 6 + [True] * 2)
        self.assertEqual(result.loc[37, 'repeat_days'], 8)
        self.assertTrue(result.loc[37, 'review_flag'])
        self.assertIn('stuck', result.loc[37, 'flag_reason'])
        quiet = score_series(series([0.0] * 40), DetectorConfig(), FIXED)
        self.assertFalse(quiet['rule_stuck'].any())

    def test_dropout_only_after_a_window_without_zeros(self):
        result = score_series(series(varying(20) + [0.0]), DetectorConfig(), FIXED)
        self.assertTrue(result.loc[20, 'rule_dropout'])
        with_zeros = [0.0 if i % 4 == 0 else v for i, v in enumerate(varying(20))] + [0.0]
        result = score_series(series(with_zeros), DetectorConfig(), FIXED)
        self.assertFalse(result.loc[20, 'rule_dropout'])

    def test_negative_value_flagged_even_without_history(self):
        result = score_series(series([5.0, -1.0]), DetectorConfig(), FIXED)
        self.assertEqual(result['rule_negative'].tolist(), [False, True])
        self.assertEqual(result.loc[1, 'score_status'], 'unscored_insufficient_history')
        self.assertTrue(result.loc[1, 'review_flag'])

    def test_rules_can_be_disabled(self):
        result = score_series(series(varying(20) + [0.0, -1.0]), DetectorConfig(rules=False), FIXED)
        self.assertFalse(result[['rule_stuck', 'rule_dropout', 'rule_negative']].any().any())


class AmbiguityTest(unittest.TestCase):
    def test_blank_row_does_not_make_a_valid_same_day_row_ambiguous(self):
        dates = list(pd.date_range('2022-01-01', periods=20).strftime('%Y-%m-%d')) + ['2022-01-20']
        result = score_series(series(varying(20) + [None], dates=dates), DetectorConfig(), FIXED)
        self.assertEqual(result.loc[19, 'score_status'], 'scored')
        self.assertEqual(result.loc[20, 'score_status'], 'unscored_invalid_value')
        self.assertTrue(pd.isna(result.loc[20, 'review_flag']))

    def test_two_valid_same_day_rows_are_both_ambiguous(self):
        dates = list(pd.date_range('2022-01-01', periods=20).strftime('%Y-%m-%d')) + ['2022-01-20']
        result = score_series(series(varying(21), dates=dates), DetectorConfig(), FIXED)
        self.assertEqual(result.loc[[19, 20], 'score_status'].tolist(), ['unscored_ambiguous_same_day'] * 2)


class ThresholdTest(unittest.TestCase):
    def calibration_frame(self, point='calm', scale=1.0, rows=500):
        above = pd.DataFrame({'anomaly_score': np.arange(1, rows + 1) * scale, 'direction': 'above'})
        below = pd.DataFrame({'anomaly_score': np.arange(1, rows + 1) * scale / 10, 'direction': 'below'})
        frame = pd.concat([above, below], ignore_index=True)
        for column in SERIES_COLUMNS:
            frame[column] = 'fixture'
        frame['MeasurementPointID'] = point
        frame['parsed_date'] = '2023-06-01'
        frame['score_status'] = 'scored'
        return frame

    def test_each_series_gets_its_own_thresholds_from_the_calibration_period(self):
        calm, erratic = self.calibration_frame('calm'), self.calibration_frame('erratic', scale=10)
        frame = pd.concat([calm, erratic], ignore_index=True)
        thresholds = calibrate_thresholds(frame, '2023-12-31', 0.02)
        table = thresholds.table.set_index('MeasurementPointID')
        self.assertEqual(tuple(table.loc['calm', ['threshold_above', 'threshold_below']]), (491.0, 49.1))
        self.assertEqual(tuple(table.loc['erratic', ['threshold_above', 'threshold_below']]), (4910.0, 491.0))
        later = frame.assign(parsed_date='2024-06-01', anomaly_score=1e6)
        again = calibrate_thresholds(pd.concat([frame, later], ignore_index=True), '2023-12-31', 0.02)
        pd.testing.assert_frame_equal(thresholds.table, again.table)

    def test_short_series_use_the_median_fallback_and_minimum_threshold(self):
        frame = pd.concat([self.calibration_frame('a'), self.calibration_frame('b', scale=3),
                           self.calibration_frame('short', rows=20)], ignore_index=True)
        thresholds = calibrate_thresholds(frame, '2023-12-31', 0.02)
        self.assertNotIn('short', set(thresholds.table['MeasurementPointID']))
        self.assertEqual(thresholds.fallback.above, (491.0 + 1473.0) / 2)
        tiny = self.calibration_frame('tiny', scale=0.001)
        limits = calibrate_thresholds(tiny, '2023-12-31', 0.02).table.iloc[0]
        self.assertEqual((limits['threshold_above'], limits['threshold_below']), (2.0, 2.0))
        applied = apply_thresholds(frame.assign(rule_stuck=False, rule_dropout=False, rule_negative=False),
                                   thresholds)
        short = applied['MeasurementPointID'].eq('short')
        self.assertTrue(applied.loc[short, 'threshold_above'].eq(thresholds.fallback.above).all())

    def test_lower_threshold_for_drops_applies_by_direction(self):
        frame = pd.DataFrame({'score_status': ['scored'] * 2, 'direction': ['above', 'below'],
                              'anomaly_score': [4.0, 4.0], 'rule_stuck': [False] * 2,
                              'rule_dropout': [False] * 2, 'rule_negative': [False] * 2})
        result = apply_thresholds(frame, Thresholds(above=6.0, below=3.0))
        self.assertEqual(result['anomaly_flag'].tolist(), [False, True])
        self.assertEqual(result['flag_reason'].tolist(), ['', 'unusual_low'])


class CaseTest(unittest.TestCase):
    def flagged_frame(self, flags, reasons=None, point='p', plant='plant'):
        frame = series([1.0] * len(flags), point=point)
        frame['InstallationCodeOrigin'] = plant
        frame['review_flag'] = pd.array(flags, dtype='boolean')
        frame['flag_reason'] = reasons or ['unusual_high' if f else '' for f in flags]
        frame['anomaly_score'] = [float(i) for i in range(len(flags))]
        frame['direction'] = 'above'
        frame['history_median'] = 0.0
        frame['SubProcessDescription'] = 'fixture'
        return frame

    def test_one_day_gap_joins_and_longer_gap_splits(self):
        flags = [False, True, True, False, True, False, False, True]
        case_ids, cases = build_cases(self.flagged_frame(flags))
        self.assertEqual(len(cases), 2)
        self.assertEqual(case_ids.iloc[1], case_ids.iloc[4])
        self.assertNotEqual(case_ids.iloc[4], case_ids.iloc[7])
        self.assertEqual(case_ids.iloc[0], '')
        first = cases.set_index('start_date').loc['2022-01-02']
        self.assertEqual((first['flagged_days'], first['end_date'], first['peak_date']), (3, '2022-01-05', '2022-01-05'))

    def test_rule_cases_rank_first_within_each_plant(self):
        long_stat = self.flagged_frame([True] * 5, point='a')
        short_rule = self.flagged_frame([True], reasons=['dropout'], point='b')
        other_plant = self.flagged_frame([True] * 3, point='c', plant='other')
        _, cases = build_cases(pd.concat([long_stat, short_rule, other_plant], ignore_index=True))
        ranks = cases.set_index('MeasurementPointID')['plant_rank'].to_dict()
        self.assertEqual(ranks, {'b': 1, 'a': 2, 'c': 1})


class SyntheticFaultTest(unittest.TestCase):
    def test_injection_changes_only_the_copy_and_the_fault_window(self):
        original = series(varying(40, base=50.0), start='2025-01-01')
        untouched = original.copy()
        dates = pd.to_datetime(original['parsed_date'])
        for kind, length in FAULT_DAYS.items():
            starts = eligible_positions(dates, length, '2025-01-01', '2025-12-31')
            self.assertEqual(starts[0], 0)
            faulty = inject(original, kind, 0, spread=2.0)
            changed = pd.to_numeric(faulty['parsed_value']).ne(pd.to_numeric(original['parsed_value']))
            self.assertTrue(changed.iloc[:length].any())
            self.assertFalse(changed.iloc[length:].any())
        pd.testing.assert_frame_equal(original, untouched)
        dropped = inject(original, 'dropout', 5, 2.0)
        self.assertEqual(pd.to_numeric(dropped['parsed_value']).iloc[5:8].tolist(), [0.0] * 3)


if __name__ == '__main__':
    unittest.main()
