'use client';
// What a job is, in words and cells: the labels, the small helpers, and every
// column the list can show. Ported from the first cockpit page, same rules.
import React, { useState } from 'react';
import { DisqualifyDialog } from '@/components/DisqualifyLead';
import { useCockpit } from './context';
import { calendarDate, todayIso } from './dates.mjs';
import { jobPreview } from './job-brief.mjs';
export { todayIso } from './dates.mjs';

export const STAGES = [
  { key: 'new', label: 'Not applied' },
  { key: 'applied', label: 'Applied' },
  { key: 'replied', label: 'In conversation' },
  { key: 'offer', label: 'Offer' },
];
export const ORDER = ['new', 'applied', 'replied', 'offer', 'won', 'lost', 'skipped'];
export const CLOSED = ['won', 'lost', 'skipped'];
export const LABEL: Record<string, string> = { new: 'Not applied', applied: 'Applied', replied: 'In conversation', offer: 'Offer', won: 'Won', lost: 'Lost', skipped: 'Skipped' };
export const OPEN_LABELS = STAGES.map(s => s.label);
export const FILE_LABEL: Record<string, string> = {
  'pitch.html': 'Pitch page',
  'application.md': 'Application',
  'loom-script.md': 'Loom script',
  'call-prep.md': 'Call prep',
  'call-review.md': 'Call review',
  'loom-review.md': 'Loom review',
  'proposal.md': 'Proposal',
  'lead-magnet.html': 'SEO audit',
  'project.md': 'Project brief',
  'delivery.md': 'Delivery update',
  'client-handover.md': 'Client handover',
  'review-request.md': 'Review request',
};
export const TOOL_WORDS: Record<string, string> = {
  mcp__upwork__upwork__find_jobs: 'Searching Upwork', mcp__upwork__upwork__get_profile: 'Reading your Upwork profile',
  mcp__upwork__upwork__list_accounts: 'Connecting to Upwork', mcp__upwork__upwork__list_freelancer_proposals: 'Checking your proposals',
  mcp__upwork__upwork__manage_proposals: 'Preparing the proposal preview (nothing is sent)', Read: 'Reading', Write: 'Writing', Edit: 'Editing',
  Bash: 'Running', Glob: 'Looking through files', Grep: 'Looking through files', WebSearch: 'Searching the web', WebFetch: 'Reading a web page',
};

