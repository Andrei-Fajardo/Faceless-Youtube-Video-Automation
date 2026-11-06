"""Painting image -> video assets (Pillow does the image work: ffmpeg's decoder rejects very large JPEGs).
  painting_prep.py fetch "File:<name>" [--original] [--width N]   download from Wikimedia Commons, write assets/credits.json (licence, source, date).
        Thumbnails stop at 3840 px; --original saves the full-resolution file (assets/paintings/original.jpg) for close zooms on small details.
  painting_prep.py prep [image] [--maxw N]                         build video/assets/painting.jpg (default 3840 px wide; 6400 for detail work) + bg.jpg,
        and store the image size in script/video.json
  painting_prep.py ref "File:<name>" <short-name>                    public-domain reference image for a reference card -> video/assets/refs/<short-name>.jpg
  painting_prep.py detail x0 y0 x1 y1                              full-resolution crop of the zoom target (fractions of the image) -> video/assets/detail.jpg,
        laid exactly over the same spot in the painting by build_video.py so the zoom is sharp
Public-domain only: fetch refuses anything whose Commons licence label does not say public domain / CC0 and prints what it found."""
import json, re, sys, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageEnhance

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "art-shorts-pipeline/0.3 (personal project)"}
img = ROOT / "assets/paintings/painting.jpg"
orig = ROOT / "assets/paintings/original.jpg"


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read()


def fetch(title, width=3840):
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|size|extmetadata&titles=" + urllib.parse.quote(title))
    page = next(iter(json.loads(get(api))["query"]["pages"].values()))
    if "imageinfo" not in page:
        sys.exit(f"STOP: Commons has no file '{title}'")
    ii = page["imageinfo"][0]; m = ii.get("extmetadata", {})
    lic = m.get("LicenseShortName", {}).get("value", "")
    print(f"{title}: {ii['width']}x{ii['height']} | licence label: '{lic}' | credit: {re.sub('<[^>]+>', '', m.get('Credit', {}).get('value', ''))[:140]}")
    if not re.search(r"public domain|cc0|pd", lic, re.I):
        sys.exit("STOP: licence label is not public domain / CC0. Pick another file or another painting.")
    img.parent.mkdir(parents=True, exist_ok=True)
    if "--original" in sys.argv:
        data = get(ii["url"].split("?")[0]); orig.write_bytes(data)
        print(f"saved original {orig.relative_to(ROOT)} ({len(data) // 1048576} MB, {ii['width']}x{ii['height']})")
    else:
        data = get("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(title.replace("File:", "")) + f"?width={width}")
        img.write_bytes(data)
        print(f"saved {img.relative_to(ROOT)} ({len(data) // 1024} KB)")
    cred = {"images": [{"file": "assets/paintings/painting.jpg", "work": title, "source_url": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title),
                        "license": lic, "original_size": f"{ii['width']}x{ii['height']}", "credit_line": re.sub("<[^>]+>", "", m.get("Credit", {}).get("value", "")),
                        "date_accessed": date.today().isoformat()}], "fonts": [],
            "audio": "Ambient bed and sound effects are synthesized locally by tools/sfx.py; the voice is synthetic (ElevenLabs)."}
    (ROOT / "assets/credits.json").write_text(json.dumps(cred, indent=2), encoding="utf-8")
    print("wrote assets/credits.json - still verify the artist died >100 years ago and who holds the painting")


