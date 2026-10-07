# SEO delivery knowledge

Distilled from a maintained local-SEO pipeline and the specs behind it (keyword method, 80-check on-page list, landing-page component stack, business profile field spec, citation tiers, the CMS audit-and-fix loop), all run on real client sites, so `/pitch-page` can build a work plan and a client diagram for any job naming SEO, local SEO, a website audit or keyword research. This file is the craft: what each task actually is and what it is measured against. The sequence, internal timing guidance and acceptance logic live in `context/tool-knowledge/delivery.md` when the member has a copy, otherwise `starters/context/tool-knowledge/delivery.md`, and are not repeated here.

## The four tracks

The client-facing shape of the work is four overlapping tracks across eight phases. The editable template is `templates/roadmap/seo.html`: change the `ROWS` and `MS` lists in the script at the bottom of that file and the phases redraw themselves. Phase numbers show order, not weeks or a delivery timeline; timing notes below guide internal planning only.

| Track | Phases | What the client gets |
|---|---|---|
| **Traffic** | 2 to 7 | Found on Google and Maps |
| **Conversion** | 3 to 4 | A website built to get the call |
| **Sales automation** | 1 to 8 | Every enquiry answered and followed up |
| **Analytics** | 1 and 7 | What every lead is worth |

Framing line: **"One system across every phase."** Closing line: **"No ranking promises: the audit establishes the starting point."**

**The overlap is the point.** A plan where every track waits for the one before it hides work that can run in parallel. Four tracks is what fits a client's attention; five reads as a list and three looks thin. Every task below sits under the track it serves, and a task that serves no track does not belong in the scope.

---

# Track 1 · Traffic (phases 2 to 7)

**"Found on Google and Maps."** The widest track, and the one that carries the search craft: what the site is, what it says, and whether either surface can see it.

## What the audit finds, in order

1. **Inventory, distrusting the sitemap in both directions.** Read robots.txt rather than guessing the sitemap location. Check both failure modes: pages reachable but unlisted, and listed URLs that are not the canonical address, since a whole sitemap can name the wrong host and redirect every entry. Derive structure from path depth, never from a name ending. Diff a crawl against the sitemap, test sibling path segments, fetch every listed URL, and read canonical and robots meta on everything found outside it. One thing no script replaces: screenshot the navigation and hold it against the sitemap.
2. **Judgment, which is where audits go wrong.** A measurement is not a finding. Two questions before anything goes in red: what does this cost the client, in their words, and what measurement would prove it. If the measurement cannot be named it is an observation. Red means broken and costing something today.
3. **The state of a page is part of the finding.** "Page missing" and "page exists and does not rank" have different costs and different fixes. Drawing both as missing sells work already paid for.
4. **Every keyword belongs to a page type.** The company name belongs to the home page and is worthless for new customers but is not an error; industry plus place belongs to the location or home page, and ranking badly means an existing page is losing; service plus place belongs to the leaf page, and ranking badly is a real gap; service plus region means the local version is missing. "Everything is missing" is almost always wrong.
5. **Report what was checked and found healthy too.** An audit that shows only defects loses the room. Never state indexation without Search Console: absent from the sitemap does not mean absent from the index. And never state the full grid as a target, since every service times every city is not a plan.

## The keyword work

| | Volume | Difficulty | Intent | Also required |
|---|---|---|---|---|
| Blog, informational | 100 or more per month | 30 or less | informational | hub carries 4 or more spokes, no upper cap |
| Service, money page | more than 30 per month | no filter | transactional | a real cost per click |

A real cost per click is the money-page filter that matters: someone paying for ads has proven money is there. **Sort the two lists differently:** money-page candidates by cost per click descending, blog candidates by volume. A keyword pulled from ads data may legitimately lack a difficulty score; do not drop it for a missing field when volume and intent are clear.

**A cluster is one page: 1 primary plus 4 secondary keywords.** The primary is the highest volume and becomes the title and H1; the secondaries become the H2 sections. **Hub and spoke is one hub plus four or more spokes, each spoke its own page.** Secondaries on a money page must be transactional too (`near me`, `emergency`, the city, `service`, `company`), never cost or how-to phrasings, which belong to the blog. "Near me" never gets its own page, which reads as spam, but is fine as a secondary inside a location page's cluster.

