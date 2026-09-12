import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../../app/globals.css', import.meta.url), 'utf8');
const colors = Object.fromEntries([...css.matchAll(/--([\w-]+):\s*(#[\da-f]{6});/gi)].map(m => [m[1], m[2]]));
function luminance(hex) {
  const [r, g, b] = hex.slice(1).match(/../g).map(v => parseInt(v, 16) / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return r * .2126 + g * .7152 + b * .0722;
}
function contrast(a, b) {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + .05) / (values[1] + .05);
}

test('desktop text and semantic labels remain readable on their light surfaces', () => {
  for (const ink of ['text', 'text-2', 'text-3', 'brand']) {
    for (const surface of ['bg', 'card', 'surface2']) {
      assert.ok(contrast(colors[ink], colors[surface]) >= 4.5, `${ink} on ${surface}`);
    }
    // Conservative blue-edge sample of the static ambient canvas.
    assert.ok(contrast(colors[ink], '#d3e3f8') >= 4.5, `${ink} on the ambient canvas`);
  }
  for (const [ink, surface] of [['red-deep', 'red-soft'], ['amber-deep', 'amber-soft'], ['ok', 'ok-soft']]) {
    assert.ok(contrast(colors[ink], colors[surface]) >= 4.5, `${ink} on ${surface}`);
  }
  for (const stop of ['#086cdd', '#0056c7', '#0062cd', '#004cae']) {
    assert.ok(contrast('#ffffff', stop) >= 4.5, `white on primary gradient ${stop}`);
  }
});

test('glass stays on the control layer with bounded blur and accessible fallbacks', () => {
  const blur = [...css.matchAll(/backdrop-filter:\s*blur\((\d+)px\)/g)];
  assert.ok(blur.length > 0);
  assert.ok(blur.every(m => Number(m[1]) < 20));
  assert.match(css, /prefers-reduced-transparency: reduce/);
  assert.match(css, /prefers-contrast: more/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /html\[data-input="keyboard"\]/);
  assert.doesNotMatch(css, /transition:\s*all\b/);
});

test('the native desktop typography requires no remote font request', () => {
  const layout = readFileSync(new URL('../../app/layout.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(layout, /fonts\.(googleapis|gstatic)\.com/);
  assert.match(css, /font-family: -apple-system/);
  assert.match(css, /--mono: ui-monospace/);
});
