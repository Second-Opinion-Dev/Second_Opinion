# Data preparation

The preparation stage downloads the TAI export, preserves original records and provenance, and produces quality flags and metadata for downstream detection. The dataset and all derived outputs are private. Definitions, installation joins, reporting cadence and the selected measurements remain subject to TAI confirmation.

## Run

Install the [project requirements](../../README.md#setup), set `AISO_API_KEY` privately via `data/.env` or the environment, then run from the repository root:

```bash
python src/data_prep/download.py tai
python src/data_prep/tai_pipeline.py --raw data/tai/extracted --output data/tai/prepared_history
python src/data_prep/tai_verify.py data/tai/prepared_history
```

Preparation requires a new or empty output directory. The full export needs significant time and disk space. `--limit-files` creates a partial preparation for inspection; the detector requires a full preparation. The main [pipeline driver](../../README.md#run) orchestrates these stages and can reuse completed inputs.

The preparation output includes `summary.json`, `point_metadata.csv.gz`, retained compressed rows under `cleaned/`, quality reports and a local SQLite intermediate. Rows keep source-file and source-row references. Flags highlight candidate issues; they do not remove, impute, average or convert source data.

## Further reading

- [Handoff](HANDOFF.md): commands, supplementary reports and caveats.
- [Data audit](DATA_AUDIT.md), [decisions](DECISIONS.md), [questions](QUESTIONS.md) and [work log](WORK_LOG.md).
- Code: [`src/data_prep/`](../../src/data_prep/); tests: [`tests/test_tai_pipeline.py`](../../tests/test_tai_pipeline.py).

Do not commit data, derived outputs or the API key, and do not alter raw files in place.
