---
description: Refreshes active Upwork conversations, then shows who needs an answer and the exact next action. Reads only and sends nothing.
argument-hint: "[job id | waiting | all]"
---

# /inbox

The working inbox for active proposals and clients. It refreshes only the
conversation scope the member asked for, then puts replies before follow-ups.
It never sends a message.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md), the
proposals and messages sections of
[references/upwork-mcp.md](../../references/upwork-mcp.md).

**Focus:** $ARGUMENTS. Empty means `waiting`. A numeric job id refreshes and
shows only that job. `waiting` refreshes active pipeline conversations and shows
only clients waiting for the member. `all` also shows conversations where the
client has the next move. Anything else: list these three choices and ask.

## ROADMAP

WHAT HAPPENS: check the pipeline, refresh the relevant Upwork room or rooms,
save fresh threads, then rank the next replies. Usually one to two minutes.

I NEED FROM YOU: nothing during the read. Any later send still needs approval of
the exact text in the cockpit.

WHAT MIGHT GO WRONG: an applied proposal has no room until the client writes;
Upwork's proposal status filter is unreliable; a missing job id needs `/sync`.

## Step 1: Files and scope

Run `python3 code/workspace.py`. For a numeric focus, run
`python3 code/pipeline.py get <id>` first and stop if the job is not present.
For `waiting` or `all`, read only jobs in applied, replied, offer and won.

## Step 2: Refresh, read only

Use `list_accounts` once for the freelancer account. Never store the org id.

For a numeric focus:

1. Use `list_freelancer_proposals` action `list`, first page, sorted by
   `MODIFIEDDATETIME` descending. Supply one documented status only if required,
   but inspect each proposal's own status because the filter does not work
   reliably. If the first page is empty, try one other documented status and
   report the connector uncertainty.
2. Find the proposal whose job id matches. If neither attempt contains it, say
   that the first pages did not contain it and route to the job on Upwork;
   absence here proves nothing.
3. Use action `get_room` for that proposal. No room means the client has not
   written and no message can be sent.
4. When a room exists, use `get_messages` action `list_rooms` once for
   `awaiting_reply_from`, then action `list_messages` for that room, newest 30.
5. Save the response with
   `python3 code/threads.py save <id> --file - --room <room id> --awaiting <you|them>`.
   If the client wrote and the current stage is applied, move it forward with
   `python3 code/pipeline.py set <id> replied`. Never move offer or won backward.

For `waiting` or `all`, complete Steps 1 and 2 of
[the sync command](sync.md). That path reads only active pipeline conversations
and writes pipeline changes through `code/pipeline.py`.

Run `python3 code/pipeline.py prune` after the refresh.

## Step 3: Show the inbox

- Numeric focus: `python3 code/funnel.py inbox --job-id <id>`
- `waiting`: `python3 code/funnel.py inbox --waiting`
- `all`: `python3 code/funnel.py inbox`

The local inbox output and cockpit retain the full waiting list. In the chat
report, give the count and the first client needing a reply, not another copy of
the list. A saved thread older than 24 hours is not evidence and its message text
must not be repeated.

## Step 4: Report

Use the completion report from `CLAUDE.md`. The next action is `/reply <id>` for
the first waiting client, or the first dated follow-up when nobody is waiting.
Report the exact Upwork call count. Nothing was sent.
