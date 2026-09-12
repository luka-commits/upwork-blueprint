import assert from 'node:assert/strict';
import test from 'node:test';
import { NARRATE, launchArgs } from './runs.mjs';

test('headless narration follows the compact canonical completion report', () => {
  assert.match(NARRATE, /only when the phase changes or a blocker needs attention/);
  assert.match(NARRATE, /final completion report follows CLAUDE\.md/);
  assert.match(NARRATE, /exact Upwork call count last/);
  assert.match(NARRATE, /under 90 words without hiding blockers or uncertainty/);
  assert.doesNotMatch(NARRATE, /Before each step|after each finding|End with one sentence/);
  const args = launchArgs('find-jobs');
  assert.equal(args[args.indexOf('--append-system-prompt') + 1], NARRATE);
});
