import assert from 'node:assert/strict';
import test from 'node:test';
import { guardApplicationTool } from './apply-guard.mjs';

const decision = (tool_name, tool_input = {}) =>
  guardApplicationTool({ tool_name, tool_input }).hookSpecificOutput;

test('application guard allows create preview and rejects every other proposal action', () => {
  const tool = 'mcp__upwork__upwork__manage_proposals';
  assert.equal(decision(tool, { action: 'create', job_reference: 'job' }).permissionDecision, 'allow');
  for (const action of ['accept_invitation', 'submit', 'withdraw', '', undefined]) {
    assert.equal(decision(tool, { action }).permissionDecision, 'deny', String(action));
  }
  assert.equal(guardApplicationTool(null).hookSpecificOutput.permissionDecision, 'deny');
});

test('application guard does not override normal permissions for unrelated tools', () => {
  for (const tool of ['Bash', 'mcp__upwork__upwork__send_message', 'mcp__other__arbitrary']) {
    assert.deepEqual(guardApplicationTool({ tool_name: tool, tool_input: { action: 'send' } }), {}, tool);
  }
});
