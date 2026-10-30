# Pitch video script

Narration and on-screen text for [`second_opinion_pitch.mp4`](second_opinion_pitch.mp4), an 84-second explainer for an audience that does not know the problem. It shows neither the dashboard nor the website. All charts, plants and readings in it are synthetic illustrations.

The narration below is the source text: `build/voiceover.py` holds the same lines and generates the voice from them. Edit both together.

**Voice:** `en-US-AndrewNeural` (neural text-to-speech). **Music:** original, generated in code (`build/mix.py`).

| # | Time | Scene |
| --- | --- | --- |
| 1 | 0:00 | The scale |
| 2 | 0:12 | The problem |
| 3 | 0:27 | Too many readings |
| 4 | 0:32 | The name |
| 5 | 0:36 | Compare |
| 6 | 0:45 | Rank |
| 7 | 0:54 | Second view |
| 8 | 1:02 | Transparent, operator decides |
| 9 | 1:14 | Close |

## 1. The scale (0:00)

> Every day, wastewater plants record thousands of measurements. Those numbers shape the reports, the decisions, and the water quality we all depend on.

On screen: a wall of sensor sparklines. "Thousands of measurements. *Every single day.*" Then the chips **Reports**, **Decisions**, **Water quality**.

## 2. The problem (0:12)

> But they're mostly checked against fixed limits. If a number stays inside the line, it passes, even when it's strange for that particular sensor. A stuck meter. A silent dropout. A slow drift. They all slip through.

On screen: "Fixed limits only see the edges." A sensor series between an upper and lower limit. Callouts mark a spike, a stuck meter, a silent dropout and a slow drift, each labelled "inside the limits". Closing line: "Inside the limits. *Still unusual.*"

## 3. Too many readings (0:27)

> And with thousands of readings, no operator has time to look at everything.

On screen: the sparkline wall zooms out. "Too many readings. *Too little time.*"

## 4. The name (0:32)

> That's why we built Second Opinion.

On screen: "That's why we built" and the **SECOND** *opinion* wordmark. Tagline: "Spot the unusual. Decide what to check first."

## 5. Compare (0:36)

> It compares every reading with the recent history of that same sensor, and flags the ones that don't fit, along with the reason why.

On screen: "01 Compare. Judged against its own history." A series with its usual range from recent history. One reading leaves the range and is flagged: "Why it was flagged: far above this sensor's usual range."

## 6. Rank (0:45)

> Flagged days are grouped into cases and ranked, plant by plant, so operators know exactly what to check first.

On screen: "02 Rank. Cases, ranked plant by plant." Two separate plant lists, each with its own ranking; rank 1 is marked **Check first**. Cases use the real measurement groups and rule names (stuck sensor, dropout to zero, far from its usual).

## 7. Second view (0:54)

> A second AI layer, called an Isolation Forest, adds an independent view, for extra confidence.

On screen: "03 Second view. A second, independent view." A point cloud is cut by random splits until the rare points stand alone. "A second ranking, to compare."

## 8. Transparent, operator decides (1:02)

> Every flag is transparent, showing the value, the history, and the rule behind it. It's a prompt to look, never a verdict. The operator always makes the call.

On screen: "Transparent. *Every flag shows its evidence.*" An evidence card lists value, history, rule and source row. Then "A prompt to look. *Never a verdict.*" and "The operator *makes the call.*" with an Investigate / Dismiss choice.

## 9. Close (1:14)

> Second Opinion. Built around TAI's Z-info platform. Putting attention where it matters most.

On screen: the wordmark, "Attention where it matters most.", "Built around TAI's Z-info platform", and the small print: Research prototype, with the team names.

## Wording rules

The script follows the repository's rules on claims: it does not promise accuracy, fewer false alarms or time saved, because there is no labelled or expert-reviewed evidence yet. It calls the project a research prototype and keeps the operator, not the model, as the decision-maker.
