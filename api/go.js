const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

function isBot(agent) {
  return /bot|crawler|spider|facebookexternalhit|whatsapp|telegram|skypeuripreview|discord|slackbot|linkedinbot|googlebot|bingbot|preview|curl|python-requests/i.test(agent || '');
}

async function handler(req, res) {
  if (req.method && !['GET', 'HEAD'].includes(req.method)) return res.status(405).end('Use GET or HEAD.');
  const { job, slug } = req.query || {};
  if (typeof job !== 'string' || typeof slug !== 'string' ||
      !/^\d{6,25}$/.test(job) || !/^[a-z0-9-]{1,80}$/.test(slug)) {
    return res.status(404).end('Link not found.');
  }
  let link;
  try {
    const registry = JSON.parse(fs.readFileSync(
      process.env.TRACKING_LINKS_PATH || path.join(process.cwd(), 'api', '_tracking-links.json'), 'utf8'));
    link = registry[job]?.[slug];
    if (!link || new URL(link.target).protocol !== 'https:') throw new Error('missing link');
  } catch {
    return res.status(404).end('Link not found.');
  }
  const check = req.method === 'HEAD' || req.query.check === '1';
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  if (check) {
    res.setHeader('X-Tracking-Status', 'check: not logged');
  } else if (!token) {
    console.warn('Click tracking skipped: BLOB_READ_WRITE_TOKEN is missing.');
    res.setHeader('X-Tracking-Status', 'skipped: BLOB_READ_WRITE_TOKEN missing');
  } else {
    const now = Date.now();
    const event = { job, slug, at: new Date(now).toISOString(),
      bot: isBot(req.headers?.['user-agent']) };
    try {
      // Wire contract: vercel/storage packages/blob/src/{api,put,put-helpers}.ts.
      const pathname = `clicks/${job}/${randomUUID()}.json`;
      const response = await fetch(`https://vercel.com/api/blob/?pathname=${encodeURIComponent(pathname)}`, {
        method: 'PUT', body: JSON.stringify(event), signal: AbortSignal.timeout(5000),
        headers: { authorization: `Bearer ${token}`, 'x-api-version': '12',
          'x-vercel-blob-store-id': token.split('_')[3] || '',
          'x-vercel-blob-access': 'private', 'x-content-type': 'application/json',
          'x-add-random-suffix': '0', 'x-allow-overwrite': '0' },
      });
      if (!response.ok) throw new Error('Blob write failed');
      res.setHeader('X-Tracking-Status', 'recorded');
    } catch {
      console.warn('Click tracking skipped: Blob write failed.');
      res.setHeader('X-Tracking-Status', 'skipped: Blob write failed');
    }
  }
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Location', link.target);
  res.status(302).end();
}

module.exports = handler;
module.exports.isBot = isBot;
