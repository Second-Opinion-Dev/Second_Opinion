# History detector

The history detector flags readings that differ from their own series' recent history or that trigger a data-quality rule. It runs independently of the AI layer and never compares plants with each other. A flag is a candidate for investigation, not a diagnosis.

See the [methodology](../methodology.md) for the reasoning behind each choice.

## Run

After a complete [data preparation](../data_prep/README.md), from the repository root and with a new, empty output directory:

```bash
python src/history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_oxygen --measurement oxygen
```

To run every group together with the AI layer, use the [pipeline driver](../../README.md#3-run-the-pipeline).

## Measurement groups

`--measurement` selects one group per run: `influent_volume` (default), `oxygen`, `ammonium`, `nitrate`, `suspended_solids` or `temperature`. Descriptions and input types are matched case-insensitively. Units are matched exactly and never converted. The exact filters are listed in the [methodology](../methodology.md#1-prepare-and-select-inputs).

## Algorithm

- **Series keys:** `InstallationCodeOrigin`, `MeasurementPointID`, `SubProcessCodeOrigin`, `ProcessCode`, `Product`, `ProductBalance`, `InstallationCodeDestination`, `SubProcessDestination` and `Unit`.
- **Window:** valid, unambiguous observations in `[day − 28, day)`, with at least 14 distinct days. The current reading is never part of its own baseline.
- **Score:** `|value − median| / max(1.4826 × MAD, 0.05 × |median|)`, with direction `above` or `below`.
- **Thresholds:** calibrated per series and per direction on data up to `--calibration-end`, at a target flag rate split equally between directions, with a minimum of 2.0. Series with fewer than 100 scored calibration readings use the median of the other series. `thresholds.csv` lists every series. `--threshold X` uses one fixed value for all series instead.
- **Clipped history:** each valid observation enters later windows clipped to `median ± 3.5 × spread`. Reported values are never changed.
- **Rules:** `rule_stuck`, `rule_dropout` and `rule_negative` (the last is not applied to temperature). `review_flag` combines the statistical flag and the rules. `flag_reason` lists `stuck`, `dropout`, `negative`, `unusual_high` and `unusual_low`.
- **Cases:** review-flagged days of one series separated by at most `--case-gap-days` form a case, ranked within each plant by rule hits, flagged days and peak score (`plant_rank`).
- **Unscored states:** invalid date or value, any preparation flag set, an ambiguous same-day duplicate, `unscored_insufficient_history` or `unscored_zero_spread`. Each row carries a status and an explanation.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--window-days` | 28 | History window length |
| `--minimum-history` | 14 | Valid days required to score |
| `--scale-floor-fraction` | 0.05 | Spread floor as a fraction of the median |
| `--clip-limit` | 3.5 | History clipping in spreads; `0` disables clipping |
| `--stuck-days` | 7 | Consecutive equal values for the stuck rule |
| `--no-rules` | off | Disable the data-quality rules |
| `--calibration-end` | 2023-12-31 | Last date used to calibrate thresholds |
| `--target-flag-rate` | 0.01 | Assumed review workload used for calibration |
| `--threshold` | none | A fixed threshold instead of calibration |
| `--case-gap-days` | 1 | Unflagged days allowed inside one case |
| `--max-points` | none | Smoke run on the first N selected points (marked `smoke_run_partial`) |

## Outputs

- `history_scores.csv.gz`: original dates, values, units, source file and row, process and point descriptions, preparation flags, history days, median, MAD, spread, score, direction, repeat days, rule columns, nullable statistical and review flags, reason, status, explanation and case ID.
- `cases.csv.gz`: one row per case with start, end, flagged days, peak score, reasons and plant rank.
- `thresholds.csv`: calibrated thresholds per series.
- `run_info.json`: the completion marker, holding the selection, settings, thresholds, package versions and counts. If it is missing, the run did not finish.

`history_days` is blank for observations rejected before a window was built, and zero when an eligible observation had no usable history.

## Artificial-fault evaluation

```bash
python src/history_detector/synthetic_faults.py --prepared data/tai/prepared_history --output data/tai/faults_influent --measurement influent_volume --sample 100
```

This copies a seeded sample of series, injects one fault per copy in the held-out year (a spike of 6 spreads, a 3-day dropout, a 10-day stuck value or a 28-day drift to 4 spreads), and scores each copy with three variants: `legacy` (no floor, no clipping, no rules, fixed threshold 3.5), `revised` (current defaults) and `revised_no_clip`. It also reports the workload on unmodified data. These results describe artificial cases only.

Code: [`src/history_detector/`](../../src/history_detector/). Tests: [`tests/test_history_detector.py`](../../tests/test_history_detector.py).
