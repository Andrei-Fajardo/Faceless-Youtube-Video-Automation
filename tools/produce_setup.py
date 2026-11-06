"""Create a studio project for one video from the reusable template.
  produce_setup.py <slug> --aspect 16:9|9:16 --kind long|short --voice <wav> --script <script.txt> --title "<title>"
Copies aitrends-2d-studio/template/scenes (props, sets, shot helpers, cast) into projects/<slug>/scenes, creates the project with new_project.py,
sets the HD style and resolution (long: 1440p, Shorts: 1080p), writes the plain narration to input/script.txt. Run from anywhere.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys
FFENV = dict(os.environ, PYTHONIOENCODING='utf-8', PATH=r'C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;' + os.environ['PATH'])   # ffmpeg and ffprobe are not on the default PATH
ROOT = pathlib.Path(__file__).resolve().parent.parent; S = ROOT / "aitrends-2d-studio"
ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--aspect", required=True); ap.add_argument("--kind", required=True, choices=["long", "short"])
ap.add_argument("--voice", required=True); ap.add_argument("--script", required=True); ap.add_argument("--title", required=True); a = ap.parse_args()
proj = S / "projects" / a.slug
if proj.exists(): sys.exit(f"STOP: projects/{a.slug} already exists; choose another slug or delete it deliberately")
res = "1440p" if a.kind == "long" else "1080p"
cmd = [sys.executable, "tools/new_project.py", "--name", a.slug, "--voice", str(pathlib.Path(a.voice).resolve()), "--aspect", a.aspect, "--resolution", res, "--title", a.title] + (["--captions"] if a.kind == "short" else [])
subprocess.run(cmd, cwd=S, check=True, env=FFENV)
shutil.copytree(S / "template" / "scenes", proj / "scenes", dirs_exist_ok=True)
text = pathlib.Path(a.script).read_text(encoding="utf-8"); text = text.split("SCRIPT:", 1)[1].strip() if "SCRIPT:" in text else text.strip()
(proj / "input" / "script.txt").write_text(text.replace("’", "'"), encoding="utf-8")
cfg = json.loads((proj / "config.json").read_text()); cfg["style"] = "duskhd"; cfg["resolution"] = res; cfg["captions"] = a.kind == "short"
if a.kind == "long": cfg.update({"bars": "wide", "fadeIn": 0.6, "fadeOut": 1.0})
(proj / "config.json").write_text(json.dumps(cfg, indent=1))
print(f"project ready: aitrends-2d-studio/projects/{a.slug} ({a.aspect}, {res}, style duskhd). Next: whisper align, write scenes/shots/*.js, story/shots.json")