export function ago(iso?: string) { if (!iso) return '–'; const h = (Date.now() - +new Date(iso)) / 36e5; return h < 1 ? '<1h ago' : h < 24 ? `${Math.floor(h)}h ago` : `${Math.floor(h / 24)}d ago`; }
export function day(iso?: string) { return iso ? calendarDate(iso).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }) : ''; }
export function short(iso?: string) { return iso ? calendarDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''; }
export function stamp(iso?: string) { return iso ? new Date(iso).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''; }
export function money(n: any) { n = Number(n); if (!n) return ''; return n >= 1000 ? '$' + Math.round(n / 1000) + 'K' : '$' + Math.round(n); }
export function firstNum(s: any): number | null { const m = String(s ?? '').replace(/,/g, '').match(/\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
// Lost and skipped jobs are over. A won job is a client: its check-in date still counts.
export const ENDED = ['lost', 'skipped'];
export const isDue = (j: any) => !!j.next_follow_up && j.next_follow_up <= todayIso() && !['new', 'applied'].includes(j.status) && !ENDED.includes(j.status);
export const openTasks = (j: any): any[] => (j.tasks || []).filter((t: any) => !t.done_at);
export const taskDueKey = (task: any): string => task?.due ? `${task.due}T${task.due_time || '00:00'}` : '9999';
export function taskIsDue(task: any, now = new Date()): boolean {
  if (!task?.due) return false;
  const today = todayIso(now);
  if (task.due !== today) return task.due < today;
  if (!task.due_time) return true;
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  return task.due_time <= time;
}
export const taskDueLabel = (task: any): string => task?.due
  ? `${short(task.due)}${task.due_time ? `, ${task.due_time}` : ''}`
  : '';
export const wonAt = (j: any): string | undefined => ((j.history || []).filter((h: any) => h.status === 'won').pop() || {}).at;
export function ageBucket(iso?: string) { if (!iso) return 'Unknown'; const h = (Date.now() - +new Date(iso)) / 36e5; return h < 24 ? 'Last 24 hours' : h < 72 ? '1 to 3 days' : 'Older'; }
export function dueBucket(j: any) { const t = todayIso(); return !j.next_follow_up || j.status === 'applied' || ENDED.includes(j.status) ? 'No follow-up' : j.next_follow_up < t ? 'Overdue' : j.next_follow_up === t ? 'Today' : 'Later'; }
export function clientText(j: any) {
  const c = j.client || {}, bits: string[] = [];
  if (c.rating) bits.push(`${c.rating}★`);
  if (c.hires != null && c.posted_jobs != null) bits.push(`${c.hires}/${c.posted_jobs} hires`);
  else if (c.hires != null) bits.push(`${c.hires} hires`);
  else if (c.posted_jobs != null) bits.push(`${c.posted_jobs} jobs posted`);
  return bits.join(' · ');
}
export function budgetText(j: any) {
  const b = String(j.budget || '').trim();
  if (!b || /no rate|not provided/i.test(b)) return j.job_type === 'hourly' ? 'Hourly, no rate' : '–';
  if (/[$]/.test(b)) return b;
  return j.job_type === 'hourly' ? `$${b.replace(/\/hr$/, '')}/hr` : `$${b}`;
}
export function embedUrl(url: string): string | null {
  let m = url.match(/loom\.com\/share\/([\w-]+)/);
  if (m) return `https://www.loom.com/embed/${m[1]}`;
  m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{6,})/);
  return m ? `https://www.youtube-nocookie.com/embed/${m[1]}` : null;
}
export function validVideoUrl(url?: string): boolean {
  return /^https:\/\/(?:www\.)?(?:loom\.com\/share\/[^\s/?#]+|youtube\.com\/watch\?v=[^\s&#]+|youtu\.be\/[^\s/?#]+)/.test(String(url || '').trim());
}

export type Filter = { kind: 'multi'; values: string[] } | { kind: 'range'; min: number | null; max: number | null };
export const filterActive = (f?: Filter) => !!f && (f.kind === 'multi' ? f.values.length > 0 : f.min != null || f.max != null);
export const describeFilter = (f: Filter) => f.kind === 'multi' ? f.values.join(', ') : [f.min != null ? `from ${f.min}` : '', f.max != null ? `to ${f.max}` : ''].filter(Boolean).join(' ');

// ---- small cells -----------------------------------------------------------------
const Dash = () => <span className="none">–</span>;

export function Score({ j }: { j: any }) {
  return <span className={`uw-score${(j.score || 0) >= 70 ? ' strong' : ''}`}>{j.score ?? '–'}</span>;
}

export function DueChip({ j }: { j: any }) {
  if (!j.next_follow_up || ['new', 'applied'].includes(j.status) || ENDED.includes(j.status)) return null;
  const days = Math.round((+new Date(j.next_follow_up) - +new Date(todayIso())) / 864e5);
  const txt = days < 0 ? `Follow-up ${-days}d overdue` : days === 0 ? 'Follow-up due today' : `Follow-up in ${days} days`;
  return <span className="uw-due-inline"><span className={`uw-duechip ${days <= 0 ? 'over' : 'soon'}`}>{txt}</span></span>;
}

export function Flags({ j }: { j: any }) {
  const { state } = useCockpit();
  const d = j.details || {}, me = state?.me || {};
  return <>
    {d.total_hired ? <span className="uw-flag gone">{d.total_hired} hired</span> : null}
    {d.min_jss && me.jss != null && d.min_jss > me.jss ? <span className="uw-flag bar">below preferred JSS</span> : null}
    {/FULL_TIME|30\+ hrs/i.test(j.engagement || d.engagement_type || '') ? <span className="uw-flag soft">full time</span> : null}
    {j.trap ? <span className="uw-flag soft">{j.trap}</span> : null}
  </>;
}

export function Comp({ j }: { j: any }) {
  const n = j.proposals, d = j.details || {};
  if (n == null || n === '') return <Dash />;
  const num = typeof n === 'number' ? n : null;
  const cls = num == null ? '' : num <= 5 ? ' low' : num >= 30 ? ' high' : '';
  return <><span className={`uw-comp-n${cls}`}>{num === 0 ? 'none yet' : `${n} bids`}</span>{d.invites_sent ? <span className="uw-sub">{d.invites_sent} invited</span> : null}</>;
}

/** The stage right in the row. Applied waits silently; Skipped records why. */
export function StageSelect({ j }: { j: any }) {
  const { move } = useCockpit();
  const [disqualifying, setDisqualifying] = useState<HTMLSelectElement | null>(null);
  return (
    <><select className={`stage-select stage-${j.status}`} aria-label={`Stage for ${j.title || 'job'}`} value={j.status}
      onClick={e => e.stopPropagation()}
      onChange={e => { const s = e.target.value; if (s === 'skipped') setDisqualifying(e.currentTarget); else void move(j.id, s); }}>
      {ORDER.map(k => <option key={k} value={k}>{LABEL[k]}</option>)}
    </select>{disqualifying ? <DisqualifyDialog job={j} returnTo={disqualifying} onClose={() => setDisqualifying(null)} /> : null}</>
  );
}

export function JobCell({ j }: { j: any }) {
  const description = jobPreview(j);
  return <>
    <span className="rt-td-title">{j.title}<Flags j={j} /></span>
    <span className="rt-td-desc" title={description}>{description}</span>
  </>;
}

export function TasksCell({ j }: { j: any }) {
  const open = openTasks(j).sort((a, b) => taskDueKey(a).localeCompare(taskDueKey(b)));
  if (!open.length) return <Dash />;
  const t = open[0];
  return <>{t.text}{t.due ? <span className="uw-sub" style={taskIsDue(t) ? { color: 'var(--red-deep)' } : undefined}>{taskDueLabel(t)}</span> : null}
    {open.length > 1 ? <span className="uw-sub">+{open.length - 1} more</span> : null}</>;
}

const ICON_PATHS: Record<string, React.ReactNode> = {
  bookmark: <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />,
  search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
  filter: <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />,
  x: <path d="M18 6 6 18M6 6l12 12" />,
  trash: <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />,
};
export function Icon({ name, size = 14, filled = false }: { name: 'bookmark' | 'search' | 'filter' | 'x' | 'trash'; size?: number; filled?: boolean }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? 'currentColor' : 'none'} stroke="currentColor"
    strokeWidth={name === 'x' ? 2.5 : 2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICON_PATHS[name]}</svg>;
}

// ---- columns, lists, views ----------------------------------------------------------
export type Col = {
  label: string; w: number; fixed?: boolean; asc?: boolean; unit?: string;
  cell: (j: any) => React.ReactNode; sort: (j: any) => any;
  filter?: 'multi' | 'range'; value?: (j: any) => any;
};

export const COLS: Record<string, Col> = {
  score: { label: 'Score', w: 92, cell: j => <Score j={j} />, sort: j => j.score ?? -1, filter: 'range', value: j => j.score },
  job: { label: 'Job', w: 440, fixed: true, asc: true, cell: j => <JobCell j={j} />, sort: j => (j.title || '').toLowerCase() },
  action: { label: 'Next step', w: 200, cell: () => null, sort: j => nextTodo(j)?.due || (j.status === 'new' ? '0000' : '9999') },
  client: { label: 'Client', w: 150, unit: 'rating', cell: j => clientText(j) || <Dash />, sort: j => (j.client || {}).rating ?? -1, filter: 'range', value: j => (j.client || {}).rating },
  comp: { label: 'Competition', w: 124, cell: j => <Comp j={j} />, sort: j => firstNum(j.proposals) ?? -1, filter: 'multi', value: j => j.proposals == null ? 'Unknown' : `${j.proposals} bids` },
  budget: { label: 'Budget', w: 150, cell: j => <>{budgetText(j)}{(j.details || {}).connects_cost != null ? <span className="uw-sub">{j.details.connects_cost} connects</span> : null}</>,
    sort: j => firstNum(j.budget) ?? -1, filter: 'multi', value: j => j.job_type === 'hourly' ? 'Hourly' : j.job_type === 'fixed' ? 'Fixed price' : 'Unknown' },
  posted: { label: 'Posted', w: 100, cell: j => ago(j.posted_date), sort: j => j.posted_date || '', filter: 'multi', value: j => ageBucket(j.posted_date) },
  stage: { label: 'Stage', w: 178, asc: true, cell: j => <StageSelect j={j} />, sort: j => ORDER.indexOf(j.status), filter: 'multi', value: j => LABEL[j.status] || j.status },
  followup: { label: 'Follow-up', w: 130, asc: true, cell: j => j.next_follow_up && !ENDED.includes(j.status) ? <DueChip j={j} /> : <Dash />, sort: j => j.next_follow_up || '9999', filter: 'multi', value: dueBucket },
  tasks: { label: 'Next task', w: 210, asc: true, cell: j => <TasksCell j={j} />, sort: j => openTasks(j).map(taskDueKey).sort()[0] || '99999',
    filter: 'multi', value: j => openTasks(j).some(task => taskIsDue(task)) ? 'Task due' : openTasks(j).length ? 'Open tasks' : 'No open tasks' },
  connects: { label: 'Connects', w: 96, cell: j => (j.details || {}).connects_cost ?? <Dash />, sort: j => (j.details || {}).connects_cost ?? -1, filter: 'range', value: j => (j.details || {}).connects_cost },
  boost: { label: 'Top slot', w: 110, cell: j => (j.details || {}).boost_recommended != null ? `+${j.details.boost_recommended} connects` : <Dash />,
    sort: j => (j.details || {}).boost_recommended ?? -1, filter: 'range', value: j => (j.details || {}).boost_recommended },
  country: { label: 'Country', w: 130, asc: true, cell: j => (j.client || {}).country || <Dash />, sort: j => (j.client || {}).country || '', filter: 'multi', value: j => (j.client || {}).country || 'Unknown' },
  spent: { label: 'Client spent', w: 120, cell: j => money((j.client || {}).spent) || <Dash />, sort: j => (j.client || {}).spent ?? -1, filter: 'range', value: j => (j.client || {}).spent },
  engagement: { label: 'Engagement', w: 150, asc: true, cell: j => j.engagement || <Dash />, sort: j => j.engagement || '', filter: 'multi', value: j => j.engagement || 'Unknown' },
  fit: { label: 'Niche fit', w: 96, cell: j => j.niche_fit != null ? `${j.niche_fit}/40` : <Dash />, sort: j => j.niche_fit ?? -1, filter: 'range', value: j => j.niche_fit },
  files: { label: 'Files', w: 170, cell: j => (j.artifacts || []).map((f: string) => FILE_LABEL[f] || f).join(', ') || <Dash />, sort: j => (j.artifacts || []).length,
    filter: 'multi', value: j => (j.artifacts || []).length ? j.artifacts.map((f: string) => FILE_LABEL[f] || f) : ['No files'] },
  won: { label: 'Client since', w: 130, cell: j => wonAt(j) ? short(wonAt(j)) : <Dash />, sort: j => wonAt(j) || '' },
  found: { label: 'Found', w: 100, cell: j => ago(j.found_at), sort: j => j.found_at || '', filter: 'multi', value: j => ageBucket(j.found_at) },
};

/** The next thing to do on a job: its follow-up or its earliest dated task, whichever comes first. */
export function nextTodo(j: any): { text: string; due: string | null; due_time?: string | null; note?: string | null } | null {
  if (j.status === 'offer') return { text: 'Review the offer', due: null };
  if (j.status === 'new') {
    const files = new Set(j.artifacts || []);
    const text = !files.has('pitch.html') || !files.has('loom-script.md')
      ? 'Apply or disqualify'
      : !validVideoUrl(j.video) ? 'Open application'
        : !files.has('application.md') ? 'Prepare application' : 'Submit on Upwork';
    return { text, due: null };
  }
  const items: { text: string; due: string | null; due_time?: string | null; note?: string | null }[] = openTasks(j)
    .map(t => ({ text: t.text, due: t.due || null, due_time: t.due_time || null }));
  if (j.status === 'applied') {
    items.sort((a, b) => taskDueKey(a).localeCompare(taskDueKey(b)));
    if (items.length) return items[0];
    const closes = !j.application_date_unknown && j.applied_at ? new Date(j.applied_at) : null;
    if (closes && !Number.isNaN(+closes)) closes.setUTCDate(closes.getUTCDate() + 14);
    return { text: 'Waiting for client', due: null,
      note: closes && !Number.isNaN(+closes) ? `Auto-close ${short(closes.toISOString())}` : 'Sync needs the submission date' };
  }
  if (j.next_follow_up && !ENDED.includes(j.status)) {
    const plan = j.follow_up_plan;
    const lane = typeof plan?.lane === 'string' ? plan.lane.replace('-', ' ') : '';
    const position = Number.isInteger(plan?.step) && Number.isInteger(plan?.max_steps) ? ` ${plan.step} of ${plan.max_steps}` : '';
    const text = lane ? `${lane[0].toUpperCase()}${lane.slice(1)} follow-up${position}` : j.status === 'won' ? 'Check in with the client' : 'Follow up';
    items.push({ text, due: j.next_follow_up });
  }
  const files = new Set(j.artifacts || []);
  const clientMessages = (j.thread?.messages || []).filter((message: any) => message?.kind !== 'event' && message?.from !== 'me');
  const clientWaiting = !!j.thread?.room_id && j.thread?.awaiting_reply_from === 'you' && clientMessages.length > 0;
  const callMentioned = clientMessages.some((message: any) => /\b(call|meeting|meet|zoom|interview|chat)\b/i.test(String(message.text || '')));
  const stageAction = j.status === 'replied' ? clientWaiting ? 'Reply to the client' : !files.has('call-prep.md') ? callMentioned ? 'Prepare for the call' : 'Check latest messages' : !files.has('call-review.md') ? 'Review the call' : !files.has('proposal.md') ? 'Draft proposal' : 'Send proposal on Upwork'
        : j.status === 'won' ? !files.has('project.md') ? 'Set up the project' : 'Add next delivery task'
            : '';
  if (stageAction) items.push({ text: stageAction, due: null });
  items.sort((a, b) => taskDueKey(a).localeCompare(taskDueKey(b)));
  return items[0] || null;
}
export const todoBucket = (j: any) => {
  const next = nextTodo(j);
  return !next ? 'Nothing planned' : taskIsDue(next) ? 'Due now' : 'Planned';
};
export function TodoCell({ j }: { j: any }) {
  const next = nextTodo(j);
  if (!next) return <Dash />;
  const late = taskIsDue(next);
  const label = next.due === todayIso()
    ? `today${next.due_time ? `, ${next.due_time}` : ''}`
    : taskDueLabel(next);
  return <>{next.text}{next.due || next.note ? <span className="uw-sub" style={late ? { color: 'var(--red-deep)', fontWeight: 600 } : undefined}>{next.due ? label : next.note}</span> : null}</>;
}
COLS.todo = { label: 'Next action', w: 190, asc: true, cell: j => <TodoCell j={j} />, sort: j => nextTodo(j)?.due || '9999', filter: 'multi', value: todoBucket };

export type View = {
  name: string; layout: 'list' | 'board'; query: string;
  filters: Record<string, Filter>; cols: string[]; widths: Record<string, number>;
  sort: { id: string; desc: boolean } | null;
};
export type Space = { title: string; board: boolean; base: (j: any) => boolean; cols: string[]; presets: View[] };

const view = (name: string, v: Partial<View>): View => ({ name, layout: 'list', query: '', filters: {}, cols: [], widths: {}, sort: null, ...v });
// One list for everything: leads, clients and what is due are views of it, not tabs.
export const SPACES: Record<'jobs', Space> = {
  jobs: {
    title: 'Jobs', board: true, base: () => true,
    cols: Object.keys(COLS),
    presets: [
      view('All open', { filters: { stage: { kind: 'multi', values: OPEN_LABELS } }, cols: ['score', 'job', 'action', 'client', 'comp', 'budget', 'stage'] }),
      view('To do', { filters: { todo: { kind: 'multi', values: ['Due now'] } }, cols: ['score', 'job', 'client', 'action', 'stage'], sort: { id: 'action', desc: false } }),
      view('To apply', { filters: { stage: { kind: 'multi', values: ['Not applied'] }, score: { kind: 'range', min: 60, max: null } },
        cols: ['score', 'job', 'action', 'client', 'comp', 'budget', 'boost', 'posted'], sort: { id: 'score', desc: true } }),
      view('In play', { filters: { stage: { kind: 'multi', values: ['Applied', 'In conversation', 'Offer'] } }, cols: ['score', 'job', 'client', 'budget', 'action', 'stage'] }),
      view('Clients', { filters: { stage: { kind: 'multi', values: ['Won'] } }, cols: ['job', 'client', 'won', 'action', 'files'], sort: { id: 'won', desc: true } }),
      view('Closed', { filters: { stage: { kind: 'multi', values: ['Lost', 'Skipped'] } }, cols: ['score', 'job', 'client', 'found', 'stage'], sort: { id: 'found', desc: true } }),
    ],
  },
};

export const GROUPS = [
  { title: 'Job', cols: ['score', 'job', 'action', 'stage', 'followup', 'tasks', 'files', 'posted', 'found', 'won'] },
  { title: 'Client', cols: ['client', 'country', 'spent'] },
  { title: 'Deal', cols: ['budget', 'comp', 'connects', 'boost', 'engagement', 'fit'] },
];

/** Every task and due follow-up across leads and clients, for the Tasks page and its badge. */
export function taskItems(jobs: any[]) {
  const items: { kind: 'task' | 'follow'; j: any; t?: any; due?: string }[] = [];
  for (const j of jobs) {
    for (const t of openTasks(j)) items.push({ kind: 'task', j, t, due: t.due });
    if (isDue(j)) items.push({ kind: 'follow', j, due: j.next_follow_up });
  }
  return items;
}
