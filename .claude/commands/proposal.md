---
description: Builds a one-page pitch site for one job, chosen by branch, and the application to submit: cover letter and bid.
argument-hint: "<job id> [more job ids] | <job id> submitted"
---

# /proposal

**`/proposal <id> submitted`:** only run `python3 code/pipeline.py set <id> applied`
and report `Upwork calls: 0`, then stop before any other step. It records the member's submission.

**Several ids run one after another.** Each page gets its own sketch, its own approval: the repetition is the command's, never the member's yes.

Follow `references/copy.md` for the page and application. The
member described in `context/me.md` is the sender.

One page that makes a client stop scrolling: a headline about their job, three
proofs, their system drawn as a diagram they can drag and edit, the short
working-together sequence and the next step on Upwork. The Loom that walks
through this page comes after it. The application includes a cover letter, bid and any screening answers stated in the full posting.

Read first: [references/upwork.md](../../references/upwork.md) (hard constraint 8, no contact route on a page before a contract), `context/me.md`.

Before Step 1, if `jobs/<id>/pitch.html` exists, run
`python3 code/pitch_check.py page jobs/<id>/pitch.html`. When it passes, keep
that page and skip building it again and go straight to the Application step.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 6 does. Never build from the summary: the diagram is drawn from the requirements, and the summary does not carry them.

## Step 2 · Which page is this

- **Anonymous client:** the page pitches the build.
- **The company is named in the posting:** the page opens with what you noticed about their situation, from their own words and public site. Research is fine, contact is not. Every observation must be checkable; a wrong one about their own business ends the conversation. Uncertain which company: treat it as anonymous.

## Step 3 · Understand the mechanism

For every tool or delivery discipline the posting names, check
`context/tool-knowledge/<tool>.md` if the member has a copy, otherwise the current
`starters/context/tool-knowledge/<tool>.md`. Shipped references cover SEO and Google Ads. Read only the
ones this job uses. If a named system is not covered, research it now with
official docs first, then save decisions in `context/tool-knowledge/<tool>.md` with
sources so the next job does not pay for the same discovery again. A familiar
category is not a reason to skip this: the specific combination is what the
client is paying for.

For SEO, choose the relevant lane from `seo.md` before
planning, and read `delivery.md`, using the same member-copy or starter rule, for how the work is
sequenced. Put the posting's plugins, badges, privacy rules and performance
targets inside the track or step they belong to, instead of turning each
requirement into another box. For Google Ads, put verified conversion measurement
before bidding and keep media spend separate from the implementation fee. These
references guide the mechanism; they never supply proof about the member or facts
about the client.

### Price guide, for every lane

Estimate effort from the full posting, never the client's budget: low, likely and
high hours; two to five milestones summing to likely; confidence; scope assumptions.

```
python3 code/pricing.py <id> --hours <low> <likely> <high> \
  --confidence high|medium|low --contract-type fixed|hourly|unknown \
  --milestone "Foundation|hours" --milestone "Build and QA|hours" \
  --assumption "one concrete scope boundary"
```

Every lane runs this before Step 4. It uses the member's rate plus a scope-risk
buffer of 5, 15 or 25 percent for high, medium or low confidence. The internal
guide is never the bid, never appears on the page and never overrides approved terms.

## Step 4 · Read the posting into a plan

**Decide which page this job gets, by branch.** Every branch has a one-page template that prints on one A4 page. Pick the one whose `Tools:` line (`templates/profile/lanes.md`) the posting matches; a job that mixes branches gets the branch that carries most of the work.

| Posting is mainly | Page | How it is made |
|---|---|---|
| SEO, local SEO, Google Business Profile | `templates/roadmap/seo.html` | copy and edit |
| Google Ads | `templates/roadmap/google-ads.html` | copy and edit |
| A website, landing page or redesign | `templates/roadmap/website.html` | copy and edit |
| GoHighLevel, CRM, sales funnel | `templates/roadmap/gohighlevel.html` + `templates/pitch/graphs/ghl-funnel.json` | `roadmap_build.py` |
| Automations (Make, Zapier, n8n, AI workflows) | `templates/roadmap/automations.html` + `templates/pitch/graphs/automations.json` | `roadmap_build.py` |
| Something else | the full pitch page below | Steps 4 and 5 |

- **Roadmap pages (SEO, Google Ads, Website):** copy the template to `jobs/<id>/pitch.html`,
  which is the file the member shares on screen in the Loom, and edit it to this client. **Skip Steps 4 and 5
  and go to Step 6**: no graph, no `pitch_generate.py`. The file's own comment lists what
  to rewrite; these decide whether it lands:

  - **The h1 is the outcome this client asked for, in their words**, never the name of a service.
  - **Tag the rows they named.** A fifth entry on any `ROWS` row is what they asked for, quoted from the posting; it prints as a tag on that row. Tag only what they actually wrote, and delete the placeholder tag.
  - **Add a row for anything they asked for that the plan does not carry.** Keep the page on one screen: if a row is added, merge two.
  - **Plain words.** A client who is not in the trade must understand every row at a glance: "customer list", not "CRM"; "count your leads", not "conversion tracking".

