# Google Ads delivery knowledge

Distilled from the Automatable Ads Blueprint, a full Google Ads delivery system for local service and lead-gen accounts. Use it when an Upwork job names Google Ads, paid search, PPC, campaign setup, account audit or ongoing management. It supplies the work plan and the mechanism behind a pitch diagram. It never supplies proof about the member, facts about the client, or a performance promise.

Every number carries its origin: **(G)** Google documentation or the API, **(S)** a study with a stated sample, **(P)** practitioner convention with no primary source. Use (S) and (P) figures to choose the work, never to promise a client an outcome.

## The order of work, and the reason for each step

1. **Audit first on an existing account, and stop at tracking.** If conversion tracking is wrong, every cost per acquisition in the account is fiction and every recommendation below it is unsafe. Nothing else is worth reading until that passes.
2. **Collect the business economics.** Service list, service area, average job value, close rate, sales capacity, the jobs they refuse. Lead value = job value x close rate, and break-even cost per lead equals lead value. Without this, "good CPL" is an opinion.
3. **Keywords and structure together, before anything is built.** The keyword list and the ad group map are one artifact: a keyword only exists once you know which ad it will be served by.
4. **Account foundation.** Time zone and currency are permanent on a serving account (G), so they are read back aloud before submit. Then the switches Google ships wrong, then the universal negative list.
5. **Landing page and measurement in the same pass.** The conversion tag, the thank-you page, the phone number swap and the form callback are built with the page, not after it. A page shipped without them cannot be verified, and the verification is the gate.
6. **Build campaigns, then ads, everything paused.** The final URL must resolve on the same domain at creation time or Google's policy check fails the whole write (G). This is why the page comes before the build.
7. **Verify, then the client enables.** One real form submit, one real call, each producing exactly one conversion request with the right label, read off the tag debugger.
8. **The learning loop.** Search terms, negatives, harvest, then one budget or bid change at a time.

## Before the first click: measurement

**Three primary conversions, no more.** One per real lead path: form submit, call from ads, call from the website. A fourth primary means something soft got promoted. Form views, scroll depth, page views, downloads and short calls stay secondary and never sit inside a bidding goal. Smart Bidding learns from primaries and nothing else.

**Counting is a business-model decision.** One per click for lead gen, Every for ecommerce (G). The API default is Every, so every hand-made lead action double counts until it is flipped. A second call from the same click is not a second lead.

**The named causes of double counting.** Both the event and the thank-you URL on one action. gtag and Tag Manager installed together, the commonest cause. A GA4 key-event import left primary beside the native tag on the same form. A calendar booking tagged on a thank-you page everybody reaches after the form already fired. Three call actions all primary at once.

**Attribution and windows.** Data-driven is the default and the only model beside last click; first-click, linear, time-decay and position-based were retired in October 2023 and the API rejects them (G). Click window 30 days by default, range 1 to 90 (G). Identical windows across actions or bidding cannot compare them. Set the window past the typical lead-to-booked time; a window shorter than the sales cycle silently drops real conversions.

**Calls are half the account in local service.** Call reporting goes on at account level first, or there is no call conversion at all, and switching it off later removes the call signal from bidding (G). Website calls swap the displayed number for a Google forwarding number through a second gtag config call carrying the call label and the number; the displayed text and the `tel:` href must match exactly or the swap fails. Forwarding numbers exist in roughly 30 countries (G), so the country is checked before the capability is promised. The caller's number is only reported on calls over 15 seconds (G). The minimum call length that counts is a judgement call: the widely quoted default is 60 seconds and the practitioner band is 30 to 60 (P), but a short threshold treats voicemail and missed pickups as leads, which is usually what a service business wants. Where Google's AI call-intent qualification is available it replaces the duration debate entirely.

**Enhanced conversions and offline import.** Email and phone are normalised and SHA-256 hashed with the conversion so a signed-in match can be recovered (G). Offline import goes in at the earliest stage that predicts revenue, usually booked appointment, one action per stage; the click must still fall inside the action's window, so a six-month sales cycle cannot be attributed to the click (G). The gclid is case sensitive and is stored exactly as received, because the upload fails silently without it.

