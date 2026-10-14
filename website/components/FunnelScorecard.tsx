'use client';
import { Fragment, useEffect, useState } from 'react';
import { analyticsMemberText as plain } from '@/lib/analytics-contract';
type Row = Record<string, any>;
const fmt = (value: any, unit = '', currency?: string): string => value == null ? 'unknown' : typeof value === 'string' ? plain(value) : unit === '$' || unit === 'usd' || unit === 'currency' ? currency ? new Intl.NumberFormat('en-US', {style: 'currency', currency, maximumFractionDigits: 0}).format(value) : `${Math.round(value)} (currency unknown)` : `${new Intl.NumberFormat('en-US', {maximumFractionDigits: unit === '%' ? 0 : 1}).format(value)}${unit === '%' ? '%' : unit === 'min' ? ' min' : unit === 's' ? ' s' : ''}`;
export function weekDateLabel(value: any): string {
  const iso = /^(\d{4})-W(\d{2})$/.exec(String(value || ''));
  let date: Date;
  if (iso) { const jan4 = new Date(Date.UTC(+iso[1],0,4)); date = new Date(jan4); date.setUTCDate(jan4.getUTCDate()-(jan4.getUTCDay()+6)%7+(+iso[2]-1)*7); }
  else date = new Date(String(value).slice(0,10)+'T00:00:00Z');
  return Number.isNaN(date.valueOf()) ? 'Date unknown' : new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:'UTC'}).format(date);
}
function Development({ row, weekStart }: { row: Row; weekStart?: string }) {
  const points: any[] = row.series?.points || [], values = points.map(p => typeof p === 'object' && p !== null ? p.value : p);
  const steps: number[] = (row.target?.kind === 'ladder' ? row.target.thresholds || [] : [row.target?.value]).filter(Number.isFinite);
  const max = Math.max(1, ...values.filter(Number.isFinite), ...steps) * 1.18;
  const labels = points.map((point,index) => {
    if(point?.week || point?.date || row.series?.labels?.[index])return weekDateLabel(point?.week || point?.date || row.series.labels[index]);
    if(!weekStart)return 'Date unknown';
    const date = new Date(weekStart+'T00:00:00Z');date.setUTCDate(date.getUTCDate()-(points.length-1-index)*7);return weekDateLabel(date.toISOString());
  });
  const labelWidth=Math.max(52,...values.filter(Number.isFinite).map(v=>fmt(v,row.series?.unit,row.currency).length*7+12));
  const left=12, slot=labelWidth, plotWidth=Math.max(slot,points.length*slot), width=plotWidth+126;
  const y=(v:number)=>112-v/max*82, x=(i:number)=>left+(i+.5)*slot;
  if(!values.some(Number.isFinite))return <p className="an-empty">No trend yet.</p>;
  return <svg className="sc-development" viewBox={`0 0 ${width} 142`} role="img" aria-label={`${row.series?.label || row.name}: ${labels.map((label,i)=>`${label}: ${fmt(values[i],row.series?.unit,row.currency)}`).join(', ')}`}>
    {steps.map((step,index)=><g className="sc-step-band" key={index}><rect x={left} y={y(step)-4} width={plotWidth} height="8"/><text x={left+plotWidth+8} y={y(step)+3}>{row.target?.kind==='ladder'?`Step ${index+1}: `:'Goal: '}{fmt(step,row.series?.unit,row.currency)}</text></g>)}
    {values.map((v,i)=><g key={i}><title>{labels[i]}: {fmt(v,row.series?.unit,row.currency)}</title>{Number.isFinite(v) && <><rect x={x(i)-14} y={y(v)} width="28" height={112-y(v)} rx="4" fill={i===values.length-1?'var(--terracotta)':'var(--ring)'}/><text className="sc-value-label" x={x(i)} y={y(v)-8} textAnchor="middle">{fmt(v,row.series?.unit,row.currency)}</text></>}<text x={x(i)} y="133" textAnchor="middle">{labels[i]}</text></g>)}
  </svg>;
}
const STATE_WORD: Row = { pass: 'Met', fail: 'Behind', undecided: 'Early', missing: 'Unknown' };
export default function FunnelScorecard({ scorecard, kpis, jobs, currency, choose, onConversations, weekStart }: {scorecard: Row[]; kpis: Row; jobs: Row[]; currency?: string; choose: (selection: any) => void; onConversations: () => void; weekStart?: string}) {
  const [opened, setOpened] = useState<string[]>([]);
  useEffect(()=>{try{const saved=JSON.parse(sessionStorage.getItem('analytics-scorecard-open') || '[]');if(Array.isArray(saved)&&saved.every(key=>typeof key==='string'))setOpened(saved);}catch{/* Storage is optional. */}},[]);
  const toggle = (key: string) => setOpened(prev => {const next=prev.includes(key)?prev.filter(v=>v!==key):[...prev,key];try{sessionStorage.setItem('analytics-scorecard-open',JSON.stringify(next));}catch{/* Storage is optional. */}return next;});
  // One period label per block: habits read "This week", rates read "Last 28 days".
  const periods = scorecard.reduce<string[]>((all, row) => all.includes(row.period_label || '') ? all : [...all, row.period_label || ''], []).sort((a, b) => Number(b === 'This week') - Number(a === 'This week'));
  return <section className="an-block"><h2>Funnel</h2>
    {!scorecard.length ? <p className="an-empty">No scorecard yet. Run /analytics.</p> : <div className="sc-card"><table className="sc-table"><thead><tr><th>Stage</th><th>Now</th><th>Before</th><th><span tabIndex={0} title="Habit goals stay fixed and cover actions you control. Conversion rates have three steps from your baseline toward the market reference.">Target</span></th><th>State</th></tr></thead><tbody>
      {periods.map(period => <Fragment key={period || 'none'}>{period && <tr className="sc-group"><td colSpan={5}>{plain(period)}</td></tr>}{scorecard.filter(row => (row.period_label || '') === period).map(row => {
        const open = opened.includes(row.key), unit = row.series?.unit || kpis[row.key]?.unit, missing = row.state === 'missing', n = row.finished?.n, k = row.finished?.k, pending = typeof row.pending === 'number' ? row.pending : row.pending?.n, previous = row.change?.previous_value, cur = row.currency || currency;
        const atStake = row.focus?.revenue_at_stake ?? row.focus?.lost_revenue ?? kpis[row.key]?.lost_revenue;
        const selected = row.next_action?.lead_filter?.lead_ids || row.evidence || [];
        const noValue = missing || row.value == null || n === 0;
        const nowTip = [missing ? 'Source missing' : n === 0 ? 'No opportunities yet' : n > 0 && k != null ? row.key === 'value_per_100_connects' ? `${n} Connects spent` : `${k} of ${n} finished` : '', pending > 0 ? `+${pending} pending${row.pending?.until ? ` until ${row.pending.until}` : ''}` : ''].filter(Boolean).join(' · ');
        const beforeTip = [row.change?.comparison_label, row.change?.new === true ? 'new' : ''].filter(Boolean).map(plain).join(' · ');
        const targetTip = row.target?.value != null ? [row.target.kind === 'habit' ? 'Goal' : 'Next step', row.target.kind === 'ladder' ? `step ${row.target.level ?? 'unknown'} of 3` : '', row.target.level === 3 ? 'top step held' : '', row.market ? `market reference ${fmt(row.market.value, unit)}` : ''].filter(Boolean).join(' · ') : 'No target yet';
        const state = STATE_WORD[missing ? 'missing' : row.state];
        const focusTip = row.focus ? [row.focus.reason && plain(row.focus.reason), atStake != null ? `Revenue at stake: ${fmt(atStake, 'currency', cur)}` : ''].filter(Boolean).join(' · ') : '';
        return <Fragment key={row.key}><tr className={`sc-row${row.focus ? ' sc-focus' : ''}`}><td className="sc-kpi"><div className="sc-kpi-in"><button className="sc-chevron" aria-expanded={open} aria-controls={`scorecard-${row.key}`} aria-label={`Details for ${plain(row.name)}`} onClick={() => toggle(row.key)}><i>{open ? '▾' : '▸'}</i></button><div><strong title={row.stage_label ? plain(row.stage_label) : undefined}>{plain(row.name)}</strong>{row.focus && <> <span className="an-chip" title={focusTip || undefined}>Focus</span></>}</div></div></td>
          <td className="sc-now" title={nowTip || undefined}><b>{noValue ? '–' : fmt(row.value, unit, cur)}</b></td>
          <td className="sc-trend" title={beforeTip || undefined}>{previous == null ? '–' : fmt(previous, unit, cur)}</td>
          <td className="sc-target" title={targetTip}>{row.target?.value != null ? <>{fmt(row.target.value, unit, cur)}{row.target.kind === 'ladder' && <span className="sc-dots" aria-label={row.target.level == null ? 'Step unknown' : `${row.target.level} of 3 steps reached`}>{[0,1,2].map(i => <i key={i} className={i < (row.target.level ?? 0) ? 'filled' : ''} />)}</span>}</> : '–'}</td>
          <td className="sc-action">{state && <span className={`sc-state sc-state-${missing ? 'missing' : row.state}`}>{state}</span>}</td></tr>
          <tr className="sc-detail" id={`scorecard-${row.key}`} hidden={!open}><td colSpan={5}>
            <Development row={{...row,currency:cur}} weekStart={weekStart}/>
            {(missing || row.next_action?.text) && <p className="sc-next">{missing ? 'Add the missing records.' : plain(row.next_action.text)}</p>}
            {selected.length > 0 && <button className="an-text-button sc-open-leads" onClick={()=>choose({title:row.name,evidence:selected,period:row.period_label})}>Open {selected.length} leads →</button>}
          </td></tr></Fragment>;
      })}</Fragment>)}
    </tbody></table></div>}
  </section>;
}
