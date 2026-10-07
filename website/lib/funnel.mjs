// The one number set the cockpit tracks: how many leads ever reached each
// stage, and how many of the step before made it. code/cockpit.py counts them.
// A stage with no earlier stage to measure against shows no rate at all: a zero
// is a measurement, null is the absence of one. A zero count draws no area.
const STEPS = [['applied', 'Applications sent'], ['replied', 'Client replies'], ['call', 'Calls'], ['offer', 'Offers'], ['won', 'Won']];

// A rate needs enough cases behind it. Below MIN_RATE leads reaching the stage
// before, the step shows its count and nothing else: at n = 30 a 20 % rate could
// be anywhere from 10 to 37 %. From MIN_RATE the rate carries its 95 % interval,
// from CLEAN_RATE it stands alone.
export const MIN_RATE = 50;
export const CLEAN_RATE = 100;

/** 95 % Wilson interval for k of n, in whole percent. */
export function wilson(k, n) {
  if (!n) return null;
  const z = 1.96, p = k / n, z2 = z * z;
  const centre = (p + z2 / (2 * n)) / (1 + z2 / n);
  const half = (z * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n);
  return [Math.max(0, Math.round(100 * (centre - half))), Math.min(100, Math.round(100 * (centre + half)))];
}

export function funnelSteps(counts = {}) {
  const value = key => Number((counts || {})[key]) || 0;
  return STEPS.map(([key, label], index) => {
    // Against the nearest earlier stage that actually happened. Not every deal has
    // a call, and an empty stage in the middle must not swallow the rate below it.
    let before = 0;
    let of = null;
    for (let back = index - 1; back >= 0 && !before; back -= 1) {
      before = value(STEPS[back][0]);
      if (before) of = STEPS[back][1];
    }
    // Two readings per stage: what the step before it converted, and what the whole
    // funnel converted. A good reply rate hides a bad close, and the other way round.
    const entry = value(STEPS[0][0]);
    const readable = before >= MIN_RATE;
    return { key, label, count: value(key), of, n: before,
             rate: readable ? Math.round(100 * value(key) / before) : null,
             interval: readable && before < CLEAN_RATE ? wilson(value(key), before) : null,
             overall: index && entry >= MIN_RATE ? Math.round(100 * value(key) / entry) : null };
  });
}

const round = n => Math.round(n * 10) / 10;

/** Equal-height bands: width and area follow the count, including zero. */
export function funnelShapes(steps, { width = 600, height = 84, gap = 2 } = {}) {
  const max = Math.max(1, ...steps.map(step => step.count));
  const widthOf = count => width * Math.max(0, count) / max;
  return steps.map((step, index) => {
    const top = widthOf(step.count);
    const bottom = top;
    const y = index * (height + gap);
    const corners = [[(width - top) / 2, y], [(width + top) / 2, y], [(width + bottom) / 2, y + height], [(width - bottom) / 2, y + height]];
    return { ...step, y, points: corners.map(([x, cy]) => `${round(x)},${round(cy)}`).join(' ') };
  });
}
