// Shared building blocks for the proposal - ported from the idiom of the
// real Automatable proposals (dark page, radial glow hero, translucent
// glow-border cards, gradient display numbers) re-skinned to this site's
// terracotta ramp. The Google exhibits stay white on purpose: they read as
// screenshots of Google and pop against the dark ground.
import { Fragment, type ReactNode, type CSSProperties } from "react";

/** Light palette for the proposal page - the site's own warm ramp. */
// One warm ground for the whole document, white only on the cards. The old
// scheme alternated white and beige band by band, and every switch produced a
// visible seam. Paper below, cards above it: the hierarchy now comes from the
// cards lifting off the page rather than from the page changing colour.
// The palette of the pitch pages that go out by email
// (~/dev/projects/personal/upwork/outputs/2026-08-15_*.html), with Pocket CEO's
// navy in place of their terracotta. Warm paper as the ground, a deeper beige
// for alternate bands, and one dark ink band near the close for punch - the
// colour division is the band, never a card on a coloured page.
export const d = {
  page: "#f3efe6",       // warm paper
  panel: "#ece5d7",      // the deeper band
  ink: "#1c1712",        // the dark band
  onInk: "#f3efe6",
  onInk2: "#b8ad9c",
  card: "#fbf9f4",
  text: "#1c1712",
  body: "#262019",
  muted: "#5c5347",
  faint: "#6f6656",
  accent: "#153AA1",
  accentStrong: "#00185E",
  accentOnInk: "#8fa8ee",
  hairline: "1px solid #e2d9c8",
  hairlineColor: "#e2d9c8",
};

// Kept exports (light tokens) for the white Google-look exhibits.
export const text = {
  strong: "#0F1012",
  body: "#393C41",
  muted: "#5C5E62",
  brand: "#153AA1",
  link: "#153AA1",
};
export const surface = { sunken: "#F0EEE8", tint: "#eef1fa", card: "#ffffff", accent: "#1c201e" };
export const line = { hairline: "1px solid #E4E1D9" };

export const chart = {
  client: "#00185E",
  competitors: ["#6d6862", "#8f8a83", "#b5b2ab"],
  grid: "#E4E1D9",
  label: "#5C5E62",
};

export const heroBg = "linear-gradient(135deg, #00185E 0%, #153AA1 55%, #00185E 100%)";

/** Domains and paths may wrap after punctuation, never through a word. */
export function SoftBreakText({ value }: { value: string }) {
  return (
    <>
      {value.split(/([.-])/).map((part, index) => (
        <Fragment key={`${part}-${index}`}>
          {part}
          {part === "." || part === "-" ? <wbr /> : null}
        </Fragment>
      ))}
    </>
  );
}

