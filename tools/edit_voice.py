"""Edit the ingested ElevenLabs take to hit the pacing gates, using only ffmpeg + measured times.
- speech segments (between pauses) are time-stretched with rubberband (pitch preserved) by 1/TEMPO
- every pause is reset to the script's designed pause_after_ms
- all line times, pauses and caption words are re-mapped onto the new audio (no re-transcription)
Run after ingest_voice.py. Idempotent: always starts from build/timeline_ingest.json + audio/voice/voice_ingest.wav."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
SR = 48000
PAD_TO = float(sys.argv[sys.argv.index("--pad-to") + 1]) if "--pad-to" in sys.argv else None   # silence-only mode: lengthen the dramatic pauses to reach this total duration; the voice is copied through untouched
NO_STRETCH = "--no-stretch" in sys.argv    # silence-only: every pause is reset to the script's pause_after_ms (longer OR shorter); the speech is copied through untouched
TEMPO = 1.0 if (PAD_TO or NO_STRETCH) else 0.89          # < 1 slows speech; 0.89 puts the take just under 2.5 words/sec
FADE = int(0.008 * SR)

tl_p, wav_p = ROOT / "build/timeline_ingest.json", ROOT / "audio/voice/voice_ingest.wav"
tl_now = json.loads((ROOT / "build/timeline.json").read_text())
if tl_now.get("source") == "elevenlabs":              # fresh ingest: remember it as the pristine input
    shutil.copy(ROOT / "build/timeline.json", tl_p); shutil.copy(ROOT / "audio/voice/voice_dry.wav", wav_p)
    shutil.copy(ROOT / "build/captions.json", ROOT / "build/captions_ingest.json")
tl = json.loads(tl_p.read_text()); cap = json.loads((ROOT / "build/captions_ingest.json").read_text())
script = {l["id"]: l for l in json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]}
v, _ = sf.read(wav_p, dtype="float32")

# pauses to replace: every line pause >= 60 ms; target = the script's designed pause_after_ms
pz = [p for p in tl["pauses"] if p["ms"] >= 60]
cuts, pos = [], 0.0
segs = []   # (orig_start, orig_end, kind, target_s)
extra = {}
if PAD_TO:   # spread the missing seconds evenly over every pause of 400 ms or more (max +0.5 s each); any remainder goes to the final hold
    need = max(0.0, PAD_TO - tl["total_duration"])
    cand = [p for p in pz if p["ms"] >= 400 and p is not pz[-1]]
    per = min(0.5, need / max(1, len(cand)))
    extra = {id(p): per for p in cand}; extra[id(pz[-1])] = max(0.0, need - per * len(cand))
for p in pz:
    tgt = (p["ms"] / 1000 + extra.get(id(p), 0.0)) if PAD_TO else script[p["after"]]["pause_after_ms"] / 1000
    segs.append((pos, p["start"], "speech", None)); segs.append((p["start"], p["end"], "pause", tgt)); pos = p["end"]
if pos < len(v) / SR - 0.01: segs.append((pos, len(v) / SR, "speech", None))

def stretch(x):
    if TEMPO == 1.0: return x
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.wav", Path(d) / "b.wav"; sf.write(a, x, SR)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(a), "-af",
                            f"rubberband=tempo={TEMPO}:transients=crisp:detector=compound:phase=laminar:window=standard:formant=preserved:pitchq=quality", str(b)], capture_output=True, text=True)
        if r.returncode: raise SystemExit(r.stderr)
        y, _ = sf.read(b, dtype="float32"); return y

out, new_t, mapping = [np.zeros(int(0.0))], 0.0, []   # mapping: (orig_start, orig_end, new_start, new_end)
lead = tl["pauses"][0] if False else None
# lead-in: everything before the first segment is already included in segs[0] (starts at 0.0)
for a, b, kind, target in segs:
    x = v[int(a * SR): int(b * SR)].copy()
    if kind == "speech":
        y = stretch(x)
        if len(y) > 2 * FADE: y[:FADE] *= np.linspace(0, 1, FADE) if a > 0.2 else 1; y[-FADE:] *= np.linspace(1, 0, FADE)
    else:
        n = int(round(target * SR)); y = np.zeros(n, np.float32); k = min(n, len(x)); y[:k] = x[:k]
        if k == n and n > FADE: y[-FADE:] *= np.linspace(1, 0, FADE)
    mapping.append((a, b, new_t, new_t + len(y) / SR, kind)); out.append(y); new_t += len(y) / SR
voice = np.concatenate(out)
sf.write(ROOT / "audio/voice/voice_dry.wav", voice, SR)

def mp(t):
    for a, b, na, nb, kind in mapping:
        if a - 1e-6 <= t <= b + 1e-6: return na + (t - a) / (b - a) * (nb - na) if b > a else na
    return mapping[-1][3]
lines = [dict(l, start=round(mp(l["start"]), 3), end=round(mp(l["end"]), 3)) for l in tl["lines"]]
for l in lines: l["duration"] = round(l["end"] - l["start"], 3)
pauses = []
for p in tl["pauses"]:
    if p["ms"] >= 60:
        a, b, na, nb, _ = next(m for m in mapping if m[4] == "pause" and abs(m[0] - p["start"]) < 1e-6)
        pauses.append(dict(p, start=round(na, 3), end=round(nb, 3), ms=int(round((nb - na) * 1000))))
items = [{"type": "pause", "kind": "lead_in", "start": 0.0, "end": lines[0]["start"], "ms": int(lines[0]["start"] * 1000), "beat": None}]
for l in lines:
    items.append({"type": "speech", "line": l["id"], "clause": 0, "text": l["text"], "start": l["start"], "end": l["end"]})
    pp = next((p for p in pauses if p["after"] == l["id"]), None)
    if pp: items.append(pp)
words = [dict(w, start=round(mp(w["start"]), 3), end=round(mp(w["end"]), 3)) for w in cap["words"]]
tl2 = {"voice_duration": round(len(voice) / SR, 3), "tail": tl["tail"], "source": "elevenlabs-edited", "tempo": TEMPO,
       "lines": lines, "pauses": pauses, "items": items, "seed": None}
tl2["total_duration"] = round(tl2["voice_duration"] + tl2["tail"], 3)
(ROOT / "build/timeline.json").write_text(json.dumps(tl2, indent=2), encoding="utf-8")
(ROOT / "build/captions.json").write_text(json.dumps({"source": "elevenlabs-edited", "words": words}, indent=2), encoding="utf-8")
print("tempo", TEMPO, "| voice", tl2["voice_duration"], "total", tl2["total_duration"], "| pauses", [p["ms"] for p in pauses])
