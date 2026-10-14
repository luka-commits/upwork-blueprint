'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { analyticsMemberText as plain } from '@/lib/analytics-contract';

type Row = Record<string, any>;
type Point = { point: number; label: string; state: string; reason?: string };
type Criterion = { point: number; label: string; met: number; partly: number; missing: number; not_needed: number; n: number; reason?: string };
const STAGES = [['Chats', 'chats'], ['Calls', 'calls']];
const LABELS: Record<string, string[]> = {
  chats: ['Answered question', 'Qualifying question', 'Call proposal when useful'],
  calls: ['Opening and agenda', 'Current state', 'Problem and cost', 'Goal and scope', 'Budget before price', 'Decision maker and timeline', 'Why you', 'Objections', 'Next step on Upwork'],
};
const CHAT_KEYS: Record<string, number> = { answered_question: 1, qualifying_question: 2, call_times: 3, call_proposal: 3 };
const STATE_NAME = { met: 'Met', partly: 'Partly met', missing: 'Missing' } as const;
const R = 18, C = 2 * Math.PI * R;
const array = (value: any): Row[] => Array.isArray(value) ? value : [];
const string = (value: any): string => typeof value === 'string' ? value : '';
const sourceText = (value: string) => plain(value) === value ? value : 'Quote unavailable in this view. Open the full source.';
function Quote({value}: {value:string}) { return plain(value) === value ? <blockquote>“{value}”</blockquote> : <p>{sourceText(value)}</p>; }
const idOf = (entry: Row) => String(entry.lead_id ?? entry.job_id ?? entry.id ?? '');
const dateOf = (entry: Row) => entry.date || entry.call_date || entry.applied_at || entry.replied_at || entry.proposal_sent_at || entry.reviewed_at || entry.as_of;
const stageName = (kind: string) => STAGES.find(([, key]) => key === kind)?.[0] || kind;
const normalizedState = (value: any) => string(value).toLowerCase().trim().replace(/[ -]+/g, '_');

/** Read recorded point judgments, including numeric-keyed objects from older snapshots. */
export function recordedPoints(entry: Row, kind: string): Point[] {
  const raw = entry.points ?? entry.review_points ?? entry.rubric;
  const values: Row[] = Array.isArray(raw) ? raw : raw && typeof raw === 'object'
    ? Object.entries(raw).map(([key, value]) => typeof value === 'object' && value !== null ? { ...value as Row, point: (value as Row).point ?? key } : { point: key, state: value }) : [];
  const aliases = kind === 'chats' ? CHAT_KEYS : {};
  const seen = new Set<number>();
  return values.flatMap(value => {
    const recordedId = value.point ?? value.number ?? value.key ?? value.id;
    const numeric = typeof recordedId === 'number' ? recordedId : /^\d+$/.test(String(recordedId)) ? Number(recordedId) : aliases[String(recordedId)];
    const state = normalizedState(value.state ?? value.status);
    if (!Number.isInteger(numeric) || numeric < 1 || seen.has(numeric) || !['met', 'partly', 'missing', 'not_needed'].includes(state)) return [];
    if (LABELS[kind] && numeric > LABELS[kind].length) return [];
    seen.add(numeric);
    return [{ point: numeric, label: LABELS[kind]?.[numeric - 1] || string(value.label || value.name) || `Point ${numeric}`, state, reason: string(value.reason) || undefined }];
  });
}

