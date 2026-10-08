'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { BOARD, LABEL, LIST } from '@/lib/stages.mjs';
import { nextStep, waitingState } from '@/lib/next-step.mjs';
import { daysInStage, searchJobs, sortJobs } from '@/lib/list-view.mjs';
import {
  bidsTone, budgetText, budgetTone, clientLines, clientTone, competitionLines, headlineText, jobFlags, postedTone, scoreTone,
} from '@/lib/job-facts.mjs';
import CopyButton from './CopyButton';

type Layout = 'list' | 'board';
type SortKey = 'score' | 'job' | 'client' | 'competition' | 'budget' | 'step';
type Sort = { key: SortKey; desc: boolean } | null;

const LAYOUT_KEY = 'cockpit-layout';
// How fresh a posting is, in hours. A dense search term turns over ten postings in
// two hours, so "today" is not a useful bucket and these are.
const FRESH: [number, string][] = [[0, 'Any age'], [1, '1h'], [4, '4h'], [12, '12h'], [24, '24h'], [72, '3d'], [168, '7d']];
// A custom age is typed as a number with an optional unit: 90m, 36h, 2d. No unit means hours.
function parseAge(text: string): number | null {
  const m = /^\s*(\d+(?:\.\d+)?)\s*(m|min|h|d)?\s*$/i.exec(text);
  if (!m) return null;
  const n = parseFloat(m[1]);
  const unit = (m[2] || 'h').toLowerCase();
  const hours = unit.startsWith('m') ? n / 60 : unit === 'd' ? n * 24 : n;
  return hours > 0 ? hours : null;
}
// The list holds the leads still to decide on; everything from Applied on lives on the board.
// The title column is gone (27.09.2026): an Upwork title is the client's own SEO line
// and says the same thing forty times over, while the summary is the sentence that
// actually decides. The title survives as the link's tooltip.
const COLUMNS: { key: SortKey | 'summary'; label: string; width?: number }[] = [
  { key: 'score', label: 'Score', width: 72 },
  { key: 'summary', label: 'Summary' },
  { key: 'client', label: 'Client', width: 200 },
  { key: 'competition', label: 'Competition', width: 158 },
  { key: 'budget', label: 'Budget', width: 128 },
  { key: 'step', label: 'Next step', width: 208 },
];

