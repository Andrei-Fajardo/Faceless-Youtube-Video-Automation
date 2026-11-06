"""Pacing engine. script.json (beats, speeds, pause_after_ms) -> audio/voice/voice_dry.wav + build/timeline.json.

- Lines split into clauses at commas (unless no_split); each clause is synthesized separately at the line's speed.
- Each clip is trimmed by threshold and given 8 ms fades.
- Designed silences are inserted as data: line pauses (+-15% seeded jitter, capped 1400 ms) and clause gaps (180-250 ms).
- The last word before any pause >= 600 ms gets a short, quiet reverb tail that rings into the silence.
- timeline.json lists speech clips AND pauses as items with start/end, so everything downstream re-times from it.
"""
import json, random, sys
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import fftconvolve, butter, sosfilt

sys.path.insert(0, str(Path(__file__).parent))
from tts_common import ROOT, SR_OUT, synth

SEED = 20261029
MAX_PAUSE_MS = 1400
BEAT_MIN_MS = {"hook": 700, "question": 800, "punchline": 800}  # jitter may not push a pause below its beat range
TAIL_MIN_PAUSE_MS = 600
cfg = json.loads((ROOT / "tools" / "voice_config.json").read_text(encoding="utf-8"))
script = json.loads((ROOT / "script" / "script.json").read_text(encoding="utf-8"))
rng = random.Random(SEED)
sil = lambda sec: np.zeros(int(round(sec * SR_OUT)), dtype=np.float32)


def trim(a, thr_db=-45.0, pad=0.015, fade=0.008):
    idx = np.where(np.abs(a) > 10 ** (thr_db / 20))[0]
    if len(idx):
        a = a[max(0, idx[0] - int(pad * SR_OUT)): min(len(a), idx[-1] + int(pad * SR_OUT))].copy()
    f = int(fade * SR_OUT)
    a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
    return a


def reverb_tail(clip, tail_s=0.35, wet_db=-22.0):
    """Quiet, short tail: convolve the last 250 ms with a decaying, low-passed noise IR; return only what rings past the clip."""
    r = np.random.default_rng(SEED)
    n = int(0.45 * SR_OUT); t = np.arange(n) / SR_OUT
    ir = r.standard_normal(n) * np.exp(-t / 0.10)
    ir = sosfilt(butter(2, 3500, btype="low", fs=SR_OUT, output="sos"), ir)
    seg = clip[-int(0.25 * SR_OUT):]
    wet = fftconvolve(seg, ir)[len(seg): len(seg) + int(tail_s * SR_OUT)]
    if len(wet) == 0 or np.abs(wet).max() == 0: return sil(tail_s)
    wet = wet / np.abs(wet).max() * np.abs(clip).max() * 10 ** (wet_db / 20)
    wet *= np.linspace(1, 0, len(wet)) ** 1.5
    return wet.astype(np.float32)


def split_clauses(line):
    if line.get("no_split"): return [line.get("tts_text", line["text"])]
    src = line.get("tts_text", line["text"])
    return [c.strip().rstrip(",") for c in src.replace(", ", ",|").split("|") if c.strip()]


pipe = None
def get_pipe():
    global pipe
    if pipe is None:
        from kokoro import KPipeline
        pipe = KPipeline(lang_code="a")
    return pipe


(ROOT / "audio" / "voice" / "lines").mkdir(parents=True, exist_ok=True)
t = cfg["lead_in"]
chunks, items, lines, pauses = [sil(t)], [], [], []
items.append({"type": "pause", "kind": "lead_in", "start": 0.0, "end": round(t, 3), "ms": int(t * 1000), "beat": None})
n_lines = len(script["lines"])
for i, line in enumerate(script["lines"]):
    clauses = split_clauses(line)
    line_start = t
    for ci, text in enumerate(clauses):
        clip = trim(synth(get_pipe(), text, cfg["voice"], line["speed"]))
        last_clause = ci == len(clauses) - 1
        base_ms = line["pause_after_ms"] if last_clause else None
        # pause that follows this clip
        if last_clause:
            ms = min(MAX_PAUSE_MS, max(BEAT_MIN_MS.get(line["beat"], 0), round(base_ms * (1 + rng.uniform(-0.15, 0.15)))))
            kind = "line"
        else:
            ms = round(rng.uniform(180, 250)); kind = "clause"
        tail = reverb_tail(clip) if ms >= TAIL_MIN_PAUSE_MS else None
        dur = len(clip) / SR_OUT
        items.append({"type": "speech", "line": line["id"], "clause": ci, "text": text, "start": round(t, 3), "end": round(t + dur, 3)})
        chunks.append(clip); t += dur
        gap = sil(ms / 1000)
        if tail is not None:
            k = min(len(tail), len(gap)); gap[:k] += tail[:k]
        chunks.append(gap)
        p = {"type": "pause", "kind": kind, "after": line["id"], "beat": line["beat"] if kind == "line" else "clause",
             "start": round(t, 3), "end": round(t + ms / 1000, 3), "ms": ms, "tail_reverb": tail is not None}
        items.append(p); pauses.append(p); t += ms / 1000
    lines.append({"id": line["id"], "beat": line["beat"], "text": line["text"], "start": round(line_start, 3),
                  "end": round([x for x in items if x["type"] == "speech" and x["line"] == line["id"]][-1]["end"], 3)})
    sf.write(ROOT / "audio" / "voice" / "lines" / f"{line['id']}.wav", np.concatenate(chunks[-2 * len(clauses):]), SR_OUT)

voice = np.concatenate(chunks)
sf.write(ROOT / "audio" / "voice" / "voice_dry.wav", voice, SR_OUT)
for l in lines: l["duration"] = round(l["end"] - l["start"], 3)
tl = {"voice_duration": round(len(voice) / SR_OUT, 3), "tail": cfg.get("end_tail", 0.4), "seed": SEED,
      "lines": lines, "pauses": pauses, "items": items}
tl["total_duration"] = round(tl["voice_duration"] + tl["tail"], 3)
(ROOT / "build").mkdir(exist_ok=True)
(ROOT / "build" / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
for l in lines: print(f"{l['id']:4} {l['beat']:9} {l['start']:6.2f}-{l['end']:6.2f}")
print("voice", tl["voice_duration"], "total", tl["total_duration"])
