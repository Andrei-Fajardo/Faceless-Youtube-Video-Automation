"""Start a new painting run. Archives the current run into runs/<old-slug>/ (moved, nothing deleted), recreates empty working dirs, writes run.json.
Usage: start_run.py <new-slug> "<Painting title>"."""
import json, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) < 3:
    sys.exit('usage: start_run.py <slug> "<title>"')
slug, title = sys.argv[1], sys.argv[2]
rp = ROOT / "run.json"
old = json.loads(rp.read_text()) if rp.exists() else None
MOVE = ["script", "build", "audio", "out", "assets", "video/index.html", "video/assets/painting.jpg", "video/assets/bg.jpg", "video/assets/mix.wav"]
if old and old["slug"] == slug:
    sys.exit(f"run '{slug}' is already the current run")
if old:
    dst = ROOT / "runs" / old["slug"]
    if dst.exists():
        sys.exit(f"runs/{old['slug']} already exists; refusing to overwrite")
    for rel in MOVE:
        src = ROOT / rel
        if src.exists():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst / rel))
    lib = dst / "assets" / "sfx_lib"   # shared sound library, not part of a run: keep it in place (copy back; the archive keeps its own copy)
    if lib.exists() and not (ROOT / "assets" / "sfx_lib").exists():
        (ROOT / "assets").mkdir(parents=True, exist_ok=True)
        shutil.copytree(lib, ROOT / "assets" / "sfx_lib")
    print(f"archived previous run -> runs/{old['slug']}")
for rel in ["script", "build/qa/frames", "audio/voice", "audio/sfx", "audio/mix", "audio/eleven-labs", "out/review", "assets/paintings", "video/assets"]:
    (ROOT / rel).mkdir(parents=True, exist_ok=True)
rp.write_text(json.dumps({"slug": slug, "title": title, "started": datetime.now().isoformat(timespec="seconds")}, indent=1))
print(f"new run: {slug} ({title})")
