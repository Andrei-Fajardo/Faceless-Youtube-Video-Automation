"""comfy_avatar.py: generate the curator with the local ComfyUI (Z-Image Turbo) and cut the background out with BiRefNet.
  comfy_avatar.py NAME SEED [SEED ...] [--w 1152] [--h 1440] [--prompt-file path]
ComfyUI must be running on localhost:8188 (E:\\comfyui-rocm-091926\\comfyui-rocm.bat). Each seed writes
assets/generated/mascot/NAME_<seed>.png (RGBA, transparent background) and NAME_<seed>_raw.png (the uncut render).
Free and local: no credits are spent. Models: z_image_turbo_bf16 (Apache-2.0), birefnet (MIT)."""
import json, shutil, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMFY = "http://127.0.0.1:8188"
OUT = ROOT / "assets/generated/mascot"
COMFY_OUT = Path(r"E:\comfyui-rocm-091926\output")
PROMPT = ("Stylized extremely low-poly 3D character, visibly faceted flat-shaded triangles, chunky geometric planes. "
          "Waist-up only, cropped at the hips, no legs, facing the camera, plain flat light-grey background. "
          "A mature distinguished man, about 55, brown swept hair, brown moustache with grey streaks, thin round gold wire glasses, "
          "kind friendly face with subtle laugh lines, holding a brass magnifying glass. "
          "Wearing a navy pinstripe three-piece suit, light grey waistcoat with gold buttons, white shirt, gold tie bar and a silk pocket square. "
          "Expression and pose: calm explaining face, one open palm out to the side, magnifier held low in the other hand. No text.")


def post(path, body):
    req = urllib.request.Request(COMFY + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def get(path):
    return json.loads(urllib.request.urlopen(COMFY + path, timeout=60).read())


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
        "8": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["3", 0], "vae": ["29", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "40": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
        "41": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["40", 0], "image": ["8", 0]}},
        "42": {"class_type": "InvertMask", "inputs": {"mask": ["41", 0]}},
        "43": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["8", 0], "alpha": ["42", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix + "_cut", "images": ["43", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix + "_raw", "images": ["8", 0]}},
    }


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    name = a[0]; seeds = []; w, h = 1152, 1440; prompt = PROMPT
    i = 1
    while i < len(a):
        if a[i] == "--w": w = int(a[i + 1]); i += 2
        elif a[i] == "--h": h = int(a[i + 1]); i += 2
        elif a[i] == "--prompt-file": prompt = Path(a[i + 1]).read_text(encoding="utf-8").strip(); i += 2
        else: seeds.append(int(a[i])); i += 1
    OUT.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        t0 = time.time(); prefix = f"{name}_{seed}"
        pid = post("/prompt", {"prompt": workflow(prompt, seed, w, h, prefix), "client_id": "claude-avatar"})["prompt_id"]
        while True:
            hist = get(f"/history/{pid}")
            if pid in hist: break
            time.sleep(2)
        st = hist[pid]["status"]["status_str"]
        if st != "success": sys.exit(f"seed {seed}: {st}: {json.dumps(hist[pid]['status'])[:600]}")
        for node, suffix in (("9", ""), ("10", "_raw")):
            im = hist[pid]["outputs"][node]["images"][0]
            src = COMFY_OUT / im.get("subfolder", "") / im["filename"]
            shutil.copy(src, OUT / f"{name}_{seed}{suffix}.png")
        print(f"seed {seed}: {w}x{h} done in {time.time() - t0:.0f}s -> {OUT / (name + '_' + str(seed) + '.png')}")


if __name__ == "__main__":
    main()
