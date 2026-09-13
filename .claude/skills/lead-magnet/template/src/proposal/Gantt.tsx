"use client";
// The build plan as a Gantt that redraws itself per package.
//
// The point is not decoration. The tiers differ in what gets built and
// therefore in how long the build takes, and a chart that changes when you
// switch package makes that difference visible in one glance - where a price
// list only asserts it. Rows outside the selected package stay on screen,
// greyed, so the client also sees what the next step up would add and what it
// would cost in weeks.
//
// With `detail`, every row opens: what they actually receive, what we need from
// them, and the one checkable thing that is true when the phase is done. That
// is the version we drive the call through - a bar chart answers "when", and
// the only question a buyer asks out loud is "what do I get".
//
// Design ported from the live Automatable audit (DOM captured 29 August 2026,
// work/2026-08-29_jono-vorbilder/dom/): same palette, same mono kickers, same
// pill idiom.
import { useState, type ReactNode } from "react";
import type { GanttBar, GanttPlan } from "./types";
import { usePackage } from "./packages";
import { ServiceIcon } from "./service-icons";

function RowDetail({ bar }: { bar: GanttBar }) {
  return (
    <div className="mt-2 mb-1 rounded-xl border border-[#E4E1D9] bg-[#fbf9f4] px-4 py-3.5">
      {/* What we actually do, before what they get. The list answers "what is
          included"; this answers "what does that mean", which is the question
          that actually gets asked out loud. */}
      {bar.description ? (
        <p className="m-0 mb-3.5 max-w-[68ch] text-[13.5px] leading-relaxed text-[#3d3933]">
          {bar.description}
        </p>
      ) : null}

      {bar.deliverables?.length ? (
        <>
          <p className="font-mono text-[9px] uppercase tracking-[1px] text-[#717171] m-0">What you get</p>
          <ul className="mt-2 mb-0 list-none p-0 grid gap-1.5">
            {bar.deliverables.map((dv) => (
              <li key={dv} className="flex gap-2.5 text-[13.5px] leading-snug text-[#262019]">
                <span className="mt-[7px] h-1 w-1 flex-shrink-0 rounded-full bg-[#153AA1]" aria-hidden />
                {dv}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {bar.milestone || bar.needsFromClient ? (
        <div className="mt-3 flex flex-wrap gap-x-8 gap-y-2 border-t border-[#E4E1D9] pt-3">
          {bar.milestone ? (
            <p className="m-0 max-w-[46ch] text-[12.5px] leading-relaxed text-[#5C5E62]">
              <span className="font-mono text-[9px] uppercase tracking-[1px] text-[#717171]">Done when</span>
              <br />
              {bar.milestone}
            </p>
          ) : null}
          {bar.needsFromClient ? (
            <p className="m-0 max-w-[46ch] text-[12.5px] leading-relaxed text-[#5C5E62]">
              <span className="font-mono text-[9px] uppercase tracking-[1px] text-[#717171]">We need from you</span>
              <br />
              {bar.needsFromClient}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function Gantt({
  plan,
  showPackages = true,
  detail = false,
  valueLabel = "worth/mo",
  renderDetail,
  hideOutOfPlan = false,
  variant = "default",
}: {
  plan: GanttPlan;
  /** Visual treatment scoped to the cold report; contracts keep the default. */
  variant?: "default" | "report";
  showPackages?: boolean;
  /** Zeilen ausblenden, die im gewählten Paket nicht enthalten sind. Im Kaltreport ist das
   *  Pflicht: ausgegraut bewarben sie genau das, was der Empfänger NICHT bekommt (the reviewer,
   *  06.09.2026). Im Vertrag bleiben sie sichtbar, dort sind sie der Ausbauweg. */
  hideOutOfPlan?: boolean;
  /** Rows open to show deliverables, milestone and what we need from them. */
  detail?: boolean;
  /** Header of the right column. The cold report carries no worth figures,
   *  so it reads "in plan" there instead of "worth/mo". */
  valueLabel?: string;
  /** The cold report opens a row to a picture and three lines instead of
   *  the long detail; when set, every row opens and this draws it. */
  renderDetail?: (bar: GanttBar) => ReactNode;
}) {
  const shared = usePackage();
  const [local, setLocal] = useState(
    plan.packages.find((p) => p.recommended)?.name ?? plan.packages[0]?.name ?? ""
  );
  // Outside a provider the chart keeps its own state, which is what the cold
  // proposal and the agreement rely on.
  const pick = shared?.pick ?? local;
  const setPick = shared?.setPick ?? setLocal;

  const [open, setOpen] = useState<string | null>(null);
  const active = plan.packages.find((p) => p.name === pick) ?? plan.packages[0];
  const weeks = Math.max(...plan.packages.map((p) => p.weeks), 1);
  const cols = Array.from({ length: weeks }, (_, i) => i + 1);

  return (
    <div className={variant === "report" ? "lm-gantt" : undefined}>
      {/* Package switch. Hidden on the cold proposal: there is no price on that
          page, so a row of price buttons would answer a question the document
          has deliberately not raised yet. */}
      {showPackages ? (
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {plan.packages.map((p) => {
          const on = p.name === pick;
          return (
            <button
              key={p.name}
              type="button"
              onClick={() => setPick(p.name)}
              aria-pressed={on}
              className={`inline-flex items-baseline gap-2 rounded-full border px-3.5 py-1.5 text-[13px] transition-colors ${
                on
                  ? "bg-[#153AA1] border-[#153AA1] text-white font-semibold"
                  : "bg-white border-[#E4E1D9] text-[#5C5E62] hover:border-[#c9c7bd]"
              }`}
            >
              {p.name}
              <span className={`tabular-nums text-[11.5px] ${on ? "text-white/80" : "text-[#717171]"}`}>
                {p.price} &middot; {p.weeks} wks
              </span>
            </button>
          );
        })}
      </div>
      ) : null}

      {/* Week header */}
      <div
        className="hidden md:grid gap-x-2 items-center mb-2"
        style={{ gridTemplateColumns: `minmax(180px, 250px) repeat(${weeks}, 1fr) 110px` }}
      >
        <span />
        {cols.map((w) => (
          <span
            key={w}
            className={`font-mono text-[9px] uppercase tracking-[1px] text-center ${
              w <= (active?.weeks ?? 0) ? "text-[#5C5E62]" : "text-[#c9c7bd]"
            }`}
          >
            wk {w}
          </span>
        ))}
        <span className="font-mono text-[9px] uppercase tracking-[1px] text-right text-[#717171]">{valueLabel}</span>
      </div>

      {plan.bars.filter((b) => !hideOutOfPlan || b.packages.includes(pick)).map((b) => {
        const inPlan = b.packages.includes(pick);
        // A tail bar is measured from the end of whichever package carries it,
        // so handover stays one week whether the build runs four or eight.
        const ownerWeeks = inPlan
          ? active?.weeks ?? b.to
          : plan.packages.find((p) => p.name === b.packages[0])?.weeks ?? b.to;
        // A row may run on a different schedule per package: Growth builds the
        // site after the keyword map, Starter builds it straight away.
        const scheduleOwner = inPlan ? pick : b.packages[0];
        const shifted = scheduleOwner ? b.weeksByPackage?.[scheduleOwner] : undefined;
        const from = b.lastWeeks
          ? Math.max(1, ownerWeeks - b.lastWeeks + 1)
          : shifted?.[0] ?? b.from;
        const to = b.lastWeeks ? ownerWeeks : shifted?.[1] ?? b.to;
        const clipped = Math.min(to, active?.weeks ?? to);
        // Discrete weeks win: a two-session row is two marks, not a span.
        const spots = b.atWeeks
          ? b.alsoAtLastWeek
            ? [...b.atWeeks, ownerWeeks]
            : b.atWeeks
          : undefined;
        const hasDetail =
          Boolean(renderDetail) ||
          (detail &&
          Boolean(b.description || b.deliverables?.length || b.milestone || b.needsFromClient));
        const isOpen = open === b.name;
        return (
          <div key={b.name} className="border-t border-[#E4E1D9] first:border-t-0">
          <div
            className={`md:grid gap-x-2 items-center py-2 ${hasDetail ? "cursor-pointer" : ""}`}
            style={{ gridTemplateColumns: `minmax(180px, 250px) repeat(${weeks}, 1fr) 110px` }}
            onClick={hasDetail ? () => setOpen(isOpen ? null : b.name) : undefined}
            role={hasDetail ? "button" : undefined}
            tabIndex={hasDetail ? 0 : undefined}
            aria-expanded={hasDetail ? isOpen : undefined}
            onKeyDown={
              hasDetail
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setOpen(isOpen ? null : b.name);
                    }
                  }
                : undefined
            }
          >
            <span className={`flex items-start text-[13.5px] leading-snug ${inPlan ? "text-[#0F1012]" : "text-[#a8a79f]"}`}>
              {hasDetail ? (
                <span
                  aria-hidden
                  className={`mr-1.5 inline-block text-[9px] text-[#717171] transition-transform ${isOpen ? "rotate-90" : ""}`}
                >
                  &#9654;
                </span>
              ) : null}
              <span className={`mr-2 inline-grid size-6 shrink-0 place-items-center rounded-md ${inPlan ? "bg-navy-soft text-navy" : "bg-[#f1efe9] text-[#a8a79f]"}`}><ServiceIcon variant={variant} category={b.category} code={b.code} tone="currentColor" size={13} /></span>
              <span className="min-w-0 pt-0.5">{b.name}
              {!inPlan ? (
                <span className="ml-2 inline-flex items-center rounded-full border border-[#E4E1D9] bg-white px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[1px] text-[#717171] align-middle">
                  {b.packages[0]}
                </span>
              ) : null}
              {b.because && inPlan ? (
                <span className="block text-[11.5px] text-[#717171] mt-0.5">{b.because}</span>
              ) : null}
              </span>
            </span>

            {/* Bars. On phones the grid collapses and the row reads as text,
                which is the right trade: a nine-column chart at 390px is a
                smear, and the week labels below carry the same information. */}
            {cols.map((w) => {
              const on = spots
                ? spots.includes(w) && w <= (active?.weeks ?? w)
                : w >= from && w <= clipped;
              const beyond = spots
                ? spots.includes(w) && w > (active?.weeks ?? w)
                : w >= from && w <= to && w > clipped;
              // Die Schiene liegt unter jeder Woche, der Balken darauf. Ohne sie schweben
              // die Balken im Weiß und die Zeile liest sich nicht als Zeitstrahl.
              return (
                <span key={w} className="hidden md:block px-0.5">
                  <span className="block h-2.5 rounded-full bg-[#efece4]">
                    <span
                      data-grow
                      data-lm-motion={variant === "report" && on && inPlan ? `plan-bar-${b.code}-${w}` : undefined}
                      className={`block h-2.5 rounded-full ${
                        on ? (inPlan ? "bg-gradient-to-r from-[#1B47C4] to-[#153AA1] shadow-[0_1px_2px_rgba(21,58,161,.35)]" : "bg-[#e0ded4]") : beyond ? "bg-[#E4E1D9]" : ""
                      }`}
                    />
                  </span>
                </span>
              );
            })}

            <span className="md:text-right block mt-1 md:mt-0">
              {b.worth ? (
                <span className={`tabular-nums text-[11.5px] ${inPlan ? "text-[#2f7d4f]" : "text-[#c9c7bd]"}`}>
                  +{b.worth}
                </span>
              ) : (
                <span className="font-mono text-[9px] uppercase tracking-[1px] text-[#717171]">
                  {b.ongoing ? "ongoing" : "included"}
                </span>
              )}
            </span>

            {/* A phase the chosen package does not include has no weeks in it.
                Clipping its range to the package length printed "weeks 6-6",
                which reads as a broken row rather than as "not in this plan". */}
            <span className="md:hidden block text-[11.5px] text-[#717171] mt-0.5">
              {inPlan ? (
                <>
                  {spots
                    ? `weeks ${spots.filter((w) => w <= (active?.weeks ?? w)).join(" and ")}`
                    : `weeks ${from}${clipped > from ? `-${clipped}` : ""}`}
                  {b.ongoing ? ", then ongoing" : ""}
                </>
              ) : (
                <>in {b.packages[0]}, weeks {from}{to > from ? `-${to}` : ""}</>
              )}
            </span>
          </div>
          {hasDetail && isOpen ? (renderDetail ? <div data-lm-motion={variant === "report" ? `plan-detail-${b.code}` : undefined} className="mb-3 rounded-xl border border-[#E4E1D9] bg-white p-4">{renderDetail(b)}</div> : <RowDetail bar={b} />) : null}
          </div>
        );
      })}

      {detail ? (
        <p className="mt-2 font-mono text-[9px] uppercase tracking-[1px] text-[#a8a79f]">
          Click any row for what it delivers
        </p>
      ) : null}
    </div>
  );
}
