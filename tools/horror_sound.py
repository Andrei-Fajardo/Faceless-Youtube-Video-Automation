"""Horror sound design, synthesized locally (numpy/scipy), deterministic. Writes
  audio/ambient.wav        the bed: sub drone, dissonant pad, room tone, heartbeat, riser, held-breath dropout, tail shimmer
  audio/mix/sfx_auto.wav   the effects stem: house creaks, footsteps coming closer, the reveal hit
tools/mix.py then levels the bed against the voice (script/video.json mix.ambient_db), ducks both under speech and masters to -14 LUFS.
The voice is never processed. Times come from build/timeline.json, build/captions.json and build/horror_events.json."""
import json, re, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).parent))
from textnorm import _word_tokens

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(13)
tl = json.loads((ROOT / "build/timeline.json").read_text())
cap = json.loads((ROOT / "build/captions.json").read_text())["words"]
EV = json.loads((ROOT / "build/horror_events.json").read_text())
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
L = {l["id"]: l for l in tl["lines"]}
TOTAL = tl["total_duration"]
N = int((TOTAL + 1.0) * SR)
t = np.arange(N) / SR


def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)
def norm(x, p=1.0): return x / (np.abs(x).max() + 1e-12) * p
def wstart(line, tok):
    for w in cap:
        if w["line"] == line and tok in _word_tokens(w["word"]): return w["start"]
    raise SystemExit(f"{line}:{tok} not found")
def wend(line, tok):
    for w in cap:
        if w["line"] == line and tok in _word_tokens(w["word"]): return w["end"]
    raise SystemExit(f"{line}:{tok} not found")


def place(buf, x, at, gain=1.0):
    i = int(max(at, 0) * SR); n = min(len(x), len(buf) - i)
    if n > 0: buf[i:i + n] += x[:n] * gain


def interp(points):   # [(t, v), ...] -> per-sample envelope
    return np.interp(t, [p[0] for p in points], [p[1] for p in points])


