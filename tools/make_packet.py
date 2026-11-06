"""Assemble out/review/ from a finished render: final.mp4, loudness.txt, claims.json, script_with_sources.md, description.txt, contact_sheet.png.
Usage: make_packet.py out/final_vN.mp4   (run tools/qa.py on the same file first: it extracts the frames and writes loudness_final.txt)"""
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PATH"] = r"C:\Program Files\File Converter;" + os.environ["PATH"]
if len(sys.argv) < 2:
    sys.exit(__doc__)
mp4 = Path(sys.argv[1])
rev = ROOT / "out/review"; rev.mkdir(parents=True, exist_ok=True)
run = json.loads((ROOT / "run.json").read_text()) if (ROOT / "run.json").exists() else {"title": "Painting"}
script = json.loads((ROOT / "script/script.json").read_text(encoding="utf-8"))["lines"]
claims = json.loads((ROOT / "script/claims.json").read_text(encoding="utf-8"))["claims"]
cred = json.loads((ROOT / "assets/credits.json").read_text(encoding="utf-8"))
cues = json.loads((ROOT / "build/cues.json").read_text())
cl = {c["id"]: c for c in claims}

shutil.copy(mp4, rev / "final.mp4")
if (ROOT / "build/qa/loudness_final.txt").exists():
    shutil.copy(ROOT / "build/qa/loudness_final.txt", rev / "loudness.txt")
shutil.copy(ROOT / "script/claims.json", rev / "claims.json")

md = [f"# Script with sources - {run['title']}", "", "| ID | Narration | Beat | Claims / sources |", "|---|---|---|---|"]
for l in script:
    src = "; ".join(f"{c} ({cl[c]['verification']}): {cl[c]['source_url']}" for c in l["claims"] if c in cl) or "-"
    md.append(f"| {l['id']} | {l['text']} | {l['beat']} | {src} |")
md += ["", "## Claim details", ""] + [f"- **{c['id']}** \"{c['narration']}\" - {c['paraphrase']} [{c['verification']}] <{c['source_url']}>" for c in claims]
(rev / "script_with_sources.md").write_text("\n".join(md), encoding="utf-8")

im = cred["images"][0]
urls = sorted({c["source_url"] for c in claims} | {c.get("supporting_url") for c in claims if c.get("supporting_url")})
sources = "Sources:\n" + "\n".join(f"- {u}" for u in urls if u)
credit = f"{'Illustrations' if 'AI-generated' in im['work'] else 'Painting'}: {im['work']}. {im.get('credit_line', '')}".strip() + f"\nImage: {im['source_url']} ({im['license']}, accessed {im['date_accessed']})"
ai_line = "The narration voice is synthetic (AI-generated)."
post_p = ROOT / "script/post.json"
if post_p.exists():
    post = json.loads(post_p.read_text(encoding="utf-8"))
    tags = post["hashtags"]
    yt_desc = post["youtube_description"].strip() + "\n\n" + sources + "\n\n" + credit + "\n" + ai_line + "\n\n" + " ".join(tags["youtube"])
    ig = post["instagram_caption"].strip() + "\n\nSources and credit in the first comment.\n" + ai_line + "\n\n" + " ".join(tags["instagram"])
    tt = post["tiktok_caption"].strip() + " " + " ".join(tags["tiktok"])
    pinned = sources + "\n\n" + credit + "\n" + ai_line
    pc = [f"# Post copy - {run['title']}", "", "Written only from the claims in claims.json. Paste as-is; character counts are in brackets.", "",
          "## YouTube Shorts", "", "Title options (the first is recommended; limit 100 characters):"]
    pc += [f"{i}. {t}  [{len(t)}]" for i, t in enumerate(post["youtube_titles"], 1)]
    yt_tags = [t for g in ("post", "niche", "broad") for t in post.get("tags", {}).get(g, [])]
    pc += ["", f"Description [{len(yt_desc)}]:", "", "```", yt_desc, "```", "",
           f"YouTube Tags ({len(yt_tags)}; paste into Studio, comma separated; at least 10):", "", "```", ", ".join(yt_tags), "```", "",
           "## TikTok", "", f"Caption [{len(tt)}]:", "", "```", tt, "```", "",
           "## Instagram Reels", "", f"Caption [{len(ig)}]:", "", "```", ig, "```", "",
           "## First / pinned comment (all platforms)", "", "```", pinned, "```", "",
           "## Before you post", "",
           "- Turn on each platform's AI-content label if it asks (YouTube altered/synthetic content, TikTok AI-generated content, Instagram AI info). The captions already say the voice is synthetic.",
           "- Check the title and caption against the video once: copy is generated from the script, not from listening to the audio.",
           "- Post the same file; do not upload the TikTok/Instagram watermarked download of another platform's copy.",
           f"- Suggested hook for thumbnails/cover frame: frame 0 ({run['title']} hook text)."]
    (rev / "post_copy.md").write_text("\n".join(pc), encoding="utf-8")
    (rev / "description.txt").write_text(yt_desc, encoding="utf-8")
