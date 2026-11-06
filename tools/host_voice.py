"""host_voice.py: mixed-voice narration for a horror run.
- speaker 'host' lines -> ElevenLabs, ONE paid call for all host lines (same budget ledger and per-run cap as eleven_tts.py)
  + subtle reverb.
- speaker 'narrator' -> Kokoro bm_lewis, unchanged.
- speaker 'child' -> Kokoro af_sky + custom EQ (lighter, more present).
- speaker 'kaiju' -> Kokoro bm_george + custom EQ (deep, cavernous).
Writes audio/voice/lines/<id>.wav, audio/voice/voice_dry.wav (raw Kokoro/ElevenLabs placement, no effects) and
audio/voice/voice_eleven.wav (the combined track that tools/ingest_voice.py reads; name kept for the pipeline).
Usage: host_voice.py [--force]"""
import argparse, hashlib, json, subprocess, sys, urllib.error, urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts_common import ROOT, SR_OUT, synth

ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); args = ap.parse_args()
cfg = json.loads((ROOT / "tools/eleven_config.json").read_text(encoding="utf-8"))
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))
run = json.loads((ROOT / "run.json").read_text())
LINES = ROOT / "audio/voice/lines"; LINES.mkdir(parents=True, exist_ok=True)
(ROOT / "audio/voice").mkdir(parents=True, exist_ok=True)
(ROOT / "audio/eleven-labs").mkdir(parents=True, exist_ok=True)

KOKORO_VOICE = {"narrator": "bm_lewis", "child": "af_sky", "kaiju": "bm_george"}
FX = {
    "host": "aecho=0.8:0.55:70|130:0.14|0.09",                                       # subtle room reverb
    "child": "highpass=f=180,equalizer=f=400:t=q:w=1:g=-3,equalizer=f=2800:t=q:w=1.2:g=3,lowpass=f=8000",
    "kaiju": "equalizer=f=80:t=q:w=1:g=6,equalizer=f=3000:t=q:w=1.4:g=-5,lowpass=f=7000,aecho=0.6:0.4:200:0.12,volume=8dB",
}


def ffilter(src, dst, chain):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", chain, "-ar", str(SR_OUT), "-ac", "1", str(dst)], check=True)


def trim(a, thr_db=-45.0, pad=0.02):
    thr = 10 ** (thr_db / 20)
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(pad * SR_OUT)); e = min(len(a), idx[-1] + int(pad * SR_OUT))
    a = a[s:e].copy(); f = int(0.005 * SR_OUT)
    a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
    return a


# ---- 1. ElevenLabs: all host lines in one call -------------------------------------------------------------------------
host_lines = [l for l in script["lines"] if l["speaker"] == "host"]
host_text = "\n\n".join(l["tts_text"] for l in host_lines)
chars = len(host_text)
ledger_p = ROOT / "eleven_usage.json"
ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {"calls": []}
month = date.today().strftime("%Y-%m")
used_month = sum(c["chars"] for c in ledger["calls"] if c["date"].startswith(month))
calls_this_run = sum(1 for c in ledger["calls"] if c.get("run") == run["slug"])
key_hash = hashlib.sha1(json.dumps([host_text, cfg["voice_id"]]).encode()).hexdigest()[:10]
mp3 = ROOT / "audio/eleven-labs" / f"{run['slug']}_host_{key_hash}.mp3"
if not mp3.exists() or args.force:
    if chars > cfg["max_chars_per_call"]:
        sys.exit(f"STOP: {chars} characters exceeds max_chars_per_call ({cfg['max_chars_per_call']}).")
    if used_month + chars > cfg["monthly_char_budget"]:
        sys.exit(f"STOP: this call would bring the month to {used_month + chars} characters (budget {cfg['monthly_char_budget']}).")
    if calls_this_run >= cfg["max_calls_per_run"]:
        sys.exit(f"STOP: {calls_this_run} paid calls already made for this run (max {cfg['max_calls_per_run']}).")
    key = next((l.split("=", 1)[1].strip().strip("\"'") for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ELEVENLABS_API_KEY=")), "")
    if len(key) < 20:
        sys.exit("STOP: ELEVENLABS_API_KEY missing in .env")
    vs = dict(cfg["voice_settings"]); vs.update(script.get("voice_settings_override", {}))
    body = json.dumps({"text": host_text, "model_id": cfg["model_id"], "voice_settings": vs}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}?output_format={cfg['output_format']}", data=body,
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"STOP: ElevenLabs returned {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}")
    mp3.write_bytes(audio)
    ledger["calls"].append({"date": date.today().isoformat(), "run": run["slug"], "chars": chars, "model": cfg["model_id"], "speed": vs.get("speed"), "hash": key_hash, "part": "host lines only"})
    ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"ElevenLabs host call: {chars} characters; month total {used_month + chars}/{cfg['monthly_char_budget']}")
