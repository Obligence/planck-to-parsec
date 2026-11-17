#!/usr/bin/env python3
"""LIGO short. Standard output: 2160x3840 (4K vertical), 60 fps.
Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 ligo_short.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 ligo_short.py render 0 43.5 out.mp4   -> renders that time range
All text and timings live in CAPTIONS and the scene functions below.
"""
import sys, math, subprocess, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import aggdraw

W, H, DUR = 1080, 1920, 43.5            # layout units; output is W*S x H*S
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
    (0.3, 3.4, "1.3 BILLION YEARS AGO", "Two black holes were circling each other. *Faster and faster.*"),
    (3.4, 6.3, None, "Each one about *30 times heavier* than our Sun."),
    (6.7, 10.2, None, "Then they collided. | *3 Suns' worth of mass* became ripples in spacetime."),
    (10.3, 14.0, None, "For one moment, it *out-powered every star* in the observable universe. Combined."),
    (14.2, 17.6, "@countdown", "The ripples crossed the dark at the *speed of light...*"),
    (17.6, 20.4, "SEPTEMBER 14, 2015", "...and finally reached *a small blue world.*"),
    (20.7, 24.0, "LIGO", "This time, *someone was listening.* Two laser beams in tunnels 4 km long."),
    (24.0, 28.0, None, "The wave *stretched* one arm and *squeezed* the other..."),
    (28.2, 31.7, None, "...by *1/1000* the width of a proton."),
    (31.7, 35.5, None, "Like measuring the distance to the nearest star to within a *human hair.*"),
    (35.6, 39.2, None, "The whole signal lasted *0.2 seconds.*"),
    (39.2, 43.2, "EINSTEIN PREDICTED IT IN 1916", "A century later, *we felt the universe tremble.*"),
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


def make_earth(R):
    n = 2 * R * S
    yy, xx = np.mgrid[0:n, 0:n]
    x = (xx - n / 2 + .5) / (n / 2); y = (yy - n / 2 + .5) / (n / 2)
    r = np.sqrt(x * x + y * y); z = np.sqrt(np.clip(1 - r * r, 0, 1))
    L = np.array([-0.55, -0.5, 0.67]); L = L / np.linalg.norm(L)
    lam = np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1)
    land = (np.sin(5 * x + 1) + np.sin(7 * y + 2) + np.sin(4 * x - 6 * y)) > 1.15
    base = np.where(land[..., None], np.array([70, 160, 95]), np.array([35, 105, 225]))
    rgb = base * (0.12 + 0.98 * lam)[..., None]
    a = np.clip((1 - r) * n / 4, 0, 1) * 255
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA")


def make_proton(R):
    n = 2 * R * S
    yy, xx = np.mgrid[0:n, 0:n]
    x = (xx - n / 2 + .5) / (n / 2); y = (yy - n / 2 + .5) / (n / 2)
    r = np.sqrt(x * x + y * y)
    c0, c1, c2 = np.array([255, 225, 160]), np.array([255, 120, 55]), np.array([150, 35, 30])
    t = np.clip(r, 0, 1)[..., None]
    rgb = np.where(t < .55, c0 + (c1 - c0) * (t / .55), c1 + (c2 - c1) * ((t - .55) / .45))
    a = np.clip((1 - r) / 0.10, 0, 1) * 255
    return Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")


BG = make_bg()
EARTH_R, PROTON_R = 80, 280
EARTH, PROTON = make_earth(EARTH_R), make_proton(PROTON_R)


def paste2x(img, sp, cx, cy, alpha):
    if alpha <= 0.004:
        return
    m = sp.getchannel("A")
    if alpha < 0.996:
        m = m.point(lambda v: int(v * alpha))
    CUR.paste(sp, (int(cx * S - sp.width / 2), int(cy * S - sp.height / 2)), m)


# ---------- physics-flavoured curves ----------
TM = 6.2          # merger time
VW = 380.0        # on-screen wave speed, px/s
C0 = (540, 1050)  # centre of the inspiral


def orbit_r(t):
    tau = max((TM - t) / TM, 0.0)
    return 34 + 190 * tau ** 0.4


def orbit_w(t):
    return min(3.0 * (224 / orbit_r(t)) ** 1.5, 22.0)


_tg = np.arange(-4.0, TM + 1e-9, 1 / 600)
_wg = np.array([orbit_w(t) for t in _tg])
_pg = np.cumsum(_wg) / 600


def phase(t):
    if t < -4.0:
        return _pg[0] + (t + 4.0) * _wg[0]
    return float(np.interp(t, _tg, _pg))


