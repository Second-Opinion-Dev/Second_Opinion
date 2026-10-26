# AISO AI for Water Hackathon — project context

## Current state

**PRE-HACKATHON PREPARATION — 26 October 2026.** The actual assignment and
datasets have not arrived. No challenge has been selected. No data schema,
labels, model, evaluation results, or application exist yet. Update this status
when the real materials arrive.

## Event and objective

AI for Water — AISO × University of Amsterdam takes place on **Wednesday,
28 October 2026 in Amsterdam**, with a €3,000 prize pool. This is a one-day
hackathon. Event details and provisional titles below come from the organiser
context supplied by the user; they have not been independently verified.

Balance technical quality, novelty, business/environmental usefulness,
explainability, feasibility, reliability, demo impact, and a clear pitch.
Build something water professionals and judges would want to continue developing.
The most complicated model is not the goal.

## Provisional challenges

| Organisation | Provisional title | Potential question to validate |
| --- | --- | --- |
| TAI / Croonwolter&dros | Spotting anomalies in wastewater treatment data — Z-info | Can abnormal process behaviour be detected early without overwhelming operators with alarms? |
| VLE Global | Anomaly detection on a simulated live feed of port and coastal water data — Aveiro | Can unusual multivariate behaviour become understandable environmental events? |
| Waterschap Amstel, Gooi en Vecht — AGV | Water quality monitoring for the Water Framework Directive — KRW | Can limited measurements reveal where attention or additional monitoring is useful? |

These titles suggest domains, not known dataset properties. Wastewater telemetry,
coastal measurements, ecological/chemical samples, timestamps, assets, locations,
coordinates, contextual signals, and labels are all unconfirmed. Never assume
particular columns, units, regulatory classes, or geographic information.

## Product and modelling principles

Aim for **data → context → anomaly/risk → explanation → event → operational
decision → action**, as far as the actual evidence permits.

Ask what happened, when it started, where it occurred, how severe it is, which
variables contributed, whether context makes it unexpected, whether a sensor/data
issue is plausible, why it was flagged, who should review it, and what to
investigate next. Do not force answers that the data cannot support.

An unusual value is not automatically an anomaly. Prefer unexpected behaviour
given available context: time, season, history, operating state, other signals,
peers, weather, flow, or tides only where actually available and valid at inference.
Separate **MODEL OBSERVATION** from **POSSIBLE DOMAIN INTERPRETATION**. Feature
contributions are not proof of physical root cause. Never fabricate causes,
confidence, regulatory conclusions, or performance.

Choose models after inspection. Begin with a credible baseline; consider robust
statistics, rolling scores, decomposition, forecasting residuals, anomaly
detectors, PCA, change points, clustering, trees/boosting, or probabilistic/spatial
methods only when justified. Neural networks, autoencoders, LSTMs, Transformers,
and graph models require evidence that their complexity is worthwhile.

## Candidate differentiators — hypotheses only

- **TAI:** contextual detection, contribution ranking, event aggregation,
  persistence/hysteresis to reduce alarms, or comparable-asset analysis.
- **VLE:** interpretable multivariate event patterns, sensor-fault versus
  environmental-event evidence, adaptive normality, or historical streaming replay.
  A correlated signal pattern alone does not establish an environmental cause.
- **AGV:** spatiotemporal analysis, risk with uncertainty, or next-best-sample
  recommendations. A conceptual priority combining risk, uncertainty, and
  information value needs defensible definitions and data before implementation.

## Evaluation and reproducibility

Determine feasible evaluation from labels and the task. Classification may use
precision/recall, F1, PR-AUC, ROC-AUC, and confusion matrices; emphasise PR-AUC,
recall at acceptable false-positive rates, and event metrics for rare anomalies.
Regression/forecasting may use MAE, RMSE, meaningful R², and residual analysis.
Operational measures may include raw flagged points, consolidated events,
alert reduction, detection delay, and validated false-alarm reduction. Fewer
alerts alone do not prove fewer false alarms. Without ground truth, explicitly
limit claims; do not invent accuracy or labels.

Use appropriate chronological and entity-aware splits. Fit preprocessing and
thresholds on training/validation data, keep evaluation held out, and avoid future
information in features or streaming replay. Record seeds, configuration, package
versions, input provenance, model artifacts, evaluation outputs, and exact commands.
Raw files stay unchanged. Work locally; never upload data or send raw contents to
external APIs without explicit authorisation. Protect sensitive identifiers.

## Demo direction — deferred until the data is understood

A judge should understand the value in 30 seconds. Python, pandas, NumPy,
scikit-learn, SciPy, Plotly, Streamlit, and joblib are the initial candidate stack.
Add statsmodels, XGBoost/LightGBM, SHAP, or other packages only when justified.

A later app might offer overview, focused exploration, events, explanations, and
methodology/evaluation. Include a map only if suitable geographic data exists.
An event may include time span, severity, affected variables, contribution ranking,
observed versus expected behaviour, defensible uncertainty, a clearly qualified
interpretation, and a recommended investigation. None of these are built yet.

## Hackathon-day sequence

1. **Understand:** inspect all supplied files recursively, explain important columns
   and relationships, targets/labels, time/location structure, and quality issues;
   update `DATA_AUDIT.md`.
2. **Frame:** express input → prediction/detection → decision → value. Identify the
   end user, desired action, false-positive/false-negative costs, and inference constraints.
3. **Explore:** focused EDA tied to the challenge, not a catalogue of charts.
4. **Baseline:** implement and evaluate the simplest credible approach.
5. **Improve:** test contextual features and stronger models; compare objectively.
6. **Differentiate:** propose THREE ideas and score business value, novelty,
   feasibility, dataset evidence, demo impact, and implementation risk; recommend one.
7. **Build:** implement incrementally and keep the project runnable.
8. **Productise:** build the Streamlit demo on reusable modules.
9. **Validate:** edge cases, missing values, reproducibility, app execution, model
   loading, and evaluation consistency.
10. **Pitch:** one-line value proposition, problem, dataset insight, approach,
    differentiator, results, live demo flow, limitations, and deployment/future work.

Always prioritise **MUST HAVE**, **SHOULD HAVE**, and **WOW FEATURE**. Protect the
working core from unfinished ambitious features. Keep functions/modules readable,
notebooks exploratory, and architecture minimal. Record consequential choices in
`DECISIONS.md`.

For every feature ask: **Would this help the water professional make a better
decision?** The final prototype should be technically credible, interpretable,
operational, evidence-based, meaningfully novel, polished, and honest.