export default function ListPage() {
  const { state, drawerId, openDrawer, closeDrawer } = useCockpit();
  const [layout, setLayout] = useState<Layout>('list');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<Sort>(null);

  useEffect(() => {
    try { if (localStorage.getItem(LAYOUT_KEY) === 'board') setLayout('board'); } catch { /* Storage is optional. */ }
  }, []);

  // Longest waiting first by default: a board exists to show what is going stale.
  const [oldestFirst, setOldestFirst] = useState(true);
  const [dueOnly, setDueOnly] = useState(false);
  // Hours: 0 shows everything.
  const [fresh, setFresh] = useState(0);
  const [custom, setCustom] = useState('');
  const all: any[] = state?.jobs || [];
  const pool = useMemo(() => all.filter(j => (layout === 'board' ? BOARD : LIST).includes(j.status)), [all, layout]);
  // Due means a task is waiting on the member now, not a follow-up set for later.
  const byDue = useMemo(() => dueOnly ? pool.filter(j => waitingState(j).kind === 'act') : pool, [pool, dueOnly]);
  // A posting stops being worth Connects within hours, so freshness is a filter and
  // not only a colour. Anything without a posting date stays visible: a missing field
  // is not evidence that the job is old.
  const filtered = useMemo(() => {
    // Only on the list. On the board a "posted 3 days ago" lead is a live conversation,
    // and hiding it behind an apply-time filter loses work that is already in flight.
    if (!fresh || layout === 'board') return byDue;
    const cutoff = Date.now() - fresh * 3600e3;
    return byDue.filter(j => !j.posted_date || Date.parse(j.posted_date) >= cutoff);
  }, [byDue, fresh, layout]);
  const jobs = useMemo(() => sortJobs(searchJobs(filtered, query), layout === 'board' ? null : sort), [filtered, query, sort, layout]);
  if (!state) return null;

  const choose = (next: Layout) => {
    setLayout(next);
    try { localStorage.setItem(LAYOUT_KEY, next); } catch { /* Storage is optional. */ }
  };
  const toggle = (id: string) => drawerId === id ? closeDrawer() : openDrawer(id);
  // Up, down, then back to the default order.
  const sortBy = (key: SortKey) => setSort(current => current?.key !== key ? { key, desc: false } : current.desc ? null : { key, desc: true });
  const noun = layout === 'board' ? 'in the pipeline' : 'to decide on';
  const dueTotal = pool.filter(j => waitingState(j).kind === 'act').length;

  return <div>
    <div className="toolbar">
      <div className="seg" role="group" aria-label="Layout" style={{ '--segment-index': Number(layout === 'board') } as React.CSSProperties}>
        <button onClick={() => choose('list')} aria-pressed={layout === 'list'}>List</button>
        <button onClick={() => choose('board')} aria-pressed={layout === 'board'}>Board</button>
      </div>
      {layout === 'board' ? <div className="seg" role="group" aria-label="Order"
        style={{ '--segment-index': Number(!oldestFirst) } as React.CSSProperties}>
        <button onClick={() => setOldestFirst(true)} aria-pressed={oldestFirst}>Longest waiting</button>
        <button onClick={() => setOldestFirst(false)} aria-pressed={!oldestFirst}>Newest</button>
      </div> : null}
      <label className="search-box">
        <input type="search" placeholder="Search jobs" aria-label="Search" value={query} onChange={e => setQuery(e.target.value)} />
      </label>
      <button type="button" className={`due-toggle${dueOnly ? ' on' : ''}`} aria-pressed={dueOnly}
        onClick={() => setDueOnly(v => !v)}>{dueTotal ? `Needs me · ${dueTotal}` : 'Needs me'}</button>
      {layout === 'board' ? null : <div className="age" role="group" aria-label="Posted within">
        {FRESH.map(([hours, label]) => <button key={label} type="button"
          onClick={() => { setCustom(''); setFresh(hours); }}
          aria-pressed={!custom && fresh === hours}>{label}</button>)}
        <input className={`age-custom${custom ? ' on' : ''}`} placeholder="Custom, e.g. 36h" aria-label="Custom age"
          value={custom} onChange={e => {
            setCustom(e.target.value);
            const hours = parseAge(e.target.value);
            setFresh(e.target.value.trim() === '' ? 0 : hours ?? fresh);
          }} />
      </div>}
      <span className="count" aria-live="polite">{jobs.length === pool.length ? `${pool.length} ${noun}` : `${jobs.length} of ${pool.length} ${noun}`}</span>
    </div>
    {layout === 'board' ? <Board jobs={jobs} oldestFirst={oldestFirst} drawerId={drawerId} toggle={toggle} />
      : !pool.length ? <p className="empty">No new jobs. Run /find-jobs in Claude Code.</p>
        : !jobs.length ? <p className="empty">Nothing matches “{query}”.</p>
          : <Table jobs={jobs} sort={sort} sortBy={sortBy} drawerId={drawerId} toggle={toggle} />}
  </div>;
}

// Green, amber and red for the facts that decide whether a lead is worth it.
const tone = (value: string) => value ? `tone-${value}` : '';

function StepCell({ job }: { job: any }) {
  const step = nextStep(job);
  const state = waitingState(job);
  return <>
    <span className="step-row">
      {step.command
        ? <CopyButton compact text={step.command} label={step.command.split(' ')[0]} />
        : <span className="step-hint">{step.label || '–'}</span>}
      <OnUpwork job={job} />
    </span>
    <span className={`uw-sub state-${state.kind.replace(' ', '-')}${state.late ? ' tone-bad' : ''}`}>
      {/* The chip already says what to do, so the line under it says only how long
          this has been sitting. Without a chip it carries the state itself. */}
      {state.kind === 'act' && step.command && !state.late
        ? `${state.age} in stage`
        : state.detail}
    </span>
  </>;
}

