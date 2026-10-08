#!/usr/bin/env python3
"""Finds the member's own career files on this computer, by name only.

    python3 code/material.py [--json] [--limit N] [--home PATH]

/about-me drafts its questions from what a member already has: a CV, a
portfolio, a case study, a reference letter, a certificate. Most members cannot
say where those files are, so this looks in the folders people keep them in and
lists what the names give away, newest first.

It opens no file. Reading one stays with Claude Code, which asks the member
before it opens anything outside this repository, so a name that matched by
accident costs a line in a list and nothing else.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
from collections.abc import Iterator

FOLDERS = ('Documents', 'Downloads', 'Desktop', 'Dropbox', 'OneDrive', 'Google Drive',
           'iCloud Drive', 'Library/Mobile Documents/com~apple~CloudDocs', 'Library/CloudStorage')
# What a file name says it is, strongest material first. Words match whole
# tokens, so "cv" finds "CV 2025.pdf" and leaves "recvd.pdf" alone.
KINDS = (
    ('CV', {'cv', 'resume', 'résumé', 'resumé', 'lebenslauf'}, ('curriculum vitae',)),
    ('LinkedIn export', {'linkedin'}, ()),
    ('Portfolio or case study', {'portfolio', 'casestudy'}, ('case study', 'case studies')),
    ('Recommendation', {'testimonial', 'testimonials', 'recommendation', 'recommendations',
                        'referenz', 'zeugnis', 'arbeitszeugnis'},
     ('reference letter', 'letter of reference', 'performance review')),
    ('Certificate or award', {'certificate', 'certificates', 'certification', 'certifications',
                              'zertifikat', 'diploma', 'award', 'awards'}, ()),
)
DOCUMENTS = {'.pdf', '.docx', '.doc', '.pages', '.odt', '.rtf', '.txt', '.md', '.pptx', '.ppt', '.key'}
# A photographed certificate is still a certificate; a photo named "portfolio" is not a portfolio.
IMAGES = {'.png', '.jpg', '.jpeg'}
IMAGE_KINDS = {'Certificate or award'}
SKIP_DIRS = {'node_modules', 'Library', 'venv', 'site-packages', '__pycache__'}
SKIP_SUFFIXES = ('.app', '.photoslibrary', '.bundle')
SYSTEM_PROFILES = {'Public', 'Default', 'Default User', 'All Users'}
MAX_DEPTH = 4
MAX_FILES = 100_000
PER_KIND = 8


def homes(home: pathlib.Path) -> list[pathlib.Path]:
    """The member's home, plus their Windows profile when this runs under WSL."""
    found = [home]
    windows = pathlib.Path('/mnt/c/Users')
    if windows.is_dir():
        found.extend(p for p in sorted(windows.iterdir())
                     if p.name not in SYSTEM_PROFILES and (p / 'Documents').is_dir())
    return found


def kind_of(path: pathlib.Path) -> str | None:
    """What the name says the file is, or None when it says nothing useful."""
    suffix = path.suffix.lower()
    if suffix not in DOCUMENTS | IMAGES:
        return None
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', path.stem)
    tokens = re.findall(r'[^\W\d_]+', spaced.lower())
    phrase = ' '.join(tokens)
    if tokens == ['profile'] and suffix == '.pdf':  # the name LinkedIn gives its own export
        return 'LinkedIn export'
    for kind, words, phrases in KINDS:
        if words & set(tokens) or any(p in phrase for p in phrases):
            return kind if suffix in DOCUMENTS or kind in IMAGE_KINDS else None
    return None


def walk(root: pathlib.Path, refused: list[str]) -> Iterator[pathlib.Path]:
    """Every file up to MAX_DEPTH below root, skipping hidden and system folders."""
    depth_of_root = len(root.parts)
    for current, dirs, files in os.walk(root, onerror=lambda error: refused.append(error.filename)):
        here = pathlib.Path(current)
        deep = len(here.parts) - depth_of_root >= MAX_DEPTH
        dirs[:] = [] if deep else [d for d in dirs if not d.startswith('.')
                                   and d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES)]
        yield from (here / name for name in files if not name.startswith('.'))


def describe(path: pathlib.Path, kind: str) -> dict | None:
    """One found file as a record, or None when it vanished or cannot be read."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return {'kind': kind, 'path': str(path), 'bytes': stat.st_size,
            'modified': datetime.date.fromtimestamp(stat.st_mtime).isoformat()}


def scan(home: pathlib.Path) -> tuple[list[str], list[str], list[dict], bool]:
    """Looks through the usual folders. Returns (looked_in, refused, files, complete)."""
    looked_in, refused, files, seen = [], [], [], 0
    roots = [base / folder for base in homes(home) for folder in FOLDERS]
    for root in (r for r in roots if r.is_dir()):
        looked_in.append(str(root))
        for path in walk(root, refused):
            seen += 1
            if seen > MAX_FILES:
                return looked_in, refused, files, False
            kind = kind_of(path)
            record = describe(path, kind) if kind else None
            if record:
                files.append(record)
    return looked_in, refused, files, True


def ranked(files: list[dict], limit: int) -> list[dict]:
    """Strongest kind first and newest first within it, at most PER_KIND of each."""
    order = [kind for kind, _, _ in KINDS]
    kept = []
    for kind in order:
        same = sorted((f for f in files if f['kind'] == kind), key=lambda f: f['modified'], reverse=True)
        kept.extend(same[:PER_KIND])
    return kept[:limit]


def size(count: int) -> str:
    return f'{count / 1_000_000:.1f} MB' if count >= 1_000_000 else f'{max(1, count // 1000)} KB'


def report(looked_in: list[str], refused: list[str], shown: list[dict],
           total: int, complete: bool) -> str:
    lines = ['Looked in: ' + (', '.join(looked_in) or 'no folder found')]
    if refused:
        lines.append('Could not open: ' + ', '.join(sorted(set(refused)))
                     + ' (the system refused; the member can allow it in their privacy settings)')
    if not complete:
        lines.append(f'Stopped after {MAX_FILES} files; the list may be incomplete.')
    if not shown:
        lines.append('No file whose name says CV, portfolio, case study, recommendation or certificate.')
    for kind in dict.fromkeys(f['kind'] for f in shown):
        lines.append(f'\n{kind}')
        lines.extend(f"  {f['path']} · {f['modified']} · {size(f['bytes'])}"
                     for f in shown if f['kind'] == kind)
    if total > len(shown):
        lines.append(f'\n+ {total - len(shown)} more with the same kind of name, older.')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--limit', type=int, default=30, help='most files to list')
    parser.add_argument('--home', type=pathlib.Path, default=pathlib.Path.home(),
                        help='the home folder to look in, the member\'s own by default')
    args = parser.parse_args(argv)
    if not args.home.is_dir():
        print(f'FAIL  {args.home} is not a folder')
        return 1
    looked_in, refused, files, complete = scan(args.home)
    shown = ranked(files, max(1, args.limit))
    if args.json:
        print(json.dumps({'looked_in': looked_in, 'refused': sorted(set(refused)),
                          'files': shown, 'more': len(files) - len(shown),
                          'complete': complete}, indent=2))
    else:
        print(report(looked_in, refused, shown, len(files), complete))
    return 0


if __name__ == '__main__':
    sys.exit(main())
