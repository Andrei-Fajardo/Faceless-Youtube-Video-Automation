# ComfyUI local image pipeline for "The Odd Detail" (AMD, free)

## Goal
Set up ComfyUI on this PC so Claude Code can generate the channel's still images locally through an MCP
server, at no per-image cost: the curator mascot (poses and mouth/eye states), backdrops, frame overlays,
and prop cutouts, delivered as files that HyperFrames can use. The paintings themselves are NOT generated;
they come from public-domain museum scans.
This file adds to the project's `CLAUDE.md`; its hard rules still apply (free only, no credentials, commit
after each stage, stop at every STOP marker).

## Hardware and constraints
- GPU: AMD Radeon RX 9060 XT 16 GB (RDNA 4). CPU: Ryzen 5 7600. RAM: 32 GB DDR5.
- Windows or Linux: detect it in Stage 0 and follow the matching path.
- ROCm support for RDNA 4 on Windows is described by the ComfyUI docs as experimental, so expect some
  trial and error. Report problems plainly; do not hide failures.

## Hard rules for this setup
- Free and local only. No cloud API keys, no paid image services.
- Commercial-use licenses only. Record each model's license in the manifest (see Stage 6). When a model
  card and a blog disagree, trust the model card, and tell me about the conflict.
  Do NOT use models that are non-commercial or research-only. As of my research this includes FLUX.1 [dev],
  FLUX.2 [dev], FLUX.2 [klein] 9B, and BRIA RMBG. Check the model card again before downloading.
- Download models only from the official repository on Hugging Face (or the official ComfyUI model repos).
  Prefer `.safetensors`. Do not load `.ckpt`, `.pt`, `.pth`, or `.bin` files, which can execute code.
- Custom nodes are a known attack surface (malicious nodes have stolen credentials and one campaign
  auto-installed malicious nodes). Install none unless the task needs it. If one is needed: it must be
  listed in the ComfyUI Registry or widely used, you must read its README and skim its code, and you must
  tell me its name and why before installing.
- Keep ComfyUI and any MCP server bound to localhost. Never run the MCP server's HTTP mode on `0.0.0.0`,
  and do not enable its experimental embedded-agent or tunnel features.
- Do not put MCP tools that install, download, remove, or stop things on auto-approve.
- No real-person likenesses. No text inside generated images (add all text in HyperFrames).

## Stage 0: environment check (report, fix what you can)
Report: OS and version, AMD driver version, `node -v` (the MCP server needs 22 or newer), `python --version`,
`git --version`, free disk space on each drive (aim for at least 50 GB free where ComfyUI and models will live;
tell me if it is lower), and confirmation that the GPU is the RX 9060 XT with 16 GB.
STOP and show me the report.

## Stage 1: install ComfyUI with AMD ROCm support
Try in this order and stop at the first that works:
1. ComfyUI Desktop for Windows (v0.7.0 and later has official AMD ROCm support; the installer normally
   picks ROCm by default).
2. The official ComfyUI portable build for AMD GPUs from the ComfyUI GitHub releases page.
3. Manual install in a venv, then the RDNA 4 PyTorch nightly from AMD:
   `pip install --pre torch torchvision torchaudio --index-url https://rocm.nightlies.amd.com/v2/gfx120X-all/`
   (On Linux, use the stable ROCm wheel documented in the ComfyUI README instead.)
Follow the current instructions at docs.comfy.org and the ComfyUI README over anything in this file.
Do not use unofficial ROCm forks.
Verify: ComfyUI starts; its system stats show the Radeon GPU (not CPU); a built-in template
(Workflow, Browse Templates) generates one image. Note the port (Desktop usually uses 8000; the CLI
version uses 8188) and the data directory (the folder containing `models/`).
STOP: show me the first image, the GPU line from system stats, and the time it took.

## Stage 2: models (all commercial-friendly; confirm each license on its model card first)
Use the model files and loader settings from ComfyUI's own template for each model, so filenames match.
Candidates for the bake-off (download only what Stage 4 needs; models are large):
- A. FLUX.2 [klein] 4B: Apache-2.0, fits in 16 GB, combines generation and editing, which matters for
  keeping the mascot consistent. Needs its own text encoder and VAE per the ComfyUI template.
- B. Z-Image Turbo: Apache-2.0, fast, around 16 GB; may be tight on this card.
- C. SDXL base 1.0: permissive OpenRAIL++ license, about 8 GB, with the biggest ecosystem of ControlNet
  and IP-Adapter tools. Only needed if A and B cannot keep the mascot consistent.
Also required:
- Background removal: BiRefNet (MIT). Place `birefnet.safetensors` from the Comfy-Org/BiRefNet repo
  in `ComfyUI/models/background_removal/` and use the built-in "BiRefNet: Remove Background" template.
- An upscaler with a commercial-OK license. Check the license before using any.
Notes: on RDNA 4, FP8 models have had problems in some ComfyUI builds. If a model errors or outputs
garbage, try its bf16 or fp16 or GGUF variant instead of debugging FP8 for hours.
STOP: list what you downloaded, file sizes, and each license.

## Stage 3: connect Claude Code to ComfyUI (MCP)
Server: `comfyui-mcp` (npm, MIT). Add it to Claude Code with:
`claude mcp add comfyui -- npx -y comfyui-mcp`
or put this in Claude Code's MCP settings:
```
{ "mcpServers": { "comfyui": { "command": "npx", "args": ["-y", "comfyui-mcp"], "env": {} } } }
```
It auto-detects ComfyUI on ports 8188 then 8000. If it cannot find the install, set `COMFYUI_PATH` to the
folder containing `models/` (and `COMFYUI_PORT` if needed). ComfyUI must be running first.
Verify with `/mcp` (connected), then ask it for system stats, the installed models list, and one test
image through `generate_image`. Then view the result with `view_image`.
Important behaviors to know:
- Its asset registry is in memory and expires (24 hours by default) and clears on restart. Copy every
  accepted image into this project right away and record it in the manifest.
