#!/usr/bin/env python3
"""Event awards and the sole atomic writer of data/badges.jsonl.

Pipeline callers may catch failures after their own write; an award never edits jobs.
Weekly analytics owns eligibility of higher tiers and passes its earned display rows to
award_weekly. All functions except check/award_weekly are read-only.
"""
import argparse
import datetime as dt
import fcntl
import json
import math
import os
import pathlib
import tempfile

import pipeline
import call_stats

TIERS = ('Bronze', 'Silver', 'Gold', 'Platinum', 'Legend')
BADGE_NAMES = ('Harbour Master', 'First Mate', 'Treasure Hunter', 'Swift Sail',
               "Ship's Bell", 'Lookout', 'Steady Anchor', 'Quick Draw',
               'Message in a Bottle', 'True North', 'Navigator', 'Lighthouse Keeper',
               'First Doubloon', 'Back on Course')
QUALIFYING_WEEKS = (1, 3, 6, 13, 26)
LEDGER_KEYS = {'badge', 'tier', 'lead_id', 'at', 'reason'}


def _stamp(value):
    if isinstance(value, dt.datetime):
        return value if value.tzinfo is not None else None
    try:
        value = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value if value.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _now(now=None):
    value = _stamp(now) if now is not None else dt.datetime.now(pipeline.member_zone())
    if value is None:
        raise ValueError('Badge time needs an ISO timestamp with a timezone.')
    return value


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _fit(job):
    if isinstance(job.get('job_fit'), dict):
        return job['job_fit']
    prefix = 'analytics job_fit: '
    for row in reversed(job.get('log') or []):
        text = str(row.get('text', ''))
        if text.startswith(prefix):
            try:
                value = json.loads(text[len(prefix):])
                if isinstance(value, dict):
                    return value
            except (TypeError, ValueError):
                pass
    return {}


def _qualified(job):
    fit = _fit(job)
    return fit.get('state') == 'pass' or (fit.get('state') == 'unclear' and
                                         bool(str(fit.get('reason', '')).strip()))


def content_pass(job, kind='application'):
    """Recognition needs an explicit passed content review, not speed or a sent flag."""
    review = job.get(kind + '_review')
    if not isinstance(review, dict):
        prefix = 'analytics ' + kind + '_review: '
        for row in reversed(job.get('log') or []):
            if str(row.get('text') or '').startswith(prefix):
                try: review = json.loads(row['text'][len(prefix):])
                except (ValueError, TypeError): review = None
                break
    if not isinstance(review, dict): return False
    if review.get('state') == 'pass': return bool(str(review.get('reason') or review.get('quote') or '').strip())
    points = review.get('points')
    return bool(review.get('reviewable') is True and isinstance(points, list) and points and
                all(row.get('state') in ('met', 'not needed', 'not_needed') and
                    (row.get('state') == 'met' or str(row.get('reason') or '').strip()) for row in points))


def _call_end(job):
    ended, held = _stamp(job.get('call_ended_at')), _stamp(job.get('call_held_at'))
    duration = job.get('call_duration_s')
    return ended or (held + dt.timedelta(seconds=duration)
                     if held and _number(duration) and duration >= 0 else None)


def _proposal_possible(job):
    outcome = str(job.get('call_outcome', '')).casefold().replace('-', '_')
    if (job.get('proposal_required') is False or outcome in (
            'disqualified', 'clean_disqualification', 'not_a_fit') or _fit(job).get('state') == 'fail'):
        return False
    # Offer/contract bypasses are not missed proposal opportunities.
    if not _stamp(job.get('proposal_sent_at')) and any(_stamp(job.get(key)) for key in
            ('offered_at', 'offer_at', 'won_at')):
        return False
    return True


def read_ledger():
    """Read earned event/weekly awards; missing means an empty ledger."""
    path = pipeline.data_dir() / 'badges.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()] if path.is_file() else []
    for row in rows:
        _validate(row)
    return rows


