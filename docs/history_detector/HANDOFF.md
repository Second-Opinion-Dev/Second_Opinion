# History detector: implementation and testing handoff

## Status and scope

This is a provisional history-only baseline for the TAI / Z-info challenge. It
has no peer comparison, real-time integration, diagnosis or operator dashboard.
Its thresholds are calibrated to an assumed workload, not to verified outcomes.
Artificial-fault comparisons exist (see `synthetic_faults.py`), but no real-world
anomaly performance, false-alarm rate or savings have been established. A flag
is an investigation candidate, not a confirmed problem.

Team decisions (28 October 2026): plants are not compared with each other,
because plants differ geographically and in timing; and each plant has its own
operator, so review budgets and rankings are per plant.

The partner briefing restricts data and keys to hackathon use. Keep all raw data,
prepared files, row-level scores, reports and credentials local and out of Git.
Delete partner data after the event unless the partner agrees otherwise in writing.

## Inputs and selection

`src/history_detector/history_detector.py` consumes a completed full output from
`src/data_prep/tai_pipeline.py`: `summary.json`, `point_metadata.csv.gz` and
`cleaned/MeasurementValues/*.csv.gz`. It rejects partial pipeline output, blank
or repeated metadata point IDs, unmatched source-file provenance and unit
mismatches. It checks the metadata selection, but metadata meanings and the
literal installation join remain unconfirmed by TAI.

The `--measurement` option selects one exploratory metadata group per run.
Descriptions and input types are compared case-insensitively; units are matched
exactly and never converted. The default `influent_volume` preserves the original
selection:

| Group | Product | Quantity | Parameter | Unit | Input | State |
| --- | --- | --- | --- | --- | --- | --- |
| `influent_volume` | Influent | Volume | Niet van toepassing | m3 | scada | Any, as in the original selection |
| `oxygen` | Actief slib | (massa)Concentratie | zuurstof | mg/l | scada | niet van toepassing |
| `ammonium` | Actief slib | (massa)Concentratie | ammonium | mg/l | scada | uitgedrukt in Stikstof |
| `nitrate` | Actief slib | (massa)Concentratie | nitraat | mg/l | scada | uitgedrukt in Stikstof |
| `suspended_solids` | Actief slib | (massa)Concentratie | Onopgeloste bestandsdelen | g/l | scada | niet van toepassing |
| `temperature` | Actief slib | Temperatuur | Niet van toepassing | oC | scada | niet van toepassing |

The groups other than influent volume are deliberately narrower than all points of that kind,
which also have other products, units, input types and expression bases. None is
an expert-approved measurement definition. Confirm with TAI what each measures,
its operational importance and reporting period before making claims.

## Algorithm and decisions

- Each series uses `InstallationCodeOrigin`, `MeasurementPointID`,
  `SubProcessCodeOrigin`, `ProcessCode`, `Product`, `ProductBalance`,
  `InstallationCodeDestination`, `SubProcessDestination` and `Unit` as keys.
  Metadata identifies the point and exploratory selection. No other plant's
  data is used.
- Sort by date and use only valid, unambiguous observations in the calendar
  interval `[day - 28 days, day)`. Default minimum history is 14 distinct days.
  Both defaults are configurable. The current reading is never in its baseline.
- Calculate the median of the window, its median absolute deviation (MAD) and a
  spread `max(1.4826 * MAD, 0.05 * |median|)`. The floor stops tiny absolute
  changes on small or quiet meters from producing extreme scores. The score is
  `abs(value - median) / spread`, with a direction (`above` / `below`).
- **Thresholds are calibrated per meter, not fixed.** By default, each series
  gets its own above and below thresholds, chosen on its own scored readings up
  to 2023-12-31 so that about 1% of them are flagged, half in each direction.
  Heavy upward tails (for example wet-weather influent) therefore get a higher
  threshold than drops, and erratic meters cannot set the bar for calm ones.
  Thresholds are never below 2.0. Series with fewer than 100 scored calibration
  readings use the median of the other series' thresholds. The 1% is a workload
  assumption, not a prevalence. `thresholds.csv` lists every series' values;
  `--threshold X` uses one fixed value for all series instead.
- **Clipped history.** Each valid observation enters later windows clipped to
  `median ± 3.5 × spread`. The reported value is never changed. A sustained fault
  therefore takes longer to become the new normal; a genuine permanent change is
  also accepted more slowly. `--clip-limit 0` restores unclipped history.
- **Data-quality rules**, independent of the threshold, mark each eligible row:
  `rule_stuck` (the same value on at least 7 consecutive days after a window that
  varied), `rule_dropout` (a zero after a full window without zeros) and
  `rule_negative` (a negative value; used for every group except temperature, which can be below zero; the others are non-negative
  quantities). A meter that is constantly zero is not "stuck". Rules apply even
  when the score is unavailable. `--no-rules` disables them.
- `review_flag` combines the statistical flag and the rules; `flag_reason` lists
  `stuck`, `dropout`, `negative`, `unusual_high` and `unusual_low`.
- **Cases.** Review-flagged days of one series form one case when separated by
  at most one unflagged or missing day (`--case-gap-days`). `cases.csv.gz` has
  one row per case with start, end, flagged days, peak score and reasons. Cases
  are ranked within each plant: rule hits first, then more flagged days, then
  higher peak score (`plant_rank`). This is a documented review order, not a
  probability or severity; rank a date-filtered subset with `rank_cases`.
