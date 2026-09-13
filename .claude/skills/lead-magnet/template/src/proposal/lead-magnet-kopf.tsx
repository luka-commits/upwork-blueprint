"use client";

/* Der Sektionskopf des Kaltreports: eine Marke, fuenf Kapitel.
 *
 * WARUM (the reviewer, 06.09.2026): „die Sektionen haben unterschiedliche Ueberschriften, der Flow
 * des Lead Magnets ist nicht mehr richtig erkennbar." Gemessen am selben Tag stimmte, was er
 * sah: von fuenf Abschnitten trug genau einer eine Marke („The path"), die uebrigen fingen
 * mit einer nackten Ueberschrift an. Wer scrollt, sieht dann eine Folge von Aussagen und
 * nicht, dass es ein Bericht mit Kapiteln ist.
 *
 * Die Nummer traegt hier echte Information, sie ist keine Deko: die Reihenfolge ist das
 * Argument des Berichts. Erst die Branche, damit der eigene Befund als Chance und nicht als
 * Vorwurf liest. Dann der eigene Befund. Dann der Weg. Dann der Termin. Wer sie umstellt,
 * zerstoert die Dramaturgie, also darf man sie sehen.
 *
 * Ausgenommen bleibt der Hero: er ist der Einstieg, kein Kapitel, und eine „00" darueber
 * waere genau die Deko-Nummer, die diese Datei vermeiden soll.
 */

import { useEffect, useState } from "react";

type Locale = "en" | "de";
type Text = { en: string; de: string };

export type Kapitel = {
  schluessel: string;
  nummer: string;
  kicker: Text;
  titel: Text;
};

/** Die fuenf Kapitel, an einer Stelle, damit Nummer und Reihenfolge nicht auseinanderlaufen.
 *  Wer eine Sektion verschiebt, aendert hier die Nummer mit. */
export const KAPITEL: Record<"branche" | "befund" | "weg" | "termin", Kapitel> = {
  branche: {
    schluessel: "branche",
    nummer: "01",
    kicker: { en: "The industry", de: "Die Branche" },
    titel: {
      en: "Almost everyone loses money in the same three places",
      de: "Fast jeder verliert Geld an denselben drei Stellen",
    },
  },
  befund: {
    schluessel: "befund",
    nummer: "02",
    kicker: { en: "Your business", de: "Ihr Betrieb" },
    titel: { en: "Where you stand today", de: "Wo Sie heute stehen" },
  },
  weg: {
    schluessel: "weg",
    nummer: "03",
    kicker: { en: "The path", de: "Der Weg" },
    titel: { en: "Three steps, in this order", de: "Drei Schritte, in dieser Reihenfolge" },
  },
  termin: {
    schluessel: "termin",
    nummer: "04",
    kicker: { en: "Your next step", de: "Ihr nächster Schritt" },
    titel: {
      en: "Turn the findings into your first actions",
      de: "Aus den Befunden werden die ersten Schritte",
    },
  },
};

/** Nummer, Kapitelname, Aussage. Immer in dieser Form, immer in dieser Groesse.
 *  `hell` dreht die Farben fuer den dunklen Abschluss um. */
export function SektionsKopf({ kapitel, locale, hell = false, className = "" }: {
  kapitel: Kapitel;
  locale: Locale;
  hell?: boolean;
  className?: string;
}) {
  return (
    /* Die id ist der Anker, den die Kapitelleiste im Kopf beobachtet und anspringt.
       scroll-mt haelt die Ueberschrift beim Sprung unter dem klebenden Kopf. */
    <div id={`kapitel-${kapitel.schluessel}`} className={`lm-kopf scroll-mt-[84px] ${className}`}>
      <p className={`m-0 flex items-center gap-2.5 lm-kapitelmarke ${hell ? "text-white/55" : "text-pewter"}`}>
        <span className={`tnum ${hell ? "text-white/80" : "text-navy"}`}>{kapitel.nummer}</span>
        <span aria-hidden className={`h-px w-6 ${hell ? "bg-white/30" : "bg-hairline"}`} />
        {kapitel.kicker[locale]}
      </p>
      <h2 className={`lm-h-aussage m-0 mt-3 max-w-[19ch] font-black ${hell ? "text-white" : ""}`}>
        {kapitel.titel[locale]}
      </h2>
    </div>
  );
}

