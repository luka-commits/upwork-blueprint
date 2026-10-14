#!/usr/bin/env python3
"""The job pipeline: every Upwork job you found, where it stands, what happened to it.

This script is the only thing that writes data/jobs.json. Commands, the cockpit
and you all go through it, so there is exactly one place a status can change.

A job moves  new -> applied -> replied -> call -> offer -> won
and can leave at any point as  lost  (they hired someone else, or went silent)
or  skipped  (not a fit, you decided against it).

Usage:
    python3 code/pipeline.py add --check <job_id> [<job_id> ...]
    python3 code/pipeline.py add --file <records.json>|- [--dry-run]
    python3 code/pipeline.py detail <job_id> --file <details.json>|-
    python3 code/pipeline.py assess <job_id> --file <assessment.json>|-
    python3 code/pipeline.py describe <job_id> "Plain-language summary of the work"
    python3 code/pipeline.py headline <job_id> "One sentence of at most 14 words"
    python3 code/pipeline.py observe <job_id> applied|replied <ISO timestamp> --source <source> --verified
    python3 code/pipeline.py set <job_id> <status> [--force] [--follow-up +3d|YYYY-MM-DD] [--note "..."]
    python3 code/pipeline.py acted <job_id> --note "..." [--at <ISO timestamp>]
    python3 code/pipeline.py record <job_id> --file <metadata.json>|-
    python3 code/pipeline.py follow-up <job_id> plan --lane <lane> --due <date> --reason "..."
    python3 code/pipeline.py follow-up <job_id> sent [--on YYYY-MM-DD]
    python3 code/pipeline.py follow-up <job_id> clear --reason "..."
    python3 code/pipeline.py note <job_id> "what happened"
    python3 code/pipeline.py task <job_id> add "what to do" [--due +2d|YYYY-MM-DD] [--time HH:MM]
    python3 code/pipeline.py task <job_id> done|reopen|delete <task_number>
    python3 code/pipeline.py get <job_id>
    python3 code/pipeline.py list [--status new] [--limit 25]
    python3 code/pipeline.py summary
    python3 code/pipeline.py archive <job_id> [<job_id> ...] [--dry-run]
    python3 code/pipeline.py reset-search [--dry-run]
    python3 code/pipeline.py prune [--hours 24] [--dry-run]   saved chats keep KEEP_CHAT_HOURS (90 days)

Exits 1 when a job id does not exist: a silent no-op would be worse than an
error that names the cause.
"""
import argparse
import contextlib
import datetime
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUSES = ('new', 'applied', 'replied', 'call', 'offer', 'won', 'lost', 'skipped')
ACTIVE = ('applied', 'replied', 'call', 'offer')
CLOSED = ('won', 'lost', 'skipped')

# Gaps after each sent follow-up, in business days. Step one is scheduled by
# the reviewer from the conversation. Later steps are mechanical so a missed
# morning cannot silently stretch or compress the sequence.
FOLLOW_UP_GAPS = {
    'active': (1,),
    'silent': (3, 4),
    'reactivation': (30, 60),
}
# 'active' has no last step: while a client is in touch the follow-up comes nearly every
# business day, and it ends when the client declines or says they have no interest.
UNBOUNDED = ('active',)

# Old unused jobs beyond this many fall out when new ones arrive, oldest first.
# Fresh intake and anything carrying the member's work never fall out.
KEEP = 500

# Upwork's terms cap caching of their content at 24 hours. These fields hold
# Upwork's words and numbers; score, rationale, status, notes and history are
# the member's own work and stay.
CACHED_FIELDS = ('description', 'client', 'budget', 'job_type', 'posted_date', 'details',
                 'proposals', 'proposal_count', 'proposals_tier')

APPLICATION_BANDS = {
    'budget_band': ('<500', '500-2000', '>2000', 'hourly', 'unknown'),
    'proposals_band': ('<5', '5-15', '15-50', '50+', 'unknown'),
    'client_hire_rate_band': ('none', '<30%', '30-70%', '>70%', 'unknown'),
    'client_spent_band': ('0', '<1k', '1k-10k', '>10k', 'unknown'),
    'posted_age_band': ('<10m', '10-60m', '1-6h', '>6h', 'unknown'),
    'bid_band': ('below', 'within', 'above', 'unknown'),
}
LEAD_SOURCES = ('outbound', 'invite', 'direct_offer', 'unknown')
_jobs_writes = 0


def award_lines(output):
    """Shared stdout contract: Badge name · Tier: reason, with no rewriting."""
    return [line for line in output.splitlines()
            if re.fullmatch(r'[^\r\n]+ · (?:Bronze|Silver|Gold|Platinum|Legend): .+', line)]


