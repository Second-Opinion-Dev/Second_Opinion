# Isolation Forest: method and handoff

## Scope and status

This is a retrospective, experimental AI layer over the existing history-only
detector. It does not compare peer plants, diagnose a cause, replace the operator,
or establish real-world accuracy. The exploratory TAI slice, daily reporting
semantics and observation availability still need partner confirmation. Existing
partner data rules apply to raw data, derived scores, fitted models and reports.
Keep all of them local and never commit or upload them. Do not load joblib files
from untrusted sources.

## Input and features

Use a complete `history_detector/history_detector.py` output directory with
`run_info.json` and `history_scores.csv.gz`. Select one unconfirmed metadata group
per run: `influent_volume`, `oxygen`, or `ammonium`; see
`history_detector/HANDOFF.md` for exact product, quantity, unit, state and input
filters. The program checks that all rows match the recorded selection. Run a
separate forest for each group; do not mix groups or compare raw scores across
their independently fitted models.
The program verifies the completion status and row count and records SHA-256
hashes of the input files in the local output. It retains all source rows,
including history-detector status, quality flags and provenance.

For each separately grouped installation, measurement point and process context,
only previously scored, unambiguous records are used to calculate these features:

1. **Signed deviation:** `(value - prior median) / (1.4826 * prior MAD)`.
2. **One-day change:** `(value - previous day's value) / (1.4826 * prior MAD)`.
   The previous calendar day must have a valid history-detector score; gaps or
   invalid previous rows are not imputed.
3. **Prior flag fraction:** the fraction of history-detector flags among scored
   observations in `[day - 7 days, day)`, requiring at least three. The history
   detector's provisional threshold controls those prior flags.

The first two features use `sign(x) * log1p(abs(x))` to compress extreme
values while retaining direction. The transform is fixed and has no fitted
parameters. Neither identifiers nor absolute plant quantities are used as model
features. Series identifiers are used only to keep histories separate; there is
no cross-plant information. There is no fitted scaler or imputer.

AI eligibility requires a valid history score, finite feature inputs, positive
MAD, one unambiguous record for the day, a valid previous day and at least three
earlier scored flags in the 7-day window. Ineligible rows remain in the output
with `ai_status` and a blank `ai_score` / `ai_flag`. The original `score_status`
and `anomaly_flag` remain available. A history-unscored record is never relabelled
normal by the AI layer. Current-day and future data do not enter prior features.

## Training and thresholds

Default train ends 2023-12-31, validation ends 2024-12-31 and held-out test ends
2025-12-31. Eligible observations after that are labelled `outside_split`; any
scores for train, validation and outside periods are retrospective descriptions,
not held-out results. Earlier readings can inform a later rolling window if they
were available at the time; actual availability needs TAI confirmation.

`IsolationForest` fits only on training features, with seed 42, 100 trees and
`max_samples=256`. Higher `ai_score = -score_samples` means more unusual; it is
not a probability. The fixed alert threshold is the 99th percentile of validation
scores by default and is applied unchanged to the held-out period. The 1% value
is a workload assumption for calibration, not an observed prevalence or target
false-alarm rate. Ties may change the exact validation flag fraction. The
history detector's fixed 3.5 threshold and the AI threshold are not directly
comparable because they were chosen differently.

For a separate fair *ranking* comparison, independently select the top 10
eligible rows per date for each method, with deterministic source-file/row
tie-breaking. This budget is an example and configurable. Both use exactly the
same eligible rows. Selection ranks all eligible rows, including those below a
method's fixed threshold; it is a retrospective day-level comparison and does
not assume simultaneous or real-time availability. Ties can be arbitrary. This
counts readings, not grouped incidents; deferred or unscored does not mean safe.
The budget applies to each separate measurement run. It is not a shared
cross-measurement operator budget; displaying all three queues can present up
to three times that many readings per day. Model scores across separate forests
are not calibrated to a common scale.

## Run and outputs

From the repo root, after running the history detector:

```bash
python3 -B isolation_forest/model.py \
  --history-dir data/tai/history_scores \
  --output data/tai/isolation_forest_run1
python3 -B isolation_forest/model.py \
  --history-dir data/tai/history_oxygen \
  --output data/tai/isolation_oxygen
python3 -B isolation_forest/model.py \
  --history-dir data/tai/history_ammonium \
  --output data/tai/isolation_ammonium
python3 -B -m unittest -v isolation_forest.test_model
```

Choose a new empty private output directory for each run; the program never
overwrites a nonempty directory or input. Configurable options: `--train-end`,
`--validation-end`, `--test-end`, `--validation-flag-fraction`,
`--daily-review-budget`, and `--seed`. Exact commands, source hashes, split
counts, thresholds, package versions, selection and history-detector settings
are captured in the private `run_info.json`.

- `isolation_forest.joblib`: trusted-local fitted model, feature order, settings,
  threshold and package versions. Loading untrusted joblib can execute code.
- `scored_records.csv.gz`: all original history rows, feature values, split,
  AI score/flag/status, explanation, and both budget selections. The three
  features are evidence, not a causal or per-feature attribution of the forest.
- `run_info.json`: completion marker and descriptive held-out counts. No marker
  means an incomplete run. Source paths, inputs and outputs are private.

## Evaluation and next steps

The local run records held-out coverage, unscored reasons, fixed-threshold flag
counts and how many top-K rows overlap. More or fewer flags alone do not show
better detection, false alarms, review costs or savings. Without reviewed
labels, relative usefulness cannot be established. Fixed-threshold counts use
different threshold-setting rules and should not be interpreted as a fair
accuracy comparison. The top-K comparison uses a common review budget, but is
also descriptive without outcomes. No synthetic anomaly recovery or expert
review has been performed.

Ask TAI to confirm the signals and review a documented sample of baseline-only,
AI-only, both and neither selections, including whether they are useful and
how long review takes. If the team authorises synthetic perturbations, inject
them into **copies** of held-out inputs and recompute the history and features
from the modified sequence; keep training and validation untouched. Report
injected-case recovery separately from real-world accuracy. Check performance
on unseen plants and other periods before generalising. Do not claim AI is an
improvement until comparable, independent evidence supports it.

The statistical detector remains available independently. The tests in
`isolation_forest/test_model.py` use artificial fixtures to check chronology,
isolation between series, duplicates, gaps, zero MAD, deterministic fitting,
held-out leakage, budget ties and model reload. They do not prove operational
usefulness or validate all possible data conditions.
