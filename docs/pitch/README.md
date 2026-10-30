# Pitch video

`second_opinion_pitch.mp4` is an 84-second investor explainer: the problem, the product and its principles. It shows no dashboard or website. All charts, plants and readings in it are synthetic illustrations.

| Path | What it is |
| --- | --- |
| [`script.md`](script.md) | The narration and on-screen text, scene by scene. |
| `src/video.html` | All visuals. Each frame is a pure function of time, drawn on a canvas. |
| `build/voiceover.py` | The narration script and the neural text-to-speech call (`edge-tts`, voice `en-US-AndrewNeural`). Only the script text leaves the machine. |
| `build/timeline.py` | Turns the clip lengths into one scene timeline shared by picture and sound. |
| `build/mix.py` | Synthesises the music from scratch (no samples), ducks it under the voice and mixes. |
| `build/render.mjs` | Renders frames with headless Chrome (`puppeteer-core`). |

To rebuild, install `edge-tts`, `imageio-ffmpeg` and `numpy` in a scratch Python environment and `puppeteer-core` in a scratch Node folder (set `TOOLS` to it), then:

1. `python build/voiceover.py <work>/vo`
2. `python build/timeline.py <work>/vo/lengths.json <work>/timing.json`
3. `python build/mix.py <work>/timing.json <work>/vo <work>/audio.wav`
4. `node build/render.mjs <work>/timing.json <work>/frames frames 30`
5. Encode the frames and `audio.wav` with ffmpeg (H.264, AAC, loudness-normalised to -16 LUFS).

The page loads Inter Tight, Instrument Serif and JetBrains Mono from Google Fonts when rendering. To change a line of narration, edit `SCRIPT` in `voiceover.py` and rerun from step 1. The scene timing follows the new clip lengths automatically.
