#!/usr/bin/env python3
"""If we copied your brain, which one would be you? The no-cloning theorem says an exact quantum copy is impossible. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 brain_copy.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 brain_copy.py render 0 41.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 62.0            # layout units; output is W*S x H*S
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
    (0.0, 5.0, None, "Copy your brain. | *Which one is you?*"),
    (5.0, 10.0, None, "The copy wakes up | *certain it is you.*"),
    (10.0, 14.0, None, "But you are *still here.* | Nothing changed."),
    (14.0, 23.0, None, "Is consciousness | a copyable pattern? | *Nobody knows.*"),
    (23.0, 27.0, None, "Physics has a surprise: | a perfect copy | is *impossible.*"),
    (27.0, 38.0, "THE NO-CLONING THEOREM, 1982", "An unknown quantum | state *can never be | copied exactly.*"),
    (38.0, 48.0, None, "Teleporting one particle's | state is real, but it | *destroys the original.*"),
    (48.0, 53.0, None, "At the deepest level, | no copy of you | *could ever be exact.*"),
    (53.0, 62.0, None, "Does your mind need | that detail? | *Still a mystery.*"),
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
AX, BX_, FY, FS = 270, 730, 800, 0.86     # the two figures: x of each, head-centre y, scale
SEGS = [(0, 100, 0, 340, 120), (-78, 110, -120, 320, 40), (78, 110, 120, 320, 40),
        (-32, 340, -44, 590, 52), (32, 340, 44, 590, 52)]          # torso, arms, legs (head is a circle at 0,0 r62)


def dim(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


def body(d, cx, y0, s, col, a):
    """A neutral, generic human figure (no likeness): head centre at (cx, y0), feet at y0 + 616*s."""
    if a <= 0:
        return
    c = rgba(col, a)
    circ(d, cx, y0, 62 * s, fill=c)
    for x0, y0_, x1, y1, w in SEGS:
        line(d, [(cx + x0 * s, y0 + y0_ * s), (cx + x1 * s, y0 + y1 * s)], c, w * s)
        circ(d, cx + x0 * s, y0 + y0_ * s, w * s / 2, fill=c); circ(d, cx + x1 * s, y0 + y1 * s, w * s / 2, fill=c)


_br = np.random.default_rng(4)
BODY_DOTS = []                # points of light inside the figure, in figure units (head dots are left to the pattern)
while len(BODY_DOTS) < 300:
    k = int(_br.integers(0, 5))
    x0, y0_, x1, y1, w = SEGS[k]
    u = _br.uniform(); off = _br.uniform(-0.46, 0.46) * w
    BODY_DOTS.append((float(lerp(x0, x1, u) + off), float(lerp(y0_, y1, u)), float(_br.uniform(0, 6.28)),
                      float(_br.uniform(4, 10)), float(_br.uniform())))
for _ in range(110):          # extra weight on the torso so the figure reads clearly
    BODY_DOTS.append((float(_br.uniform(-56, 56)), float(_br.uniform(100, 340)), float(_br.uniform(0, 6.28)),
                      float(_br.uniform(4, 10)), float(_br.uniform())))
for _ in range(46):           # head outline
    th = _br.uniform(0, 6.28)
    BODY_DOTS.append((float(60 * math.cos(th)), float(60 * math.sin(th)), float(_br.uniform(0, 6.28)),
                      float(_br.uniform(4, 10)), float(_br.uniform())))


def sparkles(d, cx, y0, s, T, a, col=GOLD, jit=4.0, r=3.6, ymax=1e9, soft=0.0):
    """The figure as points of light. ymax (figure units) reveals it from the top; soft > 0 smears it."""
    if a <= 0:
        return
    for px, py, ph, sp, u in BODY_DOTS:
        if py > ymax:
            continue
        fl = 0.5 + 0.5 * math.sin(sp * T + ph)
        x = cx + (px + jit * math.sin(sp * 0.8 * T + ph)) * s
        y = y0 + (py + jit * math.cos(sp * 0.7 * T + 2 * ph)) * s
        edge = clamp((ymax - py) / 30)
        aa = a * (0.4 + 0.6 * edge) * (1 - 0.72 * soft)
        circ(d, x, y, r * (2.2 + 3.5 * soft), fill=rgba(col, 0.10 * aa))
        circ(d, x, y, r * (1 + 0.9 * soft), fill=rgba(lerp3(col, WHITE, 0.5 * fl * (1 - soft)), (0.35 + 0.65 * fl) * aa))
        if edge < 1:
            circ(d, x, y, r * 1.6, fill=rgba(WHITE, a * (1 - edge)))


HP = [(-30, -16), (-2, -36), (28, -18), (-36, 14), (-4, 0), (32, 12), (-12, 34), (18, 36)]     # the "pattern" in a head
HE = [(0, 1), (1, 2), (0, 4), (2, 4), (0, 3), (3, 4), (4, 5), (2, 5), (3, 6), (4, 6), (4, 7), (5, 7), (6, 7)]


def pattern(d, cx, y0, s, T, a, col=GOLD, jit=0.0):
    """The same small glowing network drawn inside each head."""
    if a <= 0:
        return
    circ(d, cx, y0, 58 * s, fill=rgba((4, 6, 18), 0.75 * a))
    pts = [(cx + (x + jit * math.sin(7.3 * T + 2.1 * i)) * s, y0 + (y + jit * math.cos(6.1 * T + 1.7 * i)) * s)
           for i, (x, y) in enumerate(HP)]
    for k, (i, j) in enumerate(HE):
        line(d, [pts[i], pts[j]], rgba(col, 0.55 * a), 2.2 * s)
        q = (0.9 * T + 0.37 * k) % 1.0
        circ(d, lerp(pts[i][0], pts[j][0], q), lerp(pts[i][1], pts[j][1], q), 2.6 * s, fill=rgba(WHITE, 0.9 * a))
    for i, (x, y) in enumerate(pts):
        pul = 0.5 + 0.5 * math.sin(4 * T + 1.3 * i)
        circ(d, x, y, 9 * s, fill=rgba(col, 0.20 * a))
        circ(d, x, y, (4.2 + 1.2 * pul) * s, fill=rgba(lerp3(col, WHITE, 0.5 * pul), a))


def figure(d, cx, T, a, col=GOLD, pat=1.0, **kw):
    body(d, cx, FY, FS, dim(col, 0.13), a * (1 - kw.get("soft", 0)) * clamp(kw.get("ymax", 1e9) / 600))
    sparkles(d, cx, FY, FS, T, a, col=col, **kw)
    pattern(d, cx, FY, FS, T, a * pat, col=col, jit=kw.get("soft", 0) * 14)


def ground(d, a):
    line(d, [(110, FY + 640 * FS), (890, FY + 640 * FS)], rgba(GREY, 0.30 * a), 2)


# ---------- scenes ----------
SCAN_END = 2.7


def scene_hook(img, d, T, texts):
    a = win(T, -1.0, 5.0, 0.2, 0.3)
    if a <= 0:
        return
    p = clamp((T + 0.25) / (SCAN_END + 0.25))
    ym = lerp(-90, 640, p)                                 # scan height in figure units
    ys = FY + ym * FS
    figure(d, AX, T * 1.4, a)
    figure(d, BX_, T * 1.4, a, col=CYAN, pat=ss((ym - 40) / 60) * 0.35, ymax=ym)
    sa = a * (1 - ss((T - SCAN_END) / 0.4))
    for x in (110, 890):                                   # scanner rails
        line(d, [(x, FY - 110), (x, FY + 650 * FS)], rgba(CYAN, 0.35 * sa), 3)
    rect(d, 110, ys - 26, 890, ys, fill=rgba(CYAN, 0.10 * sa))
    line(d, [(110, ys), (890, ys)], rgba(CYAN, 0.95 * sa), 5)
    line(d, [(110, ys), (890, ys)], rgba(WHITE, 0.8 * sa), 1.6)
    for k in range(9):                                     # data streaming from the original to the copy
        q = (2.2 * T + k / 9) % 1.0
        circ(d, lerp(AX + 90, BX_ - 90, q), ys - 6 + 5 * math.sin(20 * q + k), 4, fill=rgba(WHITE, sa * ss(q / 0.2) * ss((1 - q) / 0.2)))
    ground(d, a)
    if CAPTIONS:
        texts.append((label_sprite("you", POP, 44, GOLD), AX, 1410, a))
        texts.append((label_sprite("copy", POP, 44, CYAN), BX_, 1410, a * ss((T - SCAN_END) / 0.4)))
        texts.append((label_sprite("a thought experiment", size=28, fill=GREY), CX, 1475, a))


def scene_wake(img, d, T, texts):
    a = win(T, 5.0, 10.0, 0.3, 0.3)
    if a <= 0:
        return
    g = ss((T - 5.9) / 0.7)
    figure(d, AX, T * 1.4, a)
    figure(d, BX_, T * 1.4, a, col=CYAN, pat=lerp(0.35, 1.0, g))
    dt = T - 5.9
    if dt > 0:
        circ(d, BX_, FY, 62 * FS + 380 * dt, outline=rgba(CYAN, 0.9 * math.exp(-dt / 0.5) * a), width=5)
        circ(d, BX_, FY, 95, fill=rgba(CYAN, 0.16 * a * (0.6 + 0.4 * math.sin(5 * T))))
    for k in range(6):                                     # the same pattern, mirrored across
        q = (0.6 * T + k / 6) % 1.0
        circ(d, lerp(AX + 60, BX_ - 60, q), FY - 60 * math.sin(3.14 * q), 4, fill=rgba(GOLD, 0.8 * a * (1 - g) * ss(q / 0.2) * ss((1 - q) / 0.2)))
    ground(d, a)
    texts.append((label_sprite("you", POP, 44, GOLD), AX, 1410, a))
    texts.append((label_sprite("copy", POP, 44, CYAN), BX_, 1410, a))
    texts.append((label_sprite("“I am me.”", POP, 46, WHITE), BX_ - 20, 690, a * ss((T - 7.2) / 0.4)))
    texts.append((label_sprite("a thought experiment", size=28, fill=GREY), CX, 1475, a))


def scene_two(img, d, T, texts):
    a = win(T, 10.0, 14.0, 0.3, 0.3)
    if a <= 0:
        return
    figure(d, AX, T * 1.4, a)
    figure(d, BX_, T * 1.4, a, col=CYAN)
    pul = 0.5 + 0.5 * math.sin(4.5 * T)
    circ(d, AX, FY + 250 * FS, 260 + 14 * pul, outline=rgba(GOLD, 0.30 * a), width=3)
    ground(d, a)
    texts.append((label_sprite("?", POP, 250, WHITE), CX, 1010, a * (0.72 + 0.28 * pul)))
    if CAPTIONS:
        texts.append((label_sprite("you", POP, 44, GOLD), AX, 1410, a))
        texts.append((label_sprite("you?", POP, 44, CYAN), BX_, 1410, a))
        texts.append((label_sprite("a thought experiment", size=28, fill=GREY), CX, 1475, a))


_nr = np.random.default_rng(11)
NODES = []
while len(NODES) < 16:
    x, y = _nr.uniform(-135, 135), _nr.uniform(-135, 135)
    if math.hypot(x, y) < 140 and all(math.hypot(x - u, y - v) > 46 for u, v in NODES):
        NODES.append((float(x), float(y)))
NEDGE = [(i, j) for i in range(16) for j in range(i + 1, 16)
         if math.hypot(NODES[i][0] - NODES[j][0], NODES[i][1] - NODES[j][1]) < 105]
HLX, HRX, HY, HR = 240, 760, 1030, 175
LINKS = [i for i in range(16) if NODES[i][0] > 10][:7]     # nodes on the inner side that get joined across


def net(d, cx, cy, T, a, col):
    circ(d, cx, cy, HR, fill=rgba(col, 0.05 * a), outline=rgba(col, 0.75 * a), width=4)
    for k, (i, j) in enumerate(NEDGE):
        p0, p1 = NODES[i], NODES[j]
        line(d, [(cx + p0[0], cy + p0[1]), (cx + p1[0], cy + p1[1])], rgba(col, 0.42 * a), 2.2)
        q = (0.8 * T + 0.29 * k) % 1.0
        circ(d, cx + lerp(p0[0], p1[0], q), cy + lerp(p0[1], p1[1], q), 3.2, fill=rgba(WHITE, 0.9 * a))
    for i, (x, y) in enumerate(NODES):
        pul = 0.5 + 0.5 * math.sin(3.5 * T + 1.9 * i)
        circ(d, cx + x, cy + y, 13, fill=rgba(col, 0.20 * a))
        circ(d, cx + x, cy + y, 6 + 2 * pul, fill=rgba(lerp3(col, WHITE, 0.5 * pul), a))


def scene_pattern(img, d, T, texts):
    a = win(T, 14.0, 23.0, 0.3, 0.06)
    if a <= 0:
        return
    net(d, HLX, HY, T, a, GOLD)
    net(d, HRX, HY, T, a, CYAN)
    for n, i in enumerate(LINKS):                          # the web reaches from one head to the other
        g = ss((T - 15.2 - 0.55 * n) / 1.3)
        if g <= 0:
            continue
        x0, y0 = HLX + NODES[i][0], HY + NODES[i][1]
        x1, y1 = HRX - NODES[i][0], HY + NODES[i][1]       # mirrored partner
        bow = (-1 if n % 2 else 1) * (70 + 34 * n)
        pts = []
        for j in range(31):
            u = j / 30 * g
            pts.append((lerp(x0, x1, u), lerp(y0, y1, u) + bow * math.sin(3.14 * u)))
        line(d, pts, rgba(lerp3(GOLD, CYAN, 0.5), 0.55 * a), 2.4)
        q = (0.45 * T + 0.17 * n) % 1.0
        if q < g:
            circ(d, lerp(x0, x1, q), lerp(y0, y1, q) + bow * math.sin(3.14 * q), 4.5, fill=rgba(WHITE, a))
    texts.append((label_sprite("you", POP, 44, GOLD), HLX, 800, a))
    texts.append((label_sprite("copy", POP, 44, CYAN), HRX, 800, a))
    texts.append((label_sprite("the same pattern?", POP, 50, WHITE), CX, 1300, a * ss((T - 16.0) / 0.5)))
    texts.append((label_sprite("one of the deepest open questions in science", size=32, fill=GREY), CX, 1375, a * ss((T - 19.5) / 0.5)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), CX, 1475, a))


CUT_T = 23.0


def scene_cut(img, d, T, texts):
    a = win(T, CUT_T, 27.0, 0.05, 0.3)
    if a <= 0:
        return
    dt = T - CUT_T
    circ(d, CX, 1040, min(900, 2400 * dt), fill=rgba(WHITE, 0.55 * math.exp(-dt / 0.16) * a))
    circ(d, CX, 1040, 60 + 700 * dt, outline=rgba(RED, 0.9 * math.exp(-dt / 0.45) * a), width=7)
    circ(d, CX, 1040, 30 + 420 * dt, outline=rgba(WHITE, 0.7 * math.exp(-dt / 0.35) * a), width=4)
    for k, x in enumerate((AX + 10, BX_ - 10)):            # two identical marks, and a bar through the idea
        col = GOLD if k == 0 else CYAN
        circ(d, x, 1210, 70, fill=rgba(col, 0.10 * a), outline=rgba(col, 0.9 * a), width=4)
        for i in range(5):
            th = 1.1 * T + 1.2566 * i
            circ(d, x + 36 * math.cos(th), 1210 + 36 * math.sin(th), 7, fill=rgba(col, a))
    line(d, [(AX + 100, 1210), (BX_ - 100, 1210)], rgba(WHITE, 0.8 * a), 4)
    line(d, [(BX_ - 124, 1192), (BX_ - 100, 1210), (BX_ - 124, 1228)], rgba(WHITE, 0.8 * a), 4)
    g = ss((dt - 0.9) / 0.3)
    line(d, [(CX - 62 * g, 1210 - 62 * g), (CX + 62 * g, 1210 + 62 * g)], rgba(RED, a * g), 12)
    line(d, [(CX - 62 * g, 1210 + 62 * g), (CX + 62 * g, 1210 - 62 * g)], rgba(RED, a * g), 12)
    texts.append((label_sprite("A PERFECT COPY", POP, 78, WHITE), CX, 880, a))
    line(d, [(CX - 370 * g, 884), (CX + 370 * g, 884)], rgba(RED, a * g), 9)
    texts.append((label_sprite("IMPOSSIBLE", POP, 104, RED), CX, 1010, a * ss((dt - 1.3) / 0.3)))


def sphere(d, cx, cy, R, a, col=GREY):
    circ(d, cx, cy, R, fill=rgba(col, 0.05 * a), outline=rgba(col, 0.8 * a), width=3)
    d.ellipse([(cx - R) * S, (cy - R * 0.28) * S, (cx + R) * S, (cy + R * 0.28) * S], outline=rgba(col, 0.40 * a), width=max(1.0, 2 * S))
    line(d, [(cx, cy - R), (cx, cy + R)], rgba(col, 0.28 * a), 2)


def arrow(d, cx, cy, R, th, ph, a, col=GOLD, w=7.0):
    """A quantum state drawn as an arrow from the centre of the sphere (th from the top, ph around)."""
    if a <= 0:
        return
    x = cx + R * math.sin(th) * math.cos(ph)
    y = cy - R * math.cos(th) + R * 0.28 * math.sin(th) * math.sin(ph)
    line(d, [(cx, cy), (x, y)], rgba(col, a), w)
    ang = math.atan2(y - cy, x - cx)
    for s_ in (-1, 1):
        line(d, [(x, y), (x - 30 * math.cos(ang + s_ * 0.45), y - 30 * math.sin(ang + s_ * 0.45))], rgba(col, a), w)
    circ(d, x, y, 15, fill=rgba(col, 0.30 * a))
    circ(d, cx, cy, 7, fill=rgba(col, a))


def state(T):
    return 0.95 + 0.10 * math.sin(1.3 * T), -0.5 + 0.9 * math.sin(0.5 * T)


def scene_noclone(img, d, T, texts):
    a = win(T, 27.0, 38.0, 0.3, 0.3)
    if a <= 0:
        return
    lx, rx, cy, R = 235, 765, 1010, 150
    th, ph = state(T)
    sphere(d, lx, cy, R, a)
    arrow(d, lx, cy, R, th, ph, a)
    rect(d, CX - 78, cy - 86, CX + 78, cy + 86, fill=rgba((40, 52, 84), 0.9 * a), outline=rgba(CYAN, a), width=3)
    run_ = win(T, 29.4, 32.4, 0.3, 0.3)                    # the machine tries
    for k in range(8):
        q = (1.8 * T + k / 8) % 1.0
        circ(d, lerp(lx + R + 10, CX - 84, q), cy, 4.5, fill=rgba(GOLD, a * run_ * ss(q / 0.2) * ss((1 - q) / 0.2)))
        circ(d, lerp(CX + 84, rx - R - 10, q), cy + 5 * math.sin(40 * q + k), 4.5, fill=rgba(CYAN, a * run_ * ss(q / 0.2) * ss((1 - q) / 0.2)))
    for k in range(3):
        circ(d, CX - 40 + 40 * k, cy + 52, 7, fill=rgba(lerp3(CYAN, WHITE, 0.5 + 0.5 * math.sin(14 * T + 2 * k)), a * (0.3 + 0.7 * run_)))
    g = a * ss((T - 31.4) / 0.9)                           # what comes out: smeared, and pointing wrong
    sphere(d, rx, cy, R, a * ss((T - 28.0) / 0.5), col=CYAN)
    for k in range(9):
        t2 = th + 0.9 + 0.55 * math.sin(2.3 * T + 1.7 * k)
        p2 = ph + 2.0 + 1.1 * math.sin(1.9 * T + 2.9 * k)
        arrow(d, rx, cy, R, t2, p2, 0.20 * g, col=CYAN, w=11)
    circ(d, rx, cy, R * 0.72, fill=rgba(CYAN, 0.08 * g))
    texts.append((label_sprite("COPY", POP, 38, WHITE), CX, cy - 20, a))
    texts.append((label_sprite("unknown", size=30, fill=GOLD), lx, cy - R - 78, a))
    texts.append((label_sprite("quantum state", size=30, fill=GOLD), lx, cy - R - 40, a))
    texts.append((label_sprite("not the same", POP, 40, CYAN), rx, cy - R - 50, g))
    texts.append((label_sprite("1982", POP, 150, GOLD), CX, 1310, a * ss((T - 29.0) / 0.4)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), CX, 1475, a))


def scene_teleport(img, d, T, texts):
    a = win(T, 38.0, 48.0, 0.3, 0.3)
    if a <= 0:
        return
    ax, ay, bx, by, R = 235, 1180, 735, 900, 135
    g = ss((T - 41.0) / 2.6)                               # the state leaves here and appears there
    th, ph = state(T)
    sphere(d, ax, ay, R, a, col=lerp3(GOLD, GREY, g))
    sphere(d, bx, by, R, a, col=lerp3(GREY, GOLD, g))
    arrow(d, ax, ay, R, th, ph, a * (1 - g))
    arrow(d, bx, by, R, th, ph, a * g)
    pts = []                                               # shared entanglement: a wavy link
    for j in range(61):
        u = j / 60
        x, y = lerp(ax + 90, bx - 90, u), lerp(ay - 100, by + 100, u)
        wv = 13 * math.sin(u * 6.28 * 7 - 5 * T) * math.sin(3.14 * u)
        pts.append((x + 0.62 * wv, y + 0.78 * wv))
    line(d, pts, rgba(CYAN, 0.75 * a), 3)
    ma = a * ss((T - 39.6) / 0.5)                          # the ordinary message, travelling at a finite speed
    arc = [(lerp(ax + 120, bx + 20, j / 40), lerp(ay + 90, by + 150, j / 40) + 110 * math.sin(3.14 * j / 40)) for j in range(41)]
    for j in range(0, 40, 2):
        line(d, [arc[j], arc[j + 1]], rgba(WHITE, 0.55 * ma), 2.4)
    for k in range(4):
        q = (0.33 * T + k / 4) % 1.0
        i = min(39, int(q * 40)); f = q * 40 - i
        circ(d, lerp(arc[i][0], arc[i + 1][0], f), lerp(arc[i][1], arc[i + 1][1], f), 7, fill=rgba(WHITE, ma * ss(q / 0.1) * ss((1 - q) / 0.1)))
    texts.append((label_sprite("entanglement", size=30, fill=CYAN), 395, 975, a))
    texts.append((label_sprite("+ an ordinary message", size=30, fill=WHITE), 700, 1345, ma))
    texts.append((label_sprite("(never faster than light)", size=27, fill=GREY), 700, 1385, ma))
    texts.append((label_sprite("original state: gone", POP, 36, RED), ax + 10, ay + R + 48, a * ss((g - 0.85) / 0.15)))
    texts.append((label_sprite("the state arrives", POP, 36, GOLD), bx - 20, by - R - 44, a * ss((g - 0.85) / 0.15)))
    texts.append((label_sprite("single particles only · illustration", size=28, fill=GREY), CX, 1480, a))


def scene_blur(img, d, T, texts):
    a = win(T, 48.0, 53.0, 0.3, 0.3)
    if a <= 0:
        return
    g = ss((T - 48.8) / 3.0)
    figure(d, AX, T * 1.4, a)
    figure(d, BX_, T * 1.4, a, col=CYAN, jit=4 + 20 * g, soft=0.85 * g)
    ground(d, a)
    texts.append((label_sprite("≠", POP, 170, WHITE), CX, 1010, a * ss((T - 50.2) / 0.5)))
    texts.append((label_sprite("you", POP, 44, GOLD), AX, 1410, a))
    texts.append((label_sprite("never exact", POP, 44, CYAN), BX_, 1410, a * ss((T - 50.2) / 0.5)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), CX, 1475, a))


_st = np.random.default_rng(21)
STARS = [(float(_st.uniform(40, 940)), float(_st.uniform(660, 1500)), float(_st.uniform(0, 6.28)), float(_st.uniform(0.6, 2.4)))
         for _ in range(110)]


def scene_end(img, d, T, texts):
    a = win(T, 53.0, 62.5, 0.4, 0.4)
    if a <= 0:
        return
    for x, y, ph, sp in STARS:                             # the sky comes alive around the one figure
        tw = 0.5 + 0.5 * math.sin(sp * T + ph)
        circ(d, x, y, 1.6 + 1.8 * tw, fill=rgba(WHITE, a * (0.25 + 0.6 * tw)))
    for k in range(3):
        q = (T * 0.20 + k / 3) % 1.0
        circ(d, CX, FY + 260 * FS, 110 + 430 * q, outline=rgba(GOLD, 0.22 * (1 - q) * a), width=3)
    body(d, CX, FY, FS, dim(GOLD, 0.13), a)
    sparkles(d, CX, FY, FS, T * 1.2, a, jit=5.0, r=4.0)
    pattern(d, CX, FY, FS, T, a)
    ground(d, a)
    texts.append((label_sprite("one of a kind", POP, 56, GOLD), CX, 1420, a * ss((T - 57.6) / 0.6)))


SCENES = (scene_hook, scene_wake, scene_two, scene_pattern, scene_cut, scene_noclone, scene_teleport, scene_blur, scene_end)


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
