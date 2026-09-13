import assert from 'node:assert/strict';
import test from 'node:test';
import { timelineView } from '../timeline.mjs';

test('timeline separates decisions and notes from file and task activity', () => {
  const result = timelineView({
    found_at: '2026-09-10T10:00:00Z',
    history: [{ status: 'new', at: '2026-09-10T10:00:00Z' }, { status: 'replied', at: '2026-09-12T10:00:00Z' }],
    log: [{ text: 'Client prefers a phased build.', at: '2026-09-13T10:00:00Z' }],
    files: [{ name: 'pitch.html', at: '2026-09-11T10:00:00Z' }],
    tasks: [{ id: 1, text: 'Prepare agenda', created_at: '2026-09-12T11:00:00Z', done_at: '2026-09-13T11:00:00Z' }],
  });
  assert.deepEqual(result.recent.map(item => item.kind), ['note', 'status', 'saved']);
  assert.equal(result.activity.length, 2);
  assert.equal(result.activity[0].kind, 'task');
  assert.equal(result.activity[0].done, true);
  assert.equal(result.activity[0].created_at, '2026-09-12T11:00:00Z');
  assert.equal(result.activity[0].at, '2026-09-13T11:00:00Z');
});

test('only five updates start visible, with every older note retained', () => {
  const log = Array.from({ length: 12 }, (_, i) => ({ text: `Note ${i}`, at: `2026-09-${String(i + 1).padStart(2, '0')}T10:00:00Z` }));
  const result = timelineView({ log });
  assert.equal(result.recent.length, 5);
  assert.equal(result.earlier.length, 7);
  assert.equal(result.recent[0].text, 'Note 11');
  assert.equal(result.earlier.at(-1).text, 'Note 0');
});

test('repeated stage records collapse, but reopening and repeated notes stay', () => {
  const result = timelineView({ history: ['new', 'new', 'applied', 'applied', 'new'].map(status => ({ status })),
    log: [{ text: 'Waiting' }, { text: 'Waiting' }] });
  assert.deepEqual(result.recent.filter(item => item.kind === 'status').map(item => item.status), ['new', 'applied', 'new']);
  assert.equal(result.recent.filter(item => item.kind === 'note').length, 2);
});

test('empty and incomplete records stay safe, including unknown dates', () => {
  assert.deepEqual(timelineView(), { recent: [], earlier: [], activity: [] });
  const result = timelineView({ history: [null, {}], log: [null, {}, { text: 'Undated note' }, { text: 'Dated note', at: '2026-09-13T10:00:00Z' }],
    files: [null, {}], tasks: 'invalid' });
  assert.deepEqual(result.recent.map(item => item.text), ['Dated note', 'Undated note']);
  assert.deepEqual(result.activity, []);
});

test('timeline never mutates the saved record', () => {
  const job = { history: [{ status: 'new' }, { status: 'applied' }], log: [{ text: 'Keep this' }], files: [{ name: 'pitch.html' }], tasks: [{ text: 'Task' }] };
  const before = JSON.stringify(job);
  timelineView(job);
  assert.equal(JSON.stringify(job), before);
});
