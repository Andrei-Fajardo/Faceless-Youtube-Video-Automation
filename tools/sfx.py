"""Synthesize the sound design locally (numpy/scipy), deterministic. Only what the channel uses:
  ambient.wav      quiet brown-noise room bed (no tones in the speech range), length = video + 1 s
  impact.wav       the small boom/pop at 0.00 s
  whoosh_zoom.wav  the rising 'fade-in warp' into the zoom
The user rejected every other effect (swell, wipe, settle, pull-back and title whooshes): do not add them back."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, istft, sosfilt, stft

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(42)


def lp(x, f, order=2): return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)
def hp(x, f, order=2): return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)
def norm(x, peak): return x / (np.abs(x).max() + 1e-12) * peak


def save(name, x, sub="sfx"):
    p = ROOT / "audio" / sub / name
    p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(p, x.astype(np.float32), SR)
    print(name, round(len(x) / SR, 2), "s")


tl = json.loads((ROOT / "build" / "timeline.json").read_text())
total = tl["total_duration"]

# ambient: brown noise, HP 60 Hz, LP ~1.2 kHz, slow +-1.5 dB wobble. No tones.
n = int((total + 1.0) * SR)
brown = np.cumsum(rng.standard_normal(n))
brown -= np.linspace(brown[0], brown[-1], n)
amb = lp(hp(brown, 60), 1200)
t = np.arange(n) / SR
wob_db = 1.5 * np.sin(2 * np.pi * 0.07 * t) * 0.6 + 1.5 * np.sin(2 * np.pi * 0.053 * t + 1.1) * 0.4
amb *= 10 ** (wob_db / 20)
save("ambient.wav", norm(amb, 0.5), sub="")   # audio/ambient.wav

# impact: sine sweep 120 -> 45 Hz with fast exponential decay + an 8 ms noise click
d = 0.7
t = np.arange(int(d * SR)) / SR
ph = 2 * np.pi * np.cumsum(45 + (120 - 45) * np.exp(-t / 0.08)) / SR
imp = np.sin(ph) * np.exp(-t / 0.18)
click = rng.standard_normal(int(0.008 * SR)) * np.linspace(1, 0, int(0.008 * SR))
imp[:len(click)] += 0.35 * click
save("impact.wav", norm(imp, 0.9))


# whoosh: smooth sweep (STFT mask following a moving centre frequency)
def whoosh(dur, f0, f1, peak_pos, width=0.55, tail=0.35):
    n = int(dur * SR)
    f, tt, Z = stft(rng.standard_normal(n), fs=SR, nperseg=1024, noverlap=768)
    fc = f0 * (f1 / f0) ** np.clip(tt / dur, 0, 1)
    mask = np.exp(-0.5 * ((np.log(np.maximum(f[:, None], 20)) - np.log(fc[None, :])) / width) ** 2)
    _, y = istft(Z * mask, fs=SR, nperseg=1024, noverlap=768)
    y = y[:n]
    tm = np.arange(len(y)) / SR
    pk = peak_pos * dur
    return y * np.where(tm < pk, (tm / pk) ** 2.0, np.exp(-(tm - pk) / (tail * dur)))


save("whoosh_zoom.wav", norm(whoosh(1.0, 250, 5200, 0.78), 0.95))
