---
name: build
description: Stage 7. Build the selected system incrementally in reusable modules, keeping the project runnable.
---

# Stage 7: Build

Create the project structure now, only what is needed (e.g. `src/` modules for data, features,
models, evaluation, explainability; `artifacts/`, `reports/`, `tests/`). Generated output folders
(`artifacts/`, `reports/`) and partner datasets are git-ignored; code in `src/`, tests in
`tests/` and documentation in `docs/` are tracked. Build in increments: MUST first, run end to end, then SHOULD, then WOW.

- Small functions, clear names, config in one place, deterministic seeds.
- Produce explanations as structured records (see `.agents/templates/EVENT_CARD.md`): time span,
  severity, affected variables, top contributors, observed vs expected, confidence only if
  defensible, *model observation* kept separate from a hedged *possible interpretation*, and a
  recommended investigation.
- After each increment, run it and a quick check; only keep states that work.
