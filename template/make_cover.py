#!/usr/bin/env python3
"""Cover (thumbnail) for a short: a still from the animation plus a big title.
Usage: python3 make_cover.py <scene_module> <time_s> <out.jpg> "LINE ONE|WITH *GOLD* WORDS|LINE THREE" "FOOTER"
Keeps text inside the centre 4:5 area, which survives YouTube's crops."""
import sys, importlib
from PIL import ImageDraw, ImageFont
mod = importlib.import_module(sys.argv[1]); T = float(sys.argv[2]); out = sys.argv[3]
lines = sys.argv[4].split("|"); footer = sys.argv[5] if len(sys.argv) > 5 else ""
mod.CAPTIONS = []
img = mod.frame(T); d = ImageDraw.Draw(img)
POP = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
size = 128
while max(ImageFont.truetype(POP, size).getlength(l.replace("*", "")) for l in lines) > 960: size -= 4
f = ImageFont.truetype(POP, size); y = 400
for l in lines:
    words = l.split(" "); sp = f.getlength(" ")
    x = 540 - (sum(f.getlength(w.strip("*")) for w in words) + sp * (len(words) - 1)) / 2
    for w in words:
        gold = w.startswith("*"); w = w.strip("*")
        d.text((x, y), w, font=f, fill=(255, 196, 92) if gold else (255, 255, 255), anchor="lm", stroke_width=8, stroke_fill=(2, 3, 10))
        x += f.getlength(w) + sp
    y += int(size * 1.16)
if footer:
    f2 = ImageFont.truetype(POP, 54); x = 540 - (sum(f2.getlength(c) + 8 for c in footer)) / 2
    for c in footer:
        d.text((x, 1500), c, font=f2, fill=(110, 225, 255), anchor="lm", stroke_width=5, stroke_fill=(2, 3, 10)); x += f2.getlength(c) + 8
img.save(out, quality=90)
