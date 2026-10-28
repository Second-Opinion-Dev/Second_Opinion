import unittest

from results import DEMO_METRICS, DEMO_PLANT, demo_metric, evidence, notifications


class DemoMetricsTest(unittest.TestCase):
    def test_examples_are_isolated_and_explanations_are_honest(self):
        frames = {metric: demo_metric(metric) for metric in DEMO_METRICS}
        for frame in frames.values():
            self.assertEqual(set(frame.InstallationCodeOrigin), {DEMO_PLANT})
            flagged = frame.loc[frame.forest_flag]
            self.assertEqual(len(flagged), 1)
            self.assertIn("No model was run", evidence(flagged.iloc[0]))
        self.assertEqual(len(notifications(frames, DEMO_PLANT, "2025-12-18", "2025-12-31")), 3)
        self.assertTrue(notifications(frames, "real plant", "2025-12-18", "2025-12-31").empty)


if __name__ == "__main__":
    unittest.main()
