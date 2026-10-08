# Jobs: how we search, and what we propose

The operating half, state of 28 September 2026. `/find-jobs` reads the search strategy and the
client rules. Market figures are not copied here, because a number copied goes stale and nobody
notices; the two pages at the bottom carry them with their sample sizes and caveats.

## The four angles of search terms

Every term comes from one of these four, and a run that uses only one is a run in the crowd.

- **Tools.** Platform names a client types when they know what they run: Make, n8n, Zapier, Monday,
  HubSpot, Shopify, Salesforce, ClickUp, Zoho, Pipedrive, GoHighLevel, Google Calendar, Zoom,
  Gmail, WordPress.
- **Positions and long-term work.** Titles rather than tools: GTM engineer, RevOps, AI consultant,
  email marketing expert. These postings look for a person, often for months, not for one workflow.
- **Generic problem words.** What a client writes when they know the pain and not the solution:
  automation, API integrations, business operations, client onboarding, no-code. Most freelancers
  search only here, usually just "automation", which is not wrong and is also where the crowd is.
- **The client's industry, same logic.** A dental practice, a gym, a law firm, an HVAC company, a
  Shopify store or a clinic writes about its own trade, never about automation. The industry plus
  "booking", "leads", "follow-up" or "no-shows" reaches those postings before any freelancer who
  searched only their own tool stack. A career changer owns this angle: the industry they already
  worked in is the one whose language they speak.

**The split inside the tools angle is the actual trick.** The low and no-code platforms (Make,
n8n, Zapier) are where freelancers who do automation search for themselves. Everything the client
already runs (Shopify, Salesforce, Monday, Zoho, GoHighLevel, Google Calendar, Gmail) is where
nobody looks, and it is full of postings that are automation work without saying so. One client
posted about connecting his Shopify customers to his Google Calendar, naming no platform and no
automation; the job was a single Make workflow, and it sat in a search nobody was running.
**Search the client's tools, not the member's.** The member's own stack finds the crowded queries,
the client's stack the quiet ones. Zapier and n8n lead the postings by a distance, n8n rising and
Make falling through 2026, Power Automate barely present, while GoHighLevel and generic CRM wording
carry a quarter to nearly half of the automation set alone. Current shares are in the report.

## Ten a day, and a bench of ten

The run's unit is not a score, it is **ten leads worth applying to today**, by default:
the member's own `Applications per day` in `context/me.md` replaces ten, with as many
more behind them. One turned down is replaced from the bench in the same breath. Fewer
is reported as what it is, with the cause named: too few dense tracks, limits set too
tight, or a quiet day. Padding the list with leads the score turned down wastes Connects.

**What it costs.** Measured 28 September 2026: one local SEO job cost 7 Connects. Say the
day's bill and the balance once, never buy Connects, and never talk a member out of their
own target.

## The candidate term catalog

A menu for a first run, so nobody stares at a blank page. **Every term here is
unmeasured until this account measures it**, and one page of results settles it: how
many of the ten are real work for this member, and over how many hours they spread.
A term that finds nothing another term had not, in three runs, is proposed for removal (`tracks.py measure --log`), and removed only on the member's yes. The four angles are the
columns; a field the member does not sell is a field to skip.

**Local search and paid search**
```
tools     Google Business Profile · Google Maps · Search Console · BrightLocal · Citations
roles     local SEO specialist · SEO consultant · Google Ads specialist · PPC manager
problems  not showing on Google · organic traffic · wasted ad spend · cost per lead · more calls
industry  <trade> SEO · <trade> leads · <trade> marketing · <trade> Google Ads
```

**Websites**
```
tools     Webflow · WordPress · Elementor · Wix · Squarespace · Shopify theme
roles     web designer · landing page designer
problems  website redesign · site speed · mobile friendly · one page website
industry  <trade> website · <trade> landing page
```

