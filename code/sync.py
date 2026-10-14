#!/usr/bin/env python3
"""Sync: brings the pipeline in line with what Upwork shows right now.

    python3 code/sync.py apply --file <snapshot.json>|-
    python3 code/sync.py last

/brief reads your proposals, offers, contracts and client threads through the
connector, read only, and hands that snapshot to `apply`. Apply moves each job to
the furthest stage Upwork shows evidence for, saves each client thread for the
cockpit's chat window, adds proposals you sent outside the cockpit, and records
when it ran. Status changes go through code/pipeline.py, the one writer. A saved
thread is Upwork content, so `pipeline.py prune` deletes it after KEEP_CHAT_HOURS (90 days).

The snapshot, one JSON object (every list optional):
    {"proposals": [{"job_id", "proposal_id", "room_id", "title", "url", "status", "applied_at"}],
     "invitations": [{"job_id", "invitation_id", "title", "url", "invited_at", "room_id"}],
     "no_rooms":  ["job_id"],
     "offers":    [{"job_id", "offer_id", "title", "state", "client_name", "source": "invite"|"direct_offer"}],
     "contracts": [{"job_id", "contract_id", "title", "status", "client_name",
                    "terms": {"type": "fixed"|"hourly", "fixed_amount", "hourly_rate", "currency", "start_date"}}],
     "earnings": [{"week_start", "contract_id", "billed", "currency"}],
     "connects": [{"at", "amount", "reason", "job_id"}],
     "meetings": [{"job_id", "room_id", "booked_at", "session_id", "held_at", "duration_s"}],
     "threads":   [{"job_id", "room_id", "awaiting_reply_from", "messages_complete", "messages":
                    [{"from": "client"|"me", "name", "at", "text"}]}]}
Offers and contracts without a job_id are matched by stored contract id or unique
exact title. An unmatched record needs a stable offer_id or contract_id to import.

`applied_at` is the proposal's Upwork creation time. `messages_complete` is true
only when connector pagination explicitly proves there are no older messages.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)
import threads as thread_io  # noqa: E402  (cleans raw Upwork messages)

RANK = {'new': 0, 'applied': 1, 'replied': 2, 'call': 3, 'offer': 4, 'won': 5}
# A lead the member closed stays closed. Upwork keeps serving the thread and the
# proposal that got it there, so without this it climbs back every morning.
EXITS = ('lost', 'skipped')
# Upwork's proposal words. "Accepted" means submitted, not that the client said yes.
PROPOSAL_STAGE = {'accepted': 'applied', 'pending': 'applied', 'activated': 'applied',
                  'offered': 'offer', 'hired': 'won', 'declined': 'lost', 'withdrawn': 'lost'}
OFFER_STAGE = {'awaiting_your_acceptance': 'offer', 'contract_started': 'won',
               'declined': 'lost', 'withdrawn': 'lost', 'expired': 'lost'}
CONTRACT_STAGE = {'active': 'won', 'paused': 'won', 'closed': 'won'}


def data_dir():
    return pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')


def run_pipeline(*args, stdin=None):
    r = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), *args],
                       input=stdin, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode == 0


def record_metadata(job, value):
    """Record only changed metadata, including removal of the waiting marker."""
    changed = {key: item for key, item in value.items() if job.get(key) != item}
    if not changed:
        return True
    if not run_pipeline('record', job['id'], '--file', '-', stdin=json.dumps(changed)):
        return False
    job.update(changed)
    if changed.get('follow_up_source', 'waiting') is None:
        job.pop('follow_up_source', None)
    return True


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


def booked_timestamp(value):
    """A scheduled meeting may be future, but its start must have a timezone."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return stamp.astimezone(datetime.timezone.utc).isoformat() if stamp.tzinfo and stamp.utcoffset() is not None else None


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
    """The first reply exists only when this response proves complete history.

    A message that is not an object leaves the history incomplete. It moves no stage
    and blocks every verified timestamp from this thread: a timeline built on a
    payload we could not read is a guess wearing a date.
    """
    if thread.get('messages_complete') is not True:
        return None
    turns = complete_turns(thread)
    if turns is None:
        return None
    return next((at for at, message in turns if message['from'] == 'client'), None)


