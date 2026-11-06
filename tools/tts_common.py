"""Shared Kokoro helpers: lexicon respelling, synthesis, resample to 48 kHz."""
import json
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent.parent
SR_OUT = 48000
SR_TTS = 24000


def load_lexicon():
    return json.loads((ROOT / "tools" / "lexicon.json").read_text(encoding="utf-8"))


def respell(text):
    lex = load_lexicon()
    for k in sorted(lex, key=len, reverse=True):
        text = text.replace(k, lex[k])
    return text


def synth(pipeline, text, voice, speed):
    chunks = [np.asarray(a, dtype=np.float32) for _, _, a in
              pipeline(respell(text), voice=voice, speed=speed, split_pattern=None)]
    audio = np.concatenate(chunks)
    return resample_poly(audio, SR_OUT // SR_TTS, 1).astype(np.float32)
