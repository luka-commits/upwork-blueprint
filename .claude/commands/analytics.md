---
description: "Your weekly Upwork coaching loop: checks last week's goals, measures the funnel, finds this week's focus and agrees one to three commitments with you."
argument-hint: ""
---

# /analytics

Run weekly, on the member's `## Analytics day`. Code does every number; Claude reviews
the evidence, explains the verdict and agrees the goals. Nothing is sent to Upwork.
Read `context/me.md`, [references/copy.md](../../references/copy.md),
[references/goal-library.md](../../references/goal-library.md) and
[references/coach-brief.md](../../references/coach-brief.md). `analytics.py` validates
the snapshot contract; use its complete compute object as the shape. For connector reads follow
[references/upwork.md](../../references/upwork.md) and [/brief](brief.md) Steps 1–2.

## ROADMAP

WHAT HAPPENS: refresh the evidence, check last week's commitments, measure this week's focus and propose one to three goals. First-run preparation can take longer; routine checks have no measured duration claim.
I NEED FROM YOU: missing call evidence, any tool-install yes and agreement on one to three goals before they are saved.
WHAT MIGHT GO WRONG: missing sources leave affected checks unmeasurable; too few finished cases may leave a rate unclear. The coaching still runs.

## Step 1 · Setup and sync, inside this command

Run `python3 code/workspace.py`. Read `data/sync.json` and check the connector with
`list_accounts`. If unreachable, walk through README's connection steps; preserve the
available evidence and name the source gap. If the last sync is absent or older than
24 hours at the actual zoned run time (reject future sync stamps), carry out `/brief` Steps 1–2 (read and sync only, no drafts or sends).
Use saved state when fresh; count every Upwork call.

**First analytics run:** backfill what the connector can actually enumerate: proposals,
invitations, contracts with values and start dates, Connects transactions and weekly
earnings. For proposals, read the connector's documented status enum and page **every
status**, including Archived, independently to exhaustion; Accepted/default is insufficient.
Deduplicate proposal IDs across status pages, prefer the newest modified copy, and classify
the returned proposal's own status, never the requested filter. Follow the documented pagination, stop when history is exhausted or the
connector's limit is reached, and name the uncovered period. On first sync, proposals
created by `sync.py` are imported; unmatched offers and contracts are imported too.
For absent historical leads, use `pipeline.py add --file -` with `imported: true` and
the verified fields. Existing matched leads cannot have that marker changed through
the current writer: preserve them and name that backfill limitation in coverage.
Preserve observed entry dates when known; never infer them from current stages.
Imported leads feed won value and baselines only, never rate populations or weekly applications.
Pass earnings and Connects to `sync.py apply --file -` in its documented number-and-ID
shapes. An omitted/unreachable source is missing. A verified checked-empty result is an
explicit empty list; sync records it as empty, with checked coverage.
Retain `viewedByClient` as a boolean observation with observation time/source; true
observes `proposal_viewed` verified from `upwork-proposal`, never the actual view time.
Fetch each submitted proposal's insights once by proposal ID through the read-only `get`
action and persist /brief's `proposal_insights` envelope; never rewrite application facts.
Retain proposal connectsBid/boosted evidence separately. Efficiency uses every negative
financial ledger spend, including invitation badges, without adding proposal costs again.
Invitation dates use a complete room's first verified client message or sync observation
fallback with `invited_at_source: room|sync`; later room evidence replaces the fallback.

Check `yt-dlp`, `whisper-cli` and `code/loom.py`'s `find_model()` for missing Loom
evidence. Show `brew install yt-dlp whisper.cpp` and `MODEL_DOWNLOAD` when needed;
install only on the member's yes. On Linux use platform-specific instructions.
Use `python3 code/loom.py <id> <recorded Loom URL>` for a missing Loom transcript.
For call evidence, use
[references/call-transcript.md](../../references/call-transcript.md). Do not copy its
fetch procedure here. A recap proves held; missing recaps alone never prove no-show.
Recap errors remain `recap_state: unknown` with `recap_reason` and source coverage.
Requested/pending meetings stay call-asked metadata, never booked observations.
Preserve actual sessions and reschedules. Reuse `jobs/<id>/call-review.md`; run
[/call-review <id>](call-review.md) only when that saved review is missing.
No transcript means no call review from a recap, summary or notes.
Print instant award lines returned by pipeline/sync verbatim, once; badge failure cannot fail a data write.

