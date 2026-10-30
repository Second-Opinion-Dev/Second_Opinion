"""Turn the voiceover clip lengths into one shared scene timeline.

    python timeline.py <lengths.json> <timing.json>

Each scene starts with a short lead-in, plays its voice clip, then holds a
tail before the next scene. The visuals and the audio mix both read the
result, so they cannot drift apart.
"""
import json
import sys
from pathlib import Path

LEAD = {"s1": 1.0, "s4": 0.8}
TAIL = {"s9": 3.0}
MIN_LEN = {"s4": 4.0}
DEFAULT_LEAD, DEFAULT_TAIL = 0.5, 0.8


def build(lengths):
    scenes, t = [], 0.0
    for key, vlen in lengths.items():
        lead = LEAD.get(key, DEFAULT_LEAD)
        dur = max(lead + vlen + TAIL.get(key, DEFAULT_TAIL), MIN_LEN.get(key, 0))
        scenes.append({"id": key, "start": round(t, 3), "end": round(t + dur, 3),
                       "voiceStart": round(t + lead, 3), "voiceLen": vlen})
        t += dur
    return {"scenes": scenes, "total": round(t, 3)}


if __name__ == "__main__":
    lengths = json.loads(Path(sys.argv[1]).read_text())
    timing = build(lengths)
    Path(sys.argv[2]).write_text(json.dumps(timing, indent=2))
    for s in timing["scenes"]:
        print(s["id"], s["start"], "->", s["end"])
    print("total", timing["total"])
