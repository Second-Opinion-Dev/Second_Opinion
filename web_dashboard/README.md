# Second Opinion: web dashboard

A local browser-based workspace for exploring wastewater readings and reviewing precomputed anomaly flags. The interface supports English and Dutch, light and dark themes, a searchable plant selector, a review queue, 28-day history and an optional Claude explanation. It uses a Python server and JavaScript frontend, not Streamlit.

## What you need

- Python 3.10 or newer. The web server uses Python's standard library; Node.js is needed only for JavaScript tests.
- An authorised local folder containing the team's precomputed pipeline results. Partner data and results are not included in Git. The app does not train or run models itself.
- Optionally, the authorised extracted TAI data folder for a fuller installation catalogue.
- Optionally, an Anthropic API key for Claude. The dashboard works without it.

## Start the dashboard on Windows

1. Open PowerShell in the repository folder and select the web dashboard branch:

   ```powershell
   git switch smriti-web-dashboard
   git pull --ff-only
   ```

   Preserve any uncommitted work before switching branches.

2. Start the server:

   ```powershell
   python3 web_dashboard/server.py
   ```

   If `python3` is unavailable, try `py -3 web_dashboard/server.py`.

3. Open http://127.0.0.1:8518. The server listens only on this computer.
4. In **Results folder**, enter the path to local pipeline results, for example `data/tai/pipeline`. Optionally enter `data/tai/extracted` in **Plant catalogue folder** if that folder contains `Installations`. Click **Connect results**.
5. Wait for indexing to finish. Search or select a plant, select a measurement and date range, then open a flagged reading to see its evidence and history.

Stop the server with **Ctrl+C** in PowerShell. Leave the terminal open while using the app.

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

The same pattern applies to other available metrics: `influent_volume`, `oxygen`, `nitrate`, `suspended_solids` and `temperature`. A metric without valid matching result files is unavailable. The catalogue can list plants that do not have scored readings.

The first connection builds a local SQLite index at `data/tai/second_opinion_web_index.sqlite`; large result sets can take time. Later connections reuse unchanged results. The index contains derived partner data: keep it private and out of Git. If it is read-only, the app can reuse matching completed entries, but new or changed results need a writable index.

## Optional: enable Claude

Set your key in the same PowerShell window before starting the server. The prompt hides the input:

```powershell
$secureKey = Read-Host -Prompt 'Claude API key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
python3 web_dashboard/server.py
```

Optionally set `$env:ANTHROPIC_MODEL` before starting; the default is `claude-sonnet-4-6`. Never paste a key into source code or commit it. If a key was exposed, revoke it and use a new one.

Open a flagged case, enter your question, confirm you are authorised to share the case, and click **Ask Claude**. The selected evidence and question are sent to Anthropic; the full dataset is not sent and the API key stays on the backend. No request is made automatically. Claude can make mistakes, so check its answer against the displayed evidence.

## Troubleshooting

- **Port 8518 is already in use:** stop the other dashboard server, or run on a different port in the same PowerShell session:
  ```powershell
  $env:SECOND_OPINION_PORT = '8519'
  python3 web_dashboard/server.py
  ```
  Open http://127.0.0.1:8519 instead.
- **No data or missing plants:** check the results folder path and expected files above. Add the optional extracted catalogue to see installations that have no scored results.
- **Read-only database:** check write permissions for `data/tai` or use an existing matching index. A stale or incomplete index cannot be rebuilt without write access.
- **Claude says the key is missing:** set the environment variable and restart the server in that same terminal. Refresh the page and submit a new question.
- **The page looks outdated:** restart the server and refresh the browser, using Ctrl+F5 if needed.

## Checks and limitations

From the repository root, run:

```powershell
python3 -m unittest discover -s web_dashboard -p 'test_*.py' -v
node --test web_dashboard/test_assistant_ui.cjs
node --check web_dashboard/app.js
```

Tests use fictional fixtures. The dashboard shows historical, provisional results, not live alerts or confirmed faults. A flag prompts investigation; the model inputs do not establish a cause or an operational limit. Review budget selections are not persisted, and scores from different models should not be compared. Retain and share TAI data only with the necessary permission.
