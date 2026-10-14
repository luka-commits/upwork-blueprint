#!/usr/bin/env python3
"""The cockpit: your job pipeline and each lead's details, in the browser.

    python3 code/cockpit.py [--port 4321] [--no-open]   start it (installs and builds on first run)
    python3 code/cockpit.py state                         the list data as JSON
    python3 code/cockpit.py job <id>                      one job in full as JSON

The page itself is a small Next.js app in website/. This script starts it, and it
is also where the app reads its data from, so the page reads the
same tested Python data as everything else. The app runs on this computer only
(127.0.0.1). Every status change goes through code/pipeline.py.
"""
import argparse
import datetime
import json
import math
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_check
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)
import application_check  # noqa: E402
import pitch_check  # noqa: E402
import analytics  # noqa: E402  (saved snapshots and the weekly due check)
from analytics import bars  # noqa: E402

APP = ROOT / 'website'
JOBS_DIR = pipeline.jobs_dir()


def artifacts(job_id):
    folder = JOBS_DIR / job_id
    if not folder.is_dir():
        return []
    internal = {'thread.json', 'replies.json', 'outbox.json'}
    return sorted(p.name for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith('.') and p.name not in internal)


# What a member is looking at when they open a lead: the thing a client reads, the thing
# they still have to send, and the raw material behind both. A flat list of eleven files
# hides the first two behind the third.
CLIENT_FACING = {'pitch.html', 'proposal.html'}
TO_SEND = {'application.md', 'proposal.md', 'project.md'}


def role(name):
    """Four roles: what the client reads, what the member still has to send, images as
    material, and everything else as a record of what happened."""
    if name in CLIENT_FACING:
        return 'client'
    if name in TO_SEND:
        return 'send'
    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif')):
        return 'asset'
    return 'data'


def artifact_health(job):
    """Return gate-backed readiness without hiding saved drafts from the member."""
    folder = JOBS_DIR / str(job.get('id') or '')
    valid, errors = [], {}
    proof_path = pathlib.Path(os.environ.get('BLUEPRINT_CONTEXT') or ROOT / 'context') / 'me.md'
    proof = (context_check.proof_only(proof_path.read_text(encoding='utf-8'))
             if proof_path.is_file() else '')
    for name in artifacts(str(job.get('id') or '')):
        path = folder / name
        problems = None
        try:
            # Every client-facing file has a gate in this repo. Two of them ran here and the
            # rest showed green without a check, which is worse than no tile: a member reads
            # a green proposal as a checked proposal.
            if name in ('pitch.html', 'proposal.html'):
                problems = pitch_check.check_page(path)
            elif name == 'application.md':
                problems, _, _, _, _ = application_check.check(
                    path.read_text(encoding='utf-8'), str(job.get('title') or ''), proof)
            elif name in ('proposal.md', 'project.md'):
                import document_check  # noqa: E402  (same folder, imported where it is used)
                kind = 'proposal' if name == 'proposal.md' else 'project'
                problems = document_check.validate_artifact(kind, path.read_text(encoding='utf-8'), proof)
        except (OSError, UnicodeError):
            problems = ['file could not be read']
        if problems is None or not problems:
            valid.append(name)
        else:
            errors[name] = problems
    return valid, errors


def read_json(folder, name):
    file = folder / name
    try:
        return json.loads(file.read_text(encoding='utf-8')) if file.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def client_waiting(thread):
    """True when the room waits on the member and the client has written."""
    if not isinstance(thread, dict) or not thread.get('room_id') \
            or thread.get('awaiting_reply_from') != 'you':
        return False
    return any(isinstance(m, dict) and m.get('kind') != 'event' and m.get('from') != 'me'
               for m in thread.get('messages') or [])