**The verification gate.** Auto-tagging, enhanced conversions and call reporting all read back on. Exactly three primaries with their type, category, counting and window. Tag present on the landing, thank-you and pricing pages. One real submit, one real call, one conversion request each and no duplicate. Consent banner tested in a private window with a real reject. Thank-you page returns noindex and is absent from the sitemap.

## Account structure

**The one-line rule.** If it needs its own budget, bid target, schedule or geography, it is a campaign. Otherwise it is an ad group.

**Launch with one campaign, not three.** Every service is an ad group inside it, one budget, one bid strategy. Smart Bidding learns at campaign level, so three starved campaigns sit in learning while one funded campaign is already producing. Google's structure benchmark is 15 conversions in 30 days per campaign, poolable across campaigns through a shared budget with a portfolio strategy (G). A service earns its own campaign at roughly 30 conversions a month of its own. Brand is the one exception and always separate: mixing brand into non-brand inflates the metrics and hides the true acquisition cost.

**Three to ten ad groups per campaign** is the published range. Past ten in a campaign under 50 conversions a month you are splitting hairs the bidding cannot see (S).

**Never split by city.** Location targeting is campaign level only (G), so city ad groups capture nothing but explicitly geo-modified queries, which are the minority of local search. Close variants already merged the city keywords. Geo lives at campaign level on Presence targeting; the city goes into the ad with location insertion and into the page from a URL parameter. Thin near-duplicate city pages are doorway pages under Google's spam policy even when noindexed. This is the single most expensive structural mistake in the audit list.

## STAG: the ad group

A STAG is a Single Theme Ad Group: one ad group built around one search intent, holding every keyword a searcher might type when they want the same thing, served by one ad written to mirror that intent.

**One test decides everything: would you write the identical ad for both searches?** Same ad, same STAG. Different ad, separate STAGs. This is Google's own wording on splitting ad groups that many different keywords cannot be addressed by one ad (G). The framework names change (SKAG, STAG, SIAG, IBAG); the test does not.

**Two things that are not part of the test.** The landing page is not: quality score rates ad relevance and landing page experience separately, and one strong page can serve ten ad groups. Word similarity is not, and it is a trap both ways. Five keywords that look uniform can need four different ads: `best` wants a rating line, `affordable` wants upfront pricing, `cost` and `quote` merge with each other and nothing else, `book` wants availability. Five that look varied (`company`, `contractors`, `services`, `hire a`, `specialist`) all take the same ad and are one group.

**Why not one keyword per ad group.** Close variants killed that: exact has matched same-meaning synonyms since September 2018 and phrase since July 2019, with no opt-out (G). What is left for hand-clustering is synonyms that are different concepts, like emergency against 24 hour. That hand-built cluster is the STAG. The other costs of over-splitting are data starvation at campaign level, negative-keyword starvation, and a responsive search ad that never reaches the impression volume where its assets get labelled.

**Size.** Five to fifteen same-intent keywords is the working range, with 20 the ceiling. Fifteen or more usually means two intents got merged. Symptom keywords are always their own group: "drain cleaning" is shopping for a service, "clogged drain" is a person with a problem right now.

**Cross-group routing is what makes the structure real.** Every specific group's trigger words become negatives on the generic group, on day one, not after the search terms report shows the bleed. Any word that defines one STAG is a negative on every STAG it does not define. Negatives have no close variants (G), so each routing negative goes in with its plural and singular.

## Match types and bidding

**Phrase is the default for a new lead-gen account.** Exact for the top money terms once they have data. Broad only when all five are true: a conversion-based Smart Bidding strategy, at least 30 conversions a month at campaign level (50 for target ROAS), shared negative lists live with someone reading search terms weekly, brand exclusions set, and enough budget that a bad week is survivable. Missing any one, restrict to phrase.

**The evidence both ways.** Exact beat broad on cost per lead in 74% of accounts and on conversion rate in 62% (Optmyzr, 4,000+ accounts, March 2024, vendor published). Across 992,028 keywords, exact ROAS 415%, phrase 313%, broad 277% (Optmyzr, November 2024, vendor published). Google's counter-claim is roughly 25% more conversions moving phrase to broad under target CPA (G, as a claim); independent relays put it nearer 10%. Phrase click costs rose faster than broad, 43% against 29% between June 2023 and June 2025 across 7,000 accounts (G), which is the real pressure toward broad, but only once the account can steer it.

