---
name: improve
description: Stage 5. Add context-aware features and stronger models, comparing quantitatively against the baseline.
---

# Stage 5: Improve

Add features that encode context actually present in the data (time/season, lags, rolling stats,
operating state, other sensors, weather/flow, neighbours). Try stronger models only if the
baseline's failure modes justify them (trees/boosting, PCA residuals, forecasting residuals,
change-point detection, probabilistic or spatial models; deep learning only with clear evidence).

Compare every candidate with the same split and metrics in one table. Record what was tried and
rejected in `data/tai_work/DECISIONS.md` so it is not repeated. Add event aggregation, persistence or hysteresis
if raw flags are noisy. Stop when marginal gains no longer change the story: time is better
spent on Stages 6-8.
