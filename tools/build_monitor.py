"""Surreal monitor-horror builder: video/index.html from script/video.json ("monitor" block) + build/timeline.json + build/captions.json.
No hard cuts. One camera drifts and slowly rolls the whole time; each panel melts into the next by a scale-through (the old image
rushes toward its focus point while the new one settles out of a 1.35x blow-up), a warped double exposure (SVG turbulence displacement),
and static. The whole frame breathes, speeds up, goes irregular, stops dead at the cue "stop" and resumes slowly. One monitor look
(night-vision tint, scanlines, a rolling hum bar, a ticking clock that freezes at the cue "freeze"). The last melt returns to panel 1
so the last frame equals frame 0.
All story timings come from monitor.cues (see tools/horror_timing.py). Writes video/index.html, video/assets/m_*.jpg, video/assets/grain.png
and build/monitor_events.json (read by tools/monitor_sound.py)."""
import difflib, html, json, random, re, shutil, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from horror_timing import Timing
from textnorm import tokens_with_owner

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
M = cfg["monitor"]
cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
T = Timing(M["cues"])
L = T.L
TOTAL = round(T.TOTAL, 3)
f = lambda x: f"{x:.3f}"
NL = "\n"
VID = ROOT / "video/assets"; VID.mkdir(parents=True, exist_ok=True)
MELT = M.get("melt_s", 2.2)
at, cue = T.at, T.cue


# ---- panels -> jpg ------------------------------------------------------------------------------------------------------------
src_dir = ROOT / "assets/generated/panels"
for p in M["panels"]:
    s = src_dir / f"{p['img']}.png"
    if not s.exists(): raise SystemExit(f"missing panel {s}")
    d = VID / f"m_{p['img']}.jpg"
    if not d.exists() or d.stat().st_mtime < s.stat().st_mtime:
        Image.open(s).convert("RGB").resize((1080, 1920), Image.LANCZOS).save(d, quality=92)

rng = np.random.default_rng(3)
g = rng.normal(128, 46, (960, 540)).clip(0, 255).astype(np.uint8)
Image.fromarray(np.dstack([g, g, g, np.full((960, 540), 255, np.uint8)])).save(VID / "grain.png")

# ---- captions (same word alignment as build_horror.py) ------------------------------------------------------------------------
clean = [w for w in cap if not (w["end"] - w["start"] < 0.001 and w["start"] > 0)]
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
    if cur and (c[3] != cur[-1][3] or len(cur) >= 4 or sum(len(x[0]) + 1 for x in cur) + len(c[0]) > 24):
        groups.append(cur); cur = []
    cur.append(c)
if cur: groups.append(cur)
emph = {w.lower() for w in M.get("emphasis", [])}
caps_html, caps_js = [], []
for gi, gr in enumerate(groups):
    s0 = max(0.1, gr[0][1] - 0.04)
    nxt = groups[gi + 1][0][1] - 0.04 if gi + 1 < len(groups) and groups[gi + 1][0][3] == gr[0][3] else None
    e0 = gr[-1][2] + 0.6
    if nxt is not None: e0 = min(e0, nxt - 0.02)
    e0 = min(e0, TOTAL - 0.4)
    spans = " ".join(f'<span id="c{gi}w{k}" class="cw{" em" if re.sub(r"[^a-z0-9]", "", w[0].lower()) in emph else ""}">{html.escape(w[0])}</span>' for k, w in enumerate(gr))
    caps_html.append(f'<div id="cg{gi}" class="clip cg" data-start="{f(s0)}" data-duration="{f(e0 - s0)}"><div class="cgi">{spans}</div></div>')
    js = [f'tl.set("#cg{gi}", {{opacity: 1}}, {f(s0)});']
    for k, w in enumerate(gr):
        js.append(f'tl.set("#c{gi}w{k}", {{opacity: 1}}, {f(w[1])});')
        if k + 1 < len(gr): js.append(f'tl.set("#c{gi}w{k}", {{opacity: 0.55}}, {f(gr[k + 1][1])});')
    js.append(f'tl.to("#cg{gi}", {{opacity: 0, duration: 0.2, ease: "power2.in"}}, {f(e0 - 0.2)});')
    js.append(f'tl.set("#cg{gi}", {{opacity: 0}}, {f(e0)});')
    caps_js.append(NL.join(js))

