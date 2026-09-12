---
description: Scores your Upwork profile in minutes and lists what to fix first. Needs only the Upwork connector.
argument-hint: "[focus: title | opening | proof | skills | portfolio | completeness]"
---

# /audit

The first win: where your profile stands, measured, worst problem first. It reads your profile and changes nothing on it without your yes.

Read before judging anything: [references/profile-formula.md](../../references/profile-formula.md) and the profile sections of [references/upwork-mcp.md](../../references/upwork-mcp.md).

**Focus:** $ARGUMENTS. Given a focus, run only that group of checks and questions, and update only those findings in the report. Everything else in the report stays as it is.

## Step 0 · Your files and the connector

1. Run `python3 code/workspace.py`.
2. Call `list_accounts`. **If the Upwork tools are not there**, walk the member through it and stop:
   - In a terminal: `claude mcp add --transport http upwork https://mcp.upwork.com/mcp`
   - Quit Claude and start it again in this folder. Connecting without the restart looks fine and leaves the connector invisible, the one mistake that throws no error.
   - Type `/mcp`, pick upwork, log in to Upwork in the browser window that opens.
   - Then `/audit` again.
3. Take the `org_uid` of the Freelancer account. Never write it into a file. More than one freelancer account: ask which.

## Step 1 · Read (two calls)

- `get_profile` action `get`: save the response exactly as returned to `data/profile.json`.
- `get_profile` action `list_highlights`: save it to `data/highlights.json`.

**No title and no overview?** This member starts from scratch. Say so plainly, skip the audit, and route them to `/benchmark` then `/profile`. Verdict COMPLETE: nothing to audit yet.

## Step 2 · Measure

Run `python3 code/profile_checks.py data/profile.json data/highlights.json --json`.

The script decides pass or fail for the mechanical checks. Never overrule it. If a result looks wrong to you, say so in chat and leave the finding as the script scored it.

## Step 3 · Ask what the connector cannot see, in one message

The connector returns no Job Success Score, no review texts and no intro video. Ask all three at once, with where to look ("open your profile on Upwork, the Job Success badge sits under your name"):

- Your Job Success Score, or "none yet"
- Do you have an intro video on your profile?
- How many reviews show on your profile?

Skipped answers go into the report under "Not measured", never estimated.

## Step 4 · Judge what no script can

Each of these becomes a finding only when it fails:

1. **Consistency, first.** Do title, overview, skills and portfolio tell one story? When the title promises A and the portfolio shows B, the client believes neither. This often explains a profile with decent parts and no invitations.
2. **Proof order.** Is the strongest proof the member has, by the tiers in the formula, inside the first 250 characters?
3. **Opening.** Does the first line say what the client gets, or is it a CV?
4. **Location and timezone.** Do they match where the member actually works? A wrong timezone makes every reply look late and hides them from clients who filter by it.
5. **The Step 3 answers.** No video, a Job Success Score under 90, or few reviews each shape what `/profile` should lead with.

If `benchmark.md` exists, also compare title length, overview length, skills and rate against its targets.

## Step 5 · Write audit-report.md

The findings report. First three lines, then stop:

```
# Profile audit

Updated Friday 12 September 2026 · 8 of 15 checks passed · the title promises tools your skills never mention
**Next:** run /benchmark, then /profile writes every fix below.
```

Then every finding, **ranked by what it costs to ignore, never grouped by category**. Search first (skills and title decide whether you are found), then the opening and proof (whether you are read), then the rest:

```
### [ ] 1. Add Shopify and Klaviyo as skills · clients filter by them

Your title names both, your skills name neither. Skills are the filter fields
in client search, so a client filtering for Klaviyo never sees you.

**Who:** you, on Upwork: Profile, the pencil next to Skills
**Time:** 2 min
**Source:** Upwork's own search
```

- Two or three lines of explanation per finding, at most. Quote the member's current words briefly when that makes the problem obvious.
- **Who** is always one of: `/profile writes it` · `you, on Upwork: <exact clicks>` · `me, after your yes`.
- **Source** is `Upwork's own rule` or `top-earner pattern`, from the check's source. Judgement findings say which of the two they rest on.
- After the findings: `## Passed · 7`, one line naming them in plain words. Never list them one by one.
- Then `## Not measured`: every question skipped in Step 3, and anything else this audit cannot see (how often you appear in search, client-side views).
- **No finished texts here.** `/profile` reads this report and writes every fix. The only exception: availability, employment, education and languages can be changed through the connector. Offer those here, one at a time, draft first, `confirm_draft` only after an explicit yes.

**Running it again:** read the old report first. A finding that now passes becomes `[x]` with "Fixed <date in words>", it is never deleted. New findings take their place in the ranking.

## Step 6 · Report

Completion report as CLAUDE.md defines it. Link [audit-report.md](../../audit-report.md). Next step: `/benchmark`. End with the Upwork call count, normally three.
