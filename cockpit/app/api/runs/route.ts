import { guard, json } from '@/lib/server/guard.mjs';
import { RUNS, summary } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  return json([...RUNS.values()].map(summary));
}
