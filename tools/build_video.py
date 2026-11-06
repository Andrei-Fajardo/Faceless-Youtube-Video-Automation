"""Generate video/index.html from script/video.json + build/cues.json + timeline + captions.
Nothing is hardcoded in seconds or in a painting: times come from cues, the painting's size and focus point from video.json,
so a new voice, pause, or painting rebuilds the whole film."""
import difflib, html, json, math, re, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from textnorm import _word_tokens, tokens_with_owner

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
C = json.loads((ROOT / "build/cues.json").read_text())
tl = json.loads((ROOT / "build/timeline.json").read_text())
cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
L = {l["id"]: l for l in tl["lines"]}
TOTAL = round(tl["total_duration"], 3)


def wtime(line, tok):
    """first transcript word in the line whose spoken tokens contain tok"""
    for w in cap:
        if w["line"] == line and tok.lower() in _word_tokens(w["word"]): return w
    raise SystemExit(f"fun: word '{tok}' not found in line {line}")


f = lambda x: f"{x:.3f}"
EVENTS = []   # what happens when (camera moves, cards, pops, pose changes): build/events.json, read by tools/sound_design.py
NL = "\n"

# ---- layout: painting fitted into the safe band (168..1330 px), at most 905 px tall ---------------------------------
iw, ih = cfg["painting"]["width"], cfg["painting"]["height"]
W = min(1080.0, 905.0 * iw / ih); H = W * ih / iw
LEFT, TOP = (1080 - W) / 2, round(748 - H / 2)
slot_fs = int(min(84, max(44, TOP - 168 - 14))); slot_top = TOP - int(slot_fs * 1.05) - 12
CAP_TOP = int(TOP + H + 3)
REF_TOP = CAP_TOP + 130 + 200 > 1500   # no room under the captions (tall paintings): reference cards go to the top of the frame instead
REF_Y = 190 if REF_TOP else CAP_TOP + 130
UP_TY = 176 + 0.525 * H            # painting lifted to the top of the safe band while the title shows
TITLE_TOP = int(176 + 1.05 * H + 22)
FULL = bool(cfg.get("fullbleed"))   # the artwork covers the whole 1080x1920 frame at all times: no bands, no blurred backdrop, no gradients
CY = 960 if FULL else 748
_hs = cfg.get("hook_stroke", 0)   # hook_stroke: outline radius in px, drawn as a ring of hard text-shadows (reliable in headless Chromium)
HOOK_OUTLINE = ("text-shadow:" + ",".join(f"{round(_hs * __import__('math').cos(k * 0.3927))}px {round(_hs * __import__('math').sin(k * 0.3927))}px 0 #000" for k in range(16)) + ",0 6px 26px rgba(0,0,0,.9);") if _hs else ""
if FULL:
    W = 1080.0; H = W * ih / iw; LEFT, TOP = 0.0, 0
    slot_fs = cfg.get("hook_size", 80); slot_top = cfg.get("hook_y", 250); CAP_TOP = cfg.get("caption_y", 1190)

