---
description: Builds the Pocket CEO local SEO audit for an active Upwork conversation from live website, profile, search and map evidence.
argument-hint: "<job id>"
---

# /lead-magnet

Use the project-local `lead-magnet` skill. Nothing in this command talks to
Upwork or sends a message. A successful run publishes the checked audit.

ROADMAP

1. Check the saved business website, provider access, balances and Vercel destination.
2. Measure the rendered website, search visibility and 25-point Maps grid.
3. Build, validate, publish and open the audit for review.

This normally takes several minutes. The website, Apify and DataForSEO can fail
or refuse a budget limit. A failed paid pull is held for review and never retried
automatically.

Run `python3 .claude/skills/lead-magnet/scripts/build.py $ARGUMENTS`. Its first
live step is the fail-closed preflight; never bypass it. Then open the public
audit and inspect the complete page. Finish with the compact completion report
from `CLAUDE.md`. Link the public audit, name missing evidence, and end with
`Upwork calls: 0`.
