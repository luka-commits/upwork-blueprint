#!/usr/bin/env python3
"""The job pipeline: every Upwork job you found, where it stands, what happened to it.

This script is the only thing that writes data/jobs.json. Commands, the cockpit
and you all go through it, so there is exactly one place a status can change.

A job moves  new -> applied -> replied -> offer -> won
and can leave at any point as  lost  (they hired someone else, or went silent)
or  skipped  (not a fit, you decided against it).

Usage:
    python3 code/pipeline.py add --check <job_id> [<job_id> ...]
    python3 code/pipeline.py add --file <records.json>|- [--dry-run]
    python3 code/pipeline.py detail <job_id> --file <details.json>|-
    python3 code/pipeline.py set <job_id> <status> [--follow-up +3d|YYYY-MM-DD] [--note "..."]
    python3 code/pipeline.py get <job_id>
    python3 code/pipeline.py list [--status new] [--limit 25]
    python3 code/pipeline.py summary
    python3 code/pipeline.py prune [--hours 24] [--dry-run]

Exits 1 when a job id does not exist: a silent no-op would be worse than an
error that names the cause.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUSES = ('new', 'applied', 'replied', 'offer', 'won', 'lost', 'skipped')
ACTIVE = ('applied', 'replied', 'offer')
CLOSED = ('won', 'lost', 'skipped')

# Untouched jobs beyond this many fall out when new ones arrive, oldest first.
# Anything a human moved past "new" is live pipeline and never falls out.
KEEP = 500

# Upwork's terms cap caching of their content at 24 hours. These fields hold
# Upwork's words and numbers; score, rationale, status, notes and history are
# the member's own work and stay.
CACHED_FIELDS = ('description', 'client', 'budget', 'job_type', 'posted_date', 'details')


def jobs_path():
    """Where the pipeline lives. BLUEPRINT_JOBS points tests at a throwaway file."""
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBS') or ROOT / 'data' / 'jobs.json')


def abort(msg):
    print(f'ABORT: {msg}', file=sys.stderr)
    sys.exit(1)


def load():
    path = jobs_path()
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        abort(f'{path} is not valid JSON. Nothing was changed.')


def save(jobs):
    """Writes through a temp file, so a crash mid-write never leaves half a pipeline."""
    path = jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_json_arg(file_arg):
    raw = sys.stdin.read() if file_arg == '-' else pathlib.Path(file_arg).read_text(encoding='utf-8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        abort(f'input is not valid JSON ({e}).')


def find(jobs, job_id):
    for j in jobs:
        if j.get('id') == job_id:
            return j
    abort(f'job "{job_id}" is not in the pipeline.')


def add_history(job, status, at=None):
    """Appends a status change. Append-only.

    Without it "how many applications went out today" is unanswerable, because
    status_updated_at is overwritten by the next change. The same status twice in
    a row writes nothing, so a repeated `set` cannot inflate the count.
    """
    hist = job.setdefault('history', [])
    if hist and hist[-1].get('status') == status:
        return False
    hist.append({'status': status, 'at': at or now_iso()})
    return True


def parse_follow_up(value):
    m = re.match(r'^\+(\d+)d$', value)
    if m:
        return (datetime.date.today() + datetime.timedelta(days=int(m.group(1)))).isoformat()
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        abort(f'--follow-up expects +Nd or YYYY-MM-DD, got: {value}')


def trim(jobs):
    """Caps untouched jobs at KEEP, dropping the oldest. Never touches live pipeline."""
    live = [j for j in jobs if j.get('status') != 'new']
    room = max(0, KEEP - len(live))
    untouched = sorted((j for j in jobs if j.get('status') == 'new'),
                       key=lambda j: j.get('found_at') or '', reverse=True)
    drop = {id(j) for j in untouched[room:]}
    return [j for j in jobs if id(j) not in drop], len(drop)


def cmd_add(args):
    """Duplicate check and intake, so a search never has to read the whole file.

    --check <id> ...   says NEW or KNOWN per id. Writes nothing. Run it before
                       spending a find_jobs get call on a job you already have.
    --file <path>|-    takes one record or a list, skips known ids, stamps
                       found_at, status and history, appends, trims.

    A known id is never overwritten: its record belongs to whatever status a
    human has set since.
    """
    if not args.check and not args.file:
        abort('add needs --check <id> ... or --file <path>|-')
    jobs = load()
    known = {j.get('id') for j in jobs}

    if args.check:
        new = [i for i in args.check if i not in known]
        for i in args.check:
            print(f'{"NEW  " if i in new else "KNOWN"}  {i}')
        print(f'\n{len(new)} of {len(args.check)} new, {len(args.check) - len(new)} already in the pipeline.')
        return

    records = read_json_arg(args.file)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        abort('expected one record or a list of records.')

    stamp = now_iso()
    added, skipped = [], []
    for rec in records:
        if not isinstance(rec, dict) or not rec.get('id'):
            abort('every record needs an "id".')
        jid = str(rec['id'])
        if jid in known:
            skipped.append(jid)
            continue
        rec['id'] = jid
        rec.setdefault('found_at', stamp)
        rec.setdefault('status', 'new')
        if rec['status'] not in STATUSES:
            abort(f'unknown status "{rec["status"]}" on {jid}. Allowed: {", ".join(STATUSES)}')
        rec.setdefault('status_updated_at', rec['found_at'])
        rec.setdefault('next_follow_up', None)
        rec.setdefault('notes', '')
        add_history(rec, rec['status'], rec['found_at'])
        jobs.append(rec)
        known.add(jid)
        added.append(jid)

    jobs, trimmed = trim(jobs)
    if args.dry_run:
        print(f'DRY RUN: {len(added)} would be added, {len(skipped)} skipped as duplicates, '
              f'{trimmed} old untouched jobs trimmed. Nothing changed.')
        return
    save(jobs)
    for jid in added:
        print(f'added      {jid}')
    for jid in skipped:
        print(f'duplicate  {jid}')
    print(f'\n{len(added)} added, {len(skipped)} skipped, {trimmed} trimmed. '
          f'{len(jobs)} jobs in the pipeline.')


def cmd_detail(args):
    """Adds or extends a job's `details` (what find_jobs get returned). Merges, never replaces."""
    new = read_json_arg(args.file)
    if not isinstance(new, dict):
        abort('expected one JSON object with the detail fields.')
    jobs = load()
    job = find(jobs, args.job_id)
    details = job.setdefault('details', {})
    details.update(new)
    details.setdefault('fetched_at', now_iso())
    save(jobs)
    print(f'{args.job_id}: {len(new)} detail fields added ({len(details)} in total).')


