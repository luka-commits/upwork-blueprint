// The shape of one client proposal - the 7-section spec plus the visual
// evidence layer. Stored as one JSONB row per client in Supabase's
// `proposals` table (this interface IS the contract for that column) -
// never a file in the repo.
// Hard rule everywhere: an exhibit whose data failed to pull is null, and the
// section says which number is missing. Never a decorative fake.

/** How much weight a number carries. Four classes, and the difference between
 * them is the whole point: a figure we measured, a figure someone else
 * published, a conclusion we drew, and a hole we could not fill all look
 * identical on a page unless they are marked.
 *
 * "vendor" is the one worth staring at. A company selling into this trade
 * reporting its own conversion rate is marketing, and next to a government
 * statistic it looks exactly as solid. */
export type Belegklasse = "measured" | "researched" | "inference" | "gap";
export type Vertrauen = "official" | "industry-survey" | "vendor" | "estimate";

/** One source, registered once and referenced by id from every figure that
 * rests on it. A central register rather than a source field on every number:
 * the same audit pull feeds a dozen figures, and repeating its URL twelve times
 * is how twelve copies start disagreeing about its date. */
export interface Quelle {
  /** Short, stable, referenced from figures: "gbp-scrape", "semrush-2026-08". */
  id: string;
  klasse: Belegklasse;
  /** What it is, in words an owner reads: "Your Google profile, pulled by us". */
  name: string;
  /** Where it can be checked. Absent for our own pulls, required for anything
   * published by someone else. */
  url?: string;
  /** JJJJ-MM-TT. A figure without a date ages invisibly. */
  stand: string;
  /** How many things it covers, where that makes sense. */
  n?: number;
  /** Only for researched figures. Absent means unclassified, which the checker
   * treats as a defect: an unlabelled vendor number is the failure mode. */
  vertrauen?: Vertrauen;
  /** What this source does NOT prove. Often the most useful line on the page. */
  grenze?: string;
}

/** Attached to any figure that rests on a source. `quelle` names an id from the
 * register; `klasse` may narrow it, e.g. an inference drawn from a measured
 * pull. */
export interface Belegt {
  quelle?: string;
  klasse?: Belegklasse;
  /** Only for an inference: what it was drawn from, in one line. */
  basis?: string;
}

/** One link in the chain a visitor has to pass to become money. */
export interface ChainLink extends Belegt {
  /** "Storefront", "Visibility", "Lead response", "Follow-up", "Reporting". */
  name: string;
  /** What the link does, three or four words. */
  does: string;
  /** 1-100, or null when nothing about it is visible from outside. */
  score: number | null;
  /** What we found. With a null score this carries the whole verdict,
   * e.g. "No CRM found". */
  readout: string;
  /** false = scored from what is verifiable from outside, not measured.
   * The honesty note under the chain says so, and it is what makes the
   * measured numbers above it credible. */
  measured: boolean;
  /** true = we have no data on this link, which is ignorance on our side and
   * not a failure on theirs. Such a link leaves the overall average; an absent
   * thing ("no CRM found") scores zero and stays in it. */
  unknown?: boolean;
  unknownLabel?: string;
}

/** The chain. Replaces the four pillars where it is present: five links in
 * order beats four equal boxes, because it shows that the weakest one makes
 * the rest worthless. */
export interface Chain {
  overall: number;
  links: ChainLink[];
  /** Which links are measured and which are scored from outside. */
  honestyNote: string;
  /** The line that lands it, e.g. "You need all five." */
  verdict: string;
}

export interface ScorePillar extends Belegt {
  name: string;
  /** 1-100. null = honestly not applicable (shown unscored, with the reason). */
  score: number | null;
  reason: string;
}

/** The dials. Raw numbers, never formatted strings - the client turns these on
 * the page and every money figure recomputes, so the estimate becomes theirs
 * instead of ours. Absent = the page falls back to the written MoneyMath. */
