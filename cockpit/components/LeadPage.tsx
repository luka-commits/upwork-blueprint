'use client';

import Link from 'next/link';
import { Fragment, type CSSProperties, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { formatApplicationBid, parseApplication } from '@/lib/application-review.mjs';
import { revealContent } from '@/lib/surface-motion.mjs';
import { timelineView } from '@/lib/timeline.mjs';
import { artifactUrl, artifactVersion, useArtifactText } from '@/lib/artifact-content.mjs';
import { leadWorkspace, nextPreparationMaterial } from '@/lib/lead-workspace.mjs';
import { BoostBlock, NextStep, TasksBlock } from './JobParts';
import JobBrief from './JobBrief';
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
  validVideoUrl,
  wonAt,
} from '@/lib/model';
import './lead.css';
import './stage-layout.css';

type WorkspaceView = 'work' | 'conversation' | 'timeline' | 'materials';

export default function LeadPage({ id }: { id: string }) {
  const { state, api, post, move, closeDrawer } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const [missing, setMissing] = useState(false);
  const [selection, setSelection] = useState<{ workspace: string; view: WorkspaceView } | null>(null);
  const [note, setNote] = useState('');
  const [sidebars, setSidebars] = useState<{ workspace: string; context: boolean; tools: boolean } | null>(null);
  const noteRef = useRef<HTMLInputElement>(null);
  const contextToggleRef = useRef<HTMLButtonElement>(null);
  const toolsToggleRef = useRef<HTMLButtonElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!sidebars) return;
    const animation = revealContent(centerRef.current);
    return () => animation?.cancel();
  }, [sidebars]);

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
  if (!job || String(job.id) !== id) return <p className="empty">Loading.</p>;

  const j = job;
  const isClient = j.status === 'won';
  const d = j.details || {};
  const workspace = leadWorkspace(j.status);
  const workspaceKey = `${j.id}:${workspace.mode}`;
  const contextOpen = sidebars?.workspace === workspaceKey ? sidebars.context : workspace.layout.contextOpen;
  const toolsOpen = sidebars?.workspace === workspaceKey ? sidebars.tools : workspace.layout.toolsOpen;
  const setSidebar = (key: 'context' | 'tools', open: boolean) => setSidebars(current => ({
    workspace: workspaceKey,
    context: current?.workspace === workspaceKey ? current.context : workspace.layout.contextOpen,
    tools: current?.workspace === workspaceKey ? current.tools : workspace.layout.toolsOpen,
    [key]: open,
  }));
  const toggleSidebar = (key: 'context' | 'tools', open: boolean) => {
    if (!open) {
      const panel = document.getElementById(key === 'context' ? 'lead-context' : 'lead-tools');
      if (panel?.contains(document.activeElement)) {
        (key === 'context' ? contextToggleRef : toolsToggleRef).current?.focus({ preventScroll: true });
      }
    }
    setSidebar(key, open);
  };
  const tab: WorkspaceView = selection?.workspace === workspaceKey ? selection.view : workspace.defaultView as WorkspaceView;
  const setTab = (view: WorkspaceView) => {
    setSelection({ workspace: workspaceKey, view });
    document.getElementById(`workspace-tab-${view}`)?.focus({ preventScroll: true });
  };
  const hasFlags = !!(d.total_hired ||
    (d.min_jss && state?.me?.jss != null && d.min_jss > state.me.jss) ||
    /FULL_TIME|30\+ hrs/i.test(j.engagement || d.engagement_type || '') || j.trap);

  const addNote = async () => {
    const text = note.trim();
    if (!text) return noteRef.current?.focus();
    if (await post('/api/note', { id: j.id, text })) setNote('');
  };

  return <main className={`lead-page workspace-${workspace.mode} ${isClient ? 'client-page' : 'pipeline-page'}`}>
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
        {workspace.mode === 'prepare' ? <NextStep key={`next-${j.id}`} j={j} preparationActionsOnly /> : null}
      </div>
    </header>

    <div className="lead-layout-toggles" aria-label="Workspace panels">
      <button ref={contextToggleRef} className="lead-layout-toggle" aria-expanded={contextOpen} aria-controls="lead-context"
        onClick={() => toggleSidebar('context', !contextOpen)}>
        {workspace.layout.context === 'project' ? 'Project details' : 'Job details'}
      </button>
      {workspace.layout.tools ? <button ref={toolsToggleRef} className="lead-layout-toggle" aria-expanded={toolsOpen} aria-controls="lead-tools"
        onClick={() => toggleSidebar('tools', !toolsOpen)}>Sales tools</button> : null}
    </div>

    <div className={`lead stage-layout context-${contextOpen ? 'open' : 'closed'} tools-${toolsOpen ? 'open' : 'closed'}`}>
      <aside id="lead-context" className="lead-left" hidden={!contextOpen} inert={!contextOpen ? true : undefined}>
        {isClient
          ? <><ClientDetails j={j} /><section className="panel checkin-panel"><h2>Next check-in</h2><DateChip j={j} label="Next check-in" move={move} /><FollowUpPlan j={j} /></section></>
          : <LeadDetails j={j} hasFlags={hasFlags} />}
        {workspace.mode === 'prepare' ? <section className="lead-reminder" aria-label="Reminder">
          <DateChip j={j} label="Review" move={move} /><FollowUpPlan j={j} />
        </section> : null}
      </aside>

      <div ref={centerRef} className="lead-center">
        {workspace.mode !== 'sales' && workspace.mode !== 'prepare' ? <StageActions j={j} workspace={workspace} tab={tab} setTab={setTab} move={move} /> : null}
        <WorkspacePanel j={j} workspace={workspace} tab={tab} setTab={setTab} note={note} setNote={setNote} noteRef={noteRef} addNote={addNote} />
        {workspace.mode !== 'delivery' && workspace.mode !== 'sales' ? <TasksPanel j={j} /> : null}
      </div>

      {workspace.layout.tools ? <aside id="lead-tools" className="lead-right" hidden={!toolsOpen} inert={!toolsOpen ? true : undefined}>
          <section className="next-panel" aria-label="Next step">
            <NextStep key={`next-${j.id}`} j={j} materialsLabel="Preparation" salesLabel="Call and proposal"
              replyOpen={tab === 'conversation'} onReviewReply={() => setTab('conversation')} />
            {!CLOSED.includes(j.status) ? <DateChip j={j} label={workspace.mode === 'waiting' && !j.thread?.room_id ? 'Check again' : 'Follow up'} move={move} /> : null}
            <FollowUpPlan j={j} />
          </section>
          {workspace.mode === 'sales' && tab !== 'work' ? <SalesSupport j={j} open={() => setTab('work')} /> : null}
          <TasksPanel j={j} />
      </aside> : null}
    </div>
  </main>;
}

