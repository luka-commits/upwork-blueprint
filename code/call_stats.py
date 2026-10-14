#!/usr/bin/env python3
"""Read jobs/<id>/call.md: Duration: seconds, Member: name, then Speaker: line turns."""
import argparse
import json
import pathlib
import re
import subprocess
import sys

import pipeline

WORDS = re.compile(r"\b[\w]+(?:['’-]\w+)*\b")


def analyze(text, member=None):
    duration = None
    call_at = None
    turns = []
    unlabelled = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('call at:'):
            call_at = pipeline.parse_verified_timestamp(line.split(':', 1)[1].strip())
            continue
        match = re.fullmatch(r'Duration:\s*(\d+(?:\.\d+)?)\s*(?:seconds|s)?', line, re.I)
        if match:
            duration = float(match.group(1))
            continue
        match = re.fullmatch(r'Member:\s*(.+)', line, re.I)
        if match:
            member = member or match.group(1).strip()
            continue
        match = re.fullmatch(r'([^:]{1,80}):\s*(.+)', line)
        if match:
            turns.append((match.group(1).strip(), match.group(2)))
        else:
            unlabelled = True
    result = {'duration_s': duration}
    if call_at:
        result['call_at'] = call_at
    if duration is None:
        result['note'] = 'Duration is unavailable. Preserve Duration: seconds from the recording.'
    if unlabelled or not turns:
        result['note'] = 'No complete speaker labels. Duration only; talk share and questions skipped.'
        return result
    if not member or member.casefold() not in {name.casefold() for name, _ in turns}:
        result['note'] = 'Member label is missing. Duration only; preserve Member: name from the recording.'
        return result
    words = {'member': 0, 'client': 0}
    questions = {'member': 0, 'client': 0}
    for name, turn in turns:
        side = 'member' if name.casefold() == member.casefold() else 'client'
        words[side] += len(WORDS.findall(turn))
        questions[side] += turn.count('?')
    total = sum(words.values())
    result.update(talk_share_pct=round(100 * words['member'] / total, 1) if total else None,
                  question_counts=questions, talk_share_basis='words')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('--member')
    args = parser.parse_args(argv)
    pipeline.find(pipeline.load(), args.job_id)
    path = pipeline.jobs_dir() / args.job_id / 'call.md'
    if not path.is_file():
        print(f'Call stats skipped: {path} is missing. Connect a recorder and pull its transcript.')
        return 0
    result = analyze(path.read_text(encoding='utf-8'), args.member)
    call_at = result.pop('call_at', None)
    if call_at:
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('pipeline.py')),
                        'observe', args.job_id, 'call_held', call_at, '--source', 'recorder', '--verified'],
                       text=True, check=True)
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('pipeline.py')),
                    'record', args.job_id, '--file', '-'],
                   input=json.dumps({'call_stats': result}), text=True, check=True)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
