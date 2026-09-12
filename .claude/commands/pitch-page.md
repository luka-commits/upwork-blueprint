---
description: Builds a one-page pitch site for one job, with a live diagram the client can edit, plus the script for your three to four minute Loom over it.
argument-hint: "<job id>"
---

# /pitch-page

One page that makes a client stop scrolling: a headline about their job, your walkthrough video, three proofs, their system drawn as a diagram they can drag and edit, the plan in days, and the next step on Upwork. Plus the Loom script you read while you scroll through it.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md) (the section on links before a contract), `context/me.md`, `context/proof.md`.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 5 does. Never build from the summary: the diagram is drawn from the requirements, and the summary does not carry them.

## Step 2 · Which page is this

- **Anonymous client:** the page pitches the build.
- **The company is named in the posting:** the page opens with what you noticed about their situation, from their own words and public site. Research is fine, contact is not. Every observation must be checkable; a wrong one about their own business ends the conversation. Uncertain which company: treat it as anonymous.

## Step 3 · Understand the mechanism

For every tool the posting names, check `context/tool-knowledge/<tool>.md`. Covered: use it. Not covered: research it now (official docs first), then add what you learned to that file with its source, so the next job does not pay for it again. A familiar category is never a reason to skip this: the specific combination is what the client is paying for.

## Step 4 · Read the posting into a plan

Write down, before drawing: the trigger, the systems they already run, the manual work today, where results must land, the phase two wishes, the constraints. Then five rules: use their words ("your Squarespace form", not "web form"); never invent a fact, draw a "which CRM? to confirm" node instead; mark scope with groups (what ships first, what comes later); every manual step in the posting is a step the diagram takes over; a requirement with its own sentence gets its own node.

Write the graph to `data/pitch-graph-<id>.json`:

- `nodes`: `id`, `label` (a few words), `kind` (`source`, `step`, `sink`, `decision`, `datastore`, `service`, `actor`, `note`, `milestone`), `owner` (`you` builds it, `client` already runs it, `thirdparty` outside service), optional `logo` (a file name in `code/pitch/logos/`), optional `note` (two to four plain sentences for a client outside your field; about half the nodes need one).
- `edges`: `from`, `to`, optional `label`, optional `dashed` for later phases.
- `groups`: `label` and `nodes`, one per milestone. **Milestone one is something live within two to three days.**

## Step 5 · Assemble

```
python3 code/pitch/generate.py <id> --hook "..." \
  --fit-point "number|label|context" (three times, numbers only from context/proof.md) \
  --graph data/pitch-graph-<id>.json --tool "..." (repeat) \
  --timeline "Day 1-2|what ships;;Day 3-5|what ships" --budget "..." --kickoff "..." (repeat)
```

- **Timeline in days, estimated against what you actually deliver with Claude Code,** not agency weeks.
- **Budget:** an honest frame, no invented price. When the posting gives none, say what the quote depends on.
- **Next step** (`--next-step`) points back to Upwork; the default asks them to send their website or current setup there.
- Optional: `--loom-url` once recorded, `--hero-illustration` (a wide scene of their world with the problem solved, generated, no text in it), `--live-artifact "Label|URL"` for anything actually built, `--proof-link "Label|Detail|URL"` for past work with no contact details on it, `--showcase ...` for a real sample of your work.
- Your YouTube videos appear when `context/videos.json` lists them (`{"channel": url, "videos": [{"id", "title", "thumb"}]}`); the channel page itself must show no email or booking link.

## Step 6 · The Loom script

Write `jobs/<id>/loom-script.md`: what you say while scrolling the page, in beats. Their situation, the first milestone, the path through the diagram, the parts that make it valuable to them, one or two proofs from `context/proof.md`, the timeline in days, the ask on Upwork. Spoken language, short sentences, no em-dashes. Three to four minutes.

## Step 7 · The gates

- `python3 code/pitch_check.py page jobs/<id>/pitch.html`: no email, phone, booking link, messenger or social profile anywhere on the page, no unfilled placeholder. Upwork suspends accounts for contact details before a contract, and a linked page counts.
- `python3 code/pitch_check.py loom jobs/<id>/loom-script.md`: three to four minutes of words, ending on Upwork.
- Look at the page: a headless screenshot (Chrome `--headless --screenshot`), then read the image. Never call a page done unseen.

## Step 8 · Online, only if wanted

The page works without hosting as the backdrop for your Loom, and the Loom link goes into the application. To link the page itself, deploy only that file: copy it to `data/deploy/<id>/index.html` and run `vercel deploy data/deploy/<id> --yes` (a free Vercel account, asked for the first time it is needed). Never deploy the whole job folder: it holds your drafts.

## Step 9 · Report

Completion report as CLAUDE.md defines it, with the page and the script linked, and whether the video is still missing. Next step: record the Loom, then `/apply <id>`. Upwork call count.
