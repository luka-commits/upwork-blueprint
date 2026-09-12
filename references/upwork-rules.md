# Upwork: what is allowed, with the numbers

The single source for every command in this repo that talks to Upwork. Measured 14 August 2026 from Upwork's own pages, not from blogs. Whoever changes a number here names the source next to it.

## The hard line

**Unattended automation is prohibited.** Upwork names these verbatim as grounds for enforcement:

> "Using OAuth2 tokens or session cookies from a browser or **an official client** in a script or bot"
> "Exceeding rate limits or **running background polling that resembles scraping**"

Source: [Use bots and other automation properly](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly)

Two approaches that would technically work are therefore out: copying your Claude Code login into another runner (a cron job, a hosted agent, a credential vault), and polling on a schedule.

**The Blueprint's conservative route:** use the official connector only in a
member-started local run, keep calls narrow and put a specific approval in front
of every write. This removes the unattended pattern named in the policy. It is
not evidence that Upwork has reviewed or approved this repository or every
connector action.

## The numbers

- **Requests per IP:** 10 per second, then HTTP 429. [Support](https://support.upwork.com/hc/en-us/articles/115015933428-What-are-the-API-requests-limits)
- **Requests per IP:** 300 per minute. [Developer docs](https://www.upwork.com/developer/documentation/graphql/api/docs/index.html)
- **Requests per day:** 40,000, confirmed in the API-key application. [API key](https://support.upwork.com/hc/en-us/articles/115015857647-Request-an-API-key)
- **Caching API responses:** 24 hours maximum. Both sources above.

The first two contradict each other and both are Upwork's. Assume the stricter
one. Compare the exact call count from a run with both published limits instead
of declaring it safe from an estimated range.

**The pattern matters as much as volume.** "Polling that resembles scraping" is
a behavioural judgement with no documented threshold. No request count makes
unattended polling acceptable. Member initiation is a house rule that avoids
that pattern, not a blanket compliance guarantee.

## The house rules, stricter than the terms

1. **Writing always needs an explicit yes.** A message, invitation or offer is
   sent only after approval of the exact content. A proposal is stricter: the
   Blueprint prepares its fields and optional preview but never confirms or
   submits it. The member opens Upwork, reviews the application and clicks
   Submit there. The only cockpit sending exception is the dedicated
   `send-reply` run: the member edits and clicks Send on one exact draft, then
   the server freezes its text, room, approval time and the already-known
   message ids in `jobs/<id>/outbox.json`. A runtime guard binds the send to
   that frozen approval and permits one attempt. Confirmation requires a
   freelancer message with the exact text, a new message id and a timestamp at
   or after approval. If the send or confirmation is uncertain, the unresolved
   outbox blocks another send. Run `/inbox` or inspect the Upwork conversation,
   reconcile what actually landed and never retry blindly. No other cockpit run
   receives `send_message`, and none receives `confirm_preview`.
2. **Reading runs on demand.** A command you typed or a cockpit button you clicked. No timer, no background job.
3. **Every run reports its call count.** One sentence. Then "well under the limit" is measured rather than assumed.
4. **`python3 code/pipeline.py prune` after each run.** Upwork content older than 24 hours goes. Your own scores, notes and history are yours and stay.
5. **No login leaves this machine.** Not into a vault, a cron job or a hosted agent.
6. **Never buy Connects.** Commands say what an application costs and what is left. Buying is your click on Upwork.

## Links before a contract starts

Checked 12 September 2026 against Upwork's help center, as quoted by the search index (the pages block direct fetching):

- **Contact information is banned until the contract starts.** Sharing it, or asking for it, "before a contract starts is against our Terms of Service, and may result in temporary restrictions, loss of talent badges, or permanent loss of account access." Contact information means any way to reach you outside Upwork. [Keeping your contact information safe](https://support.upwork.com/hc/en-us/articles/360051749534-How-to-keep-your-contact-information-safe-on-Upwork)
- **A link to your work is allowed.** "You can share website portfolio links with potential clients, but just be sure to ask the client to only contact you through Upwork until the contract starts." Same article.
- **So a linked page must carry no way to reach you.** No email, phone, WhatsApp, booking link, contact form or social profile. Every page this repo builds for a client before a contract (the pitch page) follows that, and says "reply here on Upwork" instead.
- **Meetings run on Upwork's own video calls** until the contract starts. [Can I share my own communication tools?](https://support.upwork.com/hc/en-us/articles/40444093133331-Can-I-share-my-own-communication-tools-like-email-or-meeting-links)
- **Exception:** if you or the client is on an Enterprise plan, contact details may be shared before a contract.

## API eligibility does not settle automation permission

Upwork's API-key application lists these eligibility criteria:

- $25,000 lifetime earnings
- Job Success Score of 90% or higher
- Identity verified, payment method, profile photo, account in good standing

Plus: *"Upwork API is available for personal and internal use only. Commercial use isn't supported."* This repo hosts nothing and holds no one's login: every member uses the official connector in their own Claude Code, for their own account.

Meeting those criteria may make an account eligible to apply for a key. It does
not by itself authorize unattended automation, commercial use or any particular
write. This Blueprint remains local and member-started regardless of earnings.

## The open contradiction, stated rather than resolved

The connector's tool description exposes a `set_tool_permission` switch with an
`always_allow` value and calls it useful for automated flows. That describes a
technical permission setting, not Upwork policy approval for unattended use.

Two Upwork sources, two directions. This file does not resolve that, because it cannot. If you intend to run anything unattended, ask Upwork support directly and write their answer here.
