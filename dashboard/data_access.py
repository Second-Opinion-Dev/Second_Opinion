"""Local data access and review-queue helpers for the dashboard."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tai" / "extracted"
CASE_COLUMNS = {"case_id", "installation", "measurement_point_id", "date", "reason", "rank"}


def read_gzip(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, compression="gzip", encoding="utf-8", encoding_errors="replace", dtype="string", **kwargs)


def catalog(root: Path = DATA):
    frames = []
    for path in sorted((root / "MeasurementPoints").glob("*.csv.gz")):
        frame = read_gzip(path)
        frame["InstallationCode"] = path.name[:-7]
        frames.append(frame)
    names = {}
    for path in sorted((root / "Installations").glob("*.csv.gz")):
        frame = read_gzip(path)
        if {"Installation", "Installation Description"}.issubset(frame.columns):
            for code, name in frame[["Installation", "Installation Description"]].itertuples(index=False, name=None):
                if pd.notna(code):
                    names[str(code)] = "" if pd.isna(name) else str(name)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), names


def values(path: Path) -> pd.DataFrame:
    frame = read_gzip(path)
    frame["ParsedDate"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["NumericValue"] = pd.to_numeric(frame["Value"].fillna("").str.strip().str.replace(",", ".", regex=False), errors="coerce")
    return frame


def daily_grid(records: pd.DataFrame, points: pd.DataFrame, start, end) -> pd.DataFrame:
    """Build a date-column grid without merging repeated source observations."""
    selected = records.loc[records["ParsedDate"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    keys = ["ProcessCode", "SubProcessDescription", "MeasurementPointID", "Unit"]
    if selected.empty:
        return pd.DataFrame(columns=keys + ["MeasurementObjectDescription"])
    selected[keys] = selected[keys].fillna("")
    selected["Value"] = selected["Value"].fillna("")
    selected["Occurrence"] = selected.groupby(keys + ["ParsedDate"], dropna=False, sort=False).cumcount()
    selected["Day"] = selected["ParsedDate"].dt.strftime("%Y-%m-%d")
    grid = selected.pivot(index=keys + ["Occurrence"], columns="Day", values="Value").reset_index()
    metadata = points[["MeasurementPointID", "MeasurementObjectDescription"]].drop_duplicates("MeasurementPointID")
    grid = grid.merge(metadata, on="MeasurementPointID", how="left", validate="many_to_one")
    grid["MeasurementObjectDescription"] = grid["MeasurementObjectDescription"].fillna("")
    days = pd.date_range(start, end).strftime("%Y-%m-%d").tolist()
    grid = grid.reindex(columns=keys + ["MeasurementObjectDescription", "Occurrence"] + days)
    return grid.sort_values(keys + ["Occurrence"], kind="stable").reset_index(drop=True)


def read_cases(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype="string", encoding="utf-8-sig")
    missing = CASE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    if frame[list(CASE_COLUMNS)].isna().any().any() or frame[list(CASE_COLUMNS)].apply(lambda s: s.str.strip().eq("").any()).any():
        raise ValueError("Required fields cannot be blank.")
    if frame["case_id"].duplicated().any():
        raise ValueError("case_id values must be unique.")
    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    if frame["rank"].isna().any() or (frame["rank"] <= 0).any() or frame["rank"].duplicated().any():
        raise ValueError("rank must be a unique positive number for each case.")
    if pd.to_datetime(frame["date"], errors="coerce").isna().any():
        raise ValueError("Each date must be a valid date.")
    return frame.sort_values("rank", kind="stable").reset_index(drop=True)