- Rows with two or more otherwise-valid observations for the same series and
  calendar date are left unscored and excluded from later history, even if values
  match. A blank or quality-flagged row on the same date does not make a valid
  row ambiguous. Original records remain intact. Rows with missing/non-finite
  values, invalid dates, or any non-false preparation flag are unscored and
  excluded from history. Installation flags are provisional literal-key checks.
- If fewer than the minimum valid days exist, return `unscored_insufficient_history`;
  if the spread is zero (constant zero history), return `unscored_zero_spread`.
  There is no imputation or automatic unit conversion. Zero and negative values
  are not invalidated; the rules only mark them for review. Each row carries a
  status and explanation. Do not interpret any score as a probability, risk
  severity or diagnosis.
- Daily dates do not prove when values were available to an operator. This is
  retrospective scoring, not a demonstrated live or intraday alert system.

## Run commands

From the repository root, with Python 3.11+ and pandas/NumPy installed, prepare
data in a **new, empty, private, Git-ignored** location. On this machine the
download is under `data/tai/extracted`:

```bash
python3 src/data_prep/tai_pipeline.py --raw data/tai/extracted --output data/tai/prepared_history
python3 src/history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_scores
python3 src/history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_oxygen --measurement oxygen
python3 src/history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_ammonium --measurement ammonium
```

If prepared data already exists, reuse it and skip the first command. Do not
overwrite existing outputs: use a new empty output path for each run. The full
preparation pass needs substantial time and disk for `working.sqlite` and
compressed files. Other teammates should substitute their local private paths.

Optional flags: `--measurement influent_volume|oxygen|ammonium|nitrate|suspended_solids|temperature`, `--window-days 28`,
`--minimum-history 14`, `--scale-floor-fraction 0.05`, `--clip-limit 3.5`,
`--stuck-days 7`, `--no-rules`, `--calibration-end 2023-12-31`,
`--target-flag-rate 0.01`, `--threshold X` (fixed, skips calibration),
`--case-gap-days 1` and `--max-points N` (smoke run on the first N selected
points only; `run_info.json` is then marked `smoke_run_partial`). `run_info.json` records the exact selection, settings,
chosen thresholds, package versions, the source preparation summary and counts.
`history_scores.csv.gz` includes original dates, values, units, source file/row,
process and selected-point descriptions, preparation flags, history days, median,
MAD, spread, score, direction, repeat days, rule columns, nullable statistical
and review flags, flag reason, status, explanation and case id. `cases.csv.gz`
holds one row per case. If `run_info.json` is absent, the run did not finish;
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

## Artificial-fault comparison

`src/history_detector/synthetic_faults.py` copies a seeded sample of series, writes
one artificial fault into each copy during the held-out year (2025), and scores
the same copy with three variants: `legacy` (original settings: no floor, no
clipping, no rules, fixed 3.5), `revised` (current defaults) and
`revised_no_clip`. Calibrated thresholds are frozen on unmodified data up to
2023. Faults: a one-day spike of 6 robust spreads, a three-day dropout to zero,
a ten-day stuck value and a 28-day drift reaching 4 robust spreads. The spread
is measured in the 60 days before 2025. It also reports the review workload on
unmodified 2025 data. These are synthetic results, not real-world accuracy.

```bash
python3 src/history_detector/synthetic_faults.py --prepared data/tai/prepared_history --output data/tai/faults_influent --measurement influent_volume --sample 100
python3 -B -m unittest discover -s tests -t . -v
```

## Smoke run after the logic fixes — 28 October 2026

Only a **smoke run** was performed: the first 30 selected points of each group
(`--max-points 30`), not the full data. All three detector groups, all three
forests and the influent fault comparison (27 series) completed in about three
minutes; 28 unit tests passed. Python 3.11, pandas 3.1.0, NumPy 2.4.6,
scikit-learn 1.9.1. Partial, provisional numbers:

| Group (30 points) | Readings marked for review | Cases | Stuck | Dropout |
| --- | --- | --- | --- | --- |
| Influent volume | 1.26% | 310 | 188 | 12 |
| Oxygen | 1.23% | 309 | 138 | 12 |
| Ammonium | 1.74% | 335 | 230 | 24 |

Influent fault comparison on unmodified 2025 data: legacy marked 11.35% of
readings (17.5 cases per meter-year); revised marked 1.58% (3.4 cases per
meter-year). On artificial faults in copies of 2025 data, detected / injected:

| Fault | Legacy | Revised |
| --- | --- | --- |
| Stuck 10 days | 5/27 | 24/27 |
| Dropout 3 days | 22/25 | 25/25 |
| Spike of 6 spreads | 23/24 | 9/24 |
| Drift to 4 spreads | 22/24 | 4/24 |

The revised settings catch stuck and dropout faults far better at about a
seventh of the workload, but miss most moderate influent spikes and drifts.
Many influent meters routinely jump by tens of spreads (median per-meter upward
threshold about 34), so such faults look like ordinary variation without extra
context such as rainfall. Legacy detected them largely because it flagged 11% of
all readings. Clipping made no measurable difference in this sample. The target
rate trades workload against sensitivity and should be chosen with operators.
Run the full comparison before reporting final figures.

## Next teammate: testing, baseline comparison and results

An experimental Isolation Forest layer and focused artificial-fixture checks
have since been added. See `docs/isolation_forest/HANDOFF.md` for its chronological
comparison and outstanding evaluation; the historical execution log above
describes the original baseline implementation, before those checks. Items 2,
3 and 5 below are now partly covered by `test_history_detector.py`, calibrated
thresholds and `synthetic_faults.py`; expert review (item 6) is still open.

1. Read `idea.md`, `docs/data_prep/DATA_AUDIT.md`, `docs/data_prep/HANDOFF.md`, and this document.
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
