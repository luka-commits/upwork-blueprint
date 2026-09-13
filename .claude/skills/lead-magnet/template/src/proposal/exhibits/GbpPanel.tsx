"use client";

/* eslint-disable @next/next/no-img-element */
import { createContext, useContext, useMemo, useState, type ReactNode, type SVGProps } from "react";
import {
  AlertTriangle as DefaultAlertTriangle,
  Bookmark as DefaultBookmark,
  CalendarDays as DefaultCalendarDays,
  Check as DefaultCheck,
  ChevronDown as DefaultChevronDown,
  CircleHelp as DefaultCircleHelp,
  Clock3 as DefaultClock3,
  ExternalLink as DefaultExternalLink,
  Globe2 as DefaultGlobe2,
  MapPin as DefaultMapPin,
  Navigation as DefaultNavigation,
  Phone as DefaultPhone,
  Star as DefaultStar,
  X as DefaultX,
} from "lucide-react";
import type {
  GbpExhibit,
  GbpAuditRow,
  GbpFieldIcon,
  GbpFieldStatus,
  GbpInlineFinding,
  GbpProfileAction,
  GbpProfileField,
  GbpProfileView,
} from "../types";
import { d, SoftBreakText } from "../ui";


type ProfileIcon = (props: SVGProps<SVGSVGElement> & { size?: number }) => ReactNode;
const defaultIcons = { AlertTriangle: DefaultAlertTriangle, Bookmark: DefaultBookmark, CalendarDays: DefaultCalendarDays, Check: DefaultCheck, ChevronDown: DefaultChevronDown, CircleHelp: DefaultCircleHelp, Clock3: DefaultClock3, ExternalLink: DefaultExternalLink, Globe2: DefaultGlobe2, MapPin: DefaultMapPin, Navigation: DefaultNavigation, Phone: DefaultPhone, Star: DefaultStar, X: DefaultX };
type ProfileIcons = { [K in keyof typeof defaultIcons]: ProfileIcon };
const ProfileIconContext = createContext<ProfileIcons>(defaultIcons);
function profileIcon(name: keyof ProfileIcons): ProfileIcon {
  return function ProfileMark(props) {
    const Icon = useContext(ProfileIconContext)[name];
    return <Icon {...props} />;
  };
}
const AlertTriangle = profileIcon("AlertTriangle");
const Bookmark = profileIcon("Bookmark");
const CalendarDays = profileIcon("CalendarDays");
const Check = profileIcon("Check");
const ChevronDown = profileIcon("ChevronDown");
const CircleHelp = profileIcon("CircleHelp");
const Clock3 = profileIcon("Clock3");
const ExternalLink = profileIcon("ExternalLink");
const Globe2 = profileIcon("Globe2");
const MapPin = profileIcon("MapPin");
const Navigation = profileIcon("Navigation");
const Phone = profileIcon("Phone");
const Star = profileIcon("Star");
const X = profileIcon("X");

const copy = {
  en: {
    title: "Google Business Profile review",
    subtitle: "Recommendation, first draft and proof in one place.",
    current: "Today",
    prepared: "Prepared",
    switcher: "Switch Google Business Profile view",
    verified: "Profile verified",
    publicPhotos: "public photos",
    actions: { website: "Website", directions: "Directions", save: "Save", call: "Call", booking: "Book" },
    legend: ["Good", "Check", "Missing", "Check inside account", "Prepared"],
    businessDetails: "Business details",
    categories: "Categories",
    primaryCategory: "Primary category",
    otherCategories: "Other categories",
    description: "Description",
    services: "Services",
    photos: "Photos",
    updates: "Business updates",
    reviews: "Reviews",
    additional: "Additional profile details",
    reviewsSuffix: "Google reviews",
    ownerResponse: "Owner response",
    noOwnerResponse: "No owner response visible",
    draft: "Draft, not live",
    ourTake: "Our recommendation",
    currentSnapshot: "Currently shown",
    preparedDraft: "Suggested first draft",
    currentEntry: "See the current entry",
    currentProof: "See the current proof",
    noChange: "No change proposed",
    openDraft: "View suggestion",
    profileAudit: "Profile check",
    liveNow: "What is live now",
    doNext: "What to do",
    fullProfile: "We finish the profile with you",
    fullProfileBody: "Final categories, description, services and review replies are prepared in the working session.",
  },
  de: {
    title: "Google-Unternehmensprofil geprüft",
    subtitle: "Empfehlung, erster Entwurf und Nachweis an einem Ort.",
    current: "Heute",
    prepared: "Vorbereitet",
    switcher: "Google-Profil Ansicht wechseln",
    verified: "Profil bestätigt",
    publicPhotos: "öffentliche Fotos",
    actions: { website: "Website", directions: "Route", save: "Speichern", call: "Anrufen", booking: "Termin" },
    legend: ["Passt", "Prüfen", "Fehlt", "Im Profil prüfen", "Vorbereitet"],
    businessDetails: "Unternehmensangaben",
    categories: "Kategorien",
    primaryCategory: "Hauptkategorie",
    otherCategories: "Weitere Kategorien",
    description: "Beschreibung",
    services: "Leistungen",
    photos: "Fotos",
    updates: "Aktuelles vom Unternehmen",
    reviews: "Rezensionen",
    additional: "Weitere Profilangaben",
    reviewsSuffix: "Google-Rezensionen",
    ownerResponse: "Antwort der Inhaberin",
    noOwnerResponse: "Keine Antwort der Inhaberin sichtbar",
    draft: "Entwurf, noch nicht live",
    ourTake: "Unsere Empfehlung",
    currentSnapshot: "Aktuell eingetragen",
    preparedDraft: "Vorgeschlagener erster Entwurf",
    currentEntry: "Aktuellen Eintrag ansehen",
    currentProof: "Aktuellen Nachweis ansehen",
    noChange: "Keine Änderung vorgeschlagen",
    openDraft: "Vorschlag ansehen",
    profileAudit: "Profil-Check",
    liveNow: "Was aktuell sichtbar ist",
    doNext: "Was zu tun ist",
    fullProfile: "Wir stellen das Profil mit Ihnen fertig",
    fullProfileBody: "Finale Kategorien, Beschreibung, Leistungen und Antworten entstehen im Arbeitstermin.",
  },
} as const;

