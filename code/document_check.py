#!/usr/bin/env python3
"""The gate for the two documents a won deal rests on: the proposal and the project.

The model writes decisions and client-facing copy. This script checks the parts
that should not depend on prose judgement:

    python3 code/document_check.py check <proposal|project> <job_id>

It reads pipeline state but never writes it. Commands change stages only through
code/pipeline.py, the pipeline's single writer.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402


ARTIFACTS = {
    'proposal': ('proposal.md', (
        '## Outcome', '## Scope', '## Not included', '## Milestones',
        '## Timing', '## Price and payment', '## Client inputs',
        '## Acceptance', '## Communication', '## Next step')),
    'project': ('project.md', (
        '## Contract baseline', '## Outcome', '## Scope', '## Client inputs',
        '## Milestones', '## Communication', '## First actions')),
}

PLACEHOLDER = re.compile(r'(?:\bTBD\b|\bTODO\b|\[insert\b|<[^>]+>)', re.I)


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    return 1


def off_upwork(text):
    """Contact details and invitations to move the conversation, as the letter gate reads them.

    The proposal is pasted into the Upwork chat, so it is bound by the same rule as a
    message: no way to reach the member off the platform before a contract exists.
    """
    import application_check  # noqa: E402  (same folder, imported where it is used)
    return [problem.replace('in the letter', 'in the proposal').replace('the letter asks', 'the proposal asks')
            for problem in application_check.pc_contacts(text)]


def validate_artifact(kind, text):
    _, required = ARTIFACTS[kind]
    problems = []
    lines = text.splitlines()
    nonblank = [line.strip() for line in text.splitlines() if line.strip()]
    if len(nonblank) < 3:
        problems.append('the file needs the three opening lines')
    else:
        if not nonblank[0].startswith('# '):
            problems.append('the first line must name the document')
        if not re.match(r'^(?:Prepared|Reviewed|Updated|Recorded)\b', nonblank[1]):
            problems.append('the second line must say when it was made')
        if not nonblank[2].startswith('**Next:**'):
            problems.append('the third line must give the next action')
    for heading in required:
        try:
            start = next(index for index, line in enumerate(lines) if line.strip() == heading) + 1
        except StopIteration:
            problems.append(f'missing section: {heading}')
            continue
        end = next((index for index in range(start, len(lines))
                    if lines[index].strip().startswith('## ')), len(lines))
        if not any(line.strip() for line in lines[start:end]):
            problems.append(f'empty section: {heading}')
    if chr(0x2014) in text:
        problems.append('contains an em-dash')
    if PLACEHOLDER.search(text):
        problems.append('contains a placeholder')
    if kind == 'proposal':
        problems.extend(off_upwork(text))
    return problems


def cmd_check(args):
    if not any(j.get('id') == args.job_id for j in pipeline.load()):
        return abort(f'job "{args.job_id}" is not in the pipeline.')
    name, _ = ARTIFACTS[args.kind]
    path = pipeline.jobs_dir() / args.job_id / name
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return abort(f'{name} is missing for this job.')
    problems = validate_artifact(args.kind, text)
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print(f'PASS: {name} has every required section and no placeholders.')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Validate a proposal or project document.')
    check.add_argument('kind', choices=tuple(ARTIFACTS))
    check.add_argument('job_id')
    check.set_defaults(func=cmd_check)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
