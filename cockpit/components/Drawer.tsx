'use client';

import Link from 'next/link';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { DueChip, Flags, Score, StageSelect, ago, budgetText, day, money, stamp, validVideoUrl, wonAt } from '@/lib/model';
import { BoostBlock, FilesChecklist, NextStep, TasksBlock } from './JobParts';
import JobBrief from './JobBrief';
import './drawer.css';

const PIPELINE_FILES = new Set(['pitch.html', 'loom-script.md', 'application.md']);

export default function Drawer() {
  const { state, api, toast, drawerId, closeDrawer } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const loadedId = useRef<string | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const focusPendingRef = useRef(false);

  useEffect(() => {
    document.body.classList.toggle('drawer-open', !!drawerId);
    return () => document.body.classList.remove('drawer-open');
  }, [drawerId]);

  useEffect(() => {
    const opening = !!drawerId;
    if (opening) {
      if (!wasOpenRef.current && document.activeElement instanceof HTMLElement) {
        returnFocusRef.current = document.activeElement;
        focusPendingRef.current = true;
      }
      requestAnimationFrame(() => {
        closeRef.current?.focus();
      });
    } else if (wasOpenRef.current) {
      const target = returnFocusRef.current;
      requestAnimationFrame(() => { if (target?.isConnected) target.focus(); });
      returnFocusRef.current = null;
    }
    wasOpenRef.current = opening;
  }, [drawerId]);

  useEffect(() => {
    if (!drawerId || !job || !focusPendingRef.current) return;
    requestAnimationFrame(() => {
      closeRef.current?.focus();
      focusPendingRef.current = false;
    });
  }, [drawerId, job]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && drawerId) closeDrawer();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerId, closeDrawer]);

  useEffect(() => {
    if (!drawerId) { loadedId.current = null; return; }
    let cancelled = false;
    const preserveScroll = loadedId.current === drawerId;
    const scroll = preserveScroll ? bodyRef.current?.scrollTop || 0 : 0;
    if (!preserveScroll) setJob(null);
    loadedId.current = drawerId;
    api(`/api/job/${drawerId}`).then(result => {
      if (cancelled) return;
      if (!result.ok) {
        if (!preserveScroll) toast('Could not load that job.');
        closeDrawer();
        return;
      }
      const card = state?.jobs?.find((item: any) => item.id === drawerId) || {};
      setJob({ ...result.data, artifacts: card.artifacts || (result.data.files || []).map((file: any) => file.name) });
      if (preserveScroll) requestAnimationFrame(() => { if (bodyRef.current) bodyRef.current.scrollTop = scroll; });
    });
    return () => { cancelled = true; };
  }, [api, closeDrawer, drawerId, state?.generated_at, toast]);

  const isClient = job?.status === 'won';
  const titleId = job ? 'drawer-title' : undefined;
  return <aside
    className={`drawer${drawerId ? ' open' : ''}`}
    aria-label={job ? undefined : 'Job details'}
    aria-labelledby={titleId}
    aria-hidden={!drawerId}
    inert={!drawerId}
    aria-busy={!!drawerId && !job}
  >
    {job ? <>
      <div className="drawer-head">
        <div className="drawer-title">
          {!isClient && job.score != null ? <Score j={job} /> : null}
          <h3 id="drawer-title">{job.url ? <a href={job.url} target="_blank" rel="noopener" title="Open on Upwork">{job.title}</a> : job.title}</h3>
          <button ref={closeRef} className="drawer-close" onClick={closeDrawer} aria-label="Close">✕</button>
        </div>
        <div className="drawer-stage">
          <StageSelect j={job} />
          {isClient ? <span className="stamp">{wonAt(job) ? `Client since ${day(wonAt(job))}` : 'Client'}</span> : <DueChip j={job} />}
        </div>
      </div>
      <div className="drawer-body" ref={bodyRef}>
        {isClient ? <ClientDrawer j={job} /> : <LeadDrawer j={job} />}
      </div>
      <div className="drawer-foot"><Link className="btn" href={`/job/${job.id}`} onClick={closeDrawer}>Open full page →</Link></div>
    </> : drawerId ? <>
      <div className="drawer-head">
        <div className="drawer-title">
          <h3>Loading job</h3>
          <button ref={closeRef} className="drawer-close" onClick={closeDrawer} aria-label="Close">✕</button>
        </div>
      </div>
      <div className="drawer-body" ref={bodyRef}><p className="empty">Loading job.</p></div>
    </> : null}
  </aside>;
}

