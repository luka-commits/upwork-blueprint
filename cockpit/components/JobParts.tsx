'use client';

import { useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import {
  CLOSED,
  LABEL,
  day,
  isDue,
  money,
  short,
  todayIso,
  validVideoUrl,
  wonAt,
} from '@/lib/model';
import './lead.css';
import { DisqualifyButton } from './DisqualifyLead';

export function NextStep({ j, materialsLabel = 'Materials', salesLabel = 'Materials', replyOpen = false, onReviewReply, preparationActionsOnly = false }: {
  j: any; materialsLabel?: string; salesLabel?: string; replyOpen?: boolean; onReviewReply?: () => void; preparationActionsOnly?: boolean;
}) {
  const { state, move, runCommand, runs, toast } = useCockpit();
  const d = j.details || {};
  const files = j.artifacts || [];
  const thread = j.thread || {};
  const room = !!thread.room_id;
  const clientMessages = (thread.messages || []).filter((message: any) => message?.kind !== 'event' && message?.from !== 'me');
  const clientWaiting = room && thread.awaiting_reply_from === 'you' && clientMessages.length > 0;
  const latestClientAt = Math.max(0, ...clientMessages.map((message: any) => Date.parse(message.at) || 0));
  const hasReplyDrafts = Array.isArray(j.replies?.drafts) && j.replies.drafts.some((draft: any) => typeof draft?.text === 'string' && draft.text.trim())
    && Date.parse(j.replies.generated_at) >= latestClientAt
    && !(j.outbox?.confirmed_at && j.outbox.draft_set === j.replies.generated_at);
  const callMentioned = clientMessages.some((message: any) => /\b(call|meeting|meet|zoom|interview|chat)\b/i.test(String(message.text || '')));
  const hasFollowUpPlan = Number.isInteger(j.follow_up_plan?.step) && Number.isInteger(j.follow_up_plan?.max_steps);
  const canRun = (command: string) => !!state?.commands?.[command];
  const copyCommand = (command: string, message: string, trailing = '') => {
    navigator.clipboard.writeText(`/${command} ${j.id}${trailing ? ` ${trailing}` : ''}`).then(
      () => toast(message),
      () => toast('Copy was blocked. Open Claude Code and type the command instead.'),
    );
  };
  const interactive = (command: string, label: string, message: string, trailing = '') =>
    <button className="primary" onClick={() => copyCommand(command, message, trailing)}>{label}</button>;
  const skip = <details className="action-more next-more">
    <summary aria-label="More actions" title="More actions"><span aria-hidden="true">…</span></summary>
    <div className="action-menu">
      <DisqualifyButton job={j} />
    </div>
  </details>;

  if (j.status === 'new') {
    if (preparationActionsOnly) return <div className="next-step">{skip}</div>;
    if (!files.includes('pitch.html') || !files.includes('loom-script.md')) return <div className="next-step">
      {!canRun('pitch-page') ? <p className="say">Create the pitch page first.</p> : null}
      {canRun('pitch-page') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('pitch-page', j.id)}>Generate pitch page</button></div> : null}
      <div className="next-secondary">{skip}</div>
    </div>;
    if (!validVideoUrl(j.video)) return <div className="next-step">
      <p className="say">Record the Loom, then save its link in {materialsLabel}.</p>
      <div className="next-secondary">{skip}</div>
    </div>;
    if (runs.some(run => run.command === 'apply' && run.job === j.id && !run.done)) return <div className="next-step">
      <p className="say">Reviewing the Loom and preparing the application.</p>
    </div>;
    if (!files.includes('application.md')) return <div className="next-step">
      <p className="say">The automatic preparation stopped. Retry it in {materialsLabel}.</p>
      <div className="next-secondary">{skip}</div>
    </div>;
    return <div className="next-step">
      <p className="say">After submitting, mark this lead Applied.</p>
      {j.url ? <div className="next-primary"><a className="btn primary" href={j.url} target="_blank" rel="noopener">Review and submit on Upwork</a></div> : null}
      <div className="next-secondary">{skip}</div>
    </div>;
  }
  if (j.status === 'won') {
    if (!files.includes('project.md')) return <div className="next-step">
      <p className="say">Turn the win into a clear project. This command opens in Claude Code because it needs your contract details.</p>
      <div className="next-primary">{interactive('won', 'Copy project setup command', 'Project setup command copied. Paste it into Claude Code and add the contract details.')}</div>
    </div>;
    const nextTask = (j.tasks || []).filter((task: any) => !task.done_at)
      .sort((a: any, b: any) => String(a.due || '9999').localeCompare(String(b.due || '9999')))[0];
    if (nextTask) return <div className="next-step"><p className="say">Next: {nextTask.text}{nextTask.due ? ` by ${day(nextTask.due)}` : ''}. Prepare a delivery update only after there is checked work to report.</p></div>;
    return <div className="next-step"><p className="say">The project is set up, but no delivery task is open. Add the next real commitment to Tasks before preparing a client update.</p></div>;
  }
  if (CLOSED.includes(j.status)) return <div className="next-step">
    <p className="say">{LABEL[j.status]}{j.notes ? `: ${j.notes}` : ''}.</p>
    <div className="next-secondary"><details className="action-more next-more"><summary aria-label="More actions" title="More actions"><span aria-hidden="true">…</span></summary>
      <div className="action-menu"><button onClick={() => move(j.id, 'new')}>Reopen</button></div>
    </details></div>
  </div>;
  if (j.status === 'applied') return <div className="next-step">
    <p className="say">{room ? 'Waiting for the client.' : 'You can message once the client opens an Upwork conversation.'}</p>
  </div>;
  // The open conversation already owns message checks and reply drafting.
  if (j.status === 'replied' && replyOpen) return null;
  if (j.status === 'replied' && !room) return <div className="next-step">
    <p className="say">No conversation saved. Use Sync to load it.</p>
  </div>;
  if (j.status === 'replied' && clientWaiting) return <div className="next-step">
    <p className="say">{hasReplyDrafts ? 'A reply is prepared. Read the latest message, edit the draft and approve the exact text when you are ready.'
      : 'The client is waiting on you. Read the latest message, then draft a reply from the saved conversation.'}</p>
    {hasReplyDrafts ? !replyOpen ? <div className="next-primary">{onReviewReply
      ? <button className="primary" onClick={onReviewReply}>Review reply drafts</button>
      : <a className="btn primary" href={`/job/${j.id}`}>Review reply drafts</a>}</div> : null
      : canRun('reply') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('reply', j.id)}>Draft a reply</button></div> : null}
  </div>;
  if (j.status === 'offer') return <div className="next-step">
    <p className="say">An offer is on the table. Review the terms on Upwork; after it becomes a contract, Sync moves the job to Won.</p>
    {j.url ? <div className="next-primary"><a className="btn primary" href={j.url} target="_blank" rel="noopener">Review offer on Upwork</a></div> : null}
  </div>;
  if (isDue(j)) return <div className="next-step">
    <p className="say">A follow-up reminder is due. Review the current Upwork conversation before deciding what to send.</p>
    <div className="next-secondary">
      {room && clientMessages.length && canRun('reply') ? <button onClick={() => runCommand('reply', j.id)}>Draft a reply</button> : null}
      {!hasFollowUpPlan ? <button onClick={() => move(j.id, j.status, '+3d')}>Snooze reminder 3 days</button> : null}
    </div>
  </div>;
  if (j.status === 'replied') {
    if (!files.includes('call-prep.md') && callMentioned) return <div className="next-step">
      <p className="say">The client replied. Prepare the call around this job, your proof and the decision you need next.</p>
      {canRun('call-prep') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('call-prep', j.id)}>Prepare for the call</button></div> : null}
    </div>;
    if (!files.includes('call-prep.md')) return <div className="next-step">
      <p className="say">You replied and the client has the next move. Check the conversation for a new message before preparing anything else.</p>
    </div>;
    if (!files.includes('call-review.md')) return <div className="next-step">
      <p className="say">Call prep is ready. After the call, paste the transcript into Claude Code for a checked review.</p>
      <div className="next-primary">{interactive('call-review', 'Copy call review command', 'Call review command copied. Paste it into Claude Code and replace the transcript placeholder.', '<transcript path>')}</div>
    </div>;
    if (!files.includes('proposal.md')) return <div className="next-step">
      <p className="say">The call is reviewed. Build the proposal in Claude Code where you can answer pricing and scope questions.</p>
      <div className="next-primary">{interactive('proposal', 'Copy proposal command', 'Proposal command copied. Paste it into Claude Code to finish scope and price.')}</div>
    </div>;
    return <div className="next-step">
      <p className="say">The proposal is ready. Review it under {salesLabel}, then send it in the Upwork conversation yourself.</p>
      {j.url ? <div className="next-primary"><a className="btn primary" href={j.url} target="_blank" rel="noopener">Open conversation on Upwork</a></div> : null}
    </div>;
  }
  return <div className="next-step">
    <p className="say">Waiting on the client{j.next_follow_up ? `. Follow up on ${day(j.next_follow_up)}` : ''}.</p>
    {canRun('reply') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('reply', j.id)}>Draft a reply</button></div> : null}
  </div>;
}

