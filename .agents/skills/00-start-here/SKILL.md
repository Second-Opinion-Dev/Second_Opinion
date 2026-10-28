---
name: start-here
description: Entry point on hackathon day. Use when the user provides the challenge statement and/or dataset and wants analysis to begin. Orients the agent, sets up working docs, and routes through the staged skills.
---

# Start here

1. Read `.agents/context/hackathon.md` and `.agents/context/principles.md`.
2. Locate the materials (default `data/raw/`). List every file recursively with sizes. Treat
   raw files as read-only. If the challenge statement is a document, read it fully.
3. Read the existing `data/tai_work/DATA_AUDIT.md` and `data/tai_work/DECISIONS.md`,
   or create them from `.agents/templates/` if they do not exist.
4. Set up the environment only if needed (WSL: `python3 -m venv .venv && source .venv/bin/activate`
   then `pip install -r requirements.txt`). Record versions in `data/tai_work/DECISIONS.md`.
5. Run the skills in order, **pausing after each for the user's go-ahead**:
   `01-understand-data` -> `02-frame-problem` -> `03-explore` -> `04-baseline` ->
   `05-improve` -> `06-differentiate` -> `07-build` -> `08-demo-app` -> `09-validate` -> `10-pitch`.
6. Do NOT jump to a full solution. Keep a running MUST / SHOULD / WOW list and the clock in mind
   (one day): working baseline early, app skeleton by midday, pitch prep reserved at the end.

Output: a short message stating which challenge this is, what files exist, and the proposed plan.
