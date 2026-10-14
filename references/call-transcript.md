# Call transcript evidence

Shared acquisition procedure for `/call-review`, `/sales-call-proposal` and
`/analytics`. Read `references/upwork.md` first. A member starts every Upwork
read. State the call budget, respect pacing and count every call; send nothing.

## Upwork first

Use fresh saved evidence first. Match the actual call to its room and session,
using `manage_meetings` read actions `list`, `list_recaps`,
`get_meeting_summary` and `get_full_transcript` only. Read all listing and recap
pages and every transcript offset until the source confirms the end. Preserve
all transcript pages in order. A failed page leaves completeness unknown.

A recap read error is unknown, not an empty recap or a no-show. Persist
`{"recap_state":"unknown","recap_reason":"<actual read error>"}` through
`python3 code/pipeline.py record <id> --file -` and retain it in `/brief` sync
coverage. Use `ok` or `empty` only for a successful recap read. A summary helps
locate the session; it cannot support a call review.

A pending meeting request remains "call asked". Preserve `call_requested_at`
and `call_request` metadata through the writer as `/brief` does; never observe
`call_booked` or change to the call stage from a pending request. Booking time
and scheduled start are different facts. Neither proves the call was held.

Pass all transcript pages as a JSON list to:

```
python3 code/call_stats.py <id> --transcript-json - --source upwork-meeting
```

Add only verified flags: `--call-at <zoned actual start>`,
`--duration-s <seconds>`, `--member "<known member speaker>"`,
`--complete <yes|no>` and `--language <verified-language>`. Never invent a
speaker identity, duration, language or completeness. The script writes
`jobs/<id>/call.md` and records derived stats through the pipeline writer.
If a temporary pages file was used instead of stdin, remove it after success.

## Allowed fallback

Only when no Upwork transcript exists, ask about the member's recorder for
Enterprise clients or calls after a contract started. Read its transcript
through an available API; otherwise accept a file or pasted full transcript.
For other calls, request a file or pasted transcript, never an outside recorder.
Read a supplied path only when the member names it. A failed Upwork read is an
unknown source, not proof that no transcript exists; offer a paste to unblock it.

Preserve every turn as `Speaker: words`, and headers `Member: name`,
`Complete: yes|no`, `Language: label`, `Call at: zoned ISO time` and
`Duration: seconds` only when verified. Never infer labels from turn order or
content. For recorder or pasted transcript pages, the same normalizer accepts
labelled strings or `{speaker, text}` segments; use `--transcript-json -` with
`--source recorder` or `--source member`. For an already normalized `call.md`,
run `python3 code/call_stats.py <id> --source recorder` or `--source member`.
Never give this script notes or a recap as a transcript.

## Missing evidence

A review needs the full transcript, complete speaker labels, verified member
identity and language. Missing, unreadable or partial evidence blocks the
review. Say what is missing, what it blocks and how to supply it: paste the
full labelled transcript, identify the member speaker, supply missing pages or
reconnect Upwork. Do not write feedback from notes or a summary.

Notes may support a proposal when scope and agreement are independently verified.
They never support call scores or a Coach's read. Only after the member confirms
the call took place, with its actual time, may notes support
`python3 code/pipeline.py observe <id> call_held <ISO time> --source member --verified`.
Missing timestamps remain unknown; do not use the scheduled time instead.
