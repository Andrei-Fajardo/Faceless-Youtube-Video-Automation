"""Narrate a What If short (finished/what-if/<slug>/script.txt) with ElevenLabs -> finished/what-if/<slug>/voice.mp3 and voice.wav.
Same guards as eleven_tts.py (per-call cap, per-run cap, monthly budget, cache); the voice is never post-processed.
Usage: eleven_whatif.py <slug> [--dry-run]"""
import argparse, hashlib, json, os, subprocess, sys, urllib.error, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("slug")
ap.add_argument("--base", default="finished/what-if")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()
cfg = json.loads((ROOT / "tools/eleven_config.json").read_text(encoding="utf-8"))
d = ROOT / args.base / args.slug
raw = (d / "script.txt").read_text(encoding="utf-8")
text = raw.split("SCRIPT:", 1)[1].strip()
vs = dict(cfg["voice_settings"])
run_name = f"whatif-{args.slug}"
chars = len(text)
key_hash = hashlib.sha1(json.dumps([text, cfg["model_id"], vs, cfg["voice_id"]], sort_keys=True).encode()).hexdigest()[:10]
mp3 = d / "voice.mp3"
meta = d / "voice_meta.json"
print(f"{args.slug}: {chars} characters | model {cfg['model_id']} | settings {vs}")
if args.dry_run:
    print(text)
    sys.exit(0)
if not cfg["voice_id"]:
    sys.exit("STOP: tools/eleven_config.json has no voice_id.")
if chars > cfg["max_chars_per_call"]:
    sys.exit(f"STOP: {chars} characters exceeds max_chars_per_call ({cfg['max_chars_per_call']}).")
ledger_p = ROOT / "eleven_usage.json"
ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {"calls": []}
month = date.today().strftime("%Y-%m")
used_month = sum(c["chars"] for c in ledger["calls"] if c["date"].startswith(month))
calls_this_run = sum(1 for c in ledger["calls"] if c.get("run") == run_name)
cached = mp3.exists() and meta.exists() and json.loads(meta.read_text()).get("hash") == key_hash
if not cached:
    if used_month + chars > cfg["monthly_char_budget"]:
        sys.exit(f"STOP: this call would bring the month to {used_month + chars} characters (budget {cfg['monthly_char_budget']}).")
    if calls_this_run >= cfg["max_calls_per_run"]:
        sys.exit(f"STOP: {calls_this_run} paid calls already made for {run_name} (max {cfg['max_calls_per_run']}).")
    key = next((l.split("=", 1)[1].strip().strip("\"'") for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ELEVENLABS_API_KEY=")), "")
    if len(key) < 20:
        sys.exit("STOP: ELEVENLABS_API_KEY missing in .env")
    body = json.dumps({"text": text, "model_id": cfg["model_id"], "voice_settings": vs}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}?output_format={cfg['output_format']}", data=body,
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"STOP: ElevenLabs returned {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}")
    mp3.write_bytes(audio)
    meta.write_text(json.dumps({"hash": key_hash, "chars": chars}))
    ledger["calls"].append({"date": date.today().isoformat(), "run": run_name, "chars": chars, "model": cfg["model_id"], "speed": vs.get("speed"), "hash": key_hash})
    ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"generated voice.mp3 ({len(audio) // 1024} KB); month total {used_month + chars}/{cfg['monthly_char_budget']} characters")
else:
    print("cache hit (no characters spent)")
os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(d / "voice.wav")], check=True)
print("decoded ->", (d / "voice.wav").relative_to(ROOT))
