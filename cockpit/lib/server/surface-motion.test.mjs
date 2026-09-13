import test from 'node:test';
import assert from 'node:assert/strict';
import { allowsSurfaceMotion, sectionIndex, revealContent } from '../surface-motion.mjs';

test('surface motion is limited to pointer navigation without reduced motion', () => {
  assert.equal(allowsSurfaceMotion('pointer', false), true);
  for (const input of ['keyboard', undefined, '']) assert.equal(allowsSurfaceMotion(input, false), false);
  assert.equal(allowsSurfaceMotion('pointer', true), false);
});

test('three-section marker keeps lead pages and follow-up reviews in Leads', () => {
  assert.deepEqual(['/', '/job/123456', '/follow-ups', '/analytics', '/commands'].map(sectionIndex), [0, 0, 0, 1, 2]);
});

test('rapid changes cancel only the previous surface animation and never animate layout', () => {
  const calls = [], animations = [];
  const element = { animate(frames, options) {
    calls.push({ frames, options });
    const animation = { cancelled: false, cancel() { this.cancelled = true; } };
    animations.push(animation);
    return animation;
  } };
  const options = { input: 'pointer', reducedMotion: false };
  revealContent(element, options);
  revealContent(element, options);
  assert.equal(animations[0].cancelled, true);
  assert.equal(animations[1].cancelled, false);
  assert.equal(calls[1].options.duration, 180);
  assert.deepEqual(Object.keys(calls[1].frames[0]), ['opacity', 'transform']);
  revealContent(element, { input: 'keyboard', reducedMotion: false });
  assert.equal(animations[1].cancelled, true);
  assert.equal(calls.length, 2);
  revealContent(element, { input: 'pointer', reducedMotion: true });
  assert.equal(calls.length, 2);
  assert.doesNotThrow(() => revealContent(null, options));
  assert.doesNotThrow(() => revealContent({}, options));
});
