'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type CSSProperties, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Drawer from '@/components/Drawer';
import { CockpitContext, type CockpitApi, type State } from '@/lib/context';
import { revealContent } from '@/lib/surface-motion.mjs';

const CONNECTION_LOST = 'The cockpit lost its connection. Start it again with /dashboard, then reload.';

function syncText(syncedAt?: string) {
  if (!syncedAt) return { text: 'never synced with Upwork', stale: true };
  const minutes = Math.max(0, Math.round((Date.now() - +new Date(syncedAt)) / 60000));
  const text = minutes < 1 ? 'synced just now' : minutes < 60 ? `synced ${minutes} min ago`
    : minutes < 1440 ? `synced ${Math.round(minutes / 60)} h ago` : `synced ${Math.round(minutes / 1440)} d ago`;
  return { text, stale: minutes > 1440 };
}

export function CockpitProvider({ token, children }: { token: string; children: ReactNode }) {
  const pathname = usePathname();
  const [state, setState] = useState<State | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVisible, setToastVisible] = useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pageRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const animation = revealContent(pageRef.current);
    return () => animation?.cancel();
  }, [pathname]);

  useEffect(() => {
    // Pointer feedback stays tactile. Keyboard navigation is immediate.
    const keyboard = () => { document.documentElement.dataset.input = 'keyboard'; };
    const pointer = () => { document.documentElement.dataset.input = 'pointer'; };
    document.addEventListener('keydown', keyboard, true);
    document.addEventListener('pointerdown', pointer, true);
    return () => {
      document.removeEventListener('keydown', keyboard, true);
      document.removeEventListener('pointerdown', pointer, true);
      delete document.documentElement.dataset.input;
    };
  }, []);

  const toast = useCallback((message: string) => {
    setToastMessage(message);
    setToastVisible(true);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToastVisible(false), 2800);
  }, []);

  const api = useCallback<CockpitApi['api']>(async path => {
    try {
      const response = await fetch(path, { headers: { 'X-Cockpit-Token': token } });
      return { ok: response.ok, data: await response.json().catch(() => ({})) };
    } catch {
      return { ok: false, data: {} };
    }
  }, [token]);

  const load = useCallback(async () => {
    const result = await api('/api/state');
    if (!result.ok) { setConnectionLost(true); return; }
    setState(result.data);
    setConnectionLost(false);
  }, [api]);

  const openDrawer = useCallback((id: string) => setDrawerId(id), []);
  const closeDrawer = useCallback(() => setDrawerId(null), []);

  useEffect(() => {
    void load();
    // Commands run in Claude Code and write the files; the poll brings their changes in.
    const poll = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 15000);
    return () => window.clearInterval(poll);
  }, [load]);

  useEffect(() => { if (pathname !== '/') setDrawerId(null); }, [pathname]);
  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); }, []);

  const value = useMemo<CockpitApi>(() => ({
    token, state, load, api, toast, drawerId, openDrawer, closeDrawer,
  }), [api, closeDrawer, drawerId, load, openDrawer, state, toast, token]);

  const sync = syncText(state?.sync?.synced_at);
  const tracker = state?.tracker || {};
  return (
    <CockpitContext.Provider value={value}>
      <header className="top">
        <div className="top-inner">
          <span className="brand"><img src="/icon.svg" width="30" height="30" alt="" />Automatable Cockpit</span>
          <nav className="tabs" aria-label="Sections" style={{ '--section-index': Number(pathname === '/analytics') } as CSSProperties}>
            <Link href="/" aria-current={pathname === '/' ? 'page' : undefined}>Leads</Link>
            <Link href="/analytics" aria-current={pathname === '/analytics' ? 'page' : undefined}>Analytics</Link>
          </nav>
          {tracker.goal ? <div className="top-progress">
            <span>Applications today</span>
            <strong aria-label={`${tracker.done} of ${tracker.goal} applications today`}>{tracker.done}<small>/ {tracker.goal}</small></strong>
            <i role="progressbar" aria-label="Daily application target" aria-valuemin={0} aria-valuemax={tracker.goal}
              aria-valuenow={Math.min(tracker.goal, tracker.done)}><span style={{ width: `${Math.min(100, 100 * tracker.done / tracker.goal)}%` }} /></i>
          </div> : null}
          <div className="top-actions">
            <span className={`stamp sync-stamp${sync.stale ? ' stale' : ''}`}>{sync.text}</span>
          </div>
        </div>
      </header>
      <main className="wrap list-wrap" ref={pageRef}>
        {connectionLost ? <div className="empty-state" role="alert"><strong>Connection lost</strong><p>{CONNECTION_LOST}</p><button onClick={() => void load()}>Try again</button></div>
          : state ? children : <p className="empty" role="status">Loading cockpit.</p>}
      </main>
      <Drawer />
      <div className={`toast${toastVisible ? ' show' : ''}`} role="status">{toastMessage}</div>
    </CockpitContext.Provider>
  );
}