def job_view(job_id):
    """One job for the full lead view: the record, its files with dates, the saved thread."""
    job = next((j for j in pipeline.load() if j.get('id') == job_id), None)
    if not job:
        return None
    j = dict(job)
    folder = JOBS_DIR / job_id
    files = []
    for name in artifacts(job_id):
        stat = (folder / name).stat()
        files.append({
            'name': name,
            'role': role(name),
            'at': datetime.datetime.fromtimestamp(
                stat.st_mtime, datetime.timezone.utc).isoformat(timespec='seconds'),
            'version': f'{stat.st_mtime_ns}-{stat.st_size}',
        })
    j['files'] = files
    j['valid_artifacts'], j['artifact_errors'] = artifact_health(job)
    j['thread'] = read_json(folder, 'thread.json')
    j['client_waiting'] = client_waiting(j['thread'])
    j['artifacts'] = [f['name'] for f in files]
    j['replies'] = read_json(folder, 'replies.json')
    saved = analytics_state(datetime.datetime.now(pipeline.member_zone()).date())
    snapshot = saved['latest'] or {}
    # A saved evidence row enriches a real pipeline lead; it never creates a lead.
    j['call_cards'] = [row for row in snapshot.get('call_cards') or []
                       if isinstance(row, dict) and str(row.get('lead_id')) == str(job_id)]
    if j['call_cards'] or (folder / 'call-review.md').is_file() or isinstance(job.get('call_review'), dict):
        # Immediate /call-review output is saved evidence, independent of the weekly check-in.
        rubric = dict(job.get('call_review') or {'reviewable': False, 'points': []}, lead_id=str(job_id))
        current = analytics.call_cards({'generated_at': datetime.datetime.now(pipeline.member_zone()).isoformat(),
                                       'reviews': {'call': {'rubric': [rubric]}}}, jobs=[job])
        if current:
            old = j['call_cards'][0] if j['call_cards'] else {}
            j['call_cards'] = [dict(old, **current[0])]
    prepared = next((row for row in snapshot.get('lead_cards') or []
                     if isinstance(row, dict) and str(row.get('lead_id', row.get('id'))) == str(job_id)), None)
    j['lead_context'] = {
        'week': snapshot.get('week'), 'prepared': prepared,
        'proposal_viewed': job.get('proposal_viewed'),
        'proposal_viewed_at': job.get('proposal_viewed_at'),
        'proposal_insights': job.get('proposal_insights'),
        'view_note': 'Upwork observed a viewed flag; observed_at is not the actual view time.',
    }
    j['analytics_errors'] = saved['errors']
    return j


def card(job):
    """A record as the list needs it: everything but the full posting."""
    j = {k: v for k, v in job.items() if k not in ('description',)}
    details = dict(job.get('details') or {})
    j['has_posting'] = bool(details.pop('description', None) or job.get('description'))
    j['details'] = details
    j['artifacts'] = artifacts(job.get('id', ''))
    j['valid_artifacts'], j['artifact_errors'] = artifact_health(job)
    j['client_waiting'] = client_waiting(read_json(JOBS_DIR / str(job.get('id') or ''), 'thread.json'))
    return j


def daily_target():
    """The member's applications-per-day goal from context/me.md, five when they set none."""
    me = pathlib.Path(os.environ.get('BLUEPRINT_CONTEXT') or ROOT / 'context') / 'me.md'
    if me.is_file():
        m = re.search(r'Applications per day:\*\*\s*(\d+)', me.read_text(encoding='utf-8'))
        if m:
            return int(m.group(1))
    return 5


FUNNEL = ('applied', 'replied', 'call', 'offer', 'won')


def reached(job):
    """The stages this member lead reached, including an explicit send timestamp."""
    stages = [job.get('status')] + [h.get('status') for h in job.get('history') or []
                                    if isinstance(h, dict)]
    if job.get('applied_at'):
        stages.append('applied')
    rank = max((FUNNEL.index(s) + 1 for s in stages if s in FUNNEL), default=0)
    return rank, 'call' in stages


def applications(jobs):
    """Every non-imported lead that ever reached application or a later stage."""
    return [job for job in jobs if not job.get('imported') and reached(job)[0]]


def funnel(jobs):
    """How many leads ever reached each stage, from applied to won."""
    # The mandatory stages count as reached: nobody wins without applying, and nobody
    # is offered without an answer. The call is the exception, because it is optional:
    # crediting it to every lead that reached an offer would invent calls nobody had.
    marks = [reached(job) for job in applications(jobs)]
    counts = {stage: sum(1 for rank, had_call in marks
                       if (had_call if stage == 'call' else rank > index))
            for index, stage in enumerate(FUNNEL)}
    eligible = applications(jobs)
    counts['proposal_sent'] = sum(bool(_when(j.get('proposal_sent_at'))) for j in eligible)
    counts['opened'] = sum(bool(_when(j.get('opened_at')) and _when(j.get('proposal_sent_at'))
                                and _when(j['opened_at']) > _when(j['proposal_sent_at'])) for j in eligible)
    return counts

