---
description: Writes your Upwork profile from your own facts and three role models, checks it, and puts it live after one yes. Every number in it is backed by your own evidence.
argument-hint: "[title | overview | skills | portfolio | video | fields]"
---

# /profile

Follow `references/copy.md`. Sell only the member in `context/me.md`; import no outside voice or identity. Most members have no live profile: write one from their facts; a live profile adds the Step 2 review. The deliverable is the written profile, never a report on an old one.

Read first [references/profile.md](../../references/profile.md), the profile sections of [references/upwork.md](../../references/upwork.md) (what the connector may write), then `context/me.md`.

**Focus:** $ARGUMENTS writes only that section of `profile.md`. Every run writes something. **`video`**: Steps 1, 4, 5 only; script from `context/me.md` and existing `profile.md`, no live read, no role models.

## Step 0 · The connector

1. Run `python3 code/workspace.py`.
2. Call `list_accounts`. If the Upwork tools are missing, walk the member through connecting per CLAUDE.md and stop; they rerun `/profile` once the tools show up.
3. Take the Freelancer account's `org_uid`, never write it to a file; if several, ask which.

## Step 1 · Read your facts

`context/me.md` holds background, offer, terms and provable results (`/about-me` writes it; this command interviews nobody). Build everything from its recorded direction (lead branch, offer, audience, country). Never reopen it or suggest another lead branch; a proof/direction mismatch is one line under "Decide first". Ask only for role-model addresses, the rate and a yes per field.

Run `python3 code/context_check.py`. Open questions never stop you: draft from what exists and list every gap under "# Decide first" atop `profile.md`. If `python3 code/context_check.py --status` says untouched, `/about-me` comes first.

**Use the member's own concrete figures, verified or not, worded as their claim; invent none.** The gate checks every number against `context/me.md`. A claim without a figure stays out. With no usable result, lead with offer and background (normal for a first profile).

## Step 2 · What is live, if anything

Call `get_profile` action `get`, save as returned to `data/profile.json`, then `list_highlights` to `data/highlights.json`; skip both if the files are under 24 hours old.

**No or nearly empty profile** is a normal start: say so in one line, skip the rest of Step 2, let Step 5 list what to create. Never invent a score or infer experience.

**With a live profile**, measure and judge it:
- Run `python3 code/profile_checks.py data/profile.json data/highlights.json --json`. The script decides mechanical pass or fail; never overrule it, say in chat if a result looks wrong.
- **Completeness**: list every missing field with its percentage (`references/profile.md`), cheapest first. Only here may you claim a complete profile ranks better.
- **Client filters** (`references/profile.md`): check all six; an empty one fails silently.
- **Judge:** do title, overview, skills, portfolio tell one story; is the result clients care about inside the first 250 characters; does a claim contradict the aggregate in `data/profile.json` (a badge or count Upwork denies is the costliest error); what could the member add that nobody in the lane does (a price, a "not for you if").

**Job Success Score and intro video** come from `context/me.md`; never estimate an unanswered field.

## Step 3 · Skills, role models and rate

**The skills clients type.** One `find_jobs` action `search`, `title` = the direction's main tool or role, `sort` `recency`, `limit` 10. Count the `skills` arrays (Upwork's spelling, the client's vocabulary). Note skills the profile lacks and any it carries that appeared in no posting.

**Three role models, before any draft.** Ask for the addresses right after the plan so the member can fetch them while you read the skills; write no draft until they are in or declined (they give hook, structure, close, lengths). The connector cannot search freelancers, so the member adds a client profile to the same login (Account Settings, no job posted) and uses Upwork talent search with their country, the Top Rated filter and the direction's keywords, favouring high earnings, many finished jobs, recent work. They paste three to five addresses (the `~` is the key) plus two or three newer freelancers from their country with few reviews. If they decline, go on without. Read each in full with `get_profile` action `get` and its `profile_key` (title, whole overview, skills, portfolio titles, employment, rate, earnings, jobs); rank by success (earnings bucket, then jobs and reviews), pick the three closest by shared skills and rate band, name the criteria, and say job success score and hours are not visible. Give four chat lines each: title, how the overview is built from open to close, skills and rate band, one thing to borrow, with URL. Take structure only, never sentences (copying gets flagged). Keep no profile text in any file, only the numbers below.

