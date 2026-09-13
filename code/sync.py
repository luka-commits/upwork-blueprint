#!/usr/bin/env python3
"""Sync: brings the pipeline in line with what Upwork shows right now.

    python3 code/sync.py apply --file <snapshot.json>|-
    python3 code/sync.py last

/sync reads your proposals, offers, contracts and client threads through the
connector, read only, and hands that snapshot to `apply`. Apply moves each job to
the furthest stage Upwork shows evidence for, saves each client thread for the
cockpit's chat window, adds proposals you sent outside the cockpit, and records
when it ran. Status changes go through code/pipeline.py, the one writer. A saved
thread is Upwork content, so `pipeline.py prune` deletes it after 24 hours.

The snapshot, one JSON object (every list optional):
    {"proposals": [{"job_id", "title", "url", "status", "applied_at"}],
     "offers":    [{"job_id", "title", "state"}],
     "contracts": [{"job_id", "title", "status"}],
     "threads":   [{"job_id", "room_id", "awaiting_reply_from", "messages_complete", "messages":
                    [{"from": "client"|"me", "name", "at", "text"}]}]}
Offers and contracts without a job_id are matched by exact title.

`applied_at` is the proposal's Upwork creation time. `messages_complete` is true
only when connector pagination explicitly proves there are no older messages.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)
import threads as thread_io  # noqa: E402  (cleans raw Upwork messages)

RANK = {'new': 0, 'applied': 1, 'replied': 2, 'offer': 3, 'won': 4}
# Upwork's proposal words. "Accepted" means submitted, not that the client said yes.
PROPOSAL_STAGE = {'accepted': 'applied', 'pending': 'applied', 'activated': 'applied',
                  'offered': 'offer', 'hired': 'won', 'declined': 'lost', 'withdrawn': 'lost'}
OFFER_STAGE = {'awaiting_your_acceptance': 'offer', 'contract_started': 'won'}


def data_dir():
    return pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')


def run_pipeline(*args, stdin=None):
    r = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), *args],
                       input=stdin, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode == 0


def verified_timestamp(value):
    """Return a canonical nonfuture zoned timestamp, or None for weak evidence."""
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


def applied_expired(job, today=None):
    """An unanswered proposal leaves the active pipeline after 14 full days."""
    if job.get('status') != 'applied' or job.get('application_date_unknown'):
        return False
    stamp = verified_timestamp(job.get('applied_at'))
    if not stamp:
        return False
    applied_day = datetime.datetime.fromisoformat(stamp).date()
    return applied_day <= (today or datetime.datetime.now(datetime.timezone.utc).date()) - datetime.timedelta(days=14)


def first_complete_client_message(thread):
    """The first reply exists only when this response proves complete history."""
    if thread.get('messages_complete') is not True:
        return None
    stamps = []
    for message in thread.get('messages') or []:
        if not isinstance(message, dict):
            return None
        author = message.get('from')
        if author == 'me':
            continue
        # An unknown author could be an earlier client reply. An explicit client
        # message without a valid timestamp could be earlier too. Either gap
        # means this complete window still cannot prove the first reply time.
        if author != 'client':
            return None
        stamp = verified_timestamp(message.get('at'))
        if stamp is None:
            return None
        stamps.append(stamp)
    return min(stamps, default=None)


def evidence(snapshot, jobs):
    """Per job id: the furthest stage Upwork shows, and whether it says lost."""
    by_title = {}
    for job in jobs:
        title = (job.get('title') or '').strip().lower()
        if title:
            by_title[title] = None if title in by_title else job['id']
    seen = {}

    def note(job_id, title, stage):
        job_id = str(job_id or '') or by_title.get((title or '').strip().lower())
        if job_id and stage:
            seen.setdefault(job_id, set()).add(stage)
        return job_id

    for p in snapshot.get('proposals') or []:
        note(p.get('job_id'), p.get('title'), PROPOSAL_STAGE.get(str(p.get('status', '')).lower()))
    for o in snapshot.get('offers') or []:
        note(o.get('job_id'), o.get('title'), OFFER_STAGE.get(str(o.get('state', '')).lower()))
    for c in snapshot.get('contracts') or []:
        if str(c.get('status', '')).upper() in ('ACTIVE', 'PAUSED', 'CLOSED'):
            note(c.get('job_id'), c.get('title'), 'won')
    for t in snapshot.get('threads') or []:
        if any(isinstance(m, dict) and m.get('from') == 'client' for m in t.get('messages') or []):
            note(t.get('job_id'), None, 'replied')
    return seen


def target(current, stages):
    """The status Upwork's evidence calls for, or None when nothing should move."""
    best = max((s for s in stages if s in RANK), key=RANK.get, default=None)
    if 'lost' in stages and not ({'offer', 'won'} & stages) and current not in ('won', 'lost'):
        return 'lost'
    if best and (current not in RANK or RANK[best] > RANK[current]):
        return best
    return None


