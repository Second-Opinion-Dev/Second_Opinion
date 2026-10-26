# Engineering decisions

Record consequential choices and the evidence behind them. Add dated entries;
when revising a decision, reference the earlier entry and explain the new evidence.

## D001 — 2026-10-26 — Prepare only a minimal scaffold

### Context

The event is on 28 October 2026. The actual assignment and datasets are not yet
available; three provisional challenges remain possible.

### Options considered

- Implement a speculative model/demo now.
- Prepare documentation, directories, and lightweight candidate dependencies.

### Decision

Prepare the scaffold only. Defer challenge selection, schemas, features, models,
metrics, and app implementation until inspection of the supplied materials.
Keep local datasets and generated outputs ignored by Git, with `.gitkeep` files
preserving empty directories. Use the seven requested initial packages without
installing them or claiming a validated environment.

### Why

This preserves flexibility and saves hackathon time without anchoring development
to fabricated data or unnecessary architecture.

### Evidence

The user's master project brief explicitly requests pre-hackathon preparation.
Initial inspection found an empty workspace and no existing Git repository.

### Risks / limitations

Dependency versions are not pinned and compatibility has not been tested. Once
the environment is installed and validated, record exact resolved versions and
run commands. Ignored local outputs are not backups. This scaffold does not
contain a working model or application, and Git has not been initialised.

## Template for future entries

### Decision identifier / date / title

TODO

### Context

TODO

### Options considered

TODO

### Decision

TODO

### Why

TODO

### Evidence

TODO — reference audit findings, experiments, metrics, or requirements.

### Risks / limitations

TODO
