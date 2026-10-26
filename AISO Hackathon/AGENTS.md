# Instructions for coding agents

## Before coding

Read these files in order:

1. `HACKATHON_CONTEXT.md`
2. `DATA_AUDIT.md`
3. `DECISIONS.md`
4. `README.md`

Inspect existing files before editing and preserve working behaviour.

## Current boundary

This repository is in PRE-HACKATHON PREPARATION. Until the real challenge and
dataset arrive, maintain only the lightweight scaffold and documentation. Do not
create models, synthetic hackathon data, assumed schemas, or a pretend demo.
When materials arrive, follow the ten-stage workflow in `HACKATHON_CONTEXT.md`,
starting with recursive inspection and an updated audit, not a full solution.

## Rules

- Never invent dataset characteristics; inspect data before modelling.
- Never fabricate performance, confidence, labels, or physical explanations.
- Separate model observations from possible domain interpretations. Correlation
  and feature contributions do not establish causality.
- Prevent temporal and other data leakage. Use appropriate chronological/entity
  splits, train-only preprocessing, and features available at inference time.
- Start with a credible baseline and compare models objectively. State evaluation
  limitations when ground truth is missing.
- Prefer simple, reliable solutions. Complexity must be justified by evidence.
- Keep reusable logic in `src/`, notebooks exploratory, and app logic dependent
  on reusable modules. Use readable functions, clear names, useful type hints,
  and comments for non-obvious reasoning; avoid unnecessary abstraction.
- Preserve reproducibility: seeds where possible, configuration, package versions,
  input provenance, artifacts, evaluation outputs, and exact run commands.
- Never silently remove or alter raw data. Store derived outputs separately.
- Work locally by default. Never upload datasets or send raw dataset contents to
  external APIs without explicit user authorisation. Do not expose sensitive
  identifiers in logs, documentation, screenshots, or committed outputs.
- Keep dependencies minimal and document consequential decisions in `DECISIONS.md`.
- Keep `DATA_AUDIT.md` factual; use TODO for unknowns and distinguish inferred
  meanings from confirmed definitions and units.
- Ask for clarification only when a truly blocking ambiguity cannot be resolved
  by inspecting the files.
- Make focused changes and run relevant checks afterward. Keep the project
  runnable after major implementation steps.
- Separate planned work into MUST HAVE, SHOULD HAVE, and WOW FEATURE. Never
  sacrifice a functioning core for an unfinished differentiator.

For each model or feature ask: “Would this help the water professional make a
better decision?”
