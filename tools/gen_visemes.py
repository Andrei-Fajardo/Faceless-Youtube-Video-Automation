"""gen_visemes.py: Higgsfield edits of an outfit's explain pose for lip-sync, plus extra expression poses.
  gen_visemes.py mouths OUTFIT [OUTFIT ...]   closed, ah, aa, oo, fv, ee, blink (0.25 credits each) -> avatar/raw/mouth/<outfit>_<name>.png
  gen_visemes.py poses OUTFIT [OUTFIT ...]    think, shrug, proud, worried (0.5 credits each)      -> avatar/raw/<outfit>_<name>.png
Uses tools/hf_gen.py (price shown first, credit floor 300)."""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv/Scripts/python.exe")
B = ("Edit the reference image: keep the exact same character, same head position and size, same pose, same outfit, same framing, "
     "same flat low-poly style and same lighting. Change ONLY the ")
SUB = (" Keep the mouth movement small, subtle and natural, low-key like a calm real speaker, far smaller than an exaggerated cartoon mouth. "
       "Eyes, eyebrows and everything else unchanged.")
MOUTHS = {   # mapped from the LIPREAD mouth chart: closed=b/m/p, fv=f/v, oo=w/oo/qu, o=o/or/u, ah=a/e/ar, ee=ee/i/y, teeth=s/x/z, mid=d/t/n/l/k/g/th/h/schwa, sh=sh/ch/zh/j/r
    "closed": "mouth: lips gently pressed together, calm neutral closed mouth with the faintest smile." + SUB,
    "fv": "mouth: upper front teeth lightly touching the lower lip, a small 'f' or 'v' mouth." + SUB,
    "oo": "mouth: lips softly rounded forward into a small 'oo' pucker with a tiny round gap." + SUB,
    "o": "mouth: lips rounded into a small open 'o', jaw slightly dropped." + SUB,
    "ah": "mouth: relaxed slightly open 'ah', a small gap between the lips with the upper teeth just visible." + SUB,
    "ee": "mouth: lips gently stretched sideways into a mild 'ee' with a hint of teeth, a soft smile." + SUB,
    "teeth": "mouth: lips slightly parted with upper and lower teeth together showing a thin line of teeth, like an 's' sound." + SUB,
    "mid": "mouth: lips just barely parted, a tiny relaxed gap, as in a soft 'd', 't' or 'n' sound." + SUB,
    "sh": "mouth: lips softly pushed forward in a small pursed 'sh' shape with a hint of teeth." + SUB,
    "blink": "eyes: both eyes closed in a relaxed blink. Mouth unchanged, lips gently closed.",
}
MOUTHS2 = {   # VTuber-style jaw levels: the same mouth forms at larger openings (natural speech, never shouting)
    "ah2": "mouth: moderately open as in a clear natural 'ah', a clear gap between the lips with upper teeth visible and a little tongue." + SUB,
    "ah3": "mouth: widely open as in a clear 'aah' while speaking, jaw dropped, upper and lower teeth and tongue visible, natural and not shouting." + SUB,
    "eh": "mouth: open medium as in 'eh', lips slightly spread, both upper and lower teeth visible." + SUB,
    "o2": "mouth: rounded and open as in a clear 'oh', jaw dropped, lips in a round shape with a visible dark gap." + SUB,
    "oo2": "mouth: lips pursed forward and slightly open as in 'ooh', small round gap with a hint of teeth." + SUB,
}
MOUTHS3 = {   # a clearly readable F/V: the old one was too subtle to see
    "fv": "mouth: clearly making the 'V' / 'F' sound: the lower lip tucked up and touching the upper front teeth, the upper front teeth clearly visible resting on the lower lip, mouth corners slightly parted. Natural speaking size, not exaggerated. Eyes, eyebrows and everything else unchanged.",
}
POSES = {
    "think": "Keep the outfit and face. New pose and expression: thoughtful, one hand on the chin, eyes looking up and to the side, mouth closed with a small curious smile, the magnifying glass held low in the other hand.",
    "shrug": "Keep the outfit and face. New pose and expression: a shrug, both palms turned up, eyebrows raised, slight sheepish smile, the magnifying glass held in one hand.",
    "proud": "Keep the outfit and face. New pose and expression: proud and satisfied, chest out, eyes gently closed, a confident smile, the magnifying glass held low.",
    "worried": "Keep the outfit and face. New pose and expression: worried and concerned, eyebrows pinched together, mouth slightly open, one hand raised in a stop-and-look gesture, the magnifying glass in the other hand.",
}


def run(args):
    r = subprocess.run([PY, str(ROOT / "tools/hf_gen.py"), *args], capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout + r.stderr).strip().splitlines()
    print(out[-1] if out else args[0], flush=True)


def main():
    mode, outfits = sys.argv[1], sys.argv[2:]
    jobs = []
    for o in outfits:
        ref = str(ROOT / f"avatar/raw/{o}_explain.png")
        if mode in ("mouths", "mouths2", "mouths3"):
            for k, v in {"mouths": MOUTHS, "mouths2": MOUTHS2, "mouths3": MOUTHS3}[mode].items():
                jobs.append([f"mouth/{o}_{k}", "4:5", B + v, "--ref", ref, "--transparent", "--floor", "300"])
        else:
            for k, v in POSES.items():
                jobs.append([f"{o}_{k}", "4:5", v, "--ref", ref, "--transparent", "--quality", "medium", "--floor", "300"])
    with ThreadPoolExecutor(7) as ex:
        list(ex.map(run, jobs))


if __name__ == "__main__":
    main()
