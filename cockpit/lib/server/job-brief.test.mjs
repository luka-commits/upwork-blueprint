import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveJobBrief } from '../job-brief.mjs';

test('uses a saved structured brief without rewriting it', () => {
  const result = deriveJobBrief({ details: { brief: {
    outcome: 'A working membership system.',
    scope: ['Build checkout pages.', 'Handle failed payments.'],
    requirements: ['Native subscription experience.'],
  } } });
  assert.deepEqual(result, {
    outcome: 'A working membership system.',
    scope: ['Build checkout pages.', 'Handle failed payments.'],
    requirements: ['Native subscription experience.'],
  });
});

test('turns a full posting into a useful fallback brief', () => {
  const result = deriveJobBrief({
    summary: 'Membership checkout and subscription automation for a coaching business.',
    details: { description: `I need a GoHighLevel expert to build membership automation.
Scope: build tiered checkout pages with monthly and yearly pricing. Build failed payment handling and notifications. Build access suspension logic and restore access after payment. Must have proven experience with GHL native subscription objects.` },
  });
  assert.equal(result.outcome, 'Membership checkout and subscription automation for a coaching business.');
  assert.equal(result.scope.length, 3);
  assert.match(result.scope[0], /tiered checkout/i);
  assert.deepEqual(result.requirements, ['Must have proven experience with GHL native subscription objects.']);
});
