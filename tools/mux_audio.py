"""Mux the lossless mastered mix into the rendered video with a single clean AAC encode (the renderer's own AAC can land under 192 kbps).
Usage: mux_audio.py out/render_vN.mp4 out/final_vN.mp4 [--reencode]   (--reencode: x264 CRF 16, slow preset, for renders over ~60 MB)   (video stream is copied untouched; audio = video/assets/mix.wav at 224 kbps CBR)"""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + os.environ["PATH"]
args_ = [a for a in sys.argv if not a.startswith("--")]
if len(args_) < 3:
    sys.exit(__doc__)
src, dst = Path(args_[1]), Path(args_[2])
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip())
r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-i", str(ROOT / "video/assets/mix.wav"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", *(["libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p"] if "--reencode" in sys.argv else ["copy"]), "-c:a", "aac", "-b:a", "224k", "-ar", "48000", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-600:])
print(f"muxed {dst.name}: video copied from {src.name}, audio re-encoded once from the lossless mix at 224 kbps")
