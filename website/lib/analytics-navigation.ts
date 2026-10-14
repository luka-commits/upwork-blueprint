// Analytics evidence opens an exact lead set, including closed and skipped leads.
export const ANALYTICS_LEADS_PARAM = 'analytics_leads';
const RETURN_KEY = 'cockpit-analytics-return';
const HISTORY_KEY = 'cockpitAnalyticsReturn';

export type AnalyticsReturn = { tab: number; scrollY: number; openDetails?: number[] };

export function analyticsLeadsHref(ids: (string | number)[]): string {
  const unique = [...new Set(ids.map(String))];
  return `/?${new URLSearchParams({ [ANALYTICS_LEADS_PARAM]: JSON.stringify(unique) })}`;
}

export function analyticsLeadIds(value: string | null): string[] | null {
  if (value === null) return null;
  try {
    const ids = JSON.parse(value);
    if (Array.isArray(ids) && ids.every(id => typeof id === 'string' || typeof id === 'number')) {
      return [...new Set(ids.map(String))];
    }
  } catch { /* A malformed evidence link must never show unrelated leads. */ }
  return [];
}

export function rememberAnalyticsReturn(tab: number): void {
  if (typeof window === 'undefined') return;
  const openDetails = Array.from(document.querySelectorAll<HTMLDetailsElement>('.an-shell details'))
    .flatMap((detail,index) => detail.open ? [index] : []);
  const position: AnalyticsReturn = { tab, scrollY: window.scrollY, openDetails };
  window.history.replaceState({ ...window.history.state, [HISTORY_KEY]: position }, '', window.location.href);
  try { window.sessionStorage.setItem(RETURN_KEY, JSON.stringify(position)); } catch { /* History still preserves Back. */ }
}

export function readAnalyticsReturn(): AnalyticsReturn | null {
  if (typeof window === 'undefined') return null;
  let position = window.history.state?.[HISTORY_KEY];
  if (!position) {
    try { position = JSON.parse(window.sessionStorage.getItem(RETURN_KEY) || 'null'); } catch { return null; }
  }
  return position && Number.isInteger(position.tab) && position.tab >= 0 && position.tab <= 2
    && Number.isFinite(position.scrollY) && position.scrollY >= 0
    && (position.openDetails === undefined || Array.isArray(position.openDetails)
      && position.openDetails.every(index => Number.isInteger(index) && index >= 0)) ? position : null;
}

export function restoreAnalyticsReturnScroll(): void {
  const position = readAnalyticsReturn();
  if (!position) return;
  // Wait for the restored tab's layout before the browser returns to its evidence row.
  window.requestAnimationFrame(() => {
    if (position.openDetails) {
      const opened = new Set(position.openDetails);
      document.querySelectorAll<HTMLDetailsElement>('.an-shell details').forEach((detail,index) => {
        detail.open = opened.has(index);
      });
    }
    window.requestAnimationFrame(() => window.scrollTo({ top: position.scrollY, behavior: 'instant' }));
  });
}