**The rate.** After the role models, recommend a range, labelled a recommendation, from the hourly ranges and fixed-price medians in the ten postings (with n and today's date), newer low-review profiles' rates, [references/jobs.md](../../references/jobs.md) and the member's proof in `context/me.md`. Never from the Top Rated role models. With no reviews, starting near the bottom and raising it per review is fine; location never means a discount. Label measured versus guess and carry the question "what would you actually quote?" into the live-preview message of Step 6 instead of a separate turn. Once they answer, write it as a number (range fine, their first-quoted figure first) into the `**Hourly rate:**` line of `context/me.md`: `/proposal` prices from it and `data/profile.json` is deleted after a day. Never ask for a smallest project.

## Step 4 · Write profile.md

Start from the role models: borrow how titles are built, overviews open and close, and what the first lines carry; structure, never sentences.

For SEO, Google Ads, WordPress or GoHighLevel, first read the matching file in `templates/profile/` (orientation and vocabulary, never text to paste). Title, hook, skills, portfolio titles and video all follow the recorded direction; if the live profile points elsewhere, write for the recorded direction and say so.

Fix every Step 2 finding in the draft. A finding needing the member's hands becomes a line in `## Profile fields` or `## Completeness` with its cost. Never copy a finding into the file: a checklist in a client-facing overview is a bug.

Write in the member's own voice per `references/profile.md` and `references/copy.md` (plain words, no em-dashes).

First three lines, then a `# Decide first` block with the open items, then the sections:

```
# Your Upwork profile

Written <today's date> · every number backed by your own evidence
**Next:** put the sections live in Step 6.
```

**Take a position.** In chat recommend one title, one hook, one skill order, each with a two-line reason from facts and role models. If the member objects, answer on the merits once: change the draft only for evidence-backed reasons, else keep it and say so. Never open with "fair point", fold under a preference or hand back a menu. Variants only when asked. Write `profile.md` straight away and run the gate; the member approves everything once, in the Step 6 previews.

Then these sections with these exact headings (the gate reads `## Title`, `## Overview`, `## Skills`, `## Portfolio titles`, `## Reference averages`):

- **`## Title`**: one title alone in a fenced `text` block, reason in one line. Description of what the member does plus searched keywords, two or three blocks split by |, main-keyword role first, never a bare keyword stack (`references/profile.md`). Orient on the role models' titles; position the member as a general expert of the branch ("SEO Expert"), not a niche role, unless their background brings it. **Maximum 70 characters**; the gate fails longer.
- **`## Overview`**: the first two lines once alone as a quote, then the whole overview in one fenced `text` block, no markdown. Order: (1) one short hook, about 20 words, in "you"/"your", built from the recorded direction, with the member's own number inside the first 250 characters if one exists; (2) up to three Built/Delivered bullets (normal case) (what, for whom, result with the member's number), strongest first, each one short line of at most 20 words: the outcome only, no process, steps or tool lists; (3) how you work plus one objection answered, a differentiator only if Upwork does not already show it; (4) a close: one imperative plus permission back to "you". Connected sentences, the bullets the only list. Never restate location, totals, earnings, badges or the skills list. With fewer than three verified results use those and ask to confirm the rest; invent none.
- **`## Skills`**: one `- Skill` line each, up to 15 (keywords live in title and skills, never woven into the overview), from the names Step 3 counted in postings, in Upwork's exact spelling (HighLevel, not GoHighLevel); mark unconfirmed ones "(check the spelling in Upwork's list)".
- **`## Portfolio titles`**: one `- New title (was: old title)` line per project. A number goes in a title only when the proof ties it to that project; otherwise keep the title as it is. Never ask the member to link results to projects.
- **`## Reference averages`**: from the role models `- title: N` and `- overview: N` in characters, the three URLs, today's date. The gate fails a title or overview more than 20 % above these; without role models only Upwork's limits apply.
- **`## Video script`**: one connected intro pitch in a fenced `text` block, only the words to read, about 45 seconds (about 100 words) unless the member names another length. Derive it from the sections above and the `video` focus, never invented beside them. No headings or announcing sentences: name and who you help, then specific examples (built what, for whom, result with number; else experience or a strength from `context/me.md`, never invented), then one small invitation. Client first names only if the member gave them. Warm, plain, contractions, one idea per sentence, numbers as said aloud, no pressure, no big promises. Close with "read it aloud once before recording; anything that trips your tongue gets cut". The member records it and gives a public YouTube link, set in Step 6 (10% of completeness); the profile goes live without it.
- **`## Profile fields`**: the remaining fields, paste-ready, from `context/me.md` only: Employment history (each relevant role with employer, title, period, non-freelance work included; no invented lines about what customers got), Education, Languages with English level, Availability in hours per week, Categories matching the direction, Hourly rate (band and number to enter), Photo (one instruction: a face, no logo, no group shot), Linked account (which), Other experiences (volunteer work, side project, system built at a non-freelance job). A field with no answer gets one line: what is missing and its cost.
- **`## Completeness`**: the shortest route to 100 as actual clicks, against the published percentages. State the Step 2 number, or for a new profile the fields to create, cheapest first.
- **`## Paste order`**: click-by-click placement of each section the connector cannot write, and of everything if a write fails.