export interface Assumptions {
  /** Their visits from Google per month, from the traffic pull. */
  visitsPerMonth: number;
  /** Of those, the share landing on money pages. Informational readers are
   * counted at a tenth of that, same as the audit does it. */
  serviceShare: number;
  /** Visits that turn into an enquiry, 0-1. */
  clickToLead: number;
  /** Enquiries that turn into a job, 0-1. */
  closeRate: number;
  /** What one job is worth to them. Asked on the call, never an industry average. */
  jobValue: number;
  /** The traffic the leading competitor pulls, for the visibility gap. */
  // Kept as the fallback for a client whose money search we could not price.
  competitorVisitsPerMonth: number;
  /** Deprecated input kept for old proposal rows. Country-level volume no
   * longer drives predicted visits or revenue. */
  searchVolume?: number;
  /** That search, so the page can name it beside the number. */
  moneyKeyword?: string;
  /** Where they currently rank for it, if at all. Absent means not in the top 20,
   * which means they get nothing from it. */
  moneyPosition?: number;
  /** Estimated visits earned by the currently ranking service page. Unlike
   * country-level keyword volume, this can drive the opportunity model. */
  rankingPageVisitsPerMonth?: number;
  /** The share of the ranking page's visits this client would realistically
   * take, 0-1. Until 31.08.2026 the model had no such factor, which silently
   * assumed the client captures every one of a competitor's visits and made
   * the headline figure an upper bound presented as an expectation. A visible
   * dial is the honest form: the assumption is on the page and the client can
   * argue with it. Absent on older rows, where CAPTURE_SHARE_DEFAULT applies. */
  captureShare?: number;
  currencySymbol: string;
}

/** One of the 15 conversion elements, as `code/pull_cro.py` measured it. */
export interface CroElement {
  key?: string;
  label: string;
  present: boolean;
  /** What its absence costs. Only shown for the missing ones. */
  consequence: string;
  /** False when the check does not fit how this business wins customers: a
   * café needs no enquiry form or reply-time promise. Rendered grey and kept
   * out of the score. Omitted means true. */
  applies?: boolean;
}

/** The real mobile paint, frame by frame, from PageSpeed Insights. */
export interface CroSpeed {
  lcp: string;
  score: number;
  /** The four official mobile Lighthouse category scores. Older rows may only
   * carry `score`, which is the performance score. */
  scores?: {
    performance?: number;
    accessibility?: number;
    "best-practices"?: number;
    seo?: number;
  };
  /** The finished page as one tall phone screenshot, beside the strip. */
  screenshot?: string | null;
  /** A compressed full-page desktop capture used for the current-page versus
   * proposed-structure comparison. The phone capture remains separate. */
  desktopScreenshot?: string | null;
  frames: { ms: number; file: string }[];
  /** The consequence line under the strip, with its source named. */
  note: string;
}

export interface CroExhibit {
  elements: CroElement[];
  have: number;
  total: number;
  /** null when the PageSpeed run failed - the section then says so. */
  speed: CroSpeed | null;
  /** One line: traffic is not the problem, the leak is. */
  read: string;
  sourcesLine: string;
}

/** The four search exhibits, in the order they argue: how far behind, where
 * the little traffic they have lands, what they actually rank for, and how the
 * map pack compares on reviews. Every list may be empty - an empty list means
 * the pull did not run, and the block says so instead of rendering a stub. */
export interface SearchDetail {
  /** e.g. "33x behind" - the leader's traffic against theirs, one badge. */
  behindLabel?: string;
  behindLine?: string;
  /** Where their existing visits land. Money = a page that sells. */
  landingPages: { path: string; kind: "money" | "info"; visits: string }[];
  /** What they rank for today. Position drives the bar length. */
  keywords: { keyword: string; kind: "money" | "info"; position: number }[];
  /** What the website itself ranks for in normal Google results: how many
   *  searches on page one, the strongest five, and whether all of it is the
   *  business's own name. */
  organic?: {
    total: number;
    pageOne: number;
    brandOnly: boolean;
    top: { keyword: string; position: number; volume: number | null; brand: boolean }[];
    /** The client's site on the same measure as the winners' sites. */
    clientKeywords?: number;
    clientVisits?: number | null;
    /** The map winners' websites: searches ranked, on page one, estimated visits. */
    winners?: { name: string; domain: string | null; keywords: number | null; pageOne: number | null; visits: number | null; farLarger: boolean }[];
    /** Page one for the town term: who holds it, directories marked. */
    serp?: { keyword: string; pageOne: { position: number; domain: string; kind: "you" | "winner" | "directory" | "business" }[]; clientPosition: number | null } | null;
    comparable?: { name: string; domain: string | null } | null;
    /** Local searches the comparable winner holds on page one and the client does not. */
    gap?: { keyword: string; volume: number; winnerPosition: number; yourPosition: number | null }[];
    /** How many people a month type the town term: the yardstick for "what is on the table". */
    demand?: { keyword: string; volume: number; scope?: "local" | "national" } | null;
  } | null;
  /** Proposal-scale research: three searches worth targeting, not a map. */
  themes?: {
    keyword: string;
    demand: string;
    clientPosition?: number;
    surfaces: string[];
  }[];
  /** How many searches each domain shows up for at all. */
  keywordCounts: { domain: string; keywords: number; isClient?: boolean }[];
  /** The map pack on the one thing it ranks on: reviews. */
  reviews: {
    name: string;
    cid?: string | number | null;
    domain?: string | null;
    rating?: number;
    reviews: number;
    isClient?: boolean;
  }[];
  /** Named when a list is empty: which pull is missing and what it would cost. */
  missing?: string[];
}

