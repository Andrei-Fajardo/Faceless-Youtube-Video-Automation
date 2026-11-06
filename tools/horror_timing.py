"""Named times for the horror builders (build_monitor.py, monitor_sound.py). A time spec is one of:
  a number            "0.2"            seconds
  a line              "S3"             start of that spoken line (script id)
  a line word         "S3:whispering"  start of that spoken word (whisper timing)
  a line end          "S3>"            end of that line
  a cue               "stop"           a name from video.json monitor.cues (may itself be a spec)
  the film end        "TOTAL"          the raw timeline length
plus an optional offset, e.g. "stop+0.5", "S13-0.1", "tear-0.02", "TOTAL-0.35"."""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from textnorm import _word_tokens

ROOT = Path(__file__).resolve().parent.parent


class Timing:
    def __init__(self, cues=None):
        tl = json.loads((ROOT / "build/timeline.json").read_text())
        self.cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
        self.L = {l["id"]: l for l in tl["lines"]}
        self.TOTAL = tl["total_duration"]
        self.raw = dict(cues or {})
        self.memo = {}

    def word(self, line, tok):
        for w in self.cap:
            if w["line"] == line and tok.lower() in _word_tokens(w["word"]): return w
        raise SystemExit(f"word '{tok}' not found in line {line}")

    def at(self, spec):
        if isinstance(spec, (int, float)): return float(spec)
        s = str(spec).strip()
        if re.fullmatch(r"[\d.]+", s): return float(s)
        m = re.fullmatch(r"([A-Za-z]\w*)(?::(\w+)|(>))?([+-][\d.]+)?", s)
        if not m: raise SystemExit(f"bad time spec {spec!r}")
        base, word, end, off = m.group(1), m.group(2), m.group(3), float(m.group(4) or 0)
        if base == "TOTAL" and word is None: t = self.TOTAL
        elif word is None and end is None and base in self.raw: t = self.cue(base)
        elif base in self.L:
            if end: t = self.L[base]["end"]
            elif word: t = self.word(base, word)["start"]
            else: t = self.L[base]["start"]
        else: raise SystemExit(f"unknown time base {base!r} in {spec!r}: not a cue, a script line or TOTAL")
        return t + off

    def cue(self, name):
        if name not in self.memo: self.memo[name] = self.at(self.raw[name])
        return self.memo[name]