OUTREACH_WEEKS = 12


def outreach(jobs, weeks=OUTREACH_WEEKS, today=None):
    """Applications sent per week, oldest first, so a member sees their own rhythm.

    The funnel's application population, counted once per lead. Prefer the send
    timestamp, then applied history; legacy leads use their earliest progressed
    history, status update or discovery date. These fallbacks place a lead in a
    week without claiming its send time was observed. Weeks start on Monday.
    """
    today = today or datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    starts = [monday - datetime.timedelta(weeks=back) for back in range(weeks - 1, -1, -1)]
    counts = {start.isoformat(): 0 for start in starts}
    first = starts[0]
    def date(value):
        try:
            return datetime.date.fromisoformat(str(value or '')[:10])
        except ValueError:
            return None

    for job in applications(jobs):
        events = [event for event in job.get('history') or [] if isinstance(event, dict)]
        applied = [date(event.get('at')) for event in events if event.get('status') == 'applied']
        progressed = [date(event.get('at')) for event in events if event.get('status') in FUNNEL]
        when = (date(job.get('applied_at')) or min((day for day in applied if day), default=None)
                or min((day for day in progressed if day), default=None)
                or date(job.get('status_updated_at')) or date(job.get('found_at')))
        if when is None or when < first or when > today:
            continue
        week = when - datetime.timedelta(days=when.weekday())
        key = week.isoformat()
        if key in counts:
            counts[key] += 1
    return [{'week': key, 'count': value} for key, value in counts.items()]


MIN_MEDIAN = 20


def _when(value):
    """A zoned timestamp as a datetime, or None. Naive times never enter a timing."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else None


def _verified(job, event):
    """The time of an event only when Upwork's own record backs it, else None."""
    proof = job.get(f'{event}_observation')
    if isinstance(proof, dict) and proof.get('verified') is True:
        return _when(job.get(f'{event}_at'))
    return None


def call_time(job):
    call = _when(job.get('call_at'))
    proof = job.get('call_observation') or {}
    if call and proof.get('source') == 'recorder' and proof.get('verified') is True:
        return call, 'recorder'
    call = next((_when(h.get('at')) for h in job.get('history') or []
                 if isinstance(h, dict) and h.get('status') == 'call'), None)
    return call, 'observed'


def timings(jobs):
    """Median seconds for five gaps, each with the number of leads behind it.

    Only leads whose applied time (and reply time, where used) was observed from
    Upwork count, so a stamp written when a command happened to run never moves a
    median. A median shows from MIN_MEDIAN leads, below that only n. Time to close
    ends at the won stamp, which is the member's own record, not Upwork's.
    """
    gaps = {'speed_to_lead': [], 'client_reply': [], 'time_to_close': [], 'our_reply': [], 'call_to_proposal': []}
    values = []
    for job in jobs:
        gaps['our_reply'].extend(n for n in job.get('reply_gaps_s') or []
                                 if isinstance(n, int) and not isinstance(n, bool) and n >= 0)
        call, source = call_time(job)
        proposal = _when(job.get('proposal_sent_at'))
        if call and proposal and proposal >= call:
            seconds = (proposal - call).total_seconds()
            gaps['call_to_proposal'].append(seconds)
            values.append({'seconds': seconds, 'call_source': source,
                           'proposal_source': (job.get('proposal_sent_observation') or {}).get('source', 'member')})
        applied = _verified(job, 'applied')
        if not applied:
            continue
        lag = job.get('speed_to_lead_s')
        if isinstance(lag, int) and not isinstance(lag, bool) and lag >= 0:
            gaps['speed_to_lead'].append(lag)
        replied = _verified(job, 'replied')
        if replied and replied >= applied:
            gaps['client_reply'].append((replied - applied).total_seconds())
        won = next((_when(h.get('at')) for h in job.get('history') or []
                    if isinstance(h, dict) and h.get('status') == 'won'), None)
        if won and won >= applied:
            gaps['time_to_close'].append((won - applied).total_seconds())
    result = {name: {'n': len(values),
                   'median_s': int(statistics.median(values)) if len(values) >= MIN_MEDIAN else None}
            for name, values in gaps.items()}

    result['call_to_proposal']['values'] = values
    return result


