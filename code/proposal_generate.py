#!/usr/bin/env python3
"""The one page a client reads after the call: a letterhead, then numbered sections top to bottom.

    python3 code/proposal_generate.py <job id> --file proposal.json
    python3 code/proposal_generate.py <job id> --file -        # JSON on stdin

Writes jobs/<id>/proposal.html from templates/proposal/template.html. The markdown
proposal stays the thing the member pastes into Upwork chat. The member delivers
the page themselves unless a real CTA URL was provided.

Every value the call did not settle is rendered as a visible "open" marker, never as a
zero and never as a rounded guess: a missing number is honest, an invented one is a claim
the first milestone exposes. Proof and worth are the exception: without one, their line is
left out, because an open proof only tells the client there is none.

The JSON, all strings unless noted:

    member, client, headline, date,
    photo (optional: the member's photo, a local file or an HTTPS URL; else their initials),
    video (object: href, title, note, length),
    flow (array, optional, three to five short steps of how it works),
    problem, deliverable, worth, timeline, cost, tools, proof,
    next_steps (array, at most three),
    cta, cta_href, fine (array),
    labels (object, optional, overrides the eight part labels)

Each part is one line. A part may also be {text, note} when one short line under it
carries something the client needs, like the milestone split under the cost. The
timeline may instead be up to four stops [{when, what}]; the cost may carry items
[{label, amount, when}], one per milestone, with its text as the total. Items with a
`when` merge timeline and price into one plan; a string timeline is then its start note.
"""
import argparse
import base64
import datetime
import html
import json
import pathlib
import sys
from urllib.parse import urlparse
from pipeline import jobs_dir, shown

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates' / 'proposal' / 'template.html'
OPEN = '<span class="missing">open</span>'
PARTS = ('problem', 'deliverable', 'worth', 'timeline', 'cost', 'tools', 'proof', 'next')
DEFAULT_LABELS = {
    'problem': 'The problem',
    'deliverable': 'What you get',
    'worth': "What it's worth",
    'timeline': 'Timeline',
    'cost': 'Investment',
    'tools': 'Tools',
    'proof': 'Proof',
    'next': 'Next steps',
}


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def esc(value):
    return html.escape(str(value), quote=True)


def value(raw):
    """A filled value, or the open marker when the call did not settle it."""
    text = str(raw or '').strip()
    return esc(text) if text else OPEN


def https(href, field):
    href = str(href or '').strip()
    if not href:
        return ''
    parsed = urlparse(href)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in href):
        abort(f'{field} needs a real HTTPS URL, or leave it empty.')
    return href


def part(raw, strong=False):
    """One line, and at most one short line under it."""
    if isinstance(raw, dict):
        text, note = raw.get('text'), str(raw.get('note') or '').strip()
    else:
        text, note = raw, ''
    line = value(text)
    if strong and 'missing' not in line:
        line = f'<strong>{line}</strong>'
    return line + (f'<small>{esc(note)}</small>' if note else '')


def photo(raw, member):
    """The member's face in the letterhead: a local file is embedded, else their initials."""
    raw = str(raw or '').strip()
    if raw.startswith('https://'):
        return f'<img class="face" alt="" src="{esc(https(raw, "photo"))}">'
    path = pathlib.Path(raw).expanduser() if raw else None
    if path and not path.is_absolute():
        path = ROOT / path
    if path and path.is_file():
        from photo import data_uri
        return f'<img class="face" alt="" src="{data_uri(path)}">'
    if raw:
        abort(f'photo not found: {raw}')
    initials = ''.join(w[0] for w in str(member or '').split()[:2]).upper()
    return f'<span class="face">{esc(initials)}</span>' if initials else ''


def flow(raw, label):
    """Optional: how the build works, three to five short steps drawn as a line. Absent, no section."""
    steps = [s for s in (raw or []) if str(s or '').strip()]
    if not steps:
        return ''
    if not 3 <= len(steps) <= 5:
        abort(f'flow has {len(steps)} steps; it draws three to five.')
    return (f'<section class="sec flow"><p class="k">{esc(label)}</p><div class="v"><ol>'
            + ''.join(f'<li><span>{esc(s)}</span></li>' for s in steps) + '</ol></div></section>')


