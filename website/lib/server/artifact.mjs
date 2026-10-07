import fs from 'node:fs';
import path from 'node:path';

const INTERNAL = new Set(['thread.json', 'replies.json', 'outbox.json']);

/** Generated HTML is untrusted and must not inherit the cockpit's token origin. */
export function artifactPath(jobsDir, id, name) {
  if (!/^[0-9]{6,25}$/.test(id) || !/^[\w][\w.-]*$/.test(name) || INTERNAL.has(name)) return null;
  const base = path.resolve(jobsDir, id), target = path.resolve(base, name);
  try {
    if (path.dirname(target) !== base || fs.realpathSync(base) !== base
        || fs.realpathSync(target) !== target || !fs.statSync(target).isFile()) return null;
    return target;
  } catch { return null; }
}

export const ARTIFACT_CSP = "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox allow-downloads; frame-ancestors 'self'; object-src 'none'; base-uri 'none'";
