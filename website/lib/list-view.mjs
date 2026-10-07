// Search and order for the one list. The board shows the same jobs, grouped.
// Search is an AND over the query's words, matched against title, summary and id,
// and an empty query is not a filter. A lead without a score ranks below every
// scored lead instead of counting as a zero, and an unknown bid count like
// `20 to 50` sorts last under competition.
import { nextStep, stageEnteredAt } from './next-step.mjs';
import { ORDER } from './stages.mjs';

const amount = value => {
  const match = String(value ?? '').replace(/,/g, '').match(/\d+(\.\d+)?/);
  return match ? parseFloat(match[0]) : -1;
};
const changedAt = stageEnteredAt;
const score = job => job.score ?? -1;

export function searchJobs(jobs, query) {
  const words = String(query || '').toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return jobs;
  return jobs.filter(job => {
    const text = [job.title, job.summary, job.id].join(' ').toLowerCase();
    return words.every(word => text.includes(word));
  });
}

const KEYS = {
  score,
  job: job => String(job.title || '').toLowerCase(),
  client: job => (job.client || {}).rating ?? -1,
  competition: job => typeof job.proposals === 'number' ? job.proposals : Infinity,
  budget: job => amount(job.budget),
  step: job => nextStep(job).label,
};

export function sortJobs(jobs, sort = null) {
  const list = [...jobs];
  const key = sort && KEYS[sort.key];
  if (!key) {
    // The most promising lead of each stage comes first.
    return list.sort((a, b) => (ORDER.indexOf(a.status) - ORDER.indexOf(b.status))
      || score(b) - score(a) || changedAt(b).localeCompare(changedAt(a)));
  }
  const direction = sort.desc ? -1 : 1;
  return list.sort((a, b) => {
    const x = key(a), y = key(b);
    return (x < y ? -1 : x > y ? 1 : 0) * direction;
  });
}

export function daysInStage(job, now = Date.now()) {
  const at = Date.parse(stageEnteredAt(job));
  return Number.isNaN(at) ? null : Math.max(0, Math.floor((now - at) / 864e5));
}
