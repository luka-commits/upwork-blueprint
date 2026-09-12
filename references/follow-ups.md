# Follow-up rules

What: a context-based sequence for dormant leads and previous clients.
Measured: 12 September 2026 against the first imported conversation.
Next: run `/follow-up` each morning after opening the cockpit.

The point is to make the next decision easy, not to maximize message count.
Every interval below is a ceiling. Conversation context can shorten a sequence
or stop it, but never extend its maximum.

## Reply now

When `awaiting_reply_from` is `you`, answer today. This is a reply, not a dormant
lead follow-up, and it does not consume a sequence step. A client question,
requested change, call request or offer always outranks scheduled follow-ups.

## Hot lead

Use `hot` when the client asked about a call, price, proposal, start date or
decision, or when an offer is close but one concrete item blocks it.

Allow up to three follow-ups. After a sent message, wait 1, then 3, then 7
business days. The first should close the named decision. The second should
reduce scope or answer a likely blocker. The third should close the loop without
guilt or fake urgency.

## Warm lead

Use `warm` after at least two substantive client turns, a reviewed deliverable or
a specific next step without an immediate buying signal.

Allow up to three follow-ups. Wait 2, then 5, then 10 business days. Use the
conversation's open loop. Add a useful observation or make the next choice
smaller. A generic status request does not count as value.

## Light lead

Use `light` after one short client response or weak engagement with no specific
next step.

Allow two follow-ups. Wait 3, then 7 business days. The second is the close. Park
the lead after that unless the client returns.

## Previous client

Use `reactivation` only for a `won` client with a positive relationship and a
real reason to reconnect. An unfinished promise or stated date overrides this
lane and becomes a normal task.

Allow two messages, 30 then 60 business days apart. Lead with a relevant idea,
change or next project based on the completed work. Do not send a vague
"hope you're well" sequence.

## Applied, lost, skipped and new

An `applied` proposal has no room until the client writes. Re-check it on day 3
and day 7, then park it. No Send button means the system is working correctly.

Do not follow up with `new` or `skipped` jobs. A `lost` lead gets one future
check only when the client explicitly named timing or budget as the reason and a
date makes sense. Otherwise it stays closed.

## Context beats the lane

Stop immediately after an explicit no, a request for no more contact, evidence
that another freelancer was hired, or a move to another agreed communication
channel. Do not duplicate the conversation across channels.

Honor a date the client named. Follow up on the next business day after a missed
promise, not according to the generic lane.

Count meaningful client turns, not message bubbles. Three short bubbles sent in
one minute are one turn. Multiple unanswered member messages reduce the next
sequence, never increase it.

## What each message earns

Step one reopens the exact decision. Step two adds a new reason to answer. The
last step gives a clean close. Every message should be understandable without
reading a sales template, grounded in the thread and written as the member.

The first measured thread supports the timing principle, not a universal
conversion claim: a useful delivery follow-up and one later reminder produced a
client reply two days later. The bare "just checking in" message added no value,
so this system excludes that pattern.