export function TasksBlock({ j }: { j: any }) {
  const { post } = useCockpit();
  const [text, setText] = useState('');
  const [due, setDue] = useState('');
  const [adding, setAdding] = useState(false);
  const textRef = useRef<HTMLInputElement>(null);
  const tasks = (j.tasks || []).slice();
  const open = tasks.filter((task: any) => !task.done_at)
    .sort((a: any, b: any) => String(a.due || '9999').localeCompare(String(b.due || '9999')));
  const done = tasks.filter((task: any) => !!task.done_at)
    .sort((a: any, b: any) => String(b.done_at).localeCompare(String(a.done_at)));
  useEffect(() => { if (adding) textRef.current?.focus(); }, [adding]);

  const add = async () => {
    const value = text.trim();
    if (!value) return textRef.current?.focus();
    const ok = await post('/api/task', { id: j.id, action: 'add', text: value, ...(due ? { due } : {}) });
    if (ok) { setText(''); setDue(''); setAdding(false); }
  };

  const task = (t: any) => <li className={t.done_at ? 'done' : ''} key={t.id}>
    <input
      type="checkbox"
      checked={!!t.done_at}
      onChange={e => post('/api/task', { id: j.id, action: e.target.checked ? 'done' : 'reopen', task: t.id })}
      aria-label={t.done_at ? `Reopen ${t.text}` : `Complete ${t.text}`}
    />
    <span>{t.text}</span>
    <time className={`when${!t.done_at && t.due && t.due < todayIso() ? ' over' : ''}`}>{t.due ? short(t.due) : ''}</time>
  </li>;

  return <div className="tasks-block">
    <ul className="tasks">
      {open.length ? open.map(task) : <li className="tasks-empty">No open tasks.</li>}
    </ul>
    {done.length ? <details className="tasks-done">
      <summary>Done · {done.length}</summary>
      <ul className="tasks">{done.map(task)}</ul>
    </details> : null}
    {!adding ? <button className="task-add-toggle" onClick={() => setAdding(true)}>+ Add task</button> : <form className="task-add" onSubmit={e => { e.preventDefault(); void add(); }}>
      <input
        ref={textRef}
        placeholder="Task"
        aria-label="New task"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === 'Escape') setAdding(false); }}
      />
      <input type="date" aria-label="Due date (optional)" value={due} onChange={e => setDue(e.target.value)} />
      <button type="submit">Add</button>
    </form>}
  </div>;
}

