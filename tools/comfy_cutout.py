"""comfy_cutout.py: cut the main subject out of an image with the local ComfyUI (BiRefNet, MIT). Free, local.
  comfy_cutout.py SRC.png DST.png
Copies SRC into ComfyUI's input folder, runs LoadImage -> RemoveBackground -> InvertMask -> JoinImageWithAlpha, saves DST as RGBA."""
import json, shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_avatar import post, get, COMFY_OUT

COMFY_IN = Path(r"E:\comfyui-rocm-091926\input")


def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    name = "cut_" + src.name
    shutil.copy(src, COMFY_IN / name)
    wf = {
        "1": {"class_type": "LoadImage", "inputs": {"image": name}},
        "40": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
        "41": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["40", 0], "image": ["1", 0]}},
        "42": {"class_type": "InvertMask", "inputs": {"mask": ["41", 0]}},
        "43": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["1", 0], "alpha": ["42", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "cutout_" + src.stem, "images": ["43", 0]}},
    }
    pid = post("/prompt", {"prompt": wf, "client_id": "claude-cutout"})["prompt_id"]
    while True:
        h = get(f"/history/{pid}")
        if pid in h: break
        time.sleep(1)
    if h[pid]["status"]["status_str"] != "success": sys.exit(json.dumps(h[pid]["status"])[:600])
    im = h[pid]["outputs"]["9"]["images"][0]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(COMFY_OUT / im.get("subfolder", "") / im["filename"], dst)
    print("cutout ->", dst)


if __name__ == "__main__":
    main()
