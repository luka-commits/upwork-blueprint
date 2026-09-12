import assert from 'node:assert/strict';
import test from 'node:test';
import { calendarDate, todayIso } from '../dates.mjs';

test('due dates keep their calendar day for members west and east of UTC', () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = 'America/Los_Angeles';
    assert.equal(todayIso(new Date('2026-09-12T00:30:00Z')), '2026-09-11');
    assert.equal(calendarDate('2026-09-12').getDate(), 12);
    process.env.TZ = 'Europe/Berlin';
    assert.equal(todayIso(new Date('2026-09-12T23:30:00Z')), '2026-09-13');
    assert.equal(calendarDate('2026-09-12').getDate(), 12);
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous; }
});
