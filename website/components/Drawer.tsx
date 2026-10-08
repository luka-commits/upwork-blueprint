'use client';

import { useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { LABEL } from '@/lib/stages.mjs';
import { deriveJobBrief } from '@/lib/job-brief.mjs';
import { ago, headlineText, jobDetails, jobFlags } from '@/lib/job-facts.mjs';
import { nextStep, replyDrafts } from '@/lib/next-step.mjs';
import { parseApplication } from '@/lib/application-review.mjs';
import { plainText } from '@/lib/plain-text.mjs';
import { artifactUrl, artifactVersion, useArtifactText } from '@/lib/artifact-content.mjs';
import CopyButton from './CopyButton';
import './drawer.css';

// Shown in their own sections; every other file is a plain link.
const SHOWN = new Set(['pitch.html', 'application.md', 'proposal.md']);

export default function Drawer() {
  const { state, api, toast, drawerId, closeDrawer } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (drawerId) requestAnimationFrame(() => closeRef.current?.focus());
  }, [drawerId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape' && drawerId) closeDrawer(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerId, closeDrawer]);

  useEffect(() => {
    document.body.classList.toggle('drawer-open', !!drawerId);
    return () => document.body.classList.remove('drawer-open');
  }, [drawerId]);

  useEffect(() => {
    if (!drawerId) { setJob(null); return; }
    setJob((current: any) => current?.id === drawerId ? current : null);
    let cancelled = false;
    void api(`/api/job/${drawerId}`).then(result => {
      if (cancelled) return;
      if (!result.ok) { toast('Could not load that job.'); closeDrawer(); return; }
      setJob(result.data);
    });
    return () => { cancelled = true; };
  }, [api, closeDrawer, drawerId, state?.generated_at, toast]);

  const step = job ? nextStep(job) : null;
  return <aside className={`drawer${drawerId ? ' open' : ''}`} aria-labelledby={drawerId ? 'drawer-title' : undefined}
    aria-hidden={!drawerId} inert={!drawerId} aria-busy={!!drawerId && !job}>
    {drawerId ? <>
      <div className="drawer-head">
        <div className="drawer-title">
          <h3 id="drawer-title">{!job ? 'Loading job' : job.url
            ? <a href={job.url} target="_blank" rel="noopener" title="Open on Upwork">{job.title}</a> : job.title}</h3>
          <button ref={closeRef} className="drawer-close" onClick={closeDrawer} aria-label="Close">✕</button>
        </div>
        {job ? <p className="drawer-headline">{headlineText(job)}</p> : null}
        {job ? <div className="drawer-stage"><span className={`stage-label stage-${job.status}`}>{LABEL[job.status] || job.status}</span></div> : null}
      </div>
      <div className="drawer-body">{job ? <>
        {step?.detail ? <section className="drawer-section" aria-label="Next step">
          <h4>Next step</h4>
          <p>{step.detail}</p>
          {step.command ? <CopyButton text={step.command} label={`Copy ${step.command}`} /> : null}
          {step.extras.length ? <p className="drawer-extras">{step.extras.map((command: string) =>
            <CopyButton key={command} compact text={command} label={command.split(' ')[0]} />)}</p> : null}
        </section> : null}
        <Conversation job={job} />
        <TheJob job={job} />
        <WorthIt job={job} />
        <Pitch job={job} />
        {(job.artifacts || []).includes('application.md') ? <Application job={job} /> : null}
        {(job.artifacts || []).includes('proposal.md') ? <Proposal job={job} /> : null}
        <Drafts job={job} />
        <OtherFiles job={job} />
      </> : <p className="empty">Loading job.</p>}</div>
    </> : null}
  </aside>;
}

/** What the client asked for. Kept short on purpose (27.09.2026).
 *
 * The drawer answers one question, do I apply, and it was answering it in six
 * bullets of scope plus eight skill chips, which is most of the posting pasted back
 * with headings on it. Three pieces of work are enough to recognise the job; the rest
 * is one click away under "Full posting". The skill chips went entirely: Upwork's tag
 * list is picked by the client from a dropdown and says nothing the outcome does not.
 */
function TheJob({ job }: { job: any }) {
  const brief = deriveJobBrief(job);
  const posting = String((job.details || {}).description || job.description || '').trim();
  const pastApplied = ['replied', 'call', 'offer', 'won', 'lost'].includes(job.status);
  return <section className="drawer-section">
    <h4>The job</h4>
    {brief.outcome ? <p className="drawer-outcome">{brief.outcome}</p> : null}
    {brief.scope.length ? <><h5>Key work</h5><ul className="drawer-list">{brief.scope.slice(0, 3).map((item: string) => <li key={item}>{item}</li>)}</ul></> : null}
    {brief.requirements.length ? <><h5>Must have</h5><ul className="drawer-list">{brief.requirements.slice(0, 4).map((item: string) => <li key={item}>{item}</li>)}</ul></> : null}
    {posting ? <details className="drawer-posting"><summary>Full posting</summary><div className="posting">{posting}</div></details>
      : pastApplied ? <p className="drawer-note">{job.url
        ? <a href={job.url} target="_blank" rel="noopener">Read the posting on Upwork</a>
        : 'The saved summary is shown above.'}</p>
        : <p className="drawer-note">Full posting comes with /proposal.</p>}
  </section>;
}

/** The facts that decide whether the job is worth an application. */
// Score, fit, Connects and competition answer one question: is this worth applying to.
// The drawer showed them at every stage, so a won client still carried the case for
// spending Connects on him, which is a decision nobody can take again.
const DECIDING = new Set(['new']);

function WorthIt({ job }: { job: any }) {
  const rows = jobDetails(job), flags = jobFlags(job);
  if (!DECIDING.has(job.status) || (!rows.length && !flags.length)) return null;
  return <section className="drawer-section">
    <h4>Worth it?</h4>
    {flags.length ? <p className="drawer-flags">{flags.map(flag => <span key={flag.text} className={`uw-flag ${flag.tone}`}>{flag.text}</span>)}</p> : null}
    <dl className="drawer-facts">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
  </section>;
}

function Pitch({ job }: { job: any }) {
  const local = (job.artifacts || []).includes('pitch.html');
  if (!job.pitch_url && !local) return null;
  return <section className="drawer-section">
    <h4>Pitch page</h4>
    {job.pitch_url
      ? <p><a href={job.pitch_url} target="_blank" rel="noopener">{job.pitch_url}</a> <CopyButton text={job.pitch_url} label="Copy link" /></p>
      : <p><a href={artifactUrl(job.id, 'pitch.html')} target="_blank" rel="noopener">Open the local pitch page</a></p>}
  </section>;
}

function Application({ job }: { job: any }) {
  const content = useArtifactText(job.id, 'application.md', artifactVersion(job.files, 'application.md'));
  if (content.status === 'loading') return <section className="drawer-section"><h4>Cover letter</h4><p className="empty">Loading.</p></section>;
  if (content.status !== 'ready') return <section className="drawer-section"><h4>Cover letter</h4>
    <p className="empty">The application could not be read. <a href={artifactUrl(job.id, 'application.md')} target="_blank" rel="noopener">Open the file</a>.</p></section>;
  const { coverLetter, answers } = parseApplication(content.text);
  return <section className="drawer-section">
    <h4>Cover letter</h4>
    <pre className="drawer-text">{coverLetter}</pre>
    <CopyButton text={coverLetter} label="Copy cover letter" />
    {answers.map((item: any, index: number) => <div key={index} className="drawer-answer">
      <h5>{item.question}</h5>
      <pre className="drawer-text">{item.answer}</pre>
      <CopyButton text={item.answer} label="Copy answer" />
    </div>)}
  </section>;
}

function Proposal({ job }: { job: any }) {
  const content = useArtifactText(job.id, 'proposal.md', artifactVersion(job.files, 'proposal.md'));
  if (content.status === 'loading') return <section className="drawer-section"><h4>Proposal</h4><p className="empty">Loading.</p></section>;
  if (content.status !== 'ready') return <section className="drawer-section"><h4>Proposal</h4>
    <p className="empty">The proposal could not be read. <a href={artifactUrl(job.id, 'proposal.md')} target="_blank" rel="noopener">Open the file</a>.</p></section>;
  return <section className="drawer-section">
    <h4>Proposal</h4>
    <pre className="drawer-text">{plainText(content.text)}</pre>
    <CopyButton text={plainText(content.text)} label="Copy proposal" />
  </section>;
}

// The client's own words, which this surface has never shown: sync saves every thread
// "for the cockpit's chat window" and there was no chat window, so a member with fifteen
// live conversations read the job posting in three sections and the client in none.
function Conversation({ job }: { job: any }) {
  const thread = job.thread || {};
  const all: any[] = Array.isArray(thread.messages) ? thread.messages : [];
  if (!all.length) {
    // A missing thread is a fact worth stating: prune follows KEEP_CHAT_HOURS (90 days by default) and only a
    // /brief run brings it back, so silence here would read as a client who said nothing.
    return <section className="drawer-section" aria-label="Conversation">
      <h4>Conversation</h4>
      <p className="muted">No saved messages. Run /brief to pull the thread again.</p>
    </section>;
  }
  const shown = all.slice(-8);
  return <section className="drawer-section" aria-label="Conversation">
    <h4>Conversation{all.length > shown.length ? ` · last ${shown.length} of ${all.length}` : ''}</h4>
    <ol className="thread">
      {shown.map((m, index) => <li key={m.id || index} className={`msg ${m.from}`}>
        <span className="msg-who">{m.from === 'me' ? 'You' : m.from === 'system' ? 'Upwork' : (m.name || 'Client')}
          {m.at ? <span className="msg-at">{ago(m.at)}</span> : null}</span>
        <p className="msg-text">{m.text}</p>
      </li>)}
    </ol>
  </section>;
}

function Drafts({ job }: { job: any }) {
  const drafts = replyDrafts(job);
  if (!drafts.length) return null;
  return <section className="drawer-section">
    <h4>Reply drafts</h4>
    {drafts.map((draft, index) => <div key={index} className="drawer-answer">
      <h5>{draft.label}</h5>
      <pre className="drawer-text">{draft.text}</pre>
      <CopyButton text={draft.text} label="Copy draft" />
    </div>)}
  </section>;
}

const GROUPS: [string, string][] = [
  ['client', 'The client sees'],
  ['send', 'You send'],
  ['asset', 'Material'],
  ['data', 'Records'],
];

function OtherFiles({ job }: { job: any }) {
  const files = (job.files || []).filter((file: any) => !SHOWN.has(file.name));
  if (!files.length) return null;
  return <>{GROUPS.map(([key, title]) => {
    const group = files.filter((file: any) => (file.role || 'data') === key);
    if (!group.length) return null;
    return <section className="drawer-section" key={key}>
      <h4>{title}</h4>
      <ul className="drawer-files">{group.map((file: any) => <li key={file.name}>
        <a href={artifactUrl(job.id, file.name, file.version)} target="_blank" rel="noopener">{file.name}</a>
      </li>)}</ul>
    </section>;
  })}</>;
}
