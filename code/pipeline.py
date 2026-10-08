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
    python3 code/pipeline.py follow-up <job_id> plan --lane active|cold|reactivation [--due <date> --reason "..."]
    python3 code/pipeline.py follow-up <job_id> sent [--on YYYY-MM-DD]
    python3 code/pipeline.py follow-up <job_id> clear --reason "..." [--replied]
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
import os
import pathlib
import re
import sys
import tempfile
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUSES = ('new', 'applied', 'replied', 'call', 'offer', 'won', 'lost', 'skipped')
ACTIVE = ('applied', 'replied', 'call', 'offer')
CLOSED = ('won', 'lost', 'skipped')

# Calendar days, each counted from the message before, so a missed morning cannot
# stretch or compress a sequence. 'active' follows the member's unanswered message
# in a sales conversation: two follow-ups, then the lead is cold (never Lost on its
# own). 'cold' is the one reactivation offer after that. 'reactivation' is for won clients.
FOLLOW_UP_GAPS = {
    'active': (3, 7),
    'cold': (30,),
    'reactivation': (30, 60),
}
SALES = ('replied', 'call', 'offer')

# Old unused jobs beyond this many fall out when new ones arrive, oldest first.
# Fresh intake and anything carrying the member's work never fall out.
KEEP = 500

# Upwork's terms cap caching of their content at 24 hours. These fields hold
# Upwork's words and numbers; score, rationale, status, notes and history are
# the member's own work and stay.
CACHED_FIELDS = ('description', 'client', 'budget', 'job_type', 'posted_date', 'details')


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
MEMBER_DETAIL_FIELDS = ('bid_amount', 'price_estimate')

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
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        abort(f'{path} is not valid JSON. Nothing was changed.')


def save(jobs):
    """Writes through a temp file, so a crash mid-write never leaves half a pipeline."""
    path = jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.pipeline-', suffix='.tmp', delete=False) as handle:
        tmp = pathlib.Path(handle.name)
        json.dump(jobs, handle, indent=2, ensure_ascii=False)
    try:
        os.replace(tmp, path)
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
    """+Nd or a date. N counts calendar days, because every lane gap does."""
    m = re.match(r'^\+(\d+)d$', value)
    if m:
        return (datetime.date.today() + datetime.timedelta(days=int(m.group(1)))).isoformat()
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        abort(f'--follow-up expects +Nd or YYYY-MM-DD, got: {value}')


def unanswered_turns(messages):
    """The member's message times since the client last wrote, oldest first.

    One turn per calendar day: three bubbles sent the same morning are one message to
    the client, and a client message resets the count. Messages come oldest first.
    """
    turns = []
    for message in messages or []:
        if not isinstance(message, dict) or message.get('kind') == 'event':
            continue
        stamp = parse_verified_timestamp(message.get('at'))
        if message.get('from') == 'client':
            turns = []
        elif message.get('from') == 'me' and stamp and (not turns or turns[-1][:10] != stamp[:10]):
            turns.append(stamp)
    return turns


