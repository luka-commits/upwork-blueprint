#!/usr/bin/env python3
"""Read jobs/<id>/call.md: Duration: seconds, Member: name, then Speaker: line turns."""
import argparse
import datetime
import json
import math
import pathlib
import re
import subprocess
import sys

import pipeline

WORDS = re.compile(r"\b[\w]+(?:['’-]\w+)*\b")


def normalize_transcript(pages, call_at=None, duration_s=None, member=None, complete=None, language=None):
    """Turn all get_full_transcript pages into labelled call.md, never raw JSON.

    Pages may be transcript strings, segment lists, or objects carrying
    ``segments``/``transcript``. Segments are ``Speaker: words`` strings or
    ``{speaker, text}`` objects. Callers must fetch every offset before saving.
    """
    if not isinstance(pages, list) or not pages:
        raise ValueError('Transcript needs a nonempty list of pages.')
    headers, turns = [], []
    if complete is not None:
        if not isinstance(complete, bool):
            raise ValueError('Complete needs a verified boolean.')
        headers.append('Complete: ' + ('yes' if complete else 'no'))
    if language is not None:
        if not isinstance(language, str) or not language.strip() or '\n' in language or '\r' in language:
            raise ValueError('Language needs one verified language label.')
        headers.append(f'Language: {language.strip()}')
    if call_at is not None:
        stamp = pipeline.parse_verified_timestamp(call_at)
        if not stamp:
            raise ValueError('Call at needs a nonfuture ISO timestamp with a timezone.')
        headers.append(f'Call at: {stamp}')
    if duration_s is not None:
        if (not isinstance(duration_s, (int, float)) or isinstance(duration_s, bool)
                or not math.isfinite(duration_s) or duration_s < 0):
            raise ValueError('Duration needs nonnegative finite seconds.')
        headers.append(f'Duration: {duration_s:g}')
    if member is not None:
        if not isinstance(member, str) or not member.strip() or ':' in member or '\n' in member or '\r' in member:
            raise ValueError('Member needs one speaker name.')
        headers.append(f'Member: {member.strip()}')
    for page in pages:
        if isinstance(page, dict):
            page = page.get('segments', page.get('transcript'))
        segments = page.splitlines() if isinstance(page, str) else page
        if not isinstance(segments, list):
            raise ValueError('Transcript page needs segments or a transcript.')
        for segment in segments:
            if isinstance(segment, str):
                if not segment.strip():
                    continue
                match = re.fullmatch(r'([^:]{1,80}):\s*(.+)', segment.strip())
                if not match:
                    raise ValueError('Every transcript segment needs a speaker label.')
                speaker, words = match.groups()
            elif isinstance(segment, dict):
                speaker, words = segment.get('speaker'), segment.get('text')
            else:
                raise ValueError('Transcript segment needs labelled text.')
            if (not isinstance(speaker, str) or not speaker.strip() or ':' in speaker
                    or len(speaker.strip()) > 80 or '\n' in speaker or '\r' in speaker
                    or not isinstance(words, str) or not words.strip()):
                raise ValueError('Transcript segment needs a speaker name and words.')
            turns.append(f'{speaker.strip()}: {" ".join(words.split())}')
    if not turns:
        raise ValueError('Transcript contains no speaker turns.')
    return '\n'.join(headers + [''] + turns) + '\n'


def analyze(text, member=None):
    duration = None
    call_at = None
    turns = []
    unlabelled = False
    member_header_seen = False
    complete, language = None, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('complete:'):
            raw = line.split(':', 1)[1].strip().lower()
            complete = True if raw in ('yes', 'full', 'true') else False if raw in ('no', 'false', 'partial') else None
            continue
        if line.lower().startswith('language:'):
            language = line.split(':', 1)[1].strip()
            continue
        if line.lower().startswith('call at:'):
            call_at = pipeline.parse_verified_timestamp(line.split(':', 1)[1].strip())
            continue
        match = re.fullmatch(r'Duration:\s*(\d+(?:\.\d+)?)\s*(?:seconds|s)?', line, re.I)
        if match:
            duration = float(match.group(1))
            continue
        match = re.fullmatch(r'Member:\s*(.+)', line, re.I)
        if match and not member_header_seen and not turns:
            member = member or match.group(1).strip()
            member_header_seen = True
            continue
        match = re.fullmatch(r'([^:]{1,80}):\s*(.+)', line)
        if match:
            turns.append((match.group(1).strip(), match.group(2)))
        else:
            unlabelled = True
    result = {'duration_s': duration, 'transcript_complete': complete, 'language': language}
    if member:
        result['member_attributed'] = member.casefold() in {name.casefold() for name, _ in turns}
    if call_at:
        result['call_at'] = call_at
        if duration is not None:
            ended = pipeline.parse_verified_timestamp((datetime.datetime.fromisoformat(call_at) + datetime.timedelta(seconds=duration)).isoformat())
            if ended:
                result['call_ended_at'] = ended
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
    parser.add_argument('--transcript-json', help='All get_full_transcript pages as a JSON list, path or - for stdin.')
    parser.add_argument('--call-at')
    parser.add_argument('--duration-s', type=float)
    parser.add_argument('--complete', choices=('yes', 'no'))
    parser.add_argument('--language')
    parser.add_argument('--source', choices=('upwork-meeting', 'recorder', 'member'), default='recorder')
    args = parser.parse_args(argv)
    args.job_id = pipeline.find(pipeline.load(), args.job_id)['id']
    path = pipeline.jobs_dir() / args.job_id / 'call.md'
    if args.transcript_json:
        raw = sys.stdin.read() if args.transcript_json == '-' else pathlib.Path(args.transcript_json).read_text(encoding='utf-8')
        try:
            text = normalize_transcript(json.loads(raw), args.call_at, args.duration_s, args.member,
                                        args.complete == 'yes' if args.complete else None, args.language)
        except (ValueError, TypeError) as error:
            parser.error(str(error))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    if not path.is_file():
        print(f'Call stats skipped: {path} is missing. Read the Upwork meeting transcript first, then eligible recorder evidence or notes.')
        return 0
    result = analyze(path.read_text(encoding='utf-8'), args.member)
    call_at = result.pop('call_at', None)
    call_ended_at = result.pop('call_ended_at', None)
    if call_at:
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('pipeline.py')),
                        'observe', args.job_id, 'call_held', call_at, '--source', args.source, '--verified'],
                       text=True, check=True)
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('pipeline.py')),
                    'record', args.job_id, '--file', '-'],
                   input=json.dumps({'call_stats': result, **({'call_ended_at': call_ended_at} if call_ended_at else {})}), text=True, check=True)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
