"""script/video.json + build/timeline.json + build/captions.json -> build/cues.json.
Cues are bound to script line ids (and a spoken word where video.json names one), so a different voice, pause or painting re-times everything."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from textnorm import _word_tokens

ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "build/timeline.json").read_text())
words = json.loads((ROOT / "build/captions.json").read_text())["words"]
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
L = {l["id"]: l for l in tl["lines"]}


def word(line, tok, last=False):
    """first (or last) whisper word in the line whose spoken tokens contain tok"""
    hits = [w for w in words if w["line"] == line and tok.lower() in _word_tokens(w["word"])]
    if not hits: raise SystemExit(f"cue word '{tok}' not found in line {line} (whisper heard: {[w['word'] for w in words if w['line'] == line]})")
    return hits[-1] if last else hits[0]


c = {}
z = cfg["zoom"]
c["look_at_start"] = L[z["line"]]["start"]          # zoom begins as the line begins
c["hand_word_end"] = L[z["line"]]["end"]            # zoom is fully on the detail by the end of the line
if z.get("pullback_line"): c["daylight_march_end"] = L[z["pullback_line"]]["end"]
else: c["daylight_march_end"] = c["hand_word_end"] + 2.0
if cfg.get("year"): c["year_start"] = word(cfg["year"]["line"], cfg["year"]["word"])["start"]
if cfg.get("title_card"):
    c["title_start"] = L[cfg["title_card"]["line"]]["start"]; c["cocq_end"] = L[cfg["title_card"]["line"]]["end"]
v = cfg.get("veil")
if v:
    c["varnish_start"] = word(v["darken_from"]["line"], v["darken_from"]["word"])["start"]
    c["midnight_start"] = word(v["darken_peak"]["line"], v["darken_peak"]["word"])["start"]
    c["midnight_end"] = word(v["darken_peak"]["line"], v["darken_peak"]["word"])["end"]
    c["there_end"] = L[v["wipe_line"]]["end"]
    c["dirt_start"] = word(v["return"]["line"], v["return"]["word"])["start"]
c["punchline_end"] = tl["lines"][-1]["end"]
c["closing_start"] = L[cfg["closing"]["from_line"]]["start"] if cfg.get("closing") else None
c["total_duration"] = tl["total_duration"]
c["lines"] = tl["lines"]; c["pauses"] = tl["pauses"]
c["long_pauses"] = [p for p in tl["pauses"] if p["ms"] >= 600]
for k in c:
    if isinstance(c[k], float): c[k] = round(c[k], 3)
(ROOT / "build/cues.json").write_text(json.dumps(c, indent=2))
print({k: v for k, v in c.items() if isinstance(v, float)})
