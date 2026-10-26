# Data audit

**Status: awaiting the real challenge and dataset.** This is an unfilled template.
TODO entries are unknowns, not evidence that a property is absent. Add per-file
and per-column rows after recursive inspection; record evidence for conclusions.

## Challenge and provenance

- Selected organisation and exact challenge: TODO
- End user, intended decision, and business/environmental value: TODO
- Received date, source, dataset version, and usage/sharing restrictions: TODO
- Inventory date, inspection commands, and input checksums where useful: TODO

## File inventory and relationships

| Relative path | Format / role | Rows × columns or other dimensions | Encoding / delimiter / sheets | Relationship / join keys |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO |

- Supporting documentation / data dictionary: TODO
- File relationships, join cardinalities, unmatched records: TODO

## Columns — repeat for each file/table

| File/table | Column | Observed dtype | Meaning and evidence | Units and source | Missing count / % | Suspicious values / ranges |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |

## Quality and structure

- Missing-value encodings and patterns: TODO
- Exact duplicate rows and duplicate candidate keys: TODO
- Suspicious values, sentinel codes, physical plausibility, sensor/data issues: TODO
- Identifiers, uniqueness, and sensitive fields: TODO
- Locations, assets, and geographic fields / coordinate reference system if present: TODO
- Changes in schema, instrumentation, or coverage: TODO

## Time structure

- Timestamp columns, formats, timezone, and daylight-saving handling: TODO
- Time range overall and by entity: TODO
- Ordering, duplicate timestamps, gaps, and irregular sampling: TODO
- Observed sampling frequency and variability by entity: TODO
- Observation time versus arrival time / prediction availability: TODO

## Targets and evaluation

- Targets/labels, definitions, provenance, and availability: TODO
- Label reliability, delayed labels, and coverage: TODO
- Anomaly prevalence, denominator, and point/event definition if applicable: TODO
- Feasible evaluation metrics and reference/baseline: TODO
- False-positive/false-negative costs and inference constraints: TODO
- Proposed train/validation/test split and rationale: TODO
- Leakage risks: future information, target proxies, repeated entities,
  overlapping windows, preprocessing, joins, and threshold selection: TODO

## Useful context and features

- Available contextual variables and evidence of relevance: TODO
- Candidate features, derivation, and availability at inference: TODO
- Evidence supporting potential differentiators: TODO
- Data limitations and claims the dataset cannot support: TODO

## Unresolved questions

| Question | Why it matters | Evidence needed / owner | Status |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

## Audit conclusion

- Confirmed findings: TODO
- Next analysis steps: TODO