def consistency(jobs, today=None):
    today = today or datetime.date.today()
    goal = daily_target()
    counts = {(today - datetime.timedelta(days=offset)).isoformat(): 0
              for offset in range(13, -1, -1)}
    for job in jobs:
        day = pipeline.application_day(job)
        if day in counts:
            counts[day] += 1
    days = [{'date': day, 'count': count} for day, count in counts.items()]
    return {'goal': goal, 'days': days, 'days_on_goal': sum(n >= goal for n in counts.values()),
            'total_days': 14}


def profile_history():
    path = pipeline.data_dir() / 'profile-history.jsonl'
    history = []
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
                datetime.date.fromisoformat(row['date'])
                if (isinstance(row['pct'], (int, float)) and not isinstance(row['pct'], bool)
                        and 0 <= row['pct'] <= 100 and isinstance(row['missing'], list)
                        and all(isinstance(name, str) for name in row['missing'])):
                    history.append(row)
            except (ValueError, KeyError, TypeError):
                continue
    return {'latest': history[-1] if history else None, 'history': history}


MIN_RATE = 50
NEXT_ACTIONS = {
    'Volume': 'Apply to your daily goal today.',
    'Profile': 'Fill the missing profile items in /profile.',
    'Proposal': 'Review your application opening against the client problem.',
    'Loom': 'Name the client problem in the first 15 seconds of your Loom.',
    'Speed': 'Answer the first client message sooner.',
    'Messaging': 'Review the reply and ask for a clear call next step.',
    'Sales call': 'Agree one next step before ending the call.',
    'Call proposal': 'Send the agreed proposal within 24 hours of the call.',
    'Opened': 'Review the proposal link and follow up on Upwork.',
}


def bottleneck(jobs, daily, profile, timing):
    counts = funnel(jobs)
    eligible = applications(jobs)
    hooks = [job['loom_hook'] for job in eligible if job.get('loom_hook') in ('pass', 'fail')]
    next_steps = [job['call_next_step'] for job in eligible
                  if isinstance(job.get('call_next_step'), bool) and
                  (reached(job)[1] or _when(job.get('call_at')))]
    calls = [(job, call_time(job)[0]) for job in eligible]
    calls = [(job, at) for job, at in calls if at]
    within_day = sum(1 for job, call in calls if _when(job.get('proposal_sent_at')) and
                     0 <= (_when(job['proposal_sent_at']) - call).total_seconds() <= 86400)
    def rate(successes, n):
        return 100 * successes / n if n else None
    latest = profile['latest']
    measures = [
        ('Volume', daily['days_on_goal'], 14, 14),
        ('Profile', latest['pct'] if latest else None, 1 if latest else 0, 1),
        ('Proposal', rate(counts['replied'], counts['applied']), counts['applied'], MIN_RATE),
        ('Loom', rate(hooks.count('pass'), len(hooks)), len(hooks), MIN_RATE),
        ('Speed', timing['our_reply']['median_s'] / 3600 if timing['our_reply']['median_s'] is not None else None,
         timing['our_reply']['n'], MIN_MEDIAN),
        ('Messaging', rate(counts['call'], counts['replied']), counts['replied'], MIN_RATE),
        ('Sales call', rate(next_steps.count(True), len(next_steps)), len(next_steps), MIN_RATE),
        ('Call proposal', rate(within_day, len(calls)), len(calls), MIN_RATE),
        ('Opened', rate(counts['opened'], counts['proposal_sent']), counts['proposal_sent'], MIN_RATE),
    ]
    limits = bars()
    unmeasured = [stage for stage, value, n, minimum in measures if value is None or n < minimum]
    result = {'stage': None, 'value': None, 'bar': None, 'n': 0, 'reasoned': False,
              'next_action': 'Keep the routine and measure the next result.', 'unmeasured': unmeasured}
    for stage, value, n, minimum in measures:
        if stage in unmeasured:
            continue
        failed = value > limits[stage] if stage == 'Speed' else value < limits[stage]
        if failed:
            result.update(stage=stage, value=round(value, 2), bar=limits[stage], n=n,
                          reasoned=stage not in ('Volume', 'Profile'), next_action=NEXT_ACTIONS[stage])
            break
    return result


