#!/usr/bin/env python3
"""The universe has a delete button: measurements of the Higgs boson and the top quark suggest that empty space may be
metastable. If it ever tunnelled to a lower-energy state, a bubble of new space would grow at almost the speed of
light with no warning. The best estimate of the wait is about 10^139 years (Standard Model only).
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 vacuum_decay.py preview 0 6.4 12      -> frame_<t>.png files
  python3 vacuum_decay.py render 0 42 out.mp4   -> renders that time range
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
    (0.0, 4.0, None, "The universe has | a *delete button.*"),
    (4.0, 10.5, "THE HIGGS FIELD", "Empty space may be | *resting on a ledge.*"),
    (10.5, 16.5, None, "If it slips through, | *a bubble is born.*"),
    (16.5, 23.0, None, "It grows at almost | *the speed of light.*"),
    (23.0, 28.0, None, "*No warning.* It arrives | with its own light."),
    (28.0, 36.0, "THE GOOD NEWS", "The wait: a 1 with | *139 zeros* of years."),
    (36.0, 42.0, None, "Almost certainly | *not today.*"),
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


def ell(d, x, y, rx, ry, fill=None, outline=None, width=1.0):
    d.ellipse([(x - rx) * S, (y - ry) * S, (x + rx) * S, (y + ry) * S], fill=fill, outline=outline, width=max(1.0, width * S))


def poly(d, pts, fill):
    if fill[3] > 0:
        d.d.polygon([float(v * S) for p in pts for v in p], aggdraw.Brush(tuple(fill[:3]), fill[3]))


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
def _haze(rng, cells, blur):
    n = Image.fromarray((rng.random((H // cells, W // cells)) * 255).astype(np.uint8), "L")
    n = n.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    v = np.asarray(n, dtype=np.float32) / 255.0
    return np.clip((v - 0.42) / 0.4, 0, 1)[:, :, None]


def make_bg():
    rng = np.random.default_rng(7)
    y = np.linspace(0, 1, H)[:, None, None]
    col = np.array([9, 13, 32]) * (1 - y) + np.array([2, 3, 10]) * y
    col = np.repeat(col, W, axis=1).astype(np.float32)
    col += _haze(rng, 240, 110) * np.array([11, 6, 21]) + _haze(rng, 200, 100) * np.array([2, 10, 16])   # faint nebula haze
    xx = (np.arange(W)[None, :, None] - W / 2) / (W / 2); yy = (np.arange(H)[:, None, None] - H / 2) / (H / 2)
    col *= np.clip(1.08 - 0.22 * (xx ** 2 + yy ** 2), 0, 1)                                              # vignette
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB").resize((W * S, H * S), Image.BICUBIC)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(900):
        x, yy_ = int(rng.integers(0, W * S)), int(rng.integers(0, H * S))
        b = int(rng.integers(60, 230)); r = float(rng.choice([0.5, 0.5, 0.5, 1, 1, 1.5])) * S
        c = [(b, b, b), (int(b * .8), int(b * .9), b), (b, int(b * .9), int(b * .75))][int(rng.integers(0, 3))]
        if r >= 1.5 * S and b > 170:                       # the few bright ones get a soft halo
            for k in range(4):
                rr = r * (5 - k); d.ellipse([x - rr, yy_ - rr, x + rr, yy_ + rr], fill=c + (14,))
        d.ellipse([x - r, yy_ - r, x + r, yy_ + r], fill=c + (255,))
    return img


BG = make_bg()

# ---------- facts used on screen (sources: Andreassen, Frost and Schwartz, "Scale-invariant instantons and the
# complete lifetime of the standard model", Physical Review D 97, 056006 (2018), arXiv:1707.08124: "the first complete
# calculation of the lifetime of our universe: 10^139 years", and "with 95% confidence, we expect our universe to last
# more than 10^58 years"; Elias-Miro et al., "Higgs mass implications on the stability of the electroweak vacuum",
# arXiv:1112.3022: for a Higgs mass of 124 to 126 GeV the Higgs potential develops an instability, "with a lifetime
# much longer than the age of the Universe", though "stability up to the Planck scale cannot be excluded";
# Scientific American, "The Quantum Bubble That Could Destroy the Universe": the bubble "would expand at almost the
# speed of light", inside it "the laws of physics we take for granted would change, making matter as we know it
# impossible", and new physics could remove the second valley altogether. Age of the universe: about 13.8 billion
# years (NASA). The hill-and-valley curve is a schematic, labelled as an illustration.) ----------
CX = 470                           # picture centre (the right-hand edge stays clear for the Shorts buttons)
BX, BY = CX, 1070                  # where the bubble is born
T1, T2, T3, T4, T5, T6, T7 = 0.0, 4.0, 10.5, 16.5, 23.0, 28.0, 36.0
TB = 14.3                          # the bubble of the main story is born
VOID = (46, 6, 30)
MAG = (255, 70, 130)
BLUE = (70, 140, 255)
_r = np.random.default_rng(23)

NGAL = 64
GAL = np.stack([_r.uniform(40, 930, NGAL), _r.uniform(680, 1470, NGAL)], axis=1)
GAL_Q = _r.uniform(0, math.pi, NGAL); GAL_L = _r.uniform(9, 22, NGAL); GAL_P = _r.uniform(0, 6.283, NGAL)
GAL_C = [((255, 236, 200), (190, 215, 255), (255, 210, 170))[int(k)] for k in _r.integers(0, 3, NGAL)]
NST = 150
STR = np.stack([_r.uniform(20, 950, NST), _r.uniform(660, 1490, NST)], axis=1); STR_P = _r.uniform(0, 6.283, NST)


def bubble_radius(T):
    """Radius of the bubble at picture time T, for its three appearances (opening, main story, loop)."""
    if T < T2 + 0.5:
        return 60 + 67.5 * T                     # the opening: already growing in the first frame
    if T > T7 - 0.5:
        return max(0.0, 60 + 67.5 * (T - DUR))   # the end: born just before the Short loops into the opening
    tm = T - TB
    return 0.0 if tm <= 0 else 22 * tm + 9 * tm ** 2.6


def scene_bubble(img, d, T, texts):
    """0-4, 14-23 and 36-42: a field of galaxies, and a bubble of new space that erases them as it grows."""
    a = win(T, -1.0, T2 + 0.3, 0.2, 0.4) + win(T, TB - 0.5, T5 + 0.3, 0.5, 0.4) + win(T, T7, DUR + 2, 0.5, 0.3)
    if a <= 0.004:
        return
    t = T - DUR if T > T7 - 0.5 else T
    R = bubble_radius(T)
    for i in range(NST):
        x, y = STR[i]
        dist = math.hypot(x - BX, y - BY)
        k = 1 - ss((R - dist) / 30 + 0.5)
        circ(d, x, y, 2.0, fill=rgba(WHITE, a * k * (0.45 + 0.3 * math.sin(2.2 * t + STR_P[i]))))
    for i in range(NGAL):
        x = GAL[i, 0] + 3 * math.sin(0.5 * t + GAL_P[i]); y = GAL[i, 1] + 3 * math.cos(0.4 * t + GAL_P[i])
        dist = math.hypot(x - BX, y - BY)
        k = 1 - ss((R - dist) / 46)              # 1 outside the bubble, 0 once the wall has passed
        if k <= 0.004:
            continue
        hot = ss((R - dist + 40) / 40)           # glows red as the wall arrives
        col = lerp3(GAL_C[i], MAG, hot)
        q = GAL_Q[i] + 0.15 * t; L = GAL_L[i]
        for s_ in (-1.0, -0.5, 0.5, 1.0):
            circ(d, x + s_ * L * math.cos(q), y + s_ * L * math.sin(q) * 0.6, 4.2 - 1.6 * abs(s_), fill=rgba(col, 0.5 * a * k))
        circ(d, x, y, 9, fill=rgba(col, 0.16 * a * k))
        circ(d, x, y, 4.4, fill=rgba(WHITE, a * k))
    if R > 1:
        circ(d, BX, BY, R, fill=rgba(VOID, 0.80 * a))
        for g in range(6):
            circ(d, BX, BY, R + 3 * g, outline=rgba(MAG, 0.20 * a), width=6 + 5 * g)
        circ(d, BX, BY, R, outline=rgba((255, 225, 235), a), width=3.5)
    if CAPTIONS and TB - 1 < T < T5 + 1:
        tm = T - TB
        texts.append((label_sprite("a bubble of new space", POP, 32, MAG), BX, BY - 120, a * ss((tm - 0.5) / 0.5) * (1 - ss((tm - 2.4) / 0.5))))
        ia = a * ss((tm - 3.7) / 0.6)
        texts.append((label_sprite("inside:", POP, 34, WHITE), BX, BY - 60, ia))
        texts.append((label_sprite("new laws of physics", POP, 44, MAG), BX, BY, ia))
        texts.append((label_sprite("no atoms as we know them", POP, 34, WHITE), BX, BY + 62, ia * ss((tm - 5.2) / 0.5)))
        la = a * ss((tm - 2.4) / 0.5)
        texts.append((label_sprite("the wall moves at almost the speed of light", size=28, fill=WHITE), CX, 1436, la))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1484, la))
    if CAPTIONS and T > T7:
        qa = a * ss((T - (DUR - 2.4)) / 0.4)
        texts.append((label_sprite("Would you want a warning?", POP, 44, GOLD), CX, 1468, qa))


def hill(u):
    """Schematic height of the Higgs energy landscape (0..1 across the picture): a ledge, a barrier, a deeper valley."""
    return (0.55 - 0.20 * math.exp(-((u - 0.30) / 0.11) ** 2) + 0.13 * math.exp(-((u - 0.50) / 0.075) ** 2)
            - 0.78 * math.exp(-((u - 0.78) / 0.13) ** 2) + 0.75 * math.exp(-((u + 0.02) / 0.10) ** 2)
            + 0.75 * math.exp(-((u - 1.03) / 0.06) ** 2))


HX0, HX1, HY0, HSC = 70, 890, 1180, 370


def hill_xy(u):
    return HX0 + (HX1 - HX0) * u, HY0 - HSC * hill(u)


HILL = [hill_xy(u) for u in np.linspace(0.035, 0.985, 160)]
U_LEDGE, U_TOP, U_DEEP = 0.303, 0.50, 0.78


def scene_ledge(img, d, T, texts):
    """4-14.5: the Higgs field as a ball on a ledge; it tunnels through the barrier and rolls into the deeper valley."""
    a = win(T, T2, TB + 0.2, 0.4, 0.5)
    if a <= 0.004:
        return
    t = T - T2; t3 = T - T3
    floor = HY0 + 215
    poly(d, HILL + [(HILL[-1][0], floor), (HILL[0][0], floor)], rgba((30, 44, 90), 0.55 * a))
    line(d, HILL, rgba(CYAN, a), 5)
    rb = 24
    go = ss((t3 - 0.9) / 1.3)                       # through the barrier
    roll = ss((t3 - 2.2) / 1.2)                     # down into the deep valley
    u = lerp(lerp(U_LEDGE, 0.60, go), U_DEEP, roll) + (1 - go) * 0.012 * math.sin(7 * t)
    x, y = hill_xy(u)
    if 0 < go < 1:                                  # straight through, not over the top
        y = lerp(hill_xy(U_LEDGE)[1], hill_xy(0.60)[1], go)
    by = y - rb - 2
    ghost = 1 - 0.65 * math.sin(math.pi * go)
    if t3 > 2.2 and roll >= 1:
        by += 5 * math.exp(-(t3 - 3.4) * 2) * math.sin(9 * (t3 - 3.4))
    for g in range(4):
        circ(d, x, by, rb + 5 + 7 * g, fill=rgba(GOLD, 0.07 * a * ghost))
    circ(d, x, by, rb, fill=rgba(GOLD, a * ghost))
    lx, ly = hill_xy(U_LEDGE); tx, ty = hill_xy(U_TOP); dx, dy = hill_xy(U_DEEP)
    if 0 < go < 1 or (t3 > 0.3 and go == 0):
        da = a * ss((t3 - 0.3) / 0.4) * (1 - roll)
        for k in range(9):
            x0 = lx + 34 + k * 26
            line(d, [(x0, ly - rb), (x0 + 13, ly - rb)], rgba(WHITE, 0.6 * da), 3)
    if CAPTIONS:
        pre = a * (1 - ss((t3 - 0.6) / 0.5))
        texts.append((label_sprite("our universe", POP, 34, GOLD), lx - 50, ly - 122, a * ss((t - 0.8) / 0.5) * (1 - ss((t3 - 0.6) / 0.5))))
        texts.append((label_sprite("is here", POP, 30, WHITE), lx - 50, ly - 80, a * ss((t - 0.8) / 0.5) * (1 - ss((t3 - 0.6) / 0.5))))
        texts.append((label_sprite("barrier", size=28, fill=GREY), tx + 40, ty - 40, a * ss((t - 2.2) / 0.5)))
        va = a * ss((t - 3.4) / 0.5)
        texts.append((label_sprite("a deeper valley", POP, 34, MAG), dx - 6, dy + 60, va))
        texts.append((label_sprite("lower energy", size=28, fill=GREY), dx - 6, dy + 104, va))
        texts.append((label_sprite("quantum tunnelling", POP, 34, WHITE), tx - 20, ly - 150, a * ss((t3 - 0.6) / 0.5)))
        texts.append((label_sprite("energy of empty space (the Higgs field)", size=28, fill=WHITE), CX, 1436, a))
        texts.append((label_sprite("illustration, if the Standard Model is the whole story", size=26, fill=GREY), CX, 1484, a))
        del pre


def arc(d, cx, cy, R, y0, y1, col, width, dash=False):
    q0 = math.asin(clamp((y0 - cy) / R, -1, 1)); q1 = math.asin(clamp((y1 - cy) / R, -1, 1))
    qs = np.linspace(q0, q1, 61)
    pts = [(cx + R * math.cos(q), cy + R * math.sin(q)) for q in qs]
    if dash:
        for k in range(0, 60, 3):
            line(d, pts[k:k + 3], col, width)
    else:
        line(d, pts, col, width)


def scene_warning(img, d, T, texts):
    """23-28: the wall and its own light arrive almost together, so there is no warning."""
    a = win(T, T5, T6 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T5
    ex, ey = 700, 1080
    xw = 40 + 150 * t                               # the wall reaches Earth at about t = 4.3
    cx0 = -1500; R = xw - cx0
    for i in range(NST):
        x, y = STR[i]
        if math.hypot(x - cx0, y - ey) > R + 8:
            circ(d, x, y, 2.0, fill=rgba(WHITE, a * (0.45 + 0.3 * math.sin(2.2 * t + STR_P[i]))))
    circ(d, cx0, ey, R, fill=rgba(VOID, 0.85 * a))
    for g in range(6):
        arc(d, cx0, ey, R + 3 * g, -20, 1940, rgba(MAG, 0.20 * a), 6 + 5 * g)
    arc(d, cx0, ey, R, -20, 1940, rgba((255, 225, 235), a), 4)
    arc(d, cx0, ey, R + 34, -20, 1940, rgba(GOLD, 0.9 * a), 3, dash=True)
    hit = ss((xw - (ex - 30)) / 40)
    ea = a * (1 - hit)
    for g in range(4):
        circ(d, ex, ey, 28 + 6 * g, fill=rgba(BLUE, 0.08 * ea))
    circ(d, ex, ey, 26, fill=rgba(BLUE, ea))
    circ(d, ex - 7, ey - 6, 10, fill=rgba((120, 200, 150), 0.9 * ea))
    if hit > 0:
        fl = math.sin(math.pi * clamp((xw - (ex - 30)) / 110))
        for g in range(5):
            circ(d, ex, ey, 40 + 40 * g, fill=rgba(MAG, 0.10 * fl * a))
    if CAPTIONS:
        texts.append((label_sprite("you", POP, 36, WHITE), ex, ey - 78, ea))
        la = a * ss((t - 0.5) / 0.4) * (1 - hit)
        texts.append((label_sprite("the wall", POP, 34, MAG), max(100, xw - 96), 760, la * ss((xw - 170) / 40)))
        texts.append((label_sprite("its light", POP, 34, GOLD), min(840, xw + 118), 1370, la))
        texts.append((label_sprite("its light reaches you just before the wall does", size=28, fill=WHITE), CX, 1436, a))
        texts.append((label_sprite("illustration, not to scale: the gap is exaggerated", size=26, fill=GREY), CX, 1484, a))


ZEROS = "1" + "0" * 139
ROWS = [ZEROS[i:i + 20] for i in range(0, 140, 20)]


def scene_number(img, d, T, texts):
    """28-36: the reassurance, the biggest number in the video: about 10^139 years."""
    a = win(T, T6, T7 + 0.2, 0.4, 0.4)
    if a <= 0.004 or not CAPTIONS:
        return
    t = T - T6
    n = int(140 * ss((t - 0.9) / 4.2) ** 0.8)
    x0, y0, dx, dy = 105, 800, 37, 62
    for r_, row in enumerate(ROWS):
        m = clamp(n - 20 * r_, 0, 20)
        if m <= 0:
            break
        s = row[:int(m)]
        sp = label_sprite(s, POP, 46, GOLD if r_ == 0 and False else WHITE, spacing=37 - 28.5)
        texts.append((sp, x0 + sp.width / (2 * S), y0 + r_ * dy, a))
    ua = a * ss((t - 0.3) / 0.4)
    texts.append((label_sprite("age of the universe so far:", size=28, fill=GREY), CX, 690, ua))
    texts.append((label_sprite("13,800,000,000 years", POP, 36, CYAN), CX, 734, ua))
    fa = a * ss((t - 5.0) / 0.5)
    texts.append((label_sprite("years", POP, 64, GOLD), CX, 1262, fa))
    texts.append((label_sprite("a 1 followed by 139 zeros", POP, 34, WHITE), CX, 1330, fa))
    texts.append((label_sprite("best estimate (2018 calculation, Standard Model only)", size=26, fill=GREY), CX, 1436, fa))
    texts.append((label_sprite("at least a 1 with 58 zeros, at 95% confidence", size=26, fill=GREY), CX, 1484, fa))


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


SCENES = (scene_bubble, scene_ledge, scene_warning, scene_number)


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
        al = win(T, t0 if t0 > 0 else -1.0, t1 if t1 < DUR else DUR + 1, 0.3, 0.25)   # the first caption is there from the first frame
        if al <= 0:
            continue
        rise = (1 - ss((T - t0) / 0.3)) * 16 if t0 > 0 else 0
        if kick:
            put(out, label_sprite(kick, INT, 38, CYAN, spacing=5), 540, 250 + rise, al)
        put(out, caption_sprite(txt), 540, 290 + rise, al, top=True)
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
