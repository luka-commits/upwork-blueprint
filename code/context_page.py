#!/usr/bin/env python3
"""The member's one-page Upwork resume, built from their own file.

    python3 code/context_page.py [--open]

/about-me ends by reporting what it wrote. A report in a terminal scrolls away,
and the file it wrote is markdown with starter lines still in it. This renders
`context/me.md` as a resume: name and headline on top, experience and selected
results in the main column, services, tools, credentials and recommendations
beside it. Only what a client would care about is on the sheet: internal limits
such as the smallest project or applications a day stay in the file, and what is
still open sits in a note under it.

An entry carries a label only when it was pulled from somewhere else (a file, an
email, the web) and the member has not confirmed it yet. What they said
themselves is simply theirs.

Output is `context/overview.html`, which is gitignored like everything else in
that folder. It is built from the files alone and reaches no service. The look
comes from `website/app/tokens.css`, the tokens every dashboard here shares. The
sheet prints as a clean A4 resume, without the note under it.
"""
import argparse
import html
import pathlib
import re
import sys
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import context_check as cc  # noqa: E402

OUT = ROOT / 'context' / 'overview.html'
TOKENS = ROOT / 'website' / 'app' / 'tokens.css'
STARTER = 'not answered yet'
EMPTY = ('nothing recorded yet', 'not filled in yet', STARTER)
CLIP = 260       # characters of a long answer before it is cut at a word
JOBS = 5         # experience entries shown, the rest become "and N more"
RESULTS = 6      # results shown on the sheet
CREDENTIALS = 6  # credentials shown beside them
# How /about-me writes the source of something the member said themselves. It needs no label.
OWN_WORDS = ('your answer', 'your own', 'you said', 'you told')
INTERNAL = ('Applications per day', 'Smallest project', 'What you do NOT', 'Hourly rate',
            'Maximum proposals', 'Lowest share', 'Industries', 'Proof to build')

