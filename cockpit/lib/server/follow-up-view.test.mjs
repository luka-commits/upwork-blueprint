import assert from 'node:assert/strict';
import test from 'node:test';
import { followUpInline, followUpLeadHref, followUpReviewAge, parseFollowUpReport } from '../follow-up-view.mjs';

test('saved review sections retain decisions, context and safe lead links', () => {
  const source = '# Follow-up review\nMade on Saturday 12 September.\n\n## Do today\n### [Coaching checkout](/job/123456)\n**Decision:** Review the draft.\n\n- Confirm the scope.\n  Use the saved client question.\n- Keep the next step small.\n\n## Coming up (1)\nCheck the applied proposal on Tuesday.\n\n## Parked\nNo reason to contact them again.';
  const out = parseFollowUpReport(source);
  assert.deepEqual(out.sections.map(section => section.title), ['Do today', 'Coming up', 'Parked']);
  assert.equal(out.sections[0].blocks[0].text, '[Coaching checkout](/job/123456)');
  assert.deepEqual(out.sections[0].blocks[2].items, ['Confirm the scope. Use the saved client question.', 'Keep the next step small.']);
  assert.match(JSON.stringify(out), /No reason to contact them again/);
});

test('unstructured, empty and extra report content is never lost or called zero due', () => {
  assert.deepEqual(parseFollowUpReport(''), { intro: [], sections: [] });
  assert.equal(parseFollowUpReport('A useful review in an older format.').intro[0].text, 'A useful review in an older format.');
  const out = parseFollowUpReport('**Do today**\nFirst item\n## Do today\nSecond item\n## Other context\nStill keep this.');
  assert.equal(out.sections.length, 1);
  assert.match(JSON.stringify(out), /First item Second item/);
  assert.match(JSON.stringify(out), /Still keep this/);
});

test('report links only navigate to local lead pages, never execute or leave the app', () => {
  for (const link of ['/job/123456', 'http://127.0.0.1:4321/job/123456', 'http://localhost:4321/job/123456/']) {
    assert.equal(followUpLeadHref(link), '/job/123456');
  }
  for (const link of ['javascript:alert(1)', 'https://upwork.com/job/123456', '//evil.test/job/123456', '/api/run', '/job/123456/../../api/run', '/job/123456?send=true', '/job/123']) {
    assert.equal(followUpLeadHref(link), null, link);
  }
  const parts = followUpInline('**Decision:** [open](/job/123456) and [unsafe](javascript:bad) <script>bad</script>');
  assert.equal(parts[0].kind, 'strong');
  assert.equal(parts.find(part => part.text === 'open').href, '/job/123456');
  assert.equal(parts.find(part => part.text === 'unsafe').href, null);
  assert.ok(parts.some(part => part.text.includes('<script>bad</script>')));
});

test('review age compares local calendar dates and keeps unknown timestamps honest', () => {
  const now = new Date(2026, 8, 12, 18);
  assert.equal(followUpReviewAge(new Date(2026, 8, 12, 7).toISOString(), now), 'today');
  assert.equal(followUpReviewAge(new Date(2026, 8, 11, 23).toISOString(), now), 'older');
  for (const value of [null, '', 'not a date', new Date(2026, 8, 13).toISOString()]) assert.equal(followUpReviewAge(value, now), 'unknown');
});
