// Buttons that start Claude. A run is the same slash command the member could
// type, started headless on this computer with only the tools that command needs.
// Only send-reply gets a sending tool. Its text comes from the server-written
// outbox after the member has read and approved it in the cockpit.
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { JOBS_DIR, ROOT } from './root.mjs';

const UPWORK_READ = ['mcp__upwork__upwork__list_accounts', 'mcp__upwork__upwork__find_jobs',
  'mcp__upwork__upwork__get_profile'];
const FILES = ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'Bash(python3 code/*)'];

export const RUNNABLE = {
  'find-jobs': { prompt: '/find-jobs', tools: [...FILES, ...UPWORK_READ, 'WebSearch'], job: false },
  sync: { prompt: '/sync', job: false, tools: [...FILES, 'mcp__upwork__upwork__list_accounts',
    'mcp__upwork__upwork__list_freelancer_proposals', 'mcp__upwork__upwork__get_messages',
    'mcp__upwork__upwork__list_offers', 'mcp__upwork__upwork__list_contracts'] },
  'pitch-page': { prompt: '/pitch-page {job}', tools: [...FILES, ...UPWORK_READ, 'WebSearch', 'WebFetch'], job: true },
  // The draft run makes the proposal preview (Connects price, boost bids) and
  // stops. It never gets confirm_preview, so it cannot submit anything.
  apply: { prompt: '/apply {job} --draft-only', job: true,
    tools: [...FILES, ...UPWORK_READ, 'mcp__upwork__upwork__list_freelancer_proposals', 'mcp__upwork__upwork__manage_proposals'] },
  reply: { prompt: '/reply {job}', job: true, tools: [...FILES] },
  'send-reply': {
    command: false,
    job: true,
    prompt: 'Send the approved Upwork reply for job {job}. Read jobs/{job}/outbox.json. '
      + 'Call list_accounts exactly once to obtain the org_uid. Then use that org_uid plus the room_id and text from the outbox. '
      + 'Call send_message action send exactly once with that room_id and the text character for character. '
      + 'Do not rewrite, trim, summarize, quote or repeat the message in your output. Then call get_messages action list_messages for the same room, newest 30. '
      + 'Confirm that one returned message from the freelancer has text exactly equal to the outbox text. If it does not, stop and report the failure without changing thread.json. '
      + 'If it does, write the complete get_messages response to jobs/{job}/.thread-confirm.json and run '
      + '`python3 code/threads.py confirm {job} --room <the exact room_id> --awaiting them`. '
      + 'End with COMPLETE, what was checked, and the Upwork call count. The expected count is 3.',
    tools: ['Read', 'Write', 'Bash(python3 code/threads.py*)',
      'mcp__upwork__upwork__list_accounts', 'mcp__upwork__upwork__send_message',
      'mcp__upwork__upwork__get_messages'],
  },
};

// A button run has no chat to talk into, only the cockpit's status line. This makes
// Claude say what it is doing and what it found, so that line stays current.
export const NARRATE = 'You were started by a button in the cockpit. The member sees only a one-line status panel. '
  + 'Before each step write one short plain sentence saying what you are doing now, and after each '
  + 'finding one sentence with what you found so far, with counts or names. No markdown in these lines. '
  + 'End with one sentence that says what changed and what the member should look at next.';

const holder = globalThis;
export const RUNS = holder.__cockpitRuns ??= new Map();

export function available(name) {
  const spec = RUNNABLE[name];
  return !!spec && (spec.command === false || fs.existsSync(path.join(ROOT, '.claude', 'commands', `${name}.md`)));
}

/** Freeze the exact approved text before Claude gets a sending tool. */
export function prepareApprovedReply(job, text, draft = null, draftSet = null) {
  if (!/^[0-9]{6,25}$/.test(job)) throw new Error('That job id is not valid.');
  if (typeof text !== 'string' || !text.trim()) throw new Error('The reply is empty.');
  if ([...RUNS.values()].some(run => run.command === 'send-reply' && !run.done)) {
    throw new Error('A reply is already being sent. Wait for its confirmation.');
  }
  const folder = path.join(JOBS_DIR, job);
  let thread;
  try { thread = JSON.parse(fs.readFileSync(path.join(folder, 'thread.json'), 'utf-8')); } catch { throw new Error('Sync this conversation before sending.'); }
  const room = String(thread?.room_id || '').trim();
  if (!room) throw new Error('A freelancer cannot message first on a proposal. Wait for the client to reply.');
  const record = { written_at: new Date().toISOString(), job_id: job, room_id: room, text,
    draft: Number.isInteger(draft) && draft >= 0 ? draft : null,
    draft_set: typeof draftSet === 'string' ? draftSet : null };
  const target = path.join(folder, 'outbox.json');
  const tmp = path.join(folder, `.outbox-${process.pid}-${crypto.randomBytes(4).toString('hex')}.tmp`);
  fs.writeFileSync(tmp, JSON.stringify(record, null, 2), { encoding: 'utf-8', mode: 0o600 });
  fs.renameSync(tmp, target);
  return record;
}

export function startApprovedReply(job, text, draft = null, draftSet = null) {
  prepareApprovedReply(job, text, draft, draftSet);
  return startRun('send-reply', job);
}

