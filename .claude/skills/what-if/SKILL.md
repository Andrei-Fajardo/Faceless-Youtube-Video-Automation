---
name: what-if
description: Second format for the faceless channel family - long-form "What If your body or mind worked differently?" stick-figure films (about 3 minutes, 900-1,050 words). Generates 35 on-brand titles, writes the full second-person story script from the proven prompts, then hands the voiceover to the make-2d-video pipeline (aiTrends 2D Studio) to animate it. Use when the user invokes /what-if (optionally followed by "topics", "script <title>", or "render") or asks for a What If video, a stick-figure video, or a long-form video.
---

# What If (long-form 2D film)

The channel's first format is "The Odd Detail" (30 s low-poly Shorts, `/short-topics`, `/art-short`). This is the second format: a ~3 minute animated short film, 16:9, drawn entirely by code (no image AI), told in second person about one human ability pushed to an extreme. Reference results: IfVerse ("What if you had 500 IQ?", 1M views in 9 days), Last Soul ("1 Minute"). The animation engine is the aiTrends 2D Studio (`make-2d-video` and its stage skills, already in `.claude/skills/`); the kit is installed in `aitrends-2d-studio/`.

## Mode: SHORT-FORM ONLY for now (user decision, 2026-10-31)
The user cannot afford a bigger ElevenLabs plan, so every What If video is a **9:16 Short of 35-50 seconds, 95-120 words, about 600 characters, one ElevenLabs call**. Use `references/short-script-prompt.md` in step 2 (not `script-prompt.md`), `--aspect 9:16` and captions on in the studio, and skip the long-form voice override discussion in step 3. Long-form (`script-prompt.md`, 900-1,050 words) stays in the folder for later; only use it if the user asks. Everything below that mentions 3 minutes, 900-1,050 words or 6,000 characters applies to long-form only.

Arguments: nothing or `topics` = step 1; `script <title or number>` = steps 2-3; `render` = steps 4-7.

## Rules that do not bend
- **Never publish or upload.** Output is a finished MP4 plus a review packet.
- **Sourced facts only.** The script prompt demands at least five real, checkable facts. Never invent a study, researcher, quote or number; write around anything unsure. Put each fact with a source URL in `projects/<slug>/story/claims.md`. Search the web for the exact figures before locking the script (WebSearch, `web-fetch` agent).
- **Keep the narration intact** once the voice exists (the studio rule): never reword, drop or reorder spoken words.
- **The voice is never EQ'd, compressed, stretched or de-essed.** The studio's `mix.py` only ducks music and ambience under the voice and loudness-normalises the whole mix to -14 LUFS (gain only). Do not add voice processing. Use the ElevenLabs voice in `tools/eleven_config.json` (voice id is stored there; never print `.env`).
- **Family-friendly and calm.** No gore, no swearing, no cruelty as comedy, no outrage or "Shocking/Terrifying" words. Disclose that the visuals and voice are AI-made when posting (YouTube altered/synthetic content setting).

