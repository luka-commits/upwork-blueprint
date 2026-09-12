'use client';

import Link from 'next/link';
import { Fragment, type ReactNode, useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { BoostBlock, NextStep, TasksBlock } from './JobParts';
import {
  CLOSED,
  FILE_LABEL,
  LABEL,
  Flags,
  Score,
  StageSelect,
  ago,
  budgetText,
  day,
  embedUrl,
  money,
  stamp,
  wonAt,
} from '@/lib/model';
import './lead.css';

export default function LeadPage({ id }: { id: string }) {
  const { state, api, post, move, closeDrawer } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState<'conversation' | 'timeline'>('conversation');
  const [note, setNote] = useState('');
  const noteRef = useRef<HTMLInputElement>(null);

  useEffect(() => { closeDrawer(); }, [id, closeDrawer]);
  useEffect(() => {
    let cancelled = false;
    api(`/api/job/${id}`).then(result => {
      if (cancelled) return;
      if (!result.ok) { setJob(null); setMissing(true); return; }
      setJob({ ...result.data, artifacts: (result.data.files || []).map((file: any) => file.name) });
      setMissing(false);
    });
    return () => { cancelled = true; };
  }, [api, id, state?.generated_at]);

  if (missing) return <p className="empty">That job is not in the pipeline. <Link href="/">Back to all jobs</Link></p>;
  if (!job) return <p className="empty">Loading.</p>;

  const j = job;
  const isClient = j.status === 'won';
  const d = j.details || {};
  const files: string[] = j.artifacts || [];
  const hasFlags = !!(d.total_hired ||
    (d.min_jss && state?.me?.jss != null && d.min_jss > state.me.jss) ||
    /FULL_TIME|30\+ hrs/i.test(j.engagement || d.engagement_type || '') || j.trap);

  const addNote = async () => {
    const text = note.trim();
    if (!text) return noteRef.current?.focus();
    if (await post('/api/note', { id: j.id, text })) setNote('');
  };

  return <main className={`lead-page ${isClient ? 'client-page' : 'pipeline-page'}`}>
    <header className="lead-head">
      <Link className="btn lead-back" href={isClient ? '/?view=Clients' : '/'}>← {isClient ? 'Clients' : 'All leads'}</Link>
      <div className="lead-identity">
        <div className="lead-kicker">
          {isClient
            ? <>Client since {day(wonAt(j))}</>
            : <><Score j={j} /><span>{LABEL[j.status] || j.status}</span></>}
        </div>
        <h1>{j.title}</h1>
      </div>
      <div className="lead-head-actions">
        <StageSelect j={j} />
        {j.url ? <a className="btn" href={j.url} target="_blank" rel="noopener">Open on Upwork</a> : null}
      </div>
    </header>

    <div className="lead">
      <aside className="lead-left">
        {isClient
          ? <ClientDetails j={j} />
          : <LeadDetails j={j} hasFlags={hasFlags} />}
      </aside>

      <ConversationPanel j={j} tab={tab} setTab={setTab} note={note} setNote={setNote} noteRef={noteRef} addNote={addNote} />

      <aside className="lead-right">
        {isClient ? <>
          <section className="panel tasks-panel">
            <h2>Tasks</h2>
            <TasksBlock key={`tasks-${j.id}`} j={j} />
          </section>
          <section className="panel checkin-panel">
            <h2>Next check-in</h2>
            <DateChip j={j} label="Next check-in" move={move} />
            <FollowUpPlan j={j} />
          </section>
          <ClientFiles j={j} />
          {j.video ? <ClientVideo j={j} /> : null}
        </> : <>
          <section className="panel next-panel">
            <h2>Next step</h2>
            <NextStep key={`next-${j.id}`} j={j} />
            {!CLOSED.includes(j.status) ? <DateChip j={j} label="Follow up" move={move} /> : null}
            <FollowUpPlan j={j} />
          </section>
          <section className="panel tasks-panel">
            <h2>Tasks</h2>
            <TasksBlock key={`tasks-${j.id}`} j={j} />
          </section>
          <section className="panel materials-panel">
            <div className="panel-heading">
              <h2>Materials</h2>
              <span>{materialCount(j, files)} of 4 ready</span>
            </div>
            <Materials j={j} files={files} />
          </section>
        </>}
      </aside>
    </div>
  </main>;
}

function LeadDetails({ j, hasFlags }: { j: any; hasFlags: boolean }) {
  const d = j.details || {};
  const c = j.client || {};
  const skillText = (j.skills || []).join(', ');
  const clientSummary = [c.country, c.rating ? `${c.rating}★` : '', c.spent ? `${money(c.spent)} spent` : ''].filter(Boolean).join(' · ');
  return <section className="panel detail-panel">
    <h2>Job details</h2>
    <dl className="fields key-fields">
      <Field label="Budget" value={budgetText(j)} />
      <Field label="Posted" value={j.posted_date ? `${day(j.posted_date)} (${ago(j.posted_date)})` : ''} />
      <Field label="Engagement" value={[j.engagement || d.engagement_type, d.experience_level && String(d.experience_level).toLowerCase()].filter(Boolean).join(' · ')} />
    </dl>
    {hasFlags ? <div className="lead-flags"><Flags j={j} /></div> : null}
    {skillText ? <Disclosure label="Skills" summary={skillText}><p>{skillText}</p></Disclosure> : null}
    {j.rationale ? <Disclosure label="Why this job" summary={j.rationale}><p>{j.rationale}</p></Disclosure> : null}
    {j.summary ? <Disclosure label="What they want" summary={j.summary}><p>{j.summary}</p></Disclosure> : null}
    <Disclosure label="Client" summary={clientSummary || 'Client details'}>
      <dl className="fields">
        <Field label="Rating" value={c.rating ? `${c.rating}★ from ${c.reviews ?? '?'} reviews` : ''} />
        <Field label="Hires" value={c.hires != null ? `${c.hires}${c.posted_jobs != null ? ` of ${c.posted_jobs} jobs posted` : ''}` : c.posted_jobs != null ? `${c.posted_jobs} jobs posted` : ''} />
        <Field label="Spent" value={(d.client_record || {}).spend_total ? money(d.client_record.spend_total) : c.spent ? money(c.spent) : ''} />
        <Field label="Payment" value={c.verified ? 'Verified' : c.verified === false ? 'Not verified' : ''} />
        <Field label="Location" value={[d.client_city, c.country].filter(Boolean).join(', ')} />
        <Field label="Time zone" value={d.client_timezone} />
      </dl>
    </Disclosure>
    {d.description ? <Disclosure label="The full posting" summary="Original Upwork brief"><div className="posting">{d.description}</div></Disclosure> : null}
  </section>;
}

function ClientDetails({ j }: { j: any }) {
  const d = j.details || {};
  const c = j.client || {};
  const name = c.name || c.company || c.company_name || d.client_name || d.client_company || j.client_name;
  const projectSummary = [budgetText(j), j.engagement || d.engagement_type].filter(Boolean).join(' · ');
  return <section className="panel detail-panel client-detail-panel">
    <h2>Client</h2>
    <dl className="fields key-fields">
      <Field label="Name" value={name} />
      <Field label="Country" value={[d.client_city, c.country].filter(Boolean).join(', ')} />
      <Field label="Spent" value={(d.client_record || {}).spend_total ? money(d.client_record.spend_total) : c.spent ? money(c.spent) : ''} />
      <Field label="Rating" value={c.rating ? `${c.rating}★${c.reviews != null ? ` from ${c.reviews} reviews` : ''}` : ''} />
    </dl>
    <Disclosure label="The project" summary={projectSummary || 'Project details'} open>
      <dl className="fields">
        <Field label="Budget" value={budgetText(j)} />
        <Field label="Engagement" value={[j.engagement || d.engagement_type, d.experience_level && String(d.experience_level).toLowerCase()].filter(Boolean).join(' · ')} />
      </dl>
      {j.summary ? <div className="project-brief"><span>What they wanted</span><p>{j.summary}</p></div> : null}
    </Disclosure>
    {d.description ? <Disclosure label="The original posting" summary="The brief this project started from"><div className="posting">{d.description}</div></Disclosure> : null}
  </section>;
}

function Disclosure({ label, summary, children, open = false }: { label: string; summary: string; children: ReactNode; open?: boolean }) {
  return <details className="lead-disclosure" open={open || undefined}>
    <summary>
      <span className="disclosure-label">{label}</span>
      <span className="disclosure-summary">{oneLine(summary)}</span>
      <span className="disclosure-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="disclosure-body">{children}</div>
  </details>;
}

function ConversationPanel({ j, tab, setTab, note, setNote, noteRef, addNote }: {
  j: any;
  tab: 'conversation' | 'timeline';
  setTab: (tab: 'conversation' | 'timeline') => void;
  note: string;
  setNote: (value: string) => void;
  noteRef: React.RefObject<HTMLInputElement | null>;
  addNote: () => void;
}) {
  const { state, runCommand } = useCockpit();
  return <section className="panel convo">
    <div className="convo-tabs">
      <button onClick={() => setTab('conversation')} aria-pressed={tab === 'conversation'}>Conversation</button>
      <button onClick={() => setTab('timeline')} aria-pressed={tab === 'timeline'}>Timeline</button>
    </div>
    <div className="convo-body">{tab === 'timeline' ? <Timeline j={j} /> : <>
      <Conversation j={j} inbox={!!state?.commands?.inbox} />
      <ReplyDrafts key={j.replies?.generated_at || 'no-drafts'} j={j} />
    </>}</div>
    <div className="composer">
      <div className="composer-row">
        <input
          ref={noteRef}
          placeholder="Add a note: a call, a promise, what they said"
          aria-label="Note"
          value={note}
          onChange={e => setNote(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') addNote(); }}
        />
        <button onClick={addNote}>Add note</button>
      </div>
      <div className="composer-note">
        <span>Notes stay here. Replies go through Upwork only after your approval.</span>
      </div>
    </div>
  </section>;
}

function ReplyDrafts({ j }: { j: any }) {
  const { state, runCommand, sendReply, runs } = useCockpit();
  const drafts = Array.isArray(j.replies?.drafts)
    ? j.replies.drafts.filter((draft: any) => draft && typeof draft.text === 'string' && draft.text.trim())
    : [];
  const draftSet = String(j.replies?.generated_at || '');
  const sentDraft = j.outbox?.confirmed_at && j.outbox?.draft_set === draftSet ? j.outbox.draft : null;
  const [texts, setTexts] = useState<string[]>(drafts.map((draft: any, index: number) =>
    sentDraft === index && typeof j.outbox?.text === 'string' ? j.outbox.text : draft.text));
  const drafting = runs.some(run => run.command === 'reply' && run.job === j.id && !run.done);
  const sending = runs.some(run => run.command === 'send-reply' && !run.done);
  const room = j.thread?.room_id;
  const canDraft = !!state?.commands?.reply && !!(j.thread?.messages || []).length;

  if (!canDraft && !drafts.length) return null;
  return <section className="reply-drafts" aria-label="Draft replies">
    <div className="reply-drafts-head">
      <div><h3>Draft replies</h3>{drafts.length ? <span>{drafts.length} options</span> : null}</div>
      {canDraft ? <button disabled={drafting || sending} onClick={() => runCommand('reply', j.id)}>
        {drafting ? 'Drafting...' : drafts.length ? 'Draft again' : 'Draft replies'}
      </button> : null}
    </div>
    {drafts.map((draft: any, index: number) => {
      const sent = sentDraft === index;
      return <div className="reply-draft" key={`${draft.label || 'Draft'}-${index}`}>
        <label htmlFor={`reply-${j.id}-${index}`}>{draft.label || `Option ${index + 1}`}</label>
        <textarea
          id={`reply-${j.id}-${index}`}
          value={texts[index] ?? ''}
          disabled={sent}
          onChange={event => setTexts(current => current.map((text, i) => i === index ? event.target.value : text))}
        />
        <div className="reply-draft-foot">
          {sent ? <span className="reply-confirmed">Sent and confirmed</span> : room ? <>
            <span>Sends this exact text to the client's Upwork chat.</span>
            <button className="primary" disabled={sending || !(texts[index] || '').trim()}
              onClick={() => sendReply(j.id, texts[index], index, draftSet)}>{sending ? 'Sending...' : 'Send'}</button>
          </> : <span>You cannot message first on a proposal. Send appears after the client replies and Upwork creates a room.</span>}
        </div>
      </div>;
    })}
  </section>;
}

function DateChip({ j, label, move }: { j: any; label: string; move: (id: string, status: string, follow?: string | null) => Promise<boolean> }) {
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(j.next_follow_up || '');
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { setDate(j.next_follow_up || ''); }, [j.next_follow_up]);
  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);
  const text = date ? `${label} ${shortDate(date)}` : `Set ${label.toLowerCase()}`;
  return <div className={`date-chip-wrap${editing ? ' editing' : ''}`}>
    <button className="date-chip" onClick={() => setEditing(true)} aria-expanded={editing}>{text}</button>
    {editing ? <input
      ref={inputRef}
      type="date"
      value={date}
      aria-label={label}
      onBlur={() => setEditing(false)}
      onChange={e => {
        const value = e.target.value;
        setDate(value);
        if (value) { void move(j.id, j.status, value); setEditing(false); }
      }}
    /> : null}
  </div>;
}

function FollowUpPlan({ j }: { j: any }) {
  const plan = j.follow_up_plan;
  if (!plan || !Number.isInteger(plan.step) || !Number.isInteger(plan.max_steps)) return null;
  const lane = String(plan.lane || 'Follow-up').replace('-', ' ');
  return <p className="say">{lane[0].toUpperCase() + lane.slice(1)} sequence, step {plan.step} of {plan.max_steps}. {plan.reason || ''}</p>;
}

function Materials({ j, files }: { j: any; files: string[] }) {
  const { state, post, runCommand, toast } = useCockpit();
  const d = j.details || {};
  const pitchReady = files.includes('pitch.html');
  const scriptReady = files.includes('loom-script.md');
  const applicationReady = files.includes('application.md');
  const canRun = (command: string) => !!state?.commands?.[command];
  const copy = (value: string) => navigator.clipboard.writeText(value).then(
    () => toast('Copied.'),
    () => toast('Copy was blocked.'),
  );
  const localLink = (name: string) => `${window.location.origin}/files/${j.id}/${name}`;
  const otherFiles = files.filter(file => !['pitch.html', 'loom-script.md', 'application.md'].includes(file));

  return <div className="materials">
    <MaterialRow label="Pitch page" ready={pitchReady} defaultOpen={!pitchReady}>
      {pitchReady ? <>
        <div className="preview"><iframe src={`/files/${j.id}/pitch.html`} title="Pitch page preview" loading="lazy" /></div>
        <div className="material-actions">
          <button onClick={() => copy(localLink('pitch.html'))}>Copy link</button>
          <a className="btn" href={`/files/${j.id}/pitch.html`} target="_blank" rel="noopener">Open</a>
        </div>
      </> : canRun('pitch-page') ? <button onClick={() => runCommand('pitch-page', j.id)}>Generate pitch page</button> : <p className="material-note">Pitch page generation is unavailable.</p>}
    </MaterialRow>

    <MaterialRow label="Loom script" ready={scriptReady} defaultOpen={pitchReady && applicationReady && !scriptReady}>
      {scriptReady
        ? <MaterialDocument id={j.id} file="loom-script.md" />
        : canRun('pitch-page') ? <button onClick={() => runCommand('pitch-page', j.id)}>Generate Loom script</button> : <p className="material-note">The Loom script is made with the pitch page.</p>}
    </MaterialRow>

    <MaterialRow label="Loom video" ready={!!j.video} defaultOpen={pitchReady && applicationReady && scriptReady && !j.video}>
      <VideoEditor j={j} post={post} copy={copy} />
    </MaterialRow>

    <MaterialRow label="Application" ready={applicationReady} defaultOpen={pitchReady && !applicationReady}>
      {applicationReady
        ? <MaterialDocument id={j.id} file="application.md" />
        : canRun('apply') ? <button onClick={() => runCommand('apply', j.id)}>Draft application</button> : <p className="material-note">Application drafting is unavailable.</p>}
      {j.status === 'new' ? <div className="boost-slot"><span>Top slot</span><BoostBlock d={d} /></div> : null}
    </MaterialRow>

    {otherFiles.length ? <div className="material-other">
      <span>Other files</span>
      <div>{otherFiles.map(file => <a key={file} href={`/files/${j.id}/${file}`} target="_blank" rel="noopener">{FILE_LABEL[file] || file}</a>)}</div>
    </div> : null}
  </div>;
}

function MaterialRow({ label, ready, defaultOpen, children }: { label: string; ready: boolean; defaultOpen?: boolean; children: ReactNode }) {
  return <details className="material-row" open={defaultOpen || undefined}>
    <summary>
      <span className={`material-state${ready ? ' ready' : ''}`} aria-hidden="true">{ready ? '✓' : ''}</span>
      <span className="material-label">{label}</span>
      <span className="material-status">{ready ? 'Ready' : 'Missing'}</span>
      <span className="material-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="material-body">{children}</div>
  </details>;
}

function MaterialDocument({ id, file }: { id: string; file: string }) {
  const { toast } = useCockpit();
  const [text, setText] = useState('Loading.');
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch(`/files/${id}/${file}`).then(async response => {
      const value = response.ok ? await response.text() : 'Could not read the file.';
      if (!cancelled) setText(value);
    });
    return () => { cancelled = true; };
  }, [id, file]);
  const copy = () => navigator.clipboard.writeText(text).then(
    () => toast('Copied.'),
    () => toast('Copy was blocked, select the text instead.'),
  );
  return <>
    <div className={`material-doc${expanded ? ' expanded' : ''}`}>{text}</div>
    <div className="material-actions">
      <button className="link" onClick={() => setExpanded(current => !current)}>{expanded ? 'Show less' : 'Show all'}</button>
      <button onClick={copy}>Copy</button>
      <a className="btn" href={`/files/${id}/${file}`} target="_blank" rel="noopener">Open</a>
    </div>
  </>;
}

