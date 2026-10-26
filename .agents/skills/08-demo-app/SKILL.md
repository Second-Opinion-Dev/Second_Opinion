---
name: demo-app
description: Stage 8. Build the Streamlit demo on top of reusable modules so a judge grasps the value in 30 seconds.
---

# Stage 8: Demo app

`app/` (Streamlit + Plotly) imports the modules from Stage 7; no model logic lives in the app.
Design for a 30-second read: summary and highest-priority events first. Suggested views, only
those the data supports: Overview, Data explorer, Events (timeline, severity, filters),
Explanation (observed vs expected, contributors), Map (only with real geographic data),
Method and evaluation (baseline comparison, honest limitations).

For streaming challenges include a replay mode that feeds records in order with no future leakage.
Load saved artifacts rather than retraining at launch. Run with `streamlit run app/main.py`
(in WSL, add `--server.address 0.0.0.0` if the Windows browser cannot connect).
Plan a scripted demo path of about two minutes.