def check_badges(*args):
    """Best effort, after the jobs lock is released: awards cannot undo a write."""
    try:
        result = subprocess.run([sys.executable, str(ROOT / 'code' / 'badges.py'), 'check', *args],
                                capture_output=True, text=True, timeout=30, check=False)
        for line in award_lines(result.stdout):
            print(line)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode:
            print(f'Badge check failed ({result.returncode}); data write completed.', file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Badge check failed; data write completed: {error}', file=sys.stderr)


CHAT_KEEP_HOURS = 2160


def chat_keep_hours():
    """How long prune keeps saved client chats: 90 days unless KEEP_CHAT_HOURS says otherwise.

    Chats are what follow-ups and feedback learn from, so they are the one Upwork
    response kept long. Everything else prune handles stays at --hours (24), because
    readers treat a surviving profile or candidate list as fresh. A member who wants
    Upwork's published 24 hours sets KEEP_CHAT_HOURS=24 in .env or the environment.
    """
    raw = os.environ.get('KEEP_CHAT_HOURS')
    if raw is None:
        try:
            for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
                key, _, value = line.partition('=')
                if key.strip() == 'KEEP_CHAT_HOURS':
                    raw = value.strip()
        except OSError:
            pass
    if raw is None:
        return CHAT_KEEP_HOURS
    value = raw.split('#', 1)[0].strip().strip('\"\'').strip()
    if value.isdigit():
        return int(value)
    print('WARNING: invalid KEEP_CHAT_HOURS; using 24 hours, not the 90-day default.', file=sys.stderr)
    return 24

# Two of the member's own decisions live inside details: the bid they approved and
# the internal estimate behind it. Pruning Upwork's content must not take them.
MEMBER_DETAIL_FIELDS = ('bid_amount', 'price_estimate', 'connects_cost')

# The video you recorded for a job. Only links a client can open on Upwork.

def jobs_path():
    """Where the pipeline lives. BLUEPRINT_JOBS points tests at a throwaway file."""
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBS') or ROOT / 'data' / 'jobs.json')


def jobs_dir():
    """Where each job's files live. A client thread saved there is Upwork content too."""
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBDIR') or ROOT / 'jobs')


def shown(path):
    """A path as the member should read it: short inside the repo, whole outside.

    `relative_to` raises when a job folder lives somewhere else, which BLUEPRINT_JOBDIR
    allows, and a line of output is never worth ending a run over.
    """
    path = pathlib.Path(path)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def data_dir():
    """Where disposable connector caches live."""
    return pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')


def abort(msg):
    print(f'ABORT: {msg}', file=sys.stderr)
    sys.exit(1)


def load():
    path = jobs_path()
    if not path.is_file():
        return []
    try:
        jobs = json.loads(path.read_text(encoding='utf-8'))
        for job in jobs:
            migrate_call(job)
        return jobs
    except json.JSONDecodeError:
        abort(f'{path} is not valid JSON. Nothing was changed.')


def migrate_call(job):
    """Split legacy scheduled and recorded calls without writing during a read."""
    booked_observation = job.get('call_booked_observation') or {}
    if job.get('call_booked_at') and not job.get('call_scheduled_at') and booked_observation.get('kind') != 'booking-confirmed':
        job['call_scheduled_at'] = job.pop('call_booked_at')
        job['call_scheduled_observation'] = job.pop('call_booked_observation', {})
    if not job.get('call_at') or job.get('call_booked_at') or job.get('call_held_at'):
        return
    observation = job.get('call_observation') or {}
    if observation.get('source') == 'recorder':
        job.setdefault('call_held_at', job['call_at'])
        job.setdefault('call_held_observation', observation)
    else:
        job.setdefault('call_scheduled_at', job['call_at'])


def numeric(value):
    """A finite non-negative number, or None when the source did not give one."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) and value >= 0 else None
    from jobs import money_value
    number = money_value(value) if isinstance(value, str) else None
    return number if number is not None and math.isfinite(number) else None


def freeze_application_facts(job):
    """Keep application-time categories once, never cached client numbers."""
    if job.get('application_facts') or not job.get('applied_at'):
        return
    from jobs import budget_top, numbers
    details = job.get('details') or {}
    client = job.get('client') or {}
    client_record = details.get('client_record') or {}
    if isinstance(client_record, dict):
        client = {**client_record, **client}
    budget, hourly = budget_top(job)
    budget_band = ('hourly' if hourly else 'unknown' if budget is None else
                   '<500' if budget < 500 else '500-2000' if budget <= 2000 else '>2000')
    raw_proposals = job.get('proposals', job.get('proposal_count', job.get('proposals_tier')))
    proposals = numeric(raw_proposals)
    proposal_band = 'unknown'
    if raw_proposals in APPLICATION_BANDS['proposals_band']:
        proposal_band = raw_proposals
    elif isinstance(raw_proposals, str) and len(numbers(raw_proposals)) > 1:
        # A reported range maps only when every endpoint belongs to the same band.
        low, high = min(numbers(raw_proposals)), max(numbers(raw_proposals))
        if low >= 5 and high <= 15:
            proposal_band = '5-15'
        elif low >= 15 and high <= 50:
            proposal_band = '15-50'
    elif proposals is not None:
        proposal_band = '<5' if proposals < 5 else '5-15' if proposals < 15 else '15-50' if proposals < 50 else '50+'
    hires = numeric(client.get('hires', client.get('total_hires')))
    posted = numeric(client.get('posted_jobs', client.get('total_posted_jobs')))
    hire_band = 'unknown'
    if hires is not None and posted is not None and posted > 0:
        rate = hires / posted
        hire_band = 'none' if hires == 0 else '<30%' if rate < .3 else '30-70%' if rate <= .7 else '>70%'
    spent = numeric(client.get('spent', client.get('total_spent')))
    spent_band = ('unknown' if spent is None else '0' if spent == 0 else '<1k' if spent < 1000
                  else '1k-10k' if spent <= 10000 else '>10k')
    payment = client.get('verified', client.get('payment_verified'))
    if not isinstance(payment, bool):
        verification = client.get('verification_status')
        payment = verification == 'VERIFIED' if verification in ('VERIFIED', 'UNVERIFIED') else 'unknown'
    age_band = 'unknown'
    applied = parse_verified_timestamp(job.get('applied_at'))
    posted_at = parse_verified_timestamp(job.get('posted_date'))
    if applied and posted_at:
        age = (datetime.datetime.fromisoformat(applied) - datetime.datetime.fromisoformat(posted_at)).total_seconds()
        if age >= 0:
            age_band = '<10m' if age < 600 else '10-60m' if age < 3600 else '1-6h' if age <= 21600 else '>6h'
    bid = numeric(details.get('bid_amount'))
    budget_values = numbers(job.get('budget'))
    bid_band = 'unknown'
    if bid is not None and budget_values:
        low, high = min(budget_values), max(budget_values)
        bid_band = 'below' if bid < low else 'above' if bid > high else 'within'
    job['application_facts'] = {
        'captured_at': now_iso(), 'source': job.get('source') or ('invite' if 'invite' in job.get('found_via', []) else 'outbound'),
        'budget_band': budget_band, 'job_type': job.get('job_type') or ('hourly' if hourly else 'unknown'),
        'proposals_band': proposal_band, 'client_hire_rate_band': hire_band,
        'client_spent_band': spent_band, 'payment_verified': payment,
        'posted_age_band': age_band, 'lane': job.get('lane') or 'unknown', 'bid_band': bid_band,
        'connects_cost': numeric(details.get('connects_cost', job.get('connects_cost'))),
    }
    if job['application_facts']['connects_cost'] is None:
        job['application_facts']['connects_cost'] = 'unknown'


def save(jobs):
    """Writes through a temp file, so a crash mid-write never leaves half a pipeline."""
    global _jobs_writes
    path = jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.pipeline-', suffix='.tmp', delete=False) as handle:
        tmp = pathlib.Path(handle.name)
        json.dump(jobs, handle, indent=2, ensure_ascii=False)
    try:
        os.replace(tmp, path)
        _jobs_writes += 1
    finally:
        tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def transaction():
    """Serialize the entire read/change/write across cockpit and command processes."""
    lock = jobs_path().with_suffix('.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def member_zone():
    """Use an IANA member clock, including the offset for the event's own date."""
    context = pathlib.Path(os.environ.get('BLUEPRINT_CONTEXT') or ROOT / 'context') / 'me.md'
    text = context.read_text(encoding='utf-8') if context.is_file() else ''
    match = re.search(r'^## Timezone\s*\n([^#]+)', text, re.M)
    name = match[1].strip().splitlines()[0] if match and match[1].strip() else None
    if not name:
        hours = re.search(r'^## Working hours\s*\n([^#]+)', text, re.M)
        zone = re.search(r'\b([A-Za-z_]+/[A-Za-z_]+)\b', hours[1]) if hours else None
        name = zone[1] if zone else os.environ.get('TZ')
    if not name:
        link = str(pathlib.Path('/etc/localtime').resolve())
        name = link.split('/zoneinfo/', 1)[-1] if '/zoneinfo/' in link else 'UTC'
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return ZoneInfo('UTC')


def local_day(value=None):
    if value is None:
        return datetime.datetime.now(member_zone()).date()
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    stamp = value if isinstance(value, datetime.datetime) else datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return stamp.astimezone(member_zone()).date() if stamp.tzinfo else stamp.date()


def preserve_follow_up(job, at=None):
    """Keep a cancelled obligation, so a miss preceding cancellation survives."""
    plan = job.get('follow_up_plan') or {}
    if plan and job.get('next_follow_up'):
        job.setdefault('follow_up_history', []).append({
            'action': 'cleared', 'at': at or now_iso(), 'cancelled_at': at or now_iso(),
            'due_on': plan.get('due_on') or job['next_follow_up'], 'lane': plan.get('lane'), 'step': plan.get('step'),
            'obligation_id': plan.get('obligation_id') or f"{job['id']}:{plan.get('lane')}:{plan.get('step')}:{plan.get('due_on') or job['next_follow_up']}",
        })


def cmd_reconcile(args):
    """Merge a stable synthetic alias into the real Upwork job, once."""
    jobs = load()
    old = find(jobs, args.old_id)
    if old['id'] == args.job_id:
        print(f'{args.old_id}: already reconciled into {args.job_id}.')
        return
    if old['id'] != args.old_id:
        abort(f'{args.old_id} is already an alias of {old["id"]}; reconcile the current identity explicitly.')
    target = next((j for j in jobs if j['id'] == args.job_id), None)
    if target is None:
        target = {'id': args.job_id}
        jobs.append(target)
    for key, item in old.items():
        if key == 'id':
            continue
        if key in ('history', 'follow_up_history', 'found_via', 'workspace_aliases'):
            existing = target.setdefault(key, [])
            for entry in item:
                if entry not in existing:
                    existing.append(entry)
        elif key in ('room_reply_metrics', 'call_sessions', 'thread_refs'):
            for identity, record in item.items():
                target.setdefault(key, {}).setdefault(identity, record)
        elif key not in target or target[key] in (None, '', [], {}):
            target[key] = item
        elif key.endswith('_at') and key not in ('status_updated_at', 'last_activity_at', 'call_scheduled_at'):
            if parse_verified_timestamp(item) and (not parse_verified_timestamp(target[key]) or item < target[key]):
                target[key] = item
                observation = key[:-3] + '_observation'
                if observation in old:
                    target[observation] = old[observation]
    rank = {name: n for n, name in enumerate(('new', 'applied', 'replied', 'call', 'offer', 'won'))}
    if rank.get(old.get('status'), -1) > rank.get(target.get('status'), -1):
        target['status'] = old['status']
    if parse_verified_timestamp(target.get('applied_at')):
        target.pop('application_date_unknown', None)
    target.setdefault('aliases', []).extend(alias for alias in [args.old_id, *old.get('aliases', [])] if alias not in target.get('aliases', []))
    source, destination = jobs_dir() / args.old_id, jobs_dir() / args.job_id
    if source.exists():
        if not destination.exists():
            source.rename(destination)
        else:
            for original in source.rglob('*'):
                if original.is_file():
                    relative = original.relative_to(source)
                    moved = destination / relative
                    moved.parent.mkdir(parents=True, exist_ok=True)
                    if moved.exists() and moved.read_bytes() != original.read_bytes():
                        moved = moved.with_name(moved.name + '.from-' + args.old_id)
                    if not moved.exists():
                        shutil.copy2(original, moved)
            shutil.rmtree(source)
    target['synthetic_import'] = False
    jobs.remove(old)
    save(jobs)
    print(f'{args.old_id}: reconciled into {args.job_id}.')


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
        if j.get('id') == job_id or job_id in j.get('aliases', []):
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
    """+Nd or a date. N counts business days, because every lane gap does.

    Calendar days here and business days in the lane meant the same "+3d" landed on
    Monday from a Friday and on Wednesday from a lane step, with nothing saying so.
    """
    m = re.match(r'^\+(\d+)d$', value)
    if m:
        return add_business_days(local_day(), int(m.group(1))).isoformat()
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        abort(f'--follow-up expects +Nd or YYYY-MM-DD, got: {value}')


def add_business_days(day, count):
    """Move forward by weekdays. Upwork conversations do not need holiday calendars."""
    current = day
    added = 0
    while added < count:
        current += datetime.timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def trim(jobs):
    """Caps old unused jobs at KEEP. Fresh leads and the member's work stay."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    live = [j for j in jobs if protected_search_lead(j, now_utc)]
    protected = {id(j) for j in live}
    room = max(0, KEEP - len(live))
    untouched = sorted((j for j in jobs if id(j) not in protected),
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
        rec.setdefault('last_activity_at', rec['status_updated_at'])
        rec.setdefault('next_follow_up', None)
        rec.setdefault('notes', '')
        freeze_application_facts(rec)
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
    stamp = now_iso()
    cached_at = details.setdefault('_cached_at', {})
    for key in details:
        if key not in ('_cached_at', 'fetched_at'):
            cached_at.setdefault(key, details.get('fetched_at') or job.get('found_at') or stamp)
    details.update(new)
    details['_cached_at'] = {**cached_at, **{key: stamp for key in new if key not in ('_cached_at', 'fetched_at')}}
    details['fetched_at'] = stamp
    save(jobs)
    print(f'{args.job_id}: {len(new)} detail fields added ({len(details)} in total).')


def cmd_set(args):
    if args.status not in STATUSES:
        abort(f'unknown status "{args.status}". Allowed: {", ".join(STATUSES)}')
    if args.status == 'applied' and args.follow_up:
        abort('applied proposals cannot have a follow-up before the client replies.')
    jobs = load()
    job = find(jobs, args.job_id)
    current = job.get('status')
    if (args.status in ('new', *ACTIVE, 'won') and current != args.status
            and (current in ('lost', 'skipped') or STATUSES.index(args.status) < STATUSES.index(current))
            and not args.force):
        abort(f'{args.job_id}: {current} -> {args.status} goes backward; use --force to confirm it.')
    job['status'] = args.status
    if current != args.status:
        job['status_updated_at'] = now_iso()
        activity = verified_timestamp(args.activity_at) if args.activity_at else job['status_updated_at']
        job['last_activity_at'] = max(job.get('last_activity_at') or '', activity)
        add_history(job, args.status, job['status_updated_at'])
    # applied_at is the day of the FIRST application and never moves. The daily
    # target counts it, so a later reply must not shift the day you applied.
    if args.status == 'applied' and not job.get('applied_at'):
        observed = getattr(args, 'applied_at', None)
        if observed == 'unknown':
            job['application_date_unknown'] = True
        elif not job.get('application_date_unknown') or observed:
            if observed:
                try:
                    datetime.datetime.fromisoformat(observed.replace('Z', '+00:00'))
                except ValueError:
                    abort('--applied-at expects an ISO timestamp or unknown.')
            job['applied_at'] = observed or job['status_updated_at']
            job.pop('application_date_unknown', None)
    freeze_application_facts(job)
    if args.status == 'applied':
        freeze_speed_to_lead(job)
    lane = (job.get('follow_up_plan') or {}).get('lane')
    if args.status in ('applied', 'lost', 'skipped'):
        preserve_follow_up(job)
        job['next_follow_up'] = None
        job.pop('follow_up_plan', None)
    elif args.status == 'won' and lane != 'reactivation' and not args.follow_up:
        # Winning ends a sales sequence. It must not end the reactivation lane, which
        # exists only for won clients: recording a sent message with `set won` used to
        # delete that plan, and the 60-day second touch went with it.
        preserve_follow_up(job)
        job['next_follow_up'] = None
        job.pop('follow_up_plan', None)
    elif args.follow_up:
        job['next_follow_up'] = parse_follow_up(args.follow_up)
    elif not job.get('follow_up_plan'):
        # The member just acted, so the ball is with the client. A date the morning sync
        # set while the client was waiting would otherwise keep the cockpit asking
        # forever for a follow-up that has already gone out.
        job['next_follow_up'] = None
    if args.status not in ('replied', 'call', 'offer', 'won'):
        job.pop('follow_up_plan', None)
    if args.follow_up or not job.get('next_follow_up'):
        job.pop('follow_up_source', None)
    recorder_call = (job.get('call_observation') or {}).get('source') == 'recorder'
    if getattr(args, 'call_at', None):
        if recorder_call:
            abort('A recorder call time cannot be replaced by a scheduled date.')
        job['call_scheduled_at'] = parse_follow_up(args.call_at)
        job['call_scheduled_precision'] = 'date'
        job.setdefault('call_booked_at', now_iso())
        job.setdefault('call_booked_observation', {'source': 'member', 'verified': True, 'kind': 'booking-confirmed', 'observed_at': now_iso()})
    if args.note:
        job['notes'] = (job.get('notes', '') + ' ' + args.note).strip()
    save(jobs)
    follow = f' (follow up {job["next_follow_up"]})' if job.get('next_follow_up') else ''
    print(f'{job["id"]} -> {args.status}{follow}')


def cmd_acted(args):
    """Record activity without changing the stage, history or scheduled sequence."""
    text = ' '.join(args.note.split())
    if not text:
        abort('activity needs a note.')
    stamp = verified_timestamp(args.at) if args.at else now_iso()
    jobs = load()
    job = find(jobs, args.job_id)
    previous = parse_verified_timestamp(job.get('last_activity_at'))
    if args.at and previous and previous >= stamp:
        print(f'{args.job_id}: activity already recorded.')
        return
    job['last_activity_at'] = stamp
    job['notes'] = (job.get('notes', '') + ' ' + text).strip()
    save(jobs)
    print(f'{args.job_id}: activity recorded.')


def cmd_record(args):
    """Store connector identity and workflow markers through the sole writer."""
    value = read_json_arg(args.file)
    allowed = {'loom_hook', 'call_next_step', 'loom_duration_s', 'loom_wpm', 'call_stats', 'reply_gaps_s', 'proposal_id', 'room_id', 'contract_id', 'contract_client', 'client_slug',
               'submission_checked_at', 'result_recorded_at', 'next_follow_up', 'follow_up_source',
               'first_reply_s', 'first_reply_at', 'source', 'invitation_id', 'invited_at',
               'call_no_show', 'won_value', 'offer_id', 'first_client_message_at', 'room_reply_metrics',
               'call_scheduled_at', 'call_ended_at', 'call_duration_s', 'call_session_id', 'call_sessions',
               'call_outcome', 'proposal_required', 'application_modality', 'application_sent_verified', 'submission_bid',
               'invited_at_source', 'proposal_status', 'proposal_cost', 'proposal_viewed', 'proposal_insights',
               'call_requested_at', 'call_request', 'recap_state', 'recap_reason', 'thread_refs', 'conversation_review', 'call_review'}
    if not isinstance(value, dict) or not value or set(value) - allowed:
        abort('metadata needs only ' + ', '.join(sorted(allowed)) + '.')
    for key, item in value.items():
        if key == 'source':
            if item not in LEAD_SOURCES:
                abort('source needs outbound, invite, direct_offer or unknown.')
        elif key == 'invited_at_source':
            if item not in ('room', 'sync'):
                abort('invited_at_source needs room or sync.')
        elif key == 'proposal_viewed':
            if (not isinstance(item, dict) or set(item) != {'value', 'observed_at', 'source'}
                    or not isinstance(item.get('value'), bool) or item.get('source') != 'upwork-proposal'):
                abort('proposal_viewed needs boolean value, observed_at and source upwork-proposal.')
            item['observed_at'] = verified_timestamp(item['observed_at'])
        elif key == 'proposal_insights':
            if (not isinstance(item, dict) or set(item) != {'data', 'fetched_at', 'source'}
                    or not isinstance(item.get('data'), dict) or item.get('source') != 'upwork-proposal'):
                abort('proposal_insights needs data object, fetched_at and source upwork-proposal.')
            item['fetched_at'] = verified_timestamp(item['fetched_at'])
        elif key == 'proposal_cost':
            if (not isinstance(item, dict) or set(item) - {'connectsBid', 'boosted', 'observed_at', 'source'}
                    or not {'observed_at', 'source'} <= set(item) or item['source'] != 'upwork-proposal'
                    or ('connectsBid' in item and (numeric(item['connectsBid']) is None
                        or not isinstance(item['connectsBid'], (int, float))))
                    or ('boosted' in item and not isinstance(item['boosted'], bool))):
                abort('proposal_cost needs observed_at, source upwork-proposal, numeric connectsBid and/or boolean boosted.')
            item['observed_at'] = verified_timestamp(item['observed_at'])
        elif key == 'call_request':
            if (not isinstance(item, dict) or set(item) - {'request_id', 'session_id', 'room_id', 'status', 'scheduled_at', 'duration_s', 'source', 'observed_at', 'requested_at_source'}
                    or item.get('source') != 'upwork-meeting' or not isinstance(item.get('status'), str)):
                abort('call_request needs request metadata with source upwork-meeting and status.')
            item['observed_at'] = verified_timestamp(item.get('observed_at'))
            if 'requested_at_source' in item and item['requested_at_source'] not in ('upwork', 'sync'):
                abort('call_request.requested_at_source needs upwork or sync.')
            if 'scheduled_at' in item:
                try:
                    stamp = datetime.datetime.fromisoformat(str(item['scheduled_at']).replace('Z', '+00:00'))
                    if stamp.tzinfo is None:
                        raise ValueError
                    item['scheduled_at'] = stamp.astimezone(datetime.timezone.utc).isoformat()
                except ValueError:
                    abort('call_request.scheduled_at needs a zoned start.')
            if 'duration_s' in item and numeric(item['duration_s']) is None:
                abort('call_request.duration_s needs non-negative finite seconds.')
        elif key == 'recap_state':
            if item not in ('ok', 'empty', 'unknown'):
                abort('recap_state needs ok, empty or unknown.')
        elif key == 'recap_reason':
            if item is not None and not isinstance(item, str):
                abort('recap_reason needs text or null.')
        elif key == 'call_no_show':
            if not isinstance(item, bool):
                abort('call_no_show needs a member-confirmed boolean.')
        elif key == 'first_reply_s':
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                abort('first_reply_s needs non-negative whole seconds.')
        elif key == 'won_value':
            if (not isinstance(item, dict) or not {'type', 'amount', 'currency', 'start_date'} <= set(item) or set(item) - {'type', 'amount', 'currency', 'start_date', 'weekly_hours'}
                    or item.get('type') not in ('fixed', 'hourly') or numeric(item.get('amount')) is None
                    or not isinstance(item.get('amount'), (int, float))
                    or not isinstance(item.get('currency'), str) or not item['currency'].strip()):
                abort('won_value needs type, numeric amount, currency and start_date.')
            if 'weekly_hours' in item and (numeric(item['weekly_hours']) is None or not isinstance(item['weekly_hours'], (int, float))):
                abort('won_value.weekly_hours needs a non-negative finite number.')
            try:
                datetime.date.fromisoformat(item['start_date'])
            except (ValueError, TypeError):
                abort('won_value.start_date needs YYYY-MM-DD.')
        elif key == 'thread_refs':
            fields = {'room_id', 'messages_complete', 'fetched_at', 'last_writer', 'source'}
            if not isinstance(item, dict) or not item:
                abort('thread_refs needs references keyed by stable Upwork room id.')
            for room_id, ref in item.items():
                if (not isinstance(room_id, str) or not room_id.strip() or not isinstance(ref, dict)
                        or set(ref) != fields or ref['room_id'] != room_id
                        or not isinstance(ref['messages_complete'], bool)
                        or ref['last_writer'] not in ('me', 'client', 'unknown')
                        or ref['source'] != 'upwork-thread'):
                    abort('thread_refs needs room identity, completeness, fetched_at, last_writer and source upwork-thread.')
                ref['fetched_at'] = verified_timestamp(ref['fetched_at'])
        elif key == 'call_review':
            if (not isinstance(item, dict) or not {'reviewable', 'points'} <= set(item)
                    or set(item) - {'reviewable', 'points', 'moments', 'fix', 'example', 'next_step'}
                    or not isinstance(item['reviewable'], bool) or not isinstance(item['points'], list)):
                abort('call_review needs reviewable and points, with optional moments and coaching text.')
            if not item['reviewable'] and item['points']:
                abort('An unreviewable call cannot have point findings.')
            if item['reviewable'] and (len(item['points']) != 9 or {point.get('point') for point in item['points'] if isinstance(point, dict)} != set(range(1, 10))):
                abort('A reviewed call needs each of the nine points once.')
            for point in item['points']:
                if (not isinstance(point, dict) or not {'point', 'state', 'quote'} <= set(point)
                        or set(point) - {'point', 'state', 'quote', 'reason'}
                        or point['state'] not in ('met', 'partly', 'missing', 'not needed')
                        or not isinstance(point['quote'], str) or not point['quote'].strip()
                        or ('reason' in point and not isinstance(point['reason'], str))
                        or (point['state'] == 'not needed' and not str(point.get('reason') or '').strip())):
                    abort('Call points need point, state and quoted evidence; not needed requires its reason.')
            if not isinstance(item.get('moments', []), list) or len(item.get('moments', [])) > 3:
                abort('Call reviews have at most three quoted key moments.')
            for moment in item.get('moments', []):
                if (not isinstance(moment, dict) or set(moment) != {'quote', 'better_wording'}
                        or any(not isinstance(text, str) or not text.strip() for text in moment.values())):
                    abort('Each call moment needs a quotation and better wording.')
            if any(not isinstance(item[field], str) for field in ('fix', 'example', 'next_step') if field in item):
                abort('Call coaching fields need text.')
        elif key == 'conversation_review':
            point_keys = {'fast_answer', 'answered_question', 'qualifying_question', 'call_times', 'follow_ups'}
            if (not isinstance(item, dict) or set(item) != {'points', 'last_writer', 'read'}
                    or not isinstance(item['read'], bool) or item['last_writer'] not in ('me', 'client', 'unknown')
                    or not isinstance(item['points'], dict) or set(item['points']) != point_keys):
                abort('conversation_review needs five points, last_writer and a boolean read flag.')
            for point in item['points'].values():
                if (not isinstance(point, dict) or set(point) != {'state', 'quote', 'reason'}
                        or point['state'] not in ('met', 'partly', 'missing', 'not_needed')
                        or not isinstance(point['quote'], str) or not isinstance(point['reason'], str)
                        or (point['state'] == 'not_needed' and not point['reason'].strip())
                        or (point['state'] in ('met', 'partly') and not point['quote'].strip())):
                    abort('Conversation points need state, quote and reason; applicable findings need quotes and not_needed needs a reason.')
            if not item['read'] and any(point['state'] != 'missing' for point in item['points'].values()):
                abort('An unread conversation has missing points, never inferred findings.')
        elif key == 'room_reply_metrics':
            if not isinstance(item, dict) or any(not isinstance(v, dict) for v in item.values()):
                abort('room_reply_metrics needs metrics keyed by stable room id.')
        elif key == 'call_sessions':
            if not isinstance(item, dict) or any(not isinstance(v, dict) for v in item.values()):
                abort('call_sessions needs records keyed by stable session id.')
        elif key == 'call_outcome':
            if item not in ('proposal_required', 'disqualified', 'direct_win', 'unresolved'):
                abort('call_outcome needs a supported qualification outcome.')
        elif key in ('proposal_required', 'application_sent_verified'):
            if not isinstance(item, bool):
                abort(f'{key} needs a boolean.')
        elif key == 'application_modality':
            if item not in ('text', 'uma'):
                abort('application_modality needs text or uma.')
        elif key == 'call_ended_at' and item is None:
            pass
        elif key == 'call_duration_s' and item is None:
            pass
        elif key in ('call_duration_s', 'submission_bid'):
            if numeric(item) is None or not isinstance(item, (int, float)):
                abort(f'{key} needs a non-negative finite number.')
        elif key == 'call_scheduled_at' and item is None:
            pass
        elif key == 'call_scheduled_at':
            try:
                stamp = datetime.datetime.fromisoformat(str(item).replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError
                value[key] = stamp.astimezone(datetime.timezone.utc).isoformat()
            except ValueError:
                abort('call_scheduled_at needs a zoned scheduled start.')
        elif key == 'follow_up_source':
            if item not in (None, 'waiting'):
                abort('follow_up_source needs waiting or null to remove it.')
        elif key == 'loom_hook':
            if item not in ('pass', 'fail'):
                abort('loom_hook needs pass or fail.')
        elif key == 'call_next_step':
            if not isinstance(item, bool):
                abort('call_next_step needs true or false.')
        elif key in ('loom_duration_s', 'loom_wpm'):
            if (not isinstance(item, (int, float)) or isinstance(item, bool)
                    or not math.isfinite(item) or item < 0):
                abort(f'{key} needs a non-negative finite number.')
        elif key == 'call_stats':
            fields = {'duration_s', 'talk_share_pct', 'question_counts', 'talk_share_basis', 'note',
                      'transcript_complete', 'language', 'member_attributed'}
            if not isinstance(item, dict) or set(item) - fields:
                abort('call_stats needs derived metrics only.')
            for name in ('duration_s', 'talk_share_pct'):
                metric = item.get(name)
                if metric is not None and (not isinstance(metric, (int, float))
                                           or isinstance(metric, bool) or not math.isfinite(metric)
                                           or metric < 0 or (name == 'talk_share_pct' and metric > 100)):
                    abort(f'call_stats.{name} needs a non-negative finite number.')
            for name in ('transcript_complete', 'member_attributed'):
                if name in item and item[name] is not None and not isinstance(item[name], bool):
                    abort(f'call_stats.{name} needs a boolean or null.')
            if item.get('language') is not None and not isinstance(item['language'], str):
                abort('call_stats.language needs text or null.')
            if 'question_counts' in item:
                counts = item['question_counts']
                if (not isinstance(counts, dict) or set(counts) != {'member', 'client'} or
                        any(not isinstance(n, int) or isinstance(n, bool) or n < 0
                            for n in counts.values())):
                    abort('question_counts needs member and client counts.')
            if any(not isinstance(item[name], str) for name in ('note', 'talk_share_basis') if name in item):
                abort('call_stats explanations need text.')
        elif key == 'reply_gaps_s':
            if (not isinstance(item, list) or any(
                    not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in item)):
                abort('reply_gaps_s needs non-negative whole seconds.')
        elif key.endswith('_at'):
            value[key] = verified_timestamp(item)
        elif key == 'next_follow_up':
            if item is not None:
                value[key] = parse_follow_up(item)
        elif not isinstance(item, str) or not item.strip():
            abort(f'{key} needs a non-empty string.')
    if 'client_slug' in value and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value['client_slug']):
        abort('client_slug needs a lowercase folder name.')
    jobs = load()
    job = find(jobs, args.job_id)
    if 'conversation_review' in value and value['conversation_review']['read']:
        path = jobs_dir() / args.job_id / 'thread.json'
        try:
            thread = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            abort('A conversation cannot be marked read without saved Upwork messages.')
        rooms = list((thread.get('rooms') or {}).values()) or [thread]
        complete = [room for room in rooms if room.get('messages_complete') is True]
        if not complete or len(complete) != len(rooms):
            abort('A conversation cannot be marked read from a partial message window.')
        texts = [str(turn.get('text') or '') for room in complete for turn in room.get('messages', [])
                 if isinstance(turn, dict) and turn.get('from') in ('me', 'client') and turn.get('kind', 'message') == 'message']
        for point in value['conversation_review']['points'].values():
            if point['quote'].strip() and not any(point['quote'] in text for text in texts):
                abort('Every conversation quotation must occur in complete saved Upwork messages.')
    if 'call_review' in value and value['call_review']['reviewable']:
        import call_stats
        path = jobs_dir() / args.job_id / 'call.md'
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            abort('A reviewed call needs its saved complete transcript.')
        stats = call_stats.analyze(text)
        if not stats.get('transcript_complete') or not stats.get('member_attributed'):
            abort('A reviewed call needs a complete transcript with member attribution.')
        utterances = [match[2] for match in re.finditer(r'^([^:\n]+):\s*(.+)$', text, re.M)
                      if match[1].strip().casefold() not in ('duration', 'member', 'call at', 'date', 'recorder', 'speakers', 'complete', 'language')]
        for point in value['call_review']['points'] + value['call_review'].get('moments', []):
            if not any(point['quote'] in utterance for utterance in utterances):
                abort('Every call review quotation must occur in the saved transcript.')
    if ('invited_at' in value and job.get('invited_at_source') == 'room'
            and value.get('invited_at_source') != 'room'):
        value.pop('invited_at', None)
        value.pop('invited_at_source', None)
    elif ('invited_at' in value and value.get('invited_at_source') in ('room', 'sync')
            and value.get('invited_at_source') == job.get('invited_at_source')):
        prior = parse_verified_timestamp(job.get('invited_at'))
        if prior:
            value['invited_at'] = min(value['invited_at'], prior)
    changed = False
    for key, item in value.items():
        if key == 'follow_up_source' and item is None:
            changed = key in job or changed
            job.pop(key, None)
        elif (key not in ('submission_checked_at', 'result_recorded_at', 'proposal_insights') or not job.get(key)) and job.get(key) != item:
            job[key] = item
            if key == 'call_no_show' and job.get('call_session_id'):
                session = job.setdefault('call_sessions', {}).setdefault(job['call_session_id'], {})
                session['no_show'] = item
                session['attendance_observed_at'] = now_iso()
            if key == 'source' and isinstance(job.get('application_facts'), dict):
                job['application_facts']['source'] = item
            changed = True
    if 'source' in value and isinstance(job.get('application_facts'), dict) and job['application_facts'].get('source') != value['source']:
        job['application_facts']['source'] = value['source']
        changed = True
    if not changed:
        print(f'{args.job_id}: metadata already recorded.')
        return
    save(jobs)
    print(f'{args.job_id}: metadata recorded.')


def cmd_follow_up(args):
    """Plan, advance or stop a context-chosen follow-up sequence."""
    jobs = load()
    job = find(jobs, args.job_id)
    source = job.pop('follow_up_source', None)

    if args.action == 'plan':
        if not args.lane or not args.due:
            abort('plan needs --lane and --due.')
        try:
            thread = json.loads((jobs_dir() / args.job_id / 'thread.json').read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            abort('sync this conversation before planning a follow-up.')
        if not str(thread.get('room_id') or '').strip():
            abort('this conversation has no room; a freelancer cannot message first.')
        lane = args.lane
        if lane == 'reactivation' and job.get('status') != 'won':
            abort('reactivation is only for a previous or current client in won.')
        if lane != 'reactivation' and job.get('status') not in ('replied', 'call', 'offer'):
            abort('sales follow-ups need a lead that has answered; applied proposals cannot message first.')
        # The lane's own first gap, not whatever date happened to be passed: gaps[0]
        # existed and was never used, so step 1 was the one step nobody measured.
        first = FOLLOW_UP_GAPS[lane][0]
        anchor = verified_timestamp(args.at) if args.at else now_iso()
        earliest = add_business_days(local_day(anchor), first)
        due = parse_follow_up(args.due)
        if datetime.date.fromisoformat(due) < earliest:
            abort(f'a {lane} follow-up waits {first} business day(s), so the earliest is '
                  f'{earliest.isoformat()}, not {due}.')
        reason = ' '.join((args.reason or '').split())
        if not reason:
            abort('a follow-up plan needs the conversation-based reason.')
        if job.get('follow_up_plan') and (job.get('follow_up_plan') or {}).get('reviewed_at') != anchor:
            preserve_follow_up(job, anchor)
        job['follow_up_plan'] = {
            'due_on': due, 'obligation_id': f'{args.job_id}:{lane}:1:{due}',
            'lane': lane,
            'step': 1,
            'max_steps': None if lane in UNBOUNDED else len(FOLLOW_UP_GAPS[lane]),
            'reason': reason[:500],
            'reviewed_at': anchor,
            **({'anchor_at': anchor} if lane == 'silent' else {}),
        }
        job['next_follow_up'] = due
        save(jobs)
        of = '' if lane in UNBOUNDED else f' of {len(FOLLOW_UP_GAPS[lane])}'
        print(f'{args.job_id}: {lane} follow-up 1{of} due {due}.')
        return

    if args.action == 'clear':
        reason = ' '.join((args.reason or '').split())
        preserve_follow_up(job, verified_timestamp(args.at) if args.at else None)
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        job.setdefault('follow_up_history', []).append({
            'action': 'cleared', 'at': now_iso(), 'reason': reason[:500],
        })
        save(jobs)
        print(f'{args.job_id}: follow-up sequence cleared.')
        return

    plan = job.get('follow_up_plan')
    if not isinstance(plan, dict):
        if source:
            save(jobs)
        print(f'{args.job_id}: no active follow-up sequence.')
        return
    # The member sends on Upwork and confirms it in Claude Code. One send per day
    # counts once, so a repeated confirmation changes nothing.
    try:
        sent_day = datetime.date.fromisoformat(args.on) if args.on else local_day()
    except ValueError:
        abort('--on expects YYYY-MM-DD.')
    history = job.get('follow_up_history') or []
    if any(entry.get('action') == 'sent' and entry.get('on') == sent_day.isoformat()
           for entry in history):
        if source:
            save(jobs)
        print(f'{args.job_id}: this confirmed follow-up was already recorded.')
        return
    confirmation = f'manual:{sent_day.isoformat()}'
    lane = plan.get('lane')
    gaps = FOLLOW_UP_GAPS.get(lane)
    step = plan.get('step')
    last = lane not in UNBOUNDED
    if not gaps or not isinstance(step, int) or step < 1 or (last and step > len(gaps)):
        abort(f'{args.job_id}: follow-up plan is invalid; clear it and review the conversation again.')
    stamp = verified_timestamp(args.at) if args.at else now_iso()
    job['last_activity_at'] = max(job.get('last_activity_at') or '', stamp)
    job.setdefault('follow_up_history', []).append({
        'action': 'sent', 'at': stamp, 'on': sent_day.isoformat(), 'lane': lane, 'step': step,
        'confirmation': confirmation, 'due_on': plan.get('due_on') or job.get('next_follow_up'),
        'obligation_id': plan.get('obligation_id') or f"{args.job_id}:{lane}:{step}:{plan.get('due_on') or job.get('next_follow_up')}",
        **({'anchor_at': plan['anchor_at']} if lane == 'silent' else {}),
        'completed': last and step == len(gaps),
    })
    if last and step == len(gaps):
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        message = f'{args.job_id}: {lane} sequence complete after follow-up {step}.'
    else:
        next_step = step + 1
        base_day = datetime.date.fromisoformat(job['next_follow_up']) if lane == 'silent' else sent_day
        due = add_business_days(base_day, gaps[min(next_step, len(gaps)) - 1]).isoformat()
        plan['step'] = next_step
        plan['reviewed_at'] = stamp
        plan['due_on'] = due
        plan['obligation_id'] = f'{args.job_id}:{lane}:{next_step}:{due}'
        job['next_follow_up'] = due
        of = '' if not last else f' of {len(gaps)}'
        message = f'{args.job_id}: follow-up {step} sent; {next_step}{of} due {due}.'
    save(jobs)
    print(message)


def cmd_describe(args):
    """Revise the member's job summary without changing its stage or source cache."""
    text = ' '.join(args.text.split())
    if not text:
        abort('a job summary needs text.')
    jobs = load()
    find(jobs, args.job_id)['summary'] = text
    save(jobs)
    print(f'{args.job_id}: job summary updated.')


HEADLINE_WORDS = 14


def clean_headline(text):
    """The cockpit list shows this sentence whole, so it stays short."""
    text = ' '.join(str(text or '').split())
    if not text:
        abort('a headline needs text.')
    if len(text.split()) > HEADLINE_WORDS:
        abort(f'a headline has at most {HEADLINE_WORDS} words.')
    if re.search(r'[.!?]\s+\S', text):
        abort('a headline is one sentence.')
    return text


def cmd_headline(args):
    """Set the one-sentence headline the cockpit list shows for a job."""
    text = clean_headline(args.text)
    jobs = load()
    find(jobs, args.job_id)['headline'] = text
    save(jobs)
    print(f'{args.job_id}: headline updated.')


def cmd_assess(args):
    """Replace one model-written assessment after the full posting was read."""
    value = read_json_arg(args.file)
    allowed = {'niche_fit', 'score', 'rationale', 'summary', 'headline', 'trap'}
    if not isinstance(value, dict) or set(value) - allowed:
        abort('assessment needs only niche_fit, score, rationale, summary, optional headline and optional trap.')
    headline = clean_headline(value['headline']) if str(value.get('headline') or '').strip() else ''
    if not isinstance(value.get('niche_fit'), int) or not 0 <= value['niche_fit'] <= 10:
        abort('assessment niche_fit must be an integer from 0 to 10.')
    if not isinstance(value.get('score'), int) or not 0 <= value['score'] <= 10:
        abort('assessment score must be an integer from 0 to 10.')
    rationale = ' '.join(str(value.get('rationale') or '').split())
    summary = ' '.join(str(value.get('summary') or '').split())
    if not rationale or not summary:
        abort('assessment needs a rationale and summary.')
    jobs = load()
    job = find(jobs, args.job_id)
    job.update(niche_fit=value['niche_fit'], score=value['score'], rationale=rationale, summary=summary,
               grade=value['score'])
    if headline:
        job['headline'] = headline
    trap = ' '.join(str(value.get('trap') or '').split())
    if trap:
        job['trap'] = trap
    else:
        job.pop('trap', None)
    save(jobs)
    print(f'{args.job_id}: assessment updated to {value["score"]}/10 from the full posting.')


def parse_verified_timestamp(value):
    """Canonicalize a nonfuture zoned timestamp, or return None."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    stamp = stamp.astimezone(datetime.timezone.utc)
    if stamp > datetime.datetime.now(datetime.timezone.utc):
        return None
    return stamp.isoformat()


def verified_timestamp(value):
    """A real platform event has a timezone and cannot be in the future."""
    stamp = parse_verified_timestamp(value)
    if stamp is None:
        abort('an observed event needs a valid nonfuture ISO timestamp with a timezone.')
    return stamp


def freeze_speed_to_lead(job):
    """Refresh exact seconds from source times; keep the scalar after pruning."""
    posted = parse_verified_timestamp(job.get('posted_date'))
    applied = parse_verified_timestamp(job.get('applied_at'))
    if posted and applied:
        lag = (datetime.datetime.fromisoformat(applied)
               - datetime.datetime.fromisoformat(posted)).total_seconds()
        if lag >= 0:
            job['speed_to_lead_s'] = int(lag)


def cmd_observe(args):
    """Record an observed event without changing stage or history."""
    if args.event == 'call':
        args.event = 'call_held'
    expected_sources = {'applied': ('upwork-proposal',), 'replied': ('upwork-thread',),
                        'proposal_sent': ('member',), 'proposal_viewed': ('upwork-proposal',), 'opened': ('pitch-click',),
                        'pitch_opened': ('pitch-click',), 'call_booked': ('member', 'upwork-thread', 'upwork-meeting'),
                        'call_held': ('recorder', 'member', 'upwork-meeting'),
                        'offered': ('upwork-offer', 'member'), 'won': ('upwork-contract', 'member')}
    sources = expected_sources[args.event]
    if args.event in ('proposal_sent', 'call_booked', 'call_held') and args.source is None:
        args.source, args.verified = 'member', True
    if not args.verified or args.source not in sources:
        abort(f'{args.event} observations require --verified --source {"|".join(sources)}.')
    event_at = verified_timestamp(args.timestamp)
    jobs = load()
    job = find(jobs, args.job_id)
    evidence_key = f'{args.event}_observation'
    previous = job.get(evidence_key)
    previous_at = parse_verified_timestamp(job.get(f'{args.event}_at'))
    if args.event == 'call_booked' and job.get('call_booked_at'):
        try:
            booked = datetime.datetime.fromisoformat(job['call_booked_at'].replace('Z', '+00:00'))
            if booked.tzinfo is not None:
                previous_at = booked.astimezone(datetime.timezone.utc).isoformat()
        except ValueError:
            pass
    previous_valid = (isinstance(previous, dict) and previous.get('verified') is True
                      and previous.get('source') in sources and previous_at is not None)
    if args.event in ('pitch_opened', 'opened'):
        send = 'applied_at' if args.event == 'pitch_opened' else 'proposal_sent_at'
        sent = parse_verified_timestamp(job.get(send))
        if not sent or event_at <= sent:
            abort(f'{args.event} needs a human hit after {send}.')
        previous_valid = previous_valid and previous_at > sent
    if previous_valid and previous_at <= event_at:
        print(f'{args.job_id}: verified {args.event} time already recorded.')
        return
    job[f'{args.event}_at'] = event_at
    job[evidence_key] = {
        'source': args.source,
        'verified': True,
        'observed_at': now_iso(),
        **({'kind': 'booking-confirmed'} if args.event == 'call_booked' else {}),
        **({'kind': 'flag-observed', 'event_time_known': False} if args.event == 'proposal_viewed' else {}),
    }
    if args.event == 'call_held':
        job['call_no_show'] = False
        session_id = getattr(args, 'session_id', None) or job.get('call_session_id')
        if session_id:
            session = job.setdefault('call_sessions', {}).setdefault(session_id, {})
            session.update(held_at=event_at, no_show=False)
    if args.event in ('call_booked', 'call_held'):
        if args.event == 'call_held' or not job.get('call_held_at'):
            job['call_at'] = event_at
            job['call_observation'] = job[evidence_key]
    if args.event == 'applied':
        freeze_application_facts(job)
        job.pop('application_date_unknown', None)
        freeze_speed_to_lead(job)
    save(jobs)
    print(f'{args.job_id}: verified {args.event} time recorded.')


def cmd_note(args):
    """A line on the job's timeline: a call, a promise, what the client said on the phone."""
    text = ' '.join(args.text.split())
    if not text:
        abort('a note needs text.')
    jobs = load()
    job = find(jobs, args.job_id)
    job.setdefault('log', []).append({'at': now_iso(), 'text': text[:1000]})
    save(jobs)
    print(f'{args.job_id}: note added.')


def cmd_task(args):
    """Tasks on a lead or a won client: add one, tick it off, reopen or delete it."""
    jobs = load()
    job = find(jobs, args.job_id)
    tasks = job.setdefault('tasks', [])
    if args.action == 'add':
        text = ' '.join((args.text or '').split())
        if not text:
            abort('a task needs text.')
        if args.time and not args.due:
            abort('--time needs --due.')
        if args.time and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', args.time):
            abort('--time expects HH:MM in 24-hour time.')
        number = max((t['id'] for t in tasks), default=0) + 1
        tasks.append({'id': number, 'text': text[:300], 'due': parse_follow_up(args.due) if args.due else None,
                      'due_time': args.time or None, 'created_at': now_iso(), 'done_at': None})
        message = f'task {number} added'
    else:
        task = next((t for t in tasks if str(t['id']) == str(args.text)), None)
        if not task:
            abort(f'there is no task {args.text} on {args.job_id}.')
        if args.action == 'done':
            task['done_at'] = now_iso()
        elif args.action == 'reopen':
            task['done_at'] = None
        else:
            tasks.remove(task)
        message = f'task {task["id"]} {"deleted" if args.action == "delete" else args.action}'
    save(jobs)
    print(f'{args.job_id}: {message}.')


def cmd_pitch_url(args):
    """Save a hosted pitch URL separately from its local preview."""
    jobs = load()
    job = find(jobs, args.job_id)
    value = args.url.strip()
    if value == '-':
        job.pop('pitch_url', None)
    else:
        parsed = urlparse(value)
        host = (parsed.hostname or '').lower().rstrip('.')
        import ipaddress
        try:
            private = not ipaddress.ip_address(host).is_global
        except ValueError:
            private = (host in ('localhost', '') or host.endswith(('.localhost', '.local', '.test', '.invalid'))
                       or '.' not in host or bool(re.fullmatch(r'[\d.]+', host)))
        if parsed.scheme != 'https' or private or parsed.username or parsed.password or any(c.isspace() for c in value):
            abort('use the public HTTPS URL of your hosted pitch page, not the local preview.')
        job['pitch_url'] = value
    save(jobs)
    print(f'{args.job_id}: pitch link {"removed" if value == "-" else "saved"}.')


def cmd_sent(args):
    """Freeze the actual submitted letter or an explicit member-confirmed match."""
    jobs = load()
    job = find(jobs, args.job_id)
    folder = jobs_dir() / args.job_id
    sent = folder / 'application.sent.md'
    if not args.file and not args.confirmed_match:
        abort('confirm that submitted text matches the draft (--confirmed-match), or supply --file actual submitted text.')
    application = pathlib.Path(args.file) if args.file else folder / 'application.md'
    if not application.is_file():
        abort(f'{application} is missing; the submitted application was not recorded.')
    answers = read_json_arg(args.answers_file) if args.answers_file else None
    if args.bid is not None and numeric(args.bid) is None:
        abort('submitted bid needs a non-negative finite amount.')
    if not sent.exists():
        with sent.open('xb') as handle:
            handle.write(application.read_bytes())
    elif sent.read_bytes() != application.read_bytes():
        abort('a different submitted copy already exists; reconcile it explicitly before replacing evidence.')
    if args.answers_file:
        (folder / 'answers.sent.json').write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.bid is not None:
        job['submission_bid'] = args.bid
    job['application_sent_copy'] = True
    job['application_sent_verified'] = True
    save(jobs)
    print(f'{args.job_id}: submitted application kept at {shown(sent)}.')


def no_show_candidate(job):
    """An overdue booking needs member confirmation, never an inferred no-show."""
    session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
    if session.get('cancelled') or session.get('held_at') or session.get('no_show') or (job.get('call_no_show') and not session):
        return False
    if job.get('call_held_at') and not session:
        return False
    try:
        at = datetime.datetime.fromisoformat(str(job.get('call_scheduled_at')).replace('Z', '+00:00'))
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=member_zone())
    return at + datetime.timedelta(hours=24) < datetime.datetime.now(datetime.timezone.utc)


