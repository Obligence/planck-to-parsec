#!/usr/bin/env python3
"""The Sun is too cold to shine: its core is hundreds of times too cold for protons to fuse classically, and only quantum
tunnelling lets it burn. Includes a real 1D Schroedinger calculation of a wave packet tunnelling through a barrier.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 sun_tunnelling.py preview 1.5 6.4 12      -> frame_<t>.png files
  python3 sun_tunnelling.py render 0 41.5 out.mp4   -> renders that time range
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
    (0.0, 4.5, None, "The Sun is | *too cold to shine.*"),
    (4.5, 10.0, None, "Its core: *15 million* | degrees. Sounds hot."),
    (10.0, 16.0, None, "To fuse, protons | must touch. | But they *repel.*"),
    (16.0, 22.0, None, "It should take | *billions of degrees.* | The Sun is far too cold."),
    (22.0, 28.0, None, "So how does it burn? | *The protons cheat.*"),
    (28.0, 35.0, "QUANTUM TUNNELLING", "A particle is a wave. | A little leaks | *through the wall.*"),
    (35.0, 41.0, None, "Even then, it rarely works: | one proton must | *become a neutron.*"),
    (41.0, 46.0, None, "Average wait: | *9 billion years.* | Your body out-heats its core."),
    (46.0, 54.0, None, "Every sunbeam began | with a particle | *walking through a wall.*"),
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
ORANGE, PROT = (255, 140, 50), (255, 110, 95)


def lerp3(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)), int(lerp(c0[1], c1[1], t)), int(lerp(c0[2], c1[2], t)))


_sr = np.random.default_rng(5)
GRAN = [(float(_sr.uniform(0, 1) ** 0.5), float(_sr.uniform(0, 6.283)), float(_sr.uniform(0.5, 2.0)), float(_sr.uniform(0, 6.283)))
        for _ in range(170)]
RAYS = [(float(_sr.uniform(0, 6.283)), float(_sr.uniform(0.25, 1.0)), float(_sr.uniform(0.3, 1.2)), float(_sr.uniform(0, 6.283)))
        for _ in range(64)]


def sun(d, cx, cy, R, T, a, rays=1.0, cool=0.0):
    """A stylised Sun: glowing disk, slowly boiling surface, flickering rays. cool > 0 tints it toward ember red."""
    if a <= 0:
        return
    hot, mid, rim = lerp3((255, 250, 220), (255, 190, 150), cool), lerp3(GOLD, (230, 110, 60), cool), lerp3(ORANGE, (150, 40, 30), cool)
    for th, ln, sp, ph in RAYS:
        fl = 0.55 + 0.45 * math.sin(sp * 2.2 * T + ph)
        th2 = th + 0.05 * T
        r1 = R * (1.06 + 0.75 * ln * fl * rays)
        line(d, [(cx + R * 0.98 * math.cos(th2), cy + R * 0.98 * math.sin(th2)), (cx + r1 * math.cos(th2), cy + r1 * math.sin(th2))],
             rgba(mid, 0.30 * a * fl), 5)
    for k in range(5):
        circ(d, cx, cy, R * (1.30 - 0.06 * k), fill=rgba(rim, 0.05 * a))
    n = 26
    for k in range(n):
        f = k / (n - 1)
        col = lerp3(rim, mid, clamp(f * 2)) if f < 0.5 else lerp3(mid, hot, (f - 0.5) * 2)
        circ(d, cx, cy, R * (1 - 0.93 * f), fill=rgba(col, a))
    for r, th, sp, ph in GRAN:
        tw = 0.5 + 0.5 * math.sin(sp * 1.6 * T + ph)
        th2 = th + 0.04 * T
        circ(d, cx + R * 0.93 * r * math.cos(th2), cy + R * 0.93 * r * math.sin(th2), 5 + 7 * tw, fill=rgba(WHITE, 0.10 * a * tw))


def proton(d, x, y, r, a, col=PROT, plus=True):
    if a <= 0:
        return
    circ(d, x, y, r * 1.9, fill=rgba(col, 0.13 * a))
    circ(d, x, y, r, fill=rgba(col, a))
    circ(d, x - r * 0.3, y - r * 0.3, r * 0.35, fill=rgba(WHITE, 0.35 * a))
    if plus:
        line(d, [(x - r * 0.45, y), (x + r * 0.45, y)], rgba(WHITE, a), r * 0.2)
        line(d, [(x, y - r * 0.45), (x, y + r * 0.45)], rgba(WHITE, a), r * 0.2)


# ---------- scenes ----------
SY = 1060


def scene_sun(img, d, T, texts):
    a = win(T, -1.0, 10.0, 0.2, 0.3)
    if a <= 0:
        return
    g = ss((T - 4.6) / 0.8)                                 # second caption: look inside, at the core
    cool = 0.75 * (1 - ss((T - 3.2) / 1.2)) * ss((T + 0.6) / 1.2) if T < 4.6 else 0
    sun(d, CX, SY, 290, T, a, rays=1.0 - 0.6 * cool, cool=cool)
    if g > 0:
        pul = 0.5 + 0.5 * math.sin(5 * T)
        circ(d, CX, SY, 290, fill=rgba((20, 8, 6), 0.55 * g * a))
        circ(d, CX, SY, 86 + 5 * pul, fill=rgba(WHITE, 0.95 * g * a))
        circ(d, CX, SY, 112 + 6 * pul, outline=rgba(GOLD, 0.9 * g * a), width=4)
        if CAPTIONS:
            texts.append((label_sprite("core", POP, 40, (30, 16, 8), stroke=0), CX, SY, g * a))
            texts.append((label_sprite("15,000,000", POP, 112, GOLD), CX, 1425, g * a))
            texts.append((label_sprite("degrees", POP, 44, WHITE), CX, 1500, g * a))


def scene_repel(img, d, T, texts):
    a = win(T, 10.0, 16.0, 0.3, 0.3)
    if a <= 0:
        return
    u = ((T - 10.0) % 2.0) / 2.0                            # one approach and bounce every two seconds
    gap = 330 - 262 * math.sin(math.pi * u) ** 0.6          # half the distance between the two protons
    close = clamp((150 - gap) / 80)
    y = 1010
    for k in range(4):                                      # the repulsion, drawn as rings that flare when they get close
        q = (1.4 * T + k / 4) % 1.0
        for sx in (-1, 1):
            circ(d, CX + sx * gap, y, 46 + 150 * q, outline=rgba(PROT, 0.38 * (1 - q) * a * (0.35 + 0.65 * close)), width=3)
    line(d, [(CX, y - 120), (CX, y + 120)], rgba(WHITE, 0.55 * a * close), 3)
    proton(d, CX - gap, y, 46, a); proton(d, CX + gap, y, 46, a)
    texts.append((label_sprite("proton", size=32, fill=PROT), CX - 300, y - 150, a))
    texts.append((label_sprite("proton", size=32, fill=PROT), CX + 300, y - 150, a))
    texts.append((label_sprite("same charge: they push apart", POP, 40, WHITE), CX, 1290, a * ss((T - 11.0) / 0.5)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), CX, 1480, a))


def scene_bars(img, d, T, texts):
    a = win(T, 16.0, 22.0, 0.3, 0.3)
    if a <= 0:
        return
    base, top = 1420, 720
    g = ss((T - 16.3) / 1.6)
    line(d, [(140, base), (860, base)], rgba(GREY, 0.6 * a), 3)
    h = (base - top) * g
    rect(d, 250, base - h, 430, base, fill=rgba(PROT, 0.92 * a))
    rect(d, 590, base - max(1.2, h * 15e6 / 1e10), 770, base, fill=rgba(GOLD, a))
    texts.append((label_sprite("needed", POP, 38, PROT), 340, top - 78, a * g))
    texts.append((label_sprite("about 10 billion", POP, 46, WHITE), 340, top - 30, a * g))
    ga = a * ss((T - 17.6) / 0.5)
    texts.append((label_sprite("the Sun", POP, 38, GOLD), 680, base - 150, ga))
    texts.append((label_sprite("15 million", POP, 46, WHITE), 680, base - 102, ga))
    line(d, [(680, base - 66), (680, base - 12)], rgba(GOLD, 0.9 * ga), 3)
    line(d, [(668, base - 26), (680, base - 12), (692, base - 26)], rgba(GOLD, 0.9 * ga), 3)
    texts.append((label_sprite("bars to scale · degrees", size=28, fill=GREY), CX, 1480, a))


def hill_y(x):
    return 1260 - 330 * math.exp(-((x - CX) / 150.0) ** 2)


def scene_hill(img, d, T, texts):
    a = win(T, 22.0, 28.0, 0.3, 0.3)
    if a <= 0:
        return
    pts = [(x, hill_y(x)) for x in range(80, 921, 8)]
    for i in range(len(pts) - 1):
        line(d, [pts[i], pts[i + 1]], rgba(CYAN, 0.9 * a), 5)
    u = ((T - 22.0) % 2.0) / 2.0                            # the proton runs at the hill, gets part of the way, rolls back
    x = 130 + 250 * math.sin(math.pi * u)
    proton(d, x, hill_y(x) - 36, 32, a)
    proton(d, 800, hill_y(800) - 36, 32, 0.9 * a)
    pul = 0.5 + 0.5 * math.sin(4.5 * T)
    texts.append((label_sprite("?", POP, 170, WHITE), CX, 800, a * (0.7 + 0.3 * pul)))
    texts.append((label_sprite("not enough energy to get over", POP, 38, WHITE), CX, 1345, a * ss((T - 22.8) / 0.5)))
    texts.append((label_sprite("the repulsion drawn as a hill · illustration", size=28, fill=GREY), CX, 1480, a))


# --- a real quantum calculation: a wave packet meets a barrier it does not have the energy to climb ---
def tunnel_sim():
    """1D time-dependent Schroedinger equation (hbar = m = 1), split-step Fourier method. Returns |psi|^2 over time."""
    n, L = 2048, 240.0
    x = np.arange(n) * L / n
    k = 2 * np.pi * np.fft.fftfreq(n, L / n)
    k0, sig, x0 = 1.5, 7.0, 70.0                             # packet energy k0^2 / 2 = 1.125
    b0, b1, v0 = 120.0, 121.8, 1.6                           # barrier taller than the packet's energy
    V = np.where((x >= b0) & (x < b1), v0, 0.0)
    psi = np.exp(-((x - x0) ** 2) / (4 * sig ** 2) + 1j * k0 * x)
    psi /= np.sqrt((abs(psi) ** 2).sum() * L / n)
    dt, steps, every = 0.04, 1500, 5
    eV, eK = np.exp(-0.5j * V * dt), np.exp(-0.5j * k ** 2 * dt)
    out = []
    for i in range(steps + 1):
        if i % every == 0:
            out.append((abs(psi) ** 2).astype(np.float32))
        psi = eV * np.fft.ifft(eK * np.fft.fft(eV * psi))
    rho = np.array(out)
    through = float(rho[-1][x >= b1].sum() * L / n)
    return x, rho, dt * every, (b0, b1), through


QX, QRHO, QDT, QB, QTHROUGH = tunnel_sim()
TUN_T = 31.6                                                # picture time at which the packet is inside the wall


def scene_tunnel(img, d, T, texts):
    a = win(T, 28.0, 35.0, 0.3, 0.3)
    if a <= 0:
        return
    st = lerp(8.0, 56.0, clamp((T - 28.0) / 7.0))            # simulation time shown
    u = min(st / QDT, len(QRHO) - 1.001); i = int(u); f = u - i
    rho = QRHO[i] * (1 - f) + QRHO[i + 1] * f
    base, x0, x1 = 1290, 40.0, 200.0
    sx = lambda q: 80 + (q - x0) / (x1 - x0) * 840
    bx0, bx1 = sx(QB[0]) - 7, sx(QB[1]) + 7
    rect(d, bx0, base - 470, bx1, base, fill=rgba(PROT, 0.30 * a), outline=rgba(PROT, 0.95 * a), width=3)
    line(d, [(80, base), (920, base)], rgba(GREY, 0.6 * a), 3)
    sel = np.nonzero((QX >= x0) & (QX <= x1))[0][::2]
    amp = 5200.0
    pts = [(sx(float(QX[j])), base - min(520.0, amp * float(rho[j]))) for j in sel]
    for j in range(len(pts) - 1):
        (xa, ya), (xb, yb) = pts[j], pts[j + 1]
        if base - ya > 0.8 or base - yb > 0.8:
            d.d.polygon([xa * S, base * S, xa * S, ya * S, xb * S, yb * S, xb * S, base * S], aggdraw.Brush(CYAN, int(70 * a)))
            line(d, [(xa, ya), (xb, yb)], rgba(CYAN, a), 4)
    dt = T - TUN_T
    if dt > 0:
        circ(d, bx1 + 10, base - 60, 30 + 420 * dt, outline=rgba(WHITE, 0.8 * math.exp(-dt / 0.45) * a), width=5)
    ga = a * ss((T - 32.4) / 0.5)
    texts.append((label_sprite("the wall", POP, 36, PROT), (bx0 + bx1) / 2, base - 505, a))
    texts.append((label_sprite("bounced back", POP, 36, WHITE), 300, base + 52, ga))
    texts.append((label_sprite("got through", POP, 36, GOLD), 780, base + 52, ga))
    texts.append((label_sprite(f"{100 * QTHROUGH:.0f}% here; in the Sun, far less", size=30, fill=GREY), CX, 1420, ga))
    texts.append((label_sprite("real quantum simulation (1D) · wall not to scale", size=28, fill=GREY), CX, 1480, a))


_wr = np.random.default_rng(9)
TRY = [(float(_wr.uniform(700, 1380)), float(_wr.uniform(0.8, 1.7)), float(_wr.uniform(0, 1))) for _ in range(30)]


def scene_wait(img, d, T, texts):
    a = win(T, 35.0, 41.0, 0.3, 0.3)
    if a <= 0:
        return
    wx = 560
    rect(d, wx, 680, wx + 22, 1400, fill=rgba(PROT, 0.30 * a), outline=rgba(PROT, 0.95 * a), width=3)
    for y, sp, ph in TRY:                                   # protons running at the wall and bouncing off, again and again
        u = (sp * 0.9 * T + ph) % 1.0
        x = wx - 26 - 380 * abs(math.sin(math.pi * u)) ** 0.8
        proton(d, x, y, 13, 0.8 * a, plus=False)
        if abs(math.sin(math.pi * u)) < 0.12:
            circ(d, wx - 6, y, 16, fill=rgba(WHITE, 0.5 * a))
    NEUT = (150, 175, 225)
    g = ss((T - 36.2) / 1.2)                                # one gets through and meets a proton on the other side...
    w = ss((T - 38.3) / 0.5)                                # ...and in that instant one of the pair must become a neutron
    px = lerp(wx + 40, 716, g)
    proton(d, 792, 1040, 34, a * ss((T - 35.4) / 0.5), col=lerp3(PROT, NEUT, w), plus=w < 0.5)
    if g > 0:
        proton(d, px, 1040, 34, a * g)
    dt = T - 38.3
    if dt > 0:
        circ(d, 754, 1040, 50 + 330 * dt, outline=rgba(WHITE, 0.8 * math.exp(-dt / 0.4) * a), width=4)
        circ(d, 754, 1040, 92 + 5 * math.sin(6 * T), outline=rgba(GOLD, 0.7 * a * w), width=4)
    texts.append((label_sprite("proton", size=30, fill=PROT), 700, 960, a * g))
    texts.append((label_sprite("neutron", size=30, fill=NEUT), 820, 1124, a * w))
    texts.append((label_sprite("fused", POP, 40, GOLD), 754, 1200, a * ss((T - 39.0) / 0.4)))
    texts.append((label_sprite("the weak force: extremely rare", POP, 38, WHITE), CX - 20, 1452, a * ss((T - 38.6) / 0.5)))
    texts.append((label_sprite("illustration", size=28, fill=GREY), 250, 665, a))


SEGS = [(0, 100, 0, 340, 120), (-78, 110, -120, 320, 40), (78, 110, 120, 320, 40),
        (-32, 340, -44, 590, 52), (32, 340, 44, 590, 52)]          # torso, arms, legs (head is a circle at 0,0 r62)


def body(d, cx, y0, s, col, a):
    """A neutral, generic human figure (no likeness): head centre at (cx, y0), feet at y0 + 616*s."""
    c = rgba(col, a)
    circ(d, cx, y0, 62 * s, fill=c)
    for x0, y0_, x1, y1, w in SEGS:
        line(d, [(cx + x0 * s, y0 + y0_ * s), (cx + x1 * s, y0 + y1 * s)], c, w * s)
        circ(d, cx + x0 * s, y0 + y0_ * s, w * s / 2, fill=c); circ(d, cx + x1 * s, y0 + y1 * s, w * s / 2, fill=c)


def scene_body(img, d, T, texts):
    a = win(T, 41.0, 46.0, 0.3, 0.3)
    if a <= 0:
        return
    pul = 0.5 + 0.5 * math.sin(3 * T)
    lx, rx = 265, 735
    rect(d, lx - 130, 880, lx + 130, 1140, fill=rgba(GOLD, (0.55 + 0.12 * pul) * a), outline=rgba(WHITE, 0.9 * a), width=3)
    for k in range(3):
        q = (0.5 * T + k / 3) % 1.0
        rect(d, lx - 130 - 60 * q, 880 - 60 * q, lx + 130 + 60 * q, 1140 + 60 * q, outline=rgba(GOLD, 0.35 * (1 - q) * a), width=2)
    body(d, rx, 800, 0.62, (255, 150, 110), a)
    for k in range(4):
        q = (0.6 * T + k / 4) % 1.0
        circ(d, rx, 990, 170 + 110 * q, outline=rgba(PROT, 0.5 * (1 - q) * a), width=3)
    texts.append((label_sprite("the Sun's centre", POP, 36, GOLD), lx, 800, a))
    texts.append((label_sprite("1 cubic metre", size=30, fill=(30, 16, 8), stroke=0), lx, 1010, a))
    texts.append((label_sprite("about 276 watts", POP, 40, WHITE), lx, 1200, a * ss((T - 41.8) / 0.4)))
    texts.append((label_sprite("like a compost heap", size=30, fill=GREY), lx, 1250, a * ss((T - 42.4) / 0.4)))
    texts.append((label_sprite("you", POP, 36, PROT), rx, 715, a))
    texts.append((label_sprite("more heat,", POP, 40, WHITE), rx, 1235, a * ss((T - 43.0) / 0.4)))
    texts.append((label_sprite("for the same volume", size=30, fill=GREY), rx, 1285, a * ss((T - 43.0) / 0.4)))
    texts.append((label_sprite("from solar models · illustration", size=28, fill=GREY), CX, 1480, a))


_pr = np.random.default_rng(13)
PHOT = [(float(_pr.uniform(0, 6.283)), float(_pr.uniform(0.25, 0.6)), float(_pr.uniform(0, 1))) for _ in range(90)]


def scene_end(img, d, T, texts):
    a = win(T, 46.0, 54.0, 0.4, 0.4)
    if a <= 0:
        return
    R = lerp(150, 230, ss((T - 46.0) / 6.0))
    for th, sp, ph in PHOT:                                 # sunlight streaming out
        q = (sp * T + ph) % 1.0
        r = R + 560 * q
        x, y = CX + r * math.cos(th), SY + r * math.sin(th)
        if 650 < y < 1510 and 20 < x < 960:
            line(d, [(x, y), (CX + (r - 34) * math.cos(th), SY + (r - 34) * math.sin(th))], rgba(GOLD, 0.8 * a * (1 - q) ** 0.5), 4)
    sun(d, CX, SY, R, T, a, rays=1.3)


SCENES = (scene_sun, scene_repel, scene_bars, scene_hill, scene_tunnel, scene_wait, scene_body, scene_end)


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
