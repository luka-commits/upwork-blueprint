'use client';
import { Fragment, useEffect, useState } from 'react';
import { analyticsMemberText as plain } from '@/lib/analytics-contract';
type Row = Record<string, any>;
const rows = (v: any): Row[] => Array.isArray(v) ? v : [];
const fmt = (value: any, unit = '', currency?: string): string => value == null ? 'unknown' : typeof value === 'string' ? plain(value) : unit === '$' || unit === 'usd' || unit === 'currency' ? currency ? new Intl.NumberFormat('en-US', {style: 'currency', currency, maximumFractionDigits: 0}).format(value) : `${Math.round(value)} (currency unknown)` : `${new Intl.NumberFormat('en-US', {maximumFractionDigits: unit === '%' ? 0 : 1}).format(value)}${unit === '%' ? '%' : unit === 'min' ? ' min' : unit === 's' ? ' s' : ''}`;
export function weekDateLabel(value: any): string {
  const iso = /^(\d{4})-W(\d{2})$/.exec(String(value || ''));
  let date: Date;
  if (iso) { const jan4 = new Date(Date.UTC(+iso[1],0,4)); date = new Date(jan4); date.setUTCDate(jan4.getUTCDate()-(jan4.getUTCDay()+6)%7+(+iso[2]-1)*7); }
  else date = new Date(String(value).slice(0,10)+'T00:00:00Z');
  return Number.isNaN(date.valueOf()) ? 'Date unknown' : new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:'UTC'}).format(date);
}
function Development({ row, compact = false, weekStart }: { row: Row; compact?: boolean; weekStart?: string }) {
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
  if(!values.some(Number.isFinite))return compact ? null : <p className="an-empty">No trend yet. Add the missing application records, then run /analytics.</p>;
  return <svg className={compact ? 'sc-spark' : 'sc-development'} viewBox={`0 0 ${width} 142`} role="img" aria-label={`${row.series?.label || row.name}: ${labels.map((label,i)=>`${label}: ${fmt(values[i],row.series?.unit,row.currency)}`).join(', ')}`}>
    {!compact && steps.map((step,index)=><g className="sc-step-band" key={index}><rect x={left} y={y(step)-4} width={plotWidth} height="8"/><text x={left+plotWidth+8} y={y(step)+3}>{row.target?.kind==='ladder'?`Step ${index+1}: `:'Goal: '}{fmt(step,row.series?.unit,row.currency)}</text></g>)}
    {values.map((v,i)=><g key={i}><title>{labels[i]}: {fmt(v,row.series?.unit,row.currency)}</title>{Number.isFinite(v) && (compact ? i>0 && Number.isFinite(values[i-1]) && <line x1={x(i-1)} x2={x(i)} y1={y(values[i-1])} y2={y(v)} className="an-chart-line"/> : <><rect x={x(i)-14} y={y(v)} width="28" height={112-y(v)} rx="4" fill={i===values.length-1?'var(--terracotta)':'var(--ring)'}/><text className="sc-value-label" x={x(i)} y={y(v)-8} textAnchor="middle">{fmt(v,row.series?.unit,row.currency)}</text></>)}{!compact && <text x={x(i)} y="133" textAnchor="middle">{labels[i]}</text>}</g>)}
  </svg>;
}
function firstSentence(value: any): string { return plain(value).split(/(?<=[.!?])\s/)[0]; }
function marketSource(market: Row): string | undefined {
  const source=market.source;const url=typeof source==='object'?source?.url:String(source || '').match(/https?:\/\/[^\s]+/)?.[0];
  return typeof url==='string' && /^https?:\/\//.test(url) ? url : undefined;
}
export default function FunnelScorecard({ scorecard, kpis, jobs, currency, choose, onConversations, weekStart }: {scorecard: Row[]; kpis: Row; jobs: Row[]; currency?: string; choose: (selection: any) => void; onConversations: () => void; weekStart?: string}) {
  const [opened, setOpened] = useState<string[]>([]);
  useEffect(()=>{try{const saved=JSON.parse(sessionStorage.getItem('analytics-scorecard-open') || '[]');if(Array.isArray(saved)&&saved.every(key=>typeof key==='string'))setOpened(saved);}catch{/* Storage is optional. */}},[]);
  const toggle = (key: string) => setOpened(prev => {const next=prev.includes(key)?prev.filter(v=>v!==key):[...prev,key];try{sessionStorage.setItem('analytics-scorecard-open',JSON.stringify(next));}catch{/* Storage is optional. */}return next;});
  return <section className="an-block"><h2>Your funnel, stage by stage</h2>
    {!scorecard.length ? <p className="an-empty">Scorecard unknown. Run /analytics to prepare it.</p> : <div className="sc-card"><table className="sc-table"><thead><tr><th>Stage and habit</th><th>Now</th><th>Change</th><th><span tabIndex={0} title="Habit goals stay fixed and cover actions you control. Conversion rates have three steps from your baseline toward the market reference.">Target ⓘ</span></th><th>What it means</th></tr></thead><tbody>
      {['top', 'middle', 'bottom'].map(group => <Fragment key={group}><tr className="sc-group"><td colSpan={5}>{({top: 'Top · finding and applying', middle: 'Middle · replies and calls', bottom: 'Bottom · proposals and wins'} as Row)[group]}</td></tr>{scorecard.filter(row => row.group === group).map(row => {
        const open = opened.includes(row.key), unit = row.series?.unit || kpis[row.key]?.unit, missing = row.state === 'missing', n = row.finished?.n, k = row.finished?.k, pending = typeof row.pending === 'number' ? row.pending : row.pending?.n, previous = row.change?.previous_value;
        const atStake = row.focus?.revenue_at_stake ?? row.focus?.lost_revenue ?? kpis[row.key]?.lost_revenue;
        const selected = row.next_action?.lead_filter?.lead_ids || row.evidence || [];
        return <Fragment key={row.key}><tr className={`sc-row${row.focus ? ' sc-focus' : ''}`}><td className="sc-kpi"><div className="sc-kpi-in"><button className="sc-chevron" aria-expanded={open} aria-controls={`scorecard-${row.key}`} aria-label={`Details for ${plain(row.name)}`} onClick={() => toggle(row.key)}><i>{open ? '▾' : '▸'}</i></button><div><strong>{plain(row.name)}</strong>{row.stage_label && <small>{plain(row.stage_label)}</small>}<small>{plain(row.period_label || 'Period unknown')}</small>{row.sample_note && <small>{plain(row.sample_note)}</small>}{row.focus && <><span className="an-chip">Focus this week</span>{row.focus.reason && <small>{plain(row.focus.reason)}</small>}<small>Revenue at stake: {atStake==null ? 'unknown' : fmt(atStake,'currency',row.currency || currency)}</small></>}</div></div></td>
          <td className="sc-now"><b>{missing ? 'unknown' : n === 0 ? 'No opportunities yet' : fmt(row.value, unit, row.currency || currency)}</b><small>{missing ? 'Source missing' : n > 0 && k != null ? row.key === 'weekly_volume' ? row.period?.kind === 'four_week_average' ? `${k} qualified over four weeks` : `${k} qualified this week` : row.key === 'value_per_100_connects' ? `${n} Connects spent` : `${k} of ${n} finished` : ''}</small>{pending > 0 && <small>+{pending} pending{row.pending?.until ? ` until ${row.pending.until}` : ''}</small>}{n === 0 && row.pending?.until && <small>Awaiting reply observation until {row.pending.until}</small>}</td>
          <td className="sc-trend"><Development row={{...row,currency:row.currency || currency}} compact /><strong>{!missing && (row.change?.new === true || row.change?.previous_n === 0 && n > 0) ? `new · ${k == null ? 'unknown' : k} of ${n == null ? 'unknown' : n} finished` : previous == null ? 'Previous four-week comparison unavailable' : row.value === previous ? 'unchanged' : `was ${fmt(previous, unit, row.currency || currency)}`}</strong><small>{plain(row.change?.comparison_label || 'Comparison period unknown')}</small></td>
          <td className="sc-target">{row.target?.value != null ? <>{row.target.kind === 'habit' ? 'Goal: ' : 'Next step: '}{fmt(row.target.value, unit, row.currency || currency)}{row.key === 'weekly_volume' && ' a week'}{row.target.kind === 'ladder' && <>{` · ${row.target.level ?? 'unknown'} of 3`}<span className="sc-dots" aria-label={row.target.level == null ? 'Step unknown' : `${row.target.level} of 3 steps reached`}>{[0,1,2].map(i => <i key={i} className={i < (row.target.level ?? 0) ? 'filled' : ''} />)}</span>{row.target.level === 3 && <small>Top step held</small>}</>}</> : <small>{missing ? 'unknown' : 'No target yet'}</small>}</td>
          <td className="sc-action">{missing ? <p>Add the missing records to check this.</p> : row.insight && <p>{plain(row.insight)}</p>}{!missing && row.next_action && <button className="an-text-button" onClick={() => choose({title: row.next_action.text, evidence: selected, period: row.period_label, note: row.focus?.reason})}>{plain(row.next_action.text)} →</button>}</td></tr>
          <tr className="sc-detail" id={`scorecard-${row.key}`} hidden={!open}><td colSpan={5}>
            {row.key === 'reply_to_call' && <button className="an-text-button" onClick={onConversations}>Why these replies stalled → Conversations</button>}
            <div className="sc-detail-grid"><section><h4>{row.series?.label || 'Eight-week development'}</h4><Development row={{...row,currency:row.currency || currency}} weekStart={weekStart}/></section>
              <section className="sc-counting"><p>{row.period?.kind === 'four_week_average' ? 'Average of the four weekly values before this week.' : firstSentence(row.counting || row.how_counted || kpis[row.key]?.definition || 'Finished cases count; pending cases stay separate.')}</p>
                {[...rows(row.job_fit?.apply),...rows(row.job_fit?.skip)].slice(0,1).map((finding,index)=><p key={index}>{firstSentence(finding.text)}</p>)}
                {row.market && <p className="an-meta">Market reference: {fmt(row.market.value,unit)}. {marketSource(row.market) && <a href={marketSource(row.market)} target="_blank" rel="noreferrer">Source</a>}</p>}
              </section>
            </div><button className="an-text-button sc-open-leads" onClick={()=>choose({title:row.name,evidence:selected,period:row.period_label})}>Open these {selected.length} leads →</button>
          </td></tr></Fragment>;
      })}</Fragment>)}
    </tbody></table></div>}

  </section>;
}
