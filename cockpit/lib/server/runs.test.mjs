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
const { RUNNABLE, RUNS, applicationPrerequisiteError, commandAvailability, history, hookSettings, launchArgs, parseEvent, prepareApprovedReply, promptFor, releaseApprovedReply, stopRun, track } = await import('./runs.mjs');

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

test('inbox preserves an optional single-job scope and call prep has a runnable', () => {
  assert.equal(promptFor('inbox', '123456'), '/inbox 123456');
  assert.equal(promptFor('inbox'), '/inbox');
  assert.ok(RUNNABLE.inbox.optionalJob);
  assert.equal(RUNNABLE['call-prep'].job, true);
});

test('installed interactive commands stay available as copy handoffs', () => {
  for (const name of ['call-review', 'loom-review', 'proposal', 'won', 'delivery']) {
    assert.equal(commandAvailability()[name], true, name);
    assert.equal(RUNNABLE[name], undefined, name);
  }
});

test('the morning follow-up review can read but cannot send', () => {
  const tools = RUNNABLE['follow-up'].tools;
  assert.ok(tools.some(tool => tool.endsWith('__get_messages')));
  assert.ok(!tools.some(tool => tool.endsWith('__send_message')));
  assert.ok(!tools.some(tool => tool.endsWith('__confirm_preview')));
});

test('lead magnet runs the local audit without Upwork or sending tools', () => {
  const spec = RUNNABLE['lead-magnet'];
  assert.equal(spec.job, true);
  assert.ok(spec.tools.includes('Bash(python3 .claude/skills/lead-magnet/scripts/build.py*)'));
  assert.ok(!spec.tools.some(tool => /mcp__upwork|send_message|confirm_preview/.test(tool)));
});

test('application drafting waits for the pitch page and Loom video', () => {
  assert.match(applicationPrerequisiteError({ files: [] }), /finish the Pitch page.*add a valid Loom or YouTube video link/);
  assert.match(applicationPrerequisiteError({ files: [{ name: 'pitch.html' }] }), /add a valid Loom or YouTube video link/);
  assert.match(applicationPrerequisiteError({ files: [], video: 'https:\/\/www.loom.com\/share\/abc' }), /finish the Pitch page/);
  assert.equal(applicationPrerequisiteError({ files: [{ name: 'pitch.html' }], video: 'https://www.loom.com/share/abc' }), '');
});

test('application runs install the preview-only action guard', () => {
  const settings = hookSettings('apply');
  const hook = settings.hooks.PreToolUse[0];
  assert.equal(hook.matcher, '.*');
  assert.match(hook.hooks[0].command, /apply-guard\.mjs"$/);
  assert.equal(hookSettings('find-jobs'), null);
});

test('reply sender runs retain their deterministic send guard binding', () => {
  const settings = hookSettings('send-reply');
  const hook = settings.hooks.PreToolUse[0];
  assert.equal(hook.matcher, '.*');
  assert.match(hook.hooks[0].command, /send-guard\.mjs"$/);
  assert.doesNotMatch(hook.hooks[0].command, /apply-guard/);
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
  assert.deepEqual(outbox.known_message_ids, []);
  assert.throws(() => prepareApprovedReply('123456', 'Again'), /previous send is not confirmed/);
  assert.throws(() => releaseApprovedReply('123456', 'wrong'), /no longer unresolved/);
  assert.ok(releaseApprovedReply('123456', outbox.written_at).cancelled_at);
  assert.equal(prepareApprovedReply('123456', 'A new approval').text, 'A new approval');
  fs.writeFileSync(path.join(folder, 'outbox.json'), '{');
  assert.throws(() => prepareApprovedReply('123456', 'Again'), /receipt is unreadable/);
  fs.writeFileSync(path.join(folder, 'thread.json'), JSON.stringify({ room_id: 'room; echo unsafe' }));
  assert.throws(() => prepareApprovedReply('123456', 'Again'), /room id is invalid/);
});

test('runtime denies unapproved tools instead of inheriting broad auto-approval', () => {
  for (const name of Object.keys(RUNNABLE)) {
    const args = launchArgs(name);
    assert.equal(args[args.indexOf('--permission-mode') + 1], 'dontAsk');
    const denied = args.slice(args.indexOf('--disallowedTools') + 1);
    assert.ok(denied.includes('mcp__upwork__upwork__confirm_preview'));
    assert.equal(denied.includes('mcp__upwork__upwork__send_message'), name !== 'send-reply');
  }
});

test('sending rejects a stale conversation or an obsolete draft set', () => {
  const folder = path.join(process.env.BLUEPRINT_JOBDIR, '123457');
  fs.mkdirSync(folder);
  const thread = { room_id: 'room-7', fetched_at: '2000-01-01T00:00:00Z', messages: [] };
  fs.writeFileSync(path.join(folder, 'thread.json'), JSON.stringify(thread));
  assert.throws(() => prepareApprovedReply('123457', 'Hello'), /older than 24 hours/);
  thread.fetched_at = new Date().toISOString();
  fs.writeFileSync(path.join(folder, 'thread.json'), JSON.stringify(thread));
  fs.writeFileSync(path.join(folder, 'replies.json'), JSON.stringify({ generated_at: '2026-09-12T12:00:00Z', drafts: [{ text: 'Hello' }] }));
  assert.throws(() => prepareApprovedReply('123457', 'Hello', 0, '2026-09-11T12:00:00Z'), /drafts changed/);
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

test('a model success cannot hide a nonzero process exit', async () => {
  const script = 'process.stdout.write(JSON.stringify({type:"result", result:"COMPLETE", is_error:false}) + "\\n"); setTimeout(() => process.exit(2), 20)';
  const child = spawn(process.execPath, ['-e', script], { stdio: ['ignore', 'pipe', 'pipe'] });
  const id = track('find-jobs', null, child);
  await new Promise(resolve => child.on('close', resolve));
  assert.ok(RUNS.get(id).error);
  assert.equal(RUNS.get(id).events.filter(e => e.kind === 'done').length, 1);
});

test('a sender cannot claim success without a confirmed message receipt', async () => {
  const child = spawn(process.execPath, ['-e', 'process.stdout.write(JSON.stringify({type:"result",result:"COMPLETE",is_error:false})+"\\n")'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const id = track('send-reply', '999999', child);
  await new Promise(resolve => child.on('close', resolve));
  assert.ok(RUNS.get(id).error);
  assert.match(RUNS.get(id).events.at(-1).text, /not confirmed/);
});

test('one corrupt history entry does not hide healthy runs', () => {
  const dir = path.join(process.env.BLUEPRINT_DATA, 'runs');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'broken.json'), '{');
  fs.writeFileSync(path.join(dir, 'healthy.json'), JSON.stringify({ id: 'healthy', started: 1 }));
  assert.ok(history().some(item => item.id === 'healthy'));
});
