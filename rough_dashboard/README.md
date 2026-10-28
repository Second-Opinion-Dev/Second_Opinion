# Second Opinion: rough dashboard

Local Streamlit prototype for operator review. This is independent of `tai_exploration` and does not train or run a detector. It reads the extracted TAI data locally and accepts a local case-results CSV once the analysis team produces one. No example cases or results are fabricated.

From the repository root, in the project's Python environment:

```bash
python3 -m streamlit run rough_dashboard/app.py --server.address 127.0.0.1
```

The explorer expects `data/tai/extracted/{Installations,MeasurementPoints,MeasurementValues}/`. Select an installation, process code and measurement point. Point metadata and source rows remain accessible; repeated dates are retained. The export is historical and daily, not live.

The daily measurement table follows the Z-info layout: choose an installation and end date, filter by process or point, and inspect up to 14 daily columns. Repeated records appear in separate numbered rows; blank cells do not establish whether a measurement was expected. It does not modify Z-info or assign validation status. The analysis assistant page explains the intended integration; no AI assistant or model is connected yet. Model results may be connected through the local results contract below.

Use **Language / Taal** and **Appearance / Weergave** in the sidebar to choose English or Dutch and light or dark mode. Interface text is translated; descriptions from the source data and explanations supplied by the analysis team are shown as provided. Selections apply to the current browser session.

## Results handover

The review queue defaults to `data/case_results.csv` and accepts another local path in the sidebar. The results producer must supply one row per case with these columns:

| Column | Meaning |
| --- | --- |
| `case_id` | Unique nonempty case identifier |
| `installation` | Installation identifier |
| `measurement_point_id` | Point identifier |
| `date` | Case date, preferably ISO `YYYY-MM-DD` |
| `reason` | Human-readable evidence for the flag |
| `rank` | Unique positive number; lower numbers are reviewed first |

Optional `value`, `unit`, `peer_context`, and `suggested_check` fields appear in the case details. When matching local records exist, the case view shows the preceding 90 days of source history. Confirm schema, coverage, grouping and ranking with the analysis team. The queue does not persist decisions, infer peer context, or estimate actual costs. Review time is an adjustable, explicitly labelled assumption. A missing or empty file is not evidence of normal operation.

Data and results must stay local and must never be committed. No changes are made to raw files.
