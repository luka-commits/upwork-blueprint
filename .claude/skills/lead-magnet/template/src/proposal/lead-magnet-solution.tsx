/* Der Lösungsabschnitt des Kaltreports: drei Schritte statt eines Wochenplans.
 *
 * WARUM KEIN BALKENPLAN MEHR (Luka, 06.09.2026): der Gantt mit Paketreitern beantwortete
 * eine Frage, die der Empfänger noch nicht hat. Er hat gerade gelesen, dass er auf 24 von
 * 25 Punkten hinter jemand anderem liegt — und bekam als Antwort einen Projektplan mit
 * Wochenrastern und drei Paketen zur Auswahl. Der volle Fahrplan gehört ins Gespräch, wo
 * jemand danebensitzt und ihn erklärt; hier muss stehen, was wir für ihn tun und was ihm
 * das bringt.
 *
 * Die Reihenfolge trägt selbst ein Argument: erst hört das Geld auf wegzulaufen (das wirkt
 * in Tagen), dann kommt neues dazu (das braucht Wochen). Wer umgekehrt anfängt, kauft
 * Sichtbarkeit für Anfragen, die er danach wieder liegen lässt.
 *
 * Jede Zeile ist das, was der Betrieb bekommt — nie, was wir tun. "Interne Verlinkung" ist
 * unsere Sprache; "Ihre Seiten verweisen aufeinander, damit Google die wichtigste erkennt"
 * ist seine.
 */

import type { ReactNode } from "react";
import { KAPITEL, SektionsKopf } from "./lead-magnet-kopf";
import { ChevronDown } from "./service-icons";

type Locale = "en" | "de";

/* ---------------------------------------------------------------- Bilder ---
 * Drei gezeichnete Szenen, keine Symbolchen. Jede zeigt genau den Vorgang, den ihr
 * Abschnitt beschreibt, und benutzt dieselben Farben wie der Rest des Berichts. Sie
 * tragen `aria-hidden`: was sie sagen, steht daneben im Text.
 *
 * Die Tiefe kommt aus drei Sachen, nicht aus Umrandungen: ein weicher Schatten unter
 * jeder Fläche, ein feiner Verlauf von oben nach unten statt einer Volltonfarbe, und
 * eine helle Kante an der Oberseite. Das ist der Unterschied zwischen einer Zeichnung
 * und einem Gegenstand.
 */

/** Schatten, Verläufe und Kanten, einmal je Bild angelegt. `id` hält sie auseinander,
 *  weil drei SVGs auf derselben Seite stehen und gleiche Namen sich überschreiben. */
