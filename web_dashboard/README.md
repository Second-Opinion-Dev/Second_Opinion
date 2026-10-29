# Second Opinion web dashboard

This is a local browser application with a JavaScript frontend and Python HTTP/SQLite backend. It does not use Streamlit or load fitted models. Run from the repository root:

```powershell
python3 web_dashboard/server.py
```

Open http://127.0.0.1:8518. Enter the path to an authorised results folder (for example `data/tai/pipeline`) and optionally an authorised extracted TAI folder to include the installation catalogue. Plants with no scored readings remain visible but have no model results. The server listens only on `127.0.0.1`.

The first connection streams completed compressed result files into `data/tai/second_opinion_web_index.sqlite`; this may take time and the index contains sensitive derived data. Bulk indexing creates the two search indexes after importing the rows, instead of updating both on each insert. The progress display uses the run manifests' split counts when they are available, and reports a separate search-index stage. Subsequent connections reuse unchanged metric indices. Source path, file timestamps and size determine whether a metric must be rebuilt. Source input files are preserved. Rows with missing plant, point, valid date or source provenance cannot be placed in the index; the original rows remain in the source files. The app does not fill missing results, aggregate duplicates, or invent examples. The table is paginated in blocks of 500. Flags and thresholds use the existing precomputed forest semantics, and the history chart shows the matching context in the previous 28 calendar days plus the flagged reading.

The pipeline contains unvalidated historical model outputs, not live alerts or confirmed faults. It ranks by score within one plant and metric; the review budget is a selection aid and review state is not stored. Scores from different models are not comparable. Model inputs are not feature attributions, operational limits, diagnoses or causes. Counts and flag rates are not accuracy estimates. Data retention and usage are subject to the TAI briefing; use partner data only with the required permission, and do not commit or upload the derived index.

Claude is optional. Set `ANTHROPIC_API_KEY` before launching the server; `ANTHROPIC_MODEL` overrides the default `claude-sonnet-4-6`. The browser never receives the key. To use it, select a flagged case, confirm you have permission and click Ask Claude. The selected case evidence and your question are sent to Anthropic. No request is made automatically. AI output may be incorrect; the deterministic evidence remains visible. TAI data sharing requires appropriate authorisation.

Checks:

```powershell
python3 -m unittest discover -s web_dashboard -p 'test_*.py' -v
node --check web_dashboard/app.js
```

The test fixtures are temporary and fictional. The original Streamlit application remains in `dashboard/` and is unaffected.
