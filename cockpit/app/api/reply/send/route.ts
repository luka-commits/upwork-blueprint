import { body, guard, json } from '@/lib/server/guard.mjs';
import { ID } from '@/lib/server/root.mjs';
import { startApprovedReply } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const data = await body(req);
  const job = String(data?.job || '');
  const text = data?.text;
  if (!ID.test(job)) return json({ error: 'That job is not valid.' }, 400);
  if (typeof text !== 'string' || !text.trim()) return json({ error: 'The reply is empty.' }, 400);
  try {
    return json({ run: startApprovedReply(job, text, data?.draft, data?.draft_set) });
  } catch (err) {
    return json({ error: String((err as Error).message || err) }, 400);
  }
}
