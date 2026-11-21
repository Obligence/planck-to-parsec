#!/usr/bin/env python3
"""The planets in a cup: if the orbits of all eight planets (Neptune's orbit, 60 AU edge to edge) fitted in an 8 cm cup,
the Milky Way (about 100,000 light-years) would be about 8,400 km across: North America from the Arctic to Panama.
Every size on screen is computed from the constants in "the scale model" below.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 solar_system_cup.py preview 0 6.4 12      -> frame_<t>.png files
  python3 solar_system_cup.py render 0 40 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 40.0            # layout units; output is W*S x H*S
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
    (0.0, 5.0, None, "Every planet's orbit | *in this cup.*"),
    (5.0, 12.0, None, "The Sun: a speck | *finer than a hair.*"),
    (12.0, 17.0, None, "The nearest star: | another speck, | *360 m away.*"),
    (17.0, 22.0, None, "So, the galaxy. | *Your room? Your city?*"),
    (22.0, 26.0, None, "All of *Canada?* | Still too small."),
    (26.0, 34.0, "FROM THE ARCTIC TO PANAMA", "The Milky Way: | *all of North America.*"),
    (34.0, 40.0, None, "Billions of stars. | Our planets: *one cup.*"),
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

# ---------- the scale model (every number below is computed from these) ----------
AU_KM, LY_KM = 149_597_870.7, 9.4607e12
NEPTUNE_AU = 30.07                       # NASA: Neptune is 30 AU from the Sun
CUP_CM = 8.0                             # the cup: Neptune's whole orbit, edge to edge, is 8 cm
GALAXY_LY = 100_000                      # NASA: the Milky Way is about 100,000 light-years across
SCALE = (CUP_CM / 100) / (2 * NEPTUNE_AU * AU_KM * 1000)          # model metres per real metre
SUN_MM = 1_392_700e3 * SCALE * 1000                               # 0.012 mm
EARTH_ORBIT_MM = 2 * AU_KM * 1000 * SCALE * 1000                  # 2.7 mm
PROXIMA_M = 4.2465 * LY_KM * 1000 * SCALE                         # about 360 m
GALAXY_KM = GALAXY_LY * LY_KM * SCALE                             # about 8,400 km
HAIR_MM = 0.07                                                    # a typical human hair

CX, CY = 500, 1045                       # picture centre (the right-hand edge stays clear for the Shorts buttons)
RIN = 262                                # inner radius of the cup, layout units
PXAU = 250 / NEPTUNE_AU                  # scene 1: Neptune's orbit sits just inside the rim
CUPW, COFFEE = (236, 238, 244), (5, 7, 16)
PLANETS = [  # name, orbit radius in AU, colour, dot radius (dots are enlarged; orbits are to scale)
    ("Mercury", 0.387, (190, 190, 190), 2.2), ("Venus", 0.723, (240, 215, 160), 2.6), ("Earth", 1.0, (110, 190, 255), 2.8),
    ("Mars", 1.524, (255, 120, 90), 2.5), ("Jupiter", 5.203, (235, 190, 150), 9.0), ("Saturn", 9.537, (240, 220, 160), 8.0),
    ("Uranus", 19.19, (160, 235, 240), 6.5), ("Neptune", 30.07, (110, 140, 255), 6.5)]
PH0 = [0.6, 2.1, 4.0, 5.2, 0.9, 2.7, 3.9, 5.5]


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


def cross(d, x, y, r, a, w=10):
    line(d, [(x - r, y - r), (x + r, y + r)], rgba(RED, a), w); line(d, [(x - r, y + r), (x + r, y - r)], rgba(RED, a), w)


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
def scene_cup(img, d, T, texts):
    """Opening (and, at the very end, the same picture again so the Short loops)."""
    end = T > 20
    a = win(T, 34.6, DUR + 2, 0.9, 0.3) if end else win(T, -1.0, 12.0, 0.2, 0.4)
    if a <= 0:
        return
    tau = T - DUR if end else T
    z = 0.0 if end else ss((T - 5.0) / 1.6)                 # zoom in on the centre of the cup
    pxau = PXAU * (200 / PXAU) ** z                         # ends with Earth's orbit 400 units wide
    k = pxau / PXAU
    if RIN * k < 2600:
        cup(d, CX, CY, RIN * k, a * (1 - ss((z - 0.35) / 0.4)))
    if not end:
        circ(d, CX, CY, 1.9, fill=rgba((255, 240, 200), a * (1 - z)))       # the Sun, enlarged just enough to see at this zoom
    orbits(d, CX, CY, pxau, tau, a, rmax=640)
    s1 = a * (1 - ss((z - 0.02) / 0.2))
    if s1 > 0 and CAPTIONS:
        line(d, [(CX - RIN, 1410), (CX - 60, 1410)], rgba(GREY, 0.9 * s1), 3); line(d, [(CX + 60, 1410), (CX + RIN, 1410)], rgba(GREY, 0.9 * s1), 3)
        for sx in (-1, 1):
            line(d, [(CX + sx * RIN, 1394), (CX + sx * RIN, 1426)], rgba(GREY, 0.9 * s1), 3)
        texts.append((label_sprite("8 cm", POP, 40, WHITE), CX, 1410, s1))
        texts.append((label_sprite("orbits to scale · planets enlarged", size=28, fill=GREY), CX, 1480, s1))
        if not end:
            texts.append((label_sprite("How big is our galaxy?", POP, 50, GOLD), CX, 700, s1 * ss((T - 2.3) / 0.4)))
            texts.append((label_sprite("Neptune's orbit", size=28, fill=PLANETS[7][2]), CX, CY + 250 + 28, s1 * ss((T - 0.9) / 0.4)))
    if z > 0.75:                                            # zoomed in: the Sun and a hair, both to scale
        g = a * ss((z - 0.75) / 0.25)
        pxmm = 400 / EARTH_ORBIT_MM
        circ(d, CX, CY, SUN_MM * pxmm / 2, fill=rgba((255, 245, 215), g))
        pul = (1.1 * T) % 1.0
        circ(d, CX, CY, 14 + 40 * pul, outline=rgba(GOLD, 0.8 * (1 - pul) * g), width=2.5)
        texts.append((label_sprite(f"the Sun: {SUN_MM:.3f} mm", POP, 40, GOLD), CX, CY - 78, g * ss((T - 6.8) / 0.4)))
        hy, hw = 1378, HAIR_MM * pxmm
        pts = [(x, hy + 9 * math.sin(x / 150.0)) for x in range(60, 941, 20)]
        ha = g * ss((T - 7.6) / 0.5)
        for i in range(len(pts) - 1):
            line(d, [pts[i], pts[i + 1]], rgba((150, 105, 70), ha), hw)
        texts.append((label_sprite(f"a human hair: about {HAIR_MM:.2f} mm", POP, 36, (220, 170, 130)), CX, hy + 48, ha))
        ea = g * ss((T - 9.2) / 0.5)
        texts.append((label_sprite(f"Earth's orbit: {EARTH_ORBIT_MM:.1f} mm wide", POP, 38, PLANETS[2][2]), CX, CY - 200 - 44, ea))
        texts.append((label_sprite("sizes to scale", size=28, fill=GREY), CX, 1480, g))


_tw = np.random.default_rng(3)


def scene_star(img, d, T, texts):
    a = win(T, 12.0, 17.0, 0.35, 0.3)
    if a <= 0:
        return
    y, x0, x1 = 1040, 150, 850
    cup(d, x0, y, 46, a, saucer=False)
    circ(d, x0, y, 1.5, fill=rgba((255, 245, 215), a))
    g = ss((T - 12.3) / 1.6)                                # the distance draws itself out, then keeps marching
    xe = lerp(x0 + 75, x1 - 30, g)
    n = 26
    for i in range(n):
        xa = x0 + 75 + (x1 - 30 - x0 - 75) * ((i + (0.8 * T) % 1.0) / n)
        if xa < xe:
            line(d, [(xa, y), (min(xa + 12, xe), y)], rgba(CYAN, 0.85 * a), 4)
    sa = a * ss((T - 13.6) / 0.4)
    twk = 0.6 + 0.4 * math.sin(7 * T)
    circ(d, x1, y, 2.0, fill=rgba((255, 190, 150), sa))
    circ(d, x1, y, 16 + 8 * twk, outline=rgba((255, 150, 110), 0.7 * sa * twk), width=2.5)
    texts.append((label_sprite("our cup", POP, 34, WHITE), x0 + 10, y - 100, a))
    texts.append((label_sprite("nearest star", POP, 34, (255, 170, 130)), x1 - 40, y - 100, sa))
    texts.append((label_sprite(f"about {round(PROXIMA_M, -1):.0f} m", POP, 96, GOLD), CX, y + 190, sa))
    texts.append((label_sprite("in reality: 4.2 light-years", POP, 36, WHITE), CX, y + 290, a * ss((T - 14.4) / 0.4)))
    texts.append((label_sprite("drawing not to scale", size=28, fill=GREY), CX, 1480, a))


WINS = [(float(_tw.uniform(0, 1)), float(_tw.uniform(0, 1)), float(_tw.uniform(0.5, 2.0)), float(_tw.uniform(0, 6.28))) for _ in range(160)]
TOWERS = [(-330, 110, 250), (-215, 90, 400), (-120, 120, 310), (5, 100, 520), (110, 130, 360), (245, 90, 450), (340, 100, 240)]


def scene_guess(img, d, T, texts):
    a = win(T, 17.0, 22.0, 0.3, 0.3)
    if a <= 0:
        return
    ra, ca = win(T, 17.0, 19.6, 0.3, 0.3) * a, win(T, 19.6, 22.0, 0.3, 0.3) * a
    if ra > 0:                                              # a room, seen from above, the cup on a table in the middle
        g = ss((T - 17.1) / 0.6)
        h = 300 * (0.6 + 0.4 * g)
        rect(d, CX - h, 1050 - h, CX + h, 1050 + h, fill=rgba(CYAN, 0.07 * ra), outline=rgba(CYAN, 0.95 * ra), width=6)
        line(d, [(CX + h - 150, 1050 + h), (CX + h - 40, 1050 + h)], rgba(COFFEE, ra), 10)       # doorway
        line(d, [(CX + h - 150, 1050 + h), (CX + h - 150 + 78, 1050 + h - 78)], rgba(CYAN, 0.9 * ra), 4)
        rect(d, CX - 95, 1050 - 60, CX + 95, 1050 + 60, outline=rgba(GREY, 0.8 * ra), width=3)
        cup(d, CX, 1050, 15, ra, saucer=False)
        texts.append((label_sprite("your room?", POP, 64, WHITE), CX, 1050 - 190, ra))
        xa = ra * ss((T - 19.0) / 0.25)
        cross(d, CX, 1050 + 150, 60, xa)
        texts.append((label_sprite("too small", POP, 44, RED), CX, 1050 + 370, xa))
    if ca > 0:                                              # a city skyline
        base = 1330
        g = ss((T - 19.7) / 0.7)
        for i, (x, w, h) in enumerate(TOWERS):
            hh = h * g
            rect(d, CX + x - w / 2, base - hh, CX + x + w / 2, base, fill=rgba((30, 44, 84), ca), outline=rgba(CYAN, 0.9 * ca), width=3)
            for j in range(int(hh // 44)):
                for k_ in range(int(w // 34)):
                    wr = WINS[(i * 37 + j * 5 + k_) % len(WINS)]
                    on = 0.5 + 0.5 * math.sin(wr[2] * 1.3 * T + wr[3])
                    if wr[0] < 0.7:
                        rect(d, CX + x - w / 2 + 12 + k_ * 34, base - 38 - j * 44, CX + x - w / 2 + 28 + k_ * 34, base - 16 - j * 44,
                             fill=rgba(GOLD, (0.35 + 0.55 * on) * ca))
        line(d, [(80, base), (920, base)], rgba(GREY, 0.7 * ca), 3)
        texts.append((label_sprite("your city?", POP, 64, WHITE), CX, 730, ca))
        xa = ca * ss((T - 21.3) / 0.25)
        cross(d, CX, 1050, 70, xa)
        texts.append((label_sprite("too small", POP, 44, RED), CX, base + 70, xa))
    texts.append((label_sprite("illustration", size=28, fill=GREY), CX, 1480, a))


# --- North America: Natural Earth outlines (public domain), azimuthal equidistant projection, kilometres from the centre ---
MAP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "solar_system_cup_map.json")))
MY, KM = 1075, 0.09                      # map centre (y) and layout units per kilometre
LAND, CAN = (70, 96, 150), (110, 225, 255)


def land(d, rings, fill, outline, a_fill, a_line):
    for ring in rings:
        pts = []
        for x, y in ring:
            pts += [(CX + x * KM) * S, (MY + y * KM) * S]
        d.d.polygon(pts, aggdraw.Pen(outline, 1.6 * S, int(255 * clamp(a_line))), aggdraw.Brush(fill, int(255 * clamp(a_fill))))


def make_galaxy():
    """A schematic barred spiral, as a sprite whose disk is GALAXY_KM wide on the map."""
    rng = np.random.default_rng(11)
    R = GALAXY_KM / 2 * KM * S                               # disk radius in pixels
    n = int(R * 2.5); c = n / 2
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


GAL = None
T_REVEAL = 26.4                                              # picture time of the big moment


def scene_map(img, d, T, texts):
    global GAL
    a = win(T, 22.0, 35.2, 0.4, 0.8)
    if a <= 0:
        return
    rev = ss((T - T_REVEAL) / 1.0)                           # 0 = "Canada?", 1 = the galaxy over the whole continent
    land(d, MAP["other"], LAND, (150, 170, 215), (0.30 + 0.45 * rev) * a, 0.8 * a)
    land(d, MAP["canada"], lerp3(CAN, LAND, rev), lerp3(WHITE, (150, 170, 215), rev), lerp(0.62, 0.75, rev) * a, 0.9 * a)
    ca = a * (1 - rev)
    if ca > 0:
        ya = 1020
        da = ca * ss((T - 22.6) / 0.5)
        line(d, [(CX - 5514 * KM / 2 - 40, ya), (CX + 5514 * KM / 2 - 40, ya)], rgba(WHITE, da), 4)
        for sx in (-1, 1):
            line(d, [(CX + sx * 5514 * KM / 2 - 40, ya - 16), (CX + sx * 5514 * KM / 2 - 40, ya + 16)], rgba(WHITE, da), 4)
        texts.append((label_sprite("Canada: about 5,500 km", POP, 40, WHITE), CX - 40, ya - 44, da))
        xa = ca * ss((T - 24.2) / 0.25)
        cross(d, CX - 60, 860, 56, xa)
        texts.append((label_sprite("too small", POP, 50, RED), 215, 1340, xa))
    if rev > 0:
        if GAL is None:
            GAL = make_galaxy()
        g = GAL.rotate(-2.2 * (T - T_REVEAL), resample=Image.BICUBIC)
        m = g.getchannel("A").point(lambda v: int(v * rev * a))
        d.paste(g, (int(CX * S - g.width / 2), int(MY * S - g.height / 2)), m)
        rr = GALAXY_KM / 2 * KM
        circ(d, CX, MY, rr, outline=rgba(GOLD, 0.75 * rev * a), width=3)
        dt = T - T_REVEAL
        circ(d, CX, MY, rr * (0.3 + 1.4 * dt), outline=rgba(WHITE, 0.7 * math.exp(-dt / 0.5) * a), width=5)
        la = a * ss((T - T_REVEAL - 1.4) / 0.5)
        sx, sy = CX - 120, MY + 158                         # the Sun's place: 26,000 light-years from the centre
        circ(d, sx, sy, 5, fill=rgba(GOLD, la)); circ(d, sx, sy, 13 + 4 * math.sin(5 * T), outline=rgba(GOLD, 0.8 * la), width=2.5)
        texts.append((label_sprite("our cup", POP, 32, GOLD), sx - 86, sy + 34, la))
        texts.append((label_sprite("Milky Way: about 8,000 km across", POP, 38, WHITE), CX, 1442, la))
    texts.append((label_sprite("map and sizes to scale · galaxy drawing is an illustration" if rev > 0.5 else "map to scale",
                               size=26, fill=GREY), CX, 1492, a))


SCENES = (scene_map, scene_cup, scene_star, scene_guess)


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