**Coverage, when the source is a per-seed API rather than a bulk keyword tool:** at least one seed per service-by-area combination, plus one seed per cross-cutting theme (trust, legality, regional rules), because those belong to no cell of the grid and otherwise fall through. Use a generous result limit; a narrow query feels complete and is not. Clean and cluster only after the full round. Never seed with the client's own vocabulary, which often has near-zero volume.

**Competitors: ask first, search second.** The owner knows who the real ones are; an algorithm returns forums, city-data sites and large platforms. Check every candidate's homepage for a comparable business model before its keywords enter the pool.

**Exclusion categories**, each from a real false positive: DIY, education and "how to become", salary, jobs, free or cheap, wholesale and parts, bare head terms (excluded on exact match only, so qualified variants survive), unrelated industry, wrong state or region, brand and navigational queries (only visible at a high result limit), off-topic drift, listing intent, and stray street addresses.

**Difficulty is a number, not a truth.** In niches dominated by government or institutional pages it comes back near zero while the real result page is all official domains. Low difficulty plus an unusual niche means running the live check anyway.

**Six checks no script can make, run on the top five of the priority list; two errors in the sample means sweeping the whole list:**

1. **Live results check, the most important.** Search the primary keyword and ask whether what ranks is what we would build. A tool saying "informational" against ten product pages is wrong, and it fails the other way just as often: in one measured batch of 29 keywords tagged non-informational, 22 were false alarms, the top ten full of plain explanatory articles. The test is whether another format truly dominates or an article still ranks among them. If only calculators, marketplaces and form downloads rank, it is not a blog topic.
2. **The real cannibalization test**, the shared-URL count below, not just a duplicate scan.
3. **Against the client's existing inventory.** Their pages exist even when we did not build them. Ranking against yourself is the finding.
4. **Read the cluster out loud.** Would one page honestly answer all five? "That needs two pages" means two pages. Same for a hub: do the spokes hold one topic or were they padded?
5. **Relevance probe.** "How to become a plumber" passes every numeric filter and is worthless. Who types this, and do they buy?
6. **The reversal test.** What would this searcher be disappointed not to find here? If that cannot be answered in a sentence, the keyword is understood too shallowly and the page will be too.

**Priority order for the build queue:** lowest difficulty first, then highest volume, then transactional before informational, every hub above its spokes.

## Cannibalization

**What it is:** two or more pages of one site competing for one query, so neither consolidates the signals it needs. Title similarity is not cannibalization: the same phrase for two different cities looks related and competes for nothing, because nobody searches both cities at once.

**The planning test, and it is the single most important rule in the keyword method.** For any two candidate keywords that sit close together, search both and count the shared URLs in the top ten. **Three or more means one page**, so the weaker term becomes a secondary in that page's cluster. **Zero or one means two separate pages.** This replaces deciding by feel and is cheap enough to run on every close pair.

**The measurement test, on a site that already exists.** Pull query-and-page pairs from Search Console and keep a query only where at least two pages each carry real impressions for it. Working thresholds: **5 impressions per page per query and 20 across the group**; below that it is noise. Two filters run first: `site:` operator queries, which match every page of the domain and otherwise top every report, and brand queries, where several pages ranking is normal. Contested queries then join into groups transitively, and each group gets a leader: the page with the best impression-weighted average position, ties broken on total clicks. That leader keeps the topic.

**The fixes, in order of preference:** cluster the loser as a secondary on the leader; or separate the intent by rewriting title, H1 and opening; or merge and redirect the old URL onto the leader; deletion is last and needs sign-off. **Ownership decides ties:** service pages own transactional terms, blogs own informational ones. If a term fits both, the service page wins and the blog links to it. An overlap with a page the client already owns gets reported, not resolved by us. **No merge and no deletion without Search Console:** keyword tools do not see the long tail below their volume floor, so "no ranking visible, delete it" is systematically wrong.

## Site architecture

**Money pages are nested, never flat:** `/services/<service>/<city>`. The gain is not the slash, it is that `/services/<service>/` exists as its own page and can rank for the service without a city.

```
/                               home: main service plus main city, form and phone on the page
/services                       index of all services
  /services/<service>           hub: one service plus its cities
    /services/<service>/<city>  leaf: the money page
/locations/<place>              name, address, phone, one form. Nothing else
/blog                           index
  /blog/<topic>-guide           hub
  /blog/<question>              spoke, links up to the hub and out to the money page
  /blog/author/<name>           author page, required for experience signals
/about  /contact                plus optional /reviews and /case-studies
```