/** One global stylesheet for the proposal page - the classes every section uses. */
export function ProposalStyles() {
  return (
    <style>{`
/* The dither field reads its two endpoint colours off these, the same token
   names the pitch pages use, so the ink takes this page's palette. */
:root{--border:#E4E1D9;--accent-deep:${d.accent};--text-2:${d.body};--accent-on-ink:${d.accentStrong}}
.pp{background:${d.page};color:${d.text};font-family:var(--font-core,"Archivo",sans-serif);min-height:100vh;position:relative}
/* Everything sits above the page-wide field; the field itself is fixed behind. */
.pp > *:not(.pp-dither-page-wrap){position:relative;z-index:1}
.pp ::selection{background:#dbe3f6;color:#0F1012}
.pp-inner{max-width:1152px;margin:0 auto;padding-left:24px;padding-right:24px}
.pp-kicker{font-size:11px;font-weight:700;letter-spacing:.28em;text-transform:uppercase;color:${d.accent};display:flex;align-items:center;gap:8px;margin:0}
.pp-h2{font-size:clamp(26px,3.4vw,38px);font-weight:900;letter-spacing:-.02em;line-height:1.1;color:${d.text};margin:14px 0 10px}
.pp-lead{color:${d.muted};font-size:16px;line-height:1.6;max-width:62ch;margin:0 0 34px}
.pp-section{padding:clamp(56px,7vw,96px) 0}
.pp-band-plain{background:${d.page}}
.pp-band-warm{background:${d.panel}}
.pp-band-ink{background:${d.ink};color:${d.onInk}}
.pp-band-ink .pp-kicker{color:${d.accentOnInk}}
.pp-band-ink .pp-h2{color:${d.onInk}}
.pp-band-ink .pp-lead{color:${d.onInk2}}
.pp-band-ink .pp-card{background:rgba(243,239,230,.05);border-color:rgba(243,239,230,.15)}
/* The story rail, pinned: which beat you are in, how many are left, and a hair
   of progress under it. Hidden over the hero, slides in once past it. */
.pp-rail{position:fixed;top:0;left:0;right:0;z-index:40;background:rgba(243,239,230,.93);
  backdrop-filter:blur(8px);border-bottom:1px solid ${d.hairlineColor};
  transform:translateY(-100%);transition:transform .28s cubic-bezier(.16,1,.3,1);pointer-events:none}
.pp-rail--on{transform:translateY(0)}
.pp-rail-inner{max-width:1152px;margin:0 auto;padding:9px 24px;display:flex;align-items:center;gap:12px}
.pp-rail-num{font-size:10px;font-weight:800;letter-spacing:.14em;color:${d.accent}}
.pp-rail-label{font-size:13px;font-weight:700;color:${d.text};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pp-rail-dots{display:none;margin-left:auto;gap:5px}
.pp-rail-dots span{width:5px;height:5px;border-radius:999px;background:${d.hairlineColor};display:block}
.pp-rail-dots span.on{background:${d.accent}}
.pp-rail-count{margin-left:auto;font-size:11px;color:${d.faint};font-variant-numeric:tabular-nums}
.pp-rail-progress{display:block;height:2px;background:${d.accent}}
@media(min-width:760px){
  .pp-rail-dots{display:flex}
  .pp-rail-count{margin-left:0}
}
.pp-sheet{padding:clamp(22px,3.4vw,34px)}
/* The money section: total on the left, the two leaks as comparable bars on the
   right, the arithmetic as chips underneath. */
.pp-money{display:grid;gap:26px 44px;align-items:center}
@media(min-width:880px){.pp-money{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
/* A range like "$27,531-$29,101" is twice as wide as a single figure, and at
   68px it ran straight into the bars beside it. Sized to the worst case, and
   allowed to break rather than overlap. */
.pp-money-total{margin:0;font-weight:900;font-size:clamp(32px,4.2vw,46px);line-height:1.05;letter-spacing:-.03em;color:${d.accent};font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.pp-money-total span{font-size:.34em;font-weight:700;color:${d.muted};white-space:nowrap}
.pp-money-line{margin:14px 0 0;color:${d.body};font-size:16px;line-height:1.55;max-width:42ch}
.pp-money-line strong{color:${d.text}}
.pp-money-bars{display:grid;gap:16px}
.pp-money-bar-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:13.5px;color:${d.muted};margin-bottom:7px}
.pp-money-bar-head b{color:${d.text};font-size:15px;font-variant-numeric:tabular-nums}
.pp-money-bar{display:block;height:12px;border-radius:6px;background:#e7ded0;overflow:hidden}
/* Where each bar's number comes from, directly under the bar - the one place
   the reader is already looking when they wonder. */
.pp-money-bar-why{display:block;margin-top:7px;font-size:12.5px;line-height:1.6;color:#717171;max-width:56ch}
.pp-theme-grid{display:grid;grid-template-columns:minmax(150px,1fr) minmax(150px,1fr) auto}
.pp-theme-row{display:grid;grid-template-columns:subgrid;grid-column:1/-1}
@media(max-width:700px){.pp-theme-grid{grid-template-columns:1fr}.pp-theme-row>span:last-child{text-align:left!important}}
/* The reasoning, in a sentence rather than as an equation. Sits on its own line
   at reading size, because it is the paragraph that decides whether the number
   above it is believed. */
/* Was capped at 68ch on a band nearly three times that wide, which is the right
   measure and the wrong shape: three short lines hugging the left edge with a
   field of empty paper beside them read as a column somebody forgot to fill.
   Same line length, bigger type, so the block fills its space and the measure
   stays inside the 65-75ch a reader can track. */
.pp-reasoning{margin:24px 0 0;padding-top:20px;border-top:1px solid #E4E1D9;font-size:17px;line-height:1.6;color:#5C5E62;max-width:72ch}
.pp-reasoning b{color:#0F1012;font-weight:800}
@media (max-width:720px){.pp-reasoning{font-size:15px}}

/* The one link on the page that has to be pressed: where the reviews can be
   checked. Sized and bordered like a control rather than set as blue text. */
.pp-proof-link{display:inline-flex;align-items:center;gap:14px;margin-top:16px;padding:13px 18px;
  border:1px solid #153AA1;border-radius:12px;background:#fff;color:#153AA1;text-decoration:none;
  transition:background .16s ease}
.pp-proof-link:hover{background:#eef1fa}
.pp-proof-link span{display:flex;flex-direction:column;gap:2px}
.pp-proof-link b{font-size:14.5px;font-weight:800}
.pp-proof-link i{font-style:normal;font-size:12px;color:#5C5E62}
@media (prefers-reduced-motion:reduce){.pp-proof-link{transition:none}}

/* The word beside each score. Carries the same three tones as the rings so the
   colour and the wording never disagree. */
.pp-verdict{font-size:10.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
  padding:3px 8px;border-radius:999px;white-space:nowrap}
.pp-verdict[data-band="good"]{color:#2f7d4f;background:rgba(47,125,79,.10);border:1px solid rgba(47,125,79,.26)}
.pp-verdict[data-band="ok"]{color:#4e7d3f;background:rgba(78,125,63,.08);border:1px solid rgba(78,125,63,.22)}
.pp-verdict[data-band="mid"]{color:#a07708;background:rgba(160,119,8,.09);border:1px solid rgba(160,119,8,.26)}
.pp-verdict[data-band="poor"]{color:#b0342c;background:rgba(176,52,44,.07);border:1px solid rgba(176,52,44,.22)}
/* The worst band is the only one that reads as an instruction rather than a
   grade, so it is filled rather than outlined: on a page of four readings the
   eye has to land on the one to fix first. */
.pp-verdict[data-band="worst"]{color:#fff;background:#b0342c;border:1px solid #b0342c}
/* Not measured is not a grade, so it is grey and carries no weight at all. */
.pp-verdict[data-band="none"]{color:#717171;background:#fff;border:1px solid #E4E1D9}
.pp-money-bar>span{display:block;height:100%;background:${d.accent};border-radius:6px}
.pp-chips{display:flex;flex-wrap:wrap;align-items:center;gap:10px 6px;margin-top:26px;padding-top:20px;border-top:${d.hairline}}
.pp-chip{display:inline-flex;align-items:baseline;gap:7px;background:${d.card};border:1px solid ${d.hairlineColor};border-radius:999px;padding:7px 14px}
.pp-chip b{font-size:15px;color:${d.text};font-variant-numeric:tabular-nums}
.pp-chip i{font-style:normal;font-size:12.5px;color:${d.muted}}
.pp-chip em{font-style:normal;margin-left:6px;color:${d.faint};font-size:13px}
/* The two leaks, named beside the total. */
.pp-split{display:inline-flex;align-items:baseline;gap:8px;border:1px solid #E4E1D9;border-radius:999px;padding:5px 13px;font-size:11.5px;color:${d.muted};background:#fff;white-space:nowrap}
.pp-split b{color:${d.text};font-size:13px;font-variant-numeric:tabular-nums}
.pp-card{background:${d.card};border:1px solid ${d.hairlineColor};border-radius:18px;box-shadow:0 1px 3px rgba(28,23,18,.05)}
/* How the audit was made: three steps with arrows between them. */
.pp-steps-flow{display:grid;gap:10px}
@media(min-width:860px){.pp-steps-flow{grid-template-columns:repeat(3,1fr)}}
.pp-flow-item{display:flex;align-items:stretch;gap:8px;min-width:0}
.pp-flow-card{flex:1;min-width:0;background:${d.card};border:1px solid ${d.hairlineColor};border-radius:16px;padding:20px 18px;position:relative}
.pp-flow-num{position:absolute;top:14px;right:16px;font-size:10px;font-weight:800;letter-spacing:.14em;color:#c9c2b2}
.pp-flow-label{margin:10px 0 0;font-size:15.5px;font-weight:800;color:${d.text};line-height:1.3}
.pp-flow-source{margin:5px 0 0;font-size:12.5px;color:${d.faint}}
.pp-flow-arrow{display:none;align-self:center;flex-shrink:0}
@media(min-width:860px){.pp-flow-arrow{display:block}}
.pp-flow-note{margin:18px 0 0;font-size:13px;color:${d.faint};max-width:70ch}

/* What you leave the call with: six short labels, two columns, no paragraphs. */
.pp-gives{display:grid;gap:18px 34px}
@media(min-width:820px){.pp-gives{grid-template-columns:1fr 1fr}}
.pp-give{display:flex;gap:13px;align-items:flex-start;min-width:0}
.pp-give-title{margin:0;font-size:15.5px;font-weight:700;line-height:1.35}
.pp-give-note{margin:3px 0 0;font-size:12.5px;opacity:.66}
.pp-band-ink .pp-give{color:${d.onInk}}
/* The founders, small, at the foot of the ask. */
.pp-founders{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;margin-top:30px;padding-top:22px;border-top:1px solid rgba(243,239,230,.16)}
.pp-founder{display:inline-flex;align-items:center;gap:10px}
.pp-founder img{width:44px;height:44px;border-radius:999px;object-fit:cover;display:block}
.pp-founder b{display:block;font-size:13.5px;font-weight:700}
.pp-founder i{display:block;font-style:normal;font-size:12px;opacity:.6}
.pp-founder-note{font-size:13px;opacity:.7}
/* The path: five numbered stops on one line. A list of promises reads as
   marketing; a line with stops reads as a process, and a process is what the
   reader is actually deciding to enter. Stacks to a vertical rail on phones,
   where a five-column line would be five columns of two words. */
.pp-path{list-style:none;margin:0;padding:0;display:grid;gap:22px;counter-reset:step}
.pp-path li{position:relative;padding-left:44px}
.pp-path-dot{position:absolute;left:0;top:0;width:28px;height:28px;border-radius:999px;background:${d.accent};color:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}
.pp-path li::before{content:"";position:absolute;left:13.5px;top:28px;bottom:-22px;width:1.5px;background:${d.hairlineColor}}
.pp-path li:last-child::before{display:none}
.pp-path-title{display:block;font-size:15.5px;font-weight:800}
.pp-path-note{display:block;margin-top:4px;font-size:13px;opacity:.7;line-height:1.5}
@media(min-width:900px){
  .pp-path{grid-template-columns:repeat(5,1fr);gap:0 18px}
  .pp-path li{padding:44px 0 0;text-align:center}
  .pp-path-dot{left:50%;transform:translateX(-50%)}
  .pp-path li::before{left:50%;right:auto;top:13.5px;bottom:auto;width:100%;height:1.5px}
  .pp-path-note{max-width:24ch;margin-left:auto;margin-right:auto}
}
.pp-band-ink .pp-path li::before{background:rgba(243,239,230,.2)}
/* The calendar, inside the dark band: white sheet, rounded, nothing around it. */
.pp-book{margin-top:26px;border-radius:16px;overflow:hidden;background:#1c1712;border:1px solid rgba(255,255,255,.1)}
.pp-glow{border:1.5px solid #8fa3d6;box-shadow:0 4px 20px rgba(16,24,40,.08)}
.pp-gradient{color:#153AA1}
.pp-pill{display:inline-flex;align-items:baseline;gap:8px;padding:9px 18px;border-radius:999px;background:#fff;border:1px solid #E4E1D9;box-shadow:0 1px 3px rgba(16,24,40,.06);font-size:14px}
.pp-hairline{border-top:${d.hairline}}
.pp-findings-grid{display:grid;gap:44px}
/* A grid item defaults to min-width:auto, so it refuses to shrink below its
   own min-content. Measured 31.08.2026 at 390px: the competitor table and the
   SERP exhibit both sat at 402px inside a 390px phone and pushed the WHOLE
   document 36px sideways. Letting the items shrink keeps the overflow inside
   the two boxes that are genuinely wide, where it already scrolls. */
.pp-findings-grid > *{min-width:0}
.pp-findings-right{overflow-x:auto}
@media(min-width:1020px){.pp-findings-grid{grid-template-columns:minmax(0,1fr) 400px;align-items:start}.pp-findings-right{position:sticky;top:32px}}
/* Meilensteine: Wochenraster am Desktop, schlichte Liste auf dem Telefon.
   Bei sechs Wochen auf 390 Pixel blieben je Meilenstein gut dreissig Pixel,
   also drei Textbloecke uebereinander. */
@media(max-width:700px){
  .pp-milestones{display:block!important}
  .pp-milestones .pp-ms-gap{display:none}
  .pp-milestones .pp-ms{margin-bottom:18px}
  .pp-milestones .pp-ms:last-child{margin-bottom:0}
}
.pp-table-label-mobile{display:none}
@media(max-width:700px){.pp-table-label-desktop{display:none}.pp-table-label-mobile{display:inline}}
.pp-2col{display:grid;gap:0 40px}
@media(min-width:760px){.pp-2col{grid-template-columns:1fr 1fr}}
.pp-4col{display:grid;gap:12px;grid-template-columns:repeat(2,1fr)}
@media(min-width:860px){.pp-4col{grid-template-columns:repeat(4,1fr)}}
/* The chain: five drawn links in a row on desktop with arrows between them,
   two columns on phones where the arrows would only add noise. */
.pp-chain-head{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:16px;margin:0 0 18px}
.pp-chain-title{margin:0;font-size:clamp(22px,3vw,30px);font-weight:800;letter-spacing:-.02em;line-height:1.15;color:${d.text}}
.pp-chain-score{display:flex;flex-direction:column;align-items:flex-start}
.pp-chain-score span{font-size:clamp(38px,5vw,50px);font-weight:900;line-height:1;letter-spacing:-.03em;color:${d.accent};font-variant-numeric:tabular-nums}
.pp-chain-score em{font-style:normal;font-size:.42em;font-weight:700;color:${d.faint}}
.pp-chain-score small{margin-top:6px;font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;color:${d.faint}}
@media(min-width:940px){.pp-chain-score{align-items:flex-end}}

.pp-chain{display:grid;gap:0;grid-template-columns:repeat(2,1fr)}
.pp-chain-item{display:flex;align-items:stretch;gap:6px;min-width:0;border-top:1px solid #EDEAE2}
.pp-chain-item:nth-child(-n+2){border-top:0}
.pp-chain-item:nth-child(even){border-left:1px solid #EDEAE2}
/* The links are columns inside one card, not five cards. Six white boxes in
   one section made the page read as a dashboard; one card with hairlines
   between the columns reads as one instrument. */
.pp-chain-card{flex:1;min-width:0;position:relative;padding:18px 14px 16px;display:flex;flex-direction:column;align-items:center;text-align:center}
.pp-chain-num{position:absolute;top:10px;right:12px;font-size:10px;font-weight:800;letter-spacing:.14em;color:#c9c7bd}
.pp-chain-art{display:block;margin-bottom:8px}
.pp-chain-name{margin:0;font-size:15px;font-weight:800;color:${d.text};line-height:1.2}
.pp-chain-does{margin:3px 0 0;font-size:12px;color:${d.muted};line-height:1.35}
.pp-chain-pill{display:inline-flex;align-items:center;border:1px solid;border-radius:999px;padding:3px 9px;margin-top:10px;font-size:10.5px;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap}
.pp-chain-bar{display:block;width:100%;height:4px;border-radius:2px;background:#e7e4dc;overflow:hidden;margin-top:9px}
.pp-chain-bar>span{display:block;height:100%;border-radius:2px}
.pp-chain-read{margin:8px 0 0;font-size:11.5px;color:${d.muted};line-height:1.4}
.pp-chain-outside{margin:6px 0 0;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#a8a79f}
.pp-chain-arrow{display:none;align-self:center;flex-shrink:0}
.pp-chain-foot{margin-top:18px;padding-top:16px;border-top:${d.hairline};text-align:center}
.pp-chain-verdict{margin:0;font-size:16px;font-weight:800;color:${d.text}}
.pp-chain-note{margin:8px auto 0;max-width:78ch;font-size:12.5px;color:${d.muted};line-height:1.6}
.pp-br{display:none}
@media(min-width:940px){
  .pp-chain{grid-template-columns:repeat(5,1fr);gap:0}
  .pp-chain-item,.pp-chain-item:nth-child(even){border-top:0;border-left:0}
  .pp-chain-arrow{display:block}
  .pp-br{display:inline}
}
/* The four pillars, inside the scorecard card: ring beside its reason, in two
   columns. Four separate cards for four numbers was three cards too many. */
.pp-pillars{display:grid;gap:18px 32px}
@media(min-width:760px){.pp-pillars{grid-template-columns:1fr 1fr}}
.pp-pillar{display:flex;align-items:flex-start;gap:14px;min-width:0}
/* The four headline tiles: what it is worth, when it pays back, what it costs,
   how long. Two columns on a phone, four on a desk. */
.pp-tiles{display:grid;gap:10px;grid-template-columns:repeat(2,1fr)}
@media(min-width:900px){.pp-tiles{grid-template-columns:repeat(4,1fr)}}
.pp-tile{background:#fff;border:1px solid ${d.hairlineColor};border-radius:16px;padding:18px 18px 16px;display:flex;flex-direction:column;gap:6px;box-shadow:0 1px 3px rgba(16,24,40,.05)}
.pp-tile-label{font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;color:${d.faint};font-weight:700}
.pp-tile-value{font-size:clamp(22px,2.6vw,30px);font-weight:900;letter-spacing:-.025em;line-height:1.05;color:${d.accent};font-variant-numeric:tabular-nums}
.pp-tile-note{font-size:11.5px;color:${d.muted};line-height:1.45}
/* The five action cards: one wide lead card, then four. The first is the one
   they should do first, and size says that faster than a label. */
.pp-actions{display:grid;gap:12px;grid-template-columns:repeat(2,1fr)}
@media(min-width:1000px){
  .pp-actions{grid-template-columns:repeat(6,1fr)}
  .pp-action{grid-column:span 3}
  .pp-action:nth-child(n+3){grid-column:span 2}
}
.pp-action{position:relative;padding:22px 20px 20px;overflow:hidden;background:${d.card};border:1px solid ${d.hairlineColor};border-radius:16px}
.pp-action-body{min-width:0}
.pp-action-num{position:absolute;top:14px;right:16px;font-size:11px;font-weight:800;letter-spacing:.16em;color:#c9c7bd}
.pp-action-art{display:block}
.pp-3col{display:grid;gap:16px}
@media(min-width:900px){.pp-3col{grid-template-columns:repeat(3,1fr);align-items:stretch}}
.pp-proof-grid{display:grid;gap:16px}
@media(min-width:860px){.pp-proof-grid{grid-template-columns:1fr 1fr}}
/* The five steps after a yes, and the terms. Numbers in circles, one line each. */
.pp-steps{list-style:none;margin:0;padding:0;display:grid;gap:10px}
@media(min-width:900px){.pp-steps{grid-template-columns:repeat(5,1fr)}}
.pp-steps li{display:flex;gap:12px;background:#fff;border:1px solid ${d.hairlineColor};border-radius:16px;padding:16px 16px 14px;box-shadow:0 1px 3px rgba(16,24,40,.05)}
@media(min-width:900px){.pp-steps li{flex-direction:column;gap:10px}}
.pp-step-num{flex:none;width:26px;height:26px;border-radius:999px;background:${d.accent};color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:800}
.pp-steps strong{display:block;font-size:14px;color:${d.text}}
.pp-steps span span{display:block;margin-top:4px;font-size:12.5px;color:${d.muted};line-height:1.5}
.pp-terms{margin:0;padding:0;list-style:none;display:grid;gap:8px;max-width:80ch}
.pp-terms li{position:relative;padding-left:20px;font-size:14.5px;color:${d.body};line-height:1.6}
.pp-terms li::before{content:"";position:absolute;left:2px;top:9px;width:6px;height:6px;border-radius:999px;background:${d.accent}}
/* Evidence one click away. The first version was a line of blue text with a
   small chevron, and a link that opens something in place has to look like a
   button or nobody presses it. So: a real control, full width, with the mark in
   a circle and a label that says what happens. */
/* The conversion sum, read left to right like arithmetic. Terms wrap as units
   so an operator never ends a line orphaned from its number. */
.pp-sum{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 0}
.pp-sum-term{display:inline-flex;align-items:baseline;gap:6px}
.pp-sum-term b{font-size:15px;font-weight:800;color:#0F1012;font-variant-numeric:tabular-nums}
.pp-sum-term i{font-style:normal;font-size:12.5px;color:#717171}
.pp-sum-term em{font-style:normal;color:#c9c7bd;font-size:13px;margin:0 12px}
.pp-sum-total{display:flex;align-items:baseline;gap:10px;margin:16px 0 0;font-size:15px;color:#5C5E62}
.pp-sum-total span{color:#c9c7bd;font-size:15px}
.pp-sum-total b{font-size:20px;font-weight:900;color:#153AA1;font-variant-numeric:tabular-nums;letter-spacing:-0.01em}
.pp-sum-note{margin:8px 0 0;font-size:12.5px;line-height:1.65;color:#717171;max-width:70ch}

/* What is already in place. A wrapping list of chips, not a paragraph of
   inline spans that leaves an orphan on the second line. */
.pp-haves{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:0;padding:0}
.pp-haves li{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:999px;
  border:1px solid #E4E1D9;background:#fff;font-size:13px;color:#5C5E62}
.pp-haves li svg{color:#2f7d4f;flex-shrink:0}

.pp-more{margin-top:6px}
.pp-more>summary{display:flex;align-items:center;gap:12px;padding:14px 18px;border:1px solid ${d.hairlineColor};
  border-radius:14px;background:${d.card};font-size:14.5px;font-weight:700;color:${d.text};transition:border-color .15s}
.pp-more>summary:hover{border-color:${d.accent}}
.pp-more>summary b{font-weight:800;color:${d.accent}}
.pp-more>summary i{font-style:normal;font-weight:400;color:${d.muted};font-size:13px}
.pp-more-mark{margin-left:auto;flex:none;width:26px;height:26px;border-radius:999px;background:${d.page};
  border:1px solid ${d.hairlineColor};display:inline-flex;align-items:center;justify-content:center;color:${d.accent}}
.pp-more-mark::before{content:"";width:7px;height:7px;border-right:1.8px solid currentColor;border-bottom:1.8px solid currentColor;
  transform:rotate(45deg) translate(-2px,-2px);transition:transform .2s}
.pp-more[open] .pp-more-mark::before{transform:rotate(-135deg) translate(-2px,-2px)}
.pp-more[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0;border-bottom-color:transparent}
.pp-more[open]>div,.pp-more[open]>summary+div{border:1px solid ${d.hairlineColor};border-top:0;border-radius:0 0 14px 14px}
.pp-more-body{border:1px solid ${d.hairlineColor};border-top:0;border-radius:0 0 14px 14px;padding:4px 18px 8px;background:${d.card}}
.pp details summary{list-style:none;cursor:pointer}
.pp details summary::-webkit-details-marker{display:none}
`}</style>
  );
}