def _validate(row):
    if (not isinstance(row, dict) or set(row) != LEDGER_KEYS or
            row.get('badge') not in BADGE_NAMES or row.get('tier') not in TIERS or
            _stamp(row.get('at')) is None or not isinstance(row.get('reason'), str) or
            not row['reason'].strip() or
            (row.get('lead_id') is not None and not isinstance(row['lead_id'], str))):
        raise ValueError('Badge ledger row needs badge, tier, lead_id, zoned at and reason.')


def _append(candidates):
    """Lock read/dedup/replace together; each badge tier is earned only once."""
    for row in candidates:
        _validate(row)
    if not candidates:
        return []
    directory = pipeline.data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.badges.lock').open('a', encoding='utf-8') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = read_ledger()
        seen = {(row['badge'], row['tier']) for row in existing}
        new = []
        dated = [_stamp(row['at']).astimezone(pipeline.member_zone()).date() for row in existing + candidates]
        activity = []
        try:
            for job in pipeline.load():
                if job.get('imported'): continue
                for field in ('applied_at', 'invited_at', 'offer_at', 'offered_at', 'call_held_at', 'won_at'):
                    event = _stamp(job.get(field))
                    if event: activity.append(event.astimezone(pipeline.member_zone()).date())
        except (OSError, ValueError, TypeError):
            pass
        first = min(activity or dated, default=None)
        first_iso = first.isocalendar()[:2] if first else None
        first_names = {row['badge'] for row in existing if _stamp(row['at']).astimezone(pipeline.member_zone()).date().isocalendar()[:2] == first_iso}
        for row in sorted(candidates, key=lambda item: (item['at'], item['badge'], TIERS.index(item['tier']))):
            key = row['badge'], row['tier']
            is_first = _stamp(row['at']).astimezone(pipeline.member_zone()).date().isocalendar()[:2] == first_iso
            if is_first and row['badge'] not in first_names and len(first_names) >= 2: continue
            if key not in seen:
                if is_first: first_names.add(row['badge'])
                new.append(row)
                seen.add(key)
        if not new:
            return []
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                             prefix='.badges-', delete=False) as stream:
                temporary = pathlib.Path(stream.name)
                for row in existing + new:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, directory / 'badges.jsonl')
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return new


def _thread_answers(job):
    path = pipeline.jobs_dir() / str(job['id']) / 'thread.json'
    thread = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    values = [_stamp(row.get('at')) for row in thread.get('messages', [])
              if row.get('from') == 'client' and row.get('kind', 'message') == 'message']
    values.append(_stamp(job.get('replied_at')))
    return [value for value in values if value]


def _call_reviews(jobs):
    """Consume validated saved weekly rubrics; also accept job-local full rubrics."""
    result = {}
    path = pipeline.data_dir() / 'analytics-history.jsonl'
    history = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
               if line.strip()] if path.is_file() else []
    for snapshot in sorted(history, key=lambda row: row.get('week', '')):
        if snapshot.get('kpis', {}).get('call_review', {}).get('state') != 'pass':
            continue
        for review in snapshot.get('reviews', {}).get('call', {}).get('rubric', []):
            if review.get('reviewable'):
                result[str(review.get('lead_id'))] = review.get('points', [])
    for job in jobs:
        review = job.get('call_review')
        if isinstance(review, dict) and review.get('reviewable') is True:
            result[str(job['id'])] = review.get('points', [])
    return result


def _call_fraction(points):
    # Full nine-point evidence is mandatory; not-needed points are excluded.
    if (not isinstance(points, list) or len(points) != 9 or
            {row.get('point') for row in points if isinstance(row, dict)} != set(range(1, 10)) or
            any(row.get('state') not in ('met', 'partly', 'missing', 'not needed') or row.get('state') == 'not needed' and not str(row.get('reason') or '').strip() for row in points)):
        return None
    applicable = [row for row in points if row['state'] != 'not needed']
    return sum(row['state'] == 'met' for row in applicable) / len(applicable) if applicable else None


