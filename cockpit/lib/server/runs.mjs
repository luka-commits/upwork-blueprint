// Buttons that start Claude. A run is the same slash command the member could
// type, started headless on this computer with only the tools that command needs.
// No run gets a tool that sends anything to Upwork: a send always happens where
// the member reads the exact text first.
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { ROOT } from './root.mjs';

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
  return Object.hasOwn(RUNNABLE, name) && fs.existsSync(path.join(ROOT, '.claude', 'commands', `${name}.md`));
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
  };
  child.on('close', code => finish(code ?? 1));
  child.on('error', err => { run.events.push({ kind: 'error', text: String(err.message || err) }); finish(1); });
  return id;
}

export function startRun(name, job) {
  const spec = RUNNABLE[name];
  const bin = claudeBinary();
  if (!bin) throw new Error('Claude Code is not installed or not on the PATH.');
  const prompt = spec.prompt.replace('{job}', job || '').trim();
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
