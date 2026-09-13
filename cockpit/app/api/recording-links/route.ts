import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || '');
  if (!ID.test(id) || !Array.isArray(data?.links)) return json({ error: 'A job and recording links are required.' }, 400);
  const result = await pipeline('recording-links', id, JSON.stringify(data.links));
  return json(result, result.ok ? 200 : 400);
}
