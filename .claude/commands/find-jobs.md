---
description: Finds the Upwork jobs worth your Connects right now, scores them against your finished profile, and puts the best into your pipeline and cockpit.
argument-hint: "[focus: recommended | tracks | recheck | skip <job id> <reason>]"
---

# /find-jobs

Looks at what was posted since the last run from two directions: Upwork's recommendations and the member's own search themes. Code counts client, budget and freshness signals; Claude judges fit, out of ten, and that is the score. Runs only when the member runs it.

Read first: [references/upwork.md](../../references/upwork.md) for what is allowed and what the connector gives you, [references/jobs.md](../../references/jobs.md) for where the work comes from and what it pays, `context/me.md`.

## Taking a lead off the list

`skip <job id> <reason>` does only that: it calls no Upwork tool and runs no search. Step 7 asks the same question for the current run's leads; this writes the same record later.

Run `python3 code/pipeline.py get <job id>`. Only a Not applied lead (status
`new`) can be skipped. A lead further along moves through `/brief`, so say that
and stop. Without a reason, ask for one line and wait: a useful reason names the
fact that rules the job out, such as budget, scope, tool or client, never a mood.

Then `python3 code/pipeline.py set <job id> skipped --note "not a fit: <reason>"`.
Keep the prefix. `python3 code/jobs.py rules` counts a reason only when the note
carries it, so a note without it takes the lead off the list and loses the lesson.

Report one line: the job title, the reason as saved, and that the lead left the
cockpit list. End with `Upwork calls: 0`, and do not continue into Step 0.

## Step 0 · Files, connector, window

