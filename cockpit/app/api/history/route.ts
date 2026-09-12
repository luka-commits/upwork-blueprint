import { guard, json } from '@/lib/server/guard.mjs';
import { history } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// The last finished runs with their result and steps, newest first.
export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  return json(history());
}
