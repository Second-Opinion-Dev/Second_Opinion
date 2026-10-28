# Agent instructions: AISO AI for Water Hackathon

## TAI data work — 28 October 2026

See `docs/data_prep/WORK_LOG.md`, `docs/data_prep/HANDOFF.md`, and `docs/data_prep/QUESTIONS.md` for TAI preparation, run commands, decisions, open questions, and incomplete checks. Keep the API key, partner data, and private reports out of Git. Preserve raw data.

Read by Codex, Claude Code and other coding agents. Paths are relative to the repo root.

## Status

**Hackathon data available.** The team has received TAI data and the challenge; see
`idea.md` and `docs/data_prep/DATA_AUDIT.md`. Inspect actual materials before implementing, and do
not invent schemas, labels, results or a pretend demo.

## Where things are

- `.agents/context/`: what the event is and the principles we work by. Read first.
- `.agents/skills/`: step-by-step playbooks, one per stage. Follow them in order.
  Start with `.agents/skills/00-start-here/SKILL.md`.
- `.agents/templates/`: templates for the working docs you create on the day.

## Git

Work on a branch named `<name>-<work>` and open a PR into `main` when done. Follow
`.agents/skills/branch-and-pr/SKILL.md`. Never commit directly to `main`.

## Always

1. Read `.agents/context/hackathon.md` and `.agents/context/principles.md`.
2. If `docs/data_prep/DATA_AUDIT.md` / `docs/data_prep/DECISIONS.md` exist, read them before acting. If not,
   create them from `.agents/templates/`.
3. Follow the relevant skill for the current stage; don't skip ahead to modelling.
4. Never fabricate data properties, metrics, labels or physical causes.
5. Partner datasets, derived outputs and the API key are git-ignored. Code in `src/`, tests in
   `tests/` and documentation in `docs/` are tracked; `data/` holds data only.
   Never commit partner data or keys. Work locally: never upload data or send raw contents to external
   services without explicit user authorisation.

## Environment

The current workspace uses Windows PowerShell and Python; `docs/data_prep/HANDOFF.md` records
the commands used here. WSL can also be used with appropriate paths and `python3`.
