---
name: lead-magnet
description: Builds and publishes a checked SEO audit for an active Upwork conversation from live website, Google profile, search and map evidence. It never sends the link or a message.
---

# Lead magnet

Build a three-part SEO audit: how the business is found in Local Maps, how its
Google Business Profile builds trust, and how its website turns attention into
an enquiry. The output is a checked report
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

The engine uses the member's own keys from `.env`, with
`~/.config/credentials.env` as the local fallback: Firecrawl for the rendered
website, Apify for the exact public Google profile, and DataForSEO for search,
competitors and the 25-point Local Maps grid. PageSpeed is used when configured;
otherwise local Lighthouse must be installed. These calls cost money. The
button click starts one run; never retry a failed paid pull automatically.

Before the first paid call, the script runs a fail-closed preflight. It verifies
the required credentials, provider access, measurable Firecrawl credits, Apify
monthly-limit headroom, DataForSEO balance, the local browser runtime and the
Vercel destination. An unknown balance or failed connection stops the run.

On the first run, install missing local packages with
`python3 -m pip install -r .claude/skills/lead-magnet/requirements.txt`, followed
by `python3 -m playwright install chromium`.
Never install anything or change credentials during an active paid run.

The report remains at `jobs/<id>/lead-magnet.html` and is published automatically
to the stable URL saved as `lead_magnet_url`. Publication uses the same
pre-contract contact-details gate as a pitch page. It creates the link but never
adds it to a message or sends anything. If publication fails after a successful
build, the next run reuses that exact current report and retries only the free
Vercel step. Changing the saved website or location clears the old URL and
requires a fresh audit.

The renderer uses the bundled source-derived React template. Read
`references/template-source.md` before changing its structure. After any
template edit, rebuild the single-file runtime with:

```bash
cd .claude/skills/lead-magnet/template
npm ci
npm run build
```

For a public pitch-page preview, never reuse a client report. Generate the
fictional current-format example instead:

```bash
python3 .claude/skills/lead-magnet/scripts/demo.py jobs/<id>/lead-magnet-example.html \
  --business "Example [industry]" --service "[client service]" \
  --location "[client market]" --conversion "[desired enquiry action]"
```

The demo uses no paid service, real client or external link. Match its fictional
business, service, market and conversion to the job's real industry. It exists
only so the pitch page can embed the real report experience safely.

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
