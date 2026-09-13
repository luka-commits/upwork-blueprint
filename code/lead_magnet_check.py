#!/usr/bin/env python3
"""Validate one SEO audit before it is published for an Upwork lead."""

import pathlib
import re
import sys

import pitch_check


def check_page(path):
    source = pathlib.Path(path)
    page = source.read_text(encoding='utf-8')
    problems = list(pitch_check.check_page(source))
    if page.count('data-audit-section="') != 3:
        problems.append('does not contain the three checked audit sections')
    if 'name="lead-magnet-template" content="upwork-lead-magnet-v1"' not in page:
        problems.append('is not the current Upwork lead-magnet template')
    if 'Reply here on Upwork' not in page:
        problems.append('does not return the client to Upwork')
    if "connect-src 'none'" not in page:
        problems.append('does not block outbound browser connections')
    if re.search(r'(?:src|href|action)=["\']https?://', page, re.I):
        problems.append('loads or links an external HTTP resource')
    return problems


def main(argv):
    if len(argv) != 1:
        print('usage: python3 code/lead_magnet_check.py jobs/<id>/lead-magnet.html', file=sys.stderr)
        return 2
    problems = check_page(argv[0])
    for problem in problems:
        print(f'FAIL  {problem}')
    print('\nPASS  checked audit is safe to publish' if not problems else f'\n{len(problems)} problem(s).')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
