#!/usr/bin/env python3
"""Does this repo work for a stranger who just cloned it? The release gate.

Mechanical checks only, the kind that surfaced as breaks on a real clone of the
repo this one grew out of:

    1. No personal data survived: names, domains, ids, machine paths
    2. Nothing shipped speaks German
    3. No em-dashes in anything shipped
    4. Every path a command mentions exists, or is the member's own file
    5. Every `python3 code/X.py cmd` a command calls is a real subcommand
    6. Every starter lands on a gitignored path, so a member never commits it
    7. Every command has a description in its frontmatter

Exit 1 on any finding, so it gates a release rather than being read politely.

    python3 code/check_repo.py [--quiet]
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / '.claude' / 'commands'
SELF = 'code/check_repo.py'

# Traces of the machine this was built on. A hit means the separation missed something.
LEAKS = [
    (r'\bLuka\b|\bKnieling\b', 'a personal name'),
    (r'flouence\.com', 'a personal domain'),
    (r'\b1898663420131815612\b', 'a specific Upwork org id'),
    (r'~0[0-9a-f]{17}', 'an Upwork profile id'),
    (r'/Users/[a-z]+/', 'an absolute home directory'),
]

# German function words and orthography. A shipped line carrying one is text a
# member will read in the wrong language.
GERMAN = re.compile(
    r'[äöüßÄÖÜ]|\b(nicht|keine[rnms]?|kein|eine[rnms]?|und|oder|wird|werden|weil|damit|'
    r'sondern|statt|schon|noch|Datei|Ordner|Zeile|erledigt|fehlt|liegt|gibt|nichts|'
    r'etwas|dieser|diesem|diesen|deine[rnms]?|selbst|bereits|jeder|jede[nrms]?)\b',
    re.IGNORECASE)

# Files a member creates or a command writes at runtime. A command may point at
# them although a fresh clone does not have them yet.
MEMBER_PATHS = ('context/', 'data/', 'jobs/')


# The cockpit app's own source. Its texts reach the member like any command does.
COCKPIT = ('cockpit/**/*.ts', 'cockpit/**/*.tsx', 'cockpit/**/*.mjs', 'cockpit/**/*.css')


def shipped(*globs):
    """Every tracked-or-trackable file matching the globs: what a stranger receives."""
    found = []
    for g in globs:
        found += [p for p in ROOT.glob(g) if p.is_file() and '.git/' not in str(p)]
    if not found:
        return []
    rels = [str(p.relative_to(ROOT)) for p in found]
    r = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT,
                       input='\n'.join(rels), capture_output=True, text=True)
    ignored = set(r.stdout.split('\n'))
    return [p for p, rel in zip(found, rels) if rel not in ignored and rel != SELF]


def lines_of(p):
    try:
        return p.read_text(encoding='utf-8').splitlines()
    except (UnicodeDecodeError, OSError):
        return []


def check_leaks():
    findings = []
    for p in shipped('**/*.md', '**/*.py', '**/*.html', '**/*.json', '**/*.js', *COCKPIT):
        for i, line in enumerate(lines_of(p), 1):
            for pattern, what in LEAKS:
                m = re.search(pattern, line)
                if m:
                    findings.append(f'{p.relative_to(ROOT)}:{i} carries {what}: {m.group(0)}')
    return findings


def check_language():
    findings = []
    for p in shipped('**/*.md', '**/*.py', *COCKPIT):
        for i, line in enumerate(lines_of(p), 1):
            if GERMAN.search(line):
                findings.append(f'{p.relative_to(ROOT)}:{i} is German: "{line.strip()[:60]}"')
                break
    return findings


def check_em_dashes():
    findings = []
    for p in shipped('**/*.md', '**/*.py', '**/*.html', *COCKPIT):
        hits = [i for i, line in enumerate(lines_of(p), 1) if '—' in line]
        if hits:
            more = f' (+{len(hits) - 1} more)' if len(hits) > 1 else ''
            findings.append(f'{p.relative_to(ROOT)}:{hits[0]} has an em-dash{more}')
    return findings


def check_paths():
    findings = []
    pat = re.compile(r'`((?:context|data|jobs|code|references|starters)/[\w./-]+)`')
    for p in sorted(COMMANDS.glob('*.md')):
        for m in pat.finditer(p.read_text(encoding='utf-8')):
            rel = m.group(1)
            if (ROOT / rel).exists() or rel.startswith(MEMBER_PATHS):
                continue
            findings.append(f'{p.name}: points at {rel}, which does not exist')
    return findings


def check_subcommands():
    findings = []
    pat = re.compile(r'python3 (code/[\w_]+\.py) ([a-z][\w-]*)')
    seen = set()
    for p in sorted(COMMANDS.glob('*.md')) + [ROOT / 'CLAUDE.md']:
        for m in pat.finditer(p.read_text(encoding='utf-8')):
            script, cmd = m.groups()
            if (script, cmd) in seen:
                continue
            seen.add((script, cmd))
            if not (ROOT / script).is_file():
                findings.append(f'{p.name}: calls {script}, which does not exist')
                continue
            r = subprocess.run([sys.executable, str(ROOT / script), cmd, '--help'],
                               capture_output=True, text=True, cwd=ROOT)
            if r.returncode != 0 and 'invalid choice' in r.stderr:
                findings.append(f'{p.name}: calls `{script} {cmd}`, not a valid subcommand')
    return findings


def check_starters_ignored():
    """Both halves of the git-pull promise: the starter ships, its copy never does.

    The first half failed once: a bare `context/` ignore pattern also matched
    starters/context/, so the starters silently never shipped.
    """
    findings = []
    starters = ROOT / 'starters'

    def ignored(rel):
        return subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT).returncode == 0

    for p in sorted(x for x in starters.rglob('*') if x.is_file()):
        rel = str(p.relative_to(starters))
        if ignored(f'starters/{rel}'):
            findings.append(f'starters/{rel} is gitignored itself, so it never ships')
        if not ignored(rel):
            findings.append(f'starters/{rel} lands on {rel}, which is not gitignored: '
                            f'a member filling it in would publish it')
    return findings


def check_frontmatter():
    findings = []
    for p in sorted(COMMANDS.glob('*.md')):
        head = p.read_text(encoding='utf-8')[:800]
        if not head.startswith('---') or 'description:' not in head:
            findings.append(f'{p.name}: no description in its frontmatter')
    return findings


CHECKS = [
    ('personal data', check_leaks),
    ('language', check_language),
    ('em-dashes', check_em_dashes),
    ('command paths', check_paths),
    ('script subcommands', check_subcommands),
    ('starters gitignored', check_starters_ignored),
    ('command frontmatter', check_frontmatter),
]


def main():
    quiet = '--quiet' in sys.argv
    total = 0
    for label, fn in CHECKS:
        found = fn()
        total += len(found)
        if found:
            print(f'\n{label}:')
            for f in found:
                print(f'  {f}')
        elif not quiet:
            print(f'ok  {label}')
    if total:
        print(f'\n{total} finding(s). Fix before publishing.')
        return 1
    if not quiet:
        print('\nClean.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
