#!/usr/bin/env python3
"""If Earth were a marble: three scale models, from Earth to the observable universe.
1) Earth = 1 cm marble: the Sun is a 1.1 m ball, 117 m away; Neptune is 3.5 km out.
2) All eight planets' orbits = an 8 cm cup: Earth is 1.3 mm from the Sun; the Milky Way is about 8,400 km (North America).
3) The Milky Way = a 25 cm dinner plate: Andromeda is about 6 m away; the observable universe is about 230 km across.
Every size on screen is computed from the constants in "the scale models" below.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 earth_marble_universe.py preview 0 6.4 12      -> frame_<t>.png files
  python3 earth_marble_universe.py render 0 70 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 74.0            # layout units; output is W*S x H*S
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
    (0.0, 5.0, None, "If Earth were | *this marble...*"),
    (5.0, 12.0, None, "The Sun: a ball | *over a metre wide.*"),
    (12.0, 18.0, None, "And it sits | *117 m away.*"),
    (18.0, 23.0, None, "Neptune, the last planet: | *3.5 km out.*"),
    (23.0, 28.0, None, "Now shrink it all. | Every orbit *in a cup.*"),
    (28.0, 33.0, None, "Earth to Sun: | *barely a millimetre.*"),
    (33.0, 37.0, None, "Your city? | *All of Canada?* | Still too small."),
    (37.0, 45.0, "FROM THE ARCTIC TO PANAMA", "The Milky Way: | *all of North America.*"),
    (45.0, 50.0, None, "Shrink again. | The Milky Way: | *a dinner plate.*"),
    (50.0, 58.0, None, "Andromeda: | a bigger plate, | *6 m away.*"),
    (58.0, 67.5, "ON THE DINNER-PLATE SCALE", "The universe we can see: | *230 km wide.*"),
    (67.5, 74.0, None, "On one plate, in one cup: | *one blue marble.*"),
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

# ---------- the scale models (every number on screen is computed from these) ----------
AU_KM, LY_KM = 149_597_870.7, 9.4607e12
EARTH_KM, SUN_KM = 12_742.0, 1_392_700.0     # NASA: the Sun is about 1.4 million km wide; 1.3 million Earths fill its volume
NEPTUNE_AU = 30.07                           # NASA: Neptune is 30 AU from the Sun
GALAXY_LY = 100_000                          # NASA: the Milky Way is about 100,000 light-years across
ANDROMEDA_LY = 2.5e6                         # NASA: Andromeda is about 2.5 million light-years away
UNIVERSE_LY = 93e9                           # the observable universe is about 93 billion light-years across
# model 1: Earth is a 1 cm marble
SUN_M = SUN_KM / EARTH_KM / 100              # 1.09 m
EARTH_SUN_M = AU_KM / EARTH_KM / 100         # 117 m
NEPTUNE_M = NEPTUNE_AU * EARTH_SUN_M         # 3.5 km
# model 2: Neptune's whole orbit, edge to edge, is an 8 cm cup
CUP_CM = 8.0
EARTH_SUN_MM = CUP_CM * 10 / (2 * NEPTUNE_AU)                       # 1.3 mm
GALAXY_KM = GALAXY_LY * LY_KM / (2 * NEPTUNE_AU * AU_KM) * CUP_CM / 1e5   # about 8,400 km
# model 3: the Milky Way is a 25 cm dinner plate
PLATE_CM = 25.0
ANDROMEDA_M = ANDROMEDA_LY / GALAXY_LY * PLATE_CM / 100             # about 6 m
UNIVERSE_KM = UNIVERSE_LY / GALAXY_LY * PLATE_CM / 1e5              # about 230 km

CX, CY = 500, 1045                       # picture centre (the right-hand edge stays clear for the Shorts buttons)
RIN = 262                                # inner radius of the cup, layout units
PXAU = 250 / NEPTUNE_AU                  # cup scene: Neptune's orbit sits just inside the rim
CUPW, COFFEE = (236, 238, 244), (5, 7, 16)
ORANGE = (255, 140, 50)
PLANETS = [  # name, orbit radius in AU, colour, dot radius (dots are enlarged; orbits are to scale)
    ("Mercury", 0.387, (190, 190, 190), 2.2), ("Venus", 0.723, (240, 215, 160), 2.6), ("Earth", 1.0, (110, 190, 255), 2.8),
    ("Mars", 1.524, (255, 120, 90), 2.5), ("Jupiter", 5.203, (235, 190, 150), 9.0), ("Saturn", 9.537, (240, 220, 160), 8.0),
    ("Uranus", 19.19, (160, 235, 240), 6.5), ("Neptune", 30.07, (110, 140, 255), 6.5)]
PH0 = [0.6, 2.1, 4.0, 5.2, 0.9, 2.7, 3.9, 5.5]
EBLUE = PLANETS[2][2]


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


def dim(d, x0, x1, y, a, gap=0, col=GREY):
    """A horizontal dimension line with end ticks (and a gap in the middle for its label)."""
    m = (x0 + x1) / 2
    if gap:
        line(d, [(x0, y), (m - gap, y)], rgba(col, a), 3); line(d, [(m + gap, y), (x1, y)], rgba(col, a), 3)
    else:
        line(d, [(x0, y), (x1, y)], rgba(col, a), 3)
    for x in (x0, x1):
        line(d, [(x, y - 16), (x, y + 16)], rgba(col, a), 3)


LANDS = [(0.3, 0.5, 0.30), (0.8, 0.25, 0.22), (1.3, -0.3, 0.26), (2.4, 0.45, 0.34), (2.9, 0.1, 0.2), (3.3, -0.45, 0.24),
         (4.3, 0.2, 0.3), (4.8, 0.6, 0.2), (5.4, -0.25, 0.28), (5.9, 0.3, 0.18)]


def earth(d, x, y, r, T, a):
    """Earth as a glass marble: turning, with a highlight. Below a few units it is just a blue dot."""
    if a <= 0:
        return
    if r < 7:
        circ(d, x, y, max(r, 1.2), fill=rgba(EBLUE, a))
        return
    circ(d, x, y, r * 1.12, fill=rgba((90, 160, 255), 0.10 * a))
    n = 14
    for k in range(n):
        f = k / (n - 1)
        circ(d, x - 0.22 * r * f, y - 0.26 * r * f, r * (1 - 0.72 * f), fill=rgba(lerp3((18, 62, 160), (70, 150, 245), f), a))
    for lon, lat, sz in LANDS:
        ph = lon + 0.55 * T
        vis = math.cos(ph)
        if vis <= 0.05:
            continue
        bx, by = r * math.cos(lat) * math.sin(ph), -r * math.sin(lat)
        br = min(sz * r * vis ** 0.5, 0.97 * r - math.hypot(bx, by))
        if br > 1:
            circ(d, x + bx, y + by, br, fill=rgba((70, 185, 120), 0.85 * a))
    circ(d, x, y, r, outline=rgba((170, 215, 255), 0.9 * a), width=max(1.5, r * 0.02))
    circ(d, x - 0.36 * r, y - 0.42 * r, 0.17 * r, fill=rgba(WHITE, 0.55 * a))
    circ(d, x - 0.2 * r, y - 0.56 * r, 0.06 * r, fill=rgba(WHITE, 0.6 * a))


_sr = np.random.default_rng(5)
RAYS = [(float(_sr.uniform(0, 6.283)), float(_sr.uniform(0.25, 1.0)), float(_sr.uniform(0.3, 1.2)), float(_sr.uniform(0, 6.283)))
        for _ in range(64)]
GRAN = [(float(_sr.uniform(0, 1) ** 0.5), float(_sr.uniform(0, 6.283)), float(_sr.uniform(0.5, 2.0)), float(_sr.uniform(0, 6.283)))
        for _ in range(140)]


def sun(d, cx, cy, R, T, a):
    """A stylised Sun: glowing disk, slowly boiling surface, short flickering rays."""
    if a <= 0:
        return
    hot, mid, rim = (255, 250, 220), GOLD, ORANGE
    for th, ln, sp, ph in RAYS:
        fl = 0.55 + 0.45 * math.sin(sp * 2.2 * T + ph)
        th2 = th + 0.05 * T
        r1 = R * (1.03 + 0.16 * ln * fl)
        line(d, [(cx + R * 0.98 * math.cos(th2), cy + R * 0.98 * math.sin(th2)), (cx + r1 * math.cos(th2), cy + r1 * math.sin(th2))],
             rgba(mid, 0.30 * a * fl), 5)
    n = 26
    for k in range(n):
        f = k / (n - 1)
        col = lerp3(rim, mid, clamp(f * 2)) if f < 0.5 else lerp3(mid, hot, (f - 0.5) * 2)
        circ(d, cx, cy, R * (1 - 0.93 * f), fill=rgba(col, a))
    for r, th, sp, ph in GRAN:
        tw = 0.5 + 0.5 * math.sin(sp * 1.6 * T + ph)
        th2 = th + 0.04 * T
        circ(d, cx + R * 0.93 * r * math.cos(th2), cy + R * 0.93 * r * math.sin(th2), 5 + 7 * tw, fill=rgba(WHITE, 0.10 * a * tw))


def cup(d, cx, cy, r, a, saucer=True):
    """A cup seen from above: saucer, handle (on the left), white wall, dark coffee."""
    if a <= 0:
        return
    if saucer:
        circ(d, cx, cy, r * 1.2, fill=rgba((150, 160, 185), 0.16 * a), outline=rgba(CUPW, 0.55 * a), width=max(1.5, r * 0.012))
    wall = r * 0.07
    d.ellipse([(cx - r * 1.42) * S, (cy - r * 0.2) * S, (cx - r * 0.95) * S, (cy + r * 0.2) * S],
              outline=rgba(CUPW, a), width=max(1.0, wall * S))
    circ(d, cx, cy, r + wall / 2, fill=rgba(COFFEE, a), outline=rgba(CUPW, a), width=wall)


def orbits(d, cx, cy, pxau, tau, a, rmax=2000):
    """The eight orbits, to scale, with the planets moving (speeds follow Kepler's law, hugely sped up)."""
    for (name, au, col, pr), ph in zip(PLANETS, PH0):
        r = au * pxau
        if r > rmax:
            continue
        circ(d, cx, cy, r, outline=rgba(col, 0.55 * a), width=1.6 if r < 30 else 2.2)
        th = ph + 5.2 * tau / au ** 1.5
        circ(d, cx + r * math.cos(th), cy + r * math.sin(th), pr, fill=rgba(col, a))


# ---------- scenes ----------
MR, MY0 = 150, 1060                      # the marble in the opening frame
SUNR = 300                               # the Sun in the size comparison (so Earth is 2 * SUNR / 109.3 wide)
SUNX = 560


def scene_marble(img, d, T, texts):
    """0-5: Earth as a marble. 5-12: the Sun beside it, to scale. From 67.8: the marble again, so the Short loops."""
    end = T > 30
    a = win(T, 67.8, DUR + 2, 1.0, 0.3) if end else win(T, -1.0, 12.0, 0.2, 0.35)
    if a <= 0:
        return
    tau = T - DUR if end else T
    g = 0.0 if end else ss((T - 5.0) / 1.4)
    er = SUNR * EARTH_KM / SUN_KM                           # Earth's radius at the Sun's scale
    r = MR * (er / MR) ** g
    ex, ey = lerp(CX, 150, g), lerp(MY0, 1250, g)
    sun(d, SUNX, MY0, SUNR, T, a * ss((g - 0.25) / 0.6))
    earth(d, ex, ey, r, tau, a)
    if not CAPTIONS:
        return
    s1 = a * (1 - ss(g / 0.2))
    if s1 > 0:
        dim(d, CX - MR, CX + MR, MY0 + MR + 70, s1, gap=62)
        texts.append((label_sprite("1 cm", POP, 40, WHITE), CX, MY0 + MR + 70, s1))
        texts.append((label_sprite("Earth, shrunk to a marble", size=30, fill=GREY), CX, 1480, s1))
        if not end:
            texts.append((label_sprite("How big is the universe?", POP, 52, GOLD), CX, 760, s1 * ss((T - 2.2) / 0.4)))
    if g > 0.9:
        s2 = a * ss((g - 0.9) / 0.1)
        pul = (1.2 * T) % 1.0
        circ(d, ex, ey, 14 + 26 * pul, outline=rgba(EBLUE, 0.9 * (1 - pul) * s2), width=2.5)
        texts.append((label_sprite("Earth: 1 cm", POP, 36, EBLUE), ex + 40, ey + 62, s2))
        texts.append((label_sprite(f"the Sun: {SUN_M:.1f} m", POP, 46, (60, 30, 6), stroke=0), SUNX, MY0 - 40, s2 * ss((T - 6.8) / 0.4)))
        texts.append((label_sprite("1.3 million Earths", POP, 40, (60, 30, 6), stroke=0), SUNX, MY0 + 30, s2 * ss((T - 9.0) / 0.4)))
        texts.append((label_sprite("would fit inside", POP, 34, (60, 30, 6), stroke=0), SUNX, MY0 + 78, s2 * ss((T - 9.0) / 0.4)))
        texts.append((label_sprite("sizes to scale", size=28, fill=GREY), CX, 1480, s2))


def scene_pitch(img, d, T, texts):
    a = win(T, 12.0, 18.0, 0.35, 0.3)
    if a <= 0:
        return
    pm = 800 / EARTH_SUN_M                                  # layout units per metre
    x0, y = 70, 1060
    L, Wd = 105 * pm, 68 * pm
    GRASS, LN = (22, 105, 62), rgba(WHITE, 0.75 * a)
    rect(d, x0, y - Wd / 2, x0 + L, y + Wd / 2, fill=rgba(GRASS, 0.85 * a), outline=LN, width=3)
    line(d, [(x0 + L / 2, y - Wd / 2), (x0 + L / 2, y + Wd / 2)], LN, 3)
    circ(d, x0 + L / 2, y, 9.15 * pm, outline=LN, width=3)
    for sx, xe in ((1, x0), (-1, x0 + L)):
        rect(d, min(xe, xe + sx * 16.5 * pm), y - 20.15 * pm, max(xe, xe + sx * 16.5 * pm), y + 20.15 * pm, outline=LN, width=3)
        rect(d, min(xe, xe + sx * 5.5 * pm), y - 9.16 * pm, max(xe, xe + sx * 5.5 * pm), y + 9.16 * pm, outline=LN, width=3)
    g = ss((T - 12.5) / 1.6)
    xe = x0 + 800 * g
    for i in range(40):                                     # the distance draws itself out
        xa = x0 + 800 * (i / 40)
        if xa + 10 < xe:
            line(d, [(xa, y), (xa + 10, y)], rgba(GOLD, a), 4)
    pul = (1.1 * T) % 1.0
    circ(d, x0, y, SUN_M * pm / 2, fill=rgba((255, 235, 170), a))
    circ(d, x0, y, 10 + 22 * pul, outline=rgba(GOLD, 0.9 * (1 - pul) * a), width=2.5)
    ea = a * ss((g - 0.9) / 0.1)
    circ(d, x0 + 800, y, 2.2, fill=rgba(EBLUE, ea))
    circ(d, x0 + 800, y, 10 + 22 * pul, outline=rgba(EBLUE, 0.9 * (1 - pul) * ea), width=2.5)
    texts.append((label_sprite("Sun", POP, 36, GOLD), x0 + 50, y - 56, a))
    texts.append((label_sprite("Earth", POP, 36, EBLUE), x0 + 800 - 34, y - 56, ea))
    texts.append((label_sprite(f"{EARTH_SUN_M:.0f} m", POP, 110, GOLD), CX, 1385, ea))
    texts.append((label_sprite("football pitch: 105 m", POP, 32, WHITE), x0 + L / 2, y - Wd / 2 - 36, a))
    texts.append((label_sprite("distance and Sun to scale · Earth dot enlarged", size=28, fill=GREY), CX, 1480, a))


def scene_neptune(img, d, T, texts):
    a = win(T, 18.0, 23.0, 0.35, 0.3)
    if a <= 0:
        return
    x0, x1, y = 80, 880, 1010
    pm = (x1 - x0) / NEPTUNE_M
    g = ss((T - 18.3) / 2.0)
    xe = lerp(x0, x1, g)
    line(d, [(x0, y), (xe, y)], rgba(GREY, 0.8 * a), 3)
    circ(d, x0, y, 7, fill=rgba((255, 235, 170), a))
    for i, (name, au, col, pr) in enumerate(PLANETS):
        x = x0 + au * EARTH_SUN_M * pm
        if x > xe + 1:
            continue
        big = i >= 4
        circ(d, x, y, 7 if big else 3, fill=rgba(col, a))
        if big:
            up = i % 2 == 0
            line(d, [(x, y - 14 if up else y + 14), (x, y - 50 if up else y + 50)], rgba(col, 0.8 * a), 2)
            texts.append((label_sprite(name, POP, 32, col), x - (30 if i == 7 else 0), y - 76 if up else y + 76, a))
    line(d, [(x0 + EARTH_SUN_M * pm, y - 12), (x0 + EARTH_SUN_M * pm, y - 150)], rgba(EBLUE, 0.8 * a), 2)
    texts.append((label_sprite("Earth: 117 m", POP, 32, EBLUE), x0 + 110, y - 176, a))
    texts.append((label_sprite("Sun", POP, 32, GOLD), x0 + 4, y + 50, a))
    na = a * ss((g - 0.95) / 0.05)
    texts.append((label_sprite(f"{NEPTUNE_M / 1000:.1f} km", POP, 120, GOLD), CX, 1290, na))
    texts.append((label_sprite("about 40 minutes on foot", POP, 38, WHITE), CX, 1390, a * ss((T - 20.9) / 0.4)))
    texts.append((label_sprite("distances to scale · dots enlarged", size=28, fill=GREY), CX, 1480, a))


def scene_cup(img, d, T, texts):
    a = win(T, 23.0, 33.0, 0.4, 0.4)
    if a <= 0:
        return
    tau = T - 23.0
    z = ss((T - 28.0) / 1.6)                                # zoom in on the centre of the cup
    pxau = PXAU * (200 / PXAU) ** z                         # ends with Earth's orbit 400 units wide
    k = pxau / PXAU
    if RIN * k < 2600:
        cup(d, CX, CY, RIN * k, a * (1 - ss((z - 0.35) / 0.4)))
    circ(d, CX, CY, lerp(1.9, 1.2, z), fill=rgba((255, 240, 200), a))      # the Sun (enlarged: it would be 0.012 mm)
    orbits(d, CX, CY, pxau, tau, a, rmax=640)
    s1 = a * (1 - ss((z - 0.02) / 0.2))
    if s1 > 0:
        dim(d, CX - RIN, CX + RIN, 1410, s1, gap=60)
        texts.append((label_sprite("8 cm", POP, 40, WHITE), CX, 1410, s1))
        texts.append((label_sprite("Neptune's orbit", size=28, fill=PLANETS[7][2]), CX, CY + 250 + 28, s1 * ss((T - 24.0) / 0.4)))
        texts.append((label_sprite("orbits to scale · planets enlarged", size=28, fill=GREY), CX, 1480, s1))
    if z > 0.75:
        g = a * ss((z - 0.75) / 0.25)
        th = PH0[2] + 5.2 * tau                               # follow the Earth: a line from the Sun to it
        ex, ey = CX + 200 * math.cos(th), CY + 200 * math.sin(th)
        line(d, [(CX, CY), (ex, ey)], rgba(EBLUE, 0.9 * g), 3)
        circ(d, ex, ey, 9, fill=rgba(EBLUE, g))
        texts.append((label_sprite("Sun", POP, 34, GOLD), CX, CY - 44, g))
        texts.append((label_sprite(f"Earth to Sun: {EARTH_SUN_MM:.1f} mm", POP, 54, EBLUE), CX, 1410, g))
        texts.append((label_sprite("orbits to scale · dots enlarged", size=28, fill=GREY), CX, 1480, g))


# --- North America: Natural Earth outlines (public domain), azimuthal equidistant projection, kilometres from the centre ---
MAP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "earth_marble_universe_map.json")))
MY, KM = 1075, 0.09                      # map centre (y) and layout units per kilometre
LAND = (70, 96, 150)


