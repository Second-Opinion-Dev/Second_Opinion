# Isolation Forest

This experimental layer provides a separate ranking of eligible history-detector readings. It learns unusual combinations of six same-series features: signed deviation, one-day change, prior mean deviation, relative level, zero indicator and repeated-day count. It does not compare peer plants or use raw identifiers as numeric features. The primary history-based case ranking remains independently usable.

One forest is fitted per exploratory measurement group. Defaults train through 2023, set a threshold using 2024 validation scores and hold out 2025. The comparison ranks the same eligible readings at an example budget of one reading per plant per day per group. Scores from separate group models are not directly comparable. Missing or unsuitable features remain unscored; the score is not a fault probability or diagnosis.

## Run

After completing the [history detector](../history_detector/README.md), run from the repository root with a new empty output directory:

```bash
python src/isolation_forest/model.py --history-dir data/tai/history_oxygen --output data/tai/isolation_oxygen
```

The private output contains `scored_records.csv.gz`, `isolation_forest.joblib` and `run_info.json` with configuration, versions and descriptive results. Never load an untrusted joblib file. For all groups, see the [pipeline driver](../../README.md#run).

There are no confirmed anomaly labels, so coverage, flags and ranking overlap cannot establish real-world accuracy, false-alarm reduction or savings. Expert review is needed to assess usefulness. See the [handoff](HANDOFF.md) for features, splits, commands, tests and limitations. Code: [`src/isolation_forest/`](../../src/isolation_forest/); tests: [`tests/test_isolation_forest.py`](../../tests/test_isolation_forest.py).
