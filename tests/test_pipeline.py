"""Checks of the pipeline driver's skip, adopt, rerun, parallel and failure handling with stub stages."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from pipeline import LiveStages, Stage, build_stages, execute, fingerprint, overview, progress_file, run_stage
from progress_bar import PROGRESS_FILE_ENV

# A stub stage: 'fail' exits with an error, 'sleepX' waits X seconds; it records its start and end times.
STUB = '''import sys, time
from pathlib import Path
output, setting, start = Path(sys.argv[1]), sys.argv[2], time.time()
if setting == 'fail':
    sys.exit(3)
if setting.startswith('sleep'):
    time.sleep(float(setting[5:]))
output.mkdir(parents=True, exist_ok=True)
(output / 'done.txt').write_text(f'{start} {time.time()}')
'''


class DriverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.script = self.root / 'stub.py'
        self.script.write_text(STUB)
        self.state = self.root / 'run' / 'state.json'

    def tearDown(self):
        self.tmp.cleanup()

    def folder(self, name):
        # Stage names like 'detect:x' are not valid folder names on Windows.
        return self.root / name.replace(':', '_')

    def stage(self, name, setting='a', needs=(), adoptable=False):
        output = self.folder(name)
        return Stage(name, self.script, [str(output), setting], output,
                     lambda: (output / 'done.txt').is_file(), needs=list(needs),
                     code=[self.script], adoptable=adoptable)

    def actions(self, stages, forced=(), jobs=1):
        return [action for _, action, _ in execute(stages, self.state, list(forced), dry_run=False, jobs=jobs)]

    def times(self, name):
        start, end = (self.folder(name) / 'done.txt').read_text().split()
        return float(start), float(end)

    def test_status_shows_what_a_running_stage_reports(self):
        stage = self.stage('long')
        status = LiveStages([(stage, 'run', 'not done yet')], self.root / 'logs')
        status.set('long', 'running')
        progress_file(stage, self.root / 'logs').parent.mkdir()
        progress_file(stage, self.root / 'logs').write_text(json.dumps({'share': 0.25, 'text': 'Working 25%'}))
        status.refresh()
        entry = status.by_name['long']
        self.assertEqual((entry['state'], entry['share'], entry['text']), ('running', 0.25, 'Working 25%'))
        self.assertIsNotNone(entry['seconds'])

    def test_stage_output_goes_to_its_log_and_messages_to_the_driver(self):
        stage = self.stage('kept')
        (self.root / 'kept').mkdir()
        (self.root / 'kept' / 'old.txt').write_text('earlier')
        said = []
        with patch('pipeline.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            with self.assertRaises(SystemExit):  # the patched stage writes no output, so it counts as incomplete
                run_stage(stage, self.root / 'logs', said.append)
        self.assertIs(run.call_args.kwargs['stderr'], subprocess.STDOUT)
        self.assertEqual(run.call_args.kwargs['stdout'].name, str(self.root / 'logs' / 'kept.log'))
        self.assertTrue(said[0].startswith('    previous output kept at '))

    def test_status_line_shows_one_stage_in_full_and_several_in_brief(self):
        entries = [{'name': 'prepare', 'action': 'skip', 'state': 'done', 'share': None, 'text': '', 'seconds': None},
                   {'name': 'verify', 'action': 'run', 'state': 'done', 'share': 1.0, 'text': '', 'seconds': 50},
                   {'name': 'detect:oxygen', 'action': 'run', 'state': 'running', 'share': 0.5,
                    'text': 'Detecting [###---]  50.0%  step 2/4: scoring series 10/20', 'seconds': 5},
                   {'name': 'detect:nitrate', 'action': 'run', 'state': 'pending', 'share': None, 'text': '', 'seconds': None}]
        share, text = overview(entries, 70)
        self.assertEqual(share, 0.5)
        self.assertEqual(text, '[1/3] Detecting [###---]  50.0%  step 2/4: scoring series 10/20')
        entries[3].update(state='running', seconds=12)
        share, text = overview(entries, 70)
        self.assertAlmostEqual(share, 1.5 / 3)
        self.assertTrue(text.startswith('Pipeline ['))
        self.assertIn('1/3 steps · detect:oxygen 50%, detect:nitrate 12s, 1m 10s elapsed', text)
        self.assertNotIn('left', text)
        self.assertLessEqual(len(overview(entries, 70, width=40)[1]), 40)

    def test_a_report_left_by_an_earlier_run_is_ignored(self):
        stage = self.stage('long')
        report = progress_file(stage, self.root / 'logs')
        report.parent.mkdir()
        report.write_text(json.dumps({'share': 1.0, 'text': 'Finished last time'}))
        os.utime(report, (time.time() - 600, time.time() - 600))
        status = LiveStages([(stage, 'run', 'not done yet')], self.root / 'logs')
        status.set('long', 'running')
        status.refresh()
        entry = status.by_name['long']
        self.assertEqual((entry['share'], entry['text']), (None, ''))

    def test_an_old_report_that_cannot_be_removed_does_not_stop_the_stage(self):
        # On Windows the driver can be reading the old report at the moment the stage starts.
        stage = Stage('s', self.script, [], None, lambda: True)
        with patch('pipeline.Path.unlink', side_effect=PermissionError(32, 'in use')), \
                patch('pipeline.subprocess.run', return_value=subprocess.CompletedProcess([], 0)):
            self.assertGreaterEqual(run_stage(stage, self.root / 'logs'), 0)

    def test_an_unexpected_stage_error_fails_that_stage_and_not_the_driver(self):
        stages = [self.stage('broken'), self.stage('other', setting='sleep0.5')]
        real_run_stage = run_stage

        def flaky(stage, logs, say=print):
            if stage.name == 'broken':
                raise OSError('disk trouble')
            return real_run_stage(stage, logs, say)

        with patch('pipeline.run_stage', side_effect=flaky):
            with self.assertRaises(SystemExit) as raised:
                execute(stages, self.state, [], dry_run=False, jobs=2)
        self.assertIn('broken failed: OSError: disk trouble', str(raised.exception))
        recorded = [key.split('|')[0] for key in json.loads(self.state.read_text())]
        self.assertEqual(recorded, ['other'])

    def test_stage_gets_its_progress_file_through_the_environment(self):
        stage = Stage('s:x', self.script, [], None, lambda: True)
        with patch('pipeline.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            run_stage(stage, self.root / 'logs')
        self.assertEqual(run.call_args.kwargs['env'][PROGRESS_FILE_ENV], str(self.root / 'logs' / 's_x.progress.json'))

    def test_independent_stages_run_at_the_same_time(self):
        stages = [self.stage(name, setting='sleep1') for name in ('a', 'b', 'c')]
        began = time.monotonic()
        self.assertEqual(self.actions(stages, jobs=3), ['run'] * 3)
        self.assertLess(time.monotonic() - began, 2.5)  # one at a time would take over 3 seconds
        spans = [self.times(name) for name in ('a', 'b', 'c')]
        self.assertLess(max(start for start, _ in spans), min(end for _, end in spans))

    def test_parallel_run_waits_for_needed_stages(self):
        stages = [self.stage('up', setting='sleep0.5'), self.stage('side', setting='sleep0.5'),
                  self.stage('down', needs=['up'])]
        self.actions(stages, jobs=3)
        self.assertGreaterEqual(self.times('down')[0], self.times('up')[1])

    def test_parallel_failure_finishes_running_stages_and_blocks_downstream(self):
        stages = [self.stage('broken', setting='fail'), self.stage('other', setting='sleep0.5'),
                  self.stage('after', needs=['broken'])]
        with self.assertRaises(SystemExit) as raised:
            self.actions(stages, jobs=2)
        self.assertIn('broken failed', str(raised.exception))
        recorded = [key.split('|')[0] for key in json.loads(self.state.read_text())]
        self.assertEqual(recorded, ['other'])
        self.assertFalse((self.root / 'after').exists())
        # The next run skips what finished and retries only the rest.
        fixed = [self.stage('broken'), self.stage('other', setting='sleep0.5'), self.stage('after', needs=['broken'])]
        self.assertEqual(self.actions(fixed, jobs=2), ['run', 'skip', 'run'])

    def test_second_run_skips_and_changed_settings_rerun_downstream(self):
        stages = [self.stage('up'), self.stage('down', needs=['up'])]
        self.assertEqual(self.actions(stages), ['run', 'run'])
        self.assertEqual(self.actions(stages), ['skip', 'skip'])
        changed = [self.stage('up', setting='b'), self.stage('down', needs=['up'])]
        self.assertEqual(self.actions(changed), ['run', 'run'])
        # The earlier output is moved aside, never deleted.
        self.assertEqual(len(list(self.root.glob('up.old-*'))), 1)

    def test_complete_output_is_adopted_only_when_allowed(self):
        for name in ('prepared', 'scores'):
            (self.root / name).mkdir()
            (self.root / name / 'done.txt').write_text('earlier')
        stages = [self.stage('prepared', adoptable=True), self.stage('scores', needs=['prepared'])]
        self.assertEqual(self.actions(stages), ['adopt', 'run'])
        self.assertEqual((self.root / 'prepared' / 'done.txt').read_text(), 'earlier')
        self.assertEqual(self.actions(stages), ['skip', 'skip'])

    def test_force_by_prefix_and_downstream(self):
        stages = [self.stage('base'), self.stage('detect:x', needs=['base']),
                  self.stage('detect:y', needs=['base']), self.stage('forest:x', needs=['detect:x'])]
        self.actions(stages)
        self.assertEqual(self.actions(stages, forced=['detect']), ['skip', 'run', 'run', 'run'])

    def test_failure_stops_and_is_not_recorded(self):
        stages = [self.stage('good'), self.stage('bad', setting='fail', needs=['good'])]
        with self.assertRaises(SystemExit):
            self.actions(stages)
        recorded = json.loads(self.state.read_text())
        self.assertEqual([key.split('|')[0] for key in recorded], ['good'])
        self.assertEqual(self.actions([self.stage('good')]), ['skip'])

    def test_plan_only_runs_nothing(self):
        report = execute([self.stage('up')], self.state, [], dry_run=True)
        self.assertEqual([action for _, action, _ in report], ['run'])
        self.assertFalse((self.root / 'up').exists())
        self.assertFalse(self.state.exists())

    def test_real_stage_list_orders_dependencies(self):
        stages = build_stages(self.root, ['oxygen'], smoke=5, with_faults=True, target_flag_rate=0.01, fault_sample=3)
        names = [stage.name for stage in stages]
        self.assertEqual(names, ['prepare', 'verify', 'detect:oxygen', 'forest:oxygen', 'faults:oxygen'])
        for position, stage in enumerate(stages):
            self.assertTrue(all(need in names[:position] for need in stage.needs))
            self.assertTrue(stage.script.is_file())
        self.assertIn('--max-points', stages[2].args)

    def test_full_run_ends_with_the_dashboard_index(self):
        stages = build_stages(self.root, ['oxygen', 'nitrate'], None, False, 0.01, 3)
        self.assertEqual(stages[-1].name, 'index')
        self.assertEqual(stages[-1].needs, ['forest:oxygen', 'forest:nitrate'])
        self.assertTrue(stages[-1].script.is_file())
        self.assertFalse(stages[-1].done())  # no results under the test folder
        smoke = build_stages(self.root, ['oxygen'], 5, False, 0.01, 3)
        self.assertNotIn('index', [stage.name for stage in smoke])

    def test_prepare_workers_change_the_command_but_not_the_fingerprint(self):
        one = build_stages(self.root, ['oxygen'], None, False, 0.01, 3)[0]
        four = build_stages(self.root, ['oxygen'], None, False, 0.01, 3, workers=4)[0]
        self.assertEqual(one.run_args, ['--workers', '1'])
        self.assertEqual(four.run_args, ['--workers', '4'])
        self.assertEqual(fingerprint(one, {}), fingerprint(four, {}))


if __name__ == '__main__':
    unittest.main()
