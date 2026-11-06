"""lipsync_check.py: frame-by-frame audit of the built page against the voice.
Reads video/index.html (pose swaps and mouth sets) and audio/voice/voice_dry.wav. Reports how long the voice sounds while the mouth is frozen
in a non-talking pose or shut, and the lag between mouth opening and voice energy (positive = mouth leads)."""
import re
from pathlib import Path
import numpy as np, soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "video/index.html").read_text(encoding="utf-8")
v, sr = sf.read(ROOT / "audio/voice/voice_dry.wav"); v = v if v.ndim == 1 else v.mean(1)
hop = sr // 100; n = len(v) // hop
env = np.convolve(np.sqrt((v[:n * hop].reshape(n, hop) ** 2).mean(1)), np.ones(3) / 3, "same")
active = env > 0.06 * np.percentile(env, 95)
ev = sorted((float(t), k, n_, int(o)) for k, n_, o, t in re.findall(r'tl\.set\("#(mp|mv)_([a-z0-9]+)", \{opacity: ([01])\}, ([0-9.]+)\)', html))
for n_, o, d, t in re.findall(r'tl\.fromTo\("#mv_([a-z0-9]+)", \{opacity: [01]\}, \{opacity: ([01]), duration: ([0-9.]+)[^}]*\}, ([0-9.]+)\)', html):
    ev.append((float(t) + float(d) / 2, "mv", n_, int(o)))   # a cross-fade counts at its midpoint
ev.sort()
W = {"mid": .2, "ah": .45, "ah2": .7, "ah3": .95, "eh": .55, "ee": .3, "o": .35, "o2": .6, "oo": .25, "oo2": .35, "fv": .1, "teeth": .2, "sh": .3}
start_pose = re.search(r'id="mp_([a-z]+)"[^>]*opacity:1', html).group(1)
pose, mouth, j = start_pose, set(), 0
op = np.zeros(n); talking = np.zeros(n, bool)
for i in range(n):
    t = i / 100
    while j < len(ev) and ev[j][0] <= t:
        _, k, nm, o = ev[j]; j += 1
        if k == "mp" and o: pose = nm
        if k == "mv" and nm != "blink": (mouth.add(nm) if o else mouth.discard(nm))
    talking[i] = pose == "talk"; op[i] = max([W[m] for m in mouth], default=0) if talking[i] else 0
frozen = (active & ~talking).sum() / 100; shut = (active & talking & (op == 0)).sum() / 100
def corr(L):
    a = op[:n - L] if L >= 0 else op[-L:]; b = env[L:] if L >= 0 else env[:n + L]; m = min(len(a), len(b)); return float(np.corrcoef(a[:m], b[:m])[0, 1])
res = {L: corr(L) for L in range(-20, 21)}; best = max(res, key=res.get)
print(f"voice sounding {active.sum() / 100:.1f} s | while frozen in another pose {frozen:.1f} s | while mouth shut {shut:.1f} s")
print(f"mouth vs voice: corr {res[0]:.2f} at 0 ms, best {res[best]:.2f} at {best * 10:+d} ms (positive = mouth leads)")