function Table({ jobs, sort, sortBy, drawerId, toggle }: {
  jobs: any[]; sort: Sort; sortBy: (key: SortKey) => void; drawerId: string | null; toggle: (id: string) => void;
}) {
  return <div className="table-card"><table className="rt-table">
    <colgroup>{COLUMNS.map(col => <col key={col.key} style={col.width ? { width: col.width } : undefined} />)}</colgroup>
    <thead><tr>{COLUMNS.map(col => {
      if (col.key === 'summary') return <th key={col.key}><span className="th-label">{col.label}</span></th>;
      const key = col.key, on = sort?.key === key;
      return <th key={key} aria-sort={on ? sort!.desc ? 'descending' : 'ascending' : 'none'}>
        <button className="th-sort" onClick={() => sortBy(key)}>{col.label}{on ? sort!.desc ? ' ↓' : ' ↑' : ''}</button>
      </th>;
    })}</tr></thead>
    <tbody>{jobs.map(j => {
      const id = String(j.id), [client, place] = clientLines(j), [posted, bids] = competitionLines(j);
      const connects = (j.details || {}).connects_cost;
      return <tr key={id} className={`uw-row${id === drawerId ? ' sel' : ''}`} tabIndex={0}
        onClick={e => { if (!(e.target as Element).closest('button, a')) toggle(id); }}
        onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) { e.preventDefault(); toggle(id); } }}>
        <td data-column="score"><span className={`uw-score ${scoreTone(j.score)}`}>{j.score == null ? '–' : j.score}</span></td>
        <td data-column="summary">
          {/* The link goes to the posting itself. Without it a member has to search Upwork
              by title to reread what the client actually wrote. */}
          {j.url
            ? <a className="rt-td-summary" href={j.url} target="_blank" rel="noopener" title={j.title}>{headlineText(j)}</a>
            : <span className="rt-td-summary" title={j.title}>{headlineText(j)}</span>}
          {jobFlags(j).map(flag => <span key={flag.text} className={`uw-flag ${flag.tone}`}>{flag.text}</span>)}
        </td>
        <td data-column="client"><span className={tone(clientTone(j))} title={(j.client || {}).rating ? undefined : 'No rating yet'}>{client}</span>
          <span className="uw-sub">{place}</span></td>
        <td data-column="competition"><span className={tone(postedTone(j))}>{posted}</span><span className={`uw-sub ${tone(bidsTone(j))}`}>{bids}</span></td>
        <td data-column="budget"><span className={tone(budgetTone(j))}>{budgetText(j)}</span>{connects != null ? <span className="uw-sub">{connects} connects</span> : null}</td>
        <td data-column="step"><StepCell job={j} /></td>
      </tr>;
    })}</tbody>
  </table></div>;
}

// The posting itself, one click away. The list had it hidden behind the summary text
// and the board had it nowhere, so reading what a client actually wrote meant searching
// Upwork by title. The url survives prune, so this works on an old lead too.
function OnUpwork({ job }: { job: any }) {
  if (!job.url) return null;
  return <a className="on-upwork" href={job.url} target="_blank" rel="noopener"
    title="Open this job on Upwork" onClick={e => e.stopPropagation()}>
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true" className="on-upwork-icon">
      <path d="M6.5 3.5H3.2A.7.7 0 0 0 2.5 4.2v8.6a.7.7 0 0 0 .7.7h8.6a.7.7 0 0 0 .7-.7V9.5"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M9.5 2.5h4v4M13.5 2.5 7 9" stroke="currentColor" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
    <span>Upwork</span>
  </a>;
}

function Board({ jobs, oldestFirst, drawerId, toggle }: { jobs: any[]; oldestFirst: boolean; drawerId: string | null; toggle: (id: string) => void }) {
  return <div className="board">{BOARD.map(stage => {
    const list = jobs.filter(j => j.status === stage)
      .sort((a, b) => ((daysInStage(b) ?? 0) - (daysInStage(a) ?? 0)) * (oldestFirst ? 1 : -1));
    return <section key={stage} className={`col stage-${stage}`}>
      <div className="col-head"><div className="col-title">{LABEL[stage]}</div><span className="col-count">{list.length}</span></div>
      <ul className="col-body">{list.length ? list.map(j => {
        const id = String(j.id), days = daysInStage(j), step = nextStep(j), state = waitingState(j);
        return <li key={id} className={`card${id === drawerId ? ' sel' : ''}`} tabIndex={0}
          onClick={e => { if (!(e.target as Element).closest('button')) toggle(id); }}
          onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) { e.preventDefault(); toggle(id); } }}>
          <span className="card-title" title={j.title}>{headlineText(j)}</span>
          <div className="card-meta">{[budgetText(j), days == null ? '' : `${days}d in stage`].filter(Boolean).join(' · ')}</div>
          {/* Say what is waiting on whom even when no command can do it: an offer to
              review is work, and a card without a chip used to look like nothing to do. */}
          {/* The state carries the wording when it has a date in it; otherwise the
              step's own label, because "Review offer" is work and "Waiting" is not. */}
          <div className={`card-state state-${state.kind.replace(' ', '-')}${state.late ? ' tone-bad' : ''}`}>
            {state.kind === 'waiting' && step.label && step.label !== 'Waiting' ? step.label : state.detail}
          </div>
          <div className="card-actions">
            {step.command ? <CopyButton compact text={step.command} label={step.command.split(' ')[0]} /> : null}
            <OnUpwork job={j} />
          </div>
        </li>;
      }) : <li className="col-empty">Nothing here</li>}</ul>
    </section>;
  })}</div>;
}
