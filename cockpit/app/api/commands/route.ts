import fs from 'node:fs';
import path from 'node:path';
import { guard, json } from '@/lib/server/guard.mjs';
import { ROOT } from '@/lib/server/root.mjs';
import { RUNNABLE } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// The course order from CLAUDE.md, then anything else alphabetically.
const PATH = ['audit', 'benchmark', 'profile', 'find-jobs', 'pitch-page', 'apply', 'inbox', 'reply', 'status', 'proposal', 'won', 'sync', 'cockpit'];

export async function GET(req: Request) {
  const refused = guard(req);
  if (refused) return refused;
  const dir = path.join(ROOT, '.claude', 'commands');
  const commands = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.md')).map(file => {
    const name = file.slice(0, -3);
    const text = fs.readFileSync(path.join(dir, file), 'utf-8');
    const front = text.match(/^---\n([\s\S]*?)\n---/)?.[1] || '';
    const field = (key: string) => (front.match(new RegExp(`^${key}:\\s*(.*)$`, 'm'))?.[1] || '').replace(/^"|"$/g, '').trim();
    const spec = (RUNNABLE as Record<string, { job: boolean }>)[name];
    return { name, description: field('description'), hint: field('argument-hint'), button: !!spec, needsJob: !!spec?.job };
  }) : [];
  const rank = (n: string) => (PATH.indexOf(n) + 1 || 99);
  commands.sort((a, b) => rank(a.name) - rank(b.name) || a.name.localeCompare(b.name));
  return json(commands);
}
