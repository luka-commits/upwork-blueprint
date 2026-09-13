# Upwork Blueprint

Win work on Upwork with Claude Code. Your profile, your job search, your applications and your pipeline, in one folder.

The full product goal and review standard are in [VISION.md](VISION.md).

## Quick start

1. Download this folder (or clone it) anywhere on your computer
2. Open a terminal in the folder and run `claude`
3. Type `/audit`. It scores your Upwork profile in a few minutes

There is no setup step. Each command walks you through exactly what it needs, the first time you run it.

## The path (run it in this order, it mirrors the course)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `/audit` | Scores your Upwork profile and lists what to fix first |
| 2 | `/benchmark` | Measures three strong visible profiles in your profession and what they do |
| 3 | `/profile` | Writes your optimal profile, ready to paste into Upwork |
| 4 | `/find-jobs` | Finds and scores the jobs worth your Connects, straight into your cockpit |
| 5 | `/pitch-page`, `/loom-review` | A one-page pitch site and Loom, with an optional transcript-based recording check |
| 6 | `/apply` | After the Pitch page and Loom video: cover letter, answers and bid, ready for you to submit on Upwork |
| 7 | `/inbox`, `/reply`, `/follow-up` | Client messages, reply drafts and the morning follow-up queue |
| 8 | `/call-prep`, `/call-review` | Prepares the sales decision and records what the call actually agreed |
| 9 | `/proposal` | Builds a scoped offer from approved commercial terms for you to send |
| 10 | `/won` | Turns a started Upwork contract into a checked client project |
| 11 | `/delivery` | Builds verified updates, handover and an earned review request |

For a local business in conversation, `/lead-magnet` builds a private
three-part SEO audit from live Firecrawl, Apify and DataForSEO evidence. The
cockpit asks for the business website and location before any paid call starts.

Any time: `/status` shows the local funnel and next move, `/cockpit` opens jobs,
clients and tasks in the browser, and `/sync` brings them up to date with Upwork
(replies, offers, contracts).

The table is the product path. A stage is available only when its file exists in
`.claude/commands/`; unfinished stages are not silently improvised.

## Requirements

- [Claude Code](https://claude.com/claude-code) installed
- An Upwork freelancer account
- The official Upwork connector. `/audit` walks you through connecting it the first time
- Python 3, and [Node.js](https://nodejs.org) (the LTS version) for the cockpit

## What this will never do

It never submits a proposal, never buys Connects, and never runs on its own in
the background. It prepares the application and opens the Upwork job; you review
the fields and click Submit there. Replies still need your approval of the exact
text. The sender freezes that text for one attempt; if confirmation is unclear,
it blocks another send until you check the Upwork conversation. The details are
in [references/upwork-rules.md](references/upwork-rules.md).

Stuck? Post in the community. The Help board answers same-day.
