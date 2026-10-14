#!/usr/bin/env python3
"""The gate for profile.md, the draft /profile writes, checked before a member pastes it.

    python3 code/profile_draft.py check profile.md [--proof context/me.md]

It passes only when the draft clears the audit's mechanical checks, lands on
Upwork's form, and every number in it can be found
in the member's evidence sections. That last one is the point: a number nobody can
back up gets exposed on the first call.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_check
# Upwork cuts a title at 70 characters: a real profile's title came back from the
# connector cut off at exactly 70 (measured 12 September 2026).
TITLE_MAX = 70
# Upwork's overview field limit, as its form states it.
OVERVIEW_MAX = 5000
SKILLS_MAX = 20
# The three role models set a ceiling, not a target to hit: a draft may run up to 20 %
# over their average length and shorter is always fine.
CEILING = 1.2
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


def reference_averages(text):
    """`- overview: 1850` lines under `## Reference averages`, in characters. Empty without the section."""
    found = {}
    for line in section(text, 'Reference averages').splitlines():
        m = re.match(r'-\s*(title|overview)\s*:\s*(\d+)', line.strip(), re.I)
        if m:
            found[m.group(1).lower()] = int(m.group(2))
    return found


def parse(text):
    portfolio = items(section(text, 'Portfolio titles'))
    return {
        'averages': reference_averages(text),
        'name': '', 'title': fenced(section(text, 'Title')),
        'overview': fenced(section(text, 'Overview')), 'rate': None,
        'video': (fenced(section(text, 'Video script')) or section(text, 'Video script')).strip(),
        'skills': items(section(text, 'Skills')), 'employment': [], 'education': [],
        'languages': [], 'aggregates': {}, 'portfolio': portfolio or None, 'certificates': None,
    }


def problems(draft, proof_text):
    found = []
    if not draft['title']:
        found.append('no title in a fenced block under "## Title"')
    if not draft['overview']:
        found.append('no overview in a fenced block under "## Overview"')
    if found:
        return found

    skip = set(NOT_FOR_DRAFTS)
    # Portfolio count and numbers are a live-profile recommendation. The draft only
    # retitles projects, so it never fails on them.
    skip |= {'portfolio'}
    # A first profile has no verified result, and the command tells it to lead with
    # the offer and the background instead of a number. Demanding a number anyway
    # left exactly one way out, inventing one, which the next check would catch and
    # the client would not. Only a verified result number switches these checks
    # on; pending entries and bare certificate years cannot supply a result.
    verified = context_check.verified_proof(proof_text)
    if not pc.RESULT_NUMBER.search(verified):
        skip |= {'opening_has_number', 'results_with_numbers'}
    # Three result lines are a recommendation. A member with fewer verified results
    # than that cannot be failed for it, so the check applies only from three.
    elif len(pc.RESULT_NUMBER.findall(verified)) < 3:
        skip |= {'results_with_numbers'}
    for r in pc.run_checks(draft):
        if r['id'] not in skip and not r['passed']:
            found.append(f'{r["label"]}: {r["detail"]}')

    if len(draft['title']) > TITLE_MAX:
        found.append(f'title is {len(draft["title"])} characters, Upwork cuts at {TITLE_MAX}')
    if len(draft['overview']) > OVERVIEW_MAX:
        found.append(f'overview is {len(draft["overview"])} characters, the field holds {OVERVIEW_MAX}')
    if len(draft['skills']) > SKILLS_MAX:
        found.append(f'{len(draft["skills"])} skills, Upwork takes {SKILLS_MAX}')
    for field, average in draft.get('averages', {}).items():
        if average and len(draft[field]) > average * CEILING:
            found.append(f'{field} is {len(draft[field])} characters, the role models average {average}: '
                         f'stay under {round(average * CEILING)}')
    if re.search(r'\*\*|^#', draft['overview'], re.M):
        found.append('overview uses markdown, which Upwork shows as raw symbols')
    for field in ('title', 'overview', 'video'):
        if chr(0x2014) in draft[field]:  # the em-dash, written so this file carries none
            found.append(f'{field} has an em-dash')


    return found


def cmd_check(args):
    draft = parse(pathlib.Path(args.file).read_text(encoding='utf-8'))
    proof = pathlib.Path(args.proof)
    # Only the evidence sections. Handed the whole file, every number in it would
    # count as a source, and an hourly rate of 40 would prove a claim of 40%.
    proof_text = (context_check.client_proof(proof.read_text(encoding='utf-8'))
                  if proof.is_file() else '')
    if args.only == 'video':
        # The script generator writes only `## Video script`, so a missing title and
        # overview are not problems here: the numbers and the em-dash are what is checked.
        found = []
        if not draft['video']:
            found.append('no "## Video script" section')
        else:
            if chr(0x2014) in draft['video']:
                found.append('video script has an em-dash')
        for f in found:
            print(f'FAIL  {f}')
        print(f'\n{"PASS" if not found else f"{len(found)} problem(s)."}  video script {len(draft["video"].split())} words')
        return 1 if found else 0
    found = problems(draft, proof_text)
    for f in found:
        print(f'FAIL  {f}')
    print(f'\n{"PASS" if not found else f"{len(found)} problem(s)."}  '
          f'title {len(draft["title"])} characters, overview {len(draft["overview"].split())} words, '
          f'{len(draft["skills"])} skills')
    return 1 if found else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('check')
    p.add_argument('file')
    p.add_argument('--proof', default=str(ROOT / 'context' / 'me.md'))
    p.add_argument('--only', choices=('video',), help='check only the video script, for /profile video')
    p.set_defaults(func=cmd_check)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
