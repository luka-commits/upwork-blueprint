import test from 'node:test';
import assert from 'node:assert/strict';
import { analyticsTiles, replyDelay } from '../analytics-view.mjs';

test('analytics keep incomplete volume distinct from a verified zero', () => {
  const incomplete = analyticsTiles({ applications_28d_complete: false, applications_28d: null, applications_28d_known: 0, application_dates_unknown: 2 });
  assert.equal(incomplete[2].value, null);
  assert.equal(incomplete[2].empty, 'Dates missing');
  assert.match(incomplete[2].hint, /2 applications with a missing/);
  const zero = analyticsTiles({ applications_28d_complete: true, applications_28d: 0 });
  assert.equal(zero[2].value, 0);
});

test('timing never turns missing, negative or invalid values into instant replies', () => {
  for (const hours of [null, undefined, -1, NaN, Infinity, '2']) assert.equal(replyDelay(hours), null);
  assert.equal(replyDelay(0), 'Under a minute');
  assert.equal(replyDelay(.5), '30 min');
  assert.equal(replyDelay(2.5), '2.5 hr');
  assert.equal(replyDelay(72), '3 days');
});

test('every displayed rate and reply delay carries its sample and scope', () => {
  const tiles = analyticsTiles({ applied_total: 8, replied_total: 2, reply_rate: 25, reply_hours: 2.5, reply_time_sample: 1, reply_time_missing: 1 });
  assert.equal(tiles[0].value, '25%');
  assert.match(tiles[0].hint, /2 of 8 applied leads/);
  assert.match(tiles[0].hint, /not a dated comparison/);
  assert.equal(tiles[1].value, '2.5 hr');
  assert.match(tiles[1].hint, /1 verified pair/);
  assert.match(tiles[1].hint, /1 conversation without verified timing/);
});

test('Loom quality carries its review sample and stays empty without one', () => {
  const measured = analyticsTiles({ loom_score: 86, loom_score_sample: 2 })[3];
  assert.equal(measured.value, '86/100');
  assert.match(measured.hint, /2 saved Loom reviews/);
  assert.match(measured.hint, /not an Upwork metric/);
  const empty = analyticsTiles({})[3];
  assert.equal(empty.value, null);
  assert.equal(empty.empty, 'No reviews yet');
});