export interface MoneyMath extends Belegt {
  /** The arithmetic, one factor per row - value plus a short label. */
  factors: { value: string; label: string }[];
  monthlyLoss: string;
  yearlyLoss: string;
  missedLeadsPerMonth: string;
  monthsToParity: string;
  /** One footnote line naming where every input came from. */
  sourcesLine: string;
}

export interface CompetitorRow extends Belegt {
  domain: string;
  isClient?: boolean;
  /** The row winning the comparison - green ground and a crown. */
  isWinner?: boolean;
  reviews: string;
  monthlyTraffic: string;
  keywords: string;
  referringDomains: string;
}

export interface Finding extends Belegt {
  /** One line: a number and what it costs them. Consequence, not diagnostic. */
  text: string;
  status: "positive" | "caution" | "critical";
  /** Written by looking at their page rather than counted by a pull, via
   * scripts/add-observed.mjs. Marked so a rerun of the generators replaces it
   * instead of stacking a second copy beside it. */
  observed?: boolean;
}

/** The search they're losing - a styled render of the LIVE SERP. Real titles,
 * real domains, real positions. Never invented, never reordered. */
export interface SerpRow {
  position: number;
  title: string;
  domain: string;
  /** Grey URL/breadcrumb line exactly as Google shows it. */
  breadcrumb?: string;
  /** The real snippet from the pull, truncated by Google itself. */
  snippet?: string;
  isClient?: boolean;
}
export interface SerpExhibit {
  keyword: string;
  /** When the live SERP opens with an AI-generated answer, name it. */
  aiOverview?: string;
  rows: SerpRow[];
  /** Shown as a band when the client is absent, e.g. "You are not in the top 20." */
  clientAbsent?: string;
  note?: string;
}

/** The visibility chart - trend lines from the traffic-history pull. */
export interface HistorySeries {
  name: string;
  isClient?: boolean;
  /** One value per monthLabel; null = no data that month (line starts later). */
  values: (number | null)[];
}
export interface VisibilityExhibit {
  monthLabels: string[];
  series: HistorySeries[];
  readout: string;
}

/** The map ranking grid - 25 real Google Maps searches, one per point.
 * ranks is row-major 5x5; null = not found at that point. A null grid means
 * no scan ran, and the note says why. */
export interface GeoGridExhibit {
  keyword: string;
  businessName: string;
  ranks: (number | null)[] | null;
  /** Real map of the scanned city behind the badges (generated from OSM tiles
   * at pull time; the frame spans the grid extent plus 25% margin). */
  mapImage?: string;
  attribution?: string;
  /** Set when the grid is a labelled demo from another market, not the client's. */
  demoLabel?: string;
  note: string;
  /** Distance from the centre to the outer points, in km, and the map zoom
   * each point was searched at (from 05.09.2026; older rows carry neither). */
  radiusKm?: number;
  zoom?: number;
  /** The competitors a customer meets first: how many of the 25 points they
   * hold a top-three spot at, from the same searches as the ranks. */
  winners?: { name: string; cid?: string | number | null; topThreePoints: number; bestRank: number | null; rating?: number | null; reviews?: number | null; category?: string | null }[];
  /** How many other businesses ever reached the top three across the grid: the depth of the field, not only its leader. */
  rivals?: number | null;
  rivalsNamed?: string[] | null;
  /** The same measure for the business itself. */
  client?: { topThreePoints: number; averageRank: number | null; rating?: number | null; reviews?: number | null };
}