/** Score band colors, tuned for the dark ground. */
export function scoreColor(score: number | null): { fg: string } {
  if (score === null) return { fg: d.faint };
  if (score < 40) return { fg: "#b0342c" };
  if (score < 70) return { fg: "#a07708" };
  return { fg: "#2f7d4f" };
}

/** A filled ring meter against 100, coloured by band. */
export function ScoreRing({ score, size, label, strokeWidth = 9 }: { score: number | null; size: number; label?: string; strokeWidth?: number }) {
  const c = scoreColor(score);
  const r = (size - strokeWidth - 3) / 2;
  const circ = 2 * Math.PI * r;
  const filled = score === null ? 0 : (score / 100) * circ;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} role="img" aria-label={label ? `${label}: ${score ?? "not scored"} of 100` : undefined}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E4E1D9" strokeWidth={strokeWidth} />
        {score !== null ? (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={c.fg}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ - filled}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        ) : null}
      </svg>
      <span
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 900,
          fontSize: Math.round(size * 0.3),
          color: c.fg,
        }}
      >
        {score === null ? "–" : score}
      </span>
    </div>
  );
}

interface SectionProps {
  number?: string;
  kicker: string;
  title: string;
  lead: string;
  icon?: ReactNode;
  children: ReactNode;
  panel?: boolean;
  /** Which band this section sits on. "plain" is the warm paper, "warm" the
   * deeper beige, "ink" the dark band - one of those near the close, never two
   * in a row. `panel` is the older boolean and still means "warm". */
  tone?: "plain" | "warm" | "ink";
  bare?: boolean;
}