function VideoEditor({ j, post, copy }: {
  j: any;
  post: (path: string, body: object) => Promise<boolean>;
  copy: (value: string) => void;
}) {
  const [url, setUrl] = useState(j.video || '');
  const [replacing, setReplacing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const emb = j.video && embedUrl(j.video);
  useEffect(() => { setUrl(j.video || ''); }, [j.video]);
  useEffect(() => { if (replacing) inputRef.current?.focus(); }, [replacing]);
  const save = async () => {
    const value = url.trim();
    if (!value) return inputRef.current?.focus();
    if (await post('/api/video', { id: j.id, url: value })) setReplacing(false);
  };
  if (!j.video || replacing) return <div className="video-input">
    <input
      ref={inputRef}
      placeholder="Paste the Loom share link"
      value={url}
      onChange={e => setUrl(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter') void save(); if (e.key === 'Escape' && j.video) setReplacing(false); }}
      aria-label="Video link"
    />
    <button onClick={save}>{j.video ? 'Replace' : 'Save link'}</button>
  </div>;
  return <>
    {emb ? <div className="video"><iframe src={emb} allowFullScreen title="Video for this job" /></div> : null}
    <div className="material-actions">
      <button onClick={() => copy(j.video)}>Copy link</button>
      <a className="btn" href={j.video} target="_blank" rel="noopener">Open</a>
      <details className="action-more">
        <summary>More</summary>
        <div className="action-menu">
          <button onClick={() => setReplacing(true)}>Replace link</button>
          <button className="danger-link" onClick={() => post('/api/video', { id: j.id, url: '-' })}>Remove video link</button>
        </div>
      </details>
    </div>
  </>;
}

function ClientFiles({ j }: { j: any }) {
  const files: any[] = j.files || [];
  return <section className="panel files-panel">
    <div className="panel-heading"><h2>Files</h2><span>{files.length}</span></div>
    {files.length ? <div className="client-files">{files.map(file => <a className="client-file" key={file.name} href={`/files/${j.id}/${file.name}`} target="_blank" rel="noopener">
      <span><b>{FILE_LABEL[file.name] || file.name}</b>{FILE_LABEL[file.name] ? <small>{file.name}</small> : null}</span>
      <time>{stamp(file.at)}</time>
    </a>)}</div> : <p className="quiet-empty">No files in this project yet.</p>}
  </section>;
}

function ClientVideo({ j }: { j: any }) {
  const { post, toast } = useCockpit();
  const emb = embedUrl(j.video);
  const copy = () => navigator.clipboard.writeText(j.video).then(() => toast('Copied.'), () => toast('Copy was blocked.'));
  return <section className="panel client-video-panel">
    <h2>Video</h2>
    {emb ? <div className="video"><iframe src={emb} allowFullScreen title="Client video" /></div> : null}
    <div className="material-actions">
      <button onClick={copy}>Copy link</button>
      <a className="btn" href={j.video} target="_blank" rel="noopener">Open</a>
      <details className="action-more">
        <summary>More</summary>
        <div className="action-menu"><button className="danger-link" onClick={() => post('/api/video', { id: j.id, url: '-' })}>Remove video link</button></div>
      </details>
    </div>
  </section>;
}

function Field({ label, value }: { label: string; value: any }) {
  return value || value === 0 ? <div><dt>{label}</dt><dd>{value}</dd></div> : null;
}

function Timeline({ j }: { j: any }) {
  const items: any[] = [];
  if (j.found_at) items.push({ at: j.found_at, kind: 'status', text: 'Found by /find-jobs' });
  (j.history || []).forEach((h: any, index: number) => {
    if (index > 0 || h.status !== 'new') items.push({ at: h.at, kind: 'status', text: `Moved to ${LABEL[h.status] || h.status}` });
  });
  (j.log || []).forEach((line: any) => items.push({ at: line.at, kind: 'note', text: line.text }));
  (j.files || []).forEach((file: any) => items.push({ at: file.at, kind: 'file', text: `${FILE_LABEL[file.name] || file.name} made` }));
  (j.tasks || []).forEach((task: any) => {
    items.push({ at: task.created_at, kind: 'task', text: `Task added: ${task.text}` });
    if (task.done_at) items.push({ at: task.done_at, kind: 'task', text: `Task done: ${task.text}` });
  });
  items.sort((a, b) => String(b.at).localeCompare(String(a.at)));
  return items.length ? <ul className="tl">{items.map((item, index) => <li key={`${item.at}-${index}`}>
    <span className={`tl-dot ${item.kind}`} />
    <div>{item.text}<div className="tl-when">{stamp(item.at)}</div></div>
  </li>)}</ul> : <p className="empty">No timeline activity yet.</p>;
}

function Conversation({ j, inbox }: { j: any; inbox: boolean }) {
  const messages = (j.thread && j.thread.messages) || [];
  if (!messages.length) return <p className="empty">No conversation saved for this job yet.<br />{inbox ? 'Run /inbox to pull the thread.' : 'Once /inbox is built it pulls the client thread into this window.'}</p>;
  let last = '';
  return <>{messages.map((message: any, index: number) => {
    const date = message.at ? day(message.at) : '';
    const separator = date && date !== last;
    last = date || last;
    const time = message.at ? new Date(message.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const meta = [message.from === 'me' ? 'You' : message.name, time].filter(Boolean).join(' · ');
    return <Fragment key={`${message.id || message.at}-${index}`}>
      {separator ? <span className="day">{date}</span> : null}
      {message.kind === 'event'
        ? <span className="msg-event">{message.text}{time ? ` · ${time}` : ''}</span>
        : <div className={`msg${message.from === 'me' ? ' me' : ''}`}><MessageText text={message.text} /><span className="msg-meta">{meta}</span></div>}
    </Fragment>;
  })}</>;
}

// Upwork sends links as <https://...> and bold as **text**; show both as a reader expects.
function MessageText({ text }: { text: string }) {
  const parts = String(text || '').split(/(<?https?:\/\/[^\s<>]+>?|\*\*[^*]+\*\*)/g);
  return <>{parts.map((part, index) => {
    if (/^<?https?:\/\//.test(part)) {
      const url = part.replace(/^<|>$/g, '');
      return <a key={index} href={url} target="_blank" rel="noopener noreferrer">{url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 48)}</a>;
    }
    if (/^\*\*[^*]+\*\*$/.test(part)) return <b key={index}>{part.slice(2, -2)}</b>;
    return <Fragment key={index}>{part}</Fragment>;
  })}</>;
}

function materialCount(j: any, files: string[]) {
  return Number(files.includes('pitch.html')) + Number(files.includes('loom-script.md')) + Number(!!j.video) + Number(files.includes('application.md'));
}

function oneLine(value: string) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}
