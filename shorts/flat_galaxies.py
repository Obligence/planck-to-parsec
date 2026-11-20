#!/usr/bin/env python3
"""Why are galaxies flat? A real particle simulation (shorts/flat_galaxies_sim.py): gas that can collide settles into a
rotating disk, dark matter that cannot stays a round halo. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 flat_galaxies.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 flat_galaxies.py render 0 41.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 48.5            # layout units; output is W*S x H*S
S = int(os.environ.get("PS_SCALE", "2"))   # 2 = 4K, 1 = 1080p
FPS = int(os.environ.get("PS_FPS", "60"))
POP = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
POPS = "/usr/share/fonts/truetype/google-fonts/Poppins-SemiBold.ttf"
INT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
for p in (POPS, INT):
    if not os.path.exists(p):
        POPS = INT = POP

WHITE, CYAN, GOLD, RED = (255, 255, 255), (110, 225, 255), (255, 196, 92), (255, 80, 100)
GREY = (170, 180, 205)

CAPTIONS = [  # start, end, kicker, text (*...* = highlighted, | = line break)
    (0.0, 4.5, None, "Galaxies are *flat.* | What holds them | *is not.*"),
    (4.5, 9.0, "A REAL SIMULATION", "One spinning cloud: | *gas* and | *dark matter.*"),
    (9.0, 13.0, None, "Gravity pulls | *everything inward.*"),
    (13.0, 19.0, None, "Gas particles *collide.* | They lose energy."),
    (19.0, 25.0, None, "But spin *can't be lost.* | The gas *snaps flat.*"),
    (25.0, 31.0, None, "Dark matter | *never collides.* | It stays *round.*"),
    (31.0, 37.0, None, "The only difference: | one *collides,* | one *does not.*"),
    (37.0, 41.0, None, "Not every galaxy is flat. | Mergers can | *scramble a disk.*"),
    (41.0, 48.5, None, "What we see is the | small flat part of a | *giant invisible ball.*"),
]


# ---------- small helpers ----------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ss(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def win(T, a, b, fi=0.35, fo=0.35):
    return ss((T - a) / fi) * ss((b - T) / fo)


def lerp(a, b, t):
    return a + (b - a) * t


def rgba(c, a):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


class Canvas:
    """Antialiased drawing (aggdraw) with the small part of the ImageDraw API the scenes use."""
    def __init__(self, img):
        self.img = img; self._open()

    def _open(self):
        self.d = aggdraw.Draw(self.img); self.d.setantialias(True)

    @staticmethod
    def _a(c):
        return c[3] if len(c) > 3 else 255

    def _args(self, fill, outline, width):
        args = []
        if outline is not None and self._a(outline) > 0:
            args.append(aggdraw.Pen(tuple(outline[:3]), float(width), self._a(outline)))
        if fill is not None and self._a(fill) > 0:
            args.append(aggdraw.Brush(tuple(fill[:3]), self._a(fill)))
        return args

    def ellipse(self, box, fill=None, outline=None, width=1):
        args = self._args(fill, outline, width)
        if args:
            self.d.ellipse([float(v) for v in box], *args)

    def rectangle(self, box, fill=None, outline=None, width=1):
        args = self._args(fill, outline, width)
        if args:
            self.d.rectangle([float(v) for v in box], *args)

    def line(self, pts, fill=None, width=1, joint=None):
        if self._a(fill) > 0:
            self.d.line([float(v) for p in pts for v in p], aggdraw.Pen(tuple(fill[:3]), float(width), self._a(fill)))

    def flush(self):
        self.d.flush()

    def paste(self, sp, xy, mask):
        self.d.flush(); self.img.paste(sp, xy, mask); self._open()


CUR = None  # canvas of the frame being drawn


def circ(d, x, y, r, fill=None, outline=None, width=1.0):
    d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill, outline=outline, width=max(1.0, width * S))


def line(d, pts, fill, width):
    d.line([(x * S, y * S) for x, y in pts], fill=fill, width=max(1.0, width * S))


def rect(d, x0, y0, x1, y1, fill=None, outline=None, width=1.0):
    d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, outline=outline, width=max(1.0, width * S))


# ---------- text sprites (drawn at 1x after the glow pass) ----------
_fonts, _sprites = {}, {}


def font(path, size):
    k = (path, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size)
    return _fonts[k]


def label_sprite(text, path=INT, size=34, fill=WHITE, spacing=0, stroke=3):
    k = ("l", text, path, size, fill, spacing, stroke)
    if k in _sprites:
        return _sprites[k]
    size, spacing, stroke = int(size * S), spacing * S, int(stroke * S)
    f = font(path, size)
    widths = [f.getlength(ch) + spacing for ch in text]
    w = int(sum(widths)) + 2 * stroke + 8
    h = int(size * 1.5) + 2 * stroke
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = stroke + 4
    if spacing:
        for ch, cw in zip(text, widths):
            d.text((x, h / 2), ch, font=f, fill=fill, anchor="lm", stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += cw
    else:
        d.text((x, h / 2), text, font=f, fill=fill, anchor="lm", stroke_width=stroke, stroke_fill=(0, 0, 0))
    _sprites[k] = im
    return im


def caption_sprite(markup, size=68, maxw=900):
    k = ("c", markup, size, maxw)
    if k in _sprites:
        return _sprites[k]
    size, maxw = int(size * S), maxw * S
    f = font(POP, size)
    space = f.getlength(" ")
    lines, cur, curw, hl = [], [], 0, False
    for tok in markup.split(" "):
        if tok == "|":
            lines.append(cur); cur, curw = [], 0
            continue
        if tok.startswith("*"):
            hl = True; tok = tok[1:]
        end = tok.endswith("*")
        if end:
            tok = tok[:-1]
        tw = f.getlength(tok)
        if cur and curw + space + tw > maxw:
            lines.append(cur); cur, curw = [], 0
        cur.append((tok, hl, tw)); curw += (space if len(cur) > 1 else 0) + tw
        if end:
            hl = False
    if cur:
        lines.append(cur)
    lh = int(size * 1.24)
    im = Image.new("RGBA", (W * S, lh * len(lines) + 30 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        tot = sum(t[2] for t in ln) + space * (len(ln) - 1)
        x = (W * S - tot) / 2
        for tok, h_, tw in ln:
            d.text((x, 15 * S + i * lh + lh / 2), tok, font=f, fill=GOLD if h_ else WHITE, anchor="lm",
                   stroke_width=5 * S, stroke_fill=(0, 0, 0))
            x += tw + space
    _sprites[k] = im
    return im


def put(img, sp, cx, cy, alpha=1.0, top=False):
    if alpha <= 0.004:
        return
    x = int(round(cx * S - sp.width / 2))
    y = int(round(cy * S if top else cy * S - sp.height / 2))
    m = sp.getchannel("A")
    if alpha < 0.996:
        m = m.point(lambda v: int(v * alpha))
    img.paste(sp, (x, y), m)


# ---------- pre-rendered assets ----------
def make_bg():
    rng = np.random.default_rng(7)
    y = np.linspace(0, 1, H * S)[:, None, None]
    col = np.array([9, 13, 32]) * (1 - y) + np.array([2, 3, 10]) * y
    img = Image.fromarray(np.repeat(col, W * S, axis=1).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    for _ in range(520):
        x, yy = int(rng.integers(0, W * S)), int(rng.integers(0, H * S))
        b = int(rng.integers(70, 230)); r = int(rng.choice([1, 1, 1, 2, 2, 3]))
        c = [(b, b, b), (int(b * .8), int(b * .9), b), (b, int(b * .9), int(b * .75))][int(rng.integers(0, 3))]
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=c)
    return img


BG = make_bg()

# ---------- the simulation (computed once, cached; see flat_galaxies_sim.py) ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flat_galaxies_sim as sim
from scipy.ndimage import gaussian_filter

_Z = sim.load()
POS, VEL, ST, QG, QD = _Z["pos"], _Z["vel"], _Z["t"], _Z["qg"], _Z["qd"]
NGAS = int(_Z["n_gas"]); SDT = float(ST[1] - ST[0]); S_END = float(ST[-1])
VIOLET = (170, 105, 255)
CX, CY = 510, 1075                   # picture centre (the right-hand edge stays clear for the Shorts buttons)
PY0, PY1 = 640, 1520                 # the band the particles are drawn in


def knots(T, pts):
    xs, ys = zip(*pts)
    return float(np.interp(T, xs, ys))


# picture time -> simulation time. The hook (T < 4.5) shows the finished galaxy, then the run starts from the cloud.
SIM_T = [(4.5, 0.0), (9.0, 1.2), (13.0, 3.3), (19.0, 4.4), (25.0, 7.5), (31.0, 11.5), (37.0, 16.0), (41.0, 19.0), (48.5, 22.5)]
ZOOM = [(4.5, 168), (9.0, 168), (13.0, 205), (19.0, 250), (25.0, 300), (37.0, 330), (41.0, 330), (44.0, 240), (48.5, 225)]
INCL = [(4.5, 7), (30.5, 7), (36.0, 76), (40.5, 76), (44.0, 12), (48.5, 9)]     # degrees above the disk plane


def camera(T):
    if T < 4.5:
        return 20.0 + 0.3 * (T + 1), 300.0, math.radians(8), 0.10 * T
    return knots(T, SIM_T), knots(T, ZOOM), math.radians(knots(T, INCL)), 0.10 * T


def positions(s):
    """Particle positions at simulation time s (cubic Hermite between saved snapshots, using saved velocities)."""
    u = min(max(s / SDT, 0.0), len(ST) - 1.001)
    i = int(u); f = u - i
    p0, p1 = POS[i], POS[i + 1]; v0, v1 = VEL[i].astype(np.float32), VEL[i + 1].astype(np.float32)
    f2, f3 = f * f, f * f * f
    return ((2 * f3 - 3 * f2 + 1) * p0 + (f3 - 2 * f2 + f) * SDT * v0 + (3 * f2 - 2 * f3) * p1 + (f3 - f2) * SDT * v1)


_RAMP = None


def draw_particles(img, d, T, a, dm_gain=1.0):
    """Every particle as a point of light: an additive density image per species, gas cyan, dark matter violet."""
    global _RAMP
    s, zoom, inc, az = camera(T)
    p = positions(s)
    ca, sa, ci, si = math.cos(az), math.sin(az), math.cos(inc), math.sin(inc)
    xs = p[:, 0] * ca + p[:, 1] * sa
    dep = -p[:, 0] * sa + p[:, 1] * ca
    ys = -(p[:, 2] * ci + dep * si)
    w, h = W * S, (PY1 - PY0) * S
    ix = np.rint((CX + xs * zoom) * S).astype(np.int64)
    iy = np.rint((CY - PY0 + ys * zoom) * S).astype(np.int64)
    ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    flat = iy * w + ix
    sg = 1.15 * S
    layer = np.zeros((h, w, 3), np.float32)
    for sl, col, gain, hot in ((slice(NGAS, None), VIOLET, 0.5 * dm_gain, 0.0), (slice(0, NGAS), CYAN, 0.42, 1.0)):
        m = ok[sl]
        dens = np.bincount(flat[sl][m], minlength=w * h).astype(np.float32).reshape(h, w)
        dens = gaussian_filter(dens, sg, truncate=2.5) * (2 * math.pi * sg * sg)
        inten = 1 - np.exp(-0.75 * gain * dens)
        layer += inten[:, :, None] * np.array(col, np.float32)
        if hot:
            layer += (1 - np.exp(-0.012 * dens))[:, :, None] * 130.0          # dense regions go white-hot
    if _RAMP is None:
        yy = np.arange(h, dtype=np.float32) / S
        _RAMP = (np.clip(yy / 45, 0, 1) * np.clip((PY1 - PY0 - yy) / 45, 0, 1))[:, None, None]
    layer = np.clip(layer * _RAMP * a, 0, 255).astype(np.uint8)
    d.flush()
    box = (0, PY0 * S, w, PY1 * S)
    img.paste(ImageChops.add(img.crop(box), Image.fromarray(layer, "RGB")), box)
    d._open()
    return s


def bar_row(d, texts, y, name, col, q, a):
    texts.append((label_sprite(name, POP, 34, col), 235, y, a))
    x0, x1 = 400, 760
    rect(d, x0, y - 9, x1, y + 9, fill=rgba(col, 0.13 * a))
    rect(d, x0, y - 9, x0 + (x1 - x0) * clamp(q), y + 9, fill=rgba(col, 0.95 * a))
    texts.append((label_sprite(f"{q:.2f}", POP, 36, WHITE), 835, y, a))


def readout(d, texts, s, a):
    """Live measurement from the simulation: thickness divided by width, for each kind of particle."""
    qg = float(np.interp(s, ST, QG)); qd = float(np.interp(s, ST, QD))
    texts.append((label_sprite("thickness ÷ width, measured   (1 = ball, 0 = flat)", size=27, fill=GREY), CX, 1352, a))
    bar_row(d, texts, 1400, "gas", CYAN, qg, a)
    bar_row(d, texts, 1446, "dark matter", VIOLET, qd, a)
    texts.append((label_sprite("real simulation, simplified model", size=29, fill=GREY), CX, 1497, a))


# ---------- scenes ----------
def scene_sim(img, d, T, texts):
    cut = ss((T - 4.3) / 0.2) * ss((4.7 - T) / 0.2)            # a quick dip as the film jumps back to the start
    a = 1 - 0.9 * cut
    end = ss((T - 41.5) / 1.5)
    s = draw_particles(img, d, T, a, dm_gain=1 + 0.5 * end)
    if not CAPTIONS:
        return
    ra = a * (1 - ss((T - 40.6) / 0.5))
    if ra > 0:
        readout(d, texts, s, ra)
    if T > 41:
        texts.append((label_sprite("real simulation, simplified model", size=29, fill=GREY), CX, 1497, a * end))
        g = ss((T - 43.6) / 0.6)
        texts.append((label_sprite("what we see", POP, 40, CYAN), CX, CY + 92, g))
        texts.append((label_sprite("what is really there", POP, 40, VIOLET), CX, CY - 300, ss((T - 44.6) / 0.6)))
    if T < 4.5:
        g = ss((T + 0.2) / 0.3) * (1 - cut)
        texts.append((label_sprite("gas", POP, 36, CYAN), CX + 250, CY + 70, g))
        texts.append((label_sprite("dark matter", POP, 36, VIOLET), CX - 240, CY - 215, g))
    fl = T - 21.2                                               # the moment the gas goes flat: one soft ring
    if 0 < fl < 2.5:
        d.ellipse([(CX - 80 - 520 * fl) * S, (CY - 14 - 90 * fl) * S, (CX + 80 + 520 * fl) * S, (CY + 14 + 90 * fl) * S],
                  outline=rgba(CYAN, 0.55 * math.exp(-fl / 0.5)), width=max(1.0, 4 * S))


SCENES = (scene_sim,)


# ---------- frame ----------
def frame(T):
    global CUR
    img = BG.copy()
    d = CUR = Canvas(img)
    texts = []
    for sc in SCENES:
        sc(img, d, T, texts)
    d.flush()
    glow = img.reduce(4 * S).filter(ImageFilter.GaussianBlur(4)).point(lambda v: int(v * 0.6))
    out = ImageChops.add(img, glow.resize((W * S, H * S), Image.BILINEAR))
    for sp, x, y, al in texts:
        put(out, sp, x, y, al)
    for t0, t1, kick, txt in CAPTIONS:
        al = win(T, t0 if t0 > 0 else -1.0, t1, 0.3, 0.25)   # the first caption is there from the first frame
        if al <= 0:
            continue
        rise = (1 - ss((T - t0) / 0.3)) * 16 if t0 > 0 else 0
        if kick:
            put(out, label_sprite(kick, INT, 38, CYAN, spacing=5), 540, 250 + rise, al)
        put(out, caption_sprite(txt), 540, 290 + rise, al, top=True)
    if T > DUR - 0.5:
        out = Image.blend(out, Image.new("RGB", (W * S, H * S), (0, 0, 0)), ss((T - (DUR - 0.5)) / 0.45))
    return out


def main():
    mode = sys.argv[1]
    if mode == "preview":
        for t in sys.argv[2:]:
            frame(float(t)).save(f"frame_{float(t):05.1f}.png")
    elif mode == "render":
        t0, t1, outp = float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
        tmp = outp.replace(".mp4", ".part.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W * S}x{H * S}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20",
                               "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp],
                              stdin=subprocess.PIPE)
        for i in range(int(round(t0 * FPS)), int(round(t1 * FPS))):
            ff.stdin.write(frame(i / FPS).tobytes())
        ff.stdin.close()
        if ff.wait() == 0:
            os.replace(tmp, outp)
        else:
            sys.exit(1)

    elif mode == "renderw":   # time-warped render: knots.json = {"new": [...], "orig": [...]}
        import json
        kn = json.load(open(sys.argv[2])); f0, f1, outp = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
        tmp = outp.replace(".mp4", ".part.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W * S}x{H * S}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20",
                               "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp],
                              stdin=subprocess.PIPE)
        for i in range(f0, f1):
            ff.stdin.write(frame(float(np.interp(i / FPS, kn["new"], kn["orig"]))).tobytes())
        ff.stdin.close()
        if ff.wait() == 0:
            os.replace(tmp, outp)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