def chirp_curve(n=1600):
    u = np.linspace(0, 1, n); um = 0.76
    y = np.zeros(n)
    pre = u < um
    tau = (um - u[pre]) / um
    y[pre] = np.sin(-2 * np.pi * 11 * tau ** 0.625) * ((tau + 0.03) ** -0.25) / (0.03 ** -0.25)
    y[pre] *= np.clip(u[pre] / 0.08, 0, 1) ** 2 * (3 - 2 * np.clip(u[pre] / 0.08, 0, 1))
    post = ~pre
    y[post] = np.sin(2 * np.pi * 38 * (u[post] - um)) * np.exp(-(u[post] - um) / 0.03)
    return u, y


CH_U, CH_Y = chirp_curve()


# ---------- scenes ----------
def black_hole(d, x, y, r, a=1.0, ring=5.0):
    for k, al in ((3.2, .10), (2.2, .18), (1.5, .30)):
        circ(d, x, y, r + ring * k * 1.6, outline=rgba((255, 150, 70), al * a), width=ring * 1.4)
    circ(d, x, y, r + ring * .8, fill=rgba((0, 0, 0), a), outline=rgba((255, 190, 110), a), width=ring)
    circ(d, x, y, r, fill=rgba((0, 0, 0), a))


def scene_holes(img, d, T, texts):
    if T > 20.7:
        return
    cx, cy = C0
    # spiral gravitational waves emitted before the merger
    if T < TM + 3.6:
        for arm in (0, 1):
            rho = 70.0; pts = []; meta = []
            while rho < 1320:
                tr = T - rho / VW
                if tr <= TM:
                    ang = phase(tr) + arm * math.pi
                    pts.append((cx + rho * math.cos(ang), cy + rho * math.sin(ang)))
                    meta.append((rho, clamp(orbit_w(tr) / 22.0)))
                else:
                    pts.append(None); meta.append(None)
                rho += 3
            for i in range(0, len(pts) - 12, 10):
                seg = pts[i:i + 12]
                if any(p is None for p in seg):
                    continue
                rho_, amp = meta[i]
                al = (0.22 + 0.6 * amp) * (1 - rho_ / 1320) * ss((rho_ - 70) / 60)
                line(d, seg, rgba(CYAN, al), 3 + 6 * amp)
    if T < TM:
        r = orbit_r(T); ph = phase(T)
        ux, uy = math.cos(ph), math.sin(ph)
        black_hole(d, cx + r * 0.89 * ux, cy + r * 0.89 * uy, 44)
        black_hole(d, cx - r * 1.11 * ux, cy - r * 1.11 * uy, 38)
    else:
        dt = T - TM
        for k in range(5):  # burst + ringdown rings
            R = VW * (dt - 0.22 * k)
            if 0 < R < 1300:
                circ(d, cx, cy, R, outline=rgba((200, 245, 255), 0.95 * 0.62 ** k * (1 - R / 1300)), width=11 - 1.8 * k)
        z = ss((T - 10.2) / 1.8)   # camera pulls back: hole shrinks into a distant dot
        hx, hy, hr = cx, lerp(cy, 760, z), lerp(60, 9, z)
        aS = ss((20.6 - T) / 0.4)
        # wave packet travelling to Earth (zoomed-out view)
        if T > 11.2:
            lead = 60 + 100 * (T - 12.0) if T > 12 else 60 + 20 * (T - 12.0)
            ain = ss((T - 11.2) / 0.8) * aS
            for k in range(6):
                R = lead - 24 * k
                if R > 12:
                    al = ain * (0.85 - 0.11 * k) * clamp(1.25 - R / 1000)
                    circ(d, hx, hy, R, outline=rgba(CYAN, al), width=5 - 0.5 * k)
        black_hole(d, hx, hy, hr, aS, ring=lerp(5, 2, z))
        if dt < 1.2:  # flash
            circ(d, cx, cy, 80 + 900 * dt, fill=rgba(WHITE, 0.55 * math.exp(-dt / 0.22)))
            circ(d, cx, cy, 120 + 150 * dt, fill=rgba(WHITE, 0.9 * math.exp(-dt / 0.12)))
        # Earth
        aE = win(T, 13.6, 20.6, 0.6, 0.4)
        if aE > 0:
            ex, ey = 540, 1400
            circ(d, ex, ey, EARTH_R + 7, outline=rgba((120, 190, 255), 0.35 * aE), width=6)
            paste2x(img, EARTH, ex, ey, aE)
            if T > 17.5:  # arrival pulse
                p = (T - 17.5)
                for k in range(3):
                    q = p - 0.35 * k
                    if 0 < q < 1.6:
                        circ(d, ex, ey, EARTH_R + 10 + 110 * q, outline=rgba(GOLD, 0.8 * (1 - q / 1.6) * aE), width=5)
            texts.append((label_sprite("Earth", size=36, fill=GREY), 705, 1400, aE))
            texts.append((label_sprite("1.3 billion light-years away", size=34, fill=GREY), 540, 690,
                          win(T, 14.2, 20.4)))


