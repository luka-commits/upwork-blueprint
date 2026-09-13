---
description: Finds the Upwork jobs worth your Connects right now, scores them against your finished profile, and puts the best into your pipeline and cockpit.
argument-hint: "[focus: recommended | tracks | recheck]"
---

# /find-jobs

Fresh jobs are useful because the member can decide before spending Connects;
whether applying earlier improves win rate is a practitioner hypothesis, not a
measured rule in this repository. This looks at what was posted since the last
run from two directions: Upwork's recommendations and the member's search
themes. Code counts client, budget and freshness signals; Claude judges fit.
Runs only when the member runs it.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md), the jobs sections of [references/upwork-mcp.md](../../references/upwork-mcp.md), `context/me.md` and `context/proof.md`.

## Step 0 · Files, connector, window

Run `python3 code/workspace.py` and `python3 code/pipeline.py prune`, then `list_accounts` (walk through connecting as `/audit` Step 0 does if the tools are missing). Then `python3 code/jobs.py window`: the hours to look back, at least 10, stretched to cover the gap since the newest saved lead, capped at 72 hours.

## Step 1 · Search, two directions

Save each response's `jobs` list to `data/search/<name>.json` as `{"jobs": [...]}`, every job with its fields as returned. The file name becomes the job's "found via", which is how weak tracks get noticed later.

1. **Upwork's recommendations:** when the connector exposes it, use the
   documented but untested `find_jobs` action `smart_search`, `mode`
   `most_recent`, `days_posted` the window in days rounded up and
   `verified_payment_only` true. The tool description calls this Upwork's
   profile recommendations and gives it a real date filter. Page with
   `next_cursor` while `hasMore`, at most 4 pages. Save as
   `recommended-1.json`, `recommended-2.json` and so on. If the action or
   documented response shape is absent, report that evidence gap and continue
   with search themes rather than guessing.
2. **Your search themes:** run `python3 code/jobs.py rules`. Its `themes`
   are the member's personal configuration from `context/me.md`. Each theme
   groups useful variations and tool names into one semantic query. For every
   theme, call `find_jobs` action `search`, `query` the emitted `query`, `sort`
   `recency`, and `verified_payment_only` true. Page with `cursor` while
   `hasNextPage` and the page's newest job is still inside the window, at most
   2 pages. Save as `query-<slug>.json`, using the emitted `slug`. Never split
   the terms into separate calls: the grouped query exists to cover variants
   without wasting calls.

   If there are no themes yet, propose three to six from the member's services,
   profile skills and proof. Use `Theme: term · variant · tool` lines, write
   them under "Job search tracks" in `context/me.md`, and say so in one line.
   Do not add a service merely because a tool exists; the member must actually
   want that work.

Default to broad themes and score after retrieval. Do not add a proposal-count
or budget filter unless `context/me.md` records that boundary as a member choice;
filters remove jobs before anyone scores them.

## Step 2 · Count

Run `python3 code/jobs.py candidates data/search/*.json --window-hours <window>`. It drops what you already applied to, unverified clients and anything outside the window, merges duplicates across searches, skips jobs already in your pipeline, and prints each candidate with its client, budget, competition and points for trust, deal and recency.

## Step 3 · Judge niche fit

Run `python3 code/jobs.py lessons` first: the member's past decisions, including
the reasons saved through **Not a fit** in the cockpit. Use relevant reasons to
calibrate fit and explain their effect in the candidate's rationale. A bare
"not a fit" is not evidence of a particular budget, niche or tool preference.
Treat one rejection as specific to that job; repeated reasons can guide ranking,
but never invent a blanket exclusion or silently rewrite `context/me.md`. Only
explicit member boundaries there may remove jobs before scoring. Automated
"cannot apply" skips describe eligibility, not the member's taste.

Also read `performance` from `python3 code/jobs.py rules`. It groups saved leads,
applications, conversations, wins and disqualifications by search theme. Prefer
themes that have produced conversations or wins when choosing which borderline
jobs to open. Repeated disqualifications with the same reason lower fit for the
same pattern. These are downstream outcomes for saved leads, not true search
precision: raw Upwork retrieval totals are deliberately deleted after each run.
Never disable or rewrite a theme without the member's explicit decision.

Then give every candidate a niche fit from 0 to 40 against `context/me.md` and `context/proof.md`:

- **35 to 40:** the center of what you sell, and your proof covers it.
- **25 to 34:** clearly yours, one step off the center.
- **20 to 24:** you could do it, your proof barely covers it.
- **Under 20:** not your work. Never logged, whatever the client or budget.

Signals that raise fit: a local service business, local-search work, Google
Business Profile, a conversion-focused local website, or lead-response work in
GoHighLevel. Your exact tools and verified proof raise confidence, but never turn
an unrelated job into a fit. Traps that look like a match and are not: bought
backlinks, ranking guarantees, generic design without local-search or conversion
scope, open-ended account-manager roles, a full-time employee disguised as a
contract, and anything the member ruled out in `context/me.md`.

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

Now judge that job's fit again from the full posting, including every mandatory
requirement. Replace its entry in `data/fit.json`, then run
`python3 code/jobs.py reassess <id>`. This replaces the snippet-based score and
closes the lead when the full posting falls below the same fit or score gate.
Never let the snippet score survive as the final assessment for an opened job.

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
2. Keep the complete scored list in the cockpit. The chat report names the count
   scoring 70 or more and, if useful, the best lead with one reason. No separate
   result list or repeated recap. None over 70: say so plainly.
3. Use the compact completion report from `CLAUDE.md`. Next step: open the cockpit,
   or `/pitch-page <id>` for the best lead. End with the actual Upwork call count,
   never an estimated range.