- **Flowchart pages (GoHighLevel, Automations):** cut the graph to what the posting needs
  (labels in the client's words, still 8 to 20 steps and still `graph_sketch.py` clean, see
  Step 4 below), save it as `jobs/<id>/pitch-graph.json`, then run
  `python3 code/roadmap_build.py templates/roadmap/<page>.html --graph jobs/<id>/pitch-graph.json --out jobs/<id>/pitch.html --title "<title>"`.
  Edit the headline, the one-line lede, the who row and the closing offer in the result. Skip Step 5.

- **All one-pagers:** fill every blank, including the photo and the public profile URL from
  `context/me.md`. The photo goes in with
  `python3 code/photo.py <their photo> --into jobs/<id>/pitch.html`, which crops and sizes
  it and refuses one too heavy to embed. `pitch_check.py` refuses the page while it still
  says `<Your name>` or `PUT-YOUR-...`, and the photo has to be embedded as a `data:` URI
  because the deploy uploads one file and nothing beside it. The one-pagers carry no
  walkthrough button: a Loom, when there is one, goes into the application text, not onto the page.

- **Anything else:** draw the diagram as below.

Write down, before drawing: the trigger, the systems they already run, the manual work today, where results must land, the phase two wishes, the constraints. Then five rules: use their words ("your Squarespace form", not "web form"); never invent a fact, draw a "which CRM? to confirm" node instead; mark scope with groups (what ships first, what comes later); every manual step in the posting is a step the diagram takes over; a requirement with its own sentence gets its own node.

Write the graph to `jobs/<id>/pitch-graph.json`:

- **The diagram has to earn its place.** A picture that says what a numbered list
  says is decoration, so it must show at least one of these three, and say which
  in the run: a **decision** with two outgoing edges that are both labelled, a
  **node the client already runs** (`owner: client`), or an **open question** the
  member still needs answered, drawn as its own node.
- Eight to twenty nodes, and **at least two steps per phase**; the generator refuses one node per phase.
- **Five roles every graph answers:** what starts it, what the system decides, the normal path, what happens when it fails or nobody answers, and what the client sees at the end.
- Combine technical internals that serve one outcome and explain them in the node
  note. Branches read better than one long chain.
- `nodes`: `id`, `label` (an everyday verb and outcome, ideally four words or fewer), `kind` (`source`, `step`, `sink`, `decision`, `datastore`, `service`, `actor`, `note`, `milestone`), `owner` (`you` builds it, `client` already runs it, `thirdparty` outside service), optional `logo` (a file name in `templates/pitch/logos/`) and `note` (what happens in this exact job). The note is one short sentence that names the exact tool and action, such as "GoHighLevel Workflows sends the missed-call SMS." Never add a separate benefit field or a generic explanation that would survive a different job title. A reader must understand the label without opening it.
- `edges`: `from`, `to`, optional `label`, optional `dashed` for later phases. **Every edge leaving a decision carries a label** ("yes" and "no", "answered" and "no answer after 24h"), because an unlabelled fork tells a client nothing.
- `groups`: `label` and `nodes`, one per sequential phase. Use two to five
  client-facing outcome labels, not technical buckets such as "Setup" or
  "Automation". The first phase must be the smallest useful result. The board
  turns each group's last connected step into its visible phase output.
- **SEO website jobs:** use the four tracks in `seo.md`, with the Step 3 fallback, as
  the **phases**, not as the nodes. Each track carries its own two or three steps,
  and the branch that matters is usually what happens to the old URLs and what the
  client has to supply. A plugin, badge, schema type or speed target belongs in a
  node note unless it changes the order or creates a real branch.

## Step 5 · Show the flow, then assemble

Images are optional. Before any paid generation, including kie.ai through
`proposal_illustrate.py`, state the current model cost per image, count and total,
then wait for an explicit yes. Unknown cost: continue without images.

**Run `python3 code/graph_sketch.py jobs/<id>/pitch-graph.json` and put the sketch in front of the member before anything is generated.** It prints the diagram as text: one block per phase, node owners, every labelled edge, and the three proofs counted rather than claimed.

Research and draft the flow alone. Then read the sketch back in two lines, say which of the three proofs it rests on and what you deliberately left out, and wait for the member's yes or correction **before** the page is rendered and published.

**Every FIX line the sketch prints is a defect, not a hint.**

