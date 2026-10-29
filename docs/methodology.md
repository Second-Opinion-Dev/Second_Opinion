# Methodology

Second Opinion is a history-based validation aid for wastewater measurements. This document covers the problem it addresses, the method it implements, the design decisions behind it and the limits of what it can claim.

## Problem

Wastewater plants report daily measurements, for example into TAI's Z-info platform, and these feed downstream analysis, reporting and decisions. Validation usually relies on predefined limits: a reading outside them triggers a warning, and a reading inside them passes, even when it is highly unusual for that specific measurement point. There are no confirmed anomaly labels, and every investigation costs an operator time.

**Problem statement:** How can we identify suspicious measurements that limit-based checks may miss, explain why they deserve attention, and help operators prioritise their validation within the time available?

A flag is a reason to investigate. It is not proof of a faulty reading, a plant incident or its physical cause, and an unflagged reading is not proof of a safe condition. The operator makes the decisions. Claiming that an existing check *missed* a reading would require the limits that actually applied at the time, plus outcome data.

## Approach

Second Opinion compares each reading with the recent history of the **same measurement point and process context**, and reports how the reading differs from its typical recent value and why it was flagged or could not be scored.

Two design decisions shape everything downstream:

- **No comparison between plants.** Plants differ in geography, process and timing, so a reading is judged only against its own series.
- **One operator per plant.** Review budgets and rankings are always per plant, never one list across all plants.

## 1. Prepare and select inputs

The detector reads the complete output of the preparation stage (`summary.json`, `point_metadata.csv.gz` and `cleaned/MeasurementValues/*.csv.gz`). Preparation preserves raw fields, the source file and row, parsed values and quality flags. The detector requires unique, nonblank point IDs, matching source files and matching point/value units, and it refuses partial preparation output.

Each run selects one exploratory measurement group, all with input type `scada`:

| Group | Product | Quantity | Parameter | Unit | State |
| --- | --- | --- | --- | --- | --- |
| `influent_volume` (default) | Influent | Volume | Niet van toepassing | m3 | Any |
| `oxygen` | Actief slib | (massa)Concentratie | zuurstof | mg/l | niet van toepassing |
| `ammonium` | Actief slib | (massa)Concentratie | ammonium | mg/l | uitgedrukt in Stikstof |
| `nitrate` | Actief slib | (massa)Concentratie | nitraat | mg/l | uitgedrukt in Stikstof |
| `suspended_solids` | Actief slib | (massa)Concentratie | Onopgeloste bestandsdelen | g/l | niet van toepassing |
| `temperature` | Actief slib | Temperatuur | Niet van toepassing | oC | niet van toepassing |

These are exact metadata combinations, deliberately narrower than every point of that kind. They are not expert-approved measurement definitions. What each reading represents, its reporting period and its operational comparability still need confirmation from the data provider.

## 2. Keep each history separate

Records are grouped by origin installation, measurement point, origin subprocess, process, product, product balance, destination installation, destination subprocess and unit. Each group forms its own history, and readings from other points, contexts or plants never enter it. Records are sorted by date before scoring.

## 3. Baseline and score

For a reading on day `t`:

1. Select eligible observations from **`[t − 28 days, t)`**: the preceding 28 calendar days, excluding the current day. Require at least **14 valid days**.
2. Calculate their **median**.
3. Calculate the **MAD** (median absolute deviation from that median) and the spread `max(1.4826 × MAD, 5% of |median|)`. The floor stops tiny changes on small or quiet meters from producing extreme scores.
4. Calculate the score and its direction (above or below):

   ```text
   score = |value − historical median| / spread
   ```

5. Flag scores at or above a **calibrated threshold**. Thresholds are chosen separately for each series and for each direction, using that series' own data up to the end of 2023, so that about 1% of its readings would be flagged. Thresholds are never below 2.0. Series with too little calibration data use the median threshold of the other series. The 1% is an assumed workload, not a probability, a measured risk or an operating limit.

The window uses only prior records, so the current reading and future readings never enter their own baseline. Valid readings enter later windows clipped to `median ± 3.5 × spread`. A sustained fault therefore does not quickly become the new normal, although a genuine permanent change is also accepted more slowly.

