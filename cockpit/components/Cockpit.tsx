'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type CSSProperties, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Drawer from '@/components/Drawer';
import RunsDock, { runTitle } from '@/components/RunsDock';
import { CockpitContext, type CockpitApi, type Made, type Run, type State } from '@/lib/context';
import { FILE_LABEL, TOOL_WORDS, todoBucket } from '@/lib/model';
import { followRunStream, RECONNECTING_RUN, RUN_TRACKING_LOST } from '@/lib/run-stream.mjs';
import { revealContent, sectionIndex } from '@/lib/surface-motion.mjs';

type Snapshot = { jobs: Set<string>; files: Set<string> };
type RunMeta = { before: Snapshot | null; narrated: boolean; controller: AbortController };
type StreamEvent = { kind: string; text?: string; detail?: string; error?: boolean; stopped?: boolean };

const STARTING = 'Starting Claude. You can keep working, this runs on its own.';
const CONNECTION_LOST = 'The cockpit lost its connection. Start it again with /cockpit, then reload.';
const DOCK_OPEN_EVENT = 'cockpit-dock-open';

function lastLine(text: string) {
  return (String(text).split('\n').map(line => line.replace(/^[#>*\-\s|]+|[*_`|]+/g, '').trim()).filter(Boolean).pop() || '').slice(0, 160);
}

function snapshot(state: State | null, job: string | null): Snapshot {
  const jobs = state?.jobs || [];
  return {
    jobs: new Set(jobs.map((item: any) => item.id)),
    files: new Set((jobs.find((item: any) => item.id === job) || {}).artifacts || []),
  };
}

function deliverables(run: Run, before: Snapshot | null, state: State | null): Made[] {
  if (!before || !state) return [];
  if (run.command === 'find-jobs') {
    const fresh = (state.jobs || []).filter((job: any) => !before.jobs.has(job.id))
      .sort((a: any, b: any) => (b.score || 0) - (a.score || 0));
    if (!fresh.length) return [{ label: 'No new jobs this time' }];
    const best = fresh[0];
    return [{ label: `${fresh.length} new job${fresh.length > 1 ? 's' : ''}, best: ${best.title} (${best.score ?? '?'})`, open: best.id }];
  }
  const job = (state.jobs || []).find((item: any) => item.id === run.job) || {};
  return (job.artifacts || []).filter((file: string) => !before.files.has(file)).map((file: string) => ({
    label: `${FILE_LABEL[file] || file} ready`,
    href: `/files/${run.job}/${file}`,
  }));
}

export function CockpitProvider({ token, children }: { token: string; children: ReactNode }) {
  const pathname = usePathname();
  const [state, setState] = useState<State | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVisible, setToastVisible] = useState(false);
  const stateRef = useRef<State | null>(null);
  const runsRef = useRef(new Map<string, Run>());
  const runMetaRef = useRef(new Map<string, RunMeta>());
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notificationAskedRef = useRef(false);
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

  const publishRuns = useCallback(() => setRuns([...runsRef.current.values()]), []);

  const toast = useCallback((message: string) => {
    setToastMessage(message);
    setToastVisible(true);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToastVisible(false), 2800);
  }, []);

  const api = useCallback<CockpitApi['api']>(async (path, body) => {
    try {
      const response = await fetch(path, {
        method: body ? 'POST' : 'GET',
        headers: { 'X-Cockpit-Token': token, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      return { ok: response.ok, data: await response.json().catch(() => ({})) };
    } catch {
      return { ok: false, data: {} };
    }
  }, [token]);

  const load = useCallback(async () => {
    const result = await api('/api/state');
    if (!result.ok) {
      setConnectionLost(true);
      return;
    }
    stateRef.current = result.data;
    setState(result.data);
    setConnectionLost(false);
  }, [api]);

  const post = useCallback<CockpitApi['post']>(async (path, body) => {
    const result = await api(path, body);
    toast(result.ok ? result.data.message : (result.data.error || result.data.message || 'That did not work.'));
    await load();
    return result.ok;
  }, [api, load, toast]);

  const move = useCallback<CockpitApi['move']>((id, status, follow, note) => {
    const currentStatus = stateRef.current?.jobs?.find((job: any) => job.id === id)?.status;
    if (status === 'won' && currentStatus !== 'won') {
      const confirmed = window.confirm('Has the Upwork contract started? Only mark Won after it has.');
      if (!confirmed) return Promise.resolve(false);
    }
    const body: Record<string, string | boolean> = { id, status };
    if (status === 'won' && currentStatus !== 'won') body.contract_started = true;
    if (follow != null) body.follow_up = follow;
    if (note != null) body.note = note;
    return post('/api/status', body);
  }, [post]);

  const openDrawer = useCallback((id: string) => setDrawerId(id), []);
  const closeDrawer = useCallback(() => setDrawerId(null), []);

  const notify = useCallback((title: string, body: string) => {
    toast(`${title}: ${body}`);
    try {
      if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body });
      }
    } catch {
      // The run still finishes when notifications are unavailable.
    }
  }, [toast]);

  const attachRun = useCallback((id: string, command: string, job: string | null, started?: number, replay = false) => {
    if (runsRef.current.has(id)) return;
    const controller = new AbortController();
    const run: Run = {
      id,
      command,
      job,
      t0: started ? started * 1000 : Date.now(),
      status: STARTING,
      log: [],
      done: false,
      replay,
      made: [],
    };
    runsRef.current.set(id, run);
    runMetaRef.current.set(id, { before: replay ? null : snapshot(stateRef.current, job), narrated: false, controller });
    publishRuns();

    const update = (change: (current: Run) => Run) => {
      const current = runsRef.current.get(id);
      if (!current) return null;
      const next = change(current);
      runsRef.current.set(id, next);
      publishRuns();
      return next;
    };

    const onEvent = async (event: StreamEvent) => {
      const meta = runMetaRef.current.get(id);
      if (!meta) return;
      if (event.kind === 'status') {
        update(current => current.log.length ? current : { ...current, status: 'Thinking about the plan.' });
      } else if (event.kind === 'tool') {
        const name = event.text || '';
        const word = TOOL_WORDS[name] || name.replace(/^mcp__upwork__upwork__/, 'Upwork: ');
        const text = `→ ${word}${event.detail ? ` · ${event.detail.slice(0, 90)}` : ''}`;
        update(current => ({
          ...current,
          status: meta.narrated ? current.status : `${word}.`,
          log: [...current.log, { kind: 'tool', text }],
        }));
      } else if (event.kind === 'text') {
        const text = event.text || '';
        const line = lastLine(text);
        if (line) meta.narrated = true;
        update(current => ({
          ...current,
          status: line || current.status,
          log: [...current.log, { kind: 'text', text }],
        }));
      } else if (event.kind === 'error') {
        update(current => ({ ...current, log: [...current.log, { kind: 'error', text: event.text || '' }] }));
      } else if (event.kind === 'done') {
        const finished = update(current => ({
          ...current,
          done: true,
          error: !!event.error,
          stopped: !!event.stopped,
          t1: current.t1 || Date.now(),
          result: event.text || '',
          showResult: true,
          status: event.stopped ? 'Stopped by you. Anything it already saved stays.'
            : event.error ? 'Failed. Show steps to see why.'
              : lastLine(event.text || '') || 'Finished.',
          log: [...current.log, { kind: event.error ? 'error' : 'done', text: event.text || '' }],
        }));
        if (!finished || finished.replay) return;
        await load();
        const made = finished.error ? [] : deliverables(finished, meta.before, stateRef.current);
        const completed = update(current => ({ ...current, made }));
        if (completed && !completed.stopped) {
          const title = completed.error ? `${runTitle(completed, stateRef.current)} failed` : `${runTitle(completed, stateRef.current)} is done`;
          const body = completed.error ? 'Open Runs to see why.' : (made.map(item => item.label).join(', ') || completed.status);
          notify(title, body);
        }
      }
    };

    void followRunStream({
      signal: controller.signal,
      openStream: signal => fetch(`/api/run/${id}`, {
        headers: { 'X-Cockpit-Token': token },
        signal,
      }),
      inspectRun: async signal => {
        const response = await fetch('/api/runs', {
          headers: { 'X-Cockpit-Token': token },
          signal,
        });
        if (!response.ok) return null;
        const items = await response.json().catch(() => null);
        return Array.isArray(items) ? items.some(item => item?.id === id) : null;
      },
      onEvent,
      onReconnect: () => update(current => current.done ? current : { ...current, status: RECONNECTING_RUN }),
      onLost: () => update(current => ({
        ...current,
        done: true,
        error: true,
        t1: current.t1 || Date.now(),
        status: RUN_TRACKING_LOST,
        log: [...current.log, { kind: 'error', text: RUN_TRACKING_LOST }],
      })),
    });
  }, [load, notify, publishRuns, token]);

  const runCommand = useCallback<CockpitApi['runCommand']>((command, job = null) => {
    if (!notificationAskedRef.current) {
      notificationAskedRef.current = true;
      try {
        if ('Notification' in window && Notification.permission === 'default') void Notification.requestPermission();
      } catch {
        // Notifications are optional.
      }
    }
    try { localStorage.setItem('dock-collapsed', JSON.stringify(false)); } catch { /* Storage is optional. */ }
    window.dispatchEvent(new Event(DOCK_OPEN_EVENT));
    void api('/api/run', { command, job }).then(result => {
      if (!result.ok) return toast(result.data.error || 'Could not start it.');
      attachRun(result.data.run, command, job);
    });
  }, [api, attachRun, toast]);

  const sendReply = useCallback<CockpitApi['sendReply']>((job, text, draft, draftSet) => {
    try { localStorage.setItem('dock-collapsed', JSON.stringify(false)); } catch { /* Storage is optional. */ }
    window.dispatchEvent(new Event(DOCK_OPEN_EVENT));
    void api('/api/reply/send', { job, text, draft, draft_set: draftSet }).then(result => {
      if (!result.ok) return toast(result.data.error || 'Could not send it.');
      attachRun(result.data.run, 'send-reply', job);
    });
  }, [api, attachRun, toast]);

  const stopRun = useCallback<CockpitApi['stopRun']>((id) => {
    void api(`/api/run/${id}/stop`, {}).then(result => {
      if (!result.ok) toast(result.data.message || 'Could not stop it.');
    });
  }, [api, toast]);

  const dismissRun = useCallback((id: string) => {
    runsRef.current.delete(id);
    runMetaRef.current.get(id)?.controller.abort();
    runMetaRef.current.delete(id);
    publishRuns();
  }, [publishRuns]);

  const toggleRunLog = useCallback((id: string) => {
    const run = runsRef.current.get(id);
    if (!run) return;
    runsRef.current.set(id, { ...run, showLog: !run.showLog });
    publishRuns();
  }, [publishRuns]);

  const toggleRunResult = useCallback((id: string) => {
    const run = runsRef.current.get(id);
    if (!run) return;
    runsRef.current.set(id, { ...run, showResult: !run.showResult });
    publishRuns();
  }, [publishRuns]);

  useEffect(() => {
    let active = true;
    void load().then(async () => {
      if (!active) return;
      const result = await api('/api/runs');
      if (!active || !result.ok || !Array.isArray(result.data)) return;
      result.data.forEach((item: any) => attachRun(item.id, item.command, item.job, item.started, item.done));
    });
    const poll = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 15000);
    return () => {
      active = false;
      window.clearInterval(poll);
    };
  }, [api, attachRun, load]);

  useEffect(() => {
    if (pathname.startsWith('/job/')) setDrawerId(null);
  }, [pathname]);

  useEffect(() => {
    document.body.classList.toggle('drawer-open', !!drawerId);
    return () => document.body.classList.remove('drawer-open');
  }, [drawerId]);

  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    runMetaRef.current.forEach(meta => meta.controller.abort());
  }, []);

  const value = useMemo<CockpitApi>(() => ({
    token,
    state,
    load,
    api,
    post,
    move,
    toast,
    drawerId,
    openDrawer,
    closeDrawer,
    runCommand,
    sendReply,
    runs,
    stopRun,
    dismissRun,
    toggleRunLog,
    toggleRunResult,
  }), [api, closeDrawer, dismissRun, drawerId, load, move, openDrawer, post, runCommand, runs, sendReply, state, stopRun, toast, token, toggleRunLog, toggleRunResult]);

  const jobs = state?.jobs || [];
  const due = state ? jobs.filter((job: any) => todoBucket(job) === 'Due now').length : 0;
  // How fresh the list is against Upwork. The poll re-renders often enough to keep the minutes honest.
  const syncedAt = state?.sync?.synced_at;
  const syncMinutes = syncedAt ? Math.max(0, Math.round((Date.now() - +new Date(syncedAt)) / 60000)) : null;
  const syncText = syncMinutes == null ? 'never synced with Upwork'
    : syncMinutes < 1 ? 'synced just now' : syncMinutes < 60 ? `synced ${syncMinutes} min ago`
      : syncMinutes < 1440 ? `synced ${Math.round(syncMinutes / 60)} h ago` : `synced ${Math.round(syncMinutes / 1440)} d ago`;
  const syncing = runs.some(run => run.command === 'sync' && !run.done);

  return (
    <CockpitContext.Provider value={value}>
      <header className={`top${pathname.startsWith('/job/') ? ' sticky' : ''}`}>
        <div className="top-inner">
          <span className="brand"><img src="/icon.png" width="30" height="30" alt="" />Automatable Cockpit</span>
          <nav className="tabs" aria-label="Sections" style={{ '--section-index': sectionIndex(pathname) } as CSSProperties}>
            <Link href="/" aria-current={pathname === '/' ? 'page' : pathname.startsWith('/job/') || pathname === '/follow-ups' ? 'location' : undefined}>Leads{due ? <span className="badge" title="Due today or earlier">{due}</span> : null}</Link>
            <Link href="/analytics" aria-current={pathname === '/analytics' ? 'page' : undefined}>Analytics</Link>
            <Link href="/commands" aria-current={pathname === '/commands' ? 'page' : undefined}>Commands</Link>
          </nav>
          <div className="top-actions">
            <span className={`stamp sync-stamp${syncMinutes == null || syncMinutes > 1440 ? ' stale' : ''}`}
              title={state?.sync ? `Last sync moved ${state.sync.moved?.length || 0}, added ${state.sync.added?.length || 0}, saved ${state.sync.threads || 0} threads` : undefined}>{syncText}</span>
            {state?.commands?.sync ? <button disabled={syncing} onClick={() => runCommand('sync')}
              title="Read replies, offers, contracts and proposals from Upwork. Sends nothing.">{syncing ? 'Syncing…' : 'Sync'}</button> : null}
            {state?.commands?.['find-jobs'] ? <button className="primary" onClick={() => runCommand('find-jobs')}>Find jobs</button> : null}
          </div>
        </div>
      </header>
      <main className={`wrap${pathname === '/' ? ' list-wrap' : ''}`} ref={pageRef}>
        {connectionLost ? <div className="empty-state" role="alert"><strong>Connection lost</strong><p>{CONNECTION_LOST}</p><button onClick={() => void load()}>Try again</button></div>
          : state ? children : <p className="empty" role="status">Loading cockpit.</p>}
      </main>
      <Drawer />
      <RunsDock />
      <div className={`toast${toastVisible ? ' show' : ''}`} role="status">{toastMessage}</div>
    </CockpitContext.Provider>
  );
}
