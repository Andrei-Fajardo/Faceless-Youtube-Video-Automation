"""open_check.py: the first-3-seconds retention check (the rules from the 2026-11-02 swiped-away audit). Run after make_cues + build_video.
  open_check.py            prints PASS/FAIL per rule, exit code 1 if any fails
Rules (YouTube showed 56.7% swiped away; the first Shorts sat on a still picture for ~3 s with a 7-8 word hook and a 0.6-0.75 s pause):
  1. Hook of 5 words or fewer, spoken in 1.8 s or less.
  2. Silence after the hook 0.35 s or less.
  3. The first real fact (line S2) starts by 2.4 s.
  4. At least 2 visual events (a cut, stamp or number pop) before 3.0 s, the first by 1.2 s.
  5. On-screen hook text at least 110 px (video.json hook_size)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "build/timeline.json").read_text()); sc = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8")); L = {l["id"]: l for l in tl["lines"]}
words = {}
for w in json.loads((ROOT / "build/captions.json").read_text())["words"]: words.setdefault(w["line"], []).append(w)
s1, s2 = tl["lines"][0], tl["lines"][1]
hook_words = len(sc["lines"][0]["text"].split()); gap = s2["start"] - s1["end"]
ev = []
for k, sh in enumerate(cfg["fun"].get("shots", [])):
    if k == 0 or sh.get("transition") != "cut": continue          # shot 0 is frame 0 itself, not a change
    at = sh.get("at", {}); line = sh.get("line") or at.get("line")
    if not line: continue
    base = L[line]["start"]
    if at.get("word"):
        w = next((w for w in words.get(line, []) if at["word"].lower() in w["word"].lower()), None); base = (w["start"] - 0.05) if w else base
    t = base + at.get("dt", 0.0)
    if t > 0.05: ev.append(("cut", round(t, 2)))          # a cut at t=0 is just frame 0
for pp in cfg["fun"].get("pops", []):
    ln = L[pp["line"]]; t = pp.get("at")
    if t is None:
        w = next((w for w in words.get(pp["line"], []) if pp.get("word", "\0").lower() in w["word"].lower()), None); t = (w["start"] - 0.05) if w else ln["start"]
    ev.append((pp.get("kind", "pop"), round(t, 2)))
early = sorted(t for _, t in ev if t < 3.0)
rows = [("Hook words <= 5", hook_words, hook_words <= 5),
        ("Hook spoken in <= 1.8 s", round(s1["end"] - s1["start"], 2), s1["end"] - s1["start"] <= 1.8),
        ("Silence after hook <= 0.35 s", round(gap, 2), gap <= 0.35),
        ("First fact (S2) starts by 2.4 s", round(s2["start"], 2), s2["start"] <= 2.4),
        ("2+ visual events before 3.0 s", early, len(early) >= 2),
        ("First visual event by 1.2 s", early[:1], bool(early) and early[0] <= 1.2),
        ("Hook text >= 110 px", cfg.get("hook_size", 80), cfg.get("hook_size", 80) >= 110)]
for n, v, ok in rows: print(("PASS " if ok else "FAIL ") + f"{n}: {v}")
sys.exit(0 if all(ok for *_, ok in rows) else 1)
