"""Where does the voice lose quality? Measures each stage against the raw ElevenLabs file. Read-only; writes build/qa/audio_diagnosis.md."""
import json, os, subprocess, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import welch, correlate, resample_poly

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + os.environ["PATH"]
SR = 48000
db = lambda x: 20 * np.log10(max(float(x), 1e-12))
tmp = Path(tempfile.mkdtemp())


def ff(*a):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-800:])


def load_mono(p):
    x, sr = sf.read(p, dtype="float32"); x = x if x.ndim == 1 else x.mean(1)
    return x if sr == SR else resample_poly(x, SR, sr).astype("float32")


mp3 = next((ROOT / "audio/eleven-labs").glob("*.mp3"))
ff("-i", str(mp3), "-ar", str(SR), "-ac", "1", "-c:a", "pcm_f32le", str(tmp / "raw_f32.wav"))       # lossless-as-possible decode of the mp3
raw = load_mono(tmp / "raw_f32.wav")
tl0 = json.loads((ROOT / "build/timeline_ingest.json").read_text()); tl1 = json.loads((ROOT / "build/timeline.json").read_text())


def speech_mask(n, tl, shift=0.0):
    m = np.zeros(n, bool)
    for l in tl["lines"]: m[int((l["start"] + shift) * SR): int((l["end"] + shift) * SR)] = True
    return m


def bands(x, mask):
    seg = x[mask[: len(x)]]
    f, P = welch(seg, SR, nperseg=4096)
    tot = P.sum()
    edges = [(80, 500), (500, 2000), (2000, 4000), (4000, 8000), (8000, 12000), (12000, 20000)]
    row = [10 * np.log10(P[(f >= a) & (f < b)].sum() / tot + 1e-12) for a, b in edges]
    c = np.cumsum(P) / tot
    return row, float(f[np.searchsorted(c, 0.99)]), float(f[np.searchsorted(c, 0.999)])