def complete_turns(thread):
    """Validate a complete room, skip system events and preserve invitation turns."""
    if thread.get('messages_complete') is not True or not isinstance(thread.get('messages'), list):
        return None
    raw = []
    for item in thread['messages']:
        if not isinstance(item, dict) or not isinstance(item.get('node', item), dict):
            return None
        node = item.get('node', item)
        if node.get('kind') in ('system', 'event') or node.get('from_side') == 'system' or node.get('from') == 'system':
            continue
        if 'from_side' in node and node['from_side'] not in ('client', 'freelancer') and not node.get('from_self'):
            return None
        raw.append(item)
    turns = []
    for message in thread_io.normalize(raw):
        if message.get('kind') in ('system', 'event') or message.get('from') == 'system':
            continue
        at = verified_timestamp(message.get('at'))
        if message.get('from') not in ('me', 'client') or at is None:
            return None
        turns.append((at, message))
    return sorted(turns, key=lambda turn: turn[0])


def first_reply(thread):
    """The first client turn to the first member answer, including invitations."""
    turns = complete_turns(thread)
    if turns is None:
        return None
    client_at = None
    for at, message in turns:
        if message['from'] == 'client' and client_at is None:
            client_at = at
        elif message['from'] == 'me' and client_at is not None:
            seconds = int((datetime.datetime.fromisoformat(at) - datetime.datetime.fromisoformat(client_at)).total_seconds())
            return {'first_reply_s': seconds, 'first_reply_at': at, 'client_at': client_at}
    return None


def reply_gaps(thread):
    """Seconds from each client turn to the next member turn in a complete room.

    The snapshot marks invitation rooms with invitation_room/opened_by_invite,
    or marks the first client turn kind:invite/is_invitation.
    """
    if thread.get('invitation_room') or thread.get('opened_by_invite'):
        return []
    if thread.get('messages_complete') is not True:
        return None
    raw = thread.get('messages') or []
    if not isinstance(raw, list):
        return None
    messages, invites = [], set()
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get('node', item), dict):
            return None
        node = item.get('node', item)
        if (node.get('kind') in ('system', 'event') or
                node.get('from_side') == 'system' or node.get('from') == 'system'):
            continue
        if 'from_side' in node and node['from_side'] not in ('client', 'freelancer') and not node.get('from_self'):
            return None
        stamp = verified_timestamp(node.get('createdDateTime', node.get('at')))
        if node.get('is_invitation') or node.get('kind') in ('invite', 'invitation'):
            invites.add(stamp)
        messages.append(item)
    turns = []
    for message in thread_io.normalize(messages):
        if message.get('kind') in ('system', 'event') or message.get('from') == 'system':
            continue
        stamp = verified_timestamp(message.get('at'))
        if message.get('from') not in ('me', 'client') or not stamp:
            return None
        at = datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        turns.append((at, stamp, message))
    turns.sort(key=lambda turn: turn[0])
    if turns and turns[0][2]['from'] == 'client' and turns[0][1] in invites:
        return []
    gaps, pending = [], None
    for at, _, message in turns:
        if message['from'] == 'client':
            if pending is None:
                pending = at
        elif pending is not None:
            gaps.append(int((at - pending).total_seconds()))
            pending = None
    return gaps


def source_stage(item, kind):
    key, stages = {'proposals': ('status', PROPOSAL_STAGE), 'offers': ('state', OFFER_STAGE),
                   'contracts': ('status', CONTRACT_STAGE)}[kind]
    raw = str(item.get(key) or '')
    stage = stages.get(raw.lower())
    if stage is None:
        print(f'WARNING: unknown {kind} status {raw!r}.', file=sys.stderr)
    return stage