def prep(src, maxw=3840):
    src = Path(src) if src else (orig if orig.exists() else img)
    im = Image.open(src); w, h = im.size
    tw = min(maxw, w); th = round(h * tw / w)
    if im.format == "JPEG": im.draft("RGB", (tw, th))      # decode at reduced size: fast even for 500-megapixel scans
    im = im.convert("RGB").resize((tw, th), Image.LANCZOS)
    out = ROOT / "video/assets"; out.mkdir(parents=True, exist_ok=True)
    im.save(out / "painting.jpg", quality=90, subsampling=0, optimize=True)
    # background: heavily blurred, darkened cover-crop (a smooth colour field, no recognisable shapes)
    s = max(1300 / tw, 2600 / th); big = im.resize((round(tw * s), round(th * s)), Image.LANCZOS)
    x0, y0 = (big.width - 1080) // 2, int((big.height - 1920) * 0.6)
    bg = big.crop((x0, y0, x0 + 1080, y0 + 1920)).resize((5, 9), Image.BOX).resize((1080, 1920), Image.BICUBIC)
    bg = ImageEnhance.Color(bg).enhance(1.1).point(lambda v: int(255 * (v / 255) ** (1 / 1.15)))
    bg = ImageEnhance.Brightness(bg).enhance(0.5)
    bg.save(out / "bg.jpg", quality=92)
    vp = ROOT / "script/video.json"
    if vp.exists():
        v = json.loads(vp.read_text(encoding="utf-8")); v["painting"] = {"width": tw, "height": th}; vp.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"prepared video/assets/painting.jpg ({tw}x{th}, from {w}x{h}) + bg.jpg" + ("; updated script/video.json" if vp.exists() else "; write script/video.json next"))


def detail(x0, y0, x1, y1):
    src = orig if orig.exists() else img
    im = Image.open(src); w, h = im.size
    box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
    crop = im.convert("RGB").crop(box)
    if crop.width > 2400: crop = crop.resize((2400, round(crop.height * 2400 / crop.width)), Image.LANCZOS)
    crop.save(ROOT / "video/assets/detail.jpg", quality=92, subsampling=0)
    vp = ROOT / "script/video.json"; v = json.loads(vp.read_text(encoding="utf-8"))
    v.setdefault("zoom", {})["detail"] = [x0, y0, x1, y1]; vp.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"detail crop {box[2] - box[0]}x{box[3] - box[1]} px of the {w}x{h} original -> video/assets/detail.jpg (recorded in video.json)")


def ref(title, name, width=700):
    """Public-domain reference image (a portrait of a person, a document page) for an on-screen reference card -> video/assets/refs/<name>.jpg.
    Refuses anything that is not public domain / CC0. Never use a photo of a living or private person: use a text-only card for them."""
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|size|extmetadata&titles=" + urllib.parse.quote(title))
    page = next(iter(json.loads(get(api))["query"]["pages"].values()))
    if "imageinfo" not in page:
        sys.exit(f"STOP: Commons has no file '{title}'")
    ii = page["imageinfo"][0]; m = ii.get("extmetadata", {})
    lic = m.get("LicenseShortName", {}).get("value", "")
    print(f"{title}: {ii['width']}x{ii['height']} | licence label: '{lic}'")
    if not re.search(r"public domain|cc0|pd", lic, re.I):
        sys.exit("STOP: licence label is not public domain / CC0.")
    data = get("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(title.replace("File:", "")) + f"?width={width}")
    out = ROOT / "video/assets/refs"; out.mkdir(parents=True, exist_ok=True)
    tmp = out / (name + ".src"); tmp.write_bytes(data)
    im = Image.open(tmp).convert("RGB"); im.thumbnail((width, width)); im.save(out / (name + ".jpg"), quality=90); tmp.unlink()
    cp = ROOT / "assets/credits.json"
    cred = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {"images": [], "fonts": []}
    cred.setdefault("images", []).append({"file": f"video/assets/refs/{name}.jpg", "work": title, "source_url": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title),
                                          "license": lic, "original_size": f"{ii['width']}x{ii['height']}", "date_accessed": date.today().isoformat(), "use": "on-screen reference card"})
    cp.write_text(json.dumps(cred, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved video/assets/refs/{name}.jpg and credited it in assets/credits.json")


def opt(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


args = [a for i, a in enumerate(sys.argv) if not a.startswith("--") and not (i > 0 and sys.argv[i - 1] in ("--width", "--maxw"))]
if len(args) >= 4 and args[1] == "ref":
    ref(args[2], args[3])
elif len(args) >= 6 and args[1] == "detail":
    detail(*(float(a) for a in args[2:6]))
elif len(args) >= 3 and args[1] == "fetch":
    fetch(args[2], opt("--width", 3840))
elif len(args) >= 2 and args[1] == "prep":
    prep(args[2] if len(args) > 2 else None, opt("--maxw", 3840))
else:
    sys.exit(__doc__)