const sourceMissing = (entry: Row) => entry.reviewable === false || entry.source_missing === true || entry.source_complete === false || entry.transcript_complete === false || ['missing', 'unknown', 'unreviewable', 'not_reviewed'].includes(normalizedState(entry.source_state));
export function reviewMarker(entry: Row, kind: string): string {
  if (sourceMissing(entry)) return 'Not reviewed';
  const points = recordedPoints(entry, kind), applicable = points.filter(point => point.state !== 'not_needed');
  const legacy = normalizedState(entry.marker || entry.assessment || entry.verdict || entry.state);
  if (applicable.some(point => point.state === 'partly' || point.state === 'missing')) return 'Needs work';
  const required = LABELS[kind] ? LABELS[kind].map((_, index) => index + 1) : [];
  if (points.length && required.some(point => !points.some(recorded => recorded.point === point))) return 'Needs work';
  if (/needs_work|fail|improve/.test(legacy)) return 'Needs work';
  if (/not_reviewed|unreviewable|unknown/.test(legacy)) return 'Not reviewed';
  if (points.length && applicable.every(point => point.state === 'met')) return 'Keep';
  return /keep|pass|met/.test(legacy) ? 'Keep' : 'Not reviewed';
}
function reviewed(entry: Row, kind: string): boolean {
  if (sourceMissing(entry)) return false;
  return entry.reviewable === true || entry.reviewed === true || entry.read === true || recordedPoints(entry, kind).length > 0 || reviewMarker(entry, kind) !== 'Not reviewed';
}
const coachRead = (entry: Row) => string(entry.coach_read) || string(entry.free_read) || string(entry.read);
const fullFinding = (entry: Row) => string(entry.key_finding).trim() || coachRead(entry).trim().split(/(?<=[.!?])\s|[\r\n]/)[0] || '';
export const keyFinding = (entry: Row) => plain(fullFinding(entry)).split(/\s+/).slice(0, 12).join(' ') || 'Key finding unavailable';
function selectedWeek(entry: Row, period: any, week: string): boolean {
  const raw = dateOf(entry), date = String(raw || '').slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(date) && period && typeof period === 'object' && period.start && period.end) return date >= String(period.start).slice(0, 10) && date <= String(period.end).slice(0, 10);
  if (typeof entry.this_week === 'boolean') return entry.this_week;
  if (entry.week) return entry.week === week;
  const isoWeek = /^(\d{4})-W(\d{2})$/.exec(week || '');
  if (/^\d{4}-\d{2}-\d{2}$/.test(date) && isoWeek) {
    const jan4 = new Date(Date.UTC(Number(isoWeek[1]), 0, 4));
    const monday = new Date(jan4); monday.setUTCDate(jan4.getUTCDate() - (jan4.getUTCDay() + 6) % 7 + (Number(isoWeek[2]) - 1) * 7);
    const end = new Date(monday); end.setUTCDate(monday.getUTCDate() + 6);
    return date >= monday.toISOString().slice(0, 10) && date <= end.toISOString().slice(0, 10);
  }
  return false;
}

function criteriaFor(entries: Row[], kind: string, aggregate: Row = {}): { points: Criterion[]; reviewed_n: number } {
  const checked = entries.filter(entry => reviewed(entry, kind));
  const catalogue = new Map<number, string>();
  if (LABELS[kind]) LABELS[kind].forEach((label, index) => catalogue.set(index + 1, label));
  else {
    array(aggregate.points).forEach(point => { const numeric = Number(point.point); if (Number.isInteger(numeric) && numeric > 0) catalogue.set(numeric, string(point.label) || `Point ${numeric}`); });
    checked.forEach(entry => recordedPoints(entry, kind).forEach(point => { if (!catalogue.has(point.point)) catalogue.set(point.point, point.label); }));
  }
  const points: Criterion[] = [...catalogue].sort(([a], [b]) => a - b).map(([point, label]) => ({ point, label, met: 0, partly: 0, missing: 0, not_needed: 0, n: 0 }));
  checked.forEach(entry => recordedPoints(entry, kind).forEach(point => {
    const row = points.find(row => row.point === point.point);
    if (!row) return;
    row[point.state as 'met' | 'partly' | 'missing' | 'not_needed']++;
    if (point.state !== 'not_needed') row.n++;
    if (!row.reason && ['partly', 'missing'].includes(point.state) && point.reason) row.reason = point.reason;
  }));
  return { points, reviewed_n: checked.length };
}

