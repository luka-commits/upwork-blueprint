'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useCockpit } from '@/lib/context';
import FunnelScorecard from './FunnelScorecard';
import AnalyticsConversations, { CallMoments } from './AnalyticsConversations';
import { readAnalyticsReturn, restoreAnalyticsReturnScroll } from '@/lib/analytics-navigation';
import AnalyticsAchievements, { effectWords } from './AnalyticsAchievements';
import CopyButton from './CopyButton';
import { analyticsMemberText, type AnalyticsPresentation } from '@/lib/analytics-contract';

type Row = Record<string, any>;
type Selection = { title: string; period?: any; evidence?: any[]; note?: string; call?: Row; review?: Row; kind?: string; };
const TABS = ['This week', 'Conversations', 'Achievements'];
const POINT_NAMES = ['Opening and agenda', 'Current state', 'Problem and cost', 'Goal and scope', 'Budget before price', 'Decision maker and timeline', 'Why you', 'Objections', 'Next step on Upwork'];
const list = (value: any): Row[] => Array.isArray(value) ? value : [];
const plain = analyticsMemberText;
const evidence = (row: Row = {}) => list(row.evidence || row.evidence_lead_ids || row.lead_ids);
const periodText = (value: any) => !value ? 'Period unavailable' : typeof value === 'string' ? plain(value) : `${value.start || 'Unknown start'} to ${value.end || 'Unknown end'}`;
const effectText = (goal: Row) => goal.effect_text || ({worked:'Improvement observed',not:'No improvement observed',undecided:'Too early to tell'} as Row)[goal.effect] || 'Effect unknown';
/** Member copy without the measurement-window phrasing: "14 of 20 reached a booking", nothing more. */
const tidy = (value: any) => plain(value).replace(/\s+(?:in|within|over) the (?:observed )?(?:last )?\d*-?(?:day )?window\b/gi, '');
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const checkDay = (iso: any) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return '';
  const date = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return `${DAYS[date.getUTCDay()]} ${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`;
};
const lowerFirst = (text: string) => /^[A-Z][a-z]/.test(text) ? text[0].toLowerCase() + text.slice(1) : text;
const whenDo = (goal: Row) => goal.when || goal.when_line ? plain(goal.when || goal.when_line)
  : goal.cue ? `${/^(when|before|after|once|if|while|as)\b/i.test(goal.cue) ? plain(goal.cue) : `When ${lowerFirst(plain(goal.cue))}`} → ${lowerFirst(plain(goal.action || 'agree the action in /analytics'))}`
    : 'Agree a cue in /analytics.';
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
export function CallCard({card: savedCard,showTitle=true}: {card: Row;showTitle?:boolean}) {
  const {api} = useCockpit();
  const [current,setCurrent] = useState<Row | null>(null);
  const id = savedCard.lead_id || savedCard.id;
  useEffect(() => { let active = true;setCurrent(null);if(id) void api(`/api/job/${encodeURIComponent(id)}`).then(result => {const latest=list(result.data?.call_cards).find(row => String(row.lead_id || row.id) === String(id));if(active && result.ok && latest)setCurrent(latest);});return () => {active=false;};},[api,id]);
  const card = current || savedCard, rawPoints = card.points || card.review_points || card.rubric || {};
  const points:Row[] = Array.isArray(rawPoints) ? rawPoints : Object.entries(rawPoints).map(([point,value])=>({...value as Row,point:(value as Row)?.point ?? point}));
  const read = card.coach_read || card.free_read || (typeof card.read==='string' ? card.read : null);
  const message = typeof card.next_message === 'object' ? card.next_message?.text : card.next_message;
  const tooLong = typeof message === 'string' && message.trim().split(/\s+/).length > 100;
  const next = card.agreed_step || card.next_step;
  return <article className="an-call-card">
    <p className="an-kicker">Call reviewed {plain(card.reviewed_at || card.as_of || card.date || card.call_date || 'date unknown')}</p>{showTitle && <h3>{plain(card.label || card.title || 'Call review')}</h3>}
    {typeof card.call_score?.score === 'number' && <p className="an-meta">Call score {card.call_score.score}{card.call_score.applicable ? `, ${card.call_score.met} of ${card.call_score.applicable} points met${card.call_score.partly ? `, ${card.call_score.partly} partly` : ''}` : ''}</p>}
    <section className="an-coach-read"><h4>Coach's read</h4>{read ? <FullText value={read}/> : <div className="an-empty">Not reviewed. <FullText value={card.coach_read_prompt || card.source_prompt || `Paste the full transcript, then run /call-review ${id}.`}/></div>}</section>
    <CallMoments card={card}/>
    {card.reviewable === false && <Empty>{plain(card.reason || 'Transcript missing.')} {plain(card.source_prompt || `Paste the full transcript, then run /call-review ${id}.`)}</Empty>}
    <section className="an-next-message"><h4>Next message</h4>{message && !tooLong ? <><FullText value={message} className="an-message" verbatim/>{card.next_message?.missing_inputs?.length ? <Text value={card.next_message.missing_inputs.join(', ')} label="Inputs needed before sending"/> : <CopyButton text={message} label="Copy message"/>}</> : <Empty>{tooLong ? 'The saved draft is over 100 words. Run' : card.next_message_state === 'not_needed' ? 'No useful message remains.' : 'No next message supplied. Run'}{card.next_message_state !== 'not_needed' && <> <code>/call-review {id}</code> for a ready draft.</>}</Empty>}</section>
    <section className="an-next-step"><h4>Agreed step</h4>{next && typeof next === 'object' ? <><FullText value={next.quote || next.action || next.text} verbatim={!!next.quote}/><p className="an-meta">{plain(next.owner || 'Owner not recorded')} · {plain(next.when || next.at || 'Time not recorded')} · {next.agreed ? 'Client agreed' : plain(next.agreement || 'Agreement not recorded')}</p></> : <FullText value={plain(next || 'Agreed step unknown')}/>}</section>
    <details className="an-points-scan"><summary>Nine points</summary><ol className="an-review-points">{POINT_NAMES.map((name,i) => {const point=points.find(row => Number(row.point || row.number || row.id)===i+1) || points[i];return <li key={name}><strong>{name}</strong> <span className="an-chip">{plain(point?.state?.replace(/_/g,' ') || 'unknown')}</span>{point?.definition && <FullText value={point.definition}/>} {point?.quote ? <SourceQuote value={point.quote} at={point.quote_at || ''}/> : <p>Supporting quote unknown.</p>}{point?.reason && <FullText value={plain(point.reason)}/>}</li>;})}</ol></details>
    {id && <p><a href={`/files/${encodeURIComponent(id)}/call.md`} target="_blank" rel="noreferrer">Open full transcript →</a></p>}
  </article>;
}
const CHAT_POINTS: Row = {answered_question:"Answered the client's question", qualifying_question:'Qualifying question', call_proposal:'Call proposal when useful'};
export function ReviewCard({review,kind,job = {}}: {review:Row;kind?:string;job?:Row}) {
  const points = review.points || review.rubric || {};
  const normalized = Array.isArray(points) ? points.map((p:Row) => ({...p,key:p.key || p.id || p.point})) : Object.entries(points).map(([key,p]) => ({...(p as Row),key}));
  const allowed = normalized.map((p:Row)=>({...p,key:p.key==='call_times'?'call_proposal':kind==='chats' && Number.isInteger(Number(p.key)) ? Object.keys(CHAT_POINTS)[Number(p.key)-1] : p.key})).filter((p:Row)=>kind!=='chats'||Object.keys(CHAT_POINTS).includes(p.key));
  return <article className="an-content-review"><p className="an-meta">As of {plain(review.as_of || review.reviewed_at || review.date || 'date unavailable')}</p><h3>Coach's read</h3>{review.coach_read || review.free_read || (typeof review.read==='string' ? review.read : null) || review.friction ? <Text value={review.coach_read || review.free_read || (typeof review.read==='string' ? review.read : null) || review.friction}/> : <Empty>Read unknown. {review.source_prompt || review.how_to_supply || 'Supply the full source, then run /analytics.'}</Empty>}
    {review.interpretation && <Text value={review.interpretation}/>} {review.unknown && <Text value={review.unknown}/>}
    {review.quote && <SourceQuote value={review.quote}/>}{review.fix && <><h4>One change</h4><Text value={review.fix}/></>}{review.example && <SourceQuote value={review.example}/>}{review.next_message && <><h4>Next message</h4><FullText verbatim className="an-message" value={typeof review.next_message==='string'?review.next_message:review.next_message.text}/></>}
    {kind === 'chats' && <p className="an-meta">Last writer: {plain(review.last_writer)}</p>}
    {allowed.length > 0 && <details><summary>{kind === 'chats' ? 'Content checks' : 'Review scan'}</summary>{allowed.map((point:Row,i:number) => <section key={point.key || i}><h4>{CHAT_POINTS[point.key] || plain(point.label || point.name || point.key || `Point ${i+1}`)}</h4><p>{plain(point.state || point.status)}</p>{point.quote && <SourceQuote value={point.quote}/>}{point.reason && <Text value={point.reason}/>}</section>)}</details>}
    {list(review.missing_sources).map((gap,i) => <FullText key={i} value={`${sourceLabel(typeof gap==='object'?gap:{source:gap})} unknown. ${sourceInstruction(typeof gap==='object'?gap:{source:gap})}`}/>)}
  </article>;
}
/** One line: mark, "did it k of n", the effect in a few words. */
function PriorGoal({goal,choose,showTitle=false}: {goal:Row;choose:(s:Selection)=>void;showTitle?:boolean}) {
  const k=goal.done_k,n=goal.done_n,known=typeof k==='number'&&typeof n==='number';
  const checked = n === 0 ? 'nothing came up' : !known ? 'not checked yet' : `did it ${k} of ${n}`;
  const [mark,label] = !known || n===0 ? ['·','Goal check'] : k===n ? ['✓','Goal carried out'] : k===0 ? ['✗','Goal not carried out'] : ['◐','Goal partly carried out'];
  return <article className="an-prior-goal"><p><span aria-label={label}>{mark}</span> {showTitle && <><strong>{plain(goal.change || goal.text || 'Agreed goal')}</strong> · </>}{checked} · {effectWords(goal)}</p><button className="an-text-button" onClick={() => choose({title:goal.change || 'Goal review',period:goal.period,evidence:evidence(goal),note:[effectText(goal),goal.effect_note,goal.decision,goal.two_weeks_undone ? goal.fallback : null].filter(Boolean).join(' ')})}>Evidence →</button></article>;
}
export const goalMatches = (goal:Row, other:Row) => {
  if (goal.goal_id && goal.goal_id===other.goal_id) return true;
  if ([goal.continues_goal_id,goal.previous_goal_id,goal.continued_from_goal_id].includes(other.goal_id) && other.goal_id) return true;
  if (goal.goal_id && other.goal_id) return false;
  const normalize=(value:any)=>String(value || '').trim().toLowerCase().replace(/\s+/g,' ');
  const change=normalize(goal.change || goal.text || goal.title), previous=normalize(other.change || other.text || other.title);
  return !!change && change===previous && (!goal.kpi || !other.kpi || goal.kpi===other.kpi) && (!goal.action || !other.action || normalize(goal.action)===normalize(other.action));
};
export default function AnalyticsPage() {
  const {state,openAnalyticsLeads,closeDrawer}=useCockpit();
  const [tab,setTab]=useState(0);
  useEffect(()=>{const saved=readAnalyticsReturn();if(saved){setTab(saved.tab);restoreAnalyticsReturnScroll();}closeDrawer?.();},[closeDrawer]);
  const tabs=useRef<(HTMLButtonElement|null)[]>([]);
  const go=(index:number)=>{closeDrawer?.();setTab(index);tabs.current[index]?.focus();};
  if(!state)return null;
  const analytics=state.analytics || {},snapshot=analytics.latest,jobs=list(state.jobs);
  if(!snapshot)return <section className="an-shell"><h1>Your weekly analytics</h1><Empty>No weekly review yet. Run <code>/analytics</code>.</Empty></section>;
  const p:AnalyticsPresentation & Row=snapshot.presentation || {},progress:Row=p.progress_strip || p.progress || {},north=snapshot.north_star || {},verdict=snapshot.verdict || {},periods=snapshot.periods || {},conversations:Row=snapshot.conversations || p.conversations || {};
  const activeGoals=list(analytics.goals?.goals || analytics.goals);
  const goals=(analytics.goals_week ? activeGoals : list(snapshot.goals_next).length ? list(snapshot.goals_next) : activeGoals.length ? activeGoals : list(p.goal_cards)).map(goal => ({...goal,...list(p.goal_cards).find(card => goalMatches(goal,card))})).filter((goal,index,all)=>all.findIndex(other=>String(other.goal_id || other.change || other.text || other.kpi).trim().toLowerCase()===String(goal.goal_id || goal.change || goal.text || goal.kpi).trim().toLowerCase())===index);
  const legacy:Row=(p as Row).voyage || {},badges=list(p.badges || progress.badges || legacy.stations || snapshot.badge_catalogue || snapshot.badges),history=[...list(p.goals_history),...list(legacy.goals_history),...list(legacy.goal_history),...list(analytics.history)].flatMap(row=>Array.isArray(row.goals_review)?row.goals_review.map((goal:Row)=>({...goal,week:row.week})):row);
  const sections=conversations.sections || conversations;
  const calls=list(sections.calls || snapshot.call_cards),reviews=snapshot.reviews || {};
  const entries:Row={chats:list(sections.chats || snapshot.conversation_review?.threads || reviews.conversation?.threads),calls};
  const patterns=list(conversations.patterns || p.conversation_patterns);
  const score=snapshot.funnel_score || {},savedHistory=list(analytics.history).filter(row=>row.week!==snapshot.week);
  const scoreHistory=list(progress.score_history || p.score_history || score.history || [...savedHistory.map(row=>({week:row.week,value:row.funnel_score?.score ?? null})),{week:snapshot.week,value:score.score ?? null}]).slice().sort((a,b)=>String(a.week).localeCompare(String(b.week)));
  const allScoreHistory=[...savedHistory.map(row=>({week:row.week,value:row.funnel_score?.score ?? null})),...scoreHistory,{week:snapshot.week,value:score.score ?? null}].filter((row,index,all)=>all.findLastIndex(other=>other.week===row.week)===index).sort((a,b)=>String(a.week).localeCompare(String(b.week)));
  const rawRank:Row=(typeof p.rank==='object' && p.rank) || p.rank_progress || (typeof snapshot.rank==='object' && snapshot.rank) || snapshot.rank_progress || legacy.rank_progress || {};
  const rank:Row={...rawRank,name:rawRank.name || rawRank.rank || (typeof p.rank==='string'?p.rank:null) || (typeof snapshot.rank==='string'?snapshot.rank:null),next_name:rawRank.next_name || rawRank.next_rank};
  const priorGoals=list(snapshot.goals_review),titleOf=(goal:Row)=>String(goal.change || goal.text || goal.title || '').trim().toLowerCase().replace(/\s+/g,' ');
  // A card shows its own last-week line; a goal whose id changed but whose title carried on still counts as that card's.
  const priorFor=(goal:Row)=>priorGoals.find(row=>goalMatches(goal,row)) || [...priorGoals].reverse().find(row=>titleOf(row) && titleOf(row)===titleOf(goal));
  const endedTitles=new Set<string>(goals.slice(0,3).flatMap(goal=>[titleOf(goal)]));
  const endedGoals=[...priorGoals].reverse().filter(prior=>{const title=titleOf(prior);if(!title || endedTitles.has(title))return false;endedTitles.add(title);return true;}).reverse().slice(0,3);
  const accountability:Row={...(p.accountability || {}),...(snapshot.accountability || {})};
  if (!accountability.application_streak) accountability.application_streak={current:snapshot.streak_weeks ?? p.streak_weeks ?? legacy.streak_weeks,best:snapshot.best_streak_weeks ?? p.best_streak_weeks ?? legacy.best_streak_weeks};
  const live=snapshot.report_facts?.live || {}, proposals=live.proposals;
  const startHere=proposals==null ? 'Add the missing Upwork records' : proposals>0 ? `Agree a decision date for ${proposals} open ${proposals===1?'proposal':'proposals'}` : 'Complete the next step in your open chats';
  const proposalIds=list(live.proposal_lead_ids || live.proposals_lead_ids || live.proposal_ids || live.proposals_evidence || snapshot.kpis?.held_to_proposal?.live_lead_ids).map((row:any)=>String(typeof row==='object'?row.lead_id || row.id:row));
  const openJobs=jobs.filter(job=>!job.imported && ['applied','replied','call','offer'].includes(job.status));
  const startIds=proposals>0 ? proposalIds.length ? proposalIds : openJobs.filter(job=>!!job.proposal_sent_at).map(job=>String(job.id)) : list(live.quiet_lead_ids || live.chat_lead_ids).length ? list(live.quiet_lead_ids || live.chat_lead_ids).map((row:any)=>String(typeof row==='object'?row.lead_id || row.id:row)) : openJobs.filter(job=>job.status==='replied'&&!job.proposal_sent_at).map(job=>String(job.id));
  const choose=(value:Selection)=>openAnalyticsLeads(list(value.evidence).map((item:any)=>String(typeof item==='object'?item.lead_id || item.id:item)));
  return <div className="an-shell"><div className="an-page-content">
    {snapshot.synthetic && <p className="an-sample-label">Example data. No member facts.</p>}
    <div className="an-tabs" role="tablist" aria-label="Weekly review">{TABS.map((name,i)=><button key={name} ref={node=>{tabs.current[i]=node;}} id={`analytics-tab-${i}`} role="tab" aria-selected={tab===i} aria-controls={`analytics-panel-${i}`} tabIndex={tab===i?0:-1} onClick={()=>go(i)} onKeyDown={event=>{let index=i;if(event.key==='ArrowRight'||event.key==='ArrowLeft')index=(i+(event.key==='ArrowRight'?1:-1)+TABS.length)%TABS.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=TABS.length-1;else return;event.preventDefault();go(index);}}>{name}</button>)}</div>
    <details className={`an-methodology${tab===1 ? ' an-methodology-inline' : ''}`}><summary aria-label="How this review is measured" title="How this review is measured">ⓘ</summary><div><p>{periodText(periods.activity || snapshot.window)}. Rates compare the last 28 days with the 28 days before; open cases stay separate.</p><p>Last sync {plain(periods.synced_at || state.sync?.synced_at || 'not recorded')}. Next review {plain(p.next_run_day || analytics.next_run_day || 'Monday')}.</p>{list(snapshot.coverage?.missing).filter((gap,i,all)=>all.findIndex(other=>sourceLabel(other,jobs)===sourceLabel(gap,jobs) && sourceInstruction(other)===sourceInstruction(gap))===i).map((gap,i)=><p key={i}>{sourceLabel(gap,jobs)} unknown. {sourceInstruction(gap)}</p>)}</div></details>
    {(state.analytics_due || list(analytics.errors).length>0) && <p className="an-due">{state.analytics_due ? 'Weekly review due.' : 'Some saved evidence could not be read.'} Run <code>/analytics</code>. {list(analytics.errors).map(plain).join(' ')}</p>}
    <section role="tabpanel" id="analytics-panel-0" aria-labelledby="analytics-tab-0" hidden={tab!==0} tabIndex={0}>
      <section className="an-week-plan"><p className="an-open-deals"><b>Open deals:</b> {startHere}. <button className="an-text-button" aria-label={proposals>0 ? `Show the ${proposals} ${proposals===1?'proposal':'proposals'}` : 'Show open chats'} onClick={()=>choose({title:proposals>0 ? `Open proposals (${proposals})` : 'Open chats',evidence:startIds})}>{proposals>0 ? 'Show them' : 'Show open chats'}</button></p><h1>This week: {plain(p.focus?.headline || verdict.headline || list(p.scorecard).find(row=>row.key===verdict.kpi)?.name || snapshot.kpis?.[verdict.kpi]?.label || 'Agree your focus in /analytics')}</h1>{(p.focus?.reason || verdict.reason || verdict.sentence) && <p>{tidy(p.focus?.reason || verdict.reason || verdict.sentence)}</p>}<div className="an-goals">{goals.slice(0,3).map((goal,i)=>{
        const coach=Object.values(reviews).find((row:any)=>row.goal_ref && (row.goal_ref===goal.goal_id || row.goal_ref===goal.kpi)&&row.example) as Row|undefined;
        const example=goal.example_state==='unknown' ? null : goal.coach_example || goal.example || coach?.example;
        const prior=priorFor(goal),day=checkDay(goal.review_on);
        return <article className="an-goal" key={goal.goal_id || i}><h3>{plain(goal.title || goal.change || goal.text || 'Agreed goal')}</h3><p>{whenDo(goal)}</p>{example ? <blockquote>“{plain(example)}”</blockquote> : <p>{plain(goal.example_prompt || 'No example quote yet. Run /analytics.')}</p>}{day && <p className="an-meta" title={plain(goal.measurement || goal.measurement_text || '') || undefined}>Check: {day}</p>}{prior && <div className="an-goal-check"><span className="an-meta">Last week</span><PriorGoal goal={prior} choose={choose}/></div>}</article>;
      })}</div>{!goals.length&&<Empty>No goals yet. Run <code>/analytics</code>.</Empty>}{endedGoals.length>0 && <div className="an-ended-goals"><span className="an-meta">Ended last week</span>{endedGoals.map((goal,i)=><PriorGoal key={goal.goal_id || i} goal={goal} choose={choose} showTitle/>)}</div>}</section>
      <FunnelScorecard scorecard={list(p.scorecard)} kpis={snapshot.kpis || {}} jobs={jobs} currency={north.currency} weekStart={periods.activity?.start} choose={choose} onConversations={()=>go(1)}/>
    </section>
    <section role="tabpanel" id="analytics-panel-1" aria-labelledby="analytics-tab-1" hidden={tab!==1} tabIndex={0}>
      <div className="an-section-heading an-conversations-heading"><h1>What helps the conversation move?</h1><button className="an-text-button" onClick={()=>go(0)}>See the funnel numbers →</button></div>
      <AnalyticsConversations entries={entries} patterns={patterns} criteria={conversations.criteria} jobs={jobs} period={periods.activity || snapshot.window || {}} week={snapshot.week} renderDetails={(entry,kind)=>kind==='calls' ? <CallCard card={entry}/> : <ReviewCard review={entry} kind={kind} job={jobs.find(job=>String(job.id)===String(entry.lead_id || entry.id))}/>}/>
    </section>
    <section role="tabpanel" id="analytics-panel-2" aria-labelledby="analytics-tab-2" hidden={tab!==2} tabIndex={0}>
      <AnalyticsAchievements score={{...score,history:allScoreHistory}} rank={rank} accountability={accountability} badges={badges} history={[...history,...priorGoals.map(goal=>({...goal,week:snapshot.week}))]} choose={choose} currency={north.currency}/>
    </section>
  </div></div>;
}
