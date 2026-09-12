import test from 'node:test';
import assert from 'node:assert/strict';
import { jobPreview } from '../job-brief.mjs';

test('new-job previews explain the job, never substitute the fit rationale', () => {
  const job = { status: 'new', summary: 'Build checkout and membership access for a coaching business.', rationale: 'An exact overlap with your proof.' };
  assert.equal(jobPreview(job), job.summary);
  assert.equal(jobPreview({ ...job, status: 'applied' }), job.summary);
});

test('a clearer saved outcome wins and stays complete for narrow rows', () => {
  const outcome = 'Members choose a plan and pay monthly or yearly. The right course access opens automatically. The owner receives a documented setup in GoHighLevel.';
  assert.equal(jobPreview({ summary: 'Membership automation.', details: { brief: { outcome } } }), outcome);
});

test('a missing description is honest rather than replaced with sales advice', () => {
  assert.match(jobPreview({ rationale: 'A great match for your work.' }), /Open this job/);
  assert.equal(jobPreview({ summary: 'Build a checkout. Crowded already, so it needs a pitch page to stand out.' }), 'Build a checkout.');
});

test('a partial structured brief still uses the available summary', () => {
  const summary = 'Connect enquiry forms to a booking calendar.';
  assert.equal(jobPreview({ summary, details: { brief: { scope: ['Build the forms.'] } } }), summary);
});