## Step 1: topics (`references/topic-prompt.md`)
Read `references/topic-prompt.md` (the channel's own prompt, verbatim). Produce exactly 35 titles in its format, then check the list against `finished/ideas.md` (section "## What If") so nothing repeats. Rank the best 8 by: picturable number, number of distinct consequence layers, how many scenes it gives (cafe, school, sport, lab), and risk (medical claims, anything hinting at self-harm: skip). Show the 35 plus the ranked 8; log the chosen ones under `## What If` in `finished/ideas.md` (status `idea`).

## Step 2: script (`references/script-prompt.md`)
Read `references/script-prompt.md` (verbatim). Fill TOPIC with the chosen title and SERIES CONTEXT with `standalone` (or the previous episode). Write the script exactly to that spec: 900-1,050 words, one continuous paragraph, no labels, numbers in words except years, 18-25 ellipses, 15-20 questions, the arc (cold open, baseline and rule, consequence montage, hidden cost, the heart, crisis and choice, resolution, optional "Is any of this real?", sting, CTA).
Self-check with code, not by eye: count words, ellipses and question marks, check no digits except years, no quotation marks, no markdown. Save to `projects/<slug>/input/script.txt` (and first, before the studio exists, to `finished/what-if/<slug>/script.txt`).
Verify the facts with search, write `claims.md`, and fix the script where a number is shaky. The user approves the script before any paid voice call (it costs about 5,500-6,500 ElevenLabs characters).

## Step 3: voice
Two ways; ask the user once which, default to the first:
1. **ElevenLabs website (zero spend risk, what the tutorial does):** the user pastes the script into ElevenLabs text-to-speech with the channel voice, downloads the MP3, and drops it in `projects/<slug>/input/`. Nothing in this repo is billed.
2. **Our tool:** `tools/eleven_tts.py` is capped at `max_chars_per_call` 1600 and `max_calls_per_run` 2 (Shorts guard rails), so a 6,000-character script does NOT fit. Do not edit those guards on your own. Tell the user the exact numbers and ask them to approve a long-form override (about 4 calls of 1,500 characters stitched in order, never time-stretched). Monthly budget is 30,000 characters (about 8,700 used on 2026-10-31); one long film uses about 6,000.
Either way, the studio transcribes the voice with Whisper and aligns it to the script (needs at least 90% match).

## Step 4-7: animate (hand off to the studio skills)
Run `/make-2d-video` (or `/new-video` -> `/video-styles` -> `/render-video` -> `/video-sound`). Defaults for this channel unless told otherwise:
- 16:9, 1080p, 24 fps, generated music and SFX, **style `dusk`** to start (the tutorial's pick; show the style grid first if the user has not chosen).
- Three user checkpoints stay: setup choices, style grid, and the preview before the final render. If the user is away, take the defaults, say what was assumed, and continue.
- Always draft, look at contact sheets, fix, then render. A full 3-minute render takes minutes on this machine (the tutorial: about 4); a preview first (`--from 0 --to 30 --scale 0.5`).
- ffmpeg is not on PATH here: prefix commands with `PATH="/c/Program Files/File Converter:/c/Program Files/Tracktion/Waveform 13:$PATH"` if `doctor.py` cannot find it.

## Step 8: packet
Copy the final MP4, script, `claims.md` and a `post_copy.md` to `finished/what-if/<slug>/`. `post_copy.md` holds: 3 title options (the What If title is the recommended one), a description with the sources and the AI-disclosure line, 5-8 tags, 3 hashtags, and a pinned-comment question from the script's CTA. Add a 9:16 cut idea (the cold open as a 30-45 s Short) only as a suggestion. `improvements.md` lists what could not be judged without listening or watching. Commit.

## Final report
Short and honest: the title and recommended YouTube title, duration, loudness, the permanent paths under `finished/what-if/<slug>/`, characters of ElevenLabs used, claims that are only `snippet`-verified, and anything unjudged (voice quality, lip-free stick-figure acting). Do not claim the audio sounds good.

## Environment fix (Node 26 + Playwright 1.56)
`npx playwright install` fails on this machine (Playwright 1.56's downloader breaks on Node 26 and leaves a stale `__dirlock`). Do not try to reinstall. `aitrends-2d-studio/render.mjs` honours `CHROMIUM_PATH`; always run the renderer with:
`export CHROMIUM_PATH="<path-to-chrome-headless-shell.exe>"` and `PATH="/c/Program Files/File Converter:/c/Program Files/Tracktion/Waveform 13:$PATH"`. `doctor.py` will still say Chromium is MISSING; ignore it. Self-test passed 2026-11-01 (14 stills, example project).

## Audit log (user request, 2026-11-01): time and resources, reviewed at month end
Wrap every pipeline command so it is timed and logged: `python tools/audit.py run --video <slug> --step <step> [--frames N] [--out FILE] -- <command...>` (steps: voice, whisper-align, contact-sheet, render-final, mix). Log steps you cannot wrap with `python tools/audit.py log --video <slug> --step <step> --secs N --note "..."` (script, web searches, scene authoring). Entries go to `audit/audit_log.jsonl`; `python tools/audit.py report [--month YYYY-MM]` writes `audit/report_YYYY-MM.md` (per step, per video, ElevenLabs characters against the budget, render fps, F: free space). Claude token use and cost cannot be read from inside a command: after each video log `/cost` output with `--step claude-session`. Never invent a duration; use `--note "time not measured"`.

## Script rule learned from the nap video v1 (user feedback)
Build every script on ONE rule stated early ("The rule: ...") and make each later line follow from it. Never stack facts that give different numbers for the same thing (a week, then a day). Read the script back as a stranger would: if a line needs the previous one explained, rewrite it.

## Quality standard for the drawn video (user requirement, 2026-11-01; applies to every What If and Curio video)
The user rejected shots where devices were generic rounded boxes and a "machine" was a box with dots. Every video must meet this before it is rendered.

**1. Real things look like the real thing (realistic up to a point).** Draw the actual object with its real parts and proportions, not a labelled box. Examples: a smartphone has a bezel, a camera island or notch, a status bar and real app screens; a piano has black keys in groups of two and three, a lid and legs; a toaster has slots, a lever, a dial and a cord; a dolphin has a curved back, dorsal fin, flukes and a beak; a pool has a coping edge, tiled steps, ripples and reflections. Study the object first (write its parts list in a code comment), then draw it flat-shaded with a light side, a shadow side, rim light and a contact shadow. Keep scale relations true (door, person, table, child). If a prop is not recognisable without a label, redraw it.

**2. Nothing looks unfinished.** No placeholder shapes, no empty flat areas (fill every set with set dressing), no leftover example-project props, no objects floating without support, no clipped text or objects cut off by accident, no overlapping text, graphics or captions, no off-centre layouts that look accidental. Text sits inside the safe area (9:16: central 900x1500; 16:9: central 90%) and is large enough to read on a phone. One clear focal point per shot.

**3. Story pictures match the words.** The thing named in the narration is on screen when it is spoken (the pool when "pool", the phone when "phone", the two taps when "two taps"). Props set up early (the bed, the signal) reappear when paid off. Characters keep one outfit; screen direction stays consistent in a scene.

**4. Story logic gate before the voice is paid for.** Write down the one rule, the cost, the planted detail and the payoff, then read every line as a stranger. No line may contradict another (numbers, abilities, choices). If an ending relies on a choice, an earlier line must establish that choice.

**5. Review gate before any render.** (a) Render the contact sheet. (b) Open EVERY shot at full size (use `--stills` at two times per shot, near its start and its end), not only the sheet. (c) Fix and repeat until a pass finds nothing. (d) Check the final file with a strip across the whole video. Record anything still weak in `improvements.md`. Do not call a video finished while a shot fails this list.


## Continuity and physics standard (user requirement, 2026-11-01, after the pool scene put children on top of the water)
Applies to every sequence in which the same people or objects appear in more than one shot.
1. **One world per sequence.** Write a single pure function `stateAt(globalTime)` (no drawing, no engine imports) that returns where every person and prop is, and in what mode (`ground`, `air`, `water`, `carried`), at that moment. Every shot of the sequence draws that same state and only chooses a camera. Nobody may appear, vanish or jump between shots unless the story says so.
2. **Real surfaces.** A standing person's feet are on a surface. Water is not a surface: the pool's footprint is forbidden to anyone in `ground` mode. Anyone airborne follows a gravity arc (about 1,860 px/s^2 at this scale); entering water ends the arc with a splash; submerged bodies drift, sink slowly or float and are drawn through a water tint.
3. **Real timing.** Arrival time = distance / speed (adult run about 450 px/s, child jog about 250-300). Reactions take about 0.4 s. People who are turned away or have not heard do not react. A person cannot do something faster than the story shows she knows about it.
4. **Automatic check before every render.** `node tools/continuity_check.mjs <slug>` samples the state every 0.04 s and fails on: a ground-mode person over water, a person floating above a surface, a jump in position faster than 900 px/s, or someone missing from a shot of their sequence. Fix every failure; do not rely on eyes alone.
5. **Narration beats are not time.** If the narration skips ahead, the world still ran: show what each person was doing during the gap (for example, a friend who did not notice because she was turned away).
