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
FIT = {'jobs': 3, 'earlier': 3, 'results': 3, 'creds': 3, 'quotes': 1, 'chips': 10, 'services': 3, 'lines': 3,
       'profile': 260, 'job': 190, 'transfer': 100, 'result': 140, 'quote': 130, 'item': 70}
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
  body { margin: 0; background: var(--canvas); color: var(--ink); font: 14px/1.5 var(--sans); -webkit-font-smoothing: antialiased; }
  .sheet, .note, .foot { max-width: 840px; margin: 0 auto; }
  .sheet { margin-top: 36px; background: var(--paper); padding: 58px 66px 50px; box-shadow: 0 2px 20px rgba(20, 20, 19, .09); }
  .top { padding-bottom: 18px; border-bottom: 1px solid var(--ring); position: relative; }
  .top::after { content: ""; position: absolute; left: 0; bottom: -1px; width: 64px; height: 2px; background: var(--terracotta); }
  h1 { font: 500 36px/1.08 var(--display); letter-spacing: -1px; margin: 0 0 8px; }
  .headline { font: 400 17px/1.4 var(--display); color: var(--body); margin: 0; }
  .contact { margin: 14px 0 0; font: 400 11px/1.4 var(--mono); letter-spacing: .6px; color: var(--label); display: flex; flex-wrap: wrap; }
  .contact span + span::before { content: ""; display: inline-block; width: 4px; height: 4px; border-radius: 50%; background: var(--terracotta); margin: 0 12px 2px; }
  .contact a { color: inherit; }
  section { padding: 20px 0 0; }
  h2 { margin: 0 0 12px; display: flex; align-items: center; gap: 10px; font: 400 10.5px/1 var(--mono);
       letter-spacing: 2.2px; text-transform: uppercase; color: var(--label); }
  h2::before { content: ""; width: 18px; height: 2px; background: var(--terracotta); }
  h2::after { content: ""; flex: 1; height: 1px; background: var(--hairline-soft); }
  p { margin: 0; }
  .row { display: grid; grid-template-columns: 116px 1fr; gap: 0 18px; margin: 0 0 12px; }
  .when { font: 400 10.5px/1.5 var(--mono); letter-spacing: .8px; text-transform: uppercase; color: var(--label); padding-top: 3px; }
  .what strong { font: 600 14.5px/1.35 var(--sans); } .what .org { color: var(--terracotta-text); font-family: var(--display); font-size: 15px; }
  .what p { margin-top: 2px; color: var(--body); }
  .what .transfer { font-style: italic; }
  .profile { font: 400 17px/1.5 var(--display); color: var(--ink); }
  ul { margin: 0; padding-left: 0; list-style: none; } li { margin: 0 0 7px; padding-left: 16px; position: relative; color: var(--body); }
  li::before { content: ""; position: absolute; left: 0; top: 9px; width: 5px; height: 5px; border-radius: 50%; background: var(--terracotta); }
  li b { color: var(--ink); font-weight: 600; }
  .mark { font-size: 11px; color: var(--warn); white-space: nowrap; }
  blockquote { margin: 0 0 10px; color: var(--ink); font: italic 400 15.5px/1.45 var(--display); } blockquote small { display: block; font-style: normal; font-size: 12px; margin-top: 2px; }
  .muted { color: var(--label); font-size: 13px; }
  .note { margin-top: 18px; background: var(--terracotta-soft); border-radius: var(--radius-panel); padding: 18px 22px; }
  .note h2 { color: var(--terracotta-text); border: 0; padding: 0; margin-bottom: 8px; }
  .note ul { padding-left: 16px; } .note li { color: var(--ink); margin-bottom: 3px; }
  .foot { padding: 18px 4px 48px; font-size: 13.5px; color: var(--label); }
  .foot code { font-family: var(--mono); background: var(--sand); padding: 1px 6px; border-radius: 5px; color: var(--ink); }
  @media screen and (max-width: 680px) { .sheet { margin: 0; padding: 30px 22px 34px; } .row { grid-template-columns: 1fr; gap: 1px; }
        .note { margin: 14px 14px 0; } .foot { padding: 16px 18px 40px; } }
  @media print { @page { size: A4; margin: 15mm 16mm; } body { background: none; font-size: 9.7px; line-height: 1.45; }
        .sheet { margin: 0; max-width: none; padding: 0; box-shadow: none; } .note, .foot { display: none; }
        h1 { font-size: 26px; } .headline { font-size: 12px; } .contact { font-size: 7.6px; margin-top: 8px; } .top { padding-bottom: 11px; }
        section { padding-top: 13px; } h2 { font-size: 7.4px; margin-bottom: 8px; } .row { grid-template-columns: 24mm 1fr; gap: 0 5mm; margin-bottom: 8px; }
        .when { font-size: 7.4px; padding-top: 2px; } .profile { font-size: 11.4px; } .what strong { font-size: 10.4px; } .what .org { font-size: 10.6px; } li::before { top: 6px; } blockquote { font-size: 10.4px; } li { margin-bottom: 4px; } .mark { font-size: 7.5px; } blockquote small { font-size: 8.5px; } }
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


SENT = re.compile(r'(?<=\))\.\s+|(?<=[a-z]{4})\.\s+(?=[A-Z])')  # not after M.Sc., B.A., Dr.
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


def mark_html(item):
    return ' <span class="mark">(to confirm)</span>' if item['pending'] else ''


def row(when, what):
    return f'<div class="row"><div class="when">{esc(when)}</div><div class="what">{what}</div></div>'


