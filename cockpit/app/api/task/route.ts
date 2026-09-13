import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || ''), action = data?.action;
  const value = String(data?.text ?? data?.task ?? '').trim();
  if (!ID.test(id) || !['add', 'done', 'reopen', 'delete'].includes(action) || !value) {
    return json({ error: 'bad job, action or empty task' }, 400);
  }
  const args = ['task', id, action, value];
  if (data.due) args.push('--due', String(data.due));
  if (data.time) args.push('--time', String(data.time));
  const r = await pipeline(...args);
  return json(r, r.ok ? 200 : 400);
}
