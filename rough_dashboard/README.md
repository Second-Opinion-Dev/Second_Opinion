# Second Opinion — local operator prototype

Run from the repository root after installing `requirements.txt`:

```bash
python3 -m streamlit run rough_dashboard/app.py --server.address 127.0.0.1
```

The default input is `data/tai/second_opinion_sample/`. Extract the team's supplied ZIP there, without committing the data. Choose another local results root in the sidebar to use a completed full run with the same directory layout. The source cache is invalidated when the manifest or scored files change. The original exploratory dashboard remains in `legacy_app.py`.

## What is connected

Temperature, nitrate and suspended solids are available as **fictional UI examples** under `NL.07.VOORBEELD — RWZI Voorbeeld` while their real outputs are unavailable. Their values, median, ordering and orange flags are invented for demonstration; no model has scored them. They never appear under a real plant. Select the example plant, a new metric and a date range ending 2025-12-31 to see its example flag. The app tries to load actual results for each new metric first; the handoff must confirm the actual metric names, preprocessing, units, file format and score semantics before replacing these placeholders. Incompatible or missing outputs fall back to the labelled example, not real model findings.

The sample ZIP contains real partner-derived measurements and **precomputed** outputs from three partial smoke runs: `influent_volume`, `oxygen`, and `ammonium`. Its README says the first 30 points per cohort were used. It is not a simulated operating event and its partial numbers must not be reported as project-wide findings. Results are historical, provisional and unvalidated; flags do not prove a fault. Partner data and derived outputs stay local, never commit or upload them, and follow the event's deletion rules.

The app reads `forest_<metric>/scored_records.csv.gz` and `run_info.json`, plus `history_<metric>/run_info.json`; it validates the measurement name, required fields, completion markers, source-row uniqueness, and that eligible forest flags agree with the run's recorded threshold. Dates, units and source provenance are retained. Missing, invalid and ineligible results are unassessed, never classified as normal. No fitted models are included in the sample. The interface performs **no new model inference** and does not load pickle/joblib files. For the actual training, scoring, feature definitions, split dates and output contract, see `isolation_forest/HANDOFF.md` and `history_detector/HANDOFF.md`.

The daily view groups the three supported metrics by process in a compact date-column table. Select “All metrics” to see the available volume, oxygen and ammonium readings together; their values and units remain separate. Missing groups are identified explicitly. Orange highlights a stored forest flag; muted values are unassessed. Repeated source rows remain separate. Select the period in the sidebar and the number of displayed days above the table. Choose one metric for the review queue, chart or assistant so forest scores from different metrics are not mixed.

The forests use six model features constructed from the same series' current and prior history; the stored score is `-score_samples`, with higher values more unusual, and the stored flag uses that metric's own 2024 validation-derived threshold. Forest scores are not fault probabilities or comparable between independently trained metrics. The initial cohort filters, measurement definitions and units require TAI confirmation. The current dataset does not supply applicable historical operational limits, so the interface does not claim any reading is within or outside them.

## Review and assistant

Each eligible forest-flagged **reading** is one case with an ID derived from metric plus source file and row. For one chosen plant, metric, point filter and date range, cases are sorted by descending forest score, then descending date, then source provenance. This is a reproducible review order, not a severity estimate; raw scores are never ranked across metrics. The budget divides the visible cases into selected and deferred. It is a per-selected-metric budget, not a single combined three-metric workload. Case grouping is not implemented. Review checkboxes are held only in the browser session and are not written back to Z-info.

The assistant uses deterministic text composed from the selected stored reading, score and historical median. It does not attribute the model result to a feature, infer causes, call an LLM, or send data off-machine. The bottom-corner assistant shows the selected plant's recorded model flags across all three metrics for the last seven days ending on the selected end date. If that window is empty, it clearly labels a preview from the selected period; the assistant page also supports 30 days or the entire selected period. Results are ordered by date, not by comparing scores across models. Clicking a notification opens the correct point and date in the daily table; the separate case button opens its evidence. The badge is the number of flags in the seven-day window, not a count of new live alerts. The active point filter applies to these notifications. No scheduled or live notifications are generated. The earlier history-detector case files and their different rule-based review order are not used as forest cases.

The separate dry-weather exploration can be started independently:

```bash
python3 -m streamlit run rough_dashboard/dry_weather.py --server.address 127.0.0.1 --server.port 8502
```

It reads the local raw TAI export and shows three-year median daily readings for one selected plant's volume, oxygen, ammonium and kWh measurement points. It keeps each selected process context and unit separate, excludes repeated-date records, and reports usable-day counts. kWh is an additional descriptive measurement, not an anomaly-detection target; a meter's identity, meaning and whether it measures total consumption must be confirmed with TAI. The national annual rainfall bars are published KNMI automatic-station averages for 2023–2025, linked on the page; they are not plant-local rainfall. This is a descriptive comparison, not a plant-specific weather analysis. It does not infer dry days, physical causes, heater or fan use, biological benefit, costs or savings. Peer comparison is outside the team's current scope.

Run the integration and existing detector checks from the repository root:

```bash
python3 -m unittest discover -s rough_dashboard -p 'test_*.py' -v
python3 -m unittest -v history_detector.test_history_detector isolation_forest.test_model
```

These use artificial fixtures and verify implementation behavior; they do not establish operational accuracy. Loading the three actual model bundles and running new inference cannot be tested until those bundles are supplied.

## Remaining work

- Obtain the three trusted fitted model bundles and the complete compatible outputs from the team, then separately implement and verify metric-specific inference using the bundles' exact feature order, thresholds and preprocessing. Never load untrusted joblib files.
- Confirm data meaning, plant context, aggregation, observation availability and actual applicable operational limits with TAI. Water-board metadata and existing validation outcomes are not established by this sample.
- Agree on grouped cases, combined review budgets, persistence and operator workflow; validate notification links and translations with operators.
- Evaluate on controlled perturbations and, if possible, a documented expert-reviewed sample. Existing chronological budget comparisons and artificial fixture tests do not establish real-world accuracy or reduced false alarms.
