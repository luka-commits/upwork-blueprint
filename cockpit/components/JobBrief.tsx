'use client';

import { deriveJobBrief } from '@/lib/job-brief.mjs';
import './job-brief.css';

export default function JobBrief({ job }: { job: any }) {
  const brief = deriveJobBrief(job);
  if (!brief.outcome && !brief.scope.length && !brief.requirements.length) {
    return <p className="job-brief-empty">No job brief is saved yet. Open the original posting before deciding.</p>;
  }
  return <div className="job-brief">
    {brief.outcome ? <section className="job-brief-part job-brief-outcome">
      <h3>Outcome</h3>
      <p>{brief.outcome}</p>
    </section> : null}
    {brief.scope.length ? <section className="job-brief-part">
      <h3>What needs doing</h3>
      <ul>{brief.scope.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>
    </section> : null}
    {brief.requirements.length ? <section className="job-brief-part">
      <h3>Must have</h3>
      <ul>{brief.requirements.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>
    </section> : null}
  </div>;
}