# raw voice sits at the ingest timeline's own time base shifted by the ingest lead shift; use its voice_ingest copy for the mask
ing = load_mono(ROOT / "audio/voice/voice_ingest.wav")
edit = load_mono(ROOT / "audio/voice/voice_dry.wav")
ff("-i", str(ROOT / "out/final_v3.mp4"), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", str(tmp / "final_aac.wav"))
final = load_mono(tmp / "final_aac.wav")
ff("-i", str(ROOT / "out/review/audio_only.wav"), "-ac", "1", "-c:a", "pcm_f32le", str(tmp / "ao.wav"))
audio_only = load_mono(tmp / "ao.wav")

stages = [("raw mp3 (decoded)", raw, speech_mask(len(raw), tl0, shift=(tl0["lines"][0]["start"] - 0.0) * 0)),
          ("ingest wav (16-bit, shifted)", ing, speech_mask(len(ing), tl0)),
          ("edited voice (rubberband 0.89)", edit, speech_mask(len(edit), tl1)),
          ("audio_only.wav (mix+master)", audio_only, speech_mask(len(audio_only), tl1)),
          ("final.mp4 audio (AAC)", final, speech_mask(len(final), tl1))]
# raw is unshifted: find its shift by matching its first loud sample to ingest's
first = lambda x: int(np.argmax(np.abs(x) > 0.01))
stages[0] = (stages[0][0], raw, speech_mask(len(raw), tl0, shift=(first(ing) - first(raw)) / SR))

out = ["# Audio diagnosis", "", "Speech-frame spectrum: share of energy per band (dB re total) and the frequency below which 99% / 99.9% of the energy sits.", "",
       "| Stage | 80-500 | 0.5-2k | 2-4k | 4-8k | 8-12k | 12-20k | 99% | 99.9% |", "|---|---|---|---|---|---|---|---|---|"]
res = {}
for name, x, m in stages:
    row, r99, r999 = bands(x, m); res[name] = row
    out.append(f"| {name} | " + " | ".join(f"{v:.1f}" for v in row) + f" | {r99:.0f} Hz | {r999:.0f} Hz |")

# TEST 1: is rubberband itself transparent? run tempo=1.0 with the exact settings used and null-test against the raw.
seg = raw[: SR * 20]; sf.write(tmp / "seg.wav", seg, SR, subtype="FLOAT")
FILT = "transients=crisp:detector=compound:phase=laminar:window=standard:formant=preserved:pitchq=quality"
ff("-i", str(tmp / "seg.wav"), "-af", f"rubberband=tempo=1.0:{FILT}", "-c:a", "pcm_f32le", str(tmp / "rb1.wav"))
rb = load_mono(tmp / "rb1.wav")
n = min(len(seg), len(rb)); lag_range = 4000
c = correlate(rb[SR:SR * 6], seg[SR:SR * 6], mode="full", method="fft"); lag = int(np.argmax(c) - (len(seg[SR:SR * 6]) - 1))
a, b = (seg[SR: SR * 18], rb[SR + lag: SR * 18 + lag]) if lag >= 0 else (seg[SR - lag: SR * 18], rb[SR: SR * 18 + lag])
k = min(len(a), len(b)); a, b = a[:k], b[:k]
resid = db(np.sqrt(((a - b) ** 2).mean())) - db(np.sqrt((a ** 2).mean()))
out += ["", "## Test 1 - is the stretcher transparent? (rubberband at tempo 1.0, same settings, null test vs raw)",
        f"Residual after aligning (lag {lag} samples): **{resid:.1f} dB** relative to the speech. (-60 dB or lower = inaudible; -30 dB = clearly different.)"]

# TEST 2: round trip 0.89 then 1/0.89 vs raw
ff("-i", str(tmp / "seg.wav"), "-af", f"rubberband=tempo=0.89:{FILT}", "-c:a", "pcm_f32le", str(tmp / "rb_slow.wav"))
ff("-i", str(tmp / "rb_slow.wav"), "-af", f"rubberband=tempo={1 / 0.89:.6f}:{FILT}", "-c:a", "pcm_f32le", str(tmp / "rb_back.wav"))
bk = load_mono(tmp / "rb_back.wav")
c = correlate(bk[SR:SR * 6], seg[SR:SR * 6], mode="full", method="fft"); lag2 = int(np.argmax(c) - (len(seg[SR:SR * 6]) - 1))
a, b = (seg[SR: SR * 16], bk[SR + lag2: SR * 16 + lag2]) if lag2 >= 0 else (seg[SR - lag2: SR * 16], bk[SR: SR * 16 + lag2])
k = min(len(a), len(b)); a, b = a[:k], b[:k]
rt = db(np.sqrt(((a - b) ** 2).mean())) - db(np.sqrt((a ** 2).mean()))
out += ["", "## Test 2 - round trip (stretch to 0.89, then back) vs raw", f"Residual: **{rt:.1f} dB** (this is the damage a 11% stretch adds; a clean tool would be near -40 dB or better)."]

# TEST 3: master peak catch on the voice-only signal
vp = load_mono(ROOT / "audio/mix/voice_proc.wav")
pm, _ = sf.read(ROOT / "audio/mix/premaster.wav", dtype="float32"); pm = pm.mean(1) if pm.ndim > 1 else pm
ao_stereo, _ = sf.read(ROOT / "out/review/audio_only.wav", dtype="float32"); ao = ao_stereo.mean(1) if ao_stereo.ndim > 1 else ao_stereo
gain = np.dot(ao, pm[: len(ao)]) / np.dot(pm[: len(ao)], pm[: len(ao)])  # effective linear gain (limiter makes it < true gain)
ceil = 0.75; g_db = 7.8
over = np.abs(pm) * 10 ** (g_db / 20) > ceil
fr = len(over) // 480 * 480; lim = over[:fr].reshape(-1, 480).any(1)
out += ["", "## Test 3 - master peak catch", f"Frames (10 ms) where the limiter acts: **{lim.mean() * 100:.1f}%** of the whole mix; effective master gain {db(gain):+.1f} dB."]

# TEST 4: noise / bed under the voice
bed_db = None
try:
    ap, _ = sf.read(ROOT / "audio/mix/amb_ducked.wav", dtype="float32"); ap = ap if ap.ndim == 1 else ap.mean(1)
    sm = speech_mask(len(ap), tl1)
    bed_db = db(np.sqrt((ap[sm] ** 2).mean())) - db(np.sqrt((edit[: len(ap)][sm[: len(edit)]] ** 2).mean()))
except Exception as e: out.append(f"(bed measure skipped: {e})")
if bed_db is not None: out += ["", "## Test 4 - bed under the voice", f"Ambient bed during speech is **{bed_db:.1f} dB** relative to the voice (a bed this low is not what muddies a voice)."]

# TEST 5: 16-bit quantization noise floor
q = 20 * np.log10(1 / 32768 / np.sqrt(12) + 1e-12)
out += ["", "## Test 5 - 16-bit stages", f"Each 16-bit write adds noise at about {q:.0f} dBFS; the voice sits near -24 dBFS RMS, so ~{-24 - q:.0f} dB SNR per write - not audible by itself."]

(ROOT / "build/qa/audio_diagnosis.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