# A resume on the house tokens: a parchment page, one ivory sheet, a serif for the
# name and headings, a small mono for section labels, terracotta for the rules.
CSS = """
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0; background: var(--canvas); color: var(--ink); font: 15px/1.55 var(--sans);
         -webkit-font-smoothing: antialiased; }
  .sheet, .note, .foot { max-width: 920px; margin: 0 auto; }
  .sheet { margin-top: 40px; background: var(--ivory); border: 1px solid var(--hairline-soft);
           border-radius: var(--radius-floating); box-shadow: var(--shadow-whisper); padding: 52px 56px 40px; }
  .kicker, h2, .meta, .when, .tag { font-family: var(--mono); text-transform: uppercase; font-weight: 400; }
  .kicker { font-size: 11px; letter-spacing: 2px; color: var(--terracotta-text); margin: 0 0 12px; }
  h1 { font: 500 clamp(34px, 5vw, 48px)/1.05 var(--display); letter-spacing: -1.2px; margin: 0 0 10px; }
  .headline { font-size: 18px; line-height: 1.4; color: var(--body); margin: 0; max-width: 36em; }
  .meta { display: flex; flex-wrap: wrap; gap: 6px 22px; margin: 18px 0 0; padding: 14px 0 0;
          border-top: 1px solid var(--hairline-soft); font-size: 11px; letter-spacing: 1.2px; color: var(--label); }
  .meta b { color: var(--ink); font-weight: 500; }
  .summary { font: 400 19px/1.45 var(--display); margin: 26px 0 0; padding-left: 18px;
             border-left: 2px solid var(--terracotta); }
  .cols { display: grid; grid-template-columns: 1.75fr 1fr; gap: 0 48px; margin-top: 8px; }
  section { padding: 26px 0 0; }
  h2 { margin: 0 0 14px; font-size: 11px; letter-spacing: 2px; color: var(--label);
       display: flex; align-items: center; gap: 10px; }
  h2::before { content: ""; width: 18px; height: 2px; background: var(--terracotta); }
  .job { margin: 0 0 18px; }
  .job-top { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
  .job strong, .item strong { font: 500 17.5px/1.3 var(--display); }
  .when { font-size: 10.5px; letter-spacing: 1px; color: var(--label); white-space: nowrap; }
  .org { margin: 1px 0 4px; font-size: 14px; font-weight: 600; color: var(--body); }
  p { margin: 0; }
  .job p, .item p, .side p, li { font-size: 14.5px; color: var(--body); }
  .item { position: relative; margin: 0 0 14px; padding-left: 18px; }
  .item::before { content: ""; position: absolute; left: 0; top: 9px; width: 6px; height: 6px;
                  border-radius: 50%; background: var(--terracotta); }
  .item strong { display: block; font-size: 16px; margin-bottom: 2px; }
  .side .item { padding-left: 0; } .side .item::before { display: none; }
  .side .item strong { font: 600 14.5px/1.35 var(--sans); }
  small { display: block; margin-top: 3px; font-size: 12.5px; color: var(--label); }
  .tag { display: inline-block; font-size: 9.5px; letter-spacing: 1.2px; padding: 3px 7px; border-radius: 6px;
         margin-right: 8px; vertical-align: 2px; background: var(--warn-bg); color: var(--warn);
         border: 1px solid var(--warn-ring); }
  ul { margin: 0; padding-left: 18px; } li { margin-bottom: 4px; }
  ul.plain { list-style: none; padding: 0; } ul.plain li { margin-bottom: 9px; }
  ul.plain b { display: block; color: var(--ink); font-weight: 600; }
  blockquote { margin: 0 0 12px; font: 400 16px/1.45 var(--display); }
  blockquote small { font: 400 12.5px/1.4 var(--sans); }
  .muted { color: var(--label); font-size: 14px; }
  .note { margin-top: 18px; background: var(--terracotta-soft); border-radius: var(--radius-panel); padding: 18px 22px; }
  .note h2 { color: var(--terracotta-text); margin-bottom: 8px; }
  .note li { color: var(--ink); }
  .foot { padding: 18px 4px 48px; font-size: 13.5px; color: var(--label); }
  .foot code { font-family: var(--mono); background: var(--sand); padding: 1px 6px; border-radius: 5px; color: var(--ink); }
  @media (max-width: 800px) { .cols { grid-template-columns: 1fr; } .sheet { margin: 0; border-radius: 0; padding: 32px 22px; }
                              .note { margin: 14px 14px 0; } .foot { padding: 16px 18px 40px; }
                              .job-top { flex-direction: column; gap: 2px; } }
  @media print { @page { size: A4; margin: 11mm; } body { background: none; font-size: 9.6px; line-height: 1.42; }
                 .sheet { margin: 0; max-width: none; border: 0; border-radius: 0; box-shadow: none; padding: 0; background: none; }
                 .note, .foot { display: none; } h1 { font-size: 27px; margin-bottom: 5px; } .headline { font-size: 12px; }
                 .meta { margin-top: 9px; padding-top: 7px; font-size: 7.5px; } .summary { font-size: 12px; margin-top: 12px; }
                 .cols { gap: 0 24px; margin-top: 0; } section { padding-top: 13px; break-inside: avoid; }
                 h2 { font-size: 7.5px; margin-bottom: 7px; } .job { margin-bottom: 9px; } .item { margin-bottom: 7px; }
                 .job strong { font-size: 12px; } .item strong { font-size: 11px; } .side .item strong { font-size: 9.6px; }
                 .job p, .item p, .side p, li, .org { font-size: 9.4px; } small { font-size: 8px; }
                 blockquote { font-size: 10.5px; } .when { font-size: 7px; } .tag { font-size: 6.5px; padding: 2px 4px; } }
"""


def esc(text):
    return html.escape(str(text), quote=False)


def sections(text):
    """Each `## heading` with the lines under it, in file order."""
    found, name, body = [], None, []
    for line in text.splitlines():
        if line.startswith('## '):
            if name:
                found.append((name, body))
            name, body = line[3:].strip(), []
        elif name is not None:
            body.append(line)
    if name:
        found.append((name, body))
    return found


def answers(me):
    """Every `**Label:** value` in the file as {label: value, or None when unanswered}."""
    found = {}
    for _, body in me.items():
        for line in body:
            match = re.match(r'^\*\*(.+?):\*\*\s*(.*)$', line.strip())
            if match:
                value = match.group(2).strip()
                found[match.group(1).strip()] = None if (not value or STARTER in value.lower()) else value
    return found


def pick(found, start):
    """The answer whose label begins with `start`; None when open or absent."""
    for label, value in found.items():
        if label.lower().startswith(start.lower()):
            return value
    return None


