"""Check everything the art-short pipeline needs, without spending anything. Exit 1 if a blocker is found."""
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + os.environ["PATH"]
rows = []


def chk(name, ok, detail="", blocker=True):
    rows.append((name, ok, detail, blocker))


env = (ROOT / ".env").read_text(encoding="utf-8") if (ROOT / ".env").exists() else ""
key = next((l.split("=", 1)[1].strip().strip("\"'") for l in env.splitlines() if l.startswith("ELEVENLABS_API_KEY=")), "")
chk("ElevenLabs key in .env", len(key) >= 20, "present (not shown)" if len(key) >= 20 else "missing: ask the user to paste it into .env")
ec = json.loads((ROOT / "tools/eleven_config.json").read_text(encoding="utf-8"))
chk("voice_id configured", bool(ec["voice_id"]), ec["voice_label"] if ec["voice_id"] else "empty: ask the user ONCE for the voice ID and write it to tools/eleven_config.json")
for exe in ("ffmpeg", "ffprobe"):
    chk(exe, shutil.which(exe) is not None, shutil.which(exe) or "not found")
filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout if shutil.which("ffmpeg") else ""
chk("ffmpeg filters alimiter + sidechaincompress", all(f in filters for f in ("alimiter", "sidechaincompress")), "", True)
py = ROOT / ".venv/Scripts/python.exe"
chk("venv python", py.exists(), str(py))
r = subprocess.run([str(py), "-c", "import soundfile, numpy, scipy, faster_whisper, num2words; print('ok')"], capture_output=True, text=True) if py.exists() else None
chk("python deps (soundfile numpy scipy faster-whisper num2words)", bool(r and "ok" in r.stdout), (r.stderr[-120:] if r and "ok" not in r.stdout else ""))
chk("whisper base.en cached", any((Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots").glob("*/model.bin")), "")
chk("node", shutil.which("node") is not None, "")
chk("video/assets/gsap.min.js (local, no CDN)", (ROOT / "video/assets/gsap.min.js").exists(), "")
chk("git identity", subprocess.run(["git", "-C", str(ROOT), "config", "user.email"], capture_output=True, text=True).stdout.strip() != "", "", False)
run = json.loads((ROOT / "run.json").read_text()) if (ROOT / "run.json").exists() else None
chk("run.json", True, f"current run: {run['slug']}" if run else "none yet", False)
for n, ok, d, blk in rows:
    print(("PASS " if ok else ("FAIL " if blk else "WARN ")) + n + (f" :: {d}" if d else ""))
sys.exit(1 if any((not ok) and blk for _, ok, _, blk in rows) else 0)
