"""Synthesise the background music and mix it with the voiceover.

    python mix.py <timing.json> <voice_dir> <out.wav>

The music is generated here from scratch (no samples, no downloads): a warm
pad, a plucked arpeggio, bass and light percussion over C - G - Am - F at
100 BPM. It starts sparse, opens up when the product is named, and ducks
under the narration.
"""
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np

SR = 44100
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# chords as MIDI notes (root in bass octave, then triad)
CHORDS = [
    (36, [60, 64, 67, 72]),   # C
    (43, [59, 62, 67, 71]),   # G
    (45, [57, 60, 64, 69]),   # Am
    (41, [57, 60, 65, 69]),   # F
]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def decode(path):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n] * gain


def pluck(freq, dur=1.6):
    t = np.arange(int(dur * SR)) / SR
    sig = (np.sin(2 * np.pi * freq * t) + .35 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 6)
           + .12 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t * 9))
    env = np.minimum(t / .004, 1) * np.exp(-t * 3.2)
    return sig * env


def pad(freqs, dur, vol=1.0):
    t = np.arange(int(dur * SR)) / SR
    sig = np.zeros_like(t)
    for f in freqs:
        for det in (-0.07, 0.0, 0.07):
            ff = f * 2 ** (det / 12)
            sig += np.sin(2 * np.pi * ff * t) + .25 * np.sin(2 * np.pi * 2 * ff * t)
    att = np.minimum(t / (BAR * .45), 1)
    rel = np.minimum((dur - t) / (BAR * .35), 1)
    return sig * att * rel * vol / (len(freqs) * 3)


def bass(freq, dur):
    t = np.arange(int(dur * SR)) / SR
    sig = np.sin(2 * np.pi * freq * t) + .3 * np.sin(2 * np.pi * 2 * freq * t)
    return sig * np.minimum(t / .01, 1) * np.exp(-t * 1.6) * np.minimum((dur - t) / .05, 1)


def kick():
    t = np.arange(int(.35 * SR)) / SR
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(rng, open_=False):
    n = int((.22 if open_ else .06) * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)  # crude high-pass
    return noise * np.exp(-t * (18 if open_ else 70))


def clap(rng):
    n = int(.25 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(12) / 12, mode="same")
    return noise * (np.exp(-t * 22) + .6 * np.exp(-((t - .012) ** 2) * 40000))


def moving_average(x, k):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.empty_like(x)
    half = k // 2
    idx = np.arange(len(x))
    lo, hi = np.clip(idx - half, 0, len(x)), np.clip(idx + k - half, 0, len(x))
    out[:] = (c[hi] - c[lo]) / k
    return out


def fft_convolve(x, kernel):
    """'same'-length convolution via FFT."""
    size = 1 << int(np.ceil(np.log2(len(x) + len(kernel))))
    full = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(kernel, size))[:len(x) + len(kernel) - 1]
    start = (len(kernel) - 1) // 2
    return full[start:start + len(x)]


def reverb(sig, seconds=2.4, mix=.28, seed=3):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 2.6)
    ir = np.convolve(ir, np.ones(8) / 8, mode="same")
    size = 1 << int(np.ceil(np.log2(len(sig) + n)))
    wet = np.fft.irfft(np.fft.rfft(sig, size) * np.fft.rfft(ir, size))[:len(sig)]
    wet *= np.max(np.abs(sig)) / (np.max(np.abs(wet)) + 1e-9)
    return sig * (1 - mix) + wet * mix


def main(timing_path, voice_dir, out_path):
    timing = json.loads(Path(timing_path).read_text())
    total = timing["total"]
    n = int(total * SR)
    rng = np.random.default_rng(7)
    melodic = np.zeros(n)
    drums = np.zeros(n)
    sub = np.zeros(n)

    drop_in = next(s for s in timing["scenes"] if s["id"] == "s4")["start"]   # product named
    full_from = next(s for s in timing["scenes"] if s["id"] == "s5")["start"]
    bars = int(np.ceil(total / BAR)) + 1
    for b in range(bars):
        t0 = b * BAR
        root, triad = CHORDS[b % 4]
        energy = 0 if t0 < drop_in - BAR else (1 if t0 < full_from - 0.1 else 2)
        # pad all the way through
        add(melodic, t0, pad([mtof(m) for m in triad[:3]], BAR + .6), .55)
        # arpeggio: sparse early, busy later
        pattern = [0, 1, 2, 3, 2, 1, 2, 3] if energy else [0, 2, 3, 2]
        step = BEAT / 2 if energy else BEAT
        for i, k in enumerate(pattern):
            add(melodic, t0 + i * step, pluck(mtof(triad[k] + (12 if energy == 2 and i % 4 == 3 else 0))), .34 if energy else .26)
        if energy >= 1:
            add(sub, t0, bass(mtof(root), BAR * .95), .7)
        if energy >= 1:
            for beat in range(4):
                add(drums, t0 + beat * BEAT, kick(), .55 if energy == 2 else .35)
        if energy == 2:
            for e in range(8):
                add(drums, t0 + e * BEAT / 2 + BEAT / 4 * (e % 2), hat(rng, e % 4 == 3), .06)
            for beat in (1, 3):
                add(drums, t0 + beat * BEAT, clap(rng), .14)
    # riser into the title card
    rs = drop_in - 2.4
    if rs > 0:
        t = np.arange(int(2.4 * SR)) / SR
        noise = rng.standard_normal(len(t))
        noise = np.convolve(noise, np.ones(4) / 4, mode="same")
        add(melodic, rs, noise * (t / 2.4) ** 2.2 * .10)

    music = reverb(melodic, mix=.3) + sub + drums
    # overall shape: fade in, gentle lift at the product reveal, long fade out
    tt = np.arange(n) / SR
    shape = np.minimum(tt / 2.5, 1) * np.minimum((total - tt) / 3.2, 1)
    shape *= 0.72 + .28 * np.clip((tt - drop_in) / 3, 0, 1)
    music *= shape

    # voice track
    voice = np.zeros(n)
    for s in timing["scenes"]:
        add(voice, s["voiceStart"], decode(Path(voice_dir) / f"{s['id']}.mp3"))
    # duck the music under the voice
    env = moving_average(np.abs(voice), int(.05 * SR))
    active = (env > .01).astype(float)
    kernel = np.hanning(int(.35 * SR))
    active = fft_convolve(active, kernel / kernel.sum())
    duck = 1 - .62 * np.clip(active * 1.4, 0, 1)
    music = music / (np.max(np.abs(music)) + 1e-9) * .5
    mixed = music * duck + voice * 1.15
    peak = np.max(np.abs(mixed))
    mixed = mixed / peak * .89
    pcm = (np.clip(mixed, -1, 1) * 32767).astype("<i2")
    Path(out_path).write_bytes(
        b"RIFF" + (36 + pcm.nbytes).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + SR.to_bytes(4, "little")
        + (SR * 2).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + pcm.nbytes.to_bytes(4, "little") + pcm.tobytes())
    print("wrote", out_path, round(total, 2), "s")


if __name__ == "__main__":
    main(*sys.argv[1:4])
