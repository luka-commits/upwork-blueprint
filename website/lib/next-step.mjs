// What a lead needs next: a command to copy into Claude Code, or a sentence for
// the member's own hands, plus the other commands that fit its stage. The
// cockpit runs nothing itself.
// The stage decides what a lead carries. `new` builds the pitch page until BOTH
// files exist, then the member submits by hand, and `/find-jobs skip <id>
// <reason>` stays available on every new lead. `applied` waits. `replied`, `call` and `offer`
// answer a waiting client first and a due follow-up second, where due means
// `next_follow_up <= today`; a future date stays Waiting. `/sales-call-proposal` is offered
// in conversation, after the call, or at offer when no proposal exists. `won`
// writes the handover and records the result once. `lost` and `skipped` carry
// no task even when a date is set and a client is waiting.
//
// The list never shows a date the reader has to subtract from today: it says
// `Waiting 3 days`, `Follow up in 5 days`, `Follow up . 2 days overdue`. Overdue
// is the only red state on the board.
import { todayIso } from './dates.mjs';

const WAITING = 'Waiting for the client. /brief picks up replies.';
const NOTHING = Object.freeze({ label: '', detail: '', command: null, extras: [] });

const has = (job, name) => (job.artifacts || []).includes(name);
// Chase every two days while the client owes an answer. Short enough to stay in
// their week, long enough not to be the freelancer who writes every morning.
//
// This is the fallback, not the schedule. A lead with a planned follow-up keeps
// its lane's escalating gaps from references/follow-ups.md (hot 1, 3, 7 business
// days; warm 2, 5, 10; light 3, 7), and `next_follow_up` wins here. The two days
// apply only where nothing is planned at all, so the two numbers never disagree
// about the same lead and neither should be changed to match the other.
const CHASE_DAYS = 2;
const LANE_STEPS = { hot: 3, warm: 3, light: 2, reactivation: 2 };

export function stageEnteredAt(job) {
  const entry = [...(job.history || [])].reverse().find(item => item?.status === job.status);
  return entry?.at || job.status_updated_at || job.found_at || '';
}

function parked(job) {
  if (job.follow_up_plan) return false;
  const last = (job.follow_up_history || []).at(-1);
  if (!last || (last.action === 'cleared' && String(last.reason || '').startsWith('The client replied'))) return false;
  return last.action === 'cleared' || (last.action === 'sent'
    && (last.completed || last.step >= LANE_STEPS[last.lane]));
}

/** Whole days from a stamp to today, or null when there is no usable stamp. */
function daysSince(stamp, today) {
  const then = Date.parse(String(stamp || '').slice(0, 10) + 'T00:00:00Z');
  const now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(then) || Number.isNaN(now)) return null;
  return Math.max(0, Math.round((now - then) / 864e5));
}

/** The chase a member owes when nothing else is scheduled: due every two days. */
function chase(job, today, command, extras) {
  if (parked(job)) return step('Parked', 'The follow-up sequence has stopped. Wait for the client to return.', null, extras);
  const silent = daysSince(job.last_activity_at || stageEnteredAt(job), today);
  if (silent == null) return step('Waiting', WAITING, null, extras);
  const over = silent - CHASE_DAYS;
  if (over >= 0) {
    return step('Follow up', `No answer for ${silent} day${silent === 1 ? '' : 's'}. Draft a nudge; approve one message or send it on Upwork.`, command, extras);
  }
  return step('Waiting', `Follow up in ${-over} day${over === -1 ? '' : 's'} unless they answer.`, null, extras);
}
const step = (label, detail, command = null, extras = []) => ({ label, detail, command, extras });

