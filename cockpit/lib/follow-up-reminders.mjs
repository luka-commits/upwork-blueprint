const ACTIVE = new Set(['replied', 'offer', 'won']);
const JOB_ID = /^\d{6,25}$/;
const CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function validCalendarDate(value) {
  if (typeof value !== 'string') return false;
  const match = CALENDAR_DATE.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1) return false;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= days[month - 1];
}

function text(value, fallback = '') {
  return typeof value === 'string' ? value.trim() : fallback;
}

function positiveInteger(value) {
  return Number.isInteger(value) && value > 0 ? value : null;
}

function compareText(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

export function scheduledFollowUps(jobs, today) {
  if (!Array.isArray(jobs) || !validCalendarDate(today)) return [];

  return jobs.flatMap(job => {
    if (!job || typeof job !== 'object') return [];
    const id = typeof job.id === 'string' ? job.id.trim() : '';
    const status = text(job.status).toLowerCase();
    const due = job.next_follow_up;
    if (!JOB_ID.test(id) || !ACTIVE.has(status) || !validCalendarDate(due)) return [];

    const plan = job.follow_up_plan && typeof job.follow_up_plan === 'object'
      && !Array.isArray(job.follow_up_plan) ? job.follow_up_plan : {};
    const step = positiveInteger(plan.step);
    const maxSteps = positiveInteger(plan.max_steps);
    const coherentSteps = step !== null && maxSteps !== null && step <= maxSteps;

    return [{
      id,
      title: text(job.title) || 'Untitled job',
      status,
      due,
      reason: text(plan.reason),
      lane: text(plan.lane) || null,
      step: coherentSteps ? step : null,
      max_steps: coherentSteps ? maxSteps : null,
    }];
  }).sort((left, right) => compareText(left.due, right.due)
    || compareText(left.title, right.title)
    || compareText(left.id, right.id));
}
