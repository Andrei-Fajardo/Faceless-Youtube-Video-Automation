"""hf_archive.py: download every completed Higgsfield image job to disk so the images outlive the subscription.
  hf_archive.py
Writes avatar/higgsfield_archive/<date>_<jobid8>.png and index.json (job id, date, model, prompt, params, file). The CLI lists at most the 100 newest
jobs, so run this after each batch. Already-downloaded jobs are skipped. Never prints tokens."""
import json, subprocess, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF = str(Path.home() / "AppData/Roaming/npm/higgsfield.cmd")
DST = ROOT / "avatar/higgsfield_archive"


def main():
    DST.mkdir(parents=True, exist_ok=True)
    idx_path = DST / "index.json"
    index = json.load(open(idx_path, encoding="utf-8")) if idx_path.exists() else {}
    r = subprocess.run([HF, "generate", "list", "--image", "--size", "100", "--json"], capture_output=True, text=True, encoding="utf-8")
    jobs = json.loads(r.stdout)
    new = skipped = pending = 0
    for j in jobs:
        if j["status"] != "completed" or not j.get("result_url"):
            pending += 1; continue
        if j["id"] in index and (DST / index[j["id"]]["file"]).exists():
            skipped += 1; continue
        name = f"{j['created_at'][:10]}_{j['id'][:8]}.png"
        try:
            urllib.request.urlretrieve(j["result_url"], DST / name)
        except Exception as e:
            print("failed", j["id"][:8], e); continue
        p = j.get("params", {})
        index[j["id"]] = {"file": name, "created_at": j["created_at"], "model": j.get("job_type"), "prompt": p.get("prompt"),
                          "aspect_ratio": p.get("aspect_ratio"), "resolution": p.get("resolution"), "quality": p.get("quality"),
                          "background": p.get("background"), "result_url": j["result_url"]}
        new += 1
    json.dump(index, open(idx_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    size = sum(f.stat().st_size for f in DST.glob("*.png")) / 1e6
    print(f"archived {new} new, {skipped} already there, {pending} not finished | {len(index)} total, {size:.0f} MB in {DST}")


if __name__ == "__main__":
    main()
