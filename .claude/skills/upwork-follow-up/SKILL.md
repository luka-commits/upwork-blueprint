---
name: upwork-follow-up
description: Reviews dormant Upwork leads and previous clients, chooses a context-based follow-up lane, creates grounded drafts and schedules the next step. Runs only when a member starts it and sends nothing.
---

# Upwork follow-up

Turn the current pipeline and fresh conversations into today's follow-up queue.
The member starts every run. The run makes decisions and drafts, but sends
nothing.

## Start with current evidence

Read `references/follow-ups.md`. Read `data/sync.json` and run
`python3 code/pipeline.py summary`.

If today's sync is missing or any relevant thread is older than 24 hours, follow
`.claude/commands/sync.md` once before reviewing. Use the project-local
`upwork-mcp` skill for those calls. Never poll or read every historical room.

Review jobs in `replied`, `offer` and `won`. An `applied` proposal without a room
cannot receive a message, so leave it waiting without a task, reminder or draft.

## Decide from the conversation

For each job, read the pipeline record and the full saved thread oldest first.
Use the status, `awaiting_reply_from`, last meaningful message, explicit dates,
client engagement and consecutive messages from the member. Apply the lane,
cadence and stop conditions in `references/follow-ups.md`.

Maximum steps are ceilings. Choose fewer when the thread is weak, the ask is
already stale, the client moved the conversation elsewhere or another message
would add no reason to answer.

For each active sequence, write the decision only through:

`python3 code/pipeline.py follow-up <id> plan --lane <lane> --due <date> --reason "<conversation-based reason>"`

Clear a sequence when a stop condition applies:

`python3 code/pipeline.py follow-up <id> clear --reason "<why>"`

## Draft only what is due

For every sendable lead due today or earlier, use the project-local
`upwork-copy` skill and follow `.claude/commands/reply.md`. Save two drafts to
`jobs/<id>/replies.json` and run `python3 code/replies.py check <id>`.

Each follow-up adds one new reason to answer: a useful observation, a narrowed
decision, a relevant next step or a graceful close. A pure "just checking in"
message is not a draft.

Write `follow-ups.md` with three short sections: `Do today`, `Coming up` and
`Parked`. Put the decision and reason before supporting detail. Link each due
job to its cockpit page. Keep the list to active or recently parked items.

## Report

Use the repository's completion report. Lead with the number due now and name
the strongest opportunity. Say that every draft still needs the member's Send
click. Explain that a confirmed Send automatically advances or completes the
active sequence. Never tell the member to mark a sent follow-up manually. End
with the exact Upwork call count.

## Self-improvement

When the member corrects a cadence decision or a follow-up wins a reply, ask
whether to keep the lesson. If yes, add the dated observation to
`context/follow-up-learnings.md`; change `references/follow-ups.md` only after two
independent examples support the same default.