def cmd_get(args):
    """Exactly one record as JSON. The cheap way to one job."""
    job = dict(find(load(), args.job_id))
    if no_show_candidate(job):
        job['no_show_candidate'] = True
    print(json.dumps(job, indent=2, ensure_ascii=False))


def cmd_list(args):
    jobs = load()
    if args.status:
        jobs = [j for j in jobs if j.get('status') == args.status]
    jobs.sort(key=lambda j: j.get('score') or 0, reverse=True)
    total = len(jobs)
    shown = jobs[:args.limit] if args.limit else jobs
    for j in shown:
        candidate = '  no_show_candidate' if no_show_candidate(j) else ''
        follow = f'  follow up {j["next_follow_up"]}' if j.get('next_follow_up') else ''
        print(f'{j.get("score", "?"):>3}  {j.get("status", "?"):<8} {j.get("id")}  {j.get("title", "")[:70]}{follow}{candidate}')
    if len(shown) < total:
        print(f'... {total - len(shown)} more (--limit 0 shows all).')


def application_day(job):
    """The recorded application date in local time; no later-stage guesses."""
    if job.get('imported') or job.get('application_date_unknown'):
        return None
    value = job.get('applied_at') or next(
        (h.get('at') for h in job.get('history', [])
         if isinstance(h, dict) and h.get('status') == 'applied'), None)
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return local_day(stamp).isoformat()


