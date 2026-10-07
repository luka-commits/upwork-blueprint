---
description: Turns a started Upwork contract into a checked handover brief for delivery, with scope, milestones and client inputs.
argument-hint: "<job id>"
---

# /onboarding

Turn a real contract into the brief the work starts from, and the onboarding around it.
This command never accepts an offer, starts a contract or sends a message.

Read first: the job pipeline record, the saved thread, `jobs/<id>/proposal.md`
when it exists, and the final Upwork contract, plus `context/me.md`.

## ROADMAP

WHAT HAPPENS: verify the contract, confirm delivery terms and write the handover; about five minutes. Later runs record only the result.
I NEED FROM YOU: confirm which contract is this job and any missing terms; after delivery, the result and its source.
WHAT MIGHT GO WRONG: a pending offer is not a contract; final terms may differ; missing access blocks day one.

## Step 1 · Contract gate

Run `python3 code/workspace.py` and `python3 code/pipeline.py get $ARGUMENTS`.
If `jobs/<id>/project.md` exists, run only the result pass: if `result_recorded_at` is set,
report it is already recorded and stop. Otherwise ask what came out of the work and where
it can be checked. Update its existing pending Results entry in `context/me.md` (create one only if absent), verified with a source
or pending without one; write only on the member's yes. Then persist the current ISO
`result_recorded_at` through `python3 code/pipeline.py record <id> --file -` and report.
Do not reread contracts, redo onboarding or open another workspace. Upwork calls: 0.

Otherwise require `replied`, `call`, `offer` or `won`. Read `list_contracts` action
`search` before changing stage; use the stored `contract_id` or the exact title to find
candidate contracts. Page only until the match is found or results end. Read its status,
type, client, rate or amount and dates. For fixed work read `list_milestones` too.
Name the contract and have the member confirm it is this job; a verbal yes without a
real started contract is insufficient. Persist `contract_id` and `contract_client`
through `pipeline.py record`, then `python3 code/pipeline.py set <id> won --note "Contract confirmed by the member"`.
Never accept an offer or start a contract for them.

## Step 2 · Confirm the delivery baseline

Then compare what you read with `jobs/<id>/proposal.md` and the saved conversation, and
put only the differences to them, one question at a time: contract type and amount or
rate, funded first milestone, agreed scope and exclusions, start date, deadline, client
inputs and acceptance method. The contract wins every conflict, and a difference is
written into the brief as a difference rather than quietly resolved.

## Step 3 · Write the handover brief

Write `jobs/<id>/project.md` with exactly these sections:

- `## Contract baseline`: type, commercial terms, start and timing
- `## Outcome`: what the client receives
- `## Scope`: deliverables and explicit exclusions
- `## Client inputs`: access, material and decisions, with owners
- `## Milestones`: output, due condition and acceptance per phase
- `## Communication`: Upwork channel and the agreed update rhythm
- `## First actions`: the smallest real steps that unblock delivery

The first three non-empty lines name the client project, say when it was recorded
and give `**Next:**`, which is the first client input still missing. No
invented dates, numbers, access or acceptance criteria. Run
`python3 code/document_check.py check project <id>` and fix every failure.

## Step 4 · The start, and whether there is a call for it

**Ask first whether there will be an onboarding call.** Plenty of jobs do not have one: a
small fixed piece with the brief already agreed starts faster in writing, and forcing a
meeting onto a client who wants the work done is a bad first impression. So ask, once, and
build whichever of the two the answer calls for.

**With a call**, write the agenda into `project.md` under `## First actions`, in this order,
because it is the order that gets everything answered: the roadmap from the proposal read
back in four or five steps so the client hears their own plan again; what the member needs
from them, named as a list with an owner each; who decides on the client side and who else
must see the work; how they will hear from the member and how fast a question gets answered;
and the first milestone with what "done" means for it. Everything the client owes gets a
date on the call, not an intention. End it by naming the single first deliverable and when
it lands.

**Without a call**, the same list goes out as one message and a request: the roadmap in four
lines, the inputs as a numbered list with a date beside each, the decision maker, the
communication rhythm, and the first milestone. A checklist a client can answer in one sitting
beats a meeting they postpone twice.

**Either way, what the client owes is the real start date.** An access list nobody has
worked through is not a formality, it is the reason a project sits idle in week one, so it
goes into `## Client inputs` with owners and dates and is named in the report as what still
blocks the start.

## Step 5 · Report

Run `python3 code/client_workspace.py new <id>` once the brief exists. A job folder is a sales
artefact and stops mattering the day the contract starts; delivery needs one place per client.
It opens `clients/<slug>/` with `context.md` (who they are, what was sold, what was promised,
what access they owe), the brief copied in, and `inputs/`, `work/` and `delivered/`. Everything
under `clients/` is the member's own and never tracked.

Then fill the lines in `context.md` that read "not recorded yet" from the proposal and the
thread, and name in the report how many are still open. A fact nobody wrote down is a question
the client gets asked twice.

**Then put the new facts about the member back into their own file**, from what the
contract said rather than from a question: the rate or amount they actually sell at, and a
`pending` Results entry for the engagement with the client's industry and the sold outcome.
Say the lines in one block, write them on a yes, and never promote a promise to a result.

Use the completion report from `CLAUDE.md` and link the handover brief. The next action
is to fill the remaining client facts and begin delivery. End with `Upwork calls: N`,
counting the calls actually made, including accounts, contract pages and milestones.