def land(d, rings, fill, outline, a_fill, a_line):
    for ring in rings:
        pts = []
        for x, y in ring:
            pts += [(CX + x * KM) * S, (MY + y * KM) * S]
        d.d.polygon(pts, aggdraw.Pen(outline, 1.6 * S, int(255 * clamp(a_line))), aggdraw.Brush(fill, int(255 * clamp(a_fill))))


GAL_PAD = 1.25                           # sprite width / disk diameter


def make_galaxy():
    """A schematic barred spiral, as a sprite whose disk is GALAXY_KM wide on the map."""
    rng = np.random.default_rng(11)
    R = GALAXY_KM / 2 * KM * S                               # disk radius in pixels
    n = int(R * 2 * GAL_PAD); c = n / 2
    acc = np.zeros((n, n), np.float32); warm = np.zeros((n, n), np.float32)

    def splat(x, y, w, layer):
        ix, iy = (c + x).astype(int), (c + y).astype(int)
        ok = (ix >= 0) & (ix < n) & (iy >= 0) & (iy < n)
        np.add.at(layer, (iy[ok], ix[ok]), w)

    m = 60000                                                # spiral arms
    for arm, wgt in ((0, 1.0), (math.pi, 1.0), (math.pi / 2, 0.55), (3 * math.pi / 2, 0.55)):
        r = R * (0.16 + 0.84 * rng.uniform(0, 1, m) ** 0.8)
        th = arm + 2.6 * np.log(r / (0.16 * R)) + rng.normal(0, 0.16, m)
        rr = r + rng.normal(0, 0.035 * R, m)
        splat(rr * np.cos(th), rr * np.sin(th), wgt * np.exp(-1.6 * r / R), acc)
    m = 50000                                                # faint smooth disk
    r = R * rng.uniform(0, 1, m) ** 0.6; th = rng.uniform(0, 6.283, m)
    splat(r * np.cos(th), r * np.sin(th), 0.25 * np.exp(-2.2 * r / R), acc)
    m = 40000                                                # bulge and bar
    splat(rng.normal(0, 0.11 * R, m), rng.normal(0, 0.05 * R, m), 1.0, warm)
    splat(rng.normal(0, 0.055 * R, m), rng.normal(0, 0.055 * R, m), 1.0, warm)

    def soft(layer, rad):
        im = Image.fromarray(np.clip(layer / np.percentile(layer[layer > 0], 99.5) * 255, 0, 255).astype(np.uint8))
        return np.asarray(im.filter(ImageFilter.GaussianBlur(rad)), np.float32) / 255
    A = np.clip(1.5 * soft(acc, 1.3 * S) + 0.9 * soft(acc, 5 * S), 0, 1); Wm = np.clip(2.2 * soft(warm, 5 * S), 0, 1)
    rgb = np.zeros((n, n, 4), np.float32)
    for i, (cb, cw) in enumerate(zip((190, 215, 255), (255, 222, 165))):
        rgb[..., i] = np.clip(cb * A + cw * Wm, 0, 255) / np.maximum(A + Wm, 1e-3).clip(1, None)
    rgb[..., 3] = 255 * np.clip(A + Wm, 0, 1) ** 0.85
    return Image.fromarray(rgb.astype(np.uint8), "RGBA")


