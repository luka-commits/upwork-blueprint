import type { ReactNode, SVGProps } from "react";

/** One drawn mark per kind of work.
 *
 *  Lives in its own file because both the rail and the panel behind it need
 *  the same mark, and the panel is imported BY the rail - putting the map in
 *  either one makes a cycle. At 14px a two-letter code is a puzzle and a shape
 *  is recognised, which matters when the reader is scanning ten rows. */
const GLYPHS: Record<string, ReactNode> = {
  ANALYTICS: <path d="M4 19V9M10 19V4M16 19v-7M22 19H2" />,
  AUTOMATION: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  REVIEWS: <path d="M12 4l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.7l5.4-.8z" />,
  LOCAL: (
    <>
      <circle cx="12" cy="10" r="3" />
      <path d="M12 21s-7-6.2-7-11a7 7 0 1114 0c0 4.8-7 11-7 11z" />
    </>
  ),
  CONVERSION: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18" />
    </>
  ),
  TRAINING: (
    <>
      <path d="M3 8l9-4 9 4-9 4z" />
      <path d="M7 11v5c0 1.1 2.2 2 5 2s5-.9 5-2v-5" />
    </>
  ),
  SEO: <path d="M4 6h16M4 12h10M4 18h13" />,
  CONTENT: (
    <>
      <path d="M6 3h9l5 5v13H6z" />
      <path d="M15 3v5h5" />
    </>
  ),
  AI: (
    <>
      <rect x="5" y="7" width="14" height="12" rx="3" />
      <path d="M12 4v3M9 13h.01M15 13h.01" />
    </>
  ),
  BOOKING: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4M9 15l2 2 4-4" />
    </>
  ),
  HANDOVER: (
    <>
      <path d="M4 12h13" />
      <path d="M13 7l5 5-5 5" />
      <path d="M20 4v16" />
    </>
  ),
};

export function ServiceIcon({
  category,
  code,
  tone,
  size = 14,
  variant = "default",
}: {
  category?: string;
  code?: string;
  tone: string;
  size?: number;
  variant?: "default" | "report";
}) {
  const reportCategory = code ? REPORT_CODES[code] ?? category : category;
  const glyph = variant === "report" ? REPORT_GLYPHS[reportCategory ?? ""] : GLYPHS[category ?? ""];
  if (!glyph) return <span style={{ width: size, height: size, flexShrink: 0 }} aria-hidden />;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={tone}
      strokeWidth={variant === "report" ? 1.65 : 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
      aria-hidden
    >
      {glyph}
    </svg>
  );
}

/** Report marks: a 24-unit grid, 1.65-unit strokes, rounded terminals.
 * The original marks stay the default for contracts and existing offers. */
