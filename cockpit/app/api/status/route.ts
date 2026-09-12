import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const STATUSES = ['new', 'applied', 'replied', 'offer', 'won', 'lost', 'skipped'];

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || '');
  if (!ID.test(id) || !STATUSES.includes(data?.status)) return json({ error: 'bad job or status' }, 400);
  const args = ['set', id, data.status];
  if (data.note) args.push('--note', String(data.note));
  if (data.follow_up) args.push('--follow-up', String(data.follow_up));
  const r = await pipeline(...args);
  return json(r, r.ok ? 200 : 400);
}
