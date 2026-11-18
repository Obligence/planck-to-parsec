#!/usr/bin/env python3
"""IceCube / 2026 Nobel Prize short. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 icecube_nobel.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 icecube_nobel.py render 0 43.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 44.0            # layout units; output is W*S x H*S
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
    (0.0, 3.6, "SOUTH POLE", "This telescope is *a cubic kilometre of ice.*"),
    (3.6, 7.4, None, "It hunts the most elusive particle we know: *the neutrino.*"),
    (7.6, 12.0, None, "*Nearly 100 trillion* pass through you every second."),
    (12.0, 15.6, None, "To catch a few, you need a detector that is *enormous.* And clear."),
    (15.8, 20.0, "ANTARCTICA", "So physicists melted *86 holes* into the ice. With hot water."),
    (20.0, 23.6, None, "Each hole reaches *2.45 km* down."),
    (23.8, 28.0, None, "Inside: *5,160 light sensors,* frozen in place."),
    (28.2, 33.2, None, "When a neutrino finally hits the ice: *a flash of light.*"),
    (33.4, 38.6, "2013", "Two years of watching. *28 neutrinos* from beyond the solar system."),
    (38.6, 43.6, "NOBEL PRIZE IN PHYSICS 2026", "A telescope *made of ice* opened a new window on the universe."),
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
ICE = (150, 215, 255)
ORANGE = (255, 150, 70)


def paste2x(img, sp, cx, cy, alpha):
    if alpha <= 0.004:
        return
    m = sp.getchannel("A")
    if alpha < 0.996:
        m = m.point(lambda v: int(v * alpha))
    CUR.paste(sp, (int(cx * S - sp.width / 2), int(cy * S - sp.height / 2)), m)


# ---------- shared pieces ----------
_rng = np.random.default_rng(11)
STREAKS = [(float(_rng.uniform(-200, 1000)), float(_rng.uniform(0.25, 0.75)), float(_rng.uniform(700, 1100)),
            float(_rng.uniform(0, 1))) for _ in range(70)]   # x at top, slope dx/dy, speed, phase


def streaks(d, T, a, n=14, col=WHITE, y0=655, y1=1500, alpha=0.38, width=2.0, length=110):
    """Neutrinos: thin streaks falling straight through everything."""
    if a <= 0:
        return
    span = (y1 - y0) + length + 200
    for xt, sl, sp, ph in STREAKS[:n]:
        yh = y0 - 100 + ((T * sp + ph * span) % span)
        ya, yb = max(yh - length, y0), min(yh, y1)
        if yb - ya < 8:
            continue
        line(d, [(xt + sl * (ya - y0), ya), (xt + sl * (yb - y0), yb)], rgba(col, alpha * a), width)


CX0, CX1, CY0, CY1 = 300, 780, 720, 1200            # the cube in the close-up scenes
SENS = [(330 + 52.5 * i, 750 + 38.2 * j) for i in range(9) for j in range(12)]
_fr = np.random.default_rng(5)
RANDOM_FLASHES = [(float(_fr.uniform(360, 720)), float(_fr.uniform(790, 1130)), -0.35 + 1.25 * k) for k in range(8)]
COUNT_FLASHES = [(float(_fr.uniform(350, 730)), float(_fr.uniform(780, 1140)), 34.0 + 0.1 * k) for k in range(28)]


def cube(d, T, a, flashes, texts, km=True, hold=0.7):
    if a <= 0:
        return
    rect(d, CX0, CY0, CX1, CY1, fill=rgba(ICE, 0.10 * a), outline=rgba(ICE, 0.75 * a), width=3)
    for i in range(9):
        x = 330 + 52.5 * i
        line(d, [(x, CY0), (x, CY1)], rgba(ICE, 0.22 * a), 1.5)
    for fx, fy, t0 in flashes:
        dt = T - t0
        if 0 < dt < 1.6:
            R = 520 * dt
            circ(d, fx, fy, min(R, 170), fill=rgba(CYAN, 0.30 * math.exp(-dt / 0.35) * a))
            circ(d, fx, fy, 10 + 40 * dt, fill=rgba(WHITE, 0.9 * math.exp(-dt / 0.18) * a))
    for sx, sy in SENS:
        lit = 0.0
        for fx, fy, t0 in flashes:
            dist = math.hypot(sx - fx, sy - fy)
            dt = T - t0 - dist / 520
            if 0 < dt < 3 * hold:
                lit = max(lit, math.exp(-dt / hold) * math.exp(-dist / 230))
        circ(d, sx, sy, 5 + 6 * lit, fill=rgba((int(lerp(120, 255, lit)), int(lerp(170, 215, lit)), int(lerp(215, 120, lit))),
                                              (0.55 + 0.45 * lit) * a))
    if km:
        by = CY1 + 34
        line(d, [(CX0, by), (CX1, by)], rgba(WHITE, a), 3)
        line(d, [(CX0, by - 14), (CX0, by + 14)], rgba(WHITE, a), 3)
        line(d, [(CX1, by - 14), (CX1, by + 14)], rgba(WHITE, a), 3)
        texts.append((label_sprite("1 km", POP, 46, WHITE), 540, by + 50, a))


# ---------- scenes ----------
def scene_open(img, d, T, texts):
    a = win(T, -1.0, 7.5, 0.3, 0.4)
    if a <= 0:
        return
    streaks(d, T, a, n=12)
    cube(d, T, a, RANDOM_FLASHES, texts)
    an = win(T, 3.9, 7.3)       # one neutrino singled out
    if an > 0:
        p = ((T - 3.9) / 3.3)
        x, y = lerp(170, 900, p), lerp(660, 1480, p)
        line(d, [(x - 80, y - 90), (x, y)], rgba(GOLD, 0.9 * an), 4)
        circ(d, x, y, 7, fill=rgba(GOLD, an))
        texts.append((label_sprite("neutrino", size=34, fill=GOLD), min(x + 110, 850), y - 55, an))
        texts.append((label_sprite("almost everything is transparent to it", size=30, fill=GREY), 540, 1400, an))


def scene_you(img, d, T, texts):
    a = win(T, 7.5, 12.1, 0.4, 0.4)
    if a <= 0:
        return
    body = rgba((70, 88, 140), a)
    cx = 540
    circ(d, cx, 850, 62, fill=body)
    for (x0, y0, x1, y1, w) in ((cx, 950, cx, 1190, 120), (cx - 78, 960, cx - 120, 1170, 40), (cx + 78, 960, cx + 120, 1170, 40),
                                (cx - 32, 1190, cx - 44, 1440, 52), (cx + 32, 1190, cx + 44, 1440, 52)):
        line(d, [(x0, y0), (x1, y1)], body, w)
        circ(d, x0, y0, w / 2, fill=body); circ(d, x1, y1, w / 2, fill=body)
    streaks(d, T * 1.3, a, n=70, col=CYAN, alpha=0.6, width=2.5, length=140)
    texts.append((label_sprite("you", size=38, fill=WHITE), 760, 850, a))
    texts.append((label_sprite("neutrinos (illustration)", size=30, fill=GREY), 250, 690, a))


def scene_grow(img, d, T, texts):
    a = win(T, 12.1, 15.7, 0.4, 0.4)
    if a <= 0:
        return
    g = ss((T - 12.5) / 2.2)
    h = lerp(22, 240, g)
    cx, cy = 540, 1010
    streaks(d, T, a, n=16)
    rect(d, cx - h, cy - h, cx + h, cy + h, fill=rgba(ICE, 0.10 * a), outline=rgba(ICE, 0.8 * a), width=3)
    dt = T - 14.75
    if 0 < dt < 1.2:
        circ(d, cx + 60, cy - 40, min(520 * dt, 230), fill=rgba(CYAN, 0.32 * math.exp(-dt / 0.35) * a))
        circ(d, cx + 60, cy - 40, 10 + 40 * dt, fill=rgba(WHITE, 0.9 * math.exp(-dt / 0.18) * a))
    texts.append((label_sprite("small detector: no hits", size=32, fill=GREY), 540, 1330, win(T, 12.2, 13.6) * a))
    texts.append((label_sprite("bigger target, more hits", size=34, fill=GOLD), 540, 1330, win(T, 14.0, 15.6) * a))


SURF, PXKM = 760, 269.4          # surface line; 1 km in layout units (this scene is to scale)
HOLEX = [405 + 33.7 * i for i in range(9)]
Y1450, Y2450 = SURF + 1.45 * PXKM, SURF + 2.45 * PXKM


def scene_drill(img, d, T, texts):
    a = win(T, 15.7, 28.1, 0.4, 0.4)
    if a <= 0:
        return
    rect(d, 60, SURF, 960, 1470, fill=rgba(ICE, 0.07 * a))
    line(d, [(60, SURF), (960, SURF)], rgba(WHITE, 0.9 * a), 4)
    rect(d, 520, SURF - 20, 560, SURF, fill=rgba(GREY, a))
    texts.append((label_sprite("South Pole", size=32, fill=GREY), 760, SURF - 36, a))
    for i, x in enumerate(HOLEX):
        p = clamp((T - 16.3 - 0.14 * i) / 2.3)
        if p <= 0:
            continue
        yb = lerp(SURF, Y2450, p)
        line(d, [(x, SURF), (x, yb)], rgba(CYAN, 0.55 * a), 3)
        if p < 1:
            circ(d, x, yb, 12, fill=rgba(ORANGE, 0.35 * a))
            circ(d, x, yb, 6, fill=rgba((255, 220, 170), a))
    texts.append((label_sprite("hot-water drill", size=30, fill=ORANGE), 230, 1010, win(T, 16.6, 19.6) * a))
    ad = ss((T - 20.2) / 0.5) * a           # depth scale
    if ad > 0:
        bx = 345
        line(d, [(bx, SURF), (bx, Y2450)], rgba(WHITE, ad), 3)
        for y in (SURF, Y1450, Y2450):
            line(d, [(bx - 14, y), (bx + 14, y)], rgba(WHITE, ad), 3)
        texts.append((label_sprite("2,450 m", POP, 44, GOLD), 205, Y2450, ad))
        texts.append((label_sprite("1,450 m", POP, 38, WHITE), 215, Y1450, ad * ss((T - 23.9) / 0.5)))
    texts.append((label_sprite("9 of the 86 holes shown, drawn to scale", size=28, fill=GREY), 540, 1478, ss((T - 17.0) / 0.5) * a))
    if T > 23.8:                            # sensors go down
        for i, x in enumerate(HOLEX):
            for j in range(8):
                yt = lerp(Y1450, Y2450, j / 7)
                p = ss((T - 24.0 - 0.07 * i - 0.1 * (7 - j)) / 1.5)
                if p <= 0:
                    continue
                frozen = ss((T - 26.6) / 0.6)
                col = (int(lerp(255, 150, frozen)), int(lerp(225, 215, frozen)), int(lerp(150, 255, frozen)))
                circ(d, x, lerp(SURF, yt, p), 4.5, fill=rgba(col, a))
        ab = ss((T - 26.4) / 0.5) * a
        rect(d, HOLEX[0] - 12, Y1450 - 12, HOLEX[-1] + 12, Y2450 + 12, outline=rgba(GOLD, ab), width=3)
        bx = HOLEX[-1] + 36
        line(d, [(bx, Y1450), (bx, Y2450)], rgba(WHITE, ab), 3)
        line(d, [(bx - 12, Y1450), (bx + 12, Y1450)], rgba(WHITE, ab), 3)
        line(d, [(bx - 12, Y2450), (bx + 12, Y2450)], rgba(WHITE, ab), 3)
        texts.append((label_sprite("1 km", POP, 42, WHITE), bx + 80, (Y1450 + Y2450) / 2, ab))
        texts.append((label_sprite("60 sensors per hole", size=32, fill=CYAN), 750, 1010, win(T, 24.4, 28.0) * a))


HIT = (560, 990, 30.3)


def scene_hit(img, d, T, texts):
    a = win(T, 28.1, 33.3, 0.4, 0.4)
    if a <= 0:
        return
    streaks(d, T, a, n=8, alpha=0.25)
    p = clamp((T - 29.1) / 1.2)
    x, y = lerp(250, HIT[0], p), lerp(655, HIT[1], p)
    if T < HIT[2] + 0.1 and T > 29.1:
        line(d, [(lerp(250, x, 0.0), 655), (x, y)], rgba(GOLD, 0.55 * a), 3)
        circ(d, x, y, 7, fill=rgba(GOLD, a))
        texts.append((label_sprite("neutrino", size=34, fill=GOLD), x + 120, y - 30, a * ss((HIT[2] - T) / 0.3)))
    cube(d, T, a, [HIT], texts, hold=6.0)
    texts.append((label_sprite("the sensors catch the light (illustration)", size=30, fill=GREY), 540, 1400,
                  ss((T - 30.6) / 0.4) * a))


def scene_count(img, d, T, texts):
    a = win(T, 33.3, 38.7, 0.4, 0.4)
    if a <= 0:
        return
    streaks(d, T, a, n=8, alpha=0.25)
    cube(d, T, a, COUNT_FLASHES, texts, km=False)
    n = int(clamp((T - 34.0) / 0.1, 0, 28))
    if T > 34.0:
        n = min(28, n + 1)
    texts.append((label_sprite(str(n), POP, 120, GOLD), 540, 1310, a))
    texts.append((label_sprite("May 2010 to May 2012", size=32, fill=GREY), 540, 1420, a))


SOURCES = [(210, 800), (470, 720), (740, 790), (880, 960), (150, 1040)]


def scene_window(img, d, T, texts):
    a = win(T, 38.7, 44.5, 0.5, 0.4)
    if a <= 0:
        return
    ix, iy = 540, 1380
    for k, (sx, sy) in enumerate(SOURCES):
        pul = 0.5 + 0.5 * math.sin(2.2 * T + k)
        circ(d, sx, sy, 26 + 6 * pul, fill=rgba((255, 170, 110), 0.18 * a))
        circ(d, sx, sy, 9, fill=rgba((255, 225, 190), a))
        line(d, [(sx, sy), (ix, iy)], rgba(CYAN, 0.16 * a), 2)
        q = ((T - 38.7) * 0.55 + 0.21 * k) % 1.0
        x, y = lerp(sx, ix, q), lerp(sy, iy, q)
        circ(d, x, y, 6, fill=rgba(GOLD, a * ss((1 - q) / 0.08) * ss(q / 0.08)))
        if q < 0.25:
            circ(d, ix, iy, 46 + 160 * q, outline=rgba(CYAN, 0.6 * (1 - q / 0.25) * a), width=3)
    rect(d, ix - 38, iy - 38, ix + 38, iy + 38, fill=rgba(ICE, 0.22 * a), outline=rgba(GOLD, a), width=4)
    texts.append((label_sprite("IceCube", POP, 40, WHITE), 730, iy, a))
    texts.append((label_sprite("distant cosmic sources (illustration)", size=30, fill=GREY), 540, 665, a))


# ---------- frame ----------
def frame(T):
    global CUR
    img = BG.copy()
    d = CUR = Canvas(img)
    texts = []
    for sc in (scene_open, scene_you, scene_grow, scene_drill, scene_hit, scene_count, scene_window):
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