def cmd_apply(args):
    raw = sys.stdin.read() if args.file == '-' else pathlib.Path(args.file).read_text(encoding='utf-8')
    snapshot = json.loads(raw)
    jobs = pipeline.load()
    known = {j['id'] for j in jobs}

    added = []
    for p in snapshot.get('proposals') or []:
        jid = str(p.get('job_id') or '')
        stage = PROPOSAL_STAGE.get(str(p.get('status', '')).lower())
        if jid and jid not in known and stage:
            record = {'id': jid, 'title': p.get('title') or 'Untitled job', 'url': p.get('url') or '',
                      'status': stage, 'found_via': ['sync'], 'notes': 'sent outside the cockpit'}
            record['application_date_unknown'] = True
            if run_pipeline('add', '--file', '-', stdin=json.dumps(record)):
                added.append(jid)
                known.add(jid)
    jobs = pipeline.load()

    today = datetime.date.today().isoformat()
    moved, waiting = [], []
    threads = {str(t.get('job_id')): t for t in snapshot.get('threads') or [] if t.get('job_id')}
    for jid, stages in evidence(snapshot, jobs).items():
        job = next((j for j in jobs if j['id'] == jid), None)
        if not job:
            continue
        new = target(job.get('status'), stages)
        if new:
            date_args = ['--applied-at', 'unknown'] if new == 'applied' else []
            if run_pipeline('set', jid, new, *date_args):
                moved.append({'id': jid, 'from': job.get('status'), 'to': new})
                job['status'] = new

    # Proposal creation time is measured Upwork evidence. Record it even when
    # this sync did not move the job, so an old unknown import can be repaired.
    applied_observations = {}
    for proposal in snapshot.get('proposals') or []:
        jid = str(proposal.get('job_id') or '')
        stamp = verified_timestamp(proposal.get('applied_at'))
        stage = PROPOSAL_STAGE.get(str(proposal.get('status', '')).lower())
        if jid in known and stage and stamp:
            applied_observations[jid] = min(stamp, applied_observations.get(jid, stamp))
    for jid, stamp in applied_observations.items():
        run_pipeline('observe', jid, 'applied', stamp, '--source', 'upwork-proposal', '--verified')

    # A newest-message window is not proof of a first reply. Only a thread whose
    # pagination explicitly proves completeness may establish replied_at.
    reply_observations = {}
    for thread in snapshot.get('threads') or []:
        jid = str(thread.get('job_id') or '')
        stamp = first_complete_client_message(thread)
        if jid in known and stamp:
            reply_observations[jid] = min(stamp, reply_observations.get(jid, stamp))
    for jid, stamp in reply_observations.items():
        run_pipeline('observe', jid, 'replied', stamp, '--source', 'upwork-thread', '--verified')

    # A client waiting on you is a follow-up due today, whatever the stage says.
    for jid, t in threads.items():
        job = next((j for j in jobs if j['id'] == jid), None)
        if not job:
            continue
        thread_io.save(jid, t.get('messages') or [], t.get('room_id'), t.get('awaiting_reply_from'))
        outbox_file = pipeline.jobs_dir() / jid / 'outbox.json'
        try:
            outbox = json.loads(outbox_file.read_text(encoding='utf-8'))
            if outbox.get('confirmed_at') and job.get('follow_up_plan'):
                run_pipeline('follow-up', jid, 'sent')
        except (OSError, json.JSONDecodeError):
            pass
        if t.get('awaiting_reply_from') == 'you' and job.get('status') not in ('lost', 'skipped'):
            if job.get('follow_up_plan'):
                run_pipeline('follow-up', jid, 'clear', '--reason', 'The client replied; review the new message first.')
            if job.get('status') in ('replied', 'offer', 'won') and run_pipeline('set', jid, job['status'], '--follow-up', today):
                waiting.append(jid)

    # Applied proposals cannot be messaged first. Once 14 days pass without a
    # client reply, remove them from the active pipeline instead of creating work.
    for job in pipeline.load():
        if job.get('status') == 'applied' and (job.get('next_follow_up') or job.get('follow_up_plan')):
            run_pipeline('follow-up', job['id'], 'clear', '--reason', 'Applied proposals cannot be followed up before the client replies.')
        if applied_expired(job) and run_pipeline('set', job['id'], 'lost', '--note', 'No client reply within 14 days.'):
            moved.append({'id': job['id'], 'from': 'applied', 'to': 'lost'})

    record = {'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'moved': moved, 'added': added, 'threads': len(threads), 'awaiting_you': waiting}
    data_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / 'sync.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    for m in moved:
        print(f'moved   {m["id"]}  {m["from"]} -> {m["to"]}')
    for jid in added:
        print(f'added   {jid}  (a proposal sent outside the cockpit)')
    for jid in waiting:
        print(f'waiting {jid}  (the client is waiting for your reply)')
    print(f'\n{len(moved)} moved, {len(added)} added, {len(threads)} threads saved, '
          f'{len(waiting)} waiting on you.')


def cmd_last(args):
    f = data_dir() / 'sync.json'
    if not f.is_file():
        print('Never synced.')
        return
    print(json.loads(f.read_text(encoding='utf-8')).get('synced_at'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('apply', help='Bring the pipeline in line with a snapshot from Upwork.')
    p.add_argument('--file', required=True, help='JSON snapshot. "-" reads stdin.')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('last', help='When the last sync ran.')
    p.set_defaults(func=cmd_last)
    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
