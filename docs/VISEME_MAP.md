# Lip-sync mouth map (from the LIPREAD mouth chart)

The pronunciation comes from the CMU dictionary (words not in it fall back to letter rules); each phoneme is mapped to one of nine low-key mouths. Consonants whose mouth just follows the neighbouring vowel (t, d, n, l, k, g, ng, th, h, r) keep the previous shape. The mouth closes where the voice (`audio/voice/voice_dry.wav`) is actually silent, and shapes lead the sound by 30 ms.

| Chart mouth(s) | Phonemes (ARPAbet) | Asset (`avatar/raw/mouth/<outfit>_<name>.png`, sprite `v_<name>.png`) |
|---|---|---|
| b, m, p (lips pressed) | B M P | `closed` (the base `talk.png`, no overlay) |
| f, v (teeth on lower lip) | F V | `fv` |
| w, wh, qu, oo (small pucker) | W UW UH | `oo` |
| o, or, u (rounded open) | OW AO OY | `o` |
| a, e, ar (open, relaxed) | AA AE AW AY EH AH (stressed) | `ah` |
| ee, i, y (mild smile with teeth) | EY IY Y | `ee` |
| s, x, z (teeth together) | S Z | `teeth` |
| schwa, short i, er, soft d/t/n/l (barely parted) | AH0 IH ER | `mid` |
| sh, ch, zh, j (soft purse) | SH CH JH ZH | `sh` |
| eyes closed (blink every 2.6 to 4.4 s) | none | `blink` |

Engine: `tools/lipsync_track.py` (phonemes on syllable peaks), audit with `tools/lipsync_check.py`.
Regenerate a set: `tools/gen_visemes.py mouths <outfit>` (Higgsfield, 0.25 credits each), then `tools/prep_visemes.py <outfit>`.
The first (too pronounced) set is kept in `avatar/raw/mouth_old/`.
