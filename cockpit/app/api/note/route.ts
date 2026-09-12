import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || ''), text = String(data?.text || '').trim();
  if (!ID.test(id) || !text) return json({ error: 'bad job or empty note' }, 400);
  const r = await pipeline('note', id, text);
  return json(r, r.ok ? 200 : 400);
}
