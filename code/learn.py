#!/usr/bin/env python3
"""What has actually worked, counted from your own pipeline.

    python3 code/learn.py report            what each dimension produced, in words
    python3 code/learn.py lessons           write data/lessons.json for /find-jobs
    python3 code/learn.py report --min 5    lower the sample gate, deliberately

This counts outcomes; it does not learn anything. Every number is a share of your own
applications, and a share of four applications is not a finding. Below the sample gate a
dimension is reported as too thin and never reaches the ranking, because a rule built on
three data points costs more Connects than it saves.

The ladder per lead comes from its own history: applied, then replied, then offer, then
won. A lead that skipped a stage still counts for the stages it reached.
"""
import argparse
import collections
import functools
import json
import os
import pathlib
import re

import pipeline

ME = pathlib.Path(os.environ.get('BLUEPRINT_ME') or pathlib.Path(__file__).resolve().parents[1] / 'context' / 'me.md')
MIN_APPLIED = 8          # below this a dimension is noise, not a lesson
MAX_POINTS = 5           # the most a lesson may move a score, in either direction
STAGES = ('applied', 'replied', 'offer', 'won')


def reached(job, stage):
    """True when this lead ever reached that stage, from its history."""
    if any(event.get('status') == stage for event in job.get('history') or []):
        return True
    return job.get('status') == stage


def tracks(job):
    """Every source slug this lead came from. `found_via` is a list, not a string."""
    found = job.get('found_via')
    if isinstance(found, str):
        found = [found]
    named = [str(slug) for slug in (found or []) if str(slug).strip()]
    return named or ['unknown']


def branch(slug):
    """Which kind of search found it: Upwork's own feed, a theme, or a client tool."""
    if slug.startswith('recommended'):
        return 'recommendation'
    if slug.startswith('tool-'):
        return "client's own tool"
    return 'search theme'


