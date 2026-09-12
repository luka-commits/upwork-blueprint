---
description: Opens the cockpit, your job list, clients, tasks and runs in the browser, with buttons that run the commands.
---

# /cockpit

Start it in the background and hand over the link:

1. Run `python3 code/cockpit.py --no-open` in the background. The first start installs the page (Node.js needed, about a minute) and every update rebuilds it once (about a minute); after that it starts in seconds. If port 4321 is taken, use `--port 4322`. If it says Node.js is missing, tell the member to install the LTS version from nodejs.org and open a new terminal.
2. Wait until it prints "Cockpit running", then open `http://127.0.0.1:4321/` for the member (on macOS `open`, on Windows `start`, on Linux `xdg-open`), and give the link as one clickable line.
3. Say in one sentence what they see: jobs by score, clients, what is due today, and buttons that start the same commands they could type. Nothing on that page sends anything to a client.

It runs only on this computer. Closing the terminal or Ctrl+C stops it.