export function nextStep(job, today = todayIso()) {
  const id = job.id;
  switch (job.status) {
    case 'new': {
      const skip = [`/find-jobs skip ${id} <reason>`];
      return has(job, 'pitch.html') && has(job, 'application.md')
        ? step('Finish Loom', `Record the Loom and return its URL to /proposal ${id} for ready page and application checks and republishing. Then submit on Upwork and run /proposal ${id} submitted.`, null, skip)
        : step('Build pitch page', 'Builds the pitch page and the application.', `/proposal ${id}`, skip);
    }
    case 'applied':
      return step('Waiting', WAITING);
    case 'replied':
    case 'call':
    case 'offer': {
      const proposal = `/sales-call-proposal ${id} <transcript path or notes>`;
      const extras = job.status === 'replied' || (job.status === 'offer' && !has(job, 'proposal.md')) ? [proposal] : [];
      if (job.client_waiting) return step('Reply', 'The client is waiting. Draft a reply; approve one message or send it on Upwork.', `/brief ${id}`, extras);
      if (job.next_follow_up && job.next_follow_up <= today) return step('Follow up', 'A follow-up is due. Draft a nudge; approve one message or send it on Upwork.', `/brief ${id}`, extras);
      if (job.next_follow_up && job.next_follow_up > today) return step('Waiting', `Follow up ${whenText(dueIn(job.next_follow_up, today))}.`, null, extras);
      if (job.status === 'call') {
        // Booked for later: the chase stops until the call has happened.
        if (job.call_at && job.call_at > today) {
          return step('Call booked', `The call is on ${job.call_at}. Nothing to chase until then.`);
        }
        // The call is behind us, and the one-pager is the work the stage carries.
        if (!has(job, 'proposal.md')) {
          return step('Write the proposal', 'Turns the call into the one-pager the client decides on.', proposal);
        }
        // Sent, and now it is chased like anything else the client owes an answer to.
        return chase(job, today, `/brief ${id}`);
      }
      if (job.status === 'offer') {
        return step('Review offer', 'Review the offer on Upwork. /brief moves it to Won once the contract starts.', null, extras);
      }
      // In conversation: chase until there is a call.
      return chase(job, today, `/brief ${id}`, extras);
    }
    case 'won': {
      // A won lead used to show nothing at all, which reads as finished when the work has
      // not started. The second /onboarding pass is the one step nobody else owns: it records what
      // was delivered, and that is what makes the next proposal provable.
      if (job.client_waiting) return step('Reply', 'The client is waiting. Draft a reply; approve one message or send it on Upwork.', `/brief ${id}`);
      if (has(job, 'project.md') && !job.result_recorded_at) return step('Record the result', 'After delivery: what came out of it, with a number and where it can be checked.', `/onboarding ${id}`);
      if (job.follow_up_plan?.lane === 'reactivation') {
        return job.next_follow_up && job.next_follow_up <= today
          ? step('Follow up', 'Draft a message; approve one message or send it on Upwork.', `/brief ${id}`)
          : step('Waiting', `Follow up ${whenText(dueIn(job.next_follow_up, today))}.`);
      }
      if (parked(job)) return step('Parked', 'The follow-up sequence has stopped. Wait for the client to return.');
      if (has(job, 'project.md')) return { ...NOTHING, extras: [] };
      return job.imported ? { ...NOTHING, extras: [] }
        : step('Write handover', 'Turns the contract into the handover brief and the onboarding.', `/onboarding ${id}`);
    }
    default:
      return { ...NOTHING, extras: [] };
  }
}

/** The reply drafts written after the client's latest message. Older drafts answer an old message. */
// What a member needs at a glance in the list: are we acting, waiting, or has a
// follow-up already been set, and how long has this lead sat where it sits.
/** Whole days from today to a date, negative once it is in the past. */
export function dueIn(iso, today = todayIso()) {
  if (!iso) return null;
  const then = Date.parse(`${iso}T00:00:00Z`), now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(then) || Number.isNaN(now)) return null;
  return Math.round((then - now) / 864e5);
}

/** The same number as a person would say it. */
export function whenText(days) {
  if (days == null) return '';
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days > 1) return `in ${days} days`;
  return days === -1 ? '1 day overdue' : `${-days} days overdue`;
}

export function waitingState(job, today = todayIso(), now = Date.now()) {
  const at = Date.parse(job.last_activity_at || stageEnteredAt(job));
  const days = Number.isNaN(at) ? null : Math.max(0, Math.floor((now - at) / 864e5));
  const age = days == null ? '' : days === 0 ? 'today' : days === 1 ? '1 day' : `${days} days`;
  const step = nextStep(job, today);
  const acting = Boolean(step.command) || step.label === 'Reply' || step.label === 'Follow up';
  const due = dueIn(job.next_follow_up, today);
  if (step.label !== 'Reply' && job.next_follow_up && job.next_follow_up > today) {
    return { kind: 'follow-up set', detail: `Follow up ${whenText(due)}`, age, days, due };
  }
  if (acting) {
    // A task with a date carries it: late is the only thing on this board that is red.
    const detail = step.label || 'Act';
    return { kind: 'act', detail: due != null && due < 0 ? `${detail} · ${whenText(due)}` : detail,
             age, days, due, late: due != null && due < 0 };
  }
  return { kind: 'waiting', detail: step.label === 'Parked' ? 'Parked' : age ? `Waiting ${age}` : 'Waiting', age, days, due };
}

export function replyDrafts(job) {
  const replies = job.replies || {};
  const drafts = (Array.isArray(replies.drafts) ? replies.drafts : [])
    .map(draft => ({ label: String(draft?.label || '').trim(), text: String(draft?.text || '').trim() }))
    .filter(draft => draft.text);
  if (!drafts.length) return [];
  const clientTimes = ((job.thread || {}).messages || [])
    .filter(message => message?.kind !== 'event' && message?.from !== 'me')
    .map(message => Date.parse(message.at) || 0);
  return (Date.parse(replies.generated_at) || 0) >= Math.max(0, ...clientTimes) ? drafts : [];
}