## Step 5 · The gate

Run `python3 code/profile_draft.py check profile.md`: it re-checks Upwork's limits, the `## Reference averages` ceiling, and every number against the evidence sections of `context/me.md`, video script included. It does not check the portfolio count. With `video` focus add `--only video`. Exit 1: fix and rerun. Never loosen claims or add a number to pass; those sections change only with the member's word or the connector's.

When the gate passes, **always print the video script in full in the chat**, as a quote the member can read aloud, with the recording steps below it (record it, upload as a public YouTube video, send the link). Never only point to the file. Do the same for the title and the overview in the preview message.

## Step 6 · Put it live, with one yes, and report

The connector documents `update_profile` previews for title, overview, skills (the draft carries up to 15, the tool accepts 20), video (`set_video`, public YouTube link), availability, employment (country as ISO code, role up to 50 characters), education, languages and other experience; the title write was tested on 7 October 2026 (at least 4 characters, overview at least 100, skills at least one), the rest is untested. Before writing over a live title, overview or skills, save them to `profile-before.md` in the repository root (gitignored). Write only when the action returns the documented preview, otherwise hand over the paste-ready text and click path. Hourly rate, portfolio, photo, categories and the linked account stay manual.

Create the previews for every writable field first and show them together in one message, each with its exact before and after. Ask once: "Put these live? Yes, or name what to skip." Add the rate recommendation to the same message ("Rate: $X, say another number to change it"). Say nothing about preview expiry or what comes next. Call `confirm_preview` for each field only after that yes (recreate a preview that expired). A vague "ok" to a different question is not a yes. If behavior differs from the documented preview flow, stop and hand over manually.

## Step 7 · Check what is online, then report

When the member says everything is online, read `get_profile` action `get` and `list_highlights` fresh (never the saved files), run `python3 code/profile_checks.py data/profile.json data/highlights.json --json`, and give the completeness number, then two lists. **Online**: what the read confirms. **Still yours to do**: every missing or unreadable field with its percentage and exact click (photo, categories, rate, portfolio, linked account, the video unless `set_video` ran). List what the connector cannot read under "Still yours to do" instead of asking, never assume it is done.

Then run `python3 code/pipeline.py prune` and give the completion report per CLAUDE.md: what is live, what stays manual, completeness number, worst gap first, three lines at most. Link [profile.md](../../profile.md). Next: `/find-jobs`. Rerun only when something real changes. End with `Upwork calls: N`, measured, never estimated; every field put live adds two.
