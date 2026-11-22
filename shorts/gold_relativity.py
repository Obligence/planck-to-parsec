#!/usr/bin/env python3
"""Without Einstein, gold would be silver: gold's inner electrons move at about 58% of the speed of light (Z/137),
relativity shrinks its orbits, gold absorbs blue light, and the reflected rest looks yellow.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 gold_relativity.py preview 0 6.4 12      -> frame_<t>.png files
  python3 gold_relativity.py render 0 51 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 51.0            # layout units; output is W*S x H*S
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
    (0.0, 5.0, None, "Without Einstein, | *gold would be silver.*"),
    (5.0, 10.0, None, "Almost every metal | is silvery. | *Gold isn't.*"),
    (10.0, 17.0, None, "79 protons whip its | inner electrons to | *58% of light speed.*"),
    (17.0, 23.0, None, "At that speed, | relativity | *shrinks their orbits.*"),
    (23.0, 30.0, None, "Now gold can | *absorb blue light.*"),
    (30.0, 36.0, None, "White light | minus blue | = *gold.*"),
    (36.0, 43.0, None, "Relativity off: | *gold turns silver.*"),
    (43.0, 51.0, None, "Every gold ring: | *a piece of relativity.*"),
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

# ---------- facts used on screen (sources: Wikipedia "Relativistic quantum chemistry" (after Pyykkoe), RSC Education,
# J. Walker "What gives gold that mellow glow?") ----------
Z_GOLD = 79                       # protons in a gold nucleus
V_1S = Z_GOLD / 137.036           # innermost electron speed / c, about 0.58
SHRINK_1S = 0.22                  # the 1s orbit is about 22% smaller with relativity

CX = 500                          # picture centre (the right-hand edge stays clear for the Shorts buttons)
GOLD_M = ((120, 80, 14), (212, 160, 46), (250, 222, 130))       # dark, mid, highlight
SILV_M = ((88, 93, 104), (165, 170, 181), (228, 231, 238))
BLUE = (80, 130, 255)


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


def metal(m):
    """m = 0 gold, 1 silver -> (dark, mid, highlight)."""
    return tuple(lerp3(g, s, clamp(m)) for g, s in zip(GOLD_M, SILV_M))


def ring(d, cx, cy, R, T, a, m=0.0, tilt=0.42, w=46):
    """A ring seen at an angle: a tube drawn as many thin ellipses, shaded across its thickness, with a moving glint."""
    if a <= 0:
        return
    dk, md, hi = metal(m)
    n = 22
    for k in range(n):
        f = k / (n - 1)                                      # 0 outer edge -> 1 inner edge
        sh = math.sin(math.pi * f) ** 0.7                    # brightest in the middle of the tube
        col = lerp3(dk, md, sh) if f < 0.62 else lerp3(dk, md, sh * 0.8)
        r = R + w / 2 - w * f
        ry = r * tilt + (w * 0.18) * (0.5 - f)
        d.ellipse([(cx - r) * S, (cy - ry) * S, (cx + r) * S, (cy + ry) * S], outline=rgba(col, a), width=max(1.0, 2.6 * S))
    r, ry = R + w * 0.12, (R + w * 0.12) * tilt + w * 0.04   # glints sweeping round the ring
    for k, (sp, ln, al) in enumerate(((0.9, 34, 0.95), (0.9, 14, 0.6))):
        st = (sp * 70 * T + 180 * k) % 360
        d.d.arc([(cx - r) * S, (cy - ry) * S, (cx + r) * S, (cy + ry) * S], st, st + ln,
                aggdraw.Pen(hi, 7 * S, int(255 * al * a)))
    q = (0.45 * T) % 1.0                                     # a sparkle
    sx, sy = cx + r * math.cos(6.283 * q * 0.0 - 0.6), cy - ry * 0.9
    tw = max(0.0, math.sin(math.pi * ((1.1 * T) % 1.0)))
    for ang in (0, 90):
        ln = 26 * tw
        line(d, [(sx - ln * math.cos(math.radians(ang)), sy - ln * math.sin(math.radians(ang))),
                 (sx + ln * math.cos(math.radians(ang)), sy + ln * math.sin(math.radians(ang)))], rgba(WHITE, 0.9 * tw * a), 3)


def bar(d, x, y, w, h, m_or_cols, a):
    """A metal bar (ingot face) with a vertical gradient."""
    dk, md, hi = m_or_cols
    n = 16
    for k in range(n):
        f = k / (n - 1)
        col = lerp3(hi, md, f / 0.4) if f < 0.4 else lerp3(md, dk, (f - 0.4) / 0.6)
        rect(d, x, y + h * k / n, x + w, y + h * (k + 1) / n + 0.6, fill=rgba(col, a))
    rect(d, x, y, x + w, y + h, outline=rgba(WHITE, 0.35 * a), width=2)


# ---------- scenes ----------
RY = 1060


def scene_ring(img, d, T, texts):
    """0-5 (and again from 42.6, so the Short loops): a gold ring that briefly turns silver."""
    end = T > 20
    a = win(T, 42.6, DUR + 2, 1.0, 0.3) if end else win(T, -1.0, 5.0, 0.2, 0.35)
    if a <= 0:
        return
    tau = T - DUR if end else T
    m = 0.0 if end else ss((T - 1.6) / 0.7) * (1 - ss((T - 3.6) / 0.7))
    ring(d, CX, RY, 250, tau, a, m=m)
    texts.append((label_sprite("without relativity", POP, 40, SILV_M[2]), CX, RY + 230, a * ss((m - 0.5) / 0.3)))
    if end and CAPTIONS:
        qa = a * ss((T - (DUR - 2.4)) / 0.4)
        texts.append((label_sprite("What else would look different", POP, 44, GOLD), CX, 760, qa))
        texts.append((label_sprite("without relativity?", POP, 44, GOLD), CX, 820, qa))
        texts.append((label_sprite("tell us below", size=30, fill=GREY), CX, 1380, qa))


METALS = [("aluminium", 1.0), ("iron", 0.92), ("silver", 1.0), ("gold", 0.0), ("platinum", 0.95), ("tin", 1.0)]


def scene_metals(img, d, T, texts):
    a = win(T, 5.0, 10.0, 0.35, 0.3)
    if a <= 0:
        return
    for i, (name, m) in enumerate(METALS):
        col, row = i % 3, i // 3
        x, y = 105 + col * 275, 760 + row * 330
        g = ss((T - 5.2 - 0.18 * i) / 0.4)
        cols = metal(1.0) if m > 0.5 else metal(0.0)
        if name == "iron":
            cols = ((62, 64, 72), (122, 125, 134), (190, 193, 200))
        yy = y + 40 * (1 - g)
        bar(d, x, yy, 240, 170, cols, a * g)
        glint = (0.5 * T + 0.17 * i) % 1.0
        line(d, [(x + 240 * glint, yy + 8), (x + 240 * glint - 50, yy + 160)], rgba(WHITE, 0.25 * a * g), 6)
        texts.append((label_sprite(name, POP, 36, GOLD if name == "gold" else WHITE), x + 120, yy + 215, a * g))
    pul = 0.5 + 0.5 * math.sin(5 * T)
    ga = a * ss((T - 7.6) / 0.5)
    rect(d, 105 + 275 * 0 - 14, 760 + 330 - 14, 105 + 240 + 14, 760 + 330 + 170 + 14, outline=rgba(GOLD, (0.6 + 0.4 * pul) * ga), width=5)


def scene_atom(img, d, T, texts):
    a = win(T, 10.0, 23.0, 0.35, 0.35)
    if a <= 0:
        return
    ay = 1000
    pr = np.random.default_rng(4)                            # the nucleus: a cluster of protons and neutrons
    for k in range(46):
        rr = 34 * math.sqrt(pr.uniform(0, 1)); th = pr.uniform(0, 6.283)
        col = (255, 110, 95) if k % 2 else (170, 180, 210)
        circ(d, CX + rr * math.cos(th), ay + rr * math.sin(th), 10, fill=rgba(col, a))
    s = ss((T - 17.6) / 2.0)                                 # relativity on: the orbits shrink
    r1 = 165 * (1 - SHRINK_1S * s)
    r6 = 360 * (1 - 0.12 * s)                                # outer shell: drawn smaller too (schematic, not to scale)
    if s > 0:
        circ(d, CX, ay, 165, outline=rgba(GREY, 0.55 * a * s), width=2)
        circ(d, CX, ay, 360, outline=rgba(GREY, 0.45 * a * s), width=2)
    circ(d, CX, ay, r1, outline=rgba(CYAN, 0.8 * a), width=3)
    circ(d, CX, ay, r6, outline=rgba(GOLD, 0.7 * a), width=3)
    w1 = 7.5                                                 # angular speed of the inner electron (shown hugely slowed)
    for k in range(10):                                      # the fast inner electron and its trail
        th = w1 * T - 0.07 * k
        circ(d, CX + r1 * math.cos(th), ay + r1 * math.sin(th), 13 - k, fill=rgba(CYAN, a * (1 - k / 10)))
    th = -0.8 * T
    circ(d, CX + r6 * math.cos(th), ay + r6 * math.sin(th), 11, fill=rgba(GOLD, a))
    la = a * (1 - s)
    texts.append((label_sprite(f"{Z_GOLD} protons", POP, 36, WHITE), CX, ay - 64, a * ss((T - 10.3) / 0.4)))
    gy = 1420                                                # speed gauge
    ga = a * ss((T - 11.0) / 0.4) * (1 - s)
    if ga > 0:
        x0, x1 = 140, 860
        rect(d, x0, gy - 14, x1, gy + 14, outline=rgba(GREY, 0.8 * ga), width=2)
        f = V_1S * ss((T - 11.2) / 1.6)
        rect(d, x0 + 3, gy - 11, x0 + 3 + (x1 - x0 - 6) * f, gy + 11, fill=rgba(CYAN, ga))
        texts.append((label_sprite(f"{100 * f:.0f}% of light speed", POP, 40, CYAN), x0 + (x1 - x0) * V_1S, gy - 52, ga))
        texts.append((label_sprite("light", size=28, fill=GREY), x1, gy + 40, ga))
    ra = a * s
    texts.append((label_sprite("without relativity", size=30, fill=GREY), CX + 250, ay - 400, ra))
    texts.append((label_sprite(f"inner orbit about {100 * SHRINK_1S:.0f}% smaller", POP, 38, CYAN), CX, 1420, ra))
    texts.append((label_sprite("schematic · not to scale · speed hugely slowed", size=26, fill=GREY), CX, 1480, a))


SPEC = [(380, (120, 60, 200)), (440, (60, 80, 255)), (490, (40, 180, 255)), (530, (60, 220, 90)),
        (580, (250, 230, 60)), (620, (255, 140, 40)), (700, (230, 40, 40))]


def spec_col(nm):
    for (n0, c0), (n1, c1) in zip(SPEC, SPEC[1:]):
        if nm <= n1:
            return lerp3(c0, c1, (nm - n0) / (n1 - n0))
    return SPEC[-1][1]


def scene_light(img, d, T, texts):
    """23-36: white light hits gold; the blue part is absorbed, the rest is reflected and looks yellow."""
    a = win(T, 23.0, 36.0, 0.35, 0.35)
    if a <= 0:
        return
    bar(d, 160, 1180, 680, 70, metal(0.0), a)               # a gold surface
    texts.append((label_sprite("gold", POP, 36, (60, 34, 4), stroke=0), CX, 1215, a))
    ab = ss((T - 25.0) / 1.0)                                # blue gets absorbed
    for i in range(7):                                       # incoming rays (white light = all colours)
        nm = 400 + 50 * i
        col = spec_col(nm)
        blue = nm < 500
        x0, x1 = 160 + 40 * i, 420 + 25 * i
        y0, y1 = 700, 1176
        ph = ((0.8 * T + i * 0.13) % 1.0)
        line(d, [(x0, y0), (x1, y1)], rgba(col, 0.75 * a), 5)
        circ(d, lerp(x0, x1, ph), lerp(y0, y1, ph), 6, fill=rgba(WHITE, 0.8 * a))
        ra = a * (1 - 0.95 * ab) if blue else a              # reflected rays: blue missing
        xe = x1 + (x1 - x0) * 0.9
        line(d, [(x1 + 4, y1), (xe + 60, y0 + 60)], rgba(col, 0.85 * ra), 5)
        if blue and ab > 0:
            pul = (1.2 * T + 0.2 * i) % 1.0
            circ(d, x1, y1 + 10, 10 + 30 * pul, outline=rgba(BLUE, 0.8 * (1 - pul) * a * ab), width=3)
    texts.append((label_sprite("white light", POP, 36, WHITE), 260, 660, a))
    texts.append((label_sprite("reflected", POP, 36, WHITE), 760, 720, a))
    texts.append((label_sprite("blue absorbed", POP, 36, BLUE), 330, 1295, a * ab))
    ya = a * ss((T - 30.6) / 0.6)                            # what's left, mixed together
    sw = 1400
    rect(d, 560, sw - 40, 820, sw + 40, fill=rgba((200, 146, 40), ya), outline=rgba(WHITE, 0.6 * ya), width=2)
    texts.append((label_sprite("what's left:", POP, 36, WHITE), 380, sw, ya))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1480, a))


def scene_switch(img, d, T, texts):
    """36-43: relativity switched off -> the ring turns silver; back on -> gold."""
    a = win(T, 36.0, 43.0, 0.35, 0.35)
    if a <= 0:
        return
    m = ss((T - 37.4) / 0.8) * (1 - ss((T - 41.2) / 0.6))
    ring(d, CX, RY + 40, 230, T, a, m=m)
    sx, sy = CX, 760                                         # a switch
    on = 1 - m
    rect(d, sx - 90, sy - 34, sx + 90, sy + 34, fill=rgba(lerp3((70, 75, 90), (200, 150, 40), on), a), outline=rgba(WHITE, 0.8 * a), width=3)
    circ(d, sx + lerp(-56, 56, on), sy, 28, fill=rgba(WHITE, a))
    texts.append((label_sprite("relativity", POP, 38, WHITE), sx - 230, sy, a))
    texts.append((label_sprite("ON" if on > 0.5 else "OFF", POP, 40, GOLD if on > 0.5 else SILV_M[1]), sx + 160, sy, a))
    texts.append((label_sprite("reflects every colour, like silver", POP, 36, SILV_M[2]), CX, 1350, a * ss((m - 0.6) / 0.3)))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1480, a))


SCENES = (scene_ring, scene_metals, scene_atom, scene_light, scene_switch)


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