def applied_on(jobs, day):
    return sum(application_day(job) == day for job in jobs)


def cmd_summary(args):
    """The whole pipeline in about twenty lines, instead of reading the raw file."""
    jobs = load()
    if not jobs:
        print('No jobs in the pipeline yet.')
        return
    today = local_day().isoformat()
    counts = {s: 0 for s in STATUSES}
    for j in jobs:
        counts[j.get('status', 'new')] = counts.get(j.get('status', 'new'), 0) + 1

    print(f'{len(jobs)} jobs in the pipeline.\n')
    for s in STATUSES:
        if counts[s]:
            print(f'  {counts[s]:3d}  {s}')

    reached = sum(counts[s] for s in ('applied', 'replied', 'call', 'offer', 'won'))
    print(f'\n  {applied_on(jobs, today)} application(s) sent today.')
    if counts['new'] and not reached:
        print('  NOTE: nothing past "new". The funnel stops before the application.')

    due = sorted((j for j in jobs if j.get('next_follow_up') and j['next_follow_up'] <= today
                  and j.get('status') not in ('lost', 'skipped')), key=lambda j: j['next_follow_up'])
    if due:
        print(f'\nFollow-ups due ({len(due)}):')
        for j in due[:10]:
            print(f'  {j["next_follow_up"]}  {j.get("id")}  {j.get("title", "")[:60]}')

    candidates = [j for j in jobs if no_show_candidate(j)]
    if candidates:
        print('\nno_show_candidate (confirm with the member):')
        for j in candidates:
            print(f'  {j["id"]}  scheduled {j["call_scheduled_at"]}')

    best = sorted((j for j in jobs if j.get('status') == 'new'),
                  key=lambda j: j.get('score') or 0, reverse=True)[:8]
    if best:
        print(f'\nBest untouched ({len(best)} of {counts["new"]}):')
        for j in best:
            print(f'  {j.get("score", "?"):>3}  {j.get("id")}  {j.get("title", "")[:60]}')