# ---- panels: melts instead of cuts ------------------------------------------------------------------------------------------
P = M["panels"]
anchors = [0.0] + [at(p["from"]) for p in P[1:]]
LOOP_AT = at(M.get("loop_from", "S14")) - 0.6          # the loop melt back to panel 1 starts here and runs to the end
wins = []                                                # transition window [t0, t1] into panel n (n >= 1), then the loop one
for n in range(1, len(P)): wins.append((anchors[n] - 0.45 * MELT, anchors[n] + 0.55 * MELT))
wins.append((LOOP_AT, TOTAL))
img_html, cam_js = [], []
SA, SB = 1.06, 1.17
EV = {"melts": [], "total": TOTAL}


def panel_js(idn, n, first, win_in, win_out, fx, fy, final_sa=None):
    """one image: enter (blow-up settles) -> drift -> exit (rushes at its focus point). win_* = (t0, t1) or None"""
    js = [f'gsap.set("{idn}", {{transformOrigin: "{fx}% {fy}%", scale: {SA}, opacity: {1 if first else 0}}});']
    t_drift0 = 0.0
    if win_in:
        a, b = win_in; dur_in = b - a
        js.append(f'tl.fromTo("{idn}", {{scale: {SA * 1.35:.3f}}}, {{scale: {SA}, duration: {f(dur_in)}, ease: "{"power2.out" if final_sa else "power3.out"}", immediateRender: false}}, {f(a)});')
        js.append(f'tl.fromTo("{idn}", {{opacity: 0}}, {{opacity: 1, duration: {f(dur_in * 0.62)}, ease: "sine.inOut", immediateRender: false}}, {f(a)});')
        t_drift0 = b
    if final_sa:   # the loop copy of panel 1 ends exactly as P1 starts: scale SA, nothing moving
        return js
    t_exit = win_out[0] if win_out else TOTAL
    if t_exit > t_drift0 + 0.1:
        js.append(f'tl.fromTo("{idn}", {{scale: {SA}}}, {{scale: {SB}, duration: {f(t_exit - t_drift0)}, ease: "none", immediateRender: false}}, {f(t_drift0)});')
    if win_out:
        a, b = win_out
        js.append(f'tl.fromTo("{idn}", {{scale: {SB}}}, {{scale: {SB * 1.55:.3f}, duration: {f(b - a)}, ease: "power2.in", immediateRender: false}}, {f(a)});')
        js.append(f'tl.fromTo("{idn}", {{opacity: 1}}, {{opacity: 0, duration: {f((b - a) * 0.62)}, ease: "sine.inOut", immediateRender: false}}, {f(a + (b - a) * 0.38)});')
    return js


for n, p in enumerate(P):
    win_in = wins[n - 1] if n > 0 else None
    win_out = wins[n]
    t_start = win_in[0] if win_in else 0.0
    t_end = win_out[1]
    img_html.append(f'<img id="p{n}" class="clip pimg" src="assets/m_{p["img"]}.jpg" alt="" data-start="{f(t_start)}" data-duration="{f(t_end - t_start)}" />')
    cam_js += panel_js(f"#p{n}", n, n == 0, win_in, win_out, p["fx"], p["fy"])
    EV["melts"].append({"t0": round(win_out[0], 3), "t1": round(win_out[1], 3), "to": P[n + 1]["img"] if n + 1 < len(P) else P[0]["img"]})
p0 = P[0]; lw = wins[-1]
img_html.append(f'<img id="pend" class="clip pimg" src="assets/m_{p0["img"]}.jpg" alt="" data-start="{f(lw[0])}" data-duration="{f(TOTAL - lw[0])}" />')
cam_js += panel_js("#pend", len(P), False, lw, None, p0["fx"], p0["fy"], final_sa=True)

# ---- roll: the world tilts further as the thing comes closer, and unwinds in the loop melt ---------------------------------------
k_roll = [(0.0, 0.0)] + [(LOOP_AT if s == "loop" else at(s), v) for s, v in M["roll"]] + [(TOTAL - 0.6, 0.0), (TOTAL, 0.0)]   # level and still for the last 0.6 s, so the last frame matches frame 0
roll_js = ['gsap.set("#world", {rotation: 0, scale: 1, transformOrigin: "50% 50%"});']
for (ta, ra), (tb, rb) in zip(k_roll, k_roll[1:]):
    sa, sb = 1 + 0.034 * abs(ra), 1 + 0.034 * abs(rb)
    roll_js.append(f'tl.fromTo("#world", {{rotation: {ra:.2f}, scale: {sa:.3f}}}, {{rotation: {rb:.2f}, scale: {sb:.3f}, duration: {f(tb - ta)}, ease: "sine.inOut", immediateRender: false}}, {f(ta)});')

