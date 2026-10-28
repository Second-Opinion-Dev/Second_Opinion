# Second Opinion: history-based validation of wastewater measurements

**Tagline:** Spot unusual measurements, understand the evidence, and decide what
to check first.

**Status:** A provisional history-only detector and an experimental Isolation
Forest layer have been implemented and run on local historical data. Focused
implementation tests and a descriptive held-out ranking comparison have been
run; neither method has been validated against real incident labels or operator
review. The proposed dashboard and review queue are not yet implemented. Peer
comparison is not used in the detector or the current project scope.

## The challenge

TAI / Z-info asks us to detect and flag unusual measurements at wastewater
plants, explain why the flags are useful, and consider what false alarms cost an
operator. The data has no confirmed anomaly labels.

In the mentor briefing, TAI described a validation workflow in which readings
outside predefined limits trigger warnings, while readings within those limits
may pass validation despite being unusual. The mentors reported approximately
30,000 new measurement points per day and around 321 plants in the platform;
these are briefing figures, not counts verified from the supplied dataset.
Validated data is used downstream for analysis, reporting and decisions. The
longer-term ambition described in the briefing is an AI-supported digital operator.

**Our problem statement:** How can we identify suspicious measurements that
existing limit-based checks may miss, explain why they deserve attention, and
help operators prioritise their validation within the time available?

A flag is a reason to investigate, not proof of a faulty reading, a plant
incident, its physical cause, or a safe condition. The operator makes decisions.
Actual applicable historical limits and outcomes are needed before claiming an
existing check missed a reading.

## The idea

Second Opinion compares a reading with the recent history of the **same
measurement point and process context**. It reports how the reading differs from
its typical recent value and why it was flagged or could not be scored.

A later operator interface could turn these observations into an investigation
queue. It could group consecutive flags, let an operator specify a review budget,
and show both selected and deferred cases. This interface is a proposal, not a
feature implemented by the current detector. Deferral is not evidence of safety.

### Illustrative example — not a dataset finding

Suppose a measurement at a plant is much higher than its recent median. The
detector can flag the reading and show its value, unit, historical median and
anomaly score. An operator can then check the measurement and operating records.
The detector does not compare other plants or conclude what caused the change.

## Implemented methodology

The implementation is `history_detector/history_detector.py`. It is a statistical,
history-based baseline; it does not train a neural network or supervised
classifier. Its threshold and performance are not validated.

### 1. Prepare and select inputs

The detector reads the completed full output of the TAI preparation pipeline:
`summary.json`, `point_metadata.csv.gz` and `cleaned/MeasurementValues/*.csv.gz`.
The preparation preserves raw fields, source file and row, parsed values and
quality flags. The detector requires unique, nonblank point IDs, matching source
files and matching point/value units; it refuses partial preparation output.

Each run selects one exploratory group, all labelled `scada`:

| Group | Product | Quantity | Parameter | Unit | State |
| --- | --- | --- | --- | --- | --- |
| `influent_volume` (default) | Influent | Volume | Niet van toepassing | m3 | Any |
| `oxygen` | Actief slib | (massa)Concentratie | zuurstof | mg/l | niet van toepassing |
| `ammonium` | Actief slib | (massa)Concentratie | ammonium | mg/l | uitgedrukt in Stikstof |

The additional groups cover only these exact metadata combinations, not every
oxygen or ammonium point. TAI has not confirmed what the readings represent,
their reporting period, units or operational comparability. Do not extrapolate
to all plants or measurement types. See `history_detector/HANDOFF.md`.

### 2. Keep each history separate

Records are grouped by origin installation, measurement point, origin subprocess,
process, product, product balance, destination installation, destination
subprocess and unit. Each group has its own history; readings from other points,
contexts or plants do not enter it. Records are sorted by date before scoring.

### 3. Calculate the historical baseline and score

For a reading on day `t`:

1. Select eligible observations from **`[t - 28 days, t)`**: the preceding 28
   calendar days, excluding the current day. Require at least **14 valid days**.
2. Calculate their **median**, the middle value in the recent history.
3. Calculate **MAD**, the median of the absolute deviations from that median.
   This gives a robust measure of the historical spread.
4. Calculate the absolute deviation score:

   ```text
   score = |current value - historical median| / (1.4826 × MAD)
   ```

5. Flag scores **greater than or equal to 3.5**. The window, minimum history and
   threshold can be configured. The 3.5 threshold is an uncalibrated starting
   value, not a probability, a measured risk level or an approved operating limit.

The window only uses prior records, preventing the current or future readings
from entering their own baseline. Valid prior flagged readings remain in later
windows; this allows adaptation but can mask a sustained change. Real-world
availability times for the date-only export still need confirmation from TAI.

### 4. Preserve uncertainty and provenance

A record is **unscored**, with a reason, when its date or value is invalid,
its preparation flags require review, there are multiple rows for that series
and calendar day, there is insufficient valid history, or the historical MAD is
zero. Same-day duplicates and other ineligible records are also excluded from
later history; the source records remain intact. The detector does not silently
average conflicting records, fill missing values or convert units. Zero and
negative values are not automatically treated as invalid.

Output includes the original date, value and unit; installation, point and
process context; source file and row; quality flags; historical count, median
and MAD; score; nullable flag; direction; status; and explanation. A blank flag
means **unscored**, not normal. The data and scores stay local and out of Git.

## Running the detector

With a local TAI download and the required Python packages, run from the project
root. Both output directories must be new or empty and must remain private:

