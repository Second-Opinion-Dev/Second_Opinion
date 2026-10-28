# TAI data preparation handoff

This is an early implementation based on `idea.md` from fetched `origin/main` at commit `b9151e8`. That document has no team-division section; this scope follows Oindrilla's assignment. Do not call the data or a peer set approved until TAI confirms the meanings and comparability.

## Setup and execution

Python 3.11+ and pandas are required. Use a private directory outside the Git repository for partner data and reports. The organiser key is read from the `AISO_API_KEY` environment variable; obtain its value from the participant briefing and set it privately in the current shell. Do not paste it into a shared document, commit, command history or chat.

From the repository root, on Windows PowerShell:

```powershell
python -m pip install pandas
python tai_redownload.py --output '../tai-redownload' --previous-manifest '../hackathon-downloads/download-manifest.json'
python tai_pipeline.py --raw '../tai-redownload/extracted' --output '../tai-analysis/pipeline-redownload'
python tai_sequence_report.py '../tai-analysis/pipeline-redownload'
```

The downloader requires a new output directory and verifies archive size, official SHA-256 when supplied, extracted sizes, gzip integrity and SHA-256 hashes. It compares the archive hash to the earlier manifest if provided. A changed hash needs investigation, not an automatic corruption conclusion. Do not run it until the key is set. It does not overwrite an existing download.

To assess the existing download instead, pass `../hackathon-downloads/tai/extracted` to `--raw`. For a quick **partial** run add `--limit-files 5` and choose a new output directory. Never use a partial run as a complete handoff. Processing all rows requires considerable time and disk space for the SQLite index and compressed outputs. The output directory must be empty, and failures leave partial output for inspection; choose a fresh path for another attempt.

## Outputs and interpretation

The pipeline retains each input row in compressed CSV, with source file and CSV record number, parsed date/value and flags. The source fields and units are unchanged. Reports include file inventory, per-column blank and decoding-replacement counts, point metadata, duplicate point IDs, point coverage, same-point/date duplicate candidates, counts and limitations. `working.sqlite` is a private intermediate containing partner-derived values.

No observation is excluded, averaged, imputed or converted. A flag is not a diagnosis. `flag_unknown_origin` is a provisional literal-key check; the correct installation relationship is not yet confirmed. Same-date groups use literal date strings and a 64-bit hash for candidate exact duplicates, so collisions and alternative timestamp representations need investigation before acting on a duplicate report. Missing dates and missing rows are different concepts.

The sequence report counts calendar gaps between recorded observations, adjacent identical nonblank strings and changes in adjacent unit strings per point, ordered by literal date. It does not establish an expected sampling frequency, identify all flatline periods, or prove gaps are missing readings. Same-date ordering is unspecified; unit changes are candidates for review.

The present scripts are **not yet a complete final handoff**: they do not generate a confirmed analysis slice, a complete join-cardinality report, a data dictionary with confirmed definitions, or a quarantine table. A full-data run and expert review are necessary; retain all records until those are completed. The selected-slice and peer eligibility decisions remain for the team and TAI. No modelling, thresholds, labels or claims of physical cause are produced here.

For Sunil: use `cleaned/MeasurementValues` with `point_metadata.csv.gz` only after validating point ID uniqueness and joins. Preserve `source_file`, `source_row`, raw `Date`, `Value`, and `Unit`, parsed fields and quality flags. Check data availability at decision time and fit any preprocessing only on the appropriate training period.