Check one existing registered tracking link with `?check=1` and its redirect; require
`X-Tracking-Status: check: not logged`, then `python3 code/clicks.py`. The test must
not become a human click or a client opening in the pipeline.
If none exists or access fails, say why tracking is missing; register or deploy nothing.
Keep each absent, stale or unreachable source in code's coverage input with its affected KPI keys
and one fix. The final contract uses `coverage.missing: [{source, blocks, how_to_supply}]`: name
the missing source, the KPI or review it blocks and the exact way to supply it. Use `missing` for an absent or unreachable required source: affected KPIs
become missing, rather than zero. `stale` labels readable evidence that needs refresh;
it never proves a source was reachable. Do not claim a check that was not made.

## Catch up since the last accepted record

Read `python3 code/analytics.py last` before choosing the review period. Catch up
on everything since that accepted check-in, including every goal due through the gap.
Use `gap: {weeks_missed, since}` from code. Member wording is exactly:
"Missed a week? Next time you run /analytics it catches up on everything since your last check-in."

Read `python3 code/analytics.py compute --catch-up` for the separate missed-week
snapshots, in chronological order. Current `record --file -` appends those histories
atomically with the current snapshot; do not record the preview objects separately.
Their historical `week`, `generated_at` and `periods` come from code. Do not invent
past agreements: current goals are agreed only for the current week. Review every
goal due since the last check-in over the full gap. If historical snapshots omit
required goal review or cannot pass the record contract, name the code gap and hold
that claim; do not fabricate past goal agreement or add fields or flags.
Then compute the current week. Then-current proposal status, Connects balance and
other unreconstructible point-in-time facts stay missing with their blocked result
and supply route. Open the chat with elapsed time since the last check-in and tell
the full gap as one story while keeping the per-week records separate.

## Step 2 · Compute, then read the cases

Run `python3 code/analytics.py compute` and keep the returned JSON unchanged as the
numeric source. It supplies activity (seven days), mature result populations (28 days), outcomes,
the own benchmark, source coverage, lead IDs and last week's goals.
Rates pool successes and eligible cases; unknown entry dates never enter a rate population.
Outcome rates (KPIs 3–9) collect weeks 1–4 without a rate verdict, then target the next
level; `## Bars` changes only the top level. Habit KPIs 10–14 start with reasoned defaults, adjustable through `## Bars` to
feasible availability, promised deadlines and dependencies. A speed miss is a
coaching candidate; require case evidence before claiming it caused lost revenue. The computed focus is the clearly failing stage with the largest lost revenue:
(target − rate) × n × own downstream conversion to won × average won value. Ties
and missing values fall back to funnel order. Its failing feeding habits come first: reply rate ← speed; reply → call ← first reply or follow-ups; held → proposal ←
proposal speed. Earlier missing or undecided stages stay in `undecided_before`. When
no rate verdict is supported, use the measured habit and returned `cases_needed`. During
baseline collection, inspect available sent applications before choosing coaching:
identify a supported, controllable defect in fit, content or execution. If none is
supported, keep the agreed practice goal without inventing a bottleneck. Preserve
code's focus identity and state; if it conflicts with the evidenced coaching action,
name the implementation gap rather than overwrite it.
Read `presentation.scorecard` as the one scorecard grouped `top`, `middle`, `bottom`.
Every row compares last 28 days with previous 28 days, including habits; do not
substitute the weekly activity window. Preserve row `key`, `group`, `name`,
`stage_label`, `period_label`, `period`, `value`, `finished` (k of n), `pending`,
`change: {previous_value, comparison_label}`, `series: {label, unit, points}` with
8 points, `target: {kind: habit|ladder, value, level, thresholds}`,
`next_action: {text, lead_filter}` or null, `split`, `focus: {reason}` or null and
`market: {value, source}` or null, as returned by code. Result names are Reply rate,
Call rate, Show-up rate and Win rate, with the transition in `stage_label` beneath.
Held-call to proposal completion sits inside "Proposal within 30 min of call end"
over all fitting held calls. Preserve that population and its split, never a
separate result row. Missing row values display "unknown", never zero or an estimate.
No new segment findings or expectation tests: KPIs 20–21 say “nothing new” until package 4.

Read each evidence lead with `python3 code/pipeline.py get <id>`, its sent application,
thread, Loom transcript, call and sent proposal where relevant. On the first run, prepare the evidence inventory. On routine runs, review at most
five cases for the chosen focus plus urgent exceptions; disclose the sampled IDs
and unreviewed coverage. This five-case limit excludes conversation coverage and badge eligibility: read every
reply thread without a call or offer, and use the complete mature population for
conversion badges. Inspect all relevant cases to verify a claimed repeated pattern. Missing or pruned evidence is a gap.

