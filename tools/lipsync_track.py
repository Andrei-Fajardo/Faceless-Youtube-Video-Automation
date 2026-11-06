"""lipsync_track.py: mouth track = the script's phonemes (what) placed on the voice audio's syllables (when). Local, no external tools.
  lipsync_track.py [--table]     reads audio/voice/voice_dry.wav + build/captions.json, writes build/lipsync.json
1. Word windows from the captions are snapped to where the voice actually starts and stops (energy onset/offset, +-120 ms).
2. Each word's phonemes come from the CMU dictionary (letter rules for unknown names).
3. Each vowel is pinned to a syllable peak in the audio inside that word; consonants fill the time between peaks.
4. Phonemes map to the nine mouths of docs/VISEME_MAP.md (Rhubarb/LIPREAD style). Silence closes the mouth; b/m/p close it briefly.
This follows how forced-alignment lip-sync tools work (Rhubarb Lip Sync, Papagayo): the text decides the shape, the audio decides the time."""
import json, re, sys
from pathlib import Path
import numpy as np
import soundfile as sf
import cmudict
from scipy.signal import find_peaks, resample_poly

ROOT = Path(__file__).resolve().parent.parent
SR, HOP = 16000, 160          # 10 ms frames
CD = cmudict.dict()
LET = {"m": "M", "b": "B", "p": "P", "f": "F", "v": "V", "w": "W", "q": "W", "u": "UW1", "o": "OW1", "a": "AE1", "e": "EH1", "i": "IH1", "y": "IY1",
       "s": "S", "z": "Z", "x": "S", "c": "K", "k": "K", "g": "G", "t": "T", "d": "D", "n": "N", "l": "L", "r": "R", "h": "HH", "j": "JH"}
VMAP = {"B": "closed", "M": "closed", "P": "closed", "F": "fv", "V": "fv", "W": "oo", "UW": "oo", "UH": "oo", "OW": "o", "AO": "o", "OY": "o",
        "AA": "ah", "AE": "ah", "AW": "ah", "AY": "ah", "EH": "ah", "AH": "ah", "EY": "ee", "IY": "ee", "Y": "ee", "IH": "mid", "ER": "mid",
        "S": "teeth", "Z": "teeth", "SH": "sh", "CH": "sh", "JH": "sh", "ZH": "sh",
        "T": "mid", "D": "mid", "N": "mid", "L": "mid", "K": "mid", "G": "mid", "NG": "mid", "TH": "mid", "DH": "mid", "HH": "mid", "R": "mid"}


def spoken(word):
    """digits as they are spoken: 1958 -> nineteen fifty-eight"""
    from num2words import num2words
    def rep(m):
        n = int(m.group(0))
        return num2words(n, to="year") if 1100 <= n <= 2099 and len(m.group(0)) == 4 else num2words(n)
    return re.sub(r"\d+", rep, word.replace(",", ""))


def phones_of(word):
    out = []
    for part in re.split(r"[-\s]+", spoken(word).lower()):
        part = re.sub(r"[^a-z']", "", part)
        if not part: continue
        pr = CD.get(part) or CD.get(part.strip("'"))
        out += pr[0] if pr else [LET[c] for c in part if c in LET] or ["AH1"]
    return out


def viseme(q):
    base = re.sub(r"\d", "", q)
    if base == "AH" and q.endswith("0"): return "mid"   # unstressed schwa barely opens the mouth
    return VMAP.get(base, "mid")