export function BoostBlock({ d }: { d: any }) {
  if (d.boost_available === false) return <div className="boost">Boosting is not open to you on this job{d.boost_reason ? `: ${d.boost_reason}` : ''}.</div>;
  if (d.boost_recommended == null && d.boost_top_bids === undefined) return <p className="note-sm" style={{ margin: 0 }}>Competing boost bids appear after the application preview is ready.</p>;
  const bids = d.boost_top_bids;
  return <div className="boost">
    {bids == null ? 'The current bids could not be read.' : bids.length ? <>Top bids now: <b>{bids.slice(0, 3).join(' · ')}</b> Connects.</> : 'Nobody has boosted yet.'}
    {d.boost_recommended != null ? <> <b>+{d.boost_recommended} Connects</b> gets you a top slot{d.connects_cost != null ? `, ${Number(d.connects_cost) + Number(d.boost_recommended)} in total` : ''}.</> : null}
    <span className="uw-sub">A bid, charged only if you land in the paid slots{d.boost_note ? ` (${d.boost_note})` : ''}. You choose it when you send.</span>
    {d.boost_recommendation === 'skip' ? <span className="uw-sub">Upwork advises against boosting this one.</span> : null}
  </div>;
}

export function Facts({ j }: { j: any }) {
  const { state } = useCockpit();
  const d = j.details || {}, c = j.client || {};
  const facts: [string, string][] = [];
  if (d.bid_avg != null) facts.push(['Competing bids', j.job_type === 'hourly'
    ? `$${d.bid_avg}/hr average, $${d.bid_min ?? '?'} to $${d.bid_max ?? '?'}`
    : `$${d.bid_avg} average, $${d.bid_min ?? '?'} to $${d.bid_max ?? '?'}`]);
  if (d.fetched_at) facts.push(['Still open?', [
    d.total_hired && 'someone already hired',
    d.offers && 'an offer is out',
    d.interviewing && `${d.interviewing} interviewing`,
    d.invites_sent && `${d.invites_sent} invited`,
  ].filter(Boolean).join(' · ') || 'yes, nobody hired yet']);
  const me = state?.me || {};
  const bar = [d.min_jss && `JSS ${d.min_jss}%`, d.min_earnings && !/any/i.test(d.min_earnings) && `${d.min_earnings} earned`].filter(Boolean);
  if (bar.length) facts.push(['Their minimum', bar.join(' · ') + (me.jss != null && d.min_jss ? (d.min_jss > me.jss ? `, you have ${me.jss}%` : ', you clear it') : '')]);
  const rec = d.client_record || {};
  const who = [
    rec.spend_total ? `${money(rec.spend_total)} spent` : c.spent ? `${money(c.spent)} spent` : '',
    c.country,
    d.client_timezone && d.client_timezone.split('/').pop().replace(/_/g, ' '),
  ].filter(Boolean);
  if (who.length) facts.push(['Client', [...new Set(who)].join(' · ')]);
  if (!facts.length) return null;
  return <dl className="facts">{facts.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>;
}

export function FilesChecklist({ j }: { j: any }) {
  const files = j.artifacts || [];
  const item = (ok: boolean, label: string, href?: string) => <li className={ok ? 'done' : 'todo'} key={label}>
    <span className="tick">{ok ? '✓' : ''}</span>
    {ok && href ? <a href={href} target="_blank" rel="noopener">{label}</a> : label}
  </li>;
  return <ul className="checklist">
    {item(files.includes('pitch.html') && files.includes('loom-script.md'), 'Pitch page and Loom script', `/files/${j.id}/pitch.html`)}
    {item(validVideoUrl(j.video) && files.includes('application.md'), 'Loom video and application', `/files/${j.id}/application.md`)}
  </ul>;
}
