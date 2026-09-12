import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { readFollowUpReport } from './follow-up-report.mjs';

const freshRoot = () => fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'follow-up-report-')));
const remove = root => fs.rmSync(root, { recursive: true, force: true });

test('reads only the normal follow-up report with its save time', () => {
  const root = freshRoot();
  try {
    const text = '# Follow-ups\n\n## Do today\n\n- Review the active conversation.\n';
    fs.writeFileSync(path.join(root, 'follow-ups.md'), text);
    const report = readFollowUpReport(root);
    assert.equal(report.available, true);
    assert.equal(report.text, text);
    assert.match(report.modified_at, /^\d{4}-\d\d-\d\dT/);
    assert.equal(report.error, undefined);
  } finally { remove(root); }
});

test('a missing report is unavailable without being an error', () => {
  const root = freshRoot();
  try {
    assert.deepEqual(readFollowUpReport(root), { available: false, modified_at: null, text: '' });
  } finally { remove(root); }
});

test('an empty report says that no report is saved without claiming zero due', () => {
  const root = freshRoot();
  try {
    fs.writeFileSync(path.join(root, 'follow-ups.md'), '  \n');
    const report = readFollowUpReport(root);
    assert.equal(report.available, false);
    assert.match(report.error, /No follow-up report has been saved yet/);
    assert.doesNotMatch(report.error, /\b0\b|zero|due/i);
    assert.equal(report.text, '');
    assert.equal(report.modified_at, null);
  } finally { remove(root); }
});

test('rejects a symlink without exposing its target or contents', () => {
  const root = freshRoot();
  try {
    const privateFile = path.join(root, 'private-client-data.txt');
    fs.writeFileSync(privateFile, 'private account secret');
    fs.symlinkSync(privateFile, path.join(root, 'follow-ups.md'));
    const report = readFollowUpReport(root);
    assert.equal(report.available, false);
    assert.match(report.error, /not a regular file/);
    assert.doesNotMatch(JSON.stringify(report), /private-client-data|account secret|follow-up-report-/);
  } finally { remove(root); }
});

test('rejects a directory and an oversized file', () => {
  const root = freshRoot();
  try {
    const file = path.join(root, 'follow-ups.md');
    fs.mkdirSync(file);
    assert.match(readFollowUpReport(root).error, /not a regular file/);
    fs.rmdirSync(file);
    fs.writeFileSync(file, Buffer.alloc(256 * 1024 + 1, 65));
    assert.match(readFollowUpReport(root).error, /too large/);
  } finally { remove(root); }
});

test('rejects invalid UTF-8 and NUL text', () => {
  const root = freshRoot();
  try {
    const file = path.join(root, 'follow-ups.md');
    fs.writeFileSync(file, Buffer.from([0xc3, 0x28]));
    assert.match(readFollowUpReport(root).error, /not valid text/);
    fs.writeFileSync(file, 'Do today\0private tail');
    const report = readFollowUpReport(root);
    assert.match(report.error, /not valid text/);
    assert.doesNotMatch(JSON.stringify(report), /private tail/);
  } finally { remove(root); }
});

test('an unreadable report returns a safe error', { skip: process.platform === 'win32' }, () => {
  const root = freshRoot();
  const file = path.join(root, 'follow-ups.md');
  try {
    fs.writeFileSync(file, 'private contents');
    fs.chmodSync(file, 0o000);
    const report = readFollowUpReport(root);
    assert.equal(report.available, false);
    assert.equal(report.error, 'The saved follow-up report could not be read.');
    assert.doesNotMatch(JSON.stringify(report), /private contents|follow-up-report-/);
  } finally {
    try { fs.chmodSync(file, 0o600); } catch { /* Cleanup still removes a missing file. */ }
    remove(root);
  }
});
