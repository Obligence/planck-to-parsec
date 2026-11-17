#!/usr/bin/env python3
"""Narration lines with Kokoro TTS (pip install kokoro-onnx soundfile; model files from the
kokoro-onnx GitHub release model-files-v1.0: kokoro-v1.0.onnx and voices-v1.0.bin).
Usage: python3 make_narration.py <lines.json> <voice> <speed> <outdir> <model_dir>
lines.json is a list, one entry per caption: "text" or ["text", speed_multiplier].
The last line gets a gentle falling, slowing ending so the video closes on a settled tone.
Writes line_NN.wav and durs.json."""
import sys, json, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
lines = json.load(open(sys.argv[1])); voice = sys.argv[2]; speed = float(sys.argv[3]); out = sys.argv[4]; md = sys.argv[5]
k = Kokoro(f"{md}/kokoro-v1.0.onnx", f"{md}/voices-v1.0.bin")
durs = []
for i, t in enumerate(lines):
    t, mult = (t, 1.0) if isinstance(t, str) else (t[0], float(t[1]))
    s, sr = k.create(t, voice=voice, speed=speed * mult, lang="en-gb" if voice.startswith("b") else "en-us")
    idx = np.where(np.abs(s) > 0.01)[0]; s = s[max(0, idx[0] - 800): idx[-1] + 2400]
    if i == len(lines) - 1:   # closing cadence: pitch and pace glide down over the final 1.4 s
        n = min(len(s), int(1.4 * sr)); tail = s[-n:]
        rate = np.linspace(1.0, 0.90, int(n / 0.95)); pos = np.cumsum(rate); pos = pos[pos < n - 1]
        s = np.concatenate([s[:-n], np.interp(pos, np.arange(n), tail)])
    sf.write(f"{out}/line_{i:02d}.wav", s, sr); durs.append(round(len(s) / sr, 2))
json.dump(durs, open(f"{out}/durs.json", "w")); print(durs, round(sum(durs), 1))
