# Hackathon context

**AI for Water**: AISO x University of Amsterdam, Wednesday 28 October 2026.
Source: the official participant briefing (added 27 Oct 2026). One day, EUR 3,000 prize
pool. We want what the water professionals would most want to keep developing, not the
most complicated model.

## Logistics

- **Where:** REC Impact, The Floor, Valckenierstraat 65, 1018 WV Amsterdam. Stay until 19:00.
- **Discord:** https://discord.com/invite/dRcNFewzBb (#announcements, #questions, #team-formation).
- **Wi-Fi:** can be slow, so download the data the night before. Students use eduroam;
  others scan the Wi-Fi QR code in the building.
- **Teams:** 3 to 5 people, one challenge. By **10:30** give the crew team name, members
  and challenge. No team yet? The crew helps until 10:30.
- **Crew:** Jan, Filip, Marko. On-site challenge experts: Jim Odenhoven (AGV);
  Alexander Proost and Mark Beijer (TAI).
- **Photos:** UvA photographer from 11:30. Opt out at check-in.

## Programme

| Time | What |
| --- | --- |
| 09:00 | Doors open, check in with the QR code on the screen |
| 09:30 | Kickoff and challenge introductions (VLE briefing video shown here) |
| 10:00 | Building starts |
| 12:30 | Lunch |
| Afternoon | Jury visits every team |
| 16:00-17:00 | UvA Executive Board and NWO Board visit; keep working |
| **17:00** | **Submission deadline**, then dinner |
| 17:45-18:30 | Finalist pitches (announced ~17:35) |
| 18:50 | Winners and photos |
| 19:00 | Close |

## Challenges

| Partner | Challenge | Notes |
| --- | --- | --- |
| Waterschap AGV (Amstel, Gooi en Vecht) | Water quality monitoring and interpretation for the Water Framework Directive (KRW), using chemistry and hydrobiology data from the Amstel area | Start with `agv/Parameter_uitleg.xlsx` |
| TAI / Z-info | Detect and flag unusual measurements at wastewater treatment plants | **No anomaly labels.** Show why flags are useful and what a false alarm costs an operator |
| VLE Global | Water quality monitoring and real-time anomaly detection in port and coastal waters (Aveiro node SP-02, simulated feed) | Live API, no key |

Never assume columns, units, locations, labels or regulatory classes beyond what is stated
here. Inspect first.

## Data access

Full details of file layout and quirks are in the briefing; the essentials:

- **VLE Global:** `https://sp02.aveiro.vle.global/`, endpoints `/api/latest` and
  `/api/history`. No key needed.
- **AGV and TAI:** `https://aiso-water-data.vercel.app`, header `X-API-Key`. The key is
  **not stored in this repo**; keep it in the git-ignored `.env`. It expires **00:00 on 29/10**.
  - `GET /files` lists every file. `GET /files/<path>` returns a download link valid 15 minutes.
  - **TAI** (`tai/`): Installations, MeasurementPoints, MeasurementValues (daily values per
    installation). Everything at once: `tai/tai_all.tar` (150 MB). Read CSVs with
    `encoding_errors="replace"`.
  - **AGV** (`agv/`): `Parameter_uitleg.xlsx` explains the parameters. `waterkwaliteit/` has
    chemistry (FYCHEM, `;`-separated) and hydrobiology (HB, `,`-separated).
    `waterkwantiteit/` has water levels, flows and pumping stations (`;`-separated); the
    10-minute polder flows come in four parts, each with its own header.

## Data rules

Partner data is for the hackathon only. Do not share or publish it, do not commit data or
the key to any repository, and **delete the data afterwards** unless the partner agrees in
writing.

## Claude API credits

Every participant gets $25 of Anthropic API credits (redeem via the link in the briefing).
Pool them as a team; use Sonnet or Haiku by default.

## Submission

One per team by **17:00** via the Typeform: https://form.typeform.com/to/v3larw4T. Cover:
which challenge and problem, how the solution works, what was built today, how it was
checked, and its limits. Links must open without a login.

## Judging and prizes

Jury picks 7 to 8 finalists from visits and submissions. Finalists pitch for at most
**5 minutes including questions**.

Criteria, **25% each**: problem fit, technical quality, impact, feasibility.

Mention the tools, data and AI used and any work prepared before today. Prizes: EUR 1,500 /
900 / 600 for the top three, split equally within the team. Strong teams may be invited to
the UvA Impact Challenge and Founder Space. Teams own what they build; partners may review
submissions and contact teams.

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

A judge should grasp the value in 30 seconds (pitch is 5 minutes with questions). Likely
stack: Python, pandas, NumPy, scikit-learn, SciPy, Plotly, Streamlit, joblib. Optional if
justified: statsmodels, XGBoost/LightGBM, SHAP. Keep dependencies minimal.