export function claudeBinary() {
  const names = process.platform === 'win32' ? ['claude.exe', 'claude.cmd', 'claude'] : ['claude'];
  const dirs = (process.env.PATH || '').split(path.delimiter).concat(path.join(os.homedir(), '.local', 'bin'));
  for (const dir of dirs) {
    for (const name of names) {
      const full = path.join(dir, name);
      try { if (fs.statSync(full).isFile()) return full; } catch { /* not here */ }
    }
  }
  return null;
}

/** One line of `claude --output-format stream-json`, reduced to what the page shows. */
export function parseEvent(line) {
  let ev;
  try { ev = JSON.parse(line); } catch { return line ? [{ kind: 'text', text: line }] : []; }
  if (ev.type === 'assistant') {
    const out = [];
    for (const part of ev.message?.content || []) {
      if (part.type === 'text' && part.text?.trim()) out.push({ kind: 'text', text: part.text });
      else if (part.type === 'thinking') out.push({ kind: 'status', text: 'thinking' });
      else if (part.type === 'tool_use') {
        const given = part.input || {};
        const detail = given.command || given.file_path || given.query || given.action || '';
        out.push({ kind: 'tool', text: part.name || 'tool', detail: String(detail).slice(0, 120) });
      }
    }
    return out;
  }
  if (ev.type === 'result') return [{ kind: 'done', text: ev.result || '', error: !!ev.is_error }];
  return [];
}

/** Follows one child process: its events, how it ended, and whether you stopped it. */
export function track(name, job, child) {
  const id = crypto.randomBytes(6).toString('hex');
  const run = { id, command: name, job, events: [], done: false, started: Date.now() / 1000,
    ended: null, error: false, stopped: false, child };
  RUNS.set(id, run);
  let stderr = '';
  child.stderr?.on('data', d => { stderr = (stderr + d).slice(-4000); });
  readline.createInterface({ input: child.stdout }).on('line', line => { run.events.push(...parseEvent(line.trim())); });
  const finish = code => {
    if (run.done) return;
    if (!run.stopped) {
      if (code && stderr.trim()) run.events.push({ kind: 'error', text: stderr.trim() });
      if (!run.events.some(e => e.kind === 'done')) run.events.push({ kind: 'done', text: `Finished with exit code ${code}.`, error: code !== 0 });
    }
    const last = [...run.events].reverse().find(e => e.kind === 'done');
    run.error = !!last?.error;
    run.ended = Date.now() / 1000;
    run.done = true;
    remember(run, last?.text || '');
  };
  child.on('close', code => finish(code ?? 1));
  child.on('error', err => { run.events.push({ kind: 'error', text: String(err.message || err) }); finish(1); });
  return id;
}

// Finished runs outlive the server, so the Commands page can show what each one did.
export const RUNS_DIR = path.join(process.env.BLUEPRINT_DATA || path.join(ROOT, 'data'), 'runs');
const KEEP_RUNS = 50;

function remember(run, result) {
  try {
    fs.mkdirSync(RUNS_DIR, { recursive: true });
    const log = run.events.filter(e => e.kind === 'text' || e.kind === 'tool' || e.kind === 'error').slice(-200)
      .map(e => ({ kind: e.kind, text: e.kind === 'tool' && e.detail ? `${e.text} · ${e.detail}` : e.text }));
    fs.writeFileSync(path.join(RUNS_DIR, `${run.id}.json`), JSON.stringify({ ...summary(run), result, log }, null, 1));
    const files = fs.readdirSync(RUNS_DIR).filter(f => f.endsWith('.json'))
      .map(f => ({ f, t: fs.statSync(path.join(RUNS_DIR, f)).mtimeMs })).sort((a, b) => b.t - a.t);
    for (const { f } of files.slice(KEEP_RUNS)) fs.unlinkSync(path.join(RUNS_DIR, f));
  } catch { /* the run itself is done either way */ }
}

export function history() {
  try {
    return fs.readdirSync(RUNS_DIR).filter(f => f.endsWith('.json'))
      .map(f => JSON.parse(fs.readFileSync(path.join(RUNS_DIR, f), 'utf-8')))
      .sort((a, b) => (b.started || 0) - (a.started || 0));
  } catch { return []; }
}

export function promptFor(name, job) {
  return RUNNABLE[name].prompt.replaceAll('{job}', job || '').trim();
}

export function startRun(name, job) {
  const spec = RUNNABLE[name];
  const bin = claudeBinary();
  if (!bin) throw new Error('Claude Code is not installed or not on the PATH.');
  const prompt = promptFor(name, job);
  const args = ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--append-system-prompt', NARRATE,
    '--permission-mode', 'acceptEdits', '--allowedTools', ...spec.tools];
  const child = spawn(bin, args, { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'], shell: bin.endsWith('.cmd') });
  return track(name, job, child);
}

/** Ends a run you no longer want. What it already saved stays. */
export function stopRun(id) {
  const run = RUNS.get(id);
  if (!run || run.done) return false;
  run.stopped = true;
  run.events.push({ kind: 'done', text: 'Stopped by you. Anything it already saved stays.', error: true, stopped: true });
  run.child.kill();
  return true;
}

export function summary(run) {
  const { id, command, job, started, ended, done, error, stopped } = run;
  return { id, command, job, started, ended, done, error, stopped };
}
