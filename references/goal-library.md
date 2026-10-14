# Weekly goal library

Start with commitments in `data/analytics-history.jsonl` that the member carried out and
whose results had time to finish. These are coaching hypotheses adapted to Upwork;
before/after improvement does not prove causation. Agree one to three goals in different
funnel stages, including the focus goal, with exactly one primary. Habits belong to the
stage they feed. Add a goal only when eligible opportunities and capacity exist this week.
Every commitment has a cue, action, smaller fallback and KPI. Record its eligible
opportunity, observable completion evidence, start and review date before agreement.
Keep full execution, fallback execution and missed opportunities separate; use the
existing `done_k of done_n` fields for execution, without inventing new field keys.
Review execution next week; keep effects open until the result has had time to finish.
Missing evidence is unreviewable; no opportunities is not completion. Choose the move
that addresses an observed repeated defect, without weakening qualification.

All contact before a contract stays on Upwork. The member submits applications and
accepts offers themselves; each message needs their yes to that exact text. Share video
only through the Upwork proposal or message thread, with no external contact or booking
instructions. Show only public or client-authorised material. Use text when video adds
no decision value or cannot be made safely. Duration bars are production settings,
not proven conversion thresholds. Past-results claims use only confirmed evidence in
`context/me.md` under Results, Reviews or Credentials.

Execution evidence follows the opportunity: submitted copy for application moves,
messages for reply/follow-up moves, meeting agreement for booking moves, full
speaker-labelled `jobs/<id>/call.md` and saved `call-review.md` for call points, sent
proposal for proposal moves and verified offer/contract terms for offer moves. Video
content needs reviewable video or its transcript; a timestamp alone proves no content.
For missing evidence, name the blocked measure and ask for the exact sent text, message,
video or speaker-labelled transcript here; use `/brief <id>`, `/call-review <id>` or
`/sales-call-proposal <id>` to save it through their existing writers. Do not infer success.

## Applied → reply · `reply_rate`

- When writing the first line → name the client's stated problem and desired outcome; if unstated, describe the deliverable without inventing business impact. Fallback: rewrite only the first sentence. KPI: `reply_rate`.
- When choosing proof → use one relevant, verifiable result, with a number and timeframe only when evidenced and shareable. Fallback: a relevant work sample explaining the problem and your contribution. KPI: `reply_rate`.
- When the post is detailed → add one job-specific observation and its implication; label an uncertain diagnosis as a hypothesis, without implementation-ready unpaid work. Fallback: one question resolving an important scope uncertainty. KPI: `reply_rate`.
- When closing the letter → ask one easy question that advances the decision and is not already answered in the post. Fallback: replace the closing line. Answer every required screening question directly and align the bid with scope. KPI: `reply_rate`.
- When recording the Loom → demonstrate one relevant point using available material and ask for one next step on Upwork, under the video rule above. Keep the chosen production limits: the client's problem within 15 seconds and under 90 seconds total; these are settings, not proven conversion thresholds. Fallback: the same observation in text. KPI: `reply_rate`.

## Speed to lead · `speed_10min` (habit)

- When `/find-jobs` flags a fresh fitting post → apply promptly after qualification and required content checks. Measure the deadline from posting, not discovery, using the member's bar (default 10 minutes). Fallback: a shorter complete proposal within that same bar. Record late submissions honestly. Habit: `speed_10min`.
- Before submitting → check the chosen service, capability, rate and availability and record fit evidence. Fallback: review an unclear case before submitting. KPI: `job_fit`. This supports the application stage, not a separate goal stage.

## Weekly volume · `weekly_volume` (habit)

- When planning the day → use member-agreed application sessions toward the weekly target; name peak posting hours only when observed data supports them. Fallback: one agreed session. Habit: `weekly_volume`.
- At each agreed session → submit the agreed share of qualified applications toward the weekly target. Fallback: a smaller agreed share. Calendar blocks support the work but do not prove submission. Habit: `weekly_volume`.
- When a day is missed → redistribute the remaining target across remaining sessions within capacity and fit rules. Fallback: one additional qualified application when available, within the weekly commitment. Habit: `weekly_volume`.

## Reply → call · `reply_to_call`

