import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pyJson } from '@/lib/server/root.mjs';
import { RUNNABLE, applicationPrerequisiteError, available, startRun } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const name = String(data?.command || ''), job = String(data?.job || '');
  if (!available(name)) return json({ error: `/${name} is not built yet` }, 400);
  if (RUNNABLE[name].command === false) return json({ error: 'That run has a dedicated approval endpoint.' }, 400);
  const jobScoped = RUNNABLE[name].job || (RUNNABLE[name].optionalJob && !!job);
  if (jobScoped && !ID.test(job)) return json({ error: 'this command needs a job' }, 400);
  if (jobScoped) {
    const lead = await pyJson('cockpit.py', ['job', job]);
    if (!lead) return json({ error: 'That job is not in the pipeline.' }, 404);
    const blocked = name === 'apply' ? applicationPrerequisiteError(lead) : '';
    if (blocked) return json({ error: blocked }, 409);
  }
  try {
    return json({ run: startRun(name, jobScoped ? job : null) });
  } catch (err) {
    return json({ error: String((err as Error).message || err) }, 500);
  }
}
