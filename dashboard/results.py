"""Read the team's precomputed, private detector outputs without loading models."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = ("influent_volume", "oxygen", "ammonium", "temperature", "nitrate", "suspended_solids")
DEMO_METRICS = ("temperature", "nitrate", "suspended_solids")
DEMO_PLANT = "NL.07.VOORBEELD — RWZI Voorbeeld"
REQUIRED = {"InstallationCodeOrigin", "MeasurementPointID", "parsed_date", "parsed_value", "Unit", "source_file", "source_row", "ai_status", "ai_score", "ai_flag", "history_median", "score_status", "review_flag"}
# Only the columns the app uses are read: full runs hold millions of rows, and reading
# every column as text exhausted memory. Repeated labels are categories, scores are floats.
CONTEXT = ("InstallationCodeOrigin", "MeasurementPointID", "SubProcessCodeOrigin", "ProcessCode", "SubProcessDescription",
           "Product", "ProductBalance", "InstallationCodeDestination", "SubProcessDestination", "Unit", "source_file",
           "ai_status", "score_status")
NUMERIC = ("parsed_value", "history_median", "history_scale", "anomaly_score", "ai_score", "signed_deviation_log",
           "day_change_log", "prior_deviation_log_mean", "relative_level_log", "is_zero", "repeat_days_log")
TEXT = ("Value", "source_row", "parsed_date", "ai_flag", "review_flag")
COLUMNS = set(CONTEXT) | set(NUMERIC) | set(TEXT)
DTYPES = {**{c: "category" for c in CONTEXT}, **{c: "float64" for c in NUMERIC}, **{c: "string" for c in TEXT}}


def parse_flag(value):
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in ("true", "1"):
        return True
    if text in ("false", "0"):
        return False
    return None


def case_key(metric, source_file, source_row):
    raw = f"{metric}\0{source_file}\0{source_row}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def demo_metric(metric):
    """Fictional, explicitly labelled UI examples; no detector was run on these."""
    examples = {
        "temperature": ("°C", [12.1, 12.2, 12.0, 11.9, 12.1, 12.2, 12.0, 12.1, 12.2, 12.0, 12.1, 12.2, 12.0, 18.0]),
        "nitrate": ("mg/l", [3.1, 3.2, 3.0, 3.1, 3.2, 3.0, 3.1, 3.2, 3.0, 3.1, 3.2, 3.0, 3.1, 8.0]),
        "suspended_solids": ("g/l", [3.0, 3.1, 3.0, 3.2, 3.1, 3.0, 3.1, 3.0, 3.2, 3.1, 3.0, 3.1, 3.0, 5.5]),
    }
    unit, values = examples[metric]
    rows = []
    for i, (date, value) in enumerate(zip(pd.date_range("2025-12-18", periods=14), values)):
        flagged = i == len(values) - 1
        point = {"temperature": "07.VBwlBI.mi-001.T", "nitrate": "07.VBwlBI.mi-004.NO3", "suspended_solids": "07.VBwlBI.mi-006.OB"}[metric]
        rows.append(dict(InstallationCodeOrigin=DEMO_PLANT, MeasurementPointID=point,
            date=date, parsed_value=value, Value=str(value), Unit=unit, metric=metric,
            forest_flag=flagged, ai_score=1.0 if flagged else 0.0, history_median=float(np.median(values[:-1])),
            source_file="SYNTHETIC DEMO", source_row=i + 1, ProcessCode="oxt", SubProcessDescription="Oxische tank",
            case_key=case_key(metric, "SYNTHETIC DEMO", i + 1) if flagged else "", is_demo=True))
    return pd.DataFrame(rows)


def source_fingerprint(root: Path):
    """Cache key changes whenever a relevant output is replaced."""
    result = []
    for metric in METRICS:
        for relative in (f"forest_{metric}/run_info.json", f"forest_{metric}/scored_records.csv.gz", f"history_{metric}/run_info.json"):
            path = root / relative
            if path.is_file():
                stat = path.stat()
                result.append((relative, stat.st_mtime_ns, stat.st_size))
            else:
                result.append((relative, None, None))
    return tuple(result)


def load_metric(root: Path, metric: str):
    if metric not in METRICS:
        raise ValueError("Unsupported metric")
    directory = root / f"forest_{metric}"
    info_path = directory / "run_info.json"
    scores_path = directory / "scored_records.csv.gz"
    history_info_path = root / f"history_{metric}" / "run_info.json"
    if not all(p.is_file() for p in (info_path, scores_path, history_info_path)):
        raise FileNotFoundError(f"Incomplete results for {metric}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    history_info = json.loads(history_info_path.read_text(encoding="utf-8"))
    if info.get("measurement") != metric or history_info.get("measurement") != metric:
        raise ValueError(f"Metric metadata mismatch: {metric}")
    if info.get("status") != "provisional_unvalidated" or history_info.get("status") not in {"smoke_run_partial", "provisional_unvalidated"}:
        raise ValueError(f"Incomplete or unsupported run status: {metric}")
    frame = pd.read_csv(scores_path, compression="gzip", usecols=lambda column: column in COLUMNS,
                        dtype=DTYPES, low_memory=False)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing fields for {metric}: {', '.join(sorted(missing))}")
    if frame[["source_file", "source_row"]].isna().any().any() or frame.duplicated(["source_file", "source_row"]).any():
        raise ValueError(f"Missing or duplicate source provenance: {metric}")
    frame["metric"] = metric
    frame["date"] = pd.to_datetime(frame["parsed_date"], errors="coerce")
    for column in ("parsed_value", "ai_score", "history_median", "anomaly_score", "history_scale"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["forest_flag"] = frame["ai_flag"].map(parse_flag)
    eligible = frame["ai_status"].eq("eligible") & frame["date"].notna() & np.isfinite(frame["parsed_value"].astype(float)) & np.isfinite(frame["ai_score"].astype(float))
    threshold = info.get("threshold")
    if not isinstance(threshold, (int, float)) or not np.isfinite(threshold):
        raise ValueError(f"Missing or invalid forest threshold: {metric}")
    if frame.loc[eligible, "forest_flag"].isna().any() or (frame.loc[eligible, "forest_flag"] != frame.loc[eligible, "ai_score"].ge(threshold)).any():
        raise ValueError(f"Stored forest flags disagree with the model threshold: {metric}")
    frame.loc[~eligible, "forest_flag"] = None
    flagged = frame["forest_flag"].eq(True)
    frame["case_key"] = ""
    frame.loc[flagged, "case_key"] = [case_key(metric, f, r) for f, r in zip(frame.loc[flagged, "source_file"], frame.loc[flagged, "source_row"])]
    if frame.loc[flagged, "case_key"].duplicated().any():
        raise ValueError(f"Case identifier collision: {metric}")
    return frame, info, history_info


def filtered_cases(frame, plant, start, end, point=None):
    cases = frame.loc[frame["forest_flag"].eq(True) & frame["InstallationCodeOrigin"].eq(plant) & frame["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    if point:
        cases = cases.loc[cases["MeasurementPointID"].eq(point)]
    return cases.sort_values(["ai_score", "date", "source_file", "source_row"], ascending=[False, False, True, True], kind="stable")


def notifications(frames, plant, start, end, point=None):
    """Find already-scored flags across metrics; sort by date, never by cross-model score."""
    groups = []
    for metric in METRICS:
        frame = frames.get(metric)
        if frame is None or frame.empty:
            continue
        cases = filtered_cases(frame, plant, start, end, point)
        if not cases.empty:
            groups.append(cases)
    if not groups:
        return pd.DataFrame()
    combined = pd.concat(groups, ignore_index=True)
    return combined.sort_values(["date", "metric", "case_key"], ascending=[False, True, True], kind="stable").reset_index(drop=True)


def evidence(case, dutch=False):
    value = case.get("parsed_value")
    unit = case.get("Unit", "")
    median = case.get("history_median")
    score = case.get("ai_score")
    if case.get("is_demo") is True or case.get("source_file") == "SYNTHETIC DEMO":
        if dutch:
            return f"De gesimuleerde meting is {value:g} {unit}. De melding is handmatig toegevoegd; er is geen model uitgevoerd."
        return f"The simulated reading is {value:g} {unit}. The flag was added manually. No model was run."
    if dutch:
        lines = [f"De meting op {case['date'].date()} is {value:g} {unit}. De Isolation Forest markeerde deze met een score van {score:.4f}."]
        if pd.notna(median): lines.append(f"De historische mediaan was {median:g} {unit}.")
        lines.append("Bedrijfsgrenzen zijn niet beschikbaar. Controleer de meting en relevante bedrijfsgegevens; de oorzaak is onbekend.")
    else:
        lines = [f"The reading on {case['date'].date()} is {value:g} {unit}. The Isolation Forest flagged it with a score of {score:.4f}."]
        if pd.notna(median): lines.append(f"The historical median was {median:g} {unit}.")
        lines.append("Operational limits are unavailable. Check the reading and relevant operating records; the cause is unknown.")
    return " ".join(lines)
