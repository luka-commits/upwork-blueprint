# Follow-up rules

What: a context-based sequence for leads in touch and for previous clients.
Basis: reasoned; the only data point is one imported conversation (12 September 2026).
Next: run `/brief` without a job id each morning; it runs this sequence first.

The point is to make the next decision easy, not to maximize message count.
Context can stop a sequence or move its date.

## Reply now

When `awaiting_reply_from` is `you`, answer today. This is a reply, not a dormant
lead follow-up, and it does not consume a sequence step. A client question,
requested change, call request or offer always outranks scheduled follow-ups.

## In touch

Use `active` when the client wrote last and needs an answer. When the member wrote
last in a messageable thread (`replied`, `call` or `offer`), use `silent`: follow up
on business days 3 and 7, then stop. Keep the original unanswered turn as `anchor_at`;
the first follow-up does not restart the clock. Honour an agreed decision date.
Each message addresses the unresolved decision: answer a blocker, narrow scope or
make the next choice smaller. A generic status request does not count as value.

## Previous client

Use `reactivation` only for a `won` client with a positive relationship and a
real reason to reconnect. An unfinished promise or stated date overrides this
lane and becomes a normal task.

Allow two messages, 30 then 60 business days apart. Lead with a relevant idea,
change or next project based on the completed work. Do not send a vague
"hope you're well" sequence.

## Applied, lost, skipped and new

An `applied` proposal has no room until the client writes, so it has no follow-up
and creates no task. After 14 full days without a client reply `/brief` lists it as
stale and asks whether to set `lost`; Lost is always the member's call.

Do not follow up with `new` or `skipped` jobs. A `lost` lead gets one future
check only when the client explicitly named timing or budget as the reason and a
date makes sense. Otherwise it stays closed.

## Context beats the cadence

Stop immediately after an explicit no, a request for no more contact, evidence
that another freelancer was hired, or a move to another agreed communication
channel. Do not duplicate the conversation across channels.

Honor a date the client named. Follow up on the next business day after a missed
promise, not on the generic cadence.

Count meaningful client turns, not message bubbles. Three short bubbles sent in
one minute are one turn. Multiple unanswered member messages reduce the next
sequence, never increase it.

## What each message earns

The first message reopens the exact decision, later ones add a new reason to
answer. Every message should be understandable without reading a sales template,
grounded in the thread and written as the member. The bare "just checking in"
message added no value in the one thread read, so this system excludes it.

## Workflow

Turn the current pipeline and fresh conversations into today's follow-up queue.
The member starts every run. The run decides and drafts; a draft only leaves on
their yes to that one message.

### Start with current evidence

Read `data/sync.json` and run
`python3 code/pipeline.py summary`.

If today's sync is missing or any relevant thread is older than 24 hours, follow
`.claude/commands/brief.md` Step 1 once before reviewing. Call the connector as
`references/upwork.md` describes. Never poll or read every historical room.

Review jobs in `replied`, `call`, `offer` and `won`. An `applied` proposal without a room
cannot receive a message, so leave it waiting without a task, reminder or draft.

### Decide from the conversation

For each job, read the pipeline record and the full saved thread oldest first.
Use the status, `awaiting_reply_from`, last meaningful message, explicit dates,
client engagement and consecutive messages from the member. Apply the lane,
cadence and stop conditions above.

Stop when the thread is weak, the client moved the conversation elsewhere or
another message would add no reason to answer.

Keep an existing plan; never restart a finished or stopped sequence unless the client returns.
For a new sequence, write the decision only through:

`python3 code/pipeline.py follow-up <id> plan --lane <lane> --due <date> --at <zoned-ISO-time> --reason "<conversation-based reason>"`

Clear a sequence when a stop condition applies:

`python3 code/pipeline.py follow-up <id> clear --reason "<why>"`

### Draft only what is due

For every sendable lead due today or earlier, follow `references/copy.md` and
Step 4 of `.claude/commands/brief.md`. Save two drafts to
`jobs/<id>/replies.json` and run `python3 code/replies.py check <id>`.

Each follow-up adds one new reason to answer: a useful observation, a narrowed
decision, a relevant next step or a graceful close. A pure "just checking in"
message is not a draft.

Report each due lead's decision and reason in chat. The cockpit shows each lead's
next action, waiting date or Parked state in its existing board and list.

### Report

Use the repository's completion report. Lead with the number due now and name
the strongest opportunity. Then run `python3 code/pipeline.py follow-up <job id> sent`
for each message that actually went out, whether it left from here on the member's
yes or they sent it on Upwork and said so. The sequence advances on arrival, never
on the draft. End with the exact Upwork call count.

### Self-improvement

When the member corrects a cadence decision or a follow-up wins a reply, ask
whether to keep the lesson. If yes, record it against that job with
`python3 code/pipeline.py note <job id> "<the dated observation>"`, where the
next run will find it. Change the intervals in this file only after two
independent examples support the same default.
