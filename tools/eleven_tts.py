"""Generate the whole narration as ONE take with ElevenLabs -> audio/eleven-labs/*.mp3 and audio/voice/voice_eleven.wav.
The key is read from the git-ignored .env and never printed. The voice is never post-processed (see mix.py / the art-short skill).
Spend guards: per-call character cap, per-run call cap, monthly budget, and a cache so identical text+settings are never paid for twice.
Usage: eleven_tts.py [--dry-run] [--speed X] [--force]"""
import argparse, hashlib, json, os, subprocess, sys, urllib.error, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--speed", type=float)
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
cfg = json.loads((ROOT / "tools/eleven_config.json").read_text(encoding="utf-8"))
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
lex = json.loads((ROOT / "tools/lexicon.json").read_text(encoding="utf-8"))
run = json.loads((ROOT / "run.json").read_text()) if (ROOT / "run.json").exists() else {"slug": "run"}
vs = dict(cfg["voice_settings"])
vs.update(json.loads((ROOT / "script/script.json").read_text(encoding="utf-8")).get("voice_settings_override", {}))   # per-run, e.g. lower stability so audio tags register
if args.speed:
    vs["speed"] = args.speed


def respell(t):
    for k in sorted(lex, key=len, reverse=True):
        t = t.replace(k, lex[k])
    return t


lines = [respell(l.get("tts_text", l["text"])).strip() for l in script]
if cfg["pause_style"] == "break_tags":   # eleven_multilingual_v2: exact pauses
    parts = []
    for i, (l, t) in enumerate(zip(script, lines)):
        parts.append(t)
        if i + 1 < len(script) and l["pause_after_ms"] >= 300:
            parts.append(f'<break time="{min(3.0, l["pause_after_ms"] / 1000):.2f}s" />')
    text = " ".join(parts)
else:                                     # eleven_v3/v4: paragraph breaks carry the pauses; audio tags are not used (unknown tags can be read aloud)
    text = "\n\n".join(lines)
chars = len(text)
key_hash = hashlib.sha1(json.dumps([text, cfg["model_id"], vs, cfg["voice_id"]], sort_keys=True).encode()).hexdigest()[:10]
mp3 = ROOT / "audio/eleven-labs" / f"{run['slug']}_{cfg['model_id']}_{key_hash}.mp3"
print(f"narration text: {chars} characters | model {cfg['model_id']} | pause style {cfg['pause_style']} | settings {vs}")
if args.dry_run:
    print("--- text that would be sent ---")
    print(text)
    sys.exit(0)

# ---- guards -----------------------------------------------------------------------------------------------------------
if not cfg["voice_id"]:
    sys.exit("STOP: tools/eleven_config.json has no voice_id. Ask the user for it once (ElevenLabs > the voice > Copy voice ID) and write it there.")
if chars > cfg["max_chars_per_call"]:
    sys.exit(f"STOP: {chars} characters exceeds max_chars_per_call ({cfg['max_chars_per_call']}). Tighten the script.")
ledger_p = ROOT / "eleven_usage.json"
ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {"calls": []}
month = date.today().strftime("%Y-%m")
used_month = sum(c["chars"] for c in ledger["calls"] if c["date"].startswith(month))
calls_this_run = sum(1 for c in ledger["calls"] if c.get("run") == run["slug"])
if not mp3.exists() or args.force:
    if used_month + chars > cfg["monthly_char_budget"]:
        sys.exit(f"STOP: this call would bring the month to {used_month + chars} characters (budget {cfg['monthly_char_budget']}). Ask the user to raise monthly_char_budget.")
    if calls_this_run >= cfg["max_calls_per_run"]:
        sys.exit(f"STOP: {calls_this_run} paid calls already made for this run (max {cfg['max_calls_per_run']}).")
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
    mp3.parent.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(audio)
    ledger["calls"].append({"date": date.today().isoformat(), "run": run["slug"], "chars": chars, "model": cfg["model_id"], "speed": vs.get("speed"), "hash": key_hash})
    ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"generated {mp3.name} ({len(audio) // 1024} KB); month total {used_month + chars}/{cfg['monthly_char_budget']} characters")
else:
    print(f"cache hit: {mp3.name} (no characters spent)")

os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
out = ROOT / "audio/voice/voice_eleven.wav"
out.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
print("decoded ->", out.relative_to(ROOT))
