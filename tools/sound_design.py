"""sound_design.py: automatic sound effects + a soft music pad for a built video. Never touches the voice.
  sound_design.py            reads build/events.json (camera moves, cards, year pop, pose changes) and script/sfx.json (cues for this video),
                             writes audio/mix/sfx_auto.wav (effects stem) and audio/music_bed.wav (pad), both picked up by tools/mix.py.
Sounds: Kenney Interface Sounds + UI Audio (CC0, assets/sfx_lib) and sounds synthesized here (whoosh, shimmer, cloth, soft boom).
Levels are dB relative to the voice's average speech level, before the mix ducks the effects under speech.
script/sfx.json: {"cues": [{"sound": "click", "at": {"line": "S4", "word": "chest", "dt": 0.1}, "db": -8}, {"sound": "ticks", "t": 21.0, "dur": 2.4}, ...]}
"""
import json, re
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
LIB = ROOT / "assets/sfx_lib"
rng = np.random.default_rng(7)
db = lambda x: 20 * np.log10(max(x, 1e-9))


def lib(name):
    p = next(LIB.rglob(name))
    x, sr = sf.read(p); x = x if x.ndim == 1 else x.mean(1)
    if sr != SR: x = resample_poly(x, SR, sr)
    return x.astype(np.float32)


def bp(x, lo, hi, order=2): return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)
def lp(x, f, order=2): return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)


def whoosh(dur):
    """airy whoosh that follows a camera glide: band-passed noise whose centre sweeps up then down, soft envelope"""
    n = int(dur * SR); t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    out = np.zeros(n); hop = 2048
    for i in range(0, n, hop):   # piecewise filter sweep
        c = 400 + 2200 * np.sin(np.pi * min(1.0, i / n)) ** 1.5
        seg = bp(noise[max(0, i - 512):i + hop], c * 0.6, min(c * 1.6, 20000))
        out[i:i + hop] = seg[-len(out[i:i + hop]):]
    env = np.sin(np.pi * t) ** 2
    return (out * env).astype(np.float32)


def shimmer(dur=1.6):
    """soft magical shimmer: high partials with slow tremolo and a gentle fade"""
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * a for f, a in ((2349, .5), (2960, .35), (3520, .3), (4699, .2), (5274, .15)))
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 7 * t)
    env = np.minimum(1, t / 0.25) * np.exp(-t * 2.2)
    return (x * env).astype(np.float32)


def cloth(dur=0.35):
    """a soft fabric rustle for a pose change"""
    n = int(dur * SR); t = np.linspace(0, 1, n)
    x = bp(rng.standard_normal(n), 900, 6000) * (np.sin(np.pi * t) ** 1.5) * (0.7 + 0.3 * rng.standard_normal(n).clip(-1, 1))
    return lp(x, 7000).astype(np.float32)


def soft_boom(dur=1.2):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * (58 * t - 6 * t ** 2)) * np.exp(-t * 4.5) + lp(rng.standard_normal(n), 250) * np.exp(-t * 9) * 0.4
    return x.astype(np.float32)


def ticks(dur):
    """counter ticks that start fast and slow down, like a number settling"""
    tk = lib("tick_002.wav"); n = int(dur * SR) + len(tk); x = np.zeros(n, np.float32); t = 0.0; gap = 0.06
    while t < dur:
        i = int(t * SR); x[i:i + len(tk)] += tk[: n - i] * (0.55 + 0.45 * (1 - t / dur)); t += gap; gap *= 1.12
    return x


def music_pad(total):
    """warm, slow pad (D major: D - Bm - G - A), filtered saw-like voices with soft attack; sits far under the voice"""
    chords = [(146.83, 185.00, 220.00, 293.66), (123.47, 146.83, 185.00, 246.94), (98.00, 146.83, 196.00, 246.94), (110.00, 138.59, 164.81, 220.00)]
    seg = 3.5; n = int((total + 1) * SR); out = np.zeros(n)
    k = 0; t0 = 0.0
    while t0 < total + 1:
        m = min(int((seg + 1.2) * SR), n - int(t0 * SR)); t = np.arange(m) / SR
        tone = np.zeros(m)
        for f0 in chords[k % 4]:
            for det in (-0.12, 0.0, 0.12):
                f = f0 * 2 ** (det / 12)
                tone += sum(np.sin(2 * np.pi * f * h * t) / h ** 1.6 for h in range(1, 6))
        env = np.minimum(1, t / 0.9) * np.clip((seg + 1.2 - t) / 1.2, 0, 1)
        i = int(t0 * SR); out[i:i + m] += lp(tone, 1800) * env
        t0 += seg; k += 1
    fade = np.minimum(1, np.arange(n) / SR / 0.6)
    return (out * fade).astype(np.float32)


