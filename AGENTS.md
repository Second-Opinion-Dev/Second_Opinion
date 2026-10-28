# Agent instructions: AISO AI for Water Hackathon

## TAI data work — 28 October 2026

See `TAI_WORK_LOG.md`, `TAI_HANDOFF.md`, and `TAI_QUESTIONS.md` for the current TAI preparation, run commands, decisions, open questions, and incomplete checks. Work on `oindrilla-tai-data-cleaning`, based on fetched main commit `b9151e8`. Keep the API key, partner data, and private reports out of Git. Preserve the user's existing checkout and raw data.

Read by Codex, Claude Code and other coding agents. Everything lives at the repo root.

## Status

**Hackathon data available.** The team has received TAI data and the challenge; see
`idea.md` and `DATA_AUDIT.md`. Inspect actual materials before implementing, and do
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
2. If `DATA_AUDIT.md` / `DECISIONS.md` exist at the root, read them before acting. If not,
   create them from `.agents/templates/`.
3. Follow the relevant skill for the current stage; don't skip ahead to modelling.
4. Never fabricate data properties, metrics, labels or physical causes.
5. `data/` is git-ignored: partner rules forbid committing or sharing the data and the API key.
   Never commit them. Work locally: never upload data or send raw contents to external
   services without explicit user authorisation.

## Environment

The current workspace uses Windows PowerShell and Python; `TAI_HANDOFF.md` records
the commands used here. WSL can also be used with appropriate paths and `python3`.