def clip(text, limit=CLIP):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0].rstrip(',;:') + '…'


def short(label):
    """A label without its parenthesis: 'How settled ... (decided, leaning, open)' reads as a gap."""
    return re.sub(r'\s*\(.*?\)', '', label).strip()


def blank(text):
    return not text.strip() or any(mark in text.lower() for mark in EMPTY)


def entries(body):
    """Each `###` block as {title, text, source, pending}. Empty starter blocks are dropped.

    `pending` is true only for something pulled from elsewhere and not confirmed yet:
    an entry the member stated themselves is never marked, whatever an older file says.
    """
    found, title, lines = [], None, []
    for line in body + ['### ']:
        if line.startswith('### '):
            if title:
                text = [x.strip() for x in lines if x.strip()
                        and not x.strip().startswith(('- ', 'Transfers:')) and not re.match(r'^\*\*.+?:\*\*', x.strip())]
                bullets = {m.group(1).lower(): m.group(2).strip() for x in lines
                           for m in [re.match(r'^-\s*([^:]+):\s*(.*)$', x.strip())] if m}
                joined = ' '.join(text)
                source = bullets.get('source', '')
                if joined and not blank(joined):
                    found.append({'title': title, 'text': joined, 'source': source,
                                  'pending': ('pending' in bullets.get('status', '').lower()
                                              and not source.lower().startswith(OWN_WORDS))})
            title, lines = line[4:].strip(), []
        elif title is not None:
            lines.append(line)
    return found


def role_of(title):
    """'Role, Employer (March 2022 to now)' as (role, employer, when); missing parts come back empty."""
    match = re.match(r'^(.*?)\s*\(([^()]*\d{4}[^()]*)\)\s*$', title)
    name, when = (match.group(1), match.group(2)) if match else (title, '')
    role, _, employer = name.rpartition(', ')
    return (role, employer, when) if role else (name, '', when)


def tag_html(item):
    """The one label on the sheet: something pulled from elsewhere that nobody has confirmed yet."""
    return '<span class="tag">to confirm</span>' if item['pending'] else ''


def trail_html(item):
    """Where an unconfirmed entry came from. A confirmed one needs no footnote on a resume."""
    if not (item['pending'] and item['source']):
        return ''
    return f'<small>Pulled from {esc(clip(item["source"], 120))}</small>'


def job_html(item):
    role, employer, when = role_of(item['title'])
    org = f'<p class="org">{esc(employer)}</p>' if employer else ''
    stamp = f'<span class="when">{esc(when)}</span>' if when else ''
    return (f'<div class="job"><div class="job-top"><strong>{esc(role)}</strong>{stamp}</div>'
            f'{org}<p>{esc(clip(item["text"], 340))}</p></div>')


def item_html(item, limit=CLIP):
    return (f'<div class="item"><strong>{tag_html(item)}{esc(item["title"])}</strong>'
            f'<p>{esc(clip(item["text"], limit))}</p>{trail_html(item)}</div>')


def block(title, inner):
    return f'<section><h2>{esc(title)}</h2>{inner}</section>' if inner else ''


def more(count, shown):
    return f'<p class="muted">and {count - shown} more in your file</p>' if count > shown else ''


def header_html(found):
    """Name, headline and the line of facts a client reads first."""
    name, _, place = (pick(found, 'Name and location') or '').partition(',')
    headline = pick(found, 'The one thing') or pick(found, 'Profession')
    facts = (('Based in', place.strip()), ('Rate', pick(found, 'Hourly rate')),
             ('Job Success', pick(found, 'Job Success')), ('Hours', pick(found, 'Timezone')))
    meta = ''.join(f'<span>{esc(label)} <b>{esc(clip(short(value), 70))}</b></span>' for label, value in facts
                   if value and not value.lower().startswith(('no ', 'none')))
    strength = (pick(found, 'What you are good at') or '').strip('"“” ')
    return ('<p class="kicker">Upwork resume</p>'
            f'<h1>{esc(name.strip() or "Your Upwork resume")}</h1>'
            + (f'<p class="headline">{esc(clip(headline))}</p>' if headline else
               '<p class="headline">What every command reads before it writes for you.</p>')
            + (f'<div class="meta">{meta}</div>' if meta else '')
            + (f'<p class="summary">{esc(clip(strength, 320))}</p>' if strength else ''))