**Never segment by match type across ad groups.** One theme holds all its match types. One keyword in three ad groups by match type is over-splitting in disguise.

**The campaign-level broad match setting is not the same thing as broad keywords.** It converts every phrase and exact keyword in the campaign to broad on save, and the new-campaign interface has pre-ticked it since July 2024. Check it at build time, every campaign.

**Bidding by data level.** Maximize Conversions with no target at launch, because the model learns account-wide and an account with 15 or more conversions in the last 30 days is already in the best case (G). The documented cold-start failure is a brand-new campaign serving zero impressions for seven days while Maximize Clicks spent its daily budget immediately: if the account serves nothing for a week, switch to Maximize Clicks with a click cap for two to four weeks, then back. Target CPA at about 30 conversions in 30 days (G), first target set from the last 30 days, then stepped down gradually with at least a week between steps. Target ROAS only past roughly 50 valued conversions a month, and never for leads that all carry the same flat value: that is target CPA with an extra throttle.

**Under Smart Bidding only a -100% device exclusion is honoured.** Location, schedule and audience bid adjustments are ignored (G). An audit that recommends a bid modifier on an automated campaign is recommending nothing.

**Learning resets** on a strategy switch, a target change, a budget move over about 20% in a week, a conversion action change, or a pause and re-enable (G). Google's stated learning period is up to three weeks or one to two conversion cycles. Do not change two things in one fortnight: two learning clocks at once produce no readable result.

**Budget arithmetic.** Daily budget is the monthly budget divided by 30.4, never 30, because that is the most Google bills in a calendar month (G), and any single day can spend twice the daily budget (G). Two sanity tests before quoting a plan: the daily budget should be at least three times the expected cost per lead, and it should buy at least ten clicks a day at the market click cost. Below that, bidding runs out of money mid-day and never sees enough auctions to learn.

## Negative keywords: the system

**Negatives do not expand.** Blocking `flowers` still serves on "flower". Plurals, stems, reorderings and synonyms each need their own entry (G). Misspellings and casing have been covered automatically since mid-2024, so misspelling lists are dead maintenance. Only the first 16 words of a query are evaluated. Plus signs are invalid and fail silently.

**Four levels, narrowest true level wins.** Account level holds the universal junk only, roughly 40 to 60 genuinely universal words, because one over-broad entry there kills a valid theme in every campaign at once. Shared lists hold the category blocks, three to seven well-named ones. Campaign level holds intent boundaries and geography. Ad group level is sculpting; needing many of them means restructure instead.

**The universal buckets** are job seekers, DIY and how-to, education and training, free and discount, informational research, customer support and existing customers, restricted and unsafe, and parts and supplies. Competitor brands and out-of-area cities are decided per account, never shipped in a universal list: a city or a trade word in a permanent list is a permanent self-block.

**Over-blocking is the more expensive mistake.** Bare `free` kills "free estimate" and "free quote". Bare `license` kills "licensed plumber near me". Bare `how to` kills "how to hire a plumber". Bare `hiring` kills "hiring a plumber". `cheap` and `affordable` are genuine hire intent for an operator who competes on price. `near me`, `cost`, `price`, `quote`, `best`, `hire`, `local` and `emergency` look like negatives and are not. The largest available sample found campaigns with account-level exclusions had a worse median cost per lead than those without (Optmyzr, 7,100 accounts, PMax not Search, vendor published) because Smart Bidding already bids losing terms down to pennies while a manual negative removes the term at any price. Negate irrelevance hard, performance softly.

**Conflicts are silent.** A negative that matches one of your own keywords makes that keyword show Active with zero impressions. Nothing errors and no report flags it. Test every new negative against every enabled keyword at the level it will land, block the write on any match, and tighten the match type before deleting anything. The two usual sources are copied industry lists and legacy negatives left after a restructure.

**A whole brand belongs in a brand exclusion list, not a negative list** (G), because exclusions cover misspellings, variants and other languages automatically.

