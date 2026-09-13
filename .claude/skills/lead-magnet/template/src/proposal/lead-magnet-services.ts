/** Was jede Leistung tut und enthält - als Fließtext, für die Service-Kästen im Kaltreport.
 *
 *  EIGENE DATEI, WEIL SIE OFT ANGEFASST WIRD (06.09.2026). Die Kästen wurden an einem Abend
 *  viermal umgebaut; Texte und Bauteil in derselben Datei heißt, dass jede Textrunde das
 *  Bauteil anfasst.
 *
 *  DIE FORM (the reviewer, 06.09.2026): keine Aufzählung, sondern ein kurzer Absatz, der die Merkmale
 *  zusammenfasst. Zwei bis drei Sätze, in der Sprache des Betriebsinhabers.
 *
 *  DIE QUELLE: jeder Absatz ist aus `deliverables` in `lib/build-plan.ts` geschrieben -
 *  derselben Liste, die im Angebot und im Vertrag steht. Nichts hier steht über den
 *  Lieferumfang hinaus. Der erste Entwurf hatte binnen Minuten drei Behauptungen enthalten,
 *  die dort nicht stehen ("jede Bewertung in 48 Stunden beantwortet", "lädt schnell im
 *  Mobilfunknetz", Bewertungen auf der Website) - genau deshalb steht hier die Regel:
 *
 *  **Ändert sich der Lieferumfang, ändert sich zuerst `build-plan.ts` und dann dieser Text.**
 *  Wer hier etwas hinzufügt, das dort nicht steht, verspricht einem Fremden etwas, das im
 *  Vertrag fehlt.
 *
 *  Der Absatz umschreibt NIE die Überschrift der Zeile ("A website that turns visits into
 *  calls" braucht darunter nicht "eine Website, die Besuche in Anrufe verwandelt").
 */

export type Locale = "en" | "de";

