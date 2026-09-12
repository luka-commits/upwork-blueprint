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
    </div>
    <div className="analytics-coverage" aria-label="Data coverage">
      <strong>Saved leads only</strong>
      <span>{countLabel(state.jobs.length, 'saved lead')}</span>
      <span>{state.sync?.synced_at ? `Last sync ${stamp(state.sync.synced_at)}` : 'Not synced with Upwork yet'}</span>
      {ins.application_dates_unknown ? <span className="coverage-gap">{countLabel(ins.application_dates_unknown, 'application date')} missing or invalid</span> : null}
    </div>

    <div className="tiles">
      {tiles.map(tile => <Tile key={tile.label} {...tile} />)}
    </div>

    <div className="analytics-section-heading">
      <h2>Pipeline</h2>
    </div>
    <div className="funnel">
      {funnel.map((item: any) => <div className="funnel-row" key={item.stage}>
          <span>{displayStage(item.stage)}</span>
          <span className="track" aria-hidden="true"><span style={{ width: `${item.count ? Math.max(3, 100 * item.count / top) : 0}%` }} /></span>
          <b>{item.count}</b>
        </div>)}
    </div>

    {tracker.goal ? <>
      <div className="analytics-section-heading">
        <h2>Applications this week</h2>
        <span className="section-fact">{tracker.week_done} this week · Goal {tracker.goal}/day</span>
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
      <div className="analytics-section-heading"><h2>Profile</h2><span className="section-fact">Account totals</span></div>
      <div className="me-stats">
        {stats.map(([value, label]) => <div key={label}><span className="me-val">{value}</span><span className="me-lbl">{label}</span></div>)}
      </div>
    </> : null}

    <details className="analytics-notes">
      <summary>Data notes</summary>
      <div className="analytics-notes-body">
        {tiles.map(tile => <div key={tile.label}><strong>{tile.label}</strong><p>{tile.hint}</p></div>)}
        <div><strong>Pipeline</strong><p>Each lead counts in every stage up to its highest recorded stage. These are pipeline records, not independently verified replies or a timed conversion study. Only jobs saved here are included.</p></div>
        <div><strong>Profile</strong><p>Account totals come from the saved profile. {me.profile_cached_at ? `Profile saved ${stamp(me.profile_cached_at)}.` : 'Profile save time unknown.'}</p></div>
      </div>
    </details>
  </div>;
}

function Tile({ label, value, empty }: { label: string; value: string | number | null; hint: string; empty: string }) {
  return <div className="tile"><span className="tile-lbl">{label}</span><span className={`tile-val${value == null ? ' empty' : ''}`}>{value == null ? empty : value}</span></div>;
}
