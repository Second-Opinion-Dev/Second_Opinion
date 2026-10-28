# Questions for TAI experts

All questions remain open unless an expert's answer is recorded with its source.

## Essential for selecting a measurement

1. What do Product, Quantity, Parameter, InputType and State mean in these exports? Which points represent incoming flow, and are these directly measured or derived?
2. What do m3, m3/p, m3/h, ml and l mean in context, including the period or denominator? Which conversions, if any, are valid?
3. How do installation codes, measurement points and process/subprocess fields relate? Which identifiers are stable and unique?
4. Is Date the observation date, reporting period, or another timestamp? What is the timezone, and when would each observation actually have been available to an operator?
5. Which plants and points are comparable in measurement method, process role and expression basis? What other metadata is needed before treating them as peers?
6. How are missing, blank, zero, negative and default-like values encoded? Are repeated readings normal for any measurement types?
7. What do duplicate or conflicting same-point, same-date records mean? Can they be corrected, or must all records be retained?

## Essential for the operator handoff

8. Which unusual measurements are worth investigating, and what checks do operators perform? How long does a typical review take?
9. Can you review a small sample of flagged, deferred and unflagged historical cases? What would make a case useful or not useful?
10. Are there changes in instrumentation, calibration, processes or reporting over time that affect comparisons?
11. Are the existing validation limits, their historical versions and actual validation outcomes available for these readings? How should we establish whether a limit applied at the time?

## Follow-up

12. Are there confirmed labels, known incidents or permitted supplementary metadata? What usage and retention restrictions apply to derived data?
13. What time coverage and history would make a point usable in practice? How should missing peer readings affect the display?
