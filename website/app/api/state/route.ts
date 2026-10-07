import { guard, json } from '@/lib/server/guard.mjs';
import { pyJson } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const state = await pyJson('cockpit.py', ['state']);
  return state ? json(state) : json({ error: 'code/cockpit.py state failed' }, 500);
}
