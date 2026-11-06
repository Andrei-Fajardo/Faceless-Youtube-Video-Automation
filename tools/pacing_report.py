"""build/timeline.json + script.json -> build/qa/pacing_report.md (and prints pass/fail)."""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT/"build/timeline.json").read_text()); sc = json.loads((ROOT/"script/script.json").read_text(encoding="utf-8"))
bp = ROOT/"build/qa/pacing_before.json"
before = json.loads(bp.read_text()) if bp.exists() else None   # the "before" column only exists for runs that were re-paced
words = sum(len(l["text"].split()) for l in sc["lines"])
sents = [s.strip() for l in sc["lines"] for s in re.split(r"(?<=[.?!])\s+", l["text"]) if s.strip()]
sl = [len(s.split()) for s in sents]; vc = json.loads((ROOT/"script/video.json").read_text(encoding="utf-8")) if (ROOT/"script/video.json").exists() else {}
tl_line = vc.get("title_card", {}).get("line")
title = next((len(l["text"].split()) for l in sc["lines"] if l["id"] == tl_line), 0)
sl_ex = [n for n in sl if n != title]
speech = sum(i["end"] - i["start"] for i in tl["items"] if i["type"] == "speech")
total = tl["total_duration"]; silence = total - speech
longp = max((p for p in tl["pauses"]), key=lambda p: p["ms"])
hook = len(sc["lines"][0]["text"].split())
chk = lambda ok: "PASS" if ok else "FAIL"
G = vc.get("gates", {}); gw = G.get("words", [90, 110]); gd = G.get("duration", [50, 60])
BANNED = ["did you know", "you won't believe", "you wont believe", "blow your mind", "here's the thing", "heres the thing", "here's the part", "incredible", "shocking", "amazing", "insane", "unbelievable", "subscribe", "follow for", "like and", "link in"]
alltext = " ".join(l["text"] for l in sc["lines"]).lower()
banned = [b for b in BANNED if b in alltext] + (["!"] if "!" in alltext else [])
rows = [("Banned phrases (hype, generic hooks, calls to action, '!')", ", ".join(banned) or "none", "none", not banned),
 ("Total words", words, f"{gw[0]}-{gw[1]}", gw[0] <= words <= gw[1]), ("Hook words", hook, "<= 8", hook <= 8),
 ("Average sentence (words)", round(sum(sl)/len(sl), 1), "<= 8", sum(sl)/len(sl) <= 8),
 ("Longest sentence (excl. title)", max(sl_ex), "<= 12", max(sl_ex) <= 12),
 ("Sentences over 14 (excl. title)", sum(1 for n in sl_ex if n > 14), "<= 1", sum(1 for n in sl_ex if n > 14) <= 1),
 ("Words/sec during speech", round(words/speech, 2), "2.1-2.5", 2.1 <= words/speech <= 2.5),
 ("Silence % of runtime", round(100*silence/total, 1), "15-22", 15 <= 100*silence/total <= 22),
 ("Longest pause (ms)", longp["ms"], "<= 1400", longp["ms"] <= 1400),
 ("Total duration (s)", total, f"{gd[0]}-{gd[1]}", gd[0] <= total <= gd[1])]
md = ["# Pacing report", "", f"Seed {tl['seed']}. Title line ({title} words) is the allowed long-sentence exception; average includes it.", "",
 "| Metric | Before | After | Target | |", "|---|---|---|---|---|"]
bmap = ({"Total words": before["words"], "Hook words": 8, "Average sentence (words)": before["avg_sentence"], "Longest sentence (excl. title)": before["longest_sentence"],
 "Sentences over 14 (excl. title)": before["over14"], "Words/sec during speech": before["wps"], "Silence % of runtime": before["silence_pct"],
 "Longest pause (ms)": int(before["longest_pause_s"]*1000), "Total duration (s)": before["total_s"]} if before else {})
for n, v, tg, ok in rows: md.append(f"| {n} | {bmap.get(n, '-')} | {v} | {tg} | {chk(ok)} |")
md += ["", f"Speech {speech:.1f} s, silence {silence:.1f} s ({100*silence/total:.1f}% of {total} s).", "",
 "## Every pause", "", "| # | after | beat | start | end | ms | reverb tail |", "|---|---|---|---|---|---|---|"]
for i, p in enumerate(tl["pauses"], 1): md.append(f"| {i} | {p['after']} | {p['beat']} | {p['start']:.2f} | {p['end']:.2f} | {p['ms']} | {'yes' if p['tail_reverb'] else ''} |")
q = [p for p in tl["pauses"] if p["beat"] == "question"]; pun = next(l for l in tl["lines"] if l["beat"] == "punchline")
before_pun = [p for p in tl["pauses"] if p["end"] <= pun["start"] + 0.01][-1]
md += ["", "## Listen at these timestamps", "", f"- Longest pause: {longp['start']:.2f}-{longp['end']:.2f} s (after {longp['after']}, {longp['ms']} ms)"]
for p in q: md.append(f"- Question pause: {p['start']:.2f}-{p['end']:.2f} s (after {p['after']}, {p['ms']} ms)")
md.append(f"- Pause before the punchline: {before_pun['start']:.2f}-{before_pun['end']:.2f} s (after {before_pun['after']}, {before_pun['ms']} ms)")
(ROOT/"build/qa/pacing_report.md").write_text("\n".join(md), encoding="utf-8")
for n, v, tg, ok in rows: print(f"{chk(ok)} {n}: {v} (target {tg})")
