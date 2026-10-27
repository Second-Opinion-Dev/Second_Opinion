# AISO AI for Water Hackathon

Our submission for **AI for Water**, AISO x University of Amsterdam, Wednesday 28 October 2026,
Amsterdam. Challenge organisations: TAI / Croonwolter&dros, VLE Global, Waterschap AGV.
Goal: a technically credible, explainable and demo-able AI solution that water professionals
would want to keep developing.

## Status

**Pre-hackathon.** The challenge, data and questions arrive on the day. Fill this section in
once they do.

| | |
| --- | --- |
| Challenge | TBD |
| Organisation | TBD |
| Problem statement | TBD |
| Approach | TBD |
| Results | TBD (recorded numbers only) |
| Demo | TBD |

## Repository layout

```text
data/                Supplied challenge materials and data (raw/ is never edited in place)
src/                 Reusable code: data, features, models, evaluation, explainability
app/                 Streamlit demo
notebooks/           Exploration only
artifacts/, reports/ Generated outputs (git-ignored)
DATA_AUDIT.md        What the data is and its quality
DECISIONS.md         What we tried and chose, and why
AGENTS.md            Instructions for AI coding agents
.agents/             Agent context, staged skills and templates
requirements.txt     Python dependencies
```

Only `AGENTS.md`, `.agents/` and `requirements.txt` exist now. The other folders and docs are
created as we need them.

## Working as a team

- One person, one item, one branch: `<name>-<work>` (e.g. `joshua-setup-fixes`).
- Open a PR into `main` when the item is done; a teammate reviews and merges. No direct commits
  to `main`. Details: `.agents/skills/branch-and-pr/SKILL.md`.
- `data/` is git-ignored: partner rules forbid committing or sharing the data (and the API key),
  so each teammate downloads their own copy: copy `data/.env.example` to `data/.env`, add the key
  from the briefing, then run `python3 data/download.py [agv|tai|vle ...]` (no argument = all).
  Never edit raw files in place, and delete the data
  after the event unless the partner agrees otherwise in writing.
- Log consequential choices in `DECISIONS.md` so we don't re-try rejected ideas.

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
