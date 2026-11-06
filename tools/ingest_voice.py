"""Ingest an externally generated voice track (ElevenLabs/Higgsfield) into the pipeline.
audio/voice/voice_eleven.wav + script/script.json -> audio/voice/voice_dry.wav, build/timeline.json, build/captions.json.
1. Find speech bursts (-40 dBFS, gaps < 300 ms merged). 2. Transcribe each burst on its own (whole-track whisper timestamps drift
around pauses). 3. Align words to script lines with difflib. Line starts/ends and pauses are therefore measured from the real audio."""
import json, re, difflib
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
LEAD, TAIL, PAD = 0.15, 0.30, 0.12   # first word at LEAD (brief: voice by 0.25 s)
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))
TAIL = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8")).get("end_hold", TAIL) if (ROOT / "script/video.json").exists() else TAIL   # silent end hold, set per painting in video.json
v, sr = sf.read(ROOT / "audio/voice/voice_eleven.wav", dtype="float32"); v = v if v.ndim == 1 else v.mean(1)
assert sr == SR

FR = 480; env = np.sqrt((v[: len(v) // FR * FR].reshape(-1, FR) ** 2).mean(1)); loud = env > 10 ** (-40 / 20)
bursts, i = [], 0
while i < len(loud):
    if loud[i]:
        j = i
        while j < len(loud) and (loud[j] or loud[j:j + 30].any()): j += 1
        while j > i and not loud[j - 1]: j -= 1
        bursts.append((i * 0.010, j * 0.010)); i = j
    else: i += 1
t0 = bursts[0][0]; shift = LEAD - t0
v = v[int(-shift * SR):] if shift < 0 else np.concatenate([np.zeros(int(shift * SR), np.float32), v])
bursts = [(a + shift, b + shift) for a, b in bursts]
tot_voice = len(v) / SR

m = WhisperModel("base.en", device="cpu", compute_type="int8")
W = []
for a, b in bursts:
    s0 = max(0.0, a - PAD); seg = v[int(s0 * SR): int(min(tot_voice, b + PAD) * SR)]
    segs, _ = m.transcribe(resample_poly(seg, 16000, SR).astype("float32"), word_timestamps=True, language="en",
                           vad_filter=False, condition_on_previous_text=False)
    for s in segs:
        for x in s.words: W.append((x.word.strip(), min(max(s0 + x.start, a), b), min(max(s0 + x.end, a), b)))

sys_path = str(Path(__file__).parent)
import sys
if sys_path not in sys.path: sys.path.insert(0, sys_path)
from textnorm import tokens_with_owner
S, owner_line = [], []
for l in script["lines"]:
    ts, _ = tokens_with_owner(l["text"].split())
    S += ts; owner_line += [l["id"]] * len(ts)
T, owner_word = tokens_with_owner([w[0] for w in W])
sm = difflib.SequenceMatcher(None, S, T, autojunk=False)
hit = {}
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        w = W[owner_word[blk.b + k]]
        lst = hit.setdefault(owner_line[blk.a + k], [])
        if w not in lst: lst.append(w)
missing = [l["id"] for l in script["lines"] if l["id"] not in hit]
if missing: raise SystemExit(f"could not align lines: {missing}")

lines = []
for l in script["lines"]:
    h = hit[l["id"]]; s, e = min(x[1] for x in h), max(x[2] for x in h)
    lines.append({"id": l["id"], "beat": l["beat"], "text": l["text"], "start": round(s, 3), "end": round(e, 3), "duration": round(e - s, 3)})
# words whisper hears differently from the script (names) fall out of the alignment: a line that is last in its burst runs to the burst end,
# and a line that is first in its burst starts at the burst start
def burst_at(t): return min(bursts, key=lambda x: 0 if x[0] - 0.02 <= t <= x[1] + 0.02 else min(abs(t - x[0]), abs(t - x[1])))
raw = [(l["start"], l["end"]) for l in lines]
for i, l in enumerate(lines):
    Be, Bs = burst_at(raw[i][1]), burst_at(raw[i][0])
    if i + 1 == len(lines) or raw[i + 1][0] > Be[1] + 0.02: l["end"] = round(Be[1], 3)
    if i == 0 or raw[i - 1][1] < Bs[0] - 0.02: l["start"] = round(Bs[0], 3)
    l["duration"] = round(l["end"] - l["start"], 3)
for a, b in zip(lines, lines[1:]):
    if b["start"] < a["end"]: b["start"] = a["end"]; b["duration"] = round(b["end"] - b["start"], 3)
items = [{"type": "pause", "kind": "lead_in", "start": 0.0, "end": lines[0]["start"], "ms": int(lines[0]["start"] * 1000), "beat": None}]
pauses = []
for i, l in enumerate(lines):
    items.append({"type": "speech", "line": l["id"], "clause": 0, "text": l["text"], "start": l["start"], "end": l["end"]})
    nxt = lines[i + 1]["start"] if i + 1 < len(lines) else tot_voice
    ms = int(round((nxt - l["end"]) * 1000))
    if ms >= 60 or i + 1 == len(lines):
        p = {"type": "pause", "kind": "line", "after": l["id"], "beat": l["beat"], "start": l["end"], "end": round(nxt, 3), "ms": ms, "tail_reverb": False}
        items.append(p); pauses.append(p)
sf.write(ROOT / "audio/voice/voice_dry.wav", v.astype(np.float32), SR)
tl = {"voice_duration": round(tot_voice, 3), "tail": TAIL, "source": "elevenlabs", "lines": lines, "pauses": pauses, "items": items, "seed": None}
tl["total_duration"] = round(tl["voice_duration"] + TAIL, 3)
(ROOT / "build/timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
words = [{"line": next((l["id"] for l in lines if l["start"] - 0.02 <= w[1] <= l["end"] + 0.02), None), "word": w[0], "start": round(w[1], 3), "end": round(w[2], 3)} for w in W]
(ROOT / "build/captions.json").write_text(json.dumps({"source": "elevenlabs per-burst", "words": words}, indent=2), encoding="utf-8")
for l in lines: print(f"{l['id']:4} {l['beat']:9} {l['start']:6.2f}-{l['end']:6.2f}")
print("bursts", len(bursts), "| voice", tl["voice_duration"], "total", tl["total_duration"], "| pauses>=600ms:", sum(1 for p in pauses if p["ms"] >= 600))