**Location pages exist only when customers physically come to the business.** If the business drives to the customer, the address lives in the footer and there are no location pages. Where they exist they carry name, address, phone and one form, and deliberately do not link to service pages, or they become a second sales page.

**Pick one stack and live with it.** Never both `/services/<service>/<city>` and `/locations/<city>/<service>`: the same results at two addresses. Keep the service stack; location pages then target no service keywords at all and cannot cannibalize.

**Four rules that do not bend:** at most three clicks from home to any page; nested not flat; every page linked from somewhere, since an orphan is effectively invisible; and roughly 10 to 400 money pages, starting around 50. Publish paced rather than in bulk, which is a suspension-avoidance rule and not a style choice.

**The blog is deliberately flat.** Money pages carry hierarchy in the URL; the blog carries it in the links, hub and spokes as siblings under `/blog/`. A post can change hubs or belong to two, and a link can be re-hung while a URL cannot without a redirect.

**A CMS generates pages nobody created.** Tag, date and search archives go to noindex; attachment pages redirect to their parent; the generated author archive is switched off on a single-author blog, which is not the author page itself; category archives survive only where the category is a real hub topic with an introduction; paginated pages canonicalize to themselves, since sending them all to page one hides the older posts. On a grown site this is quickly a thousand indexed pages with no value, and it is an audit finding, not a footnote.

**Static generation on a new build.** Client-side rendering is the one technical line the source draws without qualification: pages that render in the browser are not a reliable way to get indexed.

**City pages are never clones.** Same template, different content: different angle, different images, local details, local proof. The test that works is reading two finished city pages side by side; if the difference is not immediately visible, they are doorway pages.

## The 80 on-page checks

Fifteen categories, scored per category with a counter (`Head and metadata 8/8`). About 30 are decided from the draft, 26 need the delivered HTML and count as open rather than failed when it is missing, and 24 stay judgment and are reported by name. A finding without a location is worthless: each red line names where it sits and the smallest edit that fixes it.

- **Head and metadata (8):** title 50 to 60 characters with the primary keyword near the front; one title, unique site-wide; meta description 140 to 160 characters written for the click, primary keyword once; canonical to this page's own clean URL; viewport, `lang` and charset present.
- **URL (5):** short, lowercase, hyphenated; keyword in the slug; no dates, IDs or junk parameters; folder mirrors the site map; the URL stays stable, since changing it later costs a redirect.
- **Headings (5):** exactly one H1 containing the primary keyword; H2s mapping to the subtopics the top three cover; cluster variants in H2 and H3 naturally; no skipped levels; no stuffing.
- **Keyword placement and intent (5):** primary keyword inside the first 100 words; format matching what the live results reward; variants through the body; the page answering the real question rather than containing the phrase.
- **Content depth (6):** length within about 20 percent of the top-three average, no padding; everything the winners cover plus at least one thing they miss; original information gain from the client's own numbers and jobs; reads out loud like a person wrote it; no filler intro.
- **Images (6):** descriptive alt text under 125 characters; at least one genuine photo or screenshot; WebP, aiming under about 100 KB each; width and height set against layout shift; descriptive file names; lazy loading below the fold but never the hero image, which gets high fetch priority.
- **Internal links (5):** 3 to 5 in the body; descriptive anchors, never "click here"; pointing at money pages; at least one link up to the hub; none broken.
- **External links (4):** high-authority original sources; every statistic citing the original, never the article that quoted it; no spam neighborhoods.
- **Open Graph (5):** `og:title`, `og:description`, `og:image` at 1200x630, `og:url`, `og:type` and the X card tags.
- **Structured data (5):** the right type for the page (Article, LocalBusiness, Service, Product, Review); organization or local-business markup carrying the same name, address and phone; author markup linked to a real author page; validates without errors; `sameAs` to real profiles.
- **FAQ (4):** a block answering the questions the research surfaced, phrased the way people search, kept as text. FAQ and how-to rich results were switched off in May 2026: the markup triggers nothing now, the text is still read.
- **Extraction layer (6):** every question-style H2 followed by a self-contained 40 to 60 word answer; answer before explanation; key data in clean comparison tables rather than prose; the related entities the winners share; first-person action language where true.
- **First-hand proof (6):** a named author with a real bio, never "Admin"; at least one original photo or dataset from real work; checkable numbers instead of adjectives; visible trust signals such as a license number and years; links to author, about and contact; honest claims, since one fabricated testimonial poisons the page.
- **Page experience (6):** responsive, fast, HTTPS, no layout shift, crawlable and indexable, in the sitemap and internally linked.
- **Accessibility (4):** short paragraphs, sufficient contrast and font size, descriptive link text and tab order, natural reading level.

