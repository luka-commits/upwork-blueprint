import fs from 'node:fs';
import path from 'node:path';
import { isLocal, json } from '@/lib/server/guard.mjs';
import { ID, JOBS_DIR } from '@/lib/server/root.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.md': 'text/plain; charset=utf-8', '.pdf': 'application/pdf',
  '.png': 'image/png', '.json': 'application/json; charset=utf-8',
};

// A job's own files (pitch page, application, one-pager). Links and previews open
// them directly, so there is no token here, only the local host check and a path
// that cannot leave the job's folder.
export async function GET(req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  if (!isLocal(req)) return json({ error: 'local only' }, 403);
  const { id, name } = await params;
  if (!ID.test(id) || !/^[\w.-]+$/.test(name) || name === 'thread.json') return json({ error: 'not found' }, 404);
  const base = path.resolve(JOBS_DIR, id);
  const target = path.resolve(base, name);
  if (path.dirname(target) !== base || !fs.existsSync(target) || !fs.statSync(target).isFile()) return json({ error: 'not found' }, 404);
  return new Response(fs.readFileSync(target), {
    headers: { 'content-type': TYPES[path.extname(name)] || 'application/octet-stream', 'cache-control': 'no-store' },
  });
}
