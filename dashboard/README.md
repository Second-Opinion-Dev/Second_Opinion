# Dashboard

A local browser-based workspace for exploring wastewater readings and reviewing precomputed anomaly flags. The interface supports English and Dutch, light and dark themes, a searchable plant selector, a review queue, 28-day history and an optional Claude explanation. It is a small Python server with a plain JavaScript frontend.

## What you need

- Python 3.10 or newer. The server uses only Python's standard library; Node.js is needed only for the JavaScript tests.
- Precomputed pipeline results, by default `data/tai/pipeline/` from a full `python src/pipeline.py` run. Partner data and results are not included in Git. The dashboard does not train or run models itself.
- Optionally, the extracted Z-info export in `data/tai/extracted/` for a fuller installation catalogue. A [simulated export](../docs/simulation/README.md) works too.
- Optionally, an Anthropic API key for Claude. The dashboard works without it.

## Start the dashboard

1. From the repository root, start the server:

   ```bash
   python dashboard/server.py
   ```

   On Windows, use `py -3 dashboard/server.py` if `python` is unavailable.

2. Open http://127.0.0.1:8518. The server listens only on this computer.
3. **Results folder** and **Plant catalogue folder** are prefilled with `data/tai/pipeline` and `data/tai/extracted`. Change them if your outputs live elsewhere (for example `data/tai/pipeline_smoke30` after a smoke run), or clear the catalogue field if you have no extracted export. Relative paths resolve from the repository root. Click **Connect results**.
4. Wait for indexing to finish. Search or select a plant, select a measurement and date range, then open a flagged reading to see its evidence and history.

Stop the server with **Ctrl+C**. Leave the terminal open while using the app.

## Expected results layout

Select the parent folder of the metric folders, not a single metric folder. Each available metric needs matching completed files, for example:

```text
data/tai/pipeline/
  forest_ammonium/
    run_info.json
    scored_records.csv.gz
  history_ammonium/
    run_info.json
```

The same pattern applies to the other metrics: `influent_volume`, `oxygen`, `nitrate`, `suspended_solids` and `temperature`. A metric without valid matching result files is unavailable. The catalogue can list plants that do not have scored readings.

The server validates the measurement name, required fields, completion markers and provenance, and checks that eligible forest flags agree with the run's recorded threshold; a metric that fails is not shown. Missing, invalid and ineligible results are shown as **not assessed**, never as normal. The interface performs no model inference and never loads pickle or joblib files.

The first connection builds a local SQLite index at `data/tai/second_opinion_web_index.sqlite`; large result sets can take time. Later connections reuse unchanged results. The index contains derived partner data: keep it private and out of Git. If it is read-only, the app can reuse matching completed entries, but new or changed results need a writable index.

## Views

- **Overview and daily readings:** readings for one plant, measurement and period, with counts of flagged and not-assessed readings.
- **Review queue:** each eligible forest-flagged reading, sorted by forest score, then date. A budget splits the visible cases into selected and deferred. Raw scores are never ranked across metrics, and budget selections are not persisted.
- **Case evidence:** the reading, its stored historical median and model score, the previous 28 days of the same series and the model inputs.
- **AI assistant:** an optional, explicitly triggered Claude explanation of the selected case.

## Optional: enable Claude

Set your key in the same terminal before starting the server. In PowerShell, this prompt hides the input:

```powershell
$secureKey = Read-Host -Prompt 'Claude API key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
python dashboard/server.py
```

Optionally set `ANTHROPIC_MODEL` before starting; the default is `claude-sonnet-5-5`. Never paste a key into source code or commit it. If a key was exposed, revoke it and use a new one.

Open a flagged case, enter your question, confirm you are authorised to share the case, and click **Ask Claude**. The selected evidence and question are sent to Anthropic; the full dataset and source provenance are not sent, and the API key stays on the backend. No request is made automatically. Claude can make mistakes, so check its answer against the displayed evidence.

## Troubleshooting

- **Port 8518 is already in use:** stop the other dashboard server, or choose another port with the `SECOND_OPINION_PORT` environment variable (PowerShell: `$env:SECOND_OPINION_PORT = '8519'`) and open that port instead.
- **Folder not found:** run the pipeline first, or point **Results folder** at where its outputs are. Clear **Plant catalogue folder** if you have no extracted export.
- **No data or missing plants:** check the results folder path and expected files above. Add the extracted catalogue to see installations that have no scored results.
- **Read-only database:** check write permissions for `data/tai` or use an existing matching index. A stale or incomplete index cannot be rebuilt without write access.
- **Claude says the key is missing:** set the environment variable and restart the server in that same terminal. Refresh the page and submit a new question.
- **The page looks outdated:** restart the server and refresh the browser, using Ctrl+F5 if needed.

## Tests

From the repository root:

```bash
python -B -m unittest discover -s dashboard -p "test_*.py" -v
node --test dashboard/test_assistant_ui.cjs
node --check dashboard/app.js
```

Tests use fictional fixtures and check the implementation's behaviour, not its operational accuracy.

## Limitations

The dashboard shows historical, provisional results, not live alerts or confirmed faults. A flag prompts investigation; the model inputs do not establish a cause or an operational limit. Scores from different models should not be compared. Retain and share TAI data only with the necessary permission.

Possible next steps: grouped cases, a combined review budget across metrics, persistent review feedback, and validating wording and translations with operators.