_gal = {}


def galaxy(d, cx, cy, diam, ang, a, mirror=False):
    """Paste the galaxy drawing with its disk `diam` layout units wide."""
    if a <= 0.004:
        return
    if "base" not in _gal:
        _gal["base"] = make_galaxy()
        _gal["mirror"] = _gal["base"].transpose(Image.FLIP_LEFT_RIGHT)
    base = _gal["mirror" if mirror else "base"]
    n = max(4, int(round(diam * GAL_PAD * S)))
    key = (mirror, n)
    if n == base.width:
        sp = base
    elif key in _gal:
        sp = _gal[key]
    else:
        sp = base.resize((n, n), Image.LANCZOS)
        if len(_gal) < 12:
            _gal[key] = sp
    sp = sp.rotate(ang, resample=Image.BICUBIC)
    m = sp.getchannel("A")
    if a < 0.996:
        m = m.point(lambda v: int(v * a))
    d.paste(sp, (int(round(cx * S - n / 2)), int(round(cy * S - n / 2))), m)


def plate(d, cx, cy, r, a):
    """A dinner plate seen from above (the galaxy lies on it)."""
    if a <= 0:
        return
    circ(d, cx, cy, r, fill=rgba((200, 208, 228), 0.16 * a), outline=rgba(CUPW, a), width=max(1.5, r * 0.035))
    circ(d, cx, cy, r * 0.74, fill=rgba(COFFEE, 0.5 * a), outline=rgba(CUPW, 0.5 * a), width=max(1.0, r * 0.012))


