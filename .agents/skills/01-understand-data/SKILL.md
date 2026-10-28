---
name: understand-data
description: Stage 1. Inspect all supplied files and document what the data is, its structure and quality in DATA_AUDIT.md. Use before any modelling.
---

# Stage 1: Understand the data

Inspect everything recursively; do not model yet. For each file/table record in `DATA_AUDIT.md`
(only facts you verified; mark inferences as *inferred* and unknowns as TODO):

- format, encoding/delimiter, dimensions, relationships and join keys;
- every column: dtype, apparent meaning, units (confirmed vs guessed), missing %, odd ranges,
  sentinel values (-999, 0, 9999), constant or duplicated columns;
- timestamps: format, timezone/DST, range, ordering, duplicates, gaps, sampling frequency per entity;
- identifiers, locations/assets, coordinates and CRS, sensitive fields;
- labels/targets: existence, definition, prevalence, point vs event, delay;
- schema/instrumentation changes, flatlines, impossible values;
- leakage risks and candidate context variables.

Use quick pandas profiling in a script or notebook; keep reusable loaders in a module.
Explain to the user in plain language what each file and important column appears to be, and
list unresolved questions (worth asking the organisers on the day).

For the TAI challenge, use the existing scripts under `src/tai/` and the instructions in
`docs/tai/HANDOFF.md`; consult `DATA_AUDIT.md` and `docs/tai/QUESTIONS.md` before making
assumptions. Keep partner data, generated reports and access keys local and out of Git.

Done when: `DATA_AUDIT.md` is filled in and the user has the summary.
