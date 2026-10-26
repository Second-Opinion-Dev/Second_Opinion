# Working principles (apply at every stage)

## Honesty
- Never invent dataset characteristics, metrics, labels, confidence or physical causes.
- Separate **MODEL OBSERVATION** from **POSSIBLE DOMAIN INTERPRETATION**. Correlation and
  feature contributions are not causality. Say what the data cannot support.
- No ground truth => limit claims explicitly. Fewer alerts alone is not fewer false alarms.

## Modelling
- Ask "is this unexpected *given context*?", not "is this value unusual?". Use only context
  actually present in the data and available at inference time.
- Start with a credible, simple baseline (robust stats, rolling scores, seasonal/forecast
  residuals) and compare models objectively. Complexity must be justified by evidence;
  no LSTMs/autoencoders/GNNs for show. A tree/statistical model with a polished system often wins.
- Prevent leakage: chronological (and entity-aware) splits, preprocessing/thresholds fit on
  train only, no future info in features or streaming replay.
- Metrics by task: imbalanced anomalies -> PR-AUC, recall at fixed FPR, event-level
  precision/recall, detection delay, raw points vs consolidated events. Regression/forecast
  -> MAE, RMSE, residuals. Never report fabricated numbers.

## Engineering
- Python, readable functions, type hints where useful, comments for non-obvious reasoning.
- Reusable logic in modules (e.g. `src/`), notebooks exploratory only, the app imports modules.
- Seeds, saved config, saved artifacts, recorded package versions, exact run commands.
- Never modify raw data in place; derived data goes elsewhere. Create folders only when needed.
- Record consequential choices in `DECISIONS.md` so ideas are not re-litigated.
- Ask the user only when a blocking ambiguity cannot be resolved by inspecting the files.

## Prioritisation
Split all work into **MUST HAVE** (credible working submission), **SHOULD HAVE**
(substantially more competitive), **WOW** (differentiator if time permits). Never sacrifice
a working core for an unfinished fancy feature. For each feature ask: *would this help the
water professional make a better decision?*

## Data safety
Data is shared with teammates by committing `data/` to this (private) repo; that is the only
sanctioned place. Otherwise work locally: no uploading data or sending raw contents to external
APIs/services without explicit user authorisation. Do not expose sensitive identifiers in docs, logs or screenshots.