T_MW = 34.0                                                  # the galaxy appears over the continent
GD = GALAXY_KM * KM                                          # the galaxy's width on the map, layout units
PLR = 205                                                    # the big dinner plate (radius)


def scene_map(img, d, T, texts):
    """33-41: the Milky Way over North America. 41-46: shrink it to a dinner plate."""
    a = win(T, 33.0, 46.0, 0.4, 0.4)
    if a <= 0:
        return
    rev = ss((T - T_MW) / 1.0)
    z = ss((T - 41.0) / 1.5)                                 # 0 = on the map, 1 = on the plate
    ma = a * (1 - ss(z / 0.5))
    if ma > 0:
        land(d, MAP["other"] + MAP["canada"], LAND, (150, 170, 215), (0.35 + 0.40 * rev) * ma, 0.85 * ma)
    cy = lerp(MY, 1050, z)
    diam = lerp(GD, 2 * PLR * 0.92, z)
    plate(d, CX, cy, PLR, a * ss((z - 0.5) / 0.5))
    galaxy(d, CX, cy, diam, -2.2 * (T - T_MW), rev * a)
    if ma > 0 and rev > 0:
        circ(d, CX, MY, GD / 2, outline=rgba(GOLD, 0.75 * rev * ma), width=3)
        dt = T - T_MW
        circ(d, CX, MY, GD / 2 * (0.3 + 1.4 * dt), outline=rgba(WHITE, 0.7 * math.exp(-dt / 0.5) * ma), width=5)
        la = ma * ss((T - T_MW - 1.4) / 0.5)
        sx, sy = CX - 120, MY + 158                         # the Sun's place: about 26,000 light-years from the centre
        circ(d, sx, sy, 5, fill=rgba(GOLD, la)); circ(d, sx, sy, 13 + 4 * math.sin(5 * T), outline=rgba(GOLD, 0.8 * la), width=2.5)
        texts.append((label_sprite("our cup", POP, 32, GOLD), sx - 86, sy + 34, la))
        texts.append((label_sprite("Milky Way: about 8,000 km across", POP, 38, WHITE), CX, 1442, la))
        texts.append((label_sprite("map and sizes to scale · galaxy drawing is an illustration", size=26, fill=GREY), CX, 1492, ma))
    elif ma > 0:
        texts.append((label_sprite("map to scale", size=26, fill=GREY), CX, 1492, ma))
    pa = a * ss((z - 0.8) / 0.2)
    if pa > 0:
        dim(d, CX - PLR, CX + PLR, 1050 + PLR + 70, pa, gap=70)
        texts.append((label_sprite("25 cm", POP, 40, WHITE), CX, 1050 + PLR + 70, pa))
        texts.append((label_sprite("the Milky Way, on a dinner plate", POP, 36, GOLD), CX, 1050 - PLR - 60, pa))
        texts.append((label_sprite("galaxy drawing is an illustration", size=28, fill=GREY), CX, 1480, pa))


