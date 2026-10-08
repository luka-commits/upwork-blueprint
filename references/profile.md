# The profile: what to measure, and what to write

Everything `/profile` needs: the checks that score a live profile, then the rules that write the new
one, including how proof is ranked. Directives only; the evidence, and everything that is knowledge rather than a lever, sits in
`RESEARCH.md`. Article numbers cite `support.upwork.com/hc/en-us/articles/`, read 26 September 2026.
Adjacent: [upwork.md](upwork.md), [jobs.md](jobs.md), [copy.md](copy.md).

# Part 1 · Measure

## Completeness, the one lever Upwork admits to

A complete profile ranks better in Upwork search. That is the only ranking claim this system makes,
and 100% is a precondition for Rising Talent and Top Rated. Published percentages (211063188).
**Mandatory half, 50% together:** photo, overview, one employment entry, one skill tag. **Optional:**

- portfolio, 5% each, up to 20%
- further employment entries, 10% each, up to 20%
- education, 10% each, up to 20%
- further skill tags, 10%
- profile video, 10%
- one linked account, 10%
- certification, 5% each, up to 10%
- one other experience, 5%

Report every missing field **with its percentage, cheapest first**: a linked account is ten points for
one click, a video ten for an afternoon. A member with no Upwork contract still reaches 100% with four
portfolio items, two employment and two education entries, a linked account, one other experience and
the video.

## The filters a client can close

Each is a gate, and an empty one is a filter failed silently, not untidiness. Score all six: **English
level** (basic to native), **languages** with their proficiency, **timezone and location** (there is a
US-only filter), **availability** in hours per week, **categories**, **hourly rate**. A wrong timezone
makes every reply look late, and a client can also filter **for** freelancers with no earnings, the
one documented way a beginner is easier to find.

**How the text is matched:** a boolean match against the profile text, where AND, OR and NOT work only
in capitals. **"Title search" matches the profile title alone**, so a title missing the client's words
drops out of that search completely, so a position title still carries the searchable role noun. Categories and skills are ANDed filters: an empty slot is a
search never appeared in.

## The field limits, and where Upwork contradicts itself

- **Skills:** "up to 15" (360016252373) against "up to 20" (211060318); `set_skills` documents 20.
- **Categories:** "up to four" (360016252373) against up to 10 elsewhere.
- **Title:** 70 characters, from `update_title` and a real title cut at exactly 70; articles silent.
- **Portfolio:** title 70, role 100, description 600, 5 skill tags, images 1000 by 750 (360016144974).
- **Read the real cap in the live editor and claim no number from memory.** Editor beats this file.

## Harvest the keywords, never guess them

Every job `find_jobs` returns carries Upwork's own `skills` array: the client's vocabulary in Upwork's
exact spelling. Count the names across ten to thirty current postings in the lane; the top of that
list is the skill set and the title vocabulary. **The skill is called HighLevel, not GoHighLevel**,
exactly what a guessed list gets wrong. Use all three kinds of word, the tools the client runs, the
role titles they hire for and the problem words they use instead of a solution.

## Check every claim against the aggregate

**A badge named in an overview is not evidence.** Every claim carries its own evidence or it does not
get written: check each one against the connector's aggregate in `data/profile.json`, judge the real
badge and the real counts rather than the sentence, and never write what the member cannot back from
the evidence sections of `context/me.md`. A client checks this in two seconds. **Not levers, so do
not score them:** response rate, activity, hourly rate, rotation through results, paid placement.

## When there is no Upwork history yet

A client sees the **photo, title, rate and Job Success Score** before opening anything, so without a
JSS the other three carry the whole decision. These lanes are technical, where few postings are open
to a beginner: say that out loud rather than implying volume fixes it. Experience outside Upwork buys
no standing here, so background belongs in the copy, never in a claim about reputation. With no
verified result, the draft leads with the offer and the background, and names the gap.

# Part 2 · Write

## What has to be on the table before you write

**Buyer and offer:** target industry, buyer role, problem, service outcome, and
the tools the member genuinely uses. **Proof:** two or three comparable finished
projects with role, deliverable, result, period and where the evidence lives,
with missing metrics marked unknown. **Commercial fit:** scope, availability and
a rate built from the member's own work.

**Draft order:** title, then the overview (hook, three results, how you work, close),
then skills, portfolio titles and the factual fields. An unmeasured outcome is
described by what the system does, without inventing a number, and a placeholder is
never published as a claim.

**When sources disagree**, this order settles it: the member's own verified
evidence for claims about the member, current Upwork policy for conduct, and the
account's live interface for what that account can actually do. Community advice
and another member's outcome are ideas to test, never rules. A market report
describes its own sample and period and nothing more.

## Rank the proof

**Front-load the strongest proof the member holds.** The hook and the first bullet come from the
highest tier with an entry, then down the list. This is the house ranking, reasoned rather than
measured here, and it is internal: never show a member a tier or its letter.

- **S, the closers:** video testimonials · detailed case studies with hard proof · Top Rated · a
  100% Job Success Score · $100,000 or more earned on Upwork
- **A, strong support:** Top 1% for a skill · featured in major press · 100 or more reviews · 100
  or more projects · spoken at events
