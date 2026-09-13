/* Wo lokale Betriebe Geld verlieren: die allgemeine Lage, bevor es persönlich wird.
 *
 * WARUM DIESE SEKTION (Luka, 06.09.2026): der Bericht sprang bisher vom Hero direkt in die
 * Befunde dieses einen Betriebs. Damit las sich die Mängelliste wie ein Vorwurf an ihn.
 * Steht davor, dass die halbe Branche dieselben drei Löcher hat, liest sich derselbe Befund
 * als Chance statt als Kritik — und die eigene Messung darunter bekommt einen Maßstab.
 *
 * JEDE ZAHL HAT EINE STUDIE, UND DIE STUDIE STEHT DANEBEN. Zwei der vier Zahlen, die Luka
 * genannt hatte, sind bei der Prüfung durchgefallen und stehen deshalb nicht hier:
 *
 *   „78 % kaufen beim ersten, der antwortet" — führt zu einer nie veröffentlichten Umfrage
 *   ohne Methodik; die oft genannte HBR-Quelle sagt das an keiner Stelle.
 *
 *   „Die ersten drei auf der Karte bekommen 60 bis 75 % der Klicks" — keine Originalstudie
 *   auffindbar, die belastbaren Messungen liegen bei rund der Hälfte davon.
 *
 * Die Quelle sichtbar danebenzuschreiben ist selbst ein Verkaufsargument: kein Wettbewerber
 * tut das, und wer eine Zahl belegt, wird auch beim Rest geglaubt. Die Zahlen und ihre
 * Herkunft stehen in `context/business.md`, damit sie nur an einer Stelle gepflegt werden.
 */

import type { ReactNode } from "react";
import { KAPITEL, SektionsKopf } from "./lead-magnet-kopf";
import { Malkasten } from "./lead-magnet-solution";

type Locale = "en" | "de";
type Text = { en: string; de: string };

/** Ein Satz, der mit seiner Zahl anfaengt (Luka, 06.09.2026). `zahl` steht gross oben
 *  neben der Zeichnung, `nach` laeuft als normaler Satz darunter weiter — zusammengelesen
 *  ergeben beide einen Satz, getrennt gesetzt, weil nur so die Zahl den Blick faengt. */
type Loch = {
  zahl: Text;
  nach: Text;
  quelle: Text;
  bild: ReactNode;
};

/* Drei Szenen in derselben Machart wie unten im Loesungsteil (Luka, 06.09.2026: „wie auch
 * unten"): Verlauf statt Volltonflaeche, weicher Schatten, helle Kante. Jede zeigt genau
 * das Loch, das die Zahl daneben misst. `aria-hidden`, weil der Text alles sagt. */

/** Die Anfrage liegt ungelesen da, waehrend die Uhr fast einmal herum ist. Der rote Punkt
 *  ist die ungelesene Nachricht, der rote Bogen die verstrichene Zeit. */
function BildWartet() {
  const g = "l1";
  return (
    <svg viewBox="0 0 220 132" fill="none" aria-hidden className="h-auto w-full max-w-[214px]">
      <Malkasten id={g} />
      <ellipse cx="110" cy="126" rx="84" ry="5" fill="#2a2419" opacity=".05" />
      <g filter={`url(#${g}-hauch)`}>
        <path d="M16 26h84a10 10 0 0110 10v24a10 10 0 01-10 10H38l-13 12V70h-9a10 10 0 01-10-10V36a10 10 0 0110-10z" fill={`url(#${g}-still)`} />
      </g>
      <path d="M30 42h56M30 53h34" stroke="#b5b0a6" strokeWidth="4" strokeLinecap="round" />
      <circle className="pocht" style={{ transformOrigin: "103px 30px" }} cx="103" cy="30" r="9" fill="#b0342c" />
      <circle cx="103" cy="30" r="9" stroke="#f7f5f0" strokeWidth="2.5" />
      <g filter={`url(#${g}-schatten)`}>
        <circle cx="164" cy="66" r="42" fill={`url(#${g}-blatt)`} />
      </g>
      <circle cx="164" cy="66" r="42" stroke="#ded9d0" strokeWidth="1.5" />
      <circle cx="164" cy="66" r="33" fill="#eef1fb" stroke="#dbe1f6" strokeWidth="1.5" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <path key={i} d={`M164 ${i % 2 ? 38 : 36}v${i % 2 ? 3.5 : 5.5}`} stroke="#c2c9e4" strokeWidth={i % 2 ? 2.2 : 3} strokeLinecap="round" transform={`rotate(${i * 45} 164 66)`} />
      ))}
      <path className="fuellt" d="M164 25a41 41 0 11-30 13" stroke="#b0342c" strokeWidth="5.5" strokeLinecap="round" />
      <path className="tickt" d="M164 44v22l14 9" stroke="#233f9a" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="164" cy="66" r="4.2" fill="#233f9a" />
      <circle cx="164" cy="66" r="1.7" fill="#fff" />
    </svg>
  );
}