export const SERVICE_TEXT: Record<string, Record<Locale, string>> = {
  MM: {
    en: "We map the three businesses actually taking your work, draw how an enquiry reaches you today, and freeze 28 days of calls, clicks and enquiries as your starting numbers. What comes out is a fix list, ordered by what each gap costs you, and everything later is measured against that day.",
    de: "Wir kartieren die drei Betriebe, die Ihnen tatsächlich Aufträge abnehmen, zeichnen auf, wie eine Anfrage heute bei Ihnen ankommt, und frieren 28 Tage Anrufe, Klicks und Anfragen als Ihre Startzahlen ein. Heraus kommt eine Mängelliste, sortiert nach dem, was jede Lücke Sie kostet - und alles Spätere wird an diesem Tag gemessen.",
  },
  SL: {
    en: "Every way an enquiry can reach you gets a reply within five minutes, day and night, and a missed call gets a text back. Routing rules send each type of enquiry to whoever should handle it, and out of hours answers in wording you approved. It then runs 48 hours under watch on your real enquiries before we call it done.",
    de: "Jeder Weg, auf dem eine Anfrage bei Ihnen ankommt, bekommt in fünf Minuten eine Antwort, Tag und Nacht, und ein verpasster Anruf eine SMS zurück. Regeln leiten jede Art von Anfrage an den, der sie bearbeiten soll, und nach Feierabend wird in Formulierungen geantwortet, die Sie freigegeben haben. Danach läuft es 48 Stunden unter Beobachtung an Ihren echten Anfragen, bevor es als fertig gilt.",
  },
  RV: {
    en: "A review request goes out automatically when a job is finished, in wording you approve and can edit any time. Unhappy customers land on a private route before they land on Google, and the reviews sitting unanswered get replies drafted for you.",
    de: "Nach einem fertigen Auftrag geht die Bitte um eine Bewertung automatisch raus, in Formulierungen, die Sie freigeben und jederzeit ändern können. Unzufriedene landen auf einem privaten Weg, bevor sie bei Google landen, und für die unbeantworteten Bewertungen werden Ihnen Antworten vorgeschrieben.",
  },
  GB: {
    en: "Categories, your full service list, hours and service area are set the way Google reads them, with up to twenty photos ordered so the strongest show first. The first month of profile posts is written and scheduled, and the profile and your website are matched on the business facts, because Google reads a mismatch as a reason to trust neither.",
    de: "Kategorien, Ihre volle Leistungsliste, Zeiten und Einzugsgebiet werden so gesetzt, wie Google sie liest, dazu bis zu zwanzig Fotos in einer Reihenfolge, die die stärksten zuerst zeigt. Der erste Monat Profil-Beiträge ist geschrieben und eingeplant, und Profil und Website sagen dieselben Fakten - eine Abweichung liest Google als Grund, keinem von beiden zu trauen.",
  },
  ST: {
    en: "Home, contact and about, up to three service pages from your own service list, and a blog page ready for what comes later. Every phone screen has one tap to call and a form that lands in your inbox and on your phone. Everything you already rank for keeps its address, and the site goes live submitted to Google with Search Console set up.",
    de: "Start, Kontakt und Über uns, bis zu drei Leistungsseiten aus Ihrer eigenen Liste und eine Blogseite für das, was später kommt. Jeder Handy-Bildschirm hat einen Tipp zum Anruf und ein Formular, das in Ihrem Postfach und auf Ihrem Handy landet. Alles, wofür Sie heute schon ranken, behält seine Adresse, und die Seite geht live, bei Google eingereicht und mit eingerichteter Search Console.",
  },
  TR: {
    en: "A Claude workspace on your own account, then two recorded sixty-minute sessions in which one workflow from your business gets built with you. The recordings are yours to keep, together with written steps so you can repeat the method without us.",
    de: "Ein Claude-Arbeitsbereich auf Ihrem eigenen Konto, dann zwei aufgezeichnete Stunden zu je sechzig Minuten, in denen ein Arbeitsablauf aus Ihrem Betrieb mit Ihnen gebaut wird. Die Aufzeichnungen bleiben bei Ihnen, dazu schriftliche Schritte, mit denen Sie die Methode ohne uns wiederholen.",
  },
  KW: {
    en: "A map of the searches your customers use, grouped by service, need and location, and a technical fix list ordered by risk and likely impact. Every critical fault gets closed, and the pages that already earn are protected against indexing and redirect mistakes.",
    de: "Eine Karte der Suchen, die Ihre Kunden benutzen, gruppiert nach Leistung, Anliegen und Ort, dazu eine technische Mängelliste, sortiert nach Risiko und wahrscheinlicher Wirkung. Jeder kritische Fehler wird geschlossen, und die Seiten, die heute schon Geld bringen, werden gegen Indexierungs- und Weiterleitungsfehler geschützt.",
  },
  PG: {
    en: "You approve a site map first: what gets built now, what follows month by month, what never gets built. Then every page on the now list goes live, location pages only where you genuinely work, plus four launch articles, each linked to a page that earns.",
    de: "Zuerst geben Sie eine Seitenkarte frei: was jetzt gebaut wird, was Monat für Monat folgt und was nie gebaut wird. Dann geht jede Seite der Jetzt-Liste live, Ortsseiten nur dort, wo Sie wirklich arbeiten, dazu vier Artikel zum Start, jeder verlinkt auf eine Seite, die Geld bringt.",
  },
  RP: {
    en: "One screen with visibility, visits, enquiries and what they were worth, every figure beside your starting number. A source breakdown shows where more effort pays, and anything that cannot be measured is labelled unknown instead of filled in.",
    de: "Ein Bildschirm mit Sichtbarkeit, Besuchen, Anfragen und ihrem Wert, jede Zahl neben Ihrer Startzahl. Eine Aufschlüsselung nach Herkunft zeigt, wo sich mehr Einsatz lohnt, und was nicht messbar ist, wird als unbekannt ausgewiesen statt ausgefüllt.",
  },
  AI: {
    en: "Questions get answered round the clock, only from a script you approved, and the details a job needs are captured before the enquiry reaches you. Anything unusual goes to a person with the whole transcript attached, and the jobs you never take are excluded by rule.",
    de: "Fragen werden rund um die Uhr beantwortet, ausschließlich aus einem Skript, das Sie freigegeben haben, und die Angaben, die ein Auftrag braucht, werden erfasst, bevor die Anfrage bei Ihnen ankommt. Ungewöhnliches geht mit dem ganzen Gesprächsverlauf an einen Menschen, und die Aufträge, die Sie nie annehmen, sind per Regel ausgeschlossen.",
  },
  BK: {
    en: "Enquiries that meet your own criteria are booked straight into your calendar with the job details already captured. Anything you want to see first waits at an approval gate, and the cases that should be refused are tested before it goes live.",
    de: "Anfragen, die Ihren eigenen Kriterien entsprechen, landen direkt als Termin in Ihrem Kalender, die Auftragsdetails schon erfasst. Was Sie zuerst sehen wollen, wartet an einer Freigabe, und die Fälle, die abgelehnt gehören, werden getestet, bevor es live geht.",
  },
  HO: {
    en: "Every system sits in an account you own or control, with written operating steps for each one. You keep the session recordings, and we walk one live path with you, from a search to a booked job.",
    de: "Jedes System liegt in einem Konto, das Ihnen gehört oder das Sie kontrollieren, mit schriftlichen Bedienschritten für jedes. Die Aufzeichnungen der Sitzungen bleiben bei Ihnen, und wir gehen einen Weg live mit Ihnen durch, von der Suche bis zum gebuchten Auftrag.",
  },
};
