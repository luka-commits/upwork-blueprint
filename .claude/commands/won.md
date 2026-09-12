---
description: Converts a started Upwork contract into a checked client project with scope baseline, kickoff tasks and the next check-in.
argument-hint: "<job id>"
---

# /won

Turn a real contract into a delivery-ready client project. This command never
accepts an offer, starts a contract or sends a message.

Read first: the job pipeline record, saved thread, `jobs/<id>/call-review.md`,
`jobs/<id>/proposal.md`, `context/me.md` and `context/proof.md`.

## ROADMAP

WHAT HAPPENS: verify that the contract started, confirm the delivery baseline,
write the project record, add real kickoff tasks and set the next check-in. About
five minutes.

I NEED FROM YOU: confirmation of any contract term the saved Upwork state does
not contain, and the first client check-in date.

WHAT MIGHT GO WRONG: a verbal yes or pending offer is not a contract; proposal
scope may differ from final Upwork terms; missing access can block day one.

## Step 1: Contract gate

Run `python3 code/workspace.py` and `python3 code/pipeline.py get $ARGUMENTS`.
Continue immediately only when the pipeline status is won, which `/sync` sets
from a started contract. If the status is offer, ask whether the contract now
shows as started on Upwork. Only after an explicit yes may you run
`python3 code/pipeline.py set <id> won --note "Contract start confirmed by the member"`.
Anything earlier than offer is blocked. Never accept the offer for the member.

## Step 2: Confirm the delivery baseline

Compare the final Upwork contract terms the member can see with the call review
and proposal. Confirm only the differences or missing items, one question at a
time: contract type and amount or rate, funded first milestone for fixed work,
agreed scope and exclusions, start date, deadline, client inputs, acceptance
method and first check-in date. The contract wins every conflict.

## Step 3: Write the client project

Write `jobs/<id>/project.md` with exactly these sections:

- `## Contract baseline`: type, commercial terms, start and timing
- `## Outcome`: what the client receives
- `## Scope`: deliverables and explicit exclusions
- `## Client inputs`: access, material and decisions, with owners
- `## Milestones`: output, due condition and acceptance per phase
- `## Communication`: Upwork channel and confirmed check-in rhythm
- `## First actions`: the smallest real steps that unblock delivery

The first three non-empty lines name the client project, say when it was recorded
and give `**Next:**`. No invented dates, numbers, access or acceptance criteria.
Run `python3 code/funnel.py check project <id>` and fix every failure.

## Step 4: Make the project operable

Add only actions the confirmed baseline actually requires through
`python3 code/pipeline.py task <id> add "<action>" [--due <date>]`. Normally these
are the kickoff note, client inputs, milestone one and its review. Never create a
task for vague future work or duplicate an equivalent existing task.

Set the confirmed first check-in through
`python3 code/pipeline.py set <id> won --follow-up <date>`. Add the timeline note
`python3 code/pipeline.py note <id> "Client project opened from the active contract"`.

## Step 5: Report

Use the completion report from `CLAUDE.md` and link the project record. The next
action is the first open task. Upwork call count: 0 unless the member ran `/sync`
first as a separate command.
