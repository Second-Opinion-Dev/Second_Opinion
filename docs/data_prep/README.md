# Data preparation

The preparation stage reads a Z-info table export, keeps every original record with its provenance, and produces quality flags and point metadata for the detectors downstream. It never deletes, imputes, averages, resamples or converts source data. Flags highlight candidate issues for review.

## Input

A directory with three folders of gzipped CSV files:

| Folder | Key columns used |
| --- | --- |
| `Installations/` | `Installation` |
| `MeasurementPoints/` | `MeasurementPointID`, `ProductDescription`, `QuantityDescription`, `ParameterDescription`, `Unit`, `InputType`, `StateDescription` |
| `MeasurementValues/` | `MeasurementPointID`, `Date`, `Value`, `Unit`, `InstallationCodeOrigin`, `SubProcessCodeOrigin`, `ProcessCode`, `Product`, `ProductBalance`, `InstallationCodeDestination`, `SubProcessDestination` |

The [pipeline driver](../../README.md#3-run-the-pipeline) expects this at `data/tai/extracted/`.

## Run

From the repository root, with a new or empty output directory:

```bash
python src/data_prep/tai_pipeline.py --raw data/tai/extracted --output data/tai/prepared_history
python src/data_prep/tai_verify.py data/tai/prepared_history
```

`--workers N` cleans up to N files at once in separate processes (default 1). The output is identical to a single-process run, including file order and the SQLite rows; the Installations and MeasurementPoints files run first so every value file is flagged against the complete metadata. Each worker writes its rows to a temporary shard database that is merged and removed, so allow extra disk space for up to `2 * N` shards. The cross-file index and duplicate queries at the end still run in one process. The pipeline driver takes the same option as `python src/pipeline.py --workers N`; it is not part of the stage's recorded settings, so changing it does not trigger a rerun.

`--limit-files N` creates a partial preparation for inspection. The detectors refuse partial output. A full export needs significant time and disk space for the SQLite index and compressed outputs. If a run fails, it leaves its partial output for inspection; use a fresh output path for the next attempt.

## Outputs

- `summary.json`: file inventory, counts and limitations.
- `point_metadata.csv.gz`: the measurement-point catalog used for selection.
- `cleaned/<table>/*.csv.gz`: every input row with `source_file`, `source_row`, parsed date and value, and flags such as `flag_blank_value`, `flag_invalid_value`, `flag_invalid_date`, `flag_unknown_point` and `flag_unknown_origin`.
- Quality reports: per-column blank and decoding-replacement counts, duplicate point IDs, point coverage, and same-point, same-date duplicate candidates.
- `working.sqlite`: a private intermediate.

`tai_verify.py` independently checks the retained row counts and the sequential source-row provenance against the inventory.

All outputs contain measurement-derived values and stay local.

## Supplementary reports

Each script takes a completed preparation directory:

| Script | Purpose |
| --- | --- |
| `tai_sequence_report.py` | Per point: calendar gaps between observations, repeated adjacent values and unit changes. A gap is not proof of a missing reading. |
| `tai_metadata_report.py` | Points with missing, unique or multiple metadata rows; metadata combinations; a data dictionary with meanings marked unconfirmed. |
| `tai_installation_report.py` | Literal origin and destination installation codes checked against `Installation`, including blanks and possible row multiplication. |
| `tai_candidate_slice.py` | Copies records whose metadata literally says `Influent` / `Volume` into an exploratory slice. |
| `tai_review_candidates.py` | Copies blank, unparsable and unmatched-point records for inspection, without removing them from the retained data. |

## Caveats

- Duplicate detection uses literal date strings and a 64-bit hash, so its results are candidates, not proof that records are equal.
- `flag_unknown_origin` is a literal key check. The authoritative relationship between installations and measurements needs confirmation from the data provider.
- Missing dates and missing rows are different things. The sequence report does not establish an expected sampling frequency.

Code: [`src/data_prep/`](../../src/data_prep/). Tests: [`tests/test_tai_pipeline.py`](../../tests/test_tai_pipeline.py).