const REPORT_CODES: Record<string, string> = { MM: "ANALYTICS", SL: "AUTOMATION", RA: "AUTOMATION", RV: "REVIEWS", GB: "LOCAL", ST: "CONVERSION", TR: "TRAINING", KW: "SEO", PG: "CONTENT", RP: "ANALYTICS", AI: "AI", BK: "BOOKING", HO: "HANDOVER" };
const REPORT_GLYPHS: Record<string, ReactNode> = {
  MAP: <><path d="m3 6 6-2 6 2 6-2v14l-6 2-6-2-6 2Z"/><path d="M9 4v14m6-7v9"/><circle cx="15" cy="7" r="2.5"/></>,
  LOCAL: <><rect x="4" y="3.5" width="16" height="17" rx="4"/><circle cx="10" cy="9" r="2"/><path d="M7 15c0-3 6-3 6 0m3-7h1m-1 4h1M8 18h8"/></>,
  CONVERSION: <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 8h18M7 6h.01M10 6h.01M7 12h6m-6 3h4m5-3v5m-2-2 2 2 2-2"/></>,
  REVIEWS: <><path d="M8 19H6l-3 2V7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3h-2"/><path d="m12 7 1.5 3 3.3.5-2.4 2.3.6 3.2-3-1.5L9 16l.6-3.2-2.4-2.3 3.3-.5Z"/></>,
  AUTOMATION: <><path d="M8 4H6a3 3 0 0 0-3 3v11l4-3h8a3 3 0 0 0 3-3v-1"/><path d="m16 2-5 7h5l-1 5 6-8h-5Z"/></>,
  ANALYTICS: <><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 16v-3m4 3V9m4 7v-5M8 6h4"/></>,
  TRAINING: <><rect x="3" y="4" width="18" height="13" rx="3"/><path d="m10 8 5 3-5 3ZM8 21l2-4m6 4-2-4"/></>,
  SEO: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6m-3-3v6"/></>,
  CONTENT: <><path d="M8 3h9a3 3 0 0 1 3 3v12H8ZM4 7v13a1 1 0 0 0 1 1h11M11 7h6m-6 4h6m-6 3h3"/></>,
  AI: <><path d="M17 4H6a3 3 0 0 0-3 3v11l4-3h10a3 3 0 0 0 3-3v-1M8 8h5m-5 3h3m7-9 1 3 3 1-3 1-1 3-1-3-3-1 3-1Z"/></>,
  BOOKING: <><rect x="3" y="5" width="18" height="16" rx="4"/><path d="M3 10h18M8 3v4m8-4v4m-8 8 3 3 5-5"/></>,
  HANDOVER: <><path d="M13 5H6a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-6M13 3h8v8m0-8-10 10m-4 3 2 2 4-4"/></>,
};

type ReportIconProps = SVGProps<SVGSVGElement> & { size?: number };
export type ReportIconComponent = (props: ReportIconProps) => ReactNode;
function mark(glyph: ReactNode): ReportIconComponent {
  return function ReportMark({ size = 24, ...props }: ReportIconProps) {
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...props} strokeWidth={1.65}>{glyph}</svg>;
  };
}
export const Building2 = mark(REPORT_GLYPHS.LOCAL);
export const MonitorSmartphone = mark(REPORT_GLYPHS.CONVERSION);
export const Search = mark(REPORT_GLYPHS.MAP);
export const CalendarCheck2 = mark(REPORT_GLYPHS.BOOKING);
export const Check = mark(<path d="m5 12 4.5 4.5L19 7"/>);
export const ChevronDown = mark(<path d="m6 9 6 6 6-6"/>);

const CalendarDays = CalendarCheck2;
const X = mark(<path d="m6 6 12 12M6 18 18 6"/>);
const Star = mark(<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/>);
const MapPin = mark(<><path d="M18 10c0 5-6 11-6 11S6 15 6 10a6 6 0 1 1 12 0Z"/><circle cx="12" cy="10" r="2"/></>);
const Clock3 = mark(<><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l4 2"/></>);
const Globe2 = mark(<><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/></>);
const CircleHelp = mark(<><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2l-1.5 1v1m0 3h.01"/></>);
const AlertTriangle = mark(<><path d="m10 4-8 14a2 2 0 0 0 2 3h16a2 2 0 0 0 2-3L14 4a2.3 2.3 0 0 0-4 0Z"/><path d="M12 9v5m0 3h.01"/></>);
const ExternalLink = mark(<><path d="M13 4h7v7m0-7L10 14M9 5H6a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-3"/></>);
const Navigation = mark(<path d="m3 11 18-8-8 18-2-8Z"/>);
const Bookmark = mark(<path d="M6 21V6a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v15l-6-4Z"/>);
const Phone = mark(<path d="m8 3 3 5-3 2a15 15 0 0 0 6 6l2-3 5 3-1 4c-1 3-7 0-11-4S2 6 4 4Z"/>);
export const reportProfileIcons = { AlertTriangle, Bookmark, CalendarDays, Check, ChevronDown, CircleHelp, Clock3, ExternalLink, Globe2, MapPin, Navigation, Phone, Star, X };
