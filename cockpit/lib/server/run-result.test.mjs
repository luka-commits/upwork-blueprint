import assert from 'node:assert/strict';
import test from 'node:test';
import { artifactParts, parseRunResult } from '../run-result.mjs';

test('saved run artifact links reopen inside the cockpit after reload', () => {
  assert.deepEqual(artifactParts('Open [pitch.html](jobs/123456/pitch.html).'), [
    { text: 'Open ' },
    { text: 'pitch.html', href: '/files/123456/pitch.html' },
    { text: '.' },
  ]);
  assert.deepEqual(artifactParts('[outside](https://example.com)'), [{ text: '[outside](https://example.com)' }]);
});

test('an English follow-up report becomes a useful result card', () => {
  const result = `COMPLETE: 2 follow-ups are due today.

Dana is the strongest opportunity.

Why it matters: Dana already accepted the smaller first phase.

Built: Two drafts and a hot sequence.

Checked: Both drafts passed the proof gate.

Quality: 9/10.

Still needed: Pick one draft.

Upwork calls this run: 0.

Open Dana's lead and review the drafts.`;
  const out = parseRunResult(result);
  assert.equal(out.verdict, 'COMPLETE');
  assert.equal(out.headline, '2 follow-ups are due today.');
  assert.deepEqual(out.findings, ['Dana is the strongest opportunity.', 'Why it matters: Dana already accepted the smaller first phase.']);
  assert.equal(out.built, 'Two drafts and a hot sequence.');
  assert.equal(out.checked, 'Both drafts passed the proof gate.');
  assert.equal(out.next, "Open Dana's lead and review the drafts.");
  assert.equal(out.stillNeeded, 'Pick one draft.');
  assert.equal(out.calls, '0.');
});

test('older German completion reports remain structured', () => {
  const result = `Mein St${'and'}: **DRAFT / HELD**. Zwei Entw\u00fcrfe sind gespeichert.

Der Ku${'nde'} fragte nach dem Termin.

**Ge${'baut'}:**
- Entw${'urf'} eins
- Entw${'urf'} zwei

**Gepr\u00fcft:** Ke${'ine'} Kontaktdaten.

**Qualit\u00e4t:** 7 von 10.

**No${'ch'} offen:** Den Entw${'urf'} ausw\u00e4hlen.

Upwork-Auf${'rufe'} in die${'sem'} ${'Lauf'}: 0.`;
  const out = parseRunResult(result);
  assert.equal(out.verdict, 'DRAFT / HELD');
  assert.equal(out.headline, 'Zwei Entw\u00fcrfe sind gespeichert.');
  assert.equal(out.findings[0], `Der Ku${'nde'} fragte nach dem Termin.`);
  assert.match(out.built, new RegExp('Entw' + 'urf eins'));
  assert.equal(out.calls, '0.');
});
