---
name: lead-magnet
description: Builds the Pocket CEO local SEO audit for an active Upwork conversation from live website, Google profile, search and map evidence. Creates a local report and never sends or publishes it.
---

# Lead magnet

Build the same three-part SEO audit used by Pocket CEO: how the business is
found in Local Maps, how its Google Business Profile builds trust, and how its
website turns attention into an enquiry. The output is a private local report
for an existing Upwork conversation. It contains no price, external contact
route, calendar or unsupported claim.

## Run

Read `references/report-contract.md` and
`references/measurement-benchmarks.md`, then run:

```bash
python3 .claude/skills/lead-magnet/scripts/build.py <job-id>
```

The job must be In conversation or Offer and have a saved business website.
The cockpit saves that source through `code/pipeline.py lead-magnet-source`.

The engine uses the member's own keys from `.env`: Firecrawl for the rendered
website, Apify for the exact public Google profile, and DataForSEO for search,
competitors and the 25-point Local Maps grid. PageSpeed is used when configured;
otherwise local Lighthouse must be installed. These calls cost money. The
button click starts one run; never retry a failed paid pull automatically.

On the first run, install missing local packages with
`python3 -m pip install -r .claude/skills/lead-magnet/requirements.txt`, followed
by `python3 -m playwright install chromium`.
Never install anything or change credentials during an active paid run.

The report remains at `jobs/<id>/lead-magnet.html`. Open and review it locally.
Never publish it, add it to a message or send it from this skill. A public link
needs a separately approved host and the same pre-contract contact-details gate
as a pitch page.

## Evidence rules

Every score and sentence comes from the files produced in the same run. A
missing source stays visibly missing and leaves its score denominator. Never
turn a failed pull into a zero, choose between multiple business locations, or
infer the client's company from the Upwork job title.

## Self-improvement

When the member corrects or praises a report, ask whether the change should be
permanent. If yes, update `references/report-contract.md` for report decisions
or the relevant deterministic script for measurement logic. Save no client
example in the shipped skill.
