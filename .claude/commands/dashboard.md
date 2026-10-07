---
description: Opens the cockpit: your leads as a list or board with the next command to copy into Claude Code, plus an Analytics tab with today's applications and the funnel. It never runs a command and sends nothing.
---

# /dashboard

Open with a two-line ROADMAP: check for an existing cockpit, start it if needed,
then open it. The cockpit never runs a command. First start may need Node.js and a short install/build.

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
