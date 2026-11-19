#!/usr/bin/env python3
"""Narration lines with Kokoro TTS (pip install kokoro-onnx soundfile; model files from the
kokoro-onnx GitHub release model-files-v1.0: kokoro-v1.0.onnx and voices-v1.0.bin).
Usage: python3 make_narration.py <lines.json> <voice> <speed> <outdir> <model_dir>
lines.json is a list, one entry per caption: "text", ["text", speed_multiplier] or
{"say": spoken text, "show": subtitle text, "speed": multiplier}.
A line may hold stops such as "A question? [0.7] ~Nobody knows. [0.5] And on." (see the comment below).
The last line gets a gentle falling, slowing ending so the video closes on a settled tone.
Writes line_NN.wav and durs.json."""
import sys, json, re, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
lines = json.load(open(sys.argv[1])); voice = sys.argv[2]; speed = float(sys.argv[3]); out = sys.argv[4]; md = sys.argv[5]
k = Kokoro(f"{md}/kokoro-v1.0.onnx", f"{md}/voices-v1.0.bin")


def question_rise(x, sr, text):
    """The voice tends to read questions with a falling, statement-like ending. Re-shape the pitch of the last
    word so it rises (WORLD vocoder: pip install pyworld). Yes/no questions rise more than which/what/why ones."""
    import pyworld as pw
    yn = text.split()[0].lower().strip("~") in ("is", "are", "was", "were", "do", "does", "did", "can", "could", "will", "would", "should", "has", "have")
    top, span = (1.55, 0.50) if yn else (1.38, 0.32)
    x = x.astype(np.float64); f0, tt = pw.harvest(x, sr, frame_period=5.0)
    sp = pw.cheaptrick(x, f0, tt, sr); ap = pw.d4c(x, f0, tt, sr)
    v = np.where(f0 > 0)[0]
    if len(v) < 20:
        return x
    med = float(np.median(f0[v])); n = min(len(v), int(span / 0.005)); tail = v[-n:]
    u = np.linspace(0, 1, n); w = 0.9 * (u * u * (3 - 2 * u)) ** 0.7        # how strongly the new shape takes over
    target = med * (0.98 + (top - 0.98) * u ** 1.3)
    f0 = f0.copy(); f0[tail] = np.exp((1 - w) * np.log(f0[tail]) + w * np.log(target))
    y = pw.synthesize(f0, sp, ap, sr, 5.0)
    return y[: len(x)] * (np.max(np.abs(x)) / (np.max(np.abs(y)) + 1e-9))


durs = []
for i, t in enumerate(lines):
    if isinstance(t, dict):
        t, mult = t["say"], float(t.get("speed", 1.0))
    else:
        t, mult = (t, 1.0) if isinstance(t, str) else (t[0], float(t[1]))
    # "[0.6]" inside a line = a deliberate stop of that many seconds; the phrase after it is spoken on its own,
    # so it gets a fresh intonation. A phrase ending in "?" gets a rising, questioning ending. A phrase starting with "~" is weighted: slightly slower and lower.
    parts = re.split(r"\s*\[(\d*\.?\d+)\]\s*", t); segs = []
    for j in range(0, len(parts), 2):
        ph = parts[j].strip(); heavy = ph.startswith("~"); ph = ph.lstrip("~ ")
        x, sr = k.create(ph, voice=voice, speed=speed * mult * (0.97 if heavy else 1.0), lang="en-gb" if voice.startswith("b") else "en-us")
        idx = np.where(np.abs(x) > 0.01)[0]; x = x[max(0, idx[0] - 800): idx[-1] + 2400]
        if ph.endswith("?"):
            x = question_rise(x, sr, ph)
        if heavy:
            x = np.interp(np.arange(0, len(x) - 1, 1 / 1.035), np.arange(len(x)), x)
        if j + 1 < len(parts):   # silence up to the requested stop (the trimmed edges already hold ~0.13 s)
            x = np.concatenate([x, np.zeros(max(0, int((float(parts[j + 1]) - 0.13) * sr)))])
        segs.append(x)
    s = np.concatenate(segs)
    if i == len(lines) - 1:   # closing cadence: pitch and pace glide down over the final 1.4 s
        n = min(len(s), int(1.4 * sr)); tail = s[-n:]
        rate = np.linspace(1.0, 0.90, int(n / 0.95)); pos = np.cumsum(rate); pos = pos[pos < n - 1]
        s = np.concatenate([s[:-n], np.interp(pos, np.arange(n), tail)])
    sf.write(f"{out}/line_{i:02d}.wav", s, sr); durs.append(round(len(s) / sr, 2))
json.dump(durs, open(f"{out}/durs.json", "w")); print(durs, round(sum(durs), 1))
