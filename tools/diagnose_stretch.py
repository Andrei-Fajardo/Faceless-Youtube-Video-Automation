"""Stretch-specific diagnostics: voicing strength, segment length vs expectation, boundary glitches. Read-only."""
import json, os
from pathlib import Path
import numpy as np, soundfile as sf
ROOT = Path(__file__).resolve().parent.parent; SR = 48000; TEMPO = 0.89
tl0 = json.loads((ROOT / "build/timeline_ingest.json").read_text()); tl1 = json.loads((ROOT / "build/timeline.json").read_text())
ing, _ = sf.read(ROOT / "audio/voice/voice_ingest.wav", dtype="float32"); edit, _ = sf.read(ROOT / "audio/voice/voice_dry.wav", dtype="float32")

def voicing(x, a, b):
    """mean normalized autocorrelation peak (80-400 Hz) over loud frames in [a,b]: 1 = clean periodic voice, lower = rough/phasey"""
    seg = x[int(a * SR): int(b * SR)]; N = int(0.040 * SR); H = int(0.010 * SR); vals = []
    for i in range(0, len(seg) - N, H):
        f = seg[i:i + N]; e = np.sqrt((f ** 2).mean())
        if e < 0.02: continue
        f = f - f.mean(); ac = np.correlate(f, f, "full")[N - 1:]; ac = ac / (ac[0] + 1e-12)
        vals.append(ac[int(SR / 400): int(SR / 80)].max())
    return float(np.mean(vals)), len(vals)

# segments exactly as edit_voice.py cuts them: between line pauses >= 60 ms
pz = [p for p in tl0["pauses"] if p["ms"] >= 60]; segs = []; pos = 0.0
for p in pz: segs.append((pos, p["start"])); pos = p["end"]
if pos < len(ing) / SR - 0.01: segs.append((pos, len(ing) / SR))
# new positions: walk the edited timeline in the same order
pz1 = [p for p in tl1["pauses"] if p["ms"] >= 60]; new = []; pos1 = 0.0
for p in pz1: new.append((pos1, p["start"])); pos1 = p["end"]
if pos1 < len(edit) / SR - 0.01: new.append((pos1, len(edit) / SR))
print(f"{'seg':>3} {'orig s':>7} {'new s':>7} {'ratio':>6} {'voicing raw':>12} {'voicing new':>12} {'tail rms raw':>13} {'tail rms new':>13}")
vr, vn = [], []
for i, ((a, b), (c, d)) in enumerate(zip(segs, new)):
    exp = (b - a) / TEMPO; act = d - c
    v0, n0 = voicing(ing, a, b); v1, n1 = voicing(edit, c, d)
    t0 = np.sqrt((ing[int((b - 0.03) * SR): int(b * SR)] ** 2).mean()); t1 = np.sqrt((edit[int((d - 0.03) * SR): int(d * SR)] ** 2).mean())
    vr.append(v0); vn.append(v1)
    print(f"{i:>3} {b - a:7.2f} {act:7.2f} {act / (b - a):6.3f} {v0:12.3f} {v1:12.3f} {20 * np.log10(t0 + 1e-9):13.1f} {20 * np.log10(t1 + 1e-9):13.1f}")
print(f"\nmean voicing strength: raw {np.mean(vr):.3f}  stretched {np.mean(vn):.3f}  (change {100 * (np.mean(vn) / np.mean(vr) - 1):+.1f}%)")
# glitches: largest sample-to-sample jump relative to local level, raw vs edited
d0 = np.abs(np.diff(ing)).max(); d1 = np.abs(np.diff(edit)).max()
print(f"largest sample step: raw {d0:.3f}  edited {d1:.3f}")
# 99th percentile of high-frequency noise-like residual: energy above 8k in speech, raw vs edited, as share of total
for nm, x, tl in (("raw", ing, tl0), ("edited", edit, tl1)):
    m = np.zeros(len(x), bool)
    for l in tl["lines"]: m[int(l["start"] * SR): int(l["end"] * SR)] = True
    X = np.abs(np.fft.rfft(x[m][: SR * 30])) ** 2; f = np.fft.rfftfreq(len(x[m][: SR * 30]), 1 / SR)
    print(f"{nm}: energy above 8 kHz = {10 * np.log10(X[f > 8000].sum() / X.sum()):.1f} dB re total")
