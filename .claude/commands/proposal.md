---
description: Prepares the one-pager for the member's Loom and writes the application text for one job: cover letter and screening answers.
argument-hint: "<job id> [more job ids] | <job id> own | <job id> submitted | samples [branch]"
---

# /proposal

**`/proposal <id>`** sends the branch's sample Loom: the letter carries its URL from
`## Sample Looms` in `context/me.md`, and Step 2 is skipped. **`/proposal <id> own`**, or a
branch without a sample, builds the tailored one-pager in Step 2 for a personal Loom and
keeps `[LOOM LINK]` in the letter.

**`/proposal <id> submitted`:** only run `python3 code/pipeline.py set <id> applied`
and report `Upwork calls: 0`, then stop before any other step. It records the member's submission.

**Several ids run one after another.** The repetition is the command's, never the member's yes.

**Running `/proposal` is the member's decision to apply.** Fit was settled in `/find-jobs`:
never ask whether to apply, never offer to skip, never stop on an unmet requirement.

Follow `references/copy.md` for every line the client reads. The member described in
`context/me.md` is the sender. The member records the Loom themselves and shows the one-pager on screen;
this command prepares that page and writes the application text.

Read first: [references/upwork.md](../../references/upwork.md) (hard constraint 8, no contact route before a contract), `context/me.md`.

## `/proposal samples` · one Loom per branch, recorded once

Runs no Upwork call. One sample per name on `**Branches you picked:**` in `context/me.md`,
at most five; with no branch recorded, send the member to `/about-me` and stop.
`/proposal samples <branch>` redoes one. The branch picks its template from the Step 2
table, saved as `context/samples/<template name>.html` (`seo`, `google-ads`, `website`,
`gohighlevel`, `automations`).

1. **The page, for no client in particular.** Build it as Step 2 does, with the template's
   own graph for GoHighLevel and Automations, then fill every blank from `context/me.md`.
   The h1 is the outcome this branch's usual client wants, no row carries an `asked` tag,
   and nothing names a client, a place or a posting. `python3 code/pitch_check.py page
   <file>` must pass, then open it.
2. **The script, 45 seconds.** Save it to `context/samples/<template name>.md` in a fenced
   `text` block and print it in full in the chat. It follows the intro video's flow
   (`/profile`, Video script) with the page on screen: your name and who you help, then
   down the page phase by phase with one proof from the evidence sections where it fits,
   then one small invitation to reply here on Upwork. About 100 words, warm and plain,
   numbers as said aloud, nothing that fits only one job, never invented proof. Close
   with "read it aloud once before recording; anything that trips your tongue gets cut".
3. **The member records it** with the page on screen and pastes the share link. Only a
   `loom.com/share/...` or YouTube link counts. Write it to `context/me.md` under
   `## Sample Looms`, one `**<branch>:** <url>` line each, adding the section once if it
   is missing and replacing the line on a redo.

The report names each branch with its sample recorded or still open.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 6 does. Never write from the summary: the requirements and screening questions are in the full posting.

## Step 2 · The one-pager for the Loom

Only for `own` or a branch with no sample. The member shows one page on screen in the Loom. Pick it by branch: the one whose `Tools:` line in `templates/profile/lanes.md` the posting matches, and for a mixed job the branch that carries most of the work. Nothing is published and the letter links nothing.

| Posting is mainly | Template | How it is made |
|---|---|---|
| SEO, local SEO, Google Business Profile | `templates/roadmap/seo.html` | copy and edit |
| Google Ads | `templates/roadmap/google-ads.html` | copy and edit |
| A website, landing page or redesign | `templates/roadmap/website.html` | copy and edit |
| GoHighLevel, CRM, sales funnel | `templates/roadmap/gohighlevel.html` + `templates/pitch/graphs/ghl-funnel.json` | `roadmap_build.py` |
| Automations (Make, Zapier, n8n, AI workflows) | `templates/roadmap/automations.html` + `templates/pitch/graphs/automations.json` | `roadmap_build.py` |

- **SEO, Google Ads, Website:** copy the template to `jobs/<id>/pitch.html` and edit it to this client. The file's own comment lists what to rewrite; these decide whether it lands:
  - **The h1 is the outcome this client asked for, in their words**, never the name of a service.
  - **Tag the rows they named.** A fifth entry on any `ROWS` row is what they asked for, quoted from the posting; it prints as a tag on that row. Tag only what they actually wrote, and delete the placeholder tag.
  - **Add a row for anything they asked for that the plan does not carry.** Keep the page on one screen: if a row is added, merge two.
  - **Plain words.** A client who is not in the trade must understand every row at a glance: "customer list", not "CRM"; "count your leads", not "conversion tracking".
- **GoHighLevel, Automations:** copy the template's graph JSON to `jobs/<id>/pitch-graph.json` and cut it to what the posting needs: labels in the client's words, still 8 to 20 steps, at least two per group, every edge leaving a decision labelled, and `python3 code/graph_sketch.py jobs/<id>/pitch-graph.json` clean (a "FIX" line is a defect). Never invent a fact about their setup: draw a "which CRM? to confirm" node instead. Then run `python3 code/roadmap_build.py templates/roadmap/<page>.html --graph jobs/<id>/pitch-graph.json --out jobs/<id>/pitch.html --title "<title>"` and edit the headline, the one-line lede, the who row and the closing offer in the result.
- **Every page:** fill every blank from `context/me.md`, including the photo (`python3 code/photo.py <photo> --into jobs/<id>/pitch.html`). Then `python3 code/pitch_check.py page jobs/<id>/pitch.html`: no contact detail, no unfilled `<Your name>` or `PUT-YOUR-...`. Open the file in the browser for the member, and say which template and what you changed in one line.

