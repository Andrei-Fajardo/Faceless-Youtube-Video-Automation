"""Reproducible mix + master: voice + ambient + SFX -> out/review/audio_only.wav (-14 LUFS stereo, TP <= -1 dBTP).
The ElevenLabs voice is NOT processed: no EQ, no compression, no de-ess, no limiter on the voice itself.
Loudness comes from one gain on the master bus plus a transparent peak catch there.
Run order: ingest_voice.py -> edit_voice.py -> make_cues.py -> sfx.py -> mix.py"""
import json, os, re, subprocess
from pathlib import Path
import numpy as np, soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + os.environ["PATH"]
SR = 48000
cues = json.loads((ROOT / "build/cues.json").read_text())
tl = json.loads((ROOT / "build/timeline.json").read_text())
total = cues["total_duration"]
mixdir = ROOT / "audio/mix"; mixdir.mkdir(parents=True, exist_ok=True)
qa = ROOT / "build/qa"; qa.mkdir(parents=True, exist_ok=True)
TARGET = -14.5   # LUFS (stereo). -14 +/- 1 is the brief; -14.5 keeps the peak catch gentler on the untouched voice
db = lambda x: 20 * np.log10(max(x, 1e-9))


def ff(*a):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-1500:])
    return r.stderr


def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = r[r.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1)), s


# 1) voice
if tl.get("source", "").startswith("elevenlabs"):
    VOICE = None    # untouched
else:               # Kokoro-only humanizing chain (kept for the old pipeline)
    VOICE = ("highpass=f=75,acompressor=threshold=-24dB:ratio=3:attack=15:release=160:makeup=3,"
             "deesser=i=0.4:m=0.5:f=0.5,equalizer=f=3500:t=q:w=1:g=1.5,lowpass=f=12500,"
             "aecho=0.9:0.92:35|62:0.09|0.05,alimiter=limit=0.35:attack=5:release=80:level=disabled")