/** Legacy summary shape. Kept so already-generated proposal rows still render
 * while new proposals use the complete current/prepared profile below. */
export interface GbpPanelData {
  name: string;
  subtitle: string;
  ratingValue: number;
  reviewsCount: number;
  description?: string;
  /** Real map strip of their location, shown at the top like a live panel. */
  mapImage?: string;
  attribution?: string;
  photoLabel?: string;
}
export interface GbpAuditRow {
  label: string;
  value: string;
  status: "good" | "warn" | "bad";
}

export type GbpFieldStatus = "good" | "warn" | "bad" | "open" | "new";
export type GbpFieldIcon = "address" | "hours" | "phone" | "website" | "booking" | "info";

/** A finding belongs to the exact profile field it explains. A separate audit
 * table makes owners translate between two columns and is intentionally not
 * part of the new shape. */
export interface GbpInlineFinding {
  status: GbpFieldStatus;
  label: string;
  text: string;
}

export interface GbpProfilePhoto {
  src: string;
  alt: string;
  label?: string;
}

export type GbpProfileActionKind = "website" | "directions" | "save" | "call" | "booking";

export interface GbpProfileAction {
  kind: GbpProfileActionKind;
  label?: string;
  href?: string;
}

export interface GbpProfileField {
  label: string;
  value: string;
  icon?: GbpFieldIcon;
  /** True only when the prepared view changes this value. */
  changed?: boolean;
  detail?: string;
  href?: string;
  finding?: GbpInlineFinding;
}

export interface GbpCategoryBlock {
  headline?: string;
  primary: string;
  primaryFinding?: GbpInlineFinding;
  secondary?: string[];
  secondaryFinding?: GbpInlineFinding;
  /** Trade categories the profile lacks and the website evidences: drafts for
   * the working session, each still to be confirmed in Google's own category
   * list. Never shown on the cold report. */
  candidates?: string[];
}

export interface GbpCopyBlock {
  headline?: string;
  text: string;
  finding?: GbpInlineFinding;
}

export interface GbpServicesBlock {
  headline?: string;
  items: string[];
  finding?: GbpInlineFinding;
}

export interface GbpProfilePost {
  headline?: string;
  date: string;
  text: string;
  href?: string;
  linkLabel?: string;
  finding?: GbpInlineFinding;
}

export interface GbpProfileReview {
  author: string;
  when: string;
  rating: number;
  text: string;
  /** Exact public owner response. null means the pull found none. */
  ownerResponse?: string | null;
  /** What to prepare next; never presented as an already-published response. */
  responseAction?: string;
}

/** One faithful profile state. Current and prepared use this exact same field
 * order so every proposed change can be understood without hunting for it. */
export interface GbpProfileView {
  stateLabel?: string;
  draft?: boolean;
  name: string;
  subtitle: string;
  ratingValue: number;
  reviewsCount: number;
  verified?: boolean;
  /** Only actions evidenced for this listing. A booking action is never implied. */
  actions?: GbpProfileAction[];
  photos?: GbpProfilePhoto[];
  photoLabel?: string;
  fields: GbpProfileField[];
  fieldsHeadline?: string;
  categories?: GbpCategoryBlock;
  description?: GbpCopyBlock;
  services?: GbpServicesBlock;
  photoHeadline?: string;
  plannedPhotos?: string[];
  photoFinding?: GbpInlineFinding;
  post?: GbpProfilePost;
  reviewsHeadline?: string;
  reviewsFinding?: GbpInlineFinding;
  reviews?: GbpProfileReview[];
  additionalFields?: GbpProfileField[];
  additionalHeadline?: string;
}

