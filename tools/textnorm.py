"""Spoken-form normalization shared by ingest_voice.py and build_video.py.
Whisper writes numerals ("1642", "1940s", "2"); scripts spell them ("sixteen forty-two", "nineteen forties", "two").
Both sides are expanded to the same spoken tokens so alignment works for any painting, any date, any number."""
import re
from num2words import num2words


def _plural(w):
    return w[:-1] + "ies" if w.endswith("y") else w + "s"


def _word_tokens(w):
    """One raw word -> list of lowercase spoken tokens."""
    w = w.replace(" ", " ").lower().strip()
    m = re.fullmatch(r"[^\w]*(\d{3,4})(s?)[^\w]*", w)
    if m:
        n, pl = int(m.group(1)), m.group(2)
        spoken = num2words(n, to="year") if 1000 <= n <= 2099 else num2words(n)
        parts = re.sub(r"[^a-z ]", " ", spoken).split()
        if pl and parts: parts[-1] = _plural(parts[-1])
        return parts
    m = re.fullmatch(r"[^\w]*([\d,]+)[^\w]*", w)
    if m and re.search(r"\d", m.group(1)):
        parts = re.sub(r"[^a-z ]", " ", num2words(int(m.group(1).replace(",", "")))).split()
        return parts
    w = re.sub(r"[^a-z0-9' -]", "", w).replace("-", " ")
    return [t for t in w.split() if t]


def tokens_with_owner(words):
    """list of raw words -> (tokens, owner index of each token)"""
    toks, own = [], []
    for i, w in enumerate(words):
        for t in _word_tokens(w):
            toks.append(t); own.append(i)
    return toks, own