def cost(raw):
    """The price. With items [{label, amount}] it reads as an offer: one line per milestone, then the total."""
    items = raw.get('items') if isinstance(raw, dict) else None
    if not items:
        return part(raw, strong=True)
    rows = ''.join(f'<tr><td>{value(i.get("label"))}</td><td>{value(i.get("amount"))}</td></tr>'
                   for i in items if isinstance(i, dict))
    note = str(raw.get('note') or '').strip()
    return (f'<table class="price">{rows}<tr class="total"><td>Total</td><td>{value(raw.get("text"))}</td></tr></table>'
            + (f'<small>{esc(note)}</small>' if note else ''))


def section(label, body, kind=''):
    return f'<section class="sec {kind}"><p class="k">{esc(label)}</p><div class="v">{body}</div></section>'


def plan(data, labels):
    """When and what it costs. Milestones with a `when` become one plan: a phase per milestone,
    its days, its delivery and its amount, then the total. Otherwise timeline and price apart."""
    raw = data.get('cost')
    items = [i for i in (raw.get('items') or []) if isinstance(i, dict)] if isinstance(raw, dict) else []
    # Only a figure the client gave on the call; without one the line is left out, not marked open.
    worth = (f'<div class="worth"><span>{esc(labels["worth"])}</span><span class="v">{esc(data["worth"])}</span></div>'
             if str(data.get('worth') or '').strip() else '')
    if not any(i.get('when') for i in items):
        return (section(labels['timeline'], timeline(data.get('timeline')))
                + section(labels['cost'], cost(raw) + worth))
    if len(items) > 4:
        abort(f'cost has {len(items)} milestones; the plan shows four at most.')
    phases = ''.join(
        f'<li><i></i><b>Milestone {n} · {value(i.get("when"))}</b><span>{value(i.get("label"))}</span>'
        f'<em>{value(i.get("amount"))}</em></li>' for n, i in enumerate(items, 1))
    start = data.get('timeline') if isinstance(data.get('timeline'), str) else ''
    notes = ' '.join(esc(n) for n in (start, raw.get('note')) if str(n or '').strip())
    total = (f'<div class="sum"><small>{notes}</small>'
             f'<p><span>Total</span><strong>{value(raw.get("text"))}</strong></p></div>')
    return section(labels.get('plan', 'Plan and investment'), f'<ol class="phases">{phases}</ol>{total}{worth}', 'plan')


def proof(raw, label):
    """Proof from the evidence in me.md, or no section at all: an empty proof line tells the client there is none."""
    text = part(raw)
    return '' if 'missing' in text else section(label, text, 'proof')


def timeline(raw):
    """A sentence, or up to four stops [{when, what}] drawn as a track from start to live."""
    if not isinstance(raw, list):
        return part(raw)
    stops = [s for s in raw if isinstance(s, dict) and (s.get('when') or s.get('what'))]
    if not stops:
        return OPEN
    if len(stops) > 4:
        abort(f'timeline has {len(stops)} stops; the track shows four at most.')
    return '<ol class="track">' + ''.join(
        f'<li><b>{value(s.get("when"))}</b><span>{value(s.get("what"))}</span></li>' for s in stops) + '</ol>'


def next_steps(items):
    """The things the client does to start. Three at most, or it is not a next step."""
    items = [i for i in (items or []) if str(i or '').strip()]
    if not items:
        return OPEN
    if len(items) > 3:
        abort(f'next_steps has {len(items)} items; the client gets three at most.')
    return '<ol>' + ''.join(f'<li>{esc(i)}</li>' for i in items) + '</ol>'


