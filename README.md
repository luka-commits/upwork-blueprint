# Upwork Blueprint

Win work on Upwork with Claude Code. Your profile, your job search, your applications and your pipeline, in one folder.

The full product goal and review standard are in [VISION.md](VISION.md).

## Quick start

Before you clone: `/about-me` runs on a Claude plan alone. Every Upwork command
needs the free Upwork connector. Details are in
[Requirements](#requirements) and [What it costs to run](#what-it-costs-to-run).

1. Clone it anywhere on your computer:
   `git clone https://github.com/luka-commits/upwork-blueprint.git`
2. Open a terminal in the folder and run `./setup.sh` once. It creates your own
   files and `.env`
3. Follow [Connect Upwork](#connect-upwork), then run `/about-me`. It asks about
   your background once; later commands write from those answers

Skipping setup still works: each command walks you through its missing tools.

## Connect Upwork

This works the same in the Claude Code extension for VS Code and in the terminal.

1. Open this folder in Claude Code and approve the project's `upwork` server when it
   shows "Pending approval" (type `/mcp` to see the list).
2. In `/mcp` choose upwork, then Authenticate, and finish the login in the browser.
3. The Upwork tools appear in the same conversation. If a command still says they are
   missing, start a new conversation (VS Code) or restart `claude` (terminal).

Upwork added as a connector at claude.ai/customize/connectors on your subscription also
shows up in `/mcp`. We only verified the project's `upwork` server above; a connector's
tool names may differ.

The shared allow rules apply after you accept the workspace trust dialog.

What Claude Code reads during a command, including Upwork responses and your
`context/` files, is sent to Anthropic as part of the conversation, as in any
Claude Code session. `RESEARCH.md` is background reading; no command uses it.

## The path (run it in this order, it mirrors the course)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `/about-me` | Your work history, your offer, your terms and every result you can prove |
| 2 | `/profile` | Writes your profile from your facts and top examples, and puts it live after one yes |
| 3 | `/find-jobs` | Ten leads a day worth applying to, scored against what you sell, straight into your cockpit |
| 4 | `/proposal` | The one-pager for your Loom, plus the cover letter and screening answers you submit with your Loom |
| 5 | `/brief` | Your morning: what changed on Upwork, where every lead stands, and the messages that are due |
| 6 | `/call-prep` | Before a sales call: what the call has to settle, the client's business, the person and their market, every fact linked, plus what is worth preparing |
| 7 | `/sales-call-proposal` | Turns your sales call into the proposal you send, and says whether it is ready to start a project on |
| 8 | `/onboarding` | Turns a started contract into the handover brief and the onboarding. Run it again after delivery to record what came out of it |

/about-me also works before connecting or creating a public Upwork profile. Run it
first: every later command writes from it, and `/find-jobs` on an empty `me.md`
has nothing to score leads against.

One helper: `/dashboard` shows your leads with the next command to copy. A lead you
will not apply to leaves the list with `/find-jobs skip <job id> <reason>`, which
searches nothing, costs no Connects and keeps the reason the next search learns
from.

## Requirements

- macOS or Linux. On Windows, use WSL; native Windows is unsupported.
- [Claude Code](https://claude.com/claude-code) and an Upwork freelancer account
- Python 3.10 or newer: `python3 -m pip install -r requirements.txt`.
  If pip refuses because the system Python is managed,
  make a virtual environment first: `python3 -m venv .venv && source .venv/bin/activate`
  Activate it with `source .venv/bin/activate` in every new terminal before `claude`.
- [Node.js](https://nodejs.org) 20.19+ (20.x) or 22.12+ for the cockpit
- Optional: Claude's Google Drive and Gmail connectors. `/about-me` then looks there,
  and in your Documents, Downloads and Desktop, for old CVs, results and client
  messages on its own. Read only; Claude Code still asks before it opens a file
  outside this folder, and saying no just skips that source.

`./setup.sh` and `python3 code/tools_status.py` list what each command still needs.
Upwork commands need the connector. /about-me can start
before it is ready.

## What it costs to run

| Item | Cost |
|------|------|
| Claude Code | a paid Claude plan that includes Claude Code, or API billing |
| Upwork applications | About 70 Connects/day for ten applications; the actual job costs vary and /find-jobs counts them |
| Optional image API | Usage billed separately; paid images require your yes after the cost is shown |

The keys and bills are yours. `KIE_AI_API_KEY` generates images; you can instead
use an image model you already have. `/call-prep` uses `APIFY_API_TOKEN` for review and
ad pulls (at most $0.50 and $0.10 each, only on your pick) and a free `PAGESPEED_API_KEY`.
Details are in `.env.example`.

## Updating

Run `git pull`, then `./setup.sh` again. Activate `.venv` first if you use it.

## What appears in your folder

Everything below is yours and gitignored, so `git pull` never touches it.

- `context/me.md` - who you are and what you can back up
- `context/samples/` - one sample one-pager and its 45-second script per branch,
  for the Loom you record once
- `profile.md` - the profile to paste, written against what is live today
- `data/jobs.json` - your pipeline, written only by `code/pipeline.py`
- `jobs/<id>/` - one folder per job: the pitch page, the application,
  the call transcript, the proposal and its PDF, the threads and the drafts
- `clients/<slug>/` - a won job: the brief, the inputs, the work, what you delivered

## What this will never do

It never submits a proposal, never buys Connects, and never runs on its own in
the background. It prepares the pitch page and the application; you record the
Loom, paste its link and submit on Upwork yourself, because an application spends
Connects and is a bid.

A reply to a client is the one thing it can put into the thread for you, and only
one message at a time, with the full text in front of you and your yes on that
one message. No answer leaves the draft for you to send by hand, which is also
what happens if anything about the send looks wrong. The details are in
[references/upwork.md](references/upwork.md).

One question about this is open, and you should know it before you run
anything. Upwork's own connector guidance asks you to check with their support
before scoring results with a model and before storing connector output. This
Blueprint does both: `/find-jobs` scores postings, and `prune` expires cached
job fields in `data/jobs.json` after 24 hours and saved chats in
`jobs/<id>/thread.json` after 90 days, so your follow-ups and feedback can learn
from them. Upwork's published rule is 24 hours for all of it; to follow it to
the letter, set `KEEP_CHAT_HOURS=24` in `.env`. Nobody here has asked
Upwork yet. The reasoning and the source are in
[RESEARCH.md](RESEARCH.md#what-upwork-says-about-automation).

Stuck? Open an issue on the repository, or ask in the community you got this
from. Include what you ran and what it printed; both are usually enough.

Three things in here are not ours. The tool logos in `templates/pitch/logos/`
come from Simple Icons under CC0; brand marks stay their owners' property and
only name a tool a client already runs. The diagram look in
`templates/pitch/diagram.js` follows the design system of diagram-design by
Cathryn Lavery, MIT licence, with no code copied from it. Everything else is the author's: it ships to members to use in their
own freelancing, not to republish or resell.
