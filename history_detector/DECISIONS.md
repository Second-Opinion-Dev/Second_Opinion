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
