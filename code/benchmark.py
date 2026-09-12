#!/usr/bin/env python3
"""The benchmark: the three strongest profiles in your profession, measured, turned into targets.

/benchmark saves every candidate profile it reads to data/benchmark/, then:

    python3 code/benchmark.py rank data/benchmark/*.json
    python3 code/benchmark.py measure <three profile files> [--you data/profile.json data/highlights.json] [--json]
    python3 code/benchmark.py check benchmark.md
    python3 code/benchmark.py prune [--hours 24]

A target is the average of the three, plus or minus a fifth: the average gets
you level, the gaps all three leave open get you past.
"""
import argparse
import datetime
import json
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'benchmark'
TARGETS_FILE = ROOT / 'data' / 'targets.json'
BADGES = {'top rated plus': 3, 'top rated': 2, 'rising talent': 1}
# band: land inside the range. min: at least the low end, more is fine.
# The hourly rate is never a target: a web-search sample skews toward cheaper
# markets, and "charge what they charge" would talk a member into a pay cut.
TARGETS = (
    ('title_chars', 'Title length', 'characters', 'band'),
    ('overview_words', 'Overview length', 'words', 'band'),
    ('numbered_lines', 'Result lines with a number', 'lines', 'min'),
    ('skills', 'Skills', 'skills', 'min'),
)
BAND = 0.2


def badge_rank(aggregates):
    return BADGES.get(str(aggregates.get('top_rated') or '').strip().lower(), 0)


def earnings_value(bucket):
    """"$100K+" -> 100000. Buckets are floors, so the value is a floor too."""
    m = re.search(r'\$\s*([\d.,]+)\s*([KkMm]?)', str(bucket or ''))
    if not m:
        return 0
    value = float(m.group(1).replace(',', ''))
    return int(value * {'k': 1_000, 'm': 1_000_000}.get(m.group(2).lower(), 1))


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def metrics(p):
    overview = p['overview']
    return {
        'title_chars': len(p['title']),
        'title_blocks': len([b for b in p['title'].split('|') if b.strip()]),
        'overview_words': len(overview.split()),
        'numbered_lines': len([l for l in overview.splitlines() if pc.RESULT_NUMBER.search(l)]),
        'structured_lines': pc.structured_lines(overview),
        'skills': len(p['skills']),
        'rate': float(p['rate']) if p['rate'] else None,
        'opens_with_number': bool(pc.RESULT_NUMBER.search(overview[:pc.OPENING])),
        'opens_with_greeting': bool(pc.GREETING.search(next(
            (l for l in overview.splitlines() if l.strip()), ''))),
        'closes_with_ask': bool(pc.ASK.search(overview[-400:])),
        'keyword_line': pc.has_keyword_line(overview),
    }


def summary(path):
    p = pc.normalize(load(path))
    agg = p['aggregates']
    return {
        'file': str(path),
        'name': p['name'],
        'badge': agg.get('top_rated') or 'none',
        'earnings': agg.get('totalEarnings') or 'none shown',
        'reviews': agg.get('totalFeedback') or 0,
        'jobs': agg.get('totalJobs') or 0,
        'metrics': metrics(p),
    }


def strength(s):
    return (badge_rank({'top_rated': s['badge']}), earnings_value(s['earnings']), s['reviews'], s['jobs'])


def cmd_rank(args):
    rows = sorted((summary(f) for f in args.files), key=strength, reverse=True)
    for i, s in enumerate(rows, 1):
        print(f'{i}. {s["name"]:<20} {s["badge"]:<15} {s["earnings"]:<12} '
              f'{s["reviews"]} reviews, {s["jobs"]} jobs   {s["file"]}')


def band(values):
    avg = statistics.mean(values)
    return round(avg * (1 - BAND), 1), round(avg, 1), round(avg * (1 + BAND), 1)


def verdict(value, low, high, kind='band'):
    if value is None:
        return 'not set'
    if value < low:
        return 'below'
    if value > high and kind == 'band':
        return 'above'
    return 'on target'