function LeadDrawer({ j }: { j: any }) {
  const d = j.details || {};
  const files: string[] = j.artifacts || [];
  const ready = Number(files.includes('pitch.html') && files.includes('loom-script.md')) +
    Number(validVideoUrl(j.video) && files.includes('application.md'));
  return <>
    <section className="drawer-next" aria-label="Next step">
      <NextStep key={`next-${j.id}`} j={j} />
    </section>
    <LeadOverview j={j} />
    <div className="drawer-supporting">
      <DrawerDisclosure label="Materials" summary={`${ready} of 2 ready`}>
        <FilesChecklist j={j} />
        {j.status === 'new' && (d.boost_available === false || d.boost_recommended != null || d.boost_top_bids !== undefined)
          ? <div className="boost-slot"><span>Boost bids</span><BoostBlock d={d} /></div> : null}
      </DrawerDisclosure>
      {j.niche_fit != null ? <DrawerDisclosure label="Score details" summary={`${j.score ?? scoreTotal(j)} of 100`}>
        <p className="drawer-score-details">Fit {j.niche_fit} of 40 · client {j.client_trust ?? '?'} of 30 · deal {j.deal_quality ?? '?'} of 20 · fresh {j.recency ?? '?'} of 10</p>
      </DrawerDisclosure> : null}
      {d.description ? <DrawerDisclosure label="The full posting" summary="Original Upwork brief"><div className="posting">{d.description}</div></DrawerDisclosure> : null}
    </div>
    <h4>Tasks</h4><TasksBlock key={`tasks-${j.id}`} j={j} />
  </>;
}

function LeadOverview({ j }: { j: any }) {
  const { state } = useCockpit();
  const d = j.details || {}, c = j.client || {}, record = d.client_record || {};
  const terms = [budgetText(j), j.job_type === 'fixed' ? 'fixed price' : j.job_type === 'hourly' ? 'hourly' : '',
    j.engagement || d.engagement_type].filter(value => value && value !== '–').join(' · ');
  const competition = [j.proposals != null ? `${j.proposals} bids` : '', d.interviewing ? `${d.interviewing} interviewing` : '',
    d.total_hired ? `${d.total_hired} hired` : '', d.invites_sent ? `${d.invites_sent} invited` : ''].filter(Boolean).join(' · ');
  const client = [c.rating ? `${c.rating}★${c.reviews != null ? ` from ${c.reviews} reviews` : ''}` : '',
    record.spend_total ? `${money(record.spend_total)} spent` : c.spent ? `${money(c.spent)} spent` : '',
    c.posted_jobs != null ? `${c.posted_jobs} jobs posted` : '', c.verified === true ? 'payment verified' : c.verified === false ? 'payment not verified' : '',
    c.country].filter(Boolean).join(' · ');
  const requirements = [d.min_jss ? `${d.min_jss}% Job Success` : '',
    d.min_earnings && !/any/i.test(d.min_earnings) ? `${d.min_earnings} earned` : '', d.experience_level].filter(Boolean).join(' · ');
  const skills = (j.skills || []).slice(0, 6).join(', ');
  const hasFlags = !!(d.total_hired || (d.min_jss && state?.me?.jss != null && d.min_jss > state.me.jss) ||
    /FULL_TIME|30\+ hrs/i.test(j.engagement || d.engagement_type || '') || j.trap);
  return <section className="drawer-overview" aria-label="Job overview">
    <h4>Job overview</h4>
    <JobBrief job={j} />
    {j.rationale ? <div className="drawer-fit"><span>Fit check</span><p>{j.rationale}</p></div> : null}
    {hasFlags ? <div className="drawer-flags"><Flags j={j} /></div> : null}
    <dl className="drawer-quickfacts">
      <Field label="Budget" value={terms} />
      <Field label="Competition" value={competition} />
      <Field label="Client" value={client} />
      <Field label="Posted" value={j.posted_date ? `${ago(j.posted_date)} · ${day(j.posted_date)}` : ''} />
      <Field label="They require" value={requirements} />
      <Field label="Skills" value={skills} />
    </dl>
  </section>;
}

