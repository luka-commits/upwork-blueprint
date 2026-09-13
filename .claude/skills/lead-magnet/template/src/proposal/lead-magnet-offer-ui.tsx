"use client";

/* The offer on the cold report: named, not explained.
 *
 * One rule for every disclosure here (Luka, 06.09.2026, nach der Schienen-Fassung):
 * closed is an icon and a headline; open is ONE sentence saying what it is and one
 * saying what the owner gets from it. Kein Bild, keine Aufzählung, keine Zeichnung.
 * Die ausführliche Beschreibung gehört auf die Angebotsseite für das Gespräch; die
 * Kaltakquise entscheidet nur darüber, ob jemand antwortet. */

import { useState } from "react";
import { ChevronDown } from "./service-icons";
import type { GanttBar, GanttPlan, ProposalData } from "./types";
import { LEAD_MAGNET_OFFER, type OfferPillar } from "./lead-magnet-offer";
import { SERVICE_TEXT } from "./lead-magnet-services";
import { barWeeks } from "./plan-weeks";
import { usePackage } from "./packages";
import { LeistungsZeichen } from "./lead-magnet-solution";

type Locale = "en" | "de";

/** A video embed that exists only when its URL does. */
export function VideoStage({ url, title }: { url: string; title: string }) {
  if (!url) return null;
  return (
    <figure className="m-0 overflow-hidden rounded-[14px] border border-black/10 bg-navy-deep">
      <div className="aspect-video"><iframe src={url} title={title} allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture" allowFullScreen className="h-full w-full border-0" /></div>
    </figure>
  );
}

/** Der geöffnete Service: EIN Satz und das Paket.
 *
 *  Der Weg dahin, in einer Nacht (Luka, 05./06.09.2026): erst eine Drei-Stationen-Schiene
 *  mit gezeichneten Bildschirmen und vier Merkmalszeilen, dann zwei Sätze, jetzt einer.
 *  Der zweite Satz war jedes Mal eine allgemeine Wahrheit über die Branche ("die meisten
 *  Anfragen bekommt der, der zuerst antwortet") — richtig, aber austauschbar, und
 *  austauschbar ist in einer Kaltakquise dasselbe wie überflüssig. Was hier steht, muss
 *  sagen, was der Dienst IST. Warum er zählt, sagt der Befund weiter oben, der an diesem
 *  Betrieb gemessen wurde. */
export function ServiceOpen({ bar, locale }: { bar: GanttBar; locale: Locale }) {
  const video = bar.code ? LEAD_MAGNET_OFFER.videos[bar.code] : "";
  const satz = bar.code ? SERVICE_TEXT[bar.code]?.[locale] : "";
  // KEIN PAKET-VERMERK MEHR (Luka, 06.09.2026). Die Zeile steht ohnehin nur im gewählten
  // Paket, und "In every package" unter jedem Kasten war eine Notiz an uns, keine
  // Information für den Empfänger.
  return (
    <div className={video ? "grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:items-center" : "grid gap-2"}>
      {video ? <VideoStage url={video} title={bar.name} /> : null}
      {satz ? <p className="m-0 text-[15px] leading-[1.45] text-slate-900">{satz}</p> : null}
    </div>
  );
}

/** What Pocket CEO would run in this part of the report: three tiles that
 *  name build-plan rows by code, one open at a time, the open one below the
 *  row at full width. */
export function OfferStrip({ pillar, data, locale }: { pillar: OfferPillar; data: ProposalData; locale: Locale }) {
  const config = LEAD_MAGNET_OFFER.pillars[pillar];
  const bars = config.codes.map((code) => data.gantt?.bars.find((bar) => bar.code === code)).filter((bar): bar is GanttBar => Boolean(bar));
  const [openCode, setOpenCode] = useState<string | null>(null);
  const openBar = bars.find((bar) => bar.code === openCode);
  if (!bars.length) return null;
  return (
    <div className="lm-offer mt-6 rounded-2xl border border-navy/15 bg-navy-soft/40 p-4 sm:p-5">
      <p className="lm-blockmarke m-0">{locale === "de" ? "Was wir hier für Sie aufsetzen würden" : "What we would run for you here"}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3 sm:gap-3">
        {bars.map((bar) => {
          const open = bar.code === openCode;
          return (
            <button key={bar.code} type="button" aria-expanded={open} onClick={() => setOpenCode(open ? null : bar.code ?? null)} className={`flex items-center gap-3 rounded-xl border p-3 text-left transition ${open ? "border-navy bg-navy text-white" : "border-hairline bg-white text-slate-900 hover:border-navy/40"}`}>
              <span className={`grid size-9 shrink-0 place-items-center rounded-[11px] ${open ? "bg-white/15 text-white" : "lm-glas text-navy"}`}><LeistungsZeichen code={bar.code} className="size-[19px]" /></span>
              <b className="min-w-0 flex-1 text-[14px] leading-[1.25]">{bar.name}</b>
              <ChevronDown className={`size-4 shrink-0 transition ${open ? "rotate-180" : "text-navy"}`} aria-hidden />
            </button>
          );
        })}
      </div>
      {openBar ? <div data-lm-motion={`offer-${pillar}-${openCode}`} className="mt-3 rounded-xl border border-hairline bg-white p-4 sm:p-5"><ServiceOpen bar={openBar} locale={locale} /></div> : null}
      {config.videoUrl ? <div className="mt-4"><VideoStage url={config.videoUrl} title={locale === "de" ? "Kurz erklärt" : "A short explainer"} /></div> : null}
    </div>
  );
}

