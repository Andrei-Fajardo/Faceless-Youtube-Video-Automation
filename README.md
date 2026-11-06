# Faceless YouTube Video Automation

A pipeline that turns a topic into a finished 1080x1920 YouTube Short. It covers sourced research, script writing, AI voice-over (ElevenLabs), generated visuals (ComfyUI), automatic lip-sync poses, sound design, a rendered video, and automated QA checks before a human reviews it.

## What is in this repo

- `tools/`: pipeline scripts in Python and Node. Examples: `produce.py`, `build_video.py`, `eleven_tts.py`, `mix.py`, `qa.py`, `lipsync_track.py`, `sound_design.py`, `make_packet.py`.
- `video/`: the HyperFrames composition used to render the final video.
- `calendar/`: a small script that builds a publishing calendar.
- `.claude/skills/` and `.agents/skills/`: skill definitions for each pipeline step.
- `skill_reference/`: the skill notes and the reference-run format.
- `docs/`: notes on the lip-sync viseme map.

## What is not in this repo

Generated media, rendered output, voice samples, prompt files, account settings and API keys are kept out on purpose. Set up your own keys as described in `.env.example`, and keep them in a `.env` file that is never committed.

## Setup

1. Copy `.env.example` to `.env` and add your own API keys.
2. Install the Python and Node packages the scripts import.
3. Set `CHROMIUM_PATH` to your own Chromium headless shell if the renderer can't find one. Replace `<repo-root>` in the skill notes with the folder you cloned into.
4. Run one small step first, such as `python tools/qa.py --help`, before running the full pipeline.

## Notes

Voice and likeness data must have the consent of the person it represents. Check the terms of each service (ElevenLabs, ComfyUI models and any stock sources) before publishing output.
