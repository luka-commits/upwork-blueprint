import { guard, json } from '@/lib/server/guard.mjs';
import { ID, pyJson } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const refused = guard(req);
  if (refused) return refused;
  const { id } = await params;
  if (!ID.test(id)) return json({ error: 'bad job' }, 400);
  const job = await pyJson('cockpit.py', ['job', id]);
  return job ? json(job) : json({ error: 'not found' }, 404);
}
