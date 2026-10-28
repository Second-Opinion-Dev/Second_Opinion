import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from results import case_key, evidence, filtered_cases, load_metric, notifications, parse_flag
from measurement_table import scored_measurement_table


class ResultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        forest = self.root / "forest_oxygen"
        history = self.root / "history_oxygen"
        forest.mkdir(); history.mkdir()
        (forest / "run_info.json").write_text(json.dumps({"status":"provisional_unvalidated", "measurement":"oxygen", "threshold":0.6}))
        (history / "run_info.json").write_text(json.dumps({"status":"smoke_run_partial", "measurement":"oxygen"}))
        self.rows = pd.DataFrame([
            dict(InstallationCodeOrigin="plant", MeasurementPointID="point", parsed_date="2025-01-02", parsed_value="4", Unit="mg/l", source_file="source", source_row="2", ai_status="eligible", ai_score="0.7", ai_flag="True", history_median="2", score_status="scored", review_flag="True"),
            dict(InstallationCodeOrigin="plant", MeasurementPointID="point", parsed_date="2025-01-03", parsed_value="3", Unit="mg/l", source_file="source", source_row="3", ai_status="eligible", ai_score="0.5", ai_flag="False", history_median="2", score_status="scored", review_flag="False"),
            dict(InstallationCodeOrigin="plant", MeasurementPointID="point", parsed_date="2025-01-04", parsed_value="", Unit="mg/l", source_file="source", source_row="4", ai_status="unscored", ai_score="", ai_flag="", history_median="", score_status="unscored", review_flag=""),
        ])
        self.write()

    def tearDown(self): self.temp.cleanup()

    def write(self): self.rows.to_csv(self.root / "forest_oxygen" / "scored_records.csv.gz", index=False, compression="gzip")

    def test_nullable_flags_and_provenance(self):
        data, _, _ = load_metric(self.root, "oxygen")
        self.assertEqual(data.forest_flag.tolist(), [True, False, None])
        self.assertEqual(data.iloc[0].case_key, case_key("oxygen", "source", "2"))
        self.assertNotEqual(case_key("oxygen", "source", "2"), case_key("ammonium", "source", "2"))
        self.assertEqual(len(filtered_cases(data, "plant", "2025-01-01", "2025-01-31")), 1)
        self.assertIn("4 mg/l", evidence(data.iloc[0]))
        self.assertIn("2 mg/l", evidence(data.iloc[0], dutch=True))

    def test_wrong_flag_or_duplicate_is_rejected(self):
        self.rows.loc[0, "ai_flag"] = "False"; self.write()
        with self.assertRaisesRegex(ValueError, "threshold"): load_metric(self.root, "oxygen")
        self.rows.loc[0, "ai_flag"] = "True"
        self.rows.loc[1, "source_row"] = "2"; self.write()
        with self.assertRaisesRegex(ValueError, "provenance"): load_metric(self.root, "oxygen")

    def test_missing_and_unexpected_flags_are_not_normal(self):
        self.assertIsNone(parse_flag(None))
        self.assertIsNone(parse_flag("unknown"))
        self.assertFalse(parse_flag("False"))

    def test_table_highlights_flags_without_marking_unassessed_as_normal(self):
        data, _, _ = load_metric(self.root, "oxygen")
        data.loc[2, "parsed_value"] = 2
        data["Value"] = data.parsed_value.astype("string")
        table = scored_measurement_table(data, "2025-01-02", "2025-01-04")
        self.assertEqual(table.count('class="day flag"'), 1)
        self.assertIn('class="day unassessed"', table)
        self.assertIn("2025", table)

    def test_all_metrics_keep_same_point_and_day_separate(self):
        data, _, _ = load_metric(self.root, "oxygen")
        second = data.iloc[[0]].copy()
        second["metric"] = "ammonium"
        second["parsed_value"] = 9
        second["Value"] = "9"
        original = data.iloc[[0]].copy()
        original["Value"] = "4"
        table = scored_measurement_table(pd.concat([original, second]), "2025-01-02", "2025-01-02")
        self.assertIn("Oxygen", table)
        self.assertIn("Ammonium", table)
        self.assertEqual(table.count('class="day flag"'), 2)

    def test_notifications_use_plant_and_date_not_cross_model_scores(self):
        data, _, _ = load_metric(self.root, "oxygen")
        oxygen = data.iloc[[0]].copy()
        ammonium = oxygen.copy()
        ammonium["metric"] = "ammonium"
        ammonium["date"] = pd.Timestamp("2025-01-03")
        ammonium["ai_score"] = 0.61
        ammonium["case_key"] = case_key("ammonium", "source", "2")
        alerts = notifications({"oxygen": oxygen, "ammonium": ammonium}, "plant", "2025-01-01", "2025-01-03")
        self.assertEqual(alerts.metric.tolist(), ["ammonium", "oxygen"])
        self.assertEqual(len(notifications({"oxygen": oxygen}, "other", "2025-01-01", "2025-01-03")), 0)
        self.assertEqual(len(notifications({"oxygen": oxygen}, "plant", "2025-01-03", "2025-01-03")), 0)


if __name__ == "__main__": unittest.main()