def confirmed_application(job):
    """Verified platform event or explicit member stage action, never import placeholders."""
    observation = job.get('applied_observation') or {}
    return (not job.get('imported') and not job.get('application_date_unknown') and _stamp(job.get('applied_at')) is not None and
            (observation.get('verified') is True and observation.get('source') == 'upwork-proposal' or
             any(item.get('status') == 'applied' and _stamp(item.get('at')) for item in job.get('history') or [])))


def _events(jobs, now):
    reviews = _call_reviews(jobs)
    for job in jobs:
        if job.get('imported'):
            continue
        lead_id = str(job['id'])
        won = _stamp(job.get('won_at'))
        if not won:
            try:
                start = dt.date.fromisoformat((job.get('won_value') or {}).get('start_date', ''))
                won = dt.datetime.combine(start, dt.time(), pipeline.member_zone())
            except (TypeError, ValueError):
                pass
        if won and won <= now:
            yield 'First Doubloon', lead_id, won, 'First won contract.'
        held = _stamp(job.get('call_held_at'))
        fraction = _call_fraction(reviews.get(lead_id))
        transcript_path = pipeline.jobs_dir() / lead_id / 'call.md'
        try: transcript = call_stats.analyze(transcript_path.read_text(encoding='utf-8')) if transcript_path.is_file() else {}
        except (OSError, UnicodeError): transcript = {}
        if held and held <= now and fraction is not None and fraction >= 7 / 9 and transcript.get('transcript_complete') is True and transcript.get('member_attributed') is True:
            yield 'True North', lead_id, held, 'At least 7 of 9 applicable call-review points met.'


def check(jobs=None, lead_id=None, since=None, now=None):
    """Persist new Bronze event awards, returning their exact ledger rows.

    since restricts event times, rather than job update times. Explicit jobs supports
    pipeline integration after its successful write without reloading that write.
    """
    clock = _now(now)
    lower = None
    if since is not None:
        lower = _stamp(since)
        if lower is None:
            try:
                lower = dt.datetime.combine(dt.date.fromisoformat(str(since)), dt.time(), pipeline.member_zone())
            except (TypeError, ValueError):
                raise ValueError('Badge since needs an ISO date or zoned timestamp.') from None
    jobs = pipeline.load() if jobs is None else jobs
    if lead_id is not None:
        jobs = [job for job in jobs if str(job['id']) == str(lead_id)]
        if not jobs:
            raise ValueError(f'Unknown lead: {lead_id}.')
    rows = [{'badge': name, 'tier': 'Bronze', 'lead_id': jid,
             'at': at.isoformat(), 'reason': reason}
            for name, jid, at, reason in _events(jobs, clock) if lower is None or at >= lower]
    return _append(rows)


def award_weekly(badges, week=None, now=None):
    """Persist computed weekly tiers, without reevaluating analytics eligibility."""
    clock = _now(now)
    rows = []
    for badge in badges:
        if badge.get('badge') not in BADGE_NAMES or badge.get('tier') not in TIERS:
            raise ValueError('Unknown weekly badge or tier.')
        rows.append({'badge': badge['badge'], 'tier': badge['tier'], 'lead_id': None,
                     'at': clock.isoformat(),
                     'reason': 'Weekly analytics criteria met' + (f' for {week}' if week else '') + '.'})
    return _append(rows)


def rank(badges):
    """Count distinct badge names at each tier or higher, never duplicate tier rows."""
    highest = {}
    for row in badges:
        if row.get('badge') in BADGE_NAMES and row.get('tier') in TIERS:
            name, value = row['badge'], TIERS.index(row['tier'])
            highest[name] = max(highest.get(name, -1), value)
    result = 'Deckhand'
    for tier, title in enumerate(('Boatswain', 'Officer', 'Captain', 'Admiral'), start=1):
        if sum(value >= tier for value in highest.values()) >= 3:
            result = title
    return result


def _week_date(week):
    try:
        year, number = str(week).split('-W')
        return dt.date.fromisocalendar(int(year), int(number), 1)
    except (TypeError, ValueError):
        raise ValueError('Streak week needs YYYY-Www.') from None