```bash
python3 data/tai_work/scripts/tai_pipeline.py --raw data/tai/extracted --output data/tai/prepared_history
python3 history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_scores
python3 history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_oxygen --measurement oxygen
python3 history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_ammonium --measurement ammonium
```

Reuse a completed preparation directory instead of rerunning the first command.
For another scoring run choose a new output directory. Optional detector
settings are `--window-days`, `--minimum-history` and `--threshold`. The output
contains `history_scores.csv.gz` and a `run_info.json` completion marker with
configuration, package versions and counts. If the marker is absent, treat the
output as incomplete. Paths differ for teammates; see
`history_detector/HANDOFF.md` for setup, output fields and limitations.

## Experimental AI layer

`isolation_forest/model.py` ranks eligible records using signed deviation from
the historical median, one-day change relative to historical spread, and the
fraction of recent prior days flagged by the history detector. Each feature uses
only the same point's current or earlier observations. Raw identifiers are not
model features; peer comparisons are not used. Ineligible records remain
unscored with a reason. The existing statistical detector runs independently.

The first two features divide their deviation or change by `1.4826 ×` the
prior MAD, then apply a signed `log1p` transform to reduce extreme scales. The
change requires a valid scored reading on the previous calendar day. The prior
flag fraction uses at least three scored readings in the previous seven days;
the current day is excluded. Points with missing, ambiguous or unsuitable
history stay unscored rather than being filled with normal-looking values.

Train a separate forest for each measurement group; each pools normalised
features across that group's points, while their historical features remain
point-specific. There is no peer comparison. Do not compare raw scores from
separately fitted forests as if they were calibrated on one scale.

Each forest is trained through 2023 with a fixed seed. Its provisional threshold
is the 99th percentile of 2024 validation scores; 2025 is held out. A higher AI
score means a less common combination of features, not a fault probability.
Separately, a retrospective comparison ranks the same eligible readings for each
method with an example budget of 10 readings per day **per measurement group**.
It is not a shared operator budget across the three groups. The budget ranking
can include readings below the fixed alert threshold. Counts and overlap do not
establish which method is more useful; real labels or expert review are needed.
See `isolation_forest/HANDOFF.md` for commands, private outputs and limitations.

## Testing, baseline comparison and results — next teammate

Focused artificial-fixture tests cover important history and AI edge cases, and
the two methods have been compared descriptively at a shared review budget. No
peer comparison, expert review, real-world accuracy or false-alarm evaluation
has been performed. A successful local run does not establish that flags are
accurate or useful. The next teammate should:

1. Confirm the slice, units, duplicate handling, data availability and important
   operating measurements with TAI; ask about review time and incident labels.
2. Check the implementation's window boundaries, absence of future leakage,
   grouping, missing/duplicate values, zero MAD, provenance and edge cases.
3. Choose and freeze settings using an earlier period, then evaluate on a later
   held-out period. Compare with an agreed simple baseline at the same review
   budget; compare actual historical validation limits only if their
   applicability and values are supplied.
4. If the team authorises artificial changes in **copies** of held-out data,
   record the seed and compare recovery of spikes, drops and gradual changes,
   including unchanged periods. These are artificial-case results, not
   real-world accuracy or a measured false-alarm rate.
5. If possible, ask TAI experts to review a documented sample of flagged and
   unflagged cases and record useful / not useful / unsure. Measure review time
   or label assumptions clearly; do not claim savings from assumptions alone.

See `history_detector/HANDOFF.md` and the existing baseline and validation skills
for the detailed handoff. Do not claim precision, recall, false-alarm reduction,
operational savings or causes without adequate evidence. Peer comparison is not
part of this implementation or its proposed baseline evaluation.

## Scope and demo

**Implemented:** a provisional history-only detector, an experimental Isolation
Forest layer and private row-level output.

**Next priorities:** confirm the measurement semantics; test and calibrate the
baseline; build an understandable case view and review queue, showing deferred
cases if the operator sets a budget. These are not implemented yet.

A proposed demo would explain the operator's problem, open a historical flagged
case, show the reading and historical evidence, show the review queue if built,
and report only recorded test results and limitations. No peer comparison is
needed for this demo.

### Optional bonus: dry-weather insights

Only after the core validation workflow works, explore differences between dry
and wet periods if suitable weather information and compatible measurements are
available. Discuss operational relevance with experts. An association between
weather and a measurement does not establish a cause, treatment outcome or cost.

## Rules for agents

- Follow `AGENTS.md` and the staged playbooks. Read `data/tai_work/DATA_AUDIT.md`,
  `data/tai_work/DECISIONS.md`, `data/tai_work/HANDOFF.md`, `history_detector/DECISIONS.md` and
  `history_detector/HANDOFF.md`.
- Inspect data and confirm meanings; never invent labels, operating limits,
  performance, confidence or physical causes.
- Preserve raw inputs and provenance. Keep reusable logic outside the app and
  notebooks; record configuration, splits, package versions and run commands.
- Do not commit or publish partner data, derived sensitive details or the access
  key. Delete partner data after the event unless the partner agrees otherwise
  in writing.
- The supplied export is historical and day-granular. Do not describe the
  detector as live, infer intraday detection, or assume readings were available
  at the start of their stated day.

**Expected outcome:** a practical decision-support prototype that helps an
operator prioritise unusual measurements, with transparent evidence, recorded
validation and honest limitations.