export interface GbpExhibit {
  /** English is the default when omitted. */
  locale?: "en" | "de";
  /** New proposal shape. Both views come from one factual source dataset. */
  current?: GbpProfileView;
  prepared?: GbpProfileView;
  /** Legacy fields below remain optional during the data migration. */
  panel?: GbpPanelData | null;
  /** The account audit: what's good and bad on the profile, field by field. */
  auditRows?: GbpAuditRow[];
  auditNote?: string;
  clientName?: string;
  clientGhost?: string;
  note?: string;
}

export interface TimelineRow {
  when: string;
  visible: string;
}

/** One bar in the build plan. Weeks are 1-based and inclusive, so {from:1,to:3}
 * fills weeks one through three. */
export interface GanttBar {
  /** What is being built, in the client's words. */
  name: string;
  /** Two letters for the card badge, e.g. "GF". Written by hand rather than
   * derived: initials off a sentence produce noise, and these read as the
   * shorthand a team already uses for the piece. */
  code?: string;
  /** Which part of the system this is - "SITE", "LOCAL SEO", "AUTOMATION",
   * "AI", "TRAINING", "HANDOVER". Drives the card's colour on the board, so a
   * client can see at a glance that they are buying four different things and
   * not four weeks of the same thing. */
  category?: string;
  from: number;
  to: number;
  /** Weeks for a package that runs this row on a different schedule. Growth
   * researches before it builds, so its website sits in weeks 3-4 where
   * Starter's sits in 2-3; without this the six-week chart repeats the
   * four-week one and tells a Growth client something the delivery plan does
   * not do. Falls back to `from`/`to`. */
  weeksByPackage?: Record<string, [number, number]>;
  /** Discrete weeks instead of a span, for work that happens on two days
   * rather than continuously. The two Claude trainings are the case: drawn as
   * weeks 2-6 they read as five weeks of training, which is a promise nobody
   * made. Overrides `from`/`to` and `weeksByPackage` where present. */
  atWeeks?: number[];
  /** Adds the package's final week to `atWeeks`, so "one session near the
   * start and one at handover" stays true on a four-, six- or eight-week
   * build without three hand-maintained copies of the row. */
  alsoAtLastWeek?: boolean;
  /** Which packages carry it. A bar outside the selected package renders
   * greyed, so the client sees what the next step up would add. */
  packages: string[];
  /** What it is worth per month, as a range from their numbers. Optional -
   * without it the row simply carries no figure rather than a made-up one. */
  worth?: string;
  /** Sits at the END of the build rather than at fixed weeks, however long the
   * chosen package runs: 1 = the final week. Handover is the case - it is the
   * last thing that happens on every package, and pinning it to week 4 drew a
   * three-week handover on the six-week plan. `from`/`to` stay as the fallback. */
  lastWeeks?: number;
  /** true = keeps running after the build, under the monthly fee. */
  ongoing?: boolean;
  /** The finding from their audit that justifies this row. */
  because?: string;
  /** The full description, for the panel that opens off the card. Two or three
   * sentences in plain words: what we actually do, and why it is done that way.
   * The card carries the one-line version; this is what gets read out when
   * somebody says "what does that mean exactly". */
  description?: string;
  /** What the client actually receives from this phase, in their words. Named
   * items, not activities: "your five service pages, written and live" rather
   * than "SEO work". This is what the call gets asked about, and a plan that
   * answers it in the room is the difference between a yes and a think-about-it. */
  deliverables?: string[];
  /** Who does it. "us" is the default and renders nothing; anything the client
   * has to supply is named here, because an unspoken dependency is the most
   * common reason a build slips. */
  needsFromClient?: string;
  /** The one checkable thing that is true when the phase is done. */
  milestone?: string;
  /** Where this row actually stands, for a client who has signed. Absent
   * before signature: a proposal shows the plan, not a status. */
  state?: "planned" | "in_progress" | "blocked" | "complete";
  /** One line on what is happening, written by whoever moved the row. */
  stateNote?: string;
  /** ISO dates from the client's own record, not from the plan. */
  dueOn?: string;
  completedAt?: string;
  /** What happened on this row, newest first, from the client's own record.
   * Turns the panel from a description of a plan into a project card: what was
   * delivered, where it is, who wrote it and when. */
  updates?: {
    what: string;
    /** The delivered thing itself, and the recording of it. */
    url?: string;
    loom?: string;
    actor?: string;
    at?: string;
  }[];
}