def matched_id(item, jobs):
    if item.get('contract_id'):
        matches = [j['id'] for j in jobs if j.get('contract_id') == str(item['contract_id'])]
        if len(matches) == 1:
            return matches[0]
    if item.get('job_id'):
        return str(item['job_id'])
    title = str(item.get('title') or '').strip().lower()
    matches = [j['id'] for j in jobs if title and str(j.get('title') or '').strip().lower() == title
               and not (item.get('contract_id') and j.get('contract_id')
                        and str(item['contract_id']) != j['contract_id'])]
    return matches[0] if len(matches) == 1 else None


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

    for kind in ('proposals', 'offers', 'contracts'):
        for item in snapshot.get(kind) or []:
            note(matched_id(item, jobs), item.get('title'), source_stage(item, kind))
    for t in snapshot.get('threads') or []:
        if any(m.get('from') == 'client' and m.get('kind') not in ('system', 'event')
               for m in thread_io.normalize(t.get('messages') or [])):
            note(t.get('job_id'), None, 'replied')
    for meeting in snapshot.get('meetings') or []:
        if booked_timestamp(meeting.get('booked_at')) or verified_timestamp(meeting.get('held_at')):
            note(meeting.get('job_id'), None, 'call')
    return seen


def target(current, stages):
    """The status Upwork's evidence calls for, or None when nothing should move."""
    best = max((s for s in stages if s in RANK), key=RANK.get, default=None)
    if 'lost' in stages and 'won' not in stages and current not in ('won', 'lost'):
        return 'lost'
    if current in EXITS:
        # Only real movement reopens a closed lead: an offer or a started contract.
        return best if best in ('offer', 'won') else None
    if best and (current not in RANK or RANK[best] > RANK[current]):
        return best
    return None


def contract_value(terms):
    """Use only complete member-owned contract terms; never guess missing money."""
    if not isinstance(terms, dict) or terms.get('type') not in ('fixed', 'hourly'):
        return None
    amount = terms.get('fixed_amount' if terms['type'] == 'fixed' else 'hourly_rate')
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
        return None
    if not isinstance(terms.get('currency'), str) or not terms['currency'].strip():
        return None
    try:
        datetime.date.fromisoformat(terms.get('start_date'))
    except (ValueError, TypeError):
        return None
    return {'type': terms['type'], 'amount': amount, 'currency': terms['currency'], 'start_date': terms['start_date']}


