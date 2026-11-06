"""Render the thumbnail of a video to finished/<folder>/<slug>/thumbnail_<W>x<H>.png (and .jpg under 2 MB, YouTube's limit).
The size follows the thumbnail project: 1080x1920 for a Short (9:16), 1920x1080 for long-form (16:9).
  thumb_render.py <slug> [--folder what-if|odd-detail-js]
"""
import argparse, json, os, pathlib, subprocess, sys
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent; S = ROOT / "aitrends-2d-studio"
ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--folder", default="what-if"); a = ap.parse_args()
name = f"{a.slug}-thumb"; env = dict(os.environ, PYTHONIOENCODING="utf-8", CHROMIUM_PATH=os.environ.get("CHROMIUM_PATH", ""))
env["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + env["PATH"]
subprocess.run(["node", "render.mjs", "--project", f"projects/{name}", "--stills", "1.5"], cwd=S, env=env, check=True)
src = next((S / "projects" / name / "build" / "stills").glob("1.5s_*.png")); im = Image.open(src).convert("RGB")
want = (1080, 1920) if json.loads((S / "projects" / name / "config.json").read_text()).get("aspect") == "9:16" else (1920, 1080)
if im.size != want: sys.exit(f"STOP: thumbnail is {im.size}, expected {want[0]}x{want[1]}")
tag = f"{want[0]}x{want[1]}"; out = ROOT / "finished" / a.folder / a.slug; out.mkdir(parents=True, exist_ok=True)
im.save(out / f"thumbnail_{tag}.png"); q = 94
while True:
    im.save(out / f"thumbnail_{tag}.jpg", quality=q, optimize=True)
    if (out / f"thumbnail_{tag}.jpg").stat().st_size < 1_900_000 or q <= 70: break
    q -= 4
print("thumbnail:", out / f"thumbnail_{tag}.png", f"({(out / f'thumbnail_{tag}.png').stat().st_size // 1024} KB)", "| jpg", f"{(out / f'thumbnail_{tag}.jpg').stat().st_size // 1024} KB at quality {q}")