else:
    desc = [f"{run['title']}", "", sources, "", credit, "", ai_line]
    (rev / "description.txt").write_text("\n".join(desc), encoding="utf-8")
    print("NOTE: script/post.json missing, so only a basic description.txt was written (no titles or per-platform captions)")

names = ["t0"] + [k for k, v in sorted(((k, v) for k, v in cues.items() if isinstance(v, float) and k != "total_duration"), key=lambda kv: kv[1])] + ["last"]
frames = [ROOT / f"build/qa/frames/{n}.png" for n in names if (ROOT / f"build/qa/frames/{n}.png").exists()]
if frames:
    cols = 7; rows_n = (len(frames) + cols - 1) // cols
    inputs = sum([["-i", str(p)] for p in frames], [])
    scales = "".join(f"[{i}]scale=270:480[a{i}];" for i in range(len(frames)))
    rows = []
    for r in range(rows_n):
        idx = list(range(r * cols, min(len(frames), (r + 1) * cols)))
        if len(idx) == 1:   # hstack needs at least two inputs: a single leftover frame passes straight through (padded below)
            rows.append(f"[a{idx[0]}]null[r{r}];")
        elif len(idx) < cols:   # pad the last row with black so hstack widths match
            rows.append("".join(f"[a{i}]" for i in idx) + f"hstack={len(idx)}[r{r}];")
        else:
            rows.append("".join(f"[a{i}]" for i in idx) + f"hstack={cols}[r{r}];")
    fc = scales + "".join(rows) + (f"[r0]null" if rows_n == 1 else "".join(f"[r{r}]" for r in range(rows_n)) + f"vstack={rows_n}")
    if rows_n > 1:
        pad = f"pad=iw:ih:0:0"   # rows of unequal width: pad the narrower row before stacking
        fc = scales + "".join(rows)
        fc = fc.replace(f"[r{rows_n - 1}];", f"[rl];[rl]pad={cols * 270}:480:0:0[r{rows_n - 1}];") if len(frames) % cols else fc
        fc += "".join(f"[r{r}]" for r in range(rows_n)) + f"vstack={rows_n}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", fc, "-frames:v", "1", str(rev / "contact_sheet.png")], check=False)
print("packet written to out/review/:", ", ".join(sorted(p.name for p in rev.iterdir() if p.is_file())))

# permanent copy that start_run.py never moves: finished/<slug>/
slug = run.get("slug", "run")
fin = ROOT / "finished" / slug
fin.mkdir(parents=True, exist_ok=True)
for n in ("final.mp4", "post_copy.md", "description.txt", "script_with_sources.md", "claims.json", "contact_sheet.png", "loudness.txt", "improvements.md"):
    if (rev / n).exists():
        shutil.copy2(rev / n, fin / n)
print("permanent copy:", fin)
