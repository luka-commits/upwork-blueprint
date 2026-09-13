import test from 'node:test';
import assert from 'node:assert/strict';
import { parseLoomReview, parseLoomScript } from '../loom-artifacts.mjs';

test('Loom scripts become an intro and scannable beats', () => {
  const view = parseLoomScript(`# Loom script\nPrepared today\n**Next:** Record it.\n\nA short opening.\n\n**Beat 1 · Their workflow, 25 seconds**\nShow the first trigger.\n\n**Beat 2: The result, 1 minute**\nShow the result.`);
  assert.equal(view.intro, 'A short opening.');
  assert.deepEqual(view.beats, [
    { title: 'Their workflow', duration: '25 seconds', body: 'Show the first trigger.' },
    { title: 'The result', duration: '1 minute', body: 'Show the result.' },
  ]);
});

test('Loom reviews expose the score and keep the useful sections', () => {
  const view = parseLoomReview('## Score\n84/100\n## Verdict\nReady\n## Accuracy\nAll claims checked.');
  assert.equal(view.score, 84);
  assert.deepEqual(view.sections, [
    { label: 'Verdict', body: 'Ready' },
    { label: 'Accuracy', body: 'All claims checked.' },
  ]);
});
