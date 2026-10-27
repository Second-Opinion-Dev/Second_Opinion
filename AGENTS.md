# Agent instructions: AISO AI for Water Hackathon

Read by Codex, Claude Code and other coding agents. Everything lives at the repo root.

## Status

**Pre-hackathon.** The challenge, data and questions are unknown until 28 Oct 2026.
Do not create models, synthetic data, assumed schemas or a pretend demo. Do not create
project folders (`data/`, `src/`, `app/` ...) until the real materials arrive.

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

The user works in **WSL (Linux shell)**. Use POSIX paths and `python3`; create a venv
with `python3 -m venv .venv && source .venv/bin/activate`. Prefer running from the
Linux filesystem (e.g. `~/aiso_hackathon`); `/mnt/d/...` is slow for many small files.
