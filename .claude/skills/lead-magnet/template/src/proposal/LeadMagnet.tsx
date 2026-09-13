"use client";

/* eslint-disable @next/next/no-img-element */

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { KAPITEL, KapitelLeiste, SektionsKopf, useAktivesKapitel } from "./lead-magnet-kopf";
import { reportProfileIcons, Check, ChevronDown } from "./service-icons";
import type {
  CroElement,
  GbpAuditRow,
  ProposalData,
} from "./types";
import { GbpPanel } from "./exhibits/GbpPanel";
import { GeoGrid } from "./exhibits/GeoGrid";
import { PlanMobile, ServiceOpen } from "./lead-magnet-offer-ui";
import { Gantt } from "./Gantt";
import { PackageProvider, usePackage } from "./packages";
import { ProposalStyles } from "./ui";
import { LeadMagnetStyles } from "./lead-magnet-styles";
import { CountUp, ReportMotion } from "./lead-magnet-motion";
import { LossesSection } from "./lead-magnet-losses";
import { SolutionSection, ZeichenProfil, ZeichenSichtbarkeit, ZeichenWebsite } from "./lead-magnet-solution";

type Locale = "en" | "de";
type SectionKey = "maps" | "profile" | "website";
type ExecutiveAction = NonNullable<ProposalData["actions"]>["items"][number];

const copy = {
  en: {
    preparedFor: "Prepared for",
    title: "How customers find you.",
    checkedTitle: "What we looked at",
    checkedWebsite: "Entire website",
    checkedProfile: "Google Business Profile",
    checkedVisibility: "Google visibility",
    summary: "Fix this now",
    stand: "Your three scores",
    overall: "Overall score",
    maps: "Local Maps",
    mapsKicker: "01 · Get found",
    profile: "Google Business Profile",
    profileKicker: "02 · Build trust",
    website: "Website",
    websiteKicker: "03 · Win enquiries",
    view: "See why",
    hide: "Close",
    test: "What we checked",
    evidence: "What the map shows",
    next: "What to change",
    testValue: "25 Google Maps searches across the service area",
    nextMaps: "Complete the profile, strengthen the page for the main service and repeat the same scan in 8-12 weeks.",
    seo: "Search checked",
    seoEmpty: "No reliable local search term was available.",
    lighthouse: "Official Google Lighthouse report",
    lighthouseNote: "Google's Lighthouse test of the homepage on a phone: lab data from one run, so two runs can differ by a few points.",
    conversion: "Website essentials",
    conversionNote: "The 15 things that help a visitor understand, trust and contact the business.",
    present: "present",
    missing: "missing",
    notNeeded: "not needed here",
    mapWinners: "Who wins the map",
    spots: "of 25 spots in the top 3",
    you: "You",
    reviewsWord: "reviews",
    fragmented: (n: number) => `No business holds more than ${n} of 25 spots here; this map is decided block by block.`,
    currentPage: "Current mobile page",
    noScreenshot: "The website was checked, but no reliable page screenshot was returned in this run.",
    leave: "Prepared for your call",
    book: "Get your roadmap",
    footer: "Private audit · not indexed by search engines",
  },
  de: {
    preparedFor: "Erstellt für",
    title: "Wie Kunden Sie finden.",
    checkedTitle: "Was wir angesehen haben",
    checkedWebsite: "Gesamte Website",
    checkedProfile: "Google-Unternehmensprofil",
    checkedVisibility: "Google-Sichtbarkeit",
    summary: "Jetzt korrigieren",
    stand: "Ihre drei Werte",
    overall: "Gesamtwert",
    maps: "Lokale Sichtbarkeit",
    mapsKicker: "01 · Gefunden werden",
    profile: "Google-Unternehmensprofil",
    profileKicker: "02 · Vertrauen aufbauen",
    website: "Website",
    websiteKicker: "03 · Anfragen gewinnen",
    view: "Warum?",
    hide: "Schließen",
    test: "Was wir geprüft haben",
    evidence: "Was die Karte zeigt",
    next: "Was zu ändern ist",
    testValue: "25 Google-Maps-Suchen im Einzugsgebiet",
    nextMaps: "Profil vervollständigen, die Seite für die Hauptleistung stärken und denselben Test in 8-12 Wochen wiederholen.",
    seo: "Geprüfte Suche",
    seoEmpty: "Es war kein belastbarer lokaler Suchbegriff verfügbar.",
    lighthouse: "Offizieller Google-Lighthouse-Bericht",
    lighthouseNote: "Googles Lighthouse-Test der Startseite auf dem Handy: Labordaten aus einem Lauf, zwei Läufe können um ein paar Punkte abweichen.",
    conversion: "Was die Website braucht",
    conversionNote: "15 Elemente, die Besuchern helfen, Angebot, Vertrauen und Kontaktweg zu verstehen.",
    present: "vorhanden",
    missing: "fehlen",
    notNeeded: "hier nicht nötig",
    mapWinners: "Wer die Karte gewinnt",
    spots: "von 25 Punkten in den Top 3",
    you: "Sie",
    reviewsWord: "Bewertungen",
    fragmented: (n: number) => `Kein Betrieb hält hier mehr als ${n} von 25 Punkten; diese Karte wird Block für Block entschieden.`,
    currentPage: "Aktuelle mobile Seite",
    noScreenshot: "Die Website wurde geprüft, aber in diesem Lauf kam kein belastbarer Screenshot zurück.",
    leave: "Für Ihren Termin vorbereitet",
    book: "Fahrplan holen",
    footer: "Private Analyse · nicht von Suchmaschinen indexiert",
  },
} as const;

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function mapScore(ranks: (number | null)[] | null | undefined) {
  if (!ranks?.length) return null;
  const points = ranks.map((rank) => {
    if (rank == null) return 0;
    if (rank <= 3) return 100;
    if (rank <= 10) return 60 - (rank - 4) * 6;
    return Math.max(5, 24 - (rank - 11) * 2);
  });
  return clampScore(points.reduce((sum, point) => sum + point, 0) / points.length);
}

/** The audit rows as the panel shows them: the panel judges the latest update
 *  and the review replies from the profile itself, so the score must count
 *  those two as "warn" too, or a 100 sits above two "Improve" rows
 *  (Access ASAP, 05.09.2026). */
function auditRowsAsShown(gbp: ProposalData["findings"]["gbp"]): GbpAuditRow[] | undefined {
  const rows = gbp?.auditRows;
  if (!rows) return rows;
  const warnUpdates = gbp?.current?.post?.finding?.status === "warn";
  const warnReviews = gbp?.current?.reviewsFinding?.status === "warn";
  return rows.map((row) => {
    if (row.status !== "good") return row;
    if ((row.label === "Updates" && warnUpdates) || (row.label === "Reviews" && warnReviews)) return { ...row, status: "warn" as const };
    return row;
  });
}

function profileScore(rows: GbpAuditRow[] | undefined) {
  if (!rows?.length) return null;
  const points = { good: 100, warn: 55, bad: 0 } as const;
  return clampScore(rows.reduce((sum, row) => sum + points[row.status], 0) / rows.length);
}

function enquiryScore(elements: CroElement[] | undefined) {
  // Checks that do not fit the business (`applies: false`) stay out of the score.
  const applicable = (elements ?? []).filter((element) => element.applies !== false);
  if (!applicable.length) return null;
  return clampScore((applicable.filter((element) => element.present).length / applicable.length) * 100);
}

function scoreTone(score: number | null) {
  if (score == null) return "border-slate-300 bg-slate-100 text-slate-700";
  if (score >= 80) return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (score >= 55) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-red-200 bg-red-50 text-red-800";
}

function profileEvidence(row: GbpAuditRow | undefined, locale: Locale) {
  if (!row?.value) return null;
  const value = row.value.trim().replace(/[.]$/, "");
  if (row.label.toLowerCase() === "reviews") {
    const numbers = value.match(/[\d.,]+/g) ?? [];
    if (numbers.length >= 2) {
      return locale === "de"
        ? `Das Profil hat ${numbers[0]} Google-Bewertungen mit durchschnittlich ${numbers[1]} Sternen.`
        : `The profile has ${numbers[0]} Google reviews with an average rating of ${numbers[1]} stars.`;
    }
  }
  return locale === "de"
    ? `Im geprüften Profil steht bei „${row.label}“: ${value}.`
    : `The checked profile currently shows this for ${row.label.toLowerCase()}: ${value}.`;
}

function websiteGapEvidence(element: CroElement | undefined, locale: Locale) {
  const key = element?.key;
  const messages: Record<string, { en: string; de: string }> = {
    lead_form: { en: "The website has no form a customer can complete.", de: "Auf der Website gibt es kein Formular, das ein Kunde ausfüllen kann." },
    form_short: { en: "The enquiry form asks for more than four things, and every extra field loses submissions.", de: "Das Anfrageformular fragt mehr als vier Dinge ab, und jedes weitere Feld kostet Anfragen." },
    form_button_says_outcome: { en: "The form's button does not say what happens next, so the last click is the vaguest one.", de: "Der Button sagt nicht, was danach passiert, also ist der letzte Klick der unklarste." },
    phone_speed: { en: "The page takes longer than two seconds on a phone, and most of the visit is spent waiting.", de: "Die Seite braucht auf dem Handy länger als zwei Sekunden, und der Besuch besteht großteils aus Warten." },
    click_to_call: { en: "The phone number cannot be called with one tap on a mobile.", de: "Die Telefonnummer lässt sich auf dem Smartphone nicht mit einem Tipp anrufen." },
    online_booking: { en: "The website offers no way to book online.", de: "Auf der Website kann derzeit kein Termin online gebucht werden." },
    response_time: { en: "The website does not tell customers when they will hear back.", de: "Die Website sagt Kunden nicht, wann sie eine Antwort erhalten." },
    social_proof_numbers: { en: "The website gives no concrete proof of how much work the business has completed.", de: "Die Website zeigt keine konkreten Zahlen zu bereits erledigten Aufträgen." },
    video_top: { en: "Customers do not see a personal introduction near the top of the website.", de: "Kunden sehen oben auf der Website keine persönliche Vorstellung." },
    video_testimonials: { en: "The website shows no customer experience in a video.", de: "Die Website zeigt keine Kundenerfahrung als Video." },
    logo_wall: { en: "The website shows no recognised customers, partners or memberships.", de: "Die Website zeigt keine bekannten Kunden, Partner oder Mitgliedschaften." },
    email_capture: { en: "Visitors who are not ready to call have no email follow-up option.", de: "Besucher, die noch nicht anrufen möchten, haben keine E-Mail-Option." },
  };
  if (key && messages[key]) return messages[key][locale];
  if (!element?.label) return locale === "de" ? "Der nächste Schritt zur Anfrage ist auf der Website nicht klar." : "The website does not make the next step to an enquiry clear.";
  return locale === "de" ? `Auf der Website fehlt: ${element.label}.` : `The website does not currently show ${element.label.toLowerCase()}.`;
}

function Score({ value, compact = false, label = "Score", id }: { id: string; value: number | null; compact?: boolean; label?: string }) {
  return (
    <span className={`lm-score tnum inline-flex shrink-0 flex-col justify-center rounded-[10px] border font-black tracking-[-0.04em] ${scoreTone(value)} ${compact ? "min-w-[84px] px-3 py-2" : "min-w-[124px] px-5 py-4"}`}>
      <small className="mb-1 text-[7px] font-black uppercase tracking-[.08em] opacity-60">{label}</small>
      <span className={compact ? "text-[20px] leading-none" : "text-4xl leading-none"}><CountUp value={value} id={id} /><small className="ml-0.5 text-[.42em] font-bold opacity-60">/100</small></span>
    </span>
  );
}

/** Das Zeichen des Betriebs: sein Logo, und wenn das nicht kommt, sein Anfangsbuchstabe.
 *
 *  DAS IST KEIN SCHOENHEITSFEHLER (gemessen 06.09.2026). Die Logos holt ein fremder Dienst
 *  ueber die Domain, und fuer manche Betriebe hat er keines -- dann antwortete er 404 und im
 *  Bericht standen drei leere Kaesten, genau neben dem Namen des Empfaengers: im Kopf, im
 *  Hero und ueber dem Abschluss. Betroffen war jeder dritte der geprueften Berichte. */
function KundenZeichen({
  url, name, klasseBild, klasseErsatz,
}: { url?: string; name: string; klasseBild: string; klasseErsatz: string }) {
  const [fehlt, setFehlt] = useState(false);
  // NACHSEHEN, NICHT NUR ZUHOEREN. Das Bild scheitert oft, bevor React seine Handler
  // angehaengt hat -- das `error`-Ereignis ist dann schon vorbei und der leere Kasten bleibt
  // stehen (gemessen 06.09.2026 an der Live-Seite, nachdem `onError` allein nichts aenderte).
  const pruefen = (bild: HTMLImageElement | null) => {
    if (bild && bild.complete && bild.naturalWidth === 0) setFehlt(true);
  };
  if (!url || fehlt) {
    return <b className={klasseErsatz}>{name.slice(0, 1)}</b>;
  }
  return <img ref={pruefen} src={url} alt={name} onError={() => setFehlt(true)} className={klasseBild} />;
}