def scene_andromeda(img, d, T, texts):
    a = win(T, 46.0, 54.0, 0.4, 0.4)
    if a <= 0:
        return
    xa, xb, y = 150, 850, 1180
    pm = (xb - xa) / ANDROMEDA_M                             # layout units per metre
    r1 = PLATE_CM / 100 * pm / 2; r2 = 2 * r1                # Andromeda: about twice as wide (published sizes vary)
    plate(d, xa, y, r1, a); galaxy(d, xa, y, 2 * r1 * 0.92, -2.2 * (T - T_MW), a)
    g = ss((T - 46.4) / 1.6)
    xe = lerp(xa + 30, xb - 45, g)
    for i in range(30):
        xs = xa + 30 + (xb - 45 - xa - 30) * i / 30
        if xs + 10 < xe:
            line(d, [(xs, y), (xs + 10, y)], rgba(CYAN, 0.85 * a), 4)
    ga = a * ss((g - 0.85) / 0.15)
    plate(d, xb, y, r2, ga); galaxy(d, xb, y, 2 * r2 * 0.92, 2.2 * (T - T_MW) + 40, ga, mirror=True)
    # magnified views above each plate
    for (px, pr, big, lab, col, al, mir) in ((230, r1, 105, "Milky Way", GOLD, a, False), (700, r2, 190, "Andromeda", CYAN, ga, True)):
        cyb = 860 if not mir else 850
        x_pl = xa if not mir else xb
        line(d, [(x_pl, y - pr - 6), (px, cyb + big + 6)], rgba(GREY, 0.6 * al), 2)
        plate(d, px, cyb, big, al)
        galaxy(d, px, cyb, 2 * big * 0.92, (-2.2 if not mir else 2.2) * (T - T_MW) + (40 if mir else 0), al, mirror=mir)
        texts.append((label_sprite(lab, POP, 36, col), px, cyb - big - 34, al))
    texts.append((label_sprite(f"about {ANDROMEDA_M:.0f} m", POP, 100, GOLD), CX, 1330, ga))
    texts.append((label_sprite("in reality: 2.5 million light-years", POP, 34, WHITE), CX, 1415, a * ss((T - 49.5) / 0.4)))
    texts.append((label_sprite("bottom row to scale · circles magnified · Andromeda's size approximate", size=25, fill=GREY), CX, 1484, a))