# ---- timing anchors ---------------------------------------------------------------------------------------------------------
t_breath, t_reveal = EV["breath"]                      # picture sinks, then the cut
# real speech bursts measured from the voice (whisper's word times drift by ~0.2 s around the finale)
_v, _ = sf.read(ROOT / "audio/voice/voice_dry.wav"); _v = _v if _v.ndim == 1 else _v.mean(1)
_db = 20 * np.log10(np.sqrt((_v[: len(_v) // 480 * 480].reshape(-1, 480) ** 2).mean(1)) + 1e-9)
BURSTS, _s = [], None
for _i, _x in enumerate(_db):
    if _x > -45 and _s is None: _s = _i * 0.01
    if _x <= -45 and _s is not None and (_db[_i:_i + 25] <= -45).all(): BURSTS.append((_s, _i * 0.01)); _s = None
t_hit = BURSTS[-1][1] + 0.02                           # the hit lands as the last word ends
t_fifteen, t_sixteen = wstart("S3", "fifteen"), wstart("S5", "sixteen")
t_listen_end = L["S6"]["end"]

# ---- the bed ----------------------------------------------------------------------------------------------------------------
sub = np.sin(2 * np.pi * 41.2 * t) + 0.9 * np.sin(2 * np.pi * 41.9 * t + 0.6)             # 0.7 Hz beating
pad = np.zeros(N)
for f0, a, lf in ((110.0, 1.0, 0.061), (116.54, 0.8, 0.083), (164.81, 0.5, 0.047), (233.08, 0.35, 0.071), (311.13, 0.25, 0.057)):   # minor seconds + tritone
    vib = 1 + 0.004 * np.sin(2 * np.pi * 0.23 * t + f0)
    pad += a * np.sin(2 * np.pi * f0 * vib * t + 3 * np.sin(2 * np.pi * lf * t)) * (0.55 + 0.45 * np.sin(2 * np.pi * lf * t + f0))
pad = lp(pad, 900)
room = lp(hp(np.cumsum(rng.standard_normal(N)), 50), 520)
room = room / (np.abs(room).max() + 1e-9)
whine = np.sin(2 * np.pi * 6900 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.31 * t))          # very faint high ghost tone
bed = 0.9 * norm(sub) + 0.55 * norm(pad) + 0.35 * room + 0.05 * whine
bed *= interp([(0, 0.55), (10, 0.75), (17, 1.0), (t_breath, 1.25)])                          # tension grows

# heartbeat (in the bed so it is only ducked a little by the voice): lub-dub, quickening and growing from the 'listened' line
def thump(f0=62, d=0.22):
    n = int(d * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(f0 + 30 * np.exp(-tt / 0.03)) / SR) * np.exp(-tt / 0.07)
hb = np.zeros(N); beat = t_listen_end - 1.0; gap = 1.05
while beat < t_breath - 0.2:
    lvl = np.interp(beat, [t_listen_end - 1.0, t_breath], [0.35, 1.0])
    place(hb, thump(), beat, lvl); place(hb, thump(54, 0.2), beat + 0.2, lvl * 0.7)
    beat += gap; gap = max(0.62, gap - 0.04)
bed += 1.3 * hb

# riser into the held breath: filtered noise sweeping up, then cut dead
t_riser = L["S9"]["start"]
rn = rng.standard_normal(N)
rise = np.zeros(N)
seg = (t >= t_riser) & (t < t_breath + 0.25)
for k in range(8):                                    # a few band slices stepped up in frequency approximate a sweep
    a0 = t_riser + (t_breath - t_riser) * k / 8; a1 = a0 + (t_breath - t_riser) / 8 + 0.4
    m = np.clip(np.minimum((t - a0) / 0.3, (a1 - t) / 0.3), 0, 1)
    rise += bp(rn, 300 * 1.5 ** k, 700 * 1.5 ** k) * m * (0.5 + k * 0.15)
rise *= interp([(t_riser, 0), (t_breath, 1.0), (t_breath + 0.25, 0.8), (t_breath + 0.4, 0)])
bed += 0.5 * norm(rise)

# held-breath dropout: the whole bed goes dead from the end of 'whisper' until the voice says 'seventeen'
t_dead0 = BURSTS[-2][1] + 0.03; t_dead1 = BURSTS[-1][0] + 0.03
bed *= interp([(0, 1), (t_dead0 - 0.12, 1), (t_dead0, 0), (t_dead1 - 0.03, 0), (t_dead1 + 0.35, 1)])
# after the hit: shimmer tail, then everything falls away for the loop-back cut
tail_env = interp([(t_hit, 0), (t_hit + 0.05, 1), (EV["cuts"][-1]["t"] - 0.1, 0.55), (EV["cuts"][-1]["t"] + 0.02, 0)])
shim = np.zeros(N)
for f0 in (1480, 1568, 2217, 3135):
    shim += np.sin(2 * np.pi * f0 * t + 2 * np.sin(2 * np.pi * 5.5 * t)) * 0.3
bed += 0.25 * shim * tail_env
bed *= interp([(0, 1), (EV["cuts"][-1]["t"] - 0.15, 1), (EV["cuts"][-1]["t"] + 0.1, 0.25), (TOTAL + 1, 0.25)])   # on the loop-back the house is quiet again
sf.write(ROOT / "audio/ambient.wav", norm(bed, 0.5).astype(np.float32), SR)


# ---- effects stem -----------------------------------------------------------------------------------------------------------
def creak(dur=0.9, f_lo=620, f_hi=1500, seed=0):
    """stick-slip wood: a train of damped resonant clicks whose rate glides"""
    r = np.random.default_rng(seed); n = int(dur * SR); out = np.zeros(n); pos = 0.0
    while pos < n:
        u = pos / n; per = int(SR * (0.016 - 0.009 * np.sin(np.pi * u) + r.uniform(-0.002, 0.002)))
        fr = f_lo + (f_hi - f_lo) * (0.5 + 0.5 * np.sin(2 * np.pi * (u * 1.3 + r.uniform(0, 0.1))))
        L_ = int(0.012 * SR); tt = np.arange(L_) / SR
        c = np.sin(2 * np.pi * fr * tt) * np.exp(-tt / 0.0035) * r.uniform(0.6, 1.0)
        i = int(pos)
        if i + L_ < n: out[i:i + L_] += c
        pos += max(per, 40)
    out = bp(out, 350, 3200) * np.sin(np.pi * np.linspace(0, 1, n)) ** 0.8
    return norm(out + 0.5 * lp(norm(out), 400))


def step(seed=0, weight=1.0):
    """a heavy footfall on old stairs: low thump + short wood knock + a small creak"""
    r = np.random.default_rng(seed); n = int(0.6 * SR); tt = np.arange(n) / SR
    th = np.sin(2 * np.pi * np.cumsum(95 * np.exp(-tt / 0.05) + 48) / SR) * np.exp(-tt / 0.11)
    kn = lp(r.standard_normal(n), 1100) * np.exp(-tt / 0.018) * 0.7
    out = norm(th + kn)
    c = creak(0.35, 700, 1100, seed + 7)[: n] * 0.35
    out[: len(c)] += c
    return norm(out, weight)


def reveal_hit():
    n = int(2.6 * SR); tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(32 + 90 * np.exp(-tt / 0.12)) / SR) * np.exp(-tt / 0.55)
    burst = rng.standard_normal(n) * np.exp(-tt / 0.07)
    scr = np.zeros(n)
    for f0, a in ((1180, 1.0), (1731, 0.8), (2394, 0.7), (3317, 0.55), (4412, 0.4), (5950, 0.25)):   # inharmonic, bowed-metal screech
        vib = 1 + 0.012 * np.sin(2 * np.pi * (5.5 + a) * tt)
        scr += a * np.sin(2 * np.pi * np.cumsum(f0 * vib * (1 - 0.06 * (1 - np.exp(-tt / 0.25)))) / SR)
    scr *= np.exp(-tt / 0.75) * (1 - np.exp(-tt / 0.004))
    return norm(1.0 * norm(boom) + 0.7 * norm(hp(burst, 150)) + 0.55 * norm(scr))


# levels are relative to the voice's speech RMS, as in mix.py
v, _ = sf.read(ROOT / "audio/voice/voice_dry.wav"); v = v if v.ndim == 1 else v.mean(1)
fr = v[: len(v) // 4800 * 4800].reshape(-1, 4800); rms = np.sqrt((fr ** 2).mean(1)); vrms = np.sqrt((rms[rms > 10 ** (-45 / 20)] ** 2).mean())
G = lambda db: vrms * 10 ** (db / 20)
stem = np.zeros(N, np.float32)
place(stem, norm(thump(45, 0.8), 0.9), 0.0, G(-3))                                           # soft low boom to open
place(stem, creak(1.0, seed=1), t_fifteen + 0.1, G(-8))                                      # fifteen
place(stem, creak(0.9, seed=2), t_sixteen + 0.1, G(-8)); place(stem, creak(0.7, 700, 1700, seed=3), t_sixteen + 0.9, G(-9))   # sixteen, then one more
for k, (ts, db) in enumerate(((L["S6"]["end"] + 0.1, -14), (L["S7"]["end"] + 0.12, -11), (L["S8"]["end"] + 0.1, -8), (L["S8"]["end"] + 0.62, -6))):
    place(stem, step(20 + k), ts, G(db))                                                     # footsteps on the stairs behind him, getting closer, only in the gaps
place(stem, creak(1.2, 500, 900, seed=9), L["S4"]["end"] + 0.15, G(-12))                     # an old house settling
place(stem, reveal_hit(), t_hit, G(4))
sf.write(ROOT / "audio/mix/sfx_auto.wav", stem, SR)
print("bed + sfx written | hit at %.2f s | breath %.2f-%.2f | vrms %.4f" % (t_hit, t_breath, t_reveal, vrms))
