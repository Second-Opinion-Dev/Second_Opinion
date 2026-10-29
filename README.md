# Second Opinion

Second Opinion is an AI for Water hackathon prototype that helps wastewater operators review unusual measurements. It compares a reading with its own recent history and uses an experimental Isolation Forest to identify uncommon combinations of historical signals. A local dashboard presents previously scored readings for review.

**Status:** Research prototype, not an operational alarm system. The data has no confirmed anomaly labels, and the measurement definitions require partner confirmation. A flag is a reason to investigate, not a diagnosis. We have not established real-world accuracy, false-alarm reduction or time savings.

## What the project does

1. **Prepare:** retain original TAI measurement values, timestamps, source references and quality flags.
2. **Compare history:** score each eligible reading against the same point's previous 28 calendar days; apply rules for selected quality issues and group flagged days into cases.
3. **Offer a second opinion:** fit a separate Isolation Forest per selected measurement group, using six features derived from that point's current and previous readings.
4. **Review:** the local dashboard reads precomputed forest scores and displays individual flagged readings, supporting evidence and a per-metric review budget.

The pipeline supports six exploratory groups: influent volume, oxygen, ammonium, nitrate, suspended solids and temperature. Each group is a narrow metadata selection, not all possible measurements of that type. The default driver runs one forest per group; having code for six groups does not mean all six models or outputs are available in a particular installation. There is no peer comparison.

The history detector's grouped cases and the dashboard's individual forest-flagged reading queue are separate outputs. The dashboard does not load fitted models or run new inference. Its review checkboxes last only for the browser session. See [the dashboard guide](dashboard/README.md) for current behavior and limitations.

## Get started

Use Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, create the environment with `python -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`. Dependencies are unpinned. For reproducible runs, record `python --version` and `python -m pip freeze` alongside the results.

### Try the dashboard

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

Without partner outputs, select the explicitly labelled fictional example plant to explore example temperature, nitrate and suspended-solids readings. These examples are invented and have not been scored by a model. Missing results for the other groups are reported. To use real outputs, point the sidebar at a compatible private results directory; see [dashboard setup](dashboard/README.md).

### Run the pipeline

The real TAI dataset and trained models are **not included**. Dataset access was provided for the hackathon and the original key expired after the event; access or reuse requires the partner's permission. If you have authorised local data and valid access, configure `AISO_API_KEY` privately using `data/.env.example` as a template or an environment variable. Never commit or share the key, data, derived results or model files. The partner briefing requires deleting the data after the event unless the partner agrees otherwise in writing.

```bash
python src/pipeline.py --plan                      # inspect actions without running stages
python src/pipeline.py --smoke 30                  # limit downstream work to 30 points per group
python src/pipeline.py                             # run the full pipeline
python src/pipeline.py --groups oxygen --force detect
python src/pipeline.py --with-faults               # optional artificial-fault comparison
```

The driver downloads, prepares and verifies data, then runs the history detector and forest for each selected group. `--smoke` still requires complete preparation and does not represent a full analysis. Full preparation may require substantial time, disk and memory. `--jobs N` runs independent stages concurrently; each detector holds its group in memory. The driver records local state and moves replaced outputs aside with an `.old-<timestamp>` suffix. Results and logs stay under ignored `data/tai/` directories.

For individual steps, consult [data preparation](docs/data_prep/README.md), [history detector](docs/history_detector/README.md) and [Isolation Forest](docs/isolation_forest/README.md).

## Tests

These tests use synthetic fixtures and do not measure operational performance:

```bash
python -B -m unittest discover -s tests -t . -v
python -B -m unittest discover -s dashboard -p 'test_*.py' -v
```

## How to interpret results

The history baseline uses a rolling median and robust spread, with separate rules for selected quality patterns. Ineligible readings remain unscored with reasons; they are not automatically normal. The experimental forest learns unusual combinations of six history-based features. Its score is not a probability, and scores from different group models should not be compared directly.

Default forest training uses data through 2023, validation in 2024 and a held-out period in 2025. A retrospective comparison ranks the same eligible readings under an example per-plant, per-day budget, separately for each group. Artificial-fault recovery, flag counts and ranking overlap do not establish real-world accuracy or savings. Operator review is needed to measure usefulness and the time spent investigating false alarms. See [idea.md](idea.md) for the broader framing.

## Repository map

```text
src/data_prep/          Data download, preparation and quality reports
src/history_detector/   History baseline, case grouping and artificial-fault evaluation
src/isolation_forest/  Experimental AI layer and retrospective comparison
src/pipeline.py        Pipeline driver
dashboard/             Local Streamlit review prototype and fictional examples
tests/                 Synthetic-fixture tests for the pipeline and models
docs/                  Data audit, decisions, component guides and handoffs
slide_deck/            Hackathon presentation
idea.md                Project framing and methodology
data/                  Private local inputs and outputs, excluded from Git
```

Work on a branch and open a pull request into `main`; see [the team workflow](.agents/skills/branch-and-pr/SKILL.md). Never modify raw partner data in place. Only load model files from trusted sources: `joblib` files can execute code when loaded.