def main():
    v, sr = sf.read(ROOT / "audio/voice/voice_dry.wav"); v = v if v.ndim == 1 else v.mean(1)
    x = resample_poly(v, SR, sr)
    n = len(x) // HOP
    rms = np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(1))
    env = np.convolve(rms, np.ones(3) / 3, "same")
    thr = 0.06 * np.percentile(env, 95)
    active = env > thr
    idx = np.where(active)[0]
    for a, b in zip(idx[:-1], idx[1:]):          # bridge gaps under 90 ms: stop closures inside words are not pauses
        if 1 < b - a <= 9: active[a:b] = True
    T = lambda i: i * HOP / SR
    words = sorted(json.loads((ROOT / "build/captions.json").read_text())["words"], key=lambda w: w["start"])

    segs, table, prev_end = [], [], 0.0
    for k, w in enumerate(words):
        nxt = words[k + 1]["start"] if k + 1 < len(words) else T(n)
        lo = int(max(prev_end, w["start"] - 0.12) * 100); hi = min(int(min(nxt + 0.05, w["end"] + 0.12) * 100), n - 1)
        if hi <= lo: continue
        act = np.where(active[lo:hi + 1])[0]
        if len(act) == 0: continue
        on, off = lo + act[0], lo + act[-1]
        if off - on < 3: off = on + 3
        ph = phones_of(w["word"]); vow = [i for i, q in enumerate(ph) if q[-1].isdigit()]
        e = env[on:off + 1]                     # syllable peaks inside the word, one per vowel
        pk, pr = find_peaks(e, distance=7, prominence=0.04 * e.max() if e.max() > 0 else 0)
        if vow and len(pk) >= len(vow):
            pk = np.sort(pk[np.argsort(pr["prominences"])[::-1][:len(vow)]])
        else:
            pk = np.linspace(0.3, 0.7, max(1, len(vow))) * (off - on) if len(vow) > 1 else np.array([0.45 * (off - on)])
        nuclei = [T(on) + p / 100 for p in pk]
        t0, t1 = T(on), T(off)
        times = [None] * len(ph)
        for j, i in enumerate(vow): times[i] = nuclei[min(j, len(nuclei) - 1)]
        known = [(-1, t0)] + [(i, times[i]) for i in vow] + [(len(ph), t1)]
        for (ia, ta), (ib, tb) in zip(known[:-1], known[1:]):
            gap = list(range(ia + 1, ib))
            for g, i in enumerate(gap): times[i] = ta + (tb - ta) * (g + 1) / (len(gap) + 1)
        # each mouth starts halfway from the previous phoneme, so a vowel's shape is fully there on its syllable peak
        starts = [t0] + [(times[i - 1] + times[i]) / 2 for i in range(1, len(ph))]
        for i, q in enumerate(ph):
            s0 = starts[i]; s1 = starts[i + 1] if i + 1 < len(ph) else t1
            segs.append([viseme(q), s0, max(s1, s0 + 0.01)])
        table.append(f"{w['word']:<14} {t0:6.2f}-{t1:5.2f}  " + " ".join(f"{q}:{viseme(q)}" for q in ph))
        prev_end = t1

    full, cur = [], 0.0              # silence closes the mouth; then merge repeats and fold slivers into the longer neighbour
    for vv, a, b in segs:
        if a - cur > 0.06:   # a gap between words closes the mouth only if the voice is really silent there (connected speech keeps it parted)
            gi0, gi1 = int(cur * 100), max(int(cur * 100) + 1, int(a * 100))
            full.append(["closed" if active[gi0:gi1].mean() < 0.5 else "mid", cur, a])
        a = max(a, cur); full.append([vv, a, b]); cur = b
    full.append(["closed", cur, T(n)])

    def merge(sg):
        out = []
        for s in sg:
            if out and out[-1][0] == s[0]: out[-1][2] = s[2]
            else: out.append(list(s))
        return out
    full = merge(full)
    changed = True
    while changed:
        changed = False
        for k in range(1, len(full) - 1):
            vv, a, b = full[k]
            if b - a < (0.05 if vv in ("closed", "fv") else 0.06):
                if full[k - 1][2] - full[k - 1][1] >= full[k + 1][2] - full[k + 1][1]: full[k - 1][2] = b
                else: full[k + 1][1] = a
                del full[k]; full = merge(full); changed = True; break
    # --- VTuber-style jaw: one continuous 0..1 openness from the voice loudness every video frame (log scale, fast attack, slower release),
    # --- quantised into three levels with hysteresis; the mouth FORM (what vowel/consonant) comes from the phoneme segments above.
    FPS = 30; nf = int(T(n) * FPS)
    def ten(f0, f1):
        i0 = max(0, int(f0 * 100)); i1 = min(len(env), max(i0 + 1, int(f1 * 100)))
        return float(env[i0:i1].mean()) if i1 > i0 else 0.0
    loud = np.array([ten(f / FPS - 0.017, f / FPS + 0.017) for f in range(nf)])
    vmax = np.percentile(env, 95); vmin = 0.05 * vmax
    a_t = np.clip((np.log10(np.maximum(loud, 1e-9)) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin)), 0, 1)
    jaw = np.zeros(nf); y = 0.0
    for f in range(nf):                           # attack 60 ms, release 160 ms (exponential smoothing, like Live2D's smoothing setting)
        tau = 0.06 if a_t[f] > y else 0.16
        y += (a_t[f] - y) * (1 - np.exp(-1 / FPS / tau)); jaw[f] = y
    spk = jaw[jaw > 0.08]                         # level thresholds adapt to this voice's own loudness spread (small / medium / wide)
    p = np.percentile(spk, [8, 38, 76]); up = tuple(p); down = tuple(p - 0.07)
    level, lv = np.zeros(nf, int), 0
    for f in range(nf):
        while lv < 3 and jaw[f] > up[lv]: lv += 1
        while lv > 0 and jaw[f] < down[lv - 1]: lv -= 1
        level[f] = lv
    starts = [g[1] for g in full]
    import bisect
    FORM = {"ah": ("ah", "ah2", "ah3"), "mid": ("mid", "ah", "ah2"), "ee": ("ee", "eh", "eh"), "o": ("o", "o2", "o2"), "oo": ("oo", "oo", "oo2")}
    frames = []
    for f in range(nf):
        tm = (f + 0.5) / FPS; g = full[max(0, bisect.bisect_right(starts, tm) - 1)][0]
        if g in ("fv", "teeth", "sh"): frames.append(g)          # consonant mouths win over the jaw: a V is quiet but must still show
        elif g == "closed" or level[f] == 0: frames.append("closed")
        else: frames.append(FORM[g][level[f] - 1])
    # minimum hold: a shape stays at least 3 frames (100 ms); closures and f/v at least 2 (67 ms). Short runs are absorbed by the longer neighbour.
    MINF = lambda lab: 2 if lab in ("closed", "fv") else 3
    runs = []
    for lab in frames:
        if runs and runs[-1][0] == lab: runs[-1][1] += 1
        else: runs.append([lab, 1])
    changed = True
    while changed:
        changed = False
        for k in range(1, len(runs) - 1):
            lab, ln = runs[k]
            if ln < MINF(lab):
                if lab in ("closed", "fv") and runs[k - 1][1] > MINF(runs[k - 1][0]):   # keep a closure/f-v: borrow a frame from the neighbour
                    runs[k - 1][1] -= 1; runs[k][1] += 1
                elif runs[k - 1][1] >= runs[k + 1][1]: runs[k - 1][1] += ln; del runs[k]
                else: runs[k + 1][1] += ln; del runs[k]
                merged = []
                for r in runs:
                    if merged and merged[-1][0] == r[0]: merged[-1][1] += r[1]
                    else: merged.append(r)
                runs = merged; changed = True; break
    frames = [lab for lab, ln in runs for _ in range(ln)]
    out = []
    for f, lab in enumerate(frames):
        if out and out[-1]["v"] == lab: out[-1]["t1"] = round((f + 1) / FPS, 3)
        else: out.append({"v": lab, "t0": round(f / FPS, 3), "t1": round((f + 1) / FPS, 3)})
    json.dump({"segments": out, "fps": FPS}, open(ROOT / "build/lipsync.json", "w"), indent=1)
    from collections import Counter
    print("levels:", Counter(level.tolist()), "| shapes:", dict(Counter(frames)))
    parted = sum(s["t1"] - s["t0"] for s in out if s["v"] != "closed")
    print(f"{len(out)} mouth segments over {T(n):.1f} s | mouth parted {parted:.1f} s | voice active {active.sum() / 100:.1f} s | {len(out) / T(n):.1f} changes/s")
    if "--table" in sys.argv: print("\n".join(table))


if __name__ == "__main__":
    main()
