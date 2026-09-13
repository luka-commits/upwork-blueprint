'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useCockpit, type Run, type State } from '@/lib/context';
import { parseRunResult } from '@/lib/run-result.mjs';
import RunResult from './RunResult';

const DOCK_OPEN_EVENT = 'cockpit-dock-open';
const RUN_LABEL: Record<string, string> = {
  'find-jobs': 'Find jobs',
  sync: 'Sync Upwork',
  'pitch-page': 'Prepare pitch page',
  apply: 'Prepare application',
  reply: 'Draft replies',
  'lead-magnet': 'Build SEO audit',
  'follow-up': 'Review follow-ups',
  'send-reply': 'Send reply',
  inbox: 'Check Upwork inbox',
  status: 'Review pipeline status',
  'call-prep': 'Prepare for call',
  'call-review': 'Review call',
  'loom-review': 'Review Loom video',
  proposal: 'Prepare proposal',
  won: 'Set up won project',
  delivery: 'Prepare delivery',
};

function clock(ms: number) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

function runClass(run: Run) {
  if (!run.done) return '';
  return run.stopped ? 'stopped' : run.error ? 'failed' : 'finished';
}

function stateWord(run: Run) {
  if (!run.done) return 'Running';
  return run.stopped ? 'Stopped' : run.error ? 'Failed' : 'Done';
}

export function runTitle(run: Pick<Run, 'command' | 'job'>, state: State | null) {
  const job = run.job ? ((state?.jobs || []).find((item: any) => item.id === run.job) || {}).title || 'Job' : '';
  return `${RUN_LABEL[run.command] || run.command.replaceAll('-', ' ')}${job ? ` · ${job}` : ''}`;
}

export default function RunsDock() {
  const { state, runs, openDrawer, stopRun, dismissRun, toggleRunLog, toggleRunResult } = useCockpit();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [now, setNow] = useState(Date.now());
  const logRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    try {
      const saved = localStorage.getItem('dock-collapsed');
      if (saved) setCollapsed(JSON.parse(saved));
    } catch {
      // Storage can be blocked without breaking the dock.
    }
    const open = () => setCollapsed(false);
    window.addEventListener(DOCK_OPEN_EVENT, open);
    return () => window.removeEventListener(DOCK_OPEN_EVENT, open);
  }, []);

  useEffect(() => {
    if (!runs.some(run => !run.done)) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [runs]);

  useEffect(() => {
    runs.forEach(run => {
      const log = logRefs.current.get(run.id);
      if (log) log.scrollTop = log.scrollHeight;
    });
  }, [runs]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem('dock-collapsed', JSON.stringify(next)); } catch { /* Storage is optional. */ }
  };

  const openMadeJob = (id: string) => {
    if (pathname.startsWith('/job/')) router.push('/');
    openDrawer(id);
  };

  const newest = [...runs].reverse();
  if (!newest.length) return <section className="dock" aria-label="Runs" hidden />;
  const live = newest.filter(run => !run.done);
  const lead = live[0] || newest[0];
  const count = (test: (run: Run) => boolean) => newest.filter(test).length;
  const done = count(run => run.done && !run.error && !run.stopped);
  const stopped = count(run => !!run.stopped);
  const brokeOff = count(run => !!run.error && !run.stopped);
  const summary = [
    'Runs',
    live.length && `${live.length} running`,
    done && `${done} done`,
    stopped && `${stopped} stopped`,
    brokeOff && `${brokeOff} failed`,
  ].filter(Boolean).join(' · ');

  return (
    <section className={`dock${collapsed ? ' collapsed' : ''}`} aria-label="Runs">
      <button className="dock-head" onClick={toggleCollapsed} aria-expanded={!collapsed}>
        <span className={`spin ${live.length ? '' : runClass(lead)}`} style={{ display: 'inline-block' }} />
        <span className="grow">
          {summary}{collapsed ? <span> · {lead.status}</span> : null}
        </span>
        {live.length ? <span className="stamp">{clock(now - lead.t0)}</span> : null}
        <span className="chev" aria-hidden="true">▾</span>
      </button>
      <div className="dock-body">
        {newest.map(run => {
          const outcome = run.done && run.result ? parseRunResult(run.result) : null;
          return (
          <div className={`runitem ${runClass(run)}`} key={run.id}>
            <div className="runitem-head">
              <span className="spin" />
              <span className="grow">{runTitle(run, state)}</span>
              <span className="state">{stateWord(run)}</span>
              <span className="stamp">{clock((run.t1 || now) - run.t0)}</span>
              {run.done ? <button className="link" onClick={() => dismissRun(run.id)} aria-label="Remove run">✕</button> : null}
            </div>
            {!run.done ? <div className="run-progress" role="progressbar" aria-label={`${runTitle(run, state)} progress`}>
              <span />
            </div> : null}
            {!run.showResult || !run.result ? <div className="runitem-status">
              {!run.done ? <span className="runitem-status-label">Current step</span> : null}
              {outcome?.headline || run.status}
            </div> : null}
            {run.made.length ? (
              <div className="runitem-made">
                {run.made.map((made, index) => made.href ? (
                  <a href={made.href} target="_blank" rel="noopener" key={`${made.label}-${index}`}>{made.label} →</a>
                ) : made.open ? (
                  <a href="#" onClick={event => { event.preventDefault(); openMadeJob(made.open!); }} key={`${made.label}-${index}`}>{made.label} →</a>
                ) : <span key={`${made.label}-${index}`}>{made.label}</span>)}
              </div>
            ) : null}
            {run.log.length || !run.done ? <div className="runitem-foot">
              {run.done && run.command === 'follow-up' ? <button className="link" onClick={() => router.push('/follow-ups')}>Open follow-up review</button> : null}
              {run.done && run.result ? <button className="link" onClick={() => toggleRunResult(run.id)}>
                {run.showResult ? 'Hide result' : 'View result'}
              </button> : null}
              {run.log.length ? <button className="link" onClick={() => toggleRunLog(run.id)}>
                {run.showLog ? 'Hide steps' : `Show steps · ${run.log.length}`}
              </button> : null}
              {!run.done ? <button className="link" onClick={() => stopRun(run.id)}>Stop</button> : null}
            </div> : null}
            {run.showResult && run.result ? <RunResult result={run.result} error={run.error} stopped={run.stopped} /> : null}
            {run.showLog ? (
              <div className="run-log" ref={node => {
                if (node) logRefs.current.set(run.id, node);
                else logRefs.current.delete(run.id);
              }}>
                {run.log.map((line, index) => <div className={line.kind} key={index}>{line.text}</div>)}
              </div>
            ) : null}
          </div>
        );})}
      </div>
    </section>
  );
}
