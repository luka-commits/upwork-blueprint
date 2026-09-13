---
description: Builds the Pocket CEO local SEO audit for an active Upwork conversation from live website, profile, search and map evidence.
argument-hint: "<job id>"
---

# /lead-magnet

Use the project-local `lead-magnet` skill. Nothing in this command talks to
Upwork, sends a message or publishes a page.

ROADMAP

1. Check the saved business website, credentials and exact Google profile.
2. Measure the rendered website, search visibility and 25-point Maps grid.
3. Build and open the private audit for review.

This normally takes several minutes. The website, Apify and DataForSEO can fail
or refuse a budget limit. A failed paid pull is held for review and never retried
automatically.

Run `python3 .claude/skills/lead-magnet/scripts/build.py $ARGUMENTS`. Then open
`jobs/$ARGUMENTS/lead-magnet.html` and inspect the complete page. Finish with the
compact completion report from `CLAUDE.md`. Link only the report, name missing
evidence, and end with `Upwork calls: 0`.