# ---- captions: script words (correct spelling) anchored to whisper words through shared spoken tokens ----------------
caps = []   # (text, start, end, line)
for s in script:
    if cfg.get("title_card") and s["id"] == cfg["title_card"]["line"]:
        continue  # the title card carries these words
    units = s["text"].split()
    ut, uo = tokens_with_owner(units)
    ws = [w for w in cap if w["line"] == s["id"]]
    wt, wo = tokens_with_owner([w["word"] for w in ws])
    a, b = L[s["id"]]["start"], L[s["id"]]["end"]
    matched = {}   # whisper word idx -> units matched to it
    for blk in difflib.SequenceMatcher(None, ut, wt, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            u, w = uo[blk.a + k], wo[blk.b + k]
            if u not in matched.setdefault(w, []): matched[w].append(u)
    pos, end = [None] * len(units), [None] * len(units)
    for wi, us in matched.items():
        us = sorted(set(us)); w0, w1 = ws[wi]["start"], ws[wi]["end"]
        for k, u in enumerate(us):   # several units sharing one whisper word (a spoken year) split its interval evenly
            if pos[u] is None: pos[u], end[u] = w0 + (w1 - w0) * k / len(us), w0 + (w1 - w0) * (k + 1) / len(us)
    prev_t, i = a, 0
    while i < len(units):
        if pos[i] is not None:
            prev_t = end[i]; i += 1; continue
        j = i
        while j < len(units) and pos[j] is None: j += 1
        nxt_t = pos[j] if j < len(units) else b
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

# ---- timing derived from cues ------------------------------------------------------------------------------------------
veil = cfg.get("veil"); dark = veil["dark"] if veil else 0; peak_dark = veil["peak"] if veil else 0
t_hook_out = (C["hand_word_end"] - 0.05) if cfg.get("hook_hold") else C["look_at_start"] - 0.05   # hook_hold: keep the hook on screen while it is spoken (default: frame 0 only)
t_zoom_start, t_zoom_end = C["look_at_start"], C["hand_word_end"]
t_pull = C["daylight_march_end"] + 0.05
z = cfg["zoom"]; zoom_peak = z["scale"]
title = cfg.get("title_card"); closing = cfg.get("closing"); year = cfg.get("year")
fun = cfg.get("fun", {})
emph = {re.sub(r"[^a-z0-9']", "", w.lower()) for w in fun.get("emphasis", [])}
close_in = C["closing_start"] if closing else None
close_out = TOTAL - 0.5

caps_html, caps_js = [], []
for gi, g in enumerate(groups):
    s0 = max(0.1, g[0][1] - 0.04)
    nxt = groups[gi + 1][0][1] - 0.04 if gi + 1 < len(groups) and groups[gi + 1][0][3] == g[0][3] else None
    e0 = g[-1][2] + 0.25
    if nxt is not None: e0 = min(e0, nxt - 0.02)
    e0 = min(e0, TOTAL - 0.05)
    spans = " ".join(f'<span id="c{gi}w{k}" class="cw{" em" if re.sub(chr(91) + "^a-z0-9" + chr(39) + chr(93), "", w[0].lower()) in emph else ""}">{html.escape(w[0])}</span>' for k, w in enumerate(g))
    caps_html.append(f'<div id="cg{gi}" class="clip cg" data-start="{f(s0)}" data-duration="{f(e0 - s0)}"><div class="cgi">{spans}</div></div>')
    js = [f'tl.set("#cg{gi}", {{opacity: 1}}, {f(s0)});']
    for k, w in enumerate(g):
        js.append(f'tl.set("#c{gi}w{k}", {{opacity: 1}}, {f(w[1])});')
        if fun.get("bounce"):
            big = 1.14 if re.sub(chr(91) + "^a-z0-9" + chr(39) + chr(93), "", w[0].lower()) in emph else 1.06
            js.append(f'tl.fromTo("#c{gi}w{k}", {{scale: {big}}}, {{scale: 1, duration: 0.24, ease: "back.out(3)"}}, {f(w[1])});')
        if k + 1 < len(g): js.append(f'tl.set("#c{gi}w{k}", {{opacity: 0.5}}, {f(g[k + 1][1])});')
    js.append(f'tl.to("#cg{gi}", {{opacity: 0, duration: 0.12, ease: "power2.in"}}, {f(e0 - 0.12)});')
    js.append(f'tl.set("#cg{gi}", {{opacity: 0}}, {f(e0)});')
    caps_js.append(NL.join(js))

hook_text = cfg["hook"]
title_text = (next(s["onscreen"] for s in script if s["id"] == title["line"]) or "") if title else ""
title_fs = title.get("font_size", 72) if title else 72
title_html = "<br>".join(html.escape(x) for x in (title.get("lines") if title and title.get("lines") else textwrap.wrap(title_text, width=21)))   # 4 lines of <= 21 characters at 72 px: inside 80% of the width

# ---- fun layer (optional, all from video.json "fun"): hook ring, callouts, pops, montage ---------------------------------
fun_css, ring_html, fun_html, fun_js = "", "", [], []
mt = fun.get("montage"); m0 = None; montage_cam = []; montage_end = None
pops = list(fun.get("pops", []))
if fun:
    fun_css = """.cw { margin:0 4px; }
.cw.em { color:#ffd166; }
.callout-box { position:absolute; width:460px; text-align:center; font-family:var(--font-ui); font-weight:900; font-size:40px; line-height:1.1; color:#1b1204; }
.callout-box span { display:inline-block; background:#ffd166; padding:10px 22px; border-radius:14px; box-shadow:0 6px 22px rgba(0,0,0,.55); }
.callout-arrow { position:absolute; width:0; height:0; border-left:16px solid transparent; border-right:16px solid transparent; }
.pop { display:inline-block; font-family:var(--font-display); font-weight:700; text-shadow:0 4px 22px rgba(0,0,0,.85); }
.pop-num { font-size:170px; color:#ffd166; line-height:1; }
.pop-card { font-family:var(--font-ui); font-weight:900; font-size:60px; color:#16110a; background:#f4efe3; padding:16px 34px; border:6px solid #16110a; box-shadow:0 8px 28px rgba(0,0,0,.6); text-shadow:none; }
.pop-stamp { font-family:var(--font-ui); font-weight:900; font-size:150px; letter-spacing:.04em; color:#ff4d4d; border:14px solid #ff4d4d; padding:6px 34px; border-radius:16px; background:rgba(20,10,10,.35); }
#ring { position:absolute; width:70px; height:70px; margin:-35px 0 0 -35px; border:6px solid #ffd166; border-radius:50%; box-shadow:0 0 22px rgba(255,209,102,.9); opacity:0; }
#ringlabel { position:absolute; margin:-92px 0 0 -60px; width:120px; text-align:center; font-family:var(--font-ui); font-weight:900; font-size:30px; color:#ffd166; text-shadow:0 2px 10px rgba(0,0,0,.9); opacity:0; }"""
LAYERS_HTML = ""
_ly = fun.get("layers")
if _ly:   # 2.5D parallax: cut-out figure and foreground drift slowly against the back layer and return, so the loop closes
    LAYERS_HTML = '<img id="lfig" class="lyr" src="assets/layer_fig.png" alt="" /><img id="lfront" class="lyr" src="assets/layer_front.png" alt="" />'
    fdx, fdy = _ly.get("figure", [6, 2]); gdx, gdy = _ly.get("front", [-10, -3])
    half = TOTAL / 2
    fun_js += [f'tl.fromTo("#lfig", {{x: 0, y: 0}}, {{x: {fdx}, y: {fdy}, duration: {f(half)}, ease: "sine.inOut", immediateRender: false}}, 0);',
               f'tl.to("#lfig", {{x: 0, y: 0, duration: {f(half - 0.6)}, ease: "sine.inOut"}}, {f(half)});',
               f'tl.fromTo("#lfront", {{x: 0, y: 0}}, {{x: {gdx}, y: {gdy}, duration: {f(half)}, ease: "sine.inOut", immediateRender: false}}, 0);',
               f'tl.to("#lfront", {{x: 0, y: 0, duration: {f(half - 0.6)}, ease: "sine.inOut"}}, {f(half)});']   # back to rest 0.6 s early: exact loop
MASCOT_HTML = ""; MASCOT_CSS = ""
_mc = fun.get("mascot")
if _mc:   # a presenter character in the lower third: pose sprites stacked, swapped on the beat with a squash, gentle idle bob
    BUST = bool(_mc.get("bust")); OUTFIT = ""
    if BUST:   # waist-up presenter in one of five outfits: picked once per video (script/outfit.json), never changes mid-video
        import json as _oj, random as _orn
        _of = ROOT / "script/outfit.json"; _all = ["tweed", "velvet", "navy", "tailcoat", "emerald"]
        _want = _mc.get("outfit", "random")
        if _want != "random" and (ROOT / "video/assets/mascot" / _want).is_dir(): OUTFIT = _want   # an explicit outfit folder always wins
        elif _of.exists(): OUTFIT = _oj.load(open(_of, encoding="utf-8"))["outfit"]
        else:
            _last = ROOT / "avatar/last_outfit.txt"; _prev = _last.read_text().strip() if _last.exists() else ""
            OUTFIT = _want if _want in _all else _orn.choice([o for o in _all if o != _prev])
            _of.write_text(_oj.dumps({"outfit": OUTFIT}), encoding="utf-8"); _last.write_text(OUTFIT)
    SPRITE_DIR = f"assets/mascot/{OUTFIT}" if BUST else "assets/mascot"
    MH = _mc.get("height", 700 if BUST else 560); MW = MH * 900 / 1100; ML = _mc.get("left", (1080 - MW) / 2 if BUST else 30); FEET = _mc.get("feet_y", 1920 if BUST else 1880)
    MT = FEET - (MH if BUST else MH * 1070 / 1100)
    poses = sorted({e["pose"] for e in _mc["schedule"]} | {_mc.get("start_pose", _mc["schedule"][0]["pose"])})
    first_pose = _mc.get("start_pose", _mc["schedule"][0]["pose"])
    imgs = "".join(f'<img id="mp_{n}" class="mpose" src="{SPRITE_DIR}/{n}.png" alt="" style="opacity:{1 if n == first_pose else 0};" />' for n in poses)
    _ls = _mc.get("lipsync")   # mouth/eye patches stacked on the 'talk' sprite, swapped with the speech (see prep_visemes.py)
    if _ls:
        imgs += "".join(f'<img id="mv_{n}" class="mpose" src="{SPRITE_DIR}/v_{n}.png" alt="" style="opacity:0;" />' for n in ["ah", "ah2", "ah3", "eh", "o", "o2", "oo", "oo2", "fv", "ee", "teeth", "mid", "sh", "blink"])
    MASCOT_HTML = (f'<div id="mfloor"></div>{"" if BUST else "<div id=\"mshadow\"></div>"}<div id="mascot"><div id="mrig"><div id="mpop">{imgs}</div></div></div>')
    MASCOT_CSS = chr(10).join([f"#mfloor {{ position:absolute; left:0; top:1280px; width:1080px; height:640px; background:{'none' if FULL else 'linear-gradient(to top, rgba(0,0,0,.6), rgba(0,0,0,0))'}; z-index:3; pointer-events:none; }}",
                  f"#mshadow {{ position:absolute; left:{ML + MW * 0.12:.0f}px; top:{FEET - 14}px; width:{MW * 0.76:.0f}px; height:34px; border-radius:50%; background:rgba(0,0,0,.45); filter:blur(8px); z-index:3; }}",
                  f"#mascot {{ position:absolute; left:{ML}px; top:{MT:.0f}px; width:{MW:.0f}px; height:{MH}px; transform-origin:50% {100 if BUST else 97}%; z-index:4; }}",
                  f"#mrig, #mpop {{ position:absolute; inset:0; transform-origin:50% 98%; }}", f".mpose {{ position:absolute; inset:0; width:{MW:.0f}px; height:{MH}px; display:block; }}"])
    cur = first_pose
    def _mct(e):
        a = e.get("at", {}); ln = e.get("line") or a.get("line")
        base = (wtime(ln, a["word"])["start"] - 0.05) if a.get("word") else L[ln]["start"]
        return max(0.0, base + a.get("dt", 0.0))
    if _mc.get("lipsync"):   # the mouth only moves in the talk pose, so expressions live in the pause before their line ("when": "after" = after it) and hand back before speech resumes
        _lines = sorted(tl["lines"], key=lambda l: l["start"]); _ent = []
        for e in _mc["schedule"]:
            if e["pose"] == first_pose: continue
            li = next(i for i, l in enumerate(_lines) if l["id"] == (e.get("line") or e.get("at", {}).get("line")))
            if e.get("when") == "after":
                a0 = _lines[li]["end"] + 0.05; b0 = (_lines[li + 1]["start"] - 0.03) if li + 1 < len(_lines) else TOTAL - 0.6
            else:
                a0 = (_lines[li - 1]["end"] + 0.05) if li > 0 else 0.0; b0 = _lines[li]["start"] - 0.03
            if b0 - a0 < 0.35: a0 = b0 - 0.35
            _ent += [(max(0.0, a0), e["pose"]), (max(0.0, b0), first_pose)]
        sched = sorted(_ent + [(TOTAL - 0.55, first_pose)])
    else:
        sched = sorted([(_mct(e), e["pose"]) for e in _mc["schedule"]] + [(TOTAL - 0.55, first_pose)])
    for t, pz in sched:
        if pz == cur: continue
        _pf = _mc.get("pose_fade", 0)
        if _mc.get("pose_dip"):   # no blending (blends leave afterimages): a quick dip, an instant swap at its lowest point, then a soft settle
            fun_js += [f'tl.to("#mascot", {{scaleX: 1.018, scaleY: 0.965, duration: 0.07, ease: "sine.in"}}, {f(max(0.0, t - 0.07))});',
                       f'tl.set("#mp_{cur}", {{opacity: 0}}, {f(t)});', f'tl.set("#mp_{pz}", {{opacity: 1}}, {f(t)});',
                       f'tl.to("#mascot", {{scaleX: 1, scaleY: 1, duration: 0.28, ease: "sine.out"}}, {f(t)});']
        elif _pf:   # smooth: the new pose fades in on top of the old one, then a soft settle (no bounce)
            _pz_z = 3 + len(EVENTS)
            fun_js += [f'tl.set("#mp_{pz}", {{zIndex: {_pz_z}}}, {f(t)});',
                       f'tl.fromTo("#mp_{pz}", {{opacity: 0}}, {{opacity: 1, duration: {_pf}, ease: "sine.inOut", immediateRender: false}}, {f(t)});',
                       f'tl.set("#mp_{cur}", {{opacity: 0}}, {f(t + _pf)});',
                       f'tl.fromTo("#mascot", {{scaleX: 1.012, scaleY: 0.988}}, {{scaleX: 1, scaleY: 1, duration: 0.55, ease: "sine.out", immediateRender: false}}, {f(t)});']
        else:
            fun_js += [f'tl.set("#mp_{cur}", {{opacity: 0}}, {f(t)});', f'tl.set("#mp_{pz}", {{opacity: 1}}, {f(t)});',
                       f'tl.fromTo("#mascot", {{scaleX: 1.05, scaleY: 0.94}}, {{scaleX: 1, scaleY: 1, duration: 0.4, ease: "back.out(2.4)", immediateRender: false}}, {f(t)});']
        EVENTS.append({"type": "pose", "t": round(t, 3), "pose": pz, "from": cur})
        cur = pz
    if _ls:
        import re as _lre, random as _lrn
        talk = _ls.get("pose", "talk"); emph = {w.lower() for w in fun.get("emphasis", [])}
        changes = [(0.0, first_pose)] + [(t, pz) for t, pz in sched]
        def pose_at(t):
            cp = first_pose
            for tt, pz in changes:
                if tt <= t + 1e-6: cp = pz
            return cp
        import numpy as _np, soundfile as _sf, cmudict as _cmu
        _cd = _cmu.dict()
        _vv, _sr = _sf.read(ROOT / "audio/voice/voice_dry.wav"); _vv = _vv if _vv.ndim == 1 else _vv.mean(1)
        _hop = int(_sr * 0.01); _nf = len(_vv) // _hop
        _env = _np.sqrt((_vv[:_nf * _hop].reshape(_nf, _hop) ** 2).mean(1)); _env = _np.convolve(_env, _np.ones(3) / 3, "same")
        _thr = 0.07 * float(_np.percentile(_env, 95))
        def energy(t0, t1):
            i0 = int(max(0.0, t0) * 100); i1 = max(i0 + 1, int(t1 * 100))
            return float(_env[i0:i1].mean()) if i0 < len(_env) else 0.0
        # LIPREAD chart -> our nine low-key mouths; None = no change (consonants whose mouth follows the neighbouring vowel)
        VMAP = {"B": "closed", "M": "closed", "P": "closed", "F": "fv", "V": "fv", "W": "oo", "UW": "oo", "UH": "oo", "OW": "o", "AO": "o", "OY": "o",
                "AA": "ah", "AE": "ah", "AW": "ah", "AY": "ah", "EH": "ah", "AH": "ah", "EY": "ee", "IY": "ee", "Y": "ee", "IH": "mid", "ER": "mid",
                "S": "teeth", "Z": "teeth", "SH": "sh", "CH": "sh", "JH": "sh", "ZH": "sh"}
        LET = {"m": "B", "b": "B", "p": "B", "f": "F", "v": "F", "w": "W", "q": "W", "u": "UW", "o": "AO", "a": "AA", "e": "EH", "i": "IY", "y": "IY", "s": "S", "z": "S", "x": "S"}
        def phones_of(word):
            out = []
            for part in _lre.split(r"[-\s]+", word.lower()):
                part = _lre.sub(r"[^a-z']", "", part)
                if not part: continue
                pr = _cd.get(part)
                if pr: out += pr[0]
                else: out += [LET[c] for c in part if c in LET] or ["AH0"]
            return out
        def seg_of(w):
            ph = phones_of(w["word"])
            wts = []
            for q in ph:
                base = _lre.sub(r"\d", "", q); st = q[-1] if q[-1].isdigit() else ""
                if st: wts.append(1.0 + (0.5 if st == "1" else 0.0))
                elif base in "BMP" or base in ("F", "V"): wts.append(0.7)
                elif base in ("S", "Z", "SH", "CH", "JH", "ZH"): wts.append(0.6)
                else: wts.append(0.45)
            tot = sum(wts) or 1.0; t = w["start"] - 0.03; d = max(0.05, w["end"] - w["start"]); segs = []; curv = None; cs = t
            for q, wt in zip(ph, wts):
                base = _lre.sub(r"\d", "", q); v = VMAP.get(base)
                if base == "AH" and q.endswith("0"): v = "mid"
                if v is not None and v != curv:
                    if curv is not None: segs.append((curv, cs, t))
                    curv, cs = v, t
                t += d * wt / tot
            if curv is not None: segs.append((curv, cs, t))
            return segs
        ev = []
        words = sorted(cap, key=lambda w: w["start"]); allsegs = []
        for w in words: allsegs += seg_of(w)
        merged = []
        for v, t0, t1 in allsegs:   # too-short mouths merge into the previous one; the voice must actually be sounding or the mouth stays closed
            if merged and t1 - t0 < (0.04 if v in ("closed", "fv") else 0.07) and v not in ("closed",) and t0 - merged[-1][2] < 0.02:
                merged[-1] = (merged[-1][0], merged[-1][1], t1); continue
            merged.append((v, t0, t1))
        for v, t0, t1 in merged:
            if v != "closed" and energy(t0, t1) < _thr: continue
            ev.append((t0, None if v == "closed" else v))
            ev.append((t1, None))
        ev = [e for k, e in enumerate(ev) if not (e[1] is None and k + 1 < len(ev) and ev[k + 1][1] is not None and ev[k + 1][0] - e[0] < 0.03)]
        _trk = ROOT / "build/lipsync.json"   # mouth track measured from the voice audio (tools/lipsync_track.py); falls back to the dictionary timing above
        if _trk.exists() and _ls.get("track", True):
            _lead = _ls.get("lead", 0.04); ev = []
            for _sg in json.loads(_trk.read_text())["segments"]:
                ev.append((max(0.0, _sg["t0"] - _lead), None if _sg["v"] == "closed" else _sg["v"]))
        ev.sort(key=lambda e: e[0])
        snap = lambda t: round(t * 30) / 30   # land every mouth change on a video frame (30 fps), never later than it should be
        seq = []
        for t, v in sorted(ev + [(tt, "closed") for tt, pz in changes if pz != talk], key=lambda e: e[0]):
            hard = pose_at(t + 1e-4) != talk
            v = None if (v == "closed" or hard) else v
            t = snap(t)
            if seq and seq[-1][0] == t: seq[-1] = (t, v, hard or seq[-1][2])   # same frame: the newer shape wins (no pushing later, no drift)
            else: seq.append((t, v, hard))
        # cross-fade: the new mouth fades in on top of the old one (raised z-index), then the old one is removed; closing fades the mouth out
        # onto the closed base. Pose swaps cut hard so a talking mouth never ghosts over another pose.
        fade = _ls.get("fade", 0.08); curv = None; zc = 20
        for t, v, hard in seq:
            if v == curv: continue
            if hard or fade <= 0:
                if curv: fun_js.append(f'tl.set("#mv_{curv}", {{opacity: 0}}, {f(t)});')
                if v: fun_js.append(f'tl.set("#mv_{v}", {{opacity: 1}}, {f(t)});')
            elif v:
                zc += 1
                fun_js += [f'tl.set("#mv_{v}", {{zIndex: {zc}}}, {f(t)});',
                           f'tl.fromTo("#mv_{v}", {{opacity: 0}}, {{opacity: 1, duration: {fade}, ease: "sine.inOut", immediateRender: false}}, {f(t)});']
                if curv: fun_js.append(f'tl.set("#mv_{curv}", {{opacity: 0}}, {f(t + fade)});')
            elif curv:
                fun_js.append(f'tl.fromTo("#mv_{curv}", {{opacity: 1}}, {{opacity: 0, duration: {fade}, ease: "sine.inOut", immediateRender: false}}, {f(t)});')
            curv = v
        if curv: fun_js.append(f'tl.set("#mv_{curv}", {{opacity: 0}}, {f(TOTAL - 0.3)});')
        br = _lrn.Random(11); tb = 1.4
        while tb < TOTAL - 1.2:
            if pose_at(tb) == talk and pose_at(tb + 0.15) == talk:
                fun_js += [f'tl.set("#mv_blink", {{opacity: 1}}, {f(tb)});', f'tl.set("#mv_blink", {{opacity: 0}}, {f(tb + 0.13)});']
            tb += br.uniform(2.6, 4.4)
    _bd = _mc.get("bob_dur", 1.3); _ba = _mc.get("bob", 7); nseg = max(2, int((TOTAL - 1.4) / _bd) // 2 * 2)   # an even number of bob segments so he is back at rest at the end
    fun_js += [f'tl.to("#mascot", {{scale: 1.06, duration: 0.12, ease: "power2.out"}}, 0.1);', f'tl.to("#mascot", {{scale: 1, duration: 0.4, ease: "{'sine.out' if _mc.get('pose_fade') else 'back.out(2.6)'}"}}, 0.22);',
               f'tl.to("#mascot", {{y: -{_ba}, duration: {_bd}, ease: "sine.inOut", yoyo: true, repeat: {nseg - 1}}}, 0.7);']
    if _mc.get("accents"):   # secondary motion on wrappers (#mrig sway + breathing, #mpop nod on stressed words), all returning to rest for the loop
        import re as _are
        _em = {w.lower() for w in fun.get("emphasis", [])}; _lastp = -9.0; nb = max(2, int(TOTAL / 1.6) // 2 * 2); nsw = max(2, int(TOTAL / 2.3) // 2 * 2)
        fun_js += [f'tl.fromTo("#mrig", {{scaleY: 1}}, {{scaleY: 1.016, duration: {f(TOTAL / nb)}, ease: "sine.inOut", yoyo: true, repeat: {nb - 1}, immediateRender: false}}, 0);',
                   f'tl.fromTo("#mrig", {{rotation: -1.1}}, {{rotation: 1.1, duration: {f(TOTAL / nsw)}, ease: "sine.inOut", yoyo: true, repeat: {nsw - 1}, immediateRender: false}}, 0);']
        for w in sorted(cap, key=lambda w: w["start"]):
            tok = _are.sub(r"[^a-z0-9']", "", w["word"].lower())
            if tok in _em and w["start"] - _lastp > 0.7 and 0.4 < w["start"] < TOTAL - 1.2:
                fun_js += [f'tl.to("#mpop", {{scale: 1.035, y: -8, rotation: 1.4, duration: 0.2, ease: "sine.out"}}, {f(w["start"] - 0.03)});',
                           f'tl.to("#mpop", {{scale: 1, y: 0, rotation: 0, duration: 0.5, ease: "sine.inOut"}}, {f(w["start"] + 0.17)});']
                _lastp = w["start"]
CAPTION_SHADE_CSS = (".cw { opacity:0.72; text-shadow:0 0 5px #000, 0 0 10px #000, 0 0 18px rgba(0,0,0,.95), 0 3px 22px #000; }" if fun.get("caption_shade") else "")
hr = fun.get("hook_ring")
if hr:
    rx, ry = hr["focus"][0] * W, hr["focus"][1] * H
    ring_html = (f'<div id="ring" style="left:{rx:.1f}px;top:{ry:.1f}px;"></div>\n    '
                 f'<div id="ringlabel" style="left:{rx:.1f}px;top:{ry:.1f}px;">{html.escape(hr.get("label", "HERE"))}</div>')
    reps = max(1, int((t_hook_out - 0.1 - 0.85) / 0.45) - 1)
    fun_js += [f'tl.fromTo("#ring", {{opacity: 0, scale: 2.6}}, {{opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2)"}}, 0.35);',
               f'tl.fromTo("#ringlabel", {{opacity: 0}}, {{opacity: 1, duration: 0.3}}, 0.6);',
               f'tl.to("#ring", {{scale: 1.35, duration: 0.45, yoyo: true, repeat: {reps}, ease: "sine.inOut"}}, 0.85);',
               f'tl.to(["#ring", "#ringlabel"], {{opacity: 0, duration: 0.2}}, {f(t_hook_out - 0.1)});']
for i, c in enumerate(fun.get("callouts", [])):
    ln = L[c["line"]]; t0 = ln["start"] + c.get("delay", 0.1); t1 = ln["end"] + c.get("hold", 0.5)
    tx, ty = c["tip"]; down = c.get("dir", "down") == "down"
    left = min(max(tx - 230, 30), 1050 - 460)
    box_top = ty - 46 - 66 if down else ty + 46
    arrow_top = ty - 44 if down else ty + 10
    arrow_css = "border-top:34px solid #ffd166;" if down else "border-bottom:34px solid #ffd166;"
    fun_html.append(f'<div id="co{i}" class="clip" data-start="{f(t0)}" data-duration="{f(t1 - t0)}" style="position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:7;">'
                    f'<div id="cobox{i}" class="callout-box" style="left:{left}px;top:{box_top}px;"><span>{html.escape(c["text"])}</span></div>'
                    f'<div id="coarr{i}" class="callout-arrow" style="left:{tx - 16}px;top:{arrow_top}px;{arrow_css}"></div></div>')
    fun_js += [f'tl.fromTo(["#cobox{i}", "#coarr{i}"], {{opacity: 0, y: {-24 if down else 24}, scale: 0.8}}, {{opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(2.2)"}}, {f(t0)});',
               f'tl.to("#coarr{i}", {{y: {10 if down else -10}, duration: 0.32, yoyo: true, repeat: 3, ease: "sine.inOut"}}, {f(t0 + 0.4)});',
               f'tl.to(["#cobox{i}", "#coarr{i}"], {{opacity: 0, duration: 0.25}}, {f(t1 - 0.25)});']
if mt:
    ml = L[mt["line"]]; m0 = wtime(mt["line"], mt["word"])["start"] - 0.1
    pts = mt["points"]; n = len(pts); sc = mt.get("scale", 5.5)
    limit = (C["title_start"] - 0.8) if title else TOTAL - 1.0
    step = min(0.85, max(0.5, (ml["end"] + 0.5 - m0) / n))
    if m0 + n * step > limit: step = max(0.45, (limit - m0) / n)
    prev = "WHOLE(1.05)"
    for i, (fx, fy) in enumerate(pts):
        a = m0 + i * step
        msx, msy = mt.get("screen", [540, 760]); c1 = f"cam({sc}, {fx * W:.1f}, {fy * H:.1f}, {msx}, {msy})"; c2 = f"cam({sc + 0.3}, {fx * W:.1f}, {fy * H:.1f}, {msx}, {msy})"
        montage_cam.append(f'tl.fromTo("#cam", {prev}, {{ ...{c1}, duration: 0.22, ease: "power3.inOut" }}, {f(a)});')
        montage_cam.append(f'tl.fromTo("#cam", {c1}, {{ ...{c2}, duration: {f(step - 0.22)}, ease: "none" }}, {f(a + 0.22)});')
        prev = c2
    montage_end = m0 + n * step
    montage_cam.append(f'tl.fromTo("#cam", {prev}, {{ ...WHOLE(1.05), duration: 0.4, ease: "power2.inOut" }}, {f(montage_end)});')
    if mt.get("stamp"):
        pops.append({"line": mt["line"], "text": mt["stamp"], "kind": "stamp", "at": montage_end - 0.35, "hold": 1.3, "y": mt.get("stamp_y", 700)})
for i, pp in enumerate(pops):
    ln = L[pp["line"]]
    t0 = pp["at"] if "at" in pp else (ln["end"] - 0.35 if pp.get("at_end") else ((wtime(pp["line"], pp["word"])["start"] - 0.05) if pp.get("word") else ln["start"]))
    t1 = min(t0 + pp.get("hold", max(1.4, ln["end"] - t0 + 0.4)), TOTAL - 0.6)
    kind = pp.get("kind", "num"); y = pp.get("y", 700 if kind == "stamp" else ((520 if kind == "card" else 470) if REF_TOP else (300 if kind == "card" else 250)))
    if kind == "timer":
        big, _, small = pp["text"].partition("|")
        inner = (f'<svg width="300" height="300" viewBox="0 0 300 300"><circle cx="150" cy="150" r="120" fill="rgba(10,8,5,.55)" stroke="rgba(255,255,255,.25)" stroke-width="18"/>'
                 f'<circle id="tm{i}" cx="150" cy="150" r="120" fill="none" stroke="#ffd166" stroke-width="18" stroke-linecap="round" stroke-dasharray="754" stroke-dashoffset="754" transform="rotate(-90 150 150)"/></svg>'
                 f'<div class="timer-text">{html.escape(big)}<small>{html.escape(small)}</small></div>')
    else:
        inner = html.escape(pp["text"])
    fun_html.append(f'<div id="pw{i}" class="clip" data-start="{f(t0)}" data-duration="{f(t1 - t0)}" style="position:absolute;left:0;top:{y}px;width:1080px;text-align:center;z-index:8;">'
                    f'<div id="pop{i}" class="pop pop-{kind}">{inner}</div></div>')
    if kind == "timer":
        fun_js += [f'tl.fromTo("#pop{i}", {{scale: 0.3, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.42, ease: "back.out(2.4)"}}, {f(t0)});',
                   f'tl.fromTo("#tm{i}", {{attr: {{"stroke-dashoffset": 754}}}}, {{attr: {{"stroke-dashoffset": 0}}, duration: {f(max(0.5, t1 - t0 - 0.7))}, ease: "none", immediateRender: false}}, {f(t0 + 0.3)});',
                   f'tl.to("#pop{i}", {{opacity: 0, scale: 0.8, duration: 0.25, ease: "power2.in"}}, {f(t1 - 0.25)});']
    elif kind == "num":
        fun_js += [f'tl.fromTo("#pop{i}", {{scale: 0.3, opacity: 0, rotation: -8}}, {{scale: 1, opacity: 1, rotation: 0, duration: 0.42, ease: "back.out(2.6)"}}, {f(t0)});',
                   f'tl.to("#pop{i}", {{opacity: 0, scale: 1.2, duration: 0.22, ease: "power2.in"}}, {f(t1 - 0.22)});']
    elif kind == "card":
        fun_js += [f'tl.fromTo("#pop{i}", {{x: -1300, rotation: -10}}, {{x: 0, rotation: -3, duration: 0.5, ease: "power3.out"}}, {f(t0)});',
                   f'tl.to("#pop{i}", {{x: 1300, rotation: 6, duration: 0.35, ease: "power2.in"}}, {f(t1 - 0.35)});']
    else:
        fun_js += [f'tl.fromTo("#pop{i}", {{scale: 3.4, opacity: 0, rotation: -20}}, {{scale: 1, opacity: 1, rotation: -8, duration: 0.26, ease: "power4.in"}}, {f(t0)});',
                   f'tl.to("#pop{i}", {{scale: 1.07, duration: 0.08, yoyo: true, repeat: 1}}, {f(t0 + 0.26)});',
                   f'tl.to("#pop{i}", {{opacity: 0, duration: 0.25}}, {f(t1 - 0.25)});']

# ---- reference cards: show WHO or WHAT the narration cites (a portrait, a document, a quote with its source) ------------------
REF_TOP = CAP_TOP + 130 + 200 > 1500   # no room under the captions (tall paintings): put the cards at the top of the frame instead
REF_Y = 190 if REF_TOP else CAP_TOP + 130
fun_css += """
.refcard { width:860px; margin:0 auto; display:flex; gap:20px; align-items:center; background:#14110d; border:3px solid #ffd166; border-radius:16px; padding:16px 20px; box-shadow:0 10px 30px rgba(0,0,0,.6); text-align:left; }
.refimg { width:150px; height:150px; object-fit:cover; object-position:50% 20%; border-radius:10px; flex:none; background:#000; }
.reftext { min-width:0; }
.reftag { font-family:var(--font-ui); font-weight:900; font-size:20px; letter-spacing:.14em; color:#ffd166; }
.reflabel { font-family:var(--font-display); font-weight:700; font-size:36px; line-height:1.1; color:#f6efe2; }
.refquote { font-family:var(--font-display); font-style:italic; font-size:29px; line-height:1.2; color:#e8e1d2; margin-top:4px; }
.refsrc { font-family:var(--font-ui); font-weight:500; font-size:21px; color:#a9a091; margin-top:6px; }"""
for i, r in enumerate(fun.get("refs", [])):
    ln = L[r["line"]]
    t0 = (wtime(r["line"], r["word"])["start"] - 0.05) if r.get("word") else ln["start"] + r.get("delay", 0.15)
    t1 = min(t0 + r.get("hold", max(2.6, ln["end"] - t0 + 0.4)), TOTAL - 0.6)
    side = r.get("side", "left"); y = r.get("y", REF_Y); sgn = -1 if side == "left" else 1
    img = f'<img class="refimg" src="{r["image"]}" alt="" />' if r.get("image") else ""
    quote = f'<div class="refquote">{html.escape(r["text"])}</div>' if r.get("text") else ""
    src = f'<div class="refsrc">{html.escape(r["source"])}</div>' if r.get("source") else ""
    fun_html.append(f'<div id="rf{i}" class="clip" data-start="{f(t0)}" data-duration="{f(t1 - t0)}" style="position:absolute;left:0;top:{y}px;width:1080px;z-index:9;">'
                    f'<div id="rc{i}" class="refcard">{img}<div class="reftext"><div class="reftag">{html.escape(r.get("tag", "SOURCE"))}</div>'
                    f'<div class="reflabel">{html.escape(r["label"])}</div>{quote}{src}</div></div></div>')
    EVENTS += [{"type": "card_in", "t": round(t0, 3)}, {"type": "card_out", "t": round(t1 - 0.35, 3)}]
    fun_js += [f'tl.fromTo("#rc{i}", {{x: {sgn * 1000}, rotation: {sgn * 4}, opacity: 0}}, {{x: 0, rotation: {-sgn * 1.2}, opacity: 1, duration: 0.5, ease: "back.out(1.5)"}}, {f(t0)});',
               f'tl.to("#rc{i}", {{x: {sgn * 1000}, rotation: {sgn * 3}, opacity: 0, duration: 0.35, ease: "power2.in"}}, {f(t1 - 0.35)});']

# ---- shot list: a camera move or cut on (almost) every line, with smooth / whip / zoom transitions -------------------------
def shot_state(sh, scale, v=None):
    v = v or sh.get("view", "whole")
    if v == "whole": return f"WHOLE({scale})"
    if v == "up": return f"UP({scale})"
    tx, ty = sh.get("screen", [540, 960 if FULL else 760])
    return f"cam({scale}, {v[0] * W:.1f}, {v[1] * H:.1f}, {tx}, {ty})"


whip_times = []


def build_shots(shots):
    out, starts = [], []
    for sh in shots:
        at = sh.get("at", {}); line = sh.get("line") or at.get("line")
        base = (wtime(line, at["word"])["start"] - 0.05) if at.get("word") else L[line]["start"]
        starts.append(max(0.0, base + at.get("dt", 0.0)))
    prev_end = "WHOLE(1)"
    if FULL and shots and isinstance(shots[0].get("view"), list): prev_end = shot_state(shots[0], shots[0].get("scale", 1.0))   # frame 0 is the first shot, never the whole poster
    out.append(f'tl.set("#cam", {{ ...{prev_end} }}, 0);')   # pin frame 0 (the loop must start and end on the same frame)
    for i, sh in enumerate(shots):
        t0 = starts[i]; t1 = starts[i + 1] if i + 1 < len(shots) else TOTAL
        s0 = sh.get("scale", 1.0); s1 = sh.get("end_scale", s0)
        a, b = shot_state(sh, s0), shot_state(sh, s1, sh.get("end_view"))
        kind = sh.get("transition", "smooth")
        if kind == "whip": whip_times.append(t0)
        trn = {"whip": 1.3, "smooth": 1.3, "slow": 1.5, "zoom": 1.9, "cut": 0.001}[kind]   # gentle glides only; no snappy moves
        trn = min(trn, max(0.001, (t1 - t0) * 0.9))
        ease = {"whip": "sine.inOut", "smooth": "sine.inOut", "slow": "sine.inOut", "zoom": "sine.inOut", "cut": "none"}[kind]
        out.append(f'tl.fromTo("#cam", {prev_end}, {{ ...{a}, duration: {f(trn)}, ease: "{ease}", immediateRender: false }}, {f(t0)});')
        if kind != "cut": EVENTS.append({"type": "move", "t": round(t0, 3), "dur": round(trn, 3), "kind": kind})
        settle = 0.5 if i + 1 == len(shots) else 0.0   # last shot lands on its end pose before the final frame: seamless loop
        if t1 - t0 - trn - settle > 0.02:
            out.append(f'tl.fromTo("#cam", {a}, {{ ...{b}, duration: {f(t1 - t0 - trn - settle)}, ease: "none", immediateRender: false }}, {f(t0 + trn)});')
            prev_end = b
        else:
            prev_end = a
    return out


# ---- graphics layer 2: vignette, progress bar, parallax background, wipes, draw-on rings, colour swatches, flashes -------------
fun_css += """
.pop-timer { position:relative; width:300px; height:300px; text-shadow:none; }
.timer-text { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:var(--font-display); font-weight:700; font-size:104px; line-height:.9; color:#ffd166; }
.timer-text small { font-family:var(--font-ui); font-weight:900; font-size:34px; letter-spacing:.14em; color:#f6efe2; }
.wipe { position:absolute; top:-120px; left:0; width:380px; height:2160px; opacity:0; z-index:10; pointer-events:none; }
.swc { width:196px; height:96px; border-radius:14px; display:flex; align-items:flex-end; justify-content:center; padding-bottom:8px; box-shadow:0 8px 24px rgba(0,0,0,.55); border:3px solid rgba(255,255,255,.85); position:relative; }
.swc span { font-family:var(--font-ui); font-weight:900; font-size:24px; letter-spacing:.08em; color:#fff; text-shadow:0 2px 6px rgba(0,0,0,.8); }
.swc.strike { background:#000; }
.swc.strike::after { content:""; position:absolute; inset:0; border-radius:11px; background:linear-gradient(to top right, transparent 46%, #ff4d4d 46%, #ff4d4d 54%, transparent 54%); }
.ringsvg { position:absolute; overflow:visible; opacity:0; }"""
if fun.get("vignette"):
    fun_html.append('<div id="vignette"></div>')
    fun_css += "\n#vignette { position:absolute; inset:0; z-index:3; pointer-events:none; background:radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(0,0,0,.6) 100%); }"
if fun.get("progress"):
    fun_html.append('<div id="progress"><div id="progfill"></div></div>')
    fun_css += "\n#progress { position:absolute; left:0; top:176px; width:1080px; height:8px; z-index:12; background:rgba(255,255,255,.16); opacity:0; }\n#progfill { width:100%; height:100%; background:#ffd166; }"
    fun_js += ['gsap.set("#progfill", {transformOrigin: "0 50%", scaleX: 0});',
               f'tl.fromTo("#progfill", {{scaleX: 0}}, {{scaleX: 1, duration: {f(TOTAL)}, ease: "none", immediateRender: false}}, 0);',
               f'tl.to("#progress", {{opacity: 1, duration: 0.3}}, 0.4);',
               f'tl.to("#progress", {{opacity: 0, duration: 0.4}}, {f(TOTAL - 0.7)});']   # invisible on the first and last frame: seamless loop
if fun.get("bg_drift"):
    half = TOTAL / 2
    fun_js += ['gsap.set("#bg", {scale: 1.12, x: -26, y: 14});',
               f'tl.fromTo("#bg", {{scale: 1.12, x: -26, y: 14}}, {{scale: 1.12, x: 26, y: -34, duration: {f(half)}, ease: "sine.inOut", immediateRender: false}}, 0);',
               f'tl.to("#bg", {{scale: 1.12, x: -26, y: 14, duration: {f(half)}, ease: "sine.inOut"}}, {f(half)});']
if fun.get("flash"):
    fun_html.append('<div id="flash"></div>')
    fun_css += "\n#flash { position:absolute; inset:0; background:#fff; opacity:0; z-index:11; pointer-events:none; }"
for i, w in enumerate(fun.get("wipes", [])):
    at = w["at"]; wl = w.get("line") or at.get("line")
    t = (wtime(wl, at["word"])["start"] if at.get("word") else L[wl]["start"]) + at.get("dt", 0.0)
    fun_html.append(f'<div id="wipe{i}" class="wipe" style="background:linear-gradient(90deg,{w.get("color", "#ffd166")},{w.get("color2", "#ff8f4d")});"></div>')
    fun_js += [f'tl.set("#wipe{i}", {{opacity: 1, x: -460, skewX: -14}}, {f(max(0, t - 0.3))});',
               f'tl.to("#wipe{i}", {{x: 1560, duration: 0.6, ease: "power3.inOut"}}, {f(max(0, t - 0.3))});',
               f'tl.set("#wipe{i}", {{opacity: 0}}, {f(t + 0.32)});']
for i, c in enumerate(fun.get("circles", [])):
    ln = L[c["line"]]
    t0 = ((wtime(c["line"], c["word"])["start"] - 0.05) if c.get("word") else ln["start"]) + c.get("delay", 0.1) + c.get("dt", 0.0)
    t1 = t0 + c.get("hold", max(1.6, ln["end"] - t0 + 0.3))
    sc = c.get("scale", 5.0); r = c.get("radius", 150) / sc; sw = 7 / sc; pad = r * 0.25 + sw
    cx, cy = c["focus"][0] * W, c["focus"][1] * H; size = 2 * (r + pad); circ = 2 * math.pi * r
    ring_html += (f'\n    <svg id="cr{i}" class="ringsvg" style="left:{cx - r - pad:.1f}px;top:{cy - r - pad:.1f}px;" width="{size:.1f}" height="{size:.1f}" viewBox="0 0 {size:.1f} {size:.1f}">'
                  f'<circle id="crc{i}" cx="{size / 2:.1f}" cy="{size / 2:.1f}" r="{r:.2f}" fill="none" stroke="{c.get("color", "#ffd166")}" stroke-width="{sw:.3f}" stroke-linecap="round" '
                  f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}"/></svg>')
    fun_js += [f'tl.set("#cr{i}", {{opacity: 1}}, {f(t0)});',
               f'tl.fromTo("#crc{i}", {{attr: {{"stroke-dashoffset": {circ:.1f}}}}}, {{attr: {{"stroke-dashoffset": 0}}, duration: 0.5, ease: "power2.out", immediateRender: false}}, {f(t0)});',
               f'tl.to("#cr{i}", {{opacity: 0, duration: 0.25}}, {f(t1 - 0.25)});']
for i, sw_ in enumerate(fun.get("swatches", [])):
    ln = L[sw_["line"]]
    t0 = (wtime(sw_["line"], sw_["word"])["start"] - 0.05) if sw_.get("word") else ln["start"] + sw_.get("delay", 0.1)
    t1 = min(t0 + sw_.get("hold", max(2.4, ln["end"] - t0 + 0.5)), TOTAL - 0.6); y = sw_.get("y", 1250)
    items = "".join(f'<div class="swc sw{i}c" style="background:{c["hex"]};"><span>{html.escape(c["label"])}</span></div>' for c in sw_["colors"])
    if sw_.get("strike"): items += f'<div class="swc strike sw{i}c"><span>{html.escape(sw_["strike"])}</span></div>'
    fun_html.append(f'<div id="sw{i}" class="clip" data-start="{f(t0)}" data-duration="{f(t1 - t0)}" style="position:absolute;left:0;top:{y}px;width:1080px;display:flex;justify-content:center;gap:14px;z-index:8;">{items}</div>')
    fun_js += [f'tl.fromTo(".sw{i}c", {{y: 60, scale: 0.5, opacity: 0}}, {{y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "back.out(2)", stagger: 0.12}}, {f(t0)});',
               f'tl.to(".sw{i}c", {{opacity: 0, y: 30, duration: 0.25, stagger: 0.05}}, {f(t1 - 0.4)});']

# ---- camera chain ------------------------------------------------------------------------------------------------------
cam_js = []
cam_js.append(f'tl.fromTo("#cam", WHOLE(1), {{ ...WHOLE(1.07), duration: {f(t_zoom_start)}, ease: "sine.inOut" }}, 0);')
cam_js.append(f'tl.fromTo("#cam", WHOLE(1.07), {{ ...FOCUS, duration: {f(t_zoom_end - t_zoom_start)}, ease: "power2.inOut" }}, {f(t_zoom_start)});')
cam_js.append(f'tl.fromTo("#cam", FOCUS, {{ ...FOCUS2, duration: {f(max(0.2, t_pull - t_zoom_end))}, ease: "none" }}, {f(t_zoom_end)});')
cam_js.append(f'tl.fromTo("#cam", FOCUS2, {{ ...WHOLE(1.03), duration: 1.7, ease: "power2.inOut" }}, {f(t_pull)});')
t_after_pull = t_pull + 1.7
if title:
    drift_end = m0 if mt else C["title_start"] - 0.3
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.03), {{ ...WHOLE(1.05), duration: {f(max(0.2, drift_end - t_after_pull))}, ease: "none" }}, {f(t_after_pull)});')
    cam_js += montage_cam
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.05), {{ ...UP(1.05), duration: 0.7, ease: "power2.inOut" }}, {f(C["title_start"] - 0.3)});')
    cam_js.append(f'tl.fromTo("#cam", UP(1.05), {{ ...UP(1.06), duration: {f(C["cocq_end"] + 0.3 - C["title_start"] - 0.4)}, ease: "none" }}, {f(C["title_start"] + 0.4)});')
    back_at = C["cocq_end"] + 0.3
    settle_by = max(close_in if close_in else 0, C["cocq_end"] + 1.05)
    cam_js.append(f'tl.fromTo("#cam", UP(1.06), {{ ...WHOLE(1.05), duration: {f(max(0.6, settle_by - C["cocq_end"] - 0.45))}, ease: "power2.inOut" }}, {f(back_at)});')
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.05), {{ ...WHOLE(1), duration: {f(TOTAL - settle_by)}, ease: "sine.inOut" }}, {f(settle_by)});')
elif mt:
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.03), {{ ...WHOLE(1.05), duration: {f(max(0.2, m0 - t_after_pull))}, ease: "none" }}, {f(t_after_pull)});')
    cam_js += montage_cam
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.05), {{ ...WHOLE(1), duration: {f(TOTAL - montage_end - 0.4)}, ease: "sine.inOut" }}, {f(montage_end + 0.4)});')
else:
    cam_js.append(f'tl.fromTo("#cam", WHOLE(1.03), {{ ...WHOLE(1), duration: {f(TOTAL - t_after_pull)}, ease: "sine.inOut" }}, {f(t_after_pull)});')

