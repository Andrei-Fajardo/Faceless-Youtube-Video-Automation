"""Word timestamps -> build/captions.json (faster-whisper base.en, CPU).
Runs per line on audio/voice/lines/<id>.wav and offsets by the line's start in build/timeline.json.
Whole-track runs lost ~8 s of timestamps once the pauses grew, so per-line is the reliable path."""
import json
from pathlib import Path
import soundfile as sf
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "build" / "timeline.json").read_text())
m = WhisperModel("base.en", device="cpu", compute_type="int8")
words = []
for line in tl["lines"]:
    a, sr = sf.read(ROOT / "audio" / "voice" / "lines" / f"{line['id']}.wav", dtype="float32")
    a = a if a.ndim == 1 else a.mean(1)
    a = resample_poly(a, 16000, sr).astype("float32")  # array input sidesteps the PyAV open() mismatch
    segs, _ = m.transcribe(a, word_timestamps=True, language="en", vad_filter=False)
    for s in segs:
        for w in s.words:
            words.append({"line": line["id"], "word": w.word.strip(),
                          "start": round(line["start"] + w.start, 3), "end": round(line["start"] + w.end, 3)})
(ROOT / "build" / "captions.json").write_text(json.dumps({"source": "per-line", "words": words}, indent=2), encoding="utf-8")
print(len(words), "words")
for line in tl["lines"]:
    print(line["id"], "|", " ".join(w["word"] for w in words if w["line"] == line["id"]))
