"""Generate the pitch voiceover, one clip per scene, and report their lengths.

Only the script text below is sent to the speech service. Run with the
scratch tooling venv (edge-tts, imageio-ffmpeg):

    python voiceover.py <output_dir>
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

VOICE = "en-US-AndrewNeural"
RATE = "-3%"

SCRIPT = [
    ("s1", "Every day, wastewater plants record thousands of measurements. "
           "Those numbers shape the reports, the decisions, and the water quality we all depend on."),
    ("s2", "But they're mostly checked against fixed limits. If a number stays inside the line, it passes, "
           "even when it's strange for that particular sensor. A stuck meter. A silent dropout. "
           "A slow drift. They all slip through."),
    ("s3", "And with thousands of readings, no operator has time to look at everything."),
    ("s4", "That's why we built Second Opinion."),
    ("s5", "It compares every reading with the recent history of that same sensor, "
           "and flags the ones that don't fit, along with the reason why."),
    ("s6", "Flagged days are grouped into cases and ranked, plant by plant, "
           "so operators know exactly what to check first."),
    ("s7", "A second AI layer, called an Isolation Forest, adds an independent view, for extra confidence."),
    ("s8", "Every flag is transparent, showing the value, the history, and the rule behind it. "
           "It's a prompt to look, never a verdict. The operator always makes the call."),
    ("s9", "Second Opinion. Built around TAI's Z-info platform. Putting attention where it matters most."),
]


def duration(ffmpeg, path):
    """Decode to raw PCM and count samples; robust for mp3."""
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "24000", "-"],
        capture_output=True, check=True).stdout
    return len(out) / 2 / 24000


async def main(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    lengths = {}
    for key, text in SCRIPT:
        path = out_dir / f"{key}.mp3"
        await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path))
        lengths[key] = round(duration(ffmpeg, path), 3)
        print(key, lengths[key], flush=True)
    (out_dir / "lengths.json").write_text(json.dumps(lengths, indent=2))
    print("total", round(sum(lengths.values()), 2))


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
