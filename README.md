# AISO AI for Water Hackathon

Our submission for **AI for Water**, AISO x University of Amsterdam, Wednesday 28 October 2026,
Amsterdam. Challenge organisations: TAI / Croonwolter&dros, VLE Global, Waterschap AGV.
Goal: a technically credible, explainable and demo-able AI solution that water professionals
would want to keep developing.

## Status

**Hackathon data available.** The team is working on the TAI Second Opinion proposal; see
`idea.md`, `data/tai_work/DATA_AUDIT.md`, and `data/tai_work/HANDOFF.md` for current evidence and limitations.

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
data/                         Downloaded partner data (ignored by Git)
data/tai_work/scripts/        TAI download, preparation and analysis scripts
data/tai_work/tests/          Focused automated checks
data/tai_work/                TAI audit, decisions, handoff, questions and work log
history_detector/             Provisional history-only anomaly detector, its decisions and handoff
src/                          Other reusable code as the project grows
app/, notebooks/              Demo and exploration, when needed
artifacts/, reports/          Generated outputs (git-ignored)
AGENTS.md                     Instructions for AI coding agents
.agents/                      Agent context, staged skills and templates
requirements.txt              Python dependencies
```

For TAI setup, commands and private output locations, see `data/tai_work/HANDOFF.md`.

## Working as a team

- One person, one item, one branch: `<name>-<work>` (e.g. `joshua-setup-fixes`).
- Open a PR into `main` when the item is done; a teammate reviews and merges. No direct commits
  to `main`. Details: `.agents/skills/branch-and-pr/SKILL.md`.
- Partner data in `data/` is git-ignored; only explicitly listed TAI code and docs are tracked.
  Partner rules forbid committing or sharing the data and API key,
  so each teammate downloads their own copy: copy `data/.env.example` to `data/.env`, add the key
  from the briefing, then run `python3 data/download.py [agv|tai|vle ...]` (no argument = all).
  Never edit raw files in place, and delete the data
  after the event unless the partner agrees otherwise in writing.
- Log consequential choices in `data/tai_work/DECISIONS.md` so we don't re-try rejected ideas.

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

Exact run commands (training, evaluation, app) will be added here as they exist.

## Provisional TAI history detector

`history_detector/history_detector.py` implements a history-only rolling median/MAD
detector for separate exploratory influent-volume, oxygen and ammonium slices.
It has not been validated against real labels or operator review. Read
`history_detector/HANDOFF.md` for selection, setup, commands and limitations.

## Experimental Isolation Forest

`isolation_forest/model.py` uses prior-history features to rank eligible readings.
Run a separate forest for each selected slice; it retains the history baseline
and does not use peer comparisons. The model is
experimental; no labelled real-world accuracy is established. See
`isolation_forest/HANDOFF.md` for the method, commands, tests, comparisons and
private artifact handling.