def poster(job_id):
    """The illustrated sheet, dimmed behind the video card. Absent is fine."""
    path = jobs_dir() / job_id / 'proposal-sketch.png'
    if not path.is_file():
        return ''
    try:
        from PIL import Image
        import io
        image = Image.open(path).convert('RGB')
        # The model likes to draw a sheet lying on a table. Trim that border away so the
        # card shows the drawing and not the desk it was photographed on.
        width, height = image.size
        if width > 400 and height > 400:
            image = image.crop((int(width * .09), int(height * .22), int(width * .91), int(height * .78)))
        image.thumbnail((1200, 1200))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=80)
        payload, mime = base64.b64encode(buffer.getvalue()).decode(), 'image/jpeg'
    except (ImportError, OSError):
        # No Pillow, or a file the drawing step left half written: the page still ships,
        # with the bytes as they are. A proposal never fails on its illustration.
        payload, mime = base64.b64encode(path.read_bytes()).decode(), 'image/png'
    return f'<img class="poster" alt="" src="data:{mime};base64,{payload}">'


def video(raw, job_id):
    """Optional. Without a link the card is left out and the page opens on the problem."""
    raw = raw or {}
    href = https(raw.get('href'), 'video.href')
    if not href:
        return ''
    length = str(raw.get('length') or '').strip()
    inner = (poster(job_id) + '<i class="play"></i>'
             f'<div><b>{value(raw.get("title"))}</b><span>{value(raw.get("note"))}</span></div>')
    return (f'<a class="video" href="{esc(href)}">{inner}'
            + (f'<span class="len">{esc(length)}</span>' if length else '') + '</a>')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('job_id')
    parser.add_argument('--file', required=True, help='JSON file, or - for stdin')
    parser.add_argument('--lang', default='en')
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.file == '-' else pathlib.Path(args.file).read_text(encoding='utf-8')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        abort(f'the proposal JSON does not parse: {error}')
    if not TEMPLATE.is_file():
        abort(f'template missing: {TEMPLATE}')

    labels = {**DEFAULT_LABELS, **(data.get('labels') or {})}
    today = datetime.date.today().strftime('%d %B %Y')

    page = TEMPLATE.read_text(encoding='utf-8')
    href = https(data.get('cta_href'), 'cta_href')
    if not href:
        page = page.replace('<a class="cta" href="{{CTA_HREF}}">{{CTA}}</a>', '')
    fields = {
        '{{LANG}}': esc(args.lang),
        '{{TITLE}}': value(data.get('headline')),
        '{{MEMBER}}': value(data.get('member')),
        '{{CLIENT}}': value(data.get('client')),
        # today is a fact, not a commitment: the day the page was prepared is true whether
        # or not the call settled anything, so this one keeps its default.
        '{{DATE}}': esc(data.get('date') or today),
        '{{HEADLINE}}': value(data.get('headline')),
        '{{VIDEO}}': video(data.get('video'), args.job_id),
        '{{NEXT}}': next_steps(data.get('next_steps')),
        '{{FINE}}': '<br>'.join(value(line) for line in (data.get('fine') or [''])),
        '{{CTA}}': value(data.get('cta')),
        '{{CTA_HREF}}': esc(href),
    }
    for name in PARTS[:-1]:
        fields['{{' + name.upper() + '}}'] = part(data.get(name), strong=name == 'cost')
    fields['{{PLAN}}'] = plan(data, labels)
    fields['{{PROOF}}'] = proof(data.get('proof'), labels['proof'])
    fields['{{PHOTO}}'] = photo(data.get('photo'), data.get('member'))
    fields['{{FLOW}}'] = flow(data.get('flow'), labels.get('flow', 'How it works'))
    for name in PARTS:
        fields['{{L_' + name.upper() + '}}'] = esc(labels[name])

    for marker, replacement in fields.items():
        page = page.replace(marker, replacement)
    left = [m for m in ('{{', '}}') if m in page]
    if left:
        abort('the template still holds unfilled markers; the field list and the template drifted.')

    out = jobs_dir() / args.job_id / 'proposal.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    opens = page.count('class="missing"')
    print(f'{shown(out)} written, {opens} value(s) still open.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
