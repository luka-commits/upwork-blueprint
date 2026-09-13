import assert from 'node:assert/strict';
import test from 'node:test';
import { advanceRunStep, runPlan, runProgress } from '../run-progress.mjs';

test('pitch progress follows real command-specific milestones without regressing', () => {
  const events = [
    { text: 'Bash', detail: 'python3 code/preflight.py vercel; python3 code/pipeline.py get 2099152063478337290' },
    { text: 'Read', detail: '/repo/context/proof.md' },
    { text: 'Read', detail: '/repo/code/pitch/generate.py' },
    { text: 'Write', detail: '/repo/jobs/2099152063478337290/plan-onboarding.svg' },
    { text: 'Bash', detail: 'python3 code/pitch_deploy.py 2099152063478337290' },
    { text: 'Bash', detail: 'python3 code/check_repo.py' },
  ];
  let step = 0;
  const seen = events.map(event => (step = advanceRunStep('pitch-page', step, event)));
  assert.deepEqual(seen, [0, 1, 2, 3, 4, 5]);
  assert.ok(runProgress('pitch-page', 5) < 100);
  assert.equal(runProgress('pitch-page', 5, true), 100);
  assert.equal(advanceRunStep('pitch-page', 4, events[1]), 4);
});

test('each core run explains its own work instead of exposing generic file activity', () => {
  const commands = ['find-jobs', 'sync', 'pitch-page', 'apply', 'reply', 'lead-magnet', 'follow-up', 'inbox', 'send-reply', 'call-prep', 'status'];
  for (const command of commands) {
    const plan = runPlan(command);
    assert.ok(plan.length >= 3, command);
    assert.ok(plan.every(label => !/looking through files|reading|running/i.test(label)), command);
  }
  assert.notDeepEqual(runPlan('pitch-page'), runPlan('find-jobs'));
});
