"""Stage 2b: synthesize every script line separately -> trim -> pauses -> audio/voice/voice_dry.wav
and build/timeline.json (line starts/ends, from the audio itself)."""
import json, sys
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro import KPipeline

sys.path.insert(0, str(Path(__file__).parent))
from tts_common import ROOT, SR_OUT, synth

cfg = json.loads((ROOT / "tools" / "voice_config.json").read_text(encoding="utf-8"))
script = json.loads((ROOT / "script" / "script.json").read_text(encoding="utf-8"))

def trim(a, thr_db=-45.0, pad=0.02):
    thr = 10 ** (thr_db / 20)
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0: return a
    s = max(0, idx[0] - int(pad * SR_OUT)); e = min(len(a), idx[-1] + int(pad * SR_OUT))
    a = a[s:e].copy(); f = int(0.005 * SR_OUT)
    a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
    return a

pipe = KPipeline(lang_code="a")
(ROOT / "audio" / "voice" / "lines").mkdir(parents=True, exist_ok=True)
t = cfg["lead_in"]; parts = [np.zeros(int(t * SR_OUT), dtype=np.float32)]; lines = []
for i, l in enumerate(script["lines"]):
    ov = cfg["line_overrides"].get(l["id"], {})
    clip = trim(synth(pipe, ov.get("text", l["narration"]), cfg["voice"], ov.get("speed", cfg["speed"])))
    sf.write(ROOT / "audio" / "voice" / "lines" / f"{l['id']}.wav", clip, SR_OUT)
    gap = cfg["pause_before"].get(l["id"], cfg["pause_after_line"] if i else 0.0)
    if gap and i:
        parts.append(np.zeros(int(gap * SR_OUT), dtype=np.float32)); t += gap
    dur = len(clip) / SR_OUT
    lines.append({"id": l["id"], "start": round(t, 3), "end": round(t + dur, 3), "duration": round(dur, 3)})
    parts.append(clip); t += dur
voice = np.concatenate(parts)
sf.write(ROOT / "audio" / "voice" / "voice_dry.wav", voice, SR_OUT)
(ROOT / "build").mkdir(exist_ok=True)
tl = {"voice_duration": round(len(voice) / SR_OUT, 3), "tail": 1.2, "lines": lines}
tl["total_duration"] = round(tl["voice_duration"] + tl["tail"], 3)
(ROOT / "build" / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
for x in lines: print(x["id"], x["start"], x["end"], x["duration"])
print("voice", tl["voice_duration"], "total", tl["total_duration"])
