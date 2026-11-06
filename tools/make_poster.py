"""make_poster.py: stitch 9:16 panels into the 2x2 poster the full-bleed camera pans over (video/assets/painting.jpg, 2880x5120).
  make_poster.py P1 P2 P3 P4 [-o video/assets/painting.jpg]
Panels are placed row-major (P1 top-left, P2 top-right, P3 bottom-left, P4 bottom-right) and resized to 1440x2560 each.
build_video.py reads script/video.json "painting": {"width": 2880, "height": 5120} and treats scale 2.0 as exactly one panel."""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PW, PH = 1440, 2560


def main():
    a = sys.argv[1:]
    out = ROOT / "video/assets/painting.jpg"
    if "-o" in a:
        i = a.index("-o")
        out = Path(a[i + 1])
        del a[i:i + 2]
    if len(a) != 4:
        sys.exit(__doc__)
    poster = Image.new("RGB", (PW * 2, PH * 2))
    for n, p in enumerate(a):
        im = Image.open(p).convert("RGB")
        if abs(im.width / im.height - 9 / 16) > 0.01:
            sys.exit(f"{p} is {im.width}x{im.height}, not 9:16")
        poster.paste(im.resize((PW, PH), Image.LANCZOS), ((n % 2) * PW, (n // 2) * PH))
    out.parent.mkdir(parents=True, exist_ok=True)
    poster.save(out, quality=94)
    print(f"wrote {out} {poster.width}x{poster.height}")


main()