Run `python3 code/workspace.py`, `python3 code/pipeline.py prune` and `python3 code/pipeline.py reset-search` (yesterday's unused leads expire, with skip reasons kept), then `list_accounts` (if missing, walk the member through connecting as CLAUDE.md says and stop). Then `python3 code/jobs.py window`: the hours since **the last run rather than the last saved lead**, with a two-hour floor and 24-hour ceiling. A first run looks back 24 hours. `jobs.py clean` writes the stamp even when nothing was found, so the run must finish for the next one to narrow.

## Step 0b · Is this the first run, or a run with a direction?

If `python3 code/context_check.py --status` says `untouched`, stop and send the member to `/about-me`.
Look at `context/me.md` under "Job search tracks". **No tracks means the first run**:
it finds which searches are alive instead of hunting the best ten.
Saved tracks mean a later run even before any application. Name the mode in one line.

**The first run explores.** If what the member sells matches a ready-made lane in [references/jobs.md](../../references/jobs.md), offer that lane's terms and let them cut what they cannot deliver. Otherwise build ten to twelve candidate terms from `context/me.md` across the four branches: tools, roles clients hire for, problem words, industries worked in. One lane at a time, never two. One call per term, `limit` 10, `sort` `recency`, and **no window filter**, since the point is density. Measure with Step 3a and report per term its Connects cost, what postings pay against the member's own rate in `context/me.md`, and how many ask for entry level.

Close the first run by saving three to five surviving terms under "Job search tracks" in `context/me.md` as `- Theme: term · term`, with verdicts and dates in prose outside that list. Name the lane the evidence supports, run `python3 code/pipeline.py prune` and `python3 code/jobs.py clean`, report the measured terms and `Upwork calls: N`, name `/find-jobs` next, and stop. With no surviving terms, name `/about-me offer` next.

**Every later run exploits.** It runs the kept tracks, pages the dense ones, applies the
lessons from Step 3b, honours the window from Step 0, and tests at most one new candidate
term per run so a bad guess costs one call. A term that returned nothing twice gets
removed from `context/me.md` with a line saying so.

## Step 1 · Invitations first

Call `list_freelancer_proposals` action `invitations` once. Open invitations are the warmest leads and go to the top of the report. For each one not yet in the pipeline, fetch the job with `find_jobs` action `get`, add it with `python3 code/pipeline.py add --file -` (id, title, url, budget, job_type, client, posted_date, `found_via` set to `invitation`), then store its details as Step 6 does. The member answers on Upwork; this command never accepts or declines. No invitations: say nothing and continue.

## Step 2 · Search, two directions

Save each response's `jobs` list to `data/search/<name>.json` as `{"jobs": [...]}`, every job with its fields as returned. The file name becomes the job's "found via", which is how weak tracks get noticed later.

0. **Show the terms and the limits, and ask, before spending a single call.** List what you are about to search, one line per track with its source: their own file, the catalog in [references/jobs.md](../../references/jobs.md), or a skill name harvested from the last run. Under it, the hard no's as `python3 code/jobs.py rules` reports them, with one recommendation per number for this person, drawn from their file and profile and the tiers in jobs.md, with half a line of why. Then one question: does this fit, what is missing, what goes. Wait for the answer. This is the one gate in this command: a wrong term or limit costs the member a day of leads.

   Save the answers in `context/me.md` as `**Maximum proposals on a job:**` and `**Lowest share of your rate:**`, so the next run reads them instead of asking. Never ask for a smallest project. A limit whose figure is unknown prints as `LIMIT OFF` in the candidate step: name it out loud.

**When the member sells something the catalog does not cover**, build the list with them from the four branches, then harvest Upwork's own wording from one broad search (method in [references/jobs.md](../../references/jobs.md)). Save what they confirm under "Job search tracks" in `context/me.md`.

1. **Upwork's recommendations:** when the connector exposes it, use the documented but untested `find_jobs` action `smart_search`, `mode` `most_recent`, `days_posted` the window in days rounded up and `verified_payment_only` true. Page with `cursor` set to the previous `pageInfo.endCursor` while `pageInfo.hasNextPage` is true, at most 4 pages. Save as `recommended-1.json`, `recommended-2.json` and so on. If the action or documented response shape is absent, report that evidence gap and continue with search themes rather than guessing.
2. **Your search themes:** run `python3 code/jobs.py rules`. Its `themes`
   are the member's personal configuration from `context/me.md`. Each theme
   groups useful variations and tool names into one semantic query. For every
   theme, call `find_jobs` action `search`, `query` the emitted `query`, `sort`
   `recency`, and `verified_payment_only` true. **Page until the window is
   covered**, not to a fixed page count: keep setting `cursor` while
   `hasNextPage` and the page's oldest job is still inside the window, and stop
at the page that crosses it.

   **Send the member's own limits with the query, so the pages that come back are
   pages worth reading.** The search filters are free and server side:
   `proposals_max` for the competition ceiling, `budget_min` for fixed work,
   `rate_min` for hourly, plus `experience_level`, `job_type` and `workload`
   where the member has named a boundary.

**The window decides the page count.** Twelve pages is the runaway stop: report the term as denser than one run can reach and offer to split or narrow it with a filter. Say how many pages a term took, since that is the density measurement. Save as `query-<slug>.json`, using the emitted `slug`. Never split the grouped query into separate calls.

   If there are no themes yet, propose three to six from the member's services,
   profile skills and proof. Use `- Theme: term · variant · tool` lines, each starting with the dash because `jobs.py rules` reads no other line, write
   them under "Job search tracks" in `context/me.md`, and say so in one line.
   Do not add a service merely because a tool exists; the member must actually
   want that work.

3. **The client's own industry.** Search the trade plus the pain, not the tool (a dental practice's no-shows, a gym's leads, a law firm's follow-up). An industry the member has worked in goes first. Save as `industry-<slug>.json`.

4. **The client's own tools, the quiet half.** Search the platforms the member can work with even when the posting never says "automation": Shopify, Salesforce, Monday, ClickUp, Zoho, Pipedrive, Google Calendar, Gmail, Zoom. Propose two or three such tracks from the member's own stack, mark them in `context/me.md` like any theme, and save as `query-<slug>.json` so the funnel shows which branch paid.

Default to broad themes and score after retrieval. Do not add a proposal-count
or budget filter unless `context/me.md` records that boundary as a member choice;
filters remove jobs before anyone scores them.

**Never disqualify a client on a thin signal** (no spending history, low average spend, few reviews; see references/jobs.md). Only the posting's own text fixing a low budget and a deadline together disqualifies. Honest reviews are the one signal worth reading closely.

## Step 3 · Count

Run `python3 code/jobs.py candidates data/search/*.json --window-hours <window>`. It drops what you already applied to, unverified clients and anything outside the window, merges duplicates across searches, skips jobs already in your pipeline, and prints each candidate with its client, budget, competition and points for trust, deal and recency.

