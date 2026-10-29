"""Checks of the shared progress line: format, terminal redraws and plain lines elsewhere."""
import io
import time
import unittest
from unittest.mock import patch

import progress_bar
from progress_bar import Progress, bar_line, duration


class ProgressBarTest(unittest.TestCase):
    def test_durations(self):
        self.assertEqual([duration(s) for s in (5, 65, 3725)], ['5s', '1m 05s', '1h 02m'])

    def test_bar_line_shape_and_width(self):
        line = bar_line('Working', 0.25, '1/4 files', 30, width=100)
        self.assertTrue(line.startswith('Working ['))
        self.assertIn(']  25.0%  1/4 files, 30s elapsed, ~1m 30s left', line)
        bar = line[line.index('[') + 1:line.index(']')]
        self.assertEqual(bar.count('#'), len(bar) // 4)
        self.assertNotIn('left', bar_line('Working', 0, '0/4 files', 0))
        self.assertLessEqual(len(bar_line('Working', 0.5, '2/4 files', 30, width=30)), 30)

    def test_terminal_redraws_in_place_and_messages_keep_the_line(self):
        stream, printed = io.StringIO(), io.StringIO()
        progress = Progress(stream, interactive=True)
        with patch.object(progress, 'width', return_value=100):
            progress.show('first, longer line', force=True)
            progress.show('second', force=True)
            progress.message('ordinary output', stream=printed)
            progress.close('done')
        text = stream.getvalue()
        # The shorter line is padded over the longer one, the message clears it, and close ends it.
        self.assertIn('\rsecond            ', text)
        self.assertIn('\r' + ' ' * len('second') + '\r', text)
        self.assertTrue(text.endswith('\rdone  \n'))  # padded over the redrawn 'second'
        self.assertEqual(printed.getvalue(), 'ordinary output\n')

    def test_other_output_gets_a_line_per_interval(self):
        stream = io.StringIO()
        progress = Progress(stream, interactive=False)
        progress.show('too soon')
        self.assertEqual(stream.getvalue(), '')
        with patch.object(progress_bar, 'LINE_INTERVAL', 0):
            progress.show('after the interval')
        progress.close('done')
        self.assertEqual(stream.getvalue(), 'after the interval\ndone\n')

    def test_phase_counts_elapsed_time_while_a_step_runs(self):
        stream = io.StringIO()
        progress = Progress(stream, interactive=True)
        with patch.object(progress, 'width', return_value=100):
            with progress.phase('Building'):
                time.sleep(0.1)
        self.assertIn('\rBuilding ... 0s elapsed', stream.getvalue())


if __name__ == '__main__':
    unittest.main()