**Stop rule.** If a day's proposed negatives exceed about 10% of a campaign's search terms, the keywords or match types are wrong and negatives are mopping up a leak at the source.

## The learning loop: search terms

**Cadence.** Daily for the first week of a new campaign, after the broad toggle goes on, and after any automation layer is enabled; weekly is the floor thereafter. Never score today's data: search term rows fill in later and non-last-click conversions arrive up to 15 hours late, so score yesterday and re-check the trailing three days.

**Roughly 40 to 50% of search-term spend is hidden** behind the privacy threshold introduced in September 2020, with per-account ranges from 10% to 85% (S, and Google confirms thresholds exist). Compute the hidden share per campaign as keyword clicks minus the sum of visible search-term clicks. Above about 40%, row-by-row review is fighting a minority of the problem: shift to n-gram work and match-type restriction. Bidding itself is not blind where you are; the hidden share limits your negatives, not the algorithm.

**The decision rule is a filter with a leave-it-alone default.** Known junk patterns get negated at one click with no analysis. Converting terms are never negated. A term under roughly one target cost per lead with no conversions is noise and gets no attention at all. Only survivors get a search-results check and cost math.

**How many clicks before zero conversions means anything.** The odds of zero conversions in N clicks when the term truly converts at rate p are (1-p)^N. Set that to 5% and N is about 3 divided by the conversion rate: 148 clicks at 2%, 98 at 3% (which is where the folk "100 clicks" rule comes from), 58 at 5%, 29 at 10%. Use the account's own trailing conversion rate, never a flat 100: at a 1% conversion rate a 100-click rule generates false positives and the client will find one and discard the whole list. In money, that is about three times the target cost per lead spent with nothing to show.

**Guardrails.** One conversion at or under 1.5x target is untouchable. Above 3x target on two or more conversions is a bid or routing problem, not a negative.

**N-grams find what row-by-row misses.** Aggregate cost, clicks and conversions across one-, two- and three-word fragments over 90 days. One- and two-word grams surface negatives; three- and four-word grams surface new keywords. Negate the root token once instead of a thousand variations. A high-cost gram that is really a different intent deserves its own ad group, not a negative.

**The harvest is the half that makes money.** Negatives save pennies; a converting term you were not bidding on makes dollars, so the positive side runs every pass. Three kinds of winner: unbid terms, misrouted terms already caught by the wrong keyword, and terms whose intent differs from the whole group and are therefore a new ad group. Every promotion into a different ad group is staged as a pair, the exact keyword in the new group and a phrase negative in the old one, or both groups compete for the term and routing gets worse. Feed the converting terms' exact language back into ad headlines and the page headline.

## The landing page half

**One ad group, one page.** That is the whole reason the page exists. Sending paid traffic to a homepage is the most common and most exploitable fault in local accounts: dedicated landing pages converted at a 4.02% median against 2.35% for general website pages (Unbounce 2026, vendor published).

**Message match is the one law.** The headline carries the ad group's service and the searcher's city inside a line that sells, never a bare echo, and the line under it repeats the ad's offer in the same words rather than a synonym. Headline alignment alone lifted conversion 66% in one documented test and 212% in another (S, single cases). It is also the relevance half of Google's landing page experience rating. The guarantee has to appear on the page in the same wording as the ad, or it is a substantiation failure as well as a quality leak. Do not city-swap a claim: swapping the service and city is message match, swapping "the city's top-rated" onto a city you have never worked in is an automated false claim.

**Structure, in order:** hero with headline, offer, three credibility bullets, licence and insurance line, and both calls to action side by side; trust strip with a real star average, exact review count and named source; problem then promise; what you get, including what is not included; the proof block, which is the heaviest section; how it works in three steps with a stated response time; results; why us; service area; guarantee; what it costs; an FAQ of five to seven objections in the customer's words; the close; a single legal line.

**Ad pages carry no header, no footer and no navigation.** Zero exits. Removing navigation lifted conversion 0 to 4% on cold pages and 16 to 28% on warm pages in a five-page test (S), and no published test shows adding navigation to an ad page raising conversion. The page is noindex, out of the sitemap, and never blocked in robots.txt.