def append_financials(snapshot):
    """Append deduplicated money records with no cached job or client payloads."""
    data_dir().mkdir(parents=True, exist_ok=True)
    for name, keys in (('earnings', ('week_start', 'contract_id', 'billed', 'currency')),
                       ('connects', ('at', 'amount', 'reason', 'job_id'))):
        path = data_dir() / f'{name}.jsonl'
        existing = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
        identity = ('week_start', 'contract_id') if name == 'earnings' else keys
        seen = {tuple(row.get(key) for key in identity) for row in existing}
        rows = []
        for item in snapshot.get(name) or []:
            if not isinstance(item, dict):
                continue
            row = {key: item.get(key) for key in keys}
            number = row['billed' if name == 'earnings' else 'amount']
            if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(number):
                continue
            if name == 'earnings':
                try:
                    datetime.date.fromisoformat(row['week_start'])
                except (ValueError, TypeError):
                    continue
                if (not row['contract_id'] or not isinstance(row['contract_id'], (str, int))
                        or isinstance(row['contract_id'], bool) or not isinstance(row['currency'], str)
                        or not row['currency'].strip()):
                    continue
                row['contract_id'] = str(row['contract_id'])
            else:
                at = verified_timestamp(row['at'])
                if not at or not isinstance(row['reason'], str):
                    continue
                row['at'] = at
                if row['job_id'] is not None:
                    if not isinstance(row['job_id'], (str, int)) or isinstance(row['job_id'], bool):
                        continue
                    row['job_id'] = str(row['job_id'])
            key = tuple(row[field] for field in identity)
            if key not in seen:
                rows.append(row)
                seen.add(key)
        if rows:
            with path.open('a', encoding='utf-8') as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def cmd_apply(args):
    raw = sys.stdin.read() if args.file == '-' else pathlib.Path(args.file).read_text(encoding='utf-8')
    snapshot = json.loads(raw)
    jobs = pipeline.load()
    known = {j['id'] for j in jobs}
    first_import = not (data_dir() / 'sync.json').is_file()

    added = []
    proposal_jobs = {str(item.get('job_id')) for item in snapshot.get('proposals') or [] if item.get('job_id')}
    for kind in ('invitations', 'proposals', 'offers', 'contracts'):
        for item in snapshot.get(kind) or []:
            jid = matched_id(item, jobs)
            stage = 'new' if kind == 'invitations' else source_stage(item, kind)
            if not jid and stage:
                identity = item.get('contract_id') or item.get('offer_id') or item.get('invitation_id')
                if identity:
                    # A decimal local id works with every lead command. The source
                    # kind is included so unrelated platform ids cannot collide.
                    digest = hashlib.sha256(f'{kind}:{identity}'.encode()).digest()
                    jid = str(int.from_bytes(digest[:10], 'big'))
                else:
                    print(f'WARNING: unmatched {kind} record has no stable id; not imported.', file=sys.stderr)
            if jid and jid not in known and stage:
                record = {'id': jid, 'title': item.get('title') or 'Untitled job', 'url': item.get('url') or '',
                          'status': stage, 'found_via': ['sync'], 'notes': 'imported Upwork history',
                          'imported': first_import or kind != 'proposals', 'application_date_unknown': True}
                activity = max((verified_timestamp(message.get('at')) or ''
                                for thread in snapshot.get('threads') or [] if str(thread.get('job_id')) == jid
                                for message in thread.get('messages') or [] if isinstance(message, dict)
                                and message.get('from') in ('me', 'client') and message.get('kind') != 'event'), default='')
                if activity:
                    record['last_activity_at'] = activity
                if run_pipeline('add', '--file', '-', stdin=json.dumps(record)):
                    added.append(jid)
                    known.add(jid)
                    jobs = pipeline.load()
            if jid in known:
                metadata = {key: str(item[key]) for key in ('proposal_id', 'room_id', 'contract_id', 'invitation_id') if item.get(key)}
                job = next(j for j in jobs if j['id'] == jid)
                if kind == 'invitations':
                    metadata['source'] = 'invite'
                    invited = verified_timestamp(item.get('invited_at'))
                    if invited:
                        metadata['invited_at'] = invited
                elif kind == 'offers':
                    source = item.get('source')
                    if source in ('invite', 'direct_offer'):
                        metadata['source'] = source
                    elif jid not in proposal_jobs and not job.get('proposal_id') and not job.get('applied_at') and not job.get('source'):
                        metadata['source'] = 'direct_offer'
                if kind == 'contracts':
                    value = contract_value(item.get('terms'))
                    if value is not None:
                        metadata['won_value'] = value
                if item.get('client_name'):
                    metadata['contract_client'] = str(item['client_name'])
                if metadata:
                    record_metadata(next(j for j in jobs if j['id'] == jid), metadata)
                item['job_id'] = jid
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
            force = ['--force'] if job.get('status') in EXITS else []
            activity = max((verified_timestamp(message.get('at')) or ''
                            for message in (threads.get(jid) or {}).get('messages') or []
                            if isinstance(message, dict) and message.get('from') in ('me', 'client')
                            and message.get('kind') != 'event'), default='')
            activity = activity or verified_timestamp(job.get('last_activity_at') or job.get('status_updated_at'))
            activity_args = ['--activity-at', activity] if activity else []
            if run_pipeline('set', jid, new, *date_args, *force, *activity_args):
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

    # Meeting start times and recorded recaps are separate evidence.
    # Missing recaps never establish a no-show; that remains the member's decision.
    meetings = []
    for meeting in snapshot.get('meetings') or []:
        jid = str(meeting.get('job_id') or '')
        if jid not in known:
            continue
        saved_meeting = {'job_id': jid}
        for field in ('room_id', 'session_id'):
            value = meeting.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                saved_meeting[field] = str(value)
        seconds = meeting.get('duration_s')
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and math.isfinite(seconds) and seconds >= 0:
            saved_meeting['duration_s'] = seconds
        if meeting.get('room_id'):
            record_metadata(next(j for j in pipeline.load() if j['id'] == jid),
                            {'room_id': str(meeting['room_id'])})
        for event, validator, field in (('call_booked', booked_timestamp, 'booked_at'),
                                        ('call_held', verified_timestamp, 'held_at')):
            stamp = validator(meeting.get(field))
            if stamp:
                saved_meeting[field] = stamp
                run_pipeline('observe', jid, event, stamp, '--source', 'upwork-meeting', '--verified')
        if 'booked_at' in saved_meeting or 'held_at' in saved_meeting:
            meetings.append(saved_meeting)

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

    # First-answer timing is a separate metric, and a partial room changes nothing.
    first_answers, incomplete = {}, set()
    for thread in snapshot.get('threads') or []:
        jid = str(thread.get('job_id') or '')
        if complete_turns(thread) is None:
            incomplete.add(jid)
        answer = first_reply(thread)
        if jid in known and answer:
            if jid not in first_answers or answer['client_at'] < first_answers[jid]['client_at']:
                first_answers[jid] = answer
    for jid, answer in first_answers.items():
        if jid not in incomplete:
            job = next(j for j in pipeline.load() if j['id'] == jid)
            record_metadata(job, {key: answer[key] for key in ('first_reply_s', 'first_reply_at')})

    # The supplied rooms must cover the job: a partial room cannot replace its aggregate.
    room_gaps, partial_jobs = {}, set()
    for thread in snapshot.get('threads') or []:
        jid = str(thread.get('job_id') or '')
        gaps = reply_gaps(thread)
        if gaps is None:
            partial_jobs.add(jid)
        if jid in known and gaps is not None:
            room_gaps.setdefault(jid, []).extend(gaps)
    for jid, gaps in room_gaps.items():
        if jid in partial_jobs:
            continue
        job = next(j for j in pipeline.load() if j['id'] == jid)
        record_metadata(job, {'reply_gaps_s': gaps})

    # A sync replays message times, never poll time. Observed sends advance the
    # sequence before client replies stop it, so the same nudge is not drafted twice.
    for jid, t in threads.items():
        job = next((j for j in pipeline.load() if j['id'] == jid), None)
        if not job:
            continue
        thread_io.save(jid, t.get('messages') or [], t.get('room_id'), t.get('awaiting_reply_from'))
        if t.get('room_id'):
            record_metadata(job, {'room_id': str(t['room_id'])})
        normalized = thread_io.normalize(t.get('messages') or [])
        messages = [(verified_timestamp(m.get('at')), m) for m in normalized
                    if isinstance(m, dict) and m.get('from') in ('me', 'client') and m.get('kind') not in ('event', 'system')]
        messages = sorted((pair for pair in messages if pair[0]), key=lambda pair: pair[0])
        activity_at = verified_timestamp(job.get('last_activity_at')) or ''
        new_messages = [pair for pair in messages if pair[0] > activity_at]
        plan = job.get('follow_up_plan') or {}
        last = (job.get('follow_up_history') or [{}])[-1]
        follow_up_at = max(verified_timestamp(plan.get('reviewed_at')) or '',
                           verified_timestamp(last.get('at')) or '')
        for stamp, message in (pair for pair in messages if follow_up_at and pair[0] > follow_up_at):
            plan = job.get('follow_up_plan') or {}
            reviewed = verified_timestamp(plan.get('reviewed_at'))
            silent_due = plan.get('lane') != 'silent' or stamp[:10] >= (job.get('next_follow_up') or '9999-12-31')
            if message.get('from') == 'me' and reviewed and stamp > reviewed and silent_due:
                if run_pipeline('follow-up', jid, 'sent', '--on', stamp[:10], '--at', stamp):
                    job = next(j for j in pipeline.load() if j['id'] == jid)
            last = (job.get('follow_up_history') or [{}])[-1]
            stopped_at = verified_timestamp(last.get('at'))
            if (message.get('from') == 'client' and stopped_at and stamp > stopped_at
                    and (last.get('action') == 'cleared' or last.get('completed'))):
                if run_pipeline('follow-up', jid, 'clear', '--reason', 'The client replied; review the new message first.'):
                    job = next(j for j in pipeline.load() if j['id'] == jid)
        if new_messages:
            stamp, message = new_messages[-1]
            if stamp > (verified_timestamp(job.get('last_activity_at')) or ''):
                run_pipeline('acted', jid, '--at', stamp, '--note',
                             'Client replied on Upwork.' if message.get('from') == 'client' else 'Member sent a message on Upwork.')
        job = next(j for j in pipeline.load() if j['id'] == jid)
        if t.get('awaiting_reply_from') == 'you' and job.get('status') not in ('lost', 'skipped'):
            if job.get('follow_up_plan') and job['follow_up_plan'].get('lane') != 'active':
                run_pipeline('follow-up', jid, 'clear', '--reason', 'The client replied; review the new message first.')
                job = next(j for j in pipeline.load() if j['id'] == jid)
            if job.get('status') in ('replied', 'call', 'offer', 'won') and record_metadata(
                    job, {'next_follow_up': today, 'follow_up_source': 'waiting'}):
                waiting.append(jid)
        elif not job.get('follow_up_plan') and job.get('follow_up_source') == 'waiting':
            record_metadata(job, {'next_follow_up': None, 'follow_up_source': None})
        # Silent sequences are anchored to the original unanswered turn, not poll time.
        if messages and job.get('status') in ('replied', 'call', 'offer'):
            latest_at, latest = messages[-1]
            plan = job.get('follow_up_plan') or {}
            if latest['from'] == 'me' and t.get('awaiting_reply_from') != 'you':
                last_client = max((at for at, message in messages if message['from'] == 'client'), default='')
                prior = [entry for entry in job.get('follow_up_history') or []
                         if entry.get('lane') == 'silent' and entry.get('anchor_at')
                         and entry['anchor_at'] > last_client]
                anchor = (plan.get('anchor_at') if plan.get('lane') == 'silent' else
                          prior[-1]['anchor_at'] if prior else latest_at)
                completed = any(entry.get('lane') == 'silent' and entry.get('completed')
                                and (verified_timestamp(entry.get('at')) or '') >= (anchor or '')
                                for entry in job.get('follow_up_history') or [])
                if anchor and not completed and plan.get('lane') != 'silent':
                    due = pipeline.add_business_days(datetime.date.fromisoformat(anchor[:10]), 3).isoformat()
                    run_pipeline('follow-up', jid, 'plan', '--lane', 'silent', '--due', due,
                                 '--at', anchor, '--reason', 'The member wrote last; the client has not answered.')
            elif latest['from'] == 'client' and plan.get('lane') != 'reactivation':
                due = pipeline.add_business_days(datetime.date.fromisoformat(latest_at[:10]), 1).isoformat()
                if plan.get('lane') != 'active':
                    run_pipeline('follow-up', jid, 'plan', '--lane', 'active', '--due', due,
                                 '--at', latest_at, '--reason', 'The client replied; resume the active conversation.')
                    if t.get('awaiting_reply_from') == 'you':
                        record_metadata(next(j for j in pipeline.load() if j['id'] == jid),
                                        {'next_follow_up': today, 'follow_up_source': 'waiting'})


    # Expiration needs fresh evidence that this exact proposal was checked and
    # still has no room. Absence from a limited proposal page proves nothing.
    no_rooms = {str(jid) for jid in snapshot.get('no_rooms') or []}
    stale = []
    for job in pipeline.load():
        if job.get('status') == 'applied' and (job.get('next_follow_up') or job.get('follow_up_plan')):
            run_pipeline('follow-up', job['id'], 'clear', '--reason', 'Applied proposals cannot be followed up before the client replies.')
        # Lost is the member's call, never the sync's. A proposal that sat 14 days
        # without a room is only listed, so /brief can ask.
        if job['id'] in no_rooms and applied_expired(job):
            stale.append(job['id'])

    append_financials(snapshot)
    record = {'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'moved': moved, 'added': added, 'threads': len(threads), 'awaiting_you': waiting,
              'stale_applications': stale, 'meetings': meetings}
    data_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / 'sync.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    for m in moved:
        print(f'moved   {m["id"]}  {m["from"]} -> {m["to"]}')
    for jid in added:
        print(f'added   {jid}  (imported Upwork history)')
    for jid in waiting:
        print(f'waiting {jid}  (the client is waiting for your reply)')
    clicks = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('clicks.py'))],
                            text=True, capture_output=True, check=False)
    if clicks.returncode:
        print('Click sync failed; pipeline sync completed. Retry code/clicks.py when Blob is available.')
    elif clicks.stdout.strip():
        print(clicks.stdout.strip())
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
