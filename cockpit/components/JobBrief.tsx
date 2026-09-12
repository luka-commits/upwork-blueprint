'use client';

import { deriveJobBrief } from '@/lib/job-brief.mjs';
import './job-brief.css';

const PREVIEW_SCOPE = 3;

function compact(value: string, limit = 145) {
  if (value.length <= limit) return value;
  const cut = value.slice(0, limit + 1);
  const boundary = Math.max(cut.lastIndexOf(';'), cut.lastIndexOf(','), cut.lastIndexOf(' '));
  return `${cut.slice(0, boundary > limit * .65 ? boundary : limit).replace(/[,:;\s]+$/, '')}…`;
}

export default function JobBrief({ job }: { job: any }) {
  const brief = deriveJobBrief(job);
  if (!brief.outcome && !brief.scope.length && !brief.requirements.length && !brief.decision) {
    return <p className="job-brief-empty">No job brief is saved yet. Open the original posting before deciding.</p>;
  }
  const visibleScope = brief.scope.slice(0, PREVIEW_SCOPE);
  const scopeNeedsFull = brief.scope.length > PREVIEW_SCOPE || visibleScope.some((item: string) => compact(item) !== item);
  return <div className="job-brief">
    {brief.outcome ? <section className="job-brief-part job-brief-outcome">
      <h3>Outcome</h3>
      <p>{brief.outcome}</p>
    </section> : null}
    {brief.scope.length ? <section className="job-brief-part">
      <h3>Key work</h3>
      <ul>{visibleScope.map((item: string, index: number) => <li key={index}>{compact(item)}</li>)}</ul>
      {scopeNeedsFull ? <details className="job-brief-full">
        <summary>Full scope · {brief.scope.length} {brief.scope.length === 1 ? 'item' : 'items'}</summary>
        <ul>{brief.scope.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>
      </details> : null}
    </section> : null}
    {brief.requirements.length ? <section className="job-brief-part">
      <h3>Must have</h3>
      <ul>{brief.requirements.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>
    </section> : null}
    {brief.decision ? <section className="job-brief-part job-brief-decision">
      <h3>Saved decision note</h3>
      <p>{brief.decision}</p>
    </section> : null}
  </div>;
}
