#!/usr/bin/env python3
"""Soundtrack for a short: original synth background music + narration lines.

Usage: python3 make_audio.py <knots.json> <narration_dir> <out.wav> [boom_time_s]
knots.json holds "new" (video timeline), "starts" (when each narration line begins).
narration_dir holds line_00.wav, line_01.wav, ... (any sample rate, mono).
The music is generated here from sine waves, so there is nothing to license.
"""
import sys, json, glob, numpy as np, soundfile as sf
from scipy.signal import resample_poly, butter, lfilter

SR = 44100
kn = json.load(open(sys.argv[1])); ndir = sys.argv[2]; outp = sys.argv[3]
boom_t = float(sys.argv[4]) if len(sys.argv) > 4 else None
CALM = len(sys.argv) > 5 and sys.argv[5] == "calm"   # slower chords, quieter pulse, more echo
DUR = kn["new"][-1]; N = int(DUR * SR); t = np.arange(N) / SR
rng = np.random.default_rng(1)


def note(f):  # midi -> Hz
    return 440.0 * 2 ** ((f - 69) / 12)


def env(t0, t1, a=1.2, r=1.6):
    return np.clip((t - t0) / a, 0, 1) * np.clip((t1 - t) / r, 0, 1)


# --- pad: slow chords (D minor, B flat, F, C), ~7 s each ---
CHORDS = [(50, 53, 57, 62), (46, 50, 53, 58), (53, 57, 60, 65), (48, 52, 55, 60)]
CL = 10.0 if CALM else 7.0
L = np.zeros(N); R = np.zeros(N)
i = 0
while i * CL < DUR:
    ch = CHORDS[i % 4]; e = env(i * CL - 0.8, (i + 1) * CL + 0.8)
    for m in ch:
        f = note(m)
        for det, pan in ((-0.25, 0.3), (0.25, 0.7)):
            w = np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6.28)) + 0.25 * np.sin(2 * np.pi * 2 * (f + det) * t)
            L += w * e * (1 - pan) * 0.12; R += w * e * pan * 0.12
    sub = np.sin(2 * np.pi * note(ch[0] - 12) * t) * e * 0.22
    L += sub; R += sub
    i += 1

# --- pulse: soft plucked eighth notes from the chord, adds forward motion ---
step = 0.3
k = 0
while k * step < DUR - 1:
    t0 = k * step; ch = CHORDS[int(t0 // CL) % 4]
    m = ch[(k * 3) % 4] + 12 + (12 if k % 8 == 5 else 0)
    n0 = int(t0 * SR); n1 = min(N, n0 + int(0.9 * SR)); tt = np.arange(n1 - n0) / SR
    pl = np.sin(2 * np.pi * note(m) * tt) * np.exp(-tt / 0.16) * (0.055 if k % 2 == 0 else 0.035)
    build = (0.5 + 0.5 * min(1.0, t0 / 12.0)) * (0.3 if CALM else 1.0)          # the pulse grows in over the first seconds
    pan = 0.35 + 0.3 * ((k * 5) % 7) / 6
    L[n0:n1] += pl * (1 - pan) * build * 2; R[n0:n1] += pl * pan * build * 2
    k += 1

# --- simple echo/reverb ---
for d_s, g in (((0.41, 0.42), (0.67, 0.32), (1.03, 0.24), (1.51, 0.15)) if CALM else ((0.31, 0.32), (0.47, 0.22), (0.73, 0.14))):
    d = int(d_s * SR)
    L[d:] += g * R[:-d]; R[d:] += g * L[:-d]

# --- impact at the key moment: noise riser, then a low boom ---
if boom_t is not None:
    b, a = butter(2, 1800 / (SR / 2), "low")
    r0 = max(0, int((boom_t - 1.6) * SR)); r1 = int(boom_t * SR)
    ris = lfilter(b, a, rng.normal(0, 1, r1 - r0)) * np.linspace(0, 1, r1 - r0) ** 2 * 0.5
    L[r0:r1] += ris; R[r0:r1] += ris
    n1 = min(N, r1 + int(4 * SR)); tt = np.arange(n1 - r1) / SR
    boom = np.sin(2 * np.pi * (38 * tt + 22 * 0.35 * (1 - np.exp(-tt / 0.35)))) * np.exp(-tt / 1.1) * 0.9
    crack = lfilter(b, a, rng.normal(0, 1, n1 - r1)) * np.exp(-tt / 0.25) * 0.5
    L[r1:n1] += boom + crack; R[r1:n1] += boom + crack

music = np.stack([L, R], 1)
music *= 0.30 / np.max(np.abs(music))
music *= (np.clip(t / 1.0, 0, 1) * np.clip((DUR - t) / 2.0, 0, 1))[:, None]

# --- narration, with the music ducked underneath it ---
voice = np.zeros(N); duck = np.ones(N)
for j, f in enumerate(sorted(glob.glob(f"{ndir}/line_*.wav"))):
    s, sr = sf.read(f)
    s = resample_poly(s, SR, sr) if sr != SR else s
    n0 = int(kn["starts"][j] * SR); n1 = min(N, n0 + len(s))
    voice[n0:n1] += s[: n1 - n0]
    duck[max(0, n0 - 4000): n1 + 6000] = 0.55
sm = int(0.15 * SR); duck = np.convolve(duck, np.ones(sm) / sm, "same")
voice *= 0.89 / np.max(np.abs(voice))
mix = music * duck[:, None] + voice[:, None]
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
sf.write(outp, mix * 0.97, SR)
print("wrote", outp, round(DUR, 2), "s; peak", round(float(np.max(np.abs(mix))), 3))
