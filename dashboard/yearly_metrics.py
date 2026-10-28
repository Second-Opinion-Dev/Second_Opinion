"""Small descriptive summaries of one local measurement series."""
import numpy as np
import pandas as pd

YEARS = (2023, 2024, 2025)


def annual_medians(records: pd.DataFrame):
    """Median recorded value per year; exclude all ambiguous duplicate dates."""
    data = records.loc[records["ParsedDate"].notna()].copy()
    data = data.loc[data["ParsedDate"].dt.year.isin(YEARS)]
    # A missing row on the same day does not make another reading unique.
    duplicate = data["ParsedDate"].duplicated(keep=False)
    excluded = int(data.loc[duplicate, "ParsedDate"].nunique())
    data = data.loc[~duplicate & np.isfinite(data["NumericValue"].astype(float))].copy()
    summary = data.groupby(data["ParsedDate"].dt.year)["NumericValue"].agg(["median", "count"]).reindex(YEARS)
    summary["count"] = summary["count"].fillna(0).astype(int)
    summary.index.name = "year"
    return summary, excluded
