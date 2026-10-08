// What tells a member at a glance whether a job is worth it: the score, who the
// client is, how crowded it is and what speaks against it. The list shows the
// short form, the panel the full one.
// Freshness and crowding are read from the posting itself, never from the frozen
// score: under a day is green, three days amber, a week red; five bids or fewer
// green, thirty or more red, and a range like `20 to 50` is read from its first
// number. A score of 9 or more is strong, under 7 is weak. A budget is written
// the same way in the row, the panel and the board, and an hourly job with no
// rate says so rather than showing a dash.
import { jobPreview } from './job-brief.mjs';

/** One sentence for the list: the saved headline, else the summary's first sentence. */
export function headlineText(job) {
  const saved = String(job.headline || '').trim();
  return saved || jobPreview(job).split(/(?<=[.!?])\s+(?=[A-Z])/)[0];
}

export function ago(iso, now = Date.now()) {
  if (!iso) return '–';
  const hours = (now - +new Date(iso)) / 36e5;
  if (Number.isNaN(hours)) return '–';
  return hours < 1 ? '<1h ago' : hours < 24 ? `${Math.floor(hours)}h ago` : `${Math.floor(hours / 24)}d ago`;
}

export function money(value) {
  const n = Number(value);
  if (!n) return '';
  return n >= 1000 ? `$${Math.round(n / 1000)}K` : `$${Math.round(n)}`;
}

export function budgetText(job) {
  const b = String(job.budget || '').trim();
  if (!b || /no rate|not provided/i.test(b)) return job.job_type === 'hourly' ? 'Hourly, no rate' : '–';
  if (/[$]/.test(b)) return b;
  return job.job_type === 'hourly' ? `$${b.replace(/\/hr$/, '')}/hr` : `$${b}`;
}

const join = parts => parts.filter(Boolean).join(' · ');
const engagementText = value => String(value || '').replace(/^FULL_TIME$/, 'full time').replace(/^PART_TIME$/, 'part time');

function hiresText(client) {
  if (client.hires != null && client.posted_jobs != null) return `${client.hires}/${client.posted_jobs} hires`;
  if (client.hires != null) return `${client.hires} hires`;
  if (client.posted_jobs != null) return `${client.posted_jobs} ${client.posted_jobs === 1 ? 'job' : 'jobs'} posted`;
  return '';
}

function spentText(job) {
  const client = job.client || {}, record = (job.details || {}).client_record || {};
  const spent = money(record.spend_total || client.spent);
  return spent ? `${spent} spent` : '';
}

function bidsText(job) {
  const bids = job.proposals;
  return bids == null || bids === '' ? '' : bids === 0 ? 'No bids yet' : `${bids} bids`;
}

const COUNTRY = {
  'united states': 'US', usa: 'US', 'united kingdom': 'UK', gbr: 'UK', canada: 'CA', can: 'CA',
  australia: 'AU', aus: 'AU', germany: 'DE', deu: 'DE', netherlands: 'NL', nld: 'NL', ireland: 'IE', irl: 'IE',
  'new zealand': 'NZ', nzl: 'NZ', 'united arab emirates': 'AE', are: 'AE', switzerland: 'CH', che: 'CH',
  france: 'FR', fra: 'FR', india: 'IN', ind: 'IN', 'south africa': 'ZA', zaf: 'ZA', singapore: 'SG', sgp: 'SG',
};

export function countryCode(name) {
  const text = String(name || '').trim();
  return COUNTRY[text.toLowerCase()] || (text.length <= 3 ? text.toUpperCase() : text);
}

function shortHires(client) {
  if (client.hires != null && client.posted_jobs != null) return `${client.hires}/${client.posted_jobs} hires`;
  if (client.hires != null) return `${client.hires} hires`;
  if (client.posted_jobs != null) return `${client.posted_jobs} ${client.posted_jobs === 1 ? 'job' : 'jobs'}`;
  return '';
}

/** Two short lines for the list: reputation, then money and place. */
export function clientLines(job) {
  const client = job.client || {}, record = (job.details || {}).client_record || {};
  const stars = client.rating ? `★${client.rating}${client.reviews ? ` (${client.reviews})` : ''}` : '★ –';
  return [join([stars, shortHires(client)]), join([money(record.spend_total || client.spent) || '$0', countryCode(client.country)])];
}

/** How long ago the job was posted, then how crowded it is. */
export function competitionLines(job, now = Date.now()) {
  const d = job.details || {}, bids = job.proposals;
  const bidText = bids == null || bids === '' ? 'Bids unknown' : `${bids} bids`;
  return [job.posted_date ? ago(job.posted_date, now) : '–', join([bidText, d.invites_sent ? `${d.invites_sent} invited` : ''])];
}