if fun.get("shots"):
    cam_js = build_shots(fun["shots"])
    if fun.get("flash"):
        fv = fun["flash"] if isinstance(fun["flash"], (int, float)) and not isinstance(fun["flash"], bool) else 0.14
        for wt in whip_times:
            fun_js.append(f'tl.fromTo("#flash", {{opacity: {fv}}}, {{opacity: 0, duration: 0.24, ease: "power2.out", immediateRender: false}}, {f(wt)});')

# ---- veil / wipe (only for paintings whose premise is the darkened varnish) ---------------------------------------------
veil_js, veil_html, veil_css = [], "", ""
if veil:
    wipe_end = C["there_end"] - 0.1; wipe_start = wipe_end - 0.6
    veil_html = '<div id="veil" class="veil"></div>\n    <div id="veil-wipe" class="veil"><div id="veil-fill"></div></div>'
    veil_css = (f'#veil {{ background:{veil["color"]}; opacity:0; }}\n#veil-wipe {{ opacity:0; }}\n'
                f'#veil-fill {{ position:absolute; left:-{int(W * 1.2)}px; top:0; width:{int(W * 2.2)}px; height:100%; background:linear-gradient(90deg, rgba(0,0,0,0) 0px, rgba(0,0,0,0) {int(W * 0.93)}px, {veil["color"]} {int(W * 1.2)}px, {veil["color"]} {int(W * 2.2)}px); }}')
    veil_js = [
        f'gsap.set("#veil", {{ opacity: {dark} }});   // frame 1 is the dark painting',
        f'tl.set("#veil", {{ opacity: {dark} }}, 0);',
        f'tl.to("#veil", {{ opacity: 0.15, duration: 1.5, ease: "power2.out" }}, {f(t_zoom_start + 0.3)});',
        f'tl.to("#veil", {{ opacity: {peak_dark}, duration: {f(C["midnight_start"] - C["varnish_start"] + 0.35)}, ease: "power1.in" }}, {f(C["varnish_start"])});',
        f'tl.set("#veil", {{ opacity: 0 }}, {f(wipe_start)});',
        f'tl.set("#veil-wipe", {{ opacity: {peak_dark} }}, {f(wipe_start)});',
        f'tl.fromTo("#veil-fill", {{ x: 0 }}, {{ x: {int(W * 1.31)}, duration: {f(wipe_end - wipe_start)}, ease: "power1.inOut" }}, {f(wipe_start)});',
        f'tl.set("#veil-wipe", {{ opacity: 0 }}, {f(wipe_end + 0.02)});',
        f'tl.to("#veil", {{ opacity: {dark}, duration: {f(TOTAL - 0.25 - C["dirt_start"])}, ease: "power2.inOut" }}, {f(C["dirt_start"])});',
    ]

