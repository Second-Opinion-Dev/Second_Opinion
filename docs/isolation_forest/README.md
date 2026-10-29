# Isolation Forest

This experimental layer produces a second, independent ranking of the readings that the history detector can score. It learns unusual combinations of history-based features within one measurement group. It does not compare plants, use identifiers as features, diagnose causes or replace the history-based case ranking, which remains usable on its own.

## Run

After the [history detector](../history_detector/README.md), from the repository root and with a new, empty output directory:

```bash
python src/isolation_forest/model.py --history-dir data/tai/history_oxygen --output data/tai/isolation_oxygen
```

Run one forest per measurement group. To run every group, use the [pipeline driver](../../README.md#3-run-the-pipeline).

## Input checks

The model needs a complete history-detector output (`run_info.json` and `history_scores.csv.gz`). It verifies the completion status, row count and selection, and records SHA-256 hashes of its inputs. It keeps all source rows, including the history-detector status, quality flags and provenance.

## Features

For each series, only previously scored, unambiguous records are used:

1. **Signed deviation:** `(value − prior median) / spread`, using the history detector's floored spread.
2. **One-day change:** `(value − previous day's value) / spread`. The previous calendar day must have a valid score; gaps are not imputed.
3. **Prior mean deviation:** the mean of `log1p(|signed deviation|)` over scored observations in `[day − 7, day)`, requiring at least three.
4. **Relative level:** `(value − prior median) / max(|prior median|, spread)`.
5. **Zero:** 1 when the value is exactly zero.
6. **Repeat days:** the `log` of the number of consecutive days with this exact value.

Features 1, 2 and 4 use `sign(x) · log1p(|x|)`. The transforms have no fitted parameters, and there is no scaler or imputer. Ineligible rows stay in the output with an `ai_status` and a blank `ai_score` / `ai_flag`. A row the history detector left unscored is never relabelled normal.

## Training and thresholds

| Split | Default end | Role |
| --- | --- | --- |
| Train | 2023-12-31 | Fit `IsolationForest` (seed 42, 100 trees, `max_samples=256`) |
| Validation | 2024-12-31 | Set the alert threshold at the 99th percentile of scores |
| Held out | 2025-12-31 | Apply the fixed threshold and compare methods |

`ai_score = −score_samples`, so higher means more unusual. It is not a probability. The 1% validation rate is a workload assumption. Its thresholds are not comparable with the history detector's, because they were set on different periods and different scores.

## Budget comparison

To compare the methods fairly, each one independently selects the top eligible reading **per plant per day** (`--plant-daily-budget 1`) from exactly the same eligible rows. The baseline ranks rule hits first, then the robust score. The forest ranks by `ai_score`. Ties break on source file, then numeric source row. Selection can include readings below either method's alert threshold. The budget applies separately to each measurement group; it is not a shared operator budget. Deferred or unscored readings are not safe.

## Options

`--train-end`, `--validation-end`, `--test-end`, `--validation-flag-fraction`, `--plant-daily-budget` and `--seed`.

## Outputs

- `scored_records.csv.gz`: all history rows, feature values, split, AI score, flag and status, explanation, and both budget selections.
- `isolation_forest.joblib`: the fitted model, feature order, settings, threshold and package versions. **Load joblib files only from trusted local sources**, because loading one can execute code.
- `run_info.json`: the completion marker, holding the configuration, source hashes, split counts, thresholds, versions and descriptive held-out counts.

## Limits

Coverage, flag counts and top-K overlap describe the two methods without showing that either is accurate. Without labelled incidents or documented expert review, there is no measured accuracy, false-alarm reduction or time saving. Check behaviour on unseen plants and other periods before generalising.

Code: [`src/isolation_forest/`](../../src/isolation_forest/). Tests: [`tests/test_isolation_forest.py`](../../tests/test_isolation_forest.py).
