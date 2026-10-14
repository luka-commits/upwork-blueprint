---
description: Your weekly Upwork coaching loop: checks last week's goals, measures the funnel, finds this week's focus and agrees three commitments with you.
---

# /analytics

Run weekly, on the member's `## Analytics day`. Code does every number; Claude reviews
the evidence, explains the verdict and agrees the goals. Nothing is sent to Upwork.
Read `context/me.md`, [references/copy.md](../../references/copy.md) and
[references/goal-library.md](../../references/goal-library.md). `analytics.py` validates
the snapshot contract; use its complete compute object as the shape. For connector reads follow
[references/upwork.md](../../references/upwork.md) and [/brief](brief.md) Steps 1–2.

## ROADMAP

WHAT HAPPENS: refresh the evidence, check last week's commitments, measure this week's focus and propose three goals. Allow about fifteen minutes, plus the conversation.
I NEED FROM YOU: missing call evidence, any tool-install yes and agreement on the three goals before they are saved.
WHAT MIGHT GO WRONG: missing sources leave affected checks unmeasurable; small cohorts may not be decidable yet. The coaching still runs.

## Step 1 · Setup and sync, inside this command

Run `python3 code/workspace.py`. Read `data/sync.json` and check the connector with
`list_accounts`. If unreachable, walk through README's connection steps; preserve the
available evidence and name the source gap. If the last sync is absent or older than
24 hours, carry out `/brief` Steps 1–2 (read and sync only, no drafts or sends).
Use saved state when fresh; count every Upwork call.

**First analytics run:** backfill what the connector can actually enumerate: proposals,
invitations, contracts with values and start dates, Connects transactions and weekly
earnings. Follow the documented pagination, stop when history is exhausted or the
connector's limit is reached, and name the uncovered period. On first sync, proposals
created by `sync.py` are imported; unmatched offers and contracts are imported too.
For absent historical leads, use `pipeline.py add --file -` with `imported: true` and
the verified fields. Existing matched leads cannot have that marker changed through
the current writer: preserve them and name that backfill limitation in coverage.
Preserve observed entry dates when known; never infer them from current stages.
Imported leads feed won value and baselines only, never rate cohorts or weekly applications.
Pass earnings and Connects to `sync.py apply --file -` in its documented number-and-ID
shapes. An absent ledger is missing, never an empty ledger invented to mean zero.

Check `yt-dlp`, `whisper-cli` and `code/loom.py`'s `find_model()`. If absent, show the
applicable install line: `brew install yt-dlp whisper.cpp`; for the model use
`code/loom.py`'s `MODEL_DOWNLOAD`. Install only on the member's yes. On Linux show the
tool's platform-specific installation instructions instead of running Homebrew.
Use `python3 code/loom.py <id> <recorded Loom URL>` for a missing Loom transcript.

For calls, use Upwork first: saved meeting sessions or `manage_meetings action=list_recaps`,
then `action=get_full_transcript` for each room/session, every page by offset. These
are read actions; count and pace them under `references/upwork.md`. Normalise the page
set with `python3 code/call_stats.py <id> --transcript-json - --call-at <ISO time>
--duration-s <seconds> --member "<known member speaker>" --source upwork-meeting`
(omit unknown headers). It writes
`jobs/<id>/call.md` with one `Speaker: line` per segment and derives the call stats.
Only when no Upwork transcript exists, and for Enterprise clients or calls after a
contract started, read `## Call recorder`; ask which recorder only if still unknown.
Retrieve its available MCP/API transcript or accept a pasted transcript; otherwise
use notes. Preserve known `Call at:`, `Duration:` and `Member:` headers. Without
speaker labels a call is **not reviewable**; never invent them. Run `call_stats.py`
for each call with `--source upwork-meeting|recorder|member` matching its evidence.
A recap proves held; missing recaps alone never prove no-show.

Check one existing registered tracking link with `?check=1` and its redirect; require
`X-Tracking-Status: check: not logged`, then `python3 code/clicks.py`. The test must
not become a human click or a client opening in the pipeline.
If none exists or access fails, say why tracking is missing; register or deploy nothing.
Keep each absent, stale or unreachable source in `coverage` with its affected KPI keys
and one fix. Use `missing` for an absent or unreachable required source: affected KPIs
become missing, rather than zero. `stale` labels readable evidence that needs refresh;
it never proves a source was reachable. Do not claim a check that was not made.

## Step 2 · Compute, then read the cases

