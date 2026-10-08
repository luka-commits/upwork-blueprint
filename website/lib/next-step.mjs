// What a lead needs next: a command to copy into Claude Code, or a sentence for
// the member's own hands, plus the other commands that fit its stage. The
// cockpit runs nothing itself.
// The stage decides what a lead carries. `new` writes the application, then the
// member submits by hand (after a personal Loom when a pitch page exists), and `/find-jobs skip <id>
// <reason>` stays available on every new lead. `applied` waits. `replied`, `call` and `offer`
// answer a waiting client first and a due follow-up second, where due means
// `next_follow_up <= today`; a future date stays Waiting. The cadence is pipeline.py's:
// follow-up 1 three days after the member's unanswered message, follow-up 2 seven days
// later, then the lead is cold (status unchanged, never Lost) with one reactivation
// offer 30 days on. /brief writes every message and sends it on the member's yes, one at a time.
// A call booked for later offers `/call-prep` until its brief exists. `/sales-call-proposal`
// is offered in conversation, after the call, or at offer when no proposal exists. `won`
// writes the handover and records the result once, with no follow-ups. `lost` and `skipped` carry
// no task even when a date is set and a client is waiting.
//
// The list never shows a date the reader has to subtract from today: it says
// `Waiting 3 days`, `Follow-up 1 of 2 in 5 days`, `Follow up . 2 days overdue`. Overdue
// is the only red state on the board.
import { todayIso } from './dates.mjs';

const WAITING = 'Waiting for the client. /brief picks up replies.';
const SEND = '/brief writes it and sends it on your yes, or you send it on Upwork.';
const NOTHING = Object.freeze({ label: '', detail: '', command: null, extras: [] });

const has = (job, name) => (job.artifacts || []).includes(name);
// Follow-ups per lane, as in FOLLOW_UP_GAPS in code/pipeline.py.
const LANE_STEPS = { active: 2, cold: 1 };

export function stageEnteredAt(job) {
  const entry = [...(job.history || [])].reverse().find(item => item?.status === job.status);
  return entry?.at || job.status_updated_at || job.found_at || '';
}

