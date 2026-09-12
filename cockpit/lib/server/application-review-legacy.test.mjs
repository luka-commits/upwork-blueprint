import assert from 'node:assert/strict';
import test from 'node:test';

import { parseApplication } from '../application-review.mjs';

test('parses legacy screening answers without a markdown heading marker', () => {
  const result = parseApplication(`Hi Sam, I can build this.

Screening answers

## Have you done this before?

Yes, on a verified project.`);
  assert.equal(result.coverLetter, 'Hi Sam, I can build this.');
  assert.deepEqual(result.answers, [
    { question: 'Have you done this before?', answer: 'Yes, on a verified project.' },
  ]);
});