## Step 3 · Review and accountability

**New applications:** judge lane and rate against `context/me.md` and the full post,
`pass | fail | unclear`, with a quoted reason. Store it through the sole pipeline writer:
`python3 code/pipeline.py note <id> 'analytics job_fit: {"state":"pass","reason":"..."}'`.
Use compact JSON and the actual judgment, within the note's 1,000-character limit.
This tagged note is the assessment transport; never write `data/jobs.json` directly.

**Application review:** read verified `jobs/<id>/application.sent.md`, submitted
answers and bid; check `application_modality`. For `uma`, review submitted
interview answers/video against requested questions, not a cover-letter rubric.
Loom and a bespoke site are optional when justified by requirements, value and
preparation cost. Read Loom only if used. Every point
is `met | partly | missing` with a supporting quote: first sentence names the posted
problem in the client's words; one matching proof; every screening question answered
specifically; bid fits scope; under about 150 words; one easy closing question; Loom,
if present, names the problem within fifteen seconds and ends with one ask. Prioritise consequential eligibility blockers, then recurring defects. Repair the
actual artifact that failed: screening answer, proof, bid/scope, opener or video close;
never rewrite an opener for an unrelated defect. Treat missing sent copy as missing evidence, not a failed application.
Pass `reviews.application.rubric` as `[{lead_id, reviewable, points:[{point,state}]}]`.
Keep supporting application quotes in the private report or local sent evidence;
Application points do not accept `quote`; omit optional call-card fields here.
For text, points 1–6 follow the six application checks above; point 7 is Loom only
when used. For Uma, points 1–3 mean requested questions covered, submitted answers
are relevant and evidenced, and the submitted video meets the requested format.
Judge the actual interview artifacts; text/Loom checks do not apply. States are `met | partly | missing`. A reviewable lead needs its
sent copy; otherwise `reviewable: false` and `points: []`. Code derives point coverage.

**Conversation review:** for every reply thread without a call or offer, use read-only
`get_messages` action `list_messages`, following the connector's documented pagination
through every page. A short page is not proof of completeness. Read oldest first;
never invent a message, author, read receipt or timestamp. Record the exact contract:
`conversation_review: {threads: [{lead_id, points: {fast_answer, answered_question,
qualifying_question, call_times, follow_ups}, last_writer, read}], pattern}`.
Each of the five points is `{state: met|partly|missing|not_needed, quote, reason}`.
Check fast first answer, answer to the client's question, one qualifying question,
two concrete call times and follow-ups on business days 3 and 7. Support each with
an actual quote; for missing evidence, say what is missing without fabricating a
quote. Every `not_needed` carries a reason. Derive `last_writer` from verified messages; use `unknown` when unavailable.
`read` means this evidence review is complete, never a client read receipt.
`pattern` contains only a repeated, evidenced pattern over the reviewed threads,
with k of n; no repeated pattern means no invented generalisation. Use the coach
brief for judgment and one useful fix/example, including a one-sentence read per
thread without adding a field to the snapshot. Save each lead's judgment through
`python3 code/pipeline.py record <id> --file -` as
`{"conversation_review":{"points":{...},"last_writer":"me|client|unknown","read":true}}`.
Use actual values: `read` is a boolean for the completed evidence review, not a client
read receipt. Unread or incomplete evidence uses `read: false` and missing points
with reasons; unknown `last_writer` is `unknown`. Empty quote strings are permitted
only when there is no supporting message; met/partly need verbatim quotes. Compute
assembles `lead_id`, threads and pattern. If its pattern occurs only once, report
no repeated pattern and name the code gap instead of changing computed fields.
Keep coverage gaps visible.

**Proposal review:** use the coach brief to compare the sent proposal with the held
call's agreement, with a quoted observation and a grounded fix/example.

