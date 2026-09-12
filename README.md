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
| 2 | `/benchmark` | Finds the three best-earning profiles in your profession and measures what they do |
| 3 | `/profile` | Writes your optimal profile, ready to paste into Upwork |
| 4 | `/find-jobs` | Finds and scores the jobs worth your Connects, straight into your cockpit |
| 5 | `/pitch-page` | A one-page pitch site for one job, the thing that makes a client stop scrolling |
| 6 | `/apply` | After the Pitch page and Loom video: cover letter, answers and bid, ready for you to submit on Upwork |
| 7 | `/inbox`, `/reply`, `/follow-up` | Client messages, reply drafts and the morning follow-up queue |
| 8 | `/status` | Where everything stands, plus your post for the community sprint |
| 9 | `/proposal` | The offer you send after the sales call |
| 10 | `/won` | A won job becomes a project |

Any time: `/cockpit` opens your jobs, clients and tasks in the browser, and `/sync` brings them up to date with Upwork (replies, offers, contracts).

## Requirements

- [Claude Code](https://claude.com/claude-code) installed
- An Upwork freelancer account
- The official Upwork connector. `/audit` walks you through connecting it the first time
- Python 3, and [Node.js](https://nodejs.org) (the LTS version) for the cockpit

## What this will never do

It never submits a proposal, never buys Connects, and never runs on its own in the background. It prepares the application and opens the Upwork job; you review the fields and click Submit there. Replies still need your approval of the exact text. The details are in [references/upwork-rules.md](references/upwork-rules.md).

Stuck? Post in the community. The Help board answers same-day.