_ur = np.random.default_rng(21)
UDOT = []
while len(UDOT) < 1500:
    _x, _y = _ur.uniform(-1, 1), _ur.uniform(-1, 1)
    if _x * _x + _y * _y < 1:
        UDOT.append((float(_x), float(_y), float(_ur.uniform(1.3, 3.0)), float(_ur.uniform(0, 6.283)), float(_ur.uniform(0.6, 2.2)),
                     int(_ur.integers(0, 3))))
UCOL = [(255, 255, 255), (190, 215, 255), (255, 222, 165)]
T_UNI = 55.0                                                 # the big moment


def scene_universe(img, d, T, texts):
    a = win(T, 54.0, 64.2, 0.4, 0.7)
    if a <= 0:
        return
    UR, cy = 350, 1065
    g = ss((T - 54.2) / 2.2)
    k = 1 + 9 * (1 - g) ** 2                                 # zooming out: the field rushes inward
    for x, y, r, ph, sp, ci in UDOT:
        px, py = CX + x * UR * k, cy + y * UR * k
        if 20 < px < 980 and 650 < py < 1500:
            tw = 0.65 + 0.35 * math.sin(sp * T + ph)
            circ(d, px, py, r * (0.8 + 0.5 * (k - 1) / 9), fill=rgba(UCOL[ci], 0.9 * tw * a))
    ra = a * ss((g - 0.8) / 0.2)
    circ(d, CX, cy, UR + 6, outline=rgba(GOLD, 0.85 * ra), width=3)
    dt = T - T_UNI - 1.2
    if dt > 0:
        circ(d, CX, cy, UR * (0.2 + 1.3 * dt), outline=rgba(WHITE, 0.6 * math.exp(-dt / 0.5) * a), width=5)
    circ(d, CX, cy, 9 + 3 * math.sin(5 * T), outline=rgba(CYAN, 0.9 * ra), width=2.5)
    texts.append((label_sprite("our two plates", POP, 30, CYAN), CX, cy + 36, ra))
    texts.append((label_sprite(f"about {round(UNIVERSE_KM, -1):.0f} km across", POP, 54, WHITE), CX, 672, ra))
    texts.append((label_sprite("like Montreal to Quebec City", POP, 38, GOLD), CX, 1456, a * ss((T - 59.0) / 0.4)))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1496, ra))