def cmd_set(args):
    if args.status not in STATUSES:
        abort(f'unknown status "{args.status}". Allowed: {", ".join(STATUSES)}')
    jobs = load()
    job = find(jobs, args.job_id)
    job['status'] = args.status
    job['status_updated_at'] = now_iso()
    add_history(job, args.status)
    # applied_at is the day of the FIRST application and never moves. The daily
    # target counts it, so a later reply must not shift the day you applied.
    if args.status == 'applied' and not job.get('applied_at'):
        job['applied_at'] = job['status_updated_at']
    if args.follow_up:
        job['next_follow_up'] = parse_follow_up(args.follow_up)
    elif args.status in CLOSED:
        job['next_follow_up'] = None
    if args.note:
        job['notes'] = (job.get('notes', '') + ' ' + args.note).strip()
    save(jobs)
    follow = f' (follow up {job["next_follow_up"]})' if job.get('next_follow_up') else ''
    print(f'{job["id"]} -> {args.status}{follow}')


def cmd_get(args):
    """Exactly one record as JSON. The cheap way to one job."""
    print(json.dumps(find(load(), args.job_id), indent=2, ensure_ascii=False))


def cmd_list(args):
    jobs = load()
    if args.status:
        jobs = [j for j in jobs if j.get('status') == args.status]
    jobs.sort(key=lambda j: j.get('score') or 0, reverse=True)
    total = len(jobs)
    shown = jobs[:args.limit] if args.limit else jobs
    for j in shown:
        follow = f'  follow up {j["next_follow_up"]}' if j.get('next_follow_up') else ''
        print(f'{j.get("score", "?"):>3}  {j.get("status", "?"):<8} {j.get("id")}  {j.get("title", "")[:70]}{follow}')
    if len(shown) < total:
        print(f'... {total - len(shown)} more (--limit 0 shows all).')


