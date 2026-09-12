import { guard, json } from '@/lib/server/guard.mjs';
import { RUNS } from '@/lib/server/runs.mjs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// The live stream of one run. The page reads it with fetch, which can carry the
// token; the browser's EventSource cannot, and that is why the old page showed
// the command name and then nothing.
export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const refused = guard(req);
  if (refused) return refused;
  const { id } = await params;
  const run = RUNS.get(id);
  if (!run) return json({ error: 'no such run' }, 404);
  const encoder = new TextEncoder();
  let sent = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  const stream = new ReadableStream({
    start(controller) {
      const tick = () => {
        while (sent < run.events.length) controller.enqueue(encoder.encode(`data: ${JSON.stringify(run.events[sent++])}\n\n`));
        if (run.done && sent >= run.events.length) {
          clearInterval(timer);
          controller.close();
        }
      };
      timer = setInterval(tick, 400);
      tick();
    },
    cancel() { clearInterval(timer); },
  });
  return new Response(stream, { headers: { 'content-type': 'text/event-stream; charset=utf-8', 'cache-control': 'no-store' } });
}