**AI visibility**, the fastest-growing wording measured on 28 September 2026: six of ten
SEO postings that day asked for it by name.
```
tools     AI Overviews · ChatGPT Search · Perplexity
roles     GEO specialist · AEO specialist
problems  AI search visibility · show up in AI answers · cited by ChatGPT
```

**Automation**
```
tools     Make · n8n · Zapier · Airtable · Google Sheets · Twilio
roles     automation engineer · no-code developer · integration specialist
problems  manual data entry · connect two tools · API integration · client onboarding
industry  <trade> booking · <trade> intake · <trade> scheduling
```

**CRM and follow-up**
```
tools     GoHighLevel · GHL · HubSpot · Pipedrive · Mailgun
roles     GoHighLevel expert · marketing automation specialist · RevOps
problems  missed call text back · lead follow-up · appointment booking · CRM setup · no-shows
industry  agency · <trade> academy · med spa · clinic
```

**Paid social**
```
tools     Meta Ads Manager · Facebook Pixel · TikTok Ads · Klaviyo
roles     paid social specialist · media buyer
problems  ads stopped working · creative testing · retargeting · cost per acquisition
```

**Email and lifecycle**
```
tools     Klaviyo · Mailchimp · ActiveCampaign · ConvertKit · Beehiiv
roles     email marketing specialist · lifecycle marketer · newsletter operator
problems  abandoned cart · welcome sequence · list cleanup · open rates · newsletter automation
```

**E-commerce**
```
tools     Shopify · WooCommerce · Amazon Seller Central · Merchant Center
roles     Shopify developer · Amazon PPC specialist
problems  product feed · abandoned checkout · conversion rate · listing optimization
```

**AI assistants and chatbots**
```
tools     OpenAI API · Voiceflow · Vapi · Retell · ManyChat · Intercom
roles     AI automation engineer · chatbot developer · voice agent developer
problems  answer the phone · qualify leads · book appointments · support tickets · FAQ bot
```

**Analytics and tracking**
```
tools     GA4 · Google Tag Manager · Looker Studio · server-side tagging
roles     analytics implementation specialist · tracking consultant
problems  conversions not tracked · duplicate events · reporting dashboard · attribution
```

**The client's own systems**, the angle nobody searches. A trade business writes the
name of the software it runs, never the name of your discipline.
```
home services   Housecall Pro · Jobber · ServiceTitan
health          Dentrix · Cliniko · Zenoti
fitness         Mindbody · PushPress · TeamUp · Zen Planner
booking         Calendly · Acuity · Square Appointments
back office     QuickBooks · Wave · Airtable
```
Measured 28 September 2026, and the measurement is the point: **"Housecall Pro" returned
ten postings over seven days with three worth applying to**, among them a GoHighLevel
role for an agency running 200 local clients. **"Mindbody" returned exactly one posting
in total**, `hasMore: false`. Two neighbouring terms from the same angle, one a track
and one a dead end, and nothing but a call could tell them apart.

**The industry line always carries the service word.** Measured 28 September 2026:
"dentist" returned ten postings over seven days and not one of them was marketing work,
"plumber" the same, while "gym marketing" returned two clear fits out of ten, one Google
Ads and one GoHighLevel. The trade alone finds job adverts; the trade plus what you sell
finds clients.

## Reverse engineering a term, the cheapest discovery there is

One broad term, one page, then read the ten. Name the jobs that actually fit, and take
their wording rather than inventing any:

```
python3 code/tracks.py skills data/search/*.json --term "<a term you already run>" --id <fitting job id> --id <another>
```

It counts Upwork's own skill names on those postings and marks the ones no current term
covers. Those are candidates, not keepers: each still needs its one page of measurement.
Costs no Upwork call, because it reads the files the run already saved.

## Ready-made tracks

The `Search:` line of each branch in [templates/profile/lanes.md](../templates/profile/lanes.md)
is that branch's track, and the only place its terms live. `/find-jobs` reads
`**Branches you picked:**` in `context/me.md`, writes one track per picked branch with the
branch name as its label, and runs them in the same run without asking. A custom direction
has no line there: its terms come from its services, tools and roles in `context/me.md`,
worded the way the catalog above words them.

