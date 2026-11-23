#!/usr/bin/env python3
"""Can empty space make something from nothing? Hawking radiation: at a black hole's edge, a virtual pair can be
split, one partner falls in and the other escapes as real radiation (Hawking 1974). The energy comes from the
black hole's mass, so it slowly evaporates: a Sun-mass black hole needs about 10^67 years.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 hawking_radiation.py preview 0 6.4 12      -> frame_<t>.png files
  python3 hawking_radiation.py render 0 54 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 54.0            # layout units; output is W*S x H*S
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
    (0.0, 3.2, None, "Can *nothing* | *make something?*"),
    (3.2, 10.0, None, "Empty space | *never sits still.*"),
    (10.0, 19.2, None, "Pairs *borrow energy* | and pop into being, | *just for an instant.*"),
    (19.2, 24.2, None, "At a black hole's edge, | one falls in, | *one escapes.*"),
    (24.2, 33.3, "PREDICTED 1974", "That glow is real: | *Hawking radiation.*"),
    (33.3, 38.3, None, "Who repays the loan? | *The black hole,* | *with its mass.*"),
    (38.3, 47.8, None, "A Sun-mass black hole | takes *unimaginably long* | to evaporate."),
    (47.8, 54.0, None, "Even here, | *nothing is free.*"),
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

# ---------- facts used on screen (sources: S. W. Hawking, "Black hole explosions?", Nature 248, 30 (1974);
# T = hbar c^3 / (8 pi G M k_B) = 6.2e-8 K for one solar mass; evaporation time 5120 pi G^2 M^3 / (hbar c^4)
# = 2.1e67 years for one solar mass (photons only; D. N. Page, Phys. Rev. D 13, 198 (1976) gives the same order);
# age of the universe 13.8 billion years (Planck 2018)) ----------
YEAR = 1974
EVAP_EXP = 67                      # a Sun-mass black hole needs about 10^67 years to evaporate
AGE_UNIVERSE = "13.8 billion years"

CX, BY0 = 500, 1060                # picture centre (the right-hand edge stays clear for the Shorts buttons)
HOT = (255, 170, 80)


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))
T_LOAN, T_POP, T_MEET = 10.3, 15.2, 18.0        # scene 3: energy borrowed, pair pops out, pair meets again
T_BH, T_HERO, T_PAY, T_REV, T_END = 19.2, 20.4, 33.3, 38.3, 47.8


# ---------- the jittering energy of empty space: a fine grid of field lines that never settles ----------
_rng = np.random.default_rng(11)
GRID_Y = np.arange(690, 1461, 34)
GRID_X = np.linspace(50, 950, 61)
GRID_PH = _rng.uniform(0, 6.283, (len(GRID_Y), 4))
GRID_K = np.array([0.011, 0.023, 0.037, 0.061])
GRID_W = np.array([1.3, -2.1, 2.9, -4.3])


def jitter_grid(d, T, a, amp=4.0, bulge=0.0, cy=BY0, hole=None):
    if a <= 0.004:
        return
    for j, y0 in enumerate(GRID_Y):
        dy = np.zeros_like(GRID_X)
        for k in range(4):
            dy += np.sin(GRID_K[k] * GRID_X + GRID_W[k] * T + GRID_PH[j, k]) / (k + 1)
        dy *= amp
        if bulge:
            g = np.exp(-((GRID_X - CX) / 110.0) ** 2 - ((y0 - cy) / 120.0) ** 2)
            dy += bulge * g * np.sin(9 * T + GRID_X * 0.05)
        ry = 1 - ss((abs(y0 - 1070) - 300) / 90)            # soft top and bottom edges
        pts = list(zip(GRID_X, y0 + dy))
        for i0 in range(0, len(pts) - 1, 4):               # short pieces, fading towards the sides
            seg = pts[i0:i0 + 5]
            xm = seg[len(seg) // 2][0]
            fx = 1 - ss((abs(xm - 500) - 300) / 150)
            if hole is not None:
                hx, hy, hr = hole
                seg = [p for p in seg if math.hypot(p[0] - hx, p[1] - hy) >= hr]
            if len(seg) > 1 and fx * ry > 0.01:
                line(d, seg, rgba(CYAN, 0.30 * a * fx * ry), 2.0)


# ---------- virtual pairs: two particles pop out of nothing, drift apart a little and annihilate again ----------
FIELD = []
for _ in range(1300):
    FIELD.append((_rng.uniform(80, 920), _rng.uniform(690, 1450), _rng.uniform(-2.0, DUR + 2.0),
                  _rng.uniform(0.8, 1.3), _rng.uniform(0, math.pi)))


def particle(d, x, y, c, al, r=7.0):
    circ(d, x, y, 2.3 * r, fill=rgba(c, 0.16 * al))
    circ(d, x, y, r, fill=rgba(c, al))
    circ(d, x - 0.3 * r, y - 0.3 * r, 0.36 * r, fill=rgba(WHITE, 0.65 * al))


def flash(d, x, y, f, a, size=1.0):
    """annihilation: a ring and a brief four-pointed sparkle (f runs 0..1)"""
    circ(d, x, y, size * (6 + 30 * f), outline=rgba(WHITE, 0.8 * (1 - f) * a), width=2.5)
    ln = size * 26 * math.sin(math.pi * min(1, f * 1.4))
    for ang in (0, 90):
        dx, dy = ln * math.cos(math.radians(ang)), ln * math.sin(math.radians(ang))
        line(d, [(x - dx, y - dy), (x + dx, y + dy)], rgba(WHITE, 0.85 * (1 - f) * a), 2.5)


def pair(d, x, y, u, ang, a, sep=40):
    """One virtual pair at phase u (0..1): born, separates along a little arc, rejoins, vanishes in a flash."""
    if a <= 0.004 or not (0 < u < 1.12):
        return
    if u >= 1.0:
        flash(d, x, y, (u - 1.0) / 0.12, a, 0.7)
        return
    s = sep * math.sin(math.pi * u) ** 0.8
    al = a * ss(u / 0.15)
    bend = 0.35 * math.sin(math.pi * u)                   # they swing round each other a little
    for sgn, c in ((1, CYAN), (-1, GOLD)):
        aa = ang + sgn * bend
        particle(d, x + sgn * 0.5 * s * math.cos(aa), y + sgn * 0.5 * s * math.sin(aa), c, al)


def field(d, T, a, keep=None):
    if a <= 0.004:
        return
    for x, y, tb, L, ang in FIELD:
        u = (T - tb) / L
        if 0 < u < 1.12 and (keep is None or keep(x, y)):
            pair(d, x, y, u, ang, a)


# ---------- the black hole ----------
BGA = np.asarray(BG)


def bh_state(T):
    """radius and centre of the black hole over time (it shrinks while it pays, scene 6; moves up for scene 7)."""
    R = 150 - 75 * ss((T - (T_PAY + 0.6)) / 4.2)
    R = lerp(R, 55, ss((T - T_REV) / 1.2))
    y = lerp(BY0, 830, ss((T - T_REV) / 1.2))
    return R, y


def lens(img, d, cx, cy, R, a):
    """Gravitational lensing of the starfield around the black hole (point-mass deflection, tapered to zero
    at 4 R so there is no seam), and the black shadow inside. Works on the frame before anything else is drawn."""
    if a <= 0.004:
        return
    h = int(4.0 * R * S); px, py = int(cx * S), int(cy * S)
    x0, x1, y0, y1 = max(0, px - h), min(W * S, px + h), max(0, py - h), min(H * S, py + h)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = xx - px + 0.5, yy - py + 0.5
    r = np.sqrt(dx * dx + dy * dy) + 1e-6
    RS = R * S; TE = 1.55 * RS
    taper = 1 - np.clip((r - 2.4 * RS) / (1.6 * RS), 0, 1) ** 2
    beta = r - (TE * TE / r) * taper
    sx = np.clip(px + dx * beta / r, 0, W * S - 1).astype(np.int32)
    sy = np.clip(py + dy * beta / r, 0, H * S - 1).astype(np.int32)
    src = BGA[sy, sx].astype(np.float32)
    src[r < RS * 1.0] = 0
    cur = np.asarray(img)[y0:y1, x0:x1].astype(np.float32)
    out = cur + (src - cur) * clamp(a)
    d.flush(); img.paste(Image.fromarray(out.astype(np.uint8), "RGB"), (x0, y0)); d._open()


def black_hole(d, cx, cy, R, T, a, pulse=0.0):
    if a <= 0.004:
        return
    for k in range(18):                                   # warm glow hugging the edge
        circ(d, cx, cy, R * (1.0 + 0.05 * (18 - k)), fill=rgba(HOT, (0.035 + 0.03 * pulse) * a * (k + 1) / 18))
    circ(d, cx, cy, R * 1.04, outline=rgba(GOLD, (0.8 + 0.2 * pulse) * a), width=3 + 3 * pulse)
    for k in range(48):                                   # a thin bright ring that swirls slowly
        t0 = 6.283 * k / 48 + 0.4 * T
        w = 0.5 + 0.5 * math.sin(3 * t0 - 1.1 * T)
        line(d, [(cx + 1.10 * R * math.cos(t0), cy + 1.10 * R * math.sin(t0)),
                 (cx + 1.10 * R * math.cos(t0 + 0.09), cy + 1.10 * R * math.sin(t0 + 0.09))], rgba(HOT, 0.55 * w * a), 2)
    circ(d, cx, cy, R, fill=(0, 0, 0, int(255 * clamp(a))))


# Pairs born at the edge: the gold partner falls in, the cyan one escapes (simplified picture).
EDGE = []
_t = T_HERO + 1.0
while _t < T_END:
    rate = 1.2 if _t < 24.2 else 6.5 if _t < T_REV else 1.0
    EDGE.append((_t, _rng.uniform(0, 2 * math.pi)))
    _t += _rng.exponential(1.0 / rate)
HERO_TH = -2.25                                           # the pair we watch closely (upper left)


def edge_pair(d, T, tb, th, a, slow=1.0, minus=False):
    """returns (outgoing x, y, phase) and whether the infalling partner just crossed the edge"""
    R, cy = bh_state(T)
    q = (T - tb) / slow
    if q < 0 or q > 3.2 or a <= 0.004:
        return None, False
    ct, st = math.cos(th), math.sin(th)
    if q < 0.45:                                          # born at the edge and drifting apart
        s = ss(q / 0.45)
        r_out, r_in = R + 20 + 16 * s, R + 20 - 16 * s
        al = a * ss(q / 0.12)
        a_in = a_out = al
    else:
        e = q - 0.45
        r_in = R + 4 - 60 * e                             # falls in and is gone behind the edge
        a_in = a * (1 - ss(e / 0.35))
        r_out = R + 36 + 70 * e + 120 * e * e             # escapes, faster and faster
        a_out = a * (1 - ss((e - 1.9) / 0.8))
    crossed = 0.45 <= q < 0.45 + 0.3
    if a_in > 0.004 and r_in > R * 0.88:
        x, y = CX + r_in * ct, cy + r_in * st
        particle(d, x, y, GOLD, a_in)
        if minus:                                         # it carries negative energy into the black hole
            line(d, [(x - 4.5, y), (x + 4.5, y)], rgba((40, 20, 0), a_in), 2.4)
    if a_out > 0.004:
        for k in range(12):                               # trail
            rr = r_out - 5 * k * (1 + min(q, 2))
            if rr < R:
                break
            f = 1 - k / 12
            circ(d, CX + rr * ct, cy + rr * st, 3 + 5 * f, fill=rgba(CYAN, 0.5 * a_out * f * f))
        x, y = CX + r_out * ct, cy + r_out * st
        particle(d, x, y, CYAN, a_out, 7.5)
        return (x, y, q), crossed
    return None, crossed


# ---------- scenes ----------
def scene_field(img, d, T, texts):
    """0-10 and again at the end (so the Short loops): empty space, fizzing with virtual pairs."""
    a = win(T, -1.0, 10.6, 0.2, 0.6) + win(T, T_END - 0.4, DUR + 2, 0.9, 0.3)
    if a <= 0.004:
        return
    g = ss((T - 3.4) / 0.8) * (1 - ss((T - 9.6) / 0.6)) if T < 20 else 0.0   # scene 2: the jitter takes centre stage
    jitter_grid(d, T, a * (0.55 + 0.45 * g), amp=4.0 + 6.0 * g)
    field(d, T, a * (1 - 0.55 * g))
    if CAPTIONS:
        texts.append((label_sprite("the energy of empty space never settles", POP, 34, CYAN), CX, 655, a * g))
        texts.append((label_sprite("simplified picture", size=26, fill=GREY), CX, 1510, a * (T < 20)))
    if T > 20 and CAPTIONS:                               # closing question for viewers (last ~2.5 s)
        qa = a * ss((T - (DUR - 2.6)) / 0.4)
        texts.append((label_sprite("If black holes evaporate, where", POP, 42, GOLD), CX, 1440 - 28, qa))
        texts.append((label_sprite("does everything they swallowed go?", POP, 42, GOLD), CX, 1440 + 28, qa))


def scene_loan(img, d, T, texts):
    """10-19: one pair up close: energy is borrowed from the jitter, the pair pops out, the loan runs out, they meet."""
    a = win(T, T_LOAN - 0.4, T_BH + 0.2, 0.6, 0.6)
    if a <= 0.004:
        return
    cy = BY0 - 20
    borrow = ss((T - (T_LOAN + 0.6)) / (T_POP - T_LOAN - 1.0)) * (1 - ss((T - T_POP) / 0.3))
    jitter_grid(d, T, a * 0.6, amp=4.0, bulge=26 * borrow, cy=cy)
    field(d, T, 0.3 * a, keep=lambda x, y: math.hypot(x - CX, y - cy) > 260)
    if borrow > 0.01:                                     # energy gathering into a knot
        for k in range(8):
            circ(d, CX, cy, (8 + 13 * k) * (0.4 + 0.6 * borrow), fill=rgba(WHITE, 0.07 * borrow * a))
        circ(d, CX, cy, 10 + 8 * borrow + 3 * math.sin(14 * T), fill=rgba(WHITE, 0.9 * borrow * a))
    if T_LOAN + 0.3 < T < T_POP:                          # sparks of energy drawn in from the jittering field
        for k in range(28):
            ph = (0.55 * (T - T_LOAN) + k / 28.0 * 3.7) % 1.0
            th = 6.283 * ((k * 0.381966) % 1.0) + 0.3 * math.sin(T + k)
            rr = 330 * (1 - ph) ** 1.3 + 12
            sa = a * ss(ph / 0.2) * (1 - ss((ph - 0.85) / 0.15)) * ss((T - T_LOAN - 0.3) / 0.6) * (1 - ss((T - T_POP + 0.3) / 0.3))
            x, y = CX + rr * math.cos(th), cy + rr * math.sin(th)
            x2, y2 = CX + (rr + 26) * math.cos(th), cy + (rr + 26) * math.sin(th)
            line(d, [(x, y), (x2, y2)], rgba(CYAN, 0.8 * sa), 3)
            circ(d, x, y, 3.5, fill=rgba(WHITE, sa))
    u = (T - T_POP) / (T_MEET - T_POP)
    if 0 <= u < 1:                                        # the pair, big, swinging apart and back together
        s = 230 * math.sin(math.pi * u) ** 0.7
        bend = 0.5 * math.sin(math.pi * u)
        for sgn, c in ((1, CYAN), (-1, GOLD)):
            aa = 0.25 + sgn * bend
            particle(d, CX + sgn * 0.5 * s * math.cos(aa), cy + sgn * 0.5 * s * math.sin(aa) * 0.6, c, a * ss(u / 0.08), 20)
        if CAPTIONS:
            la = a * ss((u - 0.12) / 0.1) * (1 - ss((u - 0.8) / 0.1))
            texts.append((label_sprite("particle", POP, 36, CYAN), CX + 0.5 * s * math.cos(0.25 + bend) + 10,
                          cy + 0.3 * s * math.sin(0.25 + bend) + 58, la))
            texts.append((label_sprite("antiparticle", POP, 36, GOLD), CX - 0.5 * s * math.cos(0.25 - bend) - 10,
                          cy - 0.3 * s * math.sin(0.25 - bend) - 58, la))
        rr = 190                                          # the loan's clock: a ring that runs out
        n = max(2, int(80 * (1 - u)))
        pts = [(CX + rr * math.sin(6.283 * (1 - u) * k / (n - 1)), cy - rr * math.cos(6.283 * (1 - u) * k / (n - 1)))
               for k in range(n)]
        line(d, pts, rgba(lerp3(WHITE, (255, 90, 90), u), 0.55 * a * ss(u / 0.08)), 4)
    fu = (T - T_MEET) / 0.7
    if 0 <= fu < 1:
        flash(d, CX, cy, fu, a, 2.2)
    if CAPTIONS:                                          # the energy meter
        ma = a * ss((T - T_LOAN - 0.3) / 0.4)
        lvl = ss((T - (T_LOAN + 0.6)) / (T_POP - T_LOAN - 1.0)) * (1 - ss((T - T_MEET) / 0.35))
        gy, x0, x1 = 1420, 200, 800
        rect(d, x0, gy - 12, x1, gy + 12, fill=rgba((20, 26, 48), ma), outline=rgba(GREY, 0.8 * ma), width=2)
        if lvl > 0.005:
            rect(d, x0 + 3, gy - 9, x0 + 3 + (x1 - x0 - 6) * lvl, gy + 9, fill=rgba(WHITE, 0.9 * ma))
        lab = "energy borrowed from empty space" if T < T_POP + 0.2 else \
              "the loan must be paid back almost at once" if T < T_MEET else "paid back: nothing left"
        texts.append((label_sprite(lab, POP, 34, WHITE), CX, gy - 48, ma))
        texts.append((label_sprite("simplified picture", size=26, fill=GREY), CX, 1475, ma))


def scene_bh(img, d, T, texts):
    """19-48: the black hole; pairs at its edge; Hawking radiation; it pays with its mass; the huge time scale."""
    a = win(T, T_BH, T_END + 0.4, 0.9, 0.7)
    if a <= 0.004:
        return
    R, cy = bh_state(T)
    lens(img, d, CX, cy, R, a)
    jitter_grid(d, T, 0.5 * a * (1 - ss((T - T_REV) / 0.8)), amp=4.0, hole=(CX, cy, R * 2.2))
    field(d, T, 0.35 * a, keep=lambda x, y: math.hypot(x - CX, y - cy) > R * 2.0)
    paying = T_PAY - 0.2 < T < T_REV + 0.4
    pulse = 0.0
    for tb, th in EDGE:
        _, crossed = edge_pair(d, T, tb, th, a * (0.85 if T > 23 else 0.6), minus=paying)
        if crossed and paying:
            pulse = max(pulse, 1 - ((T - tb) - 0.45) / 0.3)
    black_hole(d, CX, cy, R, T, a, pulse)
    h, _ = edge_pair(d, T, T_HERO, HERO_TH, a, slow=1.6)
    if h and T < 24.2 and CAPTIONS:
        x, y, q = h
        la = a * ss((q - 0.6) / 0.3) * (1 - ss((T - 23.6) / 0.5))
        texts.append((label_sprite("escapes", POP, 38, CYAN), x - 10, y - 50, la))
    if T < 24.4 and CAPTIONS:
        fa = a * ss((T - (T_HERO + 1.0)) / 0.3) * (1 - ss((T - 23.6) / 0.5))
        texts.append((label_sprite("falls in", POP, 38, GOLD), CX + R * 0.55, cy + R + 60, fa))
        texts.append((label_sprite("event horizon", size=28, fill=GREY), CX + 40, cy + R + 115, a * (1 - ss((T - 23.6) / 0.5))))
    if CAPTIONS:
        ha = a * ss((T - 24.6) / 0.5) * (1 - ss((T - (T_PAY - 0.3)) / 0.4))
        texts.append((label_sprite(f"Hawking radiation · predicted {YEAR}", POP, 38, CYAN), CX, 1420, ha))
        texts.append((label_sprite("not yet detected: far too faint", size=30, fill=GREY), CX, 1466, ha))
        texts.append((label_sprite("simplified picture", size=26, fill=GREY), CX, 1510, a * (1 - ss((T - (T_PAY - 0.3)) / 0.4))))
    ga = a * ss((T - T_PAY) / 0.4) * (1 - ss((T - T_REV) / 0.4))   # scene 6: the mass gauge drains
    if ga > 0.004:
        gy, x0, x1 = 1440, 140, 860
        rect(d, x0, gy - 13, x1, gy + 13, fill=rgba((20, 26, 48), ga), outline=rgba(GREY, 0.8 * ga), width=2)
        f = R / 150.0                                     # a black hole's radius is proportional to its mass
        rect(d, x0 + 3, gy - 10, x0 + 3 + (x1 - x0 - 6) * f, gy + 10, fill=rgba(HOT, ga))
        if CAPTIONS:
            texts.append((label_sprite("black hole's mass", POP, 36, WHITE), CX, gy - 50, ga))
            texts.append((label_sprite("infalling partner: negative energy", POP, 32, GOLD), CX, 655, ga))
            texts.append((label_sprite("illustration · hugely sped up", size=26, fill=GREY), CX, 1500, ga))
    ta = a * ss((T - (T_REV + 0.5)) / 0.5)                  # scene 7: the time it takes, counted in powers of ten
    if ta > 0.004 and CAPTIONS:
        e = int(round(lerp(10, EVAP_EXP, ss((T - T_CNT0) / (T_CNT1 - T_CNT0)))))
        fin = e == EVAP_EXP
        texts.append((label_sprite("a black hole as heavy as the Sun", POP, 36, WHITE), CX, 950, ta))
        texts.append((label_sprite("needs about", POP, 40, WHITE), CX, 1050, ta))
        big = label_sprite("10", POP, 170, GOLD if fin else WHITE)
        sup = label_sprite(str(e), POP, 92, GOLD if fin else WHITE)
        yrs = label_sprite("years", POP, 64, WHITE)
        wtot = (big.width + sup.width + yrs.width) / S - 30
        x0 = CX - wtot / 2
        texts.append((big, x0 + big.width / S / 2, 1185, ta))
        texts.append((sup, x0 + big.width / S - 8 + sup.width / S / 2, 1130, ta))
        texts.append((yrs, x0 + big.width / S + sup.width / S - 14 + yrs.width / S / 2, 1205, ta))
        texts.append((label_sprite("to evaporate", POP, 40, WHITE), CX, 1300, ta))
        ua = ta * ss((T - T_UNI) / 0.5)
        texts.append((label_sprite(f"the universe so far: {AGE_UNIVERSE}", POP, 36, CYAN), CX, 1395, ua))
        texts.append((label_sprite("theory: not yet measured", size=26, fill=GREY), CX, 1460, ta))


T_CNT0, T_CNT1, T_UNI = 40.4, 42.3, 44.0                 # tuned to the narration after the draft build
SCENES = (scene_bh, scene_field, scene_loan)


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
