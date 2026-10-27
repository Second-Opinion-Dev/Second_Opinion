# Second Opinion: an investigation queue for unusual wastewater measurements

**Tagline:** Spot unusual measurements, compare the evidence, and decide what to
check first.

**Status:** Proposed hackathon project. The methods, peer eligibility, and
operational usefulness are hypotheses to test, not established results.

## The challenge

TAI / Z-info asks us to detect and flag unusual measurements at wastewater
treatment plants, explain why the flags are useful, and consider what false
alarms cost an operator. The data has no confirmed anomaly labels.

Wastewater plants collect many measurements. A reading may look unusual because
of a change in the process, a measurement or data issue, or a change also seen
at other plants. Flagging every unusual value could overwhelm an operator.

**Our problem statement:** How can we help an operator identify unusual
wastewater measurements worth checking, understand the evidence behind each
flag, and manage the time needed to review them?

An unusual value is a reason to investigate, not proof of a fault, incident,
physical cause, or safe condition. The operator remains responsible for decisions.

## The idea

Second Opinion is a decision-support dashboard that compares an observation with:

1. **Its own history:** Is this reading unusual for this measurement point?
2. **Eligible peers:** Did other comparable plants show a similar change on the
   same day, relative to their own histories?
3. **The review budget:** Which cases can be checked now, and which remain for later?

The dashboard groups suitable consecutive flags into cases and presents an
investigation queue. Each case shows the reading, unit, historical chart, available
peer context, reason for the flag, and a suggested investigation. It keeps deferred
cases visible; it never claims an unreviewed case is safe or automatically closes it.

### Illustrative example — not a dataset finding

Suppose an incoming-flow measurement for Plant A is much higher than usual. The
system compares it with Plant A's history and with changes at eligible peer plants.
It shows the evidence and suggests checking the reading and relevant operating
records. If peers also increase, say **“similar change observed at other plants”**;
do not infer that rain caused it, that the event is harmless, or that all plants
share the same cause.

## Proposed implementation

### 1. Understand and select a suitable slice

- Inspect installation, measurement-point, and daily-value files and their
  relationships. Confirm column meanings, units, input types, time availability,
  quality, and operational relevance with TAI experts.
- Prefer daily incoming water flow **only if** it has the same meaning and
  compatible units across enough plants, sufficient history and overlapping dates,
  and workable data quality. Otherwise choose a better-supported measurement.
- Identify eligible plants and points before comparing them. Compare like with
  like: measurement meaning, unit, process context, measurement method and
  expression basis must be compatible. Do not assume all plants are peers.
- Examine missing values, repeated or default-like values, and conflicting
  same-date records. Preserve raw records and document any exclusion or handling;
  do not silently average or discard conflicting values.
- Ask the experts what operators currently investigate, how long reviews take,
  what matters operationally, and whether they can review sample cases.

### 2. Build the history-only baseline

For each eligible point, compare a reading with a typical value and variability
computed from that point's **prior** observations. Flag a sufficiently large
deviation using a clear, reproducible rule; a rolling median and robust spread are
reasonable candidates. Handle insufficient history, missing data and zero spread
explicitly. Record configuration and the reasons a case was or was not assessed.

Fit or choose thresholds using training/validation data only. Keep a later time
period untouched for evaluation. Do not use future measurements in a baseline,
rolling feature, peer eligibility decision, threshold or replay.

### 3. Add peer context

For each target plant and day, calculate its change relative to its own history
and compare it with the corresponding changes of eligible peers. Use only peer
readings available at the decision time; same-date timestamps alone do not prove
simultaneous availability. Show how many peers were available, the comparison,
and why they were selected.

If peer coverage, comparability, or availability is insufficient, display
**“peer comparison unavailable”** and use the history-only result. A shared
change is context, not proof that a reading is safe. Do not automatically suppress
or downgrade shared changes without a justified and evaluated rule; retain access
to all candidates.

### 4. Build the review queue

- Rank cases using a clear, documented rule and the evidence available; do not
  claim the ranking represents verified probability or severity.
- Where appropriate, group consecutive flags for the same point and plant into a
  case. Describe grouping and preserve access to underlying observations.
- Let the operator choose a review budget, such as a number of cases. Display
  selected and deferred cases and their counts; flag that deferral can leave an
  important case unreviewed.
- If showing estimated review time or cost, use expert-provided values or clearly
  labelled assumptions. Do not present assumptions as measured savings or costs.
- Keep questionable data distinct from possible process changes; explain that
  neither category is a confirmed diagnosis. Suggested actions are checks, not
  instructions to change plant operation.

## Testing without anomaly labels

The strongest available evidence may be limited. Compare the history-only and
peer-aware methods on the **same chronological holdout, eligible points, event
definitions, review budgets and evaluation protocol**. Keep training, threshold
selection, and test data separate.

1. Create controlled artificial changes **in copies of held-out historical data**:
   spikes, drops, gradual changes, and changes shared across plants. Record the
   seed, exact locations and magnitudes, and preserve the unmodified originals.
2. Report how many injected cases each approach finds or misses at the same review
   budget, as well as the number of flagged points, grouped cases, and deferred
   cases. Include unchanged periods so the methods cannot appear successful simply
   by flagging everything. Specify whether results are point- or event-level.
3. Clearly label these as **artificial test results**. Recovery of injections is
   not real-world precision, recall, false-alarm rate, or proof of safety. Do not
   use fabricated examples as evidence of actual plant incidents.
4. If TAI experts are available, ask them to review a small, documented sample of
   real cases, including deferred or unflagged periods where feasible. Record
   useful / not useful / unsure and the review protocol. Distinguish this limited
   feedback from ground-truth validation.
5. If peer context does not improve results, report that honestly and show it as
   context only. Never claim reduced false alarms or saved time without evidence.

## Scope and demo

**Must have:** one appropriate measurement type; a reproducible history-only
baseline; an understandable case view; a ranked queue with visible deferred cases;
an honest statement of limitations.

**Should have:** eligible-peer comparison with a clear fallback; consecutive-day
case grouping; review-budget control; side-by-side baseline and peer-aware tests.

**Wow feature:** an interactive view showing how the two methods and their
deferred cases change at the same review budget, supported by recorded test results.
Do not sacrifice the working core for an unfinished feature.

For the demonstration:

1. Explain the operator's problem and open one real, historical flagged case.
2. Show its history, reason for the flag and peer context, if eligible peers exist.
3. Adjust the review budget and show selected and deferred cases.
4. Compare the baseline and peer-aware method on the same artificial tests.
5. State the limitations, expert feedback obtained, and next validation steps.

## Rules for agents

- Follow `AGENTS.md`, the staged playbooks in `.agents/skills/`, and the team's
  branch-and-PR workflow. Read the local `DATA_AUDIT.md` and `DECISIONS.md` when
  available; do not assume those private files exist in a fresh clone.
- Inspect the actual data before implementing; do not assume a flow column, peer
  set, input meaning, labels, operating limits or suitable external data.
- Work locally with partner data. Never commit, publish, or send the raw data or
  access key to external services. Delete partner data after the event unless the
  partner agrees otherwise in writing.
- Keep reusable logic outside notebooks and the app, preserve raw inputs, and
  record seeds, configuration, splits, metrics, artifacts and exact run commands.
- The provided export is historical and day-granular. Do not call it a live feed
  or claim intraday detection, causality, real-world accuracy, false-alarm
  reduction or operational savings without evidence.

**Expected outcome:** a practical prototype that helps an operator understand and
prioritise unusual measurements, with reproducible tests, a clear demonstration,
and honest limits on what is known.