An industry the member prefers adds one track, the trade plus each picked branch's service
word (`gym SEO`, `gym Google Ads`, `gym website`), only while there is room.

**At most five tracks.** Every term is one title search per page, every track adds one `query`
page and every run one page of Upwork's recommendations, and a run stops at 25 pages, so
more tracks buy coverage at the cost of depth per term, which is how a run stops finding the
fresh postings that are the whole point. Branches go first in the member's order; a branch left
out is named in the report.

## The member's limits

`jobs.py candidates` applies these after the search, with the defaults below. A figure the
member writes into `context/me.md` is also sent as the search filter in the third column,
so their own boundary costs no page; a default never is, because a filter removes jobs
before anyone scores them.

**These figures are a starting point, not a rule.** Three of the five scale with
experience, and the wrong figure is expensive in both directions: an established member
floored at a hundred dollars takes work that pays worse than their afternoon, and a
beginner floored too high finds nothing.
`/find-jobs` applies the defaults below and asks nothing; a member who wants other figures
writes them into `context/me.md`, and every later run reads them there.

| Limit | Default | Filter | Why this number |
|---|---|---|---|
| Competition | no cap unless the member sets one | `proposals_max` | Typical postings carry 18 to 41 proposals (26 September 2026), so a default cap would cut half of ordinary work. The count is shown on every lead |
| Fixed price floor | $250 | `budget_min` | Below it the writing costs more than the job pays |
| Hourly floor | 60% of the member's rate | `rate_min` | The same day returned hourly postings at $3 to $5 |
| Engagement | no `FULL_TIME` | `job_type`, `workload` | An employee disguised as a contract, and the one trap a generous budget hides best |
| Client rating | drop below 3.0, and only with at least 3 reviews | after the search | One bad review is one freelancer's bad week; three are a pattern. The rating is not a search filter |
| Age | older than the window, at most 12 hours | the window | Measured 28 September 2026: a three-hour-old posting already carried 23 proposals. A day old is a queue, not an opening |

**A posting that caps itself is a no whatever the client looks like**, for example
"$500 fixed price, done by Friday". The posting is evidence about the budget, the
client history only evidence about the client.

**Every exclusion is logged with its reason.** A limit that costs the member good
work has to be visible as a cost within two weeks, or it is a rule nobody can
argue with.

## Judging the client

Three signals, from the search row and then from `find_jobs` action `get`:

1. **Verified payment.** Every search sets `verified_payment_only` true. An unverified client
   cannot pay without clearing verification first, so this is the one hard gate.
2. **History.** `total_spent`, `total_posted_jobs` and `client_record` say whether they hired before
   and how they rated those hires. `total_spent` is missing from most search rows, so judge it on
   the job page or not at all.
3. **Hire rate.** Jobs posted against hires made, from `client_record`. A client who posts
   constantly and hires rarely is a warning, not a veto. Confidence: unmeasured, folklore.

**Do not disqualify a client on thin signals.** A low average hourly spend may be one old assistant
contract, not a ceiling, and zero spend may be a client who does not know the platform's rates.
**Do disqualify a posting whose own text caps itself**, for example "$500 fixed price, done by
Friday": the posting is evidence about the budget, the history only evidence about the client.
Record which kind of client actually paid, and let the member's own numbers settle it
within months rather than a rule written here.

## Where the numbers come from

Anyone who needs a current figure reads it there and cites the date, never taking it from here:

- **The monthly posting report:** `upwork.redwaterrev.com/report/2026-08`, rate distribution, tool
  shares, and the publisher's own caveats.
- **Upwork's asking rates by discipline:** `upwork.com/resources/upwork-hourly-rates`.
- **What we checked and what did not hold:** [RESEARCH.md](../RESEARCH.md).
