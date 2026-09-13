export function priceView(value) {
  if (!value || value.version !== 1) return null;
  const rate = Number(value.hourly_rate);
  const likely = Number(value.hours?.likely);
  const lowHours = Number(value.hours?.low);
  const highHours = Number(value.hours?.high);
  const recommended = Number(value.recommended_total);
  const lowPrice = Number(value.price_range?.low);
  const highPrice = Number(value.price_range?.high);
  if (![rate, likely, lowHours, highHours, recommended, lowPrice, highPrice].every(Number.isFinite)) return null;
  const currency = value.currency || 'USD';
  const money = amount => amount.toLocaleString('en-US', {
    style: 'currency', currency, maximumFractionDigits: amount % 1 ? 2 : 0,
  });
  const hours = amount => Number.isInteger(amount) ? String(amount) : amount.toFixed(1);
  return {
    summary: value.contract_type === 'hourly'
      ? `${money(rate)}/hr, about ${money(recommended)}`
      : `${money(recommended)} recommended`,
    recommended: money(recommended),
    range: `${money(lowPrice)} to ${money(highPrice)}`,
    basis: `${hours(likely)} likely hours at ${money(rate)}/hr plus ${Number(value.risk_buffer_percent) || 0}% scope risk`,
    hours: `${hours(lowHours)} to ${hours(highHours)} hours`,
    confidence: String(value.confidence || 'unknown'),
    roadmap: Array.isArray(value.roadmap) ? value.roadmap : [],
    assumptions: Array.isArray(value.assumptions) ? value.assumptions : [],
  };
}
