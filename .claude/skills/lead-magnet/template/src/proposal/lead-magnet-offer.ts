/** What the freelancer would run in each part of the cold report, and the videos
 *  that explain it. One place, so every report shows the same offer.
 *
 *  The service texts are not written here: each pillar names the build-plan
 *  rows (by `code`) that the report row already carries in `gantt.bars`, the
 *  same rows the call page and the agreement show. One source, no drift.
 *
 *  A video renders only when its URL is set. An empty string renders nothing
 *  on a published page; the dev server shows a marked slot instead, so the
 *  layout can be judged before the recording exists (proposal-blueprint.md:
 *  never a fake video frame on a send-ready page). */
export const LEAD_MAGNET_OFFER = {
  /** Approved glass walkthrough without the short introductory card (06.09.2026),
   *  with the selected Dry Bounce bed mixed quietly beneath the untouched voice.
   *  Native 1024×576 upright, 30 fps, 70.2 s; picture stream copied unchanged.
   *  Versioned objects preserve old reports' assets and avoid stale CDN copies. */
  // FUERS NETZ NEU KODIERT (06.09.2026): 26 MB waren bei 1024x576 gut das Sechsfache dessen,
  // was das Bild braucht, und das Video startet von selbst -- auf dem Handy im Mobilfunknetz
  // war das die teuerste Sache auf der Seite, und der Bericht geht auch in die USA. Jetzt
  // 4,2 MB (CRF 28, AAC 96k, faststart); im Standbildvergleich gegen die 5,9-MB-Fassung und
  // gegen das Original kein sichtbarer Unterschied. Die alten Dateien bleiben liegen.
  heroVideoUrl: "",
  // AUS UNSEREM EIGENEN HAUS (06.09.2026). Das Standbild ist das groesste sichtbare Element
  // der Seite. Aus dem Speicher geholt wartete es auf eine zweite Verbindung -- gemessen
  // schwankte es zwischen 0,3 und 1,7 s, und mit ihm die ganze Bewertung zwischen 86 und 95.
  // Neben der Seite ausgeliefert nutzt es die Verbindung, die ohnehin schon offen ist.
  // Es ist die unveraenderte Datei aus `videos/lead-magnet/hero-glass-no-fix-2026-09-06.jpg`.
  heroVideoPoster: "",
  heroVideoPortrait: false,
  pillars: {
    /** Get found: the search plan, the profile matched to the winners, the pages per area. */
    maps: { codes: ["KW", "GB", "PG"], videoUrl: "" },
    /** Build trust: reviews that arrive and get answered, the profile done properly. */
    profile: { codes: ["RV", "GB", "SL"], videoUrl: "" },
    /** Win enquiries: the site that converts, the pages and articles, the instant reply. */
    website: { codes: ["ST", "PG", "SL"], videoUrl: "" },
  },
  /** One short video per service box, by build-plan code; shown when the box
   *  is opened. Empty means the box opens to its deliverables only. */
  videos: { KW: "", GB: "", PG: "", RV: "", SL: "", ST: "" } as Record<string, string>,
  /** After go-live, from context/business.md: the monthly rhythm the owner buys. */
  monthly: {
    en: "After go-live: one profile post a week, every new review answered within 48 hours, and a plain monthly report of what created calls.",
    de: "Nach dem Start: ein Profilbeitrag pro Woche, jede neue Bewertung innerhalb von 48 Stunden beantwortet, und ein monatlicher Bericht darüber, was Anrufe gebracht hat.",
  },
} as const;

export type OfferPillar = keyof typeof LEAD_MAGNET_OFFER.pillars;
