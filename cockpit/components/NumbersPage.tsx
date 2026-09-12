'use client';

import { useCockpit } from '@/lib/context';
import { stamp } from '@/lib/model';
import { analyticsTiles } from '@/lib/analytics-view.mjs';
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
  const tiles = analyticsTiles(ins);
  const stats = [
    [me.jss != null ? `${me.jss}%` : null, 'Job Success'],
    [me.rate, 'Hourly rate'],
    [me.earned, 'Total earned'],
    [me.jobs, 'Total jobs'],
    [me.reviews, 'Client reviews'],
  ].filter(([value]) => value != null && value !== '');
  const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return <div className="analytics-page">
    <div className="analytics-intro">
      <h1>Analytics</h1>
      <p className="note-sm">Your saved pipeline, with the limits of the data in view.</p>
    </div>
    <div className="analytics-coverage" aria-label="Data coverage">
      <span>{countLabel(state.jobs.length, 'saved lead')}</span>
      <span>{state.sync?.synced_at ? `Last sync ${stamp(state.sync.synced_at)}` : 'Not synced with Upwork yet'}</span>
      {ins.application_dates_unknown ? <span className="coverage-gap">{countLabel(ins.application_dates_unknown, 'application date')} missing or invalid</span> : null}
      <span>Partial account coverage</span>
    </div>

    <div className="tiles">
      {tiles.map(tile => <Tile key={tile.label} {...tile} />)}
    </div>

    <div className="analytics-section-heading">
      <h2>Saved pipeline history</h2>
      <p className="note-sm">All ages together. New leads have had less time to progress.</p>
    </div>
    <div className="funnel">
      {funnel.map((item: any, index: number) => {
        const conversion = index === 0 ? 'Every saved lead, including skipped'
          : `${item.count} of ${funnel[0]?.count || 0} saved leads reached this stage`;
        return <div className="funnel-row" key={item.stage}>
          <span>{displayStage(item.stage)}</span>
          <span className="track"><span style={{ width: `${item.count ? Math.max(3, 100 * item.count / top) : 0}%` }} /></span>
          <b>{item.count}</b>
          <span className="funnel-pct">{conversion}</span>
        </div>;
      })}
      <p className="note-sm funnel-note">Each lead counts in every stage up to its highest recorded stage. These are pipeline records, not independently verified replies or a timed conversion study. Only jobs saved here are included.</p>
    </div>

    {tracker.goal ? <>
      <div className="analytics-section-heading">
        <h2>Applications this week</h2>
        <p className="note-sm">{countLabel(tracker.week_done, 'dated application')} this week · Daily goal {tracker.goal}{tracker.application_dates_unknown ? ` · ${tracker.application_dates_unknown} missing dates excluded` : ''}</p>
      </div>
      <div className="days">
        {tracker.week.map((item: any, index: number) => (
          <div
            className={`daybar${item.count >= tracker.goal ? ' hit' : ''}`}
            role="img"
            aria-label={`${names[index]}: ${item.future ? 'not yet' : countLabel(item.count, 'application')}`}
            key={item.day}
          >
            <span style={{ height: `${item.future || !item.count ? 0 : Math.max(3, Math.min(100, 100 * item.count / tracker.goal))}%` }} />
            <em>{names[index]} {item.future ? '' : item.count}</em>
          </div>
        ))}
      </div>
    </> : null}

    {stats.length ? <>
      <div className="analytics-section-heading"><h2>Profile standing</h2>
        <p className="note-sm">Account-wide totals{me.profile_cached_at ? ` · Profile saved ${stamp(me.profile_cached_at)}` : ' · Profile save time unknown'}</p></div>
      <div className="me-stats">
        {stats.map(([value, label]) => <div key={label}><span className="me-val">{value}</span><span className="me-lbl">{label}</span></div>)}
      </div>
    </> : null}
  </div>;
}

function Tile({ label, value, hint, empty }: { label: string; value: string | number | null; hint: string; empty: string }) {
  return <div className="tile"><span className="tile-lbl">{label}</span><span className={`tile-val${value == null ? ' empty' : ''}`}>{value == null ? empty : value}</span><span className="tile-hint">{hint}</span></div>;
}
