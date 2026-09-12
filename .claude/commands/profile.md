---
description: Writes your optimal Upwork profile, ready to paste, from your facts, your audit and the benchmark. Every number in it is backed by your proof file.
argument-hint: "[focus: title | overview | skills | portfolio | video]"
---

# /profile

Use the project-local `upwork-copy` skill. The member described in
`context/me.md` is the person this profile sells; never import a personal voice
or identity from outside this repository.

The fixes the audit found, written out, to the targets the benchmark set. This
command always hands over finished text and the exact place to paste it. The
connector's tool description also documents previewed writes for title,
overview and skills, but those actions remain untested; portfolio, rate and
video stay manual.

Read first: [references/profile-formula.md](../../references/profile-formula.md), then everything that exists of `audit-report.md`, `benchmark.md`, `data/targets.json`, `data/profile.json`, `context/me.md` and `context/proof.md`.

**Focus:** $ARGUMENTS. Given a focus, write only that section of `profile.md` and leave the rest as it is.

**No audit yet?** Run it first; this command needs its findings. A from-scratch
audit report with no profile text to score is enough: continue with the member's
facts and proof, rather than sending them back to `/audit`.
**No benchmark?** Write anyway, stamp the top of `profile.md` with "Written without a benchmark, so the lengths are the formula's, not your profession's. Run /benchmark and re-run this.", and say so before writing.

## Step 1 · Fill your facts, tools first

`context/me.md` and `context/proof.md` are what every later command writes from. Fill them from what already exists before asking anything:

- **Your current profile** (`data/profile.json`): collect every result already
  claimed there as a question to verify, with the source "self-authored Upwork
  profile, <date>". Do not promote it to verified proof merely because it was
  already public.
- **Your contracts:** `list_contracts` action `search`, closed contracts. A job
  title verifies what the member was hired for, not an unstated outcome.
- **Your track record:** earnings bucket, jobs and review count from the profile aggregates. Job Success only if the member gave it.
- **Anything the member already wrote down** in this folder.

Every fact gets its source, date and status: verified or pending. **Never use a
pending claim in client-facing copy.** A result becomes verified only when the
member confirms where it can be checked; a connector aggregate is verified as
an Upwork aggregate. Then ask, in one message, only what is still missing.
Always part of it, unless `context/me.md` already answers it:

1. **The niche.** Name the niche their proof points at and ask whether that is the one. A profile that serves everyone reads as serving no one, and in most professions none of the top three owns a niche, which is the opening.
2. **What they do not do.** One line.
3. **Which result belongs to which project and where it can be checked,** when
   the profile contains result claims that `context/proof.md` does not yet
   verify.

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
- **`## Overview`**: the first two lines once on their own as a quote, because they carry the click. Then the whole overview in one fenced `text` block. No markdown inside it: Upwork shows asterisks as asterisks. Structure comes from emoji or plain bullets. It opens with what the client gets and the strongest relevant verified proof when one exists, lists what you build, names the tools on one line for search, and ends with a specific ask. A good ask invites the client to send their website on Upwork.
- **`## Skills`**: one `- Skill` line each, up to 20, in Upwork's exact spelling (the skill for GoHighLevel is called HighLevel). Use names seen in real profiles or job posts; mark any you could not confirm with "(check the spelling in Upwork's list)".
- **`## Portfolio titles`**: one `- New title (was: old title)` line per project. A number goes in a title only when the proof ties it to that project.
- **`## Video script`**: 60 to 90 seconds, spoken language, in beats: what the client gets, who it is for, up to three relevant verified proofs, how you work, the ask. Optional: a profile goes live without a video, and a profile waiting on one never does.
- **`## Paste order`**: where each section goes on Upwork, click by click.

## Step 3 · The gate

Run `python3 code/profile_draft.py check profile.md`. It re-runs the audit's checks on the draft, the benchmark targets, Upwork's limits, and looks up every number in your proof file. Exit 1 means fix and run it again. Never loosen the draft's claims to pass, and never add a number to the proof file to make the gate quiet: the proof file changes only with the member's word or the connector's.

## Step 4 · Put it live, one field at a time

The connector's 12 September tool description documents `update_profile`
previews for the title (`update_title`), overview (`update_overview`), full skill
set (`set_skills`, up to 20 exact Upwork names), availability, employment,
education and languages. Use a write only when that action is present and it
returns the documented preview. Otherwise hand over the paste-ready version and
click path. Hourly rate, portfolio and video stay manual.

For each writable field, create the preview and show exactly what would replace
what. Call `confirm_preview` only after an explicit yes for that field. One
field, one yes; "approve all" is not a yes for each. If the returned behavior
differs from the documented preview flow, stop and keep the manual handoff. Then
run `/audit` again: the score comes from the live profile, not from the draft.

## Step 5 · Report

Completion report as CLAUDE.md defines it. Link [profile.md](../../profile.md). Next step: paste, then `/audit` again, which should now clear almost every check; what still fails comes back here. End with the Upwork call count.