## Step 3a · Measure which terms are worth their calls

Run `python3 code/tracks.py measure data/search/*.json`. Per term it reports the hours its ten newest postings span (the density: a live term gives ten in eight hours, a dead one reaches back three weeks), how many state a rate, the median proposal count and how many clients are payment verified. The verdict decides the next run: dense terms get a call and a page every run, steady terms one call, thin terms a weekly look. Say which terms changed category and drop a term that returned nothing twice.

## Step 3b · Apply what your own pipeline has taught

Run `python3 code/learn.py report`. It counts what happened to applied leads by search branch, client country, spending history, job type, requested level and the member's score band.

Two lines work from the first run because they count decisions. **Per search branch**: how many candidates reached the pipeline; a branch that keeps producing and never passes one is a keyword list to drop. **The disagreements**: leads the score let through and the member turned down, with reasons; weigh one of those above ten counted outcomes.

Outcome lessons wait for a sample: below eight applications in a bucket nothing is weighted. Past it, `python3 code/learn.py lessons` writes `data/lessons.json` and **`jobs.py score` applies it**: the reply rate of the track, country and job type moves the score by one point either way at most, named in the record as `lesson` and `lesson_reasons`. Say in the run which lesson moved a lead and which dimension is still too thin.

## Step 4 · Judge niche fit

Run `python3 code/jobs.py lessons` first: the member's past decisions, including
every reason saved with a skip. Use relevant reasons to
calibrate fit and explain their effect in the candidate's rationale. A bare
"not a fit" is not evidence of a particular budget, niche or tool preference.
Treat one rejection as specific to that job; repeated reasons can guide ranking,
but never invent a blanket exclusion or silently rewrite `context/me.md`. Only
explicit member boundaries there may remove jobs before scoring. Automated
"cannot apply" skips describe eligibility, not the member's taste.

Also read `performance` from `python3 code/jobs.py rules`: saved leads, applications, conversations, wins and disqualifications by search theme. Prefer themes that produced conversations or wins when choosing borderline jobs to open; repeated disqualifications with the same reason lower fit for that pattern. Never disable or rewrite a theme without the member's explicit decision.

The member's own history outranks any sentence in `context/me.md`: it is what they did, and the only thing that can tell the score it was wrong.

**Every fit names its comparable case.** The rationale says which past lead this job resembles and how it ended ("like the pet grooming lead that replied"). A rationale that only asserts fit is taste. With no history yet, say so plainly and score against `context/me.md` alone. Three turn-downs with the same reason lower the fit for the fourth job of that pattern, without waiting for permission.
Then give every candidate a fit from 0 to 10 against `context/me.md` and the member's
own history. **The fit is the score**, and there is no second scale: the hard no's
already removed what cannot be applied to, and the deductions only shave.

- **9 or 10:** what the member sells, in the words they would use, for the kind of
  client they serve. One of these is worth the day's first Connects.
- **8:** clearly theirs, one step off the centre. The bulk of a good day.
- **7:** they could do it and would not enjoy it, or the posting is vague about the
  part that matters.
- **6 or less:** not their work. Never logged, whatever the client or the budget pays.

Signals that raise fit come from `context/me.md`: the member's niche, the
clients they serve best and the services they want more of. Their exact tools
and verified proof raise confidence, but never turn an unrelated job into a fit.
Traps that look like a match and are not: ranking or result guarantees, bought
links or reviews, generic work outside the member's niche, open-ended
account-manager roles, a full-time employee disguised as a contract, and
anything the member ruled out in `context/me.md`.

Write `data/fit.json`: per job id `{"fit": 0-10, "rationale": "<what the score bets on, in one sentence>", "summary": "<what they want built and the one thing that makes this job distinctive, in two or three concrete sentences>", "headline": "<who wants what, one sentence of at most 14 words>", "trap": "<only when one applies>"}`. The cockpit list shows the headline whole, so it names the client and the concrete outcome, never a category label. The rationale never repeats what the card already shows (budget, client rating). The summary must let a member explain the job without reopening the posting; never reduce a multi-part build to a category label.

## Step 5 · Score and log