/* ------------------------------------------------ Wo bin ich gerade? ---
 * WARUM (the reviewer, 06.09.2026): „it would be cool if we have a roadmap in the header bar
 * that shows which section of the report we are in right now, that runs along as we
 * scroll down the page. That gives a clear orientation."
 *
 * Der Bericht ist lang, und wer bei Kapitel 03 ankommt, hat den Anfang nicht mehr im
 * Blick. Die Leiste beantwortet zwei Fragen auf einmal: wo stehe ich, und wie viel
 * kommt noch. Beides ohne zu scrollen, und ein Klick springt hin.
 *
 * Nur das aktive Kapitel zeigt seinen Namen. Vier Namen nebeneinander waeren eine
 * zweite Navigation im Kopf und wuerden mit den beiden Knoepfen rechts konkurrieren;
 * die drei anderen bleiben als Ziffer stehen, das genuegt zum Zaehlen.
 */

export const KAPITEL_FOLGE = ["branche", "befund", "weg", "termin"] as const;

/** Das oberste Kapitel, das gerade im oberen Drittel des Fensters steht. `null`, solange
 *  der Leser noch im Hero ist -- dann zeigt die Leiste nichts an, weil es nichts zu
 *  orientieren gibt. */
export function useAktivesKapitel(): string | null {
  const [aktiv, setAktiv] = useState<string | null>(null);
  useEffect(() => {
    /* ERST MIT IntersectionObserver GEBAUT, DANN GEMESSEN UND VERWORFEN (06.09.2026):
       der Beobachter haengt am Kapitelkopf, und sobald der oben aus dem Bild gescrollt
       ist, meldet er nichts mehr. Gemessen zeigte die Leiste dadurch bei zwei von vier
       Scrollstaenden gar kein Kapitel an.

       Was zaehlt, ist nicht „welcher Kopf ist sichtbar", sondern „an welchem Kopf bin ich
       zuletzt vorbeigekommen". Das beantwortet ein Scroll-Zaehler in einem Satz. Vier
       Messungen je Bild sind billig, und die Drosselung auf einen Frame haelt sie aus
       dem Scroll-Pfad heraus. */
    let angefordert = false;
    const marke = 96; // knapp unter dem klebenden Kopf
    const messen = () => {
      angefordert = false;
      let letztes: string | null = null;
      for (const s of KAPITEL_FOLGE) {
        const el = document.getElementById(`kapitel-${s}`);
        if (el && el.getBoundingClientRect().top <= marke) letztes = s;
      }
      setAktiv(letztes);
    };
    const beiScroll = () => {
      if (angefordert) return;
      angefordert = true;
      requestAnimationFrame(messen);
    };
    messen();
    window.addEventListener("scroll", beiScroll, { passive: true });
    window.addEventListener("resize", beiScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", beiScroll);
      window.removeEventListener("resize", beiScroll);
    };
  }, []);
  return aktiv;
}

/** Vier Ziffern im Kopf, die aktive traegt ihren Namen. Ein Klick springt ins Kapitel. */
export function KapitelLeiste({ aktiv, locale }: { aktiv: string | null; locale: Locale }) {
  const de = locale === "de";
  return (
    <nav aria-label={de ? "Kapitel des Berichts" : "Report chapters"} className="lm-leiste hidden items-center gap-1 lg:flex">
      {KAPITEL_FOLGE.map((s) => {
        const k = KAPITEL[s];
        const an = aktiv === s;
        return (
          <a
            key={s}
            href={`#kapitel-${s}`}
            aria-current={an ? "true" : undefined}
            className={`lm-leiste-glied flex items-center gap-2 rounded-full px-2.5 py-1.5 no-underline ${
              an ? "bg-navy-soft text-navy" : "text-pewter hover:text-graphite"
            }`}
          >
            <span className="tnum text-[10.5px] font-black">{k.nummer}</span>
            {an ? <span className="whitespace-nowrap text-[11px] font-bold">{k.kicker[locale]}</span> : null}
          </a>
        );
      })}
    </nav>
  );
}
