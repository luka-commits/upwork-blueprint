#!/usr/bin/env python3
"""Which search terms are worth their Connects, measured from one page each.

    python3 code/tracks.py measure data/search/*.json
    python3 code/tracks.py measure data/search/*.json --json
    python3 code/tracks.py measure data/search/*.json --log    also keep this run's counts

A search page holds the ten newest postings for its term. How many HOURS those ten
span is the density of that term: a live term returns ten postings from the last eight
hours, a dead one reaches back three weeks for the same ten. That one number decides
whether a term earns a call on every run, and it costs exactly one call per term to
learn.

Reads the files /find-jobs already saves, so measuring costs no extra Upwork calls.
Per term it reports the span, the postings per day that implies, how many postings state
a rate, the median number of proposals, and the share from clients with a verified
payment method.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import re
import statistics

FRESH_HOURS = 24
DATA = pathlib.Path(os.environ.get('BLUEPRINT_DATA') or pathlib.Path(__file__).resolve().parents[1] / 'data')
# Counts per term and run, never Upwork content, so prune leaves it alone.
TERMS_LOG = DATA / 'terms.jsonl'
DROP_AFTER_RUNS = 3      # runs in which a term found nothing of its own before it is proposed for removal


def load(path):
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    jobs = raw.get('jobs') if isinstance(raw, dict) else raw
    return jobs if isinstance(jobs, list) else []


def stamp(job):
    value = str(job.get('published_date') or job.get('created_date') or '')
    try:
        return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def rate_stated(job):
    budget = str(job.get('budget') or '')
    return bool(budget.strip())


def proposal_count(job):
    if isinstance(job.get('proposal_count'), int):
        return job['proposal_count']
    tier = str(job.get('proposals_tier') or job.get('proposals') or '')
    numbers = [int(n) for n in re.findall(r'\d+', tier)]
    return statistics.mean(numbers) if numbers else None


def measure(path):
    jobs = load(path)
    name = pathlib.Path(path).stem
    if not jobs:
        return {'term': name, 'postings': 0, 'span_hours': None, 'per_day': None,
                'fresh': 0, 'with_rate': 0, 'median_proposals': None, 'verified_clients': 0}
    stamps = sorted(s for s in (stamp(j) for j in jobs) if s)
    span = None
    per_day = None
    if len(stamps) >= 2:
        span = (stamps[-1] - stamps[0]).total_seconds() / 3600
        per_day = round(len(stamps) / span * 24, 1) if span > 0 else None
    proposals = [p for p in (proposal_count(j) for j in jobs) if p is not None]
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        'term': name,
        'postings': len(jobs),
        'span_hours': round(span, 1) if span is not None else None,
        'per_day': per_day,
        'fresh': sum(1 for s in stamps if (now - s).total_seconds() / 3600 <= FRESH_HOURS),
        'with_rate': sum(1 for j in jobs if rate_stated(j)),
        'median_proposals': round(statistics.median(proposals), 1) if proposals else None,
        'verified_clients': sum(1 for j in jobs
                                if str((j.get('client') or {}).get('verification_status') or '').upper() == 'VERIFIED'),
    }


def history(log=None):
    """Per term, how many logged runs and how many postings only it found."""
    log = log or TERMS_LOG
    seen = collections.defaultdict(lambda: {'runs': 0, 'only_here': 0})
    if log.is_file():
        for line in log.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen[row.get('term')]['runs'] += 1
            seen[row.get('term')]['only_here'] += int(row.get('only_here') or 0)
    return seen


def verdict(row):
    """What to do with this term on the next run."""
    past = row.get('history') or {}
    if past.get('runs', 0) >= DROP_AFTER_RUNS and not past.get('only_here'):
        return f'propose dropping: in {past["runs"]} runs it found nothing another term had not'
    if not row['postings']:
        return 'drop: the search returned nothing'
    if row['span_hours'] is None:
        return 'unknown: the postings carry no dates'
    if row['span_hours'] <= 24:
        return 'dense: as a branch\'s first term it is paged, as any other it gives its newest ten'
    if row['span_hours'] <= 24 * 7:
        return 'steady: one call per run is enough'
    return 'thin: check it weekly, not daily'


def posting_skills(path, keep=None):
    """Upwork's own skill names on the postings in one saved search page.

    With `keep`, only the postings whose id is in it: the reverse-engineering case,
    where one broad search is read, the jobs that actually fit are named, and their
    wording becomes the candidate terms. Upwork's vocabulary beats anyone's guess.
    """
    for job in load(path):
        if keep and str(job.get('id')) not in keep:
            continue
        for skill in job.get('skills') or []:
            name = str(skill).strip()
            if name:
                yield name


def covered(name, terms):
    """True when a current search term already carries this skill's wording."""
    plain = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
    for term in terms:
        other = re.sub(r'[^a-z0-9]+', ' ', term.lower()).strip()
        if plain and other and (plain in other or other in plain):
            return True
    return False