**Call coaching rubric:** point judgment, Coach's read, moments, next step, fix and
example follow [references/coach-brief.md](../../references/coach-brief.md), through
[/call-review](call-review.md). Reuse the saved full review and its recorded rubric,
not a summary-only review. If markdown exists but the rubric was not saved, use `/call-review` Step 3 to
re-record the complete original nine-point review when the writer supports it,
without new judgment. Otherwise name the mandatory RUN CODE writer/storage or schema-parity gap;
never drop the saved review from weekly coverage or infer points from a summary.
Preserve verified member identity, language and transcript completeness. An excerpt
or omitted language segment cannot support a whole-call verdict. Without complete
speaker labels the call is not reviewable; unknown evidence stays unknown. Credit
information established in the post/thread with its source, without penalising a
question already answered. Every `not needed` point has a reason in the saved
review and in each `not needed` point's required `reason`, as the validator requires.
Keep these nine comparable point definitions here:
1. Opening and agenda in the first two minutes.
2. Current state (already known in the thread also counts).
3. Problem and its cost in money, time or leads.
4. Goal and scope.
5. Budget before the price (a confirmed posted budget counts).
6. Decision maker and timeline (`not needed` when the decider is on the call).
7. One proof matching the stated problem.
8. Objections actively invited, and handled when raised.
9. Next step with owner, time and the client's yes.

Record qualification through `pipeline.py record <id> --file -`: `call_outcome` is
`proposal_required|disqualified|direct_win|unresolved`, with `proposal_required`
true only for an agreed proposal obligation. A clean “not a fit” is a disqualification,
never a bad call; it and proposal-free offers/contracts leave proposal denominators. Pass `reviews.call.rubric` as one object per call:
`{"lead_id":"<id>","reviewable":true,"points":[{"point":1,"state":"met","quote":"<verbatim local call.md excerpt>"}, ...],"moments":[{"quote":"<verbatim local call.md excerpt>","better_wording":"<better member wording>"}],"next_step":"<owner, time and client's agreement>","fix":"<one fix>","example":"<member wording>"}`.
Include all nine numbered points once each, with `state: met|partly|missing|not needed`;
`reason` is required for every `not needed` point. `quote` is optional when no supporting local
excerpt exists. Never fabricate missing quotes. Store verified per-point quotes in
the private rubric; include at most three moments with exactly `quote` and
`better_wording`. `next_step` is a string containing owner, time and client agreement,
or null when absent; `fix` and `example` are strings. For an unreviewable call set
`reviewable: false` and `points: []`. Derive private `call_cards`, per-point coverage
and weekly history through compute; never hand-write derived metrics or cards.
Talk share and question count remain context, never the verdict.
Private rubric/card quotes must be verbatim `jobs/<id>/call.md` excerpts and never enter the public card.

**Lost leads:** distinguish `stated | observed | unknown`; do not turn a guess into the
client's reason. Use `pipeline.py note <id> 'analytics lost_reason: {"kind":"stated","reason":"..."}'`.
**Last week's goals:** inspect the named evidence leads to mark each eligible action
done or undone. Pass each goal's `evidence_lead_ids` (all eligible leads) and
`done_lead_ids` (its completed subset), so code derives `done_k` and `done_n`.
Execution is `done_k of done_n`; outcome comes from code's KPI before
and after the goal start (`worked | not | undecided`: observed improvement, decline, or unresolved change), separately
from target attainment. An observed change is association, never proof of causation.
Review every unresolved goal due by today, including goals from missed weeks. Decide `keep | adjust | stop`.
If a commitment went undone two weeks running, say so and offer its simpler fallback.

Re-run `python3 code/analytics.py compute --file -` after all observations and
assessments. Its stdin is `{"reviews":{...},"goals_review":[...],"coverage":[...]}`.
Each review has `fix`, member-only `example`, `evidence_lead_ids` and `goal_ref: null`
until the goals are agreed; application and call also have their raw `rubric` above. Goal reviews
stay in compute's previous-goal order, each with `evidence_lead_ids`, `done_lead_ids`
and `decision`. Preserve the code-assembled `conversation_review` under its
contract name, not an invented member of `reviews`. For live source gaps not visible in saved state, supply a coverage
object `{"source":"recorder","state":"missing","fix":"Connect the recorder"}`,
using the actual source and reason. Code derives all execution/rubric counts and
affected KPI states, before the report and without writing a snapshot.
Use this returned JSON for every reported and stored number; never change a number
or state by hand. Omit live judgments for sources whose computed coverage is correct.

## Step 4 · Weekly coaching and report