Two judgment checks outrank the other seventy-eight: does the page answer what someone actually typed, and does it carry information the top three do not have. Optimizing to 80 of 80 is a trap; some checks conflict at the edges. **A real refresh re-ranks in roughly two to four weeks; changing only the published date does nothing and is explicitly debunked.** Worth checking although the list dropped them: favicon and touch icon, and no stop words in the slug.

## Titles and descriptions

Two titles can both pass the mechanical rules and only one gets clicked, so the generator writes **two or three variants per page and a human picks**. Formulas that carry their weight: number plus keyword plus promise; keyword, colon, benefit; how-to plus outcome without the pain; keyword plus a bracketed modifier; the searcher's literal question plus a concrete payoff; and the real-proof angle, what a real number of real jobs taught us. Keep the keyword in the first word or two, front-load the message so truncation cannot eat it, and keep title and H1 on the same topic, which is the strongest defense against having the title rewritten. Description formula: action verb, primary keyword near the front, the specific contents, one clear call to action. What kills click-through: misleading clickbait, stuffing, truncation past 60 and 155 characters, duplicate titles across location pages, and burying the keyword at the end.

## Internal linking

An index file lists every page with title, URL, type, a two-sentence summary and tags; the run reads the index, so the quality of the summaries decides the quality of the linking. Relatedness is judged by meaning, not shared words. Authority flows toward money pages and genuinely related posts, never from body copy to home, about or contact, which need no authority and only give it away. Money pages carry few outgoing links, which is a conversion argument rather than an SEO one: someone on the money page should not be led away. Anchors are natural words naming the target's topic. Density is about **one link per 250 words**. The run skips links that already exist, so it is safe on every publish, and it ends with the orphan sweep: any page with no inbound link gets one from the most genuinely related page.

## The Maps half: profile, categories, citations

**Proximity is the largest display factor and is entirely outside anyone's control.** Say so early and optimize only what can be influenced.

- **Primary category** is the biggest controllable lever: it decides which pack the business competes in at all. Take it from the top-ranked competitors in the same trade, then verify against the live autocomplete, because category lists come from third parties and get invented by a model. **Search volume is irrelevant for categories.** Fill all nine secondary slots with categories that are genuinely true.
- **Services: 30 to 50**, each description keyword-rich and at most 300 characters, naming the service plus the city plus one differentiator. **Here volume does count, checked with the main city, never a suburb.** A service with no volume does not go on the list. Where the taxonomy is coarse, the long tail is captured through granular service names.
- **Description: 750 characters**, and the first 100 are what shows before "see more", so the main service and the city belong in the first sentence. No URLs, no stuffing.
- **Hours are a ranking lever**, because the "open now" filter can hide a profile outside its stated hours. Mark 24/7 only if someone genuinely answers.
- **Service area:** up to 20 places, only for businesses that travel, none beyond a **two-hour drive**, which is a suspension trigger. Arbitrary cities across the country are the classic reason a profile gets pulled.
- **Attributes,** in particular identity attributes. Small lever, costs nothing, must be true. **Photos** by category, real business photos first, AI-generated second, stock as a last resort, with a monthly upload target. **Products** raise click-through on views the profile already has; they do not create impressions. **FAQ content goes on the website**, not into the profile's question section, which is being retired.
- **The straight-face rule:** no category, service or service area added just to fill a field. A suspended profile costs more than a half-full one. **Never stack profiles:** each needs its own verified address, and the real damage is diluting reviews across thin listings.

**Citations:** name, address and phone **byte-identical everywhere**, one spelling, one abbreviation style, one phone format, one URL form. One inconsistency reads as a different business. **Thirty to fifty consistent citations beat three hundred messy ones.** Tiers: universal (the profile, Apple Maps, Bing Places, Yelp, Facebook, Instagram, LinkedIn, Foursquare, Yellow Pages, Better Business Bureau), general authority (chamber of commerce, Nextdoor, MapQuest and the free general directories), the data aggregators, which feed dozens of downstream sites and save most of the manual work, then industry-specific and city-specific listings, which are worth more than another generic one. Never buy bulk citation packages, and re-audit consistency quarterly.