def cmd_measure(args):
    if len(args.files) != 3:
        print('ABORT: measure takes exactly three profiles.', file=sys.stderr)
        return 1
    top = [summary(f) for f in args.files]
    you = None
    if args.you:
        mine = pc.normalize(load(args.you[0]), load(args.you[1]) if len(args.you) > 1 else None)
        you = metrics(mine)
    targets = {}
    for key, label, unit, kind in TARGETS:
        values = [s['metrics'][key] for s in top if s['metrics'][key] is not None]
        if len(values) < 2:
            continue
        low, avg, high = band(values)
        entry = {'label': label, 'unit': unit, 'kind': kind, 'low': low, 'average': avg, 'high': high}
        if you is not None:
            entry['you'] = you[key]
            entry['verdict'] = verdict(you[key], low, high, kind)
        targets[key] = entry
    shared = [k for k in ('opens_with_number', 'closes_with_ask', 'keyword_line')
              if all(s['metrics'][k] for s in top)]
    rates = [s['metrics']['rate'] for s in top]
    result = {'measured_at': datetime.date.today().isoformat(), 'profiles': top,
              'targets': targets, 'all_three_do': shared, 'rates': rates,
              'you': you}
    # The targets outlive the raw profiles (pruned after a day): /profile gates its
    # draft against this file. Only our own numbers go in, never their text.
    TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_FILE.write_text(json.dumps({'measured_at': result['measured_at'], 'targets': targets},
                                       indent=2), encoding='utf-8')
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    for s in top:
        print(f'{s["name"]}: {s["badge"]}, {s["earnings"]}, {s["reviews"]} reviews, {s["jobs"]} jobs')
    print()
    for t in targets.values():
        mine = f'   you: {t["you"]} ({t["verdict"]})' if 'you' in t else ''
        print(f'{t["label"]}: {t["low"]} to {t["high"]} {t["unit"]} (average {t["average"]}){mine}')
    print('\nAll three:', ', '.join(shared) or 'no shared pattern among the three checked')
    print('Their hourly rates:', ', '.join(f'${r:g}' for r in rates if r is not None),
          '(context only, never a target)')
    return 0


def cmd_check(args):
    """The gate: benchmark.md holds three measured profiles and a targets section, or it fails."""
    text = pathlib.Path(args.file).read_text(encoding='utf-8')
    problems = []
    blocks = re.split(r'^## Profile ', text, flags=re.M)[1:]
    if len(blocks) != 3:
        problems.append(f'{len(blocks)} profile block(s), need exactly 3 headed "## Profile "')
    for i, b in enumerate(blocks, 1):
        if '**Measured:**' not in b:
            problems.append(f'profile {i} has no **Measured:** line with its date and numbers')
    if not re.search(r'^# Targets', text, flags=re.M):
        problems.append('no "# Targets" section')
    else:
        section = re.split(r'^# ', text.split('# Targets', 1)[1], flags=re.M)[0]
        lines = [l for l in section.splitlines() if l.startswith('**') and re.search(r'\d', l)]
        if len(lines) < 4:
            problems.append(f'{len(lines)} target line(s) with numbers, need at least 4')
    if '|' in text and re.search(r'^\s*\|.*\|\s*$', text, flags=re.M):
        problems.append('contains a table; members read this on a phone')
    for p in problems:
        print(f'FAIL  {p}')
    print('PASS  benchmark.md' if not problems else f'\n{len(problems)} problem(s).')
    return 1 if problems else 0


def cmd_prune(args):
    """Deletes raw candidate profiles older than --hours. benchmark.md keeps the measurements."""
    if not RAW.is_dir():
        print('Nothing to prune.')
        return 0
    cutoff = datetime.datetime.now().timestamp() - args.hours * 3600
    old = [f for f in RAW.glob('*.json') if f.stat().st_mtime < cutoff]
    for f in old:
        f.unlink()
    print(f'{len(old)} raw profile file(s) older than {args.hours}h removed.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('rank', help='Candidates, strongest first.')
    p.add_argument('files', nargs='+')
    p.set_defaults(func=cmd_rank)
    p = sub.add_parser('measure', help='Three profiles into targets, optionally against yours.')
    p.add_argument('files', nargs='+')
    p.add_argument('--you', nargs='+', metavar='FILE')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_measure)
    p = sub.add_parser('check', help='Gate for benchmark.md.')
    p.add_argument('file')
    p.set_defaults(func=cmd_check)
    p = sub.add_parser('prune', help='Drop raw candidate files older than 24h.')
    p.add_argument('--hours', type=int, default=24)
    p.set_defaults(func=cmd_prune)
    args = ap.parse_args(argv)
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