Use [references/coach-brief.md](../../references/coach-brief.md) for judgment and
[references/chat-report-example.md](../../references/chat-report-example.md) as a tone
example, not a form. No fixed paragraph order, sentence count or stock rubric verdict.
Carry every weekly item required by the brief, choosing the order and connections
that explain what matters most. Keep all sourced items: won value versus own history;
selection, volume, sent-application quality and speed; Reply rate, conversations,
booked and held calls, first replies and follow-ups; call coaching; proposals, close
and Win rate; inbound invites and offers; Connects spend and efficiency; supported
patterns; live pipeline and supported forecast; due goals with execution, effect
and keep/adjust/stop; immediate actions and one to three proposed commitments;
newly earned badges and three useful follow-up questions. The result in money and
one priority belong in the first two sentences, alongside Funnel Score in the
opening line. Give top, middle, bottom, inbound and money spent at least one sentence
each with its period. Include the call read across calls and the conversation pattern
when one repeats; at most two supported patterns with numbers; forecast basis as a
guide; open deals first, then one to three habits phrased as cue and action. Keep
each item once and use about 280 words without dropping a source gap. Distinguish fixed won value,
hourly terms and billed earnings; unknown terms stay unknown. Include every carried
brief item even when its source is missing, as a gap rather than a result.

The opening line includes elapsed time after a gap and the code-produced Funnel Score,
for example "Funnel Score 88, was 81" only when those numbers exist. Use
`funnel_score: {score, previous, parts: {habits, results}, dropped: [{part, reason}], baseline_only}`.
Code alone computes the weekly 0 to 100 score, never summed or ranked: habits 60
(applications versus commitment, within 10 minutes, first reply median, follow-ups
on their day, proposal within 30 minutes), 12 each capped at target; results 40
(Reply rate, Call rate, Show-up rate, Win rate), 10 each by achieved level / 3 on
finished cases, uncertain levels credit the level below. Drop parts without
opportunities and rescale, never award on 0 of 0. In weeks 1–4 use habits only,
scaled to 100, labelled "habits only until your baseline is set".

Every sent-application correction has exactly four parts: the sent passage and job
ID; the point it misses or partly meets; a replacement grounded in the job and the
member's real proof; one instruction for the next application. Repair the actual
failed artifact. Missing copy: "Your sent application is unavailable. Paste it to
receive a review." Never invent a defect to fill this shape.

The first four weekly experiences, grounded in actual records:
1. Make the next application better: explain baseline collection and no previous
   four-week comparison, review a sent passage and agree one usable practice goal.
   The app leads with that review and action, actual activity, fit and Connects spent,
   with baseline collection and no recorded calls where true. The community card
   shows actual activity, baseline collection and the goal, without improvement claims.
2. Check whether the fix was used: compare new sent copies with that goal, give
   execution k of n separately from uncertain response effect, keep or adjust it,
   and review due follow-ups when applicable. The app shows before/after passages,
   execution evidence, pending replies separately from eligible replies and only
   actual due follow-ups. The card shows execution, activity and supported outcomes.
3. Resolve low activity: distinguish few fitting jobs, skipped fitting jobs and
   difficulty finishing applications using search/sent evidence. If it cannot tell,
   ask one targeted question; offer a smaller fallback or specific correction.
   The app puts the relevant job/application beside the action; a reply-to-call goal
   needs an actual interested reply. The card shows the controllable focus, never
   a fabricated biggest improvement.
4. Decide what to keep and change: review commitments, actual application changes,
   supported outcomes and Connects spent; choose keep, adjust or stop with evidence.
   Four elapsed weeks do not establish conversion improvement. Use actual completed
   reviews and never imply a badge was earned merely by attending. The app shows
   available history and the next commitment, leaving uncertain outcomes unclear.
   The card shows supported progress and next focus; unestablished improvement
   stays unestablished. Any public question must pass the existing allowlist.
Every week gives a usable correction, checks an existing correction or resolves a
named obstacle. No opportunity means the goal was not tested, never success/failure.

Name periods and k of n; retain money/time units. Use "not clear yet" and "too few
cases" and code's `cases_needed`; no member-facing statistical jargon or raw payloads.
Quote conversation/call evidence and name the supporting job where needed. After
findings, include **What I couldn't check** whenever `coverage.missing` is not empty:
what is missing, the blocked KPI/review and exactly how to supply it. No unsupported
result may appear elsewhere in the report.

Use code's award wording once per new award. Qualifying accumulated weeks per badge:
Bronze 1, Silver 3, Gold 6, Platinum 13, Legend 26; at most two badges in the first
week. Speed needs fit and content checks; no extra credit above weekly commitment.
Pauses and weeks without opportunities neither advance nor erase progress; never
award on 0 of 0. Conversion badges use the full mature population. True North credits
informed disqualification and excludes reasoned `not needed` points. Rank Deckhand
to Admiral counts Silver-or-higher badges, never weekly review attendance. A clean
disqualification is a valid informed call outcome, not a failed sale. Preserve
the decided rank, treasure map, islands, Lighthouse Keeper and Back on Course.
Weekly compute checks tiers from reviewed evidence; record persists awards. Never
repeat an instant award already printed or call an old earned tier new. Badge
failure leaves a named gap and does not fail the data write.