def cmd_skills(args):
    keep = {str(i) for i in (args.id or [])}
    counts = collections.Counter()
    for path in args.files:
        counts.update(posting_skills(path, keep))
    terms = args.term or []
    rows = [(name, n) for name, n in counts.most_common() if n >= args.min_count]
    fresh = [(name, n) for name, n in rows if not covered(name, terms)]
    if args.json:
        print(json.dumps({'skills': [{'skill': n, 'postings': c, 'covered': covered(n, terms)}
                                     for n, c in rows]}, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print(f'No skill appears on {args.min_count} or more of these postings.')
        return 0
    print(f'{len(rows)} skills on {args.min_count}+ postings, {len(fresh)} of them outside your current terms:')
    for name, n in rows:
        mark = '   ' if covered(name, terms) else ' * '
        print(f'{mark}{n:3}  {name}')
    print('\n* is a candidate term Upwork itself uses and your tracks do not. '
          'Measure it before keeping it: one call says whether it is dense.')
    return 0


def only_here(files):
    """Per file, how many of its postings no other file in this run returned.

    A narrow term beside a broad one (GEO beside SEO) may only repeat what the broad
    one found. The title search has no "without" word, so the overlap cannot be
    avoided in the search; it can only be counted and the term dropped on a yes.
    """
    ids = {pathlib.Path(f).stem: {str(j.get('id')) for j in load(f)} for f in files}
    return {name: len(mine - set().union(*(other for n, other in ids.items() if n != name)))
            for name, mine in ids.items()}


def cmd_measure(args):
    rows = [measure(p) for p in args.files]
    unique = only_here(args.files)
    past = history()
    for row in rows:
        row['only_here'] = unique.get(row['term'], 0)
        row['history'] = past.get(row['term'])
    if args.log:
        DATA.mkdir(exist_ok=True)
        stamp_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with TERMS_LOG.open('a', encoding='utf-8') as out:
            for row in rows:
                out.write(json.dumps({'at': stamp_now, 'term': row['term'], 'postings': row['postings'],
                                      'only_here': row['only_here'], 'per_day': row['per_day']}) + '\n')
        past = history()
        for row in rows:
            row['history'] = past.get(row['term'])
    rows.sort(key=lambda r: (r['span_hours'] is None, r['span_hours'] or 1e9))
    if args.json:
        print(json.dumps({'terms': [dict(r, verdict=verdict(r)) for r in rows]},
                         indent=2, ensure_ascii=False))
        return 0
    for row in rows:
        if not row['postings']:
            print(f'{row["term"]}: {verdict(row)}')
            continue
        span = f'{row["span_hours"]}h' if row['span_hours'] is not None else 'no dates'
        per_day = f'{row["per_day"]}/day' if row['per_day'] else 'unknown rate'
        proposals = f'{row["median_proposals"]} proposals' if row['median_proposals'] else 'proposals unknown'
        print(f'{row["term"]}: {row["postings"]} newest span {span} ({per_day}), '
              f'{row["fresh"]} within {FRESH_HOURS}h, {row["with_rate"]} state a rate, '
              f'median {proposals}, {row["verified_clients"]} verified clients, '
              f'{row["only_here"]} found by no other search | {verdict(row)}')
    dense = [r for r in rows if r['span_hours'] is not None and r['span_hours'] <= 24]
    print(f'\n{len(dense)} of {len(rows)} terms are dense: more than ten postings a day.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    m = sub.add_parser('measure', help='density per saved search page')
    m.add_argument('files', nargs='+')
    m.add_argument('--json', action='store_true', help='machine-readable output')
    m.add_argument('--log', action='store_true', help='append this run per term to data/terms.jsonl')
    m.set_defaults(func=cmd_measure)
    s = sub.add_parser('skills', help="Upwork's own skill names on the postings you already pulled")
    s.add_argument('files', nargs='+')
    s.add_argument('--term', action='append', help='a search term you already run; repeatable')
    s.add_argument('--id', action='append', help='only these job ids, the ones that actually fit; repeatable')
    s.add_argument('--min-count', type=int, default=3, help='ignore skills below this many postings')
    s.add_argument('--json', action='store_true', help='machine-readable output')
    s.set_defaults(func=cmd_skills)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
