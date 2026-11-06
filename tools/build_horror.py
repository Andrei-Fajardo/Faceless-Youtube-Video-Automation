"""Horror Short builder: video/index.html from script/video.json ("horror" block) + build/timeline.json + build/captions.json.
Full-bleed photoreal panels with hard cuts and slow push-ins, film grain, a dying-bulb flicker, a held-breath dip before the reveal,
word-by-word captions (script spelling, whisper timing). No mascot, no hook text. The film ends on a cut back to panel 1 so it loops.
Writes video/index.html, video/assets/h_*.jpg, video/assets/grain.png and build/horror_events.json (read by tools/horror_sound.py)."""
import difflib, html, json, random, re, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from textnorm import _word_tokens, tokens_with_owner

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
H = cfg["horror"]
tl = json.loads((ROOT / "build/timeline.json").read_text())
cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
L = {l["id"]: l for l in tl["lines"]}
TOTAL = round(tl["total_duration"], 3)
f = lambda x: f"{x:.3f}"
NL = "\n"
VID = ROOT / "video/assets"; VID.mkdir(parents=True, exist_ok=True)


def wtime(line, tok):
    for w in cap:
        if w["line"] == line and tok.lower() in _word_tokens(w["word"]): return w
    raise SystemExit(f"word '{tok}' not found in line {line}")


def at(spec):
    """'S3' = start of that line; 'S9:seventeen' = start of that spoken word; 'END' = the loop-back cut; optional +/- offset"""
    m = re.fullmatch(r"(\w+)(?::(\w+))?([+-][\d.]+)?", spec)
    if spec == "END": return TOTAL - H.get("loop_back", 0.5)
    line, word, off = m.group(1), m.group(2), float(m.group(3) or 0)
    return (wtime(line, word)["start"] if word else L[line]["start"]) + off


# ---- panels -> jpg (the png sources stay in assets/generated/panels) -------------------------------------------------------
src_dir = ROOT / "assets/generated/panels"
for p in H["panels"]:
    s = src_dir / f"{p['img']}.png"
    if not s.exists(): raise SystemExit(f"missing panel {s}")
    d = VID / f"h_{p['img']}.jpg"
    if not d.exists() or d.stat().st_mtime < s.stat().st_mtime:
        Image.open(s).convert("RGB").resize((1080, 1920), Image.LANCZOS).save(d, quality=92)

# ---- film grain tile (540x960 noise, drawn at 2x), jittered every few frames -------------------------------------------------
rng = np.random.default_rng(3)
g = rng.normal(128, 46, (960, 540)).clip(0, 255).astype(np.uint8)
a = np.full((960, 540), 255, np.uint8)
Image.fromarray(np.dstack([g, g, g, a])).save(VID / "grain.png")

