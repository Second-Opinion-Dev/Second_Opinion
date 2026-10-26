# AISO AI for Water Hackathon

**Status: PRE-HACKATHON PREPARATION**

AI for Water — AISO × University of Amsterdam, **Wednesday, 28 October 2026,
Amsterdam**. Participating challenge organisations: **TAI / Croonwolter&dros**,
**VLE Global**, and **Waterschap Amstel, Gooi en Vecht (AGV)**.

This workspace preserves context and provides a minimal foundation for rapid,
evidence-based analysis on hackathon day. The actual assignment and dataset have
not arrived. No model, synthetic dataset, or application has been implemented.

## Project structure

```text
data/
  raw/              Original supplied files; never modify in place
  processed/        Derived local datasets
notebooks/          Exploratory analysis
src/
  data/             Reusable loading and validation logic
  features/         Feature engineering
  models/           Baselines and justified model implementations
  evaluation/       Splits, metrics, and comparisons
  explainability/   Evidence-based explanations
app/                Future Streamlit demo
artifacts/          Local model artifacts and run configurations
reports/            Local evaluation outputs and figures
tests/              Relevant tests as implementation develops
HACKATHON_CONTEXT.md
DATA_AUDIT.md
DECISIONS.md
AGENTS.md
requirements.txt
.gitignore
```

Empty directories contain `.gitkeep`. Start by reading `HACKATHON_CONTEXT.md`,
`DATA_AUDIT.md`, and `DECISIONS.md`; `AGENTS.md` guides future coding sessions.

## When the materials arrive

1. Place the original dataset, challenge statement, and accompanying documentation
   under `data/raw/`, preserving supplied names and directory structure. Retain
   original archives if extraction is needed. Do not edit raw files in place.
2. Tell Codex which challenge was assigned and where the materials are, for example:
   “The real challenge and dataset are in `data/raw/`. Start Stage 1: inspect all
   files recursively and update `DATA_AUDIT.md` before modelling.”
3. Audit files, columns, relationships, time/location structure, labels, quality,
   and leakage risks. Then frame the operational decision, perform focused EDA,
   and implement/evaluate a credible baseline before choosing improvements.

Follow the full ten-stage workflow in `HACKATHON_CONTEXT.md`. Prioritise MUST HAVE,
SHOULD HAVE, and WOW FEATURE throughout the one-day event.

## Optional local environment setup

The initial requirements list is intentionally small and unpinned. Dependencies
have not been installed or validated as part of scaffolding. When ready, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

After validating the environment, record the Python version and resolved package
versions before experiments. Add exact analysis, training, testing, and app run
commands here when those entry points exist.

## Local data and version control

Work locally; do not upload operational data or send it to external APIs without
explicit authorisation. Do not expose sensitive identifiers. `.gitignore` excludes
data, generated artifacts/reports, environments, caches, and common secret files;
review any notebook or source output before sharing. Ignored files still need
appropriate local backup. Only `.gitkeep` files under the output/data directories
are intended for tracking initially.

Git has not been initialised and no commits have been created.