/** The plan on a phone: weeks down the left, what starts in each week as
 *  tappable tiles, the open tile's picture below. A nine-column chart at
 *  390 px is a smear; this is the same plan read the way a phone reads. */
export function PlanMobile({ plan, locale }: { plan: GanttPlan; locale: Locale }) {
  const shared = usePackage();
  const [openName, setOpenName] = useState<string | null>(null);
  const pick = shared?.pick ?? plan.packages.find((p) => p.recommended)?.name ?? plan.packages[0]?.name ?? "";
  const active = plan.packages.find((p) => p.name === pick);
  const weeks = active?.weeks ?? Math.max(...plan.packages.map((p) => p.weeks), 1);
  const rows = plan.bars.filter((bar) => bar.packages.includes(pick)).map((bar) => ({ bar, ...barWeeks(bar, pick, plan.packages) }));
  const byWeek = Array.from({ length: weeks }, (_, index) => index + 1).map((week) => ({
    week,
    starts: rows.filter(({ from, spots }) => (spots ? spots[0] === week : from === week)),
  })).filter((entry) => entry.starts.length);
  const openBar = rows.find(({ bar }) => bar.name === openName)?.bar;
  // The phone plan is a small Gantt, not a list of cards: one line per row,
  // the weeks as cells on the right, so the whole plan fits on one screen
  // (Luka, 05.09.2026: "für mobile müssen wir das Design klar überarbeiten").
  const weekList = Array.from({ length: weeks }, (_, index) => index + 1);
  const inWeek = (row: { from: number; to: number; spots?: number[] }, week: number) => (row.spots ? row.spots.includes(week) : week >= row.from && week <= row.to);
  void byWeek;
  return (
    <div className="lm-mobile-plan md:hidden">
      <div className="mt-4 overflow-hidden rounded-xl border border-hairline bg-white">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-hairline bg-[#f7f5f0] px-3 py-1.5">
          <span className="text-[9px] font-black uppercase tracking-[.08em] text-graphite">{locale === "de" ? "Was" : "What"}</span>
          <span className="flex gap-[3px]">{weekList.map((week) => <span key={week} className="tnum w-3.5 text-center text-[8px] font-bold text-graphite">{week}</span>)}</span>
        </div>
        {rows.map((row) => {
          const open = row.bar.name === openName;
          return (
            <div key={row.bar.name} className="border-t border-hairline first:border-t-0">
              <button type="button" aria-expanded={open} onClick={() => setOpenName(open ? null : row.bar.name)} className={`grid w-full grid-cols-[22px_minmax(0,1fr)_auto] items-center gap-2 px-3 py-2 text-left ${open ? "bg-navy-soft/60" : "bg-white"}`}>
                <span className="lm-glas grid size-[24px] place-items-center rounded-[8px] text-navy"><LeistungsZeichen code={row.bar.code} className="size-[14px]" /></span>
                <b className="min-w-0 text-[12px] font-semibold leading-[1.2] text-slate-900">{row.bar.name}</b>
                <span className="flex items-center gap-[3px]">{weekList.map((week) => <span key={week} data-grow data-lm-motion={inWeek(row, week) ? `mobile-bar-${row.bar.code}-${week}` : undefined} className={`h-2.5 w-3.5 rounded-[3px] ${inWeek(row, week) ? "bg-navy" : "bg-slate-100"}`} />)}{row.bar.ongoing ? <span className="ml-0.5 text-[9px] leading-none text-navy">→</span> : <span className="ml-0.5 w-[7px]" />}</span>
              </button>
              {open && openBar ? <div data-lm-motion={`mobile-detail-${row.bar.code}`} className="border-t border-hairline bg-[#fafaf8] p-3"><ServiceOpen bar={openBar} locale={locale} /></div> : null}
            </div>
          );
        })}
      </div>
      <p className="mb-0 mt-2 text-[10px] leading-[1.4] text-graphite">{locale === "de" ? "→ läuft nach dem Start weiter · Zeile antippen für Details" : "→ keeps running after go-live · tap a row for what it includes"}</p>
    </div>
  );
}
