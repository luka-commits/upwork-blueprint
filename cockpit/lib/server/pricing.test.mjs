import test from 'node:test';
import assert from 'node:assert/strict';
import { priceView } from '../pricing.mjs';

test('price guide keeps recommendation, range and source math together', () => {
  const result = priceView({
    version: 1, currency: 'USD', contract_type: 'fixed', hourly_rate: 59.76,
    hours: { low: 8, likely: 12, high: 18 }, risk_buffer_percent: 15,
    price_range: { low: 500, high: 1250 }, recommended_total: 825,
    confidence: 'medium', roadmap: [{ label: 'Build', hours: 12, amount: 825 }],
    assumptions: ['One account'],
  });
  assert.equal(result.summary, '$825 recommended');
  assert.equal(result.range, '$500 to $1,250');
  assert.match(result.basis, /12 likely hours at \$59\.76\/hr plus 15%/);
});

test('invalid price guide stays hidden', () => {
  assert.equal(priceView({ version: 1, hourly_rate: 60 }), null);
});
