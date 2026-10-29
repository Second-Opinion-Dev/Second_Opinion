"""Checks that the prebuilt dashboard index is the one the dashboard itself reuses."""
from contextlib import closing
import csv
import gzip
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from dashboard_index import dashboard_server, is_current, progress_line, watch

SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'dashboard_index.py'
server = dashboard_server()


class DashboardIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.results, self.index = self.root / 'results', self.root / 'index.sqlite'
        (self.results / 'forest_oxygen').mkdir(parents=True)
        (self.results / 'history_oxygen').mkdir()
        (self.results / 'forest_oxygen/run_info.json').write_text(json.dumps(
            {'status': 'provisional_unvalidated', 'measurement': 'oxygen', 'threshold': 0.6}))
        (self.results / 'history_oxygen/run_info.json').write_text(json.dumps(
            {'status': 'provisional_unvalidated', 'measurement': 'oxygen'}))
        self.rows = [
            dict(InstallationCodeOrigin='test-plant', MeasurementPointID='test-point', Unit='mg/l', parsed_date='2025-01-01',
                 parsed_value='2', source_file='test', source_row='2', ai_status='eligible', ai_score='0.7', ai_flag='True',
                 history_median='1.5', score_status='scored', review_flag='True'),
            dict(InstallationCodeOrigin='test-plant', MeasurementPointID='test-point', Unit='mg/l', parsed_date='2025-01-02',
                 parsed_value='3', source_file='test', source_row='3', ai_status='ineligible', ai_score='', ai_flag='',
                 history_median='', score_status='unscored', review_flag=''),
        ]
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        with gzip.open(self.results / 'forest_oxygen/scored_records.csv.gz', 'wt', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=self.rows[0].keys())
            writer.writeheader()
            writer.writerows(self.rows)

    def build(self, *measurements):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--results', str(self.results), '--index', str(self.index),
                               '--measurement', *measurements], capture_output=True, text=True)

    def test_dashboard_reuses_the_prebuilt_index_without_reading_results(self):
        result = self.build('oxygen')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(is_current(self.results, self.index, ['oxygen']))
        with closing(sqlite3.connect(self.index)) as database:
            self.assertEqual(database.execute('SELECT flag FROM readings ORDER BY date').fetchall(), [(1,), (None,)])
        # Connecting the dashboard to the same folder must not stream the results again.
        with patch.object(server.gzip, 'open', side_effect=AssertionError('results were read again')):
            server.build_index(self.results, db_path=self.index)
        self.assertEqual(server.state['phase'], 'ready')
        self.assertEqual(server.state['metrics'], ['oxygen'])

    def test_changed_results_make_the_index_out_of_date(self):
        self.assertEqual(self.build('oxygen').returncode, 0)
        self.rows[0]['parsed_value'] = '7'
        self.write()
        self.assertFalse(is_current(self.results, self.index, ['oxygen']))
        self.assertFalse(is_current(self.results, self.root / 'missing.sqlite', ['oxygen']))

    def test_fails_when_a_required_measurement_is_not_indexed(self):
        result = self.build('oxygen', 'nitrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Not indexed: nitrate', result.stdout)
        self.assertFalse(is_current(self.results, self.index, ['oxygen', 'nitrate']))

    def test_flag_that_disagrees_with_the_threshold_fails_the_build(self):
        self.rows[0]['ai_flag'] = 'False'
        self.write()
        result = self.build('oxygen')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('threshold', result.stdout)

    def test_progress_goes_to_stderr_and_ends_with_the_finished_state(self):
        result = self.build('oxygen')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Not a terminal here, so plain lines and no redraws.
        self.assertNotIn('\r', result.stderr)
        self.assertIn('Index build finished: 2 rows, 1/6 measurements', result.stderr.strip().splitlines()[-1])
        self.assertNotIn('Index build', result.stdout)


class ProgressLineTest(unittest.TestCase):
    def state(self, **changes):
        return {'phase': 'indexing', 'message': '', 'processed': 40, 'skipped': 2, 'total': 100, 'metrics': ['oxygen'],
                **changes}

    def test_bar_shows_share_rows_measurements_and_time_left(self):
        line = progress_line(self.state(), 60, 6)
        self.assertIn(' 42.0%  42/100 rows, 1/6 measurements, 1m 00s elapsed, ~1m 22s left', line)
        bar = line[line.index('[') + 1:line.index(']')]
        self.assertEqual((bar.count('#'), len(bar)), (int(len(bar) * 0.42), len(bar)))
        self.assertLessEqual(len(progress_line(self.state(), 60, 6, width=40)), 40)

    def test_unknown_total_and_later_phases(self):
        self.assertNotIn('%', progress_line(self.state(total=None), 5, 6))
        self.assertTrue(progress_line(self.state(message='building_indexes'), 5, 6).startswith('Building lookup indexes'))
        self.assertTrue(progress_line(self.state(phase='ready', message='building_indexes'), 5, 6)
                        .startswith('Index build finished: 42 rows'))
        self.assertTrue(progress_line(self.state(phase='error'), 5, 6).startswith('Index build stopped'))

    def test_terminal_redraws_one_line_and_other_output_gets_whole_lines(self):
        for interactive in (True, False):
            stream, stop = io.StringIO(), threading.Event()
            stop.set()
            watch(self.state(phase='ready'), threading.Lock(), stream, interactive, stop, 6)
            text = stream.getvalue()
            self.assertEqual(text.startswith('\r'), interactive)
            self.assertTrue(text.endswith('\n'))
            self.assertEqual(text.count('\n'), 1)


if __name__ == '__main__':
    unittest.main()