function StageActions({ j, workspace, tab, setTab, move }: {
  j: any;
  workspace: ReturnType<typeof leadWorkspace>;
  tab: WorkspaceView;
  setTab: (tab: WorkspaceView) => void;
  move: (id: string, status: string, follow?: string | null) => Promise<boolean>;
}) {
  const isClient = workspace.mode === 'delivery';
  if (isClient && j.artifacts?.includes('project.md')) return null;
  return <section className="stage-actions" aria-label={isClient ? 'Next delivery step' : 'Next step'}>
    <NextStep key={`next-${j.id}`} j={j} materialsLabel="Preparation" salesLabel="Call and proposal"
      replyOpen={tab === 'conversation'} onReviewReply={() => setTab('conversation')} />
    {!isClient && !CLOSED.includes(j.status) ? <DateChip j={j} label={workspace.mode === 'waiting' && !j.thread?.room_id ? 'Check again' : 'Follow up'} move={move} /> : null}
    {!isClient ? <FollowUpPlan j={j} /> : null}
  </section>;
}

function TasksPanel({ j }: { j: any }) {
  return <section className="panel tasks-panel"><h2>Tasks</h2><TasksBlock key={`tasks-${j.id}`} j={j} /></section>;
}

function LeadDetails({ j, hasFlags }: { j: any; hasFlags: boolean }) {
  const d = j.details || {};
  const c = j.client || {};
  const skillText = (j.skills || []).join(', ');
  const clientSummary = [c.country, c.rating ? `${c.rating}★` : '', c.spent ? `${money(c.spent)} spent` : ''].filter(Boolean).join(' · ');
  return <section className="panel detail-panel">
    <h2>Job details</h2>
    <JobBrief job={j} />
    {j.rationale ? <Disclosure label="Why this job" summary={j.rationale}><p>{j.rationale}</p></Disclosure> : null}
    {hasFlags ? <div className="lead-flags"><Flags j={j} /></div> : null}
    <dl className="fields key-fields">
      <Field label="Budget" value={budgetText(j)} />
      <Field label="Application" value={d.connects_cost != null ? `${d.connects_cost} Connects` : ''} />
      <Field label="Posted" value={j.posted_date ? `${day(j.posted_date)} (${ago(j.posted_date)})` : ''} />
      <Field label="Engagement" value={[j.engagement || d.engagement_type, d.experience_level && String(d.experience_level).toLowerCase()].filter(Boolean).join(' · ')} />
    </dl>
    {skillText ? <Disclosure label="Skills" summary={skillText}><p>{skillText}</p></Disclosure> : null}
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

function WorkspacePanel({ j, workspace, tab, setTab, note, setNote, noteRef, addNote }: {
  j: any;
  workspace: ReturnType<typeof leadWorkspace>;
  tab: WorkspaceView;
  setTab: (tab: WorkspaceView) => void;
  note: string;
  setNote: (value: string) => void;
  noteRef: React.RefObject<HTMLInputElement | null>;
  addNote: () => void;
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const previousTab = useRef(tab);
  useLayoutEffect(() => {
    if (previousTab.current === tab) return;
    previousTab.current = tab;
    const animation = revealContent(contentRef.current);
    return () => animation?.cancel();
  }, [tab]);
  const files: string[] = j.artifacts || [];
  const hasTabs = workspace.tabs.length > 1;
  const selectByKey = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % workspace.tabs.length;
    else if (event.key === 'ArrowLeft') next = (index + workspace.tabs.length - 1) % workspace.tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = workspace.tabs.length - 1;
    else return;
    event.preventDefault();
    setTab(workspace.tabs[next].key as WorkspaceView);
  };
  return <section className={`panel workspace-panel${tab === 'conversation' ? ' is-conversation' : ''}`} aria-label={workspace.label}>
    {hasTabs ? <div className="workspace-tabs" role="tablist" aria-label={workspace.label}
      style={{ '--tab-count': workspace.tabs.length, '--tab-index': workspace.tabs.findIndex(item => item.key === tab) } as CSSProperties}>
      {workspace.tabs.map((item, index) => <button key={item.key} id={`workspace-tab-${item.key}`} role="tab"
        aria-selected={tab === item.key} aria-controls="workspace-content" tabIndex={tab === item.key ? 0 : -1}
        onClick={() => setTab(item.key as WorkspaceView)} onKeyDown={event => selectByKey(event, index)}>{item.label}</button>)}
    </div> : null}
    <div ref={contentRef} id="workspace-content" role={hasTabs ? 'tabpanel' : undefined} aria-labelledby={hasTabs ? `workspace-tab-${tab}` : undefined} tabIndex={hasTabs ? 0 : undefined}
      className={tab === 'conversation' ? 'convo-body' : 'workspace-content'}>
      {tab === 'timeline' ? <Timeline j={j} /> : null}
      <div className="workspace-conversation" hidden={tab !== 'conversation'}>
        <Conversation j={j} />
        <ReplyDrafts key={`${j.id}:${j.replies?.generated_at || 'no-drafts'}`} j={j} />
      </div>
      {workspace.tabs.some(item => item.key === 'materials') ? <div hidden={tab !== 'materials'}>
        <WorkspaceHeading title={workspace.mode === 'closed' ? 'Saved materials' : workspace.mode === 'delivery' ? 'Winning materials' : 'Application materials'}
          hint={workspace.mode === 'delivery' ? 'The pitch, application and sales work that led to this project.' : 'Your pitch, recording and application stay here as the lead moves forward.'} />
        <Materials j={j} files={files} includeSales={workspace.mode !== 'sales'} />
      </div> : null}
      <div hidden={tab !== 'work'}>
      {workspace.mode === 'prepare' ? <>
        <WorkspaceHeading title="Your application" />
        <Materials j={j} files={files} />
      </> : null}
      {workspace.mode === 'waiting' ? <ApplicationStatus j={j} open={setTab} /> : null}
      {workspace.mode === 'sales' ? <>
        <WorkspaceHeading title="Call and proposal" hint="Go into the call with a plan. Turn the actual conversation into scope and an offer." />
        <SalesMaterials j={j} files={files} />
      </> : null}
      {workspace.mode === 'delivery' ? <>
        <WorkspaceHeading title="Deliver the project" hint="Keep the next commitment clear, report checked work and finish with a clean handover." />
        <section className="delivery-tasks"><h3>Tasks</h3><TasksBlock key={`delivery-tasks-${j.id}`} j={j} /></section>
        <ClientFiles j={j} embedded />
      </> : null}
      </div>
    </div>
    <div className="composer">
      <div className="composer-row">
        <input
          ref={noteRef}
          placeholder="Add a private note"
          aria-label="Note"
          value={note}
          onChange={e => setNote(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') addNote(); }}
        />
        <button onClick={addNote}>Add note</button>
      </div>
    </div>
  </section>;
}

function WorkspaceHeading({ title, hint }: { title: string; hint?: string }) {
  return <div className="workspace-heading"><h2>{title}</h2>{hint ? <p>{hint}</p> : null}</div>;
}

function ApplicationStatus({ j, open }: { j: any; open: (view: WorkspaceView) => void }) {
  const hasReply = (j.thread?.messages || []).some((message: any) => message?.from === 'client' && message?.kind !== 'event');
  const appliedAt = !j.application_date_unknown && (j.applied_at || j.history?.find((event: any) => event.status === 'applied')?.at);
  const applicationSaved = j.artifacts?.includes('application.md');
  return <>
    <WorkspaceHeading title={hasReply ? 'A client reply is saved' : 'Waiting for the client'}
      hint={hasReply ? 'Use Sync to update this lead from Applied to In conversation.' : undefined} />
    <div className="application-status-card">
      <h3>{appliedAt ? `Applied ${day(appliedAt)}` : 'Submission date not recorded'}</h3>
      <p>{j.thread?.room_id ? 'Read the latest conversation before following up.'
        : 'You can send a message once the client opens an Upwork conversation.'}</p>
    </div>
    <div className="saved-application">
      <div><h3>{applicationSaved ? 'Application draft' : 'No application draft saved'}</h3>
        <p>{applicationSaved ? 'Your local draft may differ from the submitted application.'
          : 'Applications sent outside the cockpit may have no local copy.'}</p></div>
      <button onClick={() => open('materials')}>View materials</button>
    </div>
  </>;
}

function SalesSupport({ j, open }: { j: any; open: () => void }) {
  const files: string[] = j.artifacts || [];
  const saved = [['call-prep.md', 'Call prep'], ['call-review.md', 'Call review'], ['proposal.md', 'Proposal']];
  return <section className="panel sales-support">
    <h2>Sales tools</h2>
    <LeadMagnetBuilder j={j} />
    <ul>{saved.map(([file, label]) => <li key={file}><span>{label}</span><span className={files.includes(file) ? 'ready' : ''}>{files.includes(file) ? 'Ready' : 'Not prepared'}</span></li>)}</ul>
    <button onClick={open}>Open sales workspace</button>
  </section>;
}

function LeadMagnetBuilder({ j }: { j: any }) {
  const { state, post, runCommand, runs } = useCockpit();
  const source = j.lead_magnet_source || {};
  const ready = (j.artifacts || []).includes('lead-magnet.html');
  const [editing, setEditing] = useState(!source.website);
  const [website, setWebsite] = useState(source.website || '');
  const [location, setLocation] = useState(source.location || '');
  const [placeId, setPlaceId] = useState(source.place_id || '');
  const [language, setLanguage] = useState(source.language === 'German' ? 'German' : 'English');
  const running = runs.some(run => run.command === 'lead-magnet' && run.job === j.id && !run.done);
  const available = !!state?.commands?.['lead-magnet'];
  const valid = /^https:\/\/[^\s]+\.[^\s]+/.test(website.trim()) && !!location.trim();
  useEffect(() => {
    setWebsite(source.website || '');
    setLocation(source.location || '');
    setPlaceId(source.place_id || '');
    setLanguage(source.language === 'German' ? 'German' : 'English');
    if (source.website) setEditing(false);
  }, [source.website, source.location, source.place_id, source.language]);
  const start = async () => {
    if (!valid || running) return;
    const saved = await post('/api/lead-magnet-source', {
      id: j.id,
      website: website.trim(),
      location: location.trim(),
      place_id: placeId.trim(),
      language,
    });
    if (saved) {
      setEditing(false);
      const target = website.trim().replace(/^https?:\/\/(?:www\.)?/, '').replace(/\/$/, '');
      if (!window.confirm(`Start paid Firecrawl, Apify and DataForSEO calls for ${target}? Nothing will be sent or published.`)) return;
      runCommand('lead-magnet', j.id);
    }
  };
  return <div className="lead-magnet-tool">
    <div className="lead-magnet-head">
      <div><strong>Local visibility audit</strong></div>
      <span className={ready ? 'ready' : ''}>{ready ? 'Ready' : 'Not created'}</span>
    </div>
    {ready && !editing ? <a className="btn lead-magnet-open" href={artifactUrl(j.id, 'lead-magnet.html', artifactVersion(j.files, 'lead-magnet.html'))} target="_blank" rel="noopener">Open private audit</a> : null}
    {!editing && source.website ? <div className="lead-magnet-source">
      <span>{source.website.replace(/^https?:\/\/(?:www\.)?/, '').replace(/\/$/, '')}</span>
      <small>{source.location}</small>
      <button className="link" onClick={() => setEditing(true)}>Change</button>
    </div> : <div className="lead-magnet-fields">
      <label>Business website<input type="url" value={website} placeholder="https://business.com" onChange={event => setWebsite(event.target.value)} /></label>
      <label>City and country<input value={location} placeholder="Manchester, United Kingdom" onChange={event => setLocation(event.target.value)} /></label>
      <details><summary>Exact profile or language</summary><label>Google place ID<input value={placeId} placeholder="Optional unless locations are ambiguous" onChange={event => setPlaceId(event.target.value)} /></label>
        <label>Search language<select value={language} onChange={event => setLanguage(event.target.value)}><option>English</option><option>German</option></select></label></details>
    </div>}
    <p className="paid-note"><strong>Costs apply:</strong> Firecrawl, Apify and DataForSEO. Nothing is sent or published.</p>
    {available ? <button className={ready ? undefined : 'primary'} disabled={!valid || running} onClick={() => void start()}>{running ? 'Building audit...' : ready ? 'Rebuild audit' : 'Create SEO audit'}</button>
      : <p className="material-note">SEO audit creation is unavailable.</p>}
  </div>;
}

function ReplyDrafts({ j }: { j: any }) {
  const { state, post, runCommand, sendReply, runs, toast } = useCockpit();
  const drafts = Array.isArray(j.replies?.drafts)
    ? j.replies.drafts.filter((draft: any) => draft && typeof draft.text === 'string' && draft.text.trim())
    : [];
  const draftSet = String(j.replies?.generated_at || '');
  const sentDraft = j.outbox?.confirmed_at && j.outbox?.draft_set === draftSet ? j.outbox.draft : null;
  const [texts, setTexts] = useState<string[]>(drafts.map((draft: any, index: number) =>
    sentDraft === index && typeof j.outbox?.text === 'string' ? j.outbox.text : draft.text));
  const drafting = runs.some(run => run.command === 'reply' && run.job === j.id && !run.done);
  const sending = runs.some(run => run.command === 'send-reply' && run.job === j.id && !run.done);
  const room = j.thread?.room_id;
  const canDraft = !!state?.commands?.reply && !!(j.thread?.messages || []).length;
  const uncertain = !!j.outbox && !j.outbox.confirmed_at && !j.outbox.cancelled_at && !sending;
  const copy = (value: string) => navigator.clipboard.writeText(value).then(
    () => toast('Reply copied.'),
    () => toast('Copy was blocked. Select the reply text instead.'),
  );

  if (!canDraft && !drafts.length && !uncertain) return null;
  return <section className="reply-drafts" aria-label="Draft replies">
    {uncertain ? <div className="send-uncertain" role="alert">
      <strong>Send not confirmed</strong>
      <p>Check this conversation on Upwork before trying again.</p>
      <div>
        {j.url ? <a className="btn" href={j.url} target="_blank" rel="noopener">Open Upwork conversation</a> : null}
        <button onClick={() => {
          if (window.confirm('Only continue after you checked Upwork and confirmed the message was not sent. Clear the send lock?')) {
            void post('/api/reply/resolve', { job: j.id, written_at: j.outbox.written_at });
          }
        }}>I checked: message was not sent</button>
      </div>
      <small>This only clears the lock. It never sends a message.</small>
    </div> : null}
    <div className="reply-drafts-head">
      <div><h3>Draft replies</h3>{drafts.length ? <span>{drafts.length} {drafts.length === 1 ? 'option' : 'options'}</span> : null}</div>
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
            <div className="reply-draft-actions">
              <button onClick={() => copy(texts[index] || '')}>Copy</button>
              <button className="primary" disabled={sending || !(texts[index] || '').trim()}
                onClick={() => sendReply(j.id, texts[index], index, draftSet)}>{sending ? 'Sending...' : 'Send exact reply'}</button>
            </div>
          </> : <>
            <span>No Upwork chat room yet. Copy this draft if the client contacts you elsewhere on Upwork.</span>
            <button disabled={!(texts[index] || '').trim()} onClick={() => copy(texts[index] || '')}>Copy reply</button>
          </>}
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

function Materials({ j, files, includeSales = true }: { j: any; files: string[]; includeSales?: boolean }) {
  const { state, post, runCommand, toast } = useCockpit();
  const d = j.details || {};
  const pitchReady = files.includes('pitch.html');
  const scriptReady = files.includes('loom-script.md');
  const applicationReady = files.includes('application.md');
  const videoReady = validVideoUrl(j.video);
  const applicationUnlocked = pitchReady && videoReady;
  const nextMaterial = j.status === 'new' ? nextPreparationMaterial(files, videoReady) : null;
  const applicationBlocker = !pitchReady && !videoReady
    ? 'Add the pitch page and video first.'
    : !pitchReady ? 'Add the pitch page first.' : !videoReady ? 'Add a Loom or YouTube video first.' : '';
  const canRun = (command: string) => !!state?.commands?.[command];
  const copy = (value: string) => navigator.clipboard.writeText(value).then(
    () => toast('Copied.'),
    () => toast('Copy was blocked.'),
  );
  const journeyFiles = ['loom-review.md', 'call-prep.md', 'call-review.md', 'proposal.md'];
  const deliveryFiles = j.status === 'won' ? ['project.md', 'delivery.md', 'client-handover.md', 'review-request.md'] : [];
  const otherFiles = files.filter(file => !['pitch.html', 'loom-script.md', 'application.md', ...journeyFiles, ...deliveryFiles].includes(file));
  const version = (file: string) => artifactVersion(j.files, file);

  return <div className="materials">
    <MaterialRow label="Pitch page" ready={pitchReady} defaultOpen={nextMaterial === 'pitch'}>
      {pitchReady ? <>
        <div className="preview"><iframe src={artifactUrl(j.id, 'pitch.html', version('pitch.html'))} title="Pitch page preview" loading="lazy" /></div>
        <div className="material-actions">
          <a className="btn" href={artifactUrl(j.id, 'pitch.html', version('pitch.html'))} target="_blank" rel="noopener">Open local preview</a>
        </div>
        <PitchUrlEditor j={j} post={post} copy={copy} />
      </> : canRun('pitch-page') ? <button className={nextMaterial === 'pitch' ? 'primary' : undefined} onClick={() => runCommand('pitch-page', j.id)}>Generate pitch page</button> : <p className="material-note">Pitch page generation is unavailable.</p>}
    </MaterialRow>

    <MaterialRow label="Loom script" ready={scriptReady} defaultOpen={nextMaterial === 'script'}>
      {scriptReady
        ? <MaterialDocument id={j.id} file="loom-script.md" version={version('loom-script.md')} />
        : canRun('pitch-page') ? <button className={nextMaterial === 'script' ? 'primary' : undefined} onClick={() => runCommand('pitch-page', j.id)}>Generate Loom script</button> : <p className="material-note">The Loom script is made with the pitch page.</p>}
    </MaterialRow>

    <MaterialRow label="Loom video" ready={videoReady} defaultOpen={nextMaterial === 'video'}>
      <VideoEditor j={j} post={post} copy={copy} />
    </MaterialRow>

    {(videoReady || files.includes('loom-review.md')) ? <MaterialRow label="Loom review" ready={files.includes('loom-review.md')}>
      {files.includes('loom-review.md') ? <MaterialDocument id={j.id} file="loom-review.md" version={version('loom-review.md')} />
        : <CommandHandoff command="loom-review" job={j} trailing="<transcript path>" label="Copy Loom review command" hint="Paste it into Claude Code and replace the placeholder with the Loom transcript path." />}
    </MaterialRow> : null}

    <MaterialRow label="Application" ready={applicationReady} defaultOpen={nextMaterial === 'application'} status={!applicationReady && !applicationUnlocked ? 'Locked' : undefined}>
      {applicationReady
        ? <ApplicationReview j={j} />
        : canRun('apply') ? <>
          <button className={nextMaterial === 'application' ? 'primary' : undefined} disabled={!applicationUnlocked} title={applicationBlocker || undefined} onClick={() => runCommand('apply', j.id)}>Draft application</button>
          {applicationBlocker ? <p className="material-note material-blocker">{applicationBlocker}</p> : null}
        </> : <p className="material-note">Application drafting is unavailable.</p>}
      {j.status === 'new' && (d.boost_available === false || d.boost_recommended != null || d.boost_top_bids !== undefined)
        ? <div className="boost-slot"><span>Boost bids</span><BoostBlock d={d} /></div> : null}
    </MaterialRow>

    {includeSales && (j.status === 'replied' || j.status === 'offer' || ['call-prep.md', 'call-review.md', 'proposal.md'].some(file => files.includes(file))) ? <>
      <div className="material-section-label">Conversation to offer</div>
      <SalesMaterials j={j} files={files} />
    </> : null}

    {otherFiles.length ? <div className="material-other">
      <span>Other files</span>
      <div>{otherFiles.map(file => <a key={file} href={`/files/${j.id}/${file}`} target="_blank" rel="noopener">{FILE_LABEL[file] || file}</a>)}</div>
    </div> : null}
  </div>;
}

function SalesMaterials({ j, files }: { j: any; files: string[] }) {
  const { state, runCommand } = useCockpit();
  const prepared = files.includes('call-prep.md'), reviewed = files.includes('call-review.md'), proposed = files.includes('proposal.md');
  return <div className="materials sales-materials">
    <div className="sales-lead-magnet"><LeadMagnetBuilder j={j} /></div>
    <MaterialRow label="Call prep" ready={prepared} defaultOpen={!reviewed && !proposed}>
      {prepared ? <MaterialDocument id={j.id} file="call-prep.md" version={artifactVersion(j.files, 'call-prep.md')} /> : <>
        <p className="material-note">A focused agenda, discovery questions, relevant proof and the decision to reach. Use Upwork's meeting tools before a contract starts.</p>
        {state?.commands?.['call-prep'] ? <button onClick={() => runCommand('call-prep', j.id)}>Prepare for the call</button> : <p className="material-note">Call prep is unavailable.</p>}
      </>}
    </MaterialRow>
    <MaterialRow label="Call review" ready={reviewed} defaultOpen={prepared && !reviewed}>
      {reviewed ? <MaterialDocument id={j.id} file="call-review.md" version={artifactVersion(j.files, 'call-review.md')} />
        : <CommandHandoff command="call-review" job={j} trailing="<transcript path>" label="Copy call review command" hint="After the call, paste this into Claude Code with the transcript. The review separates agreed scope from unanswered questions." />}
    </MaterialRow>
    <MaterialRow label="Proposal" ready={proposed} defaultOpen={reviewed}>
      {proposed ? <MaterialDocument id={j.id} file="proposal.md" version={artifactVersion(j.files, 'proposal.md')} />
        : reviewed ? <CommandHandoff command="proposal" job={j} label="Copy proposal command" hint="Paste it into Claude Code to settle scope, price and the terms you approve." />
          : <p className="material-note">Review the call transcript first so the proposal uses agreed scope, not assumptions.</p>}
    </MaterialRow>
  </div>;
}

function PitchUrlEditor({ j, post, copy }: {
  j: any;
  post: (path: string, body: object) => Promise<boolean>;
  copy: (value: string) => void;
}) {
  const [url, setUrl] = useState(j.pitch_url || '');
  const [editing, setEditing] = useState(!j.pitch_url);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { setUrl(j.pitch_url || ''); setEditing(!j.pitch_url); }, [j.pitch_url]);
  useEffect(() => { if (editing && j.pitch_url) inputRef.current?.focus(); }, [editing, j.pitch_url]);
  const save = async () => {
    const value = url.trim();
    if (!value) return inputRef.current?.focus();
    if (await post('/api/pitch', { id: j.id, url: value })) setEditing(false);
  };
  return <div className="public-link">
    <div className="public-link-head">
      <div><b>Public pitch URL</b><span>The client-ready link. The local preview above stays on this computer.</span></div>
      {j.pitch_url && !editing ? <span className="public-link-ready">Ready</span> : null}
    </div>
    {editing ? <div className="video-input">
      <input ref={inputRef} type="url" placeholder="https://your-pitch-page.com" value={url} aria-label="Public pitch URL"
        onChange={event => setUrl(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') void save(); if (event.key === 'Escape' && j.pitch_url) setEditing(false); }} />
      <button onClick={save}>Save URL</button>
    </div> : <div className="material-actions">
      <button className="primary" onClick={() => copy(j.pitch_url)}>Copy public link</button>
      <a className="btn" href={j.pitch_url} target="_blank" rel="noopener">Open public page</a>
      <button className="link" onClick={() => setEditing(true)}>Change</button>
    </div>}
  </div>;
}

function CommandHandoff({ command, job, label, hint, trailing = '' }: { command: string; job: any; label: string; hint: string; trailing?: string }) {
  const { toast } = useCockpit();
  const copy = () => navigator.clipboard.writeText(`/${command} ${job.id}${trailing ? ` ${trailing}` : ''}`).then(
    () => toast(`${label.replace(/^Copy /, '')} copied.`),
    () => toast(`Copy was blocked. Type /${command} in Claude Code instead.`),
  );
  return <div className="command-handoff"><p>{hint}</p><button onClick={copy}>{label}</button></div>;
}

function MaterialRow({ label, ready, defaultOpen, status, children }: { label: string; ready: boolean; defaultOpen?: boolean; status?: string; children: ReactNode }) {
  const wasOpen = useRef(!!defaultOpen);
  return <details className="material-row" open={defaultOpen || undefined} onToggle={event => {
    const opened = event.currentTarget.open;
    if (opened && !wasOpen.current) revealContent(event.currentTarget.querySelector('.material-body'));
    wasOpen.current = opened;
  }}>
    <summary>
      <span className={`material-state${ready ? ' ready' : ''}`} aria-hidden="true">{ready ? '✓' : ''}</span>
      <span className="material-label">{label}</span>
      <span className={`material-status${ready ? ' sr-only' : ''}`}>{ready ? 'Ready' : status || 'Not ready'}</span>
      <span className="material-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="material-body">{children}</div>
  </details>;
}

function MaterialDocument({ id, file, version }: { id: string; file: string; version: string }) {
  const { toast } = useCockpit();
  const [expanded, setExpanded] = useState(false);
  const content = useArtifactText(id, file, version);
  const copy = () => navigator.clipboard.writeText(content.text).then(
    () => toast('Copied.'),
    () => toast('Copy was blocked, select the text instead.'),
  );
  if (content.status === 'loading') return <p className="material-note">Loading…</p>;
  if (content.status === 'error') return <div className="material-load-state"><p className="material-note">Could not load this file.</p><button onClick={content.retry}>Retry</button></div>;
  if (content.status === 'empty') return <p className="material-note">This file is empty.</p>;
  return <>
    <div className={`material-doc${expanded ? ' expanded' : ''}`}>{content.text}</div>
    <div className="material-actions">
      <button className="link" onClick={() => setExpanded(current => !current)}>{expanded ? 'Show less' : 'Show all'}</button>
      <button onClick={copy}>Copy</button>
      <a className="btn" href={artifactUrl(id, file, version)} target="_blank" rel="noopener">Open</a>
    </div>
  </>;
}

function ApplicationReview({ j }: { j: any }) {
  const { toast } = useCockpit();
  const d = j.details || {};
  const version = artifactVersion(j.files, 'application.md');
  const content = useArtifactText(j.id, 'application.md', version);
  const copy = (value: string) => navigator.clipboard.writeText(value).then(
    () => toast('Copied.'),
    () => toast('Copy was blocked, select the text instead.'),
  );
  const application = parseApplication(content.text);
  const bid = formatApplicationBid(d.bid_amount);
  const facts = [
    bid ? ['Your bid', bid, String(d.bid_amount)] : null,
    d.connects_cost != null ? ['Connects', String(d.connects_cost)] : null,
    d.connects_balance != null ? ['Balance', String(d.connects_balance)] : null,
  ].filter(Boolean) as string[][];

  if (content.status === 'loading') return <p className="material-note">Loading…</p>;
  if (content.status === 'error') return <div className="material-load-state"><p className="material-note">Could not load this file.</p><button onClick={content.retry}>Retry</button></div>;
  if (content.status === 'empty') return <p className="material-note">This file is empty.</p>;
  return <div className="application-review">
    <p className="application-handoff">Copy the fields, then review and submit on Upwork.</p>
    {facts.length ? <dl className="application-facts">{facts.map(([label, value, copyValue]) => <div key={label}><dt>{label}</dt><dd>{value}
      {copyValue ? <> <button className="link" onClick={() => copy(copyValue)}>Copy bid</button></> : null}</dd></div>)}</dl> : null}
    <ApplicationField label="Cover letter" value={application.coverLetter} onCopy={copy} />
    {application.answers.map((answer: any, index: number) => <ApplicationField
      key={`${answer.question}-${index}`}
      label={answer.question}
      value={answer.answer}
      onCopy={copy}
      answer
    />)}
    <div className="material-actions application-actions">
      {j.url ? <a className="btn primary" href={j.url} target="_blank" rel="noopener">Review and submit on Upwork</a> : null}
      <a className="btn" href={artifactUrl(j.id, 'application.md', version)} target="_blank" rel="noopener">Open text</a>
    </div>
  </div>;
}

function ApplicationField({ label, value, onCopy, answer = false }: {
  label: string;
  value: string;
  onCopy: (value: string) => void;
  answer?: boolean;
}) {
  if (!value) return null;
  return <section className="application-field">
    <div className="application-field-head">
      <h4>{answer ? 'Screening question' : label}</h4>
      <button onClick={() => onCopy(value)}>Copy {answer ? 'answer' : 'cover letter'}</button>
    </div>
    {answer ? <p className="application-question">{label}</p> : null}
    <div className="application-copy">{value}</div>
  </section>;
}

function VideoEditor({ j, post, copy }: {
  j: any;
  post: (path: string, body: object) => Promise<boolean>;
  copy: (value: string) => void;
}) {
  const [url, setUrl] = useState(j.video || '');
  const [replacing, setReplacing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const ready = validVideoUrl(j.video);
  const emb = ready ? embedUrl(j.video) : null;
  useEffect(() => { setUrl(j.video || ''); }, [j.video]);
  useEffect(() => { if (replacing) inputRef.current?.focus(); }, [replacing]);
  const save = async () => {
    const value = url.trim();
    if (!value) return inputRef.current?.focus();
    if (await post('/api/video', { id: j.id, url: value })) setReplacing(false);
  };
  if (!ready || replacing) return <div className="video-input">
    <input
      ref={inputRef}
      placeholder="Paste the Loom share link"
      value={url}
      onChange={e => setUrl(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter') void save(); if (e.key === 'Escape' && ready) setReplacing(false); }}
      aria-label="Video link"
    />
    <button onClick={save}>{ready ? 'Replace' : 'Save link'}</button>
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

function ClientFiles({ j, embedded = false }: { j: any; embedded?: boolean }) {
  const files: any[] = j.files || [];
  const names = new Set(files.map(file => file.name));
  const projectFiles = ['project.md', 'delivery.md', 'client-handover.md', 'review-request.md'];
  const originalFiles = ['pitch.html', 'loom-script.md', 'loom-review.md', 'application.md', 'call-prep.md', 'call-review.md', 'proposal.md'];
  const otherFiles = files.filter(file => !projectFiles.includes(file.name) && !originalFiles.includes(file.name));
  return <section className={embedded ? 'delivery-files' : 'panel files-panel'}>
    <div className="panel-heading"><h2>Project files</h2><span>{files.filter(file => !originalFiles.includes(file.name)).length} saved</span></div>
    <div className="materials client-materials">
      <MaterialRow label="Project brief" ready={names.has('project.md')} defaultOpen={names.has('project.md')}>
        {names.has('project.md') ? <MaterialDocument id={j.id} file="project.md" version={artifactVersion(files, 'project.md')} />
          : <CommandHandoff command="won" job={j} label="Copy project setup command" hint="Paste it into Claude Code with the contract details." />}
      </MaterialRow>
      <MaterialRow label="Delivery update" ready={names.has('delivery.md')}>
        {names.has('delivery.md') ? <MaterialDocument id={j.id} file="delivery.md" version={artifactVersion(files, 'delivery.md')} /> : null}
        <CommandHandoff command="delivery" job={j} trailing="update" label={names.has('delivery.md') ? 'Copy update command' : 'Copy delivery update command'} hint="Use this after checked work exists. Paste it into Claude Code with the latest client context." />
      </MaterialRow>
      <MaterialRow label="Client handover" ready={names.has('client-handover.md')}>
        {names.has('client-handover.md') ? <MaterialDocument id={j.id} file="client-handover.md" version={artifactVersion(files, 'client-handover.md')} /> : null}
        <CommandHandoff command="delivery" job={j} trailing="handover" label="Copy handover command" hint="Paste it into Claude Code when the work is ready to hand over or the saved handover needs updating." />
      </MaterialRow>
      <MaterialRow label="Review request" ready={names.has('review-request.md')}>
        {names.has('review-request.md') ? <MaterialDocument id={j.id} file="review-request.md" version={artifactVersion(files, 'review-request.md')} /> : null}
        <CommandHandoff command="delivery" job={j} trailing="review" label="Copy review request command" hint="Paste it into Claude Code when the outcome has been delivered and the review request is appropriate." />
      </MaterialRow>
    </div>
    {otherFiles.length ? <div className="client-files other-client-files">{otherFiles.map(file => <a className="client-file" key={file.name} href={`/files/${j.id}/${file.name}`} target="_blank" rel="noopener">
      <span><b>{FILE_LABEL[file.name] || file.name}</b>{FILE_LABEL[file.name] ? <small>{file.name}</small> : null}</span>
      <time>{stamp(file.at)}</time>
    </a>)}</div> : null}
  </section>;
}

function Field({ label, value }: { label: string; value: any }) {
  return value || value === 0 ? <div><dt>{label}</dt><dd>{value}</dd></div> : null;
}

function Timeline({ j }: { j: any }) {
  const { recent, earlier, activity } = timelineView(j);
  if (!recent.length && !activity.length) return <p className="empty">No timeline activity yet.</p>;
  return <div className="timeline">
    {recent.length ? <TimelineItems items={recent} /> : null}
    {earlier.length ? <details className="timeline-details"><summary>Earlier updates <span>{earlier.length}</span></summary>
      <div className="disclosure-body"><TimelineItems items={earlier} /></div>
    </details> : null}
    {activity.length ? <details className="timeline-details"><summary>Files and tasks <span>{activity.length}</span></summary>
      <div className="disclosure-body"><TimelineItems items={activity} /></div>
    </details> : null}
  </div>;
}

function TimelineItems({ items }: { items: any[] }) {
  const when = (at: string) => Number.isFinite(Date.parse(at)) ? stamp(at) : 'Date unknown';
  return <ul className="tl">{items.map(item => <li key={item.id}>
    <span className={`tl-dot ${item.kind}`} aria-hidden="true" />
    <div>{item.kind === 'saved' ? 'Lead saved'
      : item.kind === 'status' ? `Moved to ${LABEL[item.status] || item.status}`
        : item.kind === 'file' ? `${FILE_LABEL[item.name] || item.name} updated`
          : item.kind === 'task' ? `${item.done ? 'Completed' : 'Added'}: ${item.text}` : item.text}
      <div className="tl-when">{when(item.at)}{item.kind === 'task' && item.done ? ` · Added ${when(item.created_at)}` : ''}</div>
    </div>
  </li>)}</ul>;
}

function Conversation({ j }: { j: any }) {
  const messages = (j.thread && j.thread.messages) || [];
  if (!messages.length) return <div className="conversation-empty"><strong>No conversation saved yet</strong>
    <p>Use Sync to load the conversation.</p>
  </div>;
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

function oneLine(value: string) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}
