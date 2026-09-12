import fs from 'node:fs';
import path from 'node:path';
import { TextDecoder } from 'node:util';

const MAX_BYTES = 256 * 1024;
const MISSING = { available: false, modified_at: null, text: '' };

function unavailable(error) {
  return { available: false, modified_at: null, text: '', error };
}

/** Read the one generated follow-up report. No caller-controlled filename is accepted. */
export function readFollowUpReport(root) {
  const file = path.join(root, 'follow-ups.md');
  let entry;
  try {
    entry = fs.lstatSync(file);
  } catch (error) {
    if (error?.code === 'ENOENT') return { ...MISSING };
    return unavailable('The saved follow-up report could not be read.');
  }
  if (entry.isSymbolicLink() || !entry.isFile()) {
    return unavailable('The saved follow-up report is not a regular file.');
  }
  if (entry.size > MAX_BYTES) {
    return unavailable('The saved follow-up report is too large to open.');
  }

  let descriptor;
  try {
    descriptor = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    const current = fs.fstatSync(descriptor);
    if (!current.isFile()) return unavailable('The saved follow-up report is not a regular file.');
    if (current.size > MAX_BYTES) return unavailable('The saved follow-up report is too large to open.');
    const buffer = Buffer.alloc(current.size);
    let read = 0;
    while (read < buffer.length) {
      const count = fs.readSync(descriptor, buffer, read, buffer.length - read, read);
      if (!count) break;
      read += count;
    }
    let text;
    try {
      text = new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(0, read));
    } catch {
      return unavailable('The saved follow-up report is not valid text.');
    }
    if (text.includes('\0')) return unavailable('The saved follow-up report is not valid text.');
    if (!text.trim()) return unavailable('No follow-up report has been saved yet.');
    return { available: true, modified_at: current.mtime.toISOString(), text };
  } catch {
    return unavailable('The saved follow-up report could not be read.');
  } finally {
    if (descriptor !== undefined) {
      try { fs.closeSync(descriptor); } catch { /* The read result remains authoritative. */ }
    }
  }
}