# ---- captions: script words anchored to whisper words through shared spoken tokens (same method as build_video.py) -----------
clean = [w for w in cap if not (w["end"] - w["start"] < 0.001 and w["start"] > 0)]   # whisper's zero-length hallucinations in silent gaps
caps = []
for s in script:
    units = s["text"].split()
    ut, uo = tokens_with_owner(units)
    ws = [w for w in clean if w["line"] == s["id"]]
    wt, wo = tokens_with_owner([w["word"] for w in ws])
    a0, b0 = L[s["id"]]["start"], L[s["id"]]["end"]
    matched = {}
    for blk in difflib.SequenceMatcher(None, ut, wt, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            u, w = uo[blk.a + k], wo[blk.b + k]
            if u not in matched.setdefault(w, []): matched[w].append(u)
    pos, end = [None] * len(units), [None] * len(units)
    for wi, us in matched.items():
        us = sorted(set(us)); w0, w1 = ws[wi]["start"], ws[wi]["end"]
        for k, u in enumerate(us):
            if pos[u] is None: pos[u], end[u] = w0 + (w1 - w0) * k / len(us), w0 + (w1 - w0) * (k + 1) / len(us)
    prev_t, i = a0, 0
    while i < len(units):
        if pos[i] is not None:
            prev_t = end[i]; i += 1; continue
        j = i
        while j < len(units) and pos[j] is None: j += 1
        nxt_t = pos[j] if j < len(units) else b0
        wts = [len(x) + 1 for x in units[i:j]]; tot = sum(wts); t = prev_t
        for k, wgt in enumerate(wts):
            d = max(0.0, (nxt_t - prev_t)) * wgt / tot; pos[i + k], end[i + k] = t, t + d; t += d
        prev_t, i = nxt_t, j
    for k, x in enumerate(units): caps.append((x, pos[k], end[k], s["id"]))
groups, cur = [], []
for c in caps:
    if cur and (c[3] != cur[-1][3] or len(cur) >= 4 or sum(len(x[0]) + 1 for x in cur) + len(c[0]) > 22):
        groups.append(cur); cur = []
    cur.append(c)
if cur: groups.append(cur)
emph = {w.lower() for w in H.get("emphasis", [])}
caps_html, caps_js = [], []
for gi, gr in enumerate(groups):
    s0 = max(0.1, gr[0][1] - 0.04)
    nxt = groups[gi + 1][0][1] - 0.04 if gi + 1 < len(groups) and groups[gi + 1][0][3] == gr[0][3] else None
    e0 = gr[-1][2] + 0.55
    if gi == len(groups) - 1: e0 = TOTAL   # the last word stays until the loop-back cut
    if nxt is not None: e0 = min(e0, nxt - 0.02)
    e0 = min(e0, TOTAL - H.get("loop_back", 0.5) - 0.05)
    spans = " ".join(f'<span id="c{gi}w{k}" class="cw{" em" if re.sub(r"[^a-z0-9]", "", w[0].lower()) in emph else ""}">{html.escape(w[0])}</span>' for k, w in enumerate(gr))
    caps_html.append(f'<div id="cg{gi}" class="clip cg" data-start="{f(s0)}" data-duration="{f(e0 - s0)}"><div class="cgi">{spans}</div></div>')
    js = [f'tl.set("#cg{gi}", {{opacity: 1}}, {f(s0)});']
    for k, w in enumerate(gr):
        js.append(f'tl.set("#c{gi}w{k}", {{opacity: 1}}, {f(w[1])});')
        if k + 1 < len(gr): js.append(f'tl.set("#c{gi}w{k}", {{opacity: 0.55}}, {f(gr[k + 1][1])});')
    js.append(f'tl.to("#cg{gi}", {{opacity: 0, duration: 0.15, ease: "power2.in"}}, {f(e0 - 0.15)});')
    js.append(f'tl.set("#cg{gi}", {{opacity: 0}}, {f(e0)});')
    caps_js.append(NL.join(js))

# ---- panels: hard cuts, slow push-in with a small safe drift --------------------------------------------------------------
LB = H.get("loop_back", 0.5)
P = H["panels"]
starts = [at(p["from"]) for p in P]
starts[0] = 0.0
ends = starts[1:] + [TOTAL - LB]
img_html, cam_js, EV = [], [], {"cuts": [], "flickers": [], "total": TOTAL}
for n, (p, s0, e0) in enumerate(zip(P, starts, ends)):
    img_html.append(f'<img id="p{n}" class="clip pimg" src="assets/h_{p["img"]}.jpg" alt="" data-start="{f(s0)}" data-duration="{f(e0 - s0)}" />')
    sa, sb = p["s0"], p["s1"]; mx, my = (sb - sa) / 2 * 1080 * 0.9, (sb - sa) / 2 * 1920 * 0.9
    x1, y1 = p.get("dx", 0) * mx, p.get("dy", 0) * my
    cam_js.append(f'gsap.set("#p{n}", {{scale: {sa}, x: 0, y: 0, transformOrigin: "50% 50%"}});')
    if p.get("lunge"):   # the reveal: a fast push-in on the cut, then a slow creep
        cam_js.append(f'tl.fromTo("#p{n}", {{scale: {sa}, x: 0, y: 0}}, {{scale: {p["lunge"]}, x: {x1 * 0.5:.1f}, y: {y1 * 0.5:.1f}, duration: 0.5, ease: "power3.out", immediateRender: false}}, {f(s0)});')
        cam_js.append(f'tl.to("#p{n}", {{scale: {sb}, x: {x1:.1f}, y: {y1:.1f}, duration: {f(e0 - s0 - 0.5)}, ease: "none"}}, {f(s0 + 0.5)});')
    else:
        cam_js.append(f'tl.fromTo("#p{n}", {{scale: {sa}, x: 0, y: 0}}, {{scale: {sb}, x: {x1:.1f}, y: {y1:.1f}, duration: {f(e0 - s0)}, ease: "none", immediateRender: false}}, {f(s0)});')
    EV["cuts"].append({"t": round(s0, 3), "img": p["img"]})
# loop-back: panel 1 again, exactly as at frame 0
p0 = P[0]
img_html.append(f'<img id="pend" class="clip pimg" src="assets/h_{p0["img"]}.jpg" alt="" data-start="{f(TOTAL - LB)}" data-duration="{f(LB)}" />')
cam_js.append(f'gsap.set("#pend", {{scale: {p0["s0"]}, x: 0, y: 0, transformOrigin: "50% 50%"}});')
EV["cuts"].append({"t": round(TOTAL - LB, 3), "img": p0["img"], "loop_back": True})

# ---- flicker overlay (black layer): bulb dips, held-breath dip, reveal stutter -----------------------------------------------
fl = []
def dip(t, depth, d=0.06):   # a quick dip to `depth` black and back
    fl.append(f'tl.set("#flick", {{opacity: {depth}}}, {f(t)});'); fl.append(f'tl.set("#flick", {{opacity: 0}}, {f(t + d)});'); EV["flickers"].append(round(t, 3))
for spec, pattern in H.get("flicker_at", {}).items():
    t0 = at(spec)
    for dt, depth, d in pattern: dip(t0 + dt, depth, d)
rr = random.Random(5)
for t in np.arange(3.0, at(H["breath"]["from"]) - 1.0, 2.7):   # faint random bulb flutter before the end
    dip(float(t + rr.uniform(0, 1.2)), round(rr.uniform(0.12, 0.3), 2), 0.05)
b = H["breath"]   # held breath: the picture sinks toward black during the voice's pause, then the reveal stutters in
tb0, tb1 = at(b["from"]), at(b["reveal"])
fl.append(f'tl.fromTo("#flick", {{opacity: 0}}, {{opacity: {b["depth"]}, duration: {f(b.get("fade", 0.7))}, ease: "sine.in", immediateRender: false}}, {f(tb0)});')
for dt, depth, d in b["stutter"]:
    fl.append(f'tl.set("#flick", {{opacity: {depth}}}, {f(tb1 + dt)});')
fl.append(f'tl.set("#flick", {{opacity: 0}}, {f(tb1 + b["stutter"][-1][0] + b["stutter"][-1][2])});')
EV["breath"] = [round(tb0, 3), round(tb1, 3)]
fl.append(f'tl.set("#flick", {{opacity: 0}}, {f(TOTAL - LB)});')

# grain jitter (every 2 frames); the first and last frame use the same offset so frame 0 == last frame
gr_js = []
rg = random.Random(9)
t = 0.0
while t < TOTAL - LB:
    gr_js.append(f'tl.set("#grain", {{x: {rg.randint(-240, 0) if t else 0}, y: {rg.randint(-420, 0) if t else 0}}}, {f(t)});'); t += 1 / 15
gr_js.append(f'tl.set("#grain", {{x: 0, y: 0}}, {f(TOTAL - LB)});')

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; background:#000; }}
#root {{ position:absolute; inset:0; overflow:hidden; background:#000; font-family:"Inter", sans-serif; }}
.pimg {{ position:absolute; left:0; top:0; width:1080px; height:1920px; display:block; z-index:1; will-change:transform; }}
#vig {{ position:absolute; inset:0; z-index:8; pointer-events:none; background:radial-gradient(ellipse 75% 62% at 50% 46%, rgba(0,0,0,0) 38%, rgba(0,0,0,.55) 78%, rgba(0,0,0,.88) 100%); }}
#grainwrap {{ position:absolute; inset:0; z-index:9; overflow:hidden; pointer-events:none; opacity:{H.get("grain", 0.13)}; mix-blend-mode:overlay; }}
#grain {{ position:absolute; left:0; top:0; width:{540 * 2 * 1.5:.0f}px; height:{960 * 2 * 1.5:.0f}px; background:url(assets/grain.png); background-size:1080px 1920px; }}
#flick {{ position:absolute; inset:0; z-index:10; background:#000; opacity:0; pointer-events:none; }}
.cg {{ position:absolute; left:0; top:{H.get("caption_y", 1190)}px; width:1080px; height:120px; opacity:0; z-index:12; }}
.cgi {{ position:absolute; left:0; right:0; top:0; text-align:center; font-weight:900; font-size:60px; line-height:1.15; white-space:nowrap; letter-spacing:.01em; }}
.cw {{ display:inline-block; margin:0 6px; color:#f1ede4; opacity:0.55; padding:4px 0; text-shadow:0 2px 16px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.95), 0 0 2px #000; }}
.cw.em {{ color:#ff4a3d; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{f(TOTAL)}" data-width="1080" data-height="1920">
  {(NL + "  ").join(img_html)}
  <div id="vig"></div>
  <div id="grainwrap"><div id="grain"></div></div>
  <div id="flick"></div>
  {(NL + "  ").join(caps_html)}
  <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{f(TOTAL)}" data-volume="1"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{NL.join(cam_js)}
{NL.join(gr_js)}
{NL.join(fl)}
{NL.join(caps_js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
(ROOT / "video/index.html").write_text(page, encoding="utf-8")
(ROOT / "build/horror_events.json").write_text(json.dumps(EV, indent=1))
import shutil
if shutil.which("node"):
    js = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]; (ROOT / "build/page_script.js").write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(ROOT / "build/page_script.js")], capture_output=True, text=True)
    if r.returncode: raise SystemExit("page script does not parse: " + r.stderr[:800])
print("panels", len(P), "| caption groups", len(groups), "| flickers", len(EV["flickers"]), "| total", TOTAL, "| cuts", [c["t"] for c in EV["cuts"]])
