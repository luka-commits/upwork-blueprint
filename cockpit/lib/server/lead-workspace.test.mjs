import assert from 'node:assert/strict';
import test from 'node:test';

import { leadWorkspace, nextPreparationMaterial, preparationProgress } from '../lead-workspace.mjs';

const cases = {
  new: {
    mode: 'prepare', label: 'Application preparation', defaultView: 'work',
    tabs: [['work', 'Preparation'], ['conversation', 'Conversation'], ['timeline', 'Timeline']],
  },
  applied: {
    mode: 'waiting', label: 'Waiting for the client', defaultView: 'work',
    tabs: [['work', 'Overview'], ['materials', 'Materials'], ['conversation', 'Conversation'], ['timeline', 'Timeline']],
  },
  replied: {
    mode: 'sales', label: 'Sales workspace', defaultView: 'conversation',
    tabs: [['conversation', 'Conversation'], ['work', 'Call and proposal'], ['materials', 'Application materials'], ['timeline', 'Timeline']],
  },
  offer: {
    mode: 'sales', label: 'Sales workspace', defaultView: 'conversation',
    tabs: [['conversation', 'Conversation'], ['work', 'Call and proposal'], ['materials', 'Application materials'], ['timeline', 'Timeline']],
  },
  won: {
    mode: 'delivery', label: 'Client delivery', defaultView: 'work',
    tabs: [['work', 'Delivery'], ['conversation', 'Conversation'], ['timeline', 'Timeline'], ['materials', 'Sales history']],
  },
  lost: {
    mode: 'closed', label: 'Lead history', defaultView: 'timeline',
    tabs: [['timeline', 'Timeline'], ['conversation', 'Conversation'], ['materials', 'Materials']],
  },
  skipped: {
    mode: 'closed', label: 'Lead history', defaultView: 'timeline',
    tabs: [['timeline', 'Timeline'], ['conversation', 'Conversation'], ['materials', 'Materials']],
  },
};

for (const [status, expected] of Object.entries(cases)) {
  test(`${status} has the intended workspace, default and tab semantics`, () => {
    const actual = leadWorkspace(status);
    assert.equal(actual.mode, expected.mode);
    assert.equal(actual.label, expected.label);
    assert.equal(actual.defaultView, expected.defaultView);
    assert.deepEqual(actual.tabs.map(tab => [tab.key, tab.label]), expected.tabs);
    assert.ok(actual.tabs.some(tab => tab.key === actual.defaultView));
  });
}

test('unknown and empty statuses fail closed to safe lead history', () => {
  for (const status of ['unknown', 'paused', '', null, undefined]) {
    assert.deepEqual(leadWorkspace(status), {
      mode: 'closed',
      label: 'Lead history',
      defaultView: 'timeline',
      tabs: [
        { key: 'timeline', label: 'Timeline' },
        { key: 'conversation', label: 'Conversation' },
        { key: 'materials', label: 'Materials' },
      ],
    });
  }
});

test('workspace results and preparation inputs are not mutated or shared', () => {
  const first = leadWorkspace('new');
  first.tabs[0].label = 'Changed';
  assert.equal(leadWorkspace('new').tabs[0].label, 'Preparation');

  const files = Object.freeze([
    Object.freeze({ name: 'pitch.html' }),
    Object.freeze({ name: 'loom-script.md' }),
  ]);
  const before = JSON.stringify(files);
  preparationProgress(files, false);
  assert.equal(JSON.stringify(files), before);
});

test('preparation progress starts at zero', () => {
  assert.deepEqual(preparationProgress([], false), {
    ready: 0,
    total: 4,
    items: [
      { key: 'pitch', label: 'Pitch page', ready: false },
      { key: 'script', label: 'Loom script', ready: false },
      { key: 'video', label: 'Loom video', ready: false },
      { key: 'application', label: 'Application', ready: false },
    ],
  });
});

test('preparation progress counts partial work and requires a literal valid-video flag', () => {
  const partial = preparationProgress(['pitch.html', 'loom-script.md'], false);
  assert.equal(partial.ready, 2);
  assert.deepEqual(partial.items.map(item => item.ready), [true, true, false, false]);

  const invalidVideo = preparationProgress(['pitch.html', 'loom-script.md', 'application.md'], 'yes');
  assert.equal(invalidVideo.ready, 3);
  assert.equal(invalidVideo.items.find(item => item.key === 'video').ready, false);
});

test('preparation progress reaches four only with every file and a valid video', () => {
  const full = preparationProgress([
    { name: 'pitch.html' },
    { name: 'loom-script.md' },
    { name: 'application.md' },
  ], true);
  assert.equal(full.ready, 4);
  assert.equal(full.total, 4);
  assert.ok(full.items.every(item => item.ready));
});

test('preparation opens exactly the next prerequisite, never a blocked application', () => {
  assert.equal(nextPreparationMaterial([], false), 'pitch');
  assert.equal(nextPreparationMaterial(['pitch.html'], false), 'script');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md'], false), 'video');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md', 'application.md'], false), 'video');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md'], true), 'application');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md', 'application.md'], true), 'application');
});