def job_html(item):
    role, employer, when = role_of(item['title'])
    text, _, transfer = item['text'].partition('Transfers:')
    org = f', <span class="org">{esc(employer)}</span>' if employer else ''
    gain = f'<p class="transfer">{esc(clip(transfer.strip(), LIM["transfer"]))}</p>' if transfer.strip() else ''
    return row(when, f'<strong>{esc(role)}</strong>{org}<p>{esc(clip(text.strip(), LIM["job"]))}</p>{gain}')


def result_li(item):
    return f'<li><b>{esc(item["title"])}</b>{mark_html(item)}. {esc(clip(item["text"], LIM["result"]))}</li>'


def year_of(text):
    m = re.search(r'\b((?:19|20)\d{2})\b', text or '')
    return m.group(1) if m else ''


def school_row(line):
    when = year_of(line)
    return row(when, esc(clip(re.sub(r'\s*\(\s*((?:19|20)\d{2})\s*\)', '', line).strip(), 130)))


def cert_row(item):
    return row(year_of(item['text']), f'<strong>{esc(item["title"])}</strong>{mark_html(item)}')


def skill_row(label, text, limit):
    words = [w.strip() for w in re.split(r'\s*[,·;]\s*|\s+and\s+', text or '') if w.strip()]
    return row(label, esc(', '.join(words[:limit]))) if words else ''


def item_html(item, limit=CLIP):
    return (f'<div class="item"><strong>{tag_html(item)}{esc(item["title"])}</strong>'
            f'<p>{esc(clip(item["text"], limit))}</p>{trail_html(item)}</div>')


def block(title, inner):
    return f'<section><h2>{esc(title)}</h2>{inner}</section>' if inner else ''


def more(count, shown):
    return f'<p class="muted">and {count - shown} more in your file</p>' if count > shown else ''


def header_html(found):
    """Name, headline and the contact line a client reads first."""
    name, _, place = (pick(found, 'Name and location') or '').partition(',')
    headline = pick(found, 'The one thing') or pick(found, 'Profession')
    url = pick(found, 'Public Upwork profile URL') or ''
    facts = [place.strip(), pick(found, 'Timezone'), f'{pick(found, "Hourly rate")}/h' if pick(found, 'Hourly rate') else '',
             f'Job Success {pick(found, "Job Success")}' if pick(found, 'Job Success') else '']
    meta = ''.join(f'<span>{esc(clip(short(v), 60))}</span>' for v in facts
                   if v and not v.lower().startswith(('no ', 'none')) and 'not answered' not in v.lower())
    if url.startswith('http'):
        meta += f'<span><a href="{esc(url)}">{esc(clip(url.replace("https://", "").replace("http://", ""), 48))}</a></span>'
    return (f'<h1>{esc(name.strip() or "Your resume")}</h1>'
            + (f'<p class="headline">{esc(clip(headline))}</p>' if headline else '')
            + (f'<div class="contact">{meta}</div>' if meta else ''))


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
    experience = ''.join(job_html(j) for j in jobs[:LIM['jobs']])
    if earlier:
        experience += row('Earlier', '<p>' + esc('; '.join(f'{r}, {o} ({w})' if o else f'{r} ({w})' for r, o, w in earlier)) + '</p>')
    experience += more(len(jobs), LIM['jobs'] + len(earlier))
    experience = experience or '<p class="muted">Still open. /about-me fills this from your CV and your answers.</p>'
    selected = ('<ul>' + ''.join(result_li(r) for r in results[:LIM['results']]) + '</ul>' + more(len(results), LIM['results'])
                if results else '<p class="muted">Nothing yet. The first delivered job fills this.</p>')
    strength = (pick(found, 'What you are good at') or '').strip('"“” ')
    summary = f'<p class="profile">{esc(clip(strength, LIM["profile"]))}</p>' if strength else ''
    lines = parts(pick(found, 'Education'))
    languages = [p for p in lines if LANGUAGE.search(p)]
    named = {re.sub(r'\W+', '', c['title']).lower() for c in creds}  # a certificate listed twice shows once
    schooling = [p for p in lines if p not in languages
                 and re.sub(r'\W+', '', re.sub(r'\(.*?\)', '', p)).lower() not in named]
    skills = (skill_row('Tools', pick(found, 'Tools and systems'), LIM['chips'])
              + skill_row('Services', pick(found, 'Services you sell'), LIM['services'] * 3))
    language_row = row('Languages', esc(' · '.join(languages))) if languages else ''
    quotes = ''.join(f'<blockquote>{esc(clip(r["text"], LIM["quote"]))}<small>{esc(clip(r["title"], 60))}</small></blockquote>'
                     for r in reviews[:LIM['quotes']])
    unconfirmed = sum(1 for item in results + creds + reviews if item['pending'])
    title = (pick(found, 'Name and location') or 'Your resume').partition(',')[0]

    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)} · Resume</title>\n<style>' + tokens() + CSS + '</style>\n</head>\n<body>\n'
            '<main class="sheet">\n<header class="top">' + header_html(found) + '</header>\n'
            + block('Profile', summary) + block('Experience', experience) + block('Selected results', selected)
            + block('Education', ''.join(school_row(s) for s in schooling[:LIM['lines']]))
            + block('Certificates', ''.join(cert_row(c) for c in creds[:LIM['creds']]) + more(len(creds), LIM['creds']))
            + block('Skills and languages', skills + language_row)
            + block('Recommendations', quotes) +
            '\n</main>\n'
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