- When an interested client replies → answer their question first; offer two concrete available Upwork meeting times in the client's time zone only when a call resolves a decision, otherwise advance in the thread. Fallback: one time or resolve the remaining question in writing. KPI: `reply_to_call`.
- When the first client message arrives → use the working-hours clock and member bars (default median 5 minutes and p75 15 minutes). Give a substantive answer, or acknowledge with a concrete answer deadline and meet it. Fallback: acknowledge within the p75 bar. Track acknowledgement separately from resolution. Habit: `first_reply`.
- When a client hesitates about a call → ask what they need to decide and answer in the Upwork thread; use video only if demonstration helps. Fallback: resolve one blocking question. KPI: `reply_to_call`.
- When a client is ready without a call → confirm scope, price, timing and open terms, then ask for the matching Upwork offer. Fallback: resolve the blocking term. KPI: `reply_to_call` (offer or contract also qualifies).

## Silent clients · `follow_ups_on_time` (habit)

- When a client has been silent 3 business days → use an existing, messageable Upwork thread with an unanswered member message. Honour an agreed decision date; otherwise address the unresolved decision on the scheduled day. Fallback: one relevant question. Exclude unanswered applications without a thread. Habit: `follow_ups_on_time`.
- When still silent on business day 7 → send one final brief question, then stop. Fallback: a shorter question. Stop earlier after a decline, closure or request to stop. Both due dates use the saved silent sequence's `anchor_at`; the first follow-up does not restart the sequence. Habit: `follow_ups_on_time`.

## Booked → held · `booked_to_held`

- When a call is booked → confirm time, time zone and agenda in the Upwork thread; ask a prep question only if needed. Fallback: time and a one-line agenda. Count execution per booking, independently of attendance. KPI: `booked_to_held`.
- The day before the call → at the agreed reminder time, confirm the Upwork meeting time/link and purpose; if booked too late, confirm immediately. Fallback: time/link alone. An extra insight is optional. KPI: `booked_to_held`.
- When the client does not show → after the agreed grace period, send a courteous message with available replacement times. Fallback: one time. Keep the original booking and later reschedule separate; do not erase a confirmed no-show in a finished measurement period. KPI: `booked_to_held`.

## The call itself · call review points

Use applicable rubric coverage from the full speaker-labelled transcript and saved review.
Each `not needed` point carries a reason. Missing evidence means unreviewable execution.

- When opening → confirm the client's goal and brief agenda within the first two minutes, using the booked duration. Fallback: goal and next-step purpose. Call point 1.
- When the problem is named → if impact is not known, ask for a concrete consequence in money, time or leads and how the client estimates it. Fallback: one consequence question. No invented ROI or forced monthly calculation for a one-off project. Call point 3.
- Before any price → confirm budget constraints and relevant scope; a confirmed posted budget counts. Fallback: confirm the known budget or ask the range once. Call point 5.
- When ending → agree the next step, owner, exact time and client agreement; include scope, price and decision maker where unresolved. Fallback: one next step with owner, time and agreement. When unknown, identify other approvers/timeline, show matching proof and ask what could prevent proceeding; credit information already known. Call points 6 to 9.

## Held → proposal · `held_to_proposal`, `proposal_on_time`

- When a fit call ends → send a decision-ready proposal within 30 minutes of call end: deliverables, acceptance criteria, exclusions, dependencies, price/payment structure, timing and next step. Fallback: a shorter complete proposal within that deadline. A recap followed by a same-day proposal is partial execution and a timing miss. If essential information is missing, agree its owner and delivery time; do not silently exclude the call. Habit: `proposal_on_time`.
- When the call shows no fit → record the evidenced unmet requirement and clean disqualification. Fallback: name that requirement. This is qualification or a call-review commitment, not a `held_to_proposal` improvement goal; disqualifications leave that denominator. True North credits informed disqualification.

## Proposal → won · `proposal_to_won`