Run `python3 code/analytics.py compute` and keep the returned JSON unchanged as the
numeric source. It supplies activity (seven days), mature cohorts (28 days), outcomes,
the own benchmark, source coverage, lead IDs and last week's goals.
Rates pool successes and eligible cases; unknown entry dates never enter a cohort.
Outcome rates (KPIs 3–9) collect weeks 1–4 without a rate verdict, then target the next
rung; `## Bars` changes only the top rung. Levers 10–14 keep fixed strict targets from
day one. The focus is the first outcome decidably below its rung, or its failing feeding
lever: reply rate ← speed; reply → call ← first reply or follow-ups; held → proposal ←
proposal speed. Earlier missing or undecided stages stay in `undecided_before`. When
the funnel is not decidable yet, use the measured lever and returned `cases_needed`.
No new segment findings or expectation tests: KPIs 20–21 say “nothing new” until package 4.

Read each evidence lead with `python3 code/pipeline.py get <id>`, its sent application,
thread, Loom transcript, call and sent proposal where relevant. Inspect all recent
cases behind a pattern, not one convenient example. Missing or pruned evidence is a gap.

## Step 3 · Review and accountability

**New applications:** judge lane and rate against `context/me.md` and the full post,
`pass | fail | unclear`, with a quoted reason. Store it through the sole pipeline writer:
`python3 code/pipeline.py note <id> 'analytics job_fit: {"state":"pass","reason":"..."}'`.
Use compact JSON and the actual judgment, within the note's 1,000-character limit.
This tagged note is the assessment transport; never write `data/jobs.json` directly.

**Application review:** read `jobs/<id>/application.sent.md` and Loom if any. Every point
is `met | partly | missing` with a supporting quote: first sentence names the posted
problem in the client's words; one matching proof; every screening question answered
specifically; bid fits scope; under about 150 words; one easy closing question; Loom,
if present, names the problem within fifteen seconds and ends with one ask. Pick the
most often missing point across the week's applications and rewrite one first sentence
as the example. Treat missing sent copy as missing evidence, not a failed application.
Pass `reviews.application.rubric` in the same per-lead shape as the call rubric below:
points 1–6 follow the six application checks above, and point 7 is the Loom check
only when used. States are `met | partly | missing`. A reviewable lead needs its
sent copy; otherwise `reviewable: false` and `points: []`. Code derives point coverage.

**Conversation review:** read the saved threads oldest first. Check whether the member
answered the latest question, replied within working hours, offered a concrete next
step and completed due silent-lane follow-ups. Give one evidenced fix and one example.
**Proposal review:** compare the sent proposal with the held call's agreement: outcome,
scope, price, owner and next step. Give one evidenced fix and one example.

**Call review:** without complete speaker labels, say “not reviewable”. Otherwise
judge all nine points `met | partly | missing | not needed`, each with a quote from
`jobs/<id>/call.md`. Information already established in the thread or post can satisfy
a point; cite that source too and never penalise the member for not asking twice.
1. Opening and agenda in the first two minutes.
2. Current state (already known in the thread also counts).
3. Problem and its cost in money, time or leads.
4. Goal and scope.
5. Budget before the price (a confirmed posted budget counts).
6. Decision maker and timeline (`not needed` when the decider is on the call).
7. One proof matching the stated problem.
8. Objections actively invited, and handled when raised.
9. Next step with owner, time and the client's yes.

A clean “not a fit” is a disqualification, never a bad call. Choose the weekly fix
from the recent calls' pattern in priority 3, 5, 9, then the rest; give one sentence
to say next time. Pass `reviews.call.rubric` as one object per call:
`{"lead_id":"<id>","reviewable":true,"points":[{"point":1,"state":"met"}, ...]}`,
with all nine numbered points. For an unreviewable call set `reviewable: false`
and `points: []`. Code computes per-point coverage and its weekly history.
Talk share and question count remain context, never the verdict.
Keep supporting client quotations in the conversation and lead files only.

**Lost leads:** distinguish `stated | observed | unknown`; do not turn a guess into the
client's reason. Use `pipeline.py note <id> 'analytics lost_reason: {"kind":"stated","reason":"..."}'`.
**Last week's goals:** inspect the named evidence leads to mark each eligible action
done or undone. Pass each goal's `evidence_lead_ids` (all eligible leads) and
`done_lead_ids` (its completed subset), so code derives `done_k` and `done_n`.
Execution is `done_k of done_n`; outcome comes from code's KPI before
and after the goal start (`worked | not | undecided`). Decide `keep | adjust | stop`.
If a commitment went undone two weeks running, say so and offer its simpler fallback.

