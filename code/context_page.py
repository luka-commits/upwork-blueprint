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
sheet prints as a clean one-page A4 resume, without the note under it.
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
FULL_OUT = ROOT / 'context' / 'overview-full.html'
TOKENS = ROOT / 'website' / 'app' / 'tokens.css'
STARTER = 'not answered yet'
EMPTY = ('nothing recorded yet', 'not filled in yet', STARTER)
CLIP = 260       # characters of a long answer before it is cut at a word
# What fits one A4 page. The numbers were measured on a file with twelve jobs, fourteen
# results, ten certificates and six reviews: the sheet keeps the strongest of each kind,
# and everything the file holds goes to the full version beside it.
FIT = {'jobs': 4, 'earlier': 4, 'results': 4, 'creds': 4, 'quotes': 2, 'chips': 12, 'services': 4, 'lines': 3,
       'profile': 230, 'job': 160, 'transfer': 80, 'result': 120, 'quote': 120, 'item': 70}
FULL = {'jobs': 99, 'earlier': 0, 'results': 99, 'creds': 99, 'quotes': 99, 'chips': 40, 'services': 99, 'lines': 99,
        'profile': 600, 'job': 520, 'transfer': 300, 'result': 400, 'quote': 400, 'item': 300}
LIM = dict(FIT)
# How /about-me writes the source of something the member said themselves. It needs no label.
OWN_WORDS = ('your answer', 'your own', 'you said', 'you told')
INTERNAL = ('Applications per day', 'Smallest project', 'What you do NOT', 'Hourly rate',
            'Maximum proposals', 'Lowest share', 'Industries', 'Proof to build', 'Branches you picked')

