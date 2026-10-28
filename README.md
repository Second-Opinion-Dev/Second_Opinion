# Second Opinion — AI for Water

Second Opinion helps wastewater operators investigate unusual TAI / Z-info measurements. It compares each reading with its own recent history, groups flagged days into cases and offers an experimental Isolation Forest as a second ranking. An operator decides what to investigate; neither detector diagnoses a fault.

There are no confirmed anomaly labels. The selected measurement groups and their meanings remain exploratory; real-world accuracy, false-alarm reduction and time savings have not been established. A dashboard and feedback workflow are proposals, not implemented components. See [idea.md](idea.md) for the problem, methodology and limitations.

## Pipeline

```text
TAI download → prepare and retain provenance → verify
  → history detector + data-quality rules → per-plant ranked cases
  → optional Isolation Forest → separate scores and comparison
  → optional artificial-fault evaluation (history detector)
```

The driver runs the history detector and a separate Isolation Forest for each group: `influent_volume`, `oxygen` and `ammonium`. These are narrow exploratory metadata filters, not every reading of those types; their meaning and availability need confirmation from TAI. The history detector remains independently usable. No peer comparison is implemented.

| Component | Purpose | Documentation |
| --- | --- | --- |
| Data preparation | Download, retain source rows and flag quality issues | [Data preparation](docs/data_prep/README.md) |
| History detector | Score prior history, apply rules and group cases | [History detector](docs/history_detector/README.md) |
| Isolation Forest | Rank eligible readings using history-based features | [Isolation Forest](docs/isolation_forest/README.md) |

## Setup

Use Python 3.11 or newer. From the repository root, on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, use `python -m venv .venv`, then `.venv\Scripts\Activate.ps1`, followed by the same pip install command. Requirements are unpinned; record `python --version` and `python -m pip freeze` with results you need to reproduce. Model files are version-sensitive: use trusted local files and the recorded package versions.

For a new TAI download, copy `data/.env.example` to `data/.env` and privately add `AISO_API_KEY` from the participant briefing. Alternatively set the environment variable in your shell. The key was issued for the event and its availability may have expired. Never paste it into Git, documentation, chat or shell history.

## Run

From the repository root:

```bash
python src/pipeline.py --plan                           # inspect planned actions
python src/pipeline.py --smoke 30                       # partial run, 30 points per group
python src/pipeline.py                                  # full run
python src/pipeline.py --groups oxygen --force detect   # rerun oxygen detection and downstream
python src/pipeline.py --with-faults                    # optional artificial-fault evaluation
python -B -m unittest discover -s tests -t . -v        # synthetic-fixture tests
```

The smoke run still requires full preparation; it limits points in downstream stages and is not a complete analysis. `--plan` performs no stages. The driver reuses complete outputs when its fingerprints match, records state in `data/tai/pipeline_state.json`, and moves existing outputs aside with an `.old-<timestamp>` suffix before a rerun. Review the plan and allow substantial time and disk space for full preparation. Outputs and logs are under `data/tai/pipeline/` or `data/tai/pipeline_smoke<N>/`; see the component handoffs for individual commands and other paths.

## Interpreting results

The history score describes deviation from a point's prior median, and rules flag selected data-quality patterns. Unscored readings have reasons and must not be treated as normal. The Isolation Forest scores unusual combinations of history-based features; its score is not a probability or a diagnosis. Its held-out comparison uses the same eligible readings and a stated per-plant, per-day review budget. Artificial-fault recovery and overlap are not real-world accuracy; expert review is needed to establish usefulness and operator costs.

## Repository layout

```text
src/pipeline.py              Pipeline driver
src/data_prep/               Download, preparation and reports
src/history_detector/        History detector and artificial-fault evaluation
src/isolation_forest/        Experimental Isolation Forest
tests/                       Automated synthetic-fixture tests
docs/                        Component guides, audits, decisions and handoffs
data/                        Local partner data and outputs (ignored)
idea.md                      Project framing and detailed methodology
requirements.txt             Core Python dependencies
AGENTS.md, .agents/          Agent instructions and team workflow
```

Partner data, derived outputs, fitted models and credentials must stay local and out of Git. Never modify raw data in place. The briefing restricts data to the hackathon and requires deletion afterwards unless the partner agrees otherwise in writing. Work on a named branch and open a pull request into `main`; see [the team workflow](.agents/skills/branch-and-pr/SKILL.md).
A stage is skipped when its output is complete and its script, arguments and upstream
stages are unchanged; these are fingerprinted in `data/tai/pipeline_state.json`. A complete
download or preparation made before the driver existed is adopted as done. Outputs go to
`data/tai/pipeline/` (or `data/tai/pipeline_smoke<N>/`), with one log per stage in `logs/`.
Nothing is deleted: an output that must be redone is renamed `<name>.old-<timestamp>`
first. The download stage needs `AISO_API_KEY` (see `data/.env.example`). All outputs are
private partner-derived data and stay out of Git. Tests: `python3 -B -m unittest discover -s tests -t .`.

## Provisional TAI history detector

`src/history_detector/history_detector.py` implements a history-only rolling median/MAD
detector for six separate exploratory slices: influent volume and activated-sludge oxygen, ammonium, nitrate, suspended solids and temperature.
It has not been validated against real labels or operator review. Read
`docs/history_detector/HANDOFF.md` for selection, setup, commands and limitations.

## Experimental Isolation Forest

`src/isolation_forest/model.py` uses prior-history features to rank eligible readings.
Run a separate forest for each selected slice; it retains the history baseline
and does not use peer comparisons. The model is
experimental; no labelled real-world accuracy is established. See
`docs/isolation_forest/HANDOFF.md` for the method, commands, tests, comparisons and
private artifact handling.