**Form.** Four fields, labels above, single column, a `tel` input never split into boxes, and what the visitor typed preserved when an error shows. Conversion falls as field count rises (HubSpot, 40,000 pages). Extra qualifying questions belong on the thank-you page or the call. Button copy names the outcome, never "Submit".

**Speed and mobile.** Design the phone layout first: most paid visits are on a phone. One sticky call bar at the bottom of the viewport instead of repeated inline buttons. Core Web Vitals "good" at the 75th percentile is LCP under 2.5s, INP under 200ms, CLS under 0.1 (G), tested on a mid-tier Android over cellular, not office wifi.

**Phone number.** One real number everywhere, plain text, never inside an image, in one consistent format, with the display text and the `tel:` href matching exactly. Google's forwarding swap fails on any of those.

**Speed to lead sits outside the page but decides its value.** Between a 5-minute and a 30-minute first call, the odds of reaching the lead fall by roughly two orders of magnitude (MIT and InsideSales, 15,000+ leads, vendor published, and about twenty years old). The often-quoted 21x figure is from that same dataset and is not a Harvard study.

## Competitor research: what you actually look at

Four sources, each with a hard limit. **The Ads Transparency Center** is the anchor: every creative Google discloses, its format, first and last shown, regions and a rendered preview. It hides spend, impressions, keywords and which combination served, and since 2025 the payer name can be an agency, so competitors are matched by domain, never by name. **Live search results** are the only place you see the whole paid block, position, assets and the landing URL, but one capture is one sample of a rotating ad, and the location has to be set explicitly rather than trusted to a signed-in browser. **Auction Insights** gives impression share, overlap and outranking per competitor domain, but only once the account has spend, and it hides anyone under 10% impression share. **Third-party spy tools are sampled, not observed**: a zero from one is a coverage gap, not evidence, and every number from them is labelled estimated.

**What the output is:** a claims list, a gap list and a swipe file. Never a spend number, because none of the four sources contains one. Claims are bucketed into offer, price, speed, trust, risk reversal, identity and method, deduplicated, and counted by how many competitors run each. Offer and price sit at the top because they change what you sell. Puffery ("no job too big or small", "quality workmanship") is counted once as noise and never becomes an angle. A claim nobody runs is recorded as a zero, which is data.

**Their landing pages are inventoried, not judged:** where the ad lands, whether the page keeps the ad's promise, what proof is visible, which credentials are printed, whether the offer in the ad actually appears on the page, whether a real price is shown, the risk reversal in their words, the response promise, what the call to action is and how many form fields it has, and whether the photos are real or stock.

**Turning a gap into an angle** is a scored comparison, not an opinion: each proof signal carries a fixed impact, you score what a stranger can see on your client's side and on the best of the top three, and sort by impact plus gap. Score what is visible, never what exists; sixty testimonials in a folder score zero, and a credentials page nobody opens scores low. A gap that closes this week outranks a bigger gap that takes six months.

**Trademark line.** A competitor's mark never goes in ad text; bidding on their brand keyword is a separate and generally lawful question, and competitor terms are their own cluster with their own ads or they are negated everywhere.

## What an audit actually finds

In rough order of money, and this is the order the work gets ranked in:

- **Conversion tracking that is not telling the truth.** A primary action with zero conversions while campaigns spend. An account conversion rate above 25 to 30% for a local service, which means page views are being counted. Platform conversions more than 15% away from the client's booked jobs. A lead action left on Every counting. A GA4 import and the native tag both primary on the same form. Calls counted three ways at once. Everything below this is unsafe until it is fixed.
- **Calls not counted at all**, on a business where the phone carries half the leads. Usually the single largest number in the report.
- **Search terms that never convert**, bounded by how much of the report is visible in the first place.
- **Spend outside the service area**, which is presence-or-interest targeting left at Google's default, plus neighbouring cities that presence targeting cannot filter because the searcher is physically inside the area.
- **Search Partners and the Display Network still ticked on a Search campaign.** Display on a Search campaign has no legitimate reason for a local service.
- **Traffic landing on the homepage** instead of a page that repeats the ad.
- **Keywords that never converted** at meaningful spend, and ad groups with zero enabled ads, which serve nothing while looking healthy.
- **Broad match quietly on**, usually through the campaign-level toggle rather than the keywords.
- **Auto-apply recommendations enrolled**, which is how settings faults come back after they are fixed.
- **Bid modifiers under an automated strategy**, which cost nothing directly because Google ignores them, and cost a great deal diagnostically.
- **Negatives blocking keywords the account bids on.** Invisible in the interface: the blocked keyword shows Active with zero impressions.
- **Ad groups with one ad**, which cannot test anything, and fully pinned ads.
- **Lost impression share to budget above 10% on a campaign that is hitting target**, which is the one clean "spend more here" finding in an audit.

