"""Automatic QA gates on out/final.mp4 -> build/qa/report.md, frames -> build/qa/frames/. Exit code 1 if any gate fails."""
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;C:\Program Files\Tracktion\Waveform 13;" + os.environ["PATH"]
mp4 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out/final.mp4"
cues = json.loads((ROOT / "build/cues.json").read_text())
tl = json.loads((ROOT / "build/timeline.json").read_text())
cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
claims = json.loads((ROOT / "script/claims.json").read_text(encoding="utf-8"))["claims"]
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
credits = json.loads((ROOT / "assets/credits.json").read_text(encoding="utf-8"))
rows = []


def gate(name, ok, detail):
    rows.append((name, ok, detail))


def run(*a):
    r = subprocess.run(list(a), capture_output=True, text=True)
    return r.stdout + r.stderr


# 1 duration + format
probe = json.loads(run("ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,bit_rate", "-of", "json", str(mp4)))
dur = float(probe["format"]["duration"])
vs = next(s for s in probe["streams"] if "width" in s)
as_ = next(s for s in probe["streams"] if "sample_rate" in s)
try:
    _g = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8")).get("gates", {}).get("duration", [50, 60])
except Exception:
    _g = [50, 60]
gate(f"Duration {_g[0]}-{_g[1]} s", _g[0] <= dur <= _g[1], f"{dur:.2f} s")
gate("Video 1080x1920 H.264 yuv420p 30 fps", (vs["width"], vs["height"], vs["codec_name"], vs["pix_fmt"], vs["r_frame_rate"]) == (1080, 1920, "h264", "yuv420p", "30/1"),
     f"{vs['width']}x{vs['height']} {vs['codec_name']} {vs['pix_fmt']} {vs['r_frame_rate']}")
gate("Audio AAC 48 kHz >= 192 kbps", as_["codec_name"] == "aac" and as_["sample_rate"] == "48000" and int(as_.get("bit_rate", 0)) >= 190000,
     f"{as_['codec_name']} {as_['sample_rate']} Hz {int(as_.get('bit_rate', 0)) // 1000} kbps")

# 2 loudness of the delivered file
r = run("ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-")
s = r[r.rfind("Summary:"):]
I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)); TP = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
gate("Loudness -14 LUFS +/-1", abs(I + 14) <= 1, f"{I} LUFS")
gate("True peak <= -1 dBTP", TP <= -1.0, f"{TP} dBTP")
(ROOT / "build/qa/loudness_final.txt").write_text(s, encoding="utf-8")

# 3 silent gaps over 0.6 s (audio) other than designed pauses
sd = run("ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-af", "silencedetect=noise=-50dB:d=0.6", "-f", "null", "-")
gaps = [(float(a), float(b)) for a, b in re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)", sd)]
design = [(p["start"], p["end"]) for p in tl["pauses"]]
design[-1] = (design[-1][0], tl["total_duration"])   # the final hold includes the end tail
stray = [g for g in gaps if not any(g[0] >= a - 0.15 and g[1] <= b + 0.15 for a, b in design)]
gate("No silent gap > 0.6 s outside designed pauses", not stray, f"{len(gaps)} gaps found, {len(stray)} outside designed pauses {stray[:3]}")

# 4 black / freeze
bd = run("ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-vf", "blackdetect=d=0.25:pix_th=0.04", "-an", "-f", "null", "-")
blk = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bd)
gate("No unintended black frames", not blk, f"{blk[:3] if blk else 'none'}")
fd = run("ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-vf", "freezedetect=n=-60dB:d=1.2", "-an", "-f", "null", "-")
frz = [(float(a), float(b)) for a, b in re.findall(r"freeze_start: ([\d.]+)[\s\S]*?freeze_end: ([\d.]+)", fd)]
gate("No freeze > 1.2 s", not frz, f"{frz[:4] if frz else 'none'} (camera drifts through pauses by design; a freeze here would be a stuck frame)")

# 5 caption timing vs transcript (anchored words only: caption times are the transcript times by construction; check group windows)
html = (ROOT / "video/index.html").read_text(encoding="utf-8")
starts = [float(x) for x in re.findall(r'class="clip cg" data-start="([\d.]+)"', html)]
first_words = {}
for w in cap:
    first_words.setdefault(w["line"], []).append(w)
off = []
for st in starts:
    t = st + 0.04   # a caption group opens 40 ms before its first word; judge it against the transcript word's whole time window
    off.append(min(max(w["start"] - t, t - w["end"], 0.0) for w in cap))   # (a spoken year is one transcript word, so a later caption word may begin inside it)
gate("Caption group opens within 100 ms of a transcript word", max(off) <= 0.1, f"worst {max(off) * 1000:.0f} ms over {len(starts)} groups")

# 6 claims + credits
claim_ids = {c["id"] for c in claims}
used = {c for l in script for c in l["claims"]}
gate("Every narration claim is in claims.json with a source", used <= claim_ids and all(c["source_url"].startswith("http") for c in claims if c["id"] in used),
     f"used {sorted(used)}; missing {sorted(used - claim_ids) or 'none'}")
gate("credits.json complete", all(k in credits["images"][0] for k in ("source_url", "license", "date_accessed")), "image entry has source, license, date")

# 7 frames at t=0, every cue time, and the last frame
(ROOT / "build/qa/frames").mkdir(parents=True, exist_ok=True)
times = {"t0": 0.0, **{k: v for k, v in cues.items() if isinstance(v, float) and k != "total_duration"}, "last": dur - 0.05}
for k, t in times.items():
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(ROOT / f"build/qa/frames/{k}.png"))
# first vs last frame similarity
sim = run("ffmpeg", "-hide_banner", "-nostats", "-i", str(ROOT / "build/qa/frames/t0.png"), "-i", str(ROOT / "build/qa/frames/last.png"), "-lavfi", "ssim", "-f", "null", "-")
m = re.search(r"All:([\d.]+)", sim)
if json.loads((ROOT / "script/video.json").read_text(encoding="utf-8")).get("gates", {}).get("loop", True):   # a film may opt out of the loop gate
    gate("Last frame matches frame 0 (SSIM >= 0.97)", bool(m) and float(m.group(1)) >= 0.97, f"SSIM {m.group(1) if m else 'n/a'}")

md = ["# QA report", "", "| Gate | Result | Detail |", "|---|---|---|"] + [f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in rows]
md += ["", "Frames for manual review (hook text in frame 0, nothing cut off, text inside safe zones): `build/qa/frames/`."]
(ROOT / "build/qa/report.md").write_text("\n".join(md), encoding="utf-8")
for n, ok, d in rows:
    print(("PASS " if ok else "FAIL ") + n + " :: " + d)
sys.exit(0 if all(ok for _, ok, _ in rows) else 1)
