"""Monitor-horror sound, synthesized locally (numpy/scipy), deterministic. Writes
  audio/ambient.wav        the bed: mains hum, radio hiss and crackle, the infant's breathing (from the picture's breath schedule),
                           an optional gravelly hummed melody over a detuned music box that stops dead at the cue "stop", the dead
                           second, a tone that rises at the cue "eyes"
  audio/mix/sfx_auto.wav   the effects stem: the events listed in monitor.sound.events (skitter, peel, joint, shimmer, static, thud)
Every time is a spec from video.json (see tools/horror_timing.py), so a new story only edits the JSON.
tools/mix.py then levels the bed against the voice (script/video.json mix.ambient_db), ducks both under speech and masters.
The voice is never processed. Reads build/timeline.json, build/captions.json, build/monitor_events.json (breath schedule)."""
import json, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from horror_timing import Timing

SR = 48000
rng = np.random.default_rng(21)
cfg = json.loads((ROOT / "script/video.json").read_text(encoding="utf-8"))
M = cfg["monitor"]; S = M["sound"]
EV = json.loads((ROOT / "build/monitor_events.json").read_text())
T = Timing(M["cues"])
A = T.at
TOTAL = T.TOTAL
N = int((TOTAL + 1.0) * SR)
t = np.arange(N) / SR
T_STOP, T_TEAR = T.cue("stop"), T.cue("tear")


def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)
def norm(x, p=1.0): return x / (np.abs(x).max() + 1e-12) * p
def interp(points): return np.interp(t, [p[0] for p in points], [p[1] for p in points])
def pts(spec): return interp([(A(a), v) for a, v in spec])   # an envelope from [[time spec, value], ...]
def place(buf, x, at, gain=1.0):
    i = int(max(at, 0) * SR); n = min(len(x), len(buf) - i)
    if n > 0: buf[i:i + n] += x[:n] * gain


def gate(a, b, fade=0.03):   # 1 inside [a, b], with short fades
    return np.clip((t - a) / fade, 0, 1) * np.clip((b - t) / fade, 0, 1)


# ---- the bed ----------------------------------------------------------------------------------------------------------------
bed = np.zeros(N)
tension = pts(S["tension"])
# mains hum + harmonics, slightly beating: a house that is on
hum = (np.sin(2 * np.pi * 50.0 * t) + 0.5 * np.sin(2 * np.pi * 100.2 * t) + 0.25 * np.sin(2 * np.pi * 150.4 * t)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * t))
bed += 0.10 * hum * tension
# radio hiss of the monitor: quiet, with sparse crackle ticks
hiss = hp(rng.standard_normal(N), 3500) * 0.012
tick_n = rng.random(N) < (1.6 / SR)                                  # ~1.6 ticks per second
ticks = lp(hp(tick_n.astype(float) * rng.choice([-1, 1], N), 900), 9000)
ticks = np.convolve(ticks, np.exp(-np.arange(int(0.004 * SR)) / (0.0012 * SR)), "same") * 3.5
bed += (hiss + 0.5 * ticks) * (0.6 + 0.4 * tension)
# sub drone: opens under the melody, breaks off at "stop", swells again at "eyes"
sub = (np.sin(2 * np.pi * 38.0 * t) + 0.7 * np.sin(2 * np.pi * 38.9 * t)) * pts(S["sub"])
bed += 0.22 * sub
# an infant's breathing, on the picture's breath schedule (it stops when the humming stops)
for t0, per in EV["breaths"]:
    n = int(per * SR); u = np.arange(n) / n
    env = np.where(u < 0.42, np.sin(np.pi / 2 * u / 0.42) ** 2, np.cos(np.pi / 2 * (u - 0.42) / 0.58) ** 2)
    air = bp(rng.standard_normal(n), 450, 2200) * env ** 1.4 * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * u))
    i = int(t0 * SR); m = min(n, N - i)
    if m > 0: bed[i:i + m] += 0.075 * air[:m]


