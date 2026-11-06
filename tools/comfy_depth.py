"""comfy_depth.py: depth map for each panel with the local ComfyUI (Depth Anything 3, Small, Apache-2.0).
  comfy_depth.py PREFIX PANEL.png [PANEL.png ...] [--resolution 504] [--normalization min_max]
Writes assets/generated/depth/PREFIX_<n>.png (greyscale; white = near, black = far under min_max normalisation).
Uses the core ComfyUI nodes LoadDA3Model -> DA3Inference (mono) -> DA3Render (depth). The weights must be at
E:\\comfyui-rocm-091926\\models\\geometry_estimation\\depth_anything_3_small.safetensors (Comfy-Org repackage, apache-2.0).
ComfyUI must be running on localhost:8188. Free and local."""
import shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_avatar import post, get, COMFY_OUT, ROOT

COMFY_IN = Path(r"E:\comfyui-rocm-091926\input")
OUT = ROOT / "assets/generated/depth"
MODEL = "depth_anything_3_small.safetensors"


def workflow(src_name, resolution, normalization, prefix):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": src_name}},
        "2": {"class_type": "LoadDA3Model", "inputs": {"model_name": MODEL, "weight_dtype": "default"}},
        "3": {"class_type": "DA3Inference", "inputs": {"da3_model": ["2", 0], "image": ["1", 0], "resolution": resolution,
                                                     "resize_method": "upper_bound_resize", "mode": "mono"}},
        "4": {"class_type": "DA3Render", "inputs": {"da3_geometry": ["3", 0], "output": "depth",
                                                  "output.normalization": normalization, "output.apply_sky_clip": False}},
        "5": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["4", 0]}},
    }


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    prefix = a[0]; resolution = 504; normalization = "min_max"
    files = []
    i = 1
    while i < len(a):
        if a[i] == "--resolution": resolution = int(a[i + 1]); i += 2
        elif a[i] == "--normalization": normalization = a[i + 1]; i += 2
        else: files.append(Path(a[i])); i += 1
    OUT.mkdir(parents=True, exist_ok=True)
    COMFY_IN.mkdir(parents=True, exist_ok=True)
    for n, src in enumerate(files, 1):
        t0 = time.time()
        name = f"depth_src_{prefix}_{n}.png"
        shutil.copy(src, COMFY_IN / name)
        pid = post("/prompt", {"prompt": workflow(name, resolution, normalization, f"depth_{prefix}_{n}"),
                               "client_id": "claude-depth"})["prompt_id"]
        while True:
            hist = get(f"/history/{pid}")
            if pid in hist: break
            time.sleep(2)
        if hist[pid]["status"]["status_str"] != "success":
            sys.exit(f"depth {n}: {str(hist[pid]['status'])[:600]}")
        im = hist[pid]["outputs"]["5"]["images"][0]
        shutil.copy(COMFY_OUT / im.get("subfolder", "") / im["filename"], OUT / f"{prefix}_{n}.png")
        print(f"depth {n}: {src.name} -> {prefix}_{n}.png in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
