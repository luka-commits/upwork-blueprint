import { guard, json } from '@/lib/server/guard.mjs';
import { pyJson } from '@/lib/server/root.mjs';
import { RUNNABLE, available } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const state = await pyJson('cockpit.py', ['state']);
  if (!state) return json({ error: 'code/cockpit.py state failed' }, 500);
  const commands = Object.entries(RUNNABLE).filter(([, spec]) => spec.command !== false).map(([name]) => name).concat('inbox');
  state.commands = Object.fromEntries(commands.map(name => [name, available(name)]));
  return json(state);
}
