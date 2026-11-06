"""How loud are the bed and each SFX relative to the voice WHILE the voice speaks? Read-only."""
import json, os, subprocess
from pathlib import Path
import numpy as np, soundfile as sf
ROOT = Path(__file__).resolve().parent.parent; SR = 48000
os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
db = lambda x: 20 * np.log10(max(float(x), 1e-12))
rms = lambda x: np.sqrt((x ** 2).mean()) if len(x) else 0.0
cues = json.loads((ROOT / "build/cues.json").read_text()); tl = json.loads((ROOT / "build/timeline.json").read_text())
v, _ = sf.read(ROOT / "audio/mix/voice_proc.wav", dtype="float32"); v = v if v.ndim == 1 else v.mean(1)
amb, _ = sf.read(ROOT / "audio/mix/amb_ducked.wav", dtype="float32"); amb = amb if amb.ndim == 1 else amb.mean(1)
sfx, _ = sf.read(ROOT / "audio/mix/sfx_ducked.wav", dtype="float32"); sfx = sfx if sfx.ndim == 1 else sfx.mean(1)
n = min(len(v), len(amb), len(sfx)); v, amb, sfx = v[:n], amb[:n], sfx[:n]
speech = np.zeros(n, bool)
for l in tl["lines"]: speech[int(l["start"] * SR): int(l["end"] * SR)] = True
vs = rms(v[speech])
print(f"voice speech RMS {db(vs):.1f} dBFS, peak {db(np.abs(v).max()):.1f} dBFS (crest {db(np.abs(v).max()) - db(vs):.1f} dB)")
print(f"ambient bed during speech: {db(rms(amb[speech])) - db(vs):+.1f} dB re voice RMS")
# per-SFX level vs voice RMS, measured only over the samples where that SFX overlaps speech
SF = {"impact": 0.0, "whoosh_zoom": cues["look_at_start"] - 0.78, "whoosh_pull": cues["daylight_march_end"] + 0.05, "swell": cues["varnish_start"],
      "wipe": cues["there_end"] - 0.7, "whoosh_title": cues["title_start"] - 0.75, "settle": cues["dirt_start"]}
print("\nSFX (pre-master) vs voice RMS, over their overlap with speech:")
for name, t in SF.items():
    x, _ = sf.read(ROOT / "audio/sfx" / f"{name}.wav", dtype="float32"); a = int(max(t, 0) * SR); b = a + len(x)
    m = speech[a:b]; ov = m.mean() * 100
    if m.sum() < SR * 0.05: print(f"  {name:13} overlaps speech {ov:4.0f}% (essentially in pauses)"); continue
    seg = sfx[a:b][m]; print(f"  {name:13} overlaps speech {ov:4.0f}% | SFX RMS there {db(rms(seg)) - db(vs):+5.1f} dB re voice RMS")
# the swell is the long one: level in 1 s windows while the voice speaks
a = int(cues["varnish_start"] * SR); print("\nswell level vs voice, per second (S4a..S4c):")
for k in range(0, int((cues["midnight_end"] - cues["varnish_start"])), 1):
    s0 = a + k * SR; seg = slice(s0, s0 + SR)
    if speech[seg].mean() > 0.4: print(f"  t={s0 / SR:5.1f}s swell {db(rms(sfx[seg])) - db(rms(v[seg]) + 1e-9):+5.1f} dB re voice RMS in that second")
# limiter distortion on the voice alone: same gain + same limiter vs plain gain
gain_db = 7.8
x = np.stack([v, v], 1); sf.write("tmp_v.wav", x, SR, subtype="FLOAT")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "tmp_v.wav", "-af", f"volume={gain_db}dB,alimiter=limit=0.75:attack=7:release=70:level=disabled", "-c:a", "pcm_f32le", "tmp_vl.wav"])
vl, _ = sf.read("tmp_vl.wav", dtype="float32"); vl = vl.mean(1); ref = v * 10 ** (gain_db / 20); k = min(len(vl), len(ref))
d = vl[:k] - ref[:k]; print(f"\nmaster peak catch on the voice alone: distortion residual {db(rms(d[speech[:k]])) - db(rms(ref[:k][speech[:k]])):.1f} dB re voice; frames touched {(np.abs(ref[:k]) > 0.75).reshape(-1)[:k//480*480].reshape(-1,480).any(1).mean() * 100:.1f}%")
os.remove("tmp_v.wav"); os.remove("tmp_vl.wav")
