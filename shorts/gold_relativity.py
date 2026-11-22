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
T_GOLD, T_SILV = np.array([1.00, 0.74, 0.30]), np.array([0.93, 0.94, 0.97])    # how each metal tints what it reflects
GOLD_M = ((120, 80, 14), (212, 160, 46), (250, 222, 130))       # dark, mid, highlight (flat drawings)
SILV_C = (225, 229, 238)
BLUE = (80, 130, 255)


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


# ---------- polished metal: what a mirror-like surface with normal n shows of a simple "studio" of soft lights ----------
def studio(nx, ny, nz, rot=0.0, strip=1.0):
    """Brightness reflected towards the viewer (who looks along -z) by a mirror surface with unit normal (nx, ny, nz).
    y points up here. The studio: a dim room, a big soft light above, a narrow strip light at the side, a dark floor."""
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1          # reflection of the view direction
    az = np.arctan2(rx, rz) + rot
    b = 0.10 + 0.16 * (ry * 0.5 + 0.5)
    b = b + 1.25 * np.exp(-((ry - 0.52) / 0.20) ** 2) * (0.55 + 0.45 * np.cos(1.3 * az))        # soft box above
    b = b + 0.95 * strip * np.exp(-((np.sin(az + 1.1)) / 0.13) ** 2) * (np.cos(az + 1.1) > 0) * np.exp(-(ry / 0.75) ** 2)   # strip
    b = b + 0.30 * np.exp(-((ry + 0.45) / 0.22) ** 2)                                           # warm bounce from the floor
    b = b + 0.35 * (1 - np.abs(nz)) ** 3                                                        # brighter at grazing angles
    return b


def metal_rgb(b, tint):
    """Brightness -> colour: tinted by the metal, with the brightest highlights going to white."""
    base = np.clip(b, 0, 1)[..., None] * tint
    hot = np.clip(b - 1.0, 0, 1)[..., None]
    return np.clip(255 * (base + hot * (1 - base)), 0, 255)


NU, NV = 720, 64
_u = np.linspace(0, 2 * np.pi, NU + 1)[:, None]
_v = np.linspace(0, 2 * np.pi, NV + 1)[None, :]