export interface GanttPlan {
  /** One entry per package, longest last. */
  packages: { name: string; weeks: number; price: string; recommended?: boolean }[];
  bars: GanttBar[];
  /** The honest line about when results show. */
  expectation: string;
  /** The two or three moments on the timeline worth waiting for, named in the
   * client's terms. A build plan answers "what and when"; these answer "when
   * does something change for me", which is the question behind both. */
  milestones?: {
    /** Fixed week, or the package's last week when `atLastWeek` is set. */
    atWeek?: number;
    atLastWeek?: boolean;
    label: string;
    detail?: string;
  }[];
}

export interface InvestmentOption {
  name: string;
  price: string;
  term: string;
  included: string[];
  recommended?: boolean;
  /** How many weeks the build takes on this package. More layers need more
   * weeks, and showing it next to the price is what justifies the difference. */
  buildWeeks?: number;
  /** What runs on after the build, e.g. "$499/mo, cancel anytime". */
  thenMonthly?: string;
  /** What the monthly fee actually buys, month after month. Without this the
   * monthly reads as rent on something already built, which is the single
   * commonest reason a client cancels in month three. */
  monthlyIncludes?: string[];
  /** The way out of the monthly: a one-off fee, set to the same figure as the
   * build, and they run the whole thing themselves. Pocket CEO's promise is
   * that you can fire us, so the price of doing that belongs on the page next
   * to the price of keeping us. */
  handoverFee?: string;
}

export interface InvestmentBenefit {
  icon: "go-live" | "cancel" | "guarantee" | "training" | "ownership" | "handover";
  title: string;
  detail: string;
}

export interface ProofItem {
  name: string;
  business: string;
  result: string;
  detail: string;
  /** Verbatim words from the review file - never paraphrased. */
  quote?: string;
  photoUrl?: string;
  videoUrl?: string;
  videoThumbUrl?: string;
}

export interface FaqItem {
  q: string;
  a: string;
}

export interface ProposalCopySection {
  kicker?: string;
  title?: string;
  lead?: string;
}

export type ProposalCopy = Partial<Record<
  "intro" | "findings" | "cro" | "cost" | "timeline" | "actions" | "reviews" | "faq" | "call",
  ProposalCopySection
>>;

export interface ProposalData {
  slug: string;
  /** Fixed public-report contract. Lead-specific builders may fill slots, but
   * must not select a different layout or silently omit required sections. */
  templateVersion?: "lead-magnet-v1";
  /** Lead magnets default to English. German remains a first-class render
   * option for DACH campaigns without maintaining a second template. */
  language?: "en" | "de";
  copy?: ProposalCopy;
  /** Every source this proposal rests on, registered once. Figures point at an
   * id from here; the ledger at the end of the page prints the list.
   *
   * Why this exists (Luka, 31.08.2026): "bitte die Quellen auch immer dort
   * reinpacken." Until then the proposal marked what was measured and what was
   * not, but never where anything came from. That holds until the first person
   * asks, and the first person asks in the room where the deal is decided. */
  quellen?: Quelle[];
  clientName: string;
  clientDomain: string;
  clientFaviconUrl: string;
  preparedBy: string;
  preparedByCompany: string;
  dateLabel: string;
  expiryLabel: string;
  heroLead: string;
  /** A short founder video above the fold - the fastest trust builder there is,
   * and the first thing the conversion checklist asks for. Absent renders a
   * marked placeholder rather than a broken player. */
  // Who is sending this. Never hardcoded in a component: the template ships to
  // other members, and their proposals must not carry someone else's faces.
  team?: { name: string; where?: string; photo?: string }[];
  teamNote?: string;
  // placeholder: show the empty frame anyway, for laying the page out locally.
  // Never on a row that gets sent - see the note in HeroVideo.tsx.
  heroVideo?: { url?: string; posterUrl?: string; label?: string; placeholder?: boolean; portrait?: boolean };
  /** The one-page summary image, generated after the build; absent until it exists. */
  onePager?: { url: string; generatedAt?: string; model?: string } | null;

