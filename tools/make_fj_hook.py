import pathlib
"""Build the hook panel: fjf_3 (F and J keycaps) with the stray top keys cleared and a thin raised bar drawn on each keycap's front edge."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "assets" / "generated" / "panels" / "fjf_3.png"
OUT = REPO / "assets" / "generated" / "panels" / "fjg_1.png"
im = Image.open(SRC).convert("RGB")
W, H = im.size  # 1152 x 2048
a = np.asarray(im).astype(np.float32)

# 1. clear the top keys: extend the clean surface below them upward
cut, src0, src1 = 735, 760, 840
strip = a[src0:src1].mean(axis=0)                       # per-x colour of the clean surface, shape (W, 3)
strip = np.asarray(Image.fromarray(strip[None].astype(np.uint8)).resize((W, 1)).filter(ImageFilter.GaussianBlur(0))).astype(np.float32)[0]
rng = np.random.default_rng(3)
fill = np.zeros((cut, W, 3), np.float32)
for y in range(cut):
    t = y / cut
    fill[y] = strip * (0.78 + 0.22 * t)                  # slightly darker toward the top edge
fill += rng.normal(0, 1.2, fill.shape)                   # break banding
fillim = Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
a2 = a.copy()
a2[:cut] = np.asarray(fillim).astype(np.float32)
# feather the seam
for y in range(cut, cut + 40):
    w = 1 - (y - cut) / 40
    a2[y] = a2[y] * (1 - w) + np.asarray(fillim)[-1].astype(np.float32) * w
im = Image.fromarray(np.clip(a2, 0, 255).astype(np.uint8))

# 2. raised bars on the front edge of the F and J keycap tops (display coords x1.024 -> original)
S = 1152 / 1125
bars = [(292 * S, 1208 * S), (838 * S, 1208 * S)]        # centre of each bar
L, T = int(172 * S), int(17 * S)
layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
d, ds = ImageDraw.Draw(layer), ImageDraw.Draw(sh)
for cx, cy in bars:
    x0, x1, y0, y1 = cx - L / 2, cx + L / 2, cy - T / 2, cy + T / 2
    ds.rounded_rectangle([x0 + 3, y0 + 9, x1 + 3, y1 + 12], radius=T // 2, fill=(0, 0, 0, 190))
    d.rounded_rectangle([x0, y0, x1, y1], radius=T // 2, fill=(138, 140, 148, 255))             # body
    d.rounded_rectangle([x0 + 2, y0, x1 - 2, y0 + T * 0.45], radius=T // 3, fill=(214, 216, 222, 255))  # lit top edge
    d.rounded_rectangle([x0, y1 - T * 0.28, x1, y1], radius=T // 3, fill=(74, 76, 84, 255))     # shaded underside
sh = sh.filter(ImageFilter.GaussianBlur(6))
im = Image.alpha_composite(im.convert("RGBA"), sh)
im = Image.alpha_composite(im, layer).convert("RGB")
im.save(OUT)
print("wrote", OUT, im.size, "bars at", [(round(x), round(y)) for x, y in bars])