def applied_on(jobs, day):
    return sum(1 for j in jobs for h in j.get('history', [])
               if h.get('status') == 'applied' and str(h.get('at', ''))[:10] == day)


def cmd_summary(args):
    """The whole pipeline in about twenty lines, instead of reading the raw file."""
    jobs = load()
    if not jobs:
        print('No jobs in the pipeline yet.')
        return
    today = datetime.date.today().isoformat()
    counts = {s: 0 for s in STATUSES}
    for j in jobs:
        counts[j.get('status', 'new')] = counts.get(j.get('status', 'new'), 0) + 1

    print(f'{len(jobs)} jobs in the pipeline.\n')
    for s in STATUSES:
        if counts[s]:
            print(f'  {counts[s]:3d}  {s}')

    reached = sum(counts[s] for s in ('applied', 'replied', 'offer', 'won'))
    print(f'\n  {applied_on(jobs, today)} application(s) sent today.')
    if counts['new'] and not reached:
        print('  NOTE: nothing past "new". The funnel stops before the application.')

    due = sorted((j for j in jobs if j.get('next_follow_up') and j['next_follow_up'] <= today
                  and j.get('status') not in CLOSED), key=lambda j: j['next_follow_up'])
    if due:
        print(f'\nFollow-ups due ({len(due)}):')
        for j in due[:10]:
            print(f'  {j["next_follow_up"]}  {j.get("id")}  {j.get("title", "")[:60]}')

    best = sorted((j for j in jobs if j.get('status') == 'new'),
                  key=lambda j: j.get('score') or 0, reverse=True)[:8]
    if best:
        print(f'\nBest untouched ({len(best)} of {counts["new"]}):')
        for j in best:
            print(f'  {j.get("score", "?"):>3}  {j.get("id")}  {j.get("title", "")[:60]}')


def cmd_prune(args):
    """Drops cached Upwork content older than --hours. Your own work stays."""
    jobs = load()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=args.hours)
    hits = fields = 0
    for j in jobs:
        try:
            found = datetime.datetime.fromisoformat(str(j.get('found_at', '')).replace('Z', '+00:00'))
        except ValueError:
            continue
        if found >= cutoff:
            continue
        present = [f for f in CACHED_FIELDS if j.get(f) not in (None, '', {})]
        if not present:
            continue
        hits += 1
        fields += len(present)
        if not args.dry_run:
            for f in present:
                j.pop(f, None)
            j['cache_pruned_at'] = now_iso()
    if args.dry_run:
        print(f'DRY RUN: {hits} of {len(jobs)} jobs older than {args.hours}h, '
              f'{fields} cached fields would be removed. Nothing changed.')
        return
    if hits:
        save(jobs)
    print(f'{hits} jobs pruned, {fields} cached fields removed.')


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('add', help='Duplicate check by id, and intake of new records.')
    p.add_argument('--check', nargs='+', metavar='JOB_ID')
    p.add_argument('--file', metavar='PATH', help='JSON record or list. "-" reads stdin.')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_add)

    p = sub.add_parser('detail', help='Merge find_jobs get fields into one job.')
    p.add_argument('job_id')
    p.add_argument('--file', metavar='PATH', required=True, help='JSON object. "-" reads stdin.')
    p.set_defaults(func=cmd_detail)

    p = sub.add_parser('set', help='Move a job to a status.')
    p.add_argument('job_id')
    p.add_argument('status')
    p.add_argument('--follow-up')
    p.add_argument('--note')
    p.set_defaults(func=cmd_set)

    p = sub.add_parser('get', help='One record as JSON.')
    p.add_argument('job_id')
    p.set_defaults(func=cmd_get)

    p = sub.add_parser('list', help='Jobs by score.')
    p.add_argument('--status')
    p.add_argument('--limit', type=int, default=25, help='0 shows all.')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('summary', help='The pipeline in about twenty lines.')
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser('prune', help="Drop Upwork content older than 24h (Upwork's caching rule).")
    p.add_argument('--hours', type=int, default=24)
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_prune)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
