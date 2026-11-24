#!/usr/bin/env python3
"""Where is everybody? The Fermi paradox: the galaxy is old and big enough to be full of aliens, yet we see none.
Three of the best answers: we are too far apart, we have barely looked, or a Great Filter.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 fermi_paradox.py preview 0 6.4 12      -> frame_<t>.png files
  python3 fermi_paradox.py render 0 48.6 out.mp4 -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 48.6            # layout units; output is W*S x H*S
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
    (0.0, 4.0, None, "Where is | *everybody?*"),
    (4.0, 10.2, None, "Hundreds of billions | of stars, *billions* | *of years old.*"),
    (10.2, 16.7, None, "Aliens could cross it | in *10 million years.*"),
    (16.7, 22.4, "FERMI, 1950", "So where are they? | *The Fermi paradox.*"),
    (22.4, 29.7, "ANSWER 1", "We're | *too far apart.*"),
    (29.7, 37.3, "ANSWER 2", "We've | *barely looked.*"),
    (37.3, 44.5, "ANSWER 3", "*The Great Filter.*"),
    (44.5, 48.6, None, "The question | *stays open.*"),
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

# ---------- facts used on screen (sources: NASA (Milky Way: 100-400 billion stars, ~100,000 light-years across;
# on average at least one planet per star); oldest Milky Way stars ~13 billion years; E. M. Jones, "Where is everybody?",
# Los Alamos report LA-10311-MS (1985), on Fermi's 1950 lunch question; Planetary Society "extent of human radio
# broadcasts" (~200 light-years wide); J. T. Wright, S. Kanodia, E. Lubar, Astronomical Journal 156, 260 (2018):
# SETI so far ~ a hot tub of water compared with Earth's oceans; R. Hanson, "The Great Filter" (1996)) ----------
CX, GY = 500, 1060                 # picture centre (the right-hand edge stays clear for the Shorts buttons)
BLUE = (70, 140, 255)
T1, T2, T3, T4, T5, T6, T7, T8 = 0.0, 4.0, 10.2, 16.7, 22.4, 29.7, 37.3, 44.5


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


# ---------- the galaxy: a few thousand stars on two spiral arms plus a bulge, turning (faster near the centre) ----------
_g = np.random.default_rng(5)
NS = 3400
_arm = _g.integers(0, 2, NS)
_r = np.concatenate([np.abs(_g.normal(0, 0.12, 500)), _g.uniform(0.1, 1.0, 800) ** 0.7, _g.uniform(0.12, 1.0, NS - 1300) ** 0.8])
_th = np.where(np.arange(NS) < 1300, _g.uniform(0, 2 * np.pi, NS),
               _arm * np.pi + 3.1 * np.log(_r + 0.08) + _g.normal(0, 0.28, NS) * (1.1 - _r))
STAR_R, STAR_TH = _r, _th
STAR_B = np.where(np.arange(NS) < 1300, _g.uniform(0.2, 0.6, NS), _g.uniform(0.35, 1.0, NS))
STAR_B[:500] = _g.uniform(0.5, 1.0, 500)
STAR_C = np.where(_r < 0.22, 1, np.where(_g.uniform(0, 1, NS) < 0.25, 2, 0))   # 0 bluish white, 1 warm, 2 pale
STAR_PH = _g.uniform(0, 6.283, NS)
SUN_I = int(np.argmin(np.abs(_r - 0.55) + 0.4 * np.abs(np.cos(_th - 0.7))))     # a star partway out: "us"
COLS = [(200, 215, 255), (255, 214, 150), (235, 235, 245)]
ORIGIN_I = int(np.argmin(np.abs(_r - 0.7) + 0.4 * np.abs(np.cos(_th + 2.2))))    # where the spreading civilization starts


def galaxy_xy(T, cx, cy, size, tilt=0.55, spin=0.05):
    th = STAR_TH + spin * T / (0.25 + STAR_R)
    return cx + size * STAR_R * np.cos(th), cy + size * tilt * STAR_R * np.sin(th)


def galaxy(d, T, a, cx=CX, cy=GY, size=470, tilt=0.55, tint=None, dim=1.0):
    """tint(i) -> optional (colour, strength) per star"""
    if a <= 0.004:
        return None
    X, Y = galaxy_xy(T, cx, cy, size, tilt)
    for k in range(10):                                   # soft glow of the bulge
        circ(d, cx, cy, size * (0.30 - 0.025 * k), fill=rgba((255, 200, 140), 0.035 * a * dim))
    tw = 0.75 + 0.25 * np.sin(3.0 * T + STAR_PH)
    for i in range(NS):
        al = a * dim * STAR_B[i] * tw[i]
        c = COLS[STAR_C[i]]
        if tint is not None:
            tc, ts = tint(i)
            if ts > 0:
                c = lerp3(c, tc, ts); al = max(al, a * ts)
        circ(d, X[i], Y[i], 1.6 + 1.6 * STAR_B[i], fill=rgba(c, al))
    return X, Y


# ---------- scenes ----------
def scene_galaxy(img, d, T, texts):
    """0-10 and again at the end (so the Short loops): the Milky Way, turning; then its numbers."""
    a = win(T, -1.0, T3 + 0.5, 0.2, 0.5) + win(T, T8 - 0.3, DUR + 2, 0.8, 0.3)
    if a <= 0.004:
        return
    end = T > 20
    X, Y = galaxy(d, T - DUR if end else T, a)              # at the very end it is turned exactly as at the start
    if not end:                                           # scene 1: question marks blink on random stars, unanswered
        for k in range(7):
            ph = (0.6 * T + k / 7) % 1.0
            i = int((k * 977 + int(0.6 * T + k / 7) * 331) % NS)
            qa = a * math.sin(math.pi * ph) * (1 - ss((T - T2) / 0.5))
            if qa > 0.02 and CAPTIONS:
                texts.append((label_sprite("?", POP, 40, CYAN), X[i], Y[i] - 26, qa))
    g = ss((T - T2 - 0.2) / 0.5) * (1 - ss((T - T3 + 0.2) / 0.4)) if not end else 0
    if g > 0 and CAPTIONS:                                # scene 2: the numbers
        texts.append((label_sprite("hundreds of billions of stars", POP, 40, WHITE), CX, 1380, a * g))
        tb = ss((T - T2 - 2.2) / 0.5)
        texts.append((label_sprite("most with planets · over 10 billion years old", POP, 34, CYAN), CX, 1432, a * g * tb))
        for k, i in enumerate((SUN_I, ORIGIN_I, 123, 1777, 911)):      # a few stars get little orbiting planets
            pa = a * g * ss((T - T2 - 0.6 - 0.3 * k) / 0.4)
            for m in range(2):
                ang = (1.6 - 0.5 * m) * T + k + 2 * m
                rr = 13 + 9 * m
                circ(d, X[i], Y[i], rr, outline=rgba(GREY, 0.35 * pa), width=1)
                circ(d, X[i] + rr * math.cos(ang), Y[i] + rr * 0.6 * math.sin(ang), 2.6, fill=rgba(CYAN, pa))
    if end and CAPTIONS:                                  # closing question (last ~2.5 s)
        qa = a * ss((T - (DUR - 2.6)) / 0.4)
        texts.append((label_sprite("Which answer is right:", POP, 44, GOLD), CX, 1410, qa))
        texts.append((label_sprite("1, 2 or 3?", POP, 44, GOLD), CX, 1466, qa))


def scene_spread(img, d, T, texts):
    """10-17: one civilization spreading star to star at 1% of light speed fills the galaxy in ~10 million years."""
    a = win(T, T3, T4 + 0.4, 0.5, 0.5)
    if a <= 0.004:
        return
    X0, Y0 = galaxy_xy(T, CX, GY, 470)
    ox, oy = X0[ORIGIN_I], Y0[ORIGIN_I]
    p = ss((T - T3 - 0.6) / (T4 - T3 - 1.6))              # progress 0..1
    front = 1000 * p                                      # radius of the settled region (layout units, flattened view)

    def tint(i):
        dd = math.hypot(X0[i] - ox, (Y0[i] - oy) / 0.55)
        if dd < front:
            return CYAN, 0.85
        return CYAN, 0.0
    galaxy(d, T, a, tint=tint)
    if 0 < p < 1:
        circ(d, ox, oy, max(1, front * 0.5), outline=rgba(CYAN, 0.25 * a * (1 - p)), width=2)
    circ(d, ox, oy, 7, fill=rgba(WHITE, a))
    if CAPTIONS:
        my = int(round(10 * p))
        texts.append((label_sprite(f"{my} million years", POP, 52, CYAN if my < 10 else GOLD), CX, 1395, a))
        texts.append((label_sprite("travelling at 1% of light speed · illustration", size=28, fill=GREY), CX, 1450, a))


def scene_silent(img, d, T, texts):
    """17-22: the real galaxy: our Sun calls out, and nothing answers."""
    a = win(T, T4, T5 + 0.3, 0.5, 0.4)
    if a <= 0.004:
        return
    X, Y = galaxy(d, T, a, dim=0.75)
    sx, sy = X[SUN_I], Y[SUN_I]
    for k in range(4):                                    # our call going out
        f = ((T - T4) * 0.55 + k / 4) % 1.0
        circ(d, sx, sy, 8 + 300 * f, outline=rgba(CYAN, 0.6 * (1 - f) * a), width=2.5)
    circ(d, sx, sy, 7, fill=rgba(GOLD, a))
    if CAPTIONS:
        texts.append((label_sprite("us", POP, 34, GOLD), sx, sy + 34, a))
        texts.append((label_sprite("no answer. no visitors. nothing.", POP, 38, WHITE), CX, 1420, a * ss((T - T4 - 1.5) / 0.5)))


def scene_far(img, d, T, texts):
    """22-30: answer 1: our radio bubble is far smaller than one dot on this map."""
    a = win(T, T5, T6 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    X, Y = galaxy(d, T, a, dim=0.8)
    sx, sy = X[SUN_I], Y[SUN_I]
    z = ss((T - T5 - 1.0) / 0.8)
    for k in range(3):
        f = (0.8 * T + k / 3) % 1.0
        circ(d, sx, sy, 6 + 22 * f, outline=rgba(GOLD, 0.8 * (1 - f) * a), width=2)
    circ(d, sx, sy, 4, fill=rgba(GOLD, a))
    if z > 0:                                             # a magnifier: the bubble shown big, galaxy scale beside it
        bx, by = 760, 760
        line(d, [(sx, sy), (bx - 120, by + 60)], rgba(GOLD, 0.5 * a * z), 2)
        circ(d, bx, by, 120, fill=rgba((10, 14, 34), 0.92 * a * z), outline=rgba(GOLD, 0.8 * a * z), width=3)
        for k in range(5):
            f = (0.5 * T + k / 5) % 1.0
            circ(d, bx, by, 8 + 100 * f, outline=rgba(CYAN, 0.7 * (1 - f) * a * z), width=2)
        circ(d, bx, by, 6, fill=rgba(GOLD, a * z))
        if CAPTIONS:
            texts.append((label_sprite("our radio signals", POP, 30, CYAN), bx, by + 150, a * z))
            texts.append((label_sprite("~200 light-years wide", POP, 30, CYAN), bx, by + 188, a * z))
    if CAPTIONS:
        sa = a * ss((T - T5 - 2.5) / 0.5)
        line(d, [(CX - 430, 1500), (CX + 430, 1500)], rgba(GREY, 0.8 * sa), 2)
        for x in (CX - 430, CX + 430):
            line(d, [(x, 1490), (x, 1510)], rgba(GREY, 0.8 * sa), 2)
        texts.append((label_sprite("the galaxy: ~100,000 light-years", POP, 34, WHITE), CX, 1460, sa))
        texts.append((label_sprite("to scale, the bubble is smaller than the dot marking us", size=26, fill=GREY), CX, 1395, sa))


def scene_looked(img, d, T, texts):
    """30-37: answer 2: everything searched so far vs all there is to search: a hot tub against the oceans."""
    a = win(T, T6, T7 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    top = 820
    for k in range(26):                                   # the ocean: layered water, waves on top
        f = k / 25
        rect(d, 60, top + 26 * k, 940, top + 26 * (k + 1) + 0.6, fill=rgba(lerp3((40, 120, 210), (6, 24, 70), f), a))
    pts = [(x, top - 8 + 7 * math.sin(0.025 * x + 2.2 * T) + 4 * math.sin(0.061 * x - 3.1 * T)) for x in range(60, 941, 10)]
    for k in range(len(pts) - 1):
        line(d, [pts[k], pts[k + 1]], rgba((170, 220, 255), 0.9 * a), 4)
    for j in range(1, 9):                                 # slow swells inside the water
        yj = top + 70 * j
        pj = [(x, yj + 5 * math.sin(0.018 * x + 1.3 * T + j)) for x in range(70, 931, 20)]
        line(d, pj, rgba((150, 210, 255), 0.10 * a), 2)
    tz = ss((T - T6 - 1.5) / 0.6)                         # the hot tub, dropped in for comparison
    tx, ty = 300, 735
    if tz > 0:
        rect(d, tx - 44, ty - 26, tx + 44, ty + 26, fill=rgba((230, 235, 245), a * tz), outline=rgba(WHITE, a * tz), width=2)
        rect(d, tx - 36, ty - 18, tx + 36, ty + 4, fill=rgba((80, 170, 240), a * tz))
        for k in range(3):
            bx = tx - 24 + 24 * k; by = ty - 20 - ((1.5 * T + 0.3 * k) % 1.0) * 26
            circ(d, bx, by, 3, outline=rgba(WHITE, 0.7 * a * tz), width=1.5)
        if CAPTIONS:
            texts.append((label_sprite("searched so far", POP, 34, WHITE), tx + 210, ty - 4, a * tz))
            texts.append((label_sprite("all of Earth's oceans: everything there is to search", POP, 32, WHITE), CX, 1430, a * tz))
            texts.append((label_sprite("not to scale · estimate from 2018", size=26, fill=GREY), CX, 1480, a * tz))


STEPS = ["life", "complex life", "intelligence", "technology", "the stars"]


def scene_filter(img, d, T, texts):
    """37-45: answer 3: the Great Filter. A path of steps; a wall somewhere on it; we don't know where."""
    a = win(T, T7, T8 + 0.3, 0.4, 0.5)
    if a <= 0.004:
        return
    y0 = 1150
    xs = [120 + 190 * k for k in range(5)]
    for k in range(4):
        line(d, [(xs[k] + 36, y0), (xs[k + 1] - 36, y0)], rgba(GREY, 0.6 * a), 4)
    for k, (x, name) in enumerate(zip(xs, STEPS)):
        sa = a * ss((T - T7 - 0.2 - 0.25 * k) / 0.35)
        circ(d, x, y0, 32, fill=rgba((20, 26, 48), sa), outline=rgba(CYAN if k < 4 else GOLD, sa), width=4)
        if CAPTIONS:
            texts.append((label_sprite(name, POP, 32, WHITE), x, y0 + 66 + (34 if k % 2 else 0), sa))
    # "we are here", walking from life to technology
    wp = ss((T - T7 - 1.0) / 2.0) * 3
    wx = lerp(xs[int(min(wp, 2.999))], xs[int(min(wp, 2.999)) + 1], wp - int(min(wp, 2.999)))
    circ(d, wx, y0, 16, fill=rgba(GOLD, a))
    if CAPTIONS:
        texts.append((label_sprite("we are here", POP, 32, GOLD), wx, y0 - 62, a * ss((T - T7 - 1.0) / 0.4)))
    # the filter: a glowing wall that slides between "behind us" and "ahead of us"
    fa = a * ss((T - T7 - 1.8) / 0.5)
    if fa > 0.004:
        u = 0.5 + 0.5 * math.sin(1.1 * (T - T7 - 1.8) - 1.57)       # 0 -> behind, 1 -> ahead
        fx = lerp((xs[1] + xs[2]) / 2, (xs[3] + xs[4]) / 2, u)
        for k in range(10):
            rect(d, fx - 14 + 2.8 * k, 860, fx - 11 + 2.8 * k, 1110, fill=rgba((255, 90, 90), 0.08 * fa))
        rect(d, fx - 5, 860, fx + 5, 1110, fill=rgba((255, 110, 110), 0.95 * fa))
        if CAPTIONS:
            texts.append((label_sprite("the Great Filter", POP, 42, (255, 120, 120)), fx, 815, fa))
            texts.append((label_sprite("behind us, or ahead of us?", POP, 36, WHITE), CX, 1410, fa))
            texts.append((label_sprite("an idea, not a measurement", size=26, fill=GREY), CX, 1460, fa))


SCENES = (scene_galaxy, scene_spread, scene_silent, scene_far, scene_looked, scene_filter)


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
