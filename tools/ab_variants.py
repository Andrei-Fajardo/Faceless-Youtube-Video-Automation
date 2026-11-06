"""A/B files that isolate one variable each -> out/review/ab/. Usage: ab_variants.py  (A,B,D,E)  |  ab_variants.py C <premaster.wav> (full mix from another timeline)"""
import os, re, subprocess, sys, shutil
from pathlib import Path
import numpy as np, soundfile as sf
ROOT = Path(__file__).resolve().parent.parent; SR = 48000
os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
OUT = ROOT / "out/review/ab"; OUT.mkdir(parents=True, exist_ok=True); tmp = ROOT / "audio/mix"

def meas(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = r[r.rfind("Summary:"):]; return float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))

def master(src, target, dst):
    I0, _ = meas(src); g = target - I0
    for _ in range(5):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", f"volume={g:.2f}dB,alimiter=limit=0.75:attack=7:release=70:level=disabled", "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)])
        I, TP = meas(dst)
        if abs(I - target) <= 0.2: break
        g += target - I
    print(f"{dst.name}: {I} LUFS, {TP} dBTP, gain {g:+.1f} dB"); return g

def stereo(src, dst):
    x, sr = sf.read(src, dtype="float32"); x = x if x.ndim == 1 else x.mean(1); sf.write(dst, np.stack([x, x], 1), sr, subtype="FLOAT")

if len(sys.argv) > 2 and sys.argv[1] == "C":
    master(Path(sys.argv[2]), -14.6, OUT / "C_full_mix_NO_stretch.wav"); sys.exit()
shutil.copy(ROOT / "out/review/audio_only.wav", OUT / "A_full_mix_fixed.wav")
master(tmp / "premaster.wav", -18.0, OUT / "B_full_mix_quieter_-18LUFS.wav")
stereo(ROOT / "audio/voice/voice_dry.wav", tmp / "ab_voice_stretched.wav"); master(tmp / "ab_voice_stretched.wav", -14.6, OUT / "D_voice_only_stretched.wav")
stereo(ROOT / "audio/voice/voice_ingest.wav", tmp / "ab_voice_raw.wav"); master(tmp / "ab_voice_raw.wav", -14.6, OUT / "E_voice_only_NO_stretch.wav")
