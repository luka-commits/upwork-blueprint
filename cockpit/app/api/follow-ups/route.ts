import { guard, json } from '@/lib/server/guard.mjs';
import { ROOT } from '@/lib/server/root.mjs';
import { readFollowUpReport } from '@/lib/server/follow-up-report.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  return json(readFollowUpReport(ROOT));
}