def streak_history(history, week=None, test=None, current=None):
    """Replay chronologically: the first missed week each month consumes its anchor.

    Protected gaps keep the counter but do not add a completed week. The month is
    the missed ISO week's Monday's calendar month. A second gap in that month
    resets only the counter; it never touches awards. test defaults to run existence.
    """
    rows = {row['week']: row for row in history}
    if current is not None:
        rows[current['week']] = current
    if not rows:
        return {'streak_weeks': 0, 'anchors_used': []}
    ending = _week_date(week or max(rows))
    eligible = [_week_date(key) for key in rows if _week_date(key) <= ending]
    if not eligible:
        return {'streak_weeks': 0, 'anchors_used': []}
    start = min(eligible)
    predicate = test or (lambda row: True)
    count, months, anchors, begun = 0, set(), [], False
    cursor = start
    while cursor <= ending:
        iso = cursor.isocalendar()
        key = f'{iso.year}-W{iso.week:02d}'
        row, month = rows.get(key), (cursor.year, cursor.month)
        if row is not None and predicate(row):
            count += 1
            begun = True
        elif row is not None:
            # A recorded failing habit week breaks its run; anchors cover absence only.
            count, begun = 0, False
        elif begun:
            if month not in months:
                months.add(month)
                anchors.append(key)
            else:
                count, begun = 0, False
        cursor += dt.timedelta(weeks=1)
    return {'streak_weeks': count, 'anchors_used': anchors}


def streak(history, week=None, test=None, current=None):
    return streak_history(history, week=week, test=test, current=current)['streak_weeks']


def event_counters(jobs, now=None):
    """Pure trailing opportunity counters; missing overdue actions break a run."""
    clock = _now(now)
    proposals, invites, followups = [], [], []
    reviews = _call_reviews(jobs)
    calls = []
    for job in jobs:
        if job.get('imported'):
            continue
        ended, sent = _call_end(job), _stamp(job.get('proposal_sent_at'))
        if _proposal_possible(job) and ended and ended + dt.timedelta(minutes=30) <= clock:
            proposals.append((ended, bool(sent and 0 <= (sent - ended).total_seconds() <= 1800)))
        invited, reply = _stamp(job.get('invited_at')), _stamp(job.get('first_reply_at'))
        route = (job.get('application_facts') or {}).get('source', job.get('source', 'outbound'))
        if route == 'invite' and invited and invited + dt.timedelta(hours=1) <= clock:
            invites.append((invited, bool(reply and 0 <= (reply - invited).total_seconds() <= 3600)))
        held = _stamp(job.get('call_held_at'))
        fraction = _call_fraction(reviews.get(str(job['id'])))
        if held and held <= clock and fraction is not None:
            calls.append((held, fraction == 1))
        for row in job.get('follow_up_history', []):
            due = row.get('due_on')
            if row.get('lane') == 'silent' and due and due < clock.astimezone(pipeline.member_zone()).date().isoformat():
                followups.append((due, row.get('action') == 'sent' and row.get('on') == due))
    def tail(rows):
        total = 0
        for _, successful in reversed(sorted(rows, key=lambda row: row[0])):
            if not successful:
                break
            total += 1
        return total
    return {'proposal_streak': tail(proposals), 'invite_streak': tail(invites),
            'perfect_call_streak': tail(calls), 'follow_up_streak': tail(followups)}


def award_lines(rows):
    return [f"{row['badge']} · {row['tier']}: {row['reason']}" for row in rows]


def catalogue_criteria():
    path = pathlib.Path(__file__).resolve().parents[1] / 'outputs/badges-catalogue.md'
    try: text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError): return {}
    result = {}
    for line in text.splitlines():
        if line.startswith('| '):
            fields = [field.strip() for field in line.strip().strip('|').split('|')]
            if len(fields) >= 3 and fields[0] in BADGE_NAMES: result[fields[0]] = fields[2]
    return result


