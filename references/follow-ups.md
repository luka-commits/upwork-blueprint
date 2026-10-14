# Follow-up rules

What: the sales follow-up engine `/brief` runs every time the member starts it.
Basis: the cadence is a product decision of 8 October 2026; the rest is reasoned
from one imported conversation (12 September 2026).

The point is to make the next step easy for the client, never to maximize message
count. The code keeps the cadence; Claude reads the conversation and may stop it or
move a date when the thread gives a reason.

## The funnel

Every lead sits on the same path, and its stage decides the next message:

| Stage | Next step | The draft |
|---|---|---|
| client wrote (`replied`) | get a call | propose a call: two concrete times or one question that leads there |
| call booked (`call`, `call_at` ahead) | hold the call | nothing until the call, unless the client asks |
| call held (`call`) | the proposal | without `jobs/<id>/proposal.md`: `/sales-call-proposal <id>`; with it: the proposal reminder |
| proposal sent (`call` or `offer`) | the decision | one question that makes deciding smaller (a start date, a first milestone) |
| won | the handover | `/onboarding <id>`; no sales follow-up |

## Reply now

When the client wrote last (`awaiting_reply_from` is `you`), answer today. A reply is
not a follow-up and starts no sequence. It always outranks scheduled follow-ups.

## The cadence

After the member's message to a client who has not answered:

1. **Follow-up 1** three calendar days after that message.
2. **Follow-up 2** seven calendar days after follow-up 1.
3. **Cold.** No answer after follow-up 2: the lead is marked cold (`cold_since`) and
   keeps its stage. Never Lost on its own; Lost is always the member's call.
4. **Reactivation offer** thirty days after follow-up 2: `/brief` asks once whether to
   send one message with a fresh reason. A no, or one more message without an answer,
   parks the lead until the client writes.

Any client message stops the sequence and warms a cold lead; the next unanswered
member message starts a fresh one. Messages sent the same day count as one.
`code/sync.py` starts each sequence on its own when the member wrote last; a sequence
that was stopped or ran out restarts only after the client writes.

## Off the cadence

Claude judges every lead from its thread and may set an earlier or later date with a
reason (`plan --due <date> --reason "..."`) when:

- the client named a date ("back on the 12th"): follow up the day after it;
- a promise was missed (theirs or the member's): the next day, not the cadence;
- a question the client asked was left open: answer it now;
- the client went quiet after a call and the proposal: the follow-up is the proposal
  reminder, one question about it, never a generic nudge.

Stop at once (`clear --reason "..."`) after an explicit no, a request for no more
contact, evidence another freelancer was hired, or an agreed move to another channel.

## Applied, lost, skipped and new

An `applied` proposal has no room until the client writes, so it gets no follow-up.
After 14 full days without a reply `/brief` lists it as stale and asks about Lost.
`new`, `skipped` and `lost` get nothing, unless the client named timing or budget as
the reason to wait and gave a date: then one check on that date.

## What a follow-up says

One short message, one clear question or step, no pressure, written as the member and
grounded in the thread. Each one adds a reason to answer: a narrower decision, a
useful observation, the next concrete step. "Just checking in" is never a draft, and
neither is guilt ("I haven't heard back"). Follow-up 2 offers an easy out ("if the
timing has moved, just say so and I'll stop here").

## The commands

- `python3 code/pipeline.py follow-up <id> plan --lane active` starts the cadence from
  the saved thread (sync does this on its own).
- `... plan --lane active --due <date> --reason "..."` sets a date off the cadence.
- `... sent [--on YYYY-MM-DD]` records a follow-up that actually went out; sync also
  sees it in the thread. The sequence advances on arrival, never on the draft.
- `... clear --reason "..."` stops it; the lead stays where it is.

## Self-improvement

When the member corrects a decision or a follow-up wins a reply, ask whether to keep
the lesson; if yes, `python3 code/pipeline.py note <id> "<dated observation>"`. Change
the cadence only after two independent examples support the same change.
