#!/usr/bin/env python3
"""Bell's theorem told with a pair of gloves. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 bell_gloves.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 bell_gloves.py render 0 28.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 35.0            # layout units; output is W*S x H*S
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
    (0.0, 2.6, None, "Einstein was sure. | *He was wrong.*"),
    (2.6, 8.4, None, "Open one box: *left.* | So the other is *right.*"),
    (8.4, 12.4, "EINSTEIN, 1935", "Particles are like gloves: | *the answer is inside.*"),
    (12.4, 16.0, "QUANTUM PHYSICS", "*No answer* inside. | Not until you look."),
    (16.0, 20.4, "JOHN BELL, 1964", "Packed answers can | *never break this limit.*"),
    (20.4, 24.0, None, "Nature *breaks the limit.* | Again and again."),
    (24.0, 28.2, "NOBEL PRIZE IN PHYSICS 2022", "*Not left. Not right.* | Until the box is opened."),
    (28.2, 34.6, "EINSTEIN'S QUESTION", "Is the Moon there | *when nobody looks?*"),
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
BOXC = (150, 215, 255)
LEFTC, RIGHTC = GOLD, CYAN


def glove(d, cx, cy, s, col, a, left=True):
    """A simple mitten-style glove: palm, four fingers, thumb. left=True puts the thumb on the right-hand side."""
    if a <= 0:
        return
    c = rgba(col, a)
    m = 1 if left else -1
    rect(d, cx - 46 * s, cy - 10 * s, cx + 46 * s, cy + 70 * s, fill=c)
    circ(d, cx - 30 * s, cy + 70 * s, 16 * s, fill=c); circ(d, cx + 30 * s, cy + 70 * s, 16 * s, fill=c)
    rect(d, cx - 30 * s, cy + 60 * s, cx + 30 * s, cy + 86 * s, fill=c)
    for k, top in enumerate((-72, -92, -86, -64)):
        x = cx + (-34.5 + 23 * k) * s
        line(d, [(x, cy), (x, cy + top * s)], c, 20 * s)
        circ(d, x, cy + top * s, 10 * s, fill=c)
    tx0, ty0, tx1, ty1 = cx + m * 44 * s, cy + 40 * s, cx + m * 78 * s, cy - 6 * s
    line(d, [(tx0, ty0), (tx1, ty1)], c, 24 * s)
    circ(d, tx1, ty1, 12 * s, fill=c); circ(d, tx0, ty0, 12 * s, fill=c)
    rect(d, cx - 40 * s, cy + 92 * s, cx + 40 * s, cy + 108 * s, fill=rgba(col, 0.55 * a))


def box(d, cx, cy, a, lid=0.0, hw=125, hh=135, col=BOXC):
    """A box seen from the front; lid = 0 closed .. 1 lifted away."""
    if a <= 0:
        return
    rect(d, cx - hw, cy - hh, cx + hw, cy + hh, fill=rgba(col, 0.10 * a), outline=rgba(col, 0.85 * a), width=4)
    ly = cy - hh - 26 - 70 * lid
    rect(d, cx - hw - 14, ly, cx + hw + 14, ly + 26, fill=rgba(col, 0.30 * a), outline=rgba(col, 0.9 * a), width=4)


def particle(d, x, y, r, col, a):
    circ(d, x, y, r * 1.9, fill=rgba(col, 0.10 * a))
    circ(d, x, y, r, fill=rgba(col, 0.16 * a), outline=rgba(col, 0.9 * a), width=3)


def source(d, x, y, T, a):
    pul = 0.5 + 0.5 * math.sin(7 * T)
    circ(d, x, y, 26 + 8 * pul, fill=rgba(WHITE, 0.15 * a))
    circ(d, x, y, 10, fill=rgba(WHITE, a))


LX, RX = 215, 760          # box / particle positions when far apart (right side kept clear of the Shorts buttons)
MX = (LX + RX) / 2


# ---------- scenes ----------
def scene_hook(img, d, T, texts):
    a = win(T, -1.0, 2.6, 0.2, 0.3)
    if a <= 0:
        return
    cy = 960
    p = ((T + 0.6) * 0.55) % 1.0
    for rep in (0.0, 0.5):
        q = (p + rep) % 1.0
        fa = ss(q / 0.1) * ss((1 - q) / 0.2) * a
        for sgn, col in ((-1, LEFTC), (1, RIGHTC)):
            x = MX + sgn * lerp(40, 330, q)
            line(d, [(MX + sgn * lerp(40, 330, max(0, q - 0.25)), cy), (x - sgn * 70, cy)], rgba(col, 0.5 * fa), 6)
            particle(d, x, cy, 78, col, fa)
            glove(d, x, cy, 0.46, col, fa, left=sgn < 0)
    source(d, MX, cy, T, a)
    texts.append((label_sprite("the answer is already inside", POP, 52, WHITE), MX, 1230, a))
    s = ss((T - 1.1) / 0.35)
    if s > 0:
        line(d, [(MX - 420, 1232), (MX - 420 + 840 * s, 1232)], rgba(RED, a), 10)
    texts.append((label_sprite("WRONG", POP, 110, RED), MX, 1380, ss((T - 1.45) / 0.25) * a))


def scene_gloves(img, d, T, texts):
    a = win(T, 2.6, 8.4, 0.3, 0.3)
    if a <= 0:
        return
    cy = 1040
    apart = ss((T - 4.0) / 1.1)
    xl, xr = lerp(MX - 150, LX, apart), lerp(MX + 150, RX, apart)
    closed = ss((T - 3.3) / 0.5)              # boxes close over the gloves
    openl = ss((T - 5.5) / 0.45)              # left box opens
    knowr = ss((T - 6.7) / 0.5)               # the other one is known without opening
    glove(d, xl, cy, 1.0, LEFTC, a * max(1 - closed, openl), left=True)
    glove(d, xr, cy, 1.0, RIGHTC, a * max(1 - closed, 0.75 * knowr), left=False)
    box(d, xl, cy, a * closed, lid=openl)
    box(d, xr, cy, a * closed)
    if apart > 0:
        g = a * apart
        for k in range(9):
            x = lerp(xl + 160, xr - 160, k / 8)
            circ(d, x, cy, 3, fill=rgba(GREY, 0.6 * g))
        texts.append((label_sprite("far apart", size=30, fill=GREY), MX, cy - 44, g))
    texts.append((label_sprite("LEFT", POP, 54, LEFTC), xl, cy + 215, a * openl))
    texts.append((label_sprite("RIGHT", POP, 54, RIGHTC), xr, cy + 215, a * knowr))
    texts.append((label_sprite("still closed", size=28, fill=GREY), xr, cy + 275, a * knowr))
    texts.append((label_sprite("decided when they were packed", size=34, fill=WHITE), MX, 1420, a * ss((T - 7.1) / 0.4)))


def flying_pair(d, T, t0, a, inner, period=2.0):
    """Two particles leaving a source in opposite directions, again and again."""
    cy = 1040
    source(d, MX, cy, T, a)
    q = ((T - t0) / period) % 1.0
    fa = ss(q / 0.08) * ss((1 - q) / 0.15) * a
    e = 1 - (1 - q) ** 2
    out = []
    for sgn in (-1, 1):
        x = MX + sgn * lerp(30, 300, e)
        line(d, [(MX + sgn * 30, cy), (x - sgn * 70, cy)], rgba(GREY, 0.25 * fa), 3)
        out.append((x, cy, fa, sgn))
    for x, y, fa_, sgn in out:
        inner(x, y, fa_, sgn)


def scene_einstein(img, d, T, texts):
    a = win(T, 8.4, 12.4, 0.3, 0.3)
    if a <= 0:
        return

    def inner(x, y, fa, sgn):
        col = LEFTC if sgn < 0 else RIGHTC
        particle(d, x, y, 92, col, fa)
        glove(d, x, y, 0.55, col, fa, left=sgn < 0)
    flying_pair(d, T, 8.4, a, inner)
    texts.append((label_sprite("entangled particles", size=34, fill=WHITE), MX, 800, a))
    texts.append((label_sprite("Einstein's picture (illustration)", size=30, fill=GREY), MX, 1300, a))


def scene_quantum(img, d, T, texts):
    a = win(T, 12.4, 16.0, 0.3, 0.3)
    if a <= 0:
        return

    def inner(x, y, fa, sgn):
        particle(d, x, y, 92, WHITE, fa)
        fl = 0.5 + 0.5 * math.sin(9 * T + (0 if sgn < 0 else 2.1))
        glove(d, x, y, 0.55, LEFTC, 0.28 * fa * fl, left=True)
        glove(d, x, y, 0.55, RIGHTC, 0.28 * fa * (1 - fl), left=False)
        texts.append((label_sprite("?", POP, 96, WHITE), x, y, fa))
    flying_pair(d, T, 12.4, a, inner)
    texts.append((label_sprite("entangled particles", size=34, fill=WHITE), MX, 800, a))
    texts.append((label_sprite("nothing decided yet (illustration)", size=30, fill=GREY), MX, 1300, a))


GX0, GX1, GBOT, GLIM, GTOP = 230, 550, 1440, 990, 700
GCX = (GX0 + GX1) / 2      # the gauge
BREAK_T = 21.8
_gr = np.random.default_rng(3)
DOTS = [(float(_gr.uniform(GX0 + 30, GX1 - 30)), float(_gr.uniform(0.15, 0.95)), float(_gr.uniform(0, 6.28)),
         float(_gr.uniform(16.4, 19.2))) for _ in range(26)]
SHARDS = [(float(_gr.uniform(GX0 - 60, GX1 + 60)), float(_gr.uniform(-1, 1)), float(_gr.uniform(-1.6, -0.3)),
           float(_gr.uniform(30, 90))) for _ in range(22)]


def gauge_frame(d, a):
    rect(d, GX0, GTOP, GX1, GBOT, fill=rgba(BOXC, 0.05 * a), outline=rgba(GREY, 0.7 * a), width=3)


def scene_bell(img, d, T, texts):
    a = win(T, 16.0, 20.4, 0.3, 0.25)
    if a <= 0:
        return
    gauge_frame(d, a)
    lvl = 0.82 + 0.13 * math.sin(3.1 * T) * math.sin(1.3 * T)          # level hovers, bumps the limit, never passes
    lvl = min(lvl, 0.985) * ss((T - 16.2) / 1.2)
    ytop = lerp(GBOT, GLIM, lvl)
    rect(d, GX0 + 6, ytop, GX1 - 6, GBOT - 4, fill=rgba(CYAN, 0.30 * a))
    for x, f, ph, t0 in DOTS:
        g = ss((T - t0) / 0.3)
        y = lerp(GBOT - 20, GLIM + 16, f) + 10 * math.sin(4 * T + ph)
        circ(d, x, max(y, GLIM + 12), 8, fill=rgba(CYAN, 0.9 * a * g))
    la = ss((T - 17.2) / 0.4) * a
    line(d, [(GX0 - 90, GLIM), (GX1 + 90, GLIM)], rgba(GOLD, la), 8)
    texts.append((label_sprite("THE LIMIT", POP, 46, GOLD), 790, GLIM - 44, la))
    texts.append((label_sprite("answers packed", size=34, fill=CYAN), 770, 1220, a * ss((T - 16.6) / 0.4)))
    texts.append((label_sprite("in advance", size=34, fill=CYAN), 770, 1268, a * ss((T - 16.6) / 0.4)))
    texts.append((label_sprite("schematic", size=28, fill=GREY), GCX, 1478, a))


def scene_break(img, d, T, texts):
    a = win(T, 20.4, 24.0, 0.25, 0.3)
    if a <= 0:
        return
    gauge_frame(d, a)
    dt = T - BREAK_T
    if dt < 0:
        lvl = lerp(0.6, 1.0, ss((T - 20.4) / 0.6))
    else:
        lvl = 1.0 + 0.52 * (1 - math.exp(-dt / 0.22)) + 0.02 * math.sin(6 * T)
    ytop = lerp(GBOT, GLIM, lvl)
    col = CYAN if dt < 0 else GOLD
    rect(d, GX0 + 6, ytop, GX1 - 6, GBOT - 4, fill=rgba(col, (0.30 if dt < 0 else 0.55) * a))
    if dt >= 0:
        rect(d, GX0 + 6, ytop, GX1 - 6, GLIM, fill=rgba(WHITE, 0.35 * a))
        circ(d, GCX, GLIM, 60 + 900 * dt, outline=rgba(WHITE, 0.8 * math.exp(-dt / 0.3) * a), width=6)
        circ(d, GCX, GLIM, min(420, 1500 * dt), fill=rgba(GOLD, 0.35 * math.exp(-dt / 0.3) * a))
        for x, vx, vy, ln in SHARDS:                     # the limit line shatters
            g = math.exp(-dt / 0.45) * a
            px, py = x + vx * 260 * dt, GLIM + vy * 300 * dt + 420 * dt * dt
            line(d, [(px - ln / 2, py - vx * 14), (px + ln / 2, py + vx * 14)], rgba(GOLD, 0.9 * g), 6)
        line(d, [(GX0 - 90, GLIM), (GX1 + 90, GLIM)], rgba(GOLD, 0.35 * a), 3)
        texts.append((label_sprite("the old limit", size=30, fill=GOLD), 780, GLIM + 36, a * ss(dt / 0.5)))
        texts.append((label_sprite("real experiments", POP, 38, WHITE), 770, ytop + 20, a * ss((dt - 0.25) / 0.4)))
        texts.append((label_sprite("since 1972", size=32, fill=GREY), 770, ytop + 72, a * ss((dt - 0.6) / 0.4)))
    else:
        line(d, [(GX0 - 90, GLIM), (GX1 + 90, GLIM)], rgba(GOLD, a), 8)
        texts.append((label_sprite("THE LIMIT", POP, 46, GOLD), 790, GLIM - 44, a))
    texts.append((label_sprite("schematic", size=28, fill=GREY), GCX, 1478, a))


def scene_payoff(img, d, T, texts):
    a = win(T, 24.0, 28.2, 0.3, 0.3)
    if a <= 0:
        return
    cy = 1040
    openl = ss((T - 26.2) / 0.4)
    for x, ph in ((LX, 0.0), (RX, 2.1)):
        op = openl if x == LX else 0.0
        fl = 0.5 + 0.5 * math.sin(8 * T + ph)
        ga = a * (1 - op)
        glove(d, x, cy, 1.0, LEFTC, 0.30 * ga * fl, left=True)
        glove(d, x, cy, 1.0, RIGHTC, 0.30 * ga * (1 - fl), left=False)
        texts.append((label_sprite("?", POP, 130, WHITE), x, cy - 10, ga))
        box(d, x, cy, a, lid=op)
    glove(d, LX, cy, 1.0, LEFTC, a * openl, left=True)
    dt = T - 26.2
    if 0 < dt < 1.2:
        circ(d, LX, cy, 150 + 500 * dt, outline=rgba(WHITE, 0.7 * math.exp(-dt / 0.3) * a), width=5)
    for k in range(9):
        circ(d, lerp(LX + 160, RX - 160, k / 8), cy, 3, fill=rgba(GREY, 0.6 * a))
    texts.append((label_sprite("LEFT", POP, 54, LEFTC), LX, cy + 215, a * openl))
    texts.append((label_sprite("not decided in advance", POP, 44, WHITE), MX, 1400, a * ss((T - 24.6) / 0.4)))
    if CAPTIONS:      # the cover (no captions) puts its footer here instead
        texts.append((label_sprite("illustration", size=28, fill=GREY), MX, 1470, a))


MOONX, MOONY, MOONR = MX, 1020, 240
_mr = np.random.default_rng(21)
CRATERS = [(-90, -70, 52), (70, -110, 34), (40, 60, 62), (-110, 80, 30), (130, 20, 26), (-20, -150, 22), (-40, 150, 28)]
MDOTS = []
while len(MDOTS) < 240:
    _x, _y = _mr.uniform(-1, 1, 2)
    if _x * _x + _y * _y < 1:
        MDOTS.append((float(_x), float(_y), float(_mr.uniform(0, 6.28)), float(_mr.uniform(5, 11)), float(_mr.uniform(0, 1))))
DISSOLVE_T = 31.6


def scene_moon(img, d, T, texts):
    a = win(T, 28.2, 36.0, 0.35, 0.4)
    if a <= 0:
        return
    g = ss((T - DISSOLVE_T) / 1.1)                 # 0 = solid Moon, 1 = a cloud of undecided particles
    rise = (1 - ss((T - 28.2) / 0.9)) * 60
    cx, cy = MOONX, MOONY + rise
    ma = a * (1 - g)
    circ(d, cx, cy, MOONR * 1.25, fill=rgba((200, 210, 235), 0.06 * a))
    circ(d, cx, cy, MOONR, fill=rgba((118, 124, 140), ma))
    for x, y, r in CRATERS:
        circ(d, cx + x, cy + y, r, fill=rgba((82, 88, 104), ma))
        circ(d, cx + x + r * 0.12, cy + y + r * 0.12, r * 0.8, fill=rgba((98, 104, 120), ma))
    if g > 0:
        dt = T - DISSOLVE_T
        circ(d, cx, cy, MOONR + 700 * dt, outline=rgba(WHITE, 0.7 * math.exp(-dt / 0.35) * a), width=5)
        circ(d, cx, cy, MOONR, outline=rgba(GREY, 0.35 * a * g), width=2)
        for x, y, ph, sp, u in MDOTS:
            on = ss((g - 0.6 * u) / 0.4)
            if on <= 0:
                continue
            fl = 0.5 + 0.5 * math.sin(sp * T + ph)
            jx, jy = 16 * g * math.sin(sp * 0.7 * T + ph), 16 * g * math.cos(sp * 0.9 * T + 2 * ph)
            col = tuple(int(lerp(p_, q_, fl)) for p_, q_ in zip(GOLD, CYAN))
            px, py = cx + x * MOONR * (1 + 0.08 * g) + jx, cy + y * MOONR * (1 + 0.08 * g) + jy
            circ(d, px, py, 12, fill=rgba(col, 0.12 * a * on))
            circ(d, px, py, 5, fill=rgba(col, (0.45 + 0.55 * fl) * a * on))
    texts.append((label_sprite("its particles: nothing decided until measured", size=32, fill=WHITE), MX, 1330,
                  a * ss((T - DISSOLVE_T - 0.5) / 0.5)))
    texts.append((label_sprite("so what is real when no one looks?", POP, 48, GOLD), MX, 1412, a * ss((T - 33.0) / 0.5)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), MX, 1478, a))



# ---------- frame ----------
def frame(T):
    global CUR
    img = BG.copy()
    d = CUR = Canvas(img)
    texts = []
    for sc in (scene_hook, scene_gloves, scene_einstein, scene_quantum, scene_bell, scene_break, scene_payoff, scene_moon):
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
