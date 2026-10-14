'use client';

import { type CSSProperties, type ReactNode } from 'react';
import { analyticsMemberText as plain } from '@/lib/analytics-contract';

type Row = Record<string, any>;
type Ledger = { current: number; target: number; remaining: number; unit: string; percent: number; nextTier: string };
const list = (value: any): Row[] => Array.isArray(value) ? value : [];
const numeric = (value: any): value is number => typeof value === 'number' && Number.isFinite(value);
const slug = (value: any) => String(value).toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const TIERS = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Legend'];
const CATALOGUE = [
  ['Harbour Master', 'harbour'], ['First Mate', 'ship'], ['Treasure Hunter', 'treasure'],
  ['Swift Sail', 'hourglass'], ["Ship's Bell", 'bell'], ['Lookout', 'spyglass'],
  ['Steady Hand', 'anchor'], ['Quick Draw', 'cannon'], ['Message in a Bottle', 'bottle'],
  ['True North', 'compass'], ['Navigator', 'wheel'], ['Lighthouse Keeper', 'lighthouse'],
  ['First Doubloon', 'doubloon'], ['Back on Course', 'storm'],
];
const badgeName = (badge: Row) => badge.name || badge.badge || 'Badge';
const canonicalName = (badge: Row) => badgeName(badge) === 'Steady Anchor' ? 'Steady Hand' : badgeName(badge);
const earned = (badge: Row) => badge.locked !== true && badge.earned !== false && Boolean(badge.earned || badge.tier || badge.earned_week);
const tierClass = (badge: Row) => `an-tier-${earned(badge) ? slug(badge.tier || 'bronze') : 'locked'}`;

/** Read a recorded numeric ledger; descriptive progress strings are not data. */
export function badgeLedger(badge: Row): Ledger | null {
  const candidates = [badge.progress, badge.progress_to_next, typeof badge.next_tier === 'object' ? badge.next_tier?.progress || badge.next_tier : null];
  for (const progress of candidates) {
    if (!progress || typeof progress !== 'object') continue;
    const current = progress.current ?? progress.qualifying_weeks;
    const target = progress.target ?? progress.required_weeks;
    if (!numeric(current) || !numeric(target) || current < 0 || target <= 0) continue;
    const remaining = numeric(progress.remaining) ? Math.max(0, progress.remaining) : Math.max(0, target - current);
    const unit = typeof progress.unit === 'string' && progress.unit.trim() ? plain(progress.unit) : numeric(progress.qualifying_weeks) ? 'weeks' : 'units';
    const nextTier = typeof badge.next_tier === 'string' ? badge.next_tier : badge.next_tier?.tier || badge.next_tier?.name || progress.next_tier || progress.tier || '';
    return { current, target, remaining, unit, percent: Math.max(0, Math.min(100, current / target * 100)), nextTier: plain(nextTier || 'next tier') };
  }
  return null;
}

export function BadgeArt({ badge, size = 96 }: { badge: Row; size?: number }) {
  const name = badgeName(badge);
  const fallback = badge.fallback_image || `/badges/badge-${badge.motif || CATALOGUE.find(([label]) => label === name)?.[1] || 'compass'}.webp`;
  const image = /^\/badges\/(true-north|first-doubloon)-/.test(badge.image || '') ? fallback : String(badge.image || '').replace(/^\/badges\/steady-hand-/, '/badges/steady-anchor-');
  const artName = name === 'Steady Hand' ? 'Steady Anchor' : name;
  return <img className="an-badge-art" src={image || (earned(badge) ? `/badges/${slug(artName)}-${slug(badge.tier || 'bronze')}.webp` : fallback)} alt="" width={size} height={size} style={{width:size,height:size}} onError={event => {
    const node = event.currentTarget;
    if (!node.dataset.fallback) { node.dataset.fallback = 'true'; node.src = fallback; }
    else { node.style.visibility = 'hidden'; }
  }} />;
}

export function BadgeProgressRing({ badge, size = 128, children }: { badge: Row; size?: number; children?: ReactNode }) {
  const ledger = badgeLedger(badge), circumference = 2 * Math.PI * 45;
  return <span className={`an-badge-orbit ${tierClass(badge)}`} style={{width:size,height:size}}>
    <svg viewBox="0 0 100 100" aria-hidden="true"><circle className="an-badge-progress-track" cx="50" cy="50" r="45" fill="none" strokeWidth="3" />{ledger && <circle className="an-badge-progress-value" cx="50" cy="50" r="45" fill="none" strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - ledger.percent / 100)} transform="rotate(-90 50 50)" />}</svg>
    {children || <BadgeArt badge={badge} size={Math.max(64, size - 24)} />}
  </span>;
}

