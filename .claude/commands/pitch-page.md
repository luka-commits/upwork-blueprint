---
description: Builds a one-page pitch site for one job, with a live diagram the client can edit, plus the script for your three to four minute Loom over it.
argument-hint: "<job id>"
---

# /pitch-page

Use the project-local `upwork-copy` skill for the page and Loom script. The
member described in `context/me.md` is the sender.

One page that makes a client stop scrolling: a headline about their job, your walkthrough video, three proofs, their system drawn as a diagram they can drag and edit, the plan in days, and the next step on Upwork. Plus the Loom script you read while you scroll through it.

Read first: [references/upwork-rules.md](../../references/upwork-rules.md) (the section on links before a contract), `context/me.md`, `context/proof.md`.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 5 does. Never build from the summary: the diagram is drawn from the requirements, and the summary does not carry them.

## Step 2 · Which page is this

- **Anonymous client:** the page pitches the build.
- **The company is named in the posting:** the page opens with what you noticed about their situation, from their own words and public site. Research is fine, contact is not. Every observation must be checkable; a wrong one about their own business ends the conversation. Uncertain which company: treat it as anonymous.

## Step 3 · Understand the mechanism

For every tool or delivery discipline the posting names, check
`context/tool-knowledge/<tool>.md`. The shipped workspace already includes
implementation references for GoHighLevel, SEO and Google Ads. Read only the
ones this job uses. If a named system is not covered, research it now with
official docs first, then add the implementation decisions to its file with
sources so the next job does not pay for the same discovery again. A familiar
category is not a reason to skip this: the specific combination is what the
client is paying for.

For SEO, choose the relevant lane from `context/tool-knowledge/seo.md` before
drawing. For Google Ads, put verified conversion measurement before bidding and
keep media spend separate from the implementation fee. These references guide
the mechanism; they never supply proof about the member or facts about the
client.

## Step 4 · Read the posting into a plan

Write down, before drawing: the trigger, the systems they already run, the manual work today, where results must land, the phase two wishes, the constraints. Then five rules: use their words ("your Squarespace form", not "web form"); never invent a fact, draw a "which CRM? to confirm" node instead; mark scope with groups (what ships first, what comes later); every manual step in the posting is a step the diagram takes over; a requirement with its own sentence gets its own node.

Write the graph to `data/pitch-graph-<id>.json`:

- Keep the client-level picture to 6 to 12 nodes. Combine technical internals
  that serve one outcome and explain them in the node note. Avoid more than
  seven linked stages on the main path; branches are easier to read than one
  very long chain.
- `nodes`: `id`, `label` (a few words), `kind` (`source`, `step`, `sink`, `decision`, `datastore`, `service`, `actor`, `note`, `milestone`), `owner` (`you` builds it, `client` already runs it, `thirdparty` outside service), optional `logo` (a file name in `code/pitch/logos/`), optional `note` (two to four plain sentences for a client outside your field; about half the nodes need one).
- `edges`: `from`, `to`, optional `label`, optional `dashed` for later phases.
- `groups`: `label` and `nodes`, one per milestone. Make the first milestone the
  smallest useful result. Give it a date only when dependencies and the member's
  availability support that estimate.

Estimate the member's effort from this same scope, not from the client's budget.
Use a low, likely and high hour case; two to five roadmap milestones whose hours
sum to the likely case; a confidence level; and every assumption that could move
the estimate. Then run:

```
python3 code/pricing.py <id> --hours <low> <likely> <high> \
  --confidence high|medium|low --contract-type fixed|hourly|unknown \
  --milestone "Foundation|hours" --milestone "Build and QA|hours" \
  --assumption "one concrete scope boundary"
```

This is the internal price guide shown in the cockpit. It uses the current
Upwork profile rate and a visible scope-risk buffer. It never becomes the bid,
never appears on the client pitch page and never overrides a client-approved
commercial term.

## Step 5 · Assemble

