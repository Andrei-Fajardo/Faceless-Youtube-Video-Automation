"""make_layers.py: split painting.jpg into parallax layers for a 2.5D move (The Kiss: gold background / couple / meadow).

  make_layers.py [--preview]    writes video/assets/layer_back.jpg, layer_fig.png, layer_front.png (+ preview in build/layers_preview.png)

Segmentation is approximate (GrabCut + colour rules) and tuned for The Kiss; edit the numbers in CFG for another painting.
Layers share the painting's pixel size, so they drop into #cam exactly over each other."""
import json, sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "video/assets"
CFG = {
    "fig_rect": [0.255, 0.025, 0.775, 0.80],   # x0,y0,x1,y1 fractions: the couple's outline sits inside this
    "meadow_top": 0.68,                          # meadow can only start below this y fraction
    "work_w": 1400,
    "feather": 3,
}


def main():
    cfg = CFG
    src = cv2.imread(str(A / "painting.jpg"), cv2.IMREAD_COLOR)
    H, W = src.shape[:2]
    s = cfg["work_w"] / W
    small = cv2.resize(src, (cfg["work_w"], int(H * s)), interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    Hh, Ss, Vv = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)

    # meadow: green / blue / purple / pink flowers below meadow_top (hue in OpenCV 0-179: green 35-85, blue 90-130, purple 130-165)
    yy = np.arange(h)[:, None] * np.ones((1, w), int)
    cool = ((Hh >= 35) & (Hh <= 165) & (Ss > 55)) & (yy > cfg["meadow_top"] * h)
    cool = cv2.morphologyEx(cool.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    cool = cv2.morphologyEx(cool, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    # fill: everything below the lowest-top cool pixel in each column belongs to the meadow
    meadow = np.zeros_like(cool)
    for x in range(w):
        col = np.where(cool[:, x] > 0)[0]
        if len(col):
            meadow[col.min():, x] = 255
    meadow = cv2.GaussianBlur(meadow, (0, 0), 2)
    meadow = (meadow > 128).astype(np.uint8) * 255

    # figure: GrabCut inside the rectangle, never inside the meadow
    x0, y0, x1, y1 = cfg["fig_rect"]
    rect = (int(x0 * w), int(y0 * h), int((x1 - x0) * w), int((y1 - y0) * h))
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    mask[rect[1]:rect[1] + rect[3], rect[0]:rect[0] + rect[2]] = cv2.GC_PR_FGD
    # sure foreground: a core ellipse down the middle of the couple
    cv2.ellipse(mask, (int(0.52 * w), int(0.42 * h)), (int(0.12 * w), int(0.30 * h)), 0, 0, 360, cv2.GC_FGD, -1)
    # sure background: the gold wall left and right of the figure
    mask[:, :int(x0 * w) - 5] = cv2.GC_BGD
    mask[:, int(x1 * w) + 5:] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(small, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    fig = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8) * 255
    fig = cv2.morphologyEx(fig, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    fig = cv2.morphologyEx(fig, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    # keep the largest connected blob, fill its holes
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fig)
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fig = (lab == k).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(fig, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fig = np.zeros_like(fig); cv2.drawContours(fig, cnts, -1, 255, -1)
    fig_only = cv2.bitwise_and(fig, cv2.bitwise_not(meadow))      # the meadow sits in front of the figure's lower edge

    # full-size masks
    def up(m, blur):
        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
        return cv2.GaussianBlur(m, (0, 0), blur) if blur else m
    fig_big = up(fig_only, cfg["feather"] * 2)
    meadow_big = up(meadow, cfg["feather"] * 2)
    fg_big = cv2.dilate(up(fig, 0), np.ones((25, 25), np.uint8))  # region to inpaint behind the couple (generous)
    hole = ((cv2.resize(fig, (W, H)) > 0) | (meadow_big > 128)).astype(np.uint8) * 255
    hole = cv2.dilate(hole, np.ones((31, 31), np.uint8))

    # back layer: the painting with the couple and meadow painted out (inpaint at low res, upscale, composite)
    sm_hole = cv2.resize(hole, (w, h), interpolation=cv2.INTER_NEAREST)
    inp = cv2.inpaint(small, sm_hole, 9, cv2.INPAINT_TELEA)
    inp = cv2.GaussianBlur(inp, (0, 0), 3)
    back = src.copy()
    inp_big = cv2.resize(inp, (W, H), interpolation=cv2.INTER_CUBIC)
    hm = cv2.GaussianBlur(hole, (0, 0), 12).astype(np.float32)[..., None] / 255.0
    back = (src.astype(np.float32) * (1 - hm) + inp_big.astype(np.float32) * hm).astype(np.uint8)
    # The back layer is the untouched painting (painting.jpg): inpainting the couple out left visible smears, and the drift is only a few
    # pixels, so the uncovered sliver is just the cut-out's own edge. layer_back.jpg is therefore not used.

    rgba = np.dstack([src, fig_big])
    cv2.imwrite(str(A / "layer_fig.png"), rgba)
    rgba2 = np.dstack([src, meadow_big])
    cv2.imwrite(str(A / "layer_front.png"), rgba2)

    if "--preview" in sys.argv:
        pv = small.copy()
        pv[fig_only > 0] = (0.55 * pv[fig_only > 0] + 0.45 * np.array([0, 0, 255])).astype(np.uint8)
        pv[meadow > 0] = (0.55 * pv[meadow > 0] + 0.45 * np.array([255, 0, 0])).astype(np.uint8)
        out = ROOT / "build/layers_preview.png"; out.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(out), cv2.resize(pv, (900, int(900 * h / w))))
        print("preview:", out)
    print("layers written:", [p.name for p in (A / "layer_back.jpg", A / "layer_fig.png", A / "layer_front.png")])


if __name__ == "__main__":
    main()