if VOICE: ff("-i", str(ROOT / "audio/voice/voice_dry.wav"), "-af", VOICE, "-ar", str(SR), str(mixdir / "voice_proc.wav"))
else: ff("-i", str(ROOT / "audio/voice/voice_dry.wav"), "-ar", str(SR), "-c:a", "pcm_f32le", str(mixdir / "voice_proc.wav"))
v, _ = sf.read(mixdir / "voice_proc.wav"); v = v if v.ndim == 1 else v.mean(1)
vpeak = np.abs(v).max()
fr = v[: len(v) // 4800 * 4800].reshape(-1, 4800); rms = np.sqrt((fr ** 2).mean(1)); speech = rms[rms > 10 ** (-45 / 20)]
vrms = np.sqrt((speech ** 2).mean())
print(f"voice (untouched) peak {db(vpeak):.1f} dBFS, speech rms {db(vrms):.1f} dBFS")

# 2) SFX stem, placed on cues. Levels are dB under the voice PEAK (louder than before: impact -1, whooshes -3 to -6).
# Levels are the effect's own RMS relative to the voice's average speech RMS (NOT its peak: this voice has a ~19.6 dB peak-to-average gap,
# so peak-relative levels put effects at or above the voice level). In pauses they are loud; the sidechain below ducks them under speech.
SFX = {  # name: (start time, dB re voice speech RMS, in the clear). Only these two, by request; the ambient bed below stays.
    "impact":       (0.0, -2),                                  # small boom/pop in the first second
    "whoosh_zoom":  (cues["look_at_start"] - 0.78, -3),         # the fade-in warp at ~4 s, into the zoom on 'Look at the captain's hand'
}
stem = np.zeros(int(total * SR) + SR, dtype=np.float32); placed = {}
for name, (t, rel) in SFX.items():
    x, _ = sf.read(ROOT / "audio/sfx" / f"{name}.wav"); x = x.astype(np.float32)
    act = np.abs(x) > 0.1 * np.abs(x).max(); rms_act = np.sqrt((x[act] ** 2).mean())
    x = x / rms_act * (vrms * 10 ** (rel / 20))
    i = int(max(t, 0) * SR); stem[i:i + len(x)] += x[: len(stem) - i]; placed[name] = (round(t, 2), f"{rel} dB re voice RMS", round(db(np.abs(x).max()), 1))
auto = ROOT / "audio/mix/sfx_auto.wav"   # tools/sound_design.py: the full effects stem (replaces the two fixed effects above)
if auto.exists():
    a_, _ = sf.read(auto); a_ = a_.astype(np.float32); stem = np.zeros(int(total * SR) + SR, np.float32); stem[:min(len(stem), len(a_))] = a_[:len(stem)]
    placed = {"auto stem": str(auto.name)}
sf.write(mixdir / "sfx_stem.wav", stem, SR); print("sfx placed (start s, level, peak dBFS):", placed)

# 3) ambient: ~20 dB under speech level; gentle 1-4 kHz cut on the BED only. Rises +2.5 dB in long pauses.
amb, _ = sf.read(ROOT / "audio/ambient.wav"); amb = amb.astype(np.float32)[: int(total * SR) + SR]
_mx = json.loads((ROOT / 'script/video.json').read_text(encoding='utf-8')).get('mix', {}) if (ROOT / 'script/video.json').exists() else {}   # per-film bed level (horror runs a louder bed)
amb = amb / np.sqrt((amb ** 2).mean()) * (vrms * 10 ** (_mx.get('ambient_db', -20) / 20))
pad_f = ROOT / "audio/music_bed.wav"   # tools/sound_design.py: soft music pad, already levelled against the voice; ducked with the bed
if pad_f.exists():
    pad, _ = sf.read(pad_f); pad = pad.astype(np.float32)[: len(amb)]; amb[: len(pad)] += pad
env = np.zeros(len(amb)); RAMP = int(0.25 * SR)
for p in cues["long_pauses"]:
    a, b = int(p["start"] * SR), int(p["end"] * SR); r = min(RAMP, (b - a) // 2)
    seg = np.ones(b - a); seg[:r] = np.linspace(0, 1, r); seg[-r:] = np.linspace(1, 0, r)
    env[a:b] = np.maximum(env[a:b], seg)
amb = amb * 10 ** (_mx.get('ambient_pause_boost_db', 2.5) * env / 20)
sf.write(mixdir / "amb_pre.wav", amb, SR)

# 4) duck the bed (never the voice) with a sidechain keyed from the voice, then sum
GRAPH = ("[1:a]equalizer=f=2200:t=h:w=3000:g=-5[a0];[0:a]asplit=3[v1][v2][v3];"
         f"[a0][v1]sidechaincompress=threshold={vrms * 10 ** (-2.3 / 20):.4f}:ratio=3.5:attack=20:release=400:makeup=1,asplit[ad][ad2];"
         f"[2:a][v3]sidechaincompress=threshold={vrms * 10 ** (-14 / 20):.4f}:ratio=6:attack=8:release=260:makeup=1,asplit[sd][sd2];"
         f"[v2][ad][sd]amix=inputs=3:normalize=0:duration=longest,atrim=0:{total},asetpts=N/SR/TB,pan=stereo|c0=c0|c1=c0[m]")  # dual-mono stereo: what players measure
ff("-i", str(mixdir / "voice_proc.wav"), "-i", str(mixdir / "amb_pre.wav"), "-i", str(mixdir / "sfx_stem.wav"),
   "-filter_complex", GRAPH, "-map", "[m]", "-ar", str(SR), "-c:a", "pcm_f32le", str(mixdir / "premaster.wav"),
   "-map", "[ad2]", "-ar", str(SR), str(mixdir / "amb_ducked.wav"), "-map", "[sd2]", "-ar", str(SR), str(mixdir / "sfx_ducked.wav"))

# 5) master: one gain to reach -14 LUFS, then a lookahead peak catch at -1.5 dBFS. No EQ, no compression. Iterate the gain
#    until the limited result measures on target.
out = ROOT / "out/review"; out.mkdir(parents=True, exist_ok=True)
I0, P0, _ = measure(mixdir / "premaster.wav")
gain = TARGET - I0
for k in range(5):
    ff("-i", str(mixdir / "premaster.wav"), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.75:attack=7:release=70:level=disabled",
       "-ar", str(SR), "-c:a", "pcm_s16le", str(out / "audio_only.wav"))
    I, TP, summary = measure(out / "audio_only.wav")
    print(f"master pass {k}: gain {gain:+.2f} dB -> {I} LUFS, {TP} dBFS")
    if abs(I - TARGET) <= 0.2 and TP <= -1.2: break
    gain += (TARGET - I)
peak_in = P0 + gain
print(f"premaster peak {P0} dBFS + gain {gain:+.2f} dB = {peak_in:+.1f} dBFS before the peak catch (ceiling -1.5): peaks reduced by up to {max(0.0, peak_in + 1.5):.1f} dB")
(qa / "loudness.txt").write_text(summary, encoding="utf-8")

# 6) ducking depth check: bed level while the voice speaks
ad, _ = sf.read(mixdir / "amb_ducked.wav"); ap, _ = sf.read(mixdir / "amb_pre.wav")
n = min(len(ad), len(ap), len(v)); w = 4800
act = np.array([np.sqrt((v[i:i + w] ** 2).mean()) > 10 ** (-40 / 20) for i in range(0, n - w, w)])
rd = np.array([np.sqrt((ad[i:i + w] ** 2).mean()) for i in range(0, n - w, w)]); rp = np.array([np.sqrt((ap[i:i + w] ** 2).mean()) for i in range(0, n - w, w)])
duck = db(np.mean(rd[act] / rp[act])); print(f"ambient ducking while voice speaks: {duck:.1f} dB (target -4 to -6)")
(qa / "loudness.txt").write_text(summary + f"\nAmbient ducking while voice speaks: {duck:.1f} dB\nVoice: untouched (no EQ/compression/de-ess/limiter on the voice).\n", encoding="utf-8")