## Step 3 · Application

Use the full posting from Step 1 and `references/copy.md` for
every line the client will read. The member reviews and submits the proposal
on Upwork themselves. Prepare the cover letter, screening answers when the
posting states the questions, for manual submission.

**The first 230 characters decide.** That is all the applicant card shows a client, roughly the first 45 words. Put the outcome and the one relevant proof there, not a greeting or excitement.

### What is true about you and the scope

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against the evidence sections of `context/me.md`. **A requirement your proof does not cover never becomes a claim.** If it is mandatory, ask the member whether they meet it and where that can be checked, one single choice per requirement: met and checkable, met with nothing to point at, not met; the place is typed. Ask these together with every screening question only the member can answer (a YES or NO, a price), in one batch right after reading the full posting. "Not met" is answered honestly in the application, never claimed and never a reason to stop. If it is a preference, name the gap for the member and draft without claiming it. Lead with the strongest relevant proof by tier; never a badge or number the member does not hold.

### Write the letter

Write the letter on the member's own template: five blocks, friendly and plain, no
em-dashes, normally 120 to 180 words and never more than 220. The template comes from
the member's sent letters; keep its order and its small signposts (📽️ 🔗 ❗). Every
`<...>` below is filled from this job's posting and from `context/me.md`, never from memory.

```
Hey, I'm a <the member's real status and role from context/me.md> and can definitely help you <the client's goal, in the client's own words from the posting>.

Here's how I would do it :)
📽️: [LOOM LINK]

<Screening block, only when the posting states questions: see below>

In terms of relevant experience, <one or two sentences of proof from the evidence sections of context/me.md that fit this job, using the problem words of the posting>.

<One sentence on how the member works that answers this client's situation, for example: audit first, simplify, rebuild, document.>

<Only if the member has a portfolio link in context/me.md:>
Websites, funnels etc:
❗<the portfolio link>

Happy to jump on a call to <the one thing to scope for this job>. Looking forward to hearing from you!

All the best, <first name>
```

Fill rules:
- **The opening carries the card.** The first 230 characters are the role plus this client's outcome, with at least one word from the job title.
- **Status, counts and clients** ("Top-Rated", "15+ clients", a named result) are written only if they stand in the evidence sections of `context/me.md`. A count that is missing is left out, not asked for. **The portfolio block is optional**: most members have no link, so without one the two lines are dropped and nothing is asked.
- **The video line.** A sample Loom goes in as its URL, and no line says the video is about
  this client; a personal Loom keeps `[LOOM LINK]` and may say it walks through their plan.
- **No page link.** The Loom is the only extra: the member shows a one-pager on their own screen, and the letter links nothing else.
- **No claim beyond the proof.** A requirement the evidence does not cover is not claimed; name it to the member instead.
- Do not recap the posting, add generic praise or pad. Never add a guarantee, refund,
  free work or delivery date as a sales device.

**Screening questions.** Read the full description for any question the client wants answered (a numbered list, "please answer", "include", "start your reply with") and for questions in Upwork's own question fields. Name each one in the Step 8 report. When the posting wants the answers in the letter itself, insert this block after the video lines, one numbered line per question, each answered in one or two sentences, and where the video covers it, say so in plain words (a timestamp only after the Loom exists):

```
Answers to your screening questions:

1. <topic of the question>: <answer>
2. ...
```

Otherwise put the answers in the separate `# Screening answers` section below, for the member to paste into Upwork's question fields.

Save the cover letter to `jobs/<id>/application.md` in this exact shape so the
cockpit can present it separately:

```markdown
# Cover letter

<the complete letter>

```

When the full posting states screening questions, answer each in one or two
sentences from the posting and verified proof. A mandatory answer without
proof says so plainly and is named in the report. Do not guess questions the posting does not state. Append:

```markdown
# Screening answers

## <the client's exact question>

<one or two sentence answer>
```

### The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

### Manual handoff

Present the letter, any answers and any preferred qualification the
member does not meet. Open the saved job URL on Upwork. The member pastes the
fields, reviews Upwork's final cost and submits the proposal on Upwork
themselves.

**Before they paste, run `python3 code/application_check.py jobs/<id>/application.md
--ready`.** Same gate, one more refusal: the `[LOOM LINK]` placeholder, correct while the
letter is written and wrong the moment it is pasted.

Never mark Applied until the member submits on Upwork, then runs `/proposal <id> submitted`.
That stage rests on their word; `/brief` checks once if no proposal ever shows up.

## Step 4 · Report

Run `python3 code/pipeline.py prune` first, because Step 1 fetched the full job. Then the completion report as CLAUDE.md defines it, with the application linked. Say what the application costs in Connects and what the balance leaves.
Next, with a sample Loom: the ready check runs now, then submit on Upwork and run `/proposal <id> submitted`; `/proposal <id> own` swaps in a personal one. With a personal Loom: record it and return its URL here; replace [LOOM LINK] in the letter, run the ready check again, then submit and run `/proposal <id> submitted`.
End with `Upwork calls: N`.
