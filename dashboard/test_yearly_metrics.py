import unittest

import pandas as pd

from yearly_metrics import annual_medians


class AnnualMediansTest(unittest.TestCase):
    def test_duplicates_missing_and_outside_years(self):
        frame = pd.DataFrame({
            "ParsedDate": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-02", "2024-02-01", "2025-03-01", "2025-03-02", "2026-01-01"]),
            "NumericValue": [2, 10, 11, 5, None, 8, 999],
        })
        summary, excluded = annual_medians(frame)
        self.assertEqual(excluded, 1)
        self.assertEqual(summary.loc[2023, "median"], 2)
        self.assertEqual(summary.loc[2023, "count"], 1)
        self.assertEqual(summary.loc[2024, "median"], 5)
        self.assertEqual(summary.loc[2025, "median"], 8)
        self.assertEqual(summary.loc[2025, "count"], 1)

    def test_empty_period_has_no_zero_medians(self):
        frame = pd.DataFrame({"ParsedDate": pd.to_datetime(["2026-01-01"]), "NumericValue": [10.0]})
        summary, _ = annual_medians(frame)
        self.assertTrue(summary["median"].isna().all())
        self.assertEqual(summary["count"].sum(), 0)


if __name__ == "__main__": unittest.main()
