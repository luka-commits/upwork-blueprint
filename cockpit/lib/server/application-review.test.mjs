import assert from 'node:assert/strict';
import test from 'node:test';

import { parseApplication } from '../application-review.mjs';

test('parses a cover letter and exact screening answers', () => {
  const result = parseApplication(`# Cover letter

Hi Sam, I can build this.

# Screening answers

## Have you built this before?

Yes. Here is the relevant proof.

## When can you start?

Monday.`);

  assert.equal(result.coverLetter, 'Hi Sam, I can build this.');
  assert.deepEqual(result.answers, [
    { question: 'Have you built this before?', answer: 'Yes. Here is the relevant proof.' },
    { question: 'When can you start?', answer: 'Monday.' },
  ]);
});

test('keeps an older application file as the cover letter', () => {
  const result = parseApplication('Hi there,\n\nThis is the full proposal.');
  assert.equal(result.coverLetter, 'Hi there,\n\nThis is the full proposal.');
  assert.deepEqual(result.answers, []);
});
