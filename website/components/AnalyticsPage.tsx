'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useCockpit } from '@/lib/context';
import FunnelScorecard from './FunnelScorecard';
import CopyButton from './CopyButton';
import { analyticsMemberText, type AnalyticsPresentation } from '@/lib/analytics-contract';

type Row = Record<string, any>;
type Selection = { title: string; period?: any; evidence?: any[]; note?: string; call?: Row; review?: Row; kind?: string; badges?: Row[]; history?: Row[] };
const TABS = ['This week', 'Conversations', 'Achievements'];
const POINT_NAMES = ['Opening and agenda', 'Current state', 'Problem and cost', 'Goal and scope', 'Budget before price', 'Decision maker and timeline', 'Why you', 'Objections', 'Next step on Upwork'];
const list = (value: any): Row[] => Array.isArray(value) ? value : [];
const plain = analyticsMemberText;
const slug = (value: string) => value.toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const money = (value: any, currency?: string) => value == null ? 'Value unknown' : currency && /^[A-Z]{3}$/.test(currency) ? new Intl.NumberFormat('en-US', {style:'currency',currency,maximumFractionDigits:0}).format(value) : `${Math.round(value)} (currency unknown)`;
const evidence = (row: Row = {}) => list(row.evidence || row.evidence_lead_ids || row.lead_ids);
const periodText = (value: any) => !value ? 'Period unavailable' : typeof value === 'string' ? plain(value) : `${value.start || 'Unknown start'} to ${value.end || 'Unknown end'}`;
const effectText = (goal: Row) => goal.effect_text || ({worked:'Improvement observed',not:'No improvement observed',undecided:'Too early to tell'} as Row)[goal.effect] || 'Effect unknown';
const sourceLabel=(gap:Row,jobs:Row[]=[])=> {
  const source=String(gap.source || 'Source'), id=source.match(/[:#](\d{6,25})\b/)?.[1], title=id && jobs.find(job=>String(job.id)===id)?.title;
  const label=plain(source.replace(/[:#]\d{6,25}\b/g,''));
  return title ? `${label}: ${plain(title)}` : label;
};
const sourceInstruction=(gap:Row)=> /[:#]\d{6,25}\b/.test(String(gap.source || '')) ? /call|transcript/i.test(String(gap.source)) ? 'Paste the full call transcript, then run /analytics.' : /message|thread|review/i.test(String(gap.source)) ? 'Supply the full Upwork thread, then run /analytics.' : 'Supply the complete source, then run /analytics.' : plain(gap.how_to_supply || 'Supply the missing source, then run /analytics.');
function Empty({children}: {children: ReactNode}) { return <p className="an-empty">{children}</p>; }
const sourceText=(value:any)=>{const text=String(value ?? 'unknown');return plain(text)===text?text:'Quote unavailable in this view. Open the full source.';};
function SourceQuote({value,at}:{value:any;at?:string}) {const text=sourceText(value);return text===String(value)?<blockquote>“{text}”{at!==undefined && <small className="an-meta"> {at || 'Timestamp unavailable'}</small>}</blockquote>:<p>{text}</p>;}
function FullText({value, className, verbatim = false}: {value: any; className?: string; verbatim?: boolean}) {
  const text = verbatim ? sourceText(value) : plain(value);
  // Keep every source character; paragraph boundaries only make long reads scanable.
  const segments = Array.from(new Intl.Segmenter('en', {granularity:'sentence'}).segment(text), row => row.segment);
  const parts = segments.flatMap(sentence => sentence.match(/.{1,72}(?:\s+|$)|\S+\s*/gs) || [sentence]);
  return <>{parts.map((part,i) => <p className={className} key={i}>{part}</p>)}</>;
}
function Text({value, label = 'Read more', verbatim = false}: {value: any; label?: string; verbatim?: boolean}) {
  const text = verbatim ? sourceText(value) : plain(value);
  // Long source text stays available in a disclosure instead of being clipped.
  const preview = text.length > 90 ? text.slice(0, 86).replace(/\s+\S*$/, '') + '…' : text;
  return text.length > 90 ? <details className="an-text-detail"><summary aria-label={`${label}: ${preview}`}>{preview}</summary><FullText value={text} verbatim={verbatim}/></details> : <FullText value={text} verbatim={verbatim}/>;
}
function Spark({values, allWeeks = false}: {values: any[]; allWeeks?: boolean}) {
  const points = allWeeks ? values : values.slice(-8);
  const nums = points.map(v => typeof v === 'object' && v !== null ? v.score ?? v.value : v);
  const width = allWeeks ? Math.max(points.length <= 12 ? 320 : 600, points.length * 36) : 140, height = allWeeks ? 180 : 42;
  const x = (i:number) => (allWeeks ? 18 : 10) + i * (width - (allWeeks ? 36 : 20)) / Math.max(1, nums.length - 1);
  const y = (v:number) => height - 25 - Math.max(0, Math.min(100,v)) * (height - 40) / 100;
  return nums.some(v => Number.isFinite(v)) ? <div className={allWeeks ? 'an-history-chart' : undefined}>{allWeeks && points.length>12 && <p className="an-meta">Scroll to see all weeks.</p>}<svg className={allWeeks ? 'an-score-history' : 'an-score-spark'} style={allWeeks ? {minWidth: points.length <= 12 ? 0 : width, maxWidth: points.length <= 12 ? 600 : undefined} : undefined} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Funnel Score, ${allWeeks ? 'all' : 'last eight'} weeks: ${nums.map(v => Number.isFinite(v) ? Math.round(v) : 'unknown').join(', ')}`}>
    {nums.map((v,i) => Number.isFinite(v) ? <g key={i}><title>{`${points[i]?.week || `Week ${i+1}`}: ${Math.round(v)}`}</title>{i > 0 && Number.isFinite(nums[i-1]) && <line x1={x(i-1)} y1={y(nums[i-1])} x2={x(i)} y2={y(v)} className="an-chart-line"/>}<circle cx={x(i)} cy={y(v)} r={allWeeks ? 3 : 2} className="an-chart-dot"/>{allWeeks && <><text x={x(i)} y={y(v)-8} textAnchor="middle">{Math.round(v)}</text><text x={x(i)} y={height-5} textAnchor="middle">{points[i]?.week?.replace(/^\d+-/, '') || i+1}</text></>}</g> : null)}
  </svg></div> : <small>Score history unavailable. Run /analytics to record a week.</small>;
}
function ProgressBar({value, label}: {value: number | null; label: string}) {
  return value == null ? <small>Progress unavailable</small> : <progress max={100} value={Math.max(0,Math.min(100,value))} aria-label={label}/>;
}
function progressValue(value:any): number | null {
  if (Number.isFinite(value)) return value;
  if (value && typeof value === 'object') {
    if (Number.isFinite(value.percent)) return value.percent;
    if (Number.isFinite(value.value)) return progressValue(value.value);
    const current=value.qualifying_weeks ?? value.current, total=value.required_weeks ?? value.target;
    if (Number.isFinite(current) && Number.isFinite(total) && total > 0) return current / total * 100;
  }
  if (typeof value === 'string') {const match=value.match(/(\d+) of (\d+)/);if(match && Number(match[2]) > 0)return Number(match[1])/Number(match[2])*100;}
  return null;
}
function BadgeImage({badge}: {badge: Row}) {
  const name = badge.name || badge.badge || 'Badge';
  const image = /^\/badges\/(true-north|first-doubloon)-/.test(badge.image || '') ? badge.fallback_image || `/badges/badge-${badge.motif || 'compass'}.webp` : badge.image;
  return <img src={image || `/badges/${slug(name)}-${slug(badge.tier || 'bronze')}.webp`} alt="" width="72" height="72" onError={event => { const node = event.currentTarget; if (!node.dataset.fallback) {node.dataset.fallback='true';node.src=badge.fallback_image || `/badges/badge-${badge.motif || 'compass'}.webp`;} else node.style.visibility='hidden'; }}/>
}
function badgeProgress(badge: Row): string {
  const progress = badge.progress_to_next ?? badge.progress;
  return badge.progress_text || (typeof progress === 'string' && !/lower bound|Wilson|cohort|denominator|mature|criterion|threshold/i.test(progress) ? progress : typeof progress === 'object' && progress ? progress.text || (progress.qualifying_weeks != null && progress.required_weeks != null ? `${progress.qualifying_weeks} of ${progress.required_weeks} weeks to ${badge.next_tier || 'next tier'}` : 'Progress unavailable') : 'Progress unavailable');
}
function Badge({badge}: {badge: Row}) {
  const earned = badge.locked !== true && badge.earned !== false && !!(badge.earned || badge.tier || badge.earned_week);
  const short = typeof badge.short === 'string' && badge.short.trim().split(/\s+/).length <= 8 ? badge.short : 'Description unavailable';
  return <details className={`an-badge${earned ? '' : ' an-badge-locked'}`}><summary><BadgeImage badge={badge}/><strong>{plain(badge.name || badge.badge || 'Badge')}</strong><small>{earned ? plain(badge.tier || 'Earned') : 'Not earned yet'}</small><span>{plain(short)}</span>{earned && <><small>{plain(badgeProgress(badge))}</small><ProgressBar value={progressValue(badge.progress ?? badge.progress_to_next)} label={`${badge.name || badge.badge}: progress to ${badge.next_tier || 'next tier'}`}/></>}</summary><FullText value={plain(badge.exact_rule || badge.rule || badge.requirement || 'Rule unavailable')}/>{badge.next_rule && <FullText value={`Next tier: ${plain(badge.next_rule)}`}/>}</details>;
}
export function CallCard({card: savedCard,showTitle=true}: {card: Row;showTitle?:boolean}) {
  const {api} = useCockpit();
  const [current,setCurrent] = useState<Row | null>(null);
  const id = savedCard.lead_id || savedCard.id;
  useEffect(() => { let active = true;setCurrent(null);if(id) void api(`/api/job/${encodeURIComponent(id)}`).then(result => {const latest=list(result.data?.call_cards).find(row => String(row.lead_id || row.id) === String(id));if(active && result.ok && latest)setCurrent(latest);});return () => {active=false;};},[api,id]);
  const card = current || savedCard, points = list(card.points || card.review_points || card.rubric);
  const message = typeof card.next_message === 'object' ? card.next_message?.text : card.next_message;
  const tooLong = typeof message === 'string' && message.trim().split(/\s+/).length > 100;
  const next = card.agreed_step || card.next_step;
  return <article className="an-call-card">
    <p className="an-kicker">Call reviewed {plain(card.reviewed_at || card.as_of || card.date || card.call_date || 'date unknown')}</p>{showTitle && <h3>{plain(card.label || card.title || 'Call review')}</h3>}
    <section className="an-coach-read"><h4>Coach's read</h4>{card.coach_read ? <FullText value={card.coach_read}/> : <div className="an-empty">Not reviewed. <FullText value={card.coach_read_prompt || card.source_prompt || `Paste the full transcript, then run /call-review ${id}.`}/></div>}</section>
    {card.reviewable === false && <Empty>{plain(card.reason || 'Transcript missing.')} {plain(card.source_prompt || `Paste the full transcript, then run /call-review ${id}.`)}</Empty>}
    <section className="an-next-message"><h4>Next message</h4>{message && !tooLong ? <><FullText value={message} className="an-message" verbatim/>{card.next_message?.missing_inputs?.length ? <Text value={card.next_message.missing_inputs.join(', ')} label="Inputs needed before sending"/> : <CopyButton text={message} label="Copy message"/>}</> : <Empty>{tooLong ? 'The saved draft is over 100 words. Run' : card.next_message_state === 'not_needed' ? 'No useful message remains.' : 'No next message supplied. Run'}{card.next_message_state !== 'not_needed' && <> <code>/call-review {id}</code> for a ready draft.</>}</Empty>}</section>
    <section className="an-next-step"><h4>Agreed step</h4>{next && typeof next === 'object' ? <><FullText value={next.quote || next.action || next.text} verbatim={!!next.quote}/><p className="an-meta">{plain(next.owner || 'Owner not recorded')} · {plain(next.when || next.at || 'Time not recorded')} · {next.agreed ? 'Client agreed' : plain(next.agreement || 'Agreement not recorded')}</p></> : <FullText value={plain(next || 'Agreed step unknown')}/>}</section>
    <details className="an-points-scan"><summary>Nine points</summary><ol className="an-review-points">{POINT_NAMES.map((name,i) => {const point=points.find(row => Number(row.point || row.number || row.id)===i+1) || points[i];return <li key={name}><strong>{name}</strong> <span className="an-chip">{plain(point?.state?.replace(/_/g,' ') || 'unknown')}</span>{point?.definition && <FullText value={point.definition}/>} {point?.quote ? <SourceQuote value={point.quote} at={point.quote_at || ''}/> : <p>Supporting quote unknown.</p>}{point?.reason && <FullText value={plain(point.reason)}/>}</li>;})}</ol></details>
    {id && <p><a href={`/files/${encodeURIComponent(id)}/call.md`} target="_blank" rel="noreferrer">Open full transcript →</a></p>}
  </article>;
}
const CHAT_POINTS: Row = {answered_question:"Answered the client's question", qualifying_question:'Qualifying question', call_proposal:'Call proposal when useful'};
function ReviewCard({review,kind}: {review:Row;kind?:string}) {
  const points = review.points || review.rubric || {};
  const normalized = Array.isArray(points) ? points.map((p:Row) => ({...p,key:p.key || p.id || p.point})) : Object.entries(points).map(([key,p]) => ({...(p as Row),key}));
  const allowed = normalized.map((p:Row)=>({...p,key:p.key==='call_times'?'call_proposal':p.key})).filter((p:Row)=>kind!=='chats'||Object.keys(CHAT_POINTS).includes(p.key));
  return <article className="an-content-review"><p className="an-meta">As of {plain(review.as_of || review.reviewed_at || review.date || 'date unavailable')}</p><h3>Coach's read</h3>{review.coach_read || review.free_read || (typeof review.read==='string' ? review.read : null) || review.friction ? <Text value={review.coach_read || review.free_read || (typeof review.read==='string' ? review.read : null) || review.friction}/> : <Empty>Read unknown. {review.source_prompt || review.how_to_supply || 'Supply the full source, then run /analytics.'}</Empty>}
    {review.interpretation && <Text value={review.interpretation}/>} {review.unknown && <Text value={review.unknown}/>}
    {review.quote && <SourceQuote value={review.quote}/>}{review.fix && <><h4>One change</h4><Text value={review.fix}/></>}{review.example && <SourceQuote value={review.example}/>}{review.next_message && <><h4>Next message</h4><FullText verbatim className="an-message" value={typeof review.next_message==='string'?review.next_message:review.next_message.text}/></>}
    {kind === 'chats' && <p className="an-meta">Last writer: {plain(review.last_writer)}</p>}
    {allowed.length > 0 && <details><summary>{kind === 'chats' ? 'Content checks' : 'Review scan'}</summary>{allowed.map((point:Row,i:number) => <section key={point.key || i}><h4>{CHAT_POINTS[point.key] || plain(point.label || point.name || point.key || `Point ${i+1}`)}</h4><p>{plain(point.state || point.status)}</p>{point.quote && <SourceQuote value={point.quote}/>}{point.reason && <Text value={point.reason}/>}</section>)}</details>}
    {list(review.missing_sources).map((gap,i) => <FullText key={i} value={`${sourceLabel(typeof gap==='object'?gap:{source:gap})} unknown. ${sourceInstruction(typeof gap==='object'?gap:{source:gap})}`}/>)}
    {kind === 'applications' && <details><summary>Sent application and Loom</summary>{review.sent_copy ? <Text verbatim value={review.sent_copy}/> : <Empty>Sent copy unknown. Paste the application you sent, then run <code>/analytics</code>.</Empty>}{review.loom_transcript ? <Text verbatim value={review.loom_transcript}/> : <Empty>Loom transcript unknown. Supply the Loom link or paste its transcript, then run <code>/analytics</code>.</Empty>}</details>}
    {kind === 'proposals' && <dl className="an-evidence-facts">{['scope','price','decision_date'].map(key => <div key={key}><dt>{plain(key)}</dt><dd>{plain(review[key])}</dd></div>)}</dl>}
  </article>;
}
function PriorGoal({goal,choose}: {goal:Row;choose:(s:Selection)=>void}) {
  const checked = goal.done_n === 0 ? 'No opportunities this week' : goal.done_k == null || goal.done_n == null
    ? 'Could not check yet' : `did it ${goal.done_k} of ${goal.done_n}`;
  return <article className="an-prior-goal"><p><span aria-label={goal.done_n>0 && goal.done_k===goal.done_n ? 'Goal carried out' : 'Goal check'}>{goal.done_n>0 && goal.done_k===goal.done_n ? '✓' : '·'}</span> <strong>{plain(goal.change || goal.text || 'Agreed goal')}</strong>: {checked}. {plain(effectText(goal))}</p><button className="an-text-button" onClick={() => choose({title:goal.change || 'Goal review',period:goal.period,evidence:evidence(goal),note:[effectText(goal),goal.effect_note,goal.decision,goal.two_weeks_undone ? goal.fallback : null].filter(Boolean).join(' ')})}>Evidence →</button></article>;
}
function SelectionDrawer({value,close,jobs,calls,openLead}: {value:Selection;close:()=>void;jobs:Row[];calls:Row[];openLead:(id:string)=>void}) {
  const ref=useRef<HTMLDivElement>(null), prior=useRef<HTMLElement|null>(null);
  const [call,setCall]=useState<Row|null>(value.call || null);
  const [goalEvidence,setGoalEvidence]=useState<Selection|null>(null);
  useEffect(() => {prior.current=document.activeElement as HTMLElement;const old=document.body.style.overflow;document.body.style.overflow='hidden';const background=Array.from(document.querySelectorAll<HTMLElement>('header.top,.an-page-content'));const inert=background.map(node=>node.inert);background.forEach(node=>node.inert=true);ref.current?.focus();const keydown=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();close();}if(event.key!=='Tab')return;const nodes=Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],summary,[tabindex="0"]') || []).filter(node=>node.getClientRects().length>0),first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&(document.activeElement===first||document.activeElement===ref.current)){event.preventDefault();last?.focus();}else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===ref.current)){event.preventDefault();first?.focus();}};document.addEventListener('keydown',keydown);return()=>{document.removeEventListener('keydown',keydown);document.body.style.overflow=old;background.forEach((node,i)=>node.inert=inert[i]);prior.current?.focus();};},[]);
  return <div className="an-drawer-layer"><button className="an-drawer-shade" tabIndex={-1} aria-label="Close panel" onClick={close}/><div className="an-drawer" role="dialog" aria-modal="true" aria-labelledby="an-drawer-title" tabIndex={-1} ref={ref}><header><div><p className="an-kicker">{value.badges ? 'Progress' : 'Evidence'}</p><h2 id="an-drawer-title">{plain(value.title)}</h2></div><button onClick={close} aria-label="Close panel">Close ×</button></header>{value.period && !call && <small className="an-period">{periodText(value.period)}</small>}{value.note && <Text value={value.note}/>}
    {value.badges && !goalEvidence ? <><h3>Treasure map</h3><div className="an-badge-map">{value.badges.map((badge,i)=><Badge badge={badge} key={`${badge.name || badge.badge || i}-${badge.tier || 'locked'}-${i}`}/>)}</div>{!value.badges.length && <Empty>Badge catalogue unknown. Run <code>/analytics</code> to load it.</Empty>}<h3>Which goals worked?</h3><div className="an-goal-history">{list(value.history).map((goal,i)=><PriorGoal goal={goal} choose={setGoalEvidence} key={goal.goal_id || i}/>)}</div>{!value.history?.length && <Empty>No saved goal history yet.</Empty>}</> : call ? <>{!value.call && <button className="an-back" onClick={()=>setCall(null)}>← Back to evidence</button>}<CallCard card={call} showTitle={false}/></> : value.review ? <ReviewCard review={value.review} kind={value.kind}/> : null}
    {goalEvidence && <><button onClick={()=>setGoalEvidence(null)}>← Back to all badges</button><h3>{plain(goalEvidence.title)}</h3>{goalEvidence.note && <Text value={goalEvidence.note}/>}</>}
    {(!value.badges || goalEvidence) && <section className="an-lead-list"><h3>Source leads</h3>{list(goalEvidence?.evidence || value.evidence).map((item:any,i)=>{const id=typeof item==='object'?String(item.lead_id || item.id):String(item),job=jobs.find(row=>String(row.id)===id),saved=typeof item==='object'?item:{};return <article key={`${id}-${i}`}><strong>{plain(saved.label || job?.label || job?.title || 'Saved lead')}</strong><div>{job ? <button onClick={()=>openLead(id)}>Open lead</button> : <small>Live lead unavailable.</small>}{!value.call && !value.review && calls.find(row=>String(row.lead_id || row.id)===id) && <button onClick={()=>setCall(calls.find(row=>String(row.lead_id || row.id)===id)!)}>Review call</button>}</div></article>;})}{!(goalEvidence?.evidence || value.evidence)?.length && <Empty>No lead links supplied.</Empty>}</section>}
  </div></div>;
}
const reviewDate = (entry:Row) => entry.date || entry.call_date || entry.reviewed_at || entry.as_of;
function inWeek(entry:Row, period:Row, week:string): boolean {
  const date=reviewDate(entry);
  if (date && period?.start && period?.end) {const day=String(date).slice(0,10);return /^\d{4}-\d{2}-\d{2}$/.test(day) && day >= period.start.slice(0,10) && day <= period.end.slice(0,10);}
  return !!entry.week && entry.week === week;
}
const shortFinding = (entry:Row) => plain(entry.key_finding || entry.finding || entry.preview || entry.coach_read_preview || entry.fix || 'Key finding unavailable').split(/\s+/).slice(0,12).join(' ');
const goalMatches = (goal:Row, other:Row) => {
  if (goal.goal_id && goal.goal_id===other.goal_id) return true;
  if ([goal.continues_goal_id,goal.previous_goal_id,goal.continued_from_goal_id].includes(other.goal_id) && other.goal_id) return true;
  const normalize=(value:any)=>String(value || '').trim().toLowerCase().replace(/\s+/g,' ');
  const change=normalize(goal.change || goal.text || goal.title), previous=normalize(other.change || other.text || other.title);
  return !!change && change===previous && (!goal.kpi || !other.kpi || goal.kpi===other.kpi) && (!goal.action || !other.action || normalize(goal.action)===normalize(other.action));
};
function ReviewSection({name,kind,entries,jobs,choose,period,week}: {name:string;kind:string;entries:Row[];jobs:Row[];choose:(s:Selection)=>void;period:Row;week:string}) {
  const [all,setAll]=useState(false), [range,setRange]=useState('week');
  const missing:Row={applications:'Paste the sent application and Loom transcript, then run /analytics.',chats:'Sync the Upwork thread with /brief, then run /analytics.',calls:'Paste the full call transcript, then run /call-review <job id>.',proposals:'Paste the sent proposal, then run /analytics.'};
  const ordered=entries.filter(entry=>range==='all'||inWeek(entry,period,week)).map((entry,index)=>({entry,index})).sort((a,b)=>{
    const needsWork=(row:Row)=> /needs[_ ]work|fail|improve/i.test(row.marker || row.assessment || row.verdict || row.state || '') ? 0 : 1;
    const priority=(row:Row)=> typeof row.importance === 'number' ? row.importance : typeof row.priority === 'number' ? row.priority : ({high:0,medium:1,low:2} as Row)[row.importance || row.priority] ?? 3;
    return needsWork(a.entry)-needsWork(b.entry) || priority(a.entry)-priority(b.entry) || String(reviewDate(b.entry) || '').localeCompare(String(reviewDate(a.entry) || '')) || a.index-b.index;
  }).map(({entry})=>entry);
  const unknownDates=entries.filter(entry=>!reviewDate(entry)&&!entry.week).length;
  return <section className="an-review-section" id={`conversations-${kind}`}><div className="an-section-heading"><h2>{name}</h2><label className="an-range">Period <select value={range} onChange={event=>{setRange(event.target.value);setAll(false);}}><option value="week">This week</option><option value="all">All dates</option></select></label></div>{ordered.length ? <div className="an-review-rows">{(all?ordered:ordered.slice(0,3)).map((entry,i)=>{
    const id=entry.lead_id || entry.id,job=jobs.find(row=>String(row.id)===String(id));
    const title=job?.title || entry.job_title || entry.title || entry.label || 'Job title unavailable';
    const marker=entry.marker || entry.assessment || entry.verdict || entry.state;
    const status=entry.reviewable===false ? 'Not reviewed' : /needs[_ ]work|fail|improve/i.test(marker || '') ? 'Needs work' : /keep|pass/i.test(marker || '') ? 'Keep' : 'Assessment unknown';
    return <button key={`${id || 'review'}-${i}`} onClick={()=>choose({title,period:entry.period || reviewDate(entry),evidence:entry.evidence || (id?[id]:[]),...(kind==='calls'?{call:entry}:{review:entry,kind})})}><strong>{plain(title)}</strong><span>{entry.reviewable===false ? kind==='calls' ? 'Transcript missing. Paste the full call transcript to review it.' : missing[kind] : shortFinding(entry)}</span><small><b className="an-chip">{status}</b> {plain(reviewDate(entry) || 'Date unknown')} →</small></button>;
  })}</div> : <Empty>{entries.length && range==='week' ? 'No dated entries for this week. Choose All dates to see earlier entries. ' : ''}{missing[kind]}</Empty>}{range==='week' && unknownDates>0 && <p className="an-meta">{unknownDates} {unknownDates===1?'entry has':'entries have'} no date. Choose All dates to inspect them.</p>}{ordered.length>3 && <button className="an-text-button" aria-expanded={all} onClick={()=>setAll(!all)}>{all?'Show fewer':`Show all ${ordered.length}`}</button>}</section>;
}
export default function AnalyticsPage() {
  const {state,openDrawer,drawerId}=useCockpit();
  const [tab,setTab]=useState(0),[selection,setSelection]=useState<Selection|null>(null);
  const tabs=useRef<(HTMLButtonElement|null)[]>([]);
  const go=(index:number)=>{setTab(index);tabs.current[index]?.focus();};
  if(!state)return null;
  const analytics=state.analytics || {},snapshot=analytics.latest,jobs=list(state.jobs);
  if(!snapshot)return <section className="an-shell"><h1>Your weekly analytics</h1><Empty>No saved weekly review yet. Run <code>/analytics</code> to review your evidence and agree your focus.</Empty></section>;
  const p:AnalyticsPresentation & Row=snapshot.presentation || {},progress:Row=p.progress_strip || p.progress || {},north=snapshot.north_star || {},verdict=snapshot.verdict || {},periods=snapshot.periods || {},conversations:Row=snapshot.conversations || p.conversations || {};
  const activeGoals=list(analytics.goals?.goals || analytics.goals);
  const goals=(analytics.goals_week ? activeGoals : list(snapshot.goals_next).length ? list(snapshot.goals_next) : activeGoals.length ? activeGoals : list(p.goal_cards)).map(goal => ({...goal,...list(p.goal_cards).find(card => goalMatches(goal,card))})).filter((goal,index,all)=>all.findIndex(other=>String(other.goal_id || other.change || other.text || other.kpi).trim().toLowerCase()===String(goal.goal_id || goal.change || goal.text || goal.kpi).trim().toLowerCase())===index);
  const change='biggest_change' in progress ? progress.biggest_change : p.biggest_change ?? p.biggest_gain, newest='newest_badge' in progress ? progress.newest_badge : p.newest_badge;
  const legacy:Row=(p as Row).voyage || {},badges=list(p.badges || progress.badges || legacy.stations || snapshot.badge_catalogue || snapshot.badges),history=[...list(p.goals_history),...list(legacy.goals_history),...list(legacy.goal_history),...list(analytics.history)].flatMap(row=>Array.isArray(row.goals_review)?row.goals_review.map((goal:Row)=>({...goal,week:row.week})):row);
  const sections=conversations.sections || conversations;
  const calls=list(sections.calls || snapshot.call_cards),reviews=snapshot.reviews || {};
  const entries:Row={applications:list(sections.applications || reviews.application?.entries || reviews.application?.items),chats:list(sections.chats || snapshot.conversation_review?.threads || reviews.conversation?.threads),calls,proposals:list(sections.proposals || reviews.proposal?.entries || reviews.proposal?.items)};
  // One repeated finding belongs to its first stage; distinct evidence still has its row.
  const seenFindings=new Set<string>();
  for(const kind of ['applications','chats','calls','proposals'])entries[kind]=entries[kind].filter((entry:Row)=>{
    if(entry.duplicate_of_stage)return false;
    if(entry.reviewable===false)return true;
    if(!(entry.key_finding || entry.finding || entry.preview || entry.coach_read_preview || entry.fix))return true;
    const finding=shortFinding(entry).toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
    const key=`${entry.lead_id || entry.id}:${finding}`;
    if(!finding||seenFindings.has(key))return !finding;
    seenFindings.add(key);return true;
  });
  const patterns=list(conversations.patterns || p.conversation_patterns).slice(0,3);
  const score=snapshot.funnel_score || {},savedHistory=list(analytics.history).filter(row=>row.week!==snapshot.week);
  const scoreHistory=list(progress.score_history || p.score_history || score.history || [...savedHistory.map(row=>({week:row.week,value:row.funnel_score?.score ?? null})),{week:snapshot.week,value:score.score ?? null}]).slice().sort((a,b)=>String(a.week).localeCompare(String(b.week)));
  const allScoreHistory=[...savedHistory.map(row=>({week:row.week,value:row.funnel_score?.score ?? null})),...scoreHistory,{week:snapshot.week,value:score.score ?? null}].filter((row,index,all)=>all.findLastIndex(other=>other.week===row.week)===index).sort((a,b)=>String(a.week).localeCompare(String(b.week)));
  const rawRank:Row=(typeof p.rank==='object' && p.rank) || p.rank_progress || (typeof snapshot.rank==='object' && snapshot.rank) || snapshot.rank_progress || legacy.rank_progress || {};
  const rank:Row={...rawRank,name:rawRank.name || rawRank.rank || (typeof p.rank==='string'?p.rank:null) || (typeof snapshot.rank==='string'?snapshot.rank:null),next_name:rawRank.next_name || rawRank.next_rank};
  const priorGoals=list(snapshot.goals_review), endedGoals=priorGoals.filter(prior=>!goals.some(goal=>goalMatches(goal,prior)));
  const awards=list(snapshot.badge_awards || snapshot.awards || (snapshot.badges?.awards));
  const newAward=newest && ((newest.earned_week || newest.week || newest.as_of_week || (/^\d{4}-W\d{2}$/.test(newest.as_of || '') ? newest.as_of : null))===snapshot.week || awards.some(award=>(award.badge || award.name)===(newest.badge || newest.name) && award.tier===newest.tier && (award.week || award.earned_week || award.as_of_week)===snapshot.week)) ? newest : null;
  const changeUnit=change?.unit || snapshot.kpis?.[change?.key]?.unit || list(p.scorecard).find(row=>row.key===change?.key)?.series?.unit || (/^(reply_rate|reply_to_call|booked_to_held|proposal_to_won|invite_to_call|offer_to_contract|speed_10min|job_fit|follow_ups_on_time|proposal_on_time)$/.test(change?.key || '') ? '%' : '');
  const changeValue=(value:any)=>value==null?'unknown':changeUnit==='$'||changeUnit==='currency'?money(value,change?.currency || north.currency):`${Math.round(value)}${changeUnit==='%'?'%':changeUnit==='min'?' min':changeUnit==='s'?' s':''}`;
  const changeText=change?.previous==null ? 'Comparison unavailable' : change?.value!=null ? `${plain(change.name || change.label || change.key)} ${changeValue(change.previous)} → ${changeValue(change.value)}` : plain(change.text || change.sentence || 'Comparison unavailable');
  const live=snapshot.report_facts?.live || {}, proposals=live.proposals, quiet=live.quiet_to_reopen ?? live.chats;
  const startHere=proposals==null ? 'Start here: add the missing Upwork records to check open deals.' : proposals>0 ? `Start here: ask your ${proposals} open ${proposals===1?'proposal':'proposals'} what is holding up the decision and agree a date.` : 'Start here: review your open chats and complete the agreed next step.';
  const choose=(value:Selection)=>setSelection(value);
  return <div className="an-shell"><div className="an-page-content">
    {snapshot.synthetic && <p className="an-sample-label">Example data. No member facts.</p>}
    <div className="an-tabs" role="tablist" aria-label="Weekly review">{TABS.map((name,i)=><button key={name} ref={node=>{tabs.current[i]=node;}} id={`analytics-tab-${i}`} role="tab" aria-selected={tab===i} aria-controls={`analytics-panel-${i}`} tabIndex={tab===i?0:-1} onClick={()=>setTab(i)} onKeyDown={event=>{let index=i;if(event.key==='ArrowRight'||event.key==='ArrowLeft')index=(i+(event.key==='ArrowRight'?1:-1)+TABS.length)%TABS.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=TABS.length-1;else return;event.preventDefault();go(index);}}>{name}</button>)}</div>
    <details className="an-methodology"><summary aria-label="How this review is measured" title="How this review is measured">ⓘ</summary><div><p>{periodText(periods.activity || snapshot.window)}. Funnel results compare the last 28 days with the 28 days before. Finished cases count; pending cases stay separate.</p><p>Last sync {plain(periods.synced_at || state.sync?.synced_at || 'not recorded')}. Next review {plain(p.next_run_day || analytics.next_run_day || 'Monday')}.</p>{list(snapshot.coverage?.missing).filter((gap,i,all)=>all.findIndex(other=>sourceLabel(other,jobs)===sourceLabel(gap,jobs) && sourceInstruction(other)===sourceInstruction(gap))===i).map((gap,i)=><p key={i}>{sourceLabel(gap,jobs)} unknown. {sourceInstruction(gap)}</p>)}</div></details>
    {(state.analytics_due || list(analytics.errors).length>0) && <p className="an-due">{state.analytics_due ? 'Weekly review due.' : 'Some saved evidence could not be read.'} Run <code>/analytics</code>. {list(analytics.errors).map(plain).join(' ')}</p>}
    <section role="tabpanel" id="analytics-panel-0" aria-labelledby="analytics-tab-0" hidden={tab!==0} tabIndex={0}>
      <p className="an-start-here">{startHere}</p>{quiet>0 && <p>Review {quiet} recent quiet {quiet===1?'chat':'chats'}. Follow up when you can add useful information or complete an agreed next step.</p>}
      <section className="an-progress-strip" aria-label="Weekly progress"><div className="an-progress-score"><span className="an-kicker">Funnel Score</span><strong>{score.score == null ? 'unknown' : Math.round(score.score)}<small>{score.previous!=null?`, was ${Math.round(score.previous)}`:''}</small></strong><Spark values={scoreHistory}/>{score.baseline_only && <small>Habits only until your baseline is set</small>}</div><div className="an-progress-won"><span className="an-kicker">Won this week</span><button className="an-text-button" onClick={()=>choose({title:'Won this week',period:periods.outcome || periods.activity,evidence:evidence(north),note:north.delta_text})}>{money(north.value,north.currency)}</button><small>{north.wins != null ? `${north.wins} new contracts. ` : ''}{snapshot.forecast?.next_30_days!=null ? `About ${money(snapshot.forecast.next_30_days,north.currency)} over the next 30 days, a guide` : 'Forecast unknown'}</small><details><summary>Value details</summary><p>{north.wins ?? 'unknown'} wins. {north.value_unknown_n ?? north.unknown_value_wins?.length ?? 'unknown'} with value unknown.</p><p>Billed this week: {money(north.billed_total ?? north.billed ?? north.hourly_billed,north.billed_currency || north.currency)}, separate from won value.</p>{list(north.other_currencies || north.other_totals).map((row,i)=><p key={i}>{money(row.value ?? row.known_subtotal,row.currency)} won in {row.currency}.</p>)}</details></div><div><span className="an-kicker">{(change?.kind || change?.direction)==='decline'?'Biggest decline':'Biggest gain'}</span>{change ? <><strong>{changeText}</strong><small>{change.previous==null ? 'No previous value recorded' : 'vs the 4 weeks before'}</small></> : <small>Comparison unavailable</small>}</div></section>
      {newAward && <aside className="an-new-badge"><BadgeImage badge={newAward}/><div><strong>Earned this week: {plain(newAward.name || newAward.badge)} · {plain(newAward.tier)}</strong><p>{plain(badgeProgress(newAward))}</p><button className="an-text-button" onClick={()=>go(2)}>All badges → Achievements</button></div></aside>}
      <section className="an-week-plan"><h1>This week: {plain(p.focus?.headline || verdict.headline || list(p.scorecard).find(row=>row.key===verdict.kpi)?.name || snapshot.kpis?.[verdict.kpi]?.label || 'Agree your focus in /analytics')}</h1><p>{plain(p.focus?.reason || verdict.reason || verdict.sentence || 'Reason unavailable')}</p><div className="an-goals">{goals.slice(0,3).map((goal,i)=>{
        const coach=Object.values(reviews).find((row:any)=>row.goal_ref && (row.goal_ref===goal.goal_id || row.goal_ref===goal.kpi)&&row.example) as Row|undefined;
        const example=goal.example_state==='unknown' ? null : goal.coach_example || goal.example || coach?.example;
        const prior=priorGoals.find(row=>goalMatches(goal,row));
        return <article className="an-goal" key={goal.goal_id || i}><h3>{plain(goal.title || goal.change || goal.text || 'Agreed goal')}</h3><p>{goal.when || goal.when_line ? plain(goal.when || goal.when_line) : goal.cue ? `${/^when\b/i.test(goal.cue)?plain(goal.cue):`When ${plain(goal.cue)}`}, ${plain(goal.action || 'agree the action in /analytics')}` : 'When to act: agree a cue in /analytics.'}</p>{example ? <blockquote>“{plain(example)}”</blockquote> : <p>{plain(goal.example_prompt || 'Save a matching quoted example, then run /analytics.')}</p>}<p>Checked: {plain(goal.measurement || goal.measurement_text || 'Save how to check this goal in /analytics.')}</p>{prior ? <div className="an-goal-check"><span className="an-kicker">Last week</span><PriorGoal goal={prior} choose={choose}/></div> : <p className="an-meta">New this week</p>}</article>;
      })}</div>{!goals.length&&<Empty>No agreed goals recorded. Run <code>/analytics</code> to agree one to three.</Empty>}{endedGoals.length>0 && <p className="an-ended-goals">Ended last week: {endedGoals.map(goal=>plain(goal.change || goal.text || 'Agreed goal')).join('; ')}. <button className="an-text-button" onClick={()=>choose({title:'Ended last week',note:endedGoals.map(goal=>`${plain(goal.change || goal.text)}: ${goal.done_k==null || goal.done_n==null?'Could not check yet':`did it ${goal.done_k} of ${goal.done_n}`}. ${plain(effectText(goal))}`).join(' '),evidence:endedGoals.flatMap(evidence)})}>Evidence →</button></p>}</section>
      <FunnelScorecard scorecard={list(p.scorecard)} kpis={snapshot.kpis || {}} jobs={jobs} currency={north.currency} choose={choose} onConversations={()=>go(1)}/>
    </section>
    <section role="tabpanel" id="analytics-panel-1" aria-labelledby="analytics-tab-1" hidden={tab!==1} tabIndex={0}><div className="an-section-heading an-conversations-heading"><h1>What helps the conversation move?</h1><button className="an-text-button" onClick={()=>go(0)}>See the funnel numbers →</button></div><section className="an-patterns"><h2>Across your conversations</h2>{patterns.length?patterns.map((pattern,i)=><article key={i}>{(list(pattern.quotes).length?list(pattern.quotes):pattern.quote?[{quote:pattern.quote}]:[]).slice(0,2).map((quote,j)=><Text key={j} value={`“${typeof quote==='string'?quote:quote.quote || quote.text}”`} verbatim label="Read supporting quote"/>)}<Text value={pattern.text || pattern.sentence || pattern.read} label="Read pattern"/></article>):<Empty>No cross-stage pattern supplied. Run <code>/analytics</code> after supplying the source conversations.</Empty>}</section>{[['Applications','applications'],['Chats','chats'],['Calls','calls'],['Proposals','proposals']].map(([name,kind])=><ReviewSection name={name} kind={kind} entries={entries[kind]} jobs={jobs} choose={choose} period={periods.activity || snapshot.window || {}} week={snapshot.week} key={kind}/>)}</section>
    <section role="tabpanel" id="analytics-panel-2" aria-labelledby="analytics-tab-2" hidden={tab!==2} tabIndex={0}><h1>Achievements</h1><section className="an-rank an-block"><h2>{plain(rank.name || 'Rank unavailable')}</h2>{rank.name ? <><p>Four-week rolling Funnel Score: {rank.rolling_score == null && rank.score == null ? 'unknown' : Math.round(rank.rolling_score ?? rank.score)}{rank.held_weeks!=null ? ` · ${rank.held_weeks} of ${rank.required_weeks || 4} weeks toward the next rank` : Number.isFinite(rank.weeks) ? ` · ${rank.weeks} weeks recorded` : ''}</p><p>{rank.next_name ? `Next: ${plain(rank.next_name)}${rank.next_threshold!=null ? ` at ${Math.round(rank.next_threshold)}` : ''}` : rank.state==='highest' || rank.name==='Admiral' ? 'Highest rank reached' : 'Next rank unavailable'}</p><ProgressBar value={Number.isFinite(rank.progress) ? rank.progress : progressValue(rank.progress)} label={`Score toward ${rank.next_name || 'next rank'}`}/><small className="an-meta">Score toward {plain(rank.next_name || 'the next rank')}. Weeks held are counted above.</small></> : <Empty>Run <code>/analytics</code> to record your four-week rank.</Empty>}</section><section className="an-block"><h2>Treasure map</h2><p className="an-meta">All {badges.length} badge islands. Open an island for its rule.</p><div className="an-badge-map" aria-label="All badge islands">{badges.map((badge,i)=><Badge badge={badge} key={`${badge.name || badge.badge || i}-${badge.tier || 'locked'}-${i}`}/>)}</div>{!badges.length&&<Empty>Badge catalogue unavailable. Run <code>/analytics</code> to load it.</Empty>}</section><section className="an-block"><h2>Funnel Score over all weeks</h2><Spark values={allScoreHistory} allWeeks/></section><section className="an-block an-goal-history"><h2>Goals that worked</h2>{[...history,...priorGoals.map(goal=>({...goal,week:snapshot.week}))].filter((goal,index,all)=>all.findIndex(other=>other.goal_id===goal.goal_id && other.week===goal.week)===index).filter(goal=>goal.effect==='worked' || goal.effect==='improved').map((goal,i)=><div key={`${goal.goal_id || i}-${goal.week}`}><p className="an-meta">{plain(goal.week || 'Week unknown')}</p><PriorGoal goal={goal} choose={choose}/></div>)}{![...history,...priorGoals].some(goal=>goal.effect==='worked'||goal.effect==='improved')&&<Empty>No goal has a recorded improvement yet. Keep reviewing execution and results in /analytics.</Empty>}</section></section>
  </div>{selection && !drawerId && <SelectionDrawer key={selection.title} value={selection} close={()=>setSelection(null)} jobs={jobs} calls={calls} openLead={id=>{setSelection(null);openDrawer(id);}}/>}</div>;
}