def cmd_prune(args):
    """Drops cached Upwork content older than --hours. Your own work stays."""
    jobs = load()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now_utc - datetime.timedelta(hours=args.hours)
    chat_cutoff = now_utc - datetime.timedelta(hours=chat_keep_hours())
    hits = fields = 0
    for j in jobs:
        details = j.get('details') or {}
        cached_at = details.get('_cached_at') or {}
        fresh_details = {}
        for key, value in details.items():
            if key in ('fetched_at', '_cached_at'):
                continue
            if key in MEMBER_DETAIL_FIELDS:
                fresh_details[key] = value
                continue
            try:
                fetched = datetime.datetime.fromisoformat(str(cached_at.get(key) or details.get('fetched_at') or j.get('found_at', '')).replace('Z', '+00:00'))
                if fetched.tzinfo and fetched >= cutoff:
                    fresh_details[key] = value
            except ValueError:
                pass
        if fresh_details:
            fresh_details['fetched_at'] = details.get('fetched_at')
            fresh_details['_cached_at'] = {key: cached_at.get(key) or details.get('fetched_at')
                                           for key in fresh_details
                                           if key != 'fetched_at' and key not in MEMBER_DETAIL_FIELDS}
        try:
            found = datetime.datetime.fromisoformat(str(j.get('found_at', '')).replace('Z', '+00:00'))
        except ValueError:
            found = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        if found.tzinfo is None:
            found = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        if found >= cutoff:
            continue
        present = [f for f in CACHED_FIELDS if j.get(f) not in (None, '', {}) and not (f == 'details' and fresh_details == details)]
        if not present:
            continue
        hits += 1
        fields += len(present)
        if not args.dry_run:
            for f in present:
                j.pop(f, None)
            if fresh_details:
                j['details'] = fresh_details
            j['cache_pruned_at'] = now_iso()
    # A saved client thread is Upwork's content as well, whatever job it belongs to.
    # Client threads and call transcripts follow chat_keep_hours().
    threads = [t for t in jobs_dir().glob('*/thread.json')
               if t.is_file() and datetime.datetime.fromtimestamp(t.stat().st_mtime, datetime.timezone.utc) < chat_cutoff]
    calls = [p for p in jobs_dir().glob('*/call.md')
             if p.is_file() and datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc) < chat_cutoff]
    # The saved profile and highlights are Upwork's answers about the member, so they
    # expire like any other response. Every reader treats them as optional.
    #
    # data/fit.json is deliberately not in this list. It holds the member's own
    # judgement of how well each candidate fits their niche, which is their work and
    # not Upwork's content, and deleting it every day would throw away the input
    # /find-jobs learns from. The same goes for the skip reasons.
    raw_cache = [p for pattern in ('search/*.json', 'details/*.json', 'candidates.json',
                                   'profile.json', 'highlights.json', 'contracts.json')
                 for p in data_dir().glob(pattern)
                 if p.is_file() and datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc) < cutoff]
    previews = [p for p in jobs_dir().glob('*/.pitch-preview.png')
                if p.is_file() and datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc) < cutoff]
    if args.dry_run:
        print(f'DRY RUN: {hits} of {len(jobs)} jobs older than {args.hours}h, '
              f'{fields} cached fields, {len(threads)} saved threads, {len(calls)} call transcripts, {len(raw_cache)} raw cache files and '
              f'{len(previews)} pitch previews would be removed. Nothing changed.')
        return
    if hits:
        save(jobs)
    for t in threads:
        t.unlink()
    for call in calls:
        call.unlink()
    for item in raw_cache:
        item.unlink()
    for preview in previews:
        preview.unlink()
    print(f'{hits} jobs pruned, {fields} cached fields removed, {len(threads)} saved threads, {len(calls)} call transcripts, '
          f'{len(raw_cache)} raw cache files and {len(previews)} pitch previews deleted.')


