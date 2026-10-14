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

Give this roadmap before the first tool call, including any read.

WHAT HAPPENS: verify the contract, confirm delivery terms, write the handover and set up a client folder outside this repository with your chosen blueprints; about five minutes plus a few minutes to clone and set up. Later runs record only the result.
I NEED FROM YOU: confirm the contract and missing terms, pick blueprints, then approve the proposed client facts. The folder goes under your Clients folder setting or the repository's sibling clients folder. I will announce the exact destination once the first read reveals it, before cloning. After delivery, I need the result and its source.
WHAT MIGHT GO WRONG: a pending offer is not a contract; final terms may differ; missing access blocks day one. Missing git, no network, a private repository or a client slug already taken can hold setup.

## Step 1 · Contract gate

Run `python3 code/workspace.py` and `python3 code/pipeline.py get $ARGUMENTS`.
If the record has `handover_done_at`, run only the result pass (a `project.md` without it
means the first run stopped early: go on from the step after the brief's check, never redo it): if `result_recorded_at` is set,
report it is already recorded and stop. Otherwise ask what came out of the work and where
it can be checked, as `/about-me` Step 4 does: the kind of result as checkboxes, its figure
typed, the place as a single choice ([references/copy.md: How to ask](../../references/copy.md#how-to-ask)). Update its existing pending Results entry in `context/me.md` (create one only if absent): what they tell you is
theirs, so the pending label comes off, with where it can be checked when they name it; write only on the member's yes. Then persist the current ISO
`result_recorded_at` through `python3 code/pipeline.py record <id> --file -` and report.
Do not reread contracts, redo onboarding or open another workspace. Upwork calls: 0.

Otherwise require `replied`, `call`, `offer` or `won`; an earlier lead goes back to `/brief`. Read `list_contracts` action
`search` before changing stage; use the stored `contract_id` or the exact title to find
candidate contracts. Page only until the match is found or results end. Read its status,
type, client, rate or amount and dates. For fixed work read `list_milestones` too.
Name the contract and have the member confirm it is this job, as a single choice over the
contracts found with "none of these" among them; a verbal yes without a
real started contract is insufficient. Persist `contract_id` and `contract_client`
through `pipeline.py record`, then `python3 code/pipeline.py set <id> won --note "Contract confirmed by the member"`.
Never accept an offer or start a contract for them.

## Step 2 · Confirm the delivery baseline

Then compare what you read with `jobs/<id>/proposal.md` and the saved conversation, and
put only the differences to them, each its own single choice with the contract's value
first and up to four in a call: contract type and amount or
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
meeting onto a client who wants the work done is a bad first impression. So ask, once, as a
single choice (a call, or a written start), and build whichever of the two the answer calls for.

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

## Step 5 · Set up the client folder

Use `AskUserQuestion` with `multiSelect: true` and exactly these option labels:
`SEO`, `Google Ads`, `CRO`, `None, just the client folder`. Explain that a different
blueprint can be supplied as a GitHub URL through the tool's own Other field; never
add a fifth explicit Other option. None with other picks means the other picks.
Every question and yes in this command uses `AskUserQuestion`; typing goes through
its Other field only. An unanswered pick is a held decision, never approval.

Before creating or cloning anything, run `python3 code/client_workspace.py where <id>`
and announce the exact path it prints. It applies the `**Clients folder:**` setting from
`context/me.md` (default `<repo parent>/clients`) and writes nothing. If it prints
`TAKEN`, hold and offer a different slug through `AskUserQuestion`, run `where <id>
--slug <slug>`, announce that path and pass the same `--slug` to `new`. An ABORT about a
folder inside the Upwork repository is held until the member names another Clients folder.

Run `python3 code/client_workspace.py new <id>` with one repeated `--blueprint` flag
per pick: `seo`, `ads`, `cro`, or the typed GitHub URL. None alone means no blueprint
flag and still creates the folder. Read registry URLs and next commands only from
`code/client_workspace.py`; do not hardcode or guess them.

The client folder is its own git repository outside this repository, with root
`CLAUDE.md`, `brief.md`, `inputs/upwork/`, `work/` and `delivered/`. Sales inputs are
copied into `inputs/upwork/`, never moved; the original job folder stays intact.
Each blueprint is a separate git clone in its subfolder, excluded by the client's
`.gitignore`. `new` runs `./setup.sh` only for registry blueprints, with cwd set to
the clone. Never run scripts from an arbitrary typed clone. Read its README and
name its own manual setup step in the report, preserving its source layout and rules.
Do not install npm, pip or Playwright, add keys or connect accounts. Never manually
write `.env` during handover or prefill, or insert secrets. The authorized registry
`./setup.sh` invocation may create empty starter files, including `.env`.

Fill the root `CLAUDE.md` from the checked `project.md`, proposal, saved thread,
final contract and recorded business facts. Name the source for every prefill;
unknown fields stay `_not recorded yet_`. Keep the first three non-empty lines as
client name, recorded date and `**Next:**`. Fill these sections:

- `## The business`: name, website, what they do, where they serve.
- `## What was sold`: outcome, deliverables, exclusions, price, milestones and dates.
- `## How it runs`: Upwork channel, update rhythm and the actual contract approval terms.
- `## Access the client owes`: each item with its owner and status; promised access stays pending.
- `## Where things are`: `brief.md` and each copied file in `inputs/upwork/` by name.
- `## Blueprints here`: each blueprint's `cd <name> && claude` and registry next command,
  or typed clone's manual setup step. State that its own local context and rules lead;
  these client facts do not override them.

Never impose a milestone approval rule the contract does not contain. Before
prefilling each blueprint, read its local rules and business starter. Propose only
business sections in its `context/business.md`: name, website, what they do,
business model, service area and hours when known. Never change `## My packages`,
insert unverified proof or rewrite its layout; preserve the section structure when
`context/business.md` exists. If a typed clone lacks that file, create only
`context/business.md` with sourced business facts after the same member approval;
run no scripts, invent no packages and make no unrelated layout changes.
If no setup step is documented, name that gap rather than inventing one.

Show the exact proposed root `CLAUDE.md` and all `context/business.md` lines together
in one block, labelled by their actual file paths and with sources beside the facts.
Write only the lines approved by the member's yes through `AskUserQuestion`, then
read them back. A declined or unanswered approval leaves the prefill held.

Run `python3 code/client_workspace.py check <id>`. Fix every FAIL safely and rerun;
if a failure cannot be fixed within this scope, report HELD with its cause and owner.
On interrupted setup, rerun `new` with the selected flags to repair missing pieces
without overwriting existing work, then repeat the approval and check as needed.
Never record `handover_done_at` before every folder check passes.

## Step 6 · Report

**Then put the new facts about the member back into their own file**, from what the
contract said rather than from a question. An hourly contract's rate goes into
`**Hourly rate:**` only when it differs, as the new figure first; a fixed price changes no rate
line and goes into the entry below. The engagement becomes a Results entry with the client's
industry and the sold outcome, `- Status: pending` and `- Source: Upwork contract, <date>`: a
promise, held back from every client until the result pass records what came out. Say the
lines in one block, write them on a yes through `AskUserQuestion`, and never promote
a promise to a result. Only after the folder check is PASS and the required approvals
are resolved, record
`{"handover_done_at": "<ISO time>"}` through `python3 code/pipeline.py record <id> --file -`.

Use the completion report from `CLAUDE.md`, under 90 words, verdict first, with
**Built**, **Checked** and **Still needed** where applicable. Link the handover brief,
name the actual absolute client destination and the open `_not recorded yet_` count.
For each blueprint give the `cd ... && claude` line and the next command exactly as
`new` printed them, with CRO's `<site>` replaced by the recorded website or, without
one, the step that gets it. For typed clones name their own manual setup step instead.
Name any held approval or check failure with its owner. The next action is to fill
remaining client facts and begin delivery; after delivery, `/onboarding <id>` records
the result in `context/me.md`. Cloning is not an Upwork call. Last line:
`Upwork calls: N`, counting actual calls, including accounts, contract pages and milestones.
