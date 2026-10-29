<p align="center">
  <img src="docs/assets/banner.png" alt="Second Opinion: spot unusual measurements, compare the evidence, and decide what to check first." width="100%">
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-9fd8ea?style=flat-square&labelColor=04090d">
  <img alt="scikit-learn Isolation Forest" src="https://img.shields.io/badge/AI%20layer-Isolation%20Forest-9fd8ea?style=flat-square&labelColor=04090d">
  <img alt="Streamlit dashboard" src="https://img.shields.io/badge/dashboard-Streamlit-9fd8ea?style=flat-square&labelColor=04090d">
  <img alt="Status: research prototype" src="https://img.shields.io/badge/status-research%20prototype-f0a35e?style=flat-square&labelColor=04090d">
</p>

<p align="center">
  <a href="#why">Why</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#interpreting-results">Interpreting results</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#team">Team</a>
</p>

---

**Second Opinion** helps wastewater treatment operators decide which unusual measurements are worth checking first. It compares each daily reading with the recent history of **the same measurement point**, flags readings that deviate or look like a broken sensor, groups flagged days into cases, and ranks them **per plant**. An experimental Isolation Forest adds a second, independent ranking.

Second Opinion supports the operator's judgement and does not replace it. A flag is a reason to look, not a diagnosis, a confirmed fault or proof that everything else is fine.

## Why

Plants record thousands of measurements every day, and most validation relies on fixed limits. Two problems follow:

- **A reading can be unusual for its own point while staying inside a fixed limit.** Limit checks pass it; the operator never sees it.
- **Review time is finite.** Every unnecessary investigation costs attention, so a useful tool has to rank, not just alarm.

The data has no confirmed anomaly labels, so Second Opinion is built to be transparent rather than clever. Every flag shows the value, the historical median, the robust spread, the rule that fired and the source row it came from.

## How it works

<p align="center">
  <img src="docs/assets/pipeline.png" alt="Pipeline: prepare, score, group, investigate, with an Isolation Forest in parallel" width="100%">
</p>

| Stage | What it does | Code |
| --- | --- | --- |
| **Prepare** | Streams a Z-info table export (`Installations`, `MeasurementPoints`, `MeasurementValues`), keeps every row with its source file and row number, parses dates and values, and flags quality issues without deleting, imputing or converting anything. | [`src/data_prep/`](src/data_prep/) |
| **Detect** | Scores each reading against the prior 28 days of its own series using a rolling median and a floored MAD spread, with thresholds calibrated per series. Rules catch stuck sensors, dropouts to zero and negative values. | [`src/history_detector/`](src/history_detector/) |
| **Group** | Merges nearby flagged days into cases and ranks them within each plant: rule hits first, then duration, then peak score. | [`src/history_detector/`](src/history_detector/) |
| **Second view** | Fits one Isolation Forest per measurement group on six history-based features, trained chronologically (train ≤ 2023, validate 2024, hold out 2025). | [`src/isolation_forest/`](src/isolation_forest/) |
| **Review** | A local Streamlit dashboard shows flagged readings, their history and the evidence, in Dutch or English. | [`dashboard/`](dashboard/) |

<p align="center">
  <img src="docs/assets/detector.png" alt="Illustration of the history detector on a synthetic series: rolling median, usual range and flagged spike, stuck and dropout periods" width="100%">
</p>

The pipeline covers six exploratory measurement groups: influent volume, and activated-sludge oxygen, ammonium, nitrate, suspended solids and temperature. Each is a narrow metadata filter, not every reading of that type. Plants are never compared with each other, because they differ in geography, process and timing, and each has its own operator.

See the [methodology](docs/methodology.md) for the full method, design choices and limitations.

## Quick start

### 1. Install

