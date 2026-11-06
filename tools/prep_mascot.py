"""prep_mascot.py: align the mascot sprites so poses swap without the character jumping.
  prep_mascot.py          legacy full-body set (hero_b + pose_*), feet anchored -> video/assets/mascot/<pose>.png
  prep_mascot.py bust     the five outfit sets (avatar/raw/<outfit>_<pose>.png, waist-up) -> video/assets/mascot/<outfit>/<pose>.png
Bust mode: every pose goes on a 900x1100 canvas with the cut-off edge at the canvas bottom, the torso centred on the same x and
scaled to the idle pose's torso width, so poses swap without the body jumping."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "avatar/raw"
OUT = ROOT / "video/assets/mascot"
POSES = {"idle": "hero_b", "point": "pose_point", "lean": "pose_lean", "wow": "pose_wow", "explain": "pose_explain", "laugh": "pose_laugh"}
OUTFITS = ["tweed", "velvet", "navy", "tailcoat", "emerald"]
BUST_POSES = ["idle", "point", "lean", "wow", "explain", "laugh", "think", "shrug", "proud", "worried"]
CW, CH, AX, AY = 900, 1100, 450, 1070   # canvas and the feet anchor


def full_body():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, f in POSES.items():
        im = Image.open(RAW / f"{f}.png").convert("RGBA")
        a = np.asarray(im)[..., 3]
        ys, xs = np.where(a > 40)
        top, bot = ys.min(), ys.max()
        band = ys > bot - max(8, int(0.06 * (bot - top)))
        fx = xs[band].mean()
        canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        canvas.alpha_composite(im, (int(round(AX - fx)), int(round(AY - bot))))
        canvas.save(OUT / f"{name}.png")
        print(name, "feet x", round(float(fx)), "height", int(bot - top))


def torso(im):
    """(centre x, width) of the opaque pixels in the bottom 8% of the sprite, plus the bbox-cropped image."""
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 40)
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    a = np.asarray(im)[..., 3]
    h = a.shape[0]
    ys, xs = np.where(a[int(h * 0.92):] > 40)
    return (xs.min() + xs.max()) / 2, float(xs.max() - xs.min()), im


def bust():
    for o in OUTFITS:
        d = OUT / o
        d.mkdir(parents=True, exist_ok=True)
        base = Image.open(RAW / f"{o}_idle.png").convert("RGBA")
        _, w0, b0 = torso(base)
        k0 = min(CW / b0.width, CH / b0.height)   # idle fills the canvas
        for p in BUST_POSES:
            im = Image.open(RAW / f"{o}_{p}.png").convert("RGBA")
            cx, w, c = torso(im)
            s = k0 * min(1.12, max(0.88, w0 / max(w, 1.0))) if p != "idle" else k0
            s = min(s, CH / c.height)   # never clip the head
            c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.LANCZOS)
            canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
            canvas.alpha_composite(c, (int(round(AX - cx * s)), CH - c.height)) if 0 <= AX - cx * s else canvas.alpha_composite(c.crop((int(round(cx * s - AX)), 0, c.width, c.height)), (0, CH - c.height))
            canvas.save(d / f"{p}.png")
        print(o, "ok")


if __name__ == "__main__":
    bust() if len(sys.argv) > 1 and sys.argv[1] == "bust" else full_body()
