---
description: Opens the cockpit, your job list, clients, tasks and runs in the browser, with buttons that run the commands.
---

# /cockpit

Open with a two-line ROADMAP: check for an existing cockpit, start it if needed,
then open it. First start may need Node.js and a short install/build.

1. Check whether this repo's cockpit is already running. Reuse it; never start
   another copy or build while it runs. An update needs a restart, but only after
   checking that no command run is active. An occupied port alone does not prove
   this cockpit owns it.
2. Otherwise run `python3 code/cockpit.py --no-open` in the background. The first
   start installs the page and builds it; later source updates rebuild once.
   If an unrelated app owns the default port, select a free port with `--port`.
   If Node.js is missing, ask the member to install its LTS version from
   nodejs.org and open a new terminal.
3. Wait for readiness, then open the exact URL printed after "Cockpit running"
   (on macOS `open`, on Windows `start`, on Linux `xdg-open`). Never substitute
   the default port for the selected port or open a failed launch.

End with the compact completion report from `CLAUDE.md`, including the clickable
URL and Upwork calls: 0. Opening the cockpit sends nothing. Its Send button can
send the exact reply the member approves; proposals remain manual on Upwork.

It runs only on this computer. Closing the terminal or Ctrl+C stops it.