```
python3 code/pitch/generate.py <id> --hook "..." \
  --fit-point "number|label|context" (three times, numbers only from context/proof.md) \
  --graph data/pitch-graph-<id>.json --tool "..." (repeat) \
  --timeline "Day 1-2|what ships;;Day 3-5|what ships" --budget "..." --kickoff "..." (repeat)
```

- **Timeline:** an estimate based on explicit scope, dependencies and the
  member's real availability. Mark unresolved client inputs. Do not turn tool
  speed into a delivery guarantee.
- **Budget:** an honest frame, no invented price. When the posting gives none, say what the quote depends on.
- **Next step** (`--next-step`) points back to Upwork; the default asks them to send their website or current setup there.
- Optional: `--loom-url` once recorded, `--hero-illustration` (a wide scene of their world with the problem solved, generated, no text in it), `--live-artifact "Label|URL"` for anything actually built, `--proof-link "Label|Detail|URL"` for past work with no contact details on it, `--showcase ...` for a real sample of your work.
- Your YouTube videos appear when `context/videos.json` lists them (`{"channel": url, "videos": [{"id", "title", "thumb"}]}`); the channel page itself must show no email or booking link.

## Step 6 · The Loom script

Write `jobs/<id>/loom-script.md` as the words the member says while scrolling the finished page. Mirror the sections that are actually rendered, in their exact top-to-bottom order. Do not fall back to a generic Loom template and do not speak through a section that the page does not contain.

Use beats for:

1. The hero: their situation and the outcome you understood.
2. Why the member fits, using only proof that is visible on the page and verified in `context/proof.md`.
3. `What I'd build`: follow the diagram's groups and connections in visual order. Explain the useful path instead of reading every node aloud.
4. The proof, sample or background sections that are actually present.
5. `How this would work`: the first milestone, timeline, client inputs and scope boundaries shown on the page.
6. `The next step`: the specific future state you see for this job, then say that the goal is to exceed expectations and become a long-term partner. For jobs tied to a business website, ask them to send the website URL here on Upwork so you can run a useful audit upfront. When a website is irrelevant, ask for the closest existing setup or screenshot instead.

Keep it between 420 and 560 spoken words. Use casual spoken English, contractions and short explanations, like a capable person walking a colleague through an idea. Warm, direct and likeable. One understated joke or self-aware aside is welcome when the job gives you a natural opening, but never force a punchline and never joke at the client's expense. No greetings, generic praise, inflated claims, contact details or em-dashes. End on the Upwork CTA, with nothing after it.

## Step 7 · The gates

- `python3 code/pitch_check.py page jobs/<id>/pitch.html`: no email, phone, booking link, messenger or social profile anywhere on the page, no unfilled placeholder. Upwork suspends accounts for contact details before a contract, and a linked page counts.
- `python3 code/pitch_check.py loom jobs/<id>/loom-script.md`: three to four minutes of words, ending on Upwork.
- Run `python3 code/pitch_capture.py <id>`, read the screenshot path it prints,
  then run `python3 code/pitch_capture.py <id> --clean`. Never call a page done
  unseen. The cleanup removes the temporary screenshot after the visual check.

## Step 8 · Publish the client page

Run `python3 code/pitch_deploy.py <id>`. It deploys only the checked
`jobs/<id>/pitch.html` to the member's `upwork-pitches` Vercel project, confirms
that the page opens publicly, then saves the exact deployment URL through
`code/pipeline.py`. Never upload the job folder because it contains drafts.

Publishing is part of this command. A missing Vercel CLI or authentication is a
blocker, not a completed pitch. The member can set `VERCEL_TOKEN`,
`VERCEL_SCOPE` and `VERCEL_PITCH_PROJECT` in `.env`; an existing Vercel CLI
login also works without a token.

## Step 9 · Report

Completion report as CLAUDE.md defines it, with the public page and the script
linked, and whether the video is still missing. Next step: record the Loom,
then `/apply <id>`. Upwork call count.
