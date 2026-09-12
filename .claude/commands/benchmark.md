---
description: Finds three strong visible Upwork profiles in your profession, measures them, and turns the comparison into targets for your own profile.
argument-hint: "[profession, if it differs from your profile title]"
---

# /benchmark

What three strong visible profiles in the member's profession do, measured, so
`/profile` writes to a comparison rather than taste. This is a candidate sample,
not a ranking of all freelancers or proof that their profile format caused
their earnings.

Read first: [references/profile-formula.md](../../references/profile-formula.md) and the profile sections of [references/upwork-mcp.md](../../references/upwork-mcp.md).

**Profession:** $ARGUMENTS. Empty means: take it from your profile title and skills (`data/profile.json`, written by `/audit`), else from `context/me.md`. Say the search phrase you picked in one line and go on. Only when neither exists, ask for it.

## Step 0 · Files and connector

Run `python3 code/workspace.py`, then `list_accounts`. No Upwork tools: walk the member through connecting exactly as `/audit` Step 0 does, and stop.

## Step 1 · Find candidates, best source first

1. **A client account is connected** (`list_accounts` shows a Client org, and `find_freelancers` is available): `find_freelancers` action `search` with the profession as `query` or `skills`, `job_success_min` 90, `earnings_min` 10000, up to 10 results. Skip every boosted result, it is a paid ad placement. Take the `profile_key` of the rest.
2. **Otherwise, a web search** for the profession on `upwork.com/freelancers` (for example `upwork.com/freelancers GoHighLevel expert Top Rated`), limited to upwork.com. Keep only URLs with a key, `upwork.com/freelancers/~0...`; a name-only URL cannot be read. Up to eight candidates. Fewer than four: one more search in other words.
3. **Still fewer than three:** ask the member for three profile links from Upwork's talent search, and say that this is the only thing you need from them.

## Step 2 · Read them, one at a time

`get_profile` action `get` with each `profile_key`, one call per candidate, never more than eight. Save each response exactly as returned to `data/benchmark/<profile_key>.json`.

## Step 3 · Rank and pick three

Run `python3 code/benchmark.py rank data/benchmark/*.json`. The order is badge, then earnings, then reviews, then jobs. Take the top three and name them in one line. A candidate with no badge and under $10,000 earned only makes the three when nothing better was found, and the report says so.

## Step 4 · Measure

Run `python3 code/benchmark.py measure <the three files> --you data/profile.json data/highlights.json --json`. Leave out `--you` when `/audit` has not run yet.

The script sets the targets. Never adjust a number by hand.

## Step 5 · Judge what the numbers cannot

Read the three overviews and titles yourself and find:

- **What all three do that the member does not.** Opening, proof order, structure, the ask at the end, how the title is built. Name the pattern, not the person.
- **What none of the three does.** The gap nobody in this profession fills: a
  specific niche, relevant verified proof, a clear process or a sharper scope
  boundary. This is where the member can stand apart without inventing a claim
  or guarantee.
- **What looks strong but is claimed, not shown.** A profile that calls itself "Top Rated Plus" in its overview while its badge says Top Rated is a warning, not a model.

## Step 6 · Write benchmark.md

First three lines, then stop:

```
# Benchmark · GoHighLevel automation

Measured Saturday 12 September 2026 · the best 3 of 6 profiles a web search found, not a ranking of all of Upwork
**Next:** run /profile, it writes your profile to these targets.
```

Then `# Targets`, one line per target, each with its range and where the member stands:

```
**Title length:** 55 to 83 characters · you: 67, on target
```

Then `# What all three do that you don't`, then `# The gap none of them fills`, each a short list. Then one block per profile:

```
## Profile 1 · Haider S. · Top Rated · $100K+ earned

**Measured:** Saturday 12 September 2026 · 130 reviews · 220 jobs · $50 an hour
**Title:** four blocks split by |, tools first
**Opens with:** the client's outcome, no number
**Ends with:** an invitation to describe what is broken
```

- **Describe in your own words.** Quote at most five words from anyone's profile: their text is Upwork content and may not be kept past a day.
- No tables. Numbers always with their unit in words.

Then run `python3 code/benchmark.py check benchmark.md`. Exit 1 means it is not done.

## Step 7 · Close

Run `python3 code/benchmark.py prune`. Completion report as CLAUDE.md defines it, link [benchmark.md](../../benchmark.md), next step `/profile`. End with the Upwork call count: one per candidate read, plus the search if a client account ran it.