def services_html(me, found):
    """The branches with their services when the file lists them, else the one-line answer."""
    rows = [m.groups() for line in me.get('What you do', [])
            for m in [re.match(r'^-\s*([^:]+):\s*(.+)$', line.strip())] if m]
    if rows:
        return '<ul class="plain">' + ''.join(
            f'<li><b>{esc(name)}</b>{esc(clip(items))}</li>' for name, items in rows) + '</ul>'
    sells = pick(found, 'Services you sell')
    return f'<p>{esc(clip(sells))}</p>' if sells else ''


def open_html(found, unconfirmed):
    """What the sheet is still missing: unanswered lines, then anything waiting for a yes."""
    gaps = [short(label) for label, value in found.items() if value is None and not label.startswith(INTERNAL)]
    lines = [f'<li>{esc(gap)}</li>' for gap in gaps[:8]]
    if len(gaps) > 8:
        lines.append(f'<li>and {len(gaps) - 8} more</li>')
    if unconfirmed:
        lines.append(f'<li>{unconfirmed} {"entry" if unconfirmed == 1 else "entries"} pulled from your files, '
                     'marked "to confirm" until you say they are right</li>')
    return f'<div class="note"><h2>Not on your resume yet</h2><ul>{"".join(lines)}</ul></div>' if lines else ''


def build(me_text, proof_text):
    me = dict(sections(me_text))
    found = answers(me)
    proof = dict(sections(proof_text))
    jobs = entries(me.get('Your background', []))
    results, creds, reviews = (entries(proof.get(name, [])) for name in ('Results', 'Credentials', 'Reviews'))

    experience = ''.join(job_html(j) for j in jobs[:JOBS]) + more(len(jobs), JOBS) or \
        '<p class="muted">Still open. /about-me fills this from your CV and your answers.</p>'
    selected = ''.join(item_html(r) for r in results[:RESULTS]) + more(len(results), RESULTS) or \
        '<p class="muted">Nothing yet. The first delivered job fills this.</p>'
    tools = pick(found, 'Tools and systems')
    schooling = pick(found, 'Education')
    quotes = ''.join(f'<blockquote>{esc(clip(r["text"], 220))}<small>{esc(r["title"])}</small></blockquote>'
                     for r in reviews)
    unconfirmed = sum(1 for item in results + creds + reviews if item['pending'])
    title = (pick(found, 'Name and location') or 'Your Upwork resume').partition(',')[0]

    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)} · Upwork resume</title>\n<style>' + tokens() + CSS + '</style>\n</head>\n<body>\n'
            '<main class="sheet">\n<header>' + header_html(found) + '</header>\n'
            '<div class="cols">\n<div>\n'
            + block('Experience', experience) + block('Selected results', selected) +
            '\n</div>\n<div class="side">\n'
            + block('Services', services_html(me, found))
            + block('Tools', f'<p>{esc(clip(tools, 320))}</p>' if tools else '')
            + block('Credentials', ''.join(item_html(c, 150) for c in creds[:CREDENTIALS]) + more(len(creds), CREDENTIALS))
            + block('Education and languages', f'<p>{esc(clip(schooling, 320))}</p>' if schooling else '')
            + block('Recommendations', quotes) +
            '\n</div>\n</div>\n</main>\n'
            + open_html(found, unconfirmed) +
            '\n<p class="foot">Next: <code>/profile</code> writes your Upwork profile from this. '
            'Built from context/me.md on this machine; rebuild it with '
            '<code>python3 code/context_page.py --open</code>.</p>\n'
            '</body>\n</html>\n')


def tokens():
    """The shared tokens, inlined so the page opens from disk with no other file."""
    if not TOKENS.is_file():
        raise SystemExit(f'{TOKENS.relative_to(ROOT)} is missing: the page takes its look from it.')
    return TOKENS.read_text(encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--open', action='store_true', help='open it in the browser')
    args = parser.parse_args(argv)
    if not cc.ME.is_file():
        print(f'{cc.ME} is missing. Run python3 code/workspace.py')
        return 1
    me_text = cc.ME.read_text(encoding='utf-8')
    proof_text = cc.proof_only(me_text)
    open_points = len(cc.check_me(me_text) + cc.check_proof(proof_text))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(me_text, proof_text), encoding='utf-8')
    print(f'{OUT.relative_to(ROOT)} written, {open_points} open')
    if args.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
