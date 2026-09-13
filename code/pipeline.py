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
    python3 code/pipeline.py describe <job_id> "Plain-language summary of the work"
    python3 code/pipeline.py observe <job_id> applied|replied <ISO timestamp> --source <source> --verified
    python3 code/pipeline.py set <job_id> <status> [--follow-up +3d|YYYY-MM-DD] [--note "..."]
    python3 code/pipeline.py follow-up <job_id> plan --lane <lane> --due <date> --reason "..."
    python3 code/pipeline.py follow-up <job_id> sent [--on YYYY-MM-DD]
    python3 code/pipeline.py follow-up <job_id> clear --reason "..."
    python3 code/pipeline.py note <job_id> "what happened"
    python3 code/pipeline.py video <job_id> <loom or youtube link>|-
    python3 code/pipeline.py recording-links <job_id> '<json list>'
    python3 code/pipeline.py loom-review <job_id> on|off
    python3 code/pipeline.py loom-score <job_id> <0..100>
    python3 code/pipeline.py task <job_id> add "what to do" [--due +2d|YYYY-MM-DD]
    python3 code/pipeline.py task <job_id> done|reopen|delete <task_number>
    python3 code/pipeline.py lead-magnet-source <job_id> <website> --location "City, Country" [--place-id ID]
    python3 code/pipeline.py get <job_id>
    python3 code/pipeline.py list [--status new] [--limit 25]
    python3 code/pipeline.py summary
    python3 code/pipeline.py prune [--hours 24] [--dry-run]

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
STATUSES = ('new', 'applied', 'replied', 'offer', 'won', 'lost', 'skipped')
ACTIVE = ('applied', 'replied', 'offer')
CLOSED = ('won', 'lost', 'skipped')

# Gaps after each sent follow-up, in business days. Step one is scheduled by
# the reviewer from the conversation. Later steps are mechanical so a missed
# morning cannot silently stretch or compress the sequence.
FOLLOW_UP_GAPS = {
    'hot': (1, 3, 7),
    'warm': (2, 5, 10),
    'light': (3, 7),
    'reactivation': (30, 60),
}

# Untouched jobs beyond this many fall out when new ones arrive, oldest first.
# Anything a human moved past "new" is live pipeline and never falls out.
KEEP = 500

# Upwork's terms cap caching of their content at 24 hours. These fields hold
# Upwork's words and numbers; score, rationale, status, notes and history are
# the member's own work and stay.
CACHED_FIELDS = ('description', 'client', 'budget', 'job_type', 'posted_date', 'details')

# The video you recorded for a job. Only links a client can open on Upwork.
VIDEO_LINKS = ('https://www.loom.com/share/', 'https://loom.com/share/',
               'https://www.youtube.com/watch?v=', 'https://youtu.be/')


def jobs_path():
    """Where the pipeline lives. BLUEPRINT_JOBS points tests at a throwaway file."""
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBS') or ROOT / 'data' / 'jobs.json')


def jobs_dir():
    """Where each job's files live. A client thread saved there is Upwork content too."""
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBDIR') or ROOT / 'jobs')


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
    m = re.match(r'^\+(\d+)d$', value)
    if m:
        return (datetime.date.today() + datetime.timedelta(days=int(m.group(1)))).isoformat()
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
    jobs = load()
    job = find(jobs, args.job_id)
    job['status'] = args.status
    job['status_updated_at'] = now_iso()
    add_history(job, args.status)
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
    if args.status in ('lost', 'skipped') or (args.status == 'won' and not args.follow_up):
        job['next_follow_up'] = None
        job.pop('follow_up_plan', None)
    elif args.follow_up:
        job['next_follow_up'] = parse_follow_up(args.follow_up)
    if args.status not in ('replied', 'offer', 'won'):
        job.pop('follow_up_plan', None)
    if args.note:
        job['notes'] = (job.get('notes', '') + ' ' + args.note).strip()
    save(jobs)
    follow = f' (follow up {job["next_follow_up"]})' if job.get('next_follow_up') else ''
    print(f'{job["id"]} -> {args.status}{follow}')