export function WorkingDays({ accountability }: { accountability: Row }) {
  const days = accountability?.working_days || accountability;
  return <span>{numeric(days?.k) && numeric(days?.n) ? `Applied on ${days.k} of ${days.n} working days this week` : 'Working days not recorded'}</span>;
}

function targetRange(target: any): { min: number; max: number } | null {
  if (numeric(target)) return {min: Math.max(0, Math.min(100,target)), max: 100};
  const min = target?.min ?? target?.lower ?? target?.from ?? target?.value;
  const max = target?.max ?? target?.upper ?? target?.to ?? 100;
  return numeric(min) && numeric(max) ? {min:Math.max(0, Math.min(100,min)),max:Math.max(0, Math.min(100,max))} : null;
}

/** The history uses 0–100; the small spark fits its measured range with padding. */
export function ScoreSpark({ values, allWeeks = false, target }: { values: any[]; allWeeks?: boolean; target?: any }) {
  const points = (allWeeks ? values : values.slice(-8)).map((point, index) => ({value:typeof point === 'object' && point !== null ? point.score ?? point.value : point, label: typeof point === 'object' && point !== null ? point.week || point.date || `Week ${index + 1}` : `Week ${index + 1}`}));
  const width = allWeeks ? Math.max(640, points.length * 46) : 180, height = allWeeks ? 220 : 56;
  const left = allWeeks ? 36 : 8, right = allWeeks ? 20 : 8, top = allWeeks ? 22 : 7, bottom = allWeeks ? 34 : 7;
  const x = (index: number) => left + (points.length === 1 ? .5 : index / Math.max(1, points.length - 1)) * (width - left - right);
  const finite = points.map(point=>point.value).filter(numeric);
  const low = allWeeks ? 0 : Math.max(0,Math.min(...finite)-5), high = allWeeks ? 100 : Math.min(100,Math.max(...finite)+5);
  const y = (value: number) => top + (high - Math.max(low, Math.min(high,value))) / Math.max(1,high-low) * (height - top - bottom);
  const lastIndex = points.findLastIndex(point => numeric(point.value)), band = targetRange(target);
  if (lastIndex < 0) return <p className="an-empty">Score history not recorded. Run <code>/analytics</code> to record a week.</p>;
  return <div className={allWeeks ? 'an-achievement-chart' : 'an-score-spark-wrap'}><svg className={allWeeks ? 'an-score-history an-achievement-score-chart' : 'an-score-spark'} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio={allWeeks ? 'none' : 'xMidYMid meet'} role="img" aria-label={`Funnel Score, ${allWeeks ? 'all recorded' : 'last eight'} weeks: ${points.map(point => numeric(point.value) ? `${point.label}: ${Math.round(point.value)}` : `${point.label}: unknown`).join(', ')}`}>
    {allWeeks && <>{[0,50,100].map(value => <g className="an-history-axis" key={value}><line x1={left} x2={width-right} y1={y(value)} y2={y(value)} /><text x={left-8} y={y(value)+3} textAnchor="end">{value}</text></g>)}{band && <g className="an-chart-target"><rect x={left} y={y(Math.max(band.min,band.max))} width={width-left-right} height={Math.max(2,Math.abs(y(band.min)-y(band.max)))} /><text x={width-right} y={y(Math.max(band.min,band.max))+12} textAnchor="end">Target {band.min}{band.max !== 100 && band.max !== band.min ? `–${band.max}` : '+'}</text></g>}</>}
    {points.map((point, index) => numeric(point.value) ? <g className="an-chart-point" key={`${point.label}-${index}`} tabIndex={0} aria-label={`${point.label}: Funnel Score ${Math.round(point.value)}`}>
      {index > 0 && numeric(points[index-1].value) && <line className="an-chart-line" x1={x(index-1)} y1={y(points[index-1].value)} x2={x(index)} y2={y(point.value)} />}
      <circle className={`an-chart-dot${index === lastIndex ? ' an-chart-last' : ''}`} cx={x(index)} cy={y(point.value)} r={index === lastIndex ? allWeeks ? 5 : 4 : allWeeks ? 3 : 2} />
      <circle className="an-chart-hit" cx={x(index)} cy={y(point.value)} r={allWeeks ? 13 : 8} fill="transparent"><title>{`${point.label}: Funnel Score ${Math.round(point.value)}`}</title></circle>
      {allWeeks && (points.length <= 12 || index === 0 || index === lastIndex || index % Math.ceil(points.length / 10) === 0) && <text className="an-history-label" x={x(index)} y={height-9} textAnchor="middle">{String(point.label).replace(/^\d{4}-/, '')}</text>}
    </g> : null)}
  </svg></div>;
}