def scene_ligo(img, d, T, texts):
    a = win(T, 20.6, 28.15, 0.5, 0.4)
    if a <= 0:
        return
    cx, cy, L = 330, 1330, 540
    g = math.sin(2 * math.pi * 1.0 * (T - 24.0)) * win(T, 24.0, 28.0, 0.6, 0.6) if T > 24 else 0.0
    Lx, Ly = L + 36 * g, L - 36 * g
    beam = rgba(RED, 0.95 * a)
    # tunnels
    rect(d, cx - 16, cy - Ly - 10, cx + 16, cy, outline=rgba(GREY, 0.28 * a), width=2)
    rect(d, cx, cy - 16, cx + Lx + 10, cy + 16, outline=rgba(GREY, 0.28 * a), width=2)
    # beams
    line(d, [(140, cy), (cx, cy), (cx + Lx, cy)], beam, 5)
    line(d, [(cx, cy - Ly), (cx, cy + 150)], beam, 5)
    # travelling light pulses
    for k in range(2):
        s = ((T * 0.9 + 0.5 * k) % 1.0); tri = 1 - abs(2 * s - 1)
        circ(d, cx + Lx * tri, cy, 9, fill=rgba((255, 220, 225), a))
        circ(d, cx, cy - Ly * tri, 9, fill=rgba((255, 220, 225), a))
    # parts
    rect(d, 80, cy - 34, 150, cy + 34, fill=rgba((40, 48, 80), a), outline=rgba(GREY, a), width=3)   # laser
    line(d, [(cx - 30, cy + 30), (cx + 30, cy - 30)], rgba(CYAN, a), 6)                                # splitter
    rect(d, cx - 46, cy - Ly - 14, cx + 46, cy - Ly, fill=rgba(CYAN, a))                                # mirror top
    rect(d, cx + Lx, cy - 46, cx + Lx + 14, cy + 46, fill=rgba(CYAN, a))                                # mirror right
    glow = 0.25 + 0.75 * abs(g)
    circ(d, cx, cy + 172, 30, fill=rgba((255, 230, 150), glow * a), outline=rgba(GOLD, a), width=4)     # detector
    if abs(g) > 0.05:
        circ(d, cx, cy + 172, 30 + 26 * abs(g), outline=rgba(GOLD, 0.5 * abs(g) * a), width=4)
    lab = lambda t, c=GREY, s=30: label_sprite(t, size=s, fill=c)
    texts.append((lab("laser"), 115, cy + 70, a))
    texts.append((lab("mirror"), cx, cy - Ly - 48, a))
    texts.append((lab("mirror"), cx + Lx - 10, cy - 80, a))
    texts.append((lab("detector"), cx + 125, cy + 172, a))
    a4 = win(T, 21.3, 24.0) * a
    texts.append((label_sprite("4 km", POP, 46, WHITE), cx + L / 2 + 20, cy + 70, a4))
    texts.append((label_sprite("4 km", POP, 46, WHITE), cx + 110, cy - L / 2, a4))
    if T > 24:
        big = lambda t, c: label_sprite(t, POP, 44, c)
        hx_, vx_ = ("STRETCH", GOLD) if g > 0 else ("SQUEEZE", CYAN)
        hv_, vv_ = ("SQUEEZE", CYAN) if g > 0 else ("STRETCH", GOLD)
        texts.append((big(hx_, vx_), cx + L / 2 + 20, cy + 72, abs(g) * a))
        texts.append((big(hv_, vv_), cx + 150, cy - L / 2, abs(g) * a))
        texts.append((label_sprite("motion hugely exaggerated", size=30, fill=GREY), 600, 690, win(T, 24.3, 27.9) * a))


