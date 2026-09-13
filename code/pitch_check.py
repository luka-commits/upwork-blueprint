#!/usr/bin/env python3
"""The gate for what goes to a client before a contract: the pitch page and the Loom script.

    python3 code/pitch_check.py page jobs/<id>/pitch.html
    python3 code/pitch_check.py loom jobs/<id>/loom-script.md

The page check exists because Upwork bans contact details before a contract,
and a linked page counts: an email, a phone number, a booking link, a WhatsApp
button or a social profile on it is a way to reach the freelancer off Upwork.
The Loom check keeps the video between three and four minutes.
"""
import html
import pathlib
import re
import sys

# Spoken English lands around 140 words a minute on a screen walkthrough.
WORDS_PER_MINUTE = 140
LOOM_MIN, LOOM_MAX = 3 * WORDS_PER_MINUTE, 4 * WORDS_PER_MINUTE

CONTACT_LINKS = re.compile(
    r'(mailto:|tel:|wa\.me|whatsapp|calendly\.com|cal\.com/|tidycal|zcal\.co|savvycal|meetings\.hubspot|'
    r'linkedin\.com|instagram\.com|facebook\.com|fb\.me|tiktok\.com|twitter\.com|//x\.com|t\.me/|'
    r'skype:|telegram|discord\.gg)', re.I)
EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b', re.I)
PHONE = re.compile(r'(?<![\w.])\+?\d[\d ().-]{8,}\d(?![\w.])')
BOOKING_WORDS = re.compile(r'\b(book a call|schedule a call|book a meeting|email me|call me|whatsapp me)\b', re.I)


def visible_text(page):
    """What a reader sees: no scripts, styles, comments or embedded images."""
    page = re.sub(r'<(script|style)\b.*?</\1>', ' ', page, flags=re.S | re.I)
    page = re.sub(r'<!--.*?-->', ' ', page, flags=re.S)
    page = re.sub(r'<[^>]+>', ' ', page)
    return html.unescape(page)


def links(page):
    return [h for h in re.findall(r'href="([^"]*)"', page) if not h.startswith(('#', 'data:'))]


def check_page(path):
    page = pathlib.Path(path).read_text(encoding='utf-8')
    problems = []
    for h in links(page):
        if CONTACT_LINKS.search(h):
            problems.append(f'links a way to reach you off Upwork: {h[:80]}')
    text = visible_text(page)
    for m in EMAIL.finditer(text):
        problems.append(f'shows an email address: {m.group(0)}')
    for m in PHONE.finditer(text):
        if len(re.sub(r'\D', '', m.group(0))) >= 9:
            problems.append(f'shows what looks like a phone number: {m.group(0).strip()}')
    for m in BOOKING_WORDS.finditer(text):
        problems.append(f'asks for contact off Upwork: "{m.group(0)}"')
    if chr(0x2014) in text:
        problems.append('uses an em-dash in the copy')
    left = re.findall(r'\{\{[A-Z_]+\}\}', page)
    if left:
        problems.append(f'unfilled placeholders: {", ".join(sorted(set(left)))}')
    return problems


def check_loom(path):
    text = pathlib.Path(path).read_text(encoding='utf-8')
    spoken = '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith(('#', '>', '**Beat', '---')))
    spoken = re.sub(r'\[[^\]]*\]|\*\*[^*]*\*\*:?', ' ', spoken)
    words = len(re.findall(r"[A-Za-z0-9'$%.,-]+", spoken))
    problems = []
    if not LOOM_MIN <= words <= LOOM_MAX:
        minutes = words / WORDS_PER_MINUTE
        problems.append(f'{words} spoken words, about {minutes:.1f} minutes; the target is '
                        f'{LOOM_MIN} to {LOOM_MAX} words, three to four minutes')
    if 'upwork' not in text[-600:].lower():
        problems.append('the ending does not point the client back to Upwork')
    for link in re.findall(r'https://[^\s<>]+', text):
        if 'upwork.com' not in link.lower():
            problems.append(f'links outside Upwork: {link[:80]}')
    for match in EMAIL.finditer(text):
        problems.append(f'shows an email address: {match.group(0)}')
    for match in PHONE.finditer(text):
        if len(re.sub(r'\D', '', match.group(0))) >= 9:
            problems.append(f'shows what looks like a phone number: {match.group(0).strip()}')
    for match in BOOKING_WORDS.finditer(text):
        problems.append(f'asks for contact off Upwork: "{match.group(0)}"')
    if chr(0x2014) in text:
        problems.append('uses an em-dash')
    return problems, words


def main(argv):
    if len(argv) != 2 or argv[0] not in ('page', 'loom'):
        print(__doc__, file=sys.stderr)
        return 2
    if argv[0] == 'page':
        problems = check_page(argv[1])
        summary = 'no contact details, no placeholders'
    else:
        problems, words = check_loom(argv[1])
        summary = f'{words} spoken words, about {words / WORDS_PER_MINUTE:.1f} minutes'
    for p in problems:
        print(f'FAIL  {p}')
    print(f'\n{"PASS  " + summary if not problems else f"{len(problems)} problem(s)."}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