## Technical: fix at the layer that renders

Fetch the live HTML, check whether the SEO plugin's signature is even in the head, compare stored values against served ones, then find the renderer: a page builder, a custom template, a hook, custom code that exits before the head is built, or a static file. **Map every render path before editing**, because sites routinely have several and fixing one leaves the rest broken. Run one caching layer, not two. Leave CSS and JS combining and async off unless tested, since they break page builders. Watch quote style when pattern-matching the head: single-quoted attributes make a double-quote check report a missing tag that is right there. Mobile performance only; comparing a desktop score against a mobile one means nothing, and several passes are normal.

**Do not automate:** thin-content calls, alt-text wording, deleting pages, slug renames, and anything where the fix is editorial. Inherently short pages such as contact, terms and privacy will always trip a word-count check; flag them, never pad them.

**Redirects are the expensive mistake.** Every old address redirects to exactly one new address, or the accumulated link value is gone and the page falls out of results for weeks to months. Decide the mechanism before the first rename, because a CMS does not create a redirect when a page is renamed: the old address is a 404 the moment it is saved, and the migration list is built for nothing if this is unresolved. Noindex plus canonical is the reversible intermediate step for anything that might be deleted.

---

# Track 2 · Conversion (phases 3 to 4)

**"A website built to get the call."** Ranking without conversion is traffic into the bin, so this track is scored separately from the on-page list.

Eighteen components plus a seventeen-item launch checklist, from years of paid testing. Eight are countable from the page, ten stay judgment. **Page type decides one component outright:** an ad page carries no header and no footer, because it has one job and every menu item is a paid exit; an SEO page keeps both for the internal linking and the visitor who wants to look around.

The components: founder video near the top; three credibility bullets above the fold; a call to action above the fold and in every major section, about eight times on desktop; one strong offer above the fold; a wall of recognizable logos; video testimonials, the single largest trust lever, target nine; three selling points specific to this business, repeated in every section; short copy, mostly bullets; a stated and repeated response time, where a number in seconds beats any adjective; twenty or more written testimonials with real first names and dates; a form with a few qualifying questions; a lead magnet for filling it in; proof badges, repeated; the header and footer rule; case studies or portfolio matched to the business type; one inspiration screenshot for style only; one sticky bottom call to action on mobile instead of many inline; and copy that is social proof, results and benefits rather than features.

**The offer is the highest-leverage element and is never guessed.** Two shapes: a result with a number and a timeframe, optionally with risk reversal, or, where no honest number fits, naming the fear of choosing wrong and flipping it to the outcome. Research the niche, and if that is not conclusive, ask the owner.

The launch checklist adds a second form at the bottom, an email-capture popup, an urgency and objection-handling close, and a thank-you page after submit. Every case study takes the form `[what] for [whom], [result with a number] in [timeframe]`, and an entry missing one of the four parts is dropped rather than softened.

**Two things the on-page list lost and money pages need:** opening hours on the page, and the address with an embedded map. Both feed name-address-phone consistency and the map pack, so this track hands work back to Traffic.

**Calibrate before applying it.** The stack was written for cold paid traffic, one goal, a large decision. On a contact page with a warm visitor a lead magnet is in the way, and urgency on an evergreen page ages badly. Three questions set the strictness: how cold the visitor arrives, how many jobs the page has, how big the decision is. **The conversion rate quoted with this stack is the author's own result, not a benchmark to repeat to a client.**

**When a business says it has no proof, it usually has proof it does not recognize.** "Do you have testimonials" gets a no; "is there any recording where a customer said something nice" gets a yes. Run that catalog before writing "no proof" as a finding.

---

# Track 3 · Sales automation (phases 1 to 8)

**"Every enquiry answered and followed up."** The longest track, because it starts before anything is visible and is still running at handover. It covers everything that happens to a lead after the form, and everything that happens to a customer after the job.

**Reviews are the hardest and most effective part, and they decide position inside the pack the category put you in.** Below about **10 reviews** a profile barely shows, so the first job is reaching ten. After that velocity matters more than the total: roughly **8 new reviews per month**, because fifty in one month and none afterwards reads as a business that stopped trading. The target band is **4.7 to 4.9**, and four-star reviews are deliberately not filtered out, since a flawless five across twenty-five reviews reads as fake. Requests go out after every completed job, through the client's own CRM by email or text. Replies to four and five stars can be drafted at scale; one to three stars is answered by hand, because an automated reply to a furious customer makes it worse.