SOUNDS = {   # name: (maker, default dB re voice speech RMS)
    "card_in": (lambda d: lib("maximize_004.wav"), -12), "card_out": (lambda d: lib("minimize_004.wav"), -17),
    "pop": (lambda d: lib("drop_002.wav"), -10), "click": (lambda d: lib("switch_005.wav"), -7), "buckle": (lambda d: lib("toggle_002.wav"), -6),
    "chime": (lambda d: lib("confirmation_002.wav"), -11), "glass": (lambda d: lib("glass_002.wav"), -13), "pluck": (lambda d: lib("pluck_001.wav"), -12),
    "bong": (lambda d: lib("bong_001.wav"), -12), "glint": (lambda d: lib("glass_005.wav"), -20),
    "whoosh": (lambda d: whoosh(max(0.5, d)), -15), "shimmer": (lambda d: shimmer(d or 1.6), -15), "cloth": (lambda d: cloth(), -22),
    "boom": (lambda d: soft_boom(), -6), "ticks": (lambda d: ticks(d or 2.0), -16),
}


def main():
    ev = json.loads((ROOT / "build/events.json").read_text()); total = ev["total"]
    tl = json.loads((ROOT / "build/timeline.json").read_text()); L = {l["id"]: l for l in tl["lines"]}
    cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
    v, sr = sf.read(ROOT / "audio/voice/voice_dry.wav"); v = v if v.ndim == 1 else v.mean(1)
    fr = v[: len(v) // 4800 * 4800].reshape(-1, 4800); r = np.sqrt((fr ** 2).mean(1)); vrms = np.sqrt((r[r > 10 ** (-45 / 20)] ** 2).mean())

    def when(c):
        if "t" in c: return float(c["t"])
        a = c["at"]; base = L[a["line"]]["start"]
        if a.get("word"):
            w = next(w for w in cap if w["line"] == a["line"] and a["word"].lower() in re.sub(r"[^a-z0-9' -]", "", w["word"].lower()))
            base = w["start"]
        return base + a.get("dt", 0.0)

    cues = []
    for e in ev["events"]:   # automatic: every camera glide whooshes, cards swish in/out, the year pops, pose changes rustle
        if e["type"] == "move": cues.append(("whoosh", e["t"] - 0.05, e["dur"], None))
        elif e["type"] in ("card_in", "card_out"): cues.append((e["type"], e["t"], 0, None))
        elif e["type"] == "year": cues.append(("pop", e["t"] + 0.05, 0, None))
        elif e["type"] == "pose": cues.append(("cloth", e["t"], 0, None))
    sfx_file = ROOT / "script/sfx.json"
    if sfx_file.exists():
        for c in json.loads(sfx_file.read_text(encoding="utf-8"))["cues"]:
            cues.append((c["sound"], when(c), c.get("dur", 0), c.get("db")))
    stem = np.zeros(int((total + 2) * SR), np.float32); log = []
    for name, t, dur, lvl in sorted(cues, key=lambda c: c[1]):
        maker, dflt = SOUNDS[name]; x = maker(dur).astype(np.float32)
        act = np.abs(x) > 0.1 * np.abs(x).max(); rms = np.sqrt((x[act] ** 2).mean()) if act.any() else 1.0
        x = x / rms * vrms * 10 ** ((lvl if lvl is not None else dflt) / 20)
        i = int(max(0.0, t) * SR); j = min(len(stem), i + len(x)); stem[i:j] += x[: j - i]
        log.append(f"{t:6.2f}s {name}")
    stem = stem[: int(total * SR) + SR]
    (ROOT / "audio/mix").mkdir(parents=True, exist_ok=True)
    sf.write(ROOT / "audio/mix/sfx_auto.wav", stem, SR)
    pad = music_pad(total); pad = pad / np.sqrt((pad ** 2).mean()) * vrms * 10 ** (-23 / 20)
    sf.write(ROOT / "audio/music_bed.wav", pad.astype(np.float32), SR)
    print(f"{len(log)} effects placed, peak {db(np.abs(stem).max()):.1f} dBFS; music pad {total:.1f} s at -23 dB re voice")
    print(" | ".join(log))


if __name__ == "__main__":
    main()