/** Every total comes from the entries in the selected period; aggregate totals are never reused. */
export function CriteriaChart({ entries, kind, criteria, activePoint, onSelect }: { entries: Row[]; kind: string; criteria?: Row; activePoint: number | null; onSelect: (point: number | null) => void }) {
  const [table, setTable] = useState(false);
  const { points, reviewed_n } = criteriaFor(entries, kind, criteria);
  const tooFew = reviewed_n < 3;
  const summary = points.reduce((total, row) => ({ met: total.met + row.met, n: total.n + row.n }), { met: 0, n: 0 });
  const pct = summary.n ? Math.round(100 * summary.met / summary.n) : 0;
  const reasonLine = (row: Criterion) => row.reason ? plain(row.reason) : 'The review records a gap here; no reason was recorded.';
  const weakest = points.filter(point => point.n > 0 && point.partly + point.missing > 0).sort((a, b) => a.met / a.n - b.met / b.n || b.missing / b.n - a.missing / a.n || a.point - b.point)[0];
  return <section className="an-criteria" aria-label={`${stageName(kind)} criteria`}>
    <header className="an-criteria-heading"><div><h3>What the reviews show</h3><p className="an-meta">{reviewed_n} reviewed {kind}{tooFew ? ` · too few ${kind} to compare` : ''}</p></div><button className="an-text-button" aria-pressed={table} onClick={() => setTable(!table)}>{table ? 'Chart view' : 'Table view'}</button></header>
    {!points.length && <p className="an-meta">No recorded criteria in this period.</p>}
    {!table && summary.n > 0 && <div className="an-criteria-summary"><svg className="an-ring" viewBox="0 0 44 44" role="img" aria-label={`${pct}% of applicable points met`}><circle cx="22" cy="22" r={R} className="an-ring-track"/><circle cx="22" cy="22" r={R} className="an-ring-met" strokeDasharray={`${C * summary.met / summary.n} ${C}`} transform="rotate(-90 22 22)"/></svg><div><p className="an-big">{pct}% met</p><p className="an-meta">across {reviewed_n} {kind} · {summary.met} of {summary.n} applicable points</p></div></div>}
    {table ? <div className="an-criteria-table-scroll"><table className="an-criteria-table"><caption className="an-meta">Not needed records are excluded from applicable counts.</caption><thead><tr><th>Criterion</th><th>Met</th><th>Partly</th><th>Missing</th><th>Not needed</th><th>Applicable</th></tr></thead><tbody>{points.map(row => <tr key={row.point} className={row.point === weakest?.point ? 'an-criterion-weakest' : undefined}><th scope="row"><button className="an-text-button" aria-pressed={activePoint === row.point} onClick={() => onSelect(activePoint === row.point ? null : row.point)}>{plain(row.label)}</button>{row.point === weakest?.point && <p className="an-criterion-reason">{reasonLine(row)}</p>}</th><td>{row.met}</td><td>{row.partly}</td><td>{row.missing}</td><td>{row.not_needed} excluded</td><td>{row.n}</td></tr>)}</tbody></table></div> : <div className="an-criteria-rows">{points.map(row => <div className={`an-criterion${row.point === weakest?.point ? ' an-criterion-weakest' : ''}${activePoint === row.point ? ' an-criterion-active' : ''}`} key={row.point}>
      <div className="an-criterion-line">
        <button className="an-criterion-control" aria-pressed={activePoint === row.point} onClick={() => onSelect(activePoint === row.point ? null : row.point)}><strong>{plain(row.label)}</strong></button>
        {!tooFew && row.n > 0 ? <div className="an-criterion-bar" role="img" aria-label={`${row.label}: ${row.met} met, ${row.partly} partly, ${row.missing} missing out of ${row.n} applicable ${kind}`}>{(['met', 'partly', 'missing'] as const).map(state => row[state] > 0 ? <span tabIndex={0} key={state} className={`an-criterion-segment an-criterion-${state}`} style={{ flexGrow: row[state] }} data-tip={`${STATE_NAME[state]}: ${row[state]} of ${row.n} ${kind}`} aria-label={`${STATE_NAME[state]}: ${row[state]} of ${row.n} ${kind}`}/> : null)}</div> : <div className="an-criterion-bar an-criterion-bar-empty" aria-hidden="true"/>}
        <span className="an-criterion-k">{row.n === 0 ? 'none apply' : `${row.met} of ${row.n}`}</span>
      </div>
      <small className="an-criterion-counts">{row.met} met · {row.partly} partly · {row.missing} missing · {row.not_needed} not needed, excluded</small>
      {row.point === weakest?.point && <p className="an-criterion-reason"><b>Weakest:</b> {reasonLine(row)}</p>}
    </div>)}</div>}
    {!table && !tooFew && <p className="an-criteria-legend"><span className="an-legend-met">Met</span> <span className="an-legend-partly">Partly met</span> <span className="an-legend-missing">Missing</span></p>}
    {activePoint !== null && <p className="an-criterion-filter">Showing the entries to discuss below, expanded in place. <button className="an-text-button" onClick={() => onSelect(null)}>Show every entry</button></p>}
  </section>;
}

