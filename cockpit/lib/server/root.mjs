// Where the Blueprint lives and how the cockpit talks to its Python scripts.
// The data and every change go through the same tested scripts the commands use:
// code/cockpit.py reads, code/pipeline.py is the one writer.
import { execFile, execFileSync } from 'node:child_process';
import path from 'node:path';

export const ROOT = process.env.BLUEPRINT_ROOT || path.resolve(process.cwd(), '..');
export const JOBS_DIR = process.env.BLUEPRINT_JOBDIR || path.join(ROOT, 'jobs');
export const ID = /^[0-9]{6,25}$/;

let python = null;
export function pythonBin() {
  if (python) return python;
  for (const candidate of process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python']) {
    try {
      execFileSync(candidate, ['--version'], { stdio: 'ignore' });
      python = candidate;
      return python;
    } catch { /* try the next name */ }
  }
  throw new Error('Python 3 is not installed or not on the PATH.');
}

export function runPython(script, args) {
  return new Promise(resolve => {
    execFile(pythonBin(), [path.join(ROOT, 'code', script), ...args],
      { cwd: ROOT, maxBuffer: 64 * 1024 * 1024, env: process.env },
      (err, stdout, stderr) => resolve({ ok: !err, stdout: String(stdout), stderr: String(stderr) }));
  });
}

export async function pyJson(script, args) {
  const r = await runPython(script, args);
  if (!r.ok) return null;
  return JSON.parse(r.stdout);
}

/** One call to the pipeline, answered in the words the script printed. */
export async function pipeline(...args) {
  const r = await runPython('pipeline.py', args);
  return { ok: r.ok, message: (r.stdout || r.stderr).trim().replace(/^ABORT: /, '') };
}
