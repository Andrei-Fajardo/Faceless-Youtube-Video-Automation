"""Brand kit for the horror channel "dreadcast": profile picture (800x800), banner (2560x1440, text inside the 1546x423 safe area),
watermark (150x150 transparent PNG). One motif: a crack of light under a door, a night-vision green look, and the full stop of the name drawn as a red REC dot.
  make_brand.py OUT_DIR"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
BG, PALE, GREEN, RED = (4, 7, 9), (214, 240, 224), (143, 230, 176), (255, 59, 48)
F = "C:/Windows/Fonts/"


def font(names, size):
    for n in names:
        try: return ImageFont.truetype(F + n, size)
        except OSError: pass
    return ImageFont.load_default()


LIGHT = ["segoeuil.ttf", "calibril.ttf", "bahnschrift.ttf", "arial.ttf"]
MONO = ["consola.ttf", "cour.ttf"]


def glow(layer, radii=(6, 18, 44), gains=(0.9, 0.7, 0.55)):
    """screen-add blurred copies of an RGB layer: a phosphor halo"""
    base = np.asarray(layer).astype(np.float32)
    acc = base.copy()
    for r, g in zip(radii, gains): acc += np.asarray(layer.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) * g
    return Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8))


def finish(im, grain=0.07, scan=0.16, vig=0.55, seed=1):
    """night-vision finish: vignette, scanlines, grain"""
    W, H = im.size
    a = np.asarray(im).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = 1 - vig * np.clip((((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2) - 0.22, 0, 1)
    a *= v[..., None]
    a *= (1 - scan * ((yy % 4) < 1.2))[..., None]
    a += np.random.default_rng(seed).normal(0, grain, (H, W, 1)) * (0.4 + a.mean(2, keepdims=True))
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def door_crack(W, H, cx, top, bottom, width, spill):
    """the motif: a thin vertical crack of light (a door left open) that fans out onto the floor"""
    L = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(L)
    d.rectangle([cx - width // 2, top, cx + width // 2, bottom], fill=PALE)
    # the light fan on the floor: a soft trapezoid widening away from the door
    d.polygon([(cx - width // 2, bottom), (cx + width // 2, bottom), (cx + spill, bottom + spill * 0.9), (cx - spill, bottom + spill * 0.9)], fill=(70, 108, 88))
    return glow(L.filter(ImageFilter.GaussianBlur(1.2)), (8, 26, 70), (0.9, 0.8, 0.7))


def rec_dot(W, H, cx, cy, r):
    L = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(L).ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
    return glow(L, (r * 0.5, r * 1.4, r * 3.2), (0.8, 0.7, 0.6))


def screen_add(*layers):
    a = sum(np.asarray(l).astype(np.float32) for l in layers)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def base(W, H, tint=0.9):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    k = np.clip(1 - np.hypot((xx - W / 2) / (W * 0.7), (yy - H * 0.55) / (H * 0.7)), 0, 1)
    a = np.zeros((H, W, 3), np.float32); a[...] = BG
    a += (k[..., None] * np.array([6, 18, 14]) * tint)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def doorway(W, H, fx0, fx1, fy0, fy1, k=1.0):
    """the logo: a doorway, the door swung open a little, light in the gap and on the floor, a red dot in the dark of the door"""
    dr = Image.new("RGB", (W, H), (0, 0, 0)); dd = ImageDraw.Draw(dr)
    dd.rectangle([fx0, fy0, fx1, fy1], outline=(60, 96, 80), width=int(7 * k))
    dd.rectangle([fx0 + 7 * k, fy0 + 7 * k, fx1 - 58 * k, fy1], fill=(14, 24, 20))
    dd.rectangle([fx1 - 50 * k, fy0 + 7 * k, fx1 - 7 * k, fy1], fill=PALE)
    gap = glow(dr.filter(ImageFilter.GaussianBlur(1.0 * k)), (6 * k, 22 * k, 60 * k), (0.55, 0.45, 0.4))
    fan = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(fan).polygon([(fx1 - 50 * k, fy1), (fx1 - 7 * k, fy1), (fx1 + 150 * k, fy1 + 130 * k), (fx1 - 220 * k, fy1 + 130 * k)], fill=(96, 150, 122))
    return screen_add(gap, fan.filter(ImageFilter.GaussianBlur(26 * k)), rec_dot(W, H, int(fx0 + 100 * k), int(fy0 + 120 * k), int(12 * k)))


# ---- profile picture 800x800: the crack of light, kept inside the circular crop -----------------------------------------------
S = 800
im = base(S, S)
im = screen_add(im, doorway(S, S, 262, 538, 140, 610))
im = finish(im, grain=0.05, scan=0.12, vig=0.5)
im.save(OUT / "profile_800x800.png")

# ---- banner 2560x1440: all text inside the 1546x423 safe area (x 507-2053, y 508-932) --------------------------------------------
W, H = 2560, 1440
b = base(W, H, tint=1.0)
L = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(L)
name_f = font(LIGHT, 250)
txt = "dreadcast"
tw = d.textlength(txt, font=name_f)
dot_r = 15
x0 = int((W - (tw + 56)) / 2); y0 = 500
d.text((x0, y0), txt, font=name_f, fill=PALE)
dot_cx, dot_cy = x0 + tw + 34, y0 + 266
tag_f = font(MONO, 44)
tag = "original horror stories for when the house goes quiet"
d.text(((W - d.textlength(tag, font=tag_f)) / 2, 842), tag, font=tag_f, fill=GREEN)
text_layer = glow(L, (3, 14, 38), (0.5, 0.45, 0.35))
chrome = Image.new("RGB", (W, H), (0, 0, 0)); cd = ImageDraw.Draw(chrome)
cf = font(MONO, 34)
cd.text((120, 96), "CAM 1", font=cf, fill=GREEN); cd.text((120, 142), "03:07:41", font=cf, fill=GREEN)
cd.text((W - 120 - cd.textlength("REC", font=cf), 96), "REC", font=cf, fill=GREEN)
chrome = glow(chrome, (3, 10), (0.5, 0.4))
im = screen_add(b, text_layer, rec_dot(W, H, int(dot_cx), int(dot_cy), dot_r + 4), chrome, doorway(W, H, 2190, 2450, 330, 960, 1.0))
finish(im, grain=0.05, scan=0.14, vig=0.5, seed=4).save(OUT / "banner_2560x1440.png")

# ---- watermark 150x150, transparent: the crack of light and the dot (shown small and faded in a video corner) ---------------------
W2 = 600
wm = Image.new("RGBA", (W2, W2), (0, 0, 0, 0)); wd = ImageDraw.Draw(wm)
wd.rectangle([150, 60, 450, 540], outline=(235, 250, 240, 255), width=26)       # the doorway
wd.rectangle([330, 86, 424, 514], fill=(235, 250, 240, 255))                    # the light in the gap
wd.ellipse([215, 170, 275, 230], fill=(255, 59, 48, 255))                       # the dot in the dark
wm.resize((150, 150), Image.LANCZOS).save(OUT / "watermark_150x150.png")
print("wrote", [p.name for p in sorted(OUT.iterdir())])
