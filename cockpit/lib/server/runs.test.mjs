// npm test (inside cockpit/): the rules a button run lives by.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

// Finished runs are written to data/runs; the tests write to a throwaway folder instead.
process.env.BLUEPRINT_DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-runs-'));
const { RUNNABLE, RUNS, history, parseEvent, stopRun, track } = await import('./runs.mjs');

test('no button can submit anything to Upwork', () => {
  for (const [name, spec] of Object.entries(RUNNABLE)) {
    for (const tool of spec.tools) {
      assert.ok(!/confirm_preview|confirm_draft|send_message|respond_to_offer|submit_milestones/.test(tool), `${name} has ${tool}`);
    }
  }
});

test('the stream is reduced to text, tools, thinking and the end', () => {
  const events = parseEvent(JSON.stringify({ type: 'assistant', message: { content: [
    { type: 'thinking', thinking: 'x' }, { type: 'text', text: 'Searching' },
    { type: 'tool_use', name: 'Bash', input: { command: 'python3 code/jobs.py window' } }] } }));
  assert.deepEqual(events.map(e => e.kind), ['status', 'text', 'tool']);
  assert.equal(events[2].detail, 'python3 code/jobs.py window');
  assert.equal(parseEvent(JSON.stringify({ type: 'result', result: 'ok', is_error: false }))[0].kind, 'done');
  assert.deepEqual(parseEvent(JSON.stringify({ type: 'system', subtype: 'init' })), []);
});

test('a run can be stopped and says so', async () => {
  const child = spawn(process.execPath, ['-e', 'setTimeout(() => {}, 30000)'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const id = track('find-jobs', null, child);
  assert.equal(stopRun(id), true);
  await new Promise(resolve => child.on('close', resolve));
  await new Promise(resolve => setTimeout(resolve, 50));
  const run = RUNS.get(id);
  assert.ok(run.done && run.stopped && run.error);
  assert.equal(run.events.filter(e => e.kind === 'done').length, 1);
  assert.equal(stopRun(id), false);
});

test('a run that ends without a result still ends', async () => {
  const child = spawn(process.execPath, ['-e', 'process.exit(3)'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const id = track('find-jobs', null, child);
  await new Promise(resolve => child.on('close', resolve));
  await new Promise(resolve => setTimeout(resolve, 50));
  const run = RUNS.get(id);
  assert.ok(run.done && run.error);
  assert.match(run.events.at(-1).text, /exit code 3/);
  const saved = history().find(r => r.id === id);
  assert.ok(saved && saved.error && /exit code 3/.test(saved.result));
});
