---
description: Writes the application for one job (cover letter, screening answers, bid), shows you exactly what goes out and what it costs, and submits only after your yes.
argument-hint: "<job id> [--draft-only]"
---

# /apply

The application itself. Early applications win, so this is fast, and it never sends on its own: you read the exact letter, the bid and the Connects price, then say yes or no.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md), the proposals section of [references/upwork-mcp.md](../../references/upwork-mcp.md), [references/profile-formula.md](../../references/profile-formula.md) (the proof tiers), `context/me.md`, `context/proof.md`.

`--draft-only` (what the cockpit button runs): stop after Step 4. The send happens in a session where you read the draft.

## Step 1 · The job, the posting, the pitch page

`python3 code/pipeline.py get <id>`. The full posting is in `details.description`; missing, fetch it with `find_jobs` action `get` and `python3 code/jobs.py detail`. Read all of it: postings hide a mandatory opening phrase, questions to answer inside the letter, or requirements that decide fit before skill does. If `jobs/<id>/pitch.html` exists, the letter points to the walkthrough built on it.

## Step 2 · What is true about you, for this job

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against `context/proof.md`. **A requirement your proof does not cover never becomes a claim.** Say it plainly as a gap, or ask the member one question before writing. Lead with your strongest real proof by tier; never a badge or number you do not hold.

## Step 3 · Write the letter

300 to 400 words, in the member's voice, no em-dashes:

1. **The job title in the first sentence,** then two or three real proof points.
2. **"Here's what I'll deliver":** five to seven numbered items, each carrying a number. Past results only from the proof file; forward promises ("live on day 1") are fine and must be kept; the client's own numbers from the posting are the strongest.
3. **The video line:** a walkthrough of the plan, the Loom link once it exists. The letter never waits for the video.
4. **Risk reversal,** usually milestones: they approve each phase before the next.
5. **"Here's why I'm the right fit":** one short `##` block per major requirement, in their words, two or three lines of proof each.
6. **One specific ask that keeps the conversation on Upwork,** for example asking for their website, spec or current setup here.
7. A short close.

Screening answers go after a line `Screening answers`, each question in its exact wording, one or two sentences per answer. Save everything to `jobs/<id>/application.md`.

## Step 4 · The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

## Step 5 · The preview, never the send

1. `list_freelancer_proposals` action `invitations`: an invitation for this job means `accept_invitation` instead of `create`.
2. `list_freelancer_proposals` action `list`: an existing proposal for this job means stop and say so.
3. `manage_proposals` action `create` with `job_reference`, `cover_letter`, `charged_amount` (the member's rate unless they said otherwise) and the screening `answers`. **This returns a preview and submits nothing.**

## Step 6 · Show it and ask

Present, in this order: the letter, the answers, the bid, **the Connects this costs and what is left**, any preferred qualification the member does not meet (advisory, it does not block), and the boost option with the real competing bids and the recommended amount (never offered when the preview says it is unavailable). Ask about attachments and which portfolio projects or certificates to highlight. Then ask for the yes.

## Step 7 · On yes, and only on yes

`confirm_preview` with type `proposal` and the preview id. Then `python3 code/pipeline.py set <id> applied --follow-up +3d`. The follow-up is a re-check, not a message: a freelancer cannot write first on a proposal. Verify with `list_freelancer_proposals` action `list` that it landed.

No yes, or a change requested: revise, run the gate again, create a new preview. Never Connects bought, never a boost the member did not name.

## Step 8 · Report

Completion report as CLAUDE.md defines it, with today's count against the daily target. Upwork call count.
