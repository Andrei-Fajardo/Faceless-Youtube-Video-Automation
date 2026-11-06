"""9:16 horror thumbnail (1080x1920): the reveal panel, lifted so it reads in a bright feed, a red under-glow, and a two-line hook in Impact.
  make_horror_thumbnail.py PANEL_PNG OUT_JPG "LINE ONE" "LINE TWO"   (LINE TWO is drawn red and larger)
Text stays in the middle band (y 950-1450): above the bottom 22% that Shorts UI covers, and clear of the figure's head."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

panel, out, l1, l2 = sys.argv[1:5]
W, H = 1080, 1920
im = Image.open(panel).convert("RGB").resize((W, H), Image.LANCZOS)
a = np.asarray(im).astype(np.float32) / 255.0
a = a ** 0.78                                    # lift the shadows: a nearly black frame disappears in a bright feed
im = Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))
im = ImageEnhance.Contrast(im).enhance(1.12)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
vig = 1 - 0.55 * np.clip(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.42) / (H * 0.7)) ** 2 - 0.25, 0, 1)
arr = np.asarray(im).astype(np.float32) * vig[..., None]
glow = np.clip((yy - 950) / 520, 0, 1) * np.clip((1750 - yy) / 400, 0, 1)   # red under-glow behind the text band
arr[..., 0] = arr[..., 0] + 70 * glow; arr[..., 1] *= 1 - 0.25 * glow; arr[..., 2] *= 1 - 0.25 * glow
im = Image.fromarray(arr.clip(0, 255).astype(np.uint8))

IMPACT = "C:/Windows/Fonts/impact.ttf"
d = ImageDraw.Draw(im)


def line(text, size, y, fill):
    f = ImageFont.truetype(IMPACT, size)
    while d.textlength(text, font=f) > W * 0.86: size -= 4; f = ImageFont.truetype(IMPACT, size)
    x = (W - d.textlength(text, font=f)) / 2
    for r in (14, 9):   # heavy black outline + soft shadow
        d.text((x, y + 8), text, font=f, fill=(0, 0, 0), stroke_width=r, stroke_fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
    return size


s1 = line(l1, 190, 960, (245, 240, 230))
line(l2, 330, 960 + int(s1 * 1.12), (232, 34, 28))
im.save(out, quality=93)
print("thumbnail", out, im.size)