CAN, RED_ = (110, 225, 255), RED


def scene_canada(img, d, T, texts):
    """33-37: the guesses. A city is a dot; even Canada is too small."""
    a = win(T, 33.0, 37.4, 0.4, 0.4)
    if a <= 0:
        return
    c = ss((T - 34.6) / 0.5)                                 # Canada lights up
    land(d, MAP["other"], LAND, (150, 170, 215), 0.35 * a, 0.85 * a)
    land(d, MAP["canada"], lerp3(LAND, CAN, c), lerp3((150, 170, 215), WHITE, c), lerp(0.35, 0.62, c) * a, 0.9 * a)
    ca = a * (1 - ss((T - 34.4) / 0.3))
    cx_, cy_ = CX + 150, MY + 20                             # "your city": a dot (no particular city)
    pul = (1.3 * T) % 1.0
    circ(d, cx_, cy_, 4, fill=rgba(GOLD, ca)); circ(d, cx_, cy_, 10 + 26 * pul, outline=rgba(GOLD, 0.9 * (1 - pul) * ca), width=2.5)
    texts.append((label_sprite("your city?", POP, 40, GOLD), cx_ + 20, cy_ - 50, ca))
    texts.append((label_sprite("too small", POP, 40, RED_), cx_ + 20, cy_ + 50, ca * ss((T - 33.9) / 0.25)))
    ya = 1020
    da = a * ss((T - 34.9) / 0.4)
    dim(d, CX - 5514 * KM / 2 - 40, CX + 5514 * KM / 2 - 40, ya, da, col=WHITE)
    texts.append((label_sprite("Canada: about 5,500 km", POP, 40, WHITE), CX - 40, ya - 44, da))
    xa = a * ss((T - 36.0) / 0.25)
    line(d, [(CX - 116, 804), (CX - 4, 916)], rgba(RED_, xa), 10); line(d, [(CX - 116, 916), (CX - 4, 804)], rgba(RED_, xa), 10)
    texts.append((label_sprite("too small", POP, 50, RED_), 215, 1340, xa))
    texts.append((label_sprite("map to scale", size=26, fill=GREY), CX, 1492, a))


def later(sc):
    """Scenes written before the guessing scene was added run 4 s later."""
    return lambda img, d, T, texts: sc(img, d, T - 4.0, texts)


SCENES = (scene_marble, scene_pitch, scene_neptune, scene_cup, scene_canada, later(scene_map), later(scene_andromeda), later(scene_universe))


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
