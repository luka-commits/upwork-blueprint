---
description: Writes your optimal Upwork profile, ready to paste, from your facts, your audit and the benchmark. Every number in it is backed by your proof file.
argument-hint: "[focus: title | overview | skills | portfolio | video]"
---

# /profile

The fixes the audit found, written out, to the targets the benchmark set. The connector cannot write title, overview, skills, portfolio or video, so this command hands over finished text and the exact place to paste it.

Read first: [references/profile-formula.md](../../references/profile-formula.md), then everything that exists of `audit-report.md`, `benchmark.md`, `data/targets.json`, `data/profile.json`, `context/me.md` and `context/proof.md`.

**Focus:** $ARGUMENTS. Given a focus, write only that section of `profile.md` and leave the rest as it is.

**No audit yet?** Run it first, it takes minutes and this command needs its findings. **No benchmark?** Write anyway, stamp the top of `profile.md` with "Written without a benchmark, so the lengths are the formula's, not your profession's. Run /benchmark and re-run this.", and say so before writing.

## Step 1 · Fill your facts, tools first

`context/me.md` and `context/proof.md` are what every later command writes from. Fill them from what already exists before asking anything:

- **Your current profile** (`data/profile.json`): every result you already claim there, word for word, with the source "your Upwork profile, <date>".
- **Your contracts:** `list_contracts` action `search`, closed contracts. The job titles show what you have actually been hired for.
- **Your track record:** earnings bucket, jobs and review count from the profile aggregates. Job Success only if the member gave it.
- **Anything the member already wrote down** in this folder.

Every fact gets its source and its date. **Never add a number the member has not stated or the connector has not returned.** Then ask, in one message, only what is still missing. Always part of it, unless `context/me.md` already answers it:

1. **The niche.** Name the niche their proof points at and ask whether that is the one. A profile that serves everyone reads as serving no one, and in most professions none of the top three owns a niche, which is the opening.
2. **What they do not do.** One line.
3. **Which result belongs to which project,** when the proof has numbers but the portfolio does not.

Do not wait for the answers: write the draft on the recommendation, and list the open questions at the top of `profile.md` under "# Decide first".

## Step 2 · Write profile.md

Write in the member's own voice, taken from how they write today and how they answer, minus everything the formula bans. Plain words, no em-dashes. First three lines, then the decisions:

```
# Your Upwork profile

Written Saturday 12 September 2026 · clears 13 of 13 draft checks · every number backed by your proof file
**Next:** answer the two questions below, then paste the sections in the order at the bottom.
```

Then these sections, with these exact headings, because the gate reads them:

- **`## Title`**: the recommended title alone in a fenced `text` block, at most 70 characters, three or four blocks split by |. Below it, four to seven variants as a list, each with its angle in bold (tool first, outcome first, niche first, audience first). Picking is faster than explaining.
- **`## Overview`**: the first two lines once on their own as a quote, because they carry the click. Then the whole overview in one fenced `text` block. No markdown inside it: Upwork shows asterisks as asterisks. Structure comes from emoji or plain bullets. It opens with what the client gets and a hard number, lists what you build, shows results with numbers from the proof file, names the tools on one line for search, and ends with a specific ask. A good ask invites the client to send their website on Upwork.
- **`## Skills`**: one `- Skill` line each, up to 20, in Upwork's exact spelling (the skill for GoHighLevel is called HighLevel). Use names seen in real profiles or job posts; mark any you could not confirm with "(check the spelling in Upwork's list)".
- **`## Portfolio titles`**: one `- New title (was: old title)` line per project. A number goes in a title only when the proof ties it to that project.
- **`## Video script`**: 60 to 90 seconds, spoken language, in beats: what the client gets, who it is for, three proofs, how you work, the ask. Optional: a profile goes live without a video, and a profile waiting on one never does.
- **`## Paste order`**: where each section goes on Upwork, click by click.

## Step 3 · The gate

Run `python3 code/profile_draft.py check profile.md`. It re-runs the audit's checks on the draft, the benchmark targets, Upwork's limits, and looks up every number in your proof file. Exit 1 means fix and run it again. Never loosen the draft's claims to pass, and never add a number to the proof file to make the gate quiet: the proof file changes only with the member's word or the connector's.

## Step 4 · What the connector can change

Availability, employment, education and languages can be written through `update_profile`. Offer only what the audit flagged, one change at a time, draft first, `confirm_draft` only after an explicit yes.

## Step 5 · Report

Completion report as CLAUDE.md defines it. Link [profile.md](../../profile.md). Next step: paste, then `/audit` again, which should now clear almost every check; what still fails comes back here. End with the Upwork call count.