# ---- the frame breathes; the rhythm speeds up after "whisper", stops at "stop", resumes at "resume" -----------------------------
t_stop, t_resume, t_irreg, t_tear, t_freeze = cue("stop"), cue("resume"), cue("whisper"), cue("tear"), cue("freeze")
breaths, t = [], 0.4
while t < TOTAL - 3.4:
    if t_stop <= t < t_resume: t = t_resume; continue
    if t < t_irreg: per = 2.1
    elif t < t_stop: per = max(1.25, 2.1 - 0.85 * (t - t_irreg) / (t_stop - t_irreg)) + random.Random(int(t * 10)).uniform(-0.18, 0.18)
    else: per = 2.9
    amp = 0.011 if t < t_irreg else 0.014
    breaths.append((round(t, 3), round(per, 3), amp)); t += per
breath_js = ['gsap.set("#breath", {scale: 1, transformOrigin: "50% 50%"});']
for t0, per, amp in breaths:
    breath_js.append(f'tl.to("#breath", {{scale: {1 + amp:.4f}, duration: {f(per * 0.42)}, ease: "sine.inOut"}}, {f(t0)});')
    breath_js.append(f'tl.to("#breath", {{scale: 1, duration: {f(per * 0.58)}, ease: "sine.inOut"}}, {f(t0 + per * 0.42)});')
EV["breaths"] = [[b[0], b[1]] for b in breaths]

# ---- warp (SVG displacement): a living-wall baseline, melt swells, word-hit spikes, the signal tear at "stop" --------------------
BASE = 5
warp = [(0.0, BASE)]
def swell(t0, t1, peak):
    mid = (t0 + t1) / 2
    warp.extend([(t0, BASE), (mid, peak), (t1, BASE)])
for a, b in wins: swell(a, min(b, TOTAL - 0.4), 95)
swell(t_irreg - 0.2, t_irreg + 1.5, 70)
for s in M["spikes"]:
    t1 = at(s); warp.extend([(t1 - 0.06, BASE), (t1, 40), (t1 + 0.22, BASE)])
warp.extend([(t_tear - 0.05, BASE), (t_tear, 170), (t_tear + 0.12, 15), (t_tear + 0.2, 120), (t_tear + 0.45, BASE)])
warp.extend([(t_freeze + 0.5, BASE), (cue("peer"), 38), (cue("reveal_end"), BASE)])
warp.append((TOTAL, BASE))
warp.sort(key=lambda x: x[0])
dedup, seen = [], set()
for tt, v in warp:
    tt = round(tt, 3)
    while tt in seen: tt += 0.001
    seen.add(tt); dedup.append((tt, v))
warp_js = [f'gsap.set("#disp", {{attr: {{scale: {BASE}}}}});']
for (ta, va), (tb, vb) in zip(dedup, dedup[1:]):
    if tb - ta > 0.0005: warp_js.append(f'tl.fromTo("#disp", {{attr: {{scale: {va}}}}}, {{attr: {{scale: {vb}}}, duration: {f(tb - ta)}, ease: "none", immediateRender: false}}, {f(ta)});')

# ---- static bursts + hum bar + red flicker -------------------------------------------------------------------------------------
st = []
def burst(t0, peak, dur): st.append(f'tl.set("#static", {{opacity: {peak}}}, {f(t0)});'); st.append(f'tl.to("#static", {{opacity: 0, duration: {f(dur)}, ease: "power2.out"}}, {f(t0 + 0.02)});')
for a, b in wins: burst((a + b) / 2, 0.35, 0.5)
burst(t_irreg, 0.3, 0.6)
burst(t_tear, 0.85, 0.35); burst(t_tear + 0.14, 0.7, 0.25)
burst(t_freeze, 0.5, 0.7)
burst(TOTAL - 0.3, 0.0, 0.1)
st.insert(0, 'gsap.set("#static", {opacity: 0});')
bar = []
tb = 1.3
while tb + 5.2 < TOTAL - 0.5:   # a sweep must finish before the end, or the last frame differs from frame 0
    bar.append(f'tl.fromTo("#bar", {{y: -400}}, {{y: 2300, duration: 5.2, ease: "none", immediateRender: false}}, {f(tb)});'); tb += 7.4