- When pricing → offer alternatives only for a real scope/budget trade-off; otherwise propose one complete best-fit scope, with deliverables, exclusions, timing and price. Fallback: one complete offer. KPI: `proposal_to_won`.
- When presenting the price → explain it with the agreed scope, client-confirmed outcome and evidenced benefit. Fallback: explain the deliverable and trade-off. Do not guarantee payback from an uncertain estimate. KPI: `proposal_to_won`.
- When the proposal is sent → ask for or confirm the decision process, date and next Upwork action; offer a walkthrough only to resolve complexity. Fallback: the next-step question in text. A requested date is not an agreed date. KPI: `proposal_to_won`.
- When the client says "too expensive" → distinguish budget, value, scope, timing and risk before offering smaller scope. Fallback: one clarifying question. Do not reduce price reflexively; any concession must remain commercially viable. KPI: `proposal_to_won`.

## Invite → call · `invite_to_call`

- When an invite arrives → answer using the working-hours bars and offer a call only when useful; allow offer/contract progression without a call. Fallback: answer the immediate request within the response bar. Declining poor fit is qualification, not conversion success. Habit: `first_reply`; result: `invite_to_call`.
- When an invite leaves uncertainty about fit → before booking, provide relevant proof that resolves it; video is optional. Fallback: one specific observation in text. KPI: `invite_to_call`.

## Offer → contract · `offer_to_contract`

- When an offer arrives → check scope, deliverables, acceptance criteria, price, dates, capacity and terms against the agreement. The member accepts on Upwork when aligned. Fallback: identify all mismatches and request corrections in Upwork Messages. Start only after the contract is active; verify funded fixed-price milestones before their work. KPI: `offer_to_contract`. Kickoff belongs to delivery, after this result.

## Public goal IDs

After the member agrees a library goal, save its `goal_library_id` in the agreed
goals ledger. This selects the fixed public label below; private cue, action and
change text never appear on the community card. Goals without an ID stay private.
The public card also verifies the stable `goal_id` against that agreement.

| Goal library ID | KPI | Fixed public label |
|---|---|---|
| `reply-opener` | `reply_rate` | Name the posted problem |
| `reply-proof` | `reply_rate` | Use one relevant proof |
| `reply-observation` | `reply_rate` | Add one useful job observation |
| `reply-close` | `reply_rate` | Ask one useful closing question |
| `reply-video` | `reply_rate` | Show one relevant point |
| `speed-qualified` | `speed_10min` | Apply promptly after checking fit |
| `fit-check` | `job_fit` | Check fit before applying |
| `volume-sessions` | `weekly_volume` | Keep agreed application sessions |
| `volume-share` | `weekly_volume` | Submit the agreed qualified share |
| `volume-replan` | `weekly_volume` | Replan missed application sessions |
| `call-times` | `reply_to_call` | Offer two useful call times |
| `first-answer` | `first_reply` | Answer within agreed working hours |
| `call-question` | `reply_to_call` | Resolve the blocking question |
| `call-free-offer` | `reply_to_call` | Confirm terms before the offer |
| `followup-first` | `follow_ups_on_time` | Follow up on the agreed day |
| `followup-last` | `follow_ups_on_time` | Send one final useful question |
| `meeting-confirm` | `booked_to_held` | Confirm the meeting and agenda |
| `meeting-remind` | `booked_to_held` | Confirm the meeting before it starts |
| `meeting-reschedule` | `booked_to_held` | Offer replacement times after absence |
| `call-opening` | `call_review` | Confirm the goal and agenda |
| `call-impact` | `call_review` | Ask about the problem impact |
| `call-budget` | `call_review` | Confirm budget before naming price |
| `call-step` | `call_review` | Agree the next step and owner |
| `proposal-prompt` | `proposal_on_time` | Send the complete proposal promptly |
| `proposal-fit` | `held_to_proposal` | Record the evidenced fit decision |
| `proposal-scope` | `proposal_to_won` | Offer one complete fitting scope |
| `proposal-value` | `proposal_to_won` | Explain price with the agreed scope |
| `proposal-decision` | `proposal_to_won` | Confirm the next decision step |
| `proposal-objection` | `proposal_to_won` | Clarify the price concern |
| `invite-answer` | `first_reply` | Answer the immediate invite request |
| `invite-proof` | `invite_to_call` | Share proof before booking |
| `offer-check` | `offer_to_contract` | Check the offer against the agreement |
