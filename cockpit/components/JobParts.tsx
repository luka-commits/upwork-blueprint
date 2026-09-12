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
  wonAt,
} from '@/lib/model';
import './lead.css';

export function NextStep({ j }: { j: any }) {
  const { state, move, runCommand } = useCockpit();
  const [reasonOpen, setReasonOpen] = useState(false);
  const [reason, setReason] = useState('');
  const reasonRef = useRef<HTMLInputElement>(null);
  const d = j.details || {};
  const files = j.artifacts || [];
  const canRun = (command: string) => !!state?.commands?.[command];
  useEffect(() => { if (reasonOpen) reasonRef.current?.focus(); }, [reasonOpen]);
  const skip = <details className="action-more next-more">
    <summary>More</summary>
    <div className="action-menu">
      {!reasonOpen ? <button onClick={() => setReasonOpen(true)}>Not a fit</button> : <div className="skip-reason">
        <input
          ref={reasonRef}
          placeholder="Why not?"
          aria-label="Reason"
          value={reason}
          onChange={e => setReason(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') void move(j.id, 'skipped', null, reason.trim() ? `not a fit: ${reason.trim()}` : 'not a fit'); }}
        />
        <button onClick={() => move(j.id, 'skipped', null, reason.trim() ? `not a fit: ${reason.trim()}` : 'not a fit')}>Skip it</button>
      </div>}
    </div>
  </details>;

  if (j.status === 'new') {
    const cost = d.connects_cost != null ? ` Applying costs ${d.connects_cost} Connects.` : '';
    if (!files.includes('pitch.html')) return <div className="next-step">
      <p className="say">Start with the pitch page, the application links to it.{cost}</p>
      {canRun('pitch-page') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('pitch-page', j.id)}>Generate pitch page</button></div> : null}
      <div className="next-secondary">
        {canRun('apply') ? <button onClick={() => runCommand('apply', j.id)}>Draft application</button> : null}
        {skip}
      </div>
    </div>;
    if (!files.includes('application.md')) return <div className="next-step">
      <p className="say">The pitch page is ready. Next, the application.{cost}</p>
      {canRun('apply') ? <div className="next-primary"><button className="primary" onClick={() => runCommand('apply', j.id)}>Draft application</button></div> : null}
      <div className="next-secondary">{skip}</div>
    </div>;
    return <div className="next-step">
      <p className="say">Everything is drafted. Record the Loom, send it on Upwork yourself, then set the stage to Applied.{cost}</p>
      {j.url ? <div className="next-primary"><a className="btn primary" href={j.url} target="_blank" rel="noopener">Open on Upwork to send</a></div> : null}
      <div className="next-secondary">{skip}</div>
    </div>;
  }
  if (j.status === 'won') return <div className="next-step"><p className="say">Client since {day(wonAt(j))}. Keep what you owe them as tasks below.</p></div>;
  if (CLOSED.includes(j.status)) return <div className="next-step">
    <p className="say">{LABEL[j.status]}{j.notes ? `: ${j.notes}` : ''}.</p>
    <div className="next-secondary"><details className="action-more next-more"><summary>More</summary>
      <div className="action-menu"><button onClick={() => move(j.id, 'new')}>Reopen</button></div>
    </details></div>
  </div>;
  if (isDue(j)) return <div className="next-step">
    <p className="say">Follow-up due. Check the proposal or the thread on Upwork and nudge the client there.</p>
    <div className="next-primary"><button className="primary" onClick={() => move(j.id, j.status, '+3d')}>Followed up, next in 3 days</button></div>
    <div className="next-secondary">
      {canRun('reply') ? <button onClick={() => runCommand('reply', j.id)}>Draft a reply</button> : null}
    </div>
  </div>;
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
  if (d.boost_recommended == null && d.boost_top_bids === undefined) return <p className="note-sm" style={{ margin: 0 }}>The competing boost bids show up here once Draft application has made the proposal preview.</p>;
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
    {item(files.includes('pitch.html'), 'Pitch page', `/files/${j.id}/pitch.html`)}
    {item(files.includes('loom-script.md'), 'Loom script', `/files/${j.id}/loom-script.md`)}
    {item(!!j.video, 'Loom video', j.video || '')}
    {item(files.includes('application.md'), 'Application', `/files/${j.id}/application.md`)}
  </ul>;
}