def ring(d, cx, cy, R, T, a, m=0.0, spin=0.75, phase=0.4, texts=None):
    """A polished wedding band, turning. Real 3D: a ring with an oval cross-section, drawn as a fine mesh, each facet
    coloured by what it reflects. m = 0 gold, 1 silver."""
    if a <= 0:
        return
    ra, rb = 0.085 * R, 0.21 * R                              # radial thickness and half-width of the band
    cu, su, cv, sv = np.cos(_u), np.sin(_u), np.cos(_v), np.sin(_v)
    rr = R + ra * cv
    P = np.stack([rr * cu, rb * sv + 0 * cu, rr * su], -1)   # the ring lies flat: its axis is y
    N = np.stack([cv / ra * cu, sv / rb + 0 * cu, cv / ra * su], -1)
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    tx = math.radians(68 + 6 * math.sin(0.5 * T))            # stand it up, facing us, with a slow nod...
    ty = phase + 0.55 * math.sin(spin * T) + 0.12 * T        # ...and swing it from side to side
    cx_, sx_, cy_, sy_ = math.cos(tx), math.sin(tx), math.cos(ty), math.sin(ty)
    Rx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
    Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    M = Ry @ Rx
    P = P @ M.T; N = N @ M.T
    Pc = (P[:-1, :-1] + P[1:, :-1] + P[1:, 1:] + P[:-1, 1:]) / 4
    Nc = N[:-1, :-1] + N[1:, :-1] + N[1:, 1:] + N[:-1, 1:]
    Nc /= np.linalg.norm(Nc, axis=-1, keepdims=True)
    b = studio(Nc[..., 0], Nc[..., 1], Nc[..., 2], rot=0.25 * T)
    tint = T_GOLD * (1 - m) + T_SILV * m
    inner = np.clip(-(cv[:, :-1] + cv[:, 1:]) / 2, 0, 1) * np.ones((NU, 1))   # 1 on the inside of the band
    b = (0.06 + 1.18 * b) * (1 - 0.34 * inner)                               # the inside sees less of the lights...
    col = metal_rgb(b, tint)
    col = (col * (1 - inner[..., None]) + col * tint * inner[..., None]).astype(int)   # ...and mostly reflects the metal itself
    vis = Nc[..., 2] > 0.0
    order = np.argsort(Pc[..., 2][vis])                       # far facets first
    idx = np.argwhere(vis)[order]
    X = (cx + P[..., 0]) * S; Y = (cy - P[..., 1]) * S
    al = int(255 * clamp(a))
    dd = d.d
    for i, j in idx:
        c = (int(col[i, j, 0]), int(col[i, j, 1]), int(col[i, j, 2]))
        dd.polygon([X[i, j], Y[i, j], X[i + 1, j], Y[i + 1, j], X[i + 1, j + 1], Y[i + 1, j + 1], X[i, j + 1], Y[i, j + 1]],
                   aggdraw.Pen(c, 0.8 * S, al), aggdraw.Brush(c, al))
    # sparkles on the brightest highlights
    bb = np.where(vis, b, 0)
    for k, off in enumerate((0, NU // 3, 2 * NU // 3)):
        seg = bb[off:off + NU // 3]
        i, j = np.unravel_index(np.argmax(seg), seg.shape); i += off
        tw = max(0.0, math.sin(2.1 * T + 2.1 * k)) ** 3 * clamp(bb[i, j] - 0.9, 0, 1)
        if tw > 0.02:
            x, y = cx + Pc[i, j, 0], cy - Pc[i, j, 1]
            for ang, ln in ((0, 60), (90, 60), (45, 22), (135, 22)):
                dx, dy = ln * tw * math.cos(math.radians(ang)), ln * tw * math.sin(math.radians(ang))
                line(d, [(x - dx, y - dy), (x + dx, y + dy)], rgba(WHITE, 0.95 * tw * a), 3)
            circ(d, x, y, 5 * tw, fill=rgba(WHITE, a * tw))


_bn = {}


def ball(d, cx, cy, r, T, a, tint, rot=0.0):
    """A polished metal ball (same studio lighting as the ring)."""
    if a <= 0.004:
        return
    n = int(2 * r * S)
    if n not in _bn:
        g = (np.arange(n) + 0.5) / n * 2 - 1
        x, y = np.meshgrid(g, -g)
        r2 = x * x + y * y
        z = np.sqrt(np.clip(1 - r2, 0, 1))
        edge = np.clip((1 - np.sqrt(r2)) * n / 2, 0, 1)      # antialiased rim
        _bn[n] = (x, y, z, edge)
    x, y, z, edge = _bn[n]
    rgb = metal_rgb(studio(x, y, z, rot=rot + 0.5 * T, strip=0.25), np.asarray(tint, float))
    im = Image.fromarray(np.dstack([rgb, 255 * edge * a]).astype(np.uint8), "RGBA")
    d.paste(im, (int(round(cx * S - n / 2)), int(round(cy * S - n / 2))), im.getchannel("A"))


# ---------- scenes ----------
RY = 1070


def scene_ring(img, d, T, texts):
    """0-5 (and again from 42.6, so the Short loops): a gold ring that briefly turns silver."""
    end = T > 20
    a = win(T, 42.6, DUR + 2, 1.0, 0.3) if end else win(T, -1.0, 5.0, 0.2, 0.35)
    if a <= 0:
        return
    tau = T - DUR if end else T
    m = 0.0 if end else ss((T - 1.5) / 0.8) * (1 - ss((T - 3.5) / 0.8))
    ring(d, CX, RY, 285, tau, a, m=m)
    if CAPTIONS:
        texts.append((label_sprite("without relativity", POP, 42, SILV_C), CX, RY + 400, a * ss((m - 0.5) / 0.3)))
    if end and CAPTIONS:
        qa = a * ss((T - (DUR - 2.4)) / 0.4)
        texts.append((label_sprite("What else would look different", POP, 44, GOLD), CX, 1440 - 30, qa))
        texts.append((label_sprite("without relativity?", POP, 44, GOLD), CX, 1440 + 30, qa))


METALS = [("aluminium", (0.90, 0.91, 0.92)), ("iron", (0.60, 0.61, 0.63)), ("silver", (0.96, 0.96, 0.95)),
          ("gold", tuple(T_GOLD)), ("platinum", (0.84, 0.83, 0.80)), ("tin", (0.83, 0.85, 0.87))]


def scene_metals(img, d, T, texts):
    a = win(T, 5.0, 10.0, 0.35, 0.3)
    if a <= 0:
        return
    for i, (name, tint) in enumerate(METALS):
        col, row = i % 3, i // 3
        x, y = 200 + col * 300, 850 + row * 360
        g = ss((T - 5.15 - 0.16 * i) / 0.45)
        isg = name == "gold"
        pop = 1 + (0.16 * ss((T - 7.6) / 0.5) if isg else -0.06 * ss((T - 7.6) / 0.5))
        r = 108 * pop * (0.6 + 0.4 * g)
        ball(d, x, y, r, T, a * g, tint, rot=0.7 * i)
        if isg:
            pul = (0.9 * T) % 1.0
            circ(d, x, y, r + 14 + 46 * pul, outline=rgba(GOLD, 0.8 * (1 - pul) * a * ss((T - 7.6) / 0.5)), width=3)
        texts.append((label_sprite(name, POP, 38, GOLD if isg else WHITE), x, y + 160, a * g))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1480, a))


_ar = np.random.default_rng(4)
NUC = [(34 * math.sqrt(_ar.uniform(0, 1)), _ar.uniform(0, 6.283), k % 2, _ar.uniform(0, 6.283)) for k in range(52)]
SHELLS = [(235, 5, 1.9, 0.0), (300, 7, -1.3, 1.0)]           # faint middle shells: radius, electrons, speed, phase


def scene_atom(img, d, T, texts):
    a = win(T, 10.0, 23.0, 0.35, 0.35)
    if a <= 0:
        return
    ay = 1010
    zoom = 0.9 + 0.1 * ss((T - 10.0) / 1.5)
    s = ss((T - 17.6) / 2.0)                                 # relativity on: the orbits shrink
    for k in range(5):
        circ(d, CX, ay, 70 - 8 * k, fill=rgba((255, 150, 110), 0.05 * a))
    for rr, th, kind, ph in NUC:                             # the nucleus: a jostling cluster of protons and neutrons
        jx, jy = 2.2 * math.sin(9 * T + ph), 2.2 * math.cos(8 * T + 1.7 * ph)
        col = (255, 110, 95) if kind else (170, 180, 210)
        circ(d, CX + rr * math.cos(th) + jx, ay + rr * math.sin(th) + jy, 10, fill=rgba(col, a))
        circ(d, CX + rr * math.cos(th) + jx - 3, ay + rr * math.sin(th) + jy - 3, 3.5, fill=rgba(WHITE, 0.35 * a))
    r1 = 150 * zoom * (1 - SHRINK_1S * s)
    r6 = 385 * zoom * (1 - 0.12 * s)                         # outer shell: drawn smaller too (schematic, not to scale)
    if s > 0:
        for r0 in (150 * zoom, 385 * zoom):                  # ghosts of the orbits without relativity (dashed)
            for k in range(48):
                t0 = 6.283 * k / 48
                line(d, [(CX + r0 * math.cos(t0), ay + r0 * math.sin(t0)), (CX + r0 * math.cos(t0 + 0.07), ay + r0 * math.sin(t0 + 0.07))],
                     rgba(GREY, 0.6 * a * s), 2.5)
    for r0, ne, sp, ph in SHELLS:
        rs = r0 * zoom * (1 - 0.15 * s)
        circ(d, CX, ay, rs, outline=rgba(GREY, 0.22 * a), width=1.5)
        for k in range(ne):
            th = sp * T + ph + 6.283 * k / ne
            circ(d, CX + rs * math.cos(th), ay + rs * math.sin(th), 5, fill=rgba(GREY, 0.6 * a))
    circ(d, CX, ay, r1, outline=rgba(CYAN, 0.55 * a), width=2.5)
    circ(d, CX, ay, r6, outline=rgba(GOLD, 0.55 * a), width=2.5)
    w1 = 9.0 * (0.25 + 0.75 * ss((T - 11.0) / 1.8))          # the inner electron speeds up as the gauge fills
    th0 = 9.0 * (T - 10) if T < 11 else 9.0 + 9.0 * (0.25 * (T - 11) + 0.75 * ((T - 11) ** 2 / 3.6 if T < 12.8 else (T - 11) - 0.9))
    th0 = th0 * 0.9
    for k in range(26):                                      # ...leaving a comet trail
        th = th0 - 0.035 * k * (w1 / 9.0 * 2.2)
        f = 1 - k / 26
        circ(d, CX + r1 * math.cos(th), ay + r1 * math.sin(th), 3 + 11 * f, fill=rgba(lerp3(BLUE, CYAN, f), a * f ** 1.5))
    circ(d, CX + r1 * math.cos(th0), ay + r1 * math.sin(th0), 9, fill=rgba(WHITE, a))
    th = -0.8 * T
    for k in range(8):
        f = 1 - k / 8
        circ(d, CX + r6 * math.cos(th + 0.02 * k), ay + r6 * math.sin(th + 0.02 * k), 4 + 8 * f, fill=rgba(GOLD, a * f))
    texts.append((label_sprite(f"{Z_GOLD} protons", POP, 34, WHITE), CX, ay - 78, a * ss((T - 10.3) / 0.4)))
    gy = 1445                                                # speed gauge
    ga = a * ss((T - 11.0) / 0.4) * (1 - s)
    if ga > 0:
        x0, x1 = 140, 860
        rect(d, x0, gy - 13, x1, gy + 13, fill=rgba((20, 26, 48), ga), outline=rgba(GREY, 0.8 * ga), width=2)
        f = V_1S * ss((T - 11.2) / 1.8)
        for k in range(24):
            xa, xb = x0 + 3 + (x1 - x0 - 6) * f * k / 24, x0 + 3 + (x1 - x0 - 6) * f * (k + 1) / 24
            rect(d, xa, gy - 10, xb + 0.5, gy + 10, fill=rgba(lerp3(BLUE, CYAN, k / 23), ga))
        texts.append((label_sprite(f"{100 * f:.0f}% of light speed", POP, 42, CYAN), min(x0 + (x1 - x0) * V_1S, 700), gy - 54, ga))
    ra = a * s
    texts.append((label_sprite("without relativity", size=28, fill=GREY), CX + 255, ay - 385 * zoom - 22, ra))
    texts.append((label_sprite(f"inner orbit about {100 * SHRINK_1S:.0f}% smaller", POP, 40, CYAN), CX, 1432, ra))
    texts.append((label_sprite("schematic · not to scale · speeds hugely slowed", size=26, fill=GREY), CX, 1492, a))


RAYCOL = [(140, 70, 230), (70, 90, 255), (40, 170, 255), (60, 220, 90), (250, 230, 60), (255, 150, 40), (240, 50, 50)]


def scene_light(img, d, T, texts):
    """23-36: white light hits gold; the blue part is absorbed, the rest bounces off and looks yellow."""
    a = win(T, 23.0, 36.0, 0.35, 0.35)
    if a <= 0:
        return
    sy = 1210                                                # the gold surface: a polished bar with a moving sheen
    n = 30
    for k in range(n):
        f = k / (n - 1)
        col = lerp3(GOLD_M[2], GOLD_M[1], f / 0.25) if f < 0.25 else lerp3(GOLD_M[1], GOLD_M[0], (f - 0.25) / 0.75)
        rect(d, 110, sy + 120 * k / n, 890, sy + 120 * (k + 1) / n + 0.6, fill=rgba(col, a))
    sh = ((0.22 * T) % 1.4) - 0.2
    for k in range(12):
        xs = 110 + 780 * sh + 9 * k
        if 110 < xs < 880:
            line(d, [(xs, sy + 2), (xs - 40, sy + 118)], rgba(WHITE, 0.10 * a * (1 - abs(k - 6) / 6)), 9)
    rect(d, 110, sy, 890, sy + 120, outline=rgba(WHITE, 0.4 * a), width=2)
    texts.append((label_sprite("gold", POP, 44, (70, 40, 6), stroke=0), CX, sy + 62, a))
    ab = ss((T - 24.6) / 1.0)                                # from here on the blue photons do not come back
    hx, hy = CX, sy
    for i, col in enumerate(RAYCOL):                         # one stream of photons per colour
        blue = i < 3
        x_in, y_in = 110 + 62 * i, 690
        hit = (hx - 135 + 45 * i, hy)
        x_out, y_out = hit[0] + (hit[0] - x_in), y_in
        line(d, [(x_in, y_in), hit], rgba(col, 0.22 * a), 3)
        oa = a * (1 - ab) if blue else a
        line(d, [hit, (x_out, y_out)], rgba(col, 0.22 * oa), 3)
        for k in range(5):                                   # photons: short bright dashes running down, then back up
            q = (0.55 * T + k / 5 + 0.07 * i) % 1.0
            for leg, alpha in ((0, a), (1, oa)):
                p0, p1 = ((x_in, y_in), hit) if leg == 0 else (hit, (x_out, y_out))
                qa, qb = q, min(1.0, q + 0.07)
                xa, ya = lerp(p0[0], p1[0], qa), lerp(p0[1], p1[1], qa)
                xb, yb = lerp(p0[0], p1[0], qb), lerp(p0[1], p1[1], qb)
                line(d, [(xa, ya), (xb, yb)], rgba(col, 0.95 * alpha), 7)
                circ(d, xb, yb, 5, fill=rgba(WHITE, 0.85 * alpha))
        if blue and ab > 0:                                  # absorbed: a ripple where each blue photon lands
            pul = (0.55 * 5 * T + 0.35 * i) % 1.0
            circ(d, hit[0], hit[1] + 4, 8 + 34 * pul, outline=rgba(col, 0.9 * (1 - pul) * a * ab), width=3)
            circ(d, hit[0], hit[1] + 4, 9 * (1 - pul), fill=rgba(col, 0.8 * a * ab))
    texts.append((label_sprite("white light: every colour", POP, 34, WHITE), 300, 648, a))
    texts.append((label_sprite("reflected", POP, 34, WHITE), 800, 648, a))
    texts.append((label_sprite("blue: absorbed", POP, 38, BLUE), 250, sy + 160, a * ab))
    ya = a * ss((T - 30.5) / 0.6)                            # what the reflected colours add up to
    ball(d, 770, sy + 205, 52, T, ya, tuple(T_GOLD))
    texts.append((label_sprite("the rest looks:", POP, 36, WHITE), 560, sy + 208, ya))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1492, a))


