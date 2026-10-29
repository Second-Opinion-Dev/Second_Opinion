# Agent instructions

Guidance for coding agents (Claude Code, Codex and others) working in this repository. Paths are relative to the repository root.

## Orientation

- Start with `README.md`, then `docs/methodology.md` and the component guide for the area you are changing (`docs/data_prep/`, `docs/history_detector/`, `docs/isolation_forest/`, `dashboard/README.md`).
- Code lives in `src/`, tests in `tests/` (dashboard tests in `dashboard/`), documentation in `docs/`. `data/` holds local data and outputs only and is git-ignored.
- `site/` is the public website. Its documentation pages are generated from the markdown guides by `site/build.py`, so edit the markdown, not generated HTML. See `site/README.md`.

## Rules

1. Never commit measurement data, prepared files, scores, fitted models, reports or credentials. Do not upload data or send raw contents to external services.
2. Preserve raw data and provenance: never modify inputs in place, and never silently drop, impute, average or convert records.
3. Never fabricate data properties, labels, metrics, operating limits or physical causes. A flag is an investigation prompt, not a diagnosis, and unscored never means normal.
4. Keep histories per series and rankings per plant; do not introduce cross-plant comparisons without an explicit decision.
5. Do not claim accuracy, false-alarm reduction or time savings without labelled or expert-reviewed evidence.
6. Tests use small artificial fixtures, never real measurements.

## Commands

```bash
python src/pipeline.py --plan
python -B -m unittest discover -s tests -t . -v
python -B -m unittest discover -s dashboard -p "test_*.py" -v
node --test dashboard/test_assistant_ui.cjs
```

## Git

Work on a branch and open a pull request into `main`; never commit directly to `main`.