function ledgerText(ledger: Ledger) {
  const singular = ledger.remaining === 1 ? ledger.unit.replace(/s$/, '') : ledger.unit;
  return `${ledger.remaining} more ${singular} to ${ledger.nextTier}`;
}

function ScoreRing({score}: {score: Row}) {
  const value = score.score ?? score.value, circumference = 2 * Math.PI * 58;
  return <div className="an-score-ring"><svg viewBox="0 0 144 144" aria-hidden="true"><circle cx="72" cy="72" r="58" className="an-badge-progress-track" fill="none" strokeWidth="7" />{numeric(value) && <circle cx="72" cy="72" r="58" className="an-badge-progress-value" fill="none" strokeWidth="7" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1-Math.max(0,Math.min(100,value))/100)} transform="rotate(-90 72 72)" />}</svg><div><span className="an-kicker">Funnel Score</span><strong>{numeric(value) ? Math.round(value) : 'Unknown'}</strong>{numeric(score.previous) && <small>was {Math.round(score.previous)}</small>}</div></div>;
}

function TreasureMap({badges}: {badges: Row[]}) {
  // The catalogue order is a route. Alternate rows reverse direction to connect it.
  const rows = Math.ceil(badges.length / 2), rowHeight = 230, mapHeight = rows * rowHeight;
  const widePoints = badges.map((_,index) => {const row=Math.floor(index/2),column=row%2 === 0 ? index%2 : 1-index%2; return `${column ? 750 : 250},${row*rowHeight+85}`;}).join(' ');
  const mobilePoints = badges.map((_,index) => `${index%2 ? 65 : 35},${index*rowHeight+82}`).join(' ');
  return <div className="an-treasure-sea" style={{'--route-rows':rows,'--route-row-height':`${rowHeight}px`,'--route-mobile-height':`${badges.length * rowHeight}px`} as CSSProperties}>
    <svg className="an-treasure-route an-route-wide" viewBox={`0 0 1000 ${mapHeight}`} preserveAspectRatio="none" aria-hidden="true"><polyline points={widePoints} fill="none" vectorEffect="non-scaling-stroke" /></svg>
    <svg className="an-treasure-route an-route-mobile" viewBox={`0 0 100 ${badges.length * rowHeight}`} preserveAspectRatio="none" aria-hidden="true"><polyline points={mobilePoints} fill="none" vectorEffect="non-scaling-stroke" /></svg>
    {badges.map((badge,index) => {const row=Math.floor(index/2),column=row%2 === 0 ? index%2 : 1-index%2, ledger=badgeLedger(badge);
      return <details id={`badge-${slug(badgeName(badge))}`} className={`an-island ${tierClass(badge)}${earned(badge)?'':' an-island-locked'}`} key={badgeName(badge)} style={{'--island-row':row+1,'--island-column':column+1,'--island-index':index+1,'--island-side':index%2 ? '65%' : '35%'} as CSSProperties}>
        <summary><span className="an-island-art"><BadgeArt badge={badge} size={112}/></span><strong>{plain(badgeName(badge))}</strong><small>{earned(badge) ? plain(badge.tier || 'Earned') : 'Not earned yet'}</small></summary>
        <div className="an-island-rule"><p>{plain(badge.exact_rule || badge.rule || badge.requirement || badge.criterion || 'Rule not recorded. Run /analytics to load the badge catalogue.')}</p>{badge.next_rule && <p>Next tier: {plain(badge.next_rule)}</p>}{earned(badge) && (badge.next_tier === null || badge.tier === 'Legend') ? <p>Highest tier reached</p> : ledger ? <p>{ledgerText(ledger)} · {ledger.current} of {ledger.target} {ledger.unit}</p> : badge.next_tier ? <p>Next tier progress not recorded.</p> : null}</div>
      </details>;
    })}
  </div>;
}