# the melody: a music box with the wrong pitch, and a gravelly hum an octave below it
def mbox(freq, dur=2.4, bend=0.0, seed=0):
    n = int(dur * SR); tt = np.arange(n) / SR
    fr = freq * (1 - bend * (1 - np.exp(-tt / 0.9)))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    out = (np.sin(ph) + 0.45 * np.sin(2.76 * ph + 0.3) * np.exp(-tt / 0.5) + 0.25 * np.sin(5.4 * ph) * np.exp(-tt / 0.18)) * np.exp(-tt / 0.95) * (1 - np.exp(-tt / 0.002))
    return norm(out + 0.35 * np.sin(1.006 * ph) * np.exp(-tt / 0.7))   # a slightly out-of-tune second string


def hum_note(freq, dur, bend=0.0, seed=0):
    n = int(dur * SR); tt = np.arange(n) / SR; r = np.random.default_rng(seed)
    vib = 1 + 0.012 * np.sin(2 * np.pi * 4.7 * tt + r.uniform(0, 6)) + 0.004 * lp(r.standard_normal(n), 12)
    ph = np.cumsum(freq * (1 - bend * tt / dur) * vib) / SR
    saw = 2 * ((ph * 1.0) % 1.0) - 1
    voiced = lp(saw, 650, 3) + 0.5 * bp(saw, 800, 1100) * 0.4
    breath = bp(r.standard_normal(n), 300, 2500) * 0.35
    env = np.clip(tt / 0.25, 0, 1) * np.clip((dur - tt) / 0.3, 0, 1)
    return norm((voiced + breath) * env)


mel = [tuple(x) for x in S["melody"]["notes"]]
LULL = A(S["melody"]["start"])
lull = np.zeros(N); humv = np.zeros(N); cyc = 0.0
while LULL + cyc < T_STOP + 0.5:
    for k, (off, fq, d) in enumerate(mel):
        ts = LULL + cyc + off * (1 + 0.03 * (cyc / 8.0) ** 1.2)          # it drags behind as it goes on
        if ts >= T_STOP: break
        bend = min(0.12, 0.02 + 0.02 * (ts - LULL) / 4)
        place(lull, mbox(fq, 2.6, bend, int(ts * 10)), ts, 1.0)
        place(humv, hum_note(fq / 2, 1.1 * d + 0.5, 0.03, int(ts * 7)), ts + 0.05, 1.0)
    cyc += 8.8
cut = gate(0, T_STOP, 0.015)                                              # stops dead at "stop"
swell = interp([(0, 0), (LULL, 0), (LULL + 3, 1.0), (T_STOP, 1.4)])
bed += 0.30 * norm(lull) * cut * swell + 0.34 * norm(humv) * cut * swell
# whispering behind the narrator: breathy syllables, a little to the side of the ear
wh = np.zeros(N)
for ts in np.arange(A(S["whisper_span"][0]), A(S["whisper_span"][1]), 0.31):
    n = int(rng.uniform(0.09, 0.2) * SR); e = np.sin(np.pi * np.arange(n) / n) ** 2
    place(wh, bp(rng.standard_normal(n), 1800, 6500) * e * rng.uniform(0.3, 1.0), ts + rng.uniform(0, 0.12), 1.0)
bed += 0.11 * wh * pts(S["whisper_env"])
# after the tear: nothing but the monitor's own hiss, then a thin tone that rises at "eyes"
tone = np.sin(2 * np.pi * (6900.0 + 20 * np.sin(2 * np.pi * 0.2 * t)) * t) * pts(S["tone"])
bed += tone
dead = 1 - 0.97 * gate(T_STOP, T_TEAR + 0.2, 0.02)                      # the dead second: everything but a trace falls away
bed *= dead
# the melody returns once, far away (a half-step flat, slowing)
ret = S["melody"]["return"]
back = np.zeros(N)
for off, fq, d in mel[:ret["notes"]]:
    place(back, mbox(fq * ret["detune"], 2.8, 0.05, int(off * 11)), A(ret["at"]) + off * 1.15, 1.0)
bed += ret["gain"] * norm(back) * pts(ret["fade"])
sf.write(ROOT / "audio/ambient.wav", norm(bed, 0.5).astype(np.float32), SR)


