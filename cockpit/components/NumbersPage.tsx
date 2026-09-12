'use client';

import { useCockpit } from '@/lib/context';
import './analytics.css';

const STAGE_NAMES: Record<string, string> = {
  Replied: 'In conversation',
};

function displayStage(stage: string) {
  return STAGE_NAMES[stage] || stage;
}

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export default function NumbersPage() {
  const { state } = useCockpit();
  if (!state) return <p className="empty">Loading.</p>;
  const ins = state.insights, tracker = state.tracker, me = state.me || {};
  const funnel = ins.funnel || [];
  const top = funnel[0]?.count || 1;
  const transitions = funnel.slice(1).map((item: any, index: number) => {
    const before = funnel[index];
    return {
      from: displayStage(before.stage),
      to: displayStage(item.stage),
      before: before.count,
      drop: Math.max(0, before.count - item.count),
    };
  }).filter((item: any) => item.before > 0);
  const largestDrop = transitions.reduce((largest: any, item: any) => item.drop > (largest?.drop ?? -1) ? item : largest, null);
  const leakSummary = largestDrop?.drop
    ? `Biggest drop: ${largestDrop.drop} of ${countLabel(largestDrop.before, 'job')} ${largestDrop.drop === 1 ? 'has' : 'have'} not moved from ${largestDrop.from} to ${largestDrop.to}.`
    : funnel.length ? 'No stage drop yet.' : 'No pipeline data yet. Find jobs to start.';
  const applied = funnel.find((item: any) => item.stage === 'Applied')?.count || 0;
  const applicationsNeeded = Math.max(0, 5 - applied);
  const stats = [
    [me.jss != null ? `${me.jss}%` : null, 'Job Success'],
    [me.rate, 'Hourly rate'],
    [me.earned, 'Total earned'],
    [me.jobs, 'Jobs completed'],
    [me.reviews, 'Client reviews'],
  ].filter(([value]) => value != null && value !== '');
  const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return <div className="analytics-page">
    <div className="analytics-intro">
      <h1>Analytics</h1>
      <p className="note-sm">See what converts, where jobs stop, and whether you are applying consistently.</p>
    </div>

    <div className="tiles">
      <Tile
        label="Reply rate"
        value={ins.reply_rate == null ? null : `${ins.reply_rate}%`}
        hint={ins.reply_rate == null
          ? `Available after ${countLabel(applicationsNeeded, 'more application')}.`
          : ins.reply_rate_hint}
      />
      <Tile
        label="Time to reply"
        value={ins.reply_days == null ? null : countLabel(ins.reply_days, 'day')}
        hint={ins.reply_days == null ? 'Available after the first client reply.' : ins.reply_days_hint}
      />
      <Tile label="Applications per week" value={ins.per_week ?? 0} hint="Average over the last four weeks." />
    </div>

    <div className="analytics-section-heading">
      <h2>Pipeline conversion</h2>
      <p className="note-sm">{leakSummary}</p>
    </div>
    <div className="funnel">
      {funnel.map((item: any, index: number) => {
        const before = index ? funnel[index - 1].count : null;
        const conversion = before == null
          ? 'Starting point'
          : before > 0 ? `${Math.round(100 * item.count / before)}% from previous stage` : 'No previous-stage jobs';
        return <div className="funnel-row" key={item.stage}>
          <span>{displayStage(item.stage)}</span>
          <span className="track"><span style={{ width: `${item.count ? Math.max(3, 100 * item.count / top) : 0}%` }} /></span>
          <b>{item.count}</b>
          <span className="funnel-pct">{conversion}</span>
        </div>;
      })}
      <p className="note-sm funnel-note">Each job appears at the highest stage it reached, so a lost job still counts in every earlier stage.</p>
    </div>

    {tracker.goal ? <>
      <div className="analytics-section-heading">
        <h2>Applications this week</h2>
        <p className="note-sm">{countLabel(tracker.week_done, 'application')} this week · Daily goal {tracker.goal}</p>
      </div>
      <div className="days">
        {tracker.week.map((item: any, index: number) => (
          <div
            className={`daybar${item.count >= tracker.goal ? ' hit' : ''}`}
            role="img"
            aria-label={`${names[index]}: ${item.future ? 'not yet' : countLabel(item.count, 'application')}`}
            key={item.day}
          >
            <span style={{ height: `${item.future ? 0 : Math.max(3, Math.min(100, 100 * item.count / tracker.goal))}%` }} />
            <em>{names[index]} {item.future ? '' : item.count}</em>
          </div>
        ))}
      </div>
    </> : null}

    {stats.length ? <>
      <div className="analytics-section-heading"><h2>Profile standing</h2></div>
      <div className="me-stats">
        {stats.map(([value, label]) => <div key={label}><span className="me-val">{value}</span><span className="me-lbl">{label}</span></div>)}
      </div>
    </> : null}
  </div>;
}

function Tile({ label, value, hint }: { label: string; value: string | number | null; hint: string }) {
  return <div className="tile"><span className="tile-lbl">{label}</span><span className={`tile-val${value == null ? ' empty' : ''}`}>{value == null ? 'Not enough data' : value}</span><span className="tile-hint">{hint}</span></div>;
}