**How the numbers are presented.** Separate proven waste (spend that got a fair test and returned nothing) from blind spend (spend optimised against a signal that cannot see a whole lead type), mismatched spend and capped opportunity, and never merge them into one figure. Drop the trailing three to seven days for conversion lag. Exclude anything with less than 30 days of history and any campaign that changed strategy in the last two to three weeks. Assign every click to exactly one category. If the total claims more than about a third of spend is recoverable, it has been double counted. A clean account is a finding, not a failure.

**Things an audit should not say:** any headline "X% of your budget is wasted" figure, because the circulating ones have no traceable source; "raise Quality Score from 5 to 8", because Quality Score is a diagnostic and not an auction input (G), so only its three components are reportable; "raise optimisation score", because dismissing a recommendation raises it by exactly as much as accepting it; and any dollar figure at all on a read made without account access.

## For a pitch page

The default is the phase roadmap in `templates/roadmap/google-ads.html`: four
tracks named by what the client ends up with, verified before launch and tuned
after that. Change the `ROWS` and `MS` lists in the script at the bottom of that
file and the phases redraw themselves. Show order, never a delivery timeline. Use it for a build or an
ongoing account; draw a diagram instead only when the job mixes Ads with real
automation work.

The same order holds when a diagram is the right call. Four to five steps, in
this order:

1. **Measurement first.** Conversion actions, call tracking and the thank-you page, verified with a real test lead before a single ad is enabled. This node always comes before bidding, because it is the one the client has never been shown and the one every later number depends on.
2. **Structure and keywords.** Campaigns, single-theme ad groups, match types and the negative list, drawn as one step. Show it as a filter, not as a keyword dump.
3. **The landing page that matches the ad.** One page per ad group, the same words as the ad, one form, one number. Draw the arrow from search term to ad to page headline; that line is the whole argument.
4. **Launch and verify.** Everything paused until the client enables it, with the check that gates the launch named.
5. **The weekly loop.** Search terms in, negatives and new keywords out, one change at a time. Draw it as a loop returning to the structure node, not as a final box.

Terms a client recognises and should appear as labels or node notes: conversion tracking, call tracking, negative keywords, search terms report, match type, ad group, landing page, cost per lead, Quality Score, impression share, budget. Terms to keep in the notes rather than on the node: STAG, n-gram, close variants, data-driven attribution, enhanced conversions, learning phase.

Rules for the drawing: put media spend in its own node and mark it as the client's money, separate from the implementation fee. Give the failure path a node, because the missed-call or unanswered-form branch is what the client is actually buying. Mark anything you do not know yet as a "to confirm" node rather than inventing it: which CRM, which conversion action already exists, what a lead is worth. Never put a target CPA, a lead volume or a return figure on the diagram; those are unknown until the account and its conversion data exist.

## Sources

- The Automatable Ads Blueprint delivery system: account setup, keyword and STAG structure, negatives, search terms, conversion tracking, landing page blueprint, competitor intelligence and the seven-tier account audit, read 28 September 2026
- Google Ads conversion setup: https://support.google.com/google-ads/answer/16560108
- Google Ads account and ad group structure: https://support.google.com/google-ads/answer/14752782
- Google Ads keyword matching: https://support.google.com/google-ads/answer/14996023
- Google Ads search terms report: https://support.google.com/google-ads/answer/2472708
- Google Ads negative keyword lists: https://support.google.com/google-ads/answer/7449003
- Google Ads Smart Bidding: https://support.google.com/google-ads/answer/7065882
- Google Ads experiments: https://support.google.com/google-ads/answer/7281575
- Core Web Vitals thresholds: https://web.dev/articles/vitals
