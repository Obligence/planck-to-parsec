#!/usr/bin/env python3
"""One command from a scene script + narration lines to a finished short.

  python3 template/build.py shorts/<slug>.py scripts/<slug>.json <slug> \\
      --impact 6.2 --cover-time 7.25 --cover-text "THE *TINIEST*|MEASUREMENT|EVER MADE" --cover-footer "LIGO · 2015"

The scene script must define CAPTIONS (start, end, kicker, text), DUR and frame(T) like template/ligo_short.py.
The JSON holds one narration line per caption: "text", ["text", speed_multiplier], or
{"say": spoken text, "speed": multiplier}. No subtitles are burned in by default (Reza does not want them);
--subtitles turns them on, using each entry's optional "show" text.
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


SUB_FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-SemiBold.ttf"
if not os.path.exists(SUB_FONT):
    SUB_FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"


def entry(e):
    """A narration entry -> (spoken text, speed multiplier, subtitle text)."""
    if isinstance(e, dict):
        return e["say"], float(e.get("speed", 1.0)), e.get("show", e["say"])
    if isinstance(e, str):
        return e, 1.0, e
    return e[0], float(e[1]), e[0]


def subtitle_schedule(kn, maxc=30):
    """Split each line's subtitle text into short chunks timed across that line's audio."""
    sched = []
    for s0, d, text in zip(kn["starts"], kn["durs"], kn["subs"]):
        chunks, cur = [], ""
        for w in text.split():
            if cur and len(cur) + 1 + len(w) > maxc:
                chunks.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            chunks.append(cur)
        tot = sum(len(c) + 2 for c in chunks); t = s0
        for c in chunks:
            dt = d * (len(c) + 2) / tot; sched.append((t, t + dt, c)); t += dt
    return sched


def draw_subtitle(img, text, S):
    """Burned-in subtitle for viewers watching without sound (layout y ~1480, above the Shorts interface)."""
    from PIL import ImageDraw, ImageFont
    f = ImageFont.truetype(SUB_FONT, 46 * S); d = ImageDraw.Draw(img, "RGBA")
    w = f.getlength(text); cx, cy = 540 * S, 1480 * S; px, py, h = 26 * S, 14 * S, 46 * S
    d.rounded_rectangle([cx - w / 2 - px, cy - h / 2 - py, cx + w / 2 + px, cy + h / 2 + py + 4 * S], radius=18 * S, fill=(0, 0, 0, 170))
    d.text((cx, cy), text, font=f, fill=(255, 255, 255), anchor="mm")


def worker(path, knots, f0, f1, out):
    import numpy as np
    mod = load(path); kn = json.load(open(knots)); tmp = out.replace(".mp4", ".part.mp4")
    sched = subtitle_schedule(kn) if kn.get("subs") else []
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{mod.W * mod.S}x{mod.H * mod.S}", "-r", str(mod.FPS), "-i", "-", "-c:v", "libx264",
                           "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(mod.FPS), tmp],
                          stdin=subprocess.PIPE)
    for i in range(f0, f1):
        t = i / mod.FPS
        img = mod.frame(float(np.interp(t, kn["new"], kn["orig"])))
        for a, b_, c in sched:
            if a <= t < b_:
                draw_subtitle(img, c, mod.S); break
        ff.stdin.write(img.tobytes())
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
    ap.add_argument("--subtitles", action="store_true", help="burn the narration in as subtitles (off by default)")
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
    json.dump({"new": new, "orig": K, "starts": starts, "durs": durs, "subs": [entry(e)[2] for e in lines] if a.subtitles else []},
              open(f"{work}/knots.json", "w"))
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
