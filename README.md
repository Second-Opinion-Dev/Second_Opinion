# AISO AI for Water Hackathon

Our submission for **AI for Water**, AISO x University of Amsterdam, Wednesday 28 October 2026,
Amsterdam. Challenge organisations: TAI / Croonwolter&dros, VLE Global, Waterschap AGV.
Goal: a technically credible, explainable and demo-able AI solution that water professionals
would want to keep developing.

## Status

**Hackathon data available.** The team is working on the TAI Second Opinion proposal; see
`idea.md`, `docs/data_prep/DATA_AUDIT.md`, and `docs/data_prep/HANDOFF.md` for current evidence and limitations.

| | |
| --- | --- |
| Challenge | Investigate unusual wastewater measurements |
| Organisation | TAI / Z-info |
| Problem statement | Help operators prioritise suspicious measurements for validation |
| Approach | History-based baseline and experimental Isolation Forest; investigation queue proposed; see `idea.md` |
| Results | TBD (recorded numbers only) |
| Demo | TBD |

## Repository layout

```text
src/
  pipeline.py                 Runs the whole pipeline, skipping completed stages
  data_prep/                  Data download, TAI preparation, verification and reports
  history_detector/           History-only detector and synthetic-fault comparison
  isolation_forest/           Experimental Isolation Forest layer
tests/                        Automated checks for every stage and the driver
docs/
  data_prep/                  TAI audit, decisions, handoff, questions and work log
  history_detector/           Detector decisions and handoff
  isolation_forest/           Isolation Forest handoff
data/                         Downloaded partner data and outputs only (ignored by Git)
app/, notebooks/              Demo and exploration, when needed
artifacts/, reports/          Generated outputs (git-ignored)
AGENTS.md                     Instructions for AI coding agents
.agents/                      Agent context, staged skills and templates
requirements.txt              Python dependencies
```

For TAI setup, commands and private output locations, see `docs/data_prep/HANDOFF.md`.

## Working as a team

- One person, one item, one branch: `<name>-<work>` (e.g. `joshua-setup-fixes`).
- Open a PR into `main` when the item is done; a teammate reviews and merges. No direct commits
  to `main`. Details: `.agents/skills/branch-and-pr/SKILL.md`.
- Partner data in `data/` is git-ignored; code, tests and docs live in `src/`, `tests/` and `docs/`.
  Partner rules forbid committing or sharing the data and API key,
  so each teammate downloads their own copy: copy `data/.env.example` to `data/.env`, add the key
  from the briefing, then run `python3 src/data_prep/download.py [agv|tai|vle ...]` (no argument = all).
  Never edit raw files in place, and delete the data
  after the event unless the partner agrees otherwise in writing.
- Log consequential choices in `docs/data_prep/DECISIONS.md` so we don't re-try rejected ideas.

## Working with AI agents

We use coding agents (Claude Code, Codex) to move fast. They follow `AGENTS.md` and the staged
playbooks in `.agents/skills/` (understand data -> frame -> explore -> baseline -> improve ->
differentiate -> build -> demo app -> validate -> pitch).

On the day, put the materials in `data/raw/` and tell your agent:

> Challenge materials are in `data/raw/`. Run `.agents/skills/00-start-here`.

Review each stage's output before approving the next. Agents must not invent data properties,
metrics or causes.

## Setup (WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Work inside the WSL filesystem (`~/`) rather than `/mnt/d` for speed. To make Claude Code
auto-discover the skills: `mkdir -p .claude && ln -s ../.agents/skills .claude/skills`.

## Run the whole pipeline

`src/pipeline.py` runs every stage as a separate process through its existing script:
download → prepare → verify → detector → Isolation Forest, per measurement group, with
the synthetic-fault comparison optional. It skips stages that are already done:

```bash
python3 src/pipeline.py --plan                        # show what would run or be skipped
python3 src/pipeline.py                               # run everything not yet done
python3 src/pipeline.py --smoke 30                    # quick run on 30 points per group
python3 src/pipeline.py --with-faults                 # also run the slow fault comparison
python3 src/pipeline.py --groups oxygen --force detect  # redo detector and forest for oxygen
```

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
