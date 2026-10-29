"""Checks of the pipeline driver's skip, adopt, rerun, parallel and failure handling with stub stages."""
import json
from pathlib import Path
import tempfile
import time
import unittest

from pipeline import Stage, build_stages, execute

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

    def stage(self, name, setting='a', needs=(), adoptable=False):
        output = self.root / name
        return Stage(name, self.script, [str(output), setting], output,
                     lambda: (output / 'done.txt').is_file(), needs=list(needs),
                     code=[self.script], adoptable=adoptable)

    def actions(self, stages, forced=(), jobs=1):
        return [action for _, action, _ in execute(stages, self.state, list(forced), dry_run=False, jobs=jobs)]

    def times(self, name):
        start, end = (self.root / name / 'done.txt').read_text().split()
        return float(start), float(end)

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


if __name__ == '__main__':
    unittest.main()
