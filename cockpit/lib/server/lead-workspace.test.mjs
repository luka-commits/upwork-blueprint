import assert from 'node:assert/strict';
import test from 'node:test';

import { applicationListAction, leadWorkspace, nextPreparationMaterial, preparationProgress } from '../lead-workspace.mjs';

const cases = {
  new: {
    mode: 'prepare', label: 'Application preparation', defaultView: 'work',
    layout: { context: 'job', contextOpen: true, tools: false, toolsOpen: false },
    tabs: [['work', 'Preparation']],
  },
  applied: {
    mode: 'waiting', label: 'Waiting for the client', defaultView: 'work',
    layout: { context: 'job', contextOpen: true, tools: false, toolsOpen: false },
    tabs: [['work', 'Overview'], ['materials', 'Materials']],
  },
  replied: {
    mode: 'sales', label: 'Sales workspace', defaultView: 'conversation',
    layout: { context: 'job', contextOpen: true, tools: true, toolsOpen: true },
    tabs: [['conversation', 'Conversation'], ['work', 'Call and proposal'], ['materials', 'Application materials'], ['timeline', 'Timeline']],
  },
  offer: {
    mode: 'sales', label: 'Sales workspace', defaultView: 'conversation',
    layout: { context: 'job', contextOpen: true, tools: true, toolsOpen: true },
    tabs: [['conversation', 'Conversation'], ['work', 'Call and proposal'], ['materials', 'Application materials'], ['timeline', 'Timeline']],
  },
  won: {
    mode: 'delivery', label: 'Client delivery', defaultView: 'work',
    layout: { context: 'project', contextOpen: false, tools: false, toolsOpen: false },
    tabs: [['work', 'Delivery'], ['conversation', 'Conversation'], ['timeline', 'Timeline'], ['materials', 'Sales history']],
  },
  lost: {
    mode: 'closed', label: 'Lead history', defaultView: 'timeline',
    layout: { context: 'job', contextOpen: false, tools: false, toolsOpen: false },
    tabs: [['timeline', 'Timeline'], ['conversation', 'Conversation'], ['materials', 'Materials']],
  },
  skipped: {
    mode: 'closed', label: 'Lead history', defaultView: 'timeline',
    layout: { context: 'job', contextOpen: false, tools: false, toolsOpen: false },
    tabs: [['timeline', 'Timeline'], ['conversation', 'Conversation'], ['materials', 'Materials']],
  },
};

for (const [status, expected] of Object.entries(cases)) {
  test(`${status} has the intended workspace, default and tab semantics`, () => {
    const actual = leadWorkspace(status);
    assert.equal(actual.mode, expected.mode);
    assert.equal(actual.label, expected.label);
    assert.equal(actual.defaultView, expected.defaultView);
    assert.deepEqual(actual.layout, expected.layout);
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
      layout: { context: 'job', contextOpen: false, tools: false, toolsOpen: false },
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
  first.layout.contextOpen = false;
  assert.equal(leadWorkspace('new').tabs[0].label, 'Preparation');
  assert.equal(leadWorkspace('new').layout.contextOpen, true);

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
    total: 2,
    items: [
      { key: 'pitch', label: 'Pitch page and Loom script', ready: false },
      { key: 'application', label: 'Loom video and application', ready: false },
    ],
  });
});

test('preparation progress counts partial work and requires a literal valid-video flag', () => {
  const partial = preparationProgress(['pitch.html', 'loom-script.md'], false);
  assert.equal(partial.ready, 1);
  assert.deepEqual(partial.items.map(item => item.ready), [true, false]);

  const invalidVideo = preparationProgress(['pitch.html', 'loom-script.md', 'application.md'], 'yes');
  assert.equal(invalidVideo.ready, 1);
  assert.equal(invalidVideo.items.find(item => item.key === 'application').ready, false);
});

test('preparation reaches two only when both human steps are complete', () => {
  const full = preparationProgress([
    { name: 'pitch.html' },
    { name: 'loom-script.md' },
    { name: 'application.md' },
  ], true);
  assert.equal(full.ready, 2);
  assert.equal(full.total, 2);
  assert.ok(full.items.every(item => item.ready));
});

test('preparation chooses one of the two human steps', () => {
  assert.equal(nextPreparationMaterial([], false), 'pitch');
  assert.equal(nextPreparationMaterial(['pitch.html'], false), 'pitch');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md'], false), 'application');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md', 'application.md'], false), 'application');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md'], true), 'application');
  assert.equal(nextPreparationMaterial(['pitch.html', 'loom-script.md', 'application.md'], true), 'application');
});

test('lead list moves from apply to running, ready and open', () => {
  assert.equal(applicationListAction({ status: 'new', artifacts: [] }), 'apply');
  assert.equal(applicationListAction({ status: 'new', artifacts: [] }, true), 'running');
  assert.equal(applicationListAction({ status: 'new', artifacts: [{ name: 'pitch.html' }] }), 'apply');
  assert.equal(applicationListAction({ status: 'new', artifacts: [{ name: 'pitch.html' }, { name: 'loom-script.md' }] }), 'ready');
  assert.equal(applicationListAction({ status: 'new', artifacts: ['pitch.html', 'loom-script.md'], valid_artifacts: ['loom-script.md'] }), 'apply');
  assert.equal(applicationListAction({ status: 'applied', artifacts: [] }), 'open');
});