/** Eine Website, die breiter ist als das Telefon: was nicht mehr aufs Display passt,
 *  liegt blass dahinter, und der Anruf-Knopf liegt mit draussen. */
function BildHandy() {
  const g = "l2";
  return (
    <svg viewBox="0 0 220 132" fill="none" aria-hidden className="h-auto w-full max-w-[214px]">
      <Malkasten id={g} />
      <ellipse cx="110" cy="126" rx="84" ry="5" fill="#2a2419" opacity=".05" />

      {/* Was rechts aus dem Bildschirm laeuft */}
      <g className="rutscht" opacity=".4">
        <rect x="141" y="34" width="72" height="14" rx="4" fill="#dfe4f6" />
        <rect x="141" y="56" width="64" height="9" rx="3" fill="#e2ded5" />
        <rect x="141" y="71" width="70" height="9" rx="3" fill="#e2ded5" />
        <rect x="141" y="90" width="50" height="20" rx="7" fill="#dfe4f6" />
      </g>

      <g filter={`url(#${g}-schatten)`}>
        <rect x="52" y="6" width="88" height="120" rx="16" fill={`url(#${g}-blatt)`} />
      </g>
      <rect x="52.75" y="6.75" width="86.5" height="118.5" rx="15.25" stroke="#ded9d0" strokeWidth="1.5" />
      <rect x="59" y="14" width="74" height="104" rx="10" fill="#fff" />
      <rect x="85" y="18" width="22" height="3.5" rx="1.75" fill="#e6e2d9" />
      <rect x="66" y="34" width="78" height="14" rx="4" fill="#233f9a" opacity=".8" />
      <rect x="66" y="56" width="70" height="9" rx="3" fill="#d7d2c9" />
      <rect x="66" y="71" width="76" height="9" rx="3" fill="#d7d2c9" />
      <rect x="66" y="90" width="56" height="20" rx="7" fill="#233f9a" opacity=".2" />

      {/* Die Kante, an der es abreisst */}
      <path className="laeuft" d="M139 12v108" stroke="#b0342c" strokeWidth="2.4" strokeLinecap="round" />
      <g filter={`url(#${g}-hauch)`}>
        <circle cx="139" cy="108" r="14" fill="#b0342c" />
      </g>
      <path d="M133.5 102.5l11 11M144.5 102.5l-11 11" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}

/** Die ersten drei sind gefuellt und tragen ihre Sterne, darunter verblasst alles. Der
 *  gestrichelte Weg nach oben zeigt, wohin es gehen muesste. */
function BildErsteDrei() {
  const g = "l3";
  return (
    <svg viewBox="0 0 220 132" fill="none" aria-hidden className="h-auto w-full max-w-[214px]">
      <Malkasten id={g} />
      <ellipse cx="110" cy="126" rx="84" ry="5" fill="#2a2419" opacity=".05" />
      <g filter={`url(#${g}-schatten)`}>
        <rect x="14" y="6" width="134" height="116" rx="15" fill={`url(#${g}-blatt)`} />
      </g>
      <rect x="14.75" y="6.75" width="132.5" height="114.5" rx="14.25" stroke="#ded9d0" strokeWidth="1.5" />

      {/* Die ersten drei, mit Bewertung */}
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(0 ${i * 24})`}>
          <rect x="24" y="16" width="114" height="20" rx="7" fill="#eef1fb" />
          <rect x="30" y="21" width="10" height="10" rx="3" fill={`url(#${g}-navy)`} />
          <path d="M48 26h58" stroke="#233f9a" strokeWidth="3.2" strokeLinecap="round" opacity=".72" />
          <path d="M116 22.5l1.4 2.9 3.2.5-2.3 2.2.6 3.2-2.9-1.5-2.9 1.5.6-3.2-2.3-2.2 3.2-.5z" fill="#c4632a" />
        </g>
      ))}

      {/* Alles darunter */}
      <path d="M24 94h114" stroke="#e8e4dc" strokeWidth="1.5" />
      <g opacity=".34">
        <path d="M30 104h96M30 113h68" stroke="#cbc6bc" strokeWidth="3.2" strokeLinecap="round" />
      </g>

      {/* Der Weg nach oben, von einem blassen Eintrag ganz unten */}
      <path className="laeuft" d="M180 100V44" stroke="#233f9a" strokeWidth="2.8" strokeLinecap="round" opacity=".8" />
      <path d="M180 28l9 15h-18z" fill="#233f9a" />
      <rect x="155.25" y="105.25" width="49.5" height="17.5" rx="6.75" fill="#fdf1f0" stroke="#b0342c" strokeWidth="1.5" />
      <circle className="pocht" style={{ transformOrigin: "165px 114px" }} cx="165" cy="114" r="4.5" fill="#b0342c" />
      <path d="M175 114h22" stroke="#d8a5a1" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

const LOECHER: Loch[] = [
  {
    zahl: { en: "42 hours", de: "42 Stunden" },
    nach: { en: "is the average wait before an online enquiry gets an answer.", de: "dauert es im Schnitt, bis eine Online-Anfrage beantwortet wird." },
    quelle: {
      en: "Harvard Business Review, 2011. 2,241 companies audited.",
      de: "Harvard Business Review, 2011. 2.241 geprüfte Unternehmen.",
    },
    bild: <BildWartet />,
  },
  {
    zahl: { en: "31%", de: "31 %" },
    nach: { en: "of local business sites do not fit a phone screen.", de: "der Betriebswebsites passen nicht auf einen Handy-Bildschirm." },
    quelle: {
      en: "Pocket CEO, 11,321 businesses checked, September 2026.",
      de: "Pocket CEO, 11.321 geprüfte Betriebe, September 2026.",
    },
    bild: <BildHandy />,
  },
  {
    /* „Half" statt „~48 %" (Luka, 06.09.2026). Die Tilde vor einer Prozentzahl sieht aus
       wie ein Taschenspielertrick; „rund die Haelfte" ist dieselbe Aussage und ehrlicher,
       weil die gemessenen 47,9 % ohnehin eine Momentaufnahme sind. */
    zahl: { en: "Half", de: "Die Hälfte" },
    nach: { en: "of every local click goes to the top three on the map.", de: "aller lokalen Klicks geht an die ersten drei auf der Karte." },
    quelle: {
      en: "First Page Sage, click-through by position, 2026.",
      de: "First Page Sage, Klickrate nach Position, 2026.",
    },
    bild: <BildErsteDrei />,
  },
];

export function LossesSection({ locale }: { locale: Locale }) {
  const de = locale === "de";
  return (
    <section aria-label={de ? "Wo lokale Betriebe Geld verlieren" : "Where local businesses lose money"} className="lm-losses border-b border-black/10 bg-[#f4f1ea] px-5 py-11 sm:px-8 sm:py-14">
      <div className="mx-auto max-w-[1160px]">
        <SektionsKopf kapitel={KAPITEL.branche} locale={locale} />

        <div className="mt-8 grid gap-3.5 lg:grid-cols-3">
          {LOECHER.map((l) => (
            <article key={l.zahl.en} className="flex flex-col rounded-[18px] border border-hairline bg-white p-6 shadow-[0_1px_2px_rgba(28,23,18,.03),0_10px_30px_rgba(28,23,18,.045)] sm:p-7">
              {/* Zeichnung und Zahl auf einer Hoehe: die Zahl ist der Satzanfang und faengt
                  den Blick, bevor der Rest des Satzes darunter weiterlaeuft. */}
              <div className="flex items-center gap-3">
                <div className="w-[58%] shrink-0">{l.bild}</div>
                <p className="tnum m-0 flex-1 text-[clamp(30px,3vw,40px)] font-black leading-[.95] tracking-[-.05em] text-slate-900">{l.zahl[locale]}</p>
              </div>
              <p className="m-0 mt-3.5 flex-1 text-[17px] leading-[1.4] text-graphite sm:text-[18px]">{l.nach[locale]}</p>
              <p className="m-0 mt-5 border-t border-hairline pt-3 text-[10.5px] leading-[1.4] text-pewter">{l.quelle[locale]}</p>
            </article>
          ))}
        </div>

      </div>
    </section>
  );
}