def scene_proton(img, d, T, texts):
    a = win(T, 28.2, 31.75, 0.4, 0.35)
    if a > 0:
        px, py = 540, 1010
        s = 0.92 + 0.08 * ss((T - 28.2) / 0.7)
        circ(d, px, py, PROTON_R * 1.06, outline=rgba((255, 140, 70), 0.25 * a), width=10)
        paste2x(img, PROTON, px, py, a)
        texts.append((label_sprite("PROTON", POP, 54, (60, 15, 10), spacing=6, stroke=0), px, py, a * s))
        by = 1375; x0, x1 = px - PROTON_R, px + PROTON_R
        ab = ss((T - 28.9) / 0.5) * a
        line(d, [(x0, by), (x1, by)], rgba(WHITE, ab), 3)
        line(d, [(x0, by - 16), (x0, by + 16)], rgba(WHITE, ab), 3)
        line(d, [(x1, by - 16), (x1, by + 16)], rgba(WHITE, ab), 3)
        texts.append((label_sprite("one proton wide", size=34, fill=WHITE), 800, by + 42, ab))
        am = ss((T - 29.7) / 0.4) * a
        d.line([(px * S, (by - 40) * S), (px * S, (by + 40) * S)], fill=rgba(CYAN, am), width=2)
        line(d, [(px - 4, by + 48), (px - 60, by + 96)], rgba(CYAN, 0.8 * am), 2)
        texts.append((label_sprite("the stretch: 1/1000 of this bar", size=36, fill=CYAN), 430, by + 122, am))
    a = win(T, 31.75, 35.5, 0.4, 0.35)
    if a > 0:
        y = 1050; xs, xe = 200, 870
        prog = ss((T - 32.0) / 1.0); xp = lerp(xs, xe, prog)
        x = xs
        while x < xp - 8:
            line(d, [(x, y), (min(x + 16, xp), y)], rgba(GREY, 0.8 * a), 3); x += 30
        circ(d, xs, y, 44, fill=rgba((255, 200, 80), 0.25 * a))
        circ(d, xs, y, 28, fill=rgba((255, 225, 120), a))
        circ(d, xe, y, 26, fill=rgba((255, 110, 80), 0.25 * a * prog))
        circ(d, xe, y, 14, fill=rgba((255, 150, 110), a * prog))
        texts.append((label_sprite("Sun", size=34, fill=GREY), xs, y + 78, a))
        texts.append((label_sprite("nearest star", size=34, fill=GREY), xe - 40, y + 78, a * prog))
        texts.append((label_sprite("4.2 light-years", POP, 50, WHITE), 540, y - 70, a * prog))
        ah = ss((T - 33.3) / 0.4) * a
        d.line([((xe - 30) * S, (y - 46) * S), ((xe - 30) * S, (y + 46) * S)], fill=rgba(GOLD, ah), width=2)
        line(d, [(xe - 34, y + 54), (xe - 150, y + 190)], rgba(GOLD, 0.8 * ah), 2)
        texts.append((label_sprite("± one hair's width", POP, 44, GOLD), 600, y + 226, ah))


def scene_chirp(img, d, T, texts):
    a = win(T, 35.5, 43.3, 0.4, 0.5)
    if a <= 0:
        return
    x0, x1, yc, amp = 90, 990, 1040, 250
    line(d, [(x0, yc), (x1, yc)], rgba(GREY, 0.25 * a), 2)
    p = ss((T - 35.8) / 2.6)
    n = max(2, int(p * len(CH_U)))
    pulse = 1.0 + (0.05 * math.sin(2 * math.pi * 0.8 * T) if p >= 1 else 0)
    pts = [(lerp(x0, x1, CH_U[i]), yc - amp * pulse * CH_Y[i]) for i in range(0, n, 2)]
    if len(pts) > 1:
        line(d, pts, rgba(CYAN, a), 5)
        if p < 1:
            circ(d, pts[-1][0], pts[-1][1], 11, fill=rgba(WHITE, a))
    ab = ss((T - 36.6) / 0.5) * a
    by = 1350
    line(d, [(x0, by), (x1, by)], rgba(WHITE, ab), 3)
    line(d, [(x0, by - 16), (x0, by + 16)], rgba(WHITE, ab), 3)
    line(d, [(x1, by - 16), (x1, by + 16)], rgba(WHITE, ab), 3)
    texts.append((label_sprite("0.2 seconds", POP, 50, WHITE), 540, by + 56, ab))
    texts.append((label_sprite("the \"chirp\" of two black holes merging (illustration)", size=30, fill=GREY),
                  540, 680, ab))
    texts.append((label_sprite("spiral", size=30, fill=GREY), 330, yc + 190, ab))
    texts.append((label_sprite("merger", size=30, fill=GOLD), 775, yc - 300, ab))


# ---------- frame ----------
def frame(T):
    global CUR
    img = BG.copy()
    d = CUR = Canvas(img)
    texts = []
    scene_holes(img, d, T, texts)
    scene_ligo(img, d, T, texts)
    scene_proton(img, d, T, texts)
    scene_chirp(img, d, T, texts)
    if TM <= T < TM + 0.5:
        d.rectangle([0, 0, W * S, H * S], fill=rgba(WHITE, 0.6 * math.exp(-(T - TM) / 0.1)))
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
            if kick == "@countdown":
                yrs = int(round(1.3e9 * (1 - ss((T - 14.3) / 3.25)) / 1e6)) * 1_000_000
                kick = f"{yrs:,} YEARS TO GO" if yrs > 0 else "ARRIVAL"
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
