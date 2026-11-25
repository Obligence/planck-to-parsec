#!/usr/bin/env python3
"""Your head is older than your feet: gravity slows time, so a clock higher up runs faster.
NIST measured it across 33 cm (2010), JILA across 1 mm (2022).
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 head_older_than_feet.py preview 0 6.4 12      -> frame_<t>.png files
  python3 head_older_than_feet.py render 0 43 out.mp4   -> renders that time range
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
    (0.0, 3.5, None, "Your head is *older* | than your *feet.*"),
    (3.5, 10.0, "GENERAL RELATIVITY", "Gravity | *slows time.*"),
    (10.0, 16.5, "NIST, 2010", "One clock lifted | just *33 cm.*"),
    (16.5, 23.0, None, "*90 billionths* | *of a second* | over a lifetime."),
    (23.0, 30.0, "JILA, 2022", "Then across just | *1 millimetre.*"),
    (30.0, 37.0, None, "So your head | *ages faster.*"),
    (37.0, 43.0, None, "Too small to feel. | *But real.*"),
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

# ---------- facts used on screen (sources: NIST news release 23 Sept 2010, "NIST Pair of Aluminum Atomic Clocks Reveal
# Einstein's Relativity at a Personal Scale" (33 cm, about 90 billionths of a second over a 79-year lifetime);
# C. W. Chou, D. B. Hume, T. Rosenband, D. J. Wineland, "Optical Clocks and Relativity", Science 329, 1630 (2010);
# NIST news release 16 Feb 2022, "JILA Atomic Clocks Measure Einstein's General Relativity at Millimeter Scale"
# (1 mm, about 100,000 strontium atoms, shift ~1e-19); T. Bothwell et al., Nature 602, 420 (2022)) ----------
def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


CX = 470                           # picture centre (the right-hand edge stays clear for the Shorts buttons)
T1, T2, T3, T4, T5, T6, T7 = 0.0, 3.5, 10.0, 16.5, 23.0, 30.0, 37.0
SKIN = (150, 170, 215)


def clock(d, x, y, r, ang, col, a, glow=0.0):
    """A simple clock face with one sweeping hand (angle in turns, 0 = 12 o'clock)."""
    if a <= 0.004:
        return
    for k in range(6):
        circ(d, x, y, r + 4 + 5 * k, fill=rgba(col, (0.03 + 0.05 * glow) * a))
    circ(d, x, y, r, fill=rgba((12, 18, 40), 0.95 * a), outline=rgba(col, a), width=4)
    for k in range(12):
        q = 2 * math.pi * k / 12
        r0 = r * (0.78 if k % 3 == 0 else 0.86)
        line(d, [(x + r0 * math.sin(q), y - r0 * math.cos(q)), (x + r * 0.94 * math.sin(q), y - r * 0.94 * math.cos(q))],
             rgba(WHITE, 0.8 * a), 3 if k % 3 == 0 else 2)
    q = 2 * math.pi * ang
    line(d, [(x - 0.15 * r * math.sin(q), y + 0.15 * r * math.cos(q)), (x + 0.8 * r * math.sin(q), y - 0.8 * r * math.cos(q))],
         rgba(col, a), 5)
    circ(d, x, y, 6, fill=rgba(WHITE, a))


def person(d, T, a, cx=CX - 120, top=700, foot=1405):
    """An original, faceless stick figure, standing; breathing slightly so the frame is never still."""
    b = 3 * math.sin(1.6 * T)
    hy = top + 52 + b * 0.5
    col = rgba(SKIN, a)
    circ(d, cx, hy, 60, fill=rgba(SKIN, 0.12 * a))
    circ(d, cx, hy, 50, fill=rgba((30, 40, 72), a), outline=col, width=5)
    neck, hip = hy + 62, top + 400
    line(d, [(cx, neck), (cx, hip)], col, 16)
    sh = neck + 30
    line(d, [(cx, sh), (cx - 85, sh + 150 + b), (cx - 100, sh + 270 + b)], col, 12)
    line(d, [(cx, sh), (cx + 85, sh + 150 + b), (cx + 100, sh + 270 + b)], col, 12)
    line(d, [(cx, hip), (cx - 62, foot - 140), (cx - 70, foot)], col, 14)
    line(d, [(cx, hip), (cx + 62, foot - 140), (cx + 70, foot)], col, 14)
    line(d, [(cx - 100, foot), (cx - 52, foot)], col, 12)
    line(d, [(cx + 52, foot), (cx + 100, foot)], col, 12)
    line(d, [(cx - 260, foot + 14), (cx + 470, foot + 14)], rgba(GREY, 0.5 * a), 3)
    return hy


def scene_person(img, d, T, texts):
    """0-3.5 and again from 30 to the end (so the Short loops): a person with a clock at the head and at the feet."""
    a = win(T, -1.0, T2 + 0.4, 0.2, 0.4) + win(T, T6 - 0.3, DUR + 2, 0.5, 0.3)
    if a <= 0.004:
        return
    t = T - DUR if T > 20 else T                    # at the very end the hands stand exactly as at the start
    hy = person(d, t, a)
    hx, fx, fy = CX + 190, CX + 190, 1300
    head_ang, feet_ang = 0.08 + 0.36 * t, 0.08 + 0.27 * t     # the head clock runs ahead (hugely exaggerated)
    for k in range(3):                                         # faint ripples: the head clock "ticking ahead"
        f = (0.9 * t + k / 3) % 1.0
        circ(d, hx, hy, 72 + 60 * f, outline=rgba(GOLD, 0.45 * (1 - f) * a), width=2)
    clock(d, hx, hy, 66, head_ang, GOLD, a, glow=0.6)
    clock(d, fx, fy, 66, feet_ang, CYAN, a)
    line(d, [(CX - 50, hy), (hx - 78, hy)], rgba(GOLD, 0.5 * a), 2)
    line(d, [(CX - 40, fy + 105), (fx - 78, fy)], rgba(CYAN, 0.5 * a), 2)
    if CAPTIONS:
        late = T > 20
        sa = ss((T - T6 - 0.8) / 0.5) if late else 0.0
        texts.append((label_sprite("head", POP, 34, GOLD), hx + 150, hy - 18, a))
        texts.append((label_sprite("feet", POP, 34, CYAN), fx + 150, fy - 18, a))
        texts.append((label_sprite("faster", POP, 30, GOLD), hx + 150, hy + 22, a * sa))
        texts.append((label_sprite("slower", POP, 30, CYAN), fx + 150, fy + 22, a * sa))
        if late:
            texts.append((label_sprite("difference hugely exaggerated", size=26, fill=GREY), CX, 1455, a * (1 - ss((T - (DUR - 2.9)) / 0.3))))
            qa = a * ss((T - (DUR - 2.6)) / 0.4)
            texts.append((label_sprite("Mountain or beach:", POP, 42, GOLD), CX, 1460, qa))
            texts.append((label_sprite("who ages faster?", POP, 42, GOLD), CX, 1512, qa))


def scene_gravity(img, d, T, texts):
    """3.5-10: gravity slows time: clocks at three heights above Earth, slower the closer they are."""
    a = win(T, T2, T3 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    ey, er = 2490, 1050                                  # Earth: a big curved horizon at the bottom
    for k in range(10):
        circ(d, CX, ey, er + 18 + 14 * k, fill=rgba((70, 140, 255), 0.022 * a))
    circ(d, CX, ey, er, fill=rgba((18, 52, 112), a))
    circ(d, CX, ey, er - 30, fill=rgba((12, 36, 82), a))
    for k in range(6):                                  # gentle curved lines: gravity's pull, deepest near the ground
        yy = ey - er - 40 - 95 * k
        bend = 70 - 10 * k
        pts = [(x, yy + bend * (1 - ((x - CX) / 540) ** 2)) for x in range(-40, W + 41, 30)]
        line(d, pts, rgba(CYAN, (0.22 - 0.03 * k) * a), 2)
    rates = (0.40, 0.30, 0.20)                           # turns per second, exaggerated
    ys = (800, 1030, 1260)
    t = T - T2
    for k, (yy, rr) in enumerate(zip(ys, rates)):
        ca = a * ss((t - 0.3 - 0.35 * k) / 0.4)
        col = lerp3(GOLD, CYAN, k / 2)
        clock(d, CX, yy, 62 - 4 * k, 0.1 * k + rr * t, col, ca, glow=0.5 * (2 - k) / 2)
    if CAPTIONS:
        la = a * ss((t - 1.5) / 0.5)
        texts.append((label_sprite("higher: faster", POP, 34, GOLD), CX + 250, ys[0], la))
        texts.append((label_sprite("lower: slower", POP, 34, CYAN), CX + 250, ys[2], la))
        texts.append((label_sprite("Earth", POP, 36, WHITE), CX, 1490, la))
        texts.append((label_sprite("rates hugely exaggerated", size=26, fill=GREY), CX + 250, ys[1], la))


def lab_clock(d, x, y, a, rate, T, col):
    """An optical clock drawn as a box with a single trapped ion glowing in a laser beam."""
    rect(d, x - 120, y - 70, x + 120, y + 70, fill=rgba((20, 28, 56), a), outline=rgba(col, a), width=4)
    line(d, [(x - 110, y), (x + 110, y)], rgba((255, 90, 120), 0.7 * a), 3)
    p = 0.5 + 0.5 * math.sin(2 * math.pi * rate * T)
    circ(d, x, y, 20 + 8 * p, fill=rgba(col, 0.18 * a))
    circ(d, x, y, 9, fill=rgba(WHITE, a))
    for k in range(4):                                   # tick pulses leaving the clock
        f = (rate * T + k / 4) % 1.0
        rect(d, x - 100 + 200 * f - 4, y + 52, x - 100 + 200 * f + 4, y + 60, fill=rgba(col, a * math.sin(math.pi * f)))


def scene_lab(img, d, T, texts):
    """10-23: two atomic clocks; one is jacked up 33 cm and runs faster; over a 79-year life: ~90 billionths of a second."""
    a = win(T, T3, T5 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T3
    lift = ss((t - 1.6) / 1.6) * 190                     # 33 cm, drawn as 190 layout units
    xl, xr, base = CX - 210, CX + 200, 1180
    for x, h in ((xl, 0), (xr, lift)):                  # tables
        rect(d, x - 150, base - h, x + 150, base - h + 18, fill=rgba((120, 132, 165), a))
        line(d, [(x - 130, base - h + 18), (x - 130, 1300)], rgba((120, 132, 165), a), 8)
        line(d, [(x + 130, base - h + 18), (x + 130, 1300)], rgba((120, 132, 165), a), 8)
    if lift > 2:                                          # the jack under the right table
        n = 4
        for k in range(n):
            y0 = 1300 - (1300 - (base - lift + 18)) * k / n
            y1 = 1300 - (1300 - (base - lift + 18)) * (k + 1) / n
            line(d, [(xr - 60, y0), (xr + 60, y1)], rgba(GREY, a), 5)
            line(d, [(xr + 60, y0), (xr - 60, y1)], rgba(GREY, a), 5)
    line(d, [(xl - 260, 1300), (xr + 230, 1300)], rgba(GREY, 0.6 * a), 3)
    up = ss((t - 3.4) / 0.5)
    lab_clock(d, xl, base - 70, a, 1.0, T, CYAN)
    lab_clock(d, xr, base - lift - 70, a, 1.0 + 0.35 * up, T, GOLD)
    if lift > 2:                                          # 33 cm bracket
        bx = xr + 175
        ba = a * ss((t - 2.4) / 0.4)
        line(d, [(bx, base - 70), (bx, base - lift - 70)], rgba(GOLD, ba), 3)
        for yy in (base - 70, base - lift - 70):
            line(d, [(bx - 12, yy), (bx + 12, yy)], rgba(GOLD, ba), 3)
        if CAPTIONS:
            texts.append((label_sprite("33 cm", POP, 40, GOLD), bx + 40, base - 70 - lift - 45, ba))
    if CAPTIONS:
        texts.append((label_sprite("atomic clock", POP, 30, WHITE), xl, base - 175, a * ss((t - 0.3) / 0.4)))
        texts.append((label_sprite("ticks faster", POP, 30, GOLD), xr - 20, base - lift - 175, a * up * (1 - ss((T - T4 - 0.3) / 0.4))))
    # 17-23: a 79-year life bar fills, and the gain counts up to ~90 billionths of a second
    la = a * ss((T - T4 - 0.3) / 0.5)
    if la > 0.004:
        p = ss((T - T4 - 0.8) / 4.2)
        x0, x1, y = CX - 380, CX + 380, 1400
        rect(d, x0, y - 14, x1, y + 14, outline=rgba(GREY, la), width=2)
        rect(d, x0 + 3, y - 11, x0 + 3 + (x1 - x0 - 6) * p, y + 11, fill=rgba(GOLD, 0.85 * la))
        if CAPTIONS:
            texts.append((label_sprite(f"age {int(round(79 * p))}", POP, 34, WHITE), x0 + 70, y - 50, la))
            texts.append((label_sprite(f"+{int(round(90 * p))} billionths of a second", POP, 40, GOLD), CX + 70, y - 50, la))
            texts.append((label_sprite("for a clock 33 cm higher, over a 79-year life", size=26, fill=GREY), CX, y + 48, la))


_ag = np.random.default_rng(3)
NA = 700
AX = _ag.normal(0, 1, NA); AY = _ag.uniform(0, 1, NA) ** 1.0; AP = _ag.uniform(0, 6.283, NA)


def scene_atoms(img, d, T, texts):
    """23-30: a cloud of strontium atoms one millimetre tall, about the width of a pencil tip; its top ticks faster."""
    a = win(T, T5, T6 + 0.3, 0.4, 0.4)
    if a <= 0.004:
        return
    t = T - T5
    za = a * ss((t - 0.2) / 0.6)
    # pencil tip coming down from the top of the picture
    px, tip = CX - 230, 1000
    poly(d, [(px - 70, 700), (px + 70, 700), (px + 14, tip - 40), (px - 14, tip - 40)], rgba((196, 150, 100), za))
    poly(d, [(px - 14, tip - 40), (px + 14, tip - 40), (px, tip)], rgba((60, 64, 78), za))
    rect(d, px - 70, 655, px + 70, 700, fill=rgba((200, 120, 50), za))
    # atom cloud: 1 mm tall drawn as 400 layout units
    cx, top, hgt = CX + 70, 840, 400
    for i in range(NA):
        y = top + hgt * AY[i]
        x = cx + 95 * AX[i] * (0.55 + 0.45 * math.sin(math.pi * AY[i]))
        f = 1 - AY[i]                                   # 1 at the top, 0 at the bottom
        rate = 1.4 + 1.2 * f
        tw = 0.55 + 0.45 * math.sin(rate * 3 * T + AP[i])
        c = lerp3(CYAN, GOLD, f)
        circ(d, x, y, 3.2, fill=rgba(c, za * tw))
    bx = cx + 220
    ba = a * ss((t - 1.2) / 0.4)
    line(d, [(bx, top), (bx, top + hgt)], rgba(WHITE, ba), 3)
    for yy in (top, top + hgt):
        line(d, [(bx - 12, yy), (bx + 12, yy)], rgba(WHITE, ba), 3)
    if CAPTIONS:
        texts.append((label_sprite("1 mm", POP, 40, WHITE), bx + 70, top + hgt / 2, ba))
        texts.append((label_sprite("pencil tip", POP, 30, WHITE), px, tip + 40, za))
        texts.append((label_sprite("top: faster", POP, 30, GOLD), cx, top - 40, ba))
        texts.append((label_sprite("bottom: slower", POP, 30, CYAN), cx, top + hgt + 40, ba))
        sa = a * ss((t - 2.2) / 0.5)
        texts.append((label_sprite("about 100,000 strontium atoms", POP, 34, WHITE), CX, 1370, sa))
        texts.append((label_sprite("difference: 0.0000000000000000001", POP, 32, GOLD), CX, 1420, sa))
        texts.append((label_sprite("illustration, not to scale", size=26, fill=GREY), CX, 1468, sa))


SCENES = (scene_person, scene_gravity, scene_lab, scene_atoms)


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
