---
name: faceless-research-pipeline
description: Daily content pipeline for a faceless channel. A research agent scans X, Reddit and blogs for ideas nobody has turned into a video yet, a writer agent scores them, picks one clear winner and writes it, and the skill hands you a script, a voiceover file and a visual plan. Use when asked for today's video, a faceless channel idea, or to run the research and writer agents.
---

# Faceless research pipeline

Most auto posting faceless channels feed the AI yesterday's viral videos, so the AI writes what everyone has already seen. This skill starts one step earlier: it researches first, writes second, and only ever makes one video a day from an idea that is still fresh.

## Before the first run

Ask me three things and save the answers to `pipeline/channel.md`, then never ask again:

1. The niche, in one sentence.
2. Up to five subreddits, X accounts or search terms worth watching, and up to five blogs or newsletters.
3. The video length (default 30 to 45 seconds) and the voice: who is speaking and how.

## Step 1: the research agent

Run this as a subagent with the Task tool, so its reading never fills the main conversation. Give it `pipeline/channel.md` and this brief:

> Search the last 48 hours of X, Reddit and the listed blogs for ideas in this niche. Do not use YouTube trending, viral video lists or anything that is already a popular video: that is the recycled content this pipeline exists to avoid. For each idea record the idea in one line, the source URL, when it was posted, the engagement you can actually see on the page, and the result of one YouTube search for it (how many videos already cover it and how old they are). Return at most ten ideas. Never estimate a number you could not see.

Save what it returns to `pipeline/research/<YYYY-MM-DD>.md`.

## Step 2: the writer agent

Score every idea from 1 to 5 on four things, in a table in the same research file:

| Score | What it measures |
|---|---|
| Fresh | Posted in the last day scores 5, two days ago scores 3, older is dropped |
| Demand | The engagement the research agent actually saw |
| Gap | No video on it yet scores 5; a popular video already covering it scores 1 |
| Fit | How squarely it sits in the niche |

The highest total wins. If the top two are within one point, take the one with the bigger gap. If nothing scores at least 14, write no video today and say so: one strong video beats a daily upload of a weak one.

Then write the winner into `pipeline/out/<YYYY-MM-DD>/`:

* `script.md`: the hook in the first line, one idea, one example, and an ending that asks for a comment. Every fact links to its source in the research file.
* `voiceover.txt`: the spoken words only, plain text, ready for any text to speech tool.
* `visuals.md`: one line per beat with its timing and what is on screen (stock, screen capture or an image prompt). Image prompts never ask for words in the picture, because image models print garbled text.

## Step 3: voice and visuals

`voiceover.txt` and `visuals.md` are written so any voice and video tool can take them as they are. Name the tool you use in `pipeline/channel.md` (an API, an n8n workflow, a local model) and this step calls it. Until one is named, stop here and show me the three files.

## Running it every day

Once the first run looks right, schedule it. From the channel folder:

```bash
claude -p "Run the faceless-research-pipeline skill for today"
```

Put that line in cron, launchd or Task Scheduler at the same hour each morning. Each run writes a new dated folder, so nothing is overwritten.

## Rules that keep the channel original

* Never source an idea from a video. Ideas come from posts, threads and articles.
* One video a day at most. Forty recycled uploads is the failure this skill exists to avoid.
* Never invent a number. If the research did not see it, the script does not say it.
* Keep every research file. Last month's research shows which sources keep producing winners, so prune the list in `pipeline/channel.md` once a month.