dbox = z.get("detail")
detail_html = (f'<img id="detail" src="assets/detail.jpg" alt="" style="position:absolute;left:{dbox[0] * W:.2f}px;top:{dbox[1] * H:.2f}px;'
               f'width:{(dbox[2] - dbox[0]) * W:.2f}px;height:{(dbox[3] - dbox[1]) * H:.2f}px;display:block;" />') if dbox else ""
year_html = f'<div id="year" class="clip slot" data-start="{f(C["year_start"] - 0.1)}" data-duration="1.9">{html.escape(year["text"])}</div>' if year else ""
title_box = (f'<div id="titlebox" class="clip" data-start="{f(C["title_start"] - 0.1)}" data-duration="{f(C["cocq_end"] - C["title_start"] + 0.8)}" '
             f'style="position:absolute;left:0;top:{TITLE_TOP}px;width:1080px;height:340px;z-index:6;"><div id="title">{title_html}</div></div>') if title else ""
closing_html = f'<div id="closing" class="clip slot" data-start="{f(close_in)}" data-duration="{f(close_out - close_in)}">{html.escape(closing["text"])}</div>' if closing else ""
year_js = (f'tl.fromTo("#year", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }}, {f(C["year_start"] - 0.1)});' + NL
           + f'tl.to("#year", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {f(C["year_start"] + 1.5)});') if year else ""