function ClientDrawer({ j }: { j: any }) {
  const projectFiles = (j.files || []).filter((file: any) => !PIPELINE_FILES.has(file.name));
  return <>
    <h4>Tasks</h4><TasksBlock key={`tasks-${j.id}`} j={j} />
    <h4>Next check-in</h4><NextCheckIn j={j} />
    <div className="drawer-supporting">
      <DrawerDisclosure label="Client and project" summary={clientSummary(j)}>
        <ClientProjectFields j={j} />
      </DrawerDisclosure>
      <DrawerDisclosure label="Files" summary={projectFiles.length ? `${projectFiles.length} project ${projectFiles.length === 1 ? 'file' : 'files'}` : 'No project files yet'}>
        {projectFiles.length ? <div className="client-files">{projectFiles.map((file: any) => <a className="client-file" key={file.name} href={`/files/${j.id}/${file.name}`} target="_blank" rel="noopener">
          <span><b>{file.name}</b></span>
          <time>{stamp(file.at)}</time>
        </a>)}</div> : <p className="quiet-empty">No project files yet.</p>}
      </DrawerDisclosure>
    </div>
  </>;
}

function NextCheckIn({ j }: { j: any }) {
  const { move } = useCockpit();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(j.next_follow_up || '');
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { setDate(j.next_follow_up || ''); }, [j.next_follow_up]);
  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);
  const text = date ? `Next check-in ${shortDate(date)}` : 'Set next check-in';
  return <div className={`date-chip-wrap${editing ? ' editing' : ''}`}>
    <button className="date-chip" onClick={() => setEditing(true)} aria-expanded={editing}>{text}</button>
    {editing ? <input
      ref={inputRef}
      type="date"
      value={date}
      aria-label="Next check-in"
      onBlur={() => setEditing(false)}
      onChange={event => {
        const value = event.target.value;
        setDate(value);
        if (value) { void move(j.id, j.status, value); setEditing(false); }
      }}
    /> : null}
  </div>;
}

function DrawerDisclosure({ label, summary, children }: {
  label: string;
  summary: string;
  children: ReactNode;
}) {
  return <details className="lead-disclosure drawer-disclosure">
    <summary>
      <span className="disclosure-label">{label}</span>
      <span className="disclosure-summary">{summary}</span>
      <span className="disclosure-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="disclosure-body">{children}</div>
  </details>;
}

function ClientProjectFields({ j }: { j: any }) {
  const d = j.details || {}, c = j.client || {};
  const name = c.name || c.company || c.company_name || d.client_name || d.client_company || j.client_name;
  return <dl className="fields">
    <Field label="Name" value={name} />
    <Field label="Location" value={[d.client_city, c.country].filter(Boolean).join(', ')} />
    <Field label="Spent" value={(d.client_record || {}).spend_total ? money(d.client_record.spend_total) : c.spent ? money(c.spent) : ''} />
    <Field label="Rating" value={c.rating ? `${c.rating}★${c.reviews != null ? ` from ${c.reviews} reviews` : ''}` : ''} />
    <Field label="Budget" value={budgetText(j)} />
    <Field label="Engagement" value={[j.engagement || d.engagement_type, d.experience_level && String(d.experience_level).toLowerCase()].filter(Boolean).join(' · ')} />
  </dl>;
}

function Field({ label, value }: { label: string; value: any }) {
  return value || value === 0 ? <div><dt>{label}</dt><dd>{value}</dd></div> : null;
}

function clientSummary(j: any) {
  const d = j.details || {}, c = j.client || {};
  const name = c.name || c.company || c.company_name || d.client_name || d.client_company || j.client_name;
  return [name, budgetText(j), j.engagement || d.engagement_type].filter(value => value && value !== '–').join(' · ') || 'Project details';
}

function scoreTotal(j: any) {
  return Number(j.niche_fit || 0) + Number(j.client_trust || 0) + Number(j.deal_quality || 0) + Number(j.recency || 0);
}

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}
