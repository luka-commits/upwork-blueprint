import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID, pipeline } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const id = String(data?.id || '');
  const website = String(data?.website || '');
  const placeId = String(data?.place_id || '');
  const language = data?.language === 'German' ? 'German' : 'English';
  if (!ID.test(id) || !website) return json({ error: 'A job and business website are required.' }, 400);
  if (website.length > 500 || placeId.length > 220) return json({ error: 'The lead magnet source is too long.' }, 400);
  const args = ['lead-magnet-source', id, website, '--language', language];
  if (placeId) args.push('--place-id', placeId);
  const result = await pipeline(...args);
  return json(result, result.ok ? 200 : 400);
}
