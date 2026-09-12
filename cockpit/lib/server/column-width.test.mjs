import assert from 'node:assert/strict';
import test from 'node:test';
import { clampColumnWidth, columnWidthForKey } from '../column-width.mjs';

test('keyboard column resizing uses bounded steps and explicit endpoints', () => {
  assert.equal(columnWidthForKey(440, 'ArrowRight'), 456);
  assert.equal(columnWidthForKey(440, 'ArrowLeft'), 424);
  assert.equal(columnWidthForKey(60, 'ArrowLeft'), 56);
  assert.equal(columnWidthForKey(716, 'ArrowRight'), 720);
  assert.equal(columnWidthForKey(440, 'Home'), 56);
  assert.equal(columnWidthForKey(440, 'End'), 720);
  assert.equal(columnWidthForKey(440, 'Tab'), null);
});

test('pointer resizing uses the same width boundaries', () => {
  assert.equal(clampColumnWidth(740), 720);
  assert.equal(clampColumnWidth(40), 56);
  assert.equal(clampColumnWidth(440.4), 440);
});
