# History detector: implementation and testing handoff

## Status and scope

This is a provisional history-only baseline for the TAI / Z-info challenge. It
has no peer comparison, real-time integration, diagnosis, operator dashboard,
evaluation results or calibrated threshold. The user requested implementation
without performing the testing and baseline-comparison work; that work is for the
next teammate. No anomaly performance, false-alarm rate or savings have been
established. A flag is an investigation candidate, not a confirmed problem.

The partner briefing restricts data and keys to hackathon use. Keep all raw data,
prepared files, row-level scores, reports and credentials local and out of Git.
Delete partner data after the event unless the partner agrees otherwise in writing.

## Inputs and selection

`history_detector/history_detector.py` consumes a completed full output from
`data/tai_work/scripts/tai_pipeline.py`: `summary.json`, `point_metadata.csv.gz` and
`cleaned/MeasurementValues/*.csv.gz`. It rejects partial pipeline output, blank
or repeated metadata point IDs, unmatched source-file provenance and unit
mismatches. It checks the metadata selection, but metadata meanings and the
literal installation join remain unconfirmed by TAI.

The exploratory filter is case-insensitive for description and input type:
`ProductDescription = Influent`, `QuantityDescription = Volume`,
`ParameterDescription = Niet van toepassing`, `Unit = m3`, `InputType = scada`.
This is not an expert-approved incoming-flow dataset. Do not generalise its
results to other measurements, units or input types; confirm with TAI that this
selection measures what the team thinks it does.

## Algorithm and decisions

- Each series uses `InstallationCodeOrigin`, `MeasurementPointID`,
  `SubProcessCodeOrigin`, `ProcessCode`, `Product`, `ProductBalance`,
  `InstallationCodeDestination`, `SubProcessDestination` and `Unit` as keys.
  Metadata identifies the point and exploratory selection. No other plant's
  data is used.
- Sort by date and use only valid, unambiguous observations in the calendar
  interval `[day - 28 days, day)`. Default minimum history is 14 distinct days.
  Both defaults are configurable. The current reading is never in its baseline.
- Calculate the median of the window, its median absolute deviation (MAD), and
  `abs(value - median) / (1.4826 * MAD)`. A score of at least **3.5** is flagged
  by default. This threshold is provisional, not calibrated or validated.
- Append each valid, unambiguous observation to future windows, even when it was
  flagged. This permits adaptation but can also mask sustained changes. Do not
  interpret the score as probability, risk severity or a diagnosis.
- All repeated rows for the same series and calendar date are left unscored and
  excluded from later history, even if values match. Original records remain
  intact. Rows with missing/non-finite values, invalid dates, or any non-false
  preparation flag are also unscored and excluded from history. Installation
  flags are provisional literal-key checks, not confirmed errors.
- If fewer than the minimum valid days exist, or MAD is zero, return an unscored
  status. There is no imputation, arbitrary epsilon, flatline diagnosis, or
  automatic unit conversion. Zero and negative values are not automatically
  invalidated. Each row carries a status and explanation.
- Daily dates do not prove when values were available to an operator. This is
  retrospective scoring, not a demonstrated live or intraday alert system.

## Run commands

From the repository root, with Python 3.11+ and pandas/NumPy installed, prepare
data in a **new, empty, private, Git-ignored** location. On this machine the
download is under `data/tai/extracted`:

```bash
python3 data/tai_work/scripts/tai_pipeline.py --raw data/tai/extracted --output data/tai/prepared_history
python3 history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_scores
```

If prepared data already exists, reuse it and skip the first command. Do not
overwrite existing outputs: use a new empty output path for each run. The full
preparation pass needs substantial time and disk for `working.sqlite` and
compressed files. Other teammates should substitute their local private paths.

Optional flags: `--window-days 28 --minimum-history 14 --threshold 3.5`. `run_info.json`
records settings, package versions, the source preparation summary and counts.
`history_scores.csv.gz` includes original dates, values, units, source file/row,
process and selected-point descriptions, preparation flags, history days, median,
MAD, score, nullable flag, direction, status and explanation. If `run_info.json` is absent, the run did not finish;
do not treat partial output as complete. The program does not modify prepared or
raw input data. Results are local and contain sensitive identifiers.
`history_days` is blank for observations rejected before a history window is
constructed; a numeric zero means an eligible observation had no usable history.

## Local execution log — 28 October 2026

The two commands above completed on the local downloaded archive and wrote
`data/tai/prepared_history/summary.json` and
`data/tai/history_scores/run_info.json`. The scoring run used the default settings
and Python 3.14.6, pandas 3.0.6 and NumPy 2.5.3. Completion means the commands
ran, not that the detector's logic, results or threshold are validated. No tests,
peer comparison, benchmark or model evaluation were performed for this task.
Both output directories are local and Git-ignored; other teammates must generate
their own private data outputs or receive them through an authorised channel.

## Next teammate: testing, baseline comparison and results

An experimental Isolation Forest layer and focused artificial-fixture checks
have since been added. See `isolation_forest/HANDOFF.md` for its chronological
comparison and outstanding evaluation; the historical execution log above
describes the original baseline implementation, before those checks.

1. Read `idea.md`, `data/tai_work/DATA_AUDIT.md`, `data/tai_work/HANDOFF.md`, and this document.
   Confirm input meaning, time availability, duplicate rules and relevant
   operational points with TAI. Determine whether real validation limits or
   labelled incidents exist; do not assume they do.
2. Test the detector with small, explicitly artificial fixtures: calendar-window
   boundaries and no future leakage; grouping across installations, contexts and
   files; valid and missing flags; same-day duplicates; non-finite values; gaps;
   insufficient history; zero MAD; unit mismatch; and empty/partial inputs.
   Check the intended treatment of flagged points in subsequent history.
3. Establish chronological training, validation and held-out periods with the
   team. Select and freeze thresholds/configuration before held-out evaluation;
   record exact commands, package versions, inputs and random seeds. Compare
   equivalent points, event definitions and review budgets.
4. Compare the proposed baseline against any agreed simpler rule and, if TAI
   supplies applicable historical validation limits, those limits. Distinguish
   observed flag volumes from confirmed false alarms. Report rows eligible,
   unscored by reason, flags and grouped candidates, and review workload under
   clearly stated operator-provided or assumed review times.
5. If the team authorises controlled artificial perturbations of **copies** of
   held-out data, include spikes, drops and gradual changes, plus unchanged
   periods. Record recovery and missed injections at the same review budget;
   these are synthetic-case results, not real-world accuracy.
6. Ask an expert to review a documented sample of flagged, deferred and unflagged
   cases, with `useful / not useful / unsure` outcomes. Report sample size and
   limitations. Do not claim precision, recall, false-alarm reductions, savings,
   root causes or operating-limit misses without adequate real evidence.
7. Record what was run, observed results and limitations in a private report and
   log decisions appropriately. Avoid putting partner data, identifiers, keys or
   sensitive derived details in Git. Document unrun tests and open issues.

The existing `.agents/skills/04-baseline/SKILL.md` and
`.agents/skills/09-validate/SKILL.md` already cover baseline and validation work;
this handoff adds the specific detector contract and does not replace them.