- **B, outcome numbers:** hours saved · client revenue earned · named big-brand work · work for an
  8-figure company, or a named large employer with its public size · a business of their own with
  its numbers · a budget or team they were responsible for · people helped
- **C, nice to have:** certifications · years of experience · awards and promotions · written
  recommendations · an online following · niche-specific systems built

`/about-me` asks for every one of these in its proof interview, so a missing tier means the member
answered none, not that nobody asked. A first profile with nothing above B or C is normal: lead with
the strongest entry there is, then the offer. **A tier never excuses a claim:** every line still
needs its entry in the evidence sections, a company's size is said about the company and never as
the member's result, and a badge, score or earnings figure is written only as the aggregate in
`data/profile.json` states it.

## Title

Two or three blocks divided by `|`, 55 to 70 characters, never padded to fill. **A description of
what you do plus the keywords clients search**: the first block is the role with its main keyword
(tool or service plus a role noun), the next adds two or three more search terms joined with a
description of who it is for or what the client gets ("Local SEO & Technical Audits for Small
Businesses"). Take the terms from the skills in the fresh postings, never a slogan. No verbs, no
price, no years, no badge words, and never a bare stack of keywords. Orient on the role
models' titles, and place the member as a general expert of the branch, not a niche
role (auditor, local specialist) unless their background brings it.

## Overview

**Only the first 250 or so characters appear in the search results list** (360016252373), so the
opening decides alone. **Open with the client's problem or an outcome**, no greeting, no biography, no
restated job title, and put the **member's own hard number inside those first 250 characters** when one
exists. **No markdown:** Upwork shows asterisks as asterisks. **Results carry numbers, not adjectives**, one line each:
`Built/Delivered [what] for [kind of company], achieving [specific result with number] in [timeframe]`.

**Write prose that flows,** connected sentences and short paragraphs, with no sentence-length rule:
the two top earners of 16 write long prose and lists sat with lower earnings (measured 26 September
2026, correlation only). **Reasoned, not measured:** hook in "you", middle in "I build", close as an
imperative back to "you"; only 2 of 16 profiles do it. **Answer one objection**, usually "it will not break" or "you will own it".
**Close with one imperative plus permission**, such as "send me what you have, even if it is messy".

**What goes into the hook and the three bullets:** the highest tiers the member holds (Rank the
proof), strongest first, with numbers: a video testimonial or detailed case study, leads gained,
revenue earned, hours saved, a named brand. Upwork status the page already shows (badge, Job Success
Score, earnings) goes in only at S tier, never below it.

**Free differentiators**, because almost nobody does them: a price, a disqualification line ("this
is not for you if"), an availability window, a date on a claim, a numeric guarantee. Name one the
member could add truthfully. No word list is banned; the structure above does the work.

## The other fields

- **Skills.** Every slot filled, up to 20, in Upwork's exact spelling: an empty slot is reach given
  away, a wrong spelling a filter failed without knowing. Mark a name not confirmed in a real posting
  with "(check the spelling in Upwork's list)". Soft-skill tags are not editable.
- **Portfolio.** Four items is where completeness caps out. A title carries a number only when the
  evidence sections of `context/me.md` tie it to that project. Linking a real Upwork job notifies that
  client, who has three days to object. **No contact details in the files or the pages they link to.**
- **Intro video.** A YouTube link with monetisation off. Worth 10% of completeness, the only
  documented reason to make one.
- **Hourly rate.** The connector cannot set it. A band from the discipline and the experience level a
  client would pick, moved by verified proof alone, never a country discount, never empty. It anchors
  every later bid, so `context/me.md` carries it.
- **Employment history.** Every relevant role with employer, title and period, including work
  outside freelancing. Each entry says what that employer's customer got.
- **Languages.** Each with its proficiency, plus the English level Upwork asks for separately. A
  client who books a call on "fluent" and meets "conversational" is a refund.
- **The rest, one line each.** Photo: a real portrait, no sunglasses, logos, clipart, group photos or
  edits. Education: optional, never padded. Availability: the hours they can really answer in.
  Categories: the direction from `/about-me`, not the old job. Linked account: the cheapest percentage
  point on the list. Certificates: only what can be checked, never the lead, and Skill Certifications
  are discontinued. Other experiences: volunteer work, a side project, a system built at a
  non-freelance job. **Upwork accepts no new testimonial requests**, so never tell a member to ask.

## What Upwork forbids in a profile

**No means of direct contact anywhere in it:** phone, email, address, a link to a contact form, an
external application system, social handles; a breach is material and permanent suspension possible.
**One account and one freelancer profile** without written permission. **Nothing accurate left out and
nothing invented** about identity, location, business, skills or services. **No other people's work in
the portfolio**, no advertising for services outside Upwork, **no invented relationship** to a company
or person, no subcontracting without the client's consent. No rule bans a guarantee; the Blueprint
avoids them anyway, because a promise the member cannot keep costs the contract.

## Done

Every field carries content or a named reason why it stays empty, and the completeness percentage on
the Find Work page reads 100. A first profile is thin in portfolio and video and strong in title,
overview, skills and employment history, the four a beginner fills on day one. The connector's
title, overview and skills writes are untested previews, so paste-ready text always ships.
