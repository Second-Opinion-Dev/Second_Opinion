# Dashboard

A local Streamlit prototype that shows the operator side of Second Opinion: a daily measurement grid with flagged readings, a per-plant review queue, the history behind each case, and a simple notification assistant. It is available in Dutch and English.

## Run

After installing `requirements.txt`, start it from the repository root:

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

By default it reads `data/tai/pipeline/`, the output of a full `python src/pipeline.py` run. A different results root can be entered in the sidebar; relative paths resolve from the repository root. The source cache is invalidated when the manifest or the scored files change.

## What it reads

The app reads `forest_<metric>/scored_records.csv.gz` and `run_info.json`, plus `history_<metric>/run_info.json`. It validates the measurement name, required fields, completion markers and source-row uniqueness, and checks that eligible forest flags agree with the run's recorded threshold. Dates, units and source provenance are kept. Missing, invalid and ineligible results are shown as **not assessed**, never as normal.

The interface performs **no model inference** and never loads pickle or joblib files. It only displays stored results.

Volume, oxygen and ammonium are wired to real pipeline output. Temperature, nitrate and suspended solids are currently shown as **fictional UI examples** under a clearly labelled example plant (`NL.07.VOORBEELD — RWZI Voorbeeld`). Their values and flags are invented for demonstration, and they never appear under a real plant. When real outputs for those metrics are present and compatible, the app loads them first.

## Views

- **Daily grid:** measurements grouped by process in a compact date-column table. "All metrics" shows the available groups together, with their values and units kept separate. Orange marks a stored forest flag; muted values are not assessed. Repeated source rows remain separate.
- **Review queue:** each eligible forest-flagged reading is one case, sorted for one plant and metric by forest score, then date, then provenance. A budget splits the visible cases into selected and deferred. Raw scores are never ranked across metrics. Review checkboxes live only in the browser session.
- **Case evidence:** the reading, its history and the stored historical median, with a chart of the surrounding days.
- **Assistant:** deterministic text built from the selected reading, its score and the historical median. It does not call an LLM, infer causes or send data anywhere. The corner badge counts the selected plant's recorded flags in the seven days up to the chosen end date; it does not count live alerts.

## Rain and treatment exploration

A separate, descriptive page:

```bash
python -m streamlit run dashboard/dry_weather.py --server.address 127.0.0.1 --server.port 8502
```

It reads the local raw export and shows three-year median daily readings for one plant's volume, oxygen, ammonium and kWh measurement points, alongside published national annual rainfall averages from KNMI. That rainfall is not plant-local, and the page infers no dry days, causes, costs or savings.

`legacy_app.py` is the original exploratory dashboard, kept for reference.

## Tests

```bash
python -B -m unittest discover -s dashboard -p "test_*.py" -v
```

The tests use artificial fixtures and check the implementation's behaviour, not its operational accuracy.

## Possible next steps

- Run metric-specific inference from trusted fitted models, using each bundle's exact feature order, threshold and preprocessing.
- Grouped cases, a combined review budget across metrics, and persistent review feedback.
- Validate notification links, wording and translations with operators.
