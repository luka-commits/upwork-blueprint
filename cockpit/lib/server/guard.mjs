// The door. The cockpit can start Claude with the member's Upwork connector, so
// only this computer may talk to it, and only the page it served: a request needs
// the local host name and the token that page carries. Another website open in the
// same browser has neither.
import crypto from 'node:crypto';

const holder = globalThis;
export const TOKEN = holder.__cockpitToken ??= crypto.randomBytes(24).toString('base64url');

export const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});

export function isLocal(req) {
  const host = (req.headers.get('host') || '').replace(/:\d+$/, '');
  return host === '127.0.0.1' || host === 'localhost';
}

/** Returns a refusal to send back, or null when the request may pass. */
export function guard(req) {
  if (!isLocal(req)) return json({ error: 'local only' }, 403);
  const given = Buffer.from(req.headers.get('x-cockpit-token') || '');
  const want = Buffer.from(TOKEN);
  if (given.length !== want.length || !crypto.timingSafeEqual(given, want)) return json({ error: 'missing token' }, 403);
  return null;
}

export async function body(req) {
  try { return await req.json(); } catch { return null; }
}
