'use client';

import { useCockpit } from '@/lib/context';
import { MIN_RATE, APPLICATION_STEPS, PROPOSAL_STEPS, funnelShapes, funnelSteps } from '@/lib/funnel.mjs';

// One hue from light to dark: the house terracotta, on the ivory card.
const RAMP = ['#e5a48c', '#d97757', '#d97757', '#b05538', '#7a3620'];
const WIDTH = 560, HEIGHT = 84, GAP = 2, LABEL_X = 610;

const BAR_W = 46, BAR_GAP = 10, CHART_H = 132, BAR_TOP = 30;

/** Applications per week. The funnel says how well it converted, this says whether
 *  it happened at all, which is the part a member is actually in charge of. */
function Outreach({ weeks }: { weeks: { week: string; count: number }[] }) {
  if (!weeks?.length) return null;
  const total = weeks.reduce((sum, w) => sum + w.count, 0);
  const best = Math.max(...weeks.map(w => w.count));
  const quiet = weeks.filter(w => !w.count).length;
  const width = weeks.length * (BAR_W + BAR_GAP) - BAR_GAP;
  const label = (iso: string) => {
    const date = new Date(iso + 'T00:00:00');
    return `${date.getDate()}.${date.getMonth() + 1}.`;
  };
  return <section className="funnel" aria-label="Applications per week">
    <h2>Outreach</h2>
    <p className="funnel-headline">{total
      ? <><strong>{total}</strong> application{total === 1 ? '' : 's'} in {weeks.length} weeks · best week {best}{quiet ? ` · ${quiet} week${quiet === 1 ? '' : 's'} with none` : ''}</>
      : 'Nothing sent in the last twelve weeks.'}</p>
    <div className="funnel-card">
      <svg className="funnel-chart" viewBox={`0 0 ${width} ${BAR_TOP + CHART_H + 34}`} role="img"
           aria-label={`Applications per week, ${total} in total`}>
        {weeks.map((week, index) => {
          const scale = best ? week.count / best : 0;
          const height = Math.round(scale * CHART_H);
          const x = index * (BAR_W + BAR_GAP);
          const last = index === weeks.length - 1;
          return <g key={week.week}>
            <title>{`Week of ${label(week.week)}: ${week.count} application${week.count === 1 ? '' : 's'}`}</title>
            <rect x={x} y={BAR_TOP + CHART_H - height} width={BAR_W} height={Math.max(height, 2)} rx={4}
                  fill={last ? '#e5a48c' : '#b05538'} />
            {week.count ? <text x={x + BAR_W / 2} y={BAR_TOP + CHART_H - height - 14} className="outreach-count"
                                textAnchor="middle">{week.count}</text> : null}
            <text x={x + BAR_W / 2} y={BAR_TOP + CHART_H + 22} className="funnel-rate" textAnchor="middle">{label(week.week)}</text>
          </g>;
        })}
      </svg>
    </div>
    <p className="funnel-note">The same applications as the funnel, within twelve weeks. Weeks use the send date, or the earliest saved stage or discovery date when it is missing; undated applications stay out. The last bar is this week, still running.</p>
  </section>;
}


function Consistency({ daily }: { daily: any }) {
  if (!daily) return null;
  return <section className="funnel" aria-label="14-day consistency">
    <h2>Consistency</h2>
    <p className="funnel-headline"><strong>{daily.days_on_goal}</strong> of {daily.total_days} days on goal · {daily.goal} applications a day</p>
    <dl className="timings">{daily.days.map((day: { date: string; count: number }) =>
      <div key={day.date}><dt>{day.date}</dt><dd>{day.count}</dd></div>)}</dl>
    <p className="funnel-note">Last 14 local days, including today and weekends. Each application counts once.</p>
  </section>;
}

function Profile({ profile }: { profile: any }) {
  if (!profile?.latest) return <section className="funnel"><h2>Profile completeness</h2><p>Run /profile to measure completeness.</p></section>;
  const { latest, history } = profile;
  const change = latest.pct - history[0].pct;
  return <section className="funnel" aria-label="Profile completeness">
    <h2>Profile completeness</h2>
    <p className="funnel-headline"><strong>{latest.pct}%</strong> · {latest.date} · {change > 0 ? '+' : ''}{change} points since {history[0].date}</p>
    <p className="funnel-note">Missing: {latest.missing.join(', ') || 'none'}.</p>
    <dl className="timings">{history.map((row: { date: string; pct: number }, index: number) =>
      <div key={`${row.date}-${index}`}><dt>{row.date}</dt><dd>{row.pct}%</dd></div>)}</dl>
  </section>;
}

const TIMINGS = [
  ['speed_to_lead', 'Speed to lead', 'from the job being posted to your application'],
  ['client_reply', 'Client reply time', 'from your application to their first message'],
  ['our_reply', 'Our reply time', 'from the first client message in a block to your next reply'],
  ['call_to_proposal', 'Call to proposal', 'from the recorded call to your confirmed proposal send'],
  ['time_to_close', 'Time to close', 'from your application to won, as you recorded it'],
] as const;
const MIN_MEDIAN = 20;

