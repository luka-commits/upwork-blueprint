---
description: Writes the application for one job on the member's own template: cover letter, screening answers and bid.
argument-hint: "<job id> [more job ids] | <job id> submitted"
---

# /proposal

**`/proposal <id> submitted`:** only run `python3 code/pipeline.py set <id> applied`
and report `Upwork calls: 0`, then stop before any other step. It records the member's submission.

**Several ids run one after another.** The repetition is the command's, never the member's yes.

Follow `references/copy.md` for every line the client reads. The member described in
`context/me.md` is the sender. The member records the Loom themselves and shows a one-pager
from `templates/roadmap/` on screen; this command only writes the application text.

Read first: [references/upwork.md](../../references/upwork.md) (hard constraint 8, no contact route before a contract), `context/me.md`.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 6 does. Never write from the summary: the requirements and screening questions are in the full posting.

## Step 2 · Price guide

Estimate effort from the full posting, never the client's budget: low, likely and
high hours; two to five milestones summing to likely; confidence; scope assumptions.

```
python3 code/pricing.py <id> --hours <low> <likely> <high> \
  --confidence high|medium|low --contract-type fixed|hourly|unknown \
  --milestone "Foundation|hours" --milestone "Build and QA|hours" \
  --assumption "one concrete scope boundary"
```

It uses the member's rate plus a scope-risk buffer of 5, 15 or 25 percent for high,
medium or low confidence. The internal guide is never the bid and never overrides approved terms.

## Step 3 · Application

Use the full posting from Step 1 and `references/copy.md` for
every line the client will read. The member reviews and submits the proposal
on Upwork themselves. Prepare the cover letter, screening answers when the
posting states the questions, and the bid for manual submission.

**The first 230 characters decide.** That is all the applicant card shows a client, roughly the first 45 words. Put the outcome and the one relevant proof there, not a greeting or excitement.

### What is true about you and the scope

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against the evidence sections of `context/me.md`. **A requirement your proof does not cover never becomes a claim.** If it is mandatory, ask the member whether they meet it and where that can be checked, one single choice per requirement: met and checkable, met with nothing to point at, not met; the place is typed. Until resolved, save no client-facing draft. If it is a preference, name the gap for the member and draft without claiming it. Lead with the strongest relevant proof by tier; never a badge or number the member does not hold.

Separate explicit deliverables from assumptions. Before quoting a price or
timeline, resolve the contract type, included work, dependencies, revision or
acceptance boundary and payment structure from the posting, saved member policy
or an explicit member decision. If one changes the bid, ask before writing the application. Never convert an hourly profile rate into a fixed-price quote.

When `details.price_estimate` exists, use it as the internal starting point:
show the hour cases, profile rate, risk buffer, assumptions and roadmap together.
It is an estimate, not approval. Recalculate it when the resolved scope changes,
and get the member's explicit bid decision before writing the bid, as a single choice
between the estimate's cases with another figure typed.

### Write the letter

Write the letter on the member's own template: five blocks, friendly and plain, no
em-dashes, normally 120 to 180 words and never more than 220. The template comes from
the member's sent letters; keep its order and its small signposts (📽️ 🔗 ❗). Every
`<...>` below is filled from this job's posting and from `context/me.md`, never from memory.

```
Hey, I'm a <the member's real status and role from context/me.md> and can definitely help you <the client's goal, in the client's own words from the posting>.

Here's how I would do it :)
📽️: [LOOM LINK]

<Screening block, only when the posting states questions: see below>

In terms of relevant experience, <one or two sentences of proof from the evidence sections of context/me.md that fit this job, using the problem words of the posting>.

<One sentence on how the member works that answers this client's situation, for example: audit first, simplify, rebuild, document.>

<Only if the member has a portfolio link in context/me.md:>
Websites, funnels etc:
❗<the portfolio link>

Happy to jump on a call to <the one thing to scope for this job>. Looking forward to hearing from you!

All the best, <first name>
```

Fill rules:
- **The opening carries the card.** The first 230 characters are the role plus this client's outcome, with at least one word from the job title.
- **Status, counts and clients** ("Top-Rated", "15+ clients", a named result) are written only if they stand in the evidence sections of `context/me.md`. A count that is missing is left out, not asked for. **The portfolio block is optional**: most members have no link, so without one the two lines are dropped and nothing is asked.
- **No page link.** The Loom is the only extra: the member shows a one-pager on their own screen, and the letter links nothing else.
- **No claim beyond the proof.** A requirement the evidence does not cover is not claimed; name it to the member instead.
- Do not recap the posting, add generic praise or pad. Never add a guarantee, refund,
  free work or delivery date as a sales device.

**Screening questions.** Read the full description for any question the client wants answered (a numbered list, "please answer", "include", "start your reply with") and for questions in Upwork's own question fields. Name each one in the Step 8 report. When the posting wants the answers in the letter itself, insert this block after the video lines, one numbered line per question, each answered in one or two sentences, and where the video covers it, say so in plain words (a timestamp only after the Loom exists):

```
Answers to your screening questions:

1. <topic of the question>: <answer>
2. ...
```

Otherwise put the answers in the separate `# Screening answers` section below, for the member to paste into Upwork's question fields.

Save the cover letter to `jobs/<id>/application.md` in this exact shape so the
cockpit can present it separately:

```markdown
# Cover letter

<the complete letter>

```

When the full posting states screening questions, answer each in one or two
sentences from the posting and verified proof. A mandatory answer without
proof is a hold. Do not guess questions the posting does not state. Append:

```markdown
# Screening answers

## <the client's exact question>

<one or two sentence answer>
```

Record the member-approved bid amount through
`python3 code/pipeline.py detail <id> --file -` with a JSON object containing
`bid_amount`. Leave out costs or questions the posting did not reveal.

### The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

### Manual handoff

Present the letter, any answers, the bid and any preferred qualification the
member does not meet. Open the saved job URL on Upwork. The member pastes the
fields, reviews Upwork's final cost and submits the proposal on Upwork
themselves.

**Before they paste, run `python3 code/application_check.py jobs/<id>/application.md
--ready`.** Same gate, one more refusal: the `[LOOM LINK]` placeholder, correct while the
letter is written and wrong the moment it is pasted.

Never mark Applied until the member submits on Upwork, then runs `/proposal <id> submitted`.
That stage rests on their word; `/brief` checks once if no proposal ever shows up.

## Step 4 · Report

Run `python3 code/pipeline.py prune` first, because Step 1 fetched the full job. Then the completion report as CLAUDE.md defines it, with the application linked. Say what the application costs in Connects and what the balance leaves.
Next: record the Loom and return its URL here; replace [LOOM LINK] in the letter. Run the ready application check again. Only then submit on Upwork and run `/proposal <id> submitted`.
End with `Upwork calls: N`.
