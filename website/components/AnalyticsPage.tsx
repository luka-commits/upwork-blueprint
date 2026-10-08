'use client';

import { useCockpit } from '@/lib/context';
import { MIN_RATE, funnelShapes, funnelSteps } from '@/lib/funnel.mjs';

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


const TIMINGS = [
  ['speed_to_lead', 'Speed to lead', 'from the job being posted to your application'],
  ['client_reply', 'Client reply time', 'from your application to their first message'],
  ['time_to_close', 'Time to close', 'from your application to won, as you recorded it'],
] as const;
const MIN_MEDIAN = 20;

function span(seconds: number) {
  const hours = seconds / 3600;
  if (hours < 1) return `${Math.max(1, Math.round(seconds / 60))} min`;
  if (hours < 48) return `${Math.round(hours * 10) / 10} h`;
  return `${Math.round(hours / 24 * 10) / 10} days`;
}

/** Medians of three gaps, only from leads Upwork's own record backs. */
function Timings({ timings }: { timings?: Record<string, { n: number; median_s: number | null }> }) {
  if (!timings) return null;
  return <section className="funnel" aria-label="Timings">
    <h2>Timings</h2>
    <dl className="timings">
      {TIMINGS.map(([key, label, note]) => {
        const { n = 0, median_s = null } = timings[key] || {};
        return <div key={key}>
          <dt>{label}</dt>
          {median_s != null ? <dd>{span(median_s)}</dd> : <dd className="few">{n} of {MIN_MEDIAN} needed</dd>}
          <dd>{note}{median_s != null ? ` · median of ${n}` : ''}</dd>
        </div>;
      })}
    </dl>
    <p className="funnel-note">Only applications Upwork confirmed count, so a time never rests on when a command happened to run.</p>
  </section>;
}

/** The one thing the cockpit tracks: from application to won. */
export default function AnalyticsPage() {
  const { state } = useCockpit();
  if (!state) return null;
  const steps = funnelSteps(state.funnel);
  const shapes = funnelShapes(steps, { width: WIDTH, height: HEIGHT, gap: GAP });
  // By key, not by position: adding a stage silently turned "won" into the offer count.
  const applied = steps.find(step => step.key === 'applied') || { count: 0 };
  const won = steps.find(step => step.key === 'won') || { count: 0 };
  const winRate = applied.count >= MIN_RATE ? Math.round(100 * won.count / applied.count) : null;
  const total = steps.length * (HEIGHT + GAP) - GAP;
  // Cold leads keep their stage, so the funnel cannot show them; the count sits under it.
  const coldCount = (state.jobs || []).filter((job: any) => job.cold_since && ['replied', 'call', 'offer'].includes(job.status)).length;
  return <section className="funnel" aria-label="Funnel">
    <h2>Funnel</h2>
    <p className="funnel-headline">{applied.count
      ? <><strong>{won.count}</strong> won from {applied.count} applications{winRate != null ? ` · ${winRate}% win rate` : ''}</>
      : 'No applications yet. The funnel fills as /brief records them.'}</p>
    <div className="funnel-card">
      <svg className="funnel-chart" viewBox={`0 0 1000 ${total}`} role="img" aria-label="Funnel from applications sent to won">
        {shapes.map((shape, index) => {
          const mid = shape.y + HEIGHT / 2;
          const before = (shape.of || '').toLowerCase();
          const band = shape.interval ? ` (${shape.interval[0]} to ${shape.interval[1]}%)` : '';
          const tooFew = shape.n ? `too few to read: ${shape.n} of ${MIN_RATE} ${before}` : 'too few to read';
          return <g key={shape.key} className="funnel-step">
            <title>{`${shape.label}: ${shape.count}${shape.rate != null ? ` (${shape.rate}%${band} of ${before}${shape.overall != null ? `, ${shape.overall}% of all applications` : ''})` : ''}`}</title>
            {shape.count > 0 ? <polygon points={shape.points} fill={RAMP[index]} /> : null}
            <text x={LABEL_X} y={mid - 6} className="funnel-count">{shape.count}</text>
            <text x={LABEL_X + 72} y={mid - 6} className="funnel-label">{shape.label}</text>
            <text x={LABEL_X + 72} y={mid + 16} className="funnel-rate">{shape.rate != null
              ? `${shape.rate}%${band} of ${before}${shape.overall != null && shape.overall !== shape.rate ? ` · ${shape.overall}% of all applications` : ''}`
              : index === 0 ? 'every lead you applied to' : tooFew}</text>
          </g>;
        })}
      </svg>
    </div>
    <p className="funnel-note">Every lead counts once at each stage it ever reached.{coldCount
      ? ` ${coldCount} cold after two unanswered follow-ups, still in their stage.` : ''}</p>
    <Outreach weeks={state.outreach} />
    <Timings timings={state.timings} />
  </section>;
}