bar.insert(0, 'gsap.set("#bar", {y: -400});')

# clock: ticks each second from monitor.clock ("02:47:09"), frozen at the cue "freeze"; the frame-0 value returns for the final frame
h0, m0, s0_ = (int(x) for x in M.get("clock", "02:47:09").split(":"))
base_s = h0 * 3600 + m0 * 60 + s0_
ts_html, ts_js = [], []
for k in range(int(t_freeze) + 1):
    total_s = base_s + k
    label = f"{total_s // 3600:02d}:{(total_s // 60) % 60:02d}:{total_s % 60:02d}"
    ts_html.append(f'<span id="ts{k}" class="tsx">{label}</span>')
    ts_js.append(f'tl.set("#ts{k}", {{opacity: 1}}, {f(k)});')
    ts_js.append(f'tl.set("#ts{k}", {{opacity: 0}}, {f(k + 1 if k < int(t_freeze) else TOTAL + 1)});' if k < int(t_freeze) else f'tl.set("#ts{k}", {{opacity: 0}}, {f(TOTAL - 0.3)});')
ts_js.append(f'tl.set("#ts0", {{opacity: 1}}, {f(TOTAL - 0.3)});')
ts_js.insert(0, 'gsap.set(".tsx", {opacity: 0}); gsap.set("#ts0", {opacity: 1});')
# signal bars die at the tear and come back slowly
sig = [f'tl.set(".sb", {{opacity: 1}}, 0);', f'tl.set(".sb3", {{opacity: 0.15}}, {f(t_tear)});', f'tl.set(".sb2", {{opacity: 0.15}}, {f(t_tear + 0.1)});',
       f'tl.set(".sb1", {{opacity: 0.15}}, {f(t_tear + 0.3)});', f'tl.set(".sb1", {{opacity: 1}}, {f(cue("back1"))});', f'tl.set(".sb2", {{opacity: 1}}, {f(cue("back2"))});',
       f'tl.set(".sb3", {{opacity: 1}}, {f(cue("close"))});']
rec = []
t = 0.0
while t < TOTAL - 1.5:
    rec.append(f'tl.set("#recdot", {{opacity: 1}}, {f(t)});'); rec.append(f'tl.set("#recdot", {{opacity: 0.15}}, {f(t + 0.7)});'); t += 1.4
rec.append(f'tl.set("#recdot", {{opacity: 1}}, {f(TOTAL - 0.2)});')

gr_js = []
rg = random.Random(9); t = 0.0
while t < TOTAL - 0.3:
    gr_js.append(f'tl.set("#grain", {{x: {rg.randint(-240, 0) if t else 0}, y: {rg.randint(-420, 0) if t else 0}}}, {f(t)});'); t += 1 / 15
gr_js.append(f'tl.set("#grain", {{x: 0, y: 0}}, {f(TOTAL - 0.3)});')

EV["key"] = {k: round(cue(k), 3) for k in M["cues"]}
EV["tear"] = round(t_tear, 3); EV["loop_at"] = round(LOOP_AT, 3)

TEMPLATE = (ROOT / "tools/monitor_template.html").read_text(encoding="utf-8")
page = (TEMPLATE.replace("%%IMGS%%", (NL + "    ").join(img_html)).replace("%%CAPS%%", (NL + "  ").join(caps_html))
        .replace("%%TS%%", "".join(ts_html)).replace("%%TOTAL%%", f(TOTAL)).replace("%%CAPTION_Y%%", str(M.get("caption_y", 1230)))
        .replace("%%JS%%", NL.join(cam_js + roll_js + breath_js + warp_js + st + bar + ts_js + sig + rec + gr_js + caps_js)))
(ROOT / "video/index.html").write_text(page, encoding="utf-8")
(ROOT / "build/monitor_events.json").write_text(json.dumps(EV, indent=1))
if shutil.which("node"):
    js = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]; (ROOT / "build/page_script.js").write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(ROOT / "build/page_script.js")], capture_output=True, text=True)
    if r.returncode: raise SystemExit("page script does not parse: " + r.stderr[:800])
print("panels", len(P), "| melts", [(round(a, 1), round(b, 1)) for a, b in wins], "| breaths", len(breaths), "| caption groups", len(groups), "| total", TOTAL)
