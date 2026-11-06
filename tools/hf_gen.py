"""hf_gen.py: cheap, guarded Higgsfield image generation.
  hf_gen.py NAME ASPECT "PROMPT" [--res 1k] [--quality low] [--transparent] [--ref path ...] [--floor 400]
Saves avatar/raw/NAME.png and prints the credits left. Refuses to run if the balance is under --floor (default 400),
and prints the price first (higgsfield generate cost). Uses the globally installed higgsfield CLI."""
import json, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF = str(Path.home() / "AppData/Roaming/npm/higgsfield.cmd")


def hf(*a):
    r = subprocess.run([HF, *a], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def credits():
    _, o = hf("account", "status")
    import re
    m = re.search(r"([\d.]+) credits", o)
    return float(m.group(1)) if m else None


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        sys.exit(__doc__)
    name, aspect, prompt = a[0], a[1], a[2]
    opt = {"--res": "1k", "--quality": "low", "--floor": "400"}; refs = []; transparent = False
    i = 3
    while i < len(a):
        if a[i] == "--transparent": transparent = True; i += 1
        elif a[i] == "--ref": refs.append(a[i + 1]); i += 2
        else: opt[a[i]] = a[i + 1]; i += 2
    args = ["gpt_image_2_5", "--prompt", prompt, "--aspect_ratio", aspect, "--resolution", opt["--res"], "--quality", opt["--quality"]]
    if transparent: args += ["--background", "transparent"]
    for r in refs: args += ["--image", r]
    code, out = hf("generate", "cost", *args)
    print(f"[{name}] price: {out.strip().splitlines()[-1] if out.strip() else '?'}")
    left = credits()
    if left is None or left < float(opt["--floor"]):
        sys.exit(f"STOP: credits left {left} is under the floor {opt['--floor']}")
    code, out = hf("generate", "create", *args, "--wait", "--wait-timeout", "10m", "--json")
    if code:
        sys.exit(out[-800:])
    data = json.loads(out[out.index("["):] if "[" in out else out)
    item = data[0] if isinstance(data, list) else data
    url = item.get("result_url") or (item.get("results") or [{}])[0].get("url") or item.get("url")
    if not url:
        sys.exit("no result url in: " + out[-600:])
    dst = ROOT / "avatar/raw" / f"{name}.png"
    urllib.request.urlretrieve(url, dst)
    print(f"[{name}] saved {dst} | credits left {credits()}")


if __name__ == "__main__":
    main()
