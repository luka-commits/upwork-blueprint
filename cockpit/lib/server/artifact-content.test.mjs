import assert from 'node:assert/strict';
import test from 'node:test';

import { artifactUrl, artifactVersion, runArtifactRequest } from '../artifact-content.mjs';

test('artifact versions prefer the precise saved version and retain the timestamp fallback', () => {
  const files = [
    { name: 'application.md', at: '2026-09-12T12:00:00Z', version: '123-45' },
    { name: 'proposal.md', at: '2026-09-12T13:00:00Z' },
  ];
  assert.equal(artifactVersion(files, 'application.md'), '123-45');
  assert.equal(artifactVersion(files, 'proposal.md'), '2026-09-12T13:00:00Z');
  assert.equal(artifactVersion(files, 'missing.md'), '');
  assert.equal(artifactUrl('123456', 'application.md', '123-45'), '/files/123456/application.md?v=123-45');
});

test('artifact reads distinguish content, empty files, response errors and rejected reads', async () => {
  const read = async fetcher => {
    const states = [];
    await runArtifactRequest(fetcher, '/file', new AbortController().signal, state => states.push(state));
    return states;
  };

  assert.deepEqual(await read(async () => ({ ok: true, text: async () => 'Current text' })),
    [{ status: 'ready', text: 'Current text' }]);
  assert.deepEqual(await read(async () => ({ ok: true, text: async () => ' \n ' })),
    [{ status: 'empty', text: '' }]);
  assert.deepEqual(await read(async () => ({ ok: false, text: async () => 'private error' })),
    [{ status: 'error', text: '' }]);
  assert.deepEqual(await read(async () => { throw new Error('network detail'); }),
    [{ status: 'error', text: '' }]);
});

test('an older request cannot publish after a newer version finishes', async () => {
  const states = [];
  const oldController = new AbortController();
  let finishOldBody;
  const oldRequest = runArtifactRequest(async () => ({
    ok: true,
    text: () => new Promise(resolve => { finishOldBody = resolve; }),
  }), '/file?v=old', oldController.signal, state => states.push(['old', state]));
  await new Promise(resolve => setImmediate(resolve));

  oldController.abort();
  await runArtifactRequest(async () => ({ ok: true, text: async () => 'New text' }),
    '/file?v=new', new AbortController().signal, state => states.push(['new', state]));
  finishOldBody('Obsolete text');
  await oldRequest;

  assert.deepEqual(states, [['new', { status: 'ready', text: 'New text' }]]);
});
