---
name: validate
description: Stage 9. Test edge cases, reproducibility, app execution, model loading and evaluation consistency before presenting.
---

# Stage 9: Validate

Check and report honestly (including failures):

- edge cases: missing values, empty or short series, new categories, out-of-range inputs;
- reproducibility: clean venv install, rerun from raw data with fixed seeds reproduces metrics;
- saved artifacts load; the app starts from a clean checkout and runs the demo path;
- evaluation consistency: same split and metrics across models, no leakage (re-audit joins,
  scalers, thresholds, windows);
- every claim in the pitch traces to a recorded result.

Record exact run commands and package versions in `README.md` / `DECISIONS.md`.