@functools.lru_cache(maxsize=1)
def picked_branches():
    """The member's branches from `**Branches you picked:**`, keyed by the slug of their track.

    `/find-jobs` labels each branch's track with the branch name, so the file a lead was
    found in (`query-<slug>`) names its branch.
    """
    try:
        text = ME.read_text(encoding='utf-8')
    except OSError:
        return {}
    match = re.search(r'^\*\*Branches you picked:\*\*[ \t]*(.*)$', text, re.M | re.I)
    if not match or 'not answered yet' in match.group(1).lower():
        return {}
    names = [name.strip() for name in re.split(r'\s*[·|]\s*', match.group(1)) if name.strip()]
    return {re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-'): name for name in names}


def dimensions(job):
    """Every bucket this lead belongs to, as (dimension, value) pairs."""
    out = []
    for slug in tracks(job):
        out.append(('found via', slug))
        out.append(('search branch', branch(slug)))
        picked = picked_branches().get(re.sub(r'^(?:query|title|search)-', '', slug))
        if picked:
            out.append(('your branch', picked))
    client = job.get('client') or {}
    if client.get('country'):
        out.append(('client country', str(client['country'])))
    spent = str(client.get('spent') or client.get('total_spent') or '').strip()
    out.append(('client history', 'has spent' if spent and spent not in ('$0', '$0.00') else 'no spend recorded'))
    if job.get('job_type'):
        out.append(('job type', str(job['job_type'])))
    level = (job.get('details') or {}).get('experience_level')
    if level:
        out.append(('client asked for', str(level)))
    score = job.get('score')
    if isinstance(score, (int, float)):
        out.append(('our own score', f'{int(score) // 10 * 10} to {int(score) // 10 * 10 + 9}'))
    return out


def tally(jobs):
    counts = collections.defaultdict(lambda: collections.Counter())
    for job in jobs:
        if not reached(job, 'applied'):
            continue
        for key in dimensions(job):
            counts[key]['applied'] += 1
            for stage in STAGES[1:]:
                if reached(job, stage):
                    counts[key][stage] += 1
    return counts


def lessons(counts, min_applied=MIN_APPLIED):
    """Only the buckets with enough applications behind them, as score nudges."""
    strong = {key: c for key, c in counts.items() if c['applied'] >= min_applied}
    if not strong:
        return []
    overall_replied = sum(c['replied'] for c in strong.values())
    overall_applied = sum(c['applied'] for c in strong.values())
    base = overall_replied / overall_applied if overall_applied else 0
    out = []
    for (dimension, value), c in sorted(strong.items(), key=lambda kv: -kv[1]['applied']):
        rate = c['replied'] / c['applied']
        points = round(MAX_POINTS * (rate - base) / base) if base else 0
        points = max(-MAX_POINTS, min(MAX_POINTS, points))
        if not points:
            continue
        out.append({'dimension': dimension, 'value': value, 'applied': c['applied'],
                    'replied': c['replied'], 'reply_rate': round(rate, 3), 'points': points})
    return out


DECISIONS = (pathlib.Path(os.environ.get('BLUEPRINT_DATA') or
             pathlib.Path(__file__).resolve().parents[1] / 'data') / 'decisions.jsonl')


def rejections(path=None):
    """Every candidate the gate turned down, kept by `jobs.py score`."""
    path = path or DECISIONS
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def branch_yield(rows, jobs):
    """Per search branch: how many it produced, and how many survived the gate.

    A branch that keeps producing candidates and never one that passes is the
    clearest thing this pipeline can say about its own keywords, and it says it
    from the first run instead of after eight applications.
    """
    produced = collections.Counter()
    for row in rows:
        for name in tracks(row):
            produced[name] += 1
    passed = collections.Counter()
    for job in jobs:
        for name in tracks(job):
            passed[name] += 1
    return [(name, passed.get(name, 0), passed.get(name, 0) + count)
            for name, count in produced.most_common()]


def disagreements(jobs):
    """Leads the gate let through and the member then turned down, with the reason.

    This is the only place the score can be told it was wrong, so it is worth more
    per row than anything the counting produces.
    """
    out = []
    for job in jobs:
        if job.get('status') != 'skipped':
            continue
        note = str(job.get('notes') or '')
        out.append((int(job.get('score') or 0), job.get('title', '')[:60],
                    note.replace('not a fit:', '').strip()))
    return sorted(out, reverse=True)


def cmd_report(args):
    jobs = pipeline.load()
    counts = tally(jobs)
    applied = sum(1 for j in jobs if reached(j, 'applied'))
    print(f'{applied} of {len(jobs)} leads were applied to.')

    turned_down = rejections()
    if turned_down:
        print(f'\nThe gate turned down {len(turned_down)} candidate(s). Per search branch, '
              f'how many reached your pipeline:')
        for name, passed, seen in branch_yield(turned_down, jobs):
            verdict = 'nothing passes, stop spending calls on it' if not passed else ''
            print(f'  {name}: {passed} of {seen}' + (f'  {verdict}' if verdict else ''))

    wrong = disagreements(jobs)
    if wrong:
        print(f'\nYou turned down {len(wrong)} lead(s) the score let through. '
              f'Each one is the score being told it was wrong:')
        for score, title, why in wrong[:8]:
            print(f'  scored {score:3d}  {title}  · {why or "no reason recorded"}')

    if applied < args.min:
        print(f'\nOutcomes are still too thin to weight: a dimension needs {args.min} '
              f'applications and the whole pipeline has {applied}. The branch and disagreement '
              f'lines above do not wait for that.')
        return 0
    for (dimension, value), c in sorted(counts.items(), key=lambda kv: -kv[1]['applied']):
        verdict = 'signal' if c['applied'] >= args.min else 'too thin'
        print(f'{dimension}: {value} | applied {c["applied"]}, replied {c["replied"]}, '
              f'offer {c["offer"]}, won {c["won"]} | {verdict}')
    learned = lessons(counts, args.min)
    print(f'\n{len(learned)} lesson(s) strong enough to move a score, capped at '
          f'{MAX_POINTS} points either way.')
    for lesson in learned:
        print(f'  {lesson["dimension"]} "{lesson["value"]}": {lesson["points"]:+d} '
              f'({lesson["replied"]}/{lesson["applied"]} replied)')
    return 0


def cmd_lessons(args):
    jobs = pipeline.load()
    learned = lessons(tally(jobs), args.min)
    path = pipeline.data_dir() / 'lessons.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'written_at': pipeline.now_iso(), 'min_applied': args.min,
               'max_points': MAX_POINTS, 'lessons': learned}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(learned)} lesson(s) written to {path}.')
    return 0


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--min', type=int, default=MIN_APPLIED,
                        help=f'applications a dimension needs before it counts (default {MIN_APPLIED})')
    parser = argparse.ArgumentParser(description=__doc__, parents=[common],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('report', parents=[common],
                   help='what each dimension produced').set_defaults(func=cmd_report)
    sub.add_parser('lessons', parents=[common],
                   help='write data/lessons.json').set_defaults(func=cmd_lessons)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
