# History detector decisions

## Proposed history-only baseline — 28 October 2026

Implement a per-point, per-process-context rolling median/MAD detector for the
exploratory Influent / Volume / m3 / scada / parameter-not-applicable slice.
Use the previous 28 calendar days, at least 14 valid days, and a provisional
configurable threshold of 3.5. Preserve provenance, quality flags and raw values;
mark ambiguous same-day records, insufficient history and zero MAD unscored.
Prior flagged values remain in later history. Data meaning, date availability,
threshold and quality rules require review with TAI.

The user requested no peer comparison or testing/evaluation in this work. No
performance or false-alarm claims are made. See `HANDOFF.md` in this folder
for commands, decisions, edge cases and the next teammate's testing plan.

## Experimental Isolation Forest — 28 October 2026

Add a separate, seeded Isolation Forest over signed historical deviation,
one-day change and prior history-flag fraction. Use strictly earlier observations
for history features; keep incomplete and ambiguous rows unscored. Train through
2023, calibrate on 2024, and hold out 2025. The default 99th-percentile validation
threshold and 10-reading daily budget are configurable assumptions, not verified
false-alarm costs. The baseline remains independently runnable, and no peer
comparison is used. See `../isolation_forest/HANDOFF.md` for run commands,
comparison definitions, results location and limitations. Do not claim an
improvement or operational accuracy without expert-reviewed outcomes.

## Add exploratory oxygen and ammonium cohorts — 28 October 2026

Keep the existing influent-volume selection as the default. Add separate
metadata-defined SCADA groups for active-sludge oxygen concentration in mg/l
with state not applicable, and active-sludge ammonium concentration in mg/l
expressed in nitrogen. Preserve each point's history and train a separate
Isolation Forest for each group; keep each plant's history separate, do not mix
units, materials or states within the new groups, and do not interpret raw
scores from different models as comparable. Each forest pools normalised
features across selected points. The literal metadata
definitions and units remain unconfirmed by TAI; this does not cover all oxygen
or ammonium measurements. Existing per-run review budgets are not a shared
operator budget across groups. Store data, models and results locally. See both
handoffs for selection, commands, testing, provenance and limitations.

## Team decisions: no plant comparison, one operator per plant — 28 October 2026

The team decided not to compare plants: they differ geographically and in
timing. Each plant has its own operator who rarely sees other plants, so review
budgets and rankings are per plant, never one list across all plants.

## Detector logic fixes after QC — 28 October 2026

A QC run showed the fixed 3.5 threshold flagged 15.5% of influent readings
(95% upward), zero-MAD meters went unscored (so stuck sensors were invisible),
tiny meters received extreme scores, flagged values quickly became normal, and
each flagged day counted separately. Changes, each configurable:

- Calibrate above/below thresholds **per series** on its own data up to 2023 to
  a 1% workload assumption, split equally between directions, never below 2.0.
  Series with too little calibration data use the median of other series. A
  first attempt pooled one threshold per group; on full influent data the most
  erratic meters pushed the upward threshold to about 93 spreads for everyone,
  so pooling was replaced.
- Floor the spread at 5% of the absolute median.
- Clip values entering later history to median ± 3.5 spreads.
- Add stuck (7 days after a varying window), dropout (zero after a window
  without zeros) and negative rules, independent of the threshold.
- Count a valid row as ambiguous only when another valid row shares its date.
- Group flagged days into cases (one-day gap allowed) and rank them within each
  plant: rules first, then length, then peak score.
- Isolation Forest: replace the threshold-dependent prior-flag fraction with the
  prior mean deviation; add relative level, zero and repeat features; compare
  budgets per plant per day; break ties on numeric source rows.
- Add `synthetic_faults.py` to compare legacy and revised settings on artificial
  faults in copies of 2025 data.

The 1% target, 5% floor, 3.5 clip limit and 7 stuck days are assumptions to
review with TAI and operators. Synthetic-fault results are not real-world
accuracy. Keep the forest only if it outperforms the revised detector on
comparable evidence. A 30-point smoke run (see `HANDOFF.md`) showed far better
stuck and dropout detection at about a seventh of the legacy workload, but most
moderate influent spikes and drifts were missed; the target rate is a
workload–sensitivity trade-off to settle with operators.