Heavy-tailed series, such as influent during wet weather, get a higher upward threshold than downward one, and an erratic meter never sets the bar for a calm one. Calibrating per series was a deliberate choice: a single pooled threshold per group let the most erratic meters push the bar so high that the calm meters were barely ever flagged.

## 4. Data-quality rules

Simple rules run alongside the score and are independent of the threshold:

| Rule | Fires when |
| --- | --- |
| `stuck` | The same value repeats on 7 or more consecutive days after a history that varied. A meter that is constantly zero is not "stuck". |
| `dropout` | A zero follows a full window without zeros. |
| `negative` | A volume or concentration is negative. This rule is not applied to temperature. |

A reading is marked for review when the score or a rule fires. Rules can apply even when the statistical score is unavailable.

## 5. Cases and ranking

Flagged days of one series form one **case** when they are separated by at most one unflagged day. Cases are ranked within each plant: rule hits first, then longer cases, then higher peak score. This is a documented review order, not a probability or a severity.

## 6. Uncertainty and provenance

A record is **unscored**, with a reason, when:

- its date or value is invalid, or its preparation flags require review;
- the same series has more than one valid row on that calendar day;
- there is not enough valid history;
- or the history is constantly zero.

Same-day duplicates and other ineligible records are also kept out of later history, while the source records remain intact. The detector never silently averages conflicting records, fills missing values or converts units. Zero and negative values are not treated as invalid; the rules only mark them for review.

The output keeps the original date, value and unit; the installation, point and process context; the source file and row; quality flags; the history count, median, MAD and spread; the score and direction; rule columns; statistical and review flags; reasons; status; explanation; and the case ID. A separate table holds the cases. A blank flag means **unscored**, not normal.

## 7. Experimental AI layer

The Isolation Forest ranks eligible readings using six features, each built only from the same series' current and earlier observations:

1. signed deviation from the prior median, in spreads;
2. one-day change, in spreads;
3. mean prior deviation over the previous seven days;
4. level relative to the median;
5. whether the value is exactly zero;
6. how many consecutive days the value has repeated.

No feature depends on the detector's alert threshold, and raw identifiers are never model features. Features 1, 2 and 4 use a signed `log1p` transform to compress extreme values. Readings with missing, ambiguous or unsuitable history stay unscored rather than being filled with normal-looking values.

One forest is trained per measurement group. Training runs through 2023 with a fixed seed; the provisional threshold is the 99th percentile of 2024 validation scores; 2025 is held out. A higher score means a rarer combination of features, not a fault probability. Scores from separately fitted forests are not on a common scale.

A retrospective comparison ranks the same eligible readings with each method under an example budget of **one reading per plant per day**, separately for each group. Counts and overlap describe the two methods; they do not show which is more useful. Keep the forest only if comparable evidence shows that it adds value over the simpler detector.

## 8. Artificial-fault evaluation

`src/history_detector/synthetic_faults.py` copies a seeded sample of series and writes one artificial fault into each copy during the held-out year: a one-day spike, a three-day dropout to zero, a ten-day stuck value, or a 28-day drift. Each copy is scored with the original fixed-threshold settings and with the current defaults, using thresholds frozen on unmodified data. The script also reports the review workload on unmodified data.

This measures recovery of artificial faults and nothing more. The target flag rate is a trade-off between workload and sensitivity: lower rates catch stuck sensors and dropouts at a fraction of the workload, but can miss moderate spikes and drifts on meters that vary a lot naturally. Operators should set that trade-off.

## Limitations

- **No labels.** Without confirmed incidents or expert review, there is no measured precision, recall, false-alarm rate or time saving.
- **Retrospective, day-level data.** Daily dates do not prove when a value was available to an operator. The detector is not a live or intraday alert system.
- **Unconfirmed semantics.** Measurement meanings, units, reporting periods and the installation join need confirmation from the data provider.
- **Assumed settings.** The 1% target, 5% floor, 3.5 clip limit and 7 stuck days are configurable assumptions to review with operators.

## Next steps

1. Confirm measurement semantics, units, duplicate handling and data availability with the data provider.
2. Ask domain experts to review a documented sample of flagged, deferred and unflagged cases (useful / not useful / unsure) and measure review time.
3. Compare against the validation limits that actually applied, if they and their history can be obtained.
4. Add persistent operator feedback and a grouped case view to the dashboard.
5. Optionally, study dry versus wet periods with suitable local weather data, treating any association as descriptive rather than causal.
