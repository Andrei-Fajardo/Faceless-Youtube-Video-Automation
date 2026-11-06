"""Audit log for the channel pipeline: time and resources per step, one JSON line each, with a monthly report.

  audit.py run --video SLUG --step STEP [--out FILE] [--frames N] [--note TEXT] -- COMMAND ARGS...
      runs the command, measures wall time, ElevenLabs characters spent (from eleven_usage.json), output size, F: free space, exit code
  audit.py log --video SLUG --step STEP [--secs S] [--chars N] [--frames N] [--bytes N] [--note TEXT] [--backfilled]
      records a step you measured yourself (searches, manual work, a backfill)
  audit.py report [--month YYYY-MM]
      prints and writes audit/report_YYYY-MM.md: totals per step, per video, ElevenLabs budget, render speed

Not captured (no API for it from inside a command): Claude token use and cost. Use /cost in Claude Code and log it with
  audit.py log --video SLUG --step claude-session --note "tokens in/out and cost from /cost"
"""
import argparse, json, shutil, subprocess, sys, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "audit" / "audit_log.jsonl"
USAGE = ROOT / "eleven_usage.json"


def eleven_chars():
    try:
        return sum(c["chars"] for c in json.loads(USAGE.read_text())["calls"])
    except Exception:
        return 0


def free_gb():
    try:
        return round(shutil.disk_usage(ROOT).free / 1e9, 2)
    except Exception:
        return None


def write(entry):
    LOG.parent.mkdir(exist_ok=True)
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), **entry, "f_free_gb": free_gb()}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def cmd_run(a):
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        sys.exit("audit.py run: no command given after --")
    before = eleven_chars(); t0 = time.time()
    code = subprocess.run(cmd).returncode
    secs = round(time.time() - t0, 2)
    e = {"video": a.video, "step": a.step, "secs": secs, "exit": code, "eleven_chars": eleven_chars() - before}
    if a.frames: e["frames"] = a.frames; e["fps"] = round(a.frames / secs, 2) if secs else None
    if a.out and Path(a.out).exists(): e["bytes"] = Path(a.out).stat().st_size
    if a.note: e["note"] = a.note
    print("audit:", json.dumps(write(e)))
    sys.exit(code)


def cmd_log(a):
    e = {"video": a.video, "step": a.step}
    for k in ("secs", "chars", "frames", "bytes"):
        v = getattr(a, k)
        if v is not None: e["eleven_chars" if k == "chars" else k] = v
    if a.note: e["note"] = a.note
    if a.backfilled: e["backfilled"] = True
    print("audit:", json.dumps(write(e)))


def cmd_report(a):
    month = a.month or datetime.now().strftime("%Y-%m")
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()] if LOG.exists() else []
    rows = [r for r in rows if r["ts"].startswith(month)]
    by_step, by_video = defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0.0, 0, 0])
    frames = secs_r = 0
    for r in rows:
        s = r.get("secs") or 0
        by_step[r["step"]][0] += 1; by_step[r["step"]][1] += s
        v = by_video[r["video"]]; v[0] += s; v[1] += r.get("eleven_chars", 0) or 0; v[2] += r.get("bytes", 0) or 0
        if r.get("frames") and s: frames += r["frames"]; secs_r += s
    cfg = json.loads((ROOT / "tools/eleven_config.json").read_text(encoding="utf-8"))
    month_chars = sum(c["chars"] for c in json.loads(USAGE.read_text())["calls"] if c["date"].startswith(month)) if USAGE.exists() else 0
    out = [f"# Audit report {month}", "", f"{len(rows)} logged steps, {len(by_video)} videos. Claude token use and cost are not captured here (use /cost).", "",
           "## Per step", "| step | runs | total s | avg s |", "|---|---|---|---|"]
    for k, (n, s) in sorted(by_step.items()):
        out.append(f"| {k} | {n} | {s:.1f} | {s / n:.1f} |")
    out += ["", "## Per video", "| video | logged seconds | ElevenLabs chars (logged) | output bytes |", "|---|---|---|---|"]
    for k, (s, c, b) in sorted(by_video.items()):
        out.append(f"| {k} | {s:.1f} | {c} | {b} |")
    out += ["", "## Resources", f"- ElevenLabs characters this month (ledger): {month_chars} of {cfg['monthly_char_budget']} ({100 * month_chars / cfg['monthly_char_budget']:.1f}%)"]
    if secs_r: out.append(f"- Render speed: {frames} frames in {secs_r:.0f} s, {frames / secs_r:.1f} fps on average")
    frees = [r["f_free_gb"] for r in rows if r.get("f_free_gb") is not None]
    if frees: out.append(f"- F: free space: {frees[0]} GB at the first entry, {frees[-1]} GB at the last")
    text = "\n".join(out) + "\n"
    (ROOT / "audit" / f"report_{month}.md").write_text(text, encoding="utf-8")
    print(text)


ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="c", required=True)
r = sub.add_parser("run"); r.add_argument("--video", required=True); r.add_argument("--step", required=True); r.add_argument("--out"); r.add_argument("--frames", type=int); r.add_argument("--note"); r.add_argument("cmd", nargs=argparse.REMAINDER)
l = sub.add_parser("log"); l.add_argument("--video", required=True); l.add_argument("--step", required=True)
l.add_argument("--secs", type=float); l.add_argument("--chars", type=int); l.add_argument("--frames", type=int); l.add_argument("--bytes", type=int); l.add_argument("--note"); l.add_argument("--backfilled", action="store_true")
p = sub.add_parser("report"); p.add_argument("--month")
a = ap.parse_args()
{"run": cmd_run, "log": cmd_log, "report": cmd_report}[a.c](a)
