---
name: upwork-mcp
description: Uses the official Upwork connector inside this Blueprint for searches, syncs, profiles, proposals, messages, offers and contracts, with minimal calls and write gates.
---

# Upwork MCP

Choose and execute the smallest safe connector route for the requested Upwork
operation. This skill is project-local and depends only on files in this repo.

## Before the first call

Read `references/upwork-rules.md` and the relevant section of
`references/upwork-mcp.md`. Read the matching `.claude/commands/<name>.md` when a
command owns the workflow. State the planned call budget before calling Upwork.

Use fresh local state first. A cached response less than 24 hours old can answer
the same question without another call. Never treat an empty status-filtered
proposal response as proof that nothing exists.

## Choose the narrow route

- Account id: `list_accounts` once, and only when another call needs `org_uid`.
- Job discovery: `find_jobs search` or `smart_search`; page only until the stated
  time window or enough candidates are covered.
- Full job facts: `find_jobs get` for one opened or shortlisted job, never a list.
- Profile: `get_profile`; use `list_highlights` only when portfolio or certificates
  matter.
- Pipeline state: proposal, offer and contract list calls once per required first
  page. Use `get_room` only for pipeline jobs that can have a client reply.
- Messages: `list_rooms` once for waiting state, then `list_messages` only for the
  rooms being reviewed.

Stop when the requested fact is known. Do not broaden a search to make an empty
result look productive. Report any connector behavior that is still untested as
untested.

## Gate writes

Every write needs approval for the exact action and content. Profile previews
remain unconfirmed until the member explicitly approves them. Proposal previews
are never confirmed by this Blueprint: the member reviews the prepared fields
and submits the proposal on Upwork themselves.

Messages use only the cockpit's dedicated `send-reply` run. The server freezes
the approved text in `jobs/<id>/outbox.json`; the run sends it once, reads the
same room once and accepts only an exact returned text match. No other workflow
calls `send_message`.

Write pipeline state only through `python3 code/pipeline.py`. After the operation,
run `python3 code/pipeline.py prune` and report the exact Upwork call count.
