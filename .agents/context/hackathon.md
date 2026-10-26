# Hackathon context

**AI for Water**: AISO x University of Amsterdam, Wednesday 28 October 2026, Amsterdam.
One day. EUR 3,000 prize pool. Judged on technical quality, novelty, real business /
environmental usefulness, explainability, feasibility, reliability, demo impact and
clarity of pitch. We want what the water professionals would most want to keep developing,
not the most complicated model.

## Status of information

The challenge, data and questions are **not known yet**. Titles below are provisional and
unverified; they hint at domains, not dataset properties. Never assume columns, units,
locations, labels or regulatory classes. Inspect first.

| Organisation | Provisional title | Possible core question |
| --- | --- | --- |
| TAI / Croonwolter&dros | Spotting anomalies in wastewater treatment data (Z-info) | Detect abnormal plant behaviour early without drowning operators in alarms? |
| VLE Global | Anomaly detection on a simulated live feed of port and coastal water data (Aveiro) | Detect unusual multivariate behaviour in real time and turn it into understandable events? |
| Waterschap AGV | Water quality monitoring for the Water Framework Directive (KRW) | Make limited measurements more informative and show where attention or extra monitoring is needed? |

## Target shape of a solution

Most teams will produce DATA -> MODEL -> SCORE. We aim for, as far as the data allows:

DATA -> CONTEXT -> ANOMALY / RISK -> EXPLANATION -> EVENT -> DECISION -> ACTION

Answer where supported: what happened, when it started, where, how severe, which variables
contributed, whether it is abnormal *given context*, process/environmental event vs
sensor/data issue, why it was flagged, what deserves attention, what to investigate next.

## Differentiator hypotheses (test against the data, don't presuppose)

- **TAI-like:** context-aware detection; contribution ranking; event-level alarms;
  false-alarm reduction (persistence, hysteresis, correlated sensors); peer/asset comparison.
- **VLE-like:** event fingerprinting from multivariate signatures; sensor fault vs
  environmental event; adaptive normality; streaming replay demo.
- **AGV-like:** spatiotemporal modelling; risk + uncertainty; next-best-sample
  recommendation (priority ~ risk x uncertainty x information value; needs defensible definitions).

## Demo target

A judge should grasp the value in 30 seconds. Likely stack: Python, pandas, NumPy,
scikit-learn, SciPy, Plotly, Streamlit, joblib. Optional if justified: statsmodels,
XGBoost/LightGBM, SHAP. Keep dependencies minimal.
