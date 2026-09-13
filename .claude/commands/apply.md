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
when `jobs/<id>/pitch.html` exists and the pipeline record contains a valid HTTPS
Loom share or YouTube video link, including its video id. A non-empty string or
a bare video-service homepage is not enough. If either prerequisite is missing
or invalid, write nothing, make no preview and stop with
`DRAFT / HELD`: tell the member to finish the Pitch page or add the Loom video
link under Materials. Report zero Upwork calls.

## Step 1 · Review the recording locally

Read `loom_review_enabled` from the Step 0 pipeline record. It defaults to true
when absent. When it is false, skip this entire step and continue to Step 2.

Before any Upwork call, run `python3 code/funnel.py transcript loom <id>` and
read the transcript path it prints. Compare the recording with the job, pitch
page, Loom script and verified proof:

1. The first 20 seconds name the client's outcome and why the page exists.
2. Every claim matches the posting, pitch page or `context/proof.md`.
3. The explanation follows one clear path through the plan.
4. It is concise and conversational.
5. It ends with one next action on Upwork and no outside contact route.

Score the recording out of 100: opening and relevance 20, accuracy 30,
structure 20, delivery 15, and the Upwork next step 15. Write
`jobs/<id>/loom-review.md` with exactly `## Score` containing `N/100`, then
`## Verdict`, `## Message`, `## Accuracy`, `## Structure`, `## Delivery`, and
`## Fix before sending`. Run `python3 code/funnel.py check loom-review <id>` and
`python3 code/pipeline.py loom-score <id> <N>`. A serious unsupported
claim, wrong client fact, contact-policy violation or missing next action is a
hold: save the review and stop before creating the application or making any
Upwork call. Small delivery roughness is advice, not a blocker.

## Step 2 · The job, the posting, the pitch page

Use the pipeline record from Step 0. The full posting is in `details.description`; missing, fetch it with `find_jobs` action `get` and `python3 code/jobs.py detail`. Read all of it: postings hide a mandatory opening phrase, questions to answer inside the letter, or requirements that decide fit before skill does. The letter points to the finished walkthrough and includes its saved Loom link.

## Step 3 · What is true about you and the scope

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against `context/proof.md`. **A requirement your proof does not cover never becomes a claim.** If it is mandatory, ask the member whether they meet it and where that can be checked. Until resolved, save no client-facing draft and create no preview. If it is a preference, name the gap for the member and draft without claiming it. Lead with the strongest relevant proof by tier; never a badge or number the member does not hold.

Separate explicit deliverables from assumptions. Before quoting a price or
timeline, resolve the contract type, included work, dependencies, revision or
acceptance boundary and payment structure from the posting, saved member policy
or an explicit member decision. If one changes the bid, ask before creating the
preview. Never convert an hourly profile rate into a fixed-price quote.

## Step 4 · Write the letter

Write a compact pitch, normally 65 to 120 words and never more than 140 words,
in the member's voice, with no em-dashes. Use four short blocks:

1. One sentence on why the member fits this exact job and outcome.
2. One sentence inviting the client to watch the walkthrough, with the exact saved Loom link.
3. One or two short, relevant examples from `context/proof.md`. Never stretch unrelated proof to fill space.
4. One specific next question or ask on Upwork.

Do not recap the posting, explain a long method, add generic praise, write a
biography or pad the pitch. Never add a guarantee, refund, free work or delivery
date as a sales device. Put answers to required screening questions in
their separate fields, not in the cover letter, unless the posting explicitly
requires the answer there.

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

## Step 5 · The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

## Step 6 · The preview, never the send

1. `list_freelancer_proposals` action `invitations`: an invitation for this job
   means stop before any proposal-management call. Prepare the fields below, open
   the invitation on Upwork and let the member review and respond there. Never
   call `accept_invitation`; its preview or write behavior has not been measured.
2. `list_freelancer_proposals` action `list`: an existing proposal for this job means stop and say so.
3. When this is not an invitation and no proposal exists, if `manage_proposals`
   action `create` is available, call it with `job_reference`, `cover_letter`, the
   member-approved `charged_amount` and the screening `answers`. The tool
   description says this returns a preview and submits nothing; that behavior is
   not yet measured. If the action is absent or returns anything other than a
   preview, stop without another write and use the manual handoff. No other
   `manage_proposals` action is permitted in this command.
4. Save what the preview knows, so the cockpit shows it next to the job: `python3 code/pipeline.py detail <id> --file -` with one JSON object holding `bid_amount` (the exact `charged_amount` used), `connects_cost`, `connects_balance`, `boost_available`, `boost_reason`, `boost_top_bids` (the list of `current_top_bids`, highest first, or `null` when `current_top_bids_available` is false), `boost_recommended` (`recommended_connects`), `boost_max` (`max_boost_connects`), `boost_note`, `boost_recommendation` and `screening_questions`. Leave out what the preview did not return; never estimate a bid.

## Step 7 · Prepare the manual handoff

Present, in this order: the letter, the answers, the bid, **the Connects this costs and what is left**, any preferred qualification the member does not meet (advisory, it does not block), and the boost option with the real competing bids and the recommended amount (never offered when the preview says it is unavailable). State that no attachment or boost is selected by the Blueprint.

The cockpit shows these as separate review fields with copy controls. Open the
job's saved `url` on Upwork. The member clicks Apply, pastes the prepared fields,
chooses attachments and any boost, reviews Upwork's final cost and clicks Submit.

Never call the proposal confirmation tool and never mark the job Applied before
the member says they submitted it. After they confirm the manual submission, run
`python3 code/pipeline.py set <id> applied`. A freelancer cannot write first on a
proposal. Sync moves it to Lost after 14 days without a client reply.

If the member requests a change, revise and run the gate again. Create a new
preview only when the changed field affects it and remind the member that a new
preview replaces the previous pending one. Never buy Connects and never select
a boost.

## Step 8 · Report

Completion report as CLAUDE.md defines it, with the Loom verdict and today's
count against the daily target. The next action is manual review and submission
on Upwork. Upwork call count.
