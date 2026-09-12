'use client';

import { useCockpit } from '@/lib/context';

export default function NumbersPage() {
  const { state } = useCockpit();
  if (!state) return <p className="empty">Loading.</p>;
  const ins = state.insights, tracker = state.tracker, me = state.me || {};
  const top = ins.funnel[0].count || 1;
  let previous: number | null = null;
  const stats = [
    [me.jss != null ? `${me.jss}%` : null, 'Job Success'],
    [me.earned, 'earned'],
    [me.jobs, 'jobs done'],
    [me.reviews, 'reviews'],
    [me.rate, 'your rate'],
  ].filter(([value]) => value != null && value !== '');
  const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return <>
    <div className="tiles">
      <Tile label="Reply rate" value={ins.reply_rate == null ? null : `${ins.reply_rate}%`} hint={ins.reply_rate_hint} />
      <Tile label="Time to reply" value={ins.reply_days == null ? null : `${ins.reply_days} days`} hint={ins.reply_days_hint} />
      <Tile label="Applications per week" value={ins.per_week} hint="average of the last four weeks" />
    </div>
    <div className="funnel">
      {ins.funnel.map((item: any) => {
        const before = previous;
        const of = before && item.count ? ` · ${Math.round(100 * item.count / before)}% of the step before` : '';
        previous = item.count;
        return <div className="funnel-row" key={item.stage}>
          <span>{item.stage}</span>
          <span className="track"><span style={{ width: `${item.count ? Math.max(3, 100 * item.count / top) : 0}%` }} /></span>
          <b>{item.count}</b>
          <span className="funnel-pct">{item.count ? `${Math.round(100 * item.count / top)}%` : ''}{of}</span>
        </div>;
      })}
      <p className="note-sm" style={{ margin: '6px 0 0' }}>Every job counts at the highest stage it ever reached, so a lost job still shows it got a reply first.</p>
    </div>
    {tracker.goal ? <><h3 className="section-title">This week</h3><div className="days">
      {tracker.week.map((item: any, index: number) => <div className={`daybar${item.count >= tracker.goal ? ' hit' : ''}`} title={`${item.day}: ${item.count}`} key={item.day}>
        <span style={{ height: `${item.future ? 0 : Math.max(3, Math.min(100, 100 * item.count / tracker.goal))}%` }} /><em>{names[index]}</em>
      </div>)}
    </div></> : null}
    {stats.length ? <><h3 className="section-title">Where you stand</h3><div className="me-stats">
      {stats.map(([value, label]) => <div key={label}><span className="me-val">{value}</span><span className="me-lbl">{label}</span></div>)}
    </div></> : null}
  </>;
}

function Tile({ label, value, hint }: { label: string; value: any; hint: string }) {
  return <div className="tile"><span className="tile-lbl">{label}</span><span className={`tile-val${value == null ? ' empty' : ''}`}>{value == null ? '–' : value}</span><span className="tile-hint">{hint}</span></div>;
}
