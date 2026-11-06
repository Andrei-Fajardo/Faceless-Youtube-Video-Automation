"""comfy_panels.py: generate 9:16 full-bleed panels with the local ComfyUI (Z-Image Turbo). Free, no credits.
  comfy_panels.py PREFIX PROMPT_JSON [--seed N] [--w 1152] [--h 2048]
PROMPT_JSON is a list of prompts, one per panel. Writes assets/generated/panels/PREFIX_<n>.png (n from 1).
ComfyUI must be running on localhost:8188 (E:\\comfyui-rocm-091926\\comfyui-rocm.bat)."""
import json, shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_avatar import post, get, COMFY_OUT, ROOT

OUT = ROOT / "assets/generated/panels"


def workflow(prompt, seed, w, h, prefix):
    return {
        "30": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "29": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "28": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "27": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["30", 0]}},
        "33": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["27", 0]}},
        "13": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "11": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3, "model": ["28", 0]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 8, "cfg": 1, "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1,
                                                    "model": ["11", 0], "positive": ["27", 0], "negative": ["33", 0], "latent_image": ["13", 0]}},
        # tiled decode: a one-shot 1152x2048 decode exhausts system RAM for about a minute and freezes the PC
        "8": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["3", 0], "vae": ["29", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    prefix, pf = a[0], a[1]; seed, w, h = 7, 1152, 2048
    i = 2
    while i < len(a):
        if a[i] == "--seed": seed = int(a[i + 1])
        elif a[i] == "--w": w = int(a[i + 1])
        elif a[i] == "--h": h = int(a[i + 1])
        i += 2
    prompts = json.load(open(pf, encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for n, p in enumerate(prompts, 1):
        t0 = time.time()
        pid = post("/prompt", {"prompt": workflow(p, seed + n, w, h, f"{prefix}_{n}"), "client_id": "claude-panels"})["prompt_id"]
        while True:
            hist = get(f"/history/{pid}")
            if pid in hist: break
            time.sleep(2)
        if hist[pid]["status"]["status_str"] != "success": sys.exit(f"panel {n}: {json.dumps(hist[pid]['status'])[:600]}")
        im = hist[pid]["outputs"]["9"]["images"][0]
        shutil.copy(COMFY_OUT / im.get("subfolder", "") / im["filename"], OUT / f"{prefix}_{n}.png")
        print(f"panel {n}: {w}x{h} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