def protected_search_lead(job, now_utc):
    """A published page, application, decision or fresh intake keeps the lead."""
    if (job.get('pitch_url') or job.get('status') != 'new'
            or job.get('applied_at') or job.get('application_date_unknown')
            or (jobs_dir() / str(job.get('id')) / 'application.md').is_file()):
        return True
    if any(event.get('status') in ('applied', 'replied', 'call', 'offer', 'won')
           for event in job.get('history', []) if isinstance(event, dict)):
        return True
    try:
        found = datetime.datetime.fromisoformat(str(job.get('found_at', '')).replace('Z', '+00:00'))
    except ValueError:
        return True
    if found.tzinfo is None:
        found = found.replace(tzinfo=datetime.timezone.utc)
    return found > now_utc - datetime.timedelta(hours=24)


def search_reset_record(job):
    """Archive the decision and dates, never a copy of cached Upwork content."""
    allowed = ('id', 'title', 'status', 'found_at', 'status_updated_at', 'applied_at',
               'call_at', 'next_follow_up', 'cache_pruned_at', 'skip_reason')
    record = {key: job[key] for key in allowed if key in job}
    if not record.get('skip_reason'):
        reasons = re.findall(r'not a fit:\s*([^.]*(?:\.|$))', job.get('notes') or '', re.I)
        if reasons:
            record['skip_reason'] = '; '.join(reason.strip().rstrip('.') for reason in reasons)
    return record