# A resume on the house tokens: a parchment page, one ivory sheet, a serif for the
# name and headings, a small mono for section labels, terracotta for the rules.
CSS = """
  * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0; background: var(--canvas); color: var(--ink); font: 15px/1.55 var(--sans);
         -webkit-font-smoothing: antialiased; }
  .sheet, .note, .foot { max-width: 940px; margin: 0 auto; }
  .sheet { margin-top: 40px; background: var(--paper); border: 1px solid var(--hairline-soft);
           border-radius: var(--radius-floating); box-shadow: var(--shadow-whisper); overflow: hidden; }
  .top { background: var(--dark); color: var(--on-dark); padding: 44px 56px 34px; }
  .kicker, h2, .meta, .when, .tag, .fig { font-family: var(--mono); text-transform: uppercase; font-weight: 400; }
  .kicker { font-size: 10.5px; letter-spacing: 2.4px; color: var(--coral); margin: 0 0 14px; }
  h1 { font: 500 clamp(34px, 5vw, 46px)/1.04 var(--display); letter-spacing: -1.1px; margin: 0 0 8px; color: var(--on-dark); }
  .headline { font-size: 17px; line-height: 1.4; color: var(--on-dark-soft); margin: 0; max-width: 38em; }
  .meta { display: flex; flex-wrap: wrap; gap: 6px 26px; margin: 22px 0 0; padding: 14px 0 0;
          border-top: 1px solid rgba(250, 249, 245, .16); font-size: 10.5px; letter-spacing: 1.3px; color: var(--on-dark-soft); }
  .meta b { color: var(--on-dark); font-weight: 400; }
  .meta a { color: var(--on-dark); text-decoration: none; border-bottom: 1px solid rgba(250, 249, 245, .35); }
  .cols { display: grid; grid-template-columns: 1.85fr 1fr; padding: 6px 56px 44px; gap: 0 44px; }
  .side { border-left: 1px solid var(--hairline-soft); padding-left: 36px; }
  section { padding: 26px 0 0; }
  h2 { margin: 0 0 14px; font-size: 10.5px; letter-spacing: 2.2px; color: var(--ink);
       display: flex; align-items: center; gap: 10px; }
  h2::after { content: ""; flex: 1; height: 1px; background: var(--hairline-soft); }
  p { margin: 0; }
  .profile { font: 400 17px/1.5 var(--display); color: var(--ink); }
  .job { margin: 0 0 20px; }
  .job-top { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
  .job strong { font: 600 16px/1.3 var(--sans); color: var(--ink); }
  .when { font-size: 10px; letter-spacing: 1.1px; color: var(--label); white-space: nowrap; }
  .org { margin: 1px 0 6px; font: italic 400 15px/1.3 var(--display); color: var(--terracotta-text); }
  .job p, .item p, .result p, .side p, li { font-size: 14px; color: var(--body); }
  .transfer { margin-top: 5px; } .transfer b { color: var(--ink); font-weight: 600; }
  .result { display: grid; grid-template-columns: 96px 1fr; gap: 16px; align-items: start; margin: 0 0 16px; }
  .fig { font-size: 15px; letter-spacing: .2px; line-height: 1.25; color: var(--terracotta-text); padding: 9px 8px;
         background: var(--terracotta-soft); border-radius: var(--radius-control); text-align: center; text-transform: none; }
  .fig.dot { background: none; }
  .result strong, .item strong { display: block; font: 600 14.5px/1.35 var(--sans); color: var(--ink); margin-bottom: 2px; }
  .item { margin: 0 0 14px; }
  small { display: block; margin-top: 3px; font-size: 12px; color: var(--label); }
  .tag { display: inline-block; font-size: 9px; letter-spacing: 1.1px; padding: 3px 7px; border-radius: 6px;
         margin-right: 8px; vertical-align: 2px; background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn-ring); }
  ul { margin: 0; padding-left: 0; list-style: none; } li { margin-bottom: 5px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; } .chips li { margin: 0; padding: 4px 10px; border-radius: 999px;
           background: var(--sand); color: var(--ink); font-size: 12.5px; }
  ul.plain li { margin-bottom: 10px; } ul.plain b { display: block; color: var(--ink); font-weight: 600; }
  ul.lines li { padding-left: 14px; position: relative; } ul.lines li::before { content: ""; position: absolute; left: 0; top: 8px;
           width: 5px; height: 5px; border-radius: 50%; background: var(--terracotta); }
  blockquote { margin: 0 0 12px; font: italic 400 15px/1.45 var(--display); color: var(--ink); }
  blockquote small { font: 400 12px/1.4 var(--sans); font-style: normal; }
  .muted { color: var(--label); font-size: 13.5px; }
  .note { margin-top: 18px; background: var(--terracotta-soft); border-radius: var(--radius-panel); padding: 18px 22px; }
  .note h2 { color: var(--terracotta-text); margin-bottom: 8px; } .note h2::after { display: none; }
  .note li { color: var(--ink); padding-left: 14px; position: relative; }
  .note li::before { content: "\\2022"; position: absolute; left: 0; color: var(--terracotta); }
  .foot { padding: 18px 4px 48px; font-size: 13.5px; color: var(--label); }
  .foot code { font-family: var(--mono); background: var(--sand); padding: 1px 6px; border-radius: 5px; color: var(--ink); }
  @media screen and (max-width: 820px) { .cols { grid-template-columns: 1fr; padding: 4px 22px 32px; }
        .side { border-left: 0; padding-left: 0; } .top { padding: 32px 22px 26px; }
        .sheet { margin: 0; border-radius: 0; border-left: 0; border-right: 0; } .note { margin: 14px 14px 0; }
        .foot { padding: 16px 18px 40px; } .job-top { flex-direction: column; gap: 2px; } .result { grid-template-columns: 78px 1fr; } }
  @media print { @page { size: A4; margin: 0; } body { background: none; font-size: 9.4px; line-height: 1.42; }
        .sheet { margin: 0; max-width: none; border: 0; border-radius: 0; box-shadow: none; }
        .note, .foot { display: none; }
        .top { padding: 15mm 13mm 8mm; } h1 { font-size: 27px; margin-bottom: 4px; } .headline { font-size: 11.5px; }
        .meta { margin-top: 10px; padding-top: 8px; font-size: 7.3px; } .kicker { font-size: 7px; margin-bottom: 8px; }
        .cols { padding: 0 13mm 10mm; gap: 0 9mm; } .side { padding-left: 7mm; } section { padding-top: 11px; break-inside: avoid; }
        h2 { font-size: 7.3px; margin-bottom: 7px; } .profile { font-size: 11px; } .job { margin-bottom: 9px; }
        .job strong { font-size: 10.6px; } .org { font-size: 10px; } .when { font-size: 6.8px; }
        .job p, .item p, .result p, .side p, li { font-size: 9.1px; } .result strong, .item strong { font-size: 9.6px; }
        .result { grid-template-columns: 62px 1fr; gap: 9px; margin-bottom: 8px; } .fig { font-size: 9.5px; padding: 5px 4px; }
        .chips li { font-size: 8.4px; padding: 2px 7px; } blockquote { font-size: 9.6px; } small { font-size: 7.6px; }
        .tag { font-size: 6px; padding: 2px 4px; } }
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


SENT = re.compile(r'(?<=\))\.\s+|(?<=[a-z0-9])\.\s+(?=[A-Z])')
LANGUAGE = re.compile(r'\b(native|fluent|bilingual|conversational|proficient|intermediate|basic)\b', re.I)


def parts(text):
    """A one-line answer such as 'M.Sc. X (2021). German native, English fluent.' as separate lines."""
    return [p.strip().rstrip('.') for p in SENT.split(text or '') if p.strip()]


def metric(text):
    """The figure a result leads with: '18% to 9%' as '18% → 9%', else the first number with its unit."""
    m = re.search(r'from\s+(\d[\d.,]*\s?%?)\s+to\s+(\d[\d.,]*\s?%?)', text, re.I)
    if m:
        return f'{m.group(1).strip()} → {m.group(2).strip()}'
    m = re.search(r'\d[\d.,]*\s?(?:%|percent|x\b|k\b|hours?|hrs?|days?|weeks?)', text, re.I)
    return m.group(0).strip() if m else ''


def job_html(item):
    role, employer, when = role_of(item['title'])
    text, _, transfer = item['text'].partition('Transfers:')
    org = f'<p class="org">{esc(employer)}</p>' if employer else ''
    stamp = f'<span class="when">{esc(when)}</span>' if when else ''
    gain = (f'<p class="transfer"><b>Transfers</b> {esc(clip(transfer.strip(), LIM['transfer']))}</p>' if transfer.strip() else '')
    return (f'<div class="job"><div class="job-top"><strong>{esc(role)}</strong>{stamp}</div>'
            f'{org}<p>{esc(clip(text.strip(), LIM['job']))}</p>{gain}</div>')


def result_html(item):
    big = metric(item['text'])
    figure = f'<div class="fig">{esc(big)}</div>' if big else '<div class="fig dot"></div>'
    return (f'<div class="result">{figure}<div><strong>{tag_html(item)}{esc(item["title"])}</strong>'
            f'<p>{esc(clip(item["text"], LIM["result"]))}</p>{trail_html(item)}</div></div>')


def chips_html(text):
    words = [w.strip() for w in re.split(r'\s*[,·;]\s*|\s+and\s+', text or '') if w.strip()]
    return '<ul class="chips">' + ''.join(f'<li>{esc(w)}</li>' for w in words[:LIM['chips']]) + '</ul>' if words else ''


def lines_html(items):
    return '<ul class="lines">' + ''.join(f'<li>{esc(clip(i, 110))}</li>' for i in items[:LIM['lines']]) + '</ul>' if items else ''


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
    url = pick(found, 'Public Upwork profile URL') or ''
    facts = [('Based in', place.strip()), ('Rate', pick(found, 'Hourly rate')),
             ('Job Success', pick(found, 'Job Success')), ('Hours', pick(found, 'Timezone'))]
    meta = ''.join(f'<span>{esc(label)} <b>{esc(clip(short(value), 70))}</b></span>' for label, value in facts
                   if value and not value.lower().startswith(('no ', 'none')))
    if url.startswith('http'):
        meta += f'<span><a href="{esc(url)}">Upwork profile</a></span>'
    return ('<p class="kicker">Resume</p>'
            f'<h1>{esc(name.strip() or "Your Upwork resume")}</h1>'
            + (f'<p class="headline">{esc(clip(headline))}</p>' if headline else
               '<p class="headline">What every command reads before it writes for you.</p>')
            + (f'<div class="meta">{meta}</div>' if meta else ''))


def services_html(me, found):
    """The branches with their services when the file lists them, else the one-line answer."""
    rows = [m.groups() for line in me.get('What you do', [])
            for m in [re.match(r'^-\s*([^:]+):\s*(.+)$', line.strip())] if m]
    if rows:
        return '<ul class="plain">' + ''.join(
            f'<li><b>{esc(name)}</b>{esc(clip(items, 120))}</li>' for name, items in rows[:LIM['services']]) + '</ul>'
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


def build(me_text, proof_text, full=False, has_full=False):
    LIM.clear()
    LIM.update(FULL if full else FIT)
    me = dict(sections(me_text))
    found = answers(me)
    proof = dict(sections(proof_text))
    jobs = entries(me.get('Your background', []))
    results, creds, reviews = (entries(proof.get(name, [])) for name in ('Results', 'Credentials', 'Reviews'))

    results = sorted(results, key=lambda r: (r['pending'], not metric(r['text'])))  # proven, with a figure, first
    earlier = [role_of(j['title']) for j in jobs[LIM['jobs']:LIM['jobs'] + LIM['earlier']]]
    earlier_line = lines_html([f'{role}, {org} ({when})' if org else f'{role} ({when})' for role, org, when in earlier]) \
        if earlier else ''
    experience = ''.join(job_html(j) for j in jobs[:LIM['jobs']]) + (
        f'<p class="muted">Earlier</p>{earlier_line}' if earlier_line else '') \
        + more(len(jobs), LIM['jobs'] + (len(earlier) if earlier_line else 0)) or \
        '<p class="muted">Still open. /about-me fills this from your CV and your answers.</p>'
    selected = ''.join(result_html(r) for r in results[:LIM['results']]) + more(len(results), LIM['results']) or \
        '<p class="muted">Nothing yet. The first delivered job fills this.</p>'
    strength = (pick(found, 'What you are good at') or '').strip('"“” ')
    summary = f'<p class="profile">{esc(clip(strength, LIM["profile"]))}</p>' if strength else ''
    tools = chips_html(pick(found, 'Tools and systems'))
    lines = parts(pick(found, 'Education'))
    languages = [p for p in lines if LANGUAGE.search(p)]
    schooling = [p for p in lines if p not in languages]
    quotes = ''.join(f'<blockquote>{esc(clip(r["text"], LIM["quote"]))}<small>{esc(clip(r["title"], 60))}</small></blockquote>'
                     for r in reviews[:LIM['quotes']])
    unconfirmed = sum(1 for item in results + creds + reviews if item['pending'])
    title = (pick(found, 'Name and location') or 'Your Upwork resume').partition(',')[0]

    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)} · Upwork resume</title>\n<style>' + tokens() + CSS + '</style>\n</head>\n<body>\n'
            '<main class="sheet">\n<header class="top">' + header_html(found) + '</header>\n'
            '<div class="cols">\n<div>\n'
            + block('Profile', summary) + block('Experience', experience) + block('Selected results', selected) +
            '\n</div>\n<div class="side">\n'
            + block('Skills and tools', tools)
            + block('Services', services_html(me, found))
            + block('Education', lines_html(schooling))
            + block('Certificates', ''.join(item_html(c, LIM['item']) for c in creds[:LIM['creds']]) + more(len(creds), LIM['creds']))
            + block('Languages', lines_html(languages))
            + block('Recommendations', quotes) +
            '\n</div>\n</div>\n</main>\n'
            + open_html(found, unconfirmed) +
            '\n<p class="foot">Next: <code>/profile</code> writes your Upwork profile from this. '
            'Built from context/me.md on this machine; rebuild it with '
            '<code>python3 code/context_page.py --open</code>.'
            + (' The sheet keeps the strongest of each kind to fit one page; everything else is on the '
               '<a href="overview-full.html">full version</a>.' if has_full else '') + '</p>\n'
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
    one, everything = build(me_text, proof_text), build(me_text, proof_text, full=True)
    trimmed = one != everything
    OUT.write_text(build(me_text, proof_text, has_full=trimmed), encoding='utf-8')
    if trimmed:
        FULL_OUT.write_text(everything, encoding='utf-8')
    elif FULL_OUT.exists():
        FULL_OUT.unlink()
    print(f'{OUT.relative_to(ROOT)} written, {open_points} open' + (f'; everything on {FULL_OUT.name}' if trimmed else ''))
    if args.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
