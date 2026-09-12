import { body, guard, json } from '@/lib/server/guard.mjs';
import { releaseApprovedReply } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  try {
    releaseApprovedReply(String(data?.job || ''), String(data?.written_at || ''));
    return json({ ok: true, message: 'The approval lock is cleared. Nothing was sent.' });
  } catch (error) {
    return json({ error: String((error as Error).message || error) }, 409);
  }
}