def saved_rows(name, errors):
    """Read a ledger without turning a broken analytics row into a broken lead list."""
    path = pipeline.data_dir() / name
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        errors.append({'file': name, 'reason': 'The saved file could not be read.'})
        return []
    rows = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('not an object')
            rows.append(row)
        except (ValueError, TypeError):
            errors.append({'file': name, 'line': index,
                           'reason': 'This saved row is not a readable object.'})
    return rows


def snapshot_aliases(value):
    """Copy saved writer fields into reader aliases, without deriving any result."""
    if isinstance(value, list):
        return [snapshot_aliases(row) for row in value]
    if not isinstance(value, dict):
        return value
    row = {key: snapshot_aliases(item) for key, item in value.items()}
    for target, source in (('evidence', 'evidence_lead_ids'), ('k', 'done_k'),
                           ('n', 'done_n'), ('state', 'execution_state'),
                           ('duration_min', 'duration_minutes'), ('better', 'better_wording')):
        if target not in row and source in row:
            row[target] = row[source]
    if 'question_count' not in row and isinstance(row.get('questions'), dict) and 'member' in row['questions']:
        row['question_count'] = row['questions']['member']
    return row


def snapshot_view(snapshot, history=None):
    """Only aliases of prepared fields; missing old snapshots need a writer rerun."""
    result = snapshot_aliases(analytics.saved_snapshot_view(snapshot, history))
    presentation = dict(result['presentation']) if isinstance(result.get('presentation'), dict) else {}
    for key in ('voyage', 'funnel', 'next_run_day', 'next_run_on'):
        if key not in presentation and key in result:
            presentation[key] = result[key]
    result['presentation'] = presentation
    if isinstance(result.get('conversation_review'), dict):
        for thread in result['conversation_review'].get('threads', []):
            thread['points'] = {key: value for key, value in thread.get('points', {}).items() if key in analytics.CONVERSATION_POINTS}
    if os.environ.get('BLUEPRINT_EXAMPLE_DATA') == '1':
        result['synthetic'] = True
        result['data_label'] = 'Synthetic example · no member facts'
    return result


def analytics_state(today):
    """The cockpit reads the writer's numbers; it never runs weekly compute."""
    errors = []
    raw_snapshots = saved_rows('analytics-history.jsonl', errors)
    snapshots = [snapshot_view(row, raw_snapshots) for row in raw_snapshots]
    history = snapshots
    latest = max(history, key=lambda row: _when(row.get('generated_at')) or
                 datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), default=None)
    if latest is not None:
        presentation = latest['presentation']
        missing = [f'presentation.{key}' for key in ('number_keys', 'kpi_groups', 'insights', 'funnel', 'voyage', 'scorecard')
                   if key not in presentation]
        missing += [key for key in ('call_cards', 'funnel_score', 'conversation_review', 'gap') if key not in latest]
        if not isinstance(latest.get('coverage'), dict) or not {'sources', 'missing'} <= latest['coverage'].keys():
            missing.append('coverage.missing')
        if missing:
            errors.append({'file': 'analytics-history.jsonl', 'week': latest.get('week'),
                           'fields': missing, 'reason': 'Prepared fields are missing. Run /analytics to refresh this snapshot.'})
    goals_history = saved_rows('goals.jsonl', errors)
    iso = today.isocalendar()
    week = f'{iso.year}-W{iso.week:02d}'
    eligible = [row for row in goals_history if isinstance(row.get('week'), str)
                and row['week'] <= week and isinstance(row.get('goals'), list)]
    current = max(eligible, key=lambda row: row['week'], default=None)
    goals = [goal for goal in current['goals'] if isinstance(goal, dict)] if current else []
    # Weekly tiers and instant awards have separate writers. Neither source hides
    # an earned tier in the other, including when a later snapshot omits an award.
    awards_by_tier = {}
    for row in snapshots + [{'badges': saved_rows('badges.jsonl', errors)}]:
        for award in row.get('badges') or []:
            if not isinstance(award, dict) or not award.get('badge') or not award.get('tier'):
                continue
            key = (award['badge'], award['tier'])
            awards_by_tier[key] = dict(awards_by_tier.get(key, {}), **award)
    awards = list(awards_by_tier.values())
    try:
        due = bool(analytics.due(today))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        due = True
        errors.append({'file': 'analytics-history.jsonl',
                       'reason': 'Run /analytics to restore the weekly due check.'})
    schedule = analytics.sections().get('Analytics day', 'Monday').casefold()
    names = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
    next_run_day = ((latest or {}).get('presentation') or {}).get('next_run_day') or next(
        (name for name in names if name.casefold() in schedule), 'Monday')
    return {'latest': latest, 'history': history, 'goals': goals, 'badges': awards,
            'voyage': ((latest or {}).get('presentation') or {}).get('voyage'),
            'goals_week': current['week'] if current else None,
            'goals_history': goals_history, 'due': due, 'next_run_day': next_run_day, 'errors': errors}


