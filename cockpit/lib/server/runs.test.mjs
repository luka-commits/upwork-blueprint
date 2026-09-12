// npm test (inside cockpit/): the rules a button run lives by.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

// Finished runs are written to data/runs; the tests write to a throwaway folder instead.
process.env.BLUEPRINT_DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-runs-'));
process.env.BLUEPRINT_JOBDIR = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-jobs-'));
const { RUNNABLE, RUNS, history, parseEvent, prepareApprovedReply, promptFor, stopRun, track } = await import('./runs.mjs');

test('only the dedicated reply sender can send and no button can confirm a preview', () => {
  const senders = [];
  for (const [name, spec] of Object.entries(RUNNABLE)) {
    for (const tool of spec.tools) {
      assert.ok(!/confirm_preview/.test(tool), `${name} has ${tool}`);
      if (/send_message/.test(tool)) senders.push(name);
      if (name !== 'send-reply') assert.ok(!/confirm_draft|respond_to_offer|submit_milestones/.test(tool), `${name} has ${tool}`);
    }
  }
  assert.deepEqual(senders, ['send-reply']);
  assert.equal(RUNNABLE['send-reply'].command, false);
});

test('every job placeholder in the send prompt is resolved', () => {
  const prompt = promptFor('send-reply', '123456');
  assert.ok(!prompt.includes('{job}'));
  assert.ok(prompt.includes('jobs/123456/outbox.json'));
  assert.ok(prompt.includes('code/threads.py confirm 123456'));
  assert.ok(prompt.includes('code/pipeline.py follow-up 123456 sent'));
});

test('the morning follow-up review can read but cannot send', () => {
  const tools = RUNNABLE['follow-up'].tools;
  assert.ok(tools.some(tool => tool.endsWith('__get_messages')));
  assert.ok(!tools.some(tool => tool.endsWith('__send_message')));
  assert.ok(!tools.some(tool => tool.endsWith('__confirm_preview')));
});

test('the server freezes exact approved text and requires a room', () => {
  const folder = path.join(process.env.BLUEPRINT_JOBDIR, '123456');
  fs.mkdirSync(folder);
  assert.throws(() => prepareApprovedReply('123456', 'Hello'), /Sync this conversation/);
  fs.writeFileSync(path.join(folder, 'thread.json'), JSON.stringify({ messages: [] }));
  assert.throws(() => prepareApprovedReply('123456', 'Hello'), /cannot message first/);
  fs.writeFileSync(path.join(folder, 'thread.json'), JSON.stringify({ room_id: 'room-7', messages: [] }));
  const exact = '  Thanks.\nI will get back to you.  ';
  prepareApprovedReply('123456', exact);
  const outbox = JSON.parse(fs.readFileSync(path.join(folder, 'outbox.json'), 'utf-8'));
  assert.equal(outbox.room_id, 'room-7');
  assert.equal(outbox.text, exact);
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
