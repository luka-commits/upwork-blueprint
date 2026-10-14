---
description: "Opens your leads as a list or board and Analytics as one scorecard along the funnel, with the next command to copy. It sends nothing."
argument-hint: "[no arguments]"
---

# /dashboard

## ROADMAP

WHAT HAPPENS: check for this cockpit, start it if needed and open its exact URL; usually under a minute, longer for the first install/build.
I NEED FROM YOU: install Node.js if missing; no input otherwise.
WHAT MIGHT GO WRONG: a busy port, missing Node.js or a failed build can block opening; missing saved evidence leaves results unknown.

Analytics shows won value and forecast above one scorecard grouped top, middle and bottom.
Result rows are Reply rate, Call rate, Show-up rate and Win rate, with their stages below.
Every row uses last 28 days vs previous 28 days; the held-to-proposal step appears in
"Proposal within 30 min of call end" over all fitting held calls. Funnel Score appears
in This week. Read `presentation.scorecard`, `funnel_score` and `coverage.missing` from
saved snapshots; never compute a replacement in the command.

1. Check whether this repo's cockpit is already running. Reuse it, unless the
   repo changed since it started (a `git pull` or an edit under `website/`): then
   stop it and start it again, or it keeps showing the old build. Never start a
   second copy. An occupied port alone does not prove this cockpit owns it.
2. Otherwise run `python3 code/cockpit.py --no-open` in the background. The first
   start installs the page and builds it; later source updates rebuild once.
   If an unrelated app owns the default port, select a free port with `--port`.
   If Node.js is missing, ask the member to install its LTS version from
   nodejs.org and open a new terminal.
3. Wait for readiness, then open the exact URL printed after "Cockpit running"
   (on macOS `open`, on Linux and WSL `xdg-open`). Never substitute
   the default port for the selected port or open a failed launch.

End with the compact completion report from `CLAUDE.md`, including the clickable
URL and Upwork calls: 0. Opening the cockpit sends nothing and it writes
nothing: stages change through `/brief` or in Claude Code. Everything else is a
command or a text to copy.

It runs only on this computer. Closing the terminal or Ctrl+C stops it.

## Missing sources

For each absent or unreadable source, end the findings with "What I couldn't check":
name the source, the result or review it blocks and the exact way to supply it below.
Keep that result unknown, never zero or an estimate. Continue only work supported by
available evidence; use DRAFT or HELD for partial work and BLOCKED when no next step is
possible. Never claim a check passed, a source was empty or an action completed without
its evidence. For any other required local source, name its exact repository path
and blocked step, then ask for that file at that path or readable source text here.
For a missing script or reference, restore that exact file from the repository;
do not replace its writer or validator. Follow `references/copy.md` for member copy.

- Missing Node.js: install its LTS version from nodejs.org, open a new terminal and rerun `/dashboard`; launching is blocked.
- Missing or unreadable analytics snapshot, lead state or source coverage: name the exact file or source reported by `code/cockpit.py`; run `/analytics` for snapshots or `/brief` for Upwork state. For transcript, sent copy, meetings or contracts, show the saved `coverage.missing` source, blocked result and `how_to_supply` unchanged. Unknown results stay unknown; an open page alone does not prove complete data.

## Completion report

For every exit, use under 90 words: COMPLETE only when all applicable checks passed,
DRAFT or HELD when work exists but a gate remains, or BLOCKED when the member must
supply the next input. Include Built, Checked (the decisive evidence) and Still needed
(one action and its owner), omitting empty sections. Name each remaining source gap.
End with `Upwork calls: N`, counting actual connector calls, including failed calls.