export function Section({ number, kicker, title, lead, icon, children, panel, tone }: SectionProps) {
  const band = tone ?? (panel ? "warm" : "plain");
  return (
    <section className={`pp-section pp-band-${band}`} data-story-beat={kicker}>
      {/* data-rise: the heading block arrives as the reader reaches it, the
          body follows a beat later. Two groups, not one per element - a section
          that assembles itself piece by piece reads as a loading screen. */}
      <div className="pp-inner">
        <div data-rise>
          <p className="pp-kicker">
            {icon ? <span aria-hidden style={{ display: "inline-flex" }}>{icon}</span> : null}
            {number ? `${number} · ` : ""}{kicker}
          </p>
          <h2 className="pp-h2">{title}</h2>
          <p className="pp-lead">{lead}</p>
        </div>
        {/* No card per section. The colour division is the band itself:
            sections alternate white and warm beige full-bleed, and inside a
            section the parts are separated by hairlines and space. Cards are
            reserved for things that genuinely are objects - a price option, a
            screenshot of Google. */}
        <div data-rise>{children}</div>
      </div>
    </section>
  );
}

/** Design-kit alert, dark-tuned: tinted ground, coloured edge, icon. */
export function Alert({ tone, children }: { tone: "info" | "caution" | "critical"; children: ReactNode }) {
  const fg = tone === "info" ? "#0b62c9" : tone === "caution" ? "#a07708" : "#b0342c";
  const bg = tone === "info" ? "#e8f2ff" : tone === "caution" ? "#fdf3e6" : "#fdedec";
  return (
    // Was a 3px coloured stripe down the left edge with the radius squared off
    // on that side. The tone is carried by the tint and the icon, both of which
    // already say it, so the stripe was decoration doing a second job badly.
    <div style={{ background: bg, border: `1px solid ${fg}33`, borderRadius: 12, padding: "12px 16px", display: "flex", gap: 10, alignItems: "flex-start", color: d.body, fontSize: 14 }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={fg} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ flexShrink: 0, marginTop: 2 }}>
        {tone === "info" ? (
          <>
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </>
        ) : (
          <>
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
            <path d="M12 9v4M12 17h.01" />
          </>
        )}
      </svg>
      <span>{children}</span>
    </div>
  );
}

/** Wide content scrolls inside this instead of the page. */
export function Scroller({ children }: { children: ReactNode }) {
  return <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>{children}</div>;
}

export type { CSSProperties };