**The compliance line, and it belongs in the proposal rather than in a surprise later:** routing only happy customers to the public review link is review gating, which breaches the platform's own review policy and is an advertising-law issue in the US. The compliant version gives everyone the same link and uses the satisfaction question as a prompt, not a filter. Keep that branch in one place so it can be switched in one move.

**Profile posts belong to this track, not to Traffic.** They do not raise visibility directly; they convert views the profile already has, and they work indirectly four ways: engagement signals relevance, posts can be pulled into AI summaries, three months of silence can read as closed, and a post matching the query can earn a badge on the map listing. Cadence is **one to two posts per week, never daily**, because consistency beats volume and daily posting reads as spam. Lengths: an offer 25 to 50 words, an event 30 to 60, an announcement 30 to 80, a story 100 to 200. Plain text only, title 60 to 80 characters, the first 100 characters carrying the hook, an image at 1200x900, a call-to-action type, and a local reference baked in. A sensible monthly mix at two per week is about half offers, a third updates, the rest events and product spotlights.

**Two honesty rules for scoping this track.** A stated response time is the client's staffing promise, not ours: we deliver the routing, never the person who picks up. And posting or review automation built from scratch is a build project in its own right, so either post manually at one to two a week or connect it to the CRM the client already pays for, and say in the proposal which one it is.

---

# Track 4 · Analytics (phases 1 and 7)

**"What every lead is worth."** Two short bars on purpose: freeze the numbers at the start, compare them at handover. It is the smallest track and the one that decides whether anything else can be proved.

**The first phase is the baseline,** dated and written down with its source. Without it the closing report shows activity instead of gain, and this is the step people skip. It also sets the do-not-touch list.

**Search Console is a gate, not a nice-to-have.** It is the only source for which page sits just off page one, and it is what makes merges, deletions and prioritization decidable at all. Contradictions between two modules of the same report get reported, not smoothed.

**What is honestly claimable in a short window:** orphan pages fixed, internal link density before and after, indexed pages, crawl errors, load time, form enquiries, and impressions on the reworked pages measured against a control group of untouched ones. Traffic alone is not the headline in a six-week window, because season, algorithm updates and the client's own publishing are each larger than the effect being measured.

**The cheapest measurable win, and it touches nothing:** filter Search Console for positions four to eight with high impressions and a poor click rate. Those pages are already ranked and simply not being chosen. Rewrite the titles and measure for two to four weeks. Small, reversible, and it shows up.

---

## For a pitch page

Draw the four tracks, with the outcome in the client's words, and let the phase bars overlap. Show no delivery timeline. Drop a track only when it is genuinely out of scope, and say so rather than silently shortening the plan.

1. **Traffic, phases 2 to 7.** "You get found on Google and Maps: the pages people actually search for, built and fixed so both can see them."
2. **Conversion, phases 3 to 4.** "Your website is built to get the call, with your proof on the page and one obvious next step."
3. **Sales automation, phases 1 to 8.** "Every enquiry gets answered and followed up, and reviews keep coming in after every job."
4. **Analytics, phases 1 and 7.** "You know what every lead is worth, measured against the numbers we froze at the start."

The branch that matters on almost every SEO job is what happens to the old URLs; the second is what the client has to supply. Draw the redirect decision with both edges labelled, and draw the client-owned inputs (their CMS, their proof, their profile access, the verification wait, approval before publishing) as their own nodes rather than as steps.

Terms a client recognizes without explanation: money pages, service area, business profile, reviews, redirects, site speed, mobile, what people actually search for, and where their enquiries come from. Terms that belong in a node note instead of on the diagram: canonical, schema, crawl budget, hub and spoke, cannibalization, first-hand experience signals, core web vitals. Cannibalization reads to a client as "two of your own pages compete for the same search, so neither one wins it".

Keep the closing line: **no ranking promises: the audit establishes the starting point.** Never show a volume, a difficulty score or a traffic estimate as promised demand, never put a position or a date on results, and never repeat the click-share percentages that circulate in this field, which have no primary source behind them. What the page shows is the work, its order, and what the client has to decide.
