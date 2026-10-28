---
name: baseline
description: Stage 4. Implement and evaluate the simplest credible baseline with proper splits and metrics.
---

# Stage 4: Baseline

Build the simplest approach that is credible for the task (e.g. robust z-score or rolling
median+MAD, seasonal-naive residuals, Isolation Forest, simple regression/classifier).

- Chronological (and entity-aware) split; fit scalers/thresholds on train only; fixed seeds.
- Evaluate with the metrics agreed in Stage 2, plus operational numbers (flagged points,
  consolidated events, delay) where relevant. Without labels, say clearly that results are
  descriptive; proxies (stability, recovery of clearly marked synthetic perturbations of held-out
  data, expert review) must never be called accuracy.
- Save config, predictions and metrics to a results location (create it now, git-ignored).
- Log the result and run command in `docs/data_prep/DECISIONS.md`. Keep this baseline as the comparison anchor.