title_js = (f'tl.fromTo("#title", {{ opacity: 0, y: 26, scale: 0.97, filter: "blur(8px)" }}, {{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.75, ease: "power2.inOut" }}, {f(C["title_start"] - 0.1)});' + NL
            + f'tl.to("#title", {{ opacity: 0, y: -10, duration: 0.4, ease: "power2.in" }}, {f(C["cocq_end"] + 0.15)});') if title else ""
closing_js = (f'tl.fromTo("#closing", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4, ease: "power2.out" }}, {f(close_in)});' + NL
              + f'tl.to("#closing", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {f(close_out - 0.3)});') if closing else ""
veil_init = NL.join(x for x in veil_js if x.startswith("gsap.set"))
veil_tl = NL.join(x for x in veil_js if not x.startswith("gsap.set"))

_ex = fun.get("extra")
if _ex:   # custom HyperFrames graphics from video.json: cam_html (moves with the art), screen_html (fixed), css, js[]. {t:LINE[:dt]} and {tw:LINE:word[:dt]} become seconds.
    import re as _re
    def _tm(txt):
        txt = _re.sub(r"\{tw:(\w+):([\w-]+)(?::([+-]?[\d.]+))?\}", lambda m: f(wtime(m.group(1), m.group(2))["start"] + float(m.group(3) or 0)), txt)
        txt = _re.sub(r"\{t:(\w+)(?::([+-]?[\d.]+))?\}", lambda m: f(L[m.group(1)]["start"] + float(m.group(2) or 0)), txt)
        return txt.replace("{TOTAL}", f(TOTAL))
    LAYERS_HTML += NL + _tm(_ex.get("cam_html", ""))
    fun_html.append(_tm(_ex.get("screen_html", "")))
    fun_css += NL + _ex.get("css", "")
    fun_js += [_tm(j) for j in _ex.get("js", [])]