## Step 5 · Agree and put the goals into practice

Offer goals with supported observed improvement for this member before the library; propose from the library
first otherwise, and add at most one original commitment. Each has `stage`, `kpi`,
`change`, `start`, `cue`, `action`, `fallback`, `review_on` and `primary`. One to three different stages, exactly one primary for the focus. When there is no confirmed bottleneck, use
the closest-to-failing stage or the habit named by compute. Agree one to three with the
member, then help implement them (a reply template or call opener), without sending.

After agreement, pass exactly those goals, with the current `week`, to
`python3 code/analytics.py goals add --file -`. It refuses repeated stages. A dismissed
question or no answer leaves the goals proposed; do not save agreement that did not happen.

The payload is `{"week":"<ISO week>","goals":[<the one to three commitment objects>]}`;
each object has the fields above, dates as `YYYY-MM-DD` and `primary` as a boolean.

## Step 6 · Record and read back

Start from the final compute object and fill its coaching fields: four `reviews`
(`fix`, member-only `example`, `evidence_lead_ids`, `goal_ref` pointing to the supported
goal's KPI; call `rubric` judgments), goal execution evidence and decisions, agreed
`goals_next`, and `report`. Write each funnel KPI's `insight` (at most 12 words), up to
three `insights_top` of kinds `leak|driver|trend|habit|pipeline|learning|market`, each
with `text` (at most 12 words) and a clickable `target: {view, element}`. Keep new
segment `findings: []` until package 4; any carried finding needs `kpi` or `stage`,
`sentence`, `action`, `observed`, `expected`, `n`, `strength`, `status` and evidence.
Use the validator's known KPI/stage, finite numbers or null, nonnegative integer
`n`, `strength: emerging|holding` and `status: finding|emerging|confirmed`; no new
finding can bypass the frozen discovery/confirmation constraints. Preserve
all numeric fields, including `periods`, `coverage`, pipeline counts/value/age/stalls,
`north_star` wins/fixed/hourly, baselines, deltas, histories and bypass counts. Preserve the contract fields
`presentation.scorecard`, `funnel_score`, `coverage.missing`, `conversation_review`
and `gap`; if not yet implemented, name the code gap and hold affected results.
Do not invent fields or hand-build missing computed objects.

Keep the validated snapshot shape exactly and link supporting quotations to their
lead evidence. Coaching examples contain the member's wording. Apply the public
card's strict allowlist below; do not introduce another local privacy/retention gate.
External benchmarks, if used as orientation for thin history, stay in references
and only enter a KPI's evidence details as `external_reference` with value,
population, definition, source and date. A `market_line` (at most 8 words, including
the source name) may summarise only that verified reference, never become a target tick.

Use a code-approved fixed label for `community_card.next_focus`. The public payload accepts only
allowlisted aggregates, fixed labels, the member's own name, library/member-authored
goal texts and badge names; never client names, job titles, client text or snapshot
embeds. Frozen §13 permits generated question/biggest-improvement reason only at ≤14 words
and after the automatic check against all known lead titles/client names; otherwise
drop the field. Record refuses other unapproved public fields and wording.
Frozen §13.3 uses one common 28-day community window for rates and first reply;
label weekly applications separately. Show route and k/n, level reached, step count
and progress against the member's own baseline; no target pass/fail flags, default
target ticks or external target ticks. Peer rates do not adjust for job mix or price.
Money appears only when `Share money: yes`. Retain last week's applicable goals
with done marks, newly earned badge and at most five highest badge tiers.

Re-run `python3 code/analytics.py compute --file -` with the completed object after
agreement, so code incorporates the agreed goals into to-dos and recomputes review-based
goal marks and badges. Use that returned object unchanged for all computed fields.
Send it to `python3 code/analytics.py record --file -`. A duplicate
ISO week is refused; use `--replace` only when the member asks to correct that week's
record. Read back with `python3 code/analytics.py last`, verify the agreed goals and
report, then prune through `python3 code/pipeline.py prune`. End with CLAUDE.md's completion report and
the measured `Upwork calls: N`. A refused write or missing agreement stays HELD.
