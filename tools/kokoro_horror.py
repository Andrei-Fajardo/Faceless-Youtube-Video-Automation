"""kokoro_horror.py: local Kokoro narration for a horror run (no ElevenLabs).
Per line: Kokoro (voice from tools/voice_config.json) at the line's own speed, trimmed, then pauses from pause_after_ms.
Writes:
  audio/voice/voice_dry.wav   the raw Kokoro take (kept untouched for comparison)
  audio/voice/voice_eleven.wav the processed take, the file tools/ingest_voice.py reads (name kept for the pipeline)
The processing chain is a warmth lift, a presence lift, gentle compression, a short room echo and a limiter (ffmpeg).
Usage: kokoro_horror.py"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_common import ROOT, SR_OUT, synth

cfg = json.loads((ROOT / "tools" / "voice_config.json").read_text(encoding="utf-8"))
script = json.loads((ROOT / "script" / "script.json").read_text(encoding="utf-8"))
VOICE_DIR = ROOT / "audio" / "voice"
LINES_DIR = VOICE_DIR / "lines"
LINES_DIR.mkdir(parents=True, exist_ok=True)
VOICE_DIR.mkdir(parents=True, exist_ok=True)

FX = ",".join([
    "highpass=f=85",
    "equalizer=f=180:t=q:w=1.0:g=2.5",     # warmth
    "equalizer=f=3000:t=q:w=1.2:g=2.0",    # presence
    "acompressor=threshold=-20dB:ratio=2.5:attack=20:release=200:makeup=2",
    "aecho=0.7:0.5:40|80:0.18|0.10",       # short room body
    "alimiter=limit=0.89",
])


def trim(a, thr_db=-45.0, pad=0.02):
    thr = 10 ** (thr_db / 20)
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(pad * SR_OUT)); e = min(len(a), idx[-1] + int(pad * SR_OUT))
    a = a[s:e].copy(); f = int(0.005 * SR_OUT)
    a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
    return a


pipe = KPipeline(lang_code="a")
parts = [np.zeros(int(cfg["lead_in"] * SR_OUT), dtype=np.float32)]
for l in script["lines"]:
    clip = trim(synth(pipe, l["tts_text"], cfg["voice"], l["speed"]))
    sf.write(LINES_DIR / f"{l['id']}.wav", clip, SR_OUT)
    parts.append(clip)
    gap = l.get("pause_after_ms", 700) / 1000.0
    parts.append(np.zeros(int(gap * SR_OUT), dtype=np.float32))
voice = np.concatenate(parts + [np.zeros(int(cfg["end_tail"] * SR_OUT), dtype=np.float32)])
dry = VOICE_DIR / "voice_dry.wav"
sf.write(dry, voice, SR_OUT)
print(f"raw voice {len(voice) / SR_OUT:.2f} s -> {dry.name}")

wet = VOICE_DIR / "voice_eleven.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(dry), "-af", FX, "-ar", str(SR_OUT), "-ac", "1",
                str(wet)], check=True)
print(f"processed voice -> {wet.name} with {FX}")