if FULL:   # every camera state must stay inside the artwork: a view that shows empty space fails the build
    bad = []
    for sh in fun.get("shots", []):
        v0 = sh.get("view"); v1 = sh.get("end_view", v0)
        if not isinstance(v0, list):
            bad.append(f"shot {sh.get('line')}: view must be [x, y] in fullbleed"); continue
        tx, ty = sh.get("screen", [540, 960])
        for vv, ss in ((v0, sh.get("scale", 1.0)), (v1, sh.get("end_scale", sh.get("scale", 1.0)))):
            px, py = vv[0] * W, vv[1] * H
            if px - tx / ss < -0.5 or px + (1080 - tx) / ss > W + 0.5 or py - ty / ss < -0.5 or py + (1920 - ty) / ss > H + 0.5:
                bad.append(f"shot {sh.get('line')}: view {vv} at scale {ss} shows empty space")
    if bad: raise SystemExit("fullbleed check failed:" + NL + NL.join(bad))
page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script>
<style>
:root {{ --ink:#f6efe2; --warm:#e9c46a; --font-display:"Playfair Display", serif; --font-ui:"Inter", sans-serif; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; background:#0b0805; }}
#root {{ position:absolute; inset:0; overflow:hidden; background:#0b0805; font-family:var(--font-ui); }}
#bg {{ position:absolute; inset:0; width:1080px; height:1920px; z-index:0; }}
#cam {{ position:absolute; left:{LEFT:.1f}px; top:{TOP}px; width:{W:.1f}px; height:{H:.1f}px; overflow:visible; transform-origin:0 0; z-index:1; }}
#painting {{ position:absolute; inset:0; width:{W:.1f}px; height:{H:.1f}px; display:block; }}
{MASCOT_CSS}
.lyr {{ position:absolute; inset:0; width:{W:.1f}px; height:{H:.1f}px; display:block; }}
.veil {{ position:absolute; inset:0; overflow:hidden; pointer-events:none; }}
{veil_css}
.slot {{ position:absolute; left:0; width:1080px; text-align:center; color:var(--ink); font-family:var(--font-display); font-weight:700; letter-spacing:-0.01em; text-shadow:0 3px 18px rgba(0,0,0,.85); z-index:5; }}
#hook1, #hook2, #closing {{ top:{slot_top}px; font-size:{slot_fs}px; line-height:1.05; padding:0 {cfg.get("hook_pad", 0)}px; box-sizing:border-box; {HOOK_OUTLINE} }}
#year {{ top:{(year or {}).get("y", TOP - 86)}px; font-size:76px; color:var(--warm); }}
.cg {{ position:absolute; left:0; top:{CAP_TOP}px; width:1080px; height:120px; opacity:0; z-index:6; }}
.cgi {{ position:absolute; left:0; right:0; top:0; text-align:center; font-weight:900; font-size:58px; line-height:1.15; white-space:nowrap; }}
.cw {{ display:inline-block; color:#fff; opacity:0.5; padding:4px 0; text-shadow:0 2px 14px rgba(0,0,0,.95), 0 0 3px rgba(0,0,0,.9); }}
{CAPTION_SHADE_CSS}
#title {{ position:absolute; left:0; right:0; top:0; text-align:center; font-family:var(--font-display); font-weight:700; font-size:{title_fs}px; line-height:1.1; color:var(--ink); text-shadow:0 3px 18px rgba(0,0,0,.9); }}
{fun_css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{f(TOTAL)}" data-width="1080" data-height="1920">
  {"" if FULL else '<img id="bg" src="assets/bg.jpg" alt="" />'}
  <div id="cam">
    <img id="painting" src="assets/painting.jpg" alt="" />
    {LAYERS_HTML}
    {detail_html}
    {ring_html}
    {veil_html}
  </div>
  {MASCOT_HTML}
  <div id="hook1" class="clip slot" data-start="0" data-duration="{f(t_hook_out + 0.3)}">{html.escape(hook_text)}</div>
  {year_html}
  {(NL + "  ").join(caps_html)}
  {title_box}
  {closing_html}
  {(NL + "  ").join(fun_html)}
  <div id="hook2" class="clip slot" data-start="{f(close_out - 0.02)}" data-duration="{f(TOTAL - close_out + 0.02)}">{html.escape(hook_text)}</div>
  <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{f(TOTAL)}" data-volume="1"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
// camera: scale s about the wrapper's top-left; painting point (px,py) (wrapper px) lands on screen point (tx,ty)
const cam = (s, px, py, tx, ty) => ({{ scale: s, x: tx - {LEFT:.1f} - px * s, y: (ty - {TOP}) - py * s }});
const WHOLE = (s) => cam(s, {W / 2:.1f}, {H / 2:.1f}, 540, {CY});
const UP = (s) => cam(s, {W / 2:.1f}, {H / 2:.1f}, 540, {UP_TY:.1f});
const FOCUS = cam({zoom_peak}, {z["focus"][0] * W:.1f}, {z["focus"][1] * H:.1f}, {z["screen"][0]}, {z["screen"][1]});
const FOCUS2 = cam({zoom_peak + 0.15}, {z["focus"][0] * W:.1f}, {z["focus"][1] * H:.1f}, {z["screen"][0]}, {z["screen"][1]});
gsap.set("#cam", {{ transformOrigin: "0 0", ...WHOLE(1) }});
{veil_init}
{NL.join(cam_js)}
tl.to("#hook1", {{ opacity: 0, duration: 0.25, ease: "power2.in" }}, {f(t_hook_out)});
tl.fromTo("#hook2", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "power2.out" }}, {f(close_out - 0.02)});
{year_js}
{veil_tl}
{title_js}
{closing_js}
{NL.join(fun_js)}
{NL.join(caps_js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
(ROOT / "video/index.html").write_text(page, encoding="utf-8")
if year: EVENTS.append({"type": "year", "t": round(C["year_start"] - 0.1, 3)})
import shutil as _sh, subprocess as _sp   # the page script must parse: one bad line silently freezes the whole timeline
if _sh.which("node"):
    _js = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]; (ROOT / "build/page_script.js").write_text(_js, encoding="utf-8")
    _r = _sp.run(["node", "--check", str(ROOT / "build/page_script.js")], capture_output=True, text=True)
    if _r.returncode: raise SystemExit("page script does not parse: " + _r.stderr[:800])
(ROOT / "build/events.json").write_text(json.dumps({"total": TOTAL, "events": sorted(EVENTS, key=lambda e: e["t"])}, indent=1))
print("groups", len(groups), "| total", TOTAL, "| painting", f"{W:.0f}x{H:.0f} at top {TOP}", "| zoom", round(t_zoom_start, 2), "-", round(t_zoom_end, 2),
      "| closing caption", f"{close_out - close_in:.2f}s" if closing else "none")