const findingStyles: Record<GbpFieldStatus, string> = {
  good: "border-emerald-600 bg-emerald-50 text-emerald-950",
  warn: "border-amber-500 bg-amber-50 text-amber-950",
  bad: "border-red-600 bg-red-50 text-red-950",
  open: "border-slate-400 bg-slate-50 text-slate-800",
  new: "border-blue-600 bg-blue-50 text-blue-950",
};

const dotStyles: Record<GbpFieldStatus, string> = {
  good: "bg-emerald-600",
  warn: "bg-amber-500",
  bad: "bg-red-600",
  open: "bg-slate-400",
  new: "bg-blue-600",
};

const iconMap: Record<GbpFieldIcon, ProfileIcon> = {
  address: MapPin,
  hours: Clock3,
  phone: Phone,
  website: Globe2,
  booking: CalendarDays,
  info: CircleHelp,
};

function Stars({ rating, size = 14 }: { rating: number; size?: number }) {
  return (
    <span className="inline-flex gap-0.5 align-[-2px]" aria-label={`${rating} stars`}>
      {[1, 2, 3, 4, 5].map((value) => (
        <Star
          key={value}
          width={size}
          height={size}
          strokeWidth={1.5}
          fill={value <= Math.round(rating) ? "#fbbc04" : "#dadce0"}
          color={value <= Math.round(rating) ? "#fbbc04" : "#dadce0"}
          aria-hidden
        />
      ))}
    </span>
  );
}

function FindingNote({ finding, className = "" }: { finding?: GbpInlineFinding; className?: string }) {
  if (!finding) return null;
  return (
    <div className={`min-w-0 rounded-r-xl border-l-[3px] px-3.5 py-3 text-[15px] leading-[1.5] ${findingStyles[finding.status]} ${className}`}>
      <strong className="mb-1 block text-[11px] font-extrabold uppercase tracking-[0.06em]">{finding.label}</strong>
      <span className="block opacity-80">{finding.text}</span>
    </div>
  );
}

function normaliseLabel(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9äöüß]+/g, " ").trim();
}

function auditRowFor(rows: GbpAuditRow[] | undefined, aliases: string[]) {
  const wanted = aliases.map(normaliseLabel);
  return rows?.find((row) => {
    const label = normaliseLabel(row.label);
    return wanted.some((alias) => label.includes(alias) || alias.includes(label));
  });
}

function evidenceFinding({
  explicit,
  rows,
  aliases,
  locale,
}: {
  explicit?: GbpInlineFinding;
  rows?: GbpAuditRow[];
  aliases: string[];
  locale: "en" | "de";
}): GbpInlineFinding {
  if (explicit) return explicit;
  const row = auditRowFor(rows, aliases);
  const status: GbpFieldStatus = row?.status ?? "open";
  if (status === "good") {
    return {
      status,
      label: locale === "de" ? "Passt" : "Good",
      text: locale === "de" ? "Keine Änderung nötig." : "No change needed.",
    };
  }
  if (status === "open" || !row) {
    return {
      status: "open",
      label: locale === "de" ? "Im Konto prüfen" : "Check inside the account",
      text: locale === "de"
        ? "Die öffentliche Quelle reicht für eine sichere Empfehlung nicht aus. Vor einer Änderung im Profil prüfen."
        : "The public source is not enough for a safe recommendation. Check the field inside the profile before changing it.",
    };
  }
  return {
    status,
    label: locale === "de" ? "Beleg fehlt" : "Evidence missing",
    text: locale === "de"
      ? "Der gespeicherte Befund markiert dieses Feld, enthält aber noch keine sichere konkrete Änderung."
      : "The stored finding flags this field but does not yet support a safe, specific change.",
  };
}

function FieldIcon({ name = "info" }: { name?: GbpFieldIcon }) {
  const Icon = iconMap[name];
  return (
    <span className="grid size-8 place-items-center rounded-full border border-slate-200 text-slate-500">
      <Icon size={14} strokeWidth={1.8} aria-hidden />
    </span>
  );
}

function ProfileField({ field, prepared = false }: { field: GbpProfileField; prepared?: boolean }) {
  const changed = prepared && field.changed === true;
  const value = (
    <>
      <small className="mb-1 block text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">{field.label}</small>
      <strong className={`block text-[16px] leading-snug ${changed ? "text-emerald-800" : "text-slate-950"}`}><SoftBreakText value={field.value} /></strong>
      {field.detail ? <em className="mt-1 block text-[13px] not-italic leading-snug text-emerald-800">{field.detail}</em> : null}
    </>
  );

  return (
    <div className="grid grid-cols-[32px_minmax(0,0.8fr)_minmax(280px,1.2fr)] items-center gap-3 border-t border-slate-100 py-3 first:border-t-0 max-md:grid-cols-[32px_minmax(0,1fr)] max-md:items-start">
      <FieldIcon name={field.icon} />
      <div className="min-w-0">
        {field.href ? <a href={field.href} target="_blank" rel="noreferrer" className="no-underline">{value}</a> : value}
      </div>
      {!prepared ? <FindingNote finding={field.finding} className="max-md:col-start-2" /> : null}
    </div>
  );
}