// Green and red follow the member-fit parts of the /find-jobs score where they
// exist, because those already weigh the member's own criteria.
const share = (value, max) => value == null || value === '' ? null : Number(value) / max;
const toneOf = part => part == null ? '' : part >= 0.7 ? 'good' : part < 0.35 ? 'bad' : '';

const shaved = (job, pattern) => (job.deduction_reasons || []).some(r => pattern.test(String(r)));

export function clientTone(job) {
  const client = job.client || {}, record = (job.details || {}).client_record || {};
  if (!client.rating || client.verified === false) return 'bad';
  if (shaved(job, /client|hired|history/i)) return 'bad';
  return client.rating >= 4.8 && Number(record.spend_total || client.spent) >= 1000 ? 'good' : '';
}

// The recency part of the score is frozen when /find-jobs saw the job, so
// freshness reads the real age instead.
export function postedTone(job, now = Date.now()) {
  const days = (now - Date.parse(job.posted_date || '')) / 864e5;
  return Number.isNaN(days) ? '' : days < 1 ? 'good' : days >= 7 ? 'bad' : days >= 3 ? 'warn' : '';
}

export function bidsTone(job) {
  const text = String(job.proposals ?? '');
  const match = text.match(/\d+/);
  if (!match) return '';
  const bids = Number(match[0]) - (/less than/i.test(text) ? 1 : 0);
  return bids <= 5 ? 'good' : bids >= 30 ? 'bad' : '';
}

export function budgetTone(job) {
  if (shaved(job, /budget|rate/i)) return 'bad';
  return job.budget ? 'good' : '';
}

/** What speaks against a job, as short warnings. Empty when nothing does. */
export function jobFlags(job) {
  const d = job.details || {}, client = job.client || {};
  const flags = [];
  if (d.total_hired) flags.push({ text: `${d.total_hired} hired`, tone: 'gone' });
  if (client.verified === false) flags.push({ text: 'payment unverified', tone: 'bar' });
  if (/FULL_TIME|30\+ hrs/i.test(job.engagement || d.engagement_type || '')) flags.push({ text: 'full time', tone: 'soft' });
  if (job.trap) flags.push({ text: job.trap, tone: 'soft' });
  return flags;
}

// The gate is 7, so everything a run logs clears it. Strong stands out above it;
// weak is a lead that only got in before the gate moved.
export function scoreTone(score) {
  return score == null ? '' : score >= 9 ? 'strong' : score < 7 ? 'weak' : '';
}

/** Everything the panel shows about the job as [label, value]; empty rows are left out. */
export function jobDetails(job, now = Date.now()) {
  const d = job.details || {}, client = job.client || {};
  // The fit is the whole score; deductions are the only thing that moves it.
  // The score is the fit minus what stands against it, both out of ten, so the only
  // thing worth adding is why a point came off.
  const parts = [job.deduction ? `minus ${job.deduction} (${(job.deduction_reasons || []).join('; ')})` : '']
    .filter(Boolean);
  const budget = budgetText(job);
  const rows = [
    ['Score', job.score != null ? join([`${job.score} of 10`, ...parts]) : ''],
    ['Fit check', job.rationale || ''],
    ['Deal', join([budget === '–' ? '' : budget, job.job_type === 'fixed' ? 'fixed price' : job.job_type === 'hourly' ? 'hourly' : '',
      engagementText(job.engagement || d.engagement_type)])],
    ['Connects', join([d.connects_cost != null ? `${d.connects_cost} connects` : '', d.boost_recommended != null ? `top slot +${d.boost_recommended}` : ''])],
    ['Competition', join([bidsText(job), d.interviewing ? `${d.interviewing} interviewing` : '', d.total_hired ? `${d.total_hired} hired` : '',
      d.invites_sent ? `${d.invites_sent} invited` : ''])],
    ['Client', join([client.rating ? `★${client.rating}${client.reviews != null ? ` from ${client.reviews} reviews` : ''}` : 'no rating yet',
      spentText(job), hiresText(client), client.verified === true ? 'payment verified' : client.verified === false ? 'payment not verified' : '',
      client.country])],
    ['Posted', job.posted_date ? ago(job.posted_date, now) : ''],
    ['They require', join([d.min_jss ? `${d.min_jss}% Job Success` : '', d.min_earnings && !/any/i.test(d.min_earnings) ? `${d.min_earnings} earned` : '',
      d.experience_level])],
  ];
  return rows.filter(([, value]) => value);
}