Re-run `python3 code/analytics.py compute --file -` after all observations and
assessments. Its stdin is `{"reviews":{...},"goals_review":[...],"coverage":[...]}`.
Each review has `fix`, member-only `example`, `evidence_lead_ids` and `goal_ref: null`
until the goals are agreed; application and call also have their raw `rubric` above. Goal reviews
stay in compute's previous-goal order, each with `evidence_lead_ids`, `done_lead_ids`
and `decision`. For live source gaps not visible in saved state, supply a coverage
object `{"source":"recorder","state":"missing","fix":"Connect the recorder"}`,
using the actual source and reason. Code derives all execution/rubric counts and
affected KPI states, before the report and without writing a snapshot.
Use this returned JSON for every reported and stored number; never change a number
or state by hand. Omit live judgments for sources whose computed coverage is correct.

## Step 4 · Report in chat

Write a short conversational markdown summary, at most about 25 lines, along four beats:
1. What happened: last week's commitments, execution and effect separately; any new badge tier.
2. Where you stand: “This week's focus”, one number against its target, own benchmark
   and earlier undecided stages. Name the periods; keep money in won value.
3. Why: one insight with a clickable link to its evidence; one coaching example when useful.
   New segment findings remain “Nothing new this week” until package 4.
4. What now: the one action and urgent to-dos, then three goals for different stages.
Follow with suggested questions the evidence can answer. No charts or wall of tables.

Answer first, mention each stage once, retain only what serves the verdict. Counts
are “k of n”, never a bare percentage; money and time retain their units. Use “not
decidable yet” and “too few cases”, never statistics jargon. State the computed extra
cases needed when a rate is undecided. Quote evidence in follow-ups and name its lead ID.

## Step 5 · Agree and put the goals into practice

Offer goals that worked for this member before the library; propose from the library
first otherwise, and add at most one original commitment. Each has `stage`, `kpi`,
`change`, `start`, `cue`, `action`, `fallback`, `review_on` and `primary`. Three different
stages, exactly one primary for the focus. When there is no confirmed bottleneck, use
the closest-to-failing stage or the lever named by compute. Agree the three with the
member, then help implement them (a reply template or call opener), without sending.

After agreement, pass exactly those goals, with the current `week`, to
`python3 code/analytics.py goals add --file -`. It refuses repeated stages. A dismissed
question or no answer leaves the goals proposed; do not save agreement that did not happen.

The payload is `{"week":"<ISO week>","goals":[<the three commitment objects>]}`;
each object has the fields above, dates as `YYYY-MM-DD` and `primary` as a boolean.

## Step 6 · Record and read back

Start from the final compute object and fill its coaching fields: four `reviews`
(`fix`, member-only `example`, `evidence_lead_ids`, `goal_ref` pointing to the supported
goal's KPI; call `rubric` judgments), goal execution evidence and decisions, agreed
`goals_next`, and `report`. Write each funnel KPI's `insight` (at most 12 words), up to
three `insights_top` of kinds `leak|driver|trend|habit|pipeline|learning|market`, each
with `text` (at most 12 words) and a clickable `target: {view, element}`. Keep new
segment `findings: []` until package 4; any carried finding needs `kpi` or `stage`,
`observed`, `expected`, `n`, `strength` and evidence. Preserve
all numeric fields, including `periods`, `coverage`, pipeline counts/value/age/stalls,
`north_star` wins/fixed/hourly, baselines, deltas, histories and bypass counts.

Keep the validated snapshot shape exactly. Store IDs and anonymous one-line reasons, no
client names, post text or client quotations anywhere. The sole exception is
`reviews.*.example`, which contains only the member's own wording. Scrub the saved
report, goals, verdict and fixes too; an example spoken by a client never qualifies.
External benchmarks, if used as orientation for thin history, stay in references
and only enter a KPI's evidence details as `external_reference` with value,
population, definition, source and date. A `market_line` (at most 8 words, including
the source name) may summarise only that verified reference, never become a target tick.

Claude writes `community_card.next_focus` as a stage label and `community_card.question`
as one question (at most 14 words) from this week's verdict and situation, every week.
Preserve the card's default targets: reply 20%, reply → call 50%, call → won 30%, first
reply median 5 min, regardless of `## Bars`. Applications show this week; rates and
first reply use the same 28-day comparison window for everyone. Preserve
retain rung reached, step count, own previous-four-week trend, last week's three goals
with done marks, newly earned badge and at most five highest badge tiers.

Re-run `python3 code/analytics.py compute --file -` with the completed object after
agreement, so code incorporates the three goals into to-dos and recomputes review-based
goal marks and badges. Use that returned object unchanged for all computed fields.
Send it to `python3 code/analytics.py record --file -`. A duplicate
ISO week is refused; use `--replace` only when the member asks to correct that week's
record. Read back with `python3 code/analytics.py last`, verify the agreed goals and
report, then prune through `pipeline.py`. End with CLAUDE.md's completion report and
the measured `Upwork calls: N`. A refused write or missing agreement stays HELD.
