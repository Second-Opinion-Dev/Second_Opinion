---
name: explore
description: Stage 3. Focused exploratory analysis tied to the challenge question; avoids chart dumps.
---

# Stage 3: Focused EDA

Only investigate what bears on the framed decision. Typical questions: how does normal behave
over time, season and operating state? how strong is context dependence (weather, flow, tide,
neighbours)? are anomalies/events visible, what do they look like, how long do they last?
which sensors are redundant, faulty or flatlined? what are the spatial/temporal coverage gaps?

Rules: a handful of informative plots, each answering a stated question; note findings and their
implications in `DECISIONS.md` / `DATA_AUDIT.md`; flag anything that changes the framing.
Notebooks are fine for exploration, but move reusable code into modules.