```
python3 code/pitch_generate.py <id> --hook "..." \
  --build-lede "one job-specific sentence explaining the full flow" \
  --graph jobs/<id>/pitch-graph.json --kickoff "..." (repeat) \
  --updates "cadence|platform" \
  --plan-outcome "job-specific client benefit" (once per card) \
  --plan-image jobs/<id>/plan-01.jpg (once per card) \
  --hero-illustration jobs/<id>/hero.jpg
```

- **Industry treatment:** choose one restrained `--theme` and keep it for the whole page: `steel` for trades, construction and operations; `signal` for software, AI and automation; `growth` for SEO, marketing and commerce; `calm` for health, coaching, education and care; or `warm` for general professional services. Hero and card illustrations (one per card, two cards) use the client's actual environment, materials and workflow. Motion stays subtle, readable and disabled by reduced-motion preferences.

- **Proof stays short:** at most three client voices on the page.

- **The flow board answers to a keyboard:** every node reachable and openable with the keyboard alone, and automatic scaling never shrinks a node below 88 percent of its readable size.

- **Copy hierarchy:** lead every section and card with the result the client wants, such as fewer lost leads, and put tools and mechanics in the description below. Never use a tool name or a feature list as the headline. Both layers stay specific to this job and supported by the posting or proof.

- **Onboarding:** only the access, content and decisions needed before the first build.
- **Updates:** name a specific cadence and where updates will live. Upwork before a
  contract, the client's own workspace after hire.
- **Working together:** lead with the client outcome, then how it happens. Write one short, job-specific `--plan-outcome` per card and optionally one landscape `--plan-image` per card, in the same order. When images are chosen, hero and card images form one coherent series: one style, the actual project in the client's industry, no text, logos or generic diagrams. The subject is the system, work or finished outcome; people only as small context, never looking at a screen, pointing at a board or posing beside the work. Inspect every source image and its crop on the finished page; reject repeated compositions, fake readable UI, dominant people and crops that hide the industry or the work.
- **Member photo:** when a real member photo is available, use it as the identity
  reference for one natural action portrait and pass the finished local asset
  with `--profile-image`. Never invent a member's likeness without that
  reference. The proof beside it still comes only from the Results, Reviews and Credentials sections of
  `context/me.md`.
- Do not put a budget or speculative delivery timeline on the pitch page. The
  internal pricing guide remains in the cockpit for the member.
- **Next step** (`--next-step`) points back to Upwork; the default asks them to send their website or current setup there.
- **Build lede:** one sentence that names this job's trigger, useful outcome
  and final handoff. It sits above the board. Generic claims such as "drawn
  from your posting" are not accepted.
- Optional: `--live-artifact "Label|URL"` for anything actually built and `--proof-link "Label|Detail|URL"` for past work with no contact details on it.
- **Pictures are optional and the pitch is complete without them.** A 16:9 `--hero-illustration` sits directly below the headline, never inside the flow, and follows the image rules above. A path you pass that does not exist is still an error; passing none is not.
- Give the moving dither field a job-specific, high-contrast source through `--dither-source`: one simple industry object or scene (a roofline and ladder for roofing) that stays identifiable as dots, not a particle cloud or detailed photo. Prefer a small local SVG; it is embedded and may load nothing from the network. Keep every motif upright: horizontal mirroring is fine, vertical flipping is not.

## Step 6 · The gates

- `python3 code/pitch_check.py page jobs/<id>/pitch.html`: no email, phone, booking link, messenger or social profile anywhere on the page, no unfilled placeholder. Upwork suspends accounts for contact details before a contract, and a linked page counts.
- Run `python3 code/pitch_capture.py <id>`, read the screenshot path it prints,
  then run `python3 code/pitch_capture.py <id> --clean`. Never call a page done
  unseen. The cleanup removes the temporary screenshot after the visual check.
- Inspect the hero and every plan-image crop. Check every dither placement:
  the source must be upright, identifiable and clear of the copy.

## Step 7 · Application

Use the full posting from Step 1 and `references/copy.md` for
every line the client will read. The member reviews and submits the proposal
on Upwork themselves. Prepare the cover letter, screening answers when the
posting states the questions, and the bid for manual submission.

**The first 230 characters decide.** That is all the applicant card shows a client, roughly the first 45 words. Put the outcome and the one relevant proof there, not a greeting or excitement.

### What is true about you and the scope

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against the evidence sections of `context/me.md`. **A requirement your proof does not cover never becomes a claim.** If it is mandatory, ask the member whether they meet it and where that can be checked, one single choice per requirement: met and checkable, met with nothing to point at, not met; the place is typed. Until resolved, save no client-facing draft. If it is a preference, name the gap for the member and draft without claiming it. Lead with the strongest relevant proof by tier; never a badge or number the member does not hold.