- Workflows saved as JSON in `~/.comfyui-mcp/workflows` become their own typed MCP tools if inputs are
  marked with `PARAM_PROMPT`, `PARAM_INT_<n>`, `PARAM_FLOAT_<n>`, `PARAM_STRING_<n>`, or `PARAM_BOOL_<n>`.
  Use that for the production workflows in Stage 5.
- `generate_with_ip_adapter` needs the ComfyUI_IPAdapter_plus custom node. Do not install it unless the
  Stage 4 results show you need it (see the custom node rule).
- The package is a community project that runs commands on this machine. Skim its source before the first
  run and tell me anything surprising.
STOP: show the `/mcp` status and the test image.

## Stage 4: bake-off for the mascot (the make-or-break test)
Character spec (an original character, not a real person or an existing mascot):
a friendly low-poly 3D curator in round gold-rimmed glasses, a neat small mustache, a deep forest-green
waistcoat with antique-gold buttons, an ivory shirt with rolled sleeves, charcoal trousers, brown shoes,
holding an antique brass magnifying glass. Palette: deep forest green #1F3A2E, antique gold #B08D3C,
aged ivory #EDE4CF, small oxblood #5B1F24 accents. Faceted low-poly style with flat shading, soft studio
lighting, plain flat light-grey background, no text.
Negative prompt: realistic human, photorealistic, resembles a real person or any existing mascot, text,
letters, watermark, extra fingers, extra limbs, distorted hands, cluttered background, neon, harsh shadows.
Test A: for each candidate model (A, B, then C if needed), generate 4 seeds of a full-body front-view
character sheet. Score each (1 to 5): style match, glasses/waistcoat/magnifier correct, hands, clean background.
Test B: take the best result and try to produce 3 poses (idle, pointing up, surprised) with the SAME
face and outfit, using the model's reference-image or edit ability.
Record for every run: model, seconds per image, peak VRAM if available, and whether it errored.
Write `build/qa/mascot_bakeoff.md` with a table and the best images, then STOP and ask me to choose.
If no local setup keeps the character consistent, say so plainly and propose the cheapest fallback
(for example generating only the mascot master and poses with a low-cost hosted model, a few dollars in
total) and let me decide. Do not call any paid service without my approval.

## Stage 5: production workflows
Build and save these as API-format workflows with PARAM tokens so each becomes an MCP tool:
1. `odd_mascot_pose`: reference image plus a pose line, same camera, scale, and background every time.
2. `odd_backdrop`: portrait backdrops (a dim classical gallery wall in deep forest green with warm picture
   lights; and an aged parchment texture), with a calm empty center. No text, no recognizable artworks.
3. `odd_frame`: an ornate antique gilded picture frame on a plain background, for compositing around a
   painting. Generate flat on a plain background so BiRefNet can cut it out.
4. `odd_prop`: single props (brass magnifying glass, etc.) on a plain background.
5. `remove_bg`: BiRefNet cutout that outputs RGBA PNG.
Image sizes: generate backdrops at a size the model handles well in portrait, then upscale to at least
1440 x 2560 for the 1080 x 1920 video canvas. Mascot frames: keep identical size and framing across poses.
Mascot variants to produce for lip-sync and blinking (same pose, only the face changes): mouth closed,
slightly open, wide open, rounded "O", and eyes closed.
Poses to produce: idle, pointing up, pointing sideways, leaning in with the magnifier, surprised, thinking,
laughing, shrugging, "stop and look".

## Stage 6: cutouts, QA, and handoff to HyperFrames
Folder layout:
```
assets/generated/mascot/       mascot_<pose>.png (RGBA), mascot_<pose>_mouth-<state>.png
assets/generated/backdrops/    backdrop_<name>_<seed>.png
assets/generated/frames/       frame_<name>.png (RGBA)
assets/generated/props/        prop_<name>.png (RGBA)
assets/generated/manifest.json
```
`manifest.json` has one entry per accepted image: file, type, prompt, negative prompt, model, model license,
seed, workflow name, size, date.
QA gates (write `build/qa/image_report.md`):
- No readable text, gibberish letters, or watermarks anywhere.
- Mascot consistent across poses: same glasses, colors, proportions, and style. Show me a contact sheet.
- Cutouts: composite each RGBA on a dark and a light background and check for white or dark fringes.
  Re-run or fix the mask if there are halos.
- Palette matches the brand tokens above (sample some pixels).
- Hands and fingers look plausible.
- Every accepted image is in the manifest and every model license is recorded as commercial-OK.
STOP: show me the contact sheet and the QA report.
Then write `docs/IMAGE_PIPELINE.md`: the chosen model and settings, how to regenerate any image from the
manifest, how to start ComfyUI and the MCP server, and known problems with fixes.

## If something fails
- ROCm or driver problems: report the exact error, try the next install path in Stage 1, and tell me if
  the realistic fix is Linux or WSL2. Do not spend hours silently.
- Out of memory: use smaller or quantized variants, lower resolution then upscale, close other GPU apps.
- Black or noisy images: try a different precision (bf16 or fp16) before changing anything else.
- Do not silently change the plan, install extra software, or download extra models. Tell me what you
  changed and why.
