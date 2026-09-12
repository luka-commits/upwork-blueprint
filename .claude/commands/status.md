---
description: Shows the pipeline, today's work and the next move, plus a ready community sprint update from measured activity.
argument-hint: "[focus: today | funnel | clients | sprint]"
---

# /status

A decision-first status from the local pipeline. It makes no Upwork calls and
sends nothing.

**Focus:** $ARGUMENTS. Empty means the complete status. A focus shows only that
section at full depth. Unknown focus: list `today`, `funnel`, `clients` and
`sprint`, then ask which one.

## ROADMAP

WHAT HAPPENS: read the local pipeline, count measured stage history, rank due
work and write one phone-readable report. Under ten seconds.

I NEED FROM YOU: nothing. Run `/sync` first only when current Upwork state matters
and the last sync is stale.

WHAT MIGHT GO WRONG: local status cannot know about a reply, offer or contract
that has not been synced yet.

## Step 1: Check freshness

Run `python3 code/workspace.py` and `python3 code/sync.py last`. If the last sync
is older than the member expects, say so in one line but continue. Never treat a
stale local record as proof that nothing happened on Upwork.

## Step 2: Build the status

Run `python3 code/funnel.py status --write data/status.md`. Read the result and,
when a focus was given, show only that section without changing the file.

The counts come from status history, not only current stage. A lost lead that
replied still counts as a reply. Never invent a rate when there is too little
data; name the count that exists.

## Step 3: Report

Use the completion report from `CLAUDE.md` and link
[the status report](../../data/status.md). Give the first item under `Do next`
as the one next action. Upwork call count: 0.
