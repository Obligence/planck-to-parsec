#!/usr/bin/env python3
"""Given enough time, hydrogen starts to wonder where it came from: the Big Bang made almost only hydrogen and helium,
stars fused it into the atoms of life, and about 6 in 10 atoms in a human body are still hydrogen.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 hydrogen_wonders.py preview 0 6.4 12      -> frame_<t>.png files
  python3 hydrogen_wonders.py render 0 43 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 43.0            # layout units; output is W*S x H*S
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
    (0.0, 3.5, None, "Given time, *hydrogen* | starts to *wonder.*"),
    (3.5, 10.0, "13.8 BILLION YEARS AGO", "The Big Bang made | almost only *hydrogen.*"),
    (10.0, 16.5, None, "Gravity lit | the *first stars.*"),
    (16.5, 23.0, "INSIDE STARS", "Hydrogen became | *carbon* and *oxygen.*"),
    (23.0, 30.0, None, "Dying stars | *scattered* them."),
    (30.0, 37.0, "TODAY", "*6 in 10* of your atoms | are *hydrogen.*"),
    (37.0, 43.0, None, "You are that gas, | *looking up.*"),
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

# ---------- facts used on screen (sources: NASA Science, "Universe overview" (around 13.8 billion years ago; in the
# first minutes nucleosynthesis made hydrogen, helium and traces of lithium and beryllium; "for the next 200 million
# years the universe remained dark"); HyperPhysics (Georgia State University), "Big Bang Nucleosynthesis" (hydrogen
# about 73 to 75% and helium about 25% of ordinary matter by mass); "Composition of the human body" (hydrogen is
# about 62% of the body's atoms and about 10% of its mass). The saying "hydrogen is a light, odorless gas which,
# given enough time, turns into people" is often credited to the cosmologist Edward R. Harrison, but the attribution
# is unverified, so the video names nobody.) ----------
def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


CX = 470                           # picture centre (the right-hand edge stays clear for the Shorts buttons)
FX = CX - 110                      # the figure stands a little left, leaving room for labels
T1, T2, T3, T4, T5, T6, T7 = 0.0, 3.5, 10.0, 16.5, 23.0, 30.0, 37.0
OXY = (255, 120, 110)
BLUE = (70, 140, 255)
_r = np.random.default_rng(11)


# ----- the figure: an original, faceless person drawn as a cloud of atoms -----
def _fig_points(n):
    top = 760
    parts = [("disc", FX, top + 55, 52, 0, 0, 0, 0.15),
             ("seg", FX, top + 118, FX, top + 400, 44, 0, 0.35),
             ("seg", FX - 34, top + 135, FX - 118, top + 385, 17, 0, 0.10),
             ("seg", FX + 34, top + 135, FX + 118, top + 385, 17, 0, 0.10),
             ("seg", FX - 20, top + 400, FX - 58, top + 648, 22, 0, 0.15),
             ("seg", FX + 20, top + 400, FX + 58, top + 648, 22, 0, 0.15)]
    pts = []
    for kind, x0, y0, x1, y1, th, _, wgt in parts:
        m = int(round(n * wgt))
        if kind == "disc":
            rr = x1 * np.sqrt(_r.random(m)); q = _r.uniform(0, 2 * math.pi, m)
            pts += list(zip(x0 + rr * np.cos(q), y0 + rr * np.sin(q)))
        else:
            u = _r.random(m); off = _r.uniform(-1, 1, m) * th
            dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy)
            pts += list(zip(x0 + dx * u - dy / L * off, y0 + dy * u + dx / L * off))
    return np.array(pts)


FIG = _fig_points(1100)
NF = len(FIG)
FHYD = _r.random(NF) < 0.62                        # about 62% of the body's atoms are hydrogen
FSCAT = np.stack([_r.uniform(60, 900, NF), _r.uniform(680, 1480, NF)], axis=1)
FPH = _r.uniform(0, 6.283, NF)
FDEL = _r.uniform(0, 0.45, NF)


def figure(d, t, a, form=1.0, dim_other=1.0):
    if a <= 0.004:
        return
    for i in range(NF):
        f = ss((form - FDEL[i]) / 0.55)
        x = lerp(FSCAT[i, 0], FIG[i, 0], f) + 2.2 * math.sin(1.7 * t + FPH[i])
        y = lerp(FSCAT[i, 1], FIG[i, 1], f) + 2.2 * math.cos(1.3 * t + FPH[i] * 1.7)
        tw = 0.7 + 0.3 * math.sin(2.6 * t + FPH[i] * 3)
        if FHYD[i]:
            circ(d, x, y, 3.6, fill=rgba(CYAN, a * tw))
        else:
            circ(d, x, y, 3.6, fill=rgba(GREY, a * tw * 0.55 * dim_other))
    line(d, [(FX - 200, 1424), (FX + 200, 1424)], rgba(GREY, 0.45 * a * ss(form)), 3)


def h_atom(d, x, y, r, ph, a):
    """A hydrogen atom, schematic: one proton, one electron on a ring."""
    circ(d, x, y, r, outline=rgba(CYAN, 0.45 * a), width=2)
    circ(d, x, y, r * 0.42, fill=rgba(CYAN, 0.10 * a))
    circ(d, x, y, 7, fill=rgba(GOLD, a))
    circ(d, x + r * math.cos(ph), y + r * math.sin(ph), 5, fill=rgba(CYAN, a))


ATOMS = [(700, 800, 46, 0.0), (850, 1010, 34, 2.0), (690, 1190, 40, 4.1), (840, 1350, 30, 1.2), (130, 900, 30, 3.0), (110, 1250, 36, 5.2)]


def scene_person(img, d, T, texts):
    """0-3.5 and again from 30 to the end (so the Short loops): a person made of atoms, mostly hydrogen, wondering."""
    a = win(T, -1.0, T2 + 0.4, 0.2, 0.4) + win(T, T6, DUR + 2, 0.4, 0.3)
    if a <= 0.004:
        return
    late = T > 20
    t = T - DUR if late else T                      # at the very end everything stands exactly as at the start
    form = (T - T6) / 1.6 if late else 2.0          # at 30 s the atoms gather into the person
    figure(d, t, a, form=form)
    wa = a * (ss((T - T7) / 0.6) if late else 1.0)  # the "wondering" part: drifting hydrogen atoms and a question mark
    for k, (x, y, r, ph) in enumerate(ATOMS):
        xx = x + 16 * math.sin(0.9 * t + ph); yy = y + 14 * math.cos(0.7 * t + 2 * ph)
        h_atom(d, xx, yy, r, ph + (2.4 + 0.3 * k) * t, wa)
    if CAPTIONS:
        qy = 705 + 6 * math.sin(2.2 * t)
        texts.append((label_sprite("?", POP, 96, GOLD), FX + 6, qy, wa * (0.8 + 0.2 * math.sin(3.0 * t))))
        texts.append((label_sprite("hydrogen", POP, 30, CYAN), 705, 878, wa))
        if late:
            la = a * ss((T - T6 - 1.5) / 0.5) * (1 - ss((T - T7 + 0.3) / 0.4))
            texts.append((label_sprite("≈ 62%", POP, 92, CYAN), 760, 930, la))
            texts.append((label_sprite("of your atoms", POP, 36, WHITE), 760, 1015, la))
            texts.append((label_sprite("are hydrogen", POP, 36, CYAN), 760, 1062, la))
            texts.append((label_sprite("≈ 10% of your mass", size=26, fill=GREY), 760, 1125, la))
            texts.append((label_sprite("almost all of it", POP, 30, GOLD), 760, 1230, la * ss((T - T6 - 3.6) / 0.5)))
            texts.append((label_sprite("from the Big Bang", POP, 30, GOLD), 760, 1272, la * ss((T - T6 - 3.6) / 0.5)))
            qa = a * ss((T - (DUR - 2.6)) / 0.4)
            texts.append((label_sprite("So how old are you,", POP, 42, GOLD), CX, 1468, qa))
            texts.append((label_sprite("really?", POP, 42, GOLD), CX, 1518, qa))


NB = 520
BANG_Q = _r.uniform(0, 2 * math.pi, NB); BANG_S = 0.06 + 0.94 * np.sqrt(_r.random(NB)); BANG_HE = _r.random(NB) < 1 / 13
BANG_P = _r.uniform(0, 6.283, NB)


def scene_bang(img, d, T, texts):
    """3.5-10: the Big Bang leaves a cloud that is almost all hydrogen, with some helium."""
    a = win(T, T2, T3 + 0.3, 0.3, 0.4)
    if a <= 0.004:
        return
    t = T - T2
    cx, cy = CX, 1000
    fl = clamp(1 - t / 1.1)
    if fl > 0:
        for k in range(8):
            circ(d, cx, cy, 40 + 500 * (t / 1.1) * (k + 1) / 8, fill=rgba(WHITE, 0.10 * fl * a))
    R = 330 * (1 - math.exp(-t / 1.5)) + 6 * t
    for i in range(NB):
        rr = R * BANG_S[i]; q = BANG_Q[i] + 0.05 * t
        x = cx + rr * math.cos(q) * 1.15; y = cy + rr * math.sin(q)
        tw = 0.65 + 0.35 * math.sin(3 * t + BANG_P[i])
        if BANG_HE[i]:
            circ(d, x, y, 5.5, fill=rgba(GOLD, a * tw))
        else:
            circ(d, x, y, 3.6, fill=rgba(CYAN, a * tw))
    ba = a * ss((t - 2.0) / 0.5)
    x0, x1, y = CX - 380, CX + 380, 1432
    p = ss((t - 2.0) / 1.2)
    xm = x0 + 0.75 * (x1 - x0)
    rect(d, x0, y - 13, lerp(x0, xm, p), y + 13, fill=rgba(CYAN, 0.9 * ba))
    rect(d, xm + 4, y - 13, lerp(xm + 4, x1, p), y + 13, fill=rgba(GOLD, 0.9 * ba))
    if CAPTIONS:
        texts.append((label_sprite("hydrogen ≈ 75%", POP, 34, CYAN), x0 + 200, y - 48, ba))
        texts.append((label_sprite("helium ≈ 25%", POP, 34, GOLD), x1 - 125, y - 48, ba))
        texts.append((label_sprite("ordinary matter after the first minutes, by mass", size=26, fill=GREY), CX, y + 44, ba))


NG = 520
GAS0 = np.stack([CX + 430 * (_r.random(NG) - 0.5) * 2, 1040 + 330 * (_r.random(NG) - 0.5) * 2], axis=1)
CLUMPS = [(CX - 230, 900), (CX + 190, 1010), (CX - 60, 1270)]
GAS_C = _r.integers(0, 3, NG); GAS_OFF = _r.normal(0, 1, (NG, 2)); GAS_P = _r.uniform(0, 6.283, NG)
GAS_C = np.array([int(np.argmin([(GAS0[i, 0] - c[0]) ** 2 + (GAS0[i, 1] - c[1]) ** 2 for c in CLUMPS])) for i in range(NG)])


def star(d, x, y, r, a, T, col=(255, 236, 190)):
    if a <= 0.004:
        return
    fl = 1 + 0.05 * math.sin(5 * T + x)
    for k in range(9):
        circ(d, x, y, r * fl * (1 + 0.32 * k), fill=rgba(col, 0.085 * a))
    circ(d, x, y, r * 0.78, fill=rgba(WHITE, a))


def scene_stars(img, d, T, texts):
    """10-16.5: gravity pulls the gas into clumps, and the first stars switch on."""
    a = win(T, T3, T4 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T3
    p = ss(t / 3.6)
    for i in range(NG):
        c = CLUMPS[GAS_C[i]]
        sp = 1 - 0.86 * p
        x = lerp(GAS0[i, 0], c[0], p) + GAS_OFF[i, 0] * 26 * (1 - sp) * 0 + (GAS0[i, 0] - c[0]) * 0.0 + 14 * GAS_OFF[i, 0] * p
        y = lerp(GAS0[i, 1], c[1], p) + 14 * GAS_OFF[i, 1] * p
        q = 0.5 * p * t + GAS_P[i] * 0
        dx, dy = x - c[0], y - c[1]
        x = c[0] + dx * math.cos(q) - dy * math.sin(q); y = c[1] + dx * math.sin(q) + dy * math.cos(q)
        tw = 0.65 + 0.35 * math.sin(3 * t + GAS_P[i])
        circ(d, x, y, 3.4, fill=rgba(CYAN, a * tw * (1 - 0.45 * ss((t - 3.4) / 1.5))))
    for k, c in enumerate(CLUMPS):
        star(d, c[0], c[1], (44, 36, 40)[k], a * ss((t - 3.0 - 0.45 * k) / 0.6), T)
    if CAPTIONS:
        la = a * ss((t - 3.6) / 0.5)
        texts.append((label_sprite("first stars", POP, 36, GOLD), CLUMPS[1][0] + 30, CLUMPS[1][1] + 105, la))
        texts.append((label_sprite("after about 200 million years of darkness", size=28, fill=GREY), CX, 1452, la))
        texts.append((label_sprite("hydrogen gas", POP, 32, CYAN), CX + 150, 720, a * (1 - ss((t - 2.2) / 0.6))))


NS = 160
SW_R = np.sqrt(_r.random(NS)); SW_Q = _r.uniform(0, 6.283, NS); SW_W = _r.uniform(0.25, 0.8, NS)


def scene_fusion(img, d, T, texts):
    """16.5-23: inside a star, hydrogen is fused step by step into heavier atoms."""
    a = win(T, T4, T5 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T4
    cx, cy, R = CX, 1050, 335
    pul = 1 + 0.012 * math.sin(3 * T)
    for k in range(8):
        circ(d, cx, cy, R * pul + 10 + 16 * k, fill=rgba((255, 150, 60), 0.035 * a))
    circ(d, cx, cy, R * pul, fill=rgba((92, 40, 18), 0.92 * a), outline=rgba((255, 170, 80), a), width=4)
    circ(d, cx, cy, R * 0.72, fill=rgba((140, 62, 22), 0.55 * a))
    for i in range(NS):
        q = SW_Q[i] + SW_W[i] * t; rr = R * 0.93 * SW_R[i]
        circ(d, cx + rr * math.cos(q), cy + rr * math.sin(q), 3.2, fill=rgba(CYAN, 0.55 * a))
    xs = (cx - 252, cx - 100, cx + 68, cx + 246)
    rs = (24, 34, 46, 54)
    cols = (CYAN, (225, 230, 245), GOLD, OXY)
    names = ("H", "He", "C", "O")
    full = ("hydrogen", "helium", "carbon", "oxygen")
    for k in range(4):
        ka = a * ss((t - 0.5 - 1.05 * k) / 0.45)
        pop = 1 + 0.25 * (1 - ss((t - 0.5 - 1.05 * k) / 0.6))
        for g in range(4):
            circ(d, xs[k], cy, rs[k] * pop + 5 + 6 * g, fill=rgba(cols[k], 0.07 * ka))
        circ(d, xs[k], cy, rs[k] * pop, fill=rgba(cols[k], ka))
        if k:
            x0, x1 = xs[k - 1] + rs[k - 1] + 12, xs[k] - rs[k] - 12
            line(d, [(x0, cy), (x1, cy)], rgba(WHITE, 0.85 * ka), 4)
            line(d, [(x1 - 12, cy - 10), (x1, cy), (x1 - 12, cy + 10)], rgba(WHITE, 0.85 * ka), 4)
        if CAPTIONS:
            texts.append((label_sprite(names[k], POP, 30 + 3 * k, (12, 18, 40), stroke=0), xs[k] + 1, cy, ka))
            texts.append((label_sprite(full[k], POP, 28, cols[k]), xs[k], cy + rs[k] + 40, ka))
    if CAPTIONS:
        texts.append((label_sprite("nuclear fusion, step by step", POP, 32, WHITE), CX, cy - 150, a * ss((t - 0.4) / 0.5)))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1452, a))


NE = 420
EX_Q = _r.uniform(0, 2 * math.pi, NE); EX_S = 0.15 + 0.85 * np.sqrt(_r.random(NE)); EX_K = _r.integers(0, 4, NE)
EX_P = _r.uniform(0, 6.283, NE)


def scene_scatter(img, d, T, texts):
    """23-30: a dying star throws its new atoms into space; a new sun and a planet with oceans form from them."""
    a = win(T, T5, T6 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T5
    cx, cy = CX, 1040
    star(d, cx, cy, 70 * (1 + 0.5 * ss(t / 0.9)), a * (1 - ss((t - 0.7) / 0.5)), T, (255, 190, 120))
    R = 400 * (1 - math.exp(-max(0.0, t - 0.8) / 1.3))
    ea = a * ss((t - 0.8) / 0.2) * (1 - 0.6 * ss((t - 3.4) / 1.5))
    cols = (CYAN, CYAN, GOLD, OXY)
    for i in range(NE):
        rr = R * EX_S[i]
        x = cx + rr * math.cos(EX_Q[i]) * 1.1; y = cy + rr * math.sin(EX_Q[i])
        tw = 0.65 + 0.35 * math.sin(3 * t + EX_P[i])
        circ(d, x, y, 3.8 if EX_K[i] < 2 else 5, fill=rgba(cols[EX_K[i]], ea * tw))
    na = a * ss((t - 3.2) / 0.8)
    sx, sy = CX - 40, 1060
    star(d, sx, sy, 44, na, T, (255, 220, 140))
    q = 0.9 * (t - 3.2) + 0.6
    px, py = sx + 310 * math.cos(q), sy + 105 * math.sin(q)
    if na > 0.004:
        pts = [(sx + 310 * math.cos(u), sy + 105 * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 73)]
        line(d, pts, rgba(GREY, 0.35 * na), 2)
        for g in range(4):
            circ(d, px, py, 22 + 5 * g, fill=rgba(BLUE, 0.08 * na))
        circ(d, px, py, 20, fill=rgba(BLUE, na))
        circ(d, px - 5, py - 5, 8, fill=rgba((120, 200, 150), 0.9 * na))
    if CAPTIONS:
        texts.append((label_sprite("carbon, oxygen and more, thrown into space", size=28, fill=GREY), CX, 1452, a * ss((t - 1.2) / 0.5) * (1 - ss((t - 3.2) / 0.5))))
        texts.append((label_sprite("a new sun", POP, 32, GOLD), sx, sy - 105, na))
        texts.append((label_sprite("planets, oceans", POP, 32, BLUE), CX, 1452, na))


SCENES = (scene_person, scene_bang, scene_stars, scene_fusion, scene_scatter)


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
