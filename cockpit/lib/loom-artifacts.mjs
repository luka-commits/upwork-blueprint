const clean = value => String(value || '').trim();

export function parseLoomScript(markdown) {
  const lines = String(markdown || '').split(/\r?\n/);
  const body = lines.filter((line, index) => {
    if (index === 0 && /^#\s/.test(line)) return false;
    if (/^(Prepared|Reviewed|Updated|Recorded)\b/.test(line.trim())) return false;
    if (/^\*\*Next:\*\*/.test(line.trim())) return false;
    return true;
  });
  const intro = [];
  const beats = [];
  let current = null;
  for (const line of body) {
    const match = line.trim().match(/^\*\*(Beat\s+\d+\s*[·:|-]\s*.+?)\*\*$/i);
    if (match) {
      const title = match[1].replace(/^Beat\s+\d+\s*[·:|-]\s*/i, '').trim();
      const durationMatch = title.match(/(?:,|·)\s*([^,·]*(?:second|minute)s?)$/i);
      current = {
        title: clean(durationMatch ? title.slice(0, durationMatch.index) : title),
        duration: clean(durationMatch?.[1]),
        lines: [],
      };
      beats.push(current);
    } else if (current) current.lines.push(line);
    else intro.push(line);
  }
  return {
    intro: clean(intro.join('\n')),
    beats: beats.map(beat => ({ title: beat.title, duration: beat.duration, body: clean(beat.lines.join('\n')) })),
  };
}

export function parseLoomReview(markdown) {
  const sections = [];
  let current = null;
  for (const line of String(markdown || '').split(/\r?\n/)) {
    const heading = line.match(/^##\s+(.+?)\s*$/);
    if (heading) {
      current = { label: heading[1].trim(), lines: [] };
      sections.push(current);
    } else if (current) current.lines.push(line);
  }
  const values = sections.map(section => ({ label: section.label, body: clean(section.lines.join('\n')) }));
  const scoreText = values.find(section => section.label.toLowerCase() === 'score')?.body || '';
  const scoreMatch = scoreText.match(/\b(100|[1-9]?\d)\s*\/\s*100\b/);
  return {
    score: scoreMatch ? Number(scoreMatch[1]) : null,
    sections: values.filter(section => section.label.toLowerCase() !== 'score' && section.body),
  };
}
