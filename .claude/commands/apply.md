---
description: Prepares the full application for one job, including cover letter, screening answers, bid and costs, for manual review and submission on Upwork.
argument-hint: "<job id>"
---

# /apply

Use the project-local `upwork-copy` skill for every line the client will read.
The member described in `context/me.md` is the sender.

The application itself. Early applications win, so this is fast. The Blueprint
prepares every field and the connector preview, then stops. The member reviews
and submits the proposal on Upwork themselves.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md), the proposals section of [references/upwork-mcp.md](../../references/upwork-mcp.md), [references/profile-formula.md](../../references/profile-formula.md) (the proof tiers), `context/me.md`, `context/proof.md`.

## Step 0 · The materials gate

Before any Upwork call, run `python3 code/pipeline.py get <id>`. Continue only
when `jobs/<id>/pitch.html` exists and the pipeline record contains a non-empty
`video` link. If either is missing, write nothing, make no preview and stop with
`DRAFT / HELD`: tell the member to finish the Pitch page or add the Loom video
link under Materials. Report zero Upwork calls.

## Step 1 · The job, the posting, the pitch page

Use the pipeline record from Step 0. The full posting is in `details.description`; missing, fetch it with `find_jobs` action `get` and `python3 code/jobs.py detail`. Read all of it: postings hide a mandatory opening phrase, questions to answer inside the letter, or requirements that decide fit before skill does. The letter points to the finished walkthrough and includes its saved Loom link.

## Step 2 · What is true about you, for this job

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against `context/proof.md`. **A requirement your proof does not cover never becomes a claim.** Say it plainly as a gap, or ask the member one question before writing. Lead with your strongest real proof by tier; never a badge or number you do not hold.

## Step 3 · Write the letter

300 to 400 words, in the member's voice, no em-dashes:

1. **The job title in the first sentence,** then two or three real proof points.
2. **"Here's what I'll deliver":** five to seven numbered items, each carrying a number. Past results only from the proof file; forward promises ("live on day 1") are fine and must be kept; the client's own numbers from the posting are the strongest.
3. **The video line:** a walkthrough of the plan with the exact saved Loom link.
4. **Risk reversal,** usually milestones: they approve each phase before the next.
5. **"Here's why I'm the right fit":** one short `##` block per major requirement, in their words, two or three lines of proof each.
6. **One specific ask that keeps the conversation on Upwork,** for example asking for their website, spec or current setup here.
7. A short close.

Save everything to `jobs/<id>/application.md` in this exact shape so the cockpit
can present each field separately:

```markdown
# Cover letter

<the complete letter>

# Screening answers

## <the client's exact question>

<one or two sentence answer>
```

Omit the Screening answers section when the job asks none.

## Step 4 · The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

## Step 5 · The preview, never the send

1. `list_freelancer_proposals` action `invitations`: an invitation for this job means `accept_invitation` instead of `create`.
2. `list_freelancer_proposals` action `list`: an existing proposal for this job means stop and say so.
3. `manage_proposals` action `create` with `job_reference`, `cover_letter`, `charged_amount` (the member's rate unless they said otherwise) and the screening `answers`. **This returns a preview and submits nothing.**
4. Save what the preview knows, so the cockpit shows it next to the job: `python3 code/pipeline.py detail <id> --file -` with one JSON object holding `bid_amount` (the exact `charged_amount` used), `connects_cost`, `connects_balance`, `boost_available`, `boost_reason`, `boost_top_bids` (the list of `current_top_bids`, highest first, or `null` when `current_top_bids_available` is false), `boost_recommended` (`recommended_connects`), `boost_max` (`max_boost_connects`), `boost_note`, `boost_recommendation` and `screening_questions`. Leave out what the preview did not return; never estimate a bid.

## Step 6 · Prepare the manual handoff

Present, in this order: the letter, the answers, the bid, **the Connects this costs and what is left**, any preferred qualification the member does not meet (advisory, it does not block), and the boost option with the real competing bids and the recommended amount (never offered when the preview says it is unavailable). State that no attachment or boost is selected by the Blueprint.

The cockpit shows these as separate review fields with copy controls. Open the
job's saved `url` on Upwork. The member clicks Apply, pastes the prepared fields,
chooses attachments and any boost, reviews Upwork's final cost and clicks Submit.

Never call the proposal confirmation tool and never mark the job Applied before
the member says they submitted it. After they confirm the manual submission, run
`python3 code/pipeline.py set <id> applied --follow-up +3d`. The follow-up is a
re-check, not a message: a freelancer cannot write first on a proposal.

If the member requests a change, revise, run the gate again and create a new
preview. Never buy Connects and never select a boost.

## Step 7 · Report

Completion report as CLAUDE.md defines it, with today's count against the daily
target. The next action is manual review and submission on Upwork. Upwork call
count.
