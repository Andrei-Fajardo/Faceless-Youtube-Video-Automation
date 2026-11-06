"""prep_visemes.py: build talking sprites for lip-sync from Higgsfield mouth variants.
  prep_visemes.py OUTFIT [OUTFIT ...]
Needs avatar/raw/mouth/<outfit>_{closed,ah,aa,oo,fv,ee,blink}.png (edits of <outfit>_explain.png, same pose) and avatar/raw/<outfit>_idle/_explain.png.
Writes video/assets/mascot/<outfit>/talk.png (the closed-mouth base on the 900x1100 sprite canvas, same transform as the explain pose) and
v_<name>.png (a full-canvas RGBA with only a feathered mouth patch, or eye patch for 'blink'), so the HyperFrames build can stack them on talk.png
and swap them with the speech. The head never moves: only the patch changes."""
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "avatar/raw"
OUT = ROOT / "video/assets/mascot"
CW, CH, AX = 900, 1100, 450
VISEMES = ["ah", "ah2", "ah3", "eh", "o", "o2", "oo", "oo2", "fv", "ee", "teeth", "mid", "sh"]
MOUTH_BOX = (310, 245, 495, 415)    # x0, y0, x1, y1 in the 896x1120 source (moustache, mouth, chin)
EYE_BOX = (310, 165, 525, 262)      # both eyes and lids
FEATHER = 12


def bbox_alpha(im):
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 40)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def torso(c):
    a = np.asarray(c)[..., 3]; h = a.shape[0]
    ys, xs = np.where(a[int(h * 0.92):] > 40)
    return (xs.min() + xs.max()) / 2, float(xs.max() - xs.min())


def transform(outfit):
    """scale, bbox and paste position used by prep_mascot.bust for this outfit's explain pose"""
    idle = Image.open(RAW / f"{outfit}_idle.png").convert("RGBA"); bi = bbox_alpha(idle); ci = idle.crop(bi)
    _, w0 = torso(ci); k0 = min(CW / ci.width, CH / ci.height)
    ex = Image.open(RAW / f"{outfit}_explain.png").convert("RGBA"); be = bbox_alpha(ex); ce = ex.crop(be)
    cx, w = torso(ce)
    s = k0 * min(1.12, max(0.88, w0 / max(w, 1.0)))
    s = min(s, CH / ce.height)
    return s, be, (int(round(AX - cx * s)), CH - int(ce.height * s))


def to_canvas(im, s, be, pos):
    c = im.crop(be).resize((max(1, int(im.crop(be).width * s)), max(1, int(im.crop(be).height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    x, y = pos
    if x < 0: c = c.crop((-x, 0, c.width, c.height)); x = 0
    canvas.alpha_composite(c, (x, y))
    return canvas


def box_mask(shape, box, feather):
    m = np.zeros(shape, np.float32)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = 1.0
    k = feather * 2 + 1
    return cv2.GaussianBlur(m, (k, k), feather / 2.0)


def align(base, var):
    g = lambda im: cv2.cvtColor(np.asarray(im)[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    reg = (slice(20, 200), slice(300, 700))
    (dx, dy), _ = cv2.phaseCorrelate(g(base)[reg], g(var)[reg])
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    arr = np.asarray(var).astype(np.float32)
    out = cv2.warpAffine(arr, M, (arr.shape[1], arr.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def main():
    for o in sys.argv[1:]:
        d = OUT / o; d.mkdir(parents=True, exist_ok=True)
        s, be, pos = transform(o)
        base = Image.open(RAW / f"mouth/{o}_closed.png").convert("RGBA")
        to_canvas(base, s, be, pos).save(d / "talk.png")
        for name in VISEMES + ["blink"]:
            var = align(base, Image.open(RAW / f"mouth/{o}_{name}.png").convert("RGBA"))
            arr = np.asarray(var).astype(np.float32)
            box = EYE_BOX if name == "blink" else MOUTH_BOX
            m = box_mask(arr.shape[:2], box, FEATHER)
            arr[..., 3] = arr[..., 3] * m
            to_canvas(Image.fromarray(arr.astype(np.uint8), "RGBA"), s, be, pos).save(d / f"v_{name}.png")
        print(o, "ok: talk.png +", len(VISEMES) + 1, "overlays")


if __name__ == "__main__":
    main()
