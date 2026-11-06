"""make_odd_thumbnail.py: the Odd Detail thumbnail (1080x1920, 9:16) with the channel's landmarks.
  make_odd_thumbnail.py <slug> [<slug> ...] | --all     (specs live in finished/thumb_specs.json)
Landmarks: a gold magnifying-glass LENS over the odd detail (the detail is magnified inside it), a red "ODD DETAIL" stamp on the lens,
a huge outlined hook (Impact, white, one yellow keyword line), and the curator as a white-outlined sticker in his video outfit.
Spec per slug: {"panel": path (relative to the project), "detail": [x, y] as fractions of the panel, "zoom": lens magnification,
"hook": ["LINE", "*YELLOW LINE*", ...], "outfit": "navy", "stamp": "ODD DETAIL" (optional), "pose": "wow" (optional)}.
Writes finished/<slug>/thumbnail_1080x1920.jpg (+ .png). A plain frame-0 thumbnail already there is kept as thumbnail_frame0.jpg.
Text sits in the middle 80% of the width and clear of the bottom 12%, so the Shorts shelf and channel grid crops keep it."""
import json, math, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
HOOK_FONT, STAMP_FONT = "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/ariblk.ttf"
GOLD = [(255, 242, 176), (244, 200, 72), (196, 140, 28), (120, 80, 12)]
YELLOW, WHITE, RED = (255, 214, 10), (255, 255, 255), (229, 35, 59)
SS = 4   # supersampling for smooth circle edges


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def grad_v(w, h, stops):
    t = np.linspace(0, 1, h)[:, None]
    n = len(stops) - 1
    seg = np.minimum((t * n).astype(int), n - 1)
    f = t * n - seg
    c = np.array(stops, float)
    col = c[seg[:, 0]] * (1 - f) + c[seg[:, 0] + 1] * f
    return Image.fromarray(np.repeat(col[:, None, :], w, axis=1).astype("uint8"), "RGB")


def circle_mask(d):
    m = Image.new("L", (d * SS, d * SS), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d * SS - 1, d * SS - 1), fill=255)
    return m.resize((d, d), Image.LANCZOS)


