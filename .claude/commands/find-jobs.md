---
description: Finds the Upwork jobs worth your Connects right now, scores them against your finished profile, and puts the best into your pipeline and cockpit.
argument-hint: "[focus: recommended | tracks | recheck]"
---

# /find-jobs

Fresh jobs are useful because the member can decide before spending Connects;
whether applying earlier improves win rate is a practitioner hypothesis, not a
measured rule in this repository. This looks at what was posted since the last
run from two directions: Upwork's recommendations and the member's search
tracks. Code counts client, budget and freshness signals; Claude judges fit.
Runs only when the member runs it.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md), the jobs sections of [references/upwork-mcp.md](../../references/upwork-mcp.md), `context/me.md` and `context/proof.md`.

## Step 0 · Files, connector, window

Run `python3 code/workspace.py`, then `list_accounts` (walk through connecting as `/audit` Step 0 does if the tools are missing). Then `python3 code/jobs.py window`: the hours to look back, at least 10, stretched to cover the gap since the last run.

## Step 1 · Search, two directions

Save each response's `jobs` list to `data/search/<name>.json` as `{"jobs": [...]}`, every job with its fields as returned. The file name becomes the job's "found via", which is how weak tracks get noticed later.

1. **Upwork's recommendations:** when the connector exposes it, use the
   documented but untested `find_jobs` action `smart_search`, `mode`
   `most_recent`, `days_posted` the window in days rounded up and
   `verified_payment_only` true. The tool description calls this Upwork's
   profile recommendations and gives it a real date filter. Page with
   `next_cursor` while `hasMore`, at most 5 pages. Save as
   `recommended-1.json`, `recommended-2.json` and so on. If the action or
   documented response shape is absent, report that evidence gap and continue
   with search tracks rather than guessing.
2. **Your tracks:** the lines under "Job search tracks" in `context/me.md`. None there yet: propose three to six from your title, skills and proof (short tool or role words, 1 to 3 words each), write them into `context/me.md`, and say so in one line. For each track: `find_jobs` action `search`, `title` the track, `sort` `recency`, `verified_payment_only` true. Page with `cursor` while `hasNextPage` and the page's newest job is still inside the window, at most 4 pages. Save as `title-<track>.json`.

Default to broad tracks and score after retrieval. Do not add a proposal-count
or budget filter unless `context/me.md` records that boundary as a member choice;
filters remove jobs before anyone scores them.

## Step 2 · Count

Run `python3 code/jobs.py candidates data/search/*.json --window-hours <window>`. It drops what you already applied to, unverified clients and anything outside the window, merges duplicates across searches, skips jobs already in your pipeline, and prints each candidate with its client, budget, competition and points for trust, deal and recency.

## Step 3 · Judge niche fit

Run `python3 code/jobs.py lessons` first: your own past decisions, applied and skipped, with your reasons. They outrank anything below.

Then give every candidate a niche fit from 0 to 40 against `context/me.md` and `context/proof.md`:

- **35 to 40:** the center of what you sell, and your proof covers it.
- **25 to 34:** clearly yours, one step off the center.
- **20 to 24:** you could do it, your proof barely covers it.
- **Under 20:** not your work. Never logged, whatever the client or budget.

Signals that raise fit: a manual, repetitive process described step by step (automation in disguise, even without the word), your exact tools named, your niche named. Traps that look like a match and are not: support or ticket grinding sold as a project ("100% success rate", "hundreds of cases daily"), open-ended account-manager or operator roles instead of a build, a full-time employee disguised as a contract, and anything the member ruled out in `context/me.md`.

Write `data/fit.json`: per job id `{"fit": 0-40, "rationale": "<what the score bets on, in one sentence>", "summary": "<what they want built and the one thing that makes this job distinctive, in two or three concrete sentences>", "trap": "<only when one applies>"}`. The rationale never repeats what the card already shows (budget, client rating). The summary must let a member explain the job without reopening the posting; never reduce a multi-part build to a category label.

## Step 4 · Score and log

Run `python3 code/jobs.py score`. It adds the four parts, logs every job with fit at least 20 and score at least 50 into your pipeline, and prints the ranking.

## Step 5 · Open the best five

For the five highest new jobs, one at a time: `find_jobs` action `get` with the job id. Save to `data/details/<id>.json` these parts of the response, as returned: `connects_cost`, `can_apply`, `activityStat`, `preferred_qualifications`, `client_record` and the full `description`.

After reading that full description, add a `brief` object to the same file:

```json
{
  "outcome": "Two or three concrete sentences: what should exist when the work is done and who uses it.",
  "scope": ["Three to six specific deliverables or workstreams."],
  "requirements": ["Only explicit must-have experience, constraints or application instructions."]
}
```

Use the client's facts, not guesses. Do not mix fit, competition or sales advice into this brief; those have their own places in the cockpit. Then `python3 code/jobs.py detail <id> data/details/<id>.json`. It stores the brief, Connects price, competition, hiring progress and full posting. Only a new job with `can_apply` false is skipped automatically. Hiring progress and unmet preferred Job Success or earnings are advisory: a job may hire several people, and a preference is not an eligibility block. Never fetch details for a whole list: that is the request pattern Upwork flags as scraping.

Write the outcome in plain language: who uses the finished work, what happens
for them, and what changes. Expand shorthand such as "membership automation"
into the actual behavior from the posting. A member should be able to explain
the job aloud after reading it once. Specificity matters more than brevity.
The list uses this outcome, or the saved `summary` when no full brief exists.
Keep both focused on the requested work. Put proof fit, competition and advice
in `rationale`, not in the job description. The sidebar shows that assessment.
To clarify an existing member-written summary, use
`python3 code/pipeline.py describe <id> "Plain-language summary"`.

## Step 6 · Close

1. `python3 code/pipeline.py prune`, then `python3 code/jobs.py clean` (deletes this run's raw responses).
2. Report in the chat, as one block: every job scored 70 or more, with score, title, one line of rationale, Connects price and the link. None over 70: say so plainly, silence is a correct result.
3. Completion report as CLAUDE.md defines it. Next step: open the cockpit, or `/pitch-page <id>` for the best one.
4. The Upwork call count, which on a normal run lands between 8 and 25.
