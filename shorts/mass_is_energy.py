#!/usr/bin/env python3
"""Where your mass comes from: 99% is the energy inside protons and neutrons. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 mass_is_energy.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 mass_is_energy.py render 0 41.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 42.0            # layout units; output is W*S x H*S
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
    (0.0, 3.0, None, "*99%* of your weight | is pure energy."),
    (3.0, 8.0, None, "An atom's weight sits in its core: | *protons and neutrons.*"),
    (8.0, 11.5, None, "Inside each one: | *three quarks.*"),
    (11.5, 16.0, None, "The quarks weigh only | *1% of the proton.*"),
    (16.0, 22.0, None, "The other 99% | *is energy.*"),
    (22.0, 25.5, "EINSTEIN, 1905", "Energy *has weight.*"),
    (25.5, 29.0, None, "The Higgs field gives | *only that 1%.*"),
    (29.0, 35.0, None, "70 kg on the scale. | Without the energy: *under 1 kg.*"),
    (35.0, 41.6, None, "You are *trapped energy,* | not solid stuff."),
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

# ---------- shared pieces ----------
CX = 500                      # picture centre (the right-hand edge stays clear for the Shorts buttons)
QCOL = [(255, 120, 110), (120, 225, 140), (120, 165, 255)]
PROT, NEUT = (200, 84, 72), (84, 104, 168)
SEGS = [(0, 100, 0, 340, 120), (-78, 110, -120, 320, 40), (78, 110, 120, 320, 40),
        (-32, 340, -44, 590, 52), (32, 340, 44, 590, 52)]          # torso, arms, legs (head is a circle at 0,0 r62)


def dim(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


def body(d, cx, y0, s, col, a):
    """A neutral human figure (no likeness): head centre at (cx, y0), feet at y0 + 616*s."""
    if a <= 0:
        return
    c = rgba(col, a)
    circ(d, cx, y0, 62 * s, fill=c)
    for x0, y0_, x1, y1, w in SEGS:
        line(d, [(cx + x0 * s, y0 + y0_ * s), (cx + x1 * s, y0 + y1 * s)], c, w * s)
        circ(d, cx + x0 * s, y0 + y0_ * s, w * s / 2, fill=c); circ(d, cx + x1 * s, y0 + y1 * s, w * s / 2, fill=c)


_br = np.random.default_rng(4)
BODY_DOTS = []                # points inside the figure, in figure units
while len(BODY_DOTS) < 300:
    k = int(_br.integers(0, 7))
    if k >= 5:
        r, th = 58 * math.sqrt(_br.uniform()), _br.uniform(0, 6.28)
        px, py = r * math.cos(th), r * math.sin(th)
    else:
        x0, y0_, x1, y1, w = SEGS[k if k else 0]
        if k == 0 and _br.uniform() < 0.0:
            continue
        u = _br.uniform(); off = _br.uniform(-0.46, 0.46) * w
        px, py = lerp(x0, x1, u) + off, lerp(y0_, y1, u)
    BODY_DOTS.append((float(px), float(py), float(_br.uniform(0, 6.28)), float(_br.uniform(4, 10)), float(_br.uniform())))
for _ in range(120):          # extra weight on the torso so the figure reads clearly
    BODY_DOTS.append((float(_br.uniform(-56, 56)), float(_br.uniform(100, 340)), float(_br.uniform(0, 6.28)),
                      float(_br.uniform(4, 10)), float(_br.uniform())))


def sparkles(d, cx, y0, s, T, a, n=420, col=GOLD, jit=4.0, r=4.0):
    for px, py, ph, sp, u in BODY_DOTS[:n]:
        fl = 0.5 + 0.5 * math.sin(sp * T + ph)
        x = cx + (px + jit * math.sin(sp * 0.8 * T + ph)) * s
        y = y0 + (py + jit * math.cos(sp * 0.7 * T + 2 * ph)) * s
        circ(d, x, y, r * 2.2, fill=rgba(col, 0.10 * a))
        circ(d, x, y, r, fill=rgba(lerp3(col, WHITE, 0.5 * fl), (0.35 + 0.65 * fl) * a))


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


# ---------- scenes ----------
def scene_hook(img, d, T, texts):
    a = win(T, -1.0, 3.0, 0.2, 0.3)
    if a <= 0:
        return
    cx, y0 = 360, 790
    pul = 0.5 + 0.5 * math.sin(5 * T)
    body(d, cx, y0, 1.0, dim(GOLD, 0.30 + 0.06 * pul), a)
    sparkles(d, cx, y0, 1.0, T * 1.6, a)
    n = int(clamp((T + 0.1) / 0.9) * 99)
    texts.append((label_sprite(f"{n}%", POP, 150, GOLD), 765, 990, a))
    texts.append((label_sprite("energy", POP, 64, WHITE), 765, 1110, a * ss((T - 0.5) / 0.4)))
    texts.append((label_sprite("you", size=34, fill=GREY), cx, 1455, a))


NUC = [(0, 0), (1, 0), (-1, 0), (0.5, 0.87), (-0.5, 0.87), (0.5, -0.87), (-0.5, -0.87)]


def scene_atom(img, d, T, texts):
    a = win(T, 3.0, 8.0, 0.3, 0.3)
    if a <= 0:
        return
    cx, cy = CX, 1060
    z = 1 + 5.5 * ss((T - 4.3) / 2.3)
    ra = a * (1 - ss((z - 1) / 1.6))
    for k, (rr, sp, ph) in enumerate(((150, 2.2, 0.0), (250, 1.5, 2.0), (340, 1.1, 4.0))):
        R = rr * z
        circ(d, cx, cy, R, outline=rgba(GREY, 0.45 * ra), width=2)
        th = sp * T + ph
        circ(d, cx + R * math.cos(th), cy + R * math.sin(th), 9, fill=rgba(CYAN, ra))
    rn = 9 * z
    for k, (x, y) in enumerate(NUC):
        col = PROT if k % 2 == 0 else NEUT
        wob = 0.06 * math.sin(6 * T + k)
        circ(d, cx + (x + wob) * rn * 1.7, cy + (y - wob) * rn * 1.7, rn, fill=rgba(col, a))
    texts.append((label_sprite("an atom (not to scale)", size=32, fill=GREY), cx, 1460, ra))
    za = a * ss((z - 4.5) / 1.5)
    texts.append((label_sprite("the nucleus", POP, 46, WHITE), cx, 800, za))
    texts.append((label_sprite("over 99.9% of the atom's weight", size=34, fill=GOLD), cx, 1340, za))


def quark_pos(T, k, R, fast=1.0):
    th = 2.1 * k + 1.9 * fast * T + 0.6 * math.sin(2.3 * fast * T + k)
    r = R * (0.5 + 0.22 * math.sin(3.1 * fast * T + 2 * k))
    return r * math.cos(th), r * math.sin(th)


def scene_proton(img, d, T, texts):
    a = win(T, 8.0, 11.5, 0.3, 0.3)
    if a <= 0:
        return
    cx, cy, R = CX, 1050, 240
    g = ss((T - 8.0) / 0.8)
    circ(d, cx, cy, R, fill=rgba(PROT, 0.10 * a), outline=rgba(PROT, 0.8 * a), width=4)
    pts = [quark_pos(T, k, R) for k in range(3)]
    for i in range(3):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 3]
        seg = []
        for j in range(25):
            u = j / 24
            nx, ny = -(y1 - y0), (x1 - x0); ln = math.hypot(nx, ny) or 1
            w = 9 * math.sin(u * 6.28 * 3 + 9 * T) * math.sin(u * 3.14)
            seg.append((cx + lerp(x0, x1, u) + nx / ln * w, cy + lerp(y0, y1, u) + ny / ln * w))
        line(d, seg, rgba(GOLD, 0.55 * a * g), 3)
    for k, (x, y) in enumerate(pts):
        circ(d, cx + x, cy + y, 34, fill=rgba(QCOL[k], 0.18 * a * g))
        circ(d, cx + x, cy + y, 20, fill=rgba(QCOL[k], a * g))
    texts.append((label_sprite("a proton", POP, 46, WHITE), cx, 760, a))
    texts.append((label_sprite("3 quarks", POP, 46, CYAN), cx, 1350, a * ss((T - 9.0) / 0.4)))
    texts.append((label_sprite("illustration, not to scale", size=28, fill=GREY), cx, 1420, a))


BX0, BX1, BTOP, BBOT = 170, 430, 740, 1440          # the mass bar: 700 units tall, so 1% = 7 units
BCX = (BX0 + BX1) / 2
SLIV = BBOT - 7
FILL_T = 17.9
_sr = np.random.default_rng(8)
BAR_DOTS = [(float(_sr.uniform(BX0 + 14, BX1 - 14)), float(_sr.uniform(0, 1)), float(_sr.uniform(250, 700)),
             float(_sr.choice([-1, 1]))) for _ in range(46)]
TX = 700                                              # label column right of the bar


def bar(d, T, a, fill=0.0, pulse=False):
    rect(d, BX0, BTOP, BX1, BBOT, fill=rgba(BOXC_, 0.05 * a), outline=rgba(GREY, 0.75 * a), width=3)
    if fill > 0:
        yt = lerp(SLIV, BTOP + 3, fill)
        rect(d, BX0 + 3, yt, BX1 - 3, SLIV, fill=rgba(GOLD, 0.55 * a))
        for x, u, sp, sg in BAR_DOTS:                # fast streaks: the energy is motion
            span = SLIV - yt
            if span < 30:
                continue
            y = yt + ((u * span + sg * sp * T) % span)
            line(d, [(x, y), (x, min(SLIV, y + 26))], rgba(WHITE, 0.55 * a), 3)
    k = 1.0 + (0.6 * (0.5 + 0.5 * math.sin(9 * T)) if pulse else 0)
    rect(d, BX0 + 3, SLIV, BX1 - 3, BBOT - 2, fill=rgba(CYAN, a))
    if pulse:
        rect(d, BX0 - 6 * k, SLIV - 6 * k, BX1 + 6 * k, BBOT + 6 * k, outline=rgba(CYAN, 0.8 * a), width=3)


BOXC_ = (150, 215, 255)


def scene_weigh(img, d, T, texts):
    a = win(T, 11.5, 16.0, 0.3, 0.2)
    if a <= 0:
        return
    bar(d, T, a, pulse=T > 12.6)
    texts.append((label_sprite("a proton's mass", size=34, fill=WHITE), BCX, 695, a))
    la = a * ss((T - 12.4) / 0.4)
    line(d, [(BX1 + 14, SLIV + 3), (560, 1330)], rgba(CYAN, la), 3)
    texts.append((label_sprite("its 3 quarks", POP, 46, CYAN), TX, 1250, la))
    texts.append((label_sprite("about 1%", POP, 64, WHITE), TX, 1320, la))
    texts.append((label_sprite("?", POP, 260, WHITE), BCX, 1060, a * ss((T - 13.8) / 0.4) * (0.75 + 0.25 * math.sin(6 * T))))


def scene_energy(img, d, T, texts):
    a = win(T, 16.0, 22.0, 0.2, 0.3)
    if a <= 0:
        return
    dt = T - FILL_T
    f = 0.0 if dt < 0 else 1 - math.exp(-dt / 0.18)
    bar(d, T, a, fill=f)
    if dt >= 0:
        circ(d, BCX, 1090, min(600, 1700 * dt), fill=rgba(GOLD, 0.30 * math.exp(-dt / 0.3) * a))
        circ(d, BCX, 1090, 80 + 900 * dt, outline=rgba(WHITE, 0.8 * math.exp(-dt / 0.3) * a), width=6)
    else:
        texts.append((label_sprite("?", POP, 260, WHITE), BCX, 1060, a * (0.75 + 0.25 * math.sin(6 * T))))
    texts.append((label_sprite("a proton's mass", size=34, fill=WHITE), BCX, 695, a))
    ea = a * ss(dt / 0.3)
    texts.append((label_sprite("ENERGY", POP, 84, GOLD), TX, 960, ea))
    texts.append((label_sprite("about 99%", POP, 64, WHITE), TX, 1050, ea))
    texts.append((label_sprite("quarks in fast motion", size=32, fill=GREY), TX, 1140, a * ss((dt - 1.2) / 0.4)))
    texts.append((label_sprite("+ the strong force", size=32, fill=GREY), TX, 1185, a * ss((dt - 2.2) / 0.4)))
    texts.append((label_sprite("quarks: 1%", size=30, fill=CYAN), TX - 60, 1400, a))


def scene_emc(img, d, T, texts):
    a = win(T, 22.0, 25.5, 0.3, 0.3)
    if a <= 0:
        return
    cx, cy = CX, 1010
    pul = 0.5 + 0.5 * math.sin(4 * T)
    circ(d, cx, cy, 300 + 20 * pul, fill=rgba(GOLD, 0.07 * a))
    for k in range(40):                                   # energy streaming inward and settling
        ph = k * 2.399
        q = ((T * 0.55 + k * 0.137) % 1.0)
        r = lerp(430, 40, q)
        circ(d, cx + r * math.cos(ph + 0.8 * q), cy + r * 0.8 * math.sin(ph + 0.8 * q), 5, fill=rgba(GOLD, a * ss(q / 0.15) * ss((1 - q) / 0.2)))
    s1 = 1 - ss((T - 23.5) / 0.35); s2 = ss((T - 23.7) / 0.35)
    texts.append((label_sprite("E = mc²", POP, 170, WHITE), cx, cy, a * s1))
    texts.append((label_sprite("m = E / c²", POP, 150, GOLD), cx, cy, a * s2))
    texts.append((label_sprite("mass is energy, standing still", size=36, fill=WHITE), cx, 1260, a * s2))


def scene_higgs(img, d, T, texts):
    a = win(T, 25.5, 29.0, 0.3, 0.3)
    if a <= 0:
        return
    bar(d, T, a, fill=1.0, pulse=True)
    texts.append((label_sprite("a proton's mass", size=34, fill=WHITE), BCX, 695, a))
    texts.append((label_sprite("energy", POP, 50, WHITE), BCX, 1060, a))
    line(d, [(BX1 + 16, SLIV + 3), (560, 1330)], rgba(CYAN, a), 3)
    texts.append((label_sprite("Higgs field", POP, 56, CYAN), TX, 1240, a))
    texts.append((label_sprite("the quarks' own mass:", size=32, fill=WHITE), TX, 1305, a))
    texts.append((label_sprite("about 1%", POP, 50, WHITE), TX, 1365, a))


DROP_T = 32.5


def scene_scale(img, d, T, texts):
    a = win(T, 29.0, 35.0, 0.3, 0.3)
    if a <= 0:
        return
    cx, s = 330, 0.78
    y0 = 1290 - 616 * s - 26 * s
    g = ss((T - DROP_T) / 0.7)                       # the energy leaves
    body(d, cx, y0, s, dim(GOLD, lerp(0.42, 0.0, g)), a)
    body(d, cx, y0, s, dim(CYAN, 0.16), a * g)
    sparkles(d, cx, y0 - 520 * g * g, s, T, a * (1 - g), n=300)
    press = 6 * (1 - g)
    rect(d, cx - 190, 1290 + press, cx + 190, 1335 + press, fill=rgba((70, 80, 110), a), outline=rgba(GREY, a), width=3)
    rect(d, cx - 150, 1335 + press, cx + 150, 1350 + press, fill=rgba((50, 58, 84), a))
    n0 = a * (1 - ss((T - DROP_T) / 0.3)); n1 = a * ss((T - DROP_T - 0.3) / 0.35)
    texts.append((label_sprite("70 kg", POP, 130, WHITE), 745, 980, n0))
    texts.append((label_sprite("under", POP, 60, CYAN), 745, 900, n1))
    texts.append((label_sprite("1 kg", POP, 150, CYAN), 745, 1010, n1))
    texts.append((label_sprite("without the energy", size=32, fill=GREY), 745, 1120, n1))
    texts.append((label_sprite("example: a 70 kg person (illustration)", size=28, fill=GREY), CX, 1440, a))


def scene_end(img, d, T, texts):
    a = win(T, 35.0, 43.0, 0.4, 0.4)
    if a <= 0:
        return
    cx, y0, s = CX, (770 if CAPTIONS else 850), 0.92   # lower on the cover, under its title
    br = 1 + 0.015 * math.sin(2.2 * T)
    g = ss((T - 35.0) / 1.2)
    for k in range(3):                                  # slow rings: energy held in place
        q = ((T * 0.22 + k / 3) % 1.0)
        circ(d, cx, y0 + 300 * s, 120 + 420 * q, outline=rgba(GOLD, 0.22 * (1 - q) * a), width=3)
    sparkles(d, cx, y0, s * br, T, a * g, jit=7.0, r=4.5)
    texts.append((label_sprite("so what does “solid” really mean?", POP, 46, GOLD), cx, 1420, a * ss((T - 40.0) / 0.5)))
    if CAPTIONS:
        texts.append((label_sprite("illustration", size=28, fill=GREY), cx, 1482, a))


# ---------- frame ----------
def frame(T):
    global CUR
    img = BG.copy()
    d = CUR = Canvas(img)
    texts = []
    for sc in (scene_hook, scene_atom, scene_proton, scene_weigh, scene_energy, scene_emc, scene_higgs, scene_scale, scene_end):
        sc(img, d, T, texts)
    d.flush()
    glow = img.reduce(4 * S).filter(ImageFilter.GaussianBlur(4)).point(lambda v: int(v * 0.6))
    out = ImageChops.add(img, glow.resize((W * S, H * S), Image.BILINEAR))
    for sp, x, y, al in texts:
        put(out, sp, x, y, al)
    for t0, t1, kick, txt in CAPTIONS:
        al = win(T, t0, t1, 0.3, 0.25)
        if al <= 0:
            continue
        rise = (1 - ss((T - t0) / 0.3)) * 16
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