def shadow(canvas, layer, pos, off=(0, 14), blur=18, op=0.55):
    a = layer.getchannel("A").point(lambda v: int(v * op))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0)); sh.putalpha(a)
    pad = blur * 3
    big = Image.new("RGBA", (layer.width + 2 * pad, layer.height + 2 * pad), (0, 0, 0, 0)); big.paste(sh, (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(big, (int(pos[0] - pad + off[0]), int(pos[1] - pad + off[1])))


def background(panel):
    bg = cover(panel.convert("RGB"), W, H)
    bg = ImageEnhance.Color(bg).enhance(1.3); bg = ImageEnhance.Contrast(bg).enhance(1.12); bg = ImageEnhance.Brightness(bg).enhance(0.62)
    bg = bg.filter(ImageFilter.GaussianBlur(5))
    a = np.asarray(bg).astype(float)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.52) / (H * 0.62)) ** 2)
    a *= (1 - 0.55 * np.clip(r - 0.35, 0, 1))[..., None]                       # vignette
    top = np.clip(1 - yy / 780, 0, 1) ** 1.4 * 0.5; bot = np.clip((yy - 1250) / 670, 0, 1) ** 1.2 * 0.5
    a *= (1 - top - bot)[..., None]                                            # darker top (hook) and bottom (curator)
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def lens(canvas, panel, detail, zoom, cx, cy, R, handle_dir):
    D = 2 * R
    # sunburst rays + glow behind the lens
    rays = Image.new("RGBA", (W * 2, W * 2), (0, 0, 0, 0)); dr_ = ImageDraw.Draw(rays); n = 18
    for i in range(n):
        a0, a1 = 360 / n * i, 360 / n * i + 360 / n / 2
        dr_.pieslice((0, 0, W * 2 - 1, W * 2 - 1), a0, a1, fill=(255, 236, 160, 46))
    canvas.alpha_composite(rays.crop((W - cx, W - cy, W - cx + W, W - cy + H)).filter(ImageFilter.GaussianBlur(2)), (0, 0))
    g = Image.new("RGBA", (D * 2, D * 2), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse((D // 2, D // 2, D * 3 // 2, D * 3 // 2), fill=(255, 214, 90, 220))
    canvas.alpha_composite(g.filter(ImageFilter.GaussianBlur(60)), (cx - D, cy - D))
    # handle (behind the ring), a gold bar rotated onto handle_dir
    L, T = 300, 86
    bar = Image.new("RGBA", (L * SS, T * SS), (0, 0, 0, 0))
    m = Image.new("L", bar.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, L * SS - 1, T * SS - 1), radius=T * SS // 2, fill=255)
    gb = grad_v(L * SS, T * SS, [(150, 96, 30), (226, 170, 56), (110, 70, 16)]).convert("RGBA"); gb.putalpha(m)
    bar = gb.resize((L, T), Image.LANCZOS)
    ang = -math.degrees(math.atan2(-handle_dir[1], handle_dir[0]))
    bar = bar.rotate(-ang, expand=True, resample=Image.BICUBIC)
    hc = (cx + handle_dir[0] * (R + 28 + L / 2 - 30), cy + handle_dir[1] * (R + 28 + L / 2 - 30))
    pos = (int(hc[0] - bar.width / 2), int(hc[1] - bar.height / 2))
    shadow(canvas, bar, pos, off=(8, 16), blur=14); canvas.alpha_composite(bar, pos)
    # magnified detail inside the lens (cropped from the original panel for sharpness)
    pw, ph = panel.size; k = pw / W
    side = D / zoom * k
    px, py = detail[0] * pw, detail[1] * ph
    px = min(max(px, side / 2), pw - side / 2); py = min(max(py, side / 2), ph - side / 2)
    crop = panel.convert("RGB").crop((px - side / 2, py - side / 2, px + side / 2, py + side / 2)).resize((D, D), Image.LANCZOS)
    crop = ImageEnhance.Contrast(ImageEnhance.Color(crop).enhance(1.22)).enhance(1.1).convert("RGBA"); crop.putalpha(circle_mask(D))
    canvas.alpha_composite(crop, (cx - R, cy - R))
    # glass shine, a soft arc near the upper-left rim
    sh = Image.new("RGBA", (D, D), (0, 0, 0, 0)); ImageDraw.Draw(sh).arc((D * 0.08, D * 0.08, D * 0.92, D * 0.92), 200, 250, fill=(255, 255, 255, 120), width=22)
    sh = sh.filter(ImageFilter.GaussianBlur(5)); sh.putalpha(Image.fromarray(np.minimum(np.asarray(sh.getchannel("A")), np.asarray(circle_mask(D))).astype("uint8")))
    canvas.alpha_composite(sh, (cx - R, cy - R))
    # gold ring
    rw = 34; ds = D + 2 * rw
    ringm = Image.new("L", (ds * SS, ds * SS), 0); dr = ImageDraw.Draw(ringm)
    dr.ellipse((0, 0, ds * SS - 1, ds * SS - 1), fill=255); dr.ellipse((rw * SS, rw * SS, (ds - rw) * SS - 1, (ds - rw) * SS - 1), fill=0)
    ringm = ringm.resize((ds, ds), Image.LANCZOS)
    ring = grad_v(ds, ds, GOLD).convert("RGBA"); ring.putalpha(ringm)
    shadow(canvas, ring, (cx - R - rw, cy - R - rw), off=(0, 16), blur=20, op=0.6)
    canvas.alpha_composite(ring, (cx - R - rw, cy - R - rw))
    edge = Image.new("RGBA", (ds * SS, ds * SS), (0, 0, 0, 0)); de = ImageDraw.Draw(edge)
    de.ellipse((0, 0, ds * SS - 1, ds * SS - 1), outline=(70, 44, 6, 255), width=5)
    de.ellipse((rw * SS, rw * SS, (ds - rw) * SS - 1, (ds - rw) * SS - 1), outline=(70, 44, 6, 255), width=5)
    canvas.alpha_composite(edge.resize((ds, ds), Image.LANCZOS), (cx - R - rw, cy - R - rw))


def stamp(canvas, text, center, angle=-9):
    f = ImageFont.truetype(STAMP_FONT, 66)
    tw = f.getlength(text); w, h = int(tw + 70), 112
    lay = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((2, 2, w * 2 - 3, h * 2 - 3), radius=26, fill=RED + (255,), outline=WHITE + (255,), width=8)
    d.rounded_rectangle((20, 20, w * 2 - 21, h * 2 - 21), radius=16, outline=(255, 255, 255, 150), width=3)
    lay = lay.resize((w, h), Image.LANCZOS); d = ImageDraw.Draw(lay)
    d.text((w / 2, h / 2 + 2), text, font=f, fill=WHITE, anchor="mm", stroke_width=2, stroke_fill=(120, 10, 25))
    lay = lay.rotate(angle, expand=True, resample=Image.BICUBIC)
    pos = (int(center[0] - lay.width / 2), int(center[1] - lay.height / 2))
    shadow(canvas, lay, pos, off=(6, 12), blur=10, op=0.6); canvas.alpha_composite(lay, pos)


def hook(canvas, lines, top):
    size = 250
    while size > 90:
        f = ImageFont.truetype(HOOK_FONT, size)
        if max(f.getlength(l.strip("*")) for l in lines) + 24 <= W * 0.86: break
        size -= 4
    size = min(size, 235 if len(lines) <= 2 else 178)
    f = ImageFont.truetype(HOOK_FONT, size); lh = int(size * 1.02)
    for i, raw in enumerate(lines):
        col = YELLOW if raw.startswith("*") else WHITE; s = raw.strip("*"); y = top + i * lh
        sh = Image.new("RGBA", (W, lh + 80), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((W / 2, 40), s, font=f, fill=(0, 0, 0, 230), anchor="ma", stroke_width=22, stroke_fill=(0, 0, 0, 230))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (0, y + 10))
        lay = Image.new("RGBA", (W, lh + 80), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((W / 2, 40), s, font=f, fill=col, anchor="ma", stroke_width=14, stroke_fill=(10, 8, 6))
        canvas.alpha_composite(lay, (0, y))
    return top + len(lines) * lh


def curator(canvas, outfit, pose, cx, height):
    sp = Image.open(ROOT / "video/assets/mascot" / outfit / f"{pose}.png").convert("RGBA")
    sp = sp.crop(sp.getchannel("A").getbbox())
    sp = sp.resize((round(sp.width * height / sp.height), height), Image.LANCZOS)
    a = sp.getchannel("A").filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(1.5))
    outline = Image.new("RGBA", sp.size, (255, 255, 255, 255)); outline.putalpha(a.point(lambda v: 255 if v > 90 else 0))
    pad = 12; lay = Image.new("RGBA", (sp.width + 2 * pad, sp.height + pad), (0, 0, 0, 0))
    lay.alpha_composite(outline, (pad - 0, pad - 4)); lay.alpha_composite(sp, (pad, pad))
    pos = (int(cx - lay.width / 2), H - lay.height + 6)
    shadow(canvas, lay, pos, off=(0, -4), blur=16, op=0.5); canvas.alpha_composite(lay, pos)


def make(slug, spec):
    panel = Image.open(ROOT / spec["panel"])
    canvas = background(panel)
    cx, cy, R = 540, 1075, 296
    lens(canvas, panel, spec["detail"], spec.get("zoom", 1.6), cx, cy, R, handle_dir=(-0.72, 0.69))
    hook(canvas, spec["hook"], 118)
    stamp(canvas, spec.get("stamp", "ODD DETAIL"), (cx + 225, cy - R + 8 + (28 if len(spec["hook"]) >= 3 else 0)))
    curator(canvas, spec["outfit"], spec.get("pose", "wow"), 790, 640)
    out = ROOT / "finished" / slug; out.mkdir(parents=True, exist_ok=True)
    jpg = out / "thumbnail_1080x1920.jpg"
    if jpg.exists() and not (out / "thumbnail_frame0.jpg").exists(): shutil.copy(jpg, out / "thumbnail_frame0.jpg")
    img = canvas.convert("RGB"); img.save(out / "thumbnail_1080x1920.png")
    q = 94
    while True:
        img.save(jpg, quality=q, optimize=True)
        if jpg.stat().st_size < 1_900_000 or q <= 70: break
        q -= 4
    print(f"{slug}: {jpg} ({jpg.stat().st_size // 1024} KB, q{q})")


if __name__ == "__main__":
    specs = json.loads((ROOT / "finished/thumb_specs.json").read_text(encoding="utf-8"))
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    for s in (specs if args == ["--all"] else args):
        if s not in specs: sys.exit(f"no spec for {s} in finished/thumb_specs.json")
        make(s, specs[s])
