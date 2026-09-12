#!/usr/bin/env python3
"""The gate for profile.md, the draft /profile writes, checked before a member pastes it.

    python3 code/profile_draft.py check profile.md [--proof context/proof.md] [--targets data/targets.json]

It passes only when the draft clears the audit's mechanical checks, lands on
the benchmark targets, fits Upwork's form, and every number in it can be found
in the member's proof file. That last one is the point: a number nobody can
back up gets exposed on the first call.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmark as bm  # noqa: E402
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Upwork cuts a title at 70 characters: a real profile's title came back from the
# connector cut off at exactly 70 (measured 12 September 2026).
TITLE_MAX = 70
# Upwork's overview field limit, as its form states it.
OVERVIEW_MAX = 5000
SKILLS_MAX = 20
# Checks that read fields a draft does not contain.
NOT_FOR_DRAFTS = {'certificates', 'rate_set', 'complete'}


def section(text, name):
    m = re.search(rf'^## {re.escape(name)}\b[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return m.group(1) if m else ''


def fenced(block):
    m = re.search(r'```[a-z]*\n(.*?)\n```', block, re.S)
    return m.group(1).strip() if m else ''


def items(block):
    return [re.sub(r'\s*\(was:.*\)\s*$', '', l[2:].strip())
            for l in block.splitlines() if l.startswith('- ')]


def parse(text):
    portfolio = items(section(text, 'Portfolio titles'))
    return {
        'name': '', 'title': fenced(section(text, 'Title')),
        'overview': fenced(section(text, 'Overview')), 'rate': None,
        'skills': items(section(text, 'Skills')), 'employment': [], 'education': [],
        'languages': [], 'aggregates': {}, 'portfolio': portfolio or None, 'certificates': None,
    }


def unproven_numbers(draft, proof_text):
    """Every result number in title, overview and portfolio titles that the proof file lacks."""
    missing = set()
    for text in [draft['title'], draft['overview']] + (draft['portfolio'] or []):
        for m in pc.RESULT_NUMBER.finditer(text):
            core = re.search(r'\d[\d.,]*', m.group(0)).group(0).rstrip('.,')
            if not re.search(r'(?<![\d.,])' + re.escape(core) + r'(?!\d)', proof_text):
                missing.add(m.group(0).strip())
    return sorted(missing)


def problems(draft, proof_text, targets):
    found = []
    if not draft['title']:
        found.append('no title in a fenced block under "## Title"')
    if not draft['overview']:
        found.append('no overview in a fenced block under "## Overview"')
    if found:
        return found

    skip = set(NOT_FOR_DRAFTS)
    if draft['portfolio'] is None:
        skip |= {'portfolio_count', 'portfolio_outcomes'}
    for r in pc.run_checks(draft):
        if r['id'] not in skip and not r['passed']:
            found.append(f'{r["label"]}: {r["detail"]}')

    if len(draft['title']) > TITLE_MAX:
        found.append(f'title is {len(draft["title"])} characters, Upwork cuts at {TITLE_MAX}')
    if len(draft['overview']) > OVERVIEW_MAX:
        found.append(f'overview is {len(draft["overview"])} characters, the field holds {OVERVIEW_MAX}')
    if len(draft['skills']) > SKILLS_MAX:
        found.append(f'{len(draft["skills"])} skills, Upwork takes {SKILLS_MAX}')
    if re.search(r'\*\*|^#', draft['overview'], re.M):
        found.append('overview uses markdown, which Upwork shows as raw symbols')
    for field in ('title', 'overview'):
        if chr(0x2014) in draft[field]:  # the em-dash, written so this file carries none
            found.append(f'{field} has an em-dash')

    for n in unproven_numbers(draft, proof_text):
        found.append(f'"{n}" is not in your proof file: prove it there or cut it')

    metrics = bm.metrics(draft)
    for key, entry in (targets or {}).items():
        v = bm.verdict(metrics.get(key), entry['low'], entry['high'], entry.get('kind', 'band'))
        if v in ('below', 'above'):
            found.append(f'{entry["label"]} is {metrics.get(key)}, the benchmark range is '
                         f'{entry["low"]} to {entry["high"]} {entry["unit"]}')
    return found


def cmd_check(args):
    draft = parse(pathlib.Path(args.file).read_text(encoding='utf-8'))
    proof = pathlib.Path(args.proof)
    proof_text = proof.read_text(encoding='utf-8') if proof.is_file() else ''
    targets_file = pathlib.Path(args.targets)
    targets = (json.loads(targets_file.read_text(encoding='utf-8')).get('targets')
               if targets_file.is_file() else None)
    found = problems(draft, proof_text, targets)
    for f in found:
        print(f'FAIL  {f}')
    if not targets:
        print('NOTE  no benchmark targets found; run /benchmark for the length checks')
    print(f'\n{"PASS" if not found else f"{len(found)} problem(s)."}  '
          f'title {len(draft["title"])} characters, overview {len(draft["overview"].split())} words, '
          f'{len(draft["skills"])} skills')
    return 1 if found else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('check')
    p.add_argument('file')
    p.add_argument('--proof', default=str(ROOT / 'context' / 'proof.md'))
    p.add_argument('--targets', default=str(ROOT / 'data' / 'targets.json'))
    p.set_defaults(func=cmd_check)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
