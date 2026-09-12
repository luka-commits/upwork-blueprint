import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || '');
  if (!ID.test(id) || typeof data?.url !== 'string') return json({ error: 'A job and pitch URL are required.' }, 400);
  const result = await pipeline('pitch-url', id, data.url);
  return json(result, result.ok ? 200 : 400);
}