function span(seconds: number) {
  const hours = seconds / 3600;
  if (hours < 1) return `${Math.max(1, Math.round(seconds / 60))} min`;
  if (hours < 48) return `${Math.round(hours * 10) / 10} h`;
  return `${Math.round(hours / 24 * 10) / 10} days`;
}

/** Medians of measured gaps, only from leads Upwork's own record backs. */
function Timings({ timings }: { timings?: Record<string, { n: number; median_s: number | null; values?: { seconds: number; call_source: string; proposal_source: string }[] }> }) {
  if (!timings) return null;
  return <section className="funnel" aria-label="Timings">
    <h2>Timings</h2>
    <dl className="timings">
      {TIMINGS.map(([key, label, note]) => {
        const { n = 0, median_s = null, values = [] } = timings[key] || {};
        const observed = values.some(value => value.call_source === 'observed');
        return <div key={key}>
          <dt>{label}</dt>
          {median_s != null ? <dd>{span(median_s)}</dd> : <dd className="few">{n} of {MIN_MEDIAN} needed</dd>}
          <dd>{note}{median_s != null ? ` · median of ${n}` : ''}{observed ? ' · observed (call history)' : ''}</dd>
        </div>;
      })}
    </dl>
    <p className="funnel-note">Application timings use Upwork-confirmed sends and replies. Our reply uses complete threads; close and proposal use recorded events.</p>
  </section>;
}

function Funnel({ counts, definitions, title, entryLabel }: { counts: any; definitions: string[][]; title: string; entryLabel: string }) {
  const steps = funnelSteps(counts, definitions);
  const shapes = funnelShapes(steps, { width: WIDTH, height: HEIGHT, gap: GAP });
  const entry = steps[0].count;
  const last = steps[steps.length - 1];
  const winRate = title === 'Win the deal' && counts.applied >= MIN_RATE
    ? Math.round(100 * counts.won / counts.applied) : null;
  const total = steps.length * (HEIGHT + GAP) - GAP;
  return <section className="funnel" aria-label={title}>
    <h2>{title}</h2>
    <p className="funnel-headline">{!counts.applied ? 'No applications yet. The funnel fills as /brief records them.' : <><strong>{last.count}</strong> {last.label.toLowerCase()} from {entry} {entryLabel}{winRate != null ? ` · ${winRate}% overall win rate` : ''}</>}</p>
    <div className="funnel-card">
      <svg className="funnel-chart" viewBox={`0 0 1000 ${total}`} role="img" aria-label={title}>
        {shapes.map((shape, index) => {
          const mid = shape.y + HEIGHT / 2;
          const before = (shape.of || '').toLowerCase();
          const band = shape.interval ? ` (${shape.interval[0]} to ${shape.interval[1]}%)` : '';
          return <g key={shape.key} className="funnel-step">
            <title>{`${shape.label}: ${shape.count}, n=${index ? shape.n : shape.count}${shape.rate != null ? `, ${shape.rate}%${band}` : ''}`}</title>
            {shape.count > 0 ? <polygon points={shape.points} fill={RAMP[index]} /> : null}
            <text x={LABEL_X} y={mid - 6} className="funnel-count">{shape.count}</text>
            <text x={LABEL_X + 72} y={mid - 6} className="funnel-label">{shape.label}</text>
            <text x={LABEL_X + 72} y={mid + 16} className="funnel-rate">{index === 0
              ? `n=${shape.count} · ${entryLabel}`
              : `n=${shape.n} · ${shape.rate != null ? `${shape.rate}%${band} of ${before}` : `too few to read (${MIN_RATE} needed)`}`}</text>
          </g>;
        })}
      </svg>
    </div>
    <p className="funnel-note">Each lead counts once at each recorded stage it reached.</p>
  </section>;
}

function Bottleneck({ value }: { value: any }) {
  if (!value) return null;
  const unit = value.stage === 'Volume' ? ' days' : value.stage === 'Speed' ? ' h' : '%';
  return <p className="funnel-headline" aria-label="Bottleneck">
    {value.stage ? <><strong>{value.stage}</strong>: {value.value}{unit} against {value.bar}{unit} · n={value.n}{value.reasoned ? ' · reasoned bar' : ''}. </> : 'No measured stage below its bar. '}
    {value.next_action}{value.unmeasured.length ? ` Not measured yet: ${value.unmeasured.join(', ')}.` : ''}
  </p>;
}

export default function AnalyticsPage() {
  const { state } = useCockpit();
  if (!state) return null;
  return <>
    <Bottleneck value={state.bottleneck} />
    <Funnel counts={state.funnel} definitions={APPLICATION_STEPS} title="Win the call" entryLabel="applications" />
    <Funnel counts={state.funnel} definitions={PROPOSAL_STEPS} title="Win the deal" entryLabel="calls" />
    <Outreach weeks={state.outreach} />
    <Consistency daily={state.consistency} />
    <Profile profile={state.profile} />
    <Timings timings={state.timings} />
  </>;
}