Separate explicit deliverables from assumptions. Before quoting a price or
timeline, resolve the contract type, included work, dependencies, revision or
acceptance boundary and payment structure from the posting, saved member policy
or an explicit member decision. If one changes the bid, ask before writing the application. Never convert an hourly profile rate into a fixed-price quote.

When `details.price_estimate` exists, use it as the internal starting point:
show the hour cases, profile rate, risk buffer, assumptions and roadmap together.
It is an estimate, not approval. Recalculate it when the resolved scope changes,
and get the member's explicit bid decision before writing the bid, as a single choice
between the estimate's cases with another figure typed.

### Write the letter

Write the letter on the member's own template: five blocks, friendly and plain, no
em-dashes, normally 120 to 180 words and never more than 220. The template comes from
the member's sent letters; keep its order and its small signposts (📽️ 🔗 ❗). Every
`<...>` below is filled from this job's posting and from `context/me.md`, never from memory.

```
Hey, I'm a <the member's real status and role from context/me.md> and can definitely help you <the client's goal, in the client's own words from the posting>.

Here's how I would do it :)
📽️: [LOOM LINK]

<Screening block, only when the posting states questions: see below>

In terms of relevant experience, <one or two sentences of proof from the evidence sections of context/me.md that fit this job, using the problem words of the posting>.

<One sentence on how the member works that answers this client's situation, for example: audit first, simplify, rebuild, document.>

<Only if the member has a portfolio link in context/me.md:>
Websites, funnels etc:
❗<the portfolio link>

Happy to jump on a call to <the one thing to scope for this job>. Looking forward to hearing from you!

All the best, <first name>
```

Fill rules:
- **The opening carries the card.** The first 230 characters are the role plus this client's outcome, with at least one word from the job title.
- **Status, counts and clients** ("Top-Rated", "15+ clients", a named result) are written only if they stand in the evidence sections of `context/me.md`. A count that is missing is left out, not asked for. **The portfolio block is optional**: most members have no link, so without one the two lines are dropped and nothing is asked.
- **The page is not published.** The member opens `jobs/<id>/pitch.html` on their own screen and walks through it in the Loom. The letter carries no page link.
- **No claim beyond the proof.** A requirement the evidence does not cover is not claimed; name it to the member instead.
- Do not recap the posting, add generic praise or pad. Never add a guarantee, refund,
  free work or delivery date as a sales device.

**Screening questions.** Read the full description for any question the client wants answered (a numbered list, "please answer", "include", "start your reply with") and for questions in Upwork's own question fields. Name each one in the Step 8 report. When the posting wants the answers in the letter itself, insert this block after the video lines, one numbered line per question, each answered in one or two sentences, and where the video covers it, say so in plain words (a timestamp only after the Loom exists):

```
Answers to your screening questions:

1. <topic of the question>: <answer>
2. ...
```

Otherwise put the answers in the separate `# Screening answers` section below, for the member to paste into Upwork's question fields.

Save the cover letter to `jobs/<id>/application.md` in this exact shape so the
cockpit can present it separately:

```markdown
# Cover letter

<the complete letter>

```

When the full posting states screening questions, answer each in one or two
sentences from the posting and verified proof. A mandatory answer without
proof is a hold. Do not guess questions the posting does not state. Append:

```markdown
# Screening answers

## <the client's exact question>

<one or two sentence answer>
```

Record the member-approved bid amount through
`python3 code/pipeline.py detail <id> --file -` with a JSON object containing
`bid_amount`. Leave out costs or questions the posting did not reveal.

### The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it. Then read it once as the client would: does it answer their post, or could it sit under any other job?

### Manual handoff

Present the letter, any answers, the bid and any preferred qualification the
member does not meet. Open the saved job URL on Upwork. The member pastes the
fields, reviews Upwork's final cost and submits the proposal on Upwork
themselves.

**Before they paste, run `python3 code/application_check.py jobs/<id>/application.md
--ready`.** Same gate, one more refusal: the `[LOOM LINK]` placeholder, correct while the
letter is written and wrong the moment it is pasted.

Never mark Applied until the member submits on Upwork, then runs `/proposal <id> submitted`.
That stage rests on their word; `/brief` checks once if no proposal ever shows up.

## Step 8 · Report

Run `python3 code/pipeline.py prune` first, because Step 1 fetched the full job. Then the completion report as CLAUDE.md defines it, with the application linked. Say what the application costs in Connects and what the balance leaves.
Next: record the Loom and return its URL here; replace [LOOM LINK] in the letter. The
page stays on the member's computer. Run the ready application check again. Only then submit on Upwork and run `/proposal <id> submitted`.
End with `Upwork calls: N`.