def cmd_reset_search(args):
    """Remove expired unused search leads while preserving the member's work."""
    jobs = load()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    def searched(job):
        return any(str(source).lower().startswith(('recommended', 'query-', 'title-', 'search-'))
                   for source in job.get('found_via', []))

    removed = [job for job in jobs if searched(job)
               and not protected_search_lead(job, now_utc)]
    if args.dry_run:
        print(f'DRY RUN: {len(removed)} never-applied search leads would be removed. '
              f'{len(jobs) - len(removed)} protected leads would stay. Nothing changed.')
        return
    if not removed:
        print(f'0 search leads removed. {len(jobs)} protected leads kept.')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    archive = data_dir() / 'search-resets' / stamp
    archive.mkdir(parents=True, exist_ok=False)
    records = [search_reset_record(job) for job in removed]
    (archive / 'jobs.json').write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
    save([job for job in jobs if job not in removed])

    import shutil
    archived_workspaces = 0
    for job in removed:
        source = jobs_dir() / str(job.get('id'))
        if source.is_dir():
            target = archive / 'jobs' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            archived_workspaces += 1
    print(f'{len(removed)} never-applied search leads removed; {archived_workspaces} job workspaces archived. '
          f'{len(jobs) - len(removed)} protected leads kept. Backup: {archive}')


