---
description: "Your weekly Upwork coaching loop: checks last week's goals, measures the funnel, finds this week's focus and agrees one to three commitments with you."
argument-hint: ""
---

# /analytics

## ROADMAP

Refresh evidence, review commitments, measure the funnel and agree this week's goals. First-run preparation may take longer; routine duration is unmeasured. Wait for missing sources, installation approval and goal agreement. Missing evidence or too few finished cases can leave checks unknown; coaching continues. Run on the member's Analytics day. Upwork access is read-only; nothing is sent.

## 1. Prepare and refresh

Claude reads `context/me.md`, [copy](../../references/copy.md), [goal library](../../references/goal-library.md), [coach brief](../../references/coach-brief.md) and [Upwork rules](../../references/upwork.md), then runs:

```bash
python3 code/workspace.py
python3 code/analytics.py last
```

Check `data/sync.json` and `list_accounts`. Use fresh saved state; if sync is absent, future-dated or older than 24 hours at the zoned run time, perform [/brief](brief.md) Steps 1–2 and [capture: brief](../../references/analytics-capture.md#brief), read/sync only. If disconnected, guide README's connection steps and wait for the member. Count every Upwork call.

On the first run, backfill proposals, invitations, contracts, Connects and earnings to the connector's documented limit. Page every proposal status, including Archived, to exhaustion; deduplicate IDs, retain the newest copy and classify its returned status. Preserve verified dates; name the uncovered period. Import absent historical leads through:

```bash
python3 code/pipeline.py add --file -
python3 code/sync.py apply --file -
```

Mark historical imports as imported; preserve existing matched leads and disclose any backfill limitation. Follow the capture hook for proposal insights, viewed observations, invitation dates and ledger evidence. Missing sources remain missing; checked-empty sources are explicit empty lists.

Ask only for reconnection or evidence the tools cannot supply. Code and its errors define accepted inputs; never edit pipeline data directly.

## 2. Recover source evidence and missed weeks

Claude checks missing Loom tooling (`yt-dlp`, `whisper-cli`, `code/loom.py`'s `find_model()`). Show `brew install yt-dlp whisper.cpp` and the script's `MODEL_DOWNLOAD`, or platform-specific instructions; install only after the member agrees. Recover an existing recorded Loom with:

```bash
python3 code/loom.py <id> <recorded-Loom-URL>
```

Obtain calls through [call transcript](../../references/call-transcript.md). A recap proves held, never its absence a no-show. Requested meetings remain requested; preserve sessions and reschedules. Reuse `jobs/<id>/call-review.md`; invoke [/call-review <id>](call-review.md) only for an unreviewed session. Preserve verified session identity, language and completeness; a summary or excerpt cannot support a whole-call review.

Check one registered tracking link with `?check=1`, its redirect and `X-Tracking-Status: check: not logged`, then run:

```bash
python3 code/clicks.py
python3 code/analytics.py compute --catch-up
python3 code/analytics.py compute
```

Register or deploy nothing. A failed check is a source gap, never a human click. Review missed-week previews chronologically and every unresolved goal due through the gap. Current recording appends catch-up history atomically; never record previews separately or invent past agreements. Unreconstructible historical facts remain unknown. Tell the gap as one story, beginning with elapsed time. Explain: "Missed a week? Next time you run /analytics it catches up on everything since your last check-in."

Ask for each unavailable source through its exact recovery route; hold affected claims if code cannot preserve the history.

## 3. Read and review the cases

Claude uses compute's unchanged output for every number, state, focus, period and evidence population. Read leads with:

```bash
python3 code/pipeline.py get <id>
```

Prepare a full evidence inventory first run. Otherwise review at most five focus cases plus urgent exceptions and disclose sampled IDs and unreviewed coverage. Read every reply thread without a call or offer, all cases supporting repeated patterns, and the full mature population for conversion badges.

### Coaching rubrics

Judge from the coach brief, actual sent artifacts, full post and verified thread. For applications, check posted problem, matching proof, screening answers, bid/scope, concision, closing question and Loom when used. Uma reviews use requested interview questions and submitted answers/video. Repair the failed artifact; missing sent copy is unreviewed: "Your sent application is unavailable. Paste it to receive a review." Every correction includes the sent passage/job, missed point, grounded replacement and next-application instruction.

For chats, paginate read-only `get_messages` / `list_messages` to documented exhaustion and read oldest first. Judge the client's question answered, one useful qualifying question, and two concrete Upwork call times when useful. Timing comes from code. Honour stated decisions and agreed steps; count patterns only through code.

The comparable call scan covers: (1) opening/agenda within two minutes; (2) current state; (3) problem and cost; (4) goal/scope; (5) budget before price; (6) decision maker/timeline; (7) distinguishing proof addressing the client's concern; (8) objections invited/handled; (9) agreed next step on Upwork, owner, terms and deadline. Credit sourced information already established; explain inapplicable points. Reuse the full saved review, exact turning quotes, better wording, fix, example, read and next message. If its original scan was not recorded, use `/call-review` to record it without new judgment; otherwise name the writer gap.

Compare sent proposals with the held call's agreement using the original review criteria. Separate stated, observed and unknown loss reasons. Save assessments only through:

```bash
python3 code/pipeline.py note <id> 'analytics job_fit: {"state":"pass","reason":"<quoted judgment>"}'
python3 code/pipeline.py note <id> 'analytics lost_reason: {"kind":"stated","reason":"<verified reason>"}'
python3 code/pipeline.py record <id> --file -
python3 code/analytics.py compute --file -
```

Use actual judgments in tagged notes. Supply evidenced reviews, eligible/completed goal cases, keep/adjust/stop decisions and live source gaps to compute. Keep execution separate from effect; no opportunity means untested. Offer the simpler fallback after two undone weeks. Preserve code's focus; disclose disagreement with supported coaching rather than overwrite it. Print returned instant awards verbatim once; badge failure stays a named gap.

Ask one targeted question only when evidence cannot distinguish an obstacle; request missing sent copy, complete thread or attributed transcript through its capture/source route.

## 4. Write and check the weekly coaching

Claude writes the weekly summary in the fixed order and tone of the coach brief's weekly report section; [report example](../../references/chat-report-example.md) is the approved text. Obtain facts from the final prepared snapshot and check the report against that same snapshot:

```bash
python3 code/analytics.py facts --snapshot <snapshot-file>
python3 code/analytics.py check-report <report-file> --snapshot <snapshot-file>
```

Require check-report PASS before displaying; fix every rejected value, period or unsupported claim. Follow the brief's order; the money and Funnel Score come from code. Carry every item once, with missing sources under **Couldn't check**. Distinguish fixed won value, hourly terms and billed earnings. Name periods, units and k of n; show code's plain sample notes. List each missing source in **Couldn't check** with its exact command. Quote job-linked evidence; label interpretations and counterevidence. Use code's award wording once per new award.

Each early week improves an application, checks use of the prior fix, resolves low activity, or decides what to keep/change. Baseline collection never implies established improvement.

Ask for source gaps or a decision needed to resolve a supported obstacle; recommendations alone do not save goals.

## 5. Preserve the app presentation

Claude carries the saved code presentation into exactly **This week**, **Conversations**, **Achievements**; no separate calculation or speculative content. All disclosures expand inline, with no drawers/dialogs. Evidence opens Leads filtered to exact row IDs across all statuses without opening its drawer; Back restores the same analytics subtab and scroll. Badge links open Achievements at the targeted badge. Call coaching, full reviews and turning moments stay inline; deeper coaching uses `/call-review`.

This week retains progress, focus/goals and the complete top/middle/bottom scorecard. Habit rows show THIS WEEK against the prior four-week average; fewer than three opportunities use the four-week average as the main value with a sample note. Result rates use 28 days versus prior 28 days. Preserve evidence, histories and returned comparisons. Unknown is never zero. Call rate links to stalled replies in Conversations.

Each scorecard row's detail has one **Open these N leads →** button opening Leads filtered to that row's exact IDs, with no embedded lead list. The chart uses actual week labels, faint horizontal ladder bands labelled at right, and value labels above bars without overlap. Accent only the current bar; keep others neutral and fit height to content. The right column has at most three short lines: the count in one sentence, one job-fit finding only when present, and the market reference with a **Source** link rather than a raw URL. Omit Possible range text.

Conversations retains Applications, Chats, Calls and Proposals, actual titles/dates, review markers, criterion charts, supported patterns and full inline reviews. Default to this week, sort by importance, three rows per section plus Show all; criterion selection reveals all affected rows. Absent sent Loom says "No Loom sent" or "Loom requested, not sent"; only a sent Loom missing its transcript needs recovery. Missing sources show their supply route. Achievements retains the badge gallery, targeted badge, rank/progress, score history, current/best commitment streak and goals that worked.

Use `python3 code/analytics.py compute --file -` for presentation. No member question is needed; name code gaps. This command cannot claim measured UI or real-account acceptance.

## 6. Agree goals, record and read back

Claude proposes one to three commitments across stages, one primary focus. Prefer this member's supported improvements, otherwise the goal library; add at most one original commitment. Explain cue, action, fallback and review date. Ask for agreement before saving; dismissal leaves proposals unsaved. Help implement the agreed reply template or call opener without sending.

```bash
python3 code/analytics.py goals add --file -
python3 code/analytics.py compute --file -
python3 code/analytics.py record --file -
python3 code/analytics.py last
python3 code/analytics.py onepager --file <snapshot-file>
python3 code/pipeline.py prune
```

Pass only agreed goals for the current week, then recompute the completed coaching/report object. Preserve returned computed content. After recomputation, recheck the report against that snapshot before display or record. Record once; add `--replace` only when the member requests correction of that week's record. Read back goals/report. Generate the community card through code only, using agreed library IDs and the library's question ID; never handwrite public wording. Money appears only with Share money: yes. Prune and finish with CLAUDE.md's completion report and measured `Upwork calls: N`. Missing agreement or a refused write stays HELD.
