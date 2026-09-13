"use client";

/* Meldet einmal, dass dieser Report wirklich offen war.
 *
 * WARUM NICHT SERVERSEITIG BEIM AUSLIEFERN: die Seite wird auch geladen, ohne dass ein Mensch
 * sie sieht. Postfach-Scanner und Link-Pruefer holen das HTML, bevor die Mail im Postfach
 * liegt; ein Zaehler an der Auslieferung haette also gemeldet "geoeffnet", bevor der Empfaenger
 * die Mail bekommen hat. Deshalb zaehlt erst, was drei Sekunden lang sichtbar war.
 *
 * Kein Cookie, kein fremder Dienst. `sessionStorage` haelt nur fest, dass dieser Tab schon
 * gemeldet hat; die Stundengrenze zieht ohnehin die Datenbank. */

import { useEffect } from "react";

const WARTE_MS = 3000;

export function ReportOpenBeacon({ slug }: { slug?: string }) {
  useEffect(() => {
    if (!slug) return;
    const merker = `pc-report-open:${slug}`;
    // `?intern` am Link markiert unsere eigene Kontrolle. Der Marker bleibt im
    // Browser liegen, damit auch der zweite Blick ohne Parameter nicht zaehlt.
    const internMerker = "pc-intern";
    let intern = false;
    try {
      if (new URLSearchParams(window.location.search).has("intern")) {
        window.localStorage.setItem(internMerker, "1");
      }
      intern = window.localStorage.getItem(internMerker) === "1";
    } catch {
      intern = false;
    }
    try {
      if (sessionStorage.getItem(merker)) return;
    } catch {
      // Privates Fenster ohne Speicher: dann meldet dieser Tab eben erneut, und die
      // Stundengrenze in der Datenbank faengt es ab.
    }

    let offen = 0;
    let seit = document.visibilityState === "visible" ? Date.now() : 0;
    let gemeldet = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const melde = () => {
      if (gemeldet) return;
      gemeldet = true;
      try {
        sessionStorage.setItem(merker, "1");
      } catch {
        /* siehe oben */
      }
      void fetch(`/api/report/open${intern ? "?intern=1" : ""}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ slug }),
        keepalive: true,
      }).catch(() => {
        // Eine Messung darf die Seite nie stoeren.
      });
    };

    const planen = () => {
      if (gemeldet || seit === 0) return;
      timer = setTimeout(melde, Math.max(0, WARTE_MS - offen));
    };

    const wechsel = () => {
      if (document.visibilityState === "visible") {
        seit = Date.now();
        planen();
      } else {
        if (seit) offen += Date.now() - seit;
        seit = 0;
        if (timer) clearTimeout(timer);
      }
    };

    planen();
    document.addEventListener("visibilitychange", wechsel);
    return () => {
      document.removeEventListener("visibilitychange", wechsel);
      if (timer) clearTimeout(timer);
    };
  }, [slug]);

  return null;
}