else:
    print("ElevenLabs cache hit (no characters spent)")

host_wav = ROOT / "audio/voice/host_eleven_raw.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", str(SR_OUT), "-ac", "1", str(host_wav)], check=True)

# split the host take into lines on the largest silence gaps (one gap per line boundary)
a, _ = sf.read(host_wav, dtype="float32")
FR = 480
env = np.sqrt((a[: len(a) // FR * FR].reshape(-1, FR) ** 2).mean(1))
quiet = env < 10 ** (-40 / 20)
gaps, i = [], 0
while i < len(quiet):
    if quiet[i]:
        j = i
        while j < len(quiet) and quiet[j]: j += 1
        gaps.append((j - i, i, j)); i = j
    else:
        i += 1
gaps = [g for g in gaps if g[1] > 0 and g[2] < len(quiet)]
gaps.sort(reverse=True)
cuts = sorted(g[1] + g[0] // 2 for g in gaps[: len(host_lines) - 1])
bounds = [0] + cuts + [len(env)]          # frame indices
host_clips = []
for k, l in enumerate(host_lines):
    seg = a[bounds[k] * FR: bounds[k + 1] * FR]   # frames -> samples
    clip = trim(seg)
    sf.write(LINES / f"{l['id']}.wav", clip, SR_OUT)
    host_clips.append((l, clip))
print(f"host lines split: {len(host_clips)} clips from {len(a) / SR_OUT:.1f} s of ElevenLabs audio")

# ---- 2. Kokoro for narrator, child and kaiju -------------------------------------------------------------------------
pipe = KPipeline(lang_code="a")
clips = {}
for l in script["lines"]:
    if l["speaker"] == "host":
        continue
    raw = trim(synth(pipe, l["tts_text"], KOKORO_VOICE[l["speaker"]], l["speed"]))
    raw_p = LINES / f"{l['id']}_raw.wav"; sf.write(raw_p, raw, SR_OUT)
    out_p = LINES / f"{l['id']}.wav"
    if l["speaker"] in FX:
        ffilter(raw_p, out_p, FX[l["speaker"]])
    else:
        sf.write(out_p, raw, SR_OUT)
    clips[l["id"]] = sf.read(out_p, dtype="float32")[0]

# host lines: reverb applied to the clip itself
for l, clip in host_clips:
    p = LINES / f"{l['id']}_raw.wav"; sf.write(p, clip, SR_OUT)
    ffilter(p, LINES / f"{l['id']}.wav", FX["host"])
    clips[l["id"]] = sf.read(LINES / f"{l['id']}.wav", dtype="float32")[0]

# ---- 3. combined track on the script timing -----------------------------------------------------------------------------
parts = [np.zeros(int(0.15 * SR_OUT), dtype=np.float32)]
for l in script["lines"]:
    parts.append(clips[l["id"]])
    parts.append(np.zeros(int(l.get("pause_after_ms", 700) / 1000 * SR_OUT), dtype=np.float32))
voice = np.concatenate(parts)
sf.write(ROOT / "audio/voice/voice_dry.wav", voice, SR_OUT)
sf.write(ROOT / "audio/voice/voice_eleven.wav", voice, SR_OUT)
print(f"combined voice {len(voice) / SR_OUT:.2f} s -> audio/voice/voice_eleven.wav (host ElevenLabs, others Kokoro + EQ)")
