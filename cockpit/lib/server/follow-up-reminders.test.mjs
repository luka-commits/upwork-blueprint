import assert from 'node:assert/strict';
import test from 'node:test';

import { scheduledFollowUps } from '../follow-up-reminders.mjs';

test('returns past, current and future reminders in date then title and id order', () => {
  const jobs = [
    { id: '123459', title: 'Zulu', status: 'offer', next_follow_up: '2026-09-13' },
    { id: '123458', title: 'Beta', status: 'replied', next_follow_up: '2026-09-12' },
    { id: '123457', title: 'Alpha', status: 'applied', next_follow_up: '2026-09-12' },
    { id: '123456', title: 'Past', status: 'applied', next_follow_up: '2026-09-11' },
    { id: '123455', title: 'Alpha', status: 'applied', next_follow_up: '2026-09-12' },
  ];

  assert.deepEqual(scheduledFollowUps(jobs, '2026-09-12').map(job => job.id),
    ['123456', '123455', '123457', '123458', '123459']);
});

test('sanitizes saved reminder fields without deciding send eligibility', () => {
  const [reminder] = scheduledFollowUps([{
    id: ' 123456 ',
    title: '  CRM follow-up  ',
    status: ' Replied ',
    next_follow_up: '2026-09-12',
    thread: null,
    follow_up_plan: {
      reason: '  Client named a September decision.  ',
      lane: ' warm ',
      step: 2,
      max_steps: 3,
    },
  }], '2026-09-12');

  assert.deepEqual(reminder, {
    id: '123456',
    title: 'CRM follow-up',
    status: 'replied',
    due: '2026-09-12',
    reason: 'Client named a September decision.',
    lane: 'warm',
    step: 2,
    max_steps: 3,
  });
  assert.equal(Object.hasOwn(reminder, 'sendable'), false);
  assert.equal(Object.hasOwn(reminder, 'contact'), false);
});

test('keeps a valid won client check-in', () => {
  const result = scheduledFollowUps([{
    id: '777777', title: 'Client delivery', status: 'won',
    next_follow_up: '2026-10-01', follow_up_plan: { reason: 'Confirmed check-in' },
  }], '2026-09-12');
  assert.equal(result.length, 1);
  assert.equal(result[0].status, 'won');
  assert.equal(result[0].due, '2026-10-01');
});

test('excludes impossible dates, invalid ids and inactive or unknown statuses', () => {
  const jobs = [
    { id: '123456', title: 'Impossible', status: 'applied', next_follow_up: '2026-02-30' },
    { id: '123457', title: 'Non-leap', status: 'replied', next_follow_up: '2025-02-29' },
    { id: '123458', title: 'New', status: 'new', next_follow_up: '2026-09-12' },
    { id: '123459', title: 'Lost', status: 'lost', next_follow_up: '2026-09-12' },
    { id: '123460', title: 'Skipped', status: 'skipped', next_follow_up: '2026-09-12' },
    { id: '123461', title: 'Unknown', status: 'paused', next_follow_up: '2026-09-12' },
    { id: 'short', title: 'Bad id', status: 'applied', next_follow_up: '2026-09-12' },
  ];
  assert.deepEqual(scheduledFollowUps(jobs, '2026-09-12'), []);
});

test('malformed optional plan fields become null or an empty reason', () => {
  const result = scheduledFollowUps([{
    id: '123456', title: null, status: 'offer', next_follow_up: '2026-09-12',
    follow_up_plan: { reason: 42, lane: [], step: 3, max_steps: 2 },
  }], '2026-09-12');
  assert.deepEqual(result[0], {
    id: '123456',
    title: 'Untitled job',
    status: 'offer',
    due: '2026-09-12',
    reason: '',
    lane: null,
    step: null,
    max_steps: null,
  });
});

test('does not mutate jobs or nested follow-up plans', () => {
  const plan = Object.freeze({ reason: 'Open decision', lane: 'hot', step: 1, max_steps: 3 });
  const job = Object.freeze({
    id: '123456', title: 'Frozen', status: 'applied',
    next_follow_up: '2026-09-12', follow_up_plan: plan,
  });
  const jobs = Object.freeze([job]);
  const before = JSON.stringify(jobs);
  scheduledFollowUps(jobs, '2026-09-12');
  assert.equal(JSON.stringify(jobs), before);
});

test('rejects a malformed reference day instead of inventing one', () => {
  const jobs = [{ id: '123456', title: 'Valid reminder', status: 'applied', next_follow_up: '2026-09-12' }];
  assert.deepEqual(scheduledFollowUps(jobs, '2026-02-30'), []);
});