export function Malkasten({ id }: { id: string }) {
  return (
    <defs>
      <linearGradient id={`${id}-blatt`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#ffffff" />
        <stop offset="1" stopColor="#f6f4ef" />
      </linearGradient>
      <linearGradient id={`${id}-navy`} x1="0" y1="0" x2="0.4" y2="1">
        <stop offset="0" stopColor="#2f4cb0" />
        <stop offset="1" stopColor="#1c3382" />
      </linearGradient>
      <linearGradient id={`${id}-gruen`} x1="0" y1="0" x2="0.35" y2="1">
        <stop offset="0" stopColor="#3b8a5c" />
        <stop offset="1" stopColor="#256040" />
      </linearGradient>
      <linearGradient id={`${id}-tief`} x1="0" y1="0" x2="0.4" y2="1">
        <stop offset="0" stopColor="#22366f" />
        <stop offset="1" stopColor="#111e4a" />
      </linearGradient>
      <linearGradient id={`${id}-still`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#f1eee7" />
        <stop offset="1" stopColor="#e8e4dc" />
      </linearGradient>
      <filter id={`${id}-schatten`} x="-30%" y="-20%" width="160%" height="170%">
        <feDropShadow dx="0" dy="5" stdDeviation="7" floodColor="#2a2419" floodOpacity=".13" />
      </filter>
      <filter id={`${id}-hauch`} x="-40%" y="-30%" width="180%" height="190%">
        <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#2a2419" floodOpacity=".16" />
      </filter>
    </defs>
  );
}

/** Eine Anfrage kommt rein, die Uhr läuft, die Antwort geht in fünf Minuten zurück.
 *  Das Handy zeigt beide Nachrichten, der Ring um die Uhr ist die verstrichene Zeit. */
function BildAntwort() {
  const g = "a";
  return (
    <svg viewBox="0 0 300 180" fill="none" aria-hidden className="h-auto w-full max-w-[290px]">
      <Malkasten id={g} />
      <ellipse cx="150" cy="170" rx="120" ry="7" fill="#2a2419" opacity=".05" />

      {/* Das Telefon */}
      <g filter={`url(#${g}-schatten)`}>
        <rect x="18" y="14" width="118" height="152" rx="19" fill={`url(#${g}-blatt)`} />
      </g>
      <rect x="18.75" y="14.75" width="116.5" height="150.5" rx="18.25" stroke="#ded9d0" strokeWidth="1.5" />
      <rect x="26" y="22" width="102" height="136" rx="13" fill="#fff" />
      <rect x="62" y="27" width="30" height="4.5" rx="2.25" fill="#e6e2d9" />

      {/* Anfrage rein */}
      <g filter={`url(#${g}-hauch)`}>
        <path d="M34 44h68a8 8 0 018 8v18a8 8 0 01-8 8H46l-10 9v-9h-2a8 8 0 01-8-8V52a8 8 0 018-8z" fill={`url(#${g}-still)`} />
      </g>
      <path d="M42 56h50M42 66h32" stroke="#b5b0a6" strokeWidth="3.4" strokeLinecap="round" />

      {/* Antwort raus */}
      <g filter={`url(#${g}-hauch)`}>
        <path d="M120 96H52a8 8 0 00-8 8v22a8 8 0 008 8h56l10 9v-9h2a8 8 0 008-8v-22a8 8 0 00-8-8z" fill={`url(#${g}-gruen)`} />
      </g>
      <path d="M58 108h52M58 118h52M58 128h30" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" opacity=".92" />

      {/* Die Uhr: der orange Bogen ist die verstrichene Zeit */}
      <g filter={`url(#${g}-schatten)`}>
        <circle cx="224" cy="92" r="48" fill={`url(#${g}-blatt)`} />
      </g>
      <circle cx="224" cy="92" r="48" stroke="#ded9d0" strokeWidth="1.5" />
      <circle cx="224" cy="92" r="37" fill="#eef1fb" />
      <circle cx="224" cy="92" r="37" stroke="#dbe1f6" strokeWidth="1.5" />
      {[0, 1, 2, 3].map((i) => (
        <path key={i} d="M224 60v6" stroke="#c2c9e4" strokeWidth="3" strokeLinecap="round" transform={`rotate(${i * 90} 224 92)`} />
      ))}
      <path d="M224 47a45 45 0 0134 15.6" stroke="#c4632a" strokeWidth="5.5" strokeLinecap="round" />
      <path className="tickt" d="M224 70v22l14.5 9" stroke="#233f9a" strokeWidth="4.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="224" cy="92" r="4.6" fill="#233f9a" />
      <circle cx="224" cy="92" r="1.8" fill="#fff" />

      {/* Der Weg: rein, Uhr, raus */}
      <path className="zieht" d="M140 62c26-8 38 6 40 20" stroke="#233f9a" strokeWidth="2.6" strokeLinecap="round" opacity=".7" />
      <path d="M178 86l4.5 8 4.5-8z" fill="#233f9a" opacity=".8" />
      <path className="zieht" d="M182 126c-10 12-24 16-38 14" stroke="#2c7048" strokeWidth="2.6" strokeLinecap="round" opacity=".7" />
      <path d="M148 136l-8 4 8 5z" fill="#2c7048" opacity=".8" />
    </svg>
  );
}

/** Die Ergebnisliste, wie sie auf dem Telefon aussieht: der eigene Eintrag rückt in die
 *  ersten drei, daneben die Karte mit dem Stecknadelkopf. */
function BildGefunden() {
  const g = "b";
  return (
    <svg viewBox="0 0 300 180" fill="none" aria-hidden className="h-auto w-full max-w-[290px]">
      <Malkasten id={g} />
      <ellipse cx="150" cy="172" rx="118" ry="6" fill="#2a2419" opacity=".05" />

      {/* Die Ergebnisliste */}
      <g filter={`url(#${g}-schatten)`}>
        <rect x="14" y="12" width="164" height="152" rx="16" fill={`url(#${g}-blatt)`} />
      </g>
      <rect x="14.75" y="12.75" width="162.5" height="150.5" rx="15.25" stroke="#ded9d0" strokeWidth="1.5" />
      <rect x="26" y="24" width="140" height="24" rx="12" fill="#f3f0ea" />
      <circle cx="41" cy="36" r="6.2" fill="none" stroke="#b5b0a6" strokeWidth="2.4" />
      <path d="M45.6 40.6l4.4 4.4" stroke="#b5b0a6" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M60 36h56" stroke="#cbc6bc" strokeWidth="3.4" strokeLinecap="round" />

      {/* Der eigene Eintrag, jetzt oben */}
      <g filter={`url(#${g}-hauch)`}>
        <rect x="22" y="58" width="148" height="36" rx="11" fill="#eef1fb" />
      </g>
      <rect x="22.75" y="58.75" width="146.5" height="34.5" rx="10.25" stroke="#233f9a" strokeWidth="1.5" />
      <rect x="32" y="66" width="20" height="20" rx="6" fill={`url(#${g}-navy)`} />
      <path d="M38 76l3.4 3.4L46 73.6" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M62 71h58M62 82h34" stroke="#233f9a" strokeWidth="3.4" strokeLinecap="round" />

      {/* Die anderen, zurückgetreten */}
      <g opacity=".5">
        <rect x="32" y="106" width="20" height="20" rx="6" fill="#e8e4dc" />
        <path d="M62 111h58M62 122h44" stroke="#cbc6bc" strokeWidth="3.4" strokeLinecap="round" />
        <rect x="32" y="136" width="20" height="20" rx="6" fill="#e8e4dc" />
        <path d="M62 141h48M62 152h58" stroke="#cbc6bc" strokeWidth="3.4" strokeLinecap="round" />
      </g>

      {/* Der Aufstieg */}
      <path className="zieht" d="M196 152V92" stroke="#233f9a" strokeWidth="2.8" strokeLinecap="round" opacity=".75" />
      <path className="pocht" d="M196 78l8.5 14h-17z" fill="#233f9a" />

      {/* Die Karte */}
      <g filter={`url(#${g}-schatten)`}>
        <rect x="216" y="20" width="72" height="72" rx="17" fill={`url(#${g}-still)`} />
      </g>
      <rect x="216.75" y="20.75" width="70.5" height="70.5" rx="16.25" stroke="#ded9d0" strokeWidth="1.5" />
      <path d="M216 50h72M254 20v72" stroke="#ded9d0" strokeWidth="1.6" opacity=".8" />
      <path d="M224 84c12-6 8-20 22-28" stroke="#d3cec4" strokeWidth="3.4" strokeLinecap="round" />
      <ellipse cx="252" cy="80" rx="11" ry="3.4" fill="#2a2419" opacity=".12" />
      <g className="schwebt"><path d="M252 36c8.8 0 16 7 16 15.6 0 10.4-16 27.4-16 27.4s-16-17-16-27.4C236 43 243.2 36 252 36z" fill={`url(#${g}-navy)`} /><circle cx="252" cy="51" r="5.6" fill="#fff" /></g>

      {/* Bewertungen */}
      <g className="funkelt" transform="translate(214 112)">
        {[0, 1, 2, 3, 4].map((i) => (
          <path key={i} d={`M${i * 15.5 + 5} 0l3.1 6.5 7.1 1-5.1 5 1.2 7.1-6.3-3.4-6.3 3.4 1.2-7.1-5.1-5 7.1-1z`} fill="#c4632a" />
        ))}
      </g>
      <path d="M214 138h68" stroke="#e2ded5" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M214 150h42" stroke="#e2ded5" strokeWidth="3.4" strokeLinecap="round" />
    </svg>
  );
}

/** Die Seiten als Netz, jede verbunden mit der Hauptseite in der Mitte, dahinter der
 *  Monatsbericht mit einer Kurve, die steigt. */
function BildBleiben() {
  const g = "c";
  const knoten: [number, number][] = [[40, 118], [46, 46], [124, 128], [128, 62]];
  return (
    <svg viewBox="0 0 300 180" fill="none" aria-hidden className="h-auto w-full max-w-[290px]">
      <Malkasten id={g} />
      <ellipse cx="150" cy="172" rx="118" ry="6" fill="#2a2419" opacity=".05" />

      {/* Der Monatsbericht */}
      <g filter={`url(#${g}-schatten)`}>
        <rect x="146" y="14" width="144" height="104" rx="16" fill={`url(#${g}-blatt)`} />
      </g>
      <rect x="146.75" y="14.75" width="142.5" height="102.5" rx="15.25" stroke="#ded9d0" strokeWidth="1.5" />
      <path d="M146 40h144" stroke="#e8e4dc" strokeWidth="1.5" />
      <circle cx="160" cy="27" r="3.6" fill="#e2ded5" />
      <circle cx="172" cy="27" r="3.6" fill="#e2ded5" />
      <path d="M188 27h44" stroke="#e8e4dc" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M160 102c16 0 22-13 34-24s22 4 34-15 16-21 28-25v64H160z" fill="#2c7048" opacity=".09" />
      <path className="steigt" d="M160 102c16 0 22-13 34-24s22 4 34-15 16-21 28-25" stroke="#2c7048" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="256" cy="38" r="6.5" fill="#fff" />
      <circle className="pocht" cx="256" cy="38" r="4.5" fill="#2c7048" />

      {/* Das Netz der Seiten */}
      {knoten.map(([x, y]) => (
        <path key={`l-${x}-${y}`} d={`M76 90L${x} ${y}`} stroke="#d3cec4" strokeWidth="2.6" strokeLinecap="round" />
      ))}
      {knoten.map(([x, y]) => (
        <g key={`n-${x}-${y}`}>
          <g filter={`url(#${g}-hauch)`}>
            <rect x={x - 15} y={y - 15} width="30" height="30" rx="10" fill="#fff" />
          </g>
          <rect x={x - 14.25} y={y - 14.25} width="28.5" height="28.5" rx="9.25" stroke="#dbe1f6" strokeWidth="1.5" />
          <path d={`M${x - 7} ${y - 4}h14M${x - 7} ${y + 2}h9`} stroke="#233f9a" strokeWidth="2.6" strokeLinecap="round" opacity=".85" />
        </g>
      ))}
      <g filter={`url(#${g}-schatten)`}>
        <circle cx="76" cy="90" r="25" fill={`url(#${g}-tief)`} />
      </g>
      <path d="M65 83h22M65 90h22M65 97h13" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" opacity=".92" />

      <path d="M18 150h122" stroke="#e2ded5" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M18 162h72" stroke="#e2ded5" strokeWidth="3.4" strokeLinecap="round" />
    </svg>
  );
}

/* ------------------------------------------------------ Die drei Bereiche ---
 * Die Zeichen für „das haben wir angesehen" im Kopf des Berichts. Vorher standen dort
 * drei Symbole von der Stange; diese hier zeigen die Sache selbst — eine Seite mit
 * Anruf-Knopf, ein Profilkärtchen mit Bewertung, ein Kartenausschnitt mit drei
 * Ergebnissen. Sie sitzen in einem 20er-Feld und tragen die Farbe der Umgebung.
 */

export function ZeichenWebsite() {
  return (
    <svg viewBox="0 0 22 22" fill="none" aria-hidden className="size-[19px]">
      <rect x="1.6" y="3" width="18.8" height="16" rx="3.4" fill="currentColor" opacity=".13" />
      <rect x="1.6" y="3" width="18.8" height="16" rx="3.4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M1.6 7.6h18.8" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="4.9" cy="5.3" r=".85" fill="currentColor" />
      <circle cx="7.5" cy="5.3" r=".85" fill="currentColor" />
      <path d="M5 11h6M5 14h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="12.6" y="10.4" width="5.4" height="5.4" rx="1.7" fill="currentColor" />
      <path d="M14.1 13.1l1 1 1.8-2" stroke="#fff" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ZeichenProfil() {
  return (
    <svg viewBox="0 0 22 22" fill="none" aria-hidden className="size-[19px]">
      <rect x="1.6" y="2.6" width="18.8" height="16.8" rx="3.6" fill="currentColor" opacity=".13" />
      <rect x="1.6" y="2.6" width="18.8" height="16.8" rx="3.6" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="7.4" cy="8.2" r="2.3" fill="currentColor" />
      <path d="M4 15.4c.5-1.9 1.8-2.9 3.4-2.9s2.9 1 3.4 2.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13.4 7.4h4M13.4 10.4h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13.6 14.6l.9-1.9.9 1.9 2 .3-1.5 1.4.4 2-1.8-1-1.8 1 .4-2-1.5-1.4z" fill="currentColor" />
    </svg>
  );
}

export function ZeichenSichtbarkeit() {
  return (
    <svg viewBox="0 0 22 22" fill="none" aria-hidden className="size-[19px]">
      <path d="M2 5.4l6-2.2 6 2.2 6-2.2v13.4l-6 2.2-6-2.2-6 2.2z" fill="currentColor" opacity=".13" />
      <path d="M2 5.4l6-2.2 6 2.2 6-2.2v13.4l-6 2.2-6-2.2-6 2.2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 3.2v13.4M14 5.4v13.4" stroke="currentColor" strokeWidth="1.3" opacity=".55" />
      <path d="M11 6.4c1.8 0 3.2 1.4 3.2 3.1 0 2.1-3.2 5.5-3.2 5.5s-3.2-3.4-3.2-5.5c0-1.7 1.4-3.1 3.2-3.1z" fill="currentColor" />
      <circle cx="11" cy="9.5" r="1.15" fill="#fff" />
    </svg>
  );
}

/* ------------------------------------------------- Zeichen je Leistung ---
 * Dieselbe Machart wie die drei im Kopf (Luka, 06.09.2026: „so kannst du die auch bei den
 * einzelnen Service-Sektionen machen"): jedes zeigt die Sache selbst statt eines Symbols
 * von der Stange, sitzt in einem 22er-Feld und nimmt seine Farbe von der Umgebung.
 *
 * Die Zuordnung laeuft ueber den Code der Position aus `build-plan.ts`. Ein unbekannter
 * Code faellt auf das Karten-Zeichen zurueck statt zu verschwinden.
 */

const ZEICHEN: Record<string, () => ReactNode> = {
  /* Antwort in fünf Minuten: Sprechblase mit Uhr. */
  SL: () => (
    <>
      <path d="M3 6.6A2.6 2.6 0 015.6 4h9.8A2.6 2.6 0 0118 6.6v5.2a2.6 2.6 0 01-2.6 2.6H8.4L4.6 18v-3.6h-1V6.6z" fill="currentColor" opacity=".16" />
      <path d="M3 6.6A2.6 2.6 0 015.6 4h9.8A2.6 2.6 0 0118 6.6v5.2a2.6 2.6 0 01-2.6 2.6H8.4L4.6 18v-3.6H5A2 2 0 013 12.4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="16.4" cy="15.4" r="4.4" fill="currentColor" />
      <path d="M16.4 13.1v2.5l1.7 1.1" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  /* Bewertungssystem: Stern mit Haken. */
  RV: () => (
    <>
      <path d="M11 2.8l2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8z" fill="currentColor" opacity=".16" />
      <path d="M11 2.8l2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8.4 11.2l1.9 1.9 3.6-3.9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  /* Google-Profil: Stecknadel mit Kärtchen. */
  GB: () => (
    <>
      <path d="M11 2.6c3 0 5.4 2.4 5.4 5.3 0 3.9-5.4 11-5.4 11S5.6 11.8 5.6 7.9C5.6 5 8 2.6 11 2.6z" fill="currentColor" opacity=".16" />
      <path d="M11 2.6c3 0 5.4 2.4 5.4 5.3 0 3.9-5.4 11-5.4 11S5.6 11.8 5.6 7.9C5.6 5 8 2.6 11 2.6z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="11" cy="7.8" r="2.1" fill="currentColor" />
    </>
  ),
  /* Website: Fenster mit Anruf-Knopf. */
  ST: () => (
    <>
      <rect x="2.4" y="3.6" width="17.2" height="14.8" rx="3.2" fill="currentColor" opacity=".16" />
      <rect x="2.4" y="3.6" width="17.2" height="14.8" rx="3.2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.4 8h17.2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.6 11.4h5.2M5.6 14.4h3.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="12.8" y="10.8" width="5.2" height="5.2" rx="1.7" fill="currentColor" />
      <path d="M14.2 13.4l1 1 1.6-1.9" stroke="#fff" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  /* Keyword-Karte: Lupe über einer Liste. */
  KW: () => (
    <>
      <rect x="2.4" y="3.4" width="12.6" height="15.2" rx="3" fill="currentColor" opacity=".16" />
      <rect x="2.4" y="3.4" width="12.6" height="15.2" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.4 7.4h6.6M5.4 10.6h4.4M5.4 13.8h5.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="15.6" cy="13.4" r="4.2" fill="#fff" />
      <circle cx="15.6" cy="13.4" r="4.2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M18.7 16.5l2 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  /* Seiten: mehrere Blätter, das vorderste hervorgehoben. */
  PG: () => (
    <>
      <rect x="6.4" y="2.6" width="13.2" height="14.4" rx="2.8" fill="currentColor" opacity=".16" />
      <rect x="6.4" y="2.6" width="13.2" height="14.4" rx="2.8" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2.4" y="5.4" width="13.2" height="14.4" rx="2.8" fill="#fff" />
      <rect x="2.4" y="5.4" width="13.2" height="14.4" rx="2.8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.4 9.4h7.2M5.4 12.4h5M5.4 15.4h6.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>
  ),
  /* Reaktivierung: eine alte Karteikarte, aus der ein Pfeil zurueckkommt. */
  RA: () => (
    <>
      <rect x="2.6" y="4.4" width="12.4" height="14.6" rx="2.6" fill="currentColor" opacity=".16" />
      <rect x="2.6" y="4.4" width="12.4" height="14.6" rx="2.6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.6 9h6.4M5.6 12.2h4.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M12.4 17.6a5.4 5.4 0 106.8-6.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" />
      <path d="M16.6 8.4l3.2 2.4-2.8 2.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  /* Bestandsaufnahme: eine Messlatte mit gesetztem Startpunkt. */
  MM: () => (
    <>
      <rect x="2.4" y="3.4" width="17.2" height="15.2" rx="2.8" fill="currentColor" opacity=".16" />
      <rect x="2.4" y="3.4" width="17.2" height="15.2" rx="2.8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.4 14.6h17.2" stroke="currentColor" strokeWidth="1.4" opacity=".5" />
      <path d="M6 14.6V11M10 14.6V8M14 14.6V12.4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="17.4" cy="9.4" r="2.4" fill="currentColor" />
      <path d="M17.4 8.4v2.2" stroke="#fff" strokeWidth="1.3" strokeLinecap="round" />
    </>
  ),
  /* Training: zwei Koepfe, einer zeigt dem anderen etwas. */
  TR: () => (
    <>
      <circle cx="7.4" cy="7" r="3.2" fill="currentColor" opacity=".16" />
      <circle cx="7.4" cy="7" r="3.2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.6 18.4c0-2.9 2.1-4.8 4.8-4.8s4.8 1.9 4.8 4.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="12.6" y="4.4" width="7" height="8.6" rx="2" fill="#fff" />
      <rect x="12.6" y="4.4" width="7" height="8.6" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M14.8 7.4h2.6M14.8 10h1.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  /* Auswertung: eine steigende Linie mit ihrem Startwert. */
  RP: () => (
    <>
      <rect x="2.4" y="3.4" width="17.2" height="15.2" rx="2.8" fill="currentColor" opacity=".16" />
      <rect x="2.4" y="3.4" width="17.2" height="15.2" rx="2.8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.4 14.6l3.4-3.6 2.8 2.2 4.8-5.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M13.6 7.8h3v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle cx="5.4" cy="14.6" r="1.6" fill="currentColor" />
    </>
  ),
  /* KI-Empfang: eine Sprechblase, in der es rechnet. */
  AI: () => (
    <>
      <path d="M2.6 6.6A2.6 2.6 0 015.2 4h11.6a2.6 2.6 0 012.6 2.6v6a2.6 2.6 0 01-2.6 2.6H9L4.6 19v-3.8a2.6 2.6 0 01-2-2.6z" fill="currentColor" opacity=".16" />
      <path d="M2.6 6.6A2.6 2.6 0 015.2 4h11.6a2.6 2.6 0 012.6 2.6v6a2.6 2.6 0 01-2.6 2.6H9L4.6 19v-3.8a2.6 2.6 0 01-2-2.6z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M11 6.2l1.1 2.4 2.4 1.1-2.4 1.1L11 13.2l-1.1-2.4L7.5 9.7l2.4-1.1z" fill="currentColor" />
    </>
  ),
  /* Terminbuchung: ein Kalenderblatt mit gesetztem Haken. */
  BK: () => (
    <>
      <rect x="2.6" y="4.6" width="16.8" height="14.4" rx="2.8" fill="currentColor" opacity=".16" />
      <rect x="2.6" y="4.6" width="16.8" height="14.4" rx="2.8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.6 9h16.8M7 2.8v3.6M15 2.8v3.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M7.6 14l2.4 2.4 4.6-4.8" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </>
  ),
  /* Wiederkontakt: aus dem Kalender kommt zur richtigen Zeit eine Nachricht zurueck. */
  WK: () => (
    <>
      <rect x="2.6" y="4.4" width="13.4" height="13.4" rx="2.6" fill="currentColor" opacity=".16" />
      <rect x="2.6" y="4.4" width="13.4" height="13.4" rx="2.6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.6 8.4h13.4M6.4 2.8v3.2M12.2 2.8v3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="6.6" cy="12" r="1.3" fill="currentColor" />
      <circle cx="10.4" cy="12" r="1.3" fill="currentColor" opacity=".45" />
      <path d="M13.4 19.4a4.6 4.6 0 105.4-6.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" />
      <path d="M16.2 10.4l3 2.2-2.6 2.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  /* Uebergabe: ein Schluessel, der die Hand wechselt. */
  HO: () => (
    <>
      <circle cx="7" cy="11" r="4.4" fill="currentColor" opacity=".16" />
      <circle cx="7" cy="11" r="4.4" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="7" cy="11" r="1.5" fill="currentColor" />
      <path d="M11.4 11h7.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M15.6 11v3.2M18.4 11v2.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
};

/** Das Zeichen zu einer Position, mit der Karte als Rückfall. */
export function LeistungsZeichen({ code, className }: { code?: string; className?: string }) {
  const zeichnen = (code && ZEICHEN[code]) || ZEICHEN.GB;
  return (
    <svg viewBox="0 0 22 22" fill="none" aria-hidden className={className ?? "size-[18px]"}>
      {zeichnen()}
    </svg>
  );
}

/* ------------------------------------------------------------ Kacheltext ---
 * Kurz genug, um beim Überfliegen gelesen zu werden, lang genug, dass die Sache
 * ohne Vorwissen klar ist. Keine unserer Fachwörter.
 */

type Kachel = { en: string; de: string };
/** Eine der fünfzehn Positionen: ihr Name, und was sie dem Betrieb bringt. Der Name ist
 *  der aus dem Angebot, der Satz darunter ist seine Sprache — die beiden gehören zusammen,
 *  sonst liest er entweder eine Fachliste oder ein Versprechen ohne Substanz. */
type Leistung = { name: Kachel; nutzen: Kachel; code?: string; nurScale?: boolean };
type Schritt = {
  ton: "sofort" | "aufbau" | "dauer";
  bild: ReactNode;
  wann: Kachel;
  titel: Kachel;
  kacheln: Leistung[];
};

const SCHRITTE: Schritt[] = [
  {
    ton: "sofort",
    bild: <BildAntwort />,
    wann: { en: "Phase 1", de: "Phase 1" },
    titel: { en: "You stop losing enquiries", de: "Sie verlieren keine Anfrage mehr" },
    kacheln: [
      {
        name: { en: "A speed-to-lead system", de: "Antwort in fünf Minuten" },
        nutzen: {
          en: "Every enquiry answered within five minutes, day and night, and a missed call gets a text straight back.",
          de: "Jede Anfrage bekommt binnen fünf Minuten eine Antwort, Tag und Nacht, und ein verpasster Anruf eine SMS zurück.",
        },
        code: "SL",
      },
      {
        name: { en: "Your review system", de: "Ihr Bewertungssystem" },
        nutzen: {
          en: "A review is asked for after every finished job, and unhappy customers reach you before they reach Google.",
          de: "Nach jedem fertigen Auftrag wird um eine Bewertung gebeten, und Unzufriedene landen bei Ihnen statt bei Google.",
        },
        code: "RV",
      },
      {
        name: { en: "Reactivating your old customers", de: "Ihre alte Kundenliste, reaktiviert" },
        nutzen: {
          en: "One campaign to everyone who has not booked in a while. The fastest money in the whole plan.",
          de: "Eine Kampagne an alle, die länger nichts gebucht haben. Das schnellste Geld im ganzen Plan.",
        },
        code: "RA",
      },
      {
        name: { en: "Customers who come back on their own", de: "Kunden, die von selbst wiederkommen" },
        nutzen: {
          en: "Three to five messages, written once, that reach each customer at his own moment: a year after the job, or before the season.",
          de: "Drei bis fünf Nachrichten, einmal geschrieben, die jeden Kunden zu seinem eigenen Zeitpunkt erreichen.",
        },
        code: "WK",
      },
      {
        name: { en: "Your baseline audit", de: "Ihre Bestandsaufnahme" },
        nutzen: {
          en: "The businesses actually taking your work, how an enquiry reaches you today, and 28 days of numbers frozen as the starting point.",
          de: "Wer Ihnen die Aufträge abnimmt, wie eine Anfrage heute bei Ihnen ankommt, und 28 Tage Zahlen als Startpunkt.",
        },
        code: "MM",
      },
    ],
  },
  {
    ton: "aufbau",
    bild: <BildGefunden />,
    wann: { en: "Phase 2", de: "Phase 2" },
    titel: { en: "You show up where people search", de: "Sie tauchen auf, wo gesucht wird" },
    kacheln: [
      {
        name: { en: "Your Google Business Profile", de: "Ihr Google-Unternehmensprofil" },
        nutzen: {
          en: "Categories, your full service list with prices, hours, area and twenty real photos, plus your details identical across every directory Google checks.",
          de: "Kategorien, volle Leistungsliste mit Preisen, Zeiten, Gebiet und zwanzig echte Fotos, dazu Ihre Daten in jedem Verzeichnis gleich.",
        },
        code: "GB",
      },
      {
        name: { en: "Your new website", de: "Ihre neue Website" },
        nutzen: {
          en: "Built to get you called: one tap on every phone screen, a short form, and your town on every page.",
          de: "Gebaut, damit angerufen wird: ein Tipp auf jedem Handy, ein kurzes Formular, Ihr Ort auf jeder Seite.",
        },
        code: "ST",
      },
      {
        name: { en: "Your keyword map and site fixes", de: "Ihre Keyword-Karte und die Reparaturen" },
        nutzen: {
          en: "Pages named for the words people actually type, and the faults that stop Google reading your site closed first.",
          de: "Seiten benannt nach den Wörtern, die wirklich getippt werden, und die Fehler zuerst behoben, die Google am Lesen hindern.",
        },
        code: "KW",
      },
      {
        name: { en: "What you can prove, and how you sound", de: "Was Sie belegen können, und wie Sie klingen" },
        nutzen: {
          en: "Your numbers, years, guarantees and your own way of speaking, written down once, so no page sounds like an agency wrote it.",
          de: "Ihre Zahlen, Jahre, Garantien und Ihre Art zu sprechen, einmal festgehalten, damit keine Seite nach Agentur klingt.",
        },
        code: "ST",
      },
    ],
  },
  {
    ton: "dauer",
    bild: <BildBleiben />,
    wann: { en: "Phase 3", de: "Phase 3" },
    titel: { en: "You stay there without thinking about it", de: "Sie bleiben oben, ohne daran zu denken" },
    kacheln: [
      {
        name: { en: "Your service and location pages", de: "Ihre Leistungs- und Ortsseiten" },
        nutzen: {
          en: "A page of its own for every service and every place you genuinely work. You approve which get built before a word is written.",
          de: "Eine eigene Seite für jede Leistung und jeden Ort, an dem Sie wirklich arbeiten. Sie geben vorher frei, welche gebaut werden.",
        },
        code: "PG",
      },
      {
        name: { en: "Your pages point at each other", de: "Ihre Seiten verweisen aufeinander" },
        nutzen: {
          en: "So Google can see which of them matters most, and shows that one.",
          de: "Damit Google erkennt, welche davon die wichtigste ist, und die dann zeigt.",
        },
        code: "PG",
      },
      {
        name: { en: "A post on your profile every week", de: "Jede Woche ein Beitrag auf Ihrem Profil" },
        nutzen: {
          en: "Written and scheduled, each with a button that leads somewhere. Every new review answered inside 48 hours.",
          de: "Geschrieben und eingeplant, jeder mit einem Knopf, der irgendwohin führt. Jede neue Bewertung binnen 48 Stunden beantwortet.",
        },
        code: "GB",
      },
      {
        name: { en: "Your analytics system", de: "Ihre Auswertung" },
        nutzen: {
          en: "One page a month: enquiries, where they came from, what they were worth, each figure next to where you started.",
          de: "Monatlich eine Seite: Anfragen, woher sie kamen, was sie wert waren, jede Zahl neben Ihrem Startwert.",
        },
        code: "RP",
      },
      {
        name: { en: "Two hours of Claude, recorded", de: "Zwei Stunden Claude, aufgezeichnet" },
        nutzen: {
          en: "One workflow from your business built with you, in a workspace on your own account. The recordings stay with you.",
          de: "Ein Ablauf aus Ihrem Betrieb, gemeinsam gebaut, in einem Arbeitsbereich auf Ihrem Konto. Die Aufnahmen bleiben bei Ihnen.",
        },
        code: "TR",
      },
      {
        name: { en: "An AI front desk that knows its limits", de: "Ein KI-Empfang, der seine Grenzen kennt" },
        nurScale: true,
        nutzen: {
          en: "Answers round the clock from a script you approved, captures what a job needs, and hands anything unusual to a person.",
          de: "Antwortet rund um die Uhr aus einem Skript, das Sie freigeben, erfasst die nötigen Angaben und gibt Ungewöhnliches an einen Menschen ab.",
        },
        code: "AI",
      },
      {
        name: { en: "Enquiries booked straight into your calendar", de: "Anfragen landen direkt im Kalender" },
        nurScale: true,
        nutzen: {
          en: "Only the ones that meet your own criteria, with the job details already captured.",
          de: "Nur die, die Ihren eigenen Kriterien entsprechen, mit den Auftragsdetails schon erfasst.",
        },
        code: "BK",
      },
      {
        name: { en: "At the end, all of it is yours", de: "Am Ende gehört alles Ihnen" },
        nutzen: {
          en: "Every account in your name, written steps for each system, and one live run-through from a search to a booked job.",
          de: "Jedes Konto auf Ihren Namen, schriftliche Bedienschritte je System, und ein Durchlauf live von der Suche bis zum gebuchten Auftrag.",
        },
        code: "HO",
      },
    ],
  },
];


const TON = {
  /* `feld` traegt jetzt das Zeichen der Leistung statt eines Punktes (Luka, 06.09.2026:
     „remember to also use those icons in section 3 in the dropdowns"). Dieselbe Machart
     wie die Kaesten oben im Kopf: helle Flaeche, Zeichen in der Farbe des Schritts. */
  sofort: { num: "bg-[#2c7048]", chip: "bg-[#dcefe3] text-[#2c7048]", dot: "bg-[#2c7048]", feld: "bg-[#dcefe3] text-[#2c7048]" },
  aufbau: { num: "bg-navy", chip: "bg-navy-soft text-navy", dot: "bg-navy", feld: "bg-navy-soft text-navy" },
  dauer: { num: "bg-[#152459]", chip: "bg-[#f7ecd6] text-[#8a6215]", dot: "bg-[#152459]", feld: "bg-[#f7ecd6] text-[#8a6215]" },
} as const;

/** Die Bewegung in den drei Bildern.
 *
 *  KOSTET NICHTS UND LÄUFT AUF DER GRAFIKKARTE: alles hier bewegt entweder `transform`,
 *  `opacity` oder `stroke-dashoffset`, nie Größe oder Position im Layout — der Browser
 *  muss also nie neu rechnen, wo etwas steht. Gemessen am 06.09.2026 hob das die
 *  Blockierzeit der Seite nicht messbar an.
 *
 *  Wer Bewegung abgestellt hat, bekommt die Bilder still: die letzte Regel schaltet
 *  jede Animation ab, und weil jede in ihrem Endzustand beginnt, fehlt dann nichts. */
const BEWEGUNG = `
.lm-solution .zieht{stroke-dasharray:3 9;animation:lm-zieht 2.4s linear infinite}
@keyframes lm-zieht{to{stroke-dashoffset:-24}}
.lm-solution .tickt{transform-origin:224px 92px;animation:lm-tickt 6s cubic-bezier(.5,0,.2,1) infinite}
@keyframes lm-tickt{0%,8%{transform:rotate(0)}92%,100%{transform:rotate(360deg)}}
.lm-solution .pocht{animation:lm-pocht 3.2s ease-in-out infinite}
@keyframes lm-pocht{0%,100%{opacity:.55;transform:translateY(0)}50%{opacity:1;transform:translateY(-3px)}}
.lm-solution .steigt{stroke-dasharray:230;stroke-dashoffset:0;animation:lm-steigt 5s ease-in-out infinite}
@keyframes lm-steigt{0%{stroke-dashoffset:230}45%,100%{stroke-dashoffset:0}}
.lm-solution .funkelt{animation:lm-funkelt 4s ease-in-out infinite}
@keyframes lm-funkelt{0%,70%,100%{opacity:1}82%{opacity:.45}}
.lm-solution .schwebt{animation:lm-schwebt 5.5s ease-in-out infinite}
@keyframes lm-schwebt{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@media (prefers-reduced-motion: reduce){
  .lm-solution .zieht,.lm-solution .tickt,.lm-solution .pocht,
  .lm-solution .steigt,.lm-solution .funkelt,.lm-solution .schwebt{animation:none}
}`;

export function SolutionSection({ locale }: { locale: Locale }) {
  const de = locale === "de";
  return (
    <section aria-label={de ? "Was wir für Sie tun würden" : "What we would do for you"} className="lm-solution mb-10 sm:mb-14">
      <style dangerouslySetInnerHTML={{ __html: BEWEGUNG }} />
      <div className="mx-auto max-w-[1160px] px-5 sm:px-8">
        <SektionsKopf kapitel={KAPITEL.weg} locale={locale} />
        {/* Der erklärende Absatz unter der Überschrift ist raus (Luka, 06.09.2026,
            „minimalistisch"). Die drei Schritte tragen ihre Begründung selbst; ein Satz
            darüber, der dasselbe noch einmal sagt, verzögert nur den Blick auf sie. */}

        {/* NEBENEINANDER STATT UNTEREINANDER (Luka, 06.09.2026). Als drei volle Zeilen
            war jede Karte 1160 Pixel breit fuer eine Ueberschrift und ein Bild, also zur
            Haelfte leer, und man sah nie alle drei zugleich. Nebeneinander liest sich die
            Reihenfolge als Reihenfolge. `items-start` haelt die anderen beiden ruhig,
            wenn einer aufgeklappt wird. */}
        <div className="mt-6 grid items-start gap-3.5 lg:grid-cols-3">
          {SCHRITTE.map((s, i) => {
            const ton = TON[s.ton];
            return (
              /* AUFGEKLAPPT WIRD, WER ES WISSEN WILL (Luka, 06.09.2026). Zu sehen ist der
                 Schritt mit seinem Bild; die sechs Zeilen darunter holt sich, wer nachlesen
                 will. Der erste Schritt steht offen, damit sichtbar ist, dass hinter jeder
                 Zeile etwas liegt — eine Seite, auf der drei zugeklappte Kästen stehen und
                 sonst nichts, sieht aus wie eine leere Seite. */
              <details key={s.titel.en} data-lm-motion={`solution-${i}`} className="group overflow-hidden rounded-[18px] border border-hairline bg-white shadow-[0_1px_2px_rgba(28,23,18,.03),0_10px_30px_rgba(28,23,18,.045)]">
                <summary className="grid cursor-pointer list-none items-center gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_292px] sm:p-6 lg:grid-cols-1 lg:gap-3 [&::-webkit-details-marker]:hidden">
                  <div className="order-2 min-w-0 lg:order-none">
                    <div className="flex items-center gap-3">
                      {/* EINMAL DIE ZAHL, NICHT ZWEIMAL. Neben dem Kreis mit der "2" stand
                          die Pille "PHASE 2" -- dieselbe Ziffer im Abstand von acht Pixeln.
                          Der Kreis ist raus, die Pille traegt das Wort, das Luka wollte
                          (06.09.2026: "kannst stattdessen Phase 1, 2, 3 schreiben"). */}
                      <span className={`lm-datenlabel rounded-md px-3 py-1.5 ${ton.chip}`}>{s.wann[locale]}</span>
                    </div>
                    {/* Zwei Zeilen Platz, auch wenn der Titel nur eine braucht: sonst steht die
                        erste Karte kuerzer als die beiden neben ihr und das Trio wirkt schief. */}
                    <h3 className="lm-h-block mt-3.5 font-black lg:min-h-[2.4em]">{s.titel[locale]}</h3>
                    <span className="mt-3.5 inline-flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[.07em] text-navy">
                      {de ? `${s.kacheln.length} Punkte` : `${s.kacheln.length} things`}
                      <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
                    </span>
                  </div>
                  <div className="order-1 justify-self-center sm:justify-self-end lg:order-none lg:mb-1 lg:justify-self-start">{s.bild}</div>
                </summary>
                <ul className="m-0 grid list-none gap-px border-t border-hairline bg-hairline p-0 sm:grid-cols-2 lg:flex lg:flex-col">
                  {s.kacheln.map((k) => (
                    /* Die letzte Zeile darf keine halbe Lücke lassen: bei ungerader Anzahl
                       läuft der letzte Eintrag über beide Spalten, sonst schaut die graue
                       Trennfarbe durch und sieht aus wie ein Fehler. */
                    <li key={k.name.en} className="grid grid-cols-[22px_minmax(0,1fr)] items-start gap-3 bg-white px-5 py-4 sm:px-6 [&:last-child:nth-child(odd)]:sm:col-span-2">
                      <span className={`mt-[1px] grid size-[22px] shrink-0 place-items-center rounded-[7px] ${ton.feld}`}>
                        <LeistungsZeichen code={k.code} className="size-[15px]" />
                      </span>
                      <div className="min-w-0">
                        <b className="block text-[14px] font-bold leading-[1.3] tracking-[-.012em]">
                          {k.name[locale]}
                          {k.nurScale ? <span className="lm-datenlabel ml-2 align-middle">Scale</span> : null}
                        </b>
                        <span className="mt-1 block text-[13px] leading-[1.45] text-graphite">{k.nutzen[locale]}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })}
        </div>

        {/* Die drei Zusagen standen hier als eigene Karten und stehen jetzt im
            Preisblock darunter: zweimal dasselbe untereinander liest niemand zweimal. */}

        {/* WAS SIE RISKIEREN: NICHTS (Luka, 06.09.2026: „aus Sales-Sicht smart gestalten,
            es soll rüberkommen dass es glaubwürdig ist, dass es risikofrei ist").
            Die Reihenfolge ist die Verkaufslogik: erst was es kostet, dann warum ein Nein
            später nichts kostet, und zum Schluss das, was wir NICHT versprechen. Der letzte
            Punkt ist der, der die anderen glaubwürdig macht: wer offen sagt, wo er keine
            Zusage gibt, wird beim Rest geglaubt. Genau daran scheitern die Anbieter, über
            die sich Handwerker in ihren Bewertungen beschweren. */}
        <div className="mt-9">
          {/* OHNE UEBERSCHRIFT (Luka, 06.09.2026). Der Preis links und die vier Zusagen rechts
              sagen dasselbe wie die Zeile "Sie koennen jederzeit aussteigen", nur belegt statt
              behauptet. Eine Ueberschrift, die den Inhalt darunter wiederholt, kostet nur
              Hoehe und schiebt den Preis unter die Falz. */}
          <p className="lm-blockmarke m-0">{de ? "Die Konditionen" : "The terms"}</p>

          <div className="mt-4 grid gap-3.5 lg:grid-cols-[minmax(0,.72fr)_minmax(0,1.28fr)]">
            <div className="flex flex-col justify-center rounded-[18px] border border-hairline bg-white p-6 shadow-[0_1px_2px_rgba(28,23,18,.03),0_10px_30px_rgba(28,23,18,.045)] sm:p-7">
              {/* „Starts at" statt „Where it starts" (Luka, 06.09.2026): das eine sagt,
                  dass hier die Preise anfangen, das andere klingt nach dem einzigen Preis. */}
              <p className="lm-blockmarke m-0">{de ? "Ab" : "Starts at"}</p>
              <p className="m-0 mt-1.5 flex items-baseline gap-1.5">
                <span className="tnum text-[40px] font-black leading-none tracking-[-.045em] sm:text-[46px]">$199</span>
                <span className="text-[14px] font-bold text-graphite">{de ? "im Monat" : "a month"}</span>
              </p>
              <p className="m-0 mt-1 text-[13px] leading-[1.4] text-graphite">
                {de ? "nach einem Aufbau ab $499" : "after a build from $499"}
              </p>
              {/* DASS ES DER EINSTIEG IST, MUSS DASTEHEN (Luka, 06.09.2026). „$199 im Monat"
                  allein liest sich wie unser Preis, dabei ist es die untere Kante. Wer das
                  erst im Gespraech erfaehrt, fuehlt sich geholt — und genau das Gefuehl
                  soll dieser Abschnitt ausraeumen, nicht erzeugen. Die anderen Preise
                  stehen bewusst nicht hier: was passt, haengt am Befund, und eine
                  Preistabelle im Kaltreport laedt zum Vergleichen ein, bevor jemand
                  weiss, was er vergleicht. */}
              <p className="m-0 mt-2.5 inline-flex w-fit rounded-full bg-navy-soft/60 px-2.5 py-1 text-[11.5px] font-bold leading-[1.3] text-navy">
                {de ? "mehrere Modelle, je nach Bedarf" : "different plans for what you need"}
              </p>
            </div>

            <ul className="m-0 grid list-none gap-px overflow-hidden rounded-[18px] border border-hairline bg-hairline p-0 shadow-[0_1px_2px_rgba(28,23,18,.03),0_10px_30px_rgba(28,23,18,.045)] sm:grid-cols-2">
              {[
                /* NUR DIE ZEILE, KEIN NACHSATZ (Luka, 06.09.2026: „cut out the h2 in the
                   benefit boxes and make the headlines a bit stronger to compensate").
                   Sieben Zusagen mit je zwei Zeilen Erklaerung sind vierzehn Zeilen, die
                   niemand liest. Also traegt jede Zeile jetzt selbst, was vorher darunter
                   stand: nicht „Ihr Gebiet bleibt Ihres" plus Erklaerung, sondern gleich
                   „kein Wettbewerber von Ihnen in Ihrem Gebiet". */
                { en: "Thirty days money back", de: "Dreißig Tage Geld zurück" },
                { en: "No minimum term", de: "Keine Mindestlaufzeit" },
                { en: "Every account in your name", de: "Jedes Konto auf Ihren Namen" },
                { en: "No rival of yours in your area", de: "Kein Wettbewerber in Ihrem Gebiet" },
                { en: "One setup, then it runs", de: "Einmal einrichten, dann läuft es" },
                { en: "Luka and Varun, every time", de: "Immer Luka und Varun" },
                { en: "A five-minute report every month", de: "Jeden Monat ein Report" },
              ].map((z, k, alle) => (
                /* EINE UNGERADE ZAHL LAESST DIE LETZTE KACHEL ALLEIN, und daneben klafft ein
                   grauer Block. Sieben Zusagen sind nicht schlechter als acht, also spannt
                   sich die letzte ueber beide Spalten, statt ein achtes Argument zu erfinden,
                   nur damit das Raster aufgeht. */
                <li key={z.en} className={`bg-white px-6 py-[18px] ${
                  alle.length % 2 === 1 && k === alle.length - 1 ? "sm:max-lg:col-span-2" : ""}`}>
                  <b className="flex items-center gap-2.5 text-[15.5px] font-black leading-[1.32] tracking-[-.018em]">
                    <span className="grid size-[20px] shrink-0 place-items-center rounded-full bg-[#2c7048] text-white">
                      <svg viewBox="0 0 16 16" fill="none" aria-hidden className="size-[12px]"><path d="M3.5 8.4l3 3L12.5 5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </span>
                    <span className="min-w-0">{z[locale]}</span>
                  </b>
                </li>
              ))}
            </ul>
          </div>

        </div>
      </div>
    </section>
  );
}
