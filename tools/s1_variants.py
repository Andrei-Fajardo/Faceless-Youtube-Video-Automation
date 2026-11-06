"""A/B takes of S1 to address a robotic 'night'. -> audio/voice/s1_variants/"""
import sys
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro import KPipeline
sys.path.insert(0, str(Path(__file__).parent))
from tts_common import ROOT, synth
V = {
  "A_baseline_092": ("The Night Watch is not a night scene.", 0.92),
  "B_slower_086": ("The Night Watch is not a night scene.", 0.86),
  "C_comma_pause": ("The Night Watch, is not a night scene.", 0.92),
  "D_no_period_faster_098": ("The Night Watch is not a night scene", 0.98),
  "E_emphasis_not": ("The Night Watch is not, a night scene.", 0.90),
}
out = ROOT/"audio"/"voice"/"s1_variants"; out.mkdir(parents=True, exist_ok=True)
pipe = KPipeline(lang_code="a")
for k,(t,sp) in V.items():
    a = synth(pipe, t, "bm_lewis", sp); sf.write(out/f"{k}.wav", a, 48000); print(k, round(len(a)/48000,2))