export default function AnalyticsAchievements({score,rank,accountability,badges,history,choose}: {score:Row;rank:Row;accountability:Row;badges:Row[];history:Row[];choose:(selection:any)=>void;currency?:string}) {
  const catalogue: Row[] = CATALOGUE.map(([name,motif]) => {
    const saved = badges.filter(badge => canonicalName(badge) === name).sort((a,b) => TIERS.indexOf(b.tier)-TIERS.indexOf(a.tier))[0];
    return saved ? {...saved,badge:name,name,motif:saved.motif || motif,earned:earned(saved),locked:!earned(saved)} : {badge:name,name,motif,earned:false,locked:true};
  });
  const next = catalogue.map(badge => ({badge,ledger:badgeLedger(badge)})).filter((row): row is {badge:Row;ledger:Ledger} => Boolean(row.ledger) && row.badge.next_tier !== null && row.badge.tier !== 'Legend').sort((a,b) => a.ledger.remaining/a.ledger.target-b.ledger.remaining/b.ledger.target || a.ledger.remaining-b.ledger.remaining || badgeName(a.badge).localeCompare(badgeName(b.badge))).slice(0,2);
  const streak = accountability?.application_streak || {};
  const current = streak.current ?? accountability?.streak_weeks, best = streak.best ?? accountability?.best_streak_weeks;
  const weeks = list(score.history || score.score_history);
  const target = score.target_band ?? score.target ?? rank.next_threshold;
  const worked = history.filter(goal => goal.effect === 'worked' || goal.effect === 'improved').filter((goal,index,all) => all.findIndex(other => (other.goal_id || other.change || other.text) === (goal.goal_id || goal.change || goal.text) && other.week === goal.week) === index);
  return <>
    <h1>Achievements</h1>
    <section className="an-achievement-hero"><ScoreRing score={score}/><div className="an-achievement-summary"><span className="an-kicker">Your voyage</span><h2>{plain(rank.name || rank.rank || 'Rank not recorded')}</h2><p className="an-steady-weeks">{numeric(current) ? `${current} ${current === 1 ? 'week' : 'weeks'} steady` : 'Steady weeks not recorded'}</p>{numeric(best) && <p>Best: {best} {best === 1 ? 'week' : 'weeks'}</p>}<p><WorkingDays accountability={accountability}/></p>{rank.next_name && <small>Next rank: {plain(rank.next_name)}</small>}</div></section>
    <section className="an-next-up an-block"><h2>Next up</h2><div className="an-next-badges">{next.map(({badge,ledger}) => <article className="an-next-badge" key={badgeName(badge)}><BadgeProgressRing badge={badge} size={148}/><div><h3>{plain(badgeName(badge))}</h3><p>{ledgerText(ledger)}</p><small>{ledger.current} of {ledger.target} {ledger.unit}</small></div></article>)}</div>{!next.length && <p className="an-empty">Next badge progress not recorded.</p>}</section>
    <section className="an-block"><h2>Treasure map</h2><p className="an-meta">All 14 badge islands. Open an island for its rule.</p><TreasureMap badges={catalogue}/></section>
    <section className="an-block"><h2>Funnel Score over all weeks</h2><ScoreSpark values={weeks} allWeeks target={target}/>{!targetRange(target) && <p className="an-meta">Score target not recorded.</p>}</section>
    <section className="an-block an-worked-goals"><h2>Goals that worked</h2>{worked.map((goal,index) => {const ids=list(goal.evidence || goal.evidence_lead_ids || goal.lead_ids);const effect=goal.effect_text || goal.effect_note || 'Improvement observed';return <article className="an-worked-goal" key={`${goal.goal_id || index}-${goal.week}`}><span className="an-goal-tick" aria-label="Recorded improvement">✓</span><div><small className="an-meta">{plain(goal.week || 'Week not recorded')}</small><h3>{plain(goal.change || goal.text || goal.title || 'Agreed goal')}</h3><p>{numeric(goal.done_k) && numeric(goal.done_n) ? `did it ${goal.done_k} of ${goal.done_n}` : 'Execution not recorded'}</p><p>{plain(effect)}</p><button className="an-text-button" onClick={() => choose({title:goal.change || goal.text || 'Goal review',period:goal.period,evidence:ids,note:plain(effect)})}>Evidence →</button></div></article>;})}{!worked.length && <p className="an-empty">No goal has a recorded improvement yet.</p>}</section>
  </>;
}
