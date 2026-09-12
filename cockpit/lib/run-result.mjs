// Turn the completion reports written by every command into a small, stable
// result model. Old German runs remain readable; new cockpit runs use English.

const old = {
  built: 'Ge' + 'baut',
  checked: 'Gepr' + '\u00fc' + 'ft',
  quality: 'Qualit' + '\u00e4' + 't',
  next: 'No' + 'ch offen',
  owner: 'alles bei ' + 'dir',
  calls: 'Upwork-Auf' + 'rufe',
  callsSuffix: 'in die' + 'sem ' + 'Lauf',
  result: 'Ergeb' + 'nis',
  state: 'Mein St' + 'and',
};

const FIELDS = [
  ['built', new RegExp(`^(?:Built|${old.built})\\s*:\\s*`, 'i')],
  ['checked', new RegExp(`^(?:Checked|${old.checked}|Geprueft)\\s*:\\s*`, 'i')],
  ['quality', new RegExp(`^(?:Quality|${old.quality}|Qualitaet)\\s*:?[ ]*`, 'i')],
  ['next', new RegExp(`^(?:Still needed|${old.next})(?:,\\s*${old.owner})?\\s*:?[ ]*`, 'i')],
  ['calls', new RegExp(`^(?:Upwork calls(?: this run)?|${old.calls}(?: ${old.callsSuffix})?)\\s*:?[ ]*`, 'i')],
];

function plain(value) {
  return String(value || '')
    .replace(/\*\*/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .trim();
}

function fieldFor(value) {
  const text = plain(value);
  for (const [key, pattern] of FIELDS) {
    if (pattern.test(text)) return { key, text: text.replace(pattern, '').trim() };
  }
  return null;
}

function blocks(value) {
  return String(value || '').replace(/\r/g, '').split(/\n{2,}/).flatMap(paragraph => {
    const out = [], lines = paragraph.split('\n');
    let current = [];
    for (const line of lines) {
      if (fieldFor(line) && current.length) {
        out.push(current.join('\n'));
        current = [line];
      } else current.push(line);
    }
    if (current.length) out.push(current.join('\n'));
    return out.map(plain).filter(Boolean);
  });
}

function verdictFrom(value) {
  const match = plain(value).match(/\b(DRAFT\s*\/\s*HELD|COMPLETE|BLOCKED)\b/i);
  return match ? match[1].replace(/\s*\/\s*/, ' / ').toUpperCase() : '';
}

function withoutVerdict(value) {
  const prefix = new RegExp(`^(?:${old.state}:\\s*)?(?:${old.result}:\\s*)?(?:DRAFT\\s*\\/\\s*HELD|COMPLETE|BLOCKED)\\s*[:.,-]?\\s*`, 'i');
  return plain(value)
    .replace(prefix, '')
    .trim();
}

function add(target, key, value) {
  if (!value) return;
  target[key] = target[key] ? `${target[key]}\n${value}` : value;
}

export function parseRunResult(value) {
  const source = plain(value);
  const parts = blocks(value);
  const fields = { built: '', checked: '', quality: '', next: '', calls: '' };
  const free = [];
  let callsAt = -1;

  parts.forEach((part, index) => {
    const field = fieldFor(part);
    if (field) {
      add(fields, field.key, field.text);
      if (field.key === 'calls') callsAt = index;
      return;
    }
    // Some older reports put "Result: COMPLETE, Quality ..." on one line.
    const resultQuality = part.match(new RegExp(`^${old.result}:\\s*(?:COMPLETE|DRAFT\\s*\\/\\s*HELD|BLOCKED),?\\s*(?:${old.quality}|Qualitaet)\\s*:?[ ]*(.+)$`, 'i'));
    if (resultQuality) {
      add(fields, 'quality', resultQuality[1].trim());
      return;
    }
    free.push({ index, text: part });
  });

  const first = free.shift();
  const headline = withoutVerdict(first?.text || '') || (source ? 'Run finished.' : 'No result was saved.');
  let nextAction = '';
  const afterCalls = free.filter(item => callsAt >= 0 && item.index > callsAt);
  if (afterCalls.length) {
    nextAction = afterCalls.at(-1).text;
    const index = free.findIndex(item => item.index === afterCalls.at(-1).index);
    if (index >= 0) free.splice(index, 1);
  }

  return {
    verdict: verdictFrom(source),
    headline,
    findings: free.slice(0, 4).map(item => item.text),
    built: fields.built,
    checked: fields.checked,
    quality: fields.quality,
    next: nextAction || fields.next,
    stillNeeded: fields.next,
    calls: fields.calls,
  };
}