Run `python3 code/jobs.py score`. The score is the fit, minus the deductions the candidate step computed, plus or minus what the member's own outcomes earned that pattern, so a perfect fit with nothing against it scores 100. It logs every job with a fit of at least 6 and a score of at least 7, caps any job you named a trap at 6, and prints each score out of ten with what came off it; deductions and reasons ride along on the record. Everything turned down goes to `data/decisions.jsonl` with the points and the reason, which the next run learns from. Report grades to the member, never the raw points.

## Step 6 · Open the ten you will show

**Open exactly the leads that will reach the member**, one at a time, highest first: the ten of Step 7, plus a replacement for every one the full posting disqualifies, until ten stand or the bench above grade 7 runs out. An unopened lead hides its mandatory opening phrase, screening questions and self-capping budget, which kill an application after the Connects are spent. Ten one-at-a-time calls is not the pattern Upwork flags; fetching the whole candidate pool would be.

For each of them: `find_jobs` action `get` with the job id. Save to `data/details/<id>.json` these parts of the response, as returned: `connects_cost`, `can_apply`, `activityStat`, `preferred_qualifications`, `client_record`, `contractTerms`, `clientCompanyPublic` and the full `description`. The last two carry the experience level, engagement type, client city and timezone that `jobs.py detail` reads.

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

**Name the client's industry first, in the headline and in the first sentence of the outcome**: "A dental practice wants its GoHighLevel CRM cleaned up and automated", never "A business wants...". Take it from the posting (the client's own words, company profile, examples), never infer it from the tool they use. When the posting does not say, write "industry not stated", never a plausible guess; that blank is itself worth seeing.
The list uses this outcome, or the saved `summary` when no full brief exists.
Keep both focused on the requested work. Put proof fit, competition and advice
in `rationale`, not in the job description. The sidebar shows that assessment.
To clarify an existing member-written summary, use
`python3 code/pipeline.py describe <id> "Plain-language summary"`, and for the
list's one-sentence headline `python3 code/pipeline.py headline <id> "<sentence>"`.

## Step 7 · Close

1. `python3 code/pipeline.py prune`, then `python3 code/jobs.py clean` (deletes this run's raw responses).
2. **Show the daily target, and the bench is everything else that passed.** The target
   is ten unless `Applications per day` in `context/me.md` says otherwise. Show that
   many, numbered, each one line: who wants what, the grade, and what applying costs in Connects. Behind them
   stands every other lead that passed the gate, in rank order, which is what
   `python3 code/pipeline.py list` already prints. Open invitations come first, before the ten.
3. Ask once, in one line, which of the leads you showed are a no and why. Take the
   answer in any shape, including none, and record each with
   `python3 code/pipeline.py set <id> skipped --note "not a fit: <reason>"`. Keep the
   prefix, because `python3 code/jobs.py rules` counts a reason only when the note
   carries it. A reason names the fact that rules it out, such as budget, scope, tool
   or client. This is the half of the record that needs a person, so it is asked once,
   here, and never chased. A lead the member rejects later takes the same route through
   `/find-jobs skip <id> <reason>`.
When the member turns one down, name the next one in the same breath, so the list is ten again before they ask, while the bench holds. **The bench floor is the gate itself**: a lead below the gate is never offered as a refill. The bench is good for today only, since tomorrow's window disqualifies it. The complete scored list lives in the cockpit.
4. **Say it when ten is not there.** Fewer than ten at a 7 or better is a result, not a failure to hide: report how many there are and the cause (too few dense tracks, limits too tight, a quiet day, or a member with empty evidence sections, where a direction still two lanes wide scores honest fits at 7 and 8 and the gate eats them). Never pad the ten with leads the score turned down, and never lower the gate to fill a row.
5. **Name the day's Connects bill once.** Ten applications cost what the ten jobs cost,
   measured from each `connects_cost`. Call `get_freelancer_dashboard` action `check`
   once for the Connects balance, and include this call in `Upwork calls: N`. One
line, no advice unless the balance runs out before the ten do.
6. Use the compact completion report from `CLAUDE.md`. Next step: `/proposal <id>` for the first lead on the list, or the cockpit. Every lead shown has its full posting saved. End with `Upwork calls: N`, measured, never an estimated range.
