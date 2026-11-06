---
name: short-topics
description: Idea generator for the faceless "The Odd Detail" YouTube Shorts channel. Gives a ranked list of niche topics most people use every day but never think about (objects, interface habits, words, symbols, standards, sounds, rituals, systems: not only physical things), each with a hook, a one-sentence story spine, a sourcing plan, a visual plan and a risk flag, checked against what has already been made. Use when the user invokes /short-topics (optionally followed by a theme, a count, or "cars"), or asks for video ideas, topics or what to make next.
---

# Short Topics

The user invokes this skill to get ideas for the channel (for example `/short-topics`, `/short-topics 12`, `/short-topics digital`, `/short-topics cars`). Everything after the skill name is an optional theme, a count, or both. Default: 8 ideas. Never ask questions first: pick sensible defaults, show the ideas, then offer the next step.

Channel in one line: low-poly animated Shorts (25-32 s) about the overlooked detail inside something people use every day, told as one story with a hook that opens a question, a twist that answers it, and a callback joke. Sources are in every description; illustrations, presenter and voice are AI-generated. Project: `<repo-root>` (method and rules in `art-shorts-CLAUDE.md`, "Script method v3").

## Step 1: read what is already made (never repeat)
Read `finished/ideas.md` and list `finished/` and `runs/` (folder names are topics). Treat as taken: The Night Watch, Garden of Earthly Delights, Cafe Terrace at Night, Arnolfini Portrait, The Ambassadors, Las Meninas, The Kiss, the pull tab (can ring pull), the three-point seat belt. Do not suggest a topic that is the same story, even from another angle, unless the user asks for a sequel.

## Step 2: choose a spread, not one category
Draw ideas from at least five of these buckets. The user said it does not have to be physical: at least a third of the list should be non-physical.
- **Physical things** in the home, pocket, kitchen, bathroom, desk, street, car, shop (a part, a shape, a hole, a colour, a number printed on it).
- **Interface and digital habits**: icons, gestures, buttons, defaults, sounds, loading indicators, the shape of a form field, the keyboard layout, captchas, emoji, file formats, passwords rules, notification dots.
- **Words and phrases** everyone says (origins of "OK", "hello", "break a leg", why we say "um", why "mouse" and "bug", why clocks say AM/PM).
- **Symbols and marks**: the @ sign, the power symbol, the recycling arrows, the play triangle, the barcode, the hazard stripes, the shape of a stop sign, colour codes.
- **Standards and numbers**: paper sizes, shoe sizes, the 12 or 24-hour clock, time zones, why batteries are AA, USB orientation, phone number lengths, why screws turn clockwise.
- **Sounds and signals**: the ringtone, the camera shutter on a phone, the seatbelt chime, the microwave beep, the dial tone.
- **Rituals and systems**: queues, tipping, the handshake, the week, alphabetical order, receipts, the way elevators and crosswalk buttons work.
- **Design choices hiding a safety, cost or accident story**: why something is a particular shape, size, colour, position or material.
- **Cars and the things inside them** (the channel's strongest vein so far): controls, symbols on the dashboard, tyres, mirrors, indicators, fuel cap arrow, horn, pedal order.
If the user gave a theme (for example "digital" or "kitchen"), keep every idea inside it but still vary the angle.

## Step 3: the "overlooked" test (an idea must pass all five)
1. **Daily:** most adults touch, see or say it weekly or more.
2. **Unquestioned:** nobody has asked "why is it like that?", yet there is a reason.
3. **Surprising and checkable:** one specific fact (a person, a year, an accident, a cost saving, a mistake) that changes how you see it, available in at least one authoritative source (museum, patent office, standards body, company history, encyclopedia entry with citations, academic or news source).
4. **Visual:** you can picture three or four distinct low-poly scenes for it (a hook object, a problem, the person or moment, the payoff). A concept with no picture needs a visual metaphor; say what it is.
5. **Story-shaped:** it fits hook -> problem -> who/how -> what -> twist -> callback joke without padding.
Reject: popular myths with weak sources, topics that depend on one brand's logo, anything defamatory or about a living private person, medical or legal advice, tragedies used as punchlines, anything that needs a copyrighted image to make sense.

## Step 4: verify before you recommend
For the top three to five ideas, run a quick web search for the surprising fact and mark each idea `verified` (an authoritative source states it), `snippet` (only a search snippet) or `unverified` (from memory). Never invent a source, a quote, a date or a number. If a fact is contested (several sources disagree), say so and name the disagreement; that is fine for the channel only if the script can tell it as contested. If you have no web tool in this session, mark everything `unverified` and say so at the top.

## Step 5: output
Show a ranked list (best first). For each idea give, in this order:
1. **Topic** (a short name) and its bucket.
2. **Used daily by:** who touches it and when (one line).
3. **Hook line** (<= 8 words, raises a question; no hype words, no "did you know").
4. **Spine:** one sentence in the shape "X seems ordinary, but [odd detail]; so [twist/answer]".
5. **Source to check:** the kind of authoritative source and the exact search to run (never a made-up URL), plus the verification mark from step 4.
6. **Visuals:** the hook object plus two or three scenes, and one pose/emote moment for the curator (worried for the problem, wow for the discovery, shrug for "free"/"nobody knows", proud then laugh for the joke).
7. **Callback joke seed:** a last line that reuses the hook's image or word.
8. **Odds:** crowdedness (low / medium / high: how many Shorts already cover it) and viral score 1-5 (how much the hook surprises a stranger in two seconds). One honest line on the biggest risk (myth, contested date, brand dependence, sensitive angle).
Then:
- A **top three** with one sentence each on why they would perform (hook strength, visual novelty, series potential).
- A **series idea** if several topics share a pattern (for example "the reason is an accident", "a rule written for one person", "the cheaper option won").
- The **next step**: say "tell me the number and I'll research it and build the video", and note that the full build uses the channel pipeline (research with sources -> story script -> ComfyUI panels -> ElevenLabs voice -> poses and sound design -> render and QA), never publishing without explicit confirmation.

## Step 6: keep the log
Append every idea the user chooses (or, if the user chooses none, the top three) to `finished/ideas.md` under a heading `## Everyday topics`, one row per idea: topic | hook | status (`idea`, `researching`, `made`). Do not add rows for ideas you did not show.

## Rules
- Honest odds: do not promise virality. Say what is likely to hook and what is a gamble.
- Facts only from sources; mark every uncertainty. Estimates are attributed ("X credits it with ...").
- Keep it short: ideas are cards, not essays. No filler, no emoji.
- Do not start a video build from this skill unless the user picks a topic and asks for it.
