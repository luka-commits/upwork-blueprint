'use client';

import Link from 'next/link';
import { Fragment, useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { BoostBlock, NextStep, TasksBlock } from './JobParts';
import {
  CLOSED,
  FILE_LABEL,
  LABEL,
  DueChip,
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

export default function LeadPage({ id }: { id: string }) {
  const { state, api, post, move, toast, closeDrawer, runCommand } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState<'conversation' | 'timeline'>('conversation');
  const [note, setNote] = useState('');
  const [followDate, setFollowDate] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const noteRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);

  useEffect(() => { closeDrawer(); }, [id]);
  useEffect(() => {
    let cancelled = false;
    api(`/api/job/${id}`).then(result => {
      if (cancelled) return;
      if (!result.ok) { setJob(null); setMissing(true); return; }
      const next = { ...result.data, artifacts: (result.data.files || []).map((file: any) => file.name) };
      setJob(next);
      setMissing(false);
      setFollowDate(next.next_follow_up || '');
      setVideoUrl(next.video || '');
    });
    return () => { cancelled = true; };
  }, [id, state?.generated_at]);

  if (missing) return <p className="empty">That job is not in the pipeline. <Link href="/">Back to all jobs</Link></p>;
  if (!job) return <p className="empty">Loading.</p>;

  const j = job, d = j.details || {}, c = j.client || {}, files: string[] = j.artifacts || [];
  const back = j.status === 'won' ? '/clients' : '/';
  const emb = j.video && embedUrl(j.video);
  const docs = ['application.md', 'loom-script.md'].filter(file => files.includes(file));
  const others = files.filter(file => file !== 'pitch.html' && !docs.includes(file));
  const hasFlags = !!(d.total_hired ||
    (d.min_jss && state?.me?.jss != null && d.min_jss > state.me.jss) ||
    /FULL_TIME|30\+ hrs/i.test(j.engagement || d.engagement_type || '') || j.trap);
  const addNote = async () => {
    const text = note.trim();
    if (!text) return noteRef.current?.focus();
    if (await post('/api/note', { id: j.id, text })) setNote('');
  };
  const saveVideo = () => {
    const url = videoUrl.trim();
    if (!url) return videoRef.current?.focus();
    post('/api/video', { id: j.id, url });
  };

  return <>
    <div className="lead-head">
      <Link className="btn" href={back}>← {j.status === 'won' ? 'All clients' : 'All jobs'}</Link>
      {j.score != null ? <Score j={j} /> : null}
      <h2>{j.title}</h2>
      <StageSelect j={j} />
      <DueChip j={j} />
      {j.url ? <a className="btn" href={j.url} target="_blank" rel="noopener" style={{ marginLeft: 'auto' }}>Open on Upwork</a> : null}
    </div>
    <div className="lead">
      <div>
        <section className="panel">
          <h3>{j.status === 'won' ? 'The project' : 'Job details'}</h3>
          <dl className="fields">
            <Field label="Budget" value={budgetText(j)} />
            <Field label="Posted" value={j.posted_date ? `${day(j.posted_date)} (${ago(j.posted_date)})` : ''} />
            <Field label="Engagement" value={[j.engagement || d.engagement_type, d.experience_level && String(d.experience_level).toLowerCase()].filter(Boolean).join(' · ')} />
            <Field label="Skills" value={(j.skills || []).join(', ')} />
            {j.status === 'won' ? <Field label="Client since" value={day(wonAt(j))} /> : null}
          </dl>
          {hasFlags ? <p style={{ margin: '10px 0 0' }}><Flags j={j} /></p> : null}
          {j.rationale ? <><h4>Why this job</h4><p style={{ fontSize: 13.5, margin: 0 }}>{j.rationale}</p></> : null}
          {j.summary ? <><h4>What they want</h4><p style={{ fontSize: 13.5, margin: 0 }}>{j.summary}</p></> : null}
          {d.description ? <details><summary style={{ marginTop: 12, fontWeight: 600, color: 'var(--brand)' }}>The full posting</summary><div className="posting">{d.description}</div></details> : null}
        </section>
        <section className="panel">
          <h3>Client</h3>
          <dl className="fields">
            <Field label="Rating" value={c.rating ? `${c.rating}★ from ${c.reviews ?? '?'} reviews` : ''} />
            <Field label="Hires" value={c.hires != null ? `${c.hires}${c.posted_jobs != null ? ` of ${c.posted_jobs} jobs posted` : ''}` : c.posted_jobs != null ? `${c.posted_jobs} jobs posted` : ''} />
            <Field label="Spent" value={(d.client_record || {}).spend_total ? money(d.client_record.spend_total) : c.spent ? money(c.spent) : ''} />
            <Field label="Payment" value={c.verified ? 'verified' : c.verified === false ? 'not verified' : ''} />
            <Field label="Location" value={[d.client_city, c.country].filter(Boolean).join(', ')} />
            <Field label="Time zone" value={d.client_timezone} />
          </dl>
          {j.status === 'new' ? <><h4>Top slot</h4><BoostBlock d={d} /></> : null}
        </section>
      </div>
      <section className="panel convo">
        <div className="convo-tabs">
          <button onClick={() => setTab('conversation')} aria-pressed={tab === 'conversation'}>Conversation</button>
          <button onClick={() => setTab('timeline')} aria-pressed={tab === 'timeline'}>Timeline</button>
        </div>
        <div className="convo-body">{tab === 'timeline' ? <Timeline j={j} /> : <Conversation j={j} inbox={!!state?.commands?.inbox} />}</div>
        <div className="composer">
          <div className="composer-row">
            <input
              ref={noteRef}
              placeholder="Add a note to the timeline: a call, a promise, what they said"
              aria-label="Note"
              value={note}
              onChange={e => setNote(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') addNote(); }}
            />
            <button onClick={addNote}>Add note</button>
          </div>
          <div className="composer-row">
            {state?.commands?.reply ? <button onClick={() => runCommand('reply', j.id)}>Draft a reply</button> : null}
            <span className="note-sm">Nothing is sent from here. Replies are drafted by /reply and go out on Upwork only after your yes.</span>
          </div>
        </div>
      </section>
      <div>
        <section className="panel">
          <h3>{j.status === 'won' ? 'Client' : 'Next step'}</h3>
          <NextStep key={`next-${j.id}`} j={j} />
          {!CLOSED.includes(j.status) ? <div className="inline-form">
            <label htmlFor="followDate" className="note-sm">Follow up on</label>
            <input type="date" id="followDate" value={followDate} onChange={e => setFollowDate(e.target.value)} />
            <button onClick={() => followDate ? move(j.id, j.status, followDate) : toast('Pick a date first.')}>Save</button>
          </div> : null}
        </section>
        <section className="panel"><h3>Tasks</h3><TasksBlock key={`tasks-${j.id}`} j={j} /></section>
        <section className="panel">
          <h3>Video</h3>
          {emb ? <div className="video"><iframe src={emb} allowFullScreen title="Video for this job" /></div> : <p className="note-sm" style={{ margin: 0 }}>Record your Loom over the pitch page, then paste the share link here.</p>}
          <div className="inline-form">
            <input ref={videoRef} placeholder="https://www.loom.com/share/…" value={videoUrl} onChange={e => setVideoUrl(e.target.value)} aria-label="Video link" />
            <button onClick={saveVideo}>Save</button>
            {j.video ? <button onClick={() => post('/api/video', { id: j.id, url: '-' })} title="Remove the link">✕</button> : null}
          </div>
        </section>
        <section className="panel">
          <h3>Pitch page</h3>
          {files.includes('pitch.html') ? <>
            <div className="preview"><iframe src={`/files/${j.id}/pitch.html`} title="Pitch page preview" loading="lazy" /></div>
            <div className="actions" style={{ marginTop: 10 }}><a className="btn" href={`/files/${j.id}/pitch.html`} target="_blank" rel="noopener">Open pitch page</a></div>
          </> : <>
            <p className="note-sm" style={{ margin: '0 0 8px' }}>No pitch page yet.</p>
            {state?.commands?.['pitch-page'] ? <button onClick={() => runCommand('pitch-page', j.id)}>Generate pitch page</button> : null}
          </>}
        </section>
        {docs.map(file => <DocSection key={file} id={j.id} file={file} />)}
        {others.length ? <section className="panel"><h3>Other files</h3>{others.map(file => <div className="file-row" key={file}><span>{file}</span><a href={`/files/${j.id}/${file}`} target="_blank" rel="noopener">Open</a></div>)}</section> : null}
      </div>
    </div>
  </>;
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
  return <ul className="tl">{items.map((item, index) => <li key={`${item.at}-${index}`}>
    <span className={`tl-dot ${item.kind}`} />
    <div>{item.text}<div className="tl-when">{stamp(item.at)}</div></div>
  </li>)}</ul>;
}

function Conversation({ j, inbox }: { j: any; inbox: boolean }) {
  const messages = (j.thread && j.thread.messages) || [];
  if (!messages.length) return <p className="empty">No conversation saved for this job yet.<br />{inbox ? 'Run /inbox to pull the thread.' : 'Once /inbox is built it pulls the client thread into this window.'}</p>;
  let last = '';
  return <>{messages.map((message: any, index: number) => {
    const date = message.at ? day(message.at) : '';
    const separator = date && date !== last;
    last = date || last;
    const meta = [message.name, message.at && new Date(message.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })].filter(Boolean).join(' · ');
    return <Fragment key={`${message.at}-${index}`}>
      {separator ? <span className="day">{date}</span> : null}
      <div className={`msg${message.from === 'me' ? ' me' : ''}`}>{message.text}<span className="msg-meta">{meta}</span></div>
    </Fragment>;
  })}</>;
}

function DocSection({ id, file }: { id: string; file: string }) {
  const { toast } = useCockpit();
  const [text, setText] = useState('Loading.');
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
  return <section className="panel">
    <h3>{FILE_LABEL[file]}</h3>
    <div className="doc">{text}</div>
    <div className="actions" style={{ marginTop: 6 }}><button onClick={copy}>Copy text</button><a className="btn" href={`/files/${id}/${file}`} target="_blank" rel="noopener">Open</a></div>
  </section>;
}
