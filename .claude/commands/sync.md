---
description: Brings the cockpit up to date with Upwork - proposals sent, client replies, offers, contracts - and saves each client thread for the chat window. Reads only, sends nothing.
---

# /sync

Your pipeline says one thing, Upwork may say another: a client replied, an offer came in, a proposal was declined, or you applied from the website. This command reads what Upwork shows now and moves each job to match. It only reads. Nothing goes out.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md) and the proposals and messages parts of [references/upwork-mcp.md](../../references/upwork-mcp.md).

Short roadmap: read proposals, offers, contracts and client threads (about a minute), apply them to the pipeline, report. No stops, nothing needed from you.

## Step 1 · Read what Upwork shows

Use `list_accounts` for the `org_uid` once. Then, all read only:

1. `list_freelancer_proposals` action `list`, once per status `Accepted`, `Offered`, `Hired`, `Declined`, `Withdrawn`, sorted by `MODIFIEDDATETIME` descending, first page only (10 each). "Accepted" means submitted, not that the client said yes.
2. `list_offers` action `list_mine`, first page.
3. `list_contracts` action `search` with `contract_statuses` `ACTIVE`, first page.
4. For every job in `python3 code/pipeline.py list --status applied --limit 0` and `--status replied` and `--status offer` that has a proposal from step 1: `list_freelancer_proposals` action `get_room` with its proposal id. No room means the client has not written yet; move on. A room: `get_messages` action `list_messages`, newest 30 messages. Take `awaiting_reply_from` from the room card (`get_messages` action `list_rooms` once, limit 50, covers them all).

Keep it that narrow: one page per list, threads only for jobs already in the pipeline. Reading every room in the account would be the background-polling pattern Upwork suspends for.

## Step 2 · Apply

Write one JSON object as the docstring of `code/sync.py` describes (proposals with `job_id`, `title`, `url`, `status`; offers with `state`; contracts with `status`; threads with `job_id`, `room_id`, `awaiting_reply_from` and the messages as `from` client or me, `name`, `at`, `text`, oldest first), then:

`python3 code/sync.py apply --file -`

It moves jobs only forward (a declined proposal ends as lost), adds proposals sent outside the cockpit, saves each thread for the cockpit's chat window, turns a client waiting on you into a follow-up due today, and records the time of this sync. Then `python3 code/pipeline.py prune`.

## Step 3 · Report

Completion report as CLAUDE.md defines it. Lead with who is waiting for your reply, then what moved. The Upwork call count.
