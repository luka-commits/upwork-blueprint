---
description: Everything about you, once: your work history, what you can do and every result you can prove. Every other command reads it.
argument-hint: "[a CV file, a LinkedIn or portfolio URL, or focus: background | offer | terms | voice | proof]"
---

# /about-me

The first command, run once the Upwork connector works and before any client-facing text. It fills `context/me.md`, which every later command writes from. Nothing is public or sent. Follow `references/copy.md` for how to ask. Read [references/profile.md](../../references/profile.md) first (fact order, what must be on the table before a profile can be written, starting from zero).

**Goal.** Learn the career (what they did, for whom, how long) and the skill (what they can do today, on which tools), then lay the base: one person, one problem, one kind of client, a price, proof. Drop questions that serve neither; follow answers that open a door to either.

**Slots.** The title needs a position (the role a client types, then who it is for); the first 250 characters of the overview an outcome or hard number; each portfolio title its own number; the video script up to three proofs; `/find-jobs` the branch, its services and the tool names. A loose answer leaves a slot `/profile` can only fill with adjectives.

**Input:** $ARGUMENTS. A CV path or URL is material (Step 1). A focus value (background | offer | terms | voice | proof) runs only that block and rewrites only its part of the files. Anything else gets the list and a question.

## How this sounds

An interview, not a form. Open each block by saying what it is for and roughly how long it takes, then ask one question; the answer steers the next. Name back what you heard in a line, ask the one thing left open, move on. A block answered fully is finished.

- **At most three exchanges per block.** Then take what exists, say what stayed open, go on.
- **Never ask what an answer already gave.** Confirm it in half a line.
- **Batch the independent questions of a block** into one message; keep dependent ones apart.

## Has this already run?

Run `python3 code/workspace.py`, then `python3 code/context_check.py --status`. Its first word decides, before anything is said to the member.

**untouched**: run Step 0, then the four blocks.

**partial** or **complete**: do not interview again. Say what stands, in their words, in under ten lines (what they are hired for, services with prices, count of verified proof entries). List what is open, ask which they want to fill now, and wait. A focus argument skips the question and goes to that block.

## Step 0 · The connector, then what already exists

Call `list_accounts`. With no answer, walk the member through connecting the connector as CLAUDE.md says and wait; nothing below runs until it answers. Mention no other tools. Run `./setup.sh` quietly (safe any time, never overwrites).

1. Read `context/me.md`. A line reading "not answered yet"
   is an open question, anything else is an answer to confirm, not to ask again.
2. **Read the live profile.** `get_profile` action `get` into `data/profile.json`, `get_profile` action `list_highlights` into `data/highlights.json`, `list_contracts` action `search` on closed contracts (what clients hired them for). `/profile` reuses these files for a day.

   No profile or a nearly empty one (no title and overview, or a title and a few lines) is a normal start: say so in one line and go to Step 1.

   Otherwise say what is there in a few lines, ask what changed, and settle each profile-vs-CV difference here, one line each: education, language level, timezone. Every overview claim with a figure goes into the proof section as the member's own claim (pending) and stays usable in the profile; ask nothing about it.

   **Nothing in it is proof.** Claims from their own profile are recorded as "self-authored Upwork profile, <date>" and become verified only when the member confirms them with somewhere to check. A contract title proves a hire, never a number.

3. **Job Success Score and intro video** are not in these responses. Step 3 handles them; leave unknown values open.

## Step 1 · Background, the whole working life

**Offer first, then wait for the yes.** The first message is one question with four answers: paste the text of a CV, old portfolio page or LinkedIn profile; name a file; say yes and you look through their computer for CVs, portfolios and similar files; or say yes to their Google Drive and Gmail, which you search last (below). Until they answer, open nothing outside this repository (no listing, globbing or grepping). After a yes, or a scope like "my Documents", search it, list what you found by name only, and read only what they confirm.

A URL: fetch once; LinkedIn and login pages return nothing, so ask for the paste. Never invent an employer, title or year.

List back one line per job and ask only what is missing. Everything a CV claims is the member's wording: a fact with source and date, never verified proof.

Open the block and say why: a profession outside freelancing is usually a new profile's strongest asset.

If a CV was read, list its jobs back for a yes or no and ask only about gaps; otherwise ask: **1. Every job you have held**, with years and what you did. No filter. Follow up on gaps, then ask only what the answer left out: 2. what you were good at, in their words; 3. education, certificates and languages with the year; 4. what you built or delivered for someone, paid or not, on or off Upwork.

Then say in two lines which parts transfer to the work they want and which are only biography.

### Google Drive and Gmail, the last source

Reasoned, not measured. Both hold years of junk: old drafts, other people's documents, newsletters, threads the member was only copied on. So they fill gaps and never correct anything.

- **Only after their yes, and only when the Google connector answers.** Without it, say in one line that Drive and Gmail can be connected in Claude's connector settings, and carry on.
- **Last in line.** Read the member's answers, the live profile and every CV or file they gave first. Then search only for what is still open: a missing employer or year here, a number or a client's own words for a project in Step 4.
- **Search for the gap, never browse.** A few searches, each naming the thing: a client, a project, "CV", "case study", "report", "testimonial". List the hits by name and date and read only what the member confirms.
- **Read only.** Search and open. Never send, draft, reply, label, share, move or delete anything.
- **It loses every conflict.** Where a file or email disagrees with what the member said, their profile or the CV they handed over, the other source stands. Mention the difference in one line only when a number or a year depends on it.
- **Everything from it is pending**, recorded as "Google Drive, <file name>, <date>" or "Gmail, <subject>, <date>". It becomes verified only when the member confirms it is theirs and still true; the file or email is then where it can be checked. A document in their Drive is not proof they wrote it.
- **Take the member's own facts, leave the rest.** Nothing about another person and no private detail beyond the result itself goes into `context/me.md`.

