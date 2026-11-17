import sys, json, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
LINES = [
 "One point three billion years ago, two black holes were locked in a death spiral.",
 "Each one, about thirty times heavier than our Sun.",
 "They merged in a split second. Three Suns' worth of mass became ripples in spacetime.",
 "For an instant, it out-powered every star in the observable universe. Combined.",
 "The ripples raced across space at the speed of light,",
 "and on September fourteenth, twenty fifteen, finally washed over Earth.",
 "Waiting for them was Lie-go: two laser beams, in tunnels four kilometres long.",
 "The wave stretched one arm, and squeezed the other,",
 "by one thousandth the width of a proton.",
 "That's like measuring the distance to the nearest star, to within a hair's width.",
 "The whole signal lasted two tenths of a second.",
 "Einstein predicted these waves in nineteen sixteen. A century later, we finally caught one.",
]
voice = sys.argv[1] if len(sys.argv) > 1 else "bm_george"
try:
    print("LIGO ->", k.tokenizer.phonemize("LIGO", "en-us"), "| Lygo ->", k.tokenizer.phonemize("Lie-go", "en-us"))
except Exception as e: print("phon err", e)
durs = []
for i, t in enumerate(LINES):
    s, sr = k.create(t, voice=voice, speed=1.08, lang="en-gb" if voice.startswith("b") else "en-us")
    # trim leading/trailing silence
    idx = np.where(np.abs(s) > 0.01)[0]; s = s[max(0, idx[0] - 800): idx[-1] + 2400]
    sf.write(f"line_{i:02d}.wav", s, sr); durs.append(round(len(s) / sr, 2))
print(sr, durs, sum(durs)); json.dump(durs, open("durs.json", "w"))
