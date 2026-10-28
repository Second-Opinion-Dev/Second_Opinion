---
name: frame-problem
description: Stage 2. Turn the company challenge and audited data into an operational decision framing (input, detection, decision, value, evaluation plan).
---

# Stage 2: Frame the problem

Write (concisely, in `data/tai_work/DECISIONS.md`):

INPUT -> PREDICTION / DETECTION -> DECISION -> BUSINESS / ENVIRONMENTAL VALUE

Identify the real end user (operator, analyst, regulator), the action they take, the cost of
false positives vs false negatives, latency constraints (batch vs streaming), and what "good"
means to this organisation. Then decide:

- feasible evaluation given labels (or lack of them), the split strategy and leakage controls;
- what can be claimed honestly without ground truth;
- which context is available and valid at inference time;
- the MUST / SHOULD / WOW scope for one day.

Confirm the framing with the user before exploring.
