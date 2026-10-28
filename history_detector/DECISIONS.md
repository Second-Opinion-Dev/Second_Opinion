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
