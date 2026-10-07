#!/usr/bin/env python3
"""The one page a client reads after the call: the video first, then eight short parts.

    python3 code/proposal_generate.py <job id> --file proposal.json
    python3 code/proposal_generate.py <job id> --file -        # JSON on stdin

Writes jobs/<id>/proposal.html from templates/proposal/template.html. The markdown
proposal stays the thing the member pastes into Upwork chat. The member delivers
the page themselves unless a real CTA URL was provided.

Every value the call did not settle is rendered as a visible "open" marker, never as a
zero and never as a rounded guess: a missing number is honest, an invented one is a claim
the first milestone exposes.

The JSON, all strings unless noted:

    member, client, headline, date,
    video (object: href, title, note, length),
    problem, deliverable, worth, timeline, cost, tools, proof,
    next_steps (array, at most three),
    cta, cta_href, fine (array),
    labels (object, optional, overrides the eight part labels)

Each part is one line. A part may also be {text, note} when one short line under it
carries something the client needs, like the milestone split under the cost.
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
    'cost': 'Cost',
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
