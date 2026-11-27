#!/usr/bin/env python3
"""Falling into the black hole from the film Interstellar: it is so massive (about 100 million Suns) that its tides
are gentle at the horizon, so you would cross alive and notice nothing; from outside you would seem to freeze at the
edge; inside, the centre lies in your future, and the tides pull you apart within about half an hour at most.
The film is only referred to by name: no footage, characters, music or likenesses.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 interstellar_black_hole.py preview 0 6.4 12      -> frame_<t>.png files
  python3 interstellar_black_hole.py render 0 42 out.mp4   -> renders that time range
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
    (0.0, 4.0, None, "Falling into | *Interstellar's* black hole"),
    (4.0, 10.5, "100 MILLION SUNS", "So big, its pull | is *gentle.*"),
    (10.5, 16.5, None, "You cross the edge | *alive.*"),
    (16.5, 23.0, "SEEN FROM OUTSIDE", "You seem to | *freeze at the edge.*"),
    (23.0, 29.0, "INSIDE", "The centre is | *your future.*"),
    (29.0, 35.5, "WITHIN HALF AN HOUR", "The tides | *tear you apart.*"),
    (35.5, 42.0, None, "The film goes on. | *Physics does not.*"),
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

# ---------- facts used on screen (sources: J.-P. Luminet, "The Warped Science of Interstellar", arXiv:1503.08305:
# the film's black hole "Gargantua" has, according to Kip Thorne (the film's science adviser), about 100 million
# solar masses and spins fast; small black holes tear a traveller apart "well before being able to reach the event
# horizon". NASA Goddard, "New NASA Black Hole Visualization Takes Viewers Beyond the Brink" (6 May 2024):
# stellar-mass black holes "possess much smaller event horizons and stronger tidal forces, which can rip apart
# approaching objects before they get to the horizon", "if you have the choice, you want to fall into a supermassive
# black hole", and to anyone watching from afar the faller "would never quite get there... would slow and then seem
# to freeze just shy of it". Lewis and Kwan, "No Way Back: Maximizing survival time below the Schwarzschild event
# horizon", arXiv:0705.1029: once inside, "your destiny lies at the central singularity, irrespective of what you
# do", and the longest possible time from horizon to singularity is tau = pi*G*M/c^3. For 100 million Suns that is
# pi x 4.925e-6 s x 1e8 = about 1550 s, about 26 minutes (non-spinning black hole). The film is referred to by name
# only: no footage, characters, music or likenesses; the black hole drawn here is our own schematic.) ----------
CX = 470                           # picture centre (the right-hand edge stays clear for the Shorts buttons)
T1, T2, T3, T4, T5, T6, T7 = 0.0, 4.0, 10.5, 16.5, 23.0, 29.0, 35.5
ORANGE = (255, 150, 60)
WARM = (255, 214, 150)
MAG = (255, 70, 130)
_r = np.random.default_rng(31)


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


ND = 170
DK_PH = _r.uniform(0, 6.283, ND); DK_R = _r.uniform(1.45, 2.7, ND); DK_W = _r.uniform(0.5, 1.0, ND)


def bh(d, x, y, r, a, t, disk=True):
    """Our own schematic black hole: a dark disc, a thin bright ring and a tilted ring of orbiting matter."""
    if a <= 0.004:
        return
    pts = []
    if disk:
        for i in range(ND):
            q = DK_PH[i] + DK_W[i] * 1.6 * t / DK_R[i] ** 1.5 * 2.2
            pts.append((x + DK_R[i] * r * math.cos(q), y + DK_R[i] * r * 0.24 * math.sin(q), math.sin(q), i))
        for px, py, sq, i in pts:
            if sq < 0:
                circ(d, px, py, 3.4, fill=rgba(lerp3(ORANGE, WARM, DK_W[i]), 0.75 * a))
    for k in range(8):
        circ(d, x, y, r * (1.05 + 0.07 * k), fill=rgba(ORANGE, 0.05 * a))
    circ(d, x, y, r, fill=(0, 0, 0, int(255 * clamp(a))), outline=rgba(WARM, a), width=3.5)
    for px, py, sq, i in pts:
        if sq >= 0:
            circ(d, px, py, 3.8, fill=rgba(lerp3(ORANGE, WARM, DK_W[i]), 0.9 * a))


def astro(d, x, y, s, a, q=0.0, sy=1.0, sx=1.0, col=WHITE):
    """An original, faceless astronaut. sy / sx stretch it along / across its own axis (spaghettification)."""
    if a <= 0.004:
        return
    cq, sq = math.cos(q), math.sin(q)

    def P(u, v):
        u, v = u * s * sx, v * s * sy
        return x + u * cq - v * sq, y + u * sq + v * cq
    w = 8 * s * sx
    for p0, p1, ww in (((0, -14), (0, 14), 1.9), ((0, -10), (-17, 6), 1.0), ((0, -10), (17, 6), 1.0), ((0, 14), (-9, 42), 1.1), ((0, 14), (9, 42), 1.1)):
        line(d, [P(*p0), P(*p1)], rgba(col, a), max(2.0, w * ww))
    hx, hy = P(0, -30)
    circ(d, hx, hy, 12 * s * max(sx, 0.45), fill=rgba(col, a))
    vx, vy = P(2, -30)
    circ(d, vx, vy, 6.5 * s * max(sx, 0.45), fill=rgba((30, 40, 80), a))


BX, BY, BR = CX, 1200, 150


def scene_fall(img, d, T, texts):
    """0-4 and 35.5-42: the black hole, and a traveller falling towards it (the Short loops here)."""
    a = win(T, -1.0, T2 + 0.3, 0.2, 0.4) + win(T, T7, DUR + 2, 0.5, 0.3)
    if a <= 0.004:
        return
    late = T > 20
    t = T - DUR if late else T
    bh(d, BX, BY, BR, a, t)
    fa = a * (ss((T - (DUR - 1.6)) / 0.8) if late else 1.0)
    astro(d, BX - 40 + 10 * t, 760 + 46 * t, 1.25, fa, q=0.5 + 0.35 * t)
    if CAPTIONS and late:
        na = a * ss((T - T7 - 0.6) / 0.5) * (1 - ss((T - (DUR - 2.9)) / 0.4))
        texts.append((label_sprite("the film's black hole spins, and what lies", size=27, fill=GREY), CX, 1432, na))
        texts.append((label_sprite("inside a spinning one is less certain", size=27, fill=GREY), CX, 1472, na))
        qa = a * ss((T - (DUR - 2.4)) / 0.4)
        texts.append((label_sprite("Would you jump in?", POP, 46, GOLD), CX, 1462, qa))


def scene_tides(img, d, T, texts):
    """4-10.5: a small black hole stretches you apart before the edge; a giant one is gentle there."""
    a = win(T, T2, T3 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T2
    lx, rx = 215, 690
    line(d, [(455, 700), (455, 1400)], rgba(GREY, 0.3 * a), 2)
    # left: a small black hole
    bh(d, lx, 1215, 30, a, t * 2.2, disk=False)
    st = ss((t - 1.0) / 3.2)
    sy = 1 + 3.0 * st; sx = 1 - 0.62 * st
    ay = lerp(790, 960, ss(t / 4.2))
    astro(d, lx, ay, 1.2, a * (1 - 0.75 * ss((t - 4.4) / 0.8)), sy=sy, sx=sx, col=lerp3(WHITE, MAG, st))
    for k in range(5):
        yy = ay - 60 + 22 * k + 6 * math.sin(4 * t + k)
        for sgn in (-1, 1):
            line(d, [(lx + sgn * 62, yy), (lx + sgn * 62, yy + (12 + 5 * k) * st)], rgba(MAG, 0.7 * a * st), 3)
    # right: the giant; only the top of its horizon fits in the picture
    Rg = 520
    for k in range(8):
        circ(d, rx, 1310 + Rg, Rg + 6 + 9 * k, fill=rgba(ORANGE, 0.035 * a))
    circ(d, rx, 1310 + Rg, Rg, fill=(0, 0, 0, int(255 * a)), outline=rgba(WARM, a), width=3.5)
    astro(d, rx, 1090 + 60 * ss(t / 5) + 5 * math.sin(1.5 * t), 1.2, a, q=0.12 * math.sin(0.8 * t))
    if CAPTIONS:
        texts.append((label_sprite("a small black hole", POP, 30, WHITE), lx, 700, a))
        texts.append((label_sprite("the giant in the film", POP, 30, WARM), rx, 700, a))
        texts.append((label_sprite("torn apart", POP, 32, MAG), lx, 1296, a * ss((t - 2.6) / 0.5)))
        texts.append((label_sprite("before the edge", POP, 28, MAG), lx, 1336, a * ss((t - 2.6) / 0.5)))
        texts.append((label_sprite("gentle at the edge", POP, 32, GOLD), rx, 990, a * ss((t - 3.4) / 0.5)))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1484, a))


HX, HY, HR = CX, 1790, 600          # the giant's horizon, seen close up: its top is at y = 1190
HTOP = HY - HR


def horizon(d, a, t, inside_tint=0.0):
    for k in range(8):
        circ(d, HX, HY, HR + 6 + 9 * k, fill=rgba(ORANGE, 0.03 * a))
    circ(d, HX, HY, HR, fill=(0, 0, 0, int(255 * a)))
    n = 80
    for k in range(n):
        q0 = -math.pi / 2 + (k - n / 2) * 0.026 + 0.004 * t
        q1 = q0 + 0.014
        line(d, [(HX + HR * math.cos(q0), HY + HR * math.sin(q0)), (HX + HR * math.cos(q1), HY + HR * math.sin(q1))], rgba(CYAN, a), 4)


def scene_cross(img, d, T, texts):
    """10.5-16.5: you cross the event horizon alive, and nothing marks the spot."""
    a = win(T, T3, T4 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T3
    horizon(d, a, t)
    y = 820 + 95 * t
    astro(d, HX - 20, y, 1.25, a, q=0.3 + 0.25 * t)
    if CAPTIONS:
        texts.append((label_sprite("event horizon", POP, 32, CYAN), HX + 250, HTOP - 12, a))
        ca = a * ss((y - (HTOP - 20)) / 40)
        texts.append((label_sprite("no wall, no flash", POP, 34, GOLD), HX - 250, HTOP + 130, ca))
        texts.append((label_sprite("still alive", POP, 34, WHITE), HX - 250, HTOP + 176, ca))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1484, a))


def scene_outside(img, d, T, texts):
    """16.5-23: seen from far away, the traveller slows down and seems to freeze just outside the horizon."""
    a = win(T, T4, T5 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T4
    horizon(d, a, t)
    prog = 1 - math.exp(-t / 1.25)
    y = lerp(800, HTOP - 62, prog)
    astro(d, HX - 20, y, 1.25, a, q=0.3 + 0.9 * prog)
    sx_, sy_ = 150, 760                                   # the crew's ship: a small original shape
    poly(d, [(sx_ - 34, sy_ + 12), (sx_ + 30, sy_), (sx_ - 34, sy_ - 12)], rgba(GREY, a))
    circ(d, sx_ - 4, sy_, 6, fill=rgba(CYAN, a))
    for k in range(14):
        u0, u1 = k / 14, (k + 0.5) / 14
        line(d, [(lerp(sx_ + 44, HX - 50, u0), lerp(sy_ + 6, y - 20, u0)), (lerp(sx_ + 44, HX - 50, u1), lerp(sy_ + 6, y - 20, u1))], rgba(WHITE, 0.35 * a), 2)
    cx_, cy_, cr = 720, 900, 62                           # the traveller's clock, as the crew sees it
    circ(d, cx_, cy_, cr, fill=rgba((20, 28, 60), 0.9 * a), outline=rgba(WHITE, a), width=4)
    for k in range(12):
        q = k * math.pi / 6
        line(d, [(cx_ + (cr - 10) * math.cos(q), cy_ + (cr - 10) * math.sin(q)), (cx_ + (cr - 3) * math.cos(q), cy_ + (cr - 3) * math.sin(q))], rgba(WHITE, 0.8 * a), 2)
    q = -math.pi / 2 + 5.0 * 1.25 * prog
    line(d, [(cx_, cy_), (cx_ + (cr - 16) * math.cos(q), cy_ + (cr - 16) * math.sin(q))], rgba(GOLD, a), 5)
    circ(d, cx_, cy_, 6, fill=rgba(GOLD, a))
    if CAPTIONS:
        texts.append((label_sprite("your crew", POP, 30, WHITE), sx_ + 10, sy_ - 50, a))
        texts.append((label_sprite("your clock,", size=27, fill=GREY), cx_, cy_ + 96, a))
        texts.append((label_sprite("as they see it", size=27, fill=GREY), cx_, cy_ + 132, a))
        texts.append((label_sprite("event horizon", POP, 32, CYAN), HX + 250, HTOP - 12, a))
        texts.append((label_sprite("frozen, just outside", POP, 34, GOLD), HX - 20, HTOP + 70, a * ss((t - 3.6) / 0.6)))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1484, a))


SX, SY = CX, 1240                   # the singularity, in the two scenes inside the horizon
NA = 14
AR_Q = np.linspace(0, 2 * math.pi, NA, endpoint=False) + 0.2


def inside_bg(d, a):
    rect(d, 0, 0, 1080, 1920, fill=(0, 0, 0, int(200 * a)))
    for k in range(7):
        circ(d, SX, SY, 10 + 9 * k, fill=rgba(WHITE, 0.07 * a))
    circ(d, SX, SY, 7, fill=rgba(WHITE, a))


def scene_inside(img, d, T, texts):
    """23-29: inside the horizon every possible path leads to the centre."""
    a = win(T, T5, T6 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T5
    inside_bg(d, a)
    for i in range(NA):
        for ph in (0.0, 0.5):
            u = ((0.16 * t + ph + i * 0.37) % 1.0)
            r0 = lerp(520, 70, u); r1 = r0 - 46
            q = AR_Q[i]
            al = a * 0.55 * math.sin(math.pi * u)
            x0, y0 = SX + r0 * math.cos(q), SY + r0 * 0.82 * math.sin(q)
            x1, y1 = SX + r1 * math.cos(q), SY + r1 * 0.82 * math.sin(q)
            if 660 < y0 < 1500:
                line(d, [(x0, y0), (x1, y1)], rgba(CYAN, al), 3)
                nx, ny = -(y1 - y0), x1 - x0; L = math.hypot(nx, ny) + 1e-6
                bx, by = lerp(x1, x0, 0.3), lerp(y1, y0, 0.3)
                line(d, [(bx + nx / L * 9, by + ny / L * 9), (x1, y1), (bx - nx / L * 9, by - ny / L * 9)], rgba(CYAN, al), 3)
    ax, ay = SX - 150, 820 + 16 * t
    for k, off in enumerate((-230, -110, 0, 110, 230)):     # five attempts to steer away, all bending to the centre
        pa = a * ss((t - 1.2 - 0.25 * k) / 0.5)
        pts = []
        for u in np.linspace(0, 1, 30):
            mx, my = lerp(ax, SX, 0.5) + off, lerp(ay, SY, 0.45)
            pts.append(((1 - u) ** 2 * ax + 2 * u * (1 - u) * mx + u * u * SX, (1 - u) ** 2 * ay + 2 * u * (1 - u) * my + u * u * SY))
        line(d, pts, rgba(GOLD, 0.8 * pa), 3)
    astro(d, ax, ay, 1.2, a, q=0.2)
    if CAPTIONS:
        texts.append((label_sprite("the centre", POP, 32, WHITE), SX, SY + 60, a * ss((t - 0.6) / 0.5)))
        texts.append((label_sprite("whatever you do", POP, 32, GOLD), SX + 235, 900, a * ss((t - 2.6) / 0.5)))
        texts.append((label_sprite("illustration (non-spinning black hole)", size=26, fill=GREY), CX, 1484, a))


NSP = 60
SP_O = _r.normal(0, 1, NSP)


def scene_spaghetti(img, d, T, texts):
    """29-35.5: the tides grow until they pull the traveller apart, at most about 26 minutes after crossing."""
    a = win(T, T6, T7 + 0.2, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T6
    inside_bg(d, a)
    st = ss((t - 0.4) / 3.4)
    x = SX; y = lerp(790, 1010, ss(t / 4.0))
    sy = 1 + 3.6 * st; sx = 1 - 0.68 * st
    gone = ss((t - 3.9) / 0.9)
    astro(d, x, y, 1.25, a * (1 - gone), sy=sy, sx=sx, col=lerp3(WHITE, MAG, st))
    for i in range(NSP):
        u = clamp((t - 3.7) / 2.0 - 0.012 * i)
        if 0 < u < 1:
            py = lerp(y - 150 + 5 * i, SY, ss(u))
            circ(d, x + SP_O[i] * 9 * (1 - u), py, 3.4, fill=rgba(MAG, a * (1 - u * u)))
    for sgn in (-1, 1):
        for k in range(4):
            yy = y - 90 + 60 * k
            line(d, [(x + sgn * 95, yy), (x + sgn * 95, yy + (10 + 24 * st) * (1 if k > 1 else -1))], rgba(MAG, 0.6 * a * st * (1 - gone)), 3)
    if CAPTIONS:
        la = a * ss((t - 1.0) / 0.5)
        texts.append((label_sprite("the tides stretch you", POP, 32, MAG), 190, 880, la))
        texts.append((label_sprite("head to foot", POP, 28, WHITE), 190, 922, la))
        texts.append((label_sprite("the centre", POP, 32, WHITE), SX, SY + 60, a))
        texts.append((label_sprite("longest possible fall: about 26 minutes", size=28, fill=WHITE), CX, 1436, a))
        texts.append((label_sprite("non-spinning black hole of 100 million Suns", size=26, fill=GREY), CX, 1484, a))


SCENES = (scene_fall, scene_tides, scene_cross, scene_outside, scene_inside, scene_spaghetti)


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
