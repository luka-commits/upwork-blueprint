import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveJobBrief } from '../job-brief.mjs';

test('separates an old scoring recommendation from the client outcome', () => {
  const result = deriveJobBrief({ details: { brief: {
    outcome: 'Tiered membership checkout and subscription automation. Crowded already, so it needs a pitch page to stand out.',
    scope: ['Build the checkout.'],
    requirements: [],
  } } });
  assert.equal(result.outcome, 'Tiered membership checkout and subscription automation.');
  assert.equal(result.decision, 'Crowded already, so it needs a pitch page to stand out.');
});

test('does not discard saved scope or requirements past the overview preview', () => {
  const scope = Array.from({ length: 8 }, (_, index) => `Build part ${index + 1} with the supplied workflow.`);
  const requirements = Array.from({ length: 6 }, (_, index) => `Must satisfy requirement ${index + 1}.`);
  const result = deriveJobBrief({ details: { brief: { outcome: 'A working system.', scope, requirements } } });
  assert.deepEqual(result.scope, scope);
  assert.deepEqual(result.requirements, requirements);
});
