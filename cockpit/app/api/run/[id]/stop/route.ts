import { guard, json } from '@/lib/server/guard.mjs';
import { stopRun } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const refused = guard(req);
  if (refused) return refused;
  const { id } = await params;
  const ok = stopRun(id);
  return json({ ok, message: ok ? 'Stopped.' : 'That run is not running.' }, ok ? 200 : 404);
}