function parked(job) {
  if (job.follow_up_plan) return false;
  const last = (job.follow_up_history || []).at(-1);
  // A sequence the client's own message cleared is not parked. Older entries say so only in the reason.
  const byClient = last?.by === 'client' || (!last?.by && String(last?.reason || '').startsWith('The client replied'));
  if (!last || (last.action === 'cleared' && byClient)) return false;
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

/** "Follow-up 1 of 2" from the plan, or a plain "Follow-up" when the plan has no step. */
function followUpName(job) {
  const plan = job.follow_up_plan || {};
  return plan.step && plan.max_steps ? `Follow-up ${plan.step} of ${plan.max_steps}` : 'Follow-up';
}

/** A cold lead: two follow-ups went unanswered. One reactivation offer, then it stays parked. */
function cold(job, today, command, extras) {
  const days = daysSince(job.cold_since, today);
  const since = days == null ? 'Cold' : `Cold · since ${days} day${days === 1 ? '' : 's'}`;
  if (job.follow_up_plan?.lane !== 'cold' || !job.next_follow_up) {
    return step('Parked', `${since}. The follow-up sequence has stopped. Wait for the client to return.`, null, extras);
  }
  if (job.next_follow_up <= today) return step('Offer reactivation', `${since}. ${SEND}`, command, extras);
  return step(since, `Reactivation ${whenText(dueIn(job.next_follow_up, today))}.`, null, extras);
}

/** Nothing scheduled and nobody waiting: sync sets the date whenever the member wrote last. */
function idle(job, extras) {
  return parked(job)
    ? step('Parked', 'The follow-up sequence has stopped. Wait for the client to return.', null, extras)
    : step('Waiting', WAITING, null, extras);
}
const step = (label, detail, command = null, extras = []) => ({ label, detail, command, extras });

export function nextStep(job, today = todayIso()) {
  const id = job.id;
  switch (job.status) {
    case 'new': {
      const skip = [`/find-jobs skip ${id} <reason>`];
      // A sample Loom needs no page, so the application alone is ready to submit;
      // a page beside it means the member chose a personal Loom (`/proposal <id> own`).
      if (!has(job, 'application.md')) return step('Write application', 'Writes the application with your sample Loom.', `/proposal ${id}`, skip);
      return has(job, 'pitch.html')
        ? step('Finish Loom', `Record the Loom and return its URL to /proposal ${id} for the ready check. Then submit on Upwork and run /proposal ${id} submitted.`, null, skip)
        : step('Submit', `Paste the application on Upwork and submit it, then run /proposal ${id} submitted.`, null, [`/proposal ${id} own`, ...skip]);
    }
    case 'applied':
      return step('Waiting', WAITING);
    case 'replied':
    case 'call':
    case 'offer': {
      const proposal = `/sales-call-proposal ${id} <transcript path or notes>`;
      const extras = job.status === 'replied' || (job.status === 'offer' && !has(job, 'proposal.md')) ? [proposal] : [];
      if (job.client_waiting) return step('Reply', `The client is waiting. ${SEND}`, `/brief ${id}`, extras);
      if (job.cold_since) return cold(job, today, `/brief ${id}`, extras);
      if (job.next_follow_up && job.next_follow_up <= today) return step('Follow up', `${followUpName(job)} is due. ${SEND}`, `/brief ${id}`, extras);
      if (job.next_follow_up && job.next_follow_up > today) return step('Waiting', `${followUpName(job)} ${whenText(dueIn(job.next_follow_up, today))}.`, null, extras);
      if (job.status === 'call') {
        // Booked for later: the chase stops until the call has happened, and the brief
        // for it is the one piece of work the wait carries.
        if (job.call_at && job.call_at > today) {
          if (!has(job, 'call-prep.md')) {
            return step('Prepare the call', `The call is on ${job.call_at}. Researches the client and writes your call brief.`, `/call-prep ${id}`);
          }
          return step('Call booked', `The call is on ${job.call_at}. Your call brief is ready.`);
        }
        // The call is behind us, and the one-pager is the work the stage carries.
        if (!has(job, 'proposal.md')) {
          return step('Write the proposal', 'Turns the call into the one-pager the client decides on.', proposal);
        }
        // Sent: sync schedules the follow-up whenever the member wrote last.
        return idle(job, []);
      }
      if (job.status === 'offer') {
        return step('Review offer', 'Review the offer on Upwork. /brief moves it to Won once the contract starts.', null, extras);
      }
      return idle(job, extras);
    }
    case 'won': {
      // A won lead used to show nothing at all, which reads as finished when the work has
      // not started. The second /onboarding pass is the one step nobody else owns: it records what
      // was delivered, and that is what makes the next proposal provable.
      if (job.client_waiting) return step('Reply', `The client is waiting. ${SEND}`, `/brief ${id}`);
      if (has(job, 'project.md') && !job.result_recorded_at) return step('Record the result', 'After delivery: what came out of it, with a number and where it can be checked.', `/onboarding ${id}`);
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
    const what = job.cold_since ? `${step.label} · reactivation` : followUpName(job);
    return { kind: 'follow-up set', detail: `${what} ${whenText(due)}`, age, days, due };
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
  // Drafts that already went out are history, never an option to send again.
  if (replies.sent) return [];
  const drafts = (Array.isArray(replies.drafts) ? replies.drafts : [])
    .map(draft => ({ label: String(draft?.label || '').trim(), text: String(draft?.text || '').trim() }))
    .filter(draft => draft.text);
  if (!drafts.length) return [];
  const clientTimes = ((job.thread || {}).messages || [])
    .filter(message => message?.kind !== 'event' && message?.from !== 'me')
    .map(message => Date.parse(message.at) || 0);
  return (Date.parse(replies.generated_at) || 0) >= Math.max(0, ...clientTimes) ? drafts : [];
}