def cmd_follow_up(args):
    """Plan, advance or stop a context-chosen follow-up sequence."""
    jobs = load()
    job = find(jobs, args.job_id)

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
        if lane != 'reactivation' and job.get('status') not in ('replied', 'offer'):
            abort('sales follow-ups need a replied or offer lead; applied proposals cannot message first.')
        due = parse_follow_up(args.due)
        reason = ' '.join((args.reason or '').split())
        if not reason:
            abort('a follow-up plan needs the conversation-based reason.')
        job['follow_up_plan'] = {
            'lane': lane,
            'step': 1,
            'max_steps': len(FOLLOW_UP_GAPS[lane]),
            'reason': reason[:500],
            'reviewed_at': now_iso(),
        }
        job['next_follow_up'] = due
        save(jobs)
        print(f'{args.job_id}: {lane} follow-up 1 of {len(FOLLOW_UP_GAPS[lane])} due {due}.')
        return

    if args.action == 'clear':
        reason = ' '.join((args.reason or '').split())
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        if reason:
            job.setdefault('follow_up_history', []).append({
                'action': 'cleared', 'at': now_iso(), 'reason': reason[:500],
            })
        save(jobs)
        print(f'{args.job_id}: follow-up sequence cleared.')
        return

    plan = job.get('follow_up_plan')
    if not isinstance(plan, dict):
        print(f'{args.job_id}: no active follow-up sequence.')
        return
    try:
        outbox = json.loads((jobs_dir() / args.job_id / 'outbox.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        abort(f'{args.job_id}: no confirmed send exists for this follow-up.')
    confirmation = str(outbox.get('confirmed_at') or '')
    if not confirmation or str(outbox.get('job_id') or '') != args.job_id:
        abort(f'{args.job_id}: no confirmed send exists for this follow-up.')
    if confirmation < str(plan.get('reviewed_at') or ''):
        abort(f'{args.job_id}: the confirmed send predates this follow-up plan.')
    if any(entry.get('confirmation') == confirmation for entry in job.get('follow_up_history') or []):
        print(f'{args.job_id}: this confirmed follow-up was already recorded.')
        return
    lane = plan.get('lane')
    gaps = FOLLOW_UP_GAPS.get(lane)
    step = plan.get('step')
    if not gaps or not isinstance(step, int) or not 1 <= step <= len(gaps):
        abort(f'{args.job_id}: follow-up plan is invalid; clear it and review the conversation again.')
    try:
        sent_day = datetime.date.fromisoformat(args.on) if args.on else datetime.date.today()
    except ValueError:
        abort('--on expects YYYY-MM-DD.')
    stamp = now_iso()
    job.setdefault('follow_up_history', []).append({
        'action': 'sent', 'at': stamp, 'on': sent_day.isoformat(), 'lane': lane, 'step': step,
        'confirmation': confirmation,
    })
    if step == len(gaps):
        job.pop('follow_up_plan', None)
        job['next_follow_up'] = None
        message = f'{args.job_id}: {lane} sequence complete after follow-up {step}.'
    else:
        next_step = step + 1
        due = add_business_days(sent_day, gaps[next_step - 1]).isoformat()
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


def cmd_video(args):
    """Links the video you recorded for this job. "-" removes it."""
    url = args.url.strip()
    jobs = load()
    job = find(jobs, args.job_id)
    if url == '-':
        job.pop('video', None)
        save(jobs)
        print(f'{args.job_id}: video link removed.')
        return
    if not url.startswith(VIDEO_LINKS) or any(c in url for c in ' "<>'):
        abort(f'expects a Loom share link or a YouTube link, got: {url}')
    job['video'] = url
    job.setdefault('log', []).append({'at': now_iso(), 'text': 'Video linked'})
    save(jobs)
    print(f'{args.job_id}: video linked.')


def cmd_recording_links(args):
    """Save optional tabs the member wants open while recording this job's Loom."""
    try:
        links = json.loads(args.links)
    except json.JSONDecodeError:
        abort('recording links must be a JSON list.')
    if not isinstance(links, list) or len(links) > 8:
        abort('recording links must be a list with at most 8 items.')
    clean = []
    for item in links:
        if not isinstance(item, dict):
            abort('each recording link needs a label and URL.')
        label = ' '.join(str(item.get('label') or '').split())
        url = str(item.get('url') or '').strip()
        parsed = urlparse(url)
        if not label or len(label) > 60:
            abort('each recording link needs a label of 60 characters or fewer.')
        if (len(url) > 500 or parsed.scheme != 'https' or not parsed.hostname
                or parsed.username or parsed.password or any(c.isspace() for c in url)):
            abort('each recording link must be a public HTTPS URL without credentials.')
        clean.append({'label': label, 'url': url})
    jobs = load()
    job = find(jobs, args.job_id)
    if clean:
        job['recording_links'] = clean
    else:
        job.pop('recording_links', None)
    save(jobs)
    print(f'{args.job_id}: {len(clean)} recording link{"s" if len(clean) != 1 else ""} saved.')


def cmd_loom_score(args):
    """Save the internal recording-quality score for analytics."""
    if not 0 <= args.score <= 100:
        abort('the Loom review score must be between 0 and 100.')
    jobs = load()
    job = find(jobs, args.job_id)
    job['loom_review_score'] = args.score
    job['loom_reviewed_at'] = now_iso()
    save(jobs)
    print(f'{args.job_id}: Loom review score saved as {args.score}/100.')


def cmd_loom_review(args):
    """Choose whether this application's recording is reviewed before drafting."""
    jobs = load()
    job = find(jobs, args.job_id)
    job['loom_review_enabled'] = args.state == 'on'
    save(jobs)
    print(f'{args.job_id}: Loom review {args.state}.')


def cmd_task(args):
    """Tasks on a lead or a won client: add one, tick it off, reopen or delete it."""
    jobs = load()
    job = find(jobs, args.job_id)
    tasks = job.setdefault('tasks', [])
    if args.action == 'add':
        text = ' '.join((args.text or '').split())
        if not text:
            abort('a task needs text.')
        number = max((t['id'] for t in tasks), default=0) + 1
        tasks.append({'id': number, 'text': text[:300], 'due': parse_follow_up(args.due) if args.due else None,
                      'created_at': now_iso(), 'done_at': None})
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


def cmd_lead_magnet_source(args):
    """Save the member-confirmed local-business identity for the SEO audit."""
    jobs = load()
    job = find(jobs, args.job_id)
    if job.get('status') not in ('replied', 'offer'):
        abort('lead magnets are available only for replied or offer leads.')
    website = args.website.strip()
    location = args.location.strip()
    place_id = args.place_id.strip()
    parsed = urlparse(website)
    host = (parsed.hostname or '').lower().rstrip('.')
    import ipaddress
    try:
        private = not ipaddress.ip_address(host).is_global
    except ValueError:
        private = (host in ('localhost', '') or host.endswith(('.localhost', '.local', '.test', '.invalid'))
                   or '.' not in host or bool(re.fullmatch(r'[\d.]+', host)))
    if parsed.scheme != 'https' or private or parsed.username or parsed.password or any(c.isspace() for c in website):
        abort("use the business's public HTTPS website.")
    if not location or len(location) > 160:
        abort('location must name the business city and country in 160 characters or fewer.')
    if len(place_id) > 220 or any(c in place_id for c in '\r\n\t'):
        abort('place ID is not valid.')
    job['lead_magnet_source'] = {
        'website': website,
        'location': location,
        'place_id': place_id,
        'language': args.language,
    }
    job['lead_magnet_source_updated_at'] = now_iso()
    save(jobs)
    print(f'{args.job_id}: lead magnet source saved.')


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
    return sum(1 for j in jobs if not j.get('application_date_unknown') and str(j.get('applied_at') or next(
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

    reached = sum(counts[s] for s in ('applied', 'replied', 'offer', 'won'))
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
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=args.hours)
    hits = fields = 0
    for j in jobs:
        details = j.get('details') or {}
        cached_at = details.get('_cached_at') or {}
        fresh_details = {}
        for key, value in details.items():
            if key in ('fetched_at', '_cached_at'):
                continue
            try:
                fetched = datetime.datetime.fromisoformat(str(cached_at.get(key) or details.get('fetched_at') or j.get('found_at', '')).replace('Z', '+00:00'))
                if fetched.tzinfo and fetched >= cutoff:
                    fresh_details[key] = value
            except ValueError:
                pass
        if fresh_details:
            fresh_details['fetched_at'] = details.get('fetched_at')
            fresh_details['_cached_at'] = {key: cached_at.get(key) or details.get('fetched_at') for key in fresh_details if key != 'fetched_at'}
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
    threads = [t for t in jobs_dir().glob('*/thread.json')
               if datetime.datetime.fromtimestamp(t.stat().st_mtime, datetime.timezone.utc) < cutoff]
    if args.dry_run:
        print(f'DRY RUN: {hits} of {len(jobs)} jobs older than {args.hours}h, '
              f'{fields} cached fields and {len(threads)} saved threads would be removed. Nothing changed.')
        return
    if hits:
        save(jobs)
    for t in threads:
        t.unlink()
    print(f'{hits} jobs pruned, {fields} cached fields removed, {len(threads)} saved threads deleted.')


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

    p = sub.add_parser('describe', help='Revise the member-written job summary, not the source posting.')
    p.add_argument('job_id')
    p.add_argument('text')
    p.set_defaults(func=cmd_describe)

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
    p.set_defaults(func=cmd_set)

    p = sub.add_parser('follow-up', help='Plan, advance or clear a contextual follow-up sequence.')
    p.add_argument('job_id')
    p.add_argument('action', choices=('plan', 'sent', 'clear'))
    p.add_argument('--lane', choices=tuple(FOLLOW_UP_GAPS))
    p.add_argument('--due')
    p.add_argument('--reason')
    p.add_argument('--on', help='Date a follow-up was sent, for replay and tests.')
    p.set_defaults(func=cmd_follow_up)

    p = sub.add_parser('note', help='Add a line to a job\'s timeline.')
    p.add_argument('job_id')
    p.add_argument('text')
    p.set_defaults(func=cmd_note)

    p = sub.add_parser('video', help='Link the Loom or YouTube video you made for a job.')
    p.add_argument('job_id')
    p.add_argument('url')
    p.set_defaults(func=cmd_video)

    p = sub.add_parser('recording-links', help='Save optional tabs to open with the Loom recorder.')
    p.add_argument('job_id')
    p.add_argument('links', help='JSON list of objects with label and URL.')
    p.set_defaults(func=cmd_recording_links)

    p = sub.add_parser('loom-score', help='Save a checked Loom review score for analytics.')
    p.add_argument('job_id')
    p.add_argument('score', type=int)
    p.set_defaults(func=cmd_loom_score)

    p = sub.add_parser('loom-review', help='Turn the optional Loom review on or off for one application.')
    p.add_argument('job_id')
    p.add_argument('state', choices=('on', 'off'))
    p.set_defaults(func=cmd_loom_review)

    p = sub.add_parser('task', help='Tasks on a lead or client.')
    p.add_argument('job_id')
    p.add_argument('action', choices=('add', 'done', 'reopen', 'delete'))
    p.add_argument('text', help='The task text for add, the task number otherwise.')
    p.add_argument('--due')
    p.set_defaults(func=cmd_task)

    p = sub.add_parser('pitch-url', help='Save the public URL of a hosted pitch page.')
    p.add_argument('job_id')
    p.add_argument('url', help='Public HTTPS URL, or "-" to remove it.')
    p.set_defaults(func=cmd_pitch_url)

    p = sub.add_parser('lead-magnet-source', help='Save the confirmed local business used by the SEO audit.')
    p.add_argument('job_id')
    p.add_argument('website')
    p.add_argument('--location', required=True)
    p.add_argument('--place-id', default='')
    p.add_argument('--language', default='English', choices=('English', 'German'))
    p.set_defaults(func=cmd_lead_magnet_source)

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
    if args.cmd in ('get', 'list', 'summary') or (args.cmd == 'add' and args.check):
        args.func(args)
    else:
        with transaction():
            args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
