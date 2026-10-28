# TAI preparation decisions

## Preserve data and credentials

Download to a new private path, preserve both original and downloaded files, and keep partner records, derived reports and credentials out of Git. Verify hashes and archive integrity without treating a changed hash as proof of corruption.

## Retain uncertainty

Retain all rows and original values and units; record parsing and potential join issues as flags. Do not delete unusual, zero or negative observations or automatically impute, resample, average conflicts or convert units. A digest-based duplicate report identifies candidates, not proof of equality.

## Scope and downstream handoff

Use the final `idea.md` as project context; Oindrilla prepares the data and expert questions, while downstream detection and review-queue work belong to the team. The Influent/Volume filter is exploratory. Do not choose comparable peers or claim historical validation limits apply until supported by TAI. Preserve chronology and fit any downstream preprocessing only on the appropriate training data.

## Incomplete checks

Confirm installation key relationships, produce a complete join-cardinality assessment, obtain semantic definitions, and agree on a modelling slice and any quarantine rules with the team and TAI. See `TAI_HANDOFF.md` for script limitations and execution commands.
