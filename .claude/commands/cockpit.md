---
description: Opens the cockpit, your job inbox, pipeline and follow-ups in the browser, with buttons that run the commands.
---

# /cockpit

Start it in the background and hand over the link:

1. Run `python3 code/cockpit.py --no-open` in the background. If port 4321 is taken, use `--port 4322`.
2. Open `http://127.0.0.1:4321/` for the member (on macOS `open`, on Windows `start`, on Linux `xdg-open`), and give the link as one clickable line.
3. Say in one sentence what they see: new jobs by score, the pipeline, what is due today. Buttons start the same commands they could type, and nothing on that page sends anything to a client.

It runs only on this computer. Closing the terminal or Ctrl+C stops it.