# ---- effects stem -----------------------------------------------------------------------------------------------------------
def joint_click(seed=0):
    """a dry, wet-edged knuckle crack: two damped resonant ticks and a tiny slide"""
    r = np.random.default_rng(seed); n = int(0.35 * SR); tt = np.arange(n) / SR
    c = np.sin(2 * np.pi * r.uniform(900, 1700) * tt) * np.exp(-tt / 0.006)
    c2 = np.zeros(n); j = int(r.uniform(0.04, 0.09) * SR); m = n - j
    c2[j:] = np.sin(2 * np.pi * r.uniform(1800, 3000) * tt[:m]) * np.exp(-tt[:m] / 0.004) * 0.6
    sl = bp(r.standard_normal(n), 1500, 5500) * np.exp(-tt / 0.05) * 0.18
    return norm(c + c2 + sl)


def paper_peel(dur=1.3, seed=0):
    r = np.random.default_rng(seed); n = int(dur * SR); tt = np.arange(n) / SR
    rate = 40 + 90 * tt / dur
    pulse = (np.sin(2 * np.pi * np.cumsum(rate) / SR) > 0.6).astype(float)
    x = bp(r.standard_normal(n), 900, 7000) * (0.3 + pulse) * np.sin(np.pi * tt / dur) ** 1.4
    return norm(x)


def skitter(dur=2.4, seed=0):
    """dry leaves on pavement: clustered sharp ticks that come and go"""
    r = np.random.default_rng(seed); n = int(dur * SR); out = np.zeros(n)
    dens = lp(np.abs(r.standard_normal(n)), 3) * 6
    for i in np.where(r.random(n) < (30 / SR) * np.clip(dens, 0, 3))[0]:
        m = min(int(0.02 * SR), n - i); tt = np.arange(m) / SR
        out[i:i + m] += bp(r.standard_normal(m), 2500, 9000) * np.exp(-tt / 0.004) * r.uniform(0.3, 1.0)
    return norm(out * np.sin(np.pi * np.arange(n) / n) ** 0.6)


def lens_thud():
    n = int(3.0 * SR); tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(28 + 60 * np.exp(-tt / 0.2)) / SR) * np.exp(-tt / 0.9)
    air = lp(rng.standard_normal(n), 400) * np.exp(-tt / 0.3)
    return norm(norm(boom) + 0.4 * norm(air))


def static_burst(dur=0.45):
    n = int(dur * SR); tt = np.arange(n) / SR
    x = rng.standard_normal(n) * (rng.random(n) > 0.35) * np.exp(-tt / 0.18)
    return norm(hp(x, 300) + 0.4 * rng.standard_normal(n) * np.exp(-tt / 0.05))


def sfx(e):
    """one effect from its event: {"sfx": kind, "at": spec, "db": level vs the voice, plus kind-specific fields}"""
    k = e["sfx"]
    if k == "static": return static_burst(e["dur"])
    if k == "skitter": return skitter(e["dur"], e["seed"])
    if k == "peel": return paper_peel(e["dur"], e["seed"])
    if k == "joint": return joint_click(e["seed"])
    if k == "shimmer":
        n = int(e["dur"] * SR)
        return bp(rng.standard_normal(n), 5200, 9000) * np.sin(np.pi * np.arange(n) / n) ** 2 * 0.5
    if k == "thud": return lens_thud() * e.get("scale", 1.0)
    raise SystemExit(f"unknown sfx kind {k!r}")


v, _ = sf.read(ROOT / "audio/voice/voice_dry.wav"); v = v if v.ndim == 1 else v.mean(1)
fr = v[: len(v) // 4800 * 4800].reshape(-1, 4800); rms = np.sqrt((fr ** 2).mean(1)); vrms = np.sqrt((rms[rms > 10 ** (-45 / 20)] ** 2).mean())
G = lambda db: vrms * 10 ** (db / 20)
stem = np.zeros(N, np.float32)
for e in S["events"]:
    place(stem, sfx(e), A(e["at"]), G(e["db"]))
sf.write(ROOT / "audio/mix/sfx_auto.wav", stem, SR)
print("bed + sfx written | stop %.2f | tear %.2f | eyes %.2f | done %.2f | vrms %.4f" % (T_STOP, T_TEAR, T.cue("eyes"), T.cue("done"), vrms))
