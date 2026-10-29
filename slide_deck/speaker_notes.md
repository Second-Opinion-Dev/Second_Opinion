# Second Opinion: speaker notes

Open `index.html` in a browser. Keys: `→` / `Space` next, `←` back, `F` fullscreen, `Home` / `End` first / last slide. `second-opinion-deck.pdf` is a static export of the same slides.

## 1. Title

Second Opinion helps wastewater operators find unusual measurements and decide what to investigate. It currently covers six exploratory measurement groups: influent volume and activated-sludge oxygen, ammonium, nitrate, suspended solids and temperature. Their operational meaning, units and reporting period still need confirmation from the data provider; they are not an approved, universal selection.

## 2. Problem

The historical data has no confirmed anomaly labels. An unusual measurement may reflect an operational change, a measurement issue or something else. A reading can be unusual for its own measurement point while still sitting inside a fixed validation limit. Each unnecessary check costs an operator time; without operator feedback we cannot say how many alerts are false or how much time is saved.

Second Opinion judges each point only against its own recent history, never against other plants: plants differ in geography, process and timing.

## 3. End-to-end pipeline

1. Prepare the Z-info export and select the exploratory groups, retaining installation, measurement point, process context, dates and source references.
2. Run the independent history detector and quality rules. Keep unsuitable readings with an unscored reason.
3. Group flagged readings from the same series into cases and rank cases within each plant.
4. The optional Isolation Forest produces a separate score and flag for eligible readings. Review the evidence and compare rankings; the operator makes the decision.

No peer comparison is used. The present input is historical and date-level, not a live feed.

## 4. History detector

Each series is defined by point, installation and process context. For each reading, the detector looks at the previous 28 calendar days, excluding today, and requires at least 14 valid days. It compares the value with the history's median using a robust spread based on MAD, with a 5% floor. Previous extreme values are clipped before entering later windows. Above- and below-median thresholds are calibrated separately per series using data through 2023; the assumed 1% rate is a tuning choice, not a measured false-alarm rate.

Rules also check for repeated values after a varying history, zeros after a zero-free period, and negative values. Flagged days within a series become a case when separated by at most one unflagged day. Cases are ordered per plant by rule hits, duration and peak deviation. Invalid, ambiguous, duplicate, insufficient-history and constant-zero situations can make records unscored; a blank score does not mean normal.

## 5. Experimental Isolation Forest

The AI layer uses six same-point features: signed deviation, one-day change, mean prior deviation, relative level, zero indicator and repeated-day count. It fits one forest per measurement group. The models pool normalised features within a group, but do not compare plants with one another, and do not use identifiers as numeric features. Missing or unsuitable feature histories remain unscored.

It finds uncommon combinations, not physical causes or fault probabilities. Its output is an optional second ranking, separate from the history-based case queue. Scores from different group models are not directly comparable.

## 6. Evaluation

Each forest is trained through 2023 with a fixed seed; the 2024 validation scores set a provisional 99th-percentile alert threshold; 2025 is held out. The retrospective comparison uses the same eligible readings and an example budget of one reading per plant per day, separately for each group. A budget ranking can include readings below the alert threshold.

Report coverage, unscored reasons, candidate workload and overlap. Artificial changes, when used, are applied to copies of held-out data and measure artificial-case recovery only. Without confirmed labels or documented expert review, these results do not establish real-world accuracy, false-alarm reduction or savings. If the AI does not add value, retain the simpler detector.

## 7. Close

The intended operator experience is to inspect a ranked case, understand its historical evidence and rules, optionally compare the AI view, and decide what to investigate. The local dashboard prototype shows this flow on precomputed results; persistent feedback capture is future work. Measurement data, model outputs and credentials stay local and are never committed.

For implementation details, see the [methodology](../docs/methodology.md) and the component guides under [`docs/`](../docs/).
