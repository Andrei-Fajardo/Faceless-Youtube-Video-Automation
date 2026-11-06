"""gen_outfits.py: stage 1 makes one base image per outfit (identity from avatar/raw/mv_e.png), stage 2 makes the other poses from that base.
  gen_outfits.py base            5 bases, medium quality (0.5 credits each)
  gen_outfits.py poses [outfit]  5 poses per outfit, each edited from that outfit's base
Calls tools/hf_gen.py, so the credit floor (400) and price printout apply. Output: avatar/raw/<outfit>_<pose>.png"""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv/Scripts/python.exe")
STYLE = ("Stylized extremely low-poly 3D character, visibly faceted flat-shaded triangles, chunky geometric planes. "
         "Waist-up only, cropped at the hips, no legs, facing the camera, plain transparent background. ")
OUTFITS = {
    "tweed": "brown herringbone tweed jacket over a dark green waistcoat with gold buttons, dark green bow tie, white shirt",
    "velvet": "deep burgundy velvet blazer with black satin lapels, cream silk cravat with a gold pin, white shirt, gold pocket-watch chain",
    "navy": "navy pinstripe three-piece suit, light grey waistcoat with gold buttons, white shirt, gold tie bar and a silk pocket square",
    "tailcoat": "charcoal formal tailcoat, white wing collar, white bow tie, white waistcoat, gold cufflinks, white boutonniere",
    "emerald": "emerald-green velvet dinner jacket with black satin shawl lapels, black bow tie, white dress shirt, gold cufflinks",
}
FACE = ("Same man as the reference: about 50, brown swept hair, brown moustache with grey streaks, thin round gold wire glasses, "
        "kind friendly face, holding a brass magnifying glass. ")
POSES = {
    "point": "Expression and pose: warm smile, one finger pointing up and to the side at something, magnifier in the other hand.",
    "lean": "Expression and pose: leaning forward, curious squint, holding the magnifier up to one eye as if examining something.",
    "wow": "Expression and pose: eyebrows raised, mouth open in amazement, one hand open and raised, magnifier in the other.",
    "explain": "Expression and pose: calm explaining face, one open palm out to the side, magnifier held low in the other hand.",
    "laugh": "Expression and pose: eyes closed, big laugh, one hand on the chest, magnifier in the other hand.",
}


def gen(name, prompt, refs, quality):
    cmd = [PY, str(ROOT / "tools/hf_gen.py"), name, "4:5", prompt, "--quality", quality, "--transparent"]
    for r in refs:
        cmd += ["--ref", str(r)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else name)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "base"
    raw = ROOT / "avatar/raw"
    jobs = []
    if mode == "base":
        for o, cloth in OUTFITS.items():
            p = STYLE + FACE + f"Wearing: {cloth}. Pose: neutral friendly, finger raised, magnifier in the other hand."
            jobs.append((f"{o}_idle", p, [raw / "mv_e.png"], "medium"))
    else:
        only = sys.argv[2] if len(sys.argv) > 2 else None
        for o, cloth in OUTFITS.items():
            if only and o != only:
                continue
            for k, v in POSES.items():
                p = STYLE + FACE + f"Keep exactly this outfit and face from the reference: {cloth}. " + v
                jobs.append((f"{o}_{k}", p, [raw / f"{o}_idle.png"], "medium"))
    with ThreadPoolExecutor(5) as ex:
        list(ex.map(lambda j: gen(*j), jobs))


if __name__ == "__main__":
    main()
