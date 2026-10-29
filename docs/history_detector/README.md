# History detector

The history detector flags readings that differ from their own series' recent history or trigger a data-quality rule. It runs independently of the AI layer and does not compare peer plants. A flag is a candidate for investigation, not a diagnosis.

## How it works

For each installation, point and process context, use up to 28 previous calendar days and require 14 valid days. Compare the current value with the prior median using a robust, floored MAD spread. Per-series high and low thresholds are calibrated using data through 2023; the assumed 1% target is a workload setting, not a measured false-alarm rate. The rules also identify stuck readings and unexpected zeros. Negative values are flagged for nonnegative measurement groups, but not temperature.

Nearby flagged days are grouped into cases, ranked within each plant by rule hits, duration and peak score. The output retains source references and unscored reasons. Some rules can still flag eligible records whose statistical score is unavailable; absence of a score never means normal.

## Run

After a complete [data preparation](../data_prep/README.md), run from the repository root, using a new empty output directory:

```bash
python src/history_detector/history_detector.py --prepared data/tai/prepared_history --output data/tai/history_oxygen --measurement oxygen
```

The other group choices are `influent_volume` (the default), `ammonium`, `nitrate`, `suspended_solids` and `temperature`. Outputs include `history_scores.csv.gz`, `cases.csv.gz`, calibrated thresholds and `run_info.json`; keep them private. To run all six groups and the AI layer, see the [pipeline driver](../../README.md#run).

See the [handoff](HANDOFF.md) for exact filters, configuration, edge cases, artificial-fault evaluation, recorded tests and limitations, and [decisions](DECISIONS.md) for design choices. Code: [`src/history_detector/`](../../src/history_detector/); tests: [`tests/test_history_detector.py`](../../tests/test_history_detector.py).
