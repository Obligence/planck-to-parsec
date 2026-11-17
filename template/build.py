#!/usr/bin/env python3
"""One command from a scene script + narration lines to a finished short.

  python3 template/build.py shorts/<slug>.py scripts/<slug>.json <slug> \\
      --impact 6.2 --cover-time 7.25 --cover-text "THE *TINIEST*|MEASUREMENT|EVER MADE" --cover-footer "LIGO · 2015"

The scene script must define CAPTIONS (start, end, kicker, text), DUR and frame(T) like template/ligo_short.py.
The JSON holds one narration line per caption: "text" or ["text", speed_multiplier].
Each scene is stretched to fit its spoken line, so write scene timings for the pictures and let the voice set the pace.
Outputs: videos/<slug>.mp4 (4K, 60 fps, narration + original music) and covers/<slug>.jpg.
Add --draft for a fast 1080p/30 check render (written to build/<slug>/draft.mp4, not to videos/).
Needs: pip install --break-system-packages kokoro-onnx soundfile aggdraw scipy pillow numpy ; ffmpeg.
"""
import sys, os, json, subprocess, argparse, importlib

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
MODEL_DIR = os.path.expanduser("~/.cache/kokoro")
REL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"


def load(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    return importlib.import_module(os.path.splitext(os.path.basename(path))[0])


def worker(path, knots, f0, f1, out):
    import numpy as np
    mod = load(path); kn = json.load(open(knots)); tmp = out.replace(".mp4", ".part.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{mod.W * mod.S}x{mod.H * mod.S}", "-r", str(mod.FPS), "-i", "-", "-c:v", "libx264",
                           "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(mod.FPS), tmp],
                          stdin=subprocess.PIPE)
    for i in range(f0, f1):
        ff.stdin.write(mod.frame(float(np.interp(i / mod.FPS, kn["new"], kn["orig"]))).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit(1)
    os.replace(tmp, out)


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main():
    if sys.argv[1] == "--worker":
        return worker(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
    ap = argparse.ArgumentParser()
    ap.add_argument("scene"); ap.add_argument("lines"); ap.add_argument("slug")
    ap.add_argument("--voice", default="am_michael"); ap.add_argument("--speed", default="0.95")
    ap.add_argument("--mood", default="organ"); ap.add_argument("--impact", type=float)
    ap.add_argument("--cover-time", type=float); ap.add_argument("--cover-text"); ap.add_argument("--cover-footer", default="")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    if a.draft:
        os.environ["PS_SCALE"], os.environ["PS_FPS"] = "1", "30"
    scene = os.path.abspath(a.scene); work = os.path.join(ROOT, "build", a.slug); os.makedirs(work, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not os.path.exists(f"{MODEL_DIR}/{f}"):
            run(["curl", "-sSL", "-o", f"{MODEL_DIR}/{f}", REL + f])
    mod = load(scene); import numpy as np
    lines = json.load(open(a.lines))
    assert len(lines) == len(mod.CAPTIONS), f"{len(lines)} narration lines for {len(mod.CAPTIONS)} captions"
    for f in os.listdir(work):
        if f.startswith("line_"):
            os.remove(os.path.join(work, f))
    run([sys.executable, f"{HERE}/make_narration.py", a.lines, a.voice, a.speed, work, MODEL_DIR])
    durs = json.load(open(f"{work}/durs.json")); caps = mod.CAPTIONS
    K = [0.0] + [(caps[i - 1][1] + caps[i][0]) / 2 for i in range(1, len(caps))] + [mod.DUR]
    new, starts = [0.0], []
    for i, d in enumerate(durs):
        n = max(d + 0.9, 0.85 * (K[i + 1] - K[i])) + (1.3 if i == len(durs) - 1 else 0)
        starts.append(round(new[-1] + 0.35, 3)); new.append(round(new[-1] + n, 3))
    json.dump({"new": new, "orig": K, "starts": starts, "durs": durs}, open(f"{work}/knots.json", "w"))
    total = int(new[-1] * mod.FPS); half = total // 2
    print(f"length {new[-1]:.1f}s, {total} frames at {mod.W * mod.S}x{mod.H * mod.S}", flush=True)
    procs = [subprocess.Popen([sys.executable, __file__, "--worker", scene, f"{work}/knots.json", str(f0), str(f1), f"{work}/{n}.mp4"])
             for n, f0, f1 in (("a", 0, half), ("b", half, total))]
    audio = [sys.executable, f"{HERE}/make_audio.py", f"{work}/knots.json", work, f"{work}/sound.wav"]
    if a.impact is not None:
        audio += [f"{float(np.interp(a.impact, K, new)):.2f}", a.mood]
    elif a.mood:
        audio += ["-1", a.mood]
    run(audio)
    if any(p.wait() != 0 for p in procs):
        sys.exit("render failed")
    open(f"{work}/list.txt", "w").write("file 'a.mp4'\nfile 'b.mp4'\n")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{work}/list.txt", "-c", "copy", f"{work}/v.mp4"])
    out = f"{work}/draft.mp4" if a.draft else f"{ROOT}/videos/{a.slug}.mp4"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{work}/v.mp4", "-i", f"{work}/sound.wav", "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out])
    if a.cover_text:
        os.makedirs(f"{ROOT}/covers", exist_ok=True)
        env = dict(os.environ, PS_SCALE="1", PYTHONPATH=os.path.dirname(scene))
        run([sys.executable, f"{HERE}/make_cover.py", os.path.splitext(os.path.basename(scene))[0], a.cover_time or 0,
             f"{ROOT}/covers/{a.slug}.jpg", a.cover_text, a.cover_footer], env=env)
    print("done:", out)


if __name__ == "__main__":
    main()