function HeroVisual({ data }: { data: ProposalData }) {
  const video = data.heroVideo;
  // ES LAEUFT AN, ABER ERST WENN DIE SEITE STEHT (06.09.2026). `autoPlay` im Markup laesst den
  // Browser die 5,9 MB sofort ziehen und die Leitung damit besetzen: gemessen erschien das
  // Standbild deshalb erst nach zwei Sekunden, obwohl es nach 120 ms da war. Jetzt startet das
  // Video, sobald die Seite fertig geladen ist -- fuer den Empfaenger derselbe Eindruck, nur
  // mit einer Sekunde Vorsprung fuer alles andere.
  const [spieler, setSpieler] = useState<HTMLVideoElement | null>(null);
  useEffect(() => {
    if (!spieler) return;
    // Erst wenn der Browser nichts Dringenderes zu tun hat. Gemessen 06.09.2026: startete das
    // Video zu frueh, war sein erstes Bild das groesste sichtbare Element -- und das kam ueber
    // die gedrosselte Leitung erst nach 1,9 s. Wartet es, bleibt das Standbild das erste Bild,
    // und die Bewertung springt von 83 auf 95.
    let handle: number | undefined;
    const anfangen = () => {
      const los = () => spieler.play().catch(() => { /* der Browser darf nein sagen */ });
      handle = typeof requestIdleCallback === "function"
        ? requestIdleCallback(los, { timeout: 2500 })
        : window.setTimeout(los, 1200);
    };
    if (document.readyState === "complete") { anfangen(); }
    else window.addEventListener("load", anfangen, { once: true });
    return () => {
      window.removeEventListener("load", anfangen);
      if (handle === undefined) return;
      if (typeof cancelIdleCallback === "function") cancelIdleCallback(handle); else clearTimeout(handle);
    };
  }, [spieler]);
  if (!video?.url) return null;
  const title = video.label ?? `A short message for ${data.clientName}`;
  // A hosted file plays in a native player with its poster frame; anything
  // else is an embed. A portrait recording gets a phone-shaped frame instead
  // of a letterboxed 16:9 stage.
  const isFile = /\.(mp4|webm|mov)(\?|$)/i.test(video.url);
  const frame = video.portrait ? "mx-auto w-full max-w-[300px] aspect-[9/16]" : "aspect-video";
  return (
    <figure className="m-0 lg:justify-self-end">
      {/* DAS STANDBILD IST DAS ERSTE, WAS MAN SIEHT -- also wird es auch zuerst geholt.
          Gemessen 06.09.2026: der Browser entdeckte es erst nach 1,9 Sekunden, weil ein
          `poster` am Video-Element hinten in der Warteschlange steht. React haengt diese
          Zeile in den Kopf der Seite. */}
      {isFile && video.posterUrl ? <link rel="preload" as="image" href={video.posterUrl} fetchPriority="high" /> : null}
      <div className={`overflow-hidden rounded-[22px] border-[5px] border-[#30363a] bg-navy-deep shadow-[0_24px_60px_rgba(8,12,22,.2)] ${frame}`}>
        {isFile
          // AUTOMATISCH, ABER STUMM (the reviewer, 06.09.2026). Jeder Browser laesst ein Video nur
          // ohne Ton von selbst starten; mit Ton bleibt es stehen, und der Empfaenger sieht
          // ein totes Standbild. Also: laeuft an, zeigt Lukas Gesicht in Bewegung, und wer
          // hoeren will, tippt einmal auf den Ton. Untertitel sind im Video eingebrannt.
          // Der Start steht im Effekt oben, nicht als `autoPlay` im Markup -- der Grund dort.
          ? <video ref={setSpieler} src={video.url} poster={video.posterUrl} controls playsInline muted loop preload="none" title={title} className="h-full w-full object-cover" />
          : <iframe src={video.url} title={title} allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture" allowFullScreen className="h-full w-full border-0" />}
      </div>
    </figure>
  );
}

/* WARUM DIESER ABSCHNITT UEBERHAUPT ZAEHLT (the reviewer, 06.09.2026: „why this matters sollte als
 * eine Sektion über das GBP und dann die Sektion automate this darunter. Wichtig ist, dass
 * diese Sektionen auch minimalistisch sind und visuell anstatt viel Text").
 *
 * Ein Satz, ein Zeichen, sonst nichts. Wer den Abschnitt aufklappt, sieht danach eine Liste
 * von Befunden; ohne diese Zeile weiss er nicht, warum ihn diese Liste kuemmern sollte. Ein
 * Absatz an derselben Stelle wuerde niemand lesen, weil der Befund direkt darunter steht.
 *
 * Die Zahlen aus Kapitel 01 werden hier bewusst NICHT wiederholt. Dort steht, was die Branche
 * kostet; hier steht, warum genau dieser Abschnitt darueber entscheidet. */
const WARUM: Record<SectionKey, { en: string; de: string }> = {
  maps: {
    en: "Most people never scroll past the map. If you are not in it, you are not in the running.",
    de: "Die meisten scrollen nie an der Karte vorbei. Wer dort fehlt, ist gar nicht erst im Rennen.",
  },
  profile: {
    en: "This is the page a stranger checks in the ten seconds before deciding to call you.",
    de: "Das ist die Seite, die ein Fremder in den zehn Sekunden prüft, bevor er anruft.",
  },
  website: {
    en: "The website has one job: make calling you the easiest thing on the screen.",
    de: "Die Website hat eine Aufgabe: den Anruf zum Einfachsten auf dem Bildschirm machen.",
  },
};

function WarumLeiste({ sectionKey, locale }: { sectionKey: SectionKey; locale: Locale }) {
  return (
    <div className="lm-warum mb-5 flex items-center gap-3.5 rounded-2xl border border-hairline bg-white px-4 py-3.5 sm:mb-6 sm:gap-4 sm:px-5 sm:py-4">
      {/* EIN AUSRUFEZEICHEN, NICHT DAS ZEICHEN DER SAEULE (the reviewer, 06.09.2026). Das Saeulen-
          zeichen steht schon in der Kopfzeile darueber; ein zweites Mal sagt es nichts Neues.
          Das Ausrufezeichen sagt, was diese Zeile ist: der Grund, warum das Folgende zaehlt. */}
      <span className="lm-glas grid size-11 shrink-0 place-items-center rounded-[13px] text-navy">
        <svg viewBox="0 0 22 22" fill="none" aria-hidden className="size-[21px]">
          <circle cx="11" cy="11" r="8.4" fill="currentColor" opacity=".14" />
          <circle cx="11" cy="11" r="8.4" stroke="currentColor" strokeWidth="1.6" />
          <path d="M11 6.4v6.1" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          <circle cx="11" cy="15.8" r="1.3" fill="currentColor" />
        </svg>
      </span>
      <p className="m-0 text-[15px] font-bold leading-[1.4] text-slate-900 sm:text-[16.5px]">
        {WARUM[sectionKey][locale]}
      </p>
    </div>
  );
}

function Accordion({
  sectionKey,
  open,
  onToggle,
  kicker,
  title,
  score,
  secondaryScore,
  finding,
  children,
  locale,
}: {
  sectionKey: SectionKey;
  open: boolean;
  onToggle: () => void;
  kicker: string;
  title: string;
  score: number | null;
  secondaryScore?: { label: string; value: number | null };
  finding: string;
  children: ReactNode;
  locale: Locale;
}) {
  const t = copy[locale];
  const [index = "", purpose = kicker] = kicker.split(" · ");
  return (
    <section id={`report-${sectionKey}`} data-audit-section={sectionKey} className="lm-pillar scroll-mt-[76px] overflow-hidden border-t border-black/10 first:border-t-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`analysis-${sectionKey}`}
        onClick={onToggle}
        style={{ borderLeftColor: open ? "#2448ae" : "transparent" }}
        className={`group grid w-full grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-3 border-l-4 px-4 py-3.5 text-left transition sm:px-7 lg:grid-cols-[34px_minmax(0,1fr)_auto_auto] lg:gap-5 ${open ? "border-l-navy bg-blue-50/80" : "border-l-transparent bg-white hover:bg-[#fafaf8]"}`}
      >
        <span className="text-xs font-black tracking-[.09em] text-navy">{index}</span>
        <div className="min-w-0">
          <h2 className="m-0 text-[22px] font-black leading-[1.02] tracking-[-.04em] text-ink sm:text-[25px]">{purpose}</h2>
          <span data-onepager="pillar" className="mt-1.5 block text-[9px] font-black uppercase tracking-[.12em] text-pewter">{title}</span>
        </div>
        <div data-onepager="score" data-score={score} className="col-start-2 row-start-2 flex flex-wrap gap-2 lg:col-start-3 lg:row-start-1 lg:justify-end"><Score value={score} id={`score-${sectionKey}`} />{secondaryScore ? <span className={`tnum inline-flex min-w-[92px] flex-col justify-center rounded-[10px] border px-3 py-2 ${scoreTone(secondaryScore.value)}`}><small className="mb-1 text-[7px] font-black uppercase tracking-wide opacity-70">{secondaryScore.label}</small><b className="text-xl leading-none">{secondaryScore.value ?? "-"}<small className="text-[10px] opacity-60">/100</small></b></span> : null}</div>
        {/* The verdict sentence stays in the markup for the one-pager only;
            the row itself is number and button (the reviewer, 05.09.2026). */}
        <span data-onepager="finding" className="sr-only">{finding}</span>
        <div className="col-start-3 row-span-2 row-start-1 flex justify-end lg:col-start-4 lg:row-span-1">
          <span className={`inline-flex min-h-12 min-w-[132px] items-center justify-center gap-2 rounded-full px-5 text-[14px] font-black tracking-[-.01em] transition ${open ? "border border-navy bg-white text-navy" : "bg-navy text-white group-hover:bg-navy-deep"}`}>
            <span>{open ? t.hide : t.view}</span><ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
          </span>
        </div>
      </button>
      {open ? <div data-lm-motion={`panel-${sectionKey}`} id={`analysis-${sectionKey}`} style={{ borderLeftColor: "#2448ae" }} className="border-l-4 border-t border-black/10 bg-[#f4f6fb] px-4 py-5 sm:px-7 sm:py-7"><WarumLeiste sectionKey={sectionKey} locale={locale} />{children}</div> : null}
    </section>
  );
}

function WebsiteDetail({ data, locale }: { data: ProposalData; locale: Locale }) {
  const [mobileComparison, setMobileComparison] = useState<"current" | "plan">("current");
  const t = copy[locale];
  const elements = data.cro?.elements ?? [];
  const speed = data.cro?.speed;
  const lighthouse = [
    ["Performance", speed?.scores?.performance ?? speed?.score],
    ["Accessibility", speed?.scores?.accessibility],
    ["Best Practices", speed?.scores?.["best-practices"]],
    ["SEO", speed?.scores?.seo],
  ] as const;
  const notNeeded = elements.filter((element) => element.applies === false);
  const applicable = elements.filter((element) => element.applies !== false);
  const missing = applicable.filter((element) => !element.present);
  const normalizedKey = (element: CroElement) => {
    if (element.key) return element.key;
    const label = element.label.toLowerCase();
    if (/before you scroll|above the fold|first screen/.test(label)) return "cta_above_fold";
    if (/further down|repeated|again/.test(label)) return "cta_repeated";
    if (/tap to call|tappable|click.to.call/.test(label)) return "click_to_call";
    if (/form/.test(label)) return "lead_form";
    if (/book a time|online book/.test(label)) return "online_booking";
    if (/reply|response/.test(label)) return "response_time";
    if (/customer.*say|testimonial/.test(label) && /camera|video/.test(label)) return "video_testimonials";
    if (/customer.*say|testimonial/.test(label)) return "testimonials";
    if (/numbers|how much you have done/.test(label)) return "social_proof_numbers";
    if (/rating|google or trustpilot|review badge/.test(label)) return "review_badges";
    if (/video.*top|near the top/.test(label)) return "video_top";
    if (/companies|worked with|logo/.test(label)) return "logo_wall";
    if (/questions|faq/.test(label)) return "faq";
    if (/something free|guide|calculator/.test(label)) return "lead_magnet";
    if (/email/.test(label)) return "email_capture";
    return "other";
  };
  const elementLabels: Record<string, { en: string; de: string }> = {
    cta_above_fold: { en: "Clear contact button before scrolling", de: "Klarer Kontaktbutton vor dem Scrollen" },
    cta_repeated: { en: "Contact button repeated on long pages", de: "Kontaktbutton auf langen Seiten wiederholt" },
    click_to_call: { en: "Phone number starts a call on mobile", de: "Telefonnummer startet mobil direkt einen Anruf" },
    lead_form: { en: "Short contact form", de: "Kurzes Kontaktformular" },
    form_short: { en: "A form short enough to finish", de: "Ein Formular, das man zu Ende ausfüllt" },
    form_button_says_outcome: { en: "A button that names what happens next", de: "Ein Button, der sagt was danach passiert" },
    phone_speed: { en: "Loads in under two seconds on a phone", de: "Lädt auf dem Handy in unter zwei Sekunden" },
    online_booking: { en: "Online booking option", de: "Online-Terminbuchung" },
    response_time: { en: "Clear reply-time promise", de: "Klares Versprechen zur Antwortzeit" },
    testimonials: { en: "Written customer reviews on the website", de: "Schriftliche Kundenbewertungen auf der Website" },
    social_proof_numbers: { en: "Real numbers: years, jobs or customers", de: "Konkrete Zahlen: Jahre, Aufträge oder Kunden" },
    review_badges: { en: "Google or Trustpilot rating on the website", de: "Google- oder Trustpilot-Bewertung auf der Website" },
    video_top: { en: "Short introduction video near the top", de: "Kurzes Vorstellungsvideo weit oben" },
    video_testimonials: { en: "Customer video review", de: "Kundenbewertung als Video" },
    logo_wall: { en: "Customer or partner logos", de: "Logos von Kunden oder Partnern" },
    faq: { en: "Answers to common customer questions", de: "Antworten auf häufige Kundenfragen" },
    lead_magnet: { en: "Useful free guide or checklist", de: "Hilfreicher kostenloser Guide oder Checkliste" },
    email_capture: { en: "Email signup or follow-up option", de: "E-Mail-Anmeldung oder Follow-up" },
    other: { en: "Another clear next step", de: "Ein weiterer klarer nächster Schritt" },
  };
  const elementLabel = (element: CroElement) => elementLabels[normalizedKey(element)]?.[locale] ?? element.label;
  const groupSpecs = locale === "de" ? [
    { title: "Kontakt aufnehmen", keys: ["cta_above_fold", "cta_repeated", "click_to_call", "lead_form", "form_short", "form_button_says_outcome"] },
    { title: "Schnell genug laden", keys: ["phone_speed"] },
    { title: "Termin und Reaktion", keys: ["online_booking", "response_time"] },
    { title: "Vertrauen", keys: ["testimonials", "social_proof_numbers", "review_badges", "video_top", "video_testimonials", "logo_wall"] },
    { title: "Entscheiden und dranbleiben", keys: ["faq", "lead_magnet", "email_capture", "other"] },
  ] : [
    { title: "Make contact", keys: ["cta_above_fold", "cta_repeated", "click_to_call", "lead_form", "form_short", "form_button_says_outcome"] },
    { title: "Load fast enough", keys: ["phone_speed"] },
    { title: "Book and hear back", keys: ["online_booking", "response_time"] },
    { title: "Build trust", keys: ["testimonials", "social_proof_numbers", "review_badges", "video_top", "video_testimonials", "logo_wall"] },
    { title: "Decide and stay in touch", keys: ["faq", "lead_magnet", "email_capture", "other"] },
  ];
  const groups = groupSpecs.map((group) => ({
    ...group,
    elements: elements.filter((element) => group.keys.includes(normalizedKey(element))),
  }));
  const comparisonCopy = locale === "de" ? {
    current: "Aktuelle Website",
    currentNote: "So erscheint die geprüfte Seite heute",
    plan: "Prüfplan",
    planNote: "Was bleiben kann und wo der Anfrageweg ergänzt wird",
    orient: "Angebot sofort verstehen",
    choose: "Passende Leistung finden",
    trust: "Vertrauen aufbauen",
    contact: "Kontakt aufnehmen",
  } : {
    current: "Current website",
    currentNote: "The page as it appeared in the check",
    plan: "Page plan",
    planNote: "What can stay and where the enquiry path needs work",
    orient: "Understand the offer",
    choose: "Find the right service",
    trust: "Build trust",
    contact: "Make contact",
  };
  const planBlockSpecs = locale === "de" ? [
    { label: "Navigation und direkter Anruf", keys: ["click_to_call"] },
    { label: "Angebot und erste Handlung", keys: ["cta_above_fold"] },
    { label: "Leistungen und nächster Schritt", keys: ["cta_repeated"] },
    { label: "Echte Kundenerfahrungen", keys: ["testimonials"] },
    { label: "Ergebnisse in Zahlen", keys: ["social_proof_numbers"] },
    { label: "Google-Bewertung", keys: ["review_badges"] },
    { label: "Das Unternehmen kennenlernen", keys: ["video_top"] },
    { label: "Kundengeschichte im Video", keys: ["video_testimonials"] },
    { label: "Kunden und Partner", keys: ["logo_wall"] },
    { label: "Ablauf und Antwortzeit", keys: ["response_time"] },
    { label: "Häufige Fragen", keys: ["faq"] },
    { label: "Termin wählen", keys: ["online_booking"] },
    { label: "Kurze Anfrage senden", keys: ["lead_form", "form_short", "form_button_says_outcome"] },
    { label: "Hilfreicher Guide und E-Mail", keys: ["lead_magnet", "email_capture", "other"] },
  ] : [
    { label: "Navigation and direct call", keys: ["click_to_call"] },
    { label: "Offer and first action", keys: ["cta_above_fold"] },
    { label: "Services and next step", keys: ["cta_repeated"] },
    { label: "Real customer experiences", keys: ["testimonials"] },
    { label: "Results in numbers", keys: ["social_proof_numbers"] },
    { label: "Google rating", keys: ["review_badges"] },
    { label: "Meet the business", keys: ["video_top"] },
    { label: "Customer story on video", keys: ["video_testimonials"] },
    { label: "Clients and partners", keys: ["logo_wall"] },
    { label: "Process and reply time", keys: ["response_time"] },
    { label: "Common questions", keys: ["faq"] },
    { label: "Choose a time", keys: ["online_booking"] },
    { label: "Send a short enquiry", keys: ["lead_form", "form_short", "form_button_says_outcome"] },
    { label: "Useful guide and email", keys: ["lead_magnet", "email_capture", "other"] },
  ];
  const planBlocks = planBlockSpecs.map((block) => {
    const matched = elements.filter((element) => block.keys.includes(normalizedKey(element)));
    return { ...block, matched, present: matched.length > 0 && matched.every((element) => element.present || element.applies === false), missing: matched.filter((element) => !element.present && element.applies !== false).length };
  });

  const profile = data.findings.gbp?.current;
  const businessName = profile?.name ?? data.clientName;
  const primaryService = profile?.categories?.primary ?? (locale === "de" ? "Ihre Hauptleistung" : "Your main service");
  const place = profile?.subtitle?.split("·").at(-1)?.trim() ?? (locale === "de" ? "Ihrem Gebiet" : "your area");
  const serviceNames = profile?.services?.items?.slice(0, 3) ?? [];
  const review = profile?.reviews?.[0];
  const planVisual = (index: number, present: boolean) => {
    const ink = present ? "bg-emerald-500/75" : "bg-red-400/75";
    const pale = present ? "bg-emerald-50" : "bg-red-50";
    if (index === 0) return <div className="flex items-center gap-2 rounded-lg bg-slate-950 px-3 py-2.5 text-white"><strong className="max-w-[42%] truncate text-[9px]">{businessName}</strong><span className="ml-auto text-[7px] text-slate-300">Services</span><span className="text-[7px] text-slate-300">Reviews</span><span className={`rounded-full px-2 py-1 text-[7px] font-bold ${ink}`}>{locale === "de" ? "Anrufen" : "Call now"}</span></div>;
    if (index === 1) return <div className={`grid grid-cols-[1.15fr_.85fr] gap-3 rounded-lg p-3 ${pale}`}><div><strong className="block text-[12px] leading-tight text-slate-950">{primaryService}<br />{locale === "de" ? "in" : "in"} {place}</strong><p className="my-2 text-[7px] leading-relaxed text-slate-500">{locale === "de" ? "Klarer Nutzen, Einsatzgebiet und nächster Schritt." : "A clear outcome, service area and next step."}</p><span className={`inline-flex rounded-full px-2 py-1 text-[7px] font-bold text-white ${ink}`}>{locale === "de" ? "Hilfe anfragen" : "Request help"}</span></div><div className="grid min-h-20 place-items-center rounded-lg bg-slate-800"><span className="grid size-7 place-items-center rounded-full bg-white text-[9px] text-slate-950">▶</span></div></div>;
    if (index === 2) return <div className="grid grid-cols-3 gap-2">{(serviceNames.length ? serviceNames : [primaryService, locale === "de" ? "Zweite Leistung" : "Second service", locale === "de" ? "Dritte Leistung" : "Third service"]).map((service) => <span key={service} className={`grid min-h-14 content-between rounded-lg p-2 ${pale}`}><strong className="line-clamp-2 text-[8px] leading-tight text-slate-800">{service}</strong><i className={`mt-2 h-1.5 w-8 rounded-full ${ink}`} /></span>)}</div>;
    if (index === 3) return <div className="grid grid-cols-2 gap-2">{[review?.text ?? (locale === "de" ? "Konkrete Erfahrung eines echten Kunden." : "A specific experience from a real customer."), locale === "de" ? "Zweite freigegebene Kundenstimme." : "A second approved customer story."].map((text, item) => <span key={item} className={`rounded-lg p-2 ${pale}`}><b className="text-[8px] text-amber-500">★★★★★</b><i className="mt-1 line-clamp-2 block text-[7px] not-italic leading-relaxed text-slate-600">{text}</i></span>)}</div>;
    if (index === 4) return <div className="grid grid-cols-3 gap-2">{["Years", "Customers", "Response"].map((label, item) => <span key={label} className={`grid h-14 place-items-center rounded-lg ${pale}`}><b className="text-[16px] text-slate-900">{["10+", "500+", "1h"][item]}</b><small className="text-[6px] uppercase text-slate-500">{label}</small></span>)}</div>;
    if (index === 5) return <div className={`flex items-center justify-between rounded-lg px-3 py-3 ${pale}`}><span><b className="text-lg text-slate-950">{profile?.ratingValue?.toFixed(1) ?? "4.8"}</b><small className="ml-2 text-[9px] text-amber-500">★★★★★</small></span><span className="text-[8px] font-bold text-blue-700">{profile?.reviewsCount ?? "-"} Google reviews</span></div>;
    if ([6, 7].includes(index)) return <div className={`grid grid-cols-[.9fr_1.1fr] gap-3 rounded-lg p-2.5 ${pale}`}><div className="grid min-h-16 place-items-center rounded-lg bg-slate-800"><span className="grid size-7 place-items-center rounded-full bg-white text-[9px]">▶</span></div><div className="grid content-center gap-1.5"><strong className="text-[9px] text-slate-900">{index === 6 ? businessName : (locale === "de" ? "Eine echte Kundengeschichte" : "A real customer story")}</strong><i className="h-1.5 w-full rounded-full bg-slate-300" /><i className="h-1.5 w-2/3 rounded-full bg-slate-300" /></div></div>;
    if (index === 8) return <div className="flex gap-2">{[0, 1, 2, 3].map((item) => <span key={item} className="grid h-10 flex-1 place-items-center rounded-lg bg-slate-100 text-[7px] font-bold text-slate-400">LOGO</span>)}</div>;
    if (index === 9) return <div className="grid grid-cols-3 gap-2">{["01", "02", "03"].map((step) => <span key={step} className={`rounded-lg p-2 ${pale}`}><b className="text-[8px] text-slate-900">{step}</b><i className="mt-2 block h-1.5 w-full rounded-full bg-slate-300" /><i className="mt-1 block h-1.5 w-2/3 rounded-full bg-slate-300" /></span>)}</div>;
    if (index === 10) return <div className="grid gap-1.5">{[0, 1, 2].map((item) => <span key={item} className="flex h-7 items-center rounded-lg bg-slate-100 px-2"><i className="h-1.5 w-2/3 rounded-full bg-slate-300" /><b className="ml-auto text-[10px] text-slate-500">+</b></span>)}</div>;
    if (index === 11) return <div className={`grid grid-cols-4 gap-1.5 rounded-lg p-2.5 ${pale}`}>{["Mon", "Tue", "Wed", "Thu"].map((day, item) => <span key={day} className={`grid h-10 place-items-center rounded-md bg-white text-[7px] ${item === 2 ? "ring-2 ring-emerald-400" : ""}`}>{day}<b>{item + 10}:00</b></span>)}</div>;
    if (index === 12) return <div className={`grid gap-2 rounded-lg p-3 ${pale}`}><div className="grid grid-cols-2 gap-2"><span className="h-7 rounded-md bg-white" /><span className="h-7 rounded-md bg-white" /></div><span className="h-11 rounded-md bg-white" /><span className={`ml-auto h-6 w-24 rounded-full ${ink}`} /></div>;
    return <div className={`grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg p-3 ${pale}`}><div><strong className="block text-[9px] text-slate-900">{locale === "de" ? "Hilfreicher Guide" : "Useful local guide"}</strong><i className="mt-2 block h-1.5 w-full rounded-full bg-slate-300" /><i className="mt-1 block h-1.5 w-2/3 rounded-full bg-slate-300" /></div><span className={`rounded-full px-3 py-2 text-[7px] font-bold text-white ${ink}`}>{locale === "de" ? "Per E-Mail senden" : "Send by email"}</span></div>;
  };

  return (
    <div className="grid gap-6">
      <section className="rounded-2xl border border-hairline bg-white p-5 sm:p-6">
        <div className="mb-5"><p className="m-0 text-[11px] font-black uppercase tracking-[.14em] text-navy">01 · {t.lighthouse}</p><h3 className="mt-2 text-2xl font-black tracking-[-.03em]">{locale === "de" ? "Technische Qualität" : "Technical quality"}</h3></div>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-hairline bg-hairline lg:grid-cols-4">
          {lighthouse.map(([label, value]) => <div key={label} className="bg-white p-4"><span className="block text-[11px] font-bold text-pewter">{label}</span><strong className={`tnum mt-2 block text-3xl font-black ${value == null ? "text-slate-400" : value >= 80 ? "text-emerald-700" : value >= 55 ? "text-amber-700" : "text-red-700"}`}><CountUp value={value} id={`lighthouse-${label}`} /></strong></div>)}
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-hairline bg-white">
        <div className="flex flex-wrap items-end justify-between gap-4 p-5 sm:p-6"><div><p className="m-0 text-[11px] font-black uppercase tracking-[.14em] text-navy">02 · Website</p><h3 className="mt-2 text-2xl font-black tracking-[-.03em]">{t.conversion}</h3></div><div className="flex gap-2"><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-bold text-emerald-800">{applicable.length - missing.length} {t.present}</span><span className="rounded-full bg-red-50 px-3 py-1.5 text-sm font-bold text-red-800">{missing.length} {t.missing}</span>{notNeeded.length ? <span className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-bold text-slate-600">{notNeeded.length} {t.notNeeded}</span> : null}</div></div>

        <div className="grid gap-px border-y border-hairline bg-hairline sm:grid-cols-2 lg:grid-cols-4">
          {groups.map((group) => {
            const groupApplicable = group.elements.filter((element) => element.applies !== false);
            const presentCount = groupApplicable.filter((element) => element.present).length;
            return <details key={group.title} className="group bg-white"><summary className="flex min-h-[66px] cursor-pointer list-none items-center justify-between gap-3 p-4 [&::-webkit-details-marker]:hidden"><strong className="text-[13px] text-slate-950">{group.title}</strong><span className="flex items-center gap-2">{groupApplicable.length ? <b className={`tnum text-[12px] ${presentCount === groupApplicable.length ? "text-emerald-700" : "text-red-700"}`}>{presentCount}/{groupApplicable.length}</b> : <b className="text-[11px] font-semibold text-slate-400">{t.notNeeded}</b>}<ChevronDown className="size-4 text-navy transition-transform group-open:rotate-180" /></span></summary><div className="grid gap-2 border-t border-slate-100 px-4 pb-4 pt-3">{group.elements.map((element) => <div key={element.label} className="flex items-start gap-2 text-[11px] font-semibold leading-snug text-slate-700"><span className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full text-[10px] text-white ${element.applies === false ? "bg-slate-300" : element.present ? "bg-emerald-600" : "bg-red-600"}`}>{element.applies === false ? "-" : element.present ? <Check size={11} /> : "×"}</span><span className={element.applies === false ? "text-slate-400" : ""}>{elementLabel(element)}{element.applies === false ? ` · ${t.notNeeded}` : ""}</span></div>)}</div></details>;
          })}
        </div>

        <div className="p-5 sm:p-6">
          <div className="mb-3 grid grid-cols-2 rounded-xl bg-slate-100 p-1 lg:hidden" role="group" aria-label={locale === "de" ? "Website-Ansicht wählen" : "Choose website view"}>
            <button type="button" onClick={() => setMobileComparison("current")} aria-pressed={mobileComparison === "current"} className={`min-h-10 rounded-lg px-3 text-[12px] font-black transition-colors ${mobileComparison === "current" ? "bg-white text-navy shadow-sm" : "text-slate-500"}`}>{comparisonCopy.current}</button>
            <button type="button" onClick={() => setMobileComparison("plan")} aria-pressed={mobileComparison === "plan"} className={`min-h-10 rounded-lg px-3 text-[12px] font-black transition-colors ${mobileComparison === "plan" ? "bg-white text-navy shadow-sm" : "text-slate-500"}`}>{comparisonCopy.plan}</button>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
          <article className={`${mobileComparison === "current" ? "block" : "hidden"} overflow-hidden rounded-xl border border-hairline bg-slate-100 lg:block`}><header className="flex items-center justify-between gap-3 border-b border-hairline bg-white px-4 py-3"><strong className="block text-[13px] text-slate-950">{comparisonCopy.current}</strong><span className="rounded-full bg-slate-100 px-2 py-1 text-[9px] font-black uppercase text-slate-600">Live</span></header><div className="grid h-[410px] place-items-start overflow-hidden bg-[#ebeef2] p-3 sm:h-[470px] sm:p-4"><div className="mx-auto h-full w-full overflow-y-auto rounded-xl border border-slate-300 bg-white shadow-sm">{speed?.desktopScreenshot ? <img src={speed.desktopScreenshot} alt={`${data.clientName} current desktop website`} loading="lazy" decoding="async" className="h-auto w-full" /> :<p className="p-4 text-sm text-graphite">{t.noScreenshot}</p>}</div></div></article>
          <article className={`${mobileComparison === "plan" ? "block" : "hidden"} overflow-hidden rounded-xl border border-hairline bg-white lg:block`}><header className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3"><strong className="block text-[13px] text-slate-950">{comparisonCopy.plan}</strong><span className="rounded-full bg-blue-50 px-2 py-1 text-[9px] font-black uppercase text-blue-800">14 sections · {elements.length} checks</span></header><div className="grid h-[410px] content-start gap-2 overflow-y-auto bg-[#f5f3ee] p-3 sm:h-[470px] sm:p-4">{planBlocks.map((block, index) => <section key={block.label} className={`rounded-xl border bg-white p-3 shadow-sm ${block.present ? "border-emerald-200" : "border-red-200"}`}><div className="mb-3 flex items-center gap-3"><span className="text-[9px] font-black text-navy">{String(index + 1).padStart(2, "0")}</span><strong className="min-w-0 flex-1 text-[13px] leading-tight text-slate-950">{block.label}</strong><span className={`rounded-full px-2 py-1 text-[8px] font-black ${block.present ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>{block.present ? (locale === "de" ? "vorhanden" : "in place") : `${block.missing} ${locale === "de" ? "fehlt" : "missing"}`}</span></div>{planVisual(index, block.present)}{block.matched.length > 1 ? <div className="mt-2 flex flex-wrap gap-1.5">{block.matched.map((element) => <span key={element.label} className={`rounded-md px-2 py-1 text-[9px] font-bold ${element.present ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>{element.present ? "✓" : "×"} {elementLabel(element)}</span>)}</div> : null}</section>)}</div></article>
          </div>
        </div>

      </section>
    </div>
  );
}

/** The first sentence of a longer instruction: the fix table shows one clear
 *  sentence per row, the rest stays in the evidence section. */
function firstSentence(text: string): string {
  const match = text.trim().match(/^.*?[.!?](?=\s|$)/);
  return (match ? match[0] : text).trim();
}

/** Alles nach dem ersten Satz - der Rest, der in die Ausklapp-Zeile gehört. */
function restSentences(text: string): string {
  const rest = text.trim().slice(firstSentence(text).length).trim();
  return rest;
}

/** Ein Rahmen, der erst entsteht, wenn er in die Naehe des Bildschirms kommt.
 *
 *  Der Buchungskalender ist ein fremder Dienst und bringt beim Laden ueber eine halbe Million
 *  Zeichen JavaScript samt Facebook-Zaehler mit -- gemessen 06.09.2026 der Grund fuer eine
 *  halbe Sekunde blockierten Bildschirm, obwohl er ganz unten steht. `loading="lazy"` allein
 *  half nicht: der Browser hielt ihn fuer nah genug. */
function SpaeterRahmen({ src, title, className }: { src: string; title: string; className?: string }) {
  const [zeigen, setZeigen] = useState(false);
  const [huelle, setHuelle] = useState<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!huelle || zeigen) return;
    if (typeof IntersectionObserver === "undefined") {
      const frame = requestAnimationFrame(() => setZeigen(true));
      return () => cancelAnimationFrame(frame);
    }
    const beobachter = new IntersectionObserver(
      (eintraege) => { if (eintraege.some((e) => e.isIntersecting)) { setZeigen(true); beobachter.disconnect(); } },
      { rootMargin: "600px" },
    );
    beobachter.observe(huelle);
    return () => beobachter.disconnect();
  }, [huelle, zeigen]);
  return (
    <div ref={setHuelle} className={className}>
      {zeigen ? <iframe src={src} title={title} className="h-full w-full border-0" /> : <div className="h-full w-full bg-slate-50" aria-hidden />}
    </div>
  );
}

function ExecutiveActions({ items, locale, onViewEvidence }: { items: ExecutiveAction[]; locale: Locale; onViewEvidence: (section: SectionKey) => void }) {
  const labels = locale === "de"
    ? { title: "Jetzt beheben", link: "Details", show: "Im Bericht ansehen ↓", found: "Was wir gefunden haben", todo: "Was zu tun ist", more: (n: number) => `${n} weitere Punkte anzeigen` }
    : { title: "Fix this now", link: "Details", show: "See it in the report ↓", found: "What we found", todo: "What to do", more: (n: number) => `Show ${n} more` };
  const evidenceTarget = (action: ExecutiveAction): SectionKey => {
    const text = `${action.title} ${action.evidence ?? ""} ${action.change ?? ""}`.toLowerCase();
    if (/map|local result|checked location|sichtbar|kartenpunkt|geprüften ort|lokalen google/.test(text)) return "maps";
    if (/review|photo|profile|bewertung|foto|profil/.test(text)) return "profile";
    return "website";
  };
  return (
    <div className="lm-actions mt-5">
      {/* KLEINER (the reviewer, 06.09.2026). Als 34-px-Zeile stand die Ueberschrift so gross da
          wie die Aussagen im Hero und in der Verlust-Sektion, dabei fuehrt sie nur eine
          Liste an. Sie ordnet, sie behauptet nicht. */}
      <h2 className="m-0 text-[clamp(19px,2vw,24px)] font-black leading-[1.05] tracking-[-.028em]">{labels.title}</h2>
      <div className="mt-3 overflow-hidden rounded-[15px] border border-black/10 bg-white">
      <div className="hidden grid-cols-[26px_minmax(0,1fr)_26px_minmax(0,1fr)] gap-x-4 border-b border-black/10 bg-[#f7f5f0] px-5 py-2 sm:grid"><span /><span className="lm-spaltenkopf">{labels.found}</span><span /><span className="lm-spaltenkopf">{labels.todo}</span></div>
      <div>
        {(() => {
        const zeile = (action: ExecutiveAction, index: number, trennlinie: boolean) => {
          // KURZ, DANN AUFKLAPPEN (the reviewer, 06.09.2026). Der Befund stand hier in voller Länge,
          // teils über zwei Sätze - fünfmal untereinander liest das niemand. Links steht jetzt
          // ein Satz; der gemessene Beleg und der Rest der Anweisung liegen im Ausklapper,
          // zusammen mit dem Sprung in den Abschnitt, der es zeigt.
          const beleg = action.evidence ?? "";
          const kurz = firstSentence(action.finding ?? (beleg || action.what || action.title));
          const mehr = [action.finding && beleg && beleg !== action.finding ? beleg : restSentences(action.finding ?? beleg),
                        restSentences(action.change ?? "")].filter(Boolean);
          return (
          <article key={`${action.title}-${index}`} className={`lm-fixrow grid grid-cols-[22px_minmax(0,1fr)] items-start gap-x-3 gap-y-2.5 border-black/10 px-3.5 py-3.5 transition-colors sm:grid-cols-[26px_minmax(0,1fr)_26px_minmax(0,1fr)] sm:items-center sm:gap-x-4 sm:px-5 sm:py-3.5 ${trennlinie ? "border-b" : ""}`}>
            {/* Die Nummer zaehlt nur. Sie war ein grosser gefuellter Kreis und zog damit
                mehr Blick auf sich als der Befund daneben. */}
            <b className="tnum grid size-[22px] place-items-center self-start rounded-full border border-black/10 bg-[#f7f5f0] text-[10px] font-black text-graphite sm:self-center">{index + 1}</b>
            <div className="min-w-0">
              <p className="m-0 text-[14px] font-bold leading-[1.42] text-slate-900">{kurz}</p>
              <details className="group mt-1.5">
                <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-[9px] font-black uppercase tracking-[.06em] text-navy [&::-webkit-details-marker]:hidden">{labels.link}<ChevronDown className="size-3 transition-transform group-open:rotate-180" aria-hidden /></summary>
                {mehr.map((satz) => <p key={satz} className="m-0 mt-1.5 text-[13px] leading-[1.45] text-graphite">{satz}</p>)}
                <a href={`#report-${evidenceTarget(action)}`} onClick={() => onViewEvidence(evidenceTarget(action))} className="mt-1.5 block w-fit text-[12px] font-semibold text-navy underline decoration-navy/25 underline-offset-4">{labels.show}</a>
              </details>
            </div>
            {/* DER PFEIL IST DIE AUSSAGE (the reviewer, 06.09.2026: die Tabelle war zu langweilig).
                Vorher stand hier ein Haken, und ein Haken heisst "erledigt" - dabei ist
                das eine offene Aufgabe. Der Pfeil sagt, was der Befund links wird, wenn
                man rechts etwas tut, und macht aus zwei Textspalten eine Bewegung. Auf
                dem Telefon zeigt er nach unten, weil dort untereinander gelesen wird. */}
            <span aria-hidden className="lm-pfeil col-start-1 row-start-2 grid size-[22px] place-items-center self-center justify-self-center text-navy/60 sm:col-start-3 sm:row-start-1 sm:size-[26px]">
              <svg viewBox="0 0 20 20" fill="none" className="size-[15px] sm:size-[17px]">
                <path className="lm-pfeil-schaft" d="M3 10h11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                <path d="M11.6 5.8L16 10l-4.4 4.2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div className="lm-fix col-start-2 min-w-0 sm:col-start-4">
              <span data-onepager="fix" className="sr-only">{action.title}</span>
              <p className="m-0 rounded-xl bg-navy-soft/45 px-3 py-2.5 text-[14px] font-bold leading-[1.42] text-slate-900 sm:bg-transparent sm:p-0">{firstSentence(action.change ?? action.what ?? action.title)}</p>
            </div>
          </article>
          );
        };
        // ZWEI OFFEN, DER REST AUF WUNSCH (the reviewer, 06.09.2026). Fünf Befunde untereinander
        // liest niemand, der noch entscheidet, ob er überhaupt antwortet. Die zwei
        // stärksten stehen da, die anderen sind einen Klick entfernt - verborgen wird
        // nichts, nur gestapelt.
        const gezeigt = items.slice(0, 5);
        const rest = gezeigt.slice(2);
        return (
          <>
            {gezeigt.slice(0, 2).map((action, index) => zeile(action, index, index < 1 || rest.length > 0))}
            {rest.length ? (
              <details className="lm-more group border-t border-black/10">
                {/* GROESSER (the reviewer, 06.09.2026). Als 12-px-Zeile las sich der Aufklapper wie
                    eine Fussnote, und drei weitere Befunde sind keine Fussnote. */}
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 bg-navy-soft/50 px-3.5 py-4 text-[15px] font-black tracking-[-.01em] text-navy transition hover:bg-navy-soft sm:px-5 sm:py-[18px] sm:text-[17px] [&::-webkit-details-marker]:hidden">
                  {labels.more(rest.length)}
                  <ChevronDown className="size-5 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
                </summary>
                <div className="border-t border-black/10">
                  {rest.map((action, index) => zeile(action, index + 2, index < rest.length - 1))}
                </div>
              </details>
            ) : null}
          </>
        );
      })()}
      </div>
      </div>
    </div>
  );
}

/** The build plan, package by package, without a price: what would be built
 *  in which week, so the owner sees the vision before the call. The price is
 *  settled on the call (proposal-blueprint.md). */
/** NICHT MEHR IM KALTREPORT, ABSICHTLICH AUFGEHOBEN (the reviewer, 06.09.2026: „die Roadmap
 *  speichern wir uns für später auf"). Der Wochenplan mit Paketreitern gehört ins Angebot
 *  nach dem Gespräch, wo jemand danebensitzt und ihn erklärt - im Kaltreport steht jetzt
 *  `SolutionSection`. Diese Funktion bleibt stehen, damit die Angebotsseite sie übernehmen
 *  kann, statt sie aus der Historie zu holen. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- aufgehoben fuer die Angebotsseite, siehe Kommentar oben
function RoadmapSection({ data, locale }: { data: ProposalData; locale: Locale }) {
  const plan = data.gantt;
  if (!plan?.bars.length) return null;
  const initial = plan.packages.find((p) => p.recommended)?.name ?? plan.packages[0]?.name ?? "";
  return (
    <section aria-label={locale === "de" ? "Was wir bauen würden" : "What we would build"} className="lm-plan mb-10 sm:mb-14">
      <div className="mx-auto max-w-[1160px] px-5 sm:px-8">
        <p className="m-0 text-[11px] font-bold uppercase tracking-[0.08em] text-navy">{locale === "de" ? "Der Plan" : "The plan"}</p>
        <h2 className="mt-2 text-[clamp(26px,3vw,36px)] font-black leading-[1.05] tracking-[-.03em]">{locale === "de" ? "Was wir für Sie bauen würden" : "What we would build for you"}</h2>
        <PackageProvider names={plan.packages.map((p) => p.name)} initial={initial}>
          <PackageTabs plan={plan} locale={locale} />
          {/* DER BALKENPLAN BLEIBT (the reviewer, 06.09.2026, nach einem Zwischenschritt als Liste):
              die Wochen sind das, was diese Seite vom Angebot unterscheidet - man sieht, dass
              in Woche eins etwas passiert. Nur die Zeilen, die im gewählten Paket NICHT drin
              sind, fallen weg: ausgegraut bewarben sie ausgerechnet das, was der Empfänger
              nicht bekommt. */}
          <div className="mt-5 hidden rounded-2xl border border-hairline bg-white p-4 md:block sm:p-6"><Gantt variant="report" plan={plan} showPackages={false} hideOutOfPlan valueLabel={locale === "de" ? "im Paket" : "in plan"} renderDetail={(bar) => <ServiceOpen bar={bar} locale={locale} />} /></div>
          <PlanMobile plan={plan} locale={locale} />
        </PackageProvider>
        <p className="mb-0 mt-4 text-[13px] leading-[1.5] text-graphite">{locale === "de" ? "Umfang und Preis legen wir gemeinsam im Gespräch fest, bevor etwas beginnt." : "Scope and price are settled together on the call, before anything starts."}</p>
      </div>
    </section>
  );
}

/** The three packages by weeks, no price: the chart below redraws per pick. */
function PackageTabs({ plan, locale }: { plan: NonNullable<ProposalData["gantt"]>; locale: Locale }) {
  const shared = usePackage();
  if (!shared) return null;
  return (
    <div className="mt-4 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1 sm:inline-flex sm:gap-2 sm:bg-transparent sm:p-0" role="tablist">
      {plan.packages.map((p) => (
        <button key={p.name} type="button" role="tab" aria-selected={p.name === shared.pick} onClick={() => shared.setPick(p.name)} className={`rounded-lg px-2 py-2 text-center text-[12px] font-bold leading-tight sm:rounded-full sm:border sm:px-4 sm:text-[13px] ${p.name === shared.pick ? "bg-navy text-white sm:border-navy" : "text-slate-800 sm:border-black/10 sm:bg-white"}`}>
          {p.name}<span className="block text-[10px] font-semibold opacity-80 sm:ml-1.5 sm:inline"> {p.weeks} {locale === "de" ? "Wo." : "wks"}</span>{p.recommended ? <span className="ml-1.5 hidden text-[10px] font-black uppercase opacity-80 sm:inline">{locale === "de" ? "empfohlen" : "recommended"}</span> : null}
        </button>
      ))}
    </div>
  );
}

/** Normal Google results, full width under the map: one verdict line, then
 *  three pictures. Who holds page one for the town term, the client's site
 *  beside the map winners' sites on one measure, and the local searches a
 *  comparable winner has that the client lacks. No paragraphs. */
function OrganicSection({ organic, locale }: { organic: NonNullable<NonNullable<ProposalData["search"]>["organic"]>; locale: Locale }) {
  const de = locale === "de";
  const fmt = (n: number | null | undefined) => (n == null ? "-" : n.toLocaleString(de ? "de-DE" : "en-GB"));
  const rows = [
    { name: de ? "Sie" : "You", pageOne: organic.pageOne, mine: true, farLarger: false },
    ...(organic.winners ?? []).map((w) => ({ name: w.name, pageOne: w.pageOne ?? 0, mine: false, farLarger: w.farLarger })),
  ];
  const max = Math.max(1, ...rows.map((r) => r.pageOne ?? 0));
  const demand = organic.demand;
  const position = organic.serp?.clientPosition ?? null;
  // One sentence, measured against demand for the town term: that is what
  // is on the table, not how other local sites do (the reviewer, 05.09.2026).
  // A bare trade word is a country figure, never a town one. Saying "searches
  // a month" over the national number told a Cirencester owner his town
  // searched 33,100 times a month (07.09.2026), so the scope is now named.
  const reach = demand?.scope === "national"
    ? (de ? " landesweit" : " nationwide")
    : "";
  const verdict = demand
    ? (position
      ? (de ? `Platz ${position} für „${demand.keyword}", ${fmt(demand.volume)} Suchen im Monat${reach}.` : `Position ${position} for "${demand.keyword}", ${fmt(demand.volume)} searches a month${reach}.`)
      : (de ? `Nicht auf Seite eins für „${demand.keyword}", ${fmt(demand.volume)} Suchen im Monat${reach}.` : `Not on page one for "${demand.keyword}", ${fmt(demand.volume)} searches a month${reach}.`))
    : organic.total
      ? (de ? `Auf Seite eins für ${organic.pageOne} von ${organic.total} gefundenen Suchen.` : `On page one for ${organic.pageOne} of ${organic.total} searches found.`)
      : (de ? "In der normalen Google-Suche für keine Suche gefunden." : "Not found in normal Google results for any search.");
  const visits = organic.clientVisits;
  return (
    <div className="mt-6 rounded-2xl border border-hairline bg-white p-5">
      <h3 className="text-lg font-black">{de ? "Ihre Website in der normalen Google-Suche" : "Your website in normal Google results"}</h3>
      <p className="mb-0 mt-2 text-[15px] font-bold leading-[1.4] text-slate-900">{verdict}</p>
      {visits != null ? <p className="mb-0 mt-1 text-[12px] leading-[1.4] text-graphite">{de ? `Geschätzt ${fmt(visits)} Besuche im Monat aus Google, hochgerechnet, nicht gemessen.` : `An estimated ${fmt(visits)} visits a month from Google, worked out from rankings, not measured.`}</p> : null}
      {organic.winners?.length ? (
        <ul className="m-0 mt-5 grid list-none gap-2.5 p-0">
          <li className="text-[10px] font-bold uppercase tracking-[0.06em] text-graphite">{de ? "Suchen auf Seite eins, Sie gegen die Kartengewinner" : "Searches on page one, you against the map winners"}</li>
          {rows.map((row) => (
            <li key={row.name} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
              <span className={`min-w-0 truncate text-[12px] ${row.mine ? "font-black text-navy" : "text-slate-800"}`}>{row.name}{row.farLarger ? <small className="ml-1.5 text-[10px] font-semibold text-graphite">{de ? "weit größere Website" : "far larger site"}</small> : null}</span>
              <b className={`tnum text-[12px] ${row.mine ? "text-navy" : "text-slate-800"}`}>{fmt(row.pageOne)}</b>
              <span className="col-span-2 block h-2 overflow-hidden rounded-full bg-slate-100"><span data-grow data-lm-motion={`organic-${row.name}`} className={`block h-full rounded-full ${row.mine ? "bg-navy" : "bg-slate-400"}`} style={{ width: `${Math.max(2, Math.round(((row.pageOne ?? 0) / max) * 100))}%` }} /></span>
            </li>
          ))}
        </ul>
      ) : null}
      {organic.gap?.length ? (
        <div className="mt-5 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[10px] font-bold uppercase tracking-[0.06em] text-graphite">{de ? "Seiten, die Ihnen fehlen" : "Pages you do not have yet"}</span>
          {organic.gap.slice(0, 3).map((row) => <span key={row.keyword} className="inline-flex items-baseline gap-1.5 rounded-full border border-hairline bg-[#f7f8fb] px-2.5 py-1 text-[12px] text-slate-900">{row.keyword}<b className="tnum text-[11px] text-graphite">{fmt(row.volume)}/{de ? "Monat" : "mo"}</b></span>)}
        </div>
      ) : null}
      {organic.serp ? (
        <details className="mt-4 border-t border-hairline pt-3">
          <summary className="cursor-pointer text-[11px] font-bold text-navy">{de ? `Wer für „${organic.serp.keyword}" auf Seite eins steht` : `Who is on page one for "${organic.serp.keyword}"`}</summary>
          <ol className="m-0 mt-2 grid list-none gap-1 p-0 sm:grid-cols-2">
            {organic.serp.pageOne.map((row) => (
              <li key={row.position} className={`flex items-center gap-2 text-[12px] ${row.kind === "you" ? "font-black text-navy" : "text-slate-800"}`}>
                <span className="tnum w-5 shrink-0 text-right text-graphite">{row.position}</span>
                <span className="min-w-0 flex-1 truncate">{row.domain}</span>
                {row.kind === "winner" || row.kind === "directory" ? <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.04em] ${row.kind === "winner" ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-700"}`}>{row.kind === "winner" ? (de ? "Kartengewinner" : "map winner") : (de ? "Verzeichnis" : "directory")}</span> : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  );
}

function CloseSection({ data, locale, onPoster }: { data: ProposalData; locale: Locale; onPoster: () => void }) {
  return (
    <section id="reply" className="lm-close relative overflow-hidden border-t-[7px] border-[#6f91ef] bg-navy-deep px-5 py-8 text-white sm:px-8 sm:py-10">
      <div className="relative mx-auto max-w-[1160px]">
        <div className="max-w-[760px]">
          <SektionsKopf kapitel={KAPITEL.termin} locale={locale} hell />
          <p className="mb-0 mt-5 max-w-[52ch] text-[17px] leading-[1.55] text-white/80">
            {locale === "de"
              ? "Antworten Sie hier auf Upwork. Ich übertrage die Befunde in den ersten konkreten Schritt für Ihr Projekt."
              : "Reply here on Upwork. I'll turn these findings into the first practical step for your project."}
          </p>
          {data.onePager?.url ? (
            <button type="button" onClick={onPoster} className="mt-6 inline-flex min-h-11 items-center rounded-xl border border-white/25 bg-white/10 px-5 text-[13px] font-black text-white backdrop-blur-sm transition-colors hover:bg-white/15">
              {locale === "de" ? "Einseitige Zusammenfassung öffnen" : "Open the one-page summary"}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
// Lukas eigene Profile. Sie stehen hier und nicht in den Berichtsdaten: sie
// gehoeren zu ihm, nicht zu einem Kunden, und aendern sich pro Bericht nie.
// Vier von Hand gezogene Raender. Sie sind bewusst nicht identisch: ein
// Rechteck, das sich exakt wiederholt, sieht wieder aus wie ein CSS-Rahmen.
const SKIZZEN_RAND = [
  "M9 8 C80 4, 200 6, 292 9 C295 70, 294 140, 291 192 C210 195, 90 194, 8 191 C5 130, 6 70, 9 8 Z",
  "M7 11 C90 6, 195 9, 293 6 C296 65, 292 135, 294 189 C200 193, 95 190, 6 194 C9 130, 4 68, 7 11 Z",
  "M10 6 C85 10, 205 4, 290 11 C293 72, 296 138, 292 190 C205 187, 88 192, 9 189 C6 128, 7 66, 10 6 Z",
  "M6 9 C95 5, 190 11, 294 7 C291 68, 295 142, 290 193 C195 189, 100 195, 8 190 C11 132, 3 70, 6 9 Z",
];
const UPWORK_PROFIL = "#reply";
const YOUTUBE_KANAL = "#reply";

export function LeadMagnet({ data }: { data: ProposalData }) {
  const locale: Locale = data.language ?? data.findings.gbp?.locale ?? "en";
  const t = copy[locale];
  const [open, setOpen] = useState<SectionKey | null>(null);
  /* DIE SEITE DARF NICHT WEGSPRINGEN (the reviewer, 06.09.2026: „die Orientierung muss immer
     gegeben sein für den Lead"). Nur eine Säule ist offen: wer die zweite aufklappt,
     schliesst damit die erste, und liegt die weiter oben, faellt alles ueber dem
     Leser zusammen - der Browser haelt die Scrollposition, also rutscht der Inhalt
     unter ihm weg. Statt die Position zu korrigieren, holen wir die neu geoeffnete
     Saeule an den Kopf: dann steht immer das oben, worauf gerade geklickt wurde.
     Nur beim Wechsel, nicht beim ersten Oeffnen und nicht beim Schliessen. */
  const [springZu, setSpringZu] = useState<SectionKey | null>(null);
  const oeffneSaeule = (key: SectionKey) => {
    if (open !== null && open !== key) setSpringZu(key);
    setOpen(open === key ? null : key);
  };
  useEffect(() => {
    if (!springZu) return;
    const ziel = document.getElementById(`report-${springZu}`);
    setSpringZu(null);
    if (!ziel) return;
    const ruhig = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    ziel.scrollIntoView({ block: "start", behavior: ruhig ? "auto" : "smooth" });
  }, [springZu]);
  const aktivesKapitel = useAktivesKapitel();
  const [showSticky, setShowSticky] = useState(false);
  const [posterOpen, setPosterOpen] = useState(false);
  useEffect(() => {
    if (!posterOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setPosterOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [posterOpen]);
  useEffect(() => {
    const updateSticky = () => setShowSticky(window.scrollY > window.innerHeight * 0.8);
    updateSticky();
    window.addEventListener("scroll", updateSticky, { passive: true });
    return () => window.removeEventListener("scroll", updateSticky);
  }, []);
  const scores = useMemo(() => {
    const maps = mapScore(data.findings.geoGrid?.ranks);
    const profile = profileScore(auditRowsAsShown(data.findings.gbp));
    const enquiry = enquiryScore(data.cro?.elements);
    const lighthouseValues = data.cro?.speed?.scores ? Object.values(data.cro.speed.scores).filter((value): value is number => typeof value === "number") : data.cro?.speed?.score != null ? [data.cro.speed.score] : [];
    const lighthouse = lighthouseValues.length ? clampScore(lighthouseValues.reduce((sum, value) => sum + value, 0) / lighthouseValues.length) : null;
    const website = enquiry == null ? lighthouse : lighthouse == null ? enquiry : clampScore((enquiry + lighthouse) / 2);
    const measured = [maps, profile, website].filter((value): value is number => value != null);
    return { maps, profile, enquiry, lighthouse, website, overall: measured.length ? clampScore(measured.reduce((sum, value) => sum + value, 0) / measured.length) : data.scorecard.overall };
  }, [data]);
  const ranks = data.findings.geoGrid?.ranks ?? [];
  const missingMap = ranks.filter((rank) => rank == null).length;
  const firstProfileGap = data.findings.gbp?.auditRows?.find((row) => row.status !== "good");
  const firstWebsiteGap = data.cro?.elements.find((element) => !element.present && !["video_top", "video_testimonials"].includes(element.key ?? ""));
  const reviewRow = data.findings.gbp?.auditRows?.find((row) => row.label.toLowerCase() === "reviews");
  const performance = data.cro?.speed?.scores?.performance ?? data.cro?.speed?.score ?? null;
  const mapTerm = data.findings.geoGrid?.keyword;
  const currentPhotoCount = data.findings.gbp?.current?.photos?.length;
  const profileAction = locale === "de"
    ? firstProfileGap?.label === "Description" ? "Profilbeschreibung ergänzen"
      : firstProfileGap ? `${firstProfileGap.label} im Google-Profil korrigieren`
        : "Diese Woche ein aktuelles Foto hochladen"
    : firstProfileGap?.label === "Description" ? "Add a clear profile description"
      : firstProfileGap ? `Fix ${firstProfileGap.label.toLowerCase()} in the profile`
        : "Upload one recent photo this week";
  const websiteActions: Record<string, { en: string; de: string }> = {
    social_proof_numbers: { en: "Show proof in numbers on the website", de: "Vertrauen mit konkreten Zahlen belegen" },
    online_booking: { en: "Add an online booking route", de: "Online-Buchung ergänzen" },
    video_top: { en: "Add a short introduction video", de: "Kurzes Vorstellungsvideo ergänzen" },
    video_testimonials: { en: "Add one customer video", de: "Ein Kundenvideo ergänzen" },
    logo_wall: { en: "Show recognised clients or partners", de: "Bekannte Kunden oder Partner zeigen" },
    response_time: { en: "Promise a clear response time", de: "Klare Antwortzeit versprechen" },
    email_capture: { en: "Add an email follow-up route", de: "E-Mail-Follow-up ergänzen" },
  };
  const websiteAction = performance != null && performance < 50
    ? (locale === "de" ? `Mobile Performance verbessern (${performance}/100)` : `Improve mobile performance (${performance}/100)`)
    : firstWebsiteGap
      ? ((firstWebsiteGap.key ? websiteActions[firstWebsiteGap.key]?.[locale] : undefined) ?? (locale === "de" ? `${firstWebsiteGap.label} ergänzen` : `Add ${firstWebsiteGap.label.toLowerCase()}`))
      : (locale === "de" ? "Anfrageweg regelmäßig testen" : "Keep testing the enquiry path");
  const websiteEvidence = performance != null && performance < 50
    ? (locale === "de" ? "Die wichtigsten Inhalte der mobilen Seite laden zu langsam." : "The most important content on the mobile page loads too slowly.")
    : websiteGapEvidence(firstWebsiteGap, locale);
  const currentProfileEvidence = profileEvidence(firstProfileGap, locale);
  const currentReviewEvidence = profileEvidence(reviewRow, locale);
  const fallbackActions: ExecutiveAction[] = locale === "de" ? [
    { art: "profile", title: missingMap ? "Einen Hauptservice überall gleich benennen" : "Hauptservice monatlich abgleichen", evidence: missingMap ? `An ${missingMap} von ${ranks.length || 25} geprüften Orten sehen Kunden das Profil nicht in den lokalen Google-Ergebnissen.` : "Kunden sehen das Profil im gesamten geprüften Gebiet.", change: `Im Profil und auf der passenden Website-Seite dieselbe Bezeichnung für ${mapTerm || "den Hauptservice"} verwenden.`, benefit: "Google kann den Betrieb der richtigen Suche zuordnen, und Kunden erkennen sofort, dass die Leistung zu ihrem Problem passt.", what: "Hauptservice in Profil und Website abgleichen.", effort: "30 Minuten · Sie + Webperson" },
    { art: "profile", title: profileAction, evidence: currentProfileEvidence || (currentPhotoCount != null ? `Im geprüften Profil sind ${currentPhotoCount} öffentliche Fotos sichtbar.` : "Die öffentlichen Profilangaben sind vollständig, aber neue Fotos halten den Eindruck aktuell."), change: firstProfileGap ? profileAction : "Ein echtes, aktuelles Foto der Arbeit oder des Teams im Google-Profil hochladen.", benefit: firstProfileGap ? "Kunden verstehen schneller, ob der Betrieb ihr Anliegen löst und wie sie Kontakt aufnehmen." : "Ein aktuelles Foto zeigt, dass der Betrieb aktiv ist, und macht den ersten Anruf weniger riskant.", what: profileAction, effort: firstProfileGap ? "45 Minuten · wir nach Freigabe" : "10 Minuten · Sie" },
    { art: "form", title: websiteAction, evidence: websiteEvidence, change: websiteAction, benefit: "Kunden, die gerade nicht anrufen können, können ihr Anliegen trotzdem senden. So gehen weniger Anfragen verloren.", what: websiteAction, effort: "1-2 Stunden · wir" },
    { art: "reviews", title: "Zehn Kunden den Bewertungslink senden", evidence: currentReviewEvidence || "Auf dem geprüften Profil sind noch keine aktuellen Kundenerfahrungen sichtbar.", change: "Zehn zufriedenen Kunden heute den direkten Google-Link senden und danach jede neue Bewertung beantworten.", benefit: "Aktuelle Erfahrungen nehmen neuen Kunden Unsicherheit und erhöhen die Chance, dass sie anrufen.", what: "Bewertungslink versenden.", effort: "30 Minuten · Sie" },
  ] : [
    { art: "profile", title: missingMap ? "Use one main service name everywhere" : "Check the main service monthly", evidence: missingMap ? `At ${missingMap} of ${ranks.length || 25} checked locations, customers do not see the profile in Google's local results.` : "Customers can see the profile across the entire checked area.", change: `Use the same wording for ${mapTerm || "the main service"} in the profile and matching website page.`, benefit: "Google can match the business to the right search, and customers can immediately see that the service fits their problem.", what: "Match the main service across Google and the website.", effort: "30 minutes · you + web person" },
    { art: "profile", title: profileAction, evidence: currentProfileEvidence || (currentPhotoCount != null ? `${currentPhotoCount} public photos are visible on the checked profile.` : "The public profile details are complete, but recent photos keep it current."), change: firstProfileGap ? profileAction : "Upload one genuine, recent photo of the work or team to the Google profile.", benefit: firstProfileGap ? "Customers understand sooner whether the business can solve their problem and how to get help." : "A recent photo proves the business is active and makes the first call feel less risky.", what: profileAction, effort: firstProfileGap ? "45 minutes · us after approval" : "10 minutes · you" },
    { art: "form", title: websiteAction, evidence: websiteEvidence, change: websiteAction, benefit: "Customers who cannot call immediately can still ask for help, so fewer enquiries are lost.", what: websiteAction, effort: "1-2 hours · us" },
    { art: "reviews", title: "Text the review link to ten customers", evidence: currentReviewEvidence || "The checked profile does not show recent customer experiences.", change: "Send ten happy customers the direct Google link today, then answer every new review.", benefit: "Recent experiences remove doubt for new customers and make them more likely to call.", what: "Send the review link.", effort: "30 minutes · you" },
  ];
  const suppliedActions = (data.actions?.items ?? [])
    .filter((action) => [action.evidence, action.change, action.benefit, action.effort].every((value) => Boolean(value?.trim())))
    .map((action) => {
      let evidence = action.evidence ?? "";
      let benefit = action.benefit ?? "";
      const mapWinnerLeads = evidence.match(/^At (\d+) of (\d+) spots(.*), customers see (.+) before you\.$/i);
      const mapClientLeads = evidence.match(/^At (\d+) of (\d+) spots(.*), customers still see another business first, most often (.+)\.$/i);
      // Kurz und in einem Atemzug lesbar (the reviewer, 06.09.2026). Vorher stand hier ein
      // Zweisatz mit „ranks outside the top three at ... checked locations within 5 km";
      // dieselbe Aussage, nur so lang, dass niemand sie zu Ende liest.
      if (mapWinnerLeads) evidence = `Outside the top three at ${mapWinnerLeads[1]} of ${mapWinnerLeads[2]} nearby searches. ${mapWinnerLeads[4]} leads.`;
      if (mapClientLeads) evidence = `You lead overall, but sit outside the top three at ${mapClientLeads[1]} of ${mapClientLeads[2]} nearby searches.`;
      const mapAbsence = evidence.match(/^The profile is absent from (\d+) of (\d+) map checks(?: for .+)?\.$/i);
      if (mapAbsence) evidence = `You do not show up at all in ${mapAbsence[1]} of ${mapAbsence[2]} nearby searches.`;
      evidence = evidence
        .replace(/^The profile combines/i, "Your Google profile combines")
        .replace(/^The profile mixes/i, "Your Google profile mixes")
        .replace(/^The website does not/i, "Your website does not")
        .replace(/^The website gives no expected reply time\.?$/i, "Your website does not tell customers when they will hear back.");
      if (/\b(enquiry|anfrage)[ -]?(signals?|signale?)\b/i.test(evidence)) evidence = websiteEvidence;
      const reviewFragment = evidence.match(/^\s*([\d.,]+)\s*,?\s*(?:rated|bewertet mit)\s*([\d.,]+)/i);
      if (reviewFragment) evidence = locale === "de"
        ? `Das Profil hat ${reviewFragment[1]} Google-Bewertungen mit durchschnittlich ${reviewFragment[2]} Sternen.`
        : `The profile has ${reviewFragment[1]} Google reviews with an average rating of ${reviewFragment[2]} stars.`;
      if (/^More visitors reach the phone, calendar or form\.?$/i.test(benefit)) benefit = "Customers who cannot call immediately can still ask for help, so fewer enquiries are lost.";
      return { ...action, evidence, benefit };
    });
  // Three to five real rows. The fallbacks only top up to three, never to five:
  // padded rows were what made the report look like a template.
  const executiveActions = [...suppliedActions, ...(suppliedActions.length >= 2 ? [] : fallbackActions)]
    .filter((action, index, values) => values.findIndex((candidate) => candidate.title === action.title) === index)
    .slice(0, suppliedActions.length >= 2 ? 5 : 2);
  // The strongest evidenced finding is the hook under the headline.
  const heroHook = executiveActions[0]?.evidence ?? null;
  const topThreeShare = ranks.length ? ranks.filter((rank) => typeof rank === "number" && rank <= 3).length / ranks.length : 0;
  const mapsFinding = locale === "de"
    ? topThreeShare >= 0.8 ? "Ihr Profil steht an fast allen geprüften Orten in den Top 3."
      : topThreeShare >= 0.4 ? "An etwa der Hälfte der geprüften Orte stehen andere Anbieter vor Ihnen."
        : "An den meisten geprüften Orten stehen andere Anbieter vor Ihnen."
    : topThreeShare >= 0.8 ? "Your profile ranks in the top three at almost every checked location."
      : topThreeShare >= 0.4 ? "Other providers rank ahead of you at about half of the checked locations."
        : "Other providers rank ahead of you at most checked locations.";
  // The map explains itself: what was searched, why that term, what moves a
  // badge. No naked numbers (the blueprint), and a reader who has never heard
  // of a map pack still understands the finding.
  // The reading follows the share of points in the top three, not the count
  // of blanks: 12 green of 25 is "about half", not "only a few parts".
  const mapArea = data.findings.geoGrid?.radiusKm ? (locale === "de" ? `im Umkreis von ${data.findings.geoGrid.radiusKm} km` : `within ${data.findings.geoGrid.radiusKm} km`) : (locale === "de" ? "im geprüften Einzugsgebiet" : "across the checked area");
  const mapReading = locale === "de"
    ? topThreeShare >= 0.8 ? `Das Profil steht ${mapArea} fast überall in den Top 3.`
      : topThreeShare >= 0.4 ? `Das Profil steht ${mapArea} an etwa der Hälfte der Orte in den Top 3. An den übrigen stehen andere lokale Anbieter weiter oben.`
        : `Das Profil erscheint ${mapArea} nur an wenigen Orten weit oben. An den meisten geprüften Orten stehen andere lokale Anbieter weiter oben.`
    : topThreeShare >= 0.8 ? `The profile holds a top-three spot almost everywhere ${mapArea}.`
      : topThreeShare >= 0.4 ? `The profile holds a top-three spot at about half of the places ${mapArea}. At the rest, other nearby businesses rank higher.`
        : `The profile appears near the top in only a few places ${mapArea}. Other nearby businesses rank higher at most checked locations.`;
  // Where the business stands in this market, measured against the same
  // yardstick as the winners (top-three points): the leader, one of the three
  // with the most positions, or behind them. A share alone said "about half"
  // about a business that actually holds more spots than anyone else.
  const mapWinnersList = data.findings.geoGrid?.winners ?? [];
  const mapClient = data.findings.geoGrid?.client;
  // Wie tief das Feld ist, nicht nur wer vorn steht. "25 von 25" liest sich als
  // Dominanz, bis daneben steht, dass ueberhaupt nur drei Betriebe je oben
  // auftauchten; umgekehrt ist "keiner von 25" gegen vierzig Wettbewerber eine
  // ganz andere Nachricht als gegen zwei (the reviewer, 07.09.2026).
  const mapRivals = data.findings.geoGrid?.rivals ?? null;
  const mapField = mapRivals
    ? (locale === "de"
      ? `In allen 25 Suchen erschienen ${mapRivals} andere Betriebe je in den Top drei, so tief ist das Feld hier.`
      : `Across all 25 searches, ${mapRivals} other ${mapRivals === 1 ? "business" : "businesses"} ever reached the top three, so that is how deep the field is here.`)
    : null;
  const mapLeader = mapWinnersList[0];
  const mapAhead = mapClient ? mapWinnersList.filter((winner) => winner.topThreePoints > mapClient.topThreePoints).length : null;
  const mapPosition = mapClient && mapLeader && mapAhead !== null && mapClient.topThreePoints > 0
    ? mapAhead === 0
      ? (locale === "de"
        ? `${mapArea.charAt(0).toUpperCase()}${mapArea.slice(1)} haben Sie mit ${mapClient.topThreePoints} von 25 geprüften Orten die meisten Top-3-Platzierungen, vor ${mapLeader.name} mit ${mapLeader.topThreePoints}.`
        : `${mapArea.charAt(0).toUpperCase()}${mapArea.slice(1)}, you have the most top-three positions: ${mapClient.topThreePoints} of 25 checked locations, ahead of ${mapLeader.name} with ${mapLeader.topThreePoints}.`)
      : mapAhead <= 2
        ? (locale === "de"
          ? `Sie gehören ${mapArea} mit ${mapClient.topThreePoints} von 25 geprüften Orten zu den drei Betrieben mit den meisten Top-3-Platzierungen, hinter ${mapLeader.name} mit ${mapLeader.topThreePoints}.`
          : `${mapArea.charAt(0).toUpperCase()}${mapArea.slice(1)}, you are one of the three businesses with the most top-three positions: ${mapClient.topThreePoints} of 25 checked locations, behind ${mapLeader.name} with ${mapLeader.topThreePoints}.`)
        : (locale === "de"
          ? `${mapLeader.name} gewinnt diese Karte mit ${mapLeader.topThreePoints} von 25 Orten; Sie halten ${mapClient.topThreePoints}.`
          : `${mapLeader.name} wins this map with ${mapLeader.topThreePoints} of 25 places; you hold ${mapClient.topThreePoints}.`)
    : mapLeader && mapClient && mapClient.topThreePoints === 0
      ? (locale === "de" ? `${mapLeader.name} gewinnt diese Karte mit ${mapLeader.topThreePoints} von 25 Orten; Sie an keinem.` : `${mapLeader.name} wins this map with ${mapLeader.topThreePoints} of 25 places; you hold none.`)
      : null;
  // The side the gaps sit on. The grid is five by five, row by row from the
  // north-west; a missing rank counts as far down. Named only when one side
  // is clearly weaker than its opposite, otherwise the gaps are spread.
  const mapWeakSide = (() => {
    if (ranks.length !== 25) return null;
    const score = (index: number) => (typeof ranks[index] === "number" ? (ranks[index] as number) : 21);
    const mean = (indexes: number[]) => indexes.reduce((sum, index) => sum + score(index), 0) / indexes.length;
    const rows = (rowList: number[]) => rowList.flatMap((row) => [0, 1, 2, 3, 4].map((col) => row * 5 + col));
    const cols = (colList: number[]) => colList.flatMap((col) => [0, 1, 2, 3, 4].map((row) => row * 5 + col));
    const north = mean(rows([0, 1])), south = mean(rows([3, 4])), west = mean(cols([0, 1])), east = mean(cols([3, 4]));
    const vertical = Math.abs(north - south) >= 2 ? (south > north ? (locale === "de" ? "Süden" : "south") : (locale === "de" ? "Norden" : "north")) : "";
    const horizontal = Math.abs(west - east) >= 2 ? (west > east ? (locale === "de" ? "Westen" : "west") : (locale === "de" ? "Osten" : "east")) : "";
    const side = vertical && horizontal ? (locale === "de" ? `${vertical.slice(0, -2)}${horizontal.toLowerCase()}` : `${vertical}-${horizontal}`) : vertical || horizontal;
    if (!side) return null;
    return locale === "de" ? `Die schwächeren Orte liegen im ${side} von Ihnen.` : `The weaker spots lie to the ${side} of you.`;
  })();
  // The website's own rankings, read the way an owner needs it: found by
  // strangers, found only by people who already know the name, or not found.
  // The verdict beside the score must agree with its colour: a leader at
  // half the spots leads a fragmented map, and the sentence says both.
  const mapsVerdict = mapAhead === 0 && mapClient && mapClient.topThreePoints > 0 && topThreeShare < 0.8
    ? (locale === "de"
      ? (topThreeShare >= 0.4 ? "Sie führen diese Karte, stehen aber nur an etwa der Hälfte der geprüften Orte in den Top 3." : "Sie führen diese Karte trotz geringer Abdeckung: An den meisten geprüften Orten stehen Sie nicht in den Top 3.")
      : (topThreeShare >= 0.4 ? "You lead this map, but rank in the top three at only about half of the checked locations." : "You lead this map despite limited coverage: you rank outside the top three at most checked locations."))
    : mapsFinding;
  // The verdict beside a score follows the score. Until 05.09.2026 every row that
  // was not "good" counted as a gap, including "warn" (only checkable inside the
  // account), so a green 92 sat beside "Customers are missing key details".
  const categoryGap = data.findings.gbp?.auditRows?.find((row) => row.label === "Categories" && row.status === "bad");
  const profileStrong = scores.profile != null && scores.profile >= 80;
  const profileFinding = locale === "de"
    ? categoryGap ? "Einige Kategorien könnten Kunden ein falsches Bild vom Angebot geben."
      : profileStrong ? "Das Profil beantwortet die wichtigsten Fragen der Kunden." : "Kunden fehlen wichtige Angaben, bevor sie Kontakt aufnehmen."
    : categoryGap ? "Some categories may give customers the wrong idea about the service."
      : profileStrong ? "The profile answers the main questions customers have." : "Customers are missing key details before they get in touch.";
  const websiteStrong = scores.website != null && scores.website >= 80;
  const websiteFinding = locale === "de"
    ? websiteStrong ? "Die Seite macht es Kunden leicht, sich zu entscheiden und den nächsten Schritt zu gehen."
      : scores.lighthouse != null && scores.lighthouse >= 70 ? "Die Seite lädt gut, aber Kunden finden wenig Beleg und keinen klaren nächsten Schritt." : "Eine langsame oder unklare Seite verliert Kunden, bevor sie sich entscheiden."
    : websiteStrong ? "The website makes it easy for customers to decide and take the next step."
      : scores.lighthouse != null && scores.lighthouse >= 70 ? "The site loads well, but customers find little proof and no clear next step." : "A slow or unclear page loses customers before they decide.";
  // The walkthrough is one video for every report (lead-magnet-offer.ts); a
  // row's own Loom still wins. The legacy dev hint remains in the data,
  // but only a real URL renders a stage in either environment.
  const heroVideo = data.heroVideo?.url ? data.heroVideo : undefined;
  const hasHeroVideo = Boolean(heroVideo?.url);

  return (
    <ReportMotion><main data-template="upwork-lead-magnet-v1" className="lm-report relative min-h-screen overflow-x-clip bg-canvas text-ink">
      <ProposalStyles /><LeadMagnetStyles />
      {/* DIE KOPFZEILE BLEIBT STEHEN UND TRAEGT DEN TERMIN (the reviewer, 06.09.2026). Der Bericht
          ist lang; wer auf halber Strecke ueberzeugt ist, soll nicht erst ans Ende scrollen
          muessen. Milchglas, damit der Text darunter durchscheint statt abgeschnitten zu wirken. */}
      <header className="sticky top-0 z-40 bg-canvas/80 px-5 backdrop-blur-md sm:px-8"><nav className="mx-auto flex min-h-[68px] max-w-[1160px] items-center justify-between gap-5 border-b border-black/15"><span className="inline-flex items-center gap-2.5 sm:gap-3"><strong className="text-[13px] tracking-[-.01em]">Private audit</strong>{data.clientFaviconUrl || data.clientName ? <><span aria-hidden className="text-[15px] font-semibold text-pewter">×</span>{/* Im Kopf dunkler Grund mit weisser Schrift: `bg-navy-soft` faellt hier dunkel aus, und
    der Buchstabe war auf dem Bildschirm kaum zu lesen (nachgesehen 06.09.2026). */}
<KundenZeichen url={data.clientFaviconUrl} name={data.clientName} klasseBild="size-7 rounded-md object-cover" klasseErsatz="grid size-7 place-items-center rounded-md bg-navy text-[11px] font-black text-white" /><span className="hidden max-w-[220px] truncate text-[13px] font-bold text-ink sm:inline">{data.clientName}</span></> : null}</span><KapitelLeiste aktiv={aktivesKapitel} locale={locale} /><span className="flex items-center gap-3 sm:gap-4">{data.onePager?.url ? (<button type="button" onClick={() => setPosterOpen(true)} className="hidden min-h-9 items-center gap-1.5 rounded-full border border-black/15 px-3.5 text-[12.5px] font-bold text-graphite hover:border-navy/35 hover:bg-navy-soft/50 hover:text-navy sm:inline-flex"><svg viewBox="0 0 16 16" fill="none" aria-hidden className="size-3.5"><rect x="2.5" y="2" width="11" height="12" rx="1.6" stroke="currentColor" strokeWidth="1.6" /><path d="M5.5 6h5M5.5 9h5M5.5 12h3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>{locale === "de" ? "Report auf einer Seite" : "Report in one page"}</button>) : null}<a href="#kapitel-befund" className="lm-cta inline-flex min-h-9 items-center gap-1.5 rounded-full bg-navy px-4 text-[12.5px] font-black text-white no-underline sm:px-5 sm:text-[13px]">{locale === "de" ? "Befunde ansehen" : "See the findings"}<svg viewBox="0 0 16 16" fill="none" aria-hidden className="size-3.5"><path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></a></span></nav></header>

      <section className="lm-hero relative px-5 py-8 sm:px-8 sm:py-11"><div aria-hidden className="pointer-events-none absolute -right-16 top-8 text-[clamp(80px,13vw,190px)] font-black tracking-[-.08em] text-navy/[.035] [writing-mode:vertical-rl]">PRIVATE</div><div className={`relative mx-auto grid max-w-[1160px] items-center gap-7 ${hasHeroVideo ? (heroVideo?.portrait ? "lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-x-10 lg:gap-y-7" : "lg:grid-cols-[minmax(0,1fr)_530px] lg:gap-x-10 lg:gap-y-7") : ""}`}><div className={hasHeroVideo ? "" : "max-w-[760px]"}><span className="inline-flex max-w-full items-center gap-3 rounded-full border border-black/10 bg-white/85 py-2 pl-2 pr-5 shadow-xs"><KundenZeichen url={data.clientFaviconUrl} name={data.clientName} klasseBild="size-11 rounded-full object-cover" klasseErsatz="grid size-11 place-items-center rounded-full bg-navy-soft text-[15px] text-navy" /><span className="min-w-0"><span className="lm-datenlabel block">{t.preparedFor}</span><span className="block truncate text-[17px] font-black leading-tight tracking-[-.02em] sm:text-[19px]">{data.clientName}</span></span></span><h1 className="mt-5 max-w-[10ch] text-[clamp(42px,4.8vw,66px)] font-black leading-[.98] tracking-[-.055em]">{t.title}</h1>{heroHook ? <p data-onepager="hook" className="mb-0 mt-4 max-w-[600px] text-[17px] font-semibold leading-[1.35] text-slate-800 sm:text-[19px]">{heroHook}</p> : null}{/* DER TERMIN STEHT SCHON HIER (the reviewer, 06.09.2026). Wer nach dem ersten Satz ueberzeugt
                    ist, soll nicht acht Bildschirme weit scrollen muessen, um zu buchen. */}
                <div className="mt-7 flex flex-wrap items-center gap-x-4 gap-y-2"><a href="#kapitel-befund" className="lm-cta inline-flex min-h-12 items-center gap-2 rounded-xl bg-navy px-6 text-[15px] font-black text-white no-underline">{locale === "de" ? "Befunde ansehen" : "See the findings"}<svg viewBox="0 0 16 16" fill="none" aria-hidden className="size-4"><path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></a></div></div>{hasHeroVideo ? <HeroVisual data={{ ...data, heroVideo }} /> : null}
        {/* WAS WIR ANGESEHEN HABEN (the reviewer, 06.09.2026). Die drei Kacheln standen ohne
            Ueberschrift da und mussten selbst erklaeren, was sie sind - die Zeile darueber
            macht aus drei Begriffen eine Aussage: das ist der Umfang der Pruefung. */}
        <div className={hasHeroVideo ? "lg:col-span-2" : ""}>
        {/* Der Beleg, wer das geschrieben hat. Der Rand ist gezeichnet und nicht
          gerechnet: vier leicht unterschiedliche Pfade, damit die Karten nicht
          gestempelt wirken. Die beiden Marken sind die einzigen fremden Farben
          im Dokument, damit der Leser sie als Beleg liest und nicht als
          Fussnote (the reviewer, 07.09.2026). */}
        {(data.reviews?.items?.length ?? 0) > 0 ? (
        <section aria-label={locale === "de" ? "Wer diesen Bericht geschrieben hat" : "Who wrote this report"} className="lm-beleg mb-5">
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-3">
              <p className="m-0 max-w-[52ch] text-[12.5px] leading-[1.45] text-graphite">
                {locale === "de"
                  ? `${data.preparedBy || "Der Freelancer"} hat diesen Bericht erstellt. Die Bewertungen auf dem Upwork-Profil sind öffentlich prüfbar.`
                  : `${data.preparedBy || "The freelancer"} put this report together. The reviews on the Upwork profile are public and checkable.`}
              </p>
              <span className="flex items-center gap-2.5">
                <a href={data.reviews?.profileUrl ?? UPWORK_PROFIL} target="_blank" rel="noreferrer" className="lm-marke inline-flex items-center gap-1.5 rounded-full border border-hairline bg-white px-3 py-1.5 no-underline">
                  <svg viewBox="0 0 24 24" className="size-4" aria-hidden fill="#14A800">
                    <path d="M18.6 5.4c-2.6 0-4.5 1.7-5.3 4.4-1.2-1.8-2.1-4-2.6-5.9H7.9v7.1c0 1.4-1.1 2.5-2.5 2.5S2.9 12.4 2.9 11V3.9H0V11c0 3 2.4 5.5 5.4 5.5s5.4-2.5 5.4-5.5v-1.2c.5 1 1.2 2.1 2 3l-1.7 8.2h2.9l1.2-5.8c1.1.7 2.3 1.1 3.4 1.1 2.9 0 5.4-2.4 5.4-5.6s-2.5-5.3-5.4-5.3zm0 8c-.9 0-1.9-.4-2.7-1l.3-1c.2-1.3 1-3.4 2.5-3.4 1.3 0 2.4 1.1 2.4 2.4s-1.1 3-2.5 3z" />
                  </svg>
                  <span className="text-[13px] font-black text-ink">Upwork</span>
                </a>
                <a href={YOUTUBE_KANAL} target="_blank" rel="noreferrer" className="lm-marke inline-flex items-center gap-1.5 rounded-full border border-hairline bg-white px-3 py-1.5 no-underline">
                  <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
                    <path fill="#FF0000" d="M23.5 6.5a3 3 0 0 0-2.1-2.1C19.5 3.9 12 3.9 12 3.9s-7.5 0-9.4.5A3 3 0 0 0 .5 6.5C0 8.4 0 12 0 12s0 3.6.5 5.5a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.5.5-5.5s0-3.6-.5-5.5z" />
                    <path fill="#fff" d="M9.6 15.6 15.8 12 9.6 8.4z" />
                  </svg>
                  <span className="text-[13px] font-black text-ink">YouTube</span>
                </a>
              </span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(data.reviews?.items ?? []).slice(0, 4).map((review, index) => (
                <figure key={index} className="lm-beleg-karte relative m-0 self-start px-4 pb-3.5 pt-3">
                  {/* Ein Comic-Panel: kraeftige Kontur und ein zweiter Strich,
                      der nach unten rechts versetzt liegt. Kein weicher
                      Schatten - eine Zeichnung wirft keinen, sie hat eine
                      zweite Linie. `non-scaling-stroke` haelt beide gleich
                      dick, egal wie breit die Karte wird. */}
                  <svg className="pointer-events-none absolute inset-0 size-full overflow-visible" viewBox="0 0 320 190" preserveAspectRatio="none" aria-hidden>
                    <rect x="7" y="7" width="313" height="183" rx="14" fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" opacity=".3" />
                    <rect x="2" y="2" width="313" height="183" rx="14" fill="#fff" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  </svg>
                  <div className="relative flex gap-0.5" role="img">
                    {/* Kein aria-label an diesem div: eine bestehende Regel im
                        Bericht gibt jedem Element mit aria-label einen Pillen-
                        rahmen, und der lief hier als Balken neben den Sternen
                        durch die Karte (07.09.2026). */}
                    <span className="sr-only">5 out of 5</span>
                    {[0, 1, 2, 3, 4].map((stern) => (
                      <svg key={stern} viewBox="0 0 20 19" className="size-[14px]" aria-hidden>
                        <path d="M10 1.4l2.6 5.4 5.9.8-4.3 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L1.5 7.6l5.9-.8z" fill="#F2A93B" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
                      </svg>
                    ))}
                  </div>
                  <blockquote className="relative m-0 mt-2.5">
                    <p className="m-0 text-[12.5px] leading-[1.5] text-slate-800">{review.quote}</p>
                  </blockquote>
                  <figcaption className="relative mt-3 text-[9.5px] font-semibold uppercase leading-[1.4] tracking-[.08em] text-pewter">
                    {review.job}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>
        ) : null}
        <p className="lm-blockmarke m-0 mb-2">{t.checkedTitle}</p>
        <div className="grid overflow-hidden rounded-[16px] border border-black/10 bg-white/75 shadow-[0_8px_24px_rgba(28,23,18,.04)] sm:grid-cols-3">
          {/* EIGENE ZEICHEN STATT SYMBOLE VON DER STANGE (the reviewer, 06.09.2026: „coolere Icons
              fuer den mehr Custom-Look"). Jedes zeigt die Sache selbst -- eine Seite mit
              Anruf-Knopf, ein Profilkaertchen mit Bewertung, ein Kartenausschnitt mit
              Stecknadel. */}
          {[
            [ZeichenWebsite, t.checkedWebsite],
            [ZeichenProfil, t.checkedProfile],
            [ZeichenSichtbarkeit, t.checkedVisibility],
          ].map(([Zeichen, title], index) => {
            const CheckedIcon = Zeichen as typeof ZeichenWebsite;
            return <article key={String(title)} className={`flex items-center gap-3 px-4 py-3.5 sm:px-5 ${index ? "border-t border-black/10 sm:border-l sm:border-t-0" : ""}`}><span className="lm-glas grid size-9 shrink-0 place-items-center rounded-[11px] text-navy"><CheckedIcon /></span><strong className="block text-[13px] font-black leading-tight">{String(title)}</strong></article>;
          })}
        </div>
        </div>
      </div></section>

      <LossesSection locale={locale} />

      <section className="lm-analysis border-y border-black/10 bg-[#f4f1ea] px-5 py-10 sm:px-8 sm:py-12"><div className="mx-auto max-w-[1160px]"><SektionsKopf kapitel={KAPITEL.befund} locale={locale} className="mb-8 sm:mb-10" /><section aria-label={t.summary} className="mb-10 sm:mb-14"><ExecutiveActions items={executiveActions} locale={locale} onViewEvidence={setOpen} /></section>

      <div className="lm-scorecard overflow-hidden rounded-[24px] border border-[#d7d4cd] bg-white shadow-[0_18px_52px_rgba(28,23,18,.08)]"><div className="flex items-center justify-between bg-navy-deep px-5 py-5 text-white sm:px-7"><h2 className="m-0 text-[20px] font-black leading-none tracking-[-.025em] sm:text-[23px]">{t.stand}</h2><strong className="tnum text-[46px] font-black leading-none tracking-[-.06em] text-[#f1cf67] sm:text-[58px]"><CountUp value={scores.overall} id="overall" /><small className="ml-1 text-[15px] text-[#aab8e8]">/100</small></strong></div>
        <Accordion sectionKey="maps" open={open === "maps"} onToggle={() => oeffneSaeule("maps")} kicker={t.mapsKicker} title={t.maps} score={scores.maps} finding={mapsVerdict} locale={locale}><div className="grid gap-6 lg:grid-cols-[minmax(320px,.95fr)_minmax(0,1.05fr)]">{data.findings.geoGrid ? <GeoGrid data={data.findings.geoGrid} showNote={false} /> : null}<div className="grid content-start gap-4"><div className="rounded-2xl border border-hairline bg-white p-5"><p className="m-0 text-[16px] font-bold leading-[1.5]">{mapPosition ?? mapReading}</p>{mapWeakSide ? <p className="mb-0 mt-2 text-[13px] leading-[1.45] text-graphite">{mapWeakSide}</p> : null}{mapField ? <p className="mb-0 mt-2 text-[13px] leading-[1.45] text-graphite">{mapField}</p> : null}</div>{data.findings.geoGrid?.winners?.length ? <div className="rounded-2xl border border-hairline bg-white p-5"><h3 className="text-lg font-black">{t.mapWinners}</h3><ul className="m-0 mt-3 list-none p-0">{[...data.findings.geoGrid.winners.slice(0, 3).map((winner) => ({ label: winner.name, category: winner.category ?? null, points: winner.topThreePoints, reviews: winner.reviews, rating: winner.rating, mine: false })), ...(data.findings.geoGrid.client ? [{ label: t.you, category: data.findings.gbp?.current?.categories?.primary ?? null, points: data.findings.geoGrid.client.topThreePoints, reviews: data.findings.geoGrid.client.reviews, rating: data.findings.geoGrid.client.rating, mine: true }] : [])].sort((a, b) => b.points - a.points).map((row) => <li key={row.label} className={`grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 border-t border-slate-100 py-2 text-[13px] first:border-t-0 ${row.mine ? "font-black text-navy" : "text-slate-800"}`}><span className="min-w-0 truncate">{row.label}</span><span className="tnum whitespace-nowrap text-right text-[12px] text-graphite"><b className={row.mine ? "text-navy" : "text-slate-900"}>{row.points}</b>/{ranks.length || 25}{row.rating != null ? ` · ${Number(row.rating).toFixed(1)}★` : ""}{row.reviews != null ? ` · ${row.reviews}` : ""}</span></li>)}</ul>{data.findings.geoGrid.winners[0].topThreePoints < 10 ? <p className="mb-0 mt-3 text-[12px] leading-[1.45] text-graphite">{t.fragmented(data.findings.geoGrid.winners[0].topThreePoints)}</p> : null}</div> : null}</div></div>{data.search?.organic ? <OrganicSection organic={data.search.organic} locale={locale} /> : null}</Accordion>
        <Accordion sectionKey="profile" open={open === "profile"} onToggle={() => oeffneSaeule("profile")} kicker={t.profileKicker} title={t.profile} score={scores.profile} finding={profileFinding} locale={locale}>{data.findings.gbp ? <GbpPanel icons={reportProfileIcons} data={{ ...data.findings.gbp, locale }} requireComplete={data.templateVersion === "lead-magnet-v1"} /> : null}</Accordion>
        <Accordion sectionKey="website" open={open === "website"} onToggle={() => oeffneSaeule("website")} kicker={t.websiteKicker} title={t.website} score={scores.website} finding={websiteFinding} locale={locale}><WebsiteDetail data={data} locale={locale} /></Accordion>
      </div></div></section>

      {data.onePager?.url && posterOpen ? (
        <div role="dialog" aria-modal="true" aria-label={locale === "de" ? "Ihr ganzer Report auf einer Seite" : "Your full report in one page"} onClick={() => setPosterOpen(false)} className="fixed inset-0 z-[80] flex flex-col items-center gap-3 overflow-auto bg-ink/85 p-4 backdrop-blur-sm sm:p-8">
          <div className="sticky top-0 z-10 flex w-full max-w-[860px] items-center justify-between gap-4 text-white">
            <a href={data.onePager.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} className="text-[13px] font-bold text-white underline underline-offset-4">{locale === "de" ? "In neuem Tab öffnen ↗" : "Open in a new tab ↗"}</a>
            <button type="button" onClick={() => setPosterOpen(false)} className="rounded-full bg-white/15 px-4 py-2 text-[13px] font-bold text-white">{locale === "de" ? "Schließen" : "Close"}</button>
          </div>
          <img src={data.onePager.url} alt={locale === "de" ? `Zusammenfassung für ${data.clientName}` : `One-page summary for ${data.clientName}`} onClick={(event) => event.stopPropagation()} className="w-full max-w-[860px] rounded-xl bg-white shadow-[0_24px_80px_rgba(0,0,0,.45)]" />
        </div>
      ) : null}
      <SolutionSection locale={locale} />
      <CloseSection data={data} locale={locale} onPoster={() => setPosterOpen(true)} />
      {/* Die sechs Fragen, die auf jedem Gespraech kommen, unter dem Kalender:
          wer bucht, liest sie nicht mehr, und wer nicht bucht, hat genau
          dort seine Einwaende (the reviewer, 07.09.2026). Die
          Antworten liegen laengst in den Daten und wurden nur nie gezeigt. */}
      {(data.faq?.length ?? 0) > 0 ? (
        <section aria-label={locale === "de" ? "Häufige Fragen" : "Common questions"} className="border-t border-black/10 bg-[#f4f1ea] px-5 py-10 sm:px-8 sm:py-12">
          <div className="mx-auto max-w-[880px]">
            <p className="lm-datenlabel m-0">{locale === "de" ? "Bevor Sie fragen" : "Before you ask"}</p>
            <h2 className="mt-2 text-[clamp(26px,3vw,36px)] font-black leading-[1.05] tracking-[-.04em]">
              {locale === "de" ? "Was an dieser Stelle immer gefragt wird." : "What everyone asks at this point."}
            </h2>
            <dl className="mt-6 grid gap-3">
              {(data.faq ?? []).slice(0, 10).map((eintrag, index) => (
                <div key={index} className="rounded-2xl border border-hairline bg-white p-5">
                  <dt className="m-0 text-[15px] font-black text-slate-950">{eintrag.q}</dt>
                  <dd className="m-0 mt-2 text-[14px] leading-[1.55] text-graphite">{eintrag.a}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      ) : null}

      <footer className="bg-[#f3efe6] px-5 py-7"><div className="mx-auto flex max-w-[1160px] items-center justify-between gap-4 text-[9px] text-pewter"><strong>Private website audit</strong><span>{t.footer} · {data.dateLabel}</span></div></footer>
      {showSticky ? <a href="#reply" className="fixed inset-x-3 bottom-3 z-50 flex min-h-12 items-center justify-center rounded-xl bg-navy px-5 text-sm font-black text-white shadow-2xl sm:hidden">{locale === "de" ? "Auf Upwork antworten" : "Reply on Upwork"}</a> : null}
    </main></ReportMotion>
  );
}
