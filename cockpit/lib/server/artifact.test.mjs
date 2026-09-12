import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { artifactPath, ARTIFACT_CSP } from './artifact.mjs';

test('artifact routes reject private receipts, hidden files and symlink escapes', () => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-')));
  try {
    const job = path.join(root, '123456');
    fs.mkdirSync(job);
    fs.writeFileSync(path.join(job, 'pitch.html'), '<h1>Pitch</h1>');
    fs.writeFileSync(path.join(root, 'private.json'), 'secret');
    fs.symlinkSync(path.join(root, 'private.json'), path.join(job, 'public.json'));
    assert.equal(artifactPath(root, '123456', 'pitch.html'), path.join(job, 'pitch.html'));
    for (const name of ['../private.json', '.thread-confirm.json', 'thread.json', 'outbox.json', 'replies.json', 'public.json']) {
      assert.equal(artifactPath(root, '123456', name), null, name);
    }
    assert.ok(ARTIFACT_CSP.includes('sandbox allow-scripts'));
    assert.ok(!ARTIFACT_CSP.includes('allow-same-origin'));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