function CopyCommand({ id }: { id: string }) {
  const [copied, setCopied] = useState(false), [fallback, setFallback] = useState(false);
  const input = useRef<HTMLInputElement>(null), timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const command = `/call-review ${id}`;
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  useEffect(() => { if (fallback) { input.current?.focus(); input.current?.select(); } }, [fallback]);
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(command); setFallback(false); setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch { setFallback(true); input.current?.focus(); input.current?.select(); }
  };
  return <div className="an-call-command"><button onClick={copy} disabled={!id}>{copied ? 'Copied' : 'Copy command'}</button><span className="an-meta">Paste into your Claude session for the full analysis.</span>{fallback && <label className="an-command-fallback">Select and copy this command<input ref={input} readOnly value={command} onFocus={event => event.currentTarget.select()} aria-label="Call review command"/></label>}<span className="an-copy-status" role="status" aria-live="polite">{copied ? 'Copied' : ''}</span></div>;
}
export function CallMoments({card}: {card:Row}) {
  const moments=array(card.moments).filter(moment=>string(moment.quote).trim());
  return <>{moments.length>0 && <section className="an-call-moments"><h4>{moments.length===1?'Turning moment':'Key moments'}</h4>{moments.map((moment,index)=><div key={index}><Quote value={moment.quote}/>{moment.quote_at && <small className="an-meta">{plain(moment.quote_at)}</small>}{string(moment.better_wording || moment.better || moment.better_line) && <p className="an-better-line"><strong>Try:</strong> {plain(moment.better_wording || moment.better || moment.better_line)}</p>}</div>)}</section>}{string(card.fix) && <p><strong>One change:</strong> {plain(card.fix)}</p>}{string(card.example) && <p><strong>Example:</strong> {plain(card.example)}</p>}</>;
}
function ReviewDetails({ entry, kind, job, finding, renderDetails }: { entry: Row; kind: string; job?: Row; finding: string; renderDetails: (entry: Row, kind: string) => ReactNode }) {
  if (kind === 'calls') return <div className="an-inline-review">{renderDetails(entry, kind)}</div>;
  const moment = array(entry.moments).find(moment => string(moment.better_line || moment.better_wording || moment.better));
  const better = string(entry.better_line) || string(entry.better_wording) || string(moment?.better_line) || string(moment?.better_wording) || string(moment?.better) || string(entry.example);
  const next = string(entry.next_message) || string(entry.next_message?.text);
  const rawPoints=entry.points ?? entry.review_points ?? entry.rubric;
  const pointQuotes: Row[] = Array.isArray(rawPoints) ? rawPoints : rawPoints && typeof rawPoints==='object' ? Object.values(rawPoints) as Row[] : [];
  const quote = string(entry.quote) || array(entry.moments).map(moment => string(moment.quote)).find(Boolean) || pointQuotes.map(point=>string(point?.quote)).find(Boolean);
  return <div className="an-inline-review"><p><strong>Key finding</strong> {keyFinding(entry)}</p>{quote && <Quote value={quote}/>}{better && <p className="an-better-line"><strong>Try:</strong> {plain(better)}</p>}{next && <section className="an-inline-next"><h4>Next message</h4><p className="an-message">{sourceText(next)}</p></section>}<details className="an-full-coach"><summary>Full coach read and recorded checks</summary>{renderDetails(entry, kind)}</details></div>;
}
function ReviewSection({ name, kind, entries, jobs, criteria, period, week, renderDetails }: { name: string; kind: string; entries: Row[]; jobs: Row[]; criteria?: Row; period: any; week: string; renderDetails: (entry: Row, kind: string) => ReactNode }) {
  const [range, setRange] = useState('week'), [activePoint, setActivePoint] = useState<number | null>(null), [all, setAll] = useState(false);
  const selected = entries.filter(entry => range === 'all' || selectedWeek(entry, period, week));
  const hasGaps = activePoint !== null && selected.some(entry => reviewed(entry, kind) && recordedPoints(entry, kind).some(point => point.point === activePoint && ['partly', 'missing'].includes(point.state)));
  const filtered = selected.filter(entry => activePoint === null || reviewed(entry, kind) && recordedPoints(entry, kind).some(point => point.point === activePoint && (hasGaps ? ['partly', 'missing'].includes(point.state) : point.state === 'met')));
  const ordered = filtered.map((entry, index) => ({ entry, index })).sort((a, b) => Number(reviewMarker(b.entry, kind) === 'Needs work') - Number(reviewMarker(a.entry, kind) === 'Needs work') || String(dateOf(b.entry) || '').localeCompare(String(dateOf(a.entry) || '')) || a.index - b.index);
  const missing: Record<string, string> = { chats: 'Sync the Upwork thread with /brief, then run /analytics.', calls: 'Paste the full call transcript, then run /call-review <job id>.' };
  return <section className="an-review-section" id={`conversations-${kind}`}><div className="an-section-heading"><h2>{name}</h2><label className="an-range">Period <select value={range} onChange={event => { setRange(event.target.value); setActivePoint(null); setAll(false); }}><option value="week">This week</option><option value="all">All dates</option></select></label></div><CriteriaChart entries={selected} kind={kind} criteria={criteria} activePoint={activePoint} onSelect={point => {setActivePoint(point); setAll(false);}}/>
    {!entries.length ? <p className="an-empty">{missing[kind]}</p> : !selected.length ? <p className="an-empty">Nothing this week. <button className="an-text-button" onClick={() => { setRange('all'); setActivePoint(null); }}>Show all dates</button></p> : !ordered.length ? <p className="an-empty">No matching entries in this period. <button className="an-text-button" onClick={() => setActivePoint(null)}>Show every entry</button></p> : <div className="an-review-rows an-inline-rows">{(all || activePoint !== null ? ordered : ordered.slice(0,3)).map(({ entry, index }) => {
      const id = idOf(entry), job = jobs.find(job => String(job.id) === id), title = job?.title || entry.job_title || entry.title || entry.label || 'Job title unavailable';
      const duplicate = string(entry.duplicate_of_stage), finding = duplicate ? `Same point as in ${stageName(duplicate)}.` : keyFinding(entry);
      return <article className="an-inline-row" key={`${id || 'review'}-${dateOf(entry) || ''}-${index}`}><details className="an-entry-detail" open={activePoint === null ? undefined : true}><summary><strong>{plain(title)}</strong><span className="an-row-finding">{finding}</span><small><b className="an-chip">{reviewMarker(entry, kind)}</b> {dateOf(entry) || 'Date unknown'}</small></summary><ReviewDetails entry={entry} kind={kind} job={job} finding={finding} renderDetails={renderDetails}/></details>{kind === 'calls' && <CopyCommand id={id}/>}</article>;
    })}</div>}
    {ordered.length > 3 && activePoint === null && <button className="an-text-button" aria-expanded={all} onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${ordered.length}`}</button>}
  </section>;
}

export default function AnalyticsConversations({ entries, patterns, criteria, jobs, period, week, renderDetails }: { entries: Record<string, any[]>; patterns: any[]; criteria?: Row; jobs: any[]; period: any; week: string; renderDetails: (entry: any, kind: string) => ReactNode }) {
  const firstStages = new Map<string, string>();
  const marked: Record<string, Row[]> = {};
  STAGES.forEach(([, kind]) => { marked[kind] = array(entries[kind]).map(entry => {
    const finding = fullFinding(entry).toLowerCase().replace(/\s+/g, ' ').trim(), id = idOf(entry);
    const identity = id && finding && reviewed(entry, kind) ? `${id}:${finding}` : '';
    const first = identity ? firstStages.get(identity) : undefined;
    if (identity && !first) firstStages.set(identity, kind);
    return { ...entry, duplicate_of_stage: entry.duplicate_of_stage || (first && first !== kind ? first : undefined) };
  }); });
  const chatCallPatterns: Row[] = array(patterns).map((pattern): Row => ({ ...pattern, quotes: array(pattern.quotes).filter((quote: Row) => !quote.stage || ['chats', 'calls'].includes(String(quote.stage))) })).filter((pattern: Row, index: number) => !array(array(patterns)[index].quotes).length || pattern.quotes.length);
  const qualifiedPatterns = chatCallPatterns.filter(pattern => typeof pattern.k === 'number' && Number.isInteger(pattern.k) && typeof pattern.n === 'number' && Number.isInteger(pattern.n) && pattern.k >= 0 && pattern.n > 0 && pattern.k <= pattern.n && string(pattern.better_line).trim() && string(pattern.text).trim());
  return <><section className="an-patterns"><h2>Across your conversations</h2>{qualifiedPatterns.length ? qualifiedPatterns.map((pattern, index) => {
    const seenQuotes = new Set<string>();
    const quotes = array(pattern.quotes).filter(quote => { const text = string(quote.quote).trim(), identity = text.replace(/\s+/g, ' ').toLowerCase(); if (!text || seenQuotes.has(identity)) return false; seenQuotes.add(identity); return true; }).slice(0, 2);
    const headline = string(pattern.text).startsWith(`In ${pattern.k} of ${pattern.n} `) ? plain(pattern.text) : `In ${pattern.k} of ${pattern.n} conversations: ${plain(pattern.text)}`;
    return <article key={index}><h3 className="an-pattern-headline">{headline}</h3>{quotes.map((quote, i) => <figure className="an-pattern-quote" key={i}><Quote value={quote.quote}/><figcaption>{plain(quote.title || jobs.find(job => String(job.id) === String(quote.lead_id))?.title || 'Job title unavailable')} · {plain(quote.date || 'Date unknown')}</figcaption></figure>)}<p className="an-better-line"><strong>Try:</strong> {plain(pattern.better_line)}</p></article>;
  }) : <p className="an-empty">No counted cross-stage pattern with a better line recorded yet.</p>}</section>{STAGES.map(([name, kind]) => <ReviewSection key={kind} name={name} kind={kind} entries={marked[kind]} jobs={jobs} criteria={criteria?.[kind]} period={period} week={week} renderDetails={renderDetails}/>)}</>;
}