def event_progress(jobs, saved, today):
    """Only daily voyage and quest event counts may be read live for analytics."""
    progress = {}
    try:
        import badges
        helper = getattr(badges, 'cockpit_progress', None)
        if helper:
            progress = helper(jobs, today=today, snapshot=saved['latest'], goals=saved['goals'])
    except (ImportError, OSError, ValueError, TypeError, KeyError):
        saved['errors'].append({'file': 'badges.jsonl',
                                'reason': 'Today’s badge progress could not be read.'})
    voyage = progress.get('daily_voyage') if isinstance(progress, dict) else None
    # The analytics helper returns a flat voyage; the badge helper wraps it.
    if voyage is None and isinstance(progress, dict) and 'applications' in progress:
        voyage = progress
    if voyage is None and hasattr(analytics, 'daily_voyage'):
        voyage = analytics.daily_voyage(jobs, today)
    if not isinstance(voyage, dict):
        voyage = {'date': today.isoformat(), 'goal': None, 'applications': None}
    voyage = dict(voyage, fast_applications=voyage.get('fast_applications', voyage.get('fast')),
                  follow_ups_done=voyage.get('follow_ups_done', voyage.get('followups_done')),
                  follow_ups_due=voyage.get('follow_ups_due', voyage.get('followups_due')))
    snapshot = saved['latest'] or {}
    quests = progress.get('quests') if isinstance(progress, dict) else None
    live_quests = quests is not None
    goals = (saved['goals'] if live_quests else snapshot.get('goals_next')) or []
    quest_period = ({'start': (today - datetime.timedelta(days=today.weekday())).isoformat(),
                     'end': today.isoformat()} if live_quests else
                    (snapshot.get('periods') or {}).get('activity'))
    if quests is None:
        quests = snapshot.get('quests') or []
    by_key = {goal.get('kpi'): goal for goal in goals if isinstance(goal, dict)}
    result = []
    for quest in quests:
        if not isinstance(quest, dict):
            continue
        goal = by_key.get(quest.get('kpi'), {})
        result.append(dict(quest, text=quest.get('text', quest.get('change', goal.get('change'))),
                           k=quest.get('k', quest.get('done_k')), n=quest.get('n', quest.get('done_n')),
                           primary=quest.get('primary', goal.get('primary', False)),
                           state=quest.get('state', quest.get('execution_state', goal.get('execution_state'))),
                           period=quest.get('period', quest_period)))
    return voyage, result


def build_state():
    jobs = pipeline.load()
    now = datetime.datetime.now(pipeline.member_zone())
    today = now.date()
    saved = analytics_state(today)
    voyage, quests = event_progress(jobs, saved, today)
    done = pipeline.applied_on(jobs, today.isoformat())
    state = {
        'generated_at': now.isoformat(timespec='seconds'),
        'jobs': [card(j) for j in jobs],
        'sync': last_sync(),
        'tracker': {'goal': daily_target(), 'done': done},
        'analytics': saved,
        'analytics_due': saved['due'],
        'goals': saved['goals'],
        'badges': saved['badges'],
        'daily_voyage': voyage,
        'quests': quests,
    }
    return state