## Step 2 · The offer

One choice, one exchange.

1. **Offer the five branches** from `templates/profile/lanes.md` as our recommendation, not a menu: five branches with steady Upwork demand, each with a community course (say "branches", not "lanes"). Show each with its services; ask which they can deliver today and which they could grow into. Take picks as given and write the branch, its services and its Tools line into `me.md` yourself, and its `Search:` line as a track under "Job search tracks" (`- Theme: term · term`). Never narrow within a branch or audit what they left out; ask nothing about deliverables, tools or prices. If none fits, they name another service (point 3). Say the first ten applications test the choice.
2. **Say back in one line**: one branch is decided, two or three leaning (profile leads with the strongest, search covers all), none open (keep the search wide). Let them correct it; write their word, never a narrower service they did not name.
3. **Another expertise, only when clear** (the member names one, or the CV clearly shows one no branch covers): add it as custom (no template, no course, harder to sell) and ask once what the client ends up with and which tool it runs on, since `/find-jobs` searches on those. Check demand with `find_jobs` search only, rows only, call budget stated first: postings of the last 7 days, median price and proposal counts with n and today's date. Flag low demand, let them decide, never block; a no stays a no. A clear strength inside a branch gets one line and a question whether to lead with it. Propose no niche.
4. **Industries, a preference only.** Infer fitting ones from the CV and past work, say them in one line, ask for one or two; picking none for the start is fine. Write `**Industries you want to work with:**` in `context/me.md` (none: "none yet"); `/find-jobs` adds those words to its search. Never ask what they will not do.

## Step 3 · Terms and voice

Often one exchange. Not asked here: the hourly rate (`/profile` settles it after seeing market prices), the applications per day (ten until the member writes another number into `**Applications per day:**`) and the smallest project. Mention that once.

1. **Timezone and the hours** they answer messages.
2. **Voice**: the default is an approachable, professional sales expert who makes the next decision easy. Ask only about deviations; take the rest from how they write in this conversation.
3. **Only when the live read found a profile:** its public URL into `**Public Upwork profile URL:**` and the Job Success Score. A new member gets no Job Success Score, URL or video question.

## Step 4 · Proof, and go after the numbers
The profile lives or dies here: a hard number in the first 250 characters beats any adjective, and nobody volunteers numbers. Ask for them per project, not once in general.

**Walk every project, job or build from Step 1 up this ladder, per project; stop at the first rung that yields something real:**

1. **Money.** Revenue earned, cost cut, deal closed; how much, over what period.
2. **Time.** Hours a week saved, or how long it took before and after.
3. **Volume.** Leads, bookings, tickets, members, no-shows, followers: count before and after.
4. **Scale.** People, locations, products or clients it ran for, and for how long.
5. **The client's own words.** A review, message or recommendation, and where it sits.

When an exact figure is gone, take the range the member is sure of, with its source. "Roughly 8 hours a week, from the client's weekly report" is proof; "significant time savings" is nothing.

Write each result as: Built or Delivered [what] for [kind of company], achieving [result with number] in [timeframe].

Every entry carries **where it can be checked**, the date and a status:

- **verified** when the member gives a clear number or outcome and says where it
  can be checked, in their own words ("my records", "the client"), or an Upwork
  aggregate carries it. Take a clear figure as given: ask once for the place,
  accept any answer, never ask twice, and never hold a claim back because the
  place is vague.
- **pending** for estimates and anything vague. A pending claim with a concrete figure may appear as the member's own claim; one without a figure stays out.

**Nothing on the ladder?** With their yes from Step 1, search Drive and Gmail for that project first, under the rules of the last source. Then help: look together for a system built for the current job, an unpaid build for a friend, a study or course project with a result, volunteer work, or a process improved at work. Record what it proves as pending with its source. If still empty, write "Nothing recorded yet" and move on; `/profile` then leads with the offer and background.

Never write or round up a number the member did not give; an invented number fails at the first client call.

## Step 5 · Write the file

Keep the starter's shape, replace every "not answered yet" you have an answer for, leave the rest. At the top: what it is, the date in words, the one next action. No tables, raw JSON or ids. Add the background as its own section: one block per job with the years and one line on what transfers (`/proposal` reads it for postings in an industry the member has worked in).

## Step 6 · The gate

Run `python3 code/context_check.py`. It counts what is open: unanswered starter lines, proof without a status, verified without a place to check. Nothing here is a requirement: no CV, numbers or reviews is a normal start, and the list is the to-do, not a wall. Fix what an answer exists for, leave the rest, say which stay open. Never answer for the member.

## Step 7 · Report

Before the completion report, show the member what is now in their files, in their own words, so a wrong line is visible.

**On record as:** the one thing they are hired for, each service. **What you can prove:** every proof entry, verified and pending apart, strongest first; say which are pending and what would verify them. **Where it lives:** [context/me.md](../../context/me.md), read by every later command; name any other file this run created or changed and say it is the member's own, never touched by `git pull`.

Then run `python3 code/context_page.py --open`: it renders [context/overview.html](../../context/overview.html) (what they sell, how they work, proof verified and pending, gaps marked) and opens it. Say it can be rebuilt with the same command.

Then the completion report as CLAUDE.md defines it: how many questions stayed
open and which single answer would be worth the most. Next step: `/profile`, which
writes your profile.
End with `Upwork calls: N`: the account check, the profile, its highlights and the
closed contracts, plus one search per custom direction checked.