function ProfileSection({ label, headline, children }: { label: string; headline?: string; children: ReactNode }) {
  return (
    <section className="border-b-8 border-slate-100 px-7 py-6 last:border-b-0 max-sm:px-4 max-sm:py-5">
      <header className="mb-4">
        <span className="mb-1 block text-[11px] font-extrabold uppercase tracking-[0.09em] text-blue-700">{label}</span>
        {headline ? <strong className="block text-[19px] leading-tight tracking-[-0.02em] text-slate-950 max-sm:text-[17px]">{headline}</strong> : null}
      </header>
      {children}
    </section>
  );
}

function Action({ icon: Icon, label, href }: { icon: ProfileIcon; label: string; href?: string }) {
  const content = (
    <span className="grid min-h-[60px] place-items-center content-center gap-1 text-center text-[10px] font-bold text-blue-600 max-sm:min-h-[56px] max-sm:text-[9px]">
      <span className="grid size-8 place-items-center rounded-full border border-blue-200"><Icon size={15} strokeWidth={1.8} aria-hidden /></span>
      {label}
    </span>
  );
  return href ? <a href={href} target="_blank" rel="noreferrer" className="no-underline">{content}</a> : content;
}

function PhotoStage({ view, photoWord, draftWord, compact = false }: { view: GbpProfileView; photoWord: string; draftWord: string; compact?: boolean }) {
  // Google's photo URLs from the profile pull answer 403 when hotlinked, so a
  // photo that fails to load is dropped. With no photo left the stage collapses
  // to one slim line: a grey block under a "14 public photos" badge reads as a
  // placeholder and failed the visual review (Lock Medic, 05.09.2026).
  const [failed, setFailed] = useState<Set<string>>(() => new Set());
  const photos = (view.photos ?? []).filter((photo) => !failed.has(photo.src)).slice(0, 3);
  const label = view.photoLabel ?? `${(view.photos ?? []).length} ${photoWord}`;
  const draftBadge = view.draft ? <b className="rounded-lg bg-blue-50/95 px-2.5 py-1.5 text-[10px] text-blue-800 shadow-sm">{view.stateLabel ?? draftWord}</b> : null;
  if (!photos.length) {
    return (
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-4 py-2.5">
        <span className="text-[11px] font-semibold text-slate-500">{label}</span>
        {draftBadge}
      </div>
    );
  }
  const layout = photos.length <= 1 ? "grid-cols-1" : photos.length === 2 ? "grid-cols-2" : "grid-cols-[1.7fr_.65fr_.65fr] max-sm:grid-cols-[1.45fr_.75fr] max-sm:grid-rows-2";
  return (
    <div className={`relative grid gap-[3px] overflow-hidden bg-slate-200 ${compact ? "h-[150px] max-sm:h-[132px]" : "h-[220px] max-sm:h-[180px]"} ${layout}`}>
      {photos.map((photo, index) => (
        <img
          key={`${photo.src}-${index}`}
          src={photo.src}
          alt={photo.alt}
          onError={() => setFailed((previous) => new Set(previous).add(photo.src))}
          className={`h-full min-h-0 w-full object-cover ${photos.length >= 3 && index === 0 ? "max-sm:row-span-2" : ""}`}
        />
      ))}
      <span className="absolute bottom-3 right-3 rounded-lg bg-white/90 px-2.5 py-1.5 text-[10px] font-bold shadow-sm backdrop-blur">{label}</span>
      {view.draft ? <b className="absolute left-3 top-3 rounded-lg bg-blue-50/95 px-2.5 py-1.5 text-[10px] text-blue-800 shadow-sm backdrop-blur">{view.stateLabel ?? draftWord}</b> : null}
    </div>
  );
}

function legacyView(data: GbpExhibit): GbpProfileView | null {
  const panel = data.panel;
  if (!panel) return null;
  const comment = (row: NonNullable<GbpExhibit["auditRows"]>[number]) => {
    if (row.status === "good") return undefined;
    const actions: Record<string, string> = {
      Address: "Use exactly the same spelling on the website, legal notice and profile.",
      Phone: "Use one confirmed number everywhere a customer can see it.",
      Website: "Link the page that best matches the service a customer searched for.",
      Hours: "Confirm the public hours, including special and weekend hours.",
      Photos: "Add recent photos of the people, premises and service in action.",
      Reviews: "Ask every happy customer and answer each review personally.",
      Description: "Explain the main service, area and next step in plain language.",
      Categories: "Keep only categories that match a service customers can book.",
    };
    return {
      status: row.status,
      label: row.status === "bad" ? "Missing" : "Improve",
      text: actions[row.label] ?? "Confirm this inside the profile before publishing changes.",
    } as const;
  };
  return {
    name: panel.name,
    subtitle: panel.subtitle,
    ratingValue: panel.ratingValue,
    reviewsCount: panel.reviewsCount,
    photos: panel.mapImage ? [{ src: panel.mapImage, alt: panel.attribution ?? panel.name }] : [],
    photoLabel: panel.photoLabel,
    fields: (data.auditRows ?? []).map((row) => ({
      label: row.label,
      value: row.value,
      icon: "info",
      finding: comment(row),
    })),
    description: panel.description ? { text: panel.description } : undefined,
  };
}