  scorecard: { overall: number; overallReason: string; pillars: ScorePillar[]; note?: string };
  /** Present = the chain renders instead of the four pillars. */
  chain?: Chain;
  money: MoneyMath;
  /** Present = the money figures become live and the dial bar renders. */
  assumptions?: Assumptions;
  /** Present = the conversion section renders between 02 and 03. */
  cro?: CroExhibit;
  /** Present = the four search exhibits render inside the findings section. */
  search?: SearchDetail;
  findings: {
    rows: CompetitorRow[];
    /** One warning per metric where the client trails the competitors -
     * rendered as design-kit warning boxes directly under the table. */
    tableWarnings?: string[];
    tableNote?: string;
    items: Finding[];
    serp: SerpExhibit | null;
    visibility: VisibilityExhibit | null;
    /** Local companies only - null for remote/international businesses. */
    geoGrid: GeoGridExhibit | null;
    gbp: GbpExhibit | null;
    /** Named when an exhibit is null: which number is missing, what would get it. */
    missing?: string[];
  };
  timeline: { rows: TimelineRow[]; expectation: string };
  /** Set after the call: which package was discussed, where each executable
   * contract lives, and what was actually said. The client may still switch
   * packages until signature; the selected roadmap and contract must move as one. */
  agreement?: {
    packageName?: string;
    /** High-entropy path segment for the public agreement route. It is an
     * access field and must be removed before data reaches a client component. */
    token?: string;
    /** The GHL document that combines contract, signature and setup payment. */
    signUrl?: string;
    /** Package-specific GHL document forms. A missing entry disables signing
     * for that package rather than falling back to a different agreement. */
    signUrls?: Record<string, string>;
    /** Opened after successful signature/payment and repeated in the welcome email. */
    onboardingCalendarUrl?: string;
    /** Generic app login entry; the client requests their own magic link there. */
    appUrl?: string;
    /** First name, for the one line that has to sound like it was written by a
     * person who was on the call. */
    firstName?: string;
    /** What we agreed, taken from the recording rather than from memory. Each
     * entry pairs what they said with what changed because of it - a document
     * that only lists our own conclusions proves nothing about listening.
     * Written by `add-call-notes.mjs` from a transcript. */
    callNotes?: {
      /** e.g. "Recorded 30 August, 42 minutes". Naming the source is what makes
       * the section worth reading rather than worth doubting. */
      source?: string;
      items: { said: string; means: string }[];
    };
    /** Anything raised on the call that is NOT in the build. Written down here
     * on purpose: an unrecorded "we might also do X" is the single most common
     * way a fixed scope turns into an argument in month two. */
    outOfScope?: string[];
  };
  /** Five things the client can do this week without us. Derived from their
   * own measured findings, never a generic checklist. */
  actions?: {
    title?: string;
    lead?: string;
    note?: string;
    items: {
      title: string;
      /** Backwards-compatible combined explanation for older proposal rows. */
      what: string;
      /** The measured observation that makes this action relevant. */
      evidence?: string;
      /** The defect behind the evidence, when the evidence doubles as the hero line. */
      finding?: string;
      /** The concrete change to make. */
      change?: string;
      /** The plain-language business benefit of completing it. */
      benefit?: string;
      /** How long it takes and who does it, e.g. "10 minutes, you". */
      effort: string;
      /** Which drawing: profile, reviews, speed, video, gauge, form. */
      art: string;
    }[];
  };
  /** Real reviews at the foot of the proposal. They stand in for case studies
   * while there is no approved SEO result - weaker, and honest. */
  reviews?: {
    title?: string;
    lead?: string;
    note?: string;
    /** Where the reader can check them. A quote nobody can verify is a quote
     * nobody believes, so the section carries the link to the live profile. */
    profileUrl?: string;
    profileLabel?: string;
    items: { quote: string; stars: string; job: string }[];
  };
  /** Present = the build plan renders as a Gantt that switches per package,
   * and the written rows above become the fallback. */
  gantt?: GanttPlan;
  investment: { options: InvestmentOption[]; terms: string; benefits?: InvestmentBenefit[] };
  proof: { items: ProofItem[]; credentials: string[] };
  faq: FaqItem[];
  close: {
    costReminder: string;
    ctaLabel: string;
    ctaUrl: string;
    /** The booking widget, embedded at the foot of the page. Present = the
     * calendar renders instead of a button, because the times are the ask. */
    bookingUrl?: string;
  };
}
