'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { LABEL, short, stamp, todayIso } from '@/lib/model';
import { scheduledFollowUps } from '@/lib/follow-up-reminders.mjs';
import { followUpInline, followUpReviewAge, parseFollowUpReport } from '@/lib/follow-up-view.mjs';
import './follow-ups.css';

type Report = { available: boolean; modified_at: string | null; text: string; error?: string };
type Block = { kind: string; text?: string; items?: string[] };

function Inline({ text }: { text: string }) {
  return <>{followUpInline(text).map((part, index) => part.kind === 'link' && part.href
    ? <Link href={part.href} key={index}>{part.text}</Link>
    : part.kind === 'strong' ? <strong key={index}>{part.text}</strong> : <span key={index}>{part.text}</span>)}</>;
}

function ReportBlocks({ blocks }: { blocks: Block[] }) {
  return <div className="follow-up-prose">{blocks.map((block, index) => block.kind === 'heading'
    ? <h3 key={index}><Inline text={block.text || ''} /></h3>
    : block.kind === 'list' ? <ul key={index}>{block.items?.map((item, itemIndex) => <li key={itemIndex}><Inline text={item} /></li>)}</ul>
      : <p key={index}><Inline text={block.text || ''} /></p>)}</div>;
}

export default function FollowUpsPage() {
  const { api, state, runs, runCommand } = useCockpit();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const finishedKey = runs.filter(run => run.command === 'follow-up' && run.done).map(run => run.id).sort().join('|');
  const reviewing = runs.some(run => run.command === 'follow-up' && !run.done);
  const syncing = runs.some(run => run.command === 'sync' && !run.done);
  const canReview = !!state?.commands?.['follow-up'];

  useEffect(() => {
    let active = true;
    setLoading(true);
    void api('/api/follow-ups').then(result => {
      if (!active) return;
      if (!result.ok || typeof result.data?.available !== 'boolean' || typeof result.data?.text !== 'string') {
        setLoadError(true);
      } else {
        setReport(result.data);
        setLoadError(false);
      }
      setLoading(false);
    });
    return () => { active = false; };
  }, [api, finishedKey, reload]);

  const parsed = useMemo(() => parseFollowUpReport(report?.text), [report?.text]);
  const today = todayIso();
  const reminders = scheduledFollowUps(state?.jobs, today);
  const due = reminders.filter(item => item.due <= today);
  const later = reminders.filter(item => item.due > today);
  const age = followUpReviewAge(report?.modified_at);
  const hasReport = !!report?.available && !!report.text.trim();

  return (
    <div className="follow-ups-page">
      <div className="follow-ups-head">
        <h1>Follow-ups</h1>
        <div className="follow-ups-action">
          <button className="primary" disabled={!canReview || reviewing || syncing} onClick={() => runCommand('follow-up')}>
            {reviewing ? 'Reviewing follow-ups…' : syncing ? 'Waiting for sync…' : 'Review follow-ups'}
          </button>
          <p>{canReview ? 'Reviews leads and prepares drafts.' : 'Follow-up review is unavailable.'}</p>
        </div>
      </div>

      <div className="follow-ups-layout">
        <section className="panel follow-up-review" aria-labelledby="review-title">
          <div className="follow-up-review-head">
            <h2 id="review-title">Latest review</h2>
            <button className="link" title="Reload saved report. No Upwork calls." disabled={loading} onClick={() => setReload(value => value + 1)}>{loading ? 'Loading…' : 'Reload'}</button>
          </div>
          {reviewing ? <p className="follow-up-notice" role="status">Review in progress. Any report below is the previous saved version. Follow the run in Runs.</p> : null}
          {loadError ? <p className="follow-up-notice warning" role="alert">Could not reload the report. {hasReport ? 'The last loaded copy is still shown.' : 'Try Reload.'}</p> : null}
          {loading && !report ? <p className="follow-up-empty" role="status">Loading the saved review.</p> : null}
          {!loading && !loadError && report?.error ? <p className="follow-up-notice warning" role="alert">{report.error}</p> : null}

          {hasReport ? <>
            <div className="follow-up-review-meta">
              {age !== 'unknown' && report?.modified_at ? <time dateTime={report.modified_at}>Saved {stamp(report.modified_at)}</time> : <span>Save time unknown</span>}
            </div>
            {age !== 'today' ? <p className="follow-up-review-caution">{age === 'older'
              ? 'Earlier review. Check for new replies before acting.'
              : 'Review age unknown. Check for new replies before acting.'}</p> : null}
            {!parsed.sections.length && parsed.intro.length ? <div className="follow-up-review-intro"><ReportBlocks blocks={parsed.intro} /></div> : null}
            {[...parsed.sections].sort((a, b) => (a.key === 'do today' ? 0 : 1) - (b.key === 'do today' ? 0 : 1)).map(section => section.key === 'do today'
              ? <section className="follow-up-section do-today" key={section.key} aria-label={section.title}>
                <h2>{section.title}</h2>
                {section.blocks.length ? <ReportBlocks blocks={section.blocks} /> : <p className="note-sm">No detail was saved for this section.</p>}
              </section>
              : <details className="follow-up-section follow-up-disclosure" key={section.key}>
                <summary>{section.title}</summary>
                {section.blocks.length ? <ReportBlocks blocks={section.blocks} /> : <p className="note-sm">No detail was saved for this section.</p>}
              </details>)}
            <details className="follow-up-source"><summary>Original report</summary><pre>{report?.text}</pre></details>
          </> : !loading && !loadError && !report?.error ? <div className="follow-up-empty">
            <span className="follow-up-empty-mark" aria-hidden="true">↗</span>
            <h3>No review saved yet</h3>
            <p>Review your leads to see who is worth following up with, who needs more time, and who to leave alone.</p>
            <p className="note-sm">No report does not mean no opportunities. Your saved reminders are listed separately.</p>
          </div> : null}
        </section>

        <aside className="panel follow-up-reminders" aria-labelledby="reminders-title">
          <h2 id="reminders-title">Scheduled reminders <span>{reminders.length}</span></h2>
          <p className="follow-up-reminders-note">Saved dates. Check the conversation before acting.</p>
          {!reminders.length ? <p className="follow-up-reminders-empty">No follow-up dates are saved for active conversations or clients.</p> : null}
          {[{ name: 'Due now', items: due }, { name: 'Later', items: later }].filter(group => group.items.length).map(group => <section className="follow-up-reminder-group" key={group.name} aria-label={`${group.name} reminders`}>
            <h3>{group.name}<span>{group.items.length}</span></h3>
            <ul>{group.items.map(item => <li key={item.id}>
              <div className="follow-up-reminder-meta"><span>{LABEL[item.status]}</span><time dateTime={item.due} className={item.due <= today ? 'due' : ''}>{item.due === today ? 'Today' : item.due < today ? `Overdue · ${short(item.due)}` : short(item.due)}</time></div>
              <Link className="follow-up-reminder-link" href={`/job/${item.id}`}>{item.title}<span aria-hidden="true">↗</span></Link>
              {item.reason ? <details className="follow-up-reason"><summary>Why this date</summary><p>{item.reason}</p></details> : null}
              {item.step && item.max_steps ? <span className="follow-up-step">Saved sequence: step {item.step} of {item.max_steps}</span> : null}
            </li>)}</ul>
          </section>)}
        </aside>
      </div>
      <p className="follow-ups-footer">Saved data only. Review follow-ups checks Upwork when needed; sending still requires your approval.</p>
    </div>
  );
}