def voyage(awards, snapshot=None):
    """Pure ledger overlay: highest retained tier, rank, and fourteen stations. No KPI writes."""
    snapshot = snapshot or {}
    result = dict((snapshot.get('presentation') or {}).get('voyage') or snapshot.get('voyage') or {})
    top = {}
    for row in list(snapshot.get('badges', [])) + list(awards):
        if row.get('badge') not in BADGE_NAMES or row.get('tier') not in TIERS: continue
        if row['badge'] not in top or TIERS.index(row['tier']) >= TIERS.index(top[row['badge']]['tier']): top[row['badge']] = row
    motifs = ('harbour', 'ship', 'treasure', 'hourglass', 'bell', 'spyglass', 'anchor', 'cannon', 'bottle', 'compass', 'wheel', 'lighthouse', 'doubloon', 'storm')
    requirements = catalogue_criteria()
    old = {row.get('badge'): row for row in result.get('stations', [])}
    stations = []
    for name, motif in zip(BADGE_NAMES, motifs):
        requirement = requirements.get(name, 'unknown: badge catalogue unavailable')
        award = top.get(name, {}); tier = award.get('tier'); at = _stamp(award.get('at')); iso = at.isocalendar() if at else None
        week = award.get('earned_week') or (f'{iso.year}-W{iso.week:02d}' if iso else None)
        progress = award.get('progress_to_next') or old.get(name, {}).get('progress_to_next')
        slug = name.lower().replace("'", '').replace(' ', '-')
        image = f'/badges/{slug}-{tier.lower()}.webp' if tier else f'/badges/badge-{motif}.webp'
        stations.append({'badge': name, 'motif': motif, 'tier': tier, 'earned': bool(tier), 'earned_week': week,
                         'image': image, 'fallback_image': f'/badges/badge-{motif}.webp',
                         'locked': not bool(tier), 'island_revealed': bool(tier), 'requirement': requirement, 'criterion': requirement,
                         'progress_to_next': progress, 'next_tier': TIERS[TIERS.index(tier)+1] if tier and tier != TIERS[-1] else TIERS[0] if not tier else None,
                         'evidence': [award['lead_id']] if award.get('lead_id') else []})
    silver = sum(TIERS.index(row['tier']) >= 1 for row in top.values())
    current_rank = rank(list(top.values()))
    titles = ('Deckhand', 'Boatswain', 'Officer', 'Captain', 'Admiral')
    current_index = titles.index(current_rank)
    required_tier = TIERS[min(current_index + 1, 4)]
    eligible = sum(TIERS.index(row['tier']) >= min(current_index + 1, 4) for row in top.values())
    next_rank = titles[current_index + 1] if current_index < 4 else None
    progress = {'qualified_badges': silver, 'eligible_badges': eligible, 'needed': 3,
                'basis': 'Distinct Silver-or-higher badges', 'required_tier': required_tier, 'next_rank': next_rank,
                'text': f'{min(eligible, 3)} of 3 {required_tier}-or-higher badges toward {next_rank}' if next_rank else 'Admiral requirements met'}
    result.update(stations=stations, rank=current_rank, rank_progress=progress)
    return result


def cockpit_progress(jobs, today=None, snapshot=None, goals=None):
    """Read current voyage and saved commitments as live, pure event counts.

    Cockpit's goals list is its latest eligible goals.jsonl entry, so it overrides
    the older snapshot's suggested commitments, including an explicitly empty
    list. Import lazily because analytics itself consumes this badge module.
    """
    import analytics
    date = analytics.as_today(today)
    current = dict(snapshot or {})
    commitments = current.get('goals_next', []) if goals is None else goals
    current['goals_next'] = [goal for goal in commitments if isinstance(goal, dict)
                             and (not goal.get('start') or analytics.day(goal['start']) is not None
                                  and analytics.day(goal['start']) <= date)]
    return {'daily_voyage': analytics.daily_voyage(jobs, today=date),
            'quests': analytics.quest_progress(current, jobs, today=date)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('check')
    choice = command.add_mutually_exclusive_group(required=True)
    choice.add_argument('lead_id', nargs='?')
    choice.add_argument('--all-since', dest='since')
    args = parser.parse_args()
    try:
        for line in award_lines(check(lead_id=args.lead_id, since=args.since)):
            print(line)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f'Badge check failed: {error}\n')


if __name__ == '__main__':
    main()
