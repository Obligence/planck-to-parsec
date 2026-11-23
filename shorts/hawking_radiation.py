#!/usr/bin/env python3
"""Can empty space make something from nothing? Hawking radiation: at a black hole's edge, a virtual pair can be
split, one partner falls in and the other escapes as real radiation (Hawking 1974). The energy comes from the
black hole's mass, so it slowly evaporates: a Sun-mass black hole needs about 10^67 years.
Standard output: 2160x3840 (4K vertical), 60 fps. Set PS_SCALE=1 PS_FPS=30 for a fast 1080p draft.

Usage:
  python3 hawking_radiation.py preview 0 6.4 12      -> frame_<t>.png files
  python3 hawking_radiation.py render 0 43 out.mp4   -> renders that time range
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
    (0.0, 4.5, None, "Can *nothing* | *make something?*"),
    (4.5, 10.0, None, "Empty space is | *never truly empty.*"),
    (10.0, 16.5, None, "At a black hole's edge, | one falls in, | *one escapes.*"),
    (16.5, 22.5, "PREDICTED 1974", "That glow is real: | *Hawking radiation.*"),
    (22.5, 29.0, None, "But it's *not free:* | the black hole | *pays with its mass.*"),
    (29.0, 36.0, None, "A Sun-mass black hole | takes *unimaginably long* | to evaporate."),
    (36.0, 43.0, None, "Even here, | *nothing is free.*"),
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


# ---------- virtual pairs: two particles pop out of nothing, drift apart a little and annihilate again ----------
_rng = np.random.default_rng(11)
FIELD = []
for _ in range(1100):
    FIELD.append((_rng.uniform(80, 920), _rng.uniform(680, 1450), _rng.uniform(-2.0, DUR + 2.0),
                  _rng.uniform(0.8, 1.3), _rng.uniform(0, math.pi)))


def pair(d, x, y, u, ang, a, sep=40):
    """One virtual pair at phase u (0..1): born, separates, rejoins, vanishes in a small flash."""
    if a <= 0.004 or not (0 < u < 1.12):
        return
    if u >= 1.0:                                              # annihilation flash
        f = (u - 1.0) / 0.12
        circ(d, x, y, 6 + 26 * f, outline=rgba(WHITE, 0.8 * (1 - f) * a), width=2.5)
        return
    s = sep * math.sin(math.pi * u) ** 0.8
    al = a * ss(u / 0.15)
    dx, dy = 0.5 * s * math.cos(ang), 0.5 * s * math.sin(ang)
    for (px, py, c) in ((x + dx, y + dy, CYAN), (x - dx, y - dy, GOLD)):
        circ(d, px, py, 15, fill=rgba(c, 0.18 * al))
        circ(d, px, py, 7, fill=rgba(c, al))
        circ(d, px - 2, py - 2, 2.5, fill=rgba(WHITE, 0.6 * al))


def field(d, T, a, keep=None):
    if a <= 0.004:
        return
    for x, y, tb, L, ang in FIELD:
        u = (T - tb) / L
        if 0 < u < 1.12 and (keep is None or keep(x, y)):
            pair(d, x, y, u, ang, a)


# ---------- the black hole ----------
def bh_state(T):
    """radius and centre of the black hole over time (it shrinks while it radiates, scenes 5-6)."""
    R = 150 - 75 * ss((T - 23.5) / 5.0)
    R = lerp(R, 55, ss((T - 29.0) / 1.2))
    y = lerp(BY0, 830, ss((T - 29.0) / 1.2))
    return R, y


def black_hole(d, cx, cy, R, T, a):
    if a <= 0.004:
        return
    for k in range(16):                                       # warm glow just outside the edge
        circ(d, cx, cy, R * (1.0 + 0.055 * (16 - k)), fill=rgba(HOT, 0.045 * a * (k + 1) / 16))
    circ(d, cx, cy, R * 1.03, outline=rgba(GOLD, 0.85 * a), width=3)
    for k in range(36):                                       # a faint dashed ring turning slowly: something always moves
        t0 = 6.283 * k / 36 + 0.35 * T
        line(d, [(cx + 1.12 * R * math.cos(t0), cy + 1.12 * R * math.sin(t0)),
                 (cx + 1.12 * R * math.cos(t0 + 0.06), cy + 1.12 * R * math.sin(t0 + 0.06))], rgba(HOT, 0.5 * a), 2)
    circ(d, cx, cy, R, fill=(0, 0, 0, int(255 * clamp(a))))


# Pairs born at the edge: the gold partner falls in, the cyan one escapes (simplified picture).
EDGE = []
_t = 11.2
while _t < 36.0:
    rate = 1.6 if _t < 16.5 else 6.0 if _t < 29.0 else 1.2
    EDGE.append((_t, _rng.uniform(0, 2 * math.pi)))
    _t += _rng.exponential(1.0 / rate)
HERO_T, HERO_TH = 11.4, -2.25                                 # the one we watch closely (upper left)


def edge_pair(d, T, tb, th, a, hero=False):
    R, cy = bh_state(T)
    dt = T - tb
    if dt < 0 or a <= 0.004:
        return None
    slow = 1.7 if hero else 1.0
    q = dt / slow
    if q > 3.2:
        return None
    ct, st = math.cos(th), math.sin(th)
    out = in_ = None
    if q < 0.45:                                              # born at the edge and drifting apart
        s = ss(q / 0.45)
        r_out, r_in = R + 20 + 16 * s, R + 20 - 16 * s
        al = a * ss(q / 0.12)
        in_ = (r_in, al)
        out = (r_out, al)
    else:
        e = q - 0.45
        r_in = R + 4 - 60 * e                                 # falls in and is gone behind the edge
        in_ = (r_in, a * (1 - ss(e / 0.35)))
        r_out = R + 36 + 70 * e + 120 * e * e                 # escapes, faster and faster
        out = (r_out, a * (1 - ss((e - 1.9) / 0.8)))
    ri, ai = in_
    if ai > 0.004 and ri > R * 0.9:
        x, y = CX + ri * ct, cy + ri * st
        circ(d, x, y, 15, fill=rgba(GOLD, 0.18 * ai)); circ(d, x, y, 7, fill=rgba(GOLD, ai))
    ro, ao = out
    if ao > 0.004:
        for k in range(10):                                   # trail
            rr = ro - 5 * k * (1 + min(q, 2))
            if rr < R:
                break
            f = 1 - k / 10
            circ(d, CX + rr * ct, cy + rr * st, 3 + 5 * f, fill=rgba(CYAN, 0.5 * ao * f * f))
        x, y = CX + ro * ct, cy + ro * st
        circ(d, x, y, 15, fill=rgba(CYAN, 0.2 * ao)); circ(d, x, y, 7.5, fill=rgba(CYAN, ao))
        circ(d, x - 2, y - 2, 2.5, fill=rgba(WHITE, 0.6 * ao))
        return (x, y, q)
    return None


# ---------- scenes ----------
def scene_field(img, d, T, texts):
    """0-10 and again from 36 (so the Short loops): empty space, fizzing with virtual pairs."""
    a = win(T, -1.0, 10.6, 0.2, 0.6) + win(T, 36.2, DUR + 2, 0.9, 0.3)
    if a <= 0.004:
        return
    if T < 20:
        z = ss((T - 4.6) / 1.0)                                # scene 2: a gentle push in on one pair
        field(d, T, a)
        if z > 0 and CAPTIONS:
            texts.append((label_sprite("particle", POP, 34, CYAN), 300, 1462, a * z))
            texts.append((label_sprite("antiparticle", POP, 34, GOLD), 690, 1462, a * z))
            texts.append((label_sprite("they appear and vanish in a flash", POP, 36, WHITE), CX, 655, a * z))
    else:
        field(d, T, a)
    if CAPTIONS:
        texts.append((label_sprite("simplified picture", size=26, fill=GREY), CX, 1510, a * (T < 20)))
    if T > 20 and CAPTIONS:                                   # closing question for viewers (last ~2 s)
        qa = a * ss((T - (DUR - 2.6)) / 0.4)
        texts.append((label_sprite("If black holes evaporate, where", POP, 42, GOLD), CX, 1440 - 28, qa))
        texts.append((label_sprite("does everything they swallowed go?", POP, 42, GOLD), CX, 1440 + 28, qa))


def scene_bh(img, d, T, texts):
    """10-36: the black hole; pairs at its edge; Hawking radiation; it shrinks; the huge time scale."""
    a = win(T, 10.0, 36.6, 0.9, 0.7)
    if a <= 0.004:
        return
    R, cy = bh_state(T)
    field(d, T, 0.35 * a, keep=lambda x, y: math.hypot(x - CX, y - cy) > R * 1.9)   # space around it still fizzes
    black_hole(d, CX, cy, R, T, a)
    hero = None
    for tb, th in EDGE:
        if abs(tb - HERO_T) < 1.2 and T < 16.5:
            continue                                          # keep the hero pair alone at first
        edge_pair(d, T, tb, th, a * (0.85 if T > 16 else 0.6))
    h = edge_pair(d, T, HERO_T, HERO_TH, a, hero=True)
    if h and T < 16.5 and CAPTIONS:
        x, y, q = h
        la = a * ss((q - 0.6) / 0.3) * (1 - ss((T - 15.6) / 0.5))
        texts.append((label_sprite("escapes", POP, 38, CYAN), x - 10, y - 50, la))
    if 11.0 < T < 16.5 and CAPTIONS:
        fa = a * ss((T - (HERO_T + 1.4)) / 0.3) * (1 - ss((T - 15.6) / 0.5))
        texts.append((label_sprite("falls in", POP, 38, GOLD), CX + R * 0.55, cy + R + 60, fa))
        texts.append((label_sprite("event horizon", size=28, fill=GREY), CX + 40, cy + R + 115, a * (1 - ss((T - 15.6) / 0.5))))
    if CAPTIONS:
        ha = a * ss((T - 16.8) / 0.5) * (1 - ss((T - 22.6) / 0.4))
        texts.append((label_sprite(f"Hawking radiation · predicted {YEAR}", POP, 38, CYAN), CX, 1420, ha))
        texts.append((label_sprite("not yet detected: far too faint", size=30, fill=GREY), CX, 1468, ha))
        texts.append((label_sprite("simplified picture", size=26, fill=GREY), CX, 1510, a * (1 - ss((T - 22.4) / 0.4))))
    # scene 5: a mass gauge that drains as the particles escape
    ga = a * ss((T - 22.8) / 0.4) * (1 - ss((T - 29.0) / 0.4))
    if ga > 0.004:
        gy, x0, x1 = 1440, 140, 860
        rect(d, x0, gy - 13, x1, gy + 13, fill=rgba((20, 26, 48), ga), outline=rgba(GREY, 0.8 * ga), width=2)
        f = (R / 150.0) ** 3                                  # mass goes with the radius
        rect(d, x0 + 3, gy - 10, x0 + 3 + (x1 - x0 - 6) * f, gy + 10, fill=rgba(HOT, ga))
        if CAPTIONS:
            texts.append((label_sprite("black hole's mass", POP, 36, WHITE), CX, gy - 50, ga))
            texts.append((label_sprite("illustration · hugely sped up", size=26, fill=GREY), CX, 1500, ga))
    # scene 6: the time it takes, counted up as a power of ten
    ta = a * ss((T - 29.8) / 0.5)
    if ta > 0.004 and CAPTIONS:
        e = int(round(lerp(10, EVAP_EXP, ss((T - 29.9) / 1.7))))
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
        ua = ta * ss((T - 33.4) / 0.5)
        texts.append((label_sprite(f"the universe so far: {AGE_UNIVERSE}", POP, 36, CYAN), CX, 1395, ua))
        texts.append((label_sprite("theory: not yet measured", size=26, fill=GREY), CX, 1460, ta))


SCENES = (scene_field, scene_bh)


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
