#!/usr/bin/env python3
"""Validate the machine file that /reply writes for the cockpit.

    python3 code/replies.py check <job_id>

The model chooses the words. This script checks the fixed contract around them:
valid JSON, two or three labeled non-empty options, distinct text and no
em-dashes. It never sends or changes a reply.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (jobs_dir only)

ID = re.compile(r'^[0-9]{6,25}$')


def validate(value):
    problems = []
    if not isinstance(value, dict):
        return ['the root must be an object']
    if not isinstance(value.get('generated_at'), str) or not value['generated_at'].strip():
        problems.append('generated_at must be a non-empty string')
    drafts = value.get('drafts')
    if not isinstance(drafts, list) or len(drafts) not in (2, 3):
        problems.append('drafts must contain two or three options')
        return problems
    texts = []
    for index, draft in enumerate(drafts, 1):
        if not isinstance(draft, dict):
            problems.append(f'draft {index} must be an object')
            continue
        label, text = draft.get('label'), draft.get('text')
        if not isinstance(label, str) or not label.strip():
            problems.append(f'draft {index} needs a label')
        if not isinstance(text, str) or not text.strip():
            problems.append(f'draft {index} needs reply text')
        elif '\u2014' in text:
            problems.append(f'draft {index} contains an em-dash')
        else:
            texts.append(text.strip())
    if len(texts) != len(set(texts)):
        problems.append('draft texts must be meaningfully different')
    return problems


def cmd_check(args):
    if not ID.fullmatch(args.job_id):
        print('ABORT: that job id is not valid.', file=sys.stderr)
        return 1
    file = pipeline.jobs_dir() / args.job_id / 'replies.json'
    try:
        value = json.loads(file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print('ABORT: replies.json is missing.', file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f'ABORT: replies.json is not valid JSON at line {exc.lineno}.', file=sys.stderr)
        return 1
    problems = validate(value)
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print(f'PASS: {len(value["drafts"])} reply drafts are valid.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Validate jobs/<id>/replies.json.')
    check.add_argument('job_id')
    check.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