def scene_switch(img, d, T, texts):
    """36-43: relativity switched off -> the ring turns silver; back on -> gold."""
    a = win(T, 36.0, 43.0, 0.35, 0.35)
    if a <= 0:
        return
    m = ss((T - 37.4) / 0.8) * (1 - ss((T - 41.2) / 0.6))
    ring(d, CX, RY + 30, 240, T, a, m=m, phase=1.2)
    for t0 in (37.4, 41.2):                                  # a flash sweeps out when the switch flips
        dt = T - t0
        if 0 < dt < 1.2:
            circ(d, CX, RY + 30, 120 + 520 * dt, outline=rgba(WHITE, 0.55 * math.exp(-dt / 0.35) * a), width=5)
    sx, sy = CX + 20, 740                                    # the switch
    on = 1 - m
    body = lerp3((60, 66, 84), (214, 160, 44), on)
    for k in range(-52, 53, 4):
        circ(d, sx + k, sy, 36, fill=rgba(body, a))
    circ(d, sx + lerp(-52, 52, on), sy, 29, fill=rgba(WHITE, a))
    texts.append((label_sprite("relativity", POP, 42, WHITE), sx - 250, sy, a))
    texts.append((label_sprite("ON" if on > 0.5 else "OFF", POP, 44, GOLD if on > 0.5 else SILV_C), sx + 160, sy, a))
    texts.append((label_sprite("reflects every colour, like silver", POP, 36, SILV_C), CX, 1440, a * ss((m - 0.6) / 0.3)))
    texts.append((label_sprite("illustration", size=26, fill=GREY), CX, 1492, a))


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