Use Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r dashboard/requirements.txt   # only for the dashboard
```

Requirements are unpinned. Record `python --version` and `python -m pip freeze` alongside any results you need to reproduce.

### 2. Provide data

Second Opinion reads a **Z-info table export** of daily measurements. No data ships with this repository. Place your export at:

```text
data/tai/extracted/
├── Installations/*.csv.gz
├── MeasurementPoints/*.csv.gz
└── MeasurementValues/*.csv.gz
```

`data/` is git-ignored. Measurement data, prepared files, scores and fitted models are derived from operational data, so keep them local and never commit them.

### 3. Run the pipeline

```bash
python src/pipeline.py --plan                           # show what would run or be skipped
python src/pipeline.py --smoke 30                       # quick partial run, 30 points per group
python src/pipeline.py                                  # full run
python src/pipeline.py --groups oxygen --force detect   # redo oxygen detection and downstream
python src/pipeline.py --with-faults                    # add the artificial-fault evaluation
python src/pipeline.py --jobs 3                         # run up to three independent stages at once
```

The driver fingerprints each stage's script, arguments and upstream stages in `data/tai/pipeline_state.json` and skips stages that are already complete and unchanged. It never deletes output: anything that must be redone is first renamed `<name>.old-<timestamp>`. Outputs and one log per stage go to `data/tai/pipeline/` (or `data/tai/pipeline_smoke<N>/`). Full preparation needs substantial time and disk space. Each detector holds its whole group in memory, so check free RAM before raising `--jobs`.

### 4. Open the dashboard

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

### 5. Run the tests

```bash
python -B -m unittest discover -s tests -t . -v
python -B -m unittest discover -s dashboard -p "test_*.py" -v
```

All tests use small artificial fixtures, never real measurements.

## Interpreting results

- **History score:** distance from the point's prior median, in robust spreads. It is not a probability or a severity.
- **Rules:** stuck, dropout and negative are data-quality prompts, independent of the score.
- **Unscored:** every unscored reading carries a reason (insufficient history, same-day duplicates, invalid value, constant zero, …). Unscored never means normal.
- **Isolation Forest score:** a higher score means a rarer combination of features. It is not a fault probability, and scores from different group models are not comparable.
- **Evaluation:** the comparisons between the two methods are descriptive and use the same per-plant daily review budget. Recovery of artificial faults is not real-world accuracy. Without labelled incidents or expert review, Second Opinion makes **no claims** about precision, recall, false-alarm reduction or time saved.

## Documentation

| Guide | Covers |
| --- | --- |
| [Methodology](docs/methodology.md) | Problem framing, the full method, design decisions and limitations |
| [Data preparation](docs/data_prep/README.md) | Input format, preparation outputs, verification and supplementary reports |
| [History detector](docs/history_detector/README.md) | Measurement groups, scoring, rules, cases, options and the artificial-fault evaluation |
| [Isolation Forest](docs/isolation_forest/README.md) | Features, eligibility, chronological splits, thresholds and the budget comparison |
| [Dashboard](dashboard/README.md) | The operator prototype and the dry-weather exploration |
| [Presentation](slide_deck/) | Seven-slide overview (`index.html`, PDF export and speaker notes) |

## Repository layout

```text
src/pipeline.py              Pipeline driver
src/data_prep/               Preparation, verification and data reports
src/history_detector/        History detector and artificial-fault evaluation
src/isolation_forest/        Experimental Isolation Forest
dashboard/                   Streamlit operator prototype
tests/                       Synthetic-fixture tests
docs/                        Methodology, component guides and README graphics
slide_deck/                  Project presentation
data/                        Local data and outputs (git-ignored)
```

## Status and limitations

Second Opinion is a research prototype run on historical, day-level data. It is not a live alerting system. Measurement meanings, units, reporting periods and observation availability have to be confirmed with whoever supplies the data. The thresholds encode an assumed review workload, roughly 1% of readings, not a validated false-alarm rate. Next steps would be expert review of a documented sample of flagged and unflagged cases, persistent operator feedback, and a comparison against the validation limits that actually applied at the time.

## Team

Built by
[Joshua Varghese Thomji](https://github.com/josh1221wa),
[Sunil Parameswaran](https://github.com/SunilParameswaran),
[S Smriti](https://github.com/smritis21) and
[Oindrilla](https://github.com/oindrilla007).