def last_sync():
    """When /brief last brought the pipeline in line with Upwork, and what it found."""
    f = pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data') / 'sync.json'
    try:
        return json.loads(f.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


# --- starting the app ---------------------------------------------------------------

def needs_build():
    """A build is stale when any source file is newer than it."""
    build = APP / '.next' / 'BUILD_ID'
    if not build.is_file():
        return True
    built = build.stat().st_mtime
    sources = [APP / 'package.json', APP / 'next.config.mjs']
    for folder in ('app', 'components', 'lib'):
        sources += [p for p in (APP / folder).rglob('*') if p.is_file()]
    return any(p.stat().st_mtime > built for p in sources if p.exists())


def npm(*args):
    """npm on macOS, Linux and Windows (where it is a .cmd file and needs the shell)."""
    exe = shutil.which('npm')
    if not exe:
        print('The cockpit needs Node.js. Install the LTS version from https://nodejs.org, '
              'open a new terminal, then run this again.', file=sys.stderr)
        sys.exit(1)
    return [exe, *args], os.name == 'nt'


def port_busy(port):
    import socket
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def stop_child(child):
    """Stop only the server process this launch created, without waiting forever."""
    try:
        child.terminate()
    except OSError:
        return
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            child.kill()
        except OSError:
            return
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def start_server(port):
    """Start the built cockpit and wait for it to answer.

    Returns the running child, or the reason it never answered: the exit code when
    the server gave up on its own, and None when it simply never came up.
    """
    cmd, shell = npm('run', 'start', '--', '-p', str(port))
    env = dict(os.environ, BLUEPRINT_ROOT=str(ROOT))
    child = subprocess.Popen(cmd, cwd=APP, env=env, shell=shell)
    url = f'http://127.0.0.1:{port}/'
    for _ in range(60):
        try:
            response = urllib.request.urlopen(url, timeout=1)
            response.close()
            return child, None
        except OSError:
            exit_code = child.poll()
            if exit_code is not None:
                return None, exit_code
            time.sleep(0.5)
    stop_child(child)
    return None, None


def build(clean):
    """Build the cockpit, from scratch when the folder on disk is not trustworthy."""
    if clean:
        shutil.rmtree(APP / '.next', ignore_errors=True)
    cmd, shell = npm('run', 'build')
    subprocess.run(cmd, cwd=APP, check=True, shell=shell)


def serve(port, open_browser):
    # An older cockpit still holding the port would answer for us with stale files
    # and a page stuck on "Loading.", so a busy port stops the start instead.
    if port_busy(port):
        print(f'Port {port} is taken, most likely by a cockpit that is still running. '
              f'Stop that one (Ctrl+C in its terminal) or start this one with --port {port + 1}.', file=sys.stderr, flush=True)
        return 1
    if not (APP / 'node_modules').is_dir():
        print('First start: installing the cockpit (about a minute, only this once).', flush=True)
        cmd, shell = npm('install', '--no-audit', '--no-fund')
        subprocess.run(cmd, cwd=APP, check=True, shell=shell)
    # A build folder left behind by a development server, or by a build that was
    # interrupted, mixes two kinds of output: the production server then dies on a
    # missing chunk although the build reported success. So the first build of a
    # session starts from scratch.
    if needs_build():
        print('Building the cockpit (about a minute after each update).', flush=True)
        build(clean=True)
    # The URL is printed and the browser opened only once the server has answered a
    # request. A tab opened a second early shows the member an error page for a
    # cockpit that is about to be fine, and they close it before it is.
    url = f'http://127.0.0.1:{port}/'
    child, exit_code = start_server(port)
    # Only a server that never answered. A corrupt build keeps the process alive and
    # logging, which is exactly this case; an early exit is a port or a config and a
    # rebuild would not touch it. `needs_build` compares timestamps, so a build that
    # is current and unusable stays current forever.
    if child is None and exit_code is None:
        print('The cockpit did not start. Rebuilding it from scratch, about a minute.',
              file=sys.stderr, flush=True)
        build(clean=True)
        child, exit_code = start_server(port)
    if child is None:
        if exit_code is not None:
            print(f'Cockpit failed to start: its server exited with code {exit_code}.',
                  file=sys.stderr, flush=True)
            return exit_code or 1
        print(f'Cockpit failed to start: {url} did not become ready during startup.',
              file=sys.stderr, flush=True)
        return 1
    print(f'Cockpit running at {url}  (Ctrl+C stops it)', flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('what', nargs='?', default='serve', choices=('serve', 'state', 'job'))
    ap.add_argument('job_id', nargs='?')
    ap.add_argument('--port', type=int, default=4321)
    ap.add_argument('--no-open', action='store_true')
    args = ap.parse_args(argv)
    if args.what == 'state':
        print(json.dumps(build_state(), ensure_ascii=False))
        return 0
    if args.what == 'job':
        job = job_view(args.job_id or '')
        print(json.dumps(job, ensure_ascii=False))
        return 0 if job else 1
    return serve(args.port, not args.no_open)


if __name__ == '__main__':
    sys.exit(main())
