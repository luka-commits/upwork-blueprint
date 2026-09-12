// Read the member's saved review without turning its prose into new decisions.
const SECTION_NAMES = { 'do today': 'Do today', 'coming up': 'Coming up', parked: 'Parked' };

export function followUpLeadHref(value) {
  const match = String(value || '').trim().match(/^(?:https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d{1,5})?)?\/job\/([0-9]{6,25})\/?$/);
  return match ? `/job/${match[1]}` : null;
}

export function followUpInline(value) {
  return String(value || '').split(/(\[[^\]\n]+\]\([^\)\n]+\)|\*\*[^*\n]+\*\*|`[^`\n]+`)/g).filter(Boolean).map(text => {
    const link = text.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) return { kind: 'link', text: link[1], href: followUpLeadHref(link[2]) };
    if (text.startsWith('**') && text.endsWith('**')) return { kind: 'strong', text: text.slice(2, -2) };
    if (text.startsWith('`') && text.endsWith('`')) return { kind: 'text', text: text.slice(1, -1) };
    return { kind: 'text', text };
  });
}

function blocks(lines) {
  const result = [];
  let paragraph = [];
  const flush = () => {
    if (paragraph.length) result.push({ kind: 'paragraph', text: paragraph.join(' ') });
    paragraph = [];
  };
  for (const line of lines) {
    const text = line.trim();
    if (!text) { flush(); continue; }
    const heading = text.match(/^#{1,6}\s+(.+?)\s*#*$/);
    const item = text.match(/^(?:[-*+]\s+|\d+[.)]\s+)(.+)$/);
    if (heading) { flush(); result.push({ kind: 'heading', text: heading[1] }); }
    else if (item) {
      flush();
      if (result.at(-1)?.kind === 'list') result.at(-1).items.push(item[1]);
      else result.push({ kind: 'list', items: [item[1]] });
    } else if (/^\s{2,}/.test(line) && result.at(-1)?.kind === 'list' && !paragraph.length) {
      const items = result.at(-1).items;
      items[items.length - 1] += ` ${text}`;
    } else paragraph.push(text);
  }
  flush();
  return result;
}

export function parseFollowUpReport(value) {
  const sections = [], intro = [];
  let current = intro;
  for (const line of String(value || '').replace(/\r/g, '').split('\n')) {
    const heading = line.trim().replace(/^#{1,3}\s+/, '').replace(/^\*\*|\*\*$/g, '')
      .match(/^(do today|coming up|parked)\s*(?:[:(·-].*)?$/i);
    if (heading) {
      const key = heading[1].toLowerCase();
      let section = sections.find(item => item.key === key);
      if (!section) { section = { key, title: SECTION_NAMES[key], lines: [] }; sections.push(section); }
      current = section.lines;
    } else current.push(line);
  }
  // Never label unstructured prose as a zero-item or completed review.
  return { intro: blocks(intro), sections: sections.map(({ key, title, lines }) => ({ key, title, blocks: blocks(lines) })) };
}

export function followUpReviewAge(modifiedAt, now = new Date()) {
  const saved = new Date(modifiedAt || '');
  if (!Number.isFinite(saved.getTime()) || !Number.isFinite(now.getTime()) || saved > now) return 'unknown';
  const day = date => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  return day(saved) === day(now) ? 'today' : 'older';
}