def sequence_stopped(job):
    """A sequence that ran out or was stopped restarts only after the client writes."""
    last = (job.get('follow_up_history') or [{}])[-1]
    if last.get('action') == 'cleared':
        return not (last.get('by') == 'client' or str(last.get('reason') or '').startswith('The client replied'))
    return bool(last.get('completed'))


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
        # A stage change means the conversation moved, so the lead is no longer cold.
        job.pop('cold_since', None)
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
    lane = (job.get('follow_up_plan') or {}).get('lane')
    if args.status in ('applied', 'lost', 'skipped'):
        job['next_follow_up'] = None
        job.pop('follow_up_plan', None)
    elif args.status == 'won' and lane != 'reactivation' and not args.follow_up:
        # Winning ends a sales sequence. It must not end the reactivation lane, which
        # exists only for won clients: recording a sent message with `set won` used to
        # delete that plan, and the 60-day second touch went with it.
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
    if getattr(args, 'call_at', None):
        job['call_at'] = parse_follow_up(args.call_at)
    elif args.status != 'call':
        job.pop('call_at', None)
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
    allowed = {'proposal_id', 'room_id', 'contract_id', 'contract_client', 'client_slug',
               'submission_checked_at', 'result_recorded_at', 'next_follow_up', 'follow_up_source'}
    if not isinstance(value, dict) or not value or set(value) - allowed:
        abort('metadata needs only ' + ', '.join(sorted(allowed)) + '.')
    for key, item in value.items():
        if key == 'follow_up_source':
            if item not in (None, 'waiting'):
                abort('follow_up_source needs waiting or null to remove it.')
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
    changed = False
    for key, item in value.items():
        if key == 'follow_up_source' and item is None:
            changed = key in job or changed
            job.pop(key, None)
        elif (key not in ('submission_checked_at', 'result_recorded_at') or not job.get(key)) and job.get(key) != item:
            job[key] = item
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
        if not args.lane:
            abort('plan needs --lane.')
        try:
            thread = json.loads((jobs_dir() / args.job_id / 'thread.json').read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            abort('sync this conversation before planning a follow-up.')
        if not str(thread.get('room_id') or '').strip():
            abort('this conversation has no room; a freelancer cannot message first.')
        lane = args.lane
        if lane == 'reactivation' and job.get('status') != 'won':
            abort('reactivation is only for a previous or current client in won.')
        if lane != 'reactivation' and job.get('status') not in SALES:
            abort('sales follow-ups need a lead that has answered; applied proposals cannot message first.')
        # The cadence counts from the member's unanswered messages in the saved thread:
        # one is the message itself, two means follow-up 1 went out, three means both did.
        turns = unanswered_turns(thread.get('messages'))
        step = 1
        if lane != 'reactivation':
            if not turns:
                abort('the client wrote last; that needs a reply, not a follow-up.')
            if lane == 'active' and len(turns) > len(FOLLOW_UP_GAPS['active']):
                lane = 'cold'
            elif lane == 'active':
                step = len(turns)
        gaps = FOLLOW_UP_GAPS[lane]
        reason = ' '.join((args.reason or '').split())
        if args.due:
            # Off the cadence (a promised date, an open question) is a judgement, so it says why.
            if not reason:
                abort('a follow-up off the cadence needs the conversation-based reason.')
            due = parse_follow_up(args.due)
        elif turns:
            base = datetime.date.fromisoformat(turns[-1][:10])
            due = (base + datetime.timedelta(days=gaps[step - 1])).isoformat()
            reason = reason or f'No answer since {base.isoformat()}.'
        else:
            abort('reactivation needs --due and the reason to reconnect.')
        if lane == 'cold':
            job['cold_since'] = job.get('cold_since') or turns[-1]
        else:
            job.pop('cold_since', None)
        job['follow_up_plan'] = {
            'lane': lane,
            'step': step,
            'max_steps': len(gaps),
            'reason': reason[:500],
            'reviewed_at': now_iso(),
        }
        job['next_follow_up'] = due
        save(jobs)
        print(f'{args.job_id}: {lane} follow-up {step} of {len(gaps)} due {due}.')
        return

    if args.action == 'clear':
        reason = ' '.join((args.reason or '').split())
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        entry = {'action': 'cleared', 'at': now_iso(), 'reason': reason[:500]}
        if args.replied:
            # The client wrote, so the lead is warm again and a new sequence may start.
            job.pop('cold_since', None)
            entry['by'] = 'client'
        job.setdefault('follow_up_history', []).append(entry)
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
        sent_day = datetime.date.fromisoformat(args.on) if args.on else datetime.date.today()
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
    if not gaps or not isinstance(step, int) or step < 1:
        abort(f'{args.job_id}: follow-up plan is invalid; clear it and review the conversation again.')
    # A plan from the old endless lane can sit past the last step; it ends here too.
    final = step >= len(gaps)
    stamp = verified_timestamp(args.at) if args.at else now_iso()
    job['last_activity_at'] = max(job.get('last_activity_at') or '', stamp)
    job.setdefault('follow_up_history', []).append({
        'action': 'sent', 'at': stamp, 'on': sent_day.isoformat(), 'lane': lane, 'step': step,
        'confirmation': confirmation,
        'completed': final,
    })
    if final and lane == 'active':
        # Two follow-ups without an answer: cold, never Lost, and one offer to reactivate.
        due = (sent_day + datetime.timedelta(days=FOLLOW_UP_GAPS['cold'][0])).isoformat()
        job['cold_since'] = stamp
        job['follow_up_plan'] = {
            'lane': 'cold', 'step': 1, 'max_steps': len(FOLLOW_UP_GAPS['cold']),
            'reason': 'Two follow-ups without an answer; offer one reactivation.',
            'reviewed_at': stamp,
        }
        job['next_follow_up'] = due
        message = f'{args.job_id}: follow-up {step} sent; the lead is cold, reactivation offer due {due}.'
    elif final:
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        message = f'{args.job_id}: {lane} sequence complete after follow-up {step}.'
    else:
        next_step = step + 1
        due = (sent_day + datetime.timedelta(days=gaps[next_step - 1])).isoformat()
        plan['step'] = next_step
        plan['reviewed_at'] = stamp
        job['next_follow_up'] = due
        message = f'{args.job_id}: follow-up {step} sent; {next_step} of {len(gaps)} due {due}.'
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


def cmd_observe(args):
    """Record one verified Upwork event without changing stage or history."""
    expected_source = {'applied': 'upwork-proposal', 'replied': 'upwork-thread'}[args.event]
    if not args.verified or args.source != expected_source:
        abort(f'{args.event} observations require --verified --source {expected_source}.')
    event_at = verified_timestamp(args.timestamp)
    jobs = load()
    job = find(jobs, args.job_id)
    evidence_key = f'{args.event}_observation'
    previous = job.get(evidence_key)
    previous_at = parse_verified_timestamp(job.get(f'{args.event}_at'))
    previous_valid = (isinstance(previous, dict) and previous.get('verified') is True
                      and previous.get('source') == expected_source and previous_at is not None)
    if previous_valid and previous_at <= event_at:
        print(f'{args.job_id}: verified {args.event} time already recorded.')
        return
    job[f'{args.event}_at'] = event_at
    job[evidence_key] = {
        'source': args.source,
        'verified': True,
        'observed_at': now_iso(),
    }
    if args.event == 'applied':
        job.pop('application_date_unknown', None)
        # posted_date is Upwork content and prune deletes it after 24 hours, so the
        # one number it is for is worked out here, while it is still there.
        posted = parse_verified_timestamp(job.get('posted_date'))
        if posted:
            lag = (datetime.datetime.fromisoformat(event_at)
                   - datetime.datetime.fromisoformat(posted)).total_seconds()
            if lag >= 0:
                job['speed_to_lead_s'] = int(lag)
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
    return sum(1 for j in jobs if not j.get('imported') and not j.get('application_date_unknown') and str(j.get('applied_at') or next(
        (h.get('at') for h in j.get('history', []) if h.get('status') == 'applied'), ''))[:10] == day)


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
            continue
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
    # Chats alone follow chat_keep_hours(); see there for why nothing else does.
    threads = [t for t in jobs_dir().glob('*/thread.json')
               if t.is_file() and datetime.datetime.fromtimestamp(t.stat().st_mtime, datetime.timezone.utc) < chat_cutoff]
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
              f'{fields} cached fields, {len(threads)} saved threads, {len(raw_cache)} raw cache files and '
              f'{len(previews)} pitch previews would be removed. Nothing changed.')
        return
    if hits:
        save(jobs)
    for t in threads:
        t.unlink()
    for item in raw_cache:
        item.unlink()
    for preview in previews:
        preview.unlink()
    print(f'{hits} jobs pruned, {fields} cached fields removed, {len(threads)} saved threads, '
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
    p.add_argument('event', choices=('applied', 'replied'))
    p.add_argument('timestamp')
    p.add_argument('--source', required=True, choices=('upwork-proposal', 'upwork-thread'))
    p.add_argument('--verified', action='store_true', required=True)
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
    p.add_argument('--replied', action='store_true', help='clear: the client wrote; the lead is warm again.')
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
    if args.cmd in ('get', 'list', 'summary') or (args.cmd == 'add' and args.check):
        args.func(args)
    else:
        with transaction():
            args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