def cmd_archive(args):
    """Remove exact pipeline records after making a recoverable local backup."""
    jobs = load()
    requested = list(dict.fromkeys(args.job_ids))
    by_id = {str(job.get('id')): job for job in jobs}
    missing = [job_id for job_id in requested if job_id not in by_id]
    if missing:
        abort(f'job id(s) not in the pipeline: {", ".join(missing)}. Nothing was changed.')
    removed = [by_id[job_id] for job_id in requested]
    if args.dry_run:
        print(f'DRY RUN: {len(removed)} exact pipeline records would be archived and removed. '
              f'{len(jobs) - len(removed)} records would stay. Nothing changed.')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    archive = data_dir() / 'pipeline-archives' / stamp
    archive.mkdir(parents=True, exist_ok=False)
    (archive / 'jobs.json').write_text(json.dumps(removed, indent=2, ensure_ascii=False), encoding='utf-8')

    import shutil
    archived_workspaces = 0
    for job in removed:
        source = jobs_dir() / str(job.get('id'))
        if source.is_dir():
            target = archive / 'jobs' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)
            archived_workspaces += 1

    removed_ids = set(requested)
    save([job for job in jobs if str(job.get('id')) not in removed_ids])
    for job_id in requested:
        source = jobs_dir() / job_id
        if source.is_dir():
            shutil.rmtree(source)
    print(f'{len(removed)} pipeline records removed; {archived_workspaces} job workspaces archived. '
          f'{len(jobs) - len(removed)} records kept. Backup: {archive}')


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

    p = sub.add_parser('assess', help='Replace a scored assessment after reading the full posting.')
    p.add_argument('job_id')
    p.add_argument('--file', metavar='PATH', required=True, help='JSON object. "-" reads stdin.')
    p.set_defaults(func=cmd_assess)

    p = sub.add_parser('describe', help='Revise the member-written job summary, not the source posting.')
    p.add_argument('job_id')
    p.add_argument('text')
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser('headline', help='Set the one-sentence headline the cockpit list shows.')
    p.add_argument('job_id')
    p.add_argument('text')
    p.set_defaults(func=cmd_headline)

    p = sub.add_parser('observe', help='Record a verified Upwork event time without moving the job.')
    p.add_argument('job_id')
    p.add_argument('event', choices=('applied', 'replied', 'proposal_sent', 'proposal_viewed', 'opened', 'pitch_opened', 'call', 'call_booked', 'call_held', 'offered', 'won'))
    p.add_argument('timestamp')
    p.add_argument('--source', choices=('upwork-proposal', 'upwork-thread', 'upwork-meeting', 'member', 'pitch-click', 'recorder', 'upwork-offer', 'upwork-contract'))
    p.add_argument('--verified', action='store_true')
    p.add_argument('--session-id', help='The session this call observation belongs to.')
    p.set_defaults(func=cmd_observe)

    p = sub.add_parser('set', help='Move a job to a status.')
    p.add_argument('job_id')
    p.add_argument('status')
    p.add_argument('--follow-up')
    p.add_argument('--note')
    p.add_argument('--applied-at', help='Verified submission timestamp, or unknown when sync only knows the current stage.')
    p.add_argument('--call-at', help='The day the call happens, YYYY-MM-DD. Until then the lead is left alone.')
    p.add_argument('--force', action='store_true', help='Confirm a backward move or reopen a closed lead.')
    p.add_argument('--activity-at', help='Observed activity time for sync; otherwise the member acted now.')
    p.set_defaults(func=cmd_set)

    p = sub.add_parser('acted', help='Record activity without moving a lead.')
    p.add_argument('job_id')
    p.add_argument('--note', required=True)
    p.add_argument('--at', help='Verified message time, for sync replay.')
    p.set_defaults(func=cmd_acted)

    p = sub.add_parser('reconcile', help='Merge a synthetic alias into a verified real job id.')
    p.add_argument('old_id')
    p.add_argument('job_id')
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser('record', help='Store connector identity and workflow markers.')
    p.add_argument('job_id')
    p.add_argument('--file', required=True, help='JSON metadata. "-" reads stdin.')
    p.set_defaults(func=cmd_record)

    p = sub.add_parser('follow-up', help='Plan, advance or clear a contextual follow-up sequence.')
    p.add_argument('job_id')
    p.add_argument('action', choices=('plan', 'sent', 'clear'))
    p.add_argument('--lane', choices=tuple(FOLLOW_UP_GAPS))
    p.add_argument('--due')
    p.add_argument('--reason')
    p.add_argument('--on', help='Date a follow-up was sent, for replay and tests.')
    p.add_argument('--at', help='Verified message time, for sync replay.')
    p.set_defaults(func=cmd_follow_up)

    p = sub.add_parser('note', help='Add a line to a job\'s timeline.')
    p.add_argument('job_id')
    p.add_argument('text')
    p.set_defaults(func=cmd_note)

    p = sub.add_parser('task', help='Tasks on a lead or client.')
    p.add_argument('job_id')
    p.add_argument('action', choices=('add', 'done', 'reopen', 'delete'))
    p.add_argument('text', help='The task text for add, the task number otherwise.')
    p.add_argument('--due')
    p.add_argument('--time')
    p.set_defaults(func=cmd_task)

    p = sub.add_parser('pitch-url', help='Save the public URL of a hosted pitch page.')
    p.add_argument('job_id')
    p.add_argument('url', help='Public HTTPS URL, or "-" to remove it.')
    p.set_defaults(func=cmd_pitch_url)

    p = sub.add_parser('sent', help='Keep the application as submitted, once.')
    p.add_argument('job_id')
    p.add_argument('--confirmed-match', action='store_true')
    p.add_argument('--file', help='The actual submitted text.')
    p.add_argument('--answers-file', help='Actual submitted screening answers as JSON.')
    p.add_argument('--bid', type=float, help='Actual submitted bid.')
    p.set_defaults(func=cmd_sent)

    p = sub.add_parser('get', help='One record as JSON.')
    p.add_argument('job_id')
    p.set_defaults(func=cmd_get)

    p = sub.add_parser('list', help='Jobs by score.')
    p.add_argument('--status')
    p.add_argument('--limit', type=int, default=25, help='0 shows all.')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('summary', help='The pipeline in about twenty lines.')
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser('archive', help='Remove exact pipeline records after archiving their files.')
    p.add_argument('job_ids', nargs='+')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser('reset-search', help='Remove never-applied search leads and archive their files.')


    p.add_argument('--with-skipped', action='store_true',


                     help='accepted for compatibility; skipped leads always stay')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_reset_search)

    p = sub.add_parser('prune', help="Drop Upwork content older than 24h (Upwork's caching rule). Saved chats follow KEEP_CHAT_HOURS, 90 days by default.")
    p.add_argument('--hours', type=int, default=24)
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_prune)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    writes_before = _jobs_writes
    def execute():
        if getattr(args, 'job_id', None):
            aliases = {alias: job['id'] for job in load() for alias in job.get('aliases', [])}
            args.job_id = aliases.get(args.job_id, args.job_id)
        args.func(args)
    if args.cmd in ('get', 'list', 'summary') or (args.cmd == 'add' and args.check):
        execute()
    else:
        with transaction():
            execute()
        if _jobs_writes > writes_before and (
                args.cmd == 'observe' or (args.cmd == 'set' and args.status == 'applied')
                or (args.cmd == 'follow-up' and args.action == 'sent')):
            check_badges(args.job_id)
    return 0


if __name__ == '__main__':
    sys.exit(main())
