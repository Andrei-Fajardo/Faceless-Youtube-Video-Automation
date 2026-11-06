"""Create the thumbnail project for a video: 1080x1920 (9:16) for Shorts, 1920x1080 (16:9) for long-form.
  thumb_setup.py <slug> --title "<video title>" [--folder what-if|odd-detail-js] [--aspect auto|9:16|16:9] [--force]
--aspect auto (default) copies the aspect of the video's own project (projects/<slug>/config.json), so a 9:16 Short gets a 9:16 thumbnail.
A 16:9 thumbnail on a Short is centre-cropped by YouTube and loses the sides of the text, so Shorts must use 9:16.
--force renames an existing projects/<slug>-thumb to <slug>-thumb-old<N> (kept, not deleted) and starts a fresh one.
Creates aitrends-2d-studio/projects/<slug>-thumb (1080p, style duskhd, one 3-second shot `t01`, no captions or fades) from the template scenes and
writes a starter shots/t01.js with a working layout for you to customise.
Then render with:  python tools/thumb_render.py <slug> [--folder what-if]
"""
import argparse, json, os, pathlib, shutil, subprocess, sys
FFENV = dict(os.environ, PYTHONIOENCODING='utf-8', PATH=r'C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;' + os.environ['PATH'])   # ffmpeg and ffprobe are not on the default PATH
ROOT = pathlib.Path(__file__).resolve().parent.parent; S = ROOT / "aitrends-2d-studio"
ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--title", required=True); ap.add_argument("--folder", default="what-if")
ap.add_argument("--aspect", default="auto", choices=["auto", "9:16", "16:9"]); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
name = f"{a.slug}-thumb"; proj = S / "projects" / name
if a.aspect == "auto":
    vcfg = S / "projects" / a.slug / "config.json"; a.aspect = json.loads(vcfg.read_text()).get("aspect", "16:9") if vcfg.exists() else "16:9"
if proj.exists():
    if not a.force: sys.exit(f"STOP: projects/{name} exists; edit its shots/t01.js and re-render with thumb_render.py (or pass --force to start over; the old one is kept)")
    n = 1
    while (S / "projects" / f"{name}-old{n}").exists(): n += 1
    proj.rename(S / "projects" / f"{name}-old{n}"); print(f"kept the old thumbnail project as projects/{name}-old{n}")
vertical = a.aspect == "9:16"
voice = next(iter((ROOT / "finished").glob(f"*/{a.slug}/voice.wav")), None) or next(iter((ROOT / "finished").glob("*/*/voice.wav")))
subprocess.run([sys.executable, "tools/new_project.py", "--name", name, "--voice", str(voice), "--aspect", a.aspect, "--resolution", "1080p", "--title", a.title + " thumbnail"], cwd=S, check=True, env=FFENV)
shutil.copytree(S / "template" / "scenes", proj / "scenes", dirs_exist_ok=True)
cfg = json.loads((proj / "config.json").read_text()); cfg.update({"style": "duskhd", "resolution": "1080p", "captions": False, "bars": "none", "fadeIn": 0, "fadeOut": 0, "duration": 3, "music": {"enabled": False}, "sfx": {"enabled": False}}); (proj / "config.json").write_text(json.dumps(cfg, indent=1))
(proj / "story" / "shots.json").write_text(json.dumps({"title": "thumbnail", "duration": 3, "shots": [{"id": "t01", "start": 0, "end": 3, "line": "", "scene": "thumbnail", "set": "void", "bars": "none", "in": {"type": "cut", "dur": 0.1}, "vignette": True, "captions": False}], "music": [], "sfx": []}, indent=1))
LAND = "// t01.js — the 1920x1080 thumbnail (long-form). Rules: three to five words of text at most, huge and high-contrast; one focal subject; a face or a striking object;\n// keep the bottom-right 240x80 corner empty (YouTube puts the duration there); key content inside the centre 1600x900.\nimport { E, S, registerShot, backdrop, glow, alpha, rr, circle, seg, text, FONTS, rng } from '/engine/core.js';\nimport * as FX from '/engine/fx2d.js';\nregisterShot('t01', { draw(g, t, info) {\n  const ui = S().ui; backdrop(g, ['#070b1e', '#101a3e', '#1d2c5e']); glow(g, 1380, 540, 700, '#ffb070', 0.25);\n  text(g, 'BIG IDEA', 70, 330, { size: 170, color: '#ffffff', font: FONTS.ui, weight: 900, align: 'left', spacing: 4, stroke: 14, strokeColor: '#0a0818' });\n  text(g, 'IN FEW WORDS', 70, 520, { size: 130, color: ui.gold, font: FONTS.ui, weight: 900, align: 'left', spacing: 4, stroke: 12, strokeColor: '#0a0818', glow: 30, glowColor: 'rgba(255,170,60,.7)' });\n  circle(g, 1400, 540, 300, '#16224a');            // replace with the focal subject\n} });\n"
PORT = "// t01.js — the 1080x1920 (9:16) thumbnail for a Short. It is shown full-frame in the Shorts feed and on the video page, so design for a phone.\n// Rules: three to five words of text at most, huge and high-contrast, stacked on 2-3 lines; one focal subject; a face or a striking object.\n// SAFE ZONE: keep every word and the subject inside x 90-990 and y 150-1380. The bottom 540 px (title, channel, buttons) and the right edge below y 1000 are covered by Shorts UI: background only there.\nimport { E, S, registerShot, backdrop, glow, alpha, rr, circle, seg, text, FONTS, rng } from '/engine/core.js';\nimport * as FX from '/engine/fx2d.js';\nregisterShot('t01', { draw(g, t, info) {\n  const ui = S().ui; backdrop(g, ['#070b1e', '#101a3e', '#1d2c5e']); glow(g, 540, 560, 650, '#ffb070', 0.25);\n  circle(g, 540, 520, 300, '#16224a');            // replace with the focal subject (centre, y 200-850)\n  text(g, 'BIG IDEA', 540, 1010, { size: 230, color: '#ffffff', font: FONTS.ui, weight: 900, spacing: 3, stroke: 18, strokeColor: '#0a0818' });\n  text(g, 'FEW WORDS', 540, 1240, { size: 190, color: ui.gold, font: FONTS.ui, weight: 900, spacing: 3, stroke: 16, strokeColor: '#0a0818', glow: 30, glowColor: 'rgba(255,170,60,.7)' });\n} });\n"
(proj / "scenes" / "shots" / "t01.js").write_text(PORT if vertical else LAND, encoding="utf-8")
print(f"thumbnail project ready ({a.aspect}, {'1080x1920' if vertical else '1920x1080'}): aitrends-2d-studio/projects/{name}; edit scenes/shots/t01.js, then: python tools/thumb_render.py {a.slug} --folder {a.folder}")
