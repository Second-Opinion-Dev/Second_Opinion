# Simulated dataset

The TAI export is operational data and cannot be shared. `src/simulation/simulate_tai.py` builds a **fully simulated** export with the same three-table schema, so the pipeline, detectors and dashboard can be developed, demonstrated and tested without it. It also injects anomalies and data-quality faults on purpose and records exactly where, which the real data cannot offer.

Nothing in the output is a real measurement, plant, installation or measurement point. The schema and the metadata fields the detectors filter on come from this repository's code. Identifier, date and number formats were matched by looking at masked column shapes (letters and digits replaced) of the real export, never at its values. Simulated plants use the reserved country prefix `ZZ` (for example `ZZ.03.KQF`), so they cannot be mistaken for real installations.

## Run

From the repository root, with a new or empty output directory:

```bash
python src/simulation/simulate_tai.py --workers 14
```

The default build has 335 plants, about 25 million measurement rows, 1,826 days (2021-01-01 to 2025-12-31) and takes roughly three minutes on 14 workers. The result is deterministic for a given seed and numpy version, regardless of the number of workers. Use `--plants`, `--target-rows`, `--start` and `--end` for smaller builds, `--seed` for a different draw, `--anomaly-rate` and `--quality-scale` to change how much is injected. The default output is `data/tai`, where the pipeline and the dashboard already look, so neither needs configuring. The script refuses a non-empty output directory: move any real export out of `data/tai` first.

`data/` is git-ignored, so the generated files stay local like every other output. The generator is small and deterministic, which makes it the thing to share.

## Outputs

```text
<output>/
├── extracted/                  Same layout the preparation stage reads
│   ├── Installations/          one file per installation (412)
│   ├── MeasurementPoints/      one file per plant (335)
│   └── MeasurementValues/      one file per plant (335)
├── ground_truth/               Answer key; not part of the export
│   ├── episodes.csv.gz         one row per injected value-anomaly episode
│   └── row_labels/<plant>.csv.gz   one row per anomalous or faulty line
└── manifest.json               Parameters, counts and shares
```

Generated into `data/tai`, the tables sit where the pipeline expects them. The three tables follow the real export: gzipped CSV, every field quoted, the same columns in the same order, `Date` as `YYYY-MM-DD` and `Value` as a plain decimal string. A reading belongs to the file of its plant, and a point's metadata file and value file share a name, as the detector requires.

What is simulated, per plant:

- **Points.** A plant has the six exploratory measurement groups (influent volume, and activated-sludge oxygen, ammonium, nitrate, suspended solids and temperature) with the metadata the detector filters on, plus about 35 other point types: effluent and influent chemistry, sludge flows, dosing, energy, biogas, rainfall and more. Near-misses of the six groups exist on purpose (manual oxygen, ammonium expressed as NH4, suspended solids in mg/l, hourly influent volume) so the exact metadata filters have something to reject.
- **Series.** Daily values with a per-point level, an annual cycle, autocorrelated noise, a weekend effect where relevant and a response to a shared, rain-driven wetness signal (flow rises and concentrations dilute in wet weather). Plant size scales flows and loads.
- **Coverage.** Some points start late, some end early, and every point has gaps, so row counts differ per series.
- **Edge cases of the real export.** Two plants have no value rows. About 4% of plants are written in a legacy single-byte encoding, so their accented descriptions decode with replacement characters. Some points name another plant as destination.

## Injected anomalies

Every series keeps its first 50 reporting days clean so a history exists. A fifth of the series are left entirely clean and the rest receive episodes until about 10.5% of their rows are covered, so anomalous series differ in how much they carry. Episodes never overlap, and magnitudes are in units of the series' own spread around its 28-day running median, so a "spread" here is comparable to what the history detector measures.

| Type | What is written | Rows | Share |
| --- | --- | ---: | ---: |
| `spike` | 1–2 days shifted by 4–14 spreads, up or down | 248,749 | 1.00% |
| `level_shift` | 6–45 days offset by 3–8 spreads | 656,341 | 2.63% |
| `drift` | 15–60 days ramping to 4–10 spreads, then back | 499,071 | 2.00% |
| `stuck` | 7–40 days frozen at one value | 497,678 | 1.99% |
| `dropout` | 1–12 days at zero | 374,522 | 1.50% |
| `negative` | 1–4 days with the sign flipped (not for temperature) | 55,528 | 0.22% |
| `scale_error` | 1–6 days multiplied by 10, 100 or 1000, or divided by the same | 110,153 | 0.44% |
| `noise_burst` | 5–25 days of extra noise at 2.5–5 spreads | 277,824 | 1.11% |

Data-quality faults are injected on rows that carry no value anomaly, and the `Unit` column is never altered:

| Type | What is written | Rows | Share |
| --- | --- | ---: | ---: |
| `blank_value` | empty `Value` | 66,458 | 0.27% |
| `invalid_value` | text such as `n.v.t.`, `NaN`, `#N/A`, or a decimal comma | 26,650 | 0.11% |
| `invalid_date` | impossible or unparsable `Date` | 11,055 | 0.04% |
| `duplicate_exact` | the previous line repeated | 33,351 | 0.13% |
| `duplicate_conflict` | same point and date with a different value | 22,055 | 0.09% |
| `unknown_point` | a `MeasurementPointID` that has no metadata row | 11,139 | 0.04% |
| `unknown_origin` | an origin code that is not in `Installations` | 11,221 | 0.04% |

In the default build **2,901,795 of 24,993,728 rows (11.6%)** are labelled: 2,719,866 value-anomaly rows (10.9%) and 181,929 data-quality rows (0.7%). The faults reproduce through preparation exactly: the five `flag_*` columns counted by `tai_pipeline.py` equal the injected counts. For duplicates, only the inserted second line is labelled.

## Ground truth

- `row_labels/<plant>.csv.gz`: `source_row` (the line number in the plant's value file, header = 1, matching `source_row` after preparation), `anomaly_type`, `category` (`value` or `quality`) and `episode_id`.
- `episodes.csv.gz`: `plant`, `source_file`, `MeasurementPointID`, `measurement_kind`, `anomaly_type`, `start_date`, `end_date`, `rows`, `magnitude` and `episode_id`. `episode_id` is unique within a plant and is 0 for data-quality faults.
- `manifest.json`: seed, date range, point and row counts, and rows and labelled rows per measurement kind.

Join labels to prepared output on the plant file name plus `source_row`.

## Reading results

- The labels describe only this simulation. How well a detector recovers them says how it behaves on **synthetic** anomalies of these shapes, not how accurate it is on real data. Real faults, operating practice and sensor behaviour are not represented, so no accuracy, false-alarm or time-saving claim follows from it.
- The history detector sets its alert thresholds to flag about 1% of readings per series. With about 11% of rows labelled, a 1% review budget cannot reach every labelled row, and calibrating on a period that is itself full of anomalies raises the thresholds. Compare results by episode (did any day of the episode get flagged) rather than by row, and report the flag rate used. A larger `--target-flag-rate`, or generating with a lower `--anomaly-rate`, changes that trade-off.
- Sustained shifts and drifts are meant to be absorbed by a rolling baseline after their first days. Expect recovery of `level_shift` and `drift` rows to be low by design, and of `stuck`, `dropout`, `negative` and `scale_error` to be high.
- Preparation flags quality faults and keeps every row. Quality labels are for checking that, not for scoring the detectors.

Code: [`src/simulation/`](../../src/simulation/). Tests: [`tests/test_simulate_tai.py`](../../tests/test_simulate_tai.py).