function ProfileView({ view, locale }: { view: GbpProfileView; locale: "en" | "de" }) {
  const t = copy[locale];
  const actionIcons = { website: Globe2, directions: Navigation, save: Bookmark, call: Phone, booking: CalendarDays } as const;
  const actions: GbpProfileAction[] = view.actions ?? (["website", "directions", "save", "call", "booking"] as const).map((kind) => ({ kind }));
  const reviewCount = view.reviewsCount;

  return (
    <div className="mx-auto w-full max-w-[1160px] overflow-hidden rounded-[18px] border border-slate-200 bg-white font-[Arial,sans-serif] text-[#202124] shadow-[0_12px_36px_rgba(31,35,38,0.08)] max-sm:rounded-xl">
      <PhotoStage view={view} photoWord={t.publicPhotos} draftWord={t.draft} />
      <div className="flex items-start justify-between gap-6 px-7 pb-4 pt-6 max-sm:block max-sm:px-4 max-sm:pt-5">
        <div>
          <h3 className="m-0 text-[31px] leading-[1.12] tracking-[-0.035em] text-slate-950 max-sm:text-[25px]">{view.name}</h3>
          <p className="mt-2 flex flex-wrap items-center gap-1.5 text-[14px]"><b>{view.ratingValue.toFixed(1)}</b><Stars rating={view.ratingValue} /><span className="text-blue-600">{view.reviewsCount} {t.reviewsSuffix}</span></p>
          <p className="mt-1.5 text-[13px] text-slate-500">{view.subtitle}</p>
        </div>
        {view.verified ? <span className="mt-1 inline-flex shrink-0 rounded-full bg-emerald-50 px-2.5 py-1.5 text-[10px] font-extrabold text-emerald-800 max-sm:mt-3">✓ {t.verified}</span> : null}
      </div>
      <div className="mx-7 mb-4 grid overflow-hidden rounded-xl border border-slate-200 [&>*+*]:border-l [&>*+*]:border-slate-200 max-sm:mx-4" style={{ gridTemplateColumns: `repeat(${actions.length}, minmax(0, 1fr))` }}>
        {actions.map((action) => <Action key={action.kind} icon={actionIcons[action.kind]} label={action.label ?? t.actions[action.kind]} href={action.href} />)}
      </div>
      {!view.draft ? <div className="flex flex-wrap gap-x-4 gap-y-2 border-y border-slate-200 bg-slate-50 px-7 py-3 text-[11px] font-bold text-slate-600 max-sm:px-4">
        {(["good", "warn", "bad", "open"] as GbpFieldStatus[]).map((status, index) => <span key={status} className="inline-flex items-center gap-1.5"><i className={`size-2 rounded-full ${dotStyles[status]}`} aria-hidden />{t.legend[index]}</span>)}
      </div> : <div className="border-y border-emerald-100 bg-emerald-50 px-7 py-3 text-[12px] font-bold text-emerald-900 max-sm:px-4">✓ {locale === "de" ? "Grün zeigt die vorbereiteten Änderungen" : "Green shows the prepared changes"}</div>}
      <ProfileSection label={t.businessDetails} headline={view.fieldsHeadline}>
        {view.fields.map((field, index) => <ProfileField key={`${field.label}-${index}`} field={field} prepared={view.draft} />)}
      </ProfileSection>

      {view.categories ? (
        <ProfileSection label={t.categories} headline={view.categories.headline}>
          <div className="grid grid-cols-[minmax(220px,0.8fr)_minmax(280px,1.2fr)] items-center gap-5 py-3 max-md:grid-cols-1 max-md:gap-2">
            <div><small className="mb-1 block text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">{t.primaryCategory}</small><strong className={`block text-[25px] leading-tight ${view.draft ? "text-emerald-800" : ""}`}>{view.categories.primary}</strong></div>
            {!view.draft ? <FindingNote finding={view.categories.primaryFinding} /> : null}
          </div>
          {view.categories.secondary?.length ? <div className="grid grid-cols-[minmax(220px,0.8fr)_minmax(280px,1.2fr)] items-center gap-5 border-t border-slate-100 py-3 max-md:grid-cols-1 max-md:gap-2"><div><small className="mb-2 block text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">{t.otherCategories}</small><div className="flex flex-wrap gap-1.5">{view.categories.secondary.map((category) => <span key={category} className="rounded-full bg-emerald-50 px-2.5 py-1.5 text-[13px] font-bold text-emerald-900">{category}</span>)}</div></div>{!view.draft ? <FindingNote finding={view.categories.secondaryFinding} /> : null}</div> : null}
        </ProfileSection>
      ) : null}

      {view.description ? <ProfileSection label={t.description} headline={view.description.headline}><div className="grid grid-cols-[minmax(260px,0.9fr)_minmax(280px,1.1fr)] items-center gap-5 max-md:grid-cols-1 max-md:gap-3"><p className={`m-0 text-[15px] leading-relaxed ${view.draft ? "text-emerald-900" : "text-slate-700"}`}>{view.description.text}</p>{!view.draft ? <FindingNote finding={view.description.finding} /> : null}</div></ProfileSection> : null}
      {view.services ? <ProfileSection label={t.services} headline={view.services.headline}>{view.services.items.length ? <><div className="flex flex-wrap gap-2">{view.services.items.slice(0, 8).map((service) => <span key={service} className="rounded-full bg-emerald-50 px-2.5 py-1.5 text-[13px] font-bold text-emerald-900">{service}</span>)}</div>{view.services.items.length > 8 ? <details className="mt-3 rounded-xl border border-slate-200 px-3.5 py-3 text-[14px] text-slate-700"><summary className="cursor-pointer font-bold text-blue-800">{locale === "de" ? `Alle ${view.services.items.length} Leistungen ansehen` : `View all ${view.services.items.length} services`}</summary><div className="mt-3 flex flex-wrap gap-2">{view.services.items.slice(8).map((service) => <span key={service} className="rounded-full bg-slate-100 px-2.5 py-1.5 text-[13px] font-semibold">{service}</span>)}</div></details> : null}</> : <p className="m-0 text-[15px] text-slate-600">{locale === "de" ? "Keine öffentlich lesbaren Leistungen gefunden." : "No publicly readable services were found."}</p>}{!view.draft ? <FindingNote finding={view.services.finding} className="mt-3" /> : null}</ProfileSection> : null}

      {(view.photos?.length || view.plannedPhotos?.length || view.photoFinding) ? (
        <ProfileSection label={t.photos} headline={view.photoHeadline}>
          <div className="grid grid-cols-6 gap-2 max-md:grid-cols-3 max-sm:grid-cols-2">
            {(view.photos ?? []).map((photo, index) => <figure key={`${photo.src}-proof-${index}`} className="m-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-50"><img src={photo.src} alt={photo.alt} className="h-28 w-full object-cover" />{photo.label ? <figcaption className="px-2 py-1.5 text-[9px] font-bold text-slate-600">{photo.label}</figcaption> : null}</figure>)}
            {(view.plannedPhotos ?? []).map((photo) => <div key={photo} className="grid min-h-36 place-items-center rounded-xl border border-dashed border-blue-300 bg-blue-50 p-3 text-center text-[10px] font-bold leading-snug text-blue-800"><span><b className="mb-1 block text-xl font-normal">+</b>{photo}</span></div>)}
          </div>
          <FindingNote finding={view.photoFinding} className="mt-3" />
        </ProfileSection>
      ) : null}

      {view.post ? <ProfileSection label={t.updates} headline={view.post.headline}><div className="grid grid-cols-[100px_minmax(260px,1fr)_auto_minmax(250px,0.9fr)] items-center gap-4 max-lg:grid-cols-1 max-lg:gap-2"><span className="text-[12px] font-bold text-slate-500">{view.post.date}</span><p className={`m-0 text-[14px] leading-relaxed ${view.draft ? "text-emerald-900" : "text-slate-700"}`}>{view.post.text}</p>{view.post.href ? <a href={view.post.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12px] font-bold text-blue-600 no-underline">{view.post.linkLabel ?? "Open"}<ExternalLink size={11} /></a> : null}{!view.draft ? <FindingNote finding={view.post.finding} /> : null}</div></ProfileSection> : null}

      {view.reviews || view.reviewsCount >= 0 ? (
        <ProfileSection label={t.reviews} headline={view.reviewsHeadline}>
          <div className="grid grid-cols-[72px_minmax(150px,0.6fr)_minmax(280px,1.4fr)] items-center gap-4 pb-3 max-md:grid-cols-1 max-md:gap-2"><strong className="text-[36px] leading-none">{view.ratingValue.toFixed(1)}</strong><div><Stars rating={view.ratingValue} size={16} /><small className="mt-1 block text-[10px] text-slate-500">{reviewCount} {t.reviewsSuffix}</small></div><FindingNote finding={view.reviewsFinding} /></div>
          {view.reviews?.length ? view.reviews.map((review, index) => <article key={`${review.author}-${index}`} className="border-t border-slate-100 py-4"><div className="flex flex-wrap justify-between gap-1.5"><strong className="text-[14px]">{review.author}</strong><span className="inline-flex items-center gap-1 text-[12px] text-amber-700"><Stars rating={review.rating} size={11} />{review.when}</span></div><p className="my-2 max-w-[92ch] text-[14px] leading-relaxed text-slate-700">{review.text}</p>{view.draft && review.responseAction ? <small className="inline-flex rounded-lg bg-blue-50 px-3 py-2 text-[13px] font-bold leading-relaxed text-blue-900">{review.responseAction}</small> : review.ownerResponse ? <small className="inline-flex rounded-lg bg-emerald-50 px-3 py-2 text-[13px] font-bold leading-relaxed text-emerald-900">{t.ownerResponse}: {review.ownerResponse}</small> : review.responseAction ? <small className="inline-flex rounded-lg bg-blue-50 px-3 py-2 text-[13px] font-bold leading-relaxed text-blue-900">{review.responseAction}</small> : <small className="inline-flex rounded-lg bg-red-50 px-3 py-2 text-[13px] font-bold text-red-800">{t.noOwnerResponse}</small>}</article>) : <p className="m-0 border-t border-slate-100 py-4 text-[14px] leading-relaxed text-slate-600">{locale === "de" ? "Anzahl und Bewertung sind belegt; einzelne Rezensionstexte waren in der gespeicherten Quelle nicht enthalten." : "The rating and review count are evidenced; individual review text was not included in the stored source."}</p>}
        </ProfileSection>
      ) : null}

      {view.additionalFields?.length ? <ProfileSection label={t.additional} headline={view.additionalHeadline}>{view.additionalFields.map((field, index) => <ProfileField key={`${field.label}-additional-${index}`} field={field} prepared={view.draft} />)}</ProfileSection> : null}
    </div>
  );
}

const auditStatusRank: Record<GbpFieldStatus, number> = { good: 0, open: 1, warn: 2, new: 2, bad: 3 };

function strongestFinding(findings: GbpInlineFinding[]) {
  return findings.reduce((strongest, finding) => auditStatusRank[finding.status] > auditStatusRank[strongest.status] ? finding : strongest);
}

function AuditIcon({ finding, locale }: { finding: GbpInlineFinding; locale: "en" | "de" }) {
  const status = finding.status === "new" ? "warn" : finding.status;
  const config = {
    good: { icon: Check, label: locale === "de" ? "Passt" : "Good", styles: "border-emerald-200 bg-emerald-50 text-emerald-700" },
    warn: { icon: AlertTriangle, label: locale === "de" ? "Verbessern" : "Improve", styles: "border-amber-200 bg-amber-50 text-amber-700" },
    bad: { icon: X, label: locale === "de" ? "Fehlt" : "Missing", styles: "border-red-200 bg-red-50 text-red-700" },
    open: { icon: CircleHelp, label: locale === "de" ? "Prüfen" : "Check", styles: "border-slate-200 bg-slate-50 text-slate-600" },
  }[status];
  const Icon = config.icon;
  return <span className={`grid size-10 place-items-center rounded-full border max-md:size-9 ${config.styles}`} aria-label={config.label} title={config.label}><Icon className="size-5" strokeWidth={2.5} aria-hidden /></span>;
}

function AuditRow({ label, current, recommendation, finding, locale }: { label: string; current: ReactNode; recommendation: ReactNode; finding: GbpInlineFinding; locale: "en" | "de" }) {
  const statusLabel = finding.status === "good"
    ? (locale === "de" ? "Passt" : "Good")
    : finding.status === "bad"
      ? (locale === "de" ? "Fehlt" : "Missing")
      : finding.status === "open"
        ? (locale === "de" ? "Prüfen" : "Check")
        : (locale === "de" ? "Verbessern" : "Improve");
  return (
    <details className="group border-t border-slate-200 bg-white first:border-t-0">
      <summary className="grid cursor-pointer list-none grid-cols-[38px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3.5 md:grid-cols-[42px_minmax(150px,.48fr)_minmax(0,1.52fr)_auto] md:px-5 md:py-4 [&::-webkit-details-marker]:hidden">
        <AuditIcon finding={finding} locale={locale} />
        <span><strong className="block text-[15px] leading-tight text-slate-950">{label}</strong><small className={`mt-1 block text-[10px] font-extrabold uppercase tracking-[.05em] ${finding.status === "good" ? "text-emerald-700" : finding.status === "open" ? "text-slate-500" : "text-amber-700"}`}>{statusLabel}</small></span>
        <div className={`col-start-2 min-w-0 text-[13px] font-bold leading-[1.4] md:col-start-3 md:text-[14px] ${finding.status === "good" ? "text-emerald-800" : finding.status === "open" ? "text-slate-600" : "text-slate-950"}`}>{recommendation}</div>
        <ChevronDown className="col-start-3 row-start-1 size-5 text-blue-700 transition-transform group-open:rotate-180 md:col-start-4" aria-hidden />
      </summary>
      <div className="border-t border-slate-100 bg-slate-50 px-4 py-4 pl-[65px] md:px-5 md:pl-[227px]">
        <span className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[.07em] text-slate-400">{copy[locale].currentSnapshot}</span>
        <div className="text-[14px] font-semibold leading-[1.5] text-slate-600">{current}</div>
      </div>
    </details>
  );
}

function CurrentValues({ items, disclosureLabel }: { items: { label: string; value: string }[]; disclosureLabel?: string }) {
  const values = (
    <dl className="m-0 grid gap-1.5">
      {items.map((item) => <div key={`${item.label}-${item.value}`} className="grid grid-cols-[88px_minmax(0,1fr)] gap-2"><dt className="text-[11px] font-extrabold uppercase tracking-[.04em] text-slate-400">{item.label}</dt><dd className="m-0 break-words text-slate-700">{item.value}</dd></div>)}
    </dl>
  );
  if (!disclosureLabel) return values;
  return <details><summary className="cursor-pointer font-bold text-blue-800">{disclosureLabel}</summary><div className="mt-3">{values}</div></details>;
}

function Recommendation({ finding, goodText }: { finding: GbpInlineFinding; goodText: string }) {
  const genericGood = /^(no change needed|keine änderung nötig)\.?$/i.test(finding.text.trim());
  return <p className="m-0">{finding.status === "good" ? (genericGood ? goodText : finding.text) : finding.text}</p>;
}

function displayDate(value: string, locale: "en" | "de") {
  if (!value.includes("T")) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "de" ? "de-DE" : "en-GB", { day: "numeric", month: "long", year: "numeric" }).format(date);
}

function IntegratedProfileView({
  current,
  auditRows,
  locale,
}: {
  current: GbpProfileView;
  prepared: GbpProfileView;
  auditRows?: GbpAuditRow[];
  locale: "en" | "de";
}) {
  const t = copy[locale];
  const rawCategoryFinding = evidenceFinding({
    explicit: current.categories?.secondaryFinding ?? current.categories?.primaryFinding,
    rows: auditRows,
    aliases: ["categories", "category", "kategorien", "kategorie"],
    locale,
  });
  const categoryFinding = rawCategoryFinding;
  const descriptionFinding = evidenceFinding({ explicit: current.description?.finding, rows: auditRows, aliases: ["description", "beschreibung"], locale });
  const servicesFinding = evidenceFinding({ explicit: current.services?.finding, rows: auditRows, aliases: ["services", "service", "leistungen", "leistung"], locale });
  const photoFinding = evidenceFinding({ explicit: current.photoFinding, rows: auditRows, aliases: ["photos", "photo", "fotos", "bilder"], locale });
  const postFinding = evidenceFinding({ explicit: current.post?.finding, rows: auditRows, aliases: ["updates", "posts", "beiträge", "aktuelles"], locale });
  const reviewsFinding = evidenceFinding({ explicit: current.reviewsFinding, rows: auditRows, aliases: ["reviews", "review", "bewertungen", "rezensionen"], locale });
  const phoneFirstBusiness = /emergency|locksmith|notdienst|schlüsseldienst/i.test(`${current.subtitle} ${current.categories?.primary ?? ""}`);
  const businessFieldFindings = current.fields.map((field) => {
    const bookingWithoutLink = /booking|termin/i.test(field.label) && /no booking|kein termin/i.test(field.value);
    const explicit = phoneFirstBusiness && bookingWithoutLink ? {
      status: "good" as const,
      label: locale === "de" ? "Passt" : "Good",
      text: locale === "de" ? "Der Anruf ist für dringende Hilfe der passende Hauptweg." : "Calling is the right primary route for urgent work.",
    } : field.finding;
    return { field, finding: evidenceFinding({ explicit, rows: auditRows, aliases: [field.label], locale }) };
  });
  const businessIssues = businessFieldFindings.filter(({ finding }) => finding.status !== "good");
  const businessFinding = businessIssues.length ? strongestFinding(businessIssues.map(({ finding }) => finding)) : {
    status: "good" as const,
    label: locale === "de" ? "Passt" : "Good",
    text: locale === "de" ? "Kontaktangaben und Öffnungszeiten sind veröffentlicht." : "Contact details and opening hours are published.",
  };
  const noPublicValue = locale === "de" ? "Nicht öffentlich gefunden" : "Not found publicly";
  const secondaryCategories = current.categories?.secondary ?? [];
  const services = current.services?.items ?? [];
  const visibleAdditionalFields = (current.additionalFields ?? []).filter((field) => !/^(available|unavailable)_attributes$/i.test(field.label));
  const normalizedAdditionalFields: GbpProfileField[] = visibleAdditionalFields.length ? visibleAdditionalFields : [{
    label: locale === "de" ? "Attribute" : "Attributes",
    value: locale === "de" ? "Öffentlich nicht vollständig sichtbar" : "Not fully visible publicly",
    icon: "info" as const,
  }];
  const additionalFindings = normalizedAdditionalFields.map((field) => evidenceFinding({ explicit: field.finding, rows: auditRows, aliases: [field.label], locale }));
  const additionalFinding = additionalFindings.length ? strongestFinding(additionalFindings) : evidenceFinding({ rows: auditRows, aliases: ["attributes", "details", "attribute", "angaben"], locale });
  const sections = [
    {
      label: t.businessDetails,
      finding: businessFinding,
      current: <CurrentValues disclosureLabel={locale === "de" ? "Adresse, Zeiten und Kontakt ansehen" : "View address, hours and contact details"} items={current.fields.map((field) => ({ label: field.label, value: field.value }))} />,
      recommendation: businessIssues.length ? <ul className="m-0 grid list-none gap-1.5 p-0">{businessIssues.map(({ field, finding }) => <li key={field.label}><strong>{field.label}:</strong> {finding.text}</li>)}</ul> : <Recommendation finding={businessFinding} goodText={businessFinding.text} />,
    },
    {
      label: t.categories,
      finding: categoryFinding,
      current: <CurrentValues items={[{ label: t.primaryCategory, value: current.categories?.primary ?? noPublicValue }, { label: t.otherCategories, value: secondaryCategories.length ? secondaryCategories.join(" · ") : noPublicValue }]} />,
      recommendation: <Recommendation finding={categoryFinding} goodText={locale === "de" ? "Die Kategorien passen zu den Leistungen, die Kunden buchen können." : "The categories match the services customers can book."} />,
    },
    {
      label: t.description,
      finding: descriptionFinding,
      current: current.description?.text ? <details><summary className="cursor-pointer font-bold text-slate-800">{current.description.text.slice(0, 150)}{current.description.text.length > 150 ? "…" : ""}</summary>{current.description.text.length > 150 ? <p className="mb-0 mt-2 font-normal">{current.description.text}</p> : null}</details> : noPublicValue,
      recommendation: <Recommendation finding={descriptionFinding} goodText={locale === "de" ? "Leistung und Einzugsgebiet sind klar." : "The service and area are clear."} />,
    },
    {
      label: t.services,
      finding: servicesFinding,
      current: services.length ? <details><summary className="cursor-pointer font-bold text-slate-800">{services.length} {locale === "de" ? "Leistungen eingetragen" : "services listed"}</summary><p className="mb-0 mt-2 font-normal">{services.join(" · ")}</p></details> : (locale === "de" ? "Keine öffentlichen Leistungen eingetragen." : "No public services are listed."),
      recommendation: <Recommendation finding={servicesFinding} goodText={locale === "de" ? "Kunden sehen, was sie buchen können." : "Customers can see what they can book."} />,
    },
    {
      label: t.photos,
      finding: photoFinding,
      current: <div><p className="m-0">{current.photoLabel ?? `${current.photos?.length ?? 0} ${t.publicPhotos}`}</p>{current.photos?.length ? <div className="mt-2 flex gap-1.5">{current.photos.slice(0, 3).map((photo, index) => <img key={`${photo.src}-${index}`} src={photo.src} alt={photo.alt} className="size-12 rounded-lg border border-slate-200 object-cover" />)}</div> : null}</div>,
      recommendation: <Recommendation finding={photoFinding} goodText={locale === "de" ? "Echte Fotos zeigen den Betrieb bei der Arbeit." : "Real photos show the business at work."} />,
    },
    {
      label: t.updates,
      finding: postFinding,
      current: current.post ? <details><summary className="cursor-pointer font-bold text-slate-800">{displayDate(current.post.date, locale)}</summary><p className="mb-0 mt-2 font-normal">{current.post.text}</p></details> : noPublicValue,
      recommendation: <Recommendation finding={postFinding} goodText={locale === "de" ? "Das Profil zeigt einen aktuellen Beitrag." : "The profile has a recent update."} />,
    },
    {
      label: t.reviews,
      finding: reviewsFinding,
      current: <div><p className="m-0"><strong>{current.ratingValue.toFixed(1)}</strong> <Stars rating={current.ratingValue} size={12} /> · {current.reviewsCount} {t.reviewsSuffix}</p>{current.reviews?.length ? <details className="mt-2"><summary className="cursor-pointer font-bold text-slate-800">{locale === "de" ? "Rezensionen und Antworten ansehen" : "View reviews and replies"}</summary><div className="mt-2 grid gap-2">{current.reviews.slice(0, 3).map((review, index) => <div key={`${review.author}-${index}`} className="rounded-lg bg-slate-50 p-2.5"><strong className="block text-[12px] text-slate-900">{review.author}</strong><p className="my-1 text-[12px] font-normal">{review.text}</p><small className={review.ownerResponse ? "text-emerald-800" : "text-red-700"}>{review.ownerResponse ? `${t.ownerResponse}: ${review.ownerResponse}` : t.noOwnerResponse}</small></div>)}</div></details> : null}</div>,
      recommendation: <Recommendation finding={reviewsFinding} goodText={locale === "de" ? "Bewertung und Antworten schaffen Vertrauen." : "The rating and replies build trust."} />,
    },
    {
      label: t.additional,
      finding: additionalFinding,
      current: <CurrentValues items={normalizedAdditionalFields.map((field) => ({ label: field.label, value: field.value }))} />,
      recommendation: <Recommendation finding={additionalFinding} goodText={locale === "de" ? "Die geprüften Angaben sind vollständig." : "The checked details are complete."} />,
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1160px] overflow-hidden rounded-[18px] border border-slate-200 bg-white font-[Arial,sans-serif] text-[#202124] shadow-[0_12px_36px_rgba(31,35,38,0.08)] max-sm:rounded-xl">
      <PhotoStage view={current} photoWord={t.publicPhotos} draftWord={t.draft} compact />
      <div className="flex items-start justify-between gap-6 px-6 py-5 max-sm:block max-sm:px-4 max-sm:py-4">
        <div>
          <span className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.09em] text-blue-700">{t.profileAudit}</span>
          <h3 className="m-0 text-[27px] leading-[1.12] tracking-[-0.035em] text-slate-950 max-sm:text-[23px]">{current.name}</h3>
          <p className="mt-2 flex flex-wrap items-center gap-1.5 text-[14px]"><b>{current.ratingValue.toFixed(1)}</b><Stars rating={current.ratingValue} /><span className="text-blue-600">{current.reviewsCount} {t.reviewsSuffix}</span></p>
          <p className="mt-1.5 text-[13px] text-slate-500">{current.subtitle}</p>
        </div>
        {current.verified ? <span className="mt-1 inline-flex shrink-0 rounded-full bg-emerald-50 px-2.5 py-1.5 text-[10px] font-extrabold text-emerald-800 max-sm:mt-3">✓ {t.verified}</span> : null}
      </div>
      <div className="border-y border-slate-200 bg-slate-50">
        {sections.map((section) => <AuditRow key={section.label} {...section} locale={locale} />)}
      </div>
    </div>
  );
}

/** Reusable, bilingual Business Profile audit. English is the default. */
export function GbpPanel({ data, requireComplete = false, icons = defaultIcons }: { data: GbpExhibit; requireComplete?: boolean; icons?: ProfileIcons }) {
  const locale = data.locale ?? "en";
  const t = copy[locale];
  const legacy = useMemo(() => legacyView(data), [data]);
  const current = requireComplete ? data.current : (data.current ?? legacy);
  const prepared = data.prepared;
  if (!current || (requireComplete && !prepared)) {
    return <div role="alert" className="rounded-[18px] border border-red-200 bg-red-50 px-5 py-6 text-[14px] font-bold text-red-950">{locale === "de" ? "Der vollständige aktuelle und vorbereitete Profil-Datensatz fehlt. Dieser Bericht darf noch nicht freigegeben werden." : "The complete current and prepared profile evidence is missing. This report is not ready for release."}</div>;
  }

  return (
    <ProfileIconContext.Provider value={icons}><div className="m-0">
      {!prepared ? <div className="rounded-t-[18px] border border-b-0 border-slate-200 bg-white px-6 py-4 max-sm:px-4"><strong className="block text-[18px] tracking-[-0.02em] text-slate-950">{t.title}</strong><span className="mt-1 block text-[12px] leading-snug text-slate-500">{t.subtitle}</span></div> : null}
      {prepared ? <IntegratedProfileView current={current} prepared={prepared} auditRows={data.auditRows} locale={locale} /> : <ProfileView view={current} locale={locale} />}
      {data.note ? <p style={{ color: d.faint }} className="mt-3 text-[14px] leading-relaxed">{data.note}</p> : null}
    </div></ProfileIconContext.Provider>
  );
}

/** Legacy export retained for old layouts. New proposals do not use a ghost. */
export function GbpGhost({ data }: { data: GbpExhibit }) {
  return <div className="grid min-h-40 place-items-center rounded-2xl border-2 border-dashed border-stone-300 bg-stone-50 p-6 text-center"><div><p className="m-0 text-xl text-stone-600">{data.clientName ?? "Business Profile"}</p><p className="mt-2 text-sm text-red-700">{data.clientGhost ?? "No public profile data available"}</p></div></div>;
}
