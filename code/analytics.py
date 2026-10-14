#!/usr/bin/env python3
"""Weekly analytics. Read the pipeline; write only weekly snapshots and goals.

    python3 code/analytics.py compute [--today YYYY-MM-DD]
    python3 code/analytics.py record --file - [--replace]
    python3 code/analytics.py goals add --file -
    python3 code/analytics.py last
    python3 code/analytics.py due [--today YYYY-MM-DD]
"""
import argparse
import copy
import contextvars
import datetime as dt
import fcntl
import functools
import hashlib
import html
import shutil
import struct
import subprocess
import tempfile
import json
import math
import os
import pathlib
import re
import statistics
import sys
from zoneinfo import ZoneInfo

import pipeline
import call_stats
import badges as badge_ledger

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULTS = {'won_value': None, 'value_per_100_connects': None, 'reply_rate': 20, 'reply_to_call': 50, 'booked_to_held': 90,
            'held_to_proposal': 90, 'proposal_to_won': 30, 'invite_to_call': 50,
            'offer_to_contract': 80, 'weekly_volume': 25, 'speed_10min': 80,
            'first_reply': 5, 'first_reply_p75': 15, 'follow_ups_on_time': 100,
            'proposal_on_time': 90, 'job_fit': 100}
LEGACY_BARS = {'Volume': 10, 'Profile': 100, 'Proposal': 10, 'Loom': 100, 'Speed': 2,
               'Messaging': 30, 'Sales call': 80, 'Call proposal': 90, 'Opened': 80}
MIN_OUTCOME_CASES = 1  # Nonempty cohort; Wilson alone gates performance and promotion.
FUNNEL = ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal',
          'proposal_to_won', 'invite_to_call', 'offer_to_contract')
LABELS = {'won_value': 'New contract value won this week', 'value_per_100_connects': 'Period contract value per 100 net Connects',
          'reply_rate': 'Reply rate', 'reply_to_call': 'Call rate',
          'booked_to_held': 'Show-up rate', 'held_to_proposal': 'Held call to proposal',
          'proposal_to_won': 'Win rate', 'invite_to_call': 'Invite → call',
          'offer_to_contract': 'Offer → contract', 'weekly_volume': 'Weekly applications',
          'speed_10min': 'Applied within 10 minutes', 'first_reply': 'Our first reply',
          'follow_ups_on_time': 'Follow-ups on their due day', 'proposal_on_time': 'Proposal within 30 min of call end',
          'job_fit': 'Jobs that fit lane and rate', 'application_review': 'Application review',
          'conversation_review': 'Conversation review', 'call_review': 'Call review',
          'proposal_review': 'Proposal review', 'segments': 'Segments', 'behaviour': 'Behaviour',
          'lost_reasons': 'Lost reasons', 'goal_effect': 'Effect of last week’s goals', 'goal_done': 'Goals carried out'}
ACTIONS = {'reply_rate': 'Name the client problem and one matching proof in your application.',
           'reply_to_call': 'Offer two concrete call times in your reply.',
           'booked_to_held': 'Confirm the call and its agenda before the booked time.',
           'held_to_proposal': 'Agree the scope and next step before ending the call.',
           'proposal_to_won': 'Confirm the decision date and follow up on that day.',
           'invite_to_call': 'Answer the invitation with a clear next step.',
           'offer_to_contract': 'Clarify the terms and agree the contract start.',
           'weekly_volume': 'Set aside time for the weekly application goal.',
           'speed_10min': 'Prepare your proof before checking newly posted jobs.',
           'first_reply': 'Check interested replies during working hours.',
           'follow_ups_on_time': 'Complete the silent-lane follow-ups due today.',
           'proposal_on_time': 'Draft the proposal immediately after the held call.'}

# Lower outcome rungs exist only where the frozen specification supplies them.
RUNGS = {'reply_rate': (11, 15, 20), 'reply_to_call': (30, 40, 50),
         'booked_to_held': (70, 80, 90), 'held_to_proposal': (70, 80, 90),
         'proposal_to_won': (20, 25, 30), 'invite_to_call': (30, 40, 50),
         'offer_to_contract': (60, 70, 80)}
FEEDING_LEVERS = {'reply_rate': ('speed_10min',),
                  'reply_to_call': ('first_reply', 'follow_ups_on_time'),
                  'held_to_proposal': ('proposal_on_time',)}
LEVERS = ('weekly_volume', 'speed_10min', 'first_reply', 'follow_ups_on_time', 'proposal_on_time')
TIERS = ('Bronze', 'Silver', 'Gold', 'Platinum', 'Legend')
OUTCOME_BADGES = {'Harbour Master': ('reply_rate', (11, 15, 20, 25, 30)),
                  'First Mate': ('reply_to_call', (30, 40, 50, 60, 70)),
                  'Treasure Hunter': ('call_to_won', (20, 25, 30, 40, 50))}
BADGE_NAMES = tuple(OUTCOME_BADGES) + ('Swift Sail', "Ship's Bell", 'Lookout', 'Steady Anchor',
    'Quick Draw', 'Message in a Bottle', 'True North', 'Navigator', 'Lighthouse Keeper',
    'First Doubloon', 'Back on Course')


def context_text():
    path = pathlib.Path(os.environ.get('BLUEPRINT_CONTEXT') or ROOT / 'context') / 'me.md'
    return path.read_text(encoding='utf-8') if path.is_file() else ''


def sections():
    result, name = {}, None
    for line in context_text().splitlines():
        if line.startswith('## '):
            name = line[3:].strip()
            result.setdefault(name, [])
        elif name:
            result[name].append(line.strip())
    return {key: '\n'.join(value).strip() for key, value in result.items()}


def bars():
    """Package 2 names plus unchanged legacy names for the existing cockpit."""
    result = {**LEGACY_BARS, **DEFAULTS}
    for line in sections().get('Bars', '').splitlines():
        match = re.fullmatch(r'\s*([^:]+):\s*(\d+(?:\.\d+)?)\s*', line)
        if not match or match[1].strip() not in result:
            continue
        name, value = match[1].strip(), float(match[2])
        maximum = (14 if name == 'Volume' else None if name in
                   ('Speed', 'first_reply', 'first_reply_p75', 'weekly_volume', 'won_value', 'value_per_100_connects') else 100)
        if math.isfinite(value) and value >= 0 and (maximum is None or value <= maximum):
            result[name] = value
    weekly = re.search(r'\d+', sections().get('Weekly goal', ''))
    if weekly and 'weekly_volume' not in sections().get('Bars', ''):
        result['weekly_volume'] = int(weekly[0])
    return result


def data_path(name):
    return pipeline.data_dir() / name


def read_lines(name):
    path = data_path(name)
    try:
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.is_file() else []
    except (OSError, UnicodeError, ValueError):
        if name not in ('earnings.jsonl', 'connects.jsonl'): raise
        return []


def timestamp(value):
    try:
        stamp = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp if stamp.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def day(value):
    stamp = timestamp(value)
    if stamp:
        return stamp.astimezone(local_zone()).date()
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


_RUN_ZONE = contextvars.ContextVar('analytics_member_zone', default=None)


def local_zone():
    return _RUN_ZONE.get() or pipeline.member_zone()


def member_clock(function):
    @functools.wraps(function)
    def zoned(*args, **kwargs):
        if _RUN_ZONE.get() is not None: return function(*args, **kwargs)
        token = _RUN_ZONE.set(pipeline.member_zone())
        try: return function(*args, **kwargs)
        finally: _RUN_ZONE.reset(token)
    return zoned


def run_timestamp(today=None, now=None):
    if now is not None:
        stamp = now if isinstance(now, dt.datetime) else timestamp(now)
        require(stamp is not None and stamp.tzinfo is not None, 'Run time needs a zoned timestamp.')
        return stamp.astimezone(local_zone())
    stamp = dt.datetime.now(local_zone())
    if today is not None:
        date = as_today(today)
        stamp = dt.datetime.combine(date, stamp.timetz().replace(tzinfo=None), local_zone())
    return stamp


def as_today(value=None):
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(value) if value else dt.datetime.now(local_zone()).date()


def event(job, name):
    if name == 'offer':
        names = ('offered_at', 'offer_at')
    elif name == 'won':
        names = ('won_at',)
    else:
        names = (name + '_at',)
    values = [timestamp(job.get(key)) for key in names]
    # Stage history records discovery time, never sales outcome time.
    values = [value for value in values if value]
    if values:
        return min(values)
    if name == 'won':
        started = day((job.get('won_value') or {}).get('start_date'))
        if started:
            return dt.datetime.combine(started, dt.time(), local_zone())
    return None


def route(job):
    return (job.get('application_facts') or {}).get('source', job.get('source', 'outbound'))


def assessment(job, key):
    direct = job.get(key)
    if isinstance(direct, dict):
        return direct
    prefix = 'analytics ' + key + ': '
    for item in reversed(job.get('log') or []):
        if str(item.get('text', '')).startswith(prefix):
            try:
                value = json.loads(item['text'][len(prefix):])
                valid = value.get('state') in ('pass', 'fail', 'unclear') if key == 'job_fit' or key.endswith('_review') else value.get('kind') in ('stated', 'observed', 'unknown')
                if valid and isinstance(value.get('reason'), str):
                    return value
            except (ValueError, TypeError, AttributeError):
                pass
    return None


def wilson(k, n):
    if not n:
        return None, None
    z = 1.959963984540054
    p, z2 = k / n, z * z
    middle = (p + z2 / (2 * n)) / (1 + z2 / n)
    radius = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return (0.0 if k == 0 else max(0.0, 100 * (middle - radius)),
            100.0 if k == n else min(100.0, 100 * (middle + radius)))


def beta_cdf(x, a, b):
    """Regularized incomplete beta via a convergent continued fraction; stdlib only."""
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1 - beta_cdf(1 - x, b, a)
    qab, qap, qam = a + b, a + 1, a - 1
    tiny = 1e-300
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 401):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d; d = d if abs(d) > tiny else tiny
            c = 1 + aa / c; c = c if abs(c) > tiny else tiny
            d = 1 / d
            delta = d * c; h *= delta
        if abs(delta - 1) < 1e-13: break
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    return max(0.0, min(1.0, front * h / a))


def beta_quantile(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(55):
        middle = (lo + hi) / 2
        if beta_cdf(middle, a, b) < q: lo = middle
        else: hi = middle
    return (lo + hi) / 2


@functools.lru_cache(maxsize=8192)
def exact_bounds(k, n, alpha=.05):
    if not n: return None, None
    return (0.0 if k == 0 else 100 * beta_quantile(alpha / 2, k, n - k + 1),
            100.0 if k == n else 100 * beta_quantile(1 - alpha / 2, k + 1, n - k))


@functools.lru_cache(maxsize=8192)
def rate_state(k, n, target):
    low, high = wilson(k, n)
    return 'undecided' if not n else 'pass' if low + 1e-9 >= target else 'fail' if high + 1e-9 < target else 'undecided'


@functools.lru_cache(maxsize=8192)
def cases_needed(k, n, target):
    """More cases at the current observed rate; no finite estimate at the target."""
    if not n or k / n == target / 100:
        return None
    if rate_state(k, n, target) != 'undecided':
        return 0
    p = k / n
    lo, hi = n, max(n + 1, 2 * n)
    while hi <= 1000000 and rate_state(round(p * hi), hi, target) == 'undecided':
        lo, hi = hi, hi * 2
    if hi > 1000000: return None
    while hi - lo > 1:
        middle = (lo + hi) // 2
        if rate_state(round(p * middle), middle, target) == 'undecided': lo = middle
        else: hi = middle
    return hi - n


def span(today, days, back=0):
    end = today - dt.timedelta(days=1 + back)
    return end - dt.timedelta(days=days - 1), end


def inside(value, bounds):
    stamp = timestamp(value)
    value = stamp.astimezone(local_zone()).date() if stamp else day(value)
    return value is not None and bounds[0] <= value <= bounds[1]


def period(bounds):
    return {'start': bounds[0].isoformat(), 'end': bounds[1].isoformat()}


def ids(rows):
    return sorted({str(job['id']) for job in rows})


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def rounded(value):
    return round(value, 4) if number(value) else value


def metric(key, k=None, n=None, value=None, target=None, state='undecided', evidence=None, reason=None):
    order = list(LABELS).index(key) + 1
    layer = 'result' if order < 3 else 'funnel' if order < 10 else 'lever' if order < 16 else 'insight' if order in (20, 21) else 'coaching'
    unit = 'usd' if order < 3 else 'min' if key == 'first_reply' else 'count' if key in ('weekly_volume', 'goal_done') else 'text' if order >= 16 else '%'
    return {'label': LABELS[key], 'layer': layer, 'strand': 'outbound' if order in (3, 4, 5, 6, 7) else 'inbound' if order in (8, 9) else None,
            'order': order, 'unit': unit, 'value': rounded(value), 'k': k, 'n': n, 'low': None, 'high': None,
            'target': target, 'target_text': f'{target:g} %' if number(target) and unit == '%' else str(target) if target is not None else 'one fix' if order in (16, 17, 18, 19) else 'up vs own four weeks' if order < 3 else None,
            'direction': 'down' if key == 'first_reply' else 'up', 'state': state, 'reason': reason,
            'baseline': None, 'delta': None, 'history': [], 'evidence': evidence or []}


def rate_metric(key, rows, good, target):
    k, n = sum(bool(good(job)) for job in rows), len(rows)
    result = metric(key, k, n, 100 * k / n if n else None, target, rate_state(k, n, target), ids(rows))
    result['exact_low'], result['exact_high'] = map(rounded, exact_bounds(k, n))
    result['low'], result['high'] = map(rounded, wilson(k, n))
    result['interval_method'] = 'Wilson 95%; performance interval'
    result['performance_low'], result['performance_high'] = map(rounded, wilson(k, n))
    result['performance_interval_method'] = 'Wilson 95%; performance verdict, no minimum-n gate'
    result['cases_needed_assumption'] = 'Stationary observed rate with additional cases; not a promise.'
    result['cases_needed'] = cases_needed(k, n, target) if result['state'] == 'undecided' else 0
    if result['state'] == 'undecided':
        result['reason'] = ('No mature cases; a current rate cannot be estimated.' if not n else 'At the target rate, more cases at this rate cannot decide the result.' if k / n == target / 100 else 'Too few cases to decide against the target.')
    return result


PUBLIC_OUTCOME_LABELS = {'reply_rate': 'Applied → reply within 7 days',
    'reply_to_call': 'Reply → booked call, held call, offer or contract within 14 days',
    'invite_to_call': 'Invite → booked call, held call, offer or contract within 14 days',
    'call_to_won': 'Held call → won within 28 days', 'booked_to_held': 'Booked call → held within 2 days', 'proposal_to_won': 'Proposal → won within 21 days'}


HORIZONS = {'reply_rate': 7, 'reply_to_call': 14, 'booked_to_held': 2,
            'held_to_proposal': 7, 'proposal_to_won': 21, 'invite_to_call': 14,
            'offer_to_contract': 21, 'call_to_won': 28}


def cohort(jobs, name, maturity, today, bounds, strand=None):
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    # Complete 28-day entry population, with equal follow-up for every member.
    entry_bounds = tuple(value - dt.timedelta(days=maturity) for value in bounds) if maturity else bounds
    def eligible(job):
        eligible_route = strand is None or (route(job) in ('invite', 'direct_offer') if strand == 'inbound' else route(job) == strand)
        entry = event(job, name)
        return (not job.get('imported') and eligible_route and entry and inside(entry, entry_bounds)
                and entry + dt.timedelta(days=maturity) <= cutoff)
    return [job for job in jobs if eligible(job)]


def has_after(job, outcome, entry, cutoff):
    result = event(job, outcome)
    return bool(result and entry <= result <= cutoff)


def call_end(job):
    ended = timestamp(job.get('call_ended_at'))
    start, duration = event(job, 'call_held'), job.get('call_duration_s')
    return ended or (start + dt.timedelta(seconds=duration) if start and number(duration) and duration >= 0 else None)


def proposal_eligible(job):
    outcome = str(job.get('call_outcome', '')).casefold().replace('-', '_')
    if job.get('proposal_required') is False or outcome in ('disqualified', 'clean_disqualification', 'not_a_fit'):
        return False
    fit = assessment(job, 'job_fit') or {}
    if fit.get('state') == 'fail': return False
    if not event(job, 'proposal_sent') and (event(job, 'offer') or event(job, 'won')):
        return False
    return True


def qualified(job, reviewed_unclear=True):
    fit = assessment(job, 'job_fit') or {}
    return fit.get('state') == 'pass' or (reviewed_unclear and fit.get('state') == 'unclear' and bool(str(fit.get('reason', '')).strip()))


def call_to_won(jobs, today, strand='outbound'):
    rows = cohort(jobs, 'call_held', 28, today, span(today, 28), strand)
    result = rate_metric('proposal_to_won', rows, lambda job: has_after(job, 'won', event(job, 'call_held'), event(job, 'call_held') + dt.timedelta(days=28)), 30)
    result.update(label='Held call → won within 28 days', outcome_label=PUBLIC_OUTCOME_LABELS['call_to_won'], progression=None, strand=strand, horizon_days=28,
                  entry_period=period(tuple(value - dt.timedelta(days=28) for value in span(today, 28))),
                  disqualified_n=sum(not proposal_eligible(job) and not event(job, 'won') for job in rows),
                  bypass_n=sum(bool(event(job, 'won')) and not event(job, 'proposal_sent') for job in rows))
    return result


def contract_value(job):
    terms = job.get('won_value') or {}
    if terms.get('type') == 'fixed' and number(terms.get('amount')):
        return terms['amount']
    if terms.get('type') == 'hourly' and number(terms.get('rate', terms.get('amount'))) and number(terms.get('weekly_hours')):
        return terms.get('rate', terms.get('amount')) * terms['weekly_hours'] * 4
    return None


def latest_earnings(rows):
    latest = {}
    for row in rows:
        latest[(str(row.get('contract_id')), row.get('week_start'))] = row
    return list(latest.values())


def financial(jobs, earnings, bounds, full_week=False):
    wins = [job for job in jobs if inside((job.get('won_value') or {}).get('start_date') or event(job, 'won'), bounds)]
    valued = [job for job in wins if contract_value(job) is not None and (job.get('won_value') or {}).get('currency')]
    # §13: choose the member's most frequent contract currency, never exchange money.
    frequencies = {}
    for job in jobs:
        code = (job.get('won_value') or {}).get('currency')
        if code and contract_value(job) is not None:
            frequencies[code] = frequencies.get(code, 0) + 1
    currency = min(frequencies, key=lambda code: (-frequencies[code], code)) if frequencies else 'USD'
    totals = {}
    for job in valued:
        code = job['won_value']['currency']
        item = totals.setdefault(code, {'currency': code, 'value': 0, 'wins': 0, 'fixed_value': 0, 'hourly_contract_value': 0})
        amount = contract_value(job)
        item['value'] += amount
        item['wins'] += 1
        item['fixed_value' if job['won_value']['type'] == 'fixed' else 'hourly_contract_value'] += amount
    selected = totals.get(currency, {'value': 0, 'fixed_value': 0, 'hourly_contract_value': 0})
    unknown = len(wins) - len(valued)
    bills = [row for row in latest_earnings(earnings) if inside(row.get('week_start'), bounds) and number(row.get('billed'))]
    bill_totals = {}
    for row in bills:
        code = row.get('currency')
        if code: bill_totals[code] = bill_totals.get(code, 0) + row['billed']
    bill_currency = currency if currency in bill_totals else next(iter(bill_totals), currency) if len(bill_totals) <= 1 else None
    return {'value': selected['value'] if valued or not wins else None,
            'known_subtotal': selected['value'], 'fixed_value': selected['fixed_value'],
            'hourly_contract_value': selected['hourly_contract_value'], 'hourly_billed': bill_totals.get(bill_currency, 0) if bill_currency else None,
            'billed_currency': bill_currency, 'billed_totals': [{'currency': code, 'value': value} for code, value in sorted(bill_totals.items())],
            'currency': currency, 'totals': list(sorted(totals.values(), key=lambda row: row['currency'])),
            'other_totals': [row for code, row in sorted(totals.items()) if code != currency],
            'evidence': ids(wins), 'wins': len(wins), 'valued_wins': len(valued),
            'value_unknown_n': unknown, 'hourly_wins_unknown': sum((job.get('won_value') or {}).get('type') == 'hourly' and contract_value(job) is None for job in wins),
            'hourly_note': f'+{unknown} wins, value unknown' if unknown else None}


def readable_lines(name):
    path = data_path(name)
    try:
        if not path.is_file(): return False
        return all(isinstance(json.loads(line), dict) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    except (OSError, UnicodeError, ValueError): return False


def source_coverage(jobs, today, now=None):
    sync_path = data_path('sync.json')
    try: sync = json.loads(sync_path.read_text(encoding='utf-8')) if sync_path.is_file() else {}
    except (OSError, UnicodeError, ValueError): sync = {}
    synced = timestamp(sync.get('synced_at'))
    cutoff = run_timestamp(now=now)
    if _RECONSTRUCTING.get() and synced and synced > cutoff: synced = cutoff
    upwork = 'missing' if sync.get('status') == 'error' or not synced or synced > cutoff else 'stale' if cutoff - synced >= dt.timedelta(hours=24) else 'ok'
    jobdir = pipeline.jobs_dir()
    recorder = bool(sections().get('Call recorder') or sections().get('Recorder') or any(event(job, 'call_held') for job in jobs) or any(jobdir.glob('*/call.md')))
    loom = bool(any(jobdir.glob('*/loom.md')) or any(job.get('loom_hook') for job in jobs))
    loom_used = any(job.get('loom_url') for job in jobs) or any(re.search(r'https?://(?:www\.)?(?:loom\.com|youtu\.be|youtube\.com)/', (read_source(path) or '')) for path in jobdir.glob('*/application.sent.md'))
    tracking = bool(os.environ.get('BLOB_READ_WRITE_TOKEN') or any(job.get('pitch_url') or event(job, 'opened') or event(job, 'pitch_opened') for job in jobs))
    rows = []
    for source, state, affects, fix in (
        ('upwork', upwork, list(LABELS)[:15], 'Run /brief to sync Upwork.'),
        ('recorder', 'ok' if recorder else 'missing', ['call_review'], 'Add a labelled call transcript or confirm held calls.'),
        ('tracking', 'ok' if tracking else 'missing', [], 'Check the tracking link and its saved click source.'),
        ('loom', 'ok' if loom else 'missing', ['application_review'] if loom_used else [], 'Add the Loom transcript when the application uses Loom.'),
        ('earnings', 'ok' if readable_lines('earnings.jsonl') else 'missing', [], 'Read the earnings summary in /brief.'),
        ('connects', 'ok' if readable_lines('connects.jsonl') else 'missing', ['value_per_100_connects'], 'Read the Connects history in /brief.')):
        rows.append({'source': source, 'state': state, 'affects': affects, 'fix': fix if state != 'ok' else ''})
    return rows, sync.get('synced_at')


def coverage_sources(value):
    """Accept the original source list at the input boundary; snapshots use one object."""
    return value.get('sources', []) if isinstance(value, dict) else value


def read_source(path):
    try:
        return path.read_text(encoding='utf-8') if path.is_file() else None
    except (OSError, UnicodeError):
        return None


def coverage_fields(sources, jobs, today):
    missing = [{'source': row['source'], 'blocks': row['affects'], 'how_to_supply': row['fix']}
               for row in sources if row['state'] == 'missing']
    def absent(source, blocks, supply):
        entry = {'source': source, 'blocks': blocks, 'how_to_supply': supply}
        if entry not in missing: missing.append(entry)
    for job in jobs:
        jid = str(job['id']); folder = pipeline.jobs_dir() / jid
        if event(job, 'applied') and not job.get('imported'):
            if not read_source(folder / 'application.sent.md') or job.get('application_sent_verified') is not True:
                absent('sent copy:' + jid, ['application_review'], 'Open the submitted Upwork application and save its sent copy.')
            if job.get('loom_url') and not read_source(folder / 'loom.md'):
                absent('Loom:' + jid, ['application_review'], 'Paste the Loom transcript for ' + jid + '.')
        if event(job, 'call_held'):
            text = read_source(folder / 'call.md')
            stats = call_stats.analyze(text) if text else {}
            if not text or not stats.get('transcript_complete') or not stats.get('member_attributed'):
                absent('call transcript:' + jid, ['call_review'], 'Paste a transcript or run /call-review ' + jid + '.')
        if event(job, 'won') and contract_value(job) is None:
            absent('contract terms:' + jid, ['won_value', 'value_per_100_connects', 'forecast'], 'Reconnect Upwork and read the agreed contract amount or hourly hours for ' + jid + '.')
    return {'sources': copy.deepcopy(sources), 'missing': missing}


CONVERSATION_POINTS = ('answered_question', 'qualifying_question', 'call_times')
CALL_POINT_LABELS = {1: 'Opening and agenda', 2: 'Current state', 3: 'Problem and cost',
    4: 'Goal and scope', 5: 'Budget before price', 6: 'Decision maker and timeline',
    7: 'Why you', 8: 'Objections', 9: 'Next step on Upwork'}
CALL_POINT_DEFINITIONS = {7: "Proof meets the client's stated concern and distinguishes the member from other applicants.",
    9: 'Who sends the proposal or client offer, fixed with milestones or hourly, and by when, with the client\'s yes. Posted budget or scope counts as covered.'}


def conversation_reviews(jobs, today, quiet_only=True):
    """Read the coach's saved judgement; deterministic code never invents a thread read."""
    threads = []
    for job in jobs:
        if job.get('imported') or not event(job, 'replied') or day(event(job, 'replied')) > today or quiet_only and day(event(job, 'replied')) == today:
            continue
        if quiet_only and any(event(job, key) and day(event(job, key)) < today for key in ('call_booked', 'call_held', 'offer', 'won')):
            continue
        path = pipeline.jobs_dir() / str(job['id']) / 'thread.json'
        text = read_source(path)
        try: raw = json.loads(text) if text else {}
        except (ValueError, TypeError): raw = {}
        rooms = list((raw.get('rooms') or {}).values()) or [raw]
        messages = [message for room in rooms for message in room.get('messages', []) if isinstance(message, dict)]
        complete = bool(rooms) and all(room.get('messages_complete') is True for room in rooms) and all(ref.get('messages_complete') is True for ref in (job.get('thread_refs') or {}).values())
        if _RECONSTRUCTING.get():
            complete = complete and all(timestamp(room.get('fetched_at')) and day(room['fetched_at']) <= today for room in rooms)
        saved = assessment(job, 'conversation_review') or {}
        utterances = '\n'.join(str(row.get('text') or '') for row in messages)
        points = {}
        for name in CONVERSATION_POINTS:
            point = saved.get('points', {}).get(name, {})
            supported = bool(messages and complete and point.get('state') in ('met', 'partly', 'missing', 'not_needed') and
                             (point.get('state') in ('missing', 'not_needed') and str(point.get('reason') or '').strip() or
                              str(point.get('quote') or '').strip() and point['quote'] in utterances))
            points[name] = {key: point.get(key) for key in ('state', 'quote', 'reason')} if supported else {
                'state': 'missing', 'quote': None, 'reason': 'Messages or a quoted coach review are unknown. Read the complete Upwork thread.'}
        read = bool(complete and messages and saved.get('read') is True and all(points[name]['reason'] != 'Messages or a quoted coach review are unknown. Read the complete Upwork thread.' for name in CONVERSATION_POINTS))
        last = max(messages, key=lambda row: timestamp(row.get('at')) or dt.datetime.min.replace(tzinfo=dt.timezone.utc), default={}).get('from', 'unknown')
        last = 'me' if last in ('me', 'member') else 'client' if last == 'client' else 'unknown'
        threads.append({'lead_id': str(job['id']), 'points': points, 'last_writer': last, 'read': read,
                        'free_read': saved.get('free_read') if read else None,
                        'next_message': saved.get('next_message') if read else None})
    checked = [row for row in threads if row['read']]
    counts = {name: sum(row['points'][name]['state'] == 'missing' for row in checked) for name in CONVERSATION_POINTS}
    most = max(counts, key=counts.get) if counts else None
    descriptions = {'answered_question': 'an answer to the client question',
                    'qualifying_question': 'one qualifying question', 'call_times': 'a useful call proposal'}
    pattern = f"In {counts[most]} of {len(checked)} quiet threads, {descriptions[most]} was missing." if most and counts[most] >= 2 else None
    return {'threads': threads, 'pattern': pattern}


def funnel_score(snapshot, history=None):
    """Item 23: bounded weekly performance, with opportunity-free parts rescaled away."""
    kpis = snapshot.get('kpis', {}); history = history or []
    baseline_only = any(kpis.get(key, {}).get('baseline_phase', False) for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won'))
    dropped, habit_values, result_values = [], [], []
    for key in LEVERS:
        row = kpis.get(key, {})
        if row.get('state') == 'missing' or row.get('unknown_n', 0) or not number(row.get('value')):
            dropped.append({'part': key, 'reason': 'unknown source' if row.get('state') == 'missing' or row.get('unknown_n', 0) else 'No eligible cases yet'})
            continue
        # Applications use the commitment as their denominator; zero applications can miss a positive commitment.
        opportunities = row.get('n') if key != 'weekly_volume' else row.get('target')
        if not opportunities or not number(row.get('target')) or row['target'] <= 0:
            dropped.append({'part': key, 'reason': 'No eligible cases yet'}); continue
        value, target = row['value'], row['target']
        ratio = (1 if value <= target else target / value) if key == 'first_reply' else value / target
        habit_values.append(12 * min(max(ratio, 0), 1))
    for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won'):
        row = kpis.get(key, {})
        if baseline_only:
            dropped.append({'part': key, 'reason': 'Baseline not set'}); continue
        if row.get('state') == 'missing' or not row.get('weekly_opportunities', row.get('n')):
            dropped.append({'part': key, 'reason': 'unknown source' if row.get('state') == 'missing' else 'No eligible cases yet'}); continue
        # The retained level is the ladder milestone, never an undecided next rung.
        result_values.append(10 * min(max(row.get('rung_reached', 0), 0), 3) / 3)
    capacity = 12 * len(habit_values) + 10 * len(result_values)
    scale = 100 / capacity if capacity else None
    parts = {'habits': rounded(sum(habit_values) * scale) if scale else None,
             'results': rounded(sum(result_values) * scale) if scale and result_values else None}
    latest = max((row for row in history if row.get('week', '') < snapshot.get('week', '')), key=lambda row: row['week'], default={})
    previous = latest.get('funnel_score', {}).get('score')
    return {'score': round((sum(habit_values) + sum(result_values)) * scale) if scale else None,
            'previous': previous, 'parts': parts, 'dropped': dropped, 'baseline_only': baseline_only}


SCORECARD_NAMES = {'job_fit': 'Jobs that fit lane and rate', 'weekly_volume': 'Qualified applications',
    'speed_10min': 'Applied within 10 min', 'reply_rate': 'Reply rate', 'first_reply': 'First reply time',
    'follow_ups_on_time': 'Follow-ups on their day', 'reply_to_call': 'Call rate', 'booked_to_held': 'Show-up rate',
    'proposal_on_time': 'Proposal within 30 min of call end', 'proposal_to_won': 'Win rate',
    'invite_to_call': 'Invite to call rate', 'offer_to_contract': 'Offer to contract rate',
    'value_per_100_connects': 'Won value per 100 Connects'}
SCORECARD_STAGE = {'reply_rate': 'Applied to reply', 'reply_to_call': 'Reply to booked call',
    'booked_to_held': 'Booked call to held call', 'proposal_to_won': 'Proposal to won'}


def scorecard_action_ids(key, row, jobs, today, now):
    allowed = set(row.get('evidence', []))
    if key == 'first_reply':
        return sorted({str(job['id']) for job, minutes, unanswered in response_cases(jobs, span(today, 28), timestamp(now)) if str(job['id']) in allowed and (unanswered or minutes > row['target'])})
    if key == 'follow_ups_on_time':
        missed = set()
        for job in jobs:
            if str(job['id']) not in allowed: continue
            for item in job.get('follow_up_history') or []:
                if item.get('lane') == 'silent' and inside(item.get('due_on'), span(today, 28)) and not (item.get('action') == 'sent' and day(item.get('on') or item.get('at')) == day(item['due_on'])):
                    cancelled = timestamp(item.get('cancelled_at'))
                    if not cancelled or day(cancelled) >= day(item['due_on']): missed.add(str(job['id']))
            plan = job.get('follow_up_plan') or {}
            due = plan.get('due_on') or job.get('next_follow_up')
            if plan.get('lane') == 'silent' and inside(due, span(today, 28)) and not any(item.get('action') == 'sent' and day(item.get('on') or item.get('at')) == day(due) for item in job.get('follow_up_history') or []): missed.add(str(job['id']))
        return sorted(missed)
    if key == 'speed_10min': return sorted(str(job['id']) for job in jobs if str(job['id']) in allowed and (job.get('application_facts') or {}).get('posted_age_band') != '<10m')
    outcomes = {'reply_rate': ('replied',), 'reply_to_call': ('call_booked', 'call_held', 'offer', 'won'), 'booked_to_held': ('call_held',), 'proposal_to_won': ('won',), 'proposal_on_time': ('proposal_sent',)}.get(key, ())
    return sorted(str(job['id']) for job in jobs if str(job['id']) in allowed and not any(event(job, outcome) for outcome in outcomes))


def scorecard_fields(snapshot, jobs, history, today):
    """One last-28-days scorecard; the weekly habit KPIs remain the score's inputs."""
    now = snapshot['generated_at']; current, _ = calculate(jobs, today, now=now, activity_bounds=span(today, 28))
    historic_token = _RECONSTRUCTING.set(True)
    try:
        previous, _ = calculate(jobs, today - dt.timedelta(days=28), now=dt.datetime.combine(today - dt.timedelta(days=28), dt.time(), local_zone()), activity_bounds=span(today - dt.timedelta(days=28), 28))
    finally:
        _RECONSTRUCTING.reset(historic_token)
    # Weekly volume is the four-week commitment, not one week's quota.
    for metrics in (current, previous):
        row = metrics['weekly_volume']; row.update(n=int(bars()['weekly_volume'] * 4), target=bars()['weekly_volume'], value=row['k'] / 4)
    groups = {'top': ('job_fit', 'weekly_volume', 'speed_10min', 'reply_rate'),
        'middle': ('first_reply', 'follow_ups_on_time', 'reply_to_call', 'booked_to_held', 'invite_to_call'),
        'bottom': ('proposal_on_time', 'proposal_to_won', 'offer_to_contract', 'value_per_100_connects')}
    focus = snapshot.get('verdict', {}).get('kpi'); rows = []
    entry_names = {'reply_rate': 'applied', 'reply_to_call': 'replied', 'booked_to_held': 'call_booked', 'proposal_to_won': 'proposal_sent', 'invite_to_call': 'invited', 'offer_to_contract': 'offer'}
    for group, keys in groups.items():
        for key in keys:
            row = current[key]; prior = previous[key]; frozen = snapshot['kpis'][key]
            if key in FUNNEL:
                for field in ('target', 'rungs', 'rung_reached', 'baseline_phase', 'state', 'reason'):
                    row[field] = frozen.get(field)
            if frozen['state'] == 'missing': row.update(state='missing', value=None, reason=frozen.get('reason'))
            if row.get('unknown_n', 0): row.update(state='missing', value=None, reason='Some source observations are unknown. Supply the missing timestamps or call end evidence.')
            pending = [job for job in jobs if key in entry_names and not job.get('imported') and route(job) == ('invite' if key == 'invite_to_call' else 'inbound' if key == 'offer_to_contract' else 'outbound') and inside(event(job, entry_names[key]), span(today, 28)) and event(job, entry_names[key]) + dt.timedelta(days=HORIZONS[key]) > timestamp(now)]
            until = max((event(job, entry_names[key]) + dt.timedelta(days=HORIZONS[key]) for job in pending), default=None)
            previous_value = prior.get('value') if prior.get('state') != 'missing' and not snapshot['kpis']['reply_rate'].get('baseline_phase', True) else None
            comparison = 'Previous four-week comparison unavailable' if previous_value is None else 'unchanged' if row.get('value') == previous_value else 'was ' + (f'{previous_value:g}%' if row['unit'] == '%' else f'{previous_value:g} min' if row['unit'] == 'min' else f'{previous_value:g}')
            split = []
            if key == 'proposal_on_time':
                split = [dict(label='Held calls to proposal', k=current['held_to_proposal']['k'], n=current['held_to_proposal']['n'], evidence=current['held_to_proposal']['evidence'])]
            market = None
            if key == 'reply_rate': market = {'value': '5.1% agency reply rate; different population', 'source': 'GigRadar Q2 2026, 30 July 2026: https://gigradar.io/upwork/reports/2026/q2/all-industries'}
            if key == 'proposal_to_won': market = {'value': '34% sales proposal close rate; not Upwork', 'source': 'Proposify State of Proposals 2026: https://www.proposify.com/state-of-proposals-2026'}
            series = [old.get('presentation', {}).get('scorecard', []) for old in sorted(history, key=lambda item: item['week'])[-7:]]
            points = [next((item.get('value') for item in items if item.get('key') == key), None) for items in series] + [row.get('value')]
            points = [None] * (8 - len(points)) + points
            rows.append({'key': key, 'group': group, 'name': SCORECARD_NAMES[key], 'stage_label': SCORECARD_STAGE.get(key),
                'period_label': 'Last 28 days', 'counting': ({'weekly_volume': 'Qualified applications in the last 28 days, divided by four weekly commitments.', 'job_fit': 'All sent outbound applications in the last 28 days, with a saved lane and rate fit review.', 'speed_10min': 'Qualified applications in the last 28 days with frozen posting age; unknown ages remain unknown.', 'first_reply': 'Client messages received in the last 28 days; unanswered messages count at their working-hours age.', 'follow_ups_on_time': 'Distinct silent-lane obligations due in the last 28 days; a sent follow-up counts on its due business day.', 'proposal_on_time': 'All fitting held calls in the last 28 days; sent within 30 min of call end. Clean disqualifications and offer or contract bypasses are excluded.', 'value_per_100_connects': 'Known new contract value divided by net Connects spent in the last 28 days, multiplied by 100. Zero spend is not measurable.'}.get(key) or f'Finished outbound cases with a fixed {HORIZONS.get(key, 0)}-day outcome horizon; the full 28-day mature entry cohort includes unsuccessful cases.'), 'period': copy.deepcopy(snapshot['window']), 'value': row.get('value'),
                'finished': {'k': row.get('k'), 'n': row.get('n')}, 'pending': {'n': len(pending), 'until': until.date().isoformat() if until else None},
                'uncertainty': {'low': row.get('low'), 'high': row.get('high')},
                'change': {'previous_value': previous_value, 'comparison_label': 'Previous 28 days', 'text': comparison},
                'series': {'label': 'Last eight weekly checks', 'unit': row['unit'], 'points': points},
                'target': {'kind': 'ladder' if key in FUNNEL else 'habit', 'value': row.get('target'), 'level': frozen.get('rung_reached'), 'thresholds': frozen.get('rungs', [])},
                'next_action': {'text': snapshot.get('verdict', {}).get('next_action') or ACTIONS.get(key, ''), 'lead_filter': {'kpi': key, 'lead_ids': scorecard_action_ids(key, row, jobs, today, now)}} if key == focus else None,
                'split': split, 'focus': {'reason': snapshot.get('verdict', {}).get('reason') or snapshot.get('verdict', {}).get('sentence')} if key == focus else None,
                'content_link': {'view': 'conversations', 'text': 'Why these replies stalled → Conversations'} if key == 'reply_to_call' else None,
                'market': market, 'state': row['state'], 'evidence': row.get('evidence', []), 'insight': frozen.get('insight') or row.get('reason')})
    return rows


def working_elapsed(client, response):
    if not client or not response or response < client: return None
    config = sections().get('Working hours', '09:00-18:00 Mon-Fri')
    match = re.search(r'(\d{2}:\d{2})\s*[-–]\s*(\d{2}:\d{2})', config)
    start, end = (dt.time.fromisoformat(value) for value in match.groups()) if match else (dt.time(9), dt.time(18))
    weekdays = range(7) if re.search(r'Mon[-–]Sun|every day|daily', config, re.I) else range(5)
    client, response = client.astimezone(local_zone()), response.astimezone(local_zone())
    if not (client.weekday() in weekdays and start <= client.time() < end): return None
    elapsed, current = 0, client.date()
    while current <= response.date():
        if current.weekday() in weekdays:
            opening, closing = dt.datetime.combine(current, start, local_zone()), dt.datetime.combine(current, end, local_zone())
            elapsed += max(0, (min(response, closing) - max(client, opening)).total_seconds())
        current += dt.timedelta(days=1)
    return elapsed / 60


def working_reply(job):
    reply, seconds = timestamp(job.get('first_reply_at')), job.get('first_reply_s')
    return working_elapsed(reply - dt.timedelta(seconds=seconds), reply) if reply and number(seconds) and seconds >= 0 else None


def response_cases(jobs, bounds, now):
    result = []
    for job in jobs:
        if job.get('imported'): continue
        rooms = job.get('room_reply_metrics')
        observations = list(rooms.values()) if isinstance(rooms, dict) and rooms else [job]
        for item in observations:
            reply = timestamp(item.get('first_reply_at'))
            seconds = item.get('first_reply_s')
            client = timestamp(item.get('first_client_at') or item.get('first_client_message_at'))
            if not client and reply and number(seconds): client = reply - dt.timedelta(seconds=seconds)
            if not client or not inside(client, bounds): continue
            if reply and reply > now: reply = None
            elapsed = working_elapsed(client, reply or now)
            if elapsed is not None:
                result.append((job, elapsed, reply is None))
    return result


def quantile_bounds(values, q, alpha=.05):
    """Exact distribution-free order-statistic interval for a population quantile."""
    n = len(values)
    if not n: return None, None
    values = sorted(values)
    masses = [math.comb(n, j) * q ** j * (1 - q) ** (n - j) for j in range(n + 1)]
    lower_rank, upper_rank = 0, n + 1
    for rank in range(1, n + 1):
        if sum(masses[:rank]) <= alpha / 2: lower_rank = rank
        if sum(masses[rank:]) <= alpha / 2:
            upper_rank = rank; break
    return (values[lower_rank - 1] if lower_rank else 0.0,
            values[upper_rank - 1] if upper_rank <= n else None)


def downstream_value(jobs, key, today, bounds):
    """Conditional conversion AFTER the failing stage; never double-count its gap."""
    wins = [job for job in jobs if event(job, 'won') and event(job, 'won') < dt.datetime.combine(today, dt.time(), local_zone())]
    amounts = [contract_value(job) for job in wins]
    currencies = {(job.get('won_value') or {}).get('currency') for job in wins}
    average = statistics.mean(amounts) if amounts and all(number(value) for value in amounts) and len(currencies) == 1 and None not in currencies else None
    if key in ('proposal_to_won', 'offer_to_contract'): return 1.0, average
    exit_names, horizon, strand = {
        'reply_rate': (('replied',), 28, 'outbound'),
        'reply_to_call': (('call_booked', 'offer', 'won'), 28, 'outbound'),
        'booked_to_held': (('call_held',), 21, 'outbound'),
        'held_to_proposal': (('proposal_sent',), 21, 'outbound'),
        'invite_to_call': (('call_booked', 'offer', 'won'), 28, 'invite')
    }[key]
    proxies = []
    for job in jobs:
        exits = [event(job, name) for name in exit_names if event(job, name)]
        if exits: proxies.append(dict(job, downstream_exit_at=min(exits).isoformat()))
    exits = cohort(proxies, 'downstream_exit', horizon, today, bounds, strand)
    converted = sum(has_after(job, 'won', event(job, 'downstream_exit'), event(job, 'downstream_exit') + dt.timedelta(days=horizon)) for job in exits)
    return converted / len(exits) if exits else None, average


@member_clock
def calculate(jobs, today, since=None, now=None, cohort_days=28, activity_bounds=None):
    limits, bounds, activity = bars(), span(today, cohort_days), activity_bounds or span(today, 7)
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    kpis = {}
    specs = [('reply_rate', 'applied', 7, 'outbound', ('replied',)),
             ('reply_to_call', 'replied', 14, 'outbound', ('call_booked', 'call_held', 'offer', 'won')),
             ('booked_to_held', 'call_booked', 2, 'outbound', ('call_held',)),
             ('held_to_proposal', 'call_held', 7, 'outbound', ('proposal_sent',)),
             ('proposal_to_won', 'proposal_sent', 21, 'outbound', ('won',)),
             ('invite_to_call', 'invited', 14, 'invite', ('call_booked', 'call_held', 'offer', 'won')),
             ('offer_to_contract', 'offer', 21, 'inbound', ('won',))]
    for key, entry, maturity, strand, outcomes in specs:
        rows = cohort(jobs, entry, maturity, today, bounds, strand)
        if key == 'booked_to_held':
            entry, outcomes = 'attendance_entry', ('attendance_held',)
            rows = []
            for job in jobs:
                session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
                scheduled = timestamp(session.get('scheduled_at') or job.get('call_scheduled_at'))
                if not job.get('imported') and route(job) == 'outbound' and scheduled and scheduled + dt.timedelta(days=2) <= cutoff and not session.get('cancelled') and (since is None or day(scheduled) >= since) and inside(scheduled, tuple(value - dt.timedelta(days=2) for value in bounds)):
                    held_at = timestamp(session.get('held_at')) if session else event(job, 'call_held')
                    rows.append(dict(job, attendance_entry_at=scheduled.isoformat(), attendance_held_at=held_at.isoformat() if held_at else None))
        if since is not None:
            rows = [job for job in rows if day(event(job, entry)) >= since]
        excluded = [job for job in rows if key == 'held_to_proposal' and not proposal_eligible(job)]
        rows = [job for job in rows if job not in excluded]
        def success(job):
            end = event(job, entry) + dt.timedelta(days=maturity)
            return any(has_after(job, outcome, event(job, entry), end) for outcome in outcomes)
        result = rate_metric(key, rows, success, limits[key])
        result.update(outcome_label=PUBLIC_OUTCOME_LABELS.get(key, LABELS[key] + f' within {maturity} days'), progression=None, horizon_days=maturity, entry_period=period(tuple(value - dt.timedelta(days=maturity) for value in bounds)), excluded_n=len(excluded))
        if key in ('reply_to_call', 'invite_to_call'):
            def progressed(job, name):
                return has_after(job, name, event(job, entry), event(job, entry) + dt.timedelta(days=maturity))
            result['progression'] = {'booked_calls': sum(progressed(job, 'call_booked') for job in rows),
                'held_calls': sum(progressed(job, 'call_held') for job in rows),
                'offer_or_contract_without_call': sum(success(job) and not progressed(job, 'call_booked') and not progressed(job, 'call_held') for job in rows)}
        winners = [job for job in rows if has_after(job, 'won', event(job, entry), cutoff)]
        result['bypass'] = {'call': sum(not event(job, 'call_booked') and not event(job, 'call_held') for job in winners),
                            'proposal': sum(not event(job, 'proposal_sent') for job in winners)}
        downstream_rate, avg_value = downstream_value(jobs, key, today, bounds)
        result.update(downstream_to_won=downstream_rate, average_won_value=avg_value)
        result['lost_revenue'] = ((max(0, limits[key] - result['value']) / 100) * len(rows) * downstream_rate * avg_value) if number(avg_value) and number(result['value']) and number(downstream_rate) else None
        result['delta_pp'] = None
        kpis[key] = result
    applied = cohort(jobs, 'applied', 0, today, activity, 'outbound')
    raw_applied = applied
    applied = [job for job in raw_applied if qualified(job)]
    n = len(applied)
    kpis['weekly_volume'] = metric('weekly_volume', n, int(limits['weekly_volume']), n, limits['weekly_volume'], 'pass' if n >= limits['weekly_volume'] else 'fail', ids(applied))
    kpis['weekly_volume'].update(raw_n=len(raw_applied), unqualified_n=len(raw_applied) - n)
    known = [job for job in applied if (job.get('application_facts') or {}).get('posted_age_band') not in (None, 'unknown')]
    kpis['speed_10min'] = rate_metric('speed_10min', known, lambda job: job['application_facts']['posted_age_band'] == '<10m', limits['speed_10min'])
    proposal_known = [job for job in applied if (job.get('application_facts') or {}).get('proposals_band') not in (None, 'unknown')]
    kpis['speed_10min']['proposals_under_5'] = {'k': sum(job['application_facts']['proposals_band'] == '<5' for job in proposal_known), 'n': len(proposal_known)}
    kpis['speed_10min']['unknown_n'] = n - len(known)
    if n and not known:
        kpis['speed_10min'].update(state='missing', reason='No frozen posting age is known for this week’s applications.')
    run_at = run_timestamp(today, now)
    reply_rows = response_cases(jobs, activity, run_at)
    values = sorted(value for _, value, _ in reply_rows)
    open_n = sum(open_case for _, _, open_case in reply_rows)
    median = statistics.median(values) if values else None
    p75 = values[max(0, math.ceil(.75 * len(values)) - 1)] if values else None
    median_low, median_high = quantile_bounds(values, .5)
    p75_low, p75_high = quantile_bounds(values, .75)
    # §13: completed observations decide the lever; pending responses enter at their age.
    passed = bool(values and median <= limits['first_reply'] and p75 <= limits['first_reply_p75'])
    state = ('no opportunities' if not values else 'undecided' if len(values) < 10
             else 'pass' if passed else 'fail')
    kpis['first_reply'] = metric('first_reply', sum(not pending and value <= limits['first_reply'] for _, value, pending in reply_rows),
        len(values), median, limits['first_reply'], state, ids([job for job, _, _ in reply_rows]),
        None if state != 'undecided' else 'Fewer than 10 client messages; unanswered messages count at their current age.')
    kpis['first_reply'].update(p75=p75, p75_target=limits['first_reply_p75'], median_low=median_low,
        median_high=median_high, p75_low=p75_low, p75_high=p75_high, open_n=open_n,
        target_text=f"{limits['first_reply']:g} min / {limits['first_reply_p75']:g} min")
    follow = []
    for job in jobs:
        if job.get('imported'): continue
        obligations = {}
        for item in job.get('follow_up_history') or []:
            due_on = item.get('due_on')
            if item.get('lane') != 'silent' or not inside(due_on, activity): continue
            identity = item.get('obligation_id') or ('legacy', item.get('lane'), due_on)
            prior = obligations.get(identity, {})
            merged = dict(prior, **item)
            merged['due_on'] = prior.get('due_on', due_on)
            if prior.get('action') == 'sent':
                for field in ('action', 'on', 'at'):
                    if field in prior: merged[field] = prior[field]
            obligations[identity] = merged
        plan = job.get('follow_up_plan') or {}
        due_on = plan.get('due_on') or job.get('next_follow_up')
        identity = plan.get('obligation_id') or ('legacy', plan.get('lane'), due_on)
        if plan.get('lane') == 'silent' and inside(due_on, activity) and identity not in obligations:
            obligations[identity] = {'due_on': due_on}
        for item in obligations.values():
            cancelled = timestamp(item.get('cancelled_at'))
            due_start = dt.datetime.combine(day(item['due_on']), dt.time(), local_zone())
            if cancelled and cancelled < due_start and item.get('action') != 'sent': continue
            follow.append((job, item))
    proxies = [{'id': job['id'], 'entry': item} for job, item in follow]
    kpis['follow_ups_on_time'] = rate_metric('follow_ups_on_time', proxies, lambda job: job['entry'].get('action') == 'sent' and day(job['entry'].get('on') or job['entry'].get('at')) == day(job['entry']['due_on']), limits['follow_ups_on_time'])
    held_all = cohort(jobs, 'call_held', 0, today, activity)
    held = [job for job in held_all if proposal_eligible(job) and call_end(job)]
    kpis['proposal_on_time'] = rate_metric('proposal_on_time', held, lambda job: event(job, 'proposal_sent') is not None and 0 <= (event(job, 'proposal_sent') - call_end(job)).total_seconds() <= 1800, limits['proposal_on_time'])
    kpis['proposal_on_time'].update(excluded_n=sum(not proposal_eligible(job) for job in held_all), unknown_n=sum(proposal_eligible(job) and not call_end(job) for job in held_all))
    assessed = [(job, assessment(job, 'job_fit')) for job in raw_applied]
    clear = list(raw_applied)
    kpis['job_fit'] = rate_metric('job_fit', clear, lambda job: (assessment(job, 'job_fit') or {}).get('state') == 'pass', limits['job_fit'])
    kpis['job_fit']['unclear_n'] = sum(not value or value.get('state') == 'unclear' for _, value in assessed)
    kpis['job_fit']['assessed_n'] = sum(bool(value) for _, value in assessed)
    if applied and not clear:
        kpis['job_fit'].update(state='missing', reason='Applications have no clear lane-and-rate fit judgments yet.')
    for key in ('speed_10min', 'follow_ups_on_time', 'proposal_on_time', 'job_fit'):
        row = kpis[key]
        if not row['n'] and row['state'] != 'missing':
            row.update(state='no opportunities', reason='No opportunities in the completed period.', cases_needed=None)
        elif row['state'] != 'missing':
            row.update(state='pass' if row['value'] >= row['target'] else 'fail', reason=None, cases_needed=0)
    speed = kpis['speed_10min']
    speed['eligible_n'] = n
    if speed['unknown_n'] and n:
        lower, upper = 100 * speed['k'] / n, 100 * (speed['k'] + speed['unknown_n']) / n
        speed.update(coverage_low=lower, coverage_high=upper,
                     state='pass' if lower >= speed['target'] else 'fail' if upper < speed['target'] else 'undecided',
                     reason='Unknown posting ages bound complete-population compliance.')
    fit = kpis['job_fit']
    if fit['n']:
        unknown = fit['unclear_n']
        lower, upper = 100 * fit['k'] / fit['n'], 100 * (fit['k'] + unknown) / fit['n']
        fit.update(coverage_low=lower, coverage_high=upper, known_n=fit['n'] - unknown)
        if unknown:
            fit.update(value=None, state='missing' if unknown == fit['n'] else 'pass' if lower >= fit['target'] else 'fail' if upper < fit['target'] else 'undecided',
                       reason='Unknown fit judgments bound compliance; absent evidence is not a failed fit.')
    earnings = [row for row in read_lines('earnings.jsonl') if since is None or (day(row.get('week_start')) and day(row['week_start']) >= since)]
    fixed = financial(jobs, earnings, activity)
    weekly_value = fixed['value']
    kpis['won_value'] = metric('won_value', fixed['wins'], fixed['wins'], weekly_value, limits['won_value'],
                              'missing' if weekly_value is None else 'undecided', fixed['evidence'], fixed['hourly_note'])
    kpis['won_value']['currency'] = fixed['currency']
    total = financial(jobs, [], bounds)
    connects = [row for row in read_lines('connects.jsonl') if number(row.get('amount')) and inside(row.get('at'), bounds)
               and (since is None or day(row.get('at')) >= since)]
    # The period ratio is descriptive, never acquisition ROI. Only refunds offset spend;
    # grants and purchases do not offset application charges.
    debit = sum(-row['amount'] for row in connects if row['amount'] < 0)
    refunds = sum(row['amount'] for row in connects if row['amount'] > 0 and 'refund' in ' '.join(str(row.get(key) or '') for key in ('purpose', 'type', 'description', 'reason')).casefold())
    spend = max(0, debit - refunds)
    kpis['value_per_100_connects'] = metric('value_per_100_connects', total['wins'], spend,
        total['value'] / spend * 100 if spend and total['value'] is not None else None, limits['value_per_100_connects'],
        'undecided' if spend else 'not measurable', total['evidence'], 'Descriptive period ratio; not attributable acquisition ROI.' if spend else 'Zero Connects spend; efficiency is not measurable; not attributable acquisition ROI.')
    kpis['value_per_100_connects']['currency'] = total['currency']
    for key in list(LABELS)[15:]:
        kpis[key] = metric(key, state='undecided', reason='Requires the weekly evidence review.')
    for key in ('segments', 'behaviour'):
        kpis[key].update(value='nothing new', state='undecided', reason='Available in package 4; nothing new this week.')
    lost = [job for job in jobs if job.get('status') == 'lost' and inside(job.get('status_updated_at') or next((item.get('at') for item in reversed(job.get('history') or []) if item.get('status') == 'lost'), None), activity)]
    reasons = {kind: sum((assessment(job, 'lost_reason') or {}).get('kind', 'unknown') == kind for job in lost) for kind in ('stated', 'observed', 'unknown')}
    kpis['lost_reasons'].update(k=len(lost) - reasons['unknown'], n=len(lost), value=reasons, evidence=ids(lost))
    coverage, _ = source_coverage(jobs, today, now)
    for source in coverage:
        if source['state'] == 'ok':
            continue
        for key in source['affects']:
            if source['state'] == 'stale' and kpis[key]['n']:
                continue
            # Optional Loom/tracking absence leaves the whole review explicitly missing.
            kpis[key].update(state='missing', reason=f"{source['source']} source is absent. {source['fix']}", value=None)
    if any(source['source'] == 'upwork' and source['state'] == 'missing' for source in coverage):
        weekly_value = None
    fixed['value'] = weekly_value
    if not data_path('earnings.jsonl').is_file(): fixed['hourly_billed'] = None
    fixed['billed_period'] = period(activity)
    fixed['billed_label'] = 'Billed this week'
    return {key: kpis[key] for key in LABELS}, fixed


def lever_shortfall(row):
    target, value = row.get('target'), row.get('value')
    if not number(value) or not number(target) or target <= 0: return 0
    short = max(0, (value - target) / target) if row['direction'] == 'down' else max(0, (target - value) / target)
    if row['direction'] == 'down' and number(row.get('p75')) and row.get('p75_target', 0) > 0:
        short = max(short, (row['p75'] - row['p75_target']) / row['p75_target'])
    return short


def verdict(kpis):
    failures = [key for key in FUNNEL if kpis[key]['state'] == 'fail']
    unavailable = [key for key in FUNNEL if kpis[key]['state'] in ('undecided', 'missing')]
    # Missing downstream value makes economic comparison unavailable; retain funnel order.
    failure = max(failures, key=lambda key: kpis[key]['lost_revenue']) if failures and all(number(kpis[key].get('lost_revenue')) for key in failures) else next(iter(failures), None)
    if failure:
        feeding = [key for key in FEEDING_LEVERS.get(failure, ()) if kpis[key]['state'] == 'fail']
        key = max(feeding, key=lambda name: lever_shortfall(kpis[name])) if feeding else failure
        mode, state = ('levers', 'levers') if feeding else ('funnel', 'confirmed')
        earlier = [name for name in FUNNEL[:FUNNEL.index(failure)] if name in unavailable]
        sentence = (f"Proposed focus: {kpis[key]['label']}, {kpis[key]['k']} of {kpis[key]['n']}; "
                    f"{kpis[failure]['label']} is below its {kpis[failure]['target']:g} % rung.")
    else:
        levers = [name for name in LEVERS if kpis[name]['state'] == 'fail']
        key = max(levers, key=lambda name: lever_shortfall(kpis[name])) if levers else next((name for name in ('weekly_volume', 'speed_10min') if kpis[name]['state'] != 'missing'), None)
        mode, state = 'levers', 'levers' if unavailable or levers else 'none'
        earlier = []
        sentence = 'No confirmed target gap; remaining funnel stages are undecided or missing.' if unavailable else 'No confirmed target gap this week.'
        if key: sentence += f" Proposed focus: {kpis[key]['label']}."
    if earlier:
        sentence += ' Earlier stages not decidable or missing: ' + ', '.join(kpis[name]['label'] for name in earlier) + '.'
    return {'label': "This week's focus", 'state': state, 'mode': mode, 'kpi': key,
            'stage': kpis[key]['label'] if key else None, 'sentence': sentence,
            'next_action': ACTIONS.get(key, 'Keep the routine and review the next evidence.'), 'undecided_before': earlier,
            'undecided_stages': unavailable, 'economic_basis': 'Observed stage shortfall × cohort size × downstream conversion × average won value; order fallback if incomplete.'}


def pipeline_counts(jobs, today):
    result = {'outbound': [], 'inbound': []}
    for strand in result:
        for stage in ('new', 'applied', 'replied', 'call', 'offer'):
            rows = [job for job in jobs if job.get('status') == stage and (route(job) == 'outbound' if strand == 'outbound' else route(job) in ('invite', 'direct_offer'))]
            movements = [day(job.get('last_activity_at') or job.get('status_updated_at') or job.get('found_at')) for job in rows]
            stages = [day(job.get('status_updated_at') or next((item.get('at') for item in reversed(job.get('history') or []) if item.get('status') == stage), None) or job.get('found_at')) for job in rows]
            ages = [(today - value).days for value in movements if value]
            stage_ages = [(today - value).days for value in stages if value]
            values = [job.get('price_estimate') or (job.get('details') or {}).get('price_estimate') or job.get('bid_amount') or (job.get('details') or {}).get('bid_amount') for job in rows]
            row = {'stage': stage, 'count': len(rows), 'known_value': sum(value for value in values if number(value)),
                   'oldest_days': max(stage_ages, default=None), 'stalled': sum(age >= 7 for age in ages),
                   'proposals_out': sum(bool(event(job, 'proposal_sent')) for job in rows)}
            if stage == 'call':
                booked, held = 0, 0
                for job in rows:
                    session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
                    attended = timestamp(session.get('held_at')) if session else event(job, 'call_held')
                    scheduled = timestamp(session.get('scheduled_at') or job.get('call_scheduled_at'))
                    if attended: held += 1
                    elif not session.get('cancelled') and (scheduled or event(job, 'call_booked')): booked += 1
                row.update(booked=booked, held=held, unknown_call=len(rows) - booked - held)
            result[strand].append(row)
    return result


def goal_id(goal, week):
    text = json.dumps([week, goal['kpi'], goal['start'], goal['change']], ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def latest_goals(today):
    resolved = set()
    iso = today.isocalendar()
    current_week = f'{iso.year}-W{iso.week:02d}'
    for snapshot in read_lines('analytics-history.jsonl'):
        if snapshot.get('week', '') >= current_week: continue
        for review in snapshot.get('goals_review', []):
            if review.get('goal_id') and (review.get('decision') == 'stop' or
                    (review.get('mature', False) and review.get('decision') in ('keep', 'adjust'))):
                resolved.add(review['goal_id'])
    result = []
    for row in read_lines('goals.jsonl'):
        for goal in row.get('goals', []):
            identity = goal_id(goal, row['week'])
            if day(goal.get('review_on')) and day(goal['review_on']) <= today and identity not in resolved:
                result.append(dict(goal, goal_id=identity))
    return result


def difference_bounds(before, after):
    if before.get('unit') == '%' and before.get('n') and after.get('n'):
        low_b, high_b = exact_bounds(before['k'], before['n'], .025)
        low_a, high_a = exact_bounds(after['k'], after['n'], .025)
        return low_a - high_b, high_a - low_b
    if before.get('unit') == 'min':
        if before.get('median_low') is not None and after.get('median_low') is not None:
            return ((after['median_low'] - before['median_high']) if before.get('median_high') is not None else None,
                    (after['median_high'] - before['median_low']) if after.get('median_high') is not None else None)
    return None, None


def goal_reviews(jobs, today, now=None):
    rows = []
    for goal in latest_goals(today):
        start = day(goal.get('start'))
        if not start or goal.get('kpi') not in LABELS: continue
        key = goal['kpi']
        horizon = HORIZONS.get(key, 0)
        before_bounds = (start - dt.timedelta(days=28), start - dt.timedelta(days=1))
        before = calculate(jobs, start + dt.timedelta(days=horizon), now=now,
                           cohort_days=28, activity_bounds=before_bounds)[0][key]
        mature_on = start + dt.timedelta(days=7 + horizon)
        mature = today >= mature_on
        # Every post-start entry gets the same outcome horizon; recent entries stay out.
        after_days = max(1, (today - start).days - horizon)
        after_bounds = (start, max(start, today - dt.timedelta(days=1)))
        after = calculate(jobs, today, since=start, now=now, cohort_days=after_days,
                          activity_bounds=after_bounds)[0][key]
        low, high = difference_bounds(before, after)  # descriptive change interval retained
        effect = 'undecided'
        if mature and before['state'] != 'missing' and after['state'] != 'missing':
            if before.get('unit') == '%' and before.get('n') and after.get('n') and number(before['value']):
                lo, hi = wilson(after['k'], after['n'])
                before_rate = 100 * before['k'] / before['n']
                after_rate = 100 * after['k'] / after['n']
                effect = ('worked' if lo > before_rate else
                          'not' if hi < before_rate or after_rate == before_rate else 'undecided')
            elif key == 'first_reply' and not before.get('open_n') and not after.get('open_n'):
                if number(low) and number(high):
                    effect = 'worked' if high < 0 else 'not' if low > 0 or after['value'] == before['value'] else 'undecided'
        rows.append({'goal_id': goal['goal_id'], 'start': start.isoformat(), 'review_on': goal['review_on'],
            'change': goal['change'], 'kpi': key, 'done_k': 0, 'done_n': 0, 'effect': effect, 'mature': mature,
            'before': before['value'], 'after': after['value'], 'decision': 'adjust', 'before_k': before['k'],
            'before_n': before['n'], 'after_k': after['k'], 'after_n': after['n'], 'state': after['state'],
            'attainment': after['state'], 'difference_low': rounded(low), 'difference_high': rounded(high),
            'matures_on': mature_on.isoformat(), 'before_period': period(before_bounds),
            'after_period': period((start, max(start, today - dt.timedelta(days=1 + horizon)))),
            'effect_note': ('Count outcomes have no specified effect interval; execution is reviewed separately.' if before['unit'] == 'count' else 'Descriptive quantile change; observed change, not causal attribution.' if before['unit'] == 'min' else 'After Wilson interval versus before rate; observed change, not causal attribution.'),
            'execution_state': 'unverified', 'evidence_lead_ids': [], 'done_lead_ids': [], 'outcome_evidence': after['evidence']})
    return rows


def apply_ladders(kpis, history, today, jobs, now=None):
    dates = [event(job, name).astimezone(local_zone()).date() for job in jobs if not job.get('imported')
             for name in ('applied', 'invited', 'offer') if event(job, name)]
    dates += [dt.date.fromisocalendar(int(row['week'][:4]), int(row['week'][6:]), 1) for row in history]
    start = min(dates, default=today)
    start -= dt.timedelta(days=start.weekday())
    phase = today <= start + dt.timedelta(weeks=4)
    first_four = calculate(jobs, start + dt.timedelta(weeks=4), now=now)[0]
    for key in FUNNEL:
        row = kpis[key]
        rungs = list(RUNGS[key])
        rungs[-1] = bars()[key]
        # A top-rung override must not reverse the ladder.
        require(len(rungs) == 1 or rungs[-1] > rungs[-2], f'{key} top rung must exceed its previous rung.')
        previous = [item.get('kpis', {}).get(key, {}) for item in sorted(history, key=lambda item: item['week'])]
        rung_eligible = not phase and row['state'] != 'missing' and row['n'] >= MIN_OUTCOME_CASES
        reached = max([sum(rate_state(row['k'], row['n'], rung) == 'pass' for rung in rungs) if rung_eligible else 0] +
                      [min(len(rungs), item.get('rung_reached', 0)) for item in previous if not item.get('baseline_phase', False)])
        target = rungs[min(reached, len(rungs) - 1)]
        benchmark = row['value'] if phase else first_four[key]['value']
        if reached and not phase:
            benchmark = rungs[reached - 1]
        avg = row.get('average_won_value')
        row['lost_revenue'] = max(0, target - row['value']) / 100 * row['n'] * row['downstream_to_won'] * avg if number(row['value']) and number(avg) and number(row.get('downstream_to_won')) else None
        row.update(own_benchmark=benchmark, initial_benchmark=first_four[key]['value'], rungs=rungs, rung_reached=reached, target=target,
                   ladder_mode='maintain' if reached == len(rungs) else 'advance', promotion_policy='Wilson lower bound; no minimum-n gate; historical attainment, not lifetime confidence',
                   min_outcome_cases=MIN_OUTCOME_CASES, rung_eligible=rung_eligible,
                   promotion_reason=None if rung_eligible else 'Outcome tiers need a nonempty cohort after baseline collection.',
                   target_text=f'{target:g} %' + (' · top rung held' if reached == len(rungs) else ''), baseline_phase=phase, baseline_ready=not phase and row['n'] > 0)
        if row['state'] != 'missing':
            row['state'] = 'undecided' if phase else rate_state(row['k'], row['n'], target)
            row['cases_needed'] = cases_needed(row['k'], row['n'], target) if row['state'] == 'undecided' else 0
            row['reason'] = 'Weeks 1–4 collect your own baseline; no rate verdict.' if phase else (
                'Too few mature cases to decide against the next rung.' if row['state'] == 'undecided' else None)


def lead_todos(jobs, today, goals):
    rows = []
    for job in jobs:
        if job.get('status') in ('won', 'lost') or job.get('imported'):
            continue
        jid = str(job['id'])
        due = day(job.get('next_follow_up'))
        if due and due <= today:
            rows.append({'text': 'Follow up on lead ' + jid, 'lead_id': jid, 'due': due.isoformat(), 'kind': 'follow_up'})
        movement = day(job.get('last_activity_at') or job.get('status_updated_at') or event(job, 'replied') or job.get('found_at'))
        if job.get('status') in ('replied', 'call', 'offer') and movement and (today - movement).days >= 7:
            rows.append({'text': 'Check quiet lead ' + jid, 'lead_id': jid, 'due': (movement + dt.timedelta(days=7)).isoformat(), 'kind': 'stalled'})
        booked = timestamp(job.get('call_scheduled_at'))
        session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
        if booked and booked + dt.timedelta(hours=24) <= dt.datetime.combine(today, dt.time(), local_zone()) and not (session.get('held_at') or session.get('cancelled') or (event(job, 'call_held') and not session)) and not job.get('call_no_show'):
            rows.append({'text': 'Confirm whether lead ' + jid + ' attended', 'lead_id': jid,
                         'due': booked.astimezone(local_zone()).date().isoformat(), 'kind': 'no_show_confirm'})
        held = event(job, 'call_held')
        if held and proposal_eligible(job) and not event(job, 'proposal_sent'):
            due = day(job.get('proposal_due_on') or job.get('proposal_promised_at')) or held.astimezone(local_zone()).date()
            rows.append({'text': 'Prepare proposal for lead ' + jid, 'lead_id': jid, 'due': due.isoformat(), 'kind': 'proposal_due'})
    for goal in goals:
        rows.append({'text': goal['action'], 'lead_id': None, 'due': goal['review_on'], 'kind': 'goal'})
    order = {'proposal_due': 0, 'no_show_confirm': 1, 'follow_up': 2, 'stalled': 3, 'goal': 4}
    return sorted(rows, key=lambda row: (row['due'], order[row['kind']], row['lead_id'] or '', row['text']))[:7]


def explore_fields(jobs, today, history):
    bounds = span(today, 28)
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    monday = today - dt.timedelta(days=today.weekday())
    cohorts = []
    for back in range(7, -1, -1):
        start = monday - dt.timedelta(weeks=back)
        rows = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and inside(event(job, 'applied'), (start, start + dt.timedelta(days=6)))]
        steps = {'applied': rows, 'replied': [job for job in rows if event(job, 'replied')],
                 'call': [job for job in rows if event(job, 'call_booked') or event(job, 'call_held')],
                 'won': [job for job in rows if event(job, 'won')]}
        iso = start.isocalendar()
        cohorts.append({'week': f'{iso.year}-W{iso.week:02d}', **{key: len(value) for key, value in steps.items()},
                        'lead_ids': {key: ids(value) for key, value in steps.items()}})
    daily = []
    for back in range(84, 0, -1):
        date = today - dt.timedelta(days=back)
        rows = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and qualified(job) and inside(event(job, 'applied'), (date, date))]
        daily.append({'date': date.isoformat(), 'count': len(rows), 'lead_ids': ids(rows)})
    replies = [(job, value) for job, value, pending in response_cases(jobs, bounds, run_timestamp(today)) if not pending]
    hist = []
    for label, low, high in (('<5m', 0, 5), ('5-15m', 5, 15), ('15-60m', 15, 60), ('1-4h', 60, 240), ('>4h', 240, math.inf)):
        hist.append({'bucket': label, 'count': sum(low <= value < high for _, value in replies), 'basis': 'Completed first answers by client arrival; pending cases excluded'})
    mature = cohort(jobs, 'applied', 7, today, bounds, 'outbound')
    speed = []
    for label in ('<10m', '10-60m', '1-6h', '>6h'):
        rows = [job for job in mature if (job.get('application_facts') or {}).get('posted_age_band') == label]
        k = sum(has_after(job, 'replied', event(job, 'applied'), event(job, 'applied') + dt.timedelta(days=7)) for job in rows)
        speed.append({'bucket': label, 'k': k, 'n': len(rows), 'rate': rounded(100 * k / len(rows)) if rows else None, 'market_line': None, 'evidence': ids(rows)})
    segments = []
    dimensions = sorted({key for job in mature for key in (job.get('application_facts') or {}) if key not in ('source', 'frozen_at')})
    for dimension in dimensions:
        values = sorted({str((job.get('application_facts') or {}).get(dimension)) for job in mature if isinstance((job.get('application_facts') or {}).get(dimension), (str, int, float))})
        for value in values:
            rows = [job for job in mature if str((job.get('application_facts') or {}).get(dimension)) == value]
            k = sum(has_after(job, 'replied', event(job, 'applied'), event(job, 'applied') + dt.timedelta(days=7)) for job in rows)
            segments.append({'dimension': dimension, 'value': value, 'k': k, 'n': len(rows),
                             'observed': rounded(100 * k / len(rows)), 'expected': None, 'lead_ids': ids(rows)})
    forecast = []
    for stage, entry, maturity in (('applied', 'applied', 28), ('replied', 'replied', 28), ('call', 'call_held', 21), ('offer', 'offer', 21)):
        rows = [job for job in jobs if job.get('status') == stage and not job.get('imported')]
        values = [job.get('price_estimate') or (job.get('details') or {}).get('price_estimate') or job.get('bid_amount') for job in rows]
        known = sum(value for value in values if number(value))
        past = cohort(jobs, entry, maturity, today, bounds)
        won = [job for job in past if has_after(job, 'won', event(job, entry), event(job, entry) + dt.timedelta(days=maturity))]
        k = len(won)
        amounts = [contract_value(job) for job in won]
        currencies = {(job.get('won_value') or {}).get('currency') for job in won}
        average = statistics.mean(amounts) if amounts and all(number(value) for value in amounts) and len(currencies) == 1 and None not in currencies else None
        state = rate_state(k, len(past), 30)
        own = k / len(past) if past and state != 'undecided' else None
        forecast.append({'stage': stage, 'count': len(rows), 'known_value': known,
                         'own_rate': rounded(own), 'average_won_value': rounded(average), 'k': k, 'n': len(past),
                         'horizon_days': maturity, 'expected': rounded(len(rows) * own * average) if own is not None and average is not None else None})
    rubric = []
    for snapshot in sorted(history, key=lambda row: row['week'])[-7:]:
        review = snapshot.get('reviews', {}).get('call', {})
        points = {str(row['point']): rounded(100 * row['met'] / row['n']) if row['n'] else None for row in review.get('coverage', [])}
        rubric.append({'week': snapshot['week'], 'points': {str(index): points.get(str(index)) for index in range(1, 10)},
                       'calls': sum(item.get('reviewable', False) for item in review.get('rubric', []))})
    return {'cohorts': cohorts, 'daily_applications': daily, 'reply_time_hist': hist, 'speed_curve': speed,
            'segments': segments, 'forecast': {'next_30_days': rounded(sum(row['expected'] for row in forecast)) if all(row['expected'] is not None for row in forecast) else None,
                'by_stage': forecast, 'label': 'Expected new contract value under observed stage horizons; not a calibrated 30-day prediction'}, 'call_rubric_weeks': rubric, 'insights_top': []}


def public_member_name():
    text = context_text()
    match = re.search(r'^\s*(?:\*\*)?(?:Name and location|Name|Full name)(?:\*\*)?:\s*(?:\*\*)?([^\n*]+)', text, re.M | re.I)
    if not match: return None
    parts = match[1].split(',', 1)[0].strip().split()
    if not parts or not all(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ'-]+", part) for part in parts): return None
    return parts[0] + (' ' + parts[-1][0] + '.' if len(parts) > 1 else '')


def community_card(jobs, today, kpis, reviews, week, streak, now=None):
    # Older unresolved goals remain in the private review; sharing shows the latest agreed set only.
    latest_start = max((row.get('start', '') for row in reviews), default='')
    reviews = [row for row in reviews if row.get('start', '') == latest_start]
    # Frozen §13: all public conversion entries share the oldest (28-day)
    # maturity window. Activity applications remain a separate seven-day count.
    bounds = tuple(value - dt.timedelta(days=28) for value in span(today, 28))
    def public_rate(key, entry, outcomes, horizon, window, target):
        rows = cohort(jobs, entry, 0, today, window, 'outbound')
        def success(job):
            start = event(job, entry)
            return any(has_after(job, name, start, start + dt.timedelta(days=horizon)) for name in outcomes)
        row = rate_metric('proposal_to_won' if key == 'call_to_won' else key, rows, success, target)
        row.update(entry_period=period(window), outcome_label=PUBLIC_OUTCOME_LABELS[key], progression=None)
        if key == 'reply_to_call':
            def within(job, name):
                start = event(job, entry)
                return has_after(job, name, start, start + dt.timedelta(days=horizon))
            row['progression'] = {'booked_calls': sum(within(job, 'call_booked') for job in rows),
                'held_calls': sum(within(job, 'call_held') for job in rows),
                'offer_or_contract_without_call': sum((within(job, 'offer') or within(job, 'won')) and
                    not (within(job, 'call_booked') or within(job, 'call_held')) for job in rows)}
        return row
    result = {'week': week, 'applications': sum(qualified(job) for job in cohort(jobs, 'applied', 0, today, span(today, 7), 'outbound')),
              'streak_weeks': streak, 'goals_done': f"{sum(row['done_n'] > 0 and row['done_k'] == row['done_n'] for row in reviews)}/{len(reviews)}",
              'goals': [{'text': ' '.join(row['change'].split()[:6]), 'done': row['done_n'] > 0 and row['done_k'] == row['done_n'],
                        'k': row['done_k'], 'n': row['done_n'], 'state': row.get('execution_state', 'unverified')} for row in reviews],
              'next_focus': None, 'question': None, 'new_badge': None, 'top_badges': [], 'member_name': public_member_name()}
    improvements = []
    for name, entry, outcomes, horizon, rungs in (
            ('reply_rate', 'applied', ('replied',), 7, (11, 15, 20)),
            ('reply_to_call', 'replied', ('call_booked', 'call_held', 'offer', 'won'), 14, (30, 40, 50)),
            ('call_to_won', 'call_held', ('won',), 28, (20, 25, 30)),
            ('booked_to_held', 'call_booked', ('call_held',), 2, (70, 80, 90)),
            ('proposal_to_won', 'proposal_sent', ('won',), 21, (20, 25, 30))):
        row = public_rate(name, entry, outcomes, horizon, bounds, rungs[-1])
        old = public_rate(name, entry, outcomes, horizon, tuple(value - dt.timedelta(days=28) for value in bounds), rungs[-1])
        value, prior = row['value'], old['value']
        low, high = difference_bounds(old, row)
        trend = 'up' if number(low) and low > 0 else 'down' if number(high) and high < 0 else 'undecided'
        result[name] = {'value': value, 'target': rungs[-1], 'rung_reached': sum(rate_state(row['k'], row['n'], rung) == 'pass' for rung in rungs) if row['n'] >= MIN_OUTCOME_CASES else 0, 'of': 3, 'trend': trend,
                        'k': row['k'], 'n': row['n'], 'state': row['state'], 'horizon_days': horizon,
                        'entry_period': row['entry_period'], 'outcome_label': row['outcome_label'], 'progression': row.get('progression')}
        if trend == 'up': improvements.append({'kpi': name, 'from': prior, 'to': value})
    values = [value for _, value, _ in response_cases(jobs, bounds, run_timestamp(today, now))]
    result['first_reply_median_min'] = statistics.median(values) if values else None
    result['first_reply_target_min'] = 5
    result['biggest_improvement'] = max(improvements, key=lambda row: row['to'] - row['from'], default=None)
    result['won_value'] = financial(jobs, read_lines('earnings.jsonl'), span(today, 7))['value'] if sections().get('Share money', '').strip().casefold() == 'yes' else None
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in source_coverage(jobs, today, now)[0]):
        for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won', 'call_to_won'):
            result[key].update(value=None, k=None, n=None, state='missing')
        result['applications'] = None
        result['first_reply_median_min'] = None
    return result


def badge_results(snapshot, jobs, history, today):
    """Tiers accumulate qualifying weeks. Misses and pauses never erase earned progress."""
    week = snapshot['week']; prior = {row['week']: row for row in history if row.get('week', '') < week}
    all_rows = list(prior.values()) + [snapshot]
    old = {}
    for row in all_rows[:-1]:
        for badge in row.get('badges', []):
            if badge.get('badge') in BADGE_NAMES and badge.get('tier') in TIERS:
                old.setdefault((badge['badge'], badge['tier']), badge)
    for award in badge_ledger.read_ledger():
        at = day(award.get('at'))
        if at and at <= today:
            iso = at.isocalendar(); earned = f'{iso.year}-W{iso.week:02d}'
            old.setdefault((award['badge'], award['tier']), dict(award, earned_week=earned))
    def passing(row, key):
        item = row.get('kpis', {}).get(key, {})
        return item.get('state') == 'pass' and (item.get('n') or 0) > 0 and number(item.get('value'))
    def criterion(row, name):
        recorded = row.get('badge_qualifying', {})
        if name in recorded: return recorded[name] is True
        kpis = row.get('kpis', {})
        if name in OUTCOME_BADGES:
            key, thresholds = OUTCOME_BADGES[name]
            item = row.get('call_to_won', {}) if key == 'call_to_won' else kpis.get(key, {})
            phase = kpis.get('proposal_to_won' if key == 'call_to_won' else key, {}).get('baseline_phase', True)
            return not phase and item.get('state') != 'missing' and (item.get('n') or 0) > 0 and wilson(item['k'], item['n'])[0] >= thresholds[0]
        mapping = {'Swift Sail': 'speed_10min', "Ship's Bell": 'first_reply', 'Lookout': 'follow_ups_on_time', 'Steady Anchor': 'weekly_volume', 'Quick Draw': 'proposal_on_time'}
        if name in ('Swift Sail', "Ship's Bell", 'Quick Draw'): return False
        if name in mapping: return passing(row, mapping[name])
        if name == 'Navigator': return all(passing(row, key) for key in LEVERS)
        if name == 'Lighthouse Keeper': return bool(row.get('report', '').strip())
        if name == 'First Doubloon': return (row.get('north_star', {}).get('wins') or 0) > 0
        if name == 'Back on Course': return (row.get('gap', {}).get('weeks_missed') or 0) >= 2
        return False
    # Content is an explicit coach judgement, separate from measured speed.
    weekly = [job for job in jobs if not job.get('imported') and inside(event(job, 'applied'), span(today, 7)) and qualified(job)]
    qualifying = {name: criterion(snapshot, name) for name in BADGE_NAMES}
    qualifying["Ship's Bell"] = passing(snapshot, 'first_reply')
    def application_content(job):
        return badge_ledger.content_pass(job, 'application') or any(item.get('lead_id') == str(job['id']) and item.get('reviewable') and item.get('points') and all(point['state'] == 'met' for point in item['points']) for item in snapshot.get('reviews', {}).get('application', {}).get('rubric', []))
    swift_good = sum((job.get('application_facts') or {}).get('posted_age_band') == '<10m' and application_content(job) for job in weekly)
    qualifying['Swift Sail'] = bool(weekly) and snapshot['kpis']['speed_10min']['state'] != 'missing' and swift_good / len(weekly) * 100 >= snapshot['kpis']['speed_10min']['target']
    replies = [job for job in jobs if inside(job.get('first_client_message_at') or job.get('replied_at') or job.get('invited_at'), span(today, 7))]
    qualifying["Ship's Bell"] = qualifying["Ship's Bell"] and bool(replies) and all(badge_ledger.content_pass(job, 'conversation') for job in replies)
    calls = [job for job in jobs if inside(event(job, 'call_held'), span(today, 7)) and proposal_eligible(job)]
    quick_good = sum(bool(badge_ledger.content_pass(job, 'proposal') and call_end(job) and event(job, 'proposal_sent') and 0 <= (event(job, 'proposal_sent') - call_end(job)).total_seconds() <= 1800) for job in calls)
    qualifying['Quick Draw'] = bool(calls) and snapshot['kpis']['proposal_on_time']['state'] != 'missing' and quick_good / len(calls) * 100 >= snapshot['kpis']['proposal_on_time']['target']
    invites = [job for job in jobs if route(job) == 'invite' and inside(event(job, 'invited'), span(today, 7))]
    times = [working_reply(job) for job in invites]
    qualifying['Message in a Bottle'] = bool(invites) and all(number(value) and value <= 60 and badge_ledger.content_pass(job, 'conversation') for job, value in zip(invites, times))
    point_rows = list(snapshot.get('reviews', {}).get('call', {}).get('rubric', []))
    point_rows += [dict(job.get('call_review', {}), lead_id=str(job['id'])) for job in jobs if isinstance(job.get('call_review'), dict) and inside(event(job, 'call_held'), span(today, 7))]
    qualifying['True North'] = snapshot['kpis']['call_review']['state'] == 'pass' and any(item.get('reviewable') and (badge_ledger._call_fraction(item.get('points')) or 0) >= 7 / 9 for item in point_rows)
    qualifying['Navigator'] = qualifying['Navigator'] and all(qualifying[name] for name in ('Swift Sail', "Ship's Bell", 'Lookout', 'Steady Anchor', 'Quick Draw'))
    snapshot['badge_qualifying'] = qualifying
    counts = {name: sum(criterion(row, name) for row in all_rows) for name in BADGE_NAMES}
    first_week = not prior
    first_names = {name for name, tier in old if old[(name, tier)].get('earned_week') == week}
    result = []
    priority = ('Steady Anchor', 'Swift Sail', "Ship's Bell", 'Lookout', 'Quick Draw', 'True North') + tuple(name for name in BADGE_NAMES if name not in ('Steady Anchor', 'Swift Sail', "Ship's Bell", 'Lookout', 'Quick Draw', 'True North'))
    for name in priority:
        limit = 1 if name == 'Back on Course' else 5
        thresholds = (1,) if limit == 1 else badge_ledger.QUALIFYING_WEEKS
        reached = max([index for index, threshold in enumerate(thresholds) if counts[name] >= threshold] +
                      [TIERS.index(tier) for old_name, tier in old if old_name == name], default=-1)
        next_index = reached + 1
        progress = 'All tiers earned' if next_index >= limit else f'{min(counts[name], thresholds[next_index])} of {thresholds[next_index]} ' + ('returns' if name == 'Back on Course' else 'weeks')
        for index in range(reached + 1):
            tier = TIERS[index]; earned = old.get((name, tier))
            if earned is None and first_week and name not in first_names and len(first_names) >= 2: continue
            if earned is None and first_week: first_names.add(name)
            result.append({'badge': name, 'tier': tier, 'earned_week': earned['earned_week'] if earned else week,
                           'new': earned is None or earned['earned_week'] == week, 'progress_to_next': progress})
    return result


def presentation_fields(snapshot):
    """Snapshot owns selection and grouping; readers render these keys without recomputing."""
    kpis = snapshot['kpis']
    eligible = [key for key, row in kpis.items() if number(row.get('baseline')) and
                number(row.get('delta')) and (row.get('state') in ('pass', 'fail') or (row.get('n') or 0) >= 10)]
    def adjusted(key):
        row = kpis[key]
        denominator = max(abs(row['baseline']), 1)
        return row['delta'] * (-1 if row.get('direction') == 'down' else 1) / denominator
    focus, efficiency = snapshot.get('verdict', {}).get('kpi'), 'value_per_100_connects'
    selected = [focus] if focus in kpis and focus != efficiency else []
    candidates = [key for key in eligible if key not in selected and key != efficiency]
    order = lambda key: kpis[key].get('order', list(kpis).index(key))
    positive = sorted((key for key in candidates if adjusted(key) > 0), key=lambda key: (-adjusted(key), order(key)))[:2]
    negative = sorted((key for key in candidates if adjusted(key) < 0), key=lambda key: (adjusted(key), order(key)))[:2]
    selected += positive + negative
    for key in sorted(candidates, key=lambda key: (-abs(adjusted(key)), order(key))):
        if len(selected) >= 5: break
        if key not in selected: selected.append(key)
    if efficiency in kpis: selected.append(efficiency)
    groups = {'top': [], 'middle': [], 'bottom': []}
    top = {'job_fit', 'weekly_volume', 'speed_10min', 'application_review', 'segments', 'behaviour'}
    middle = {'reply_rate', 'reply_to_call', 'booked_to_held', 'invite_to_call', 'first_reply', 'follow_ups_on_time', 'conversation_review', 'call_review'}
    for key in kpis: groups['top' if key in top else 'middle' if key in middle else 'bottom'].append(key)
    # Six visual slots; placeholders never masquerade as eligible KPI comparisons.
    slots = [{'key': key, 'role': 'focus' if key == focus else 'efficiency' if key == efficiency else 'comparison',
              'group': next((group for group, keys in groups.items() if key in keys), 'bottom')} for key in selected]
    while len(slots) < 6:
        slots.insert(max(0, len(slots) - 1), {'key': None, 'role': 'comparison', 'group': 'bottom',
                     'label': 'Comparison not yet known', 'reason': 'At least 10 cases or a decidable KPI, plus an own baseline, are needed.'})
    # Selection normalization is an approved cross-unit assumption; delta stays raw.
    summaries = {group: {'stood_out': [dict(kpi=key, text=kpis[key]['insight'], evidence=kpis[key].get('evidence', []))
                                    for key in keys if kpis[key].get('insight')],
                         'leak': focus if focus in keys else None} for group, keys in groups.items()}
    return {'number_keys': selected, 'number_slots': slots, 'selection_basis': 'direction-adjusted delta / max(abs(baseline), 1)',
            'number_gap': None if len(selected) == 6 else 'Fewer than four eligible nonreserved movements with a numeric baseline.',
            'insights': copy.deepcopy(snapshot.get('insights_top', [])[:3]),
            'insights_all': copy.deepcopy(snapshot.get('insights_top', []) + snapshot.get('findings', [])),
            'kpi_groups': groups, 'number_groups': {group: {'label': {'top': 'Top of funnel', 'middle': 'Middle of funnel', 'bottom': 'Bottom of funnel'}[group], 'keys': groups[group], 'stood_out': ' '.join(item['text'] for item in summary['stood_out']), 'leak': summary['leak']} for group, summary in summaries.items()}}


def followup_counts(jobs, bounds):
    """Distinct silent-lane obligations; later cancellation cannot erase a missed due day."""
    opportunities, completed = [], []
    for job in jobs:
        if job.get('imported'): continue
        obligations = {}
        for item in job.get('follow_up_history') or []:
            if item.get('lane') != 'silent' or not inside(item.get('due_on'), bounds): continue
            key = item.get('obligation_id') or ('legacy', item.get('lane'), item.get('due_on'))
            prior = obligations.get(key, {})
            obligations[key] = prior if prior.get('action') == 'sent' else dict(prior, **item)
        plan = job.get('follow_up_plan') or {}
        due = plan.get('due_on') or job.get('next_follow_up')
        key = plan.get('obligation_id') or ('legacy', plan.get('lane'), due)
        if plan.get('lane') == 'silent' and inside(due, bounds): obligations.setdefault(key, dict(plan, due_on=due))
        for key, item in obligations.items():
            cancelled = timestamp(item.get('cancelled_at'))
            if cancelled and cancelled < dt.datetime.combine(day(item['due_on']), dt.time(), local_zone()) and item.get('action') != 'sent': continue
            opportunities.append(str(job['id']))
            if item.get('action') == 'sent' and day(item.get('on') or item.get('at')) == day(item['due_on']): completed.append(str(job['id']))
    return opportunities, completed


@member_clock
def daily_voyage(jobs, today=None, weekly_goal=None):
    today = as_today(today)
    applied = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and qualified(job) and day(event(job, 'applied')) == today]
    fast = [job for job in applied if (number(job.get('speed_to_lead_s')) and 0 <= job['speed_to_lead_s'] <= 600) or (job.get('application_facts') or {}).get('posted_age_band') == '<10m']
    due, done = followup_counts(jobs, (today, today))
    return {'date': today.isoformat(), 'applications': len(applied), 'goal': (bars()['weekly_volume'] if weekly_goal is None else weekly_goal) / 5,
            'fast': len(fast), 'followups_due': len(due), 'followups_done': len(done),
            'evidence': {'applications': ids(applied), 'fast': ids(fast), 'followups': sorted(set(due))}}


@member_clock
def quest_progress(snapshot, jobs, today=None):
    today = as_today(today)
    bounds = (today - dt.timedelta(days=today.weekday()), today)
    result = []
    for goal in snapshot.get('goals_next', []):
        key = goal['kpi']
        row = snapshot.get('kpis', {}).get(key, {})
        due, done = [], []
        unit = 'opportunities'
        if key == 'weekly_volume':
            done = [str(job['id']) for job in jobs if not job.get('imported') and route(job) == 'outbound' and qualified(job) and inside(event(job, 'applied'), bounds)]
            n, unit = bars()['weekly_volume'], 'applications'
        elif key == 'follow_ups_on_time':
            due, done = followup_counts(jobs, bounds)
            n, unit = len(due), 'due follow-ups'
        elif key == 'proposal_on_time':
            due = [str(job['id']) for job in jobs if not job.get('imported') and proposal_eligible(job) and call_end(job) and inside(event(job, 'call_held'), bounds)]
            done = [str(job['id']) for job in jobs if str(job['id']) in due and event(job, 'proposal_sent') and 0 <= (event(job, 'proposal_sent') - call_end(job)).total_seconds() <= 1800]
            n, unit = len(due), 'calls'
        elif key == 'first_reply':
            cases = response_cases(jobs, bounds, run_timestamp(today))
            due = [str(job['id']) for job, _, _ in cases]
            done = [str(job['id']) for job, value, pending in cases if not pending and value <= bars()['first_reply']]
            n, unit = len(due), 'replies'
        elif key == 'speed_10min':
            due = [str(job['id']) for job in jobs if not job.get('imported') and qualified(job) and route(job) == 'outbound' and inside(event(job, 'applied'), bounds)]
            done = [str(job['id']) for job in jobs if str(job['id']) in due and ((number(job.get('speed_to_lead_s')) and 0 <= job['speed_to_lead_s'] <= 600) or (job.get('application_facts') or {}).get('posted_age_band') == '<10m')]
            n, unit = len(due), 'applications'
        else:
            # Arbitrary commitments require explicit behavior proof, not outcome success.
            entry = {'reply_rate': 'applied', 'reply_to_call': 'replied', 'booked_to_held': 'call_booked',
                     'held_to_proposal': 'call_held', 'proposal_to_won': 'proposal_sent',
                     'invite_to_call': 'invited', 'offer_to_contract': 'offer'}.get(key, 'applied')
            start = day(goal.get('start')) or bounds[0]
            goal_bounds = (max(start, bounds[0]), today)
            due = sorted({str(job['id']) for job in jobs if not job.get('imported') and inside(event(job, entry), goal_bounds)})
            unit = {'applied': 'applications', 'replied': 'replies', 'call_booked': 'calls', 'call_held': 'calls',
                    'proposal_sent': 'proposals', 'invited': 'invitations', 'offer': 'offers'}[entry]
            identity = goal.get('goal_id') or goal_id(dict(goal, start=start.isoformat()), snapshot.get('week', today.strftime('%G-W%V')))
            proven = set()
            for job in jobs:
                jid = str(job['id'])
                if jid not in due: continue
                for item in job.get('log') or []:
                    text = str(item.get('text', ''))
                    if not text.startswith('analytics goal_action: '): continue
                    try: action = json.loads(text[len('analytics goal_action: '):])
                    except (TypeError, ValueError): continue
                    if (isinstance(action, dict) and set(action) == {'goal_id', 'kpi', 'at', 'evidence'}
                        and action['goal_id'] == identity and action['kpi'] == key and timestamp(action['at'])
                        and inside(action['at'], goal_bounds) and isinstance(action['evidence'], str) and action['evidence'].strip()):
                        proven.add(jid)
            for review in snapshot.get('goals_review', []):
                if review.get('goal_id') == identity and review.get('kpi') == key:
                    proven.update(str(jid) for jid in review.get('done_lead_ids', []) if str(jid) in due)
            n, done = len(due), sorted(proven)
            state = 'no opportunity' if not n else 'complete' if len(done) == n else 'partial' if done else 'unverified'
            result.append({'goal_id': identity, 'kpi': key, 'change': goal['change'], 'done_k': len(done) if done or not n else None,
                           'done_n': n, 'unit': unit, 'evidence': due, 'execution_state': state,
                           'note': 'Explicit goal action proof required; outcome success is not execution.' if state == 'unverified' else None})
            continue
        result.append({'goal_id': goal.get('goal_id') or goal_id(dict(goal, start=goal.get('start') or bounds[0].isoformat()), snapshot.get('week', today.strftime('%G-W%V'))),
                       'kpi': key, 'change': goal['change'], 'done_k': len(done), 'done_n': n, 'unit': unit, 'evidence': sorted(set(due + done))})
    return result


def saved_review_time(job, review, kind='call'):
    # Only recorded timestamps, never the current projection time or file mtime.
    for key in ('reviewed_at', 'as_of'):
        if timestamp(review.get(key)): return review[key]
    recorded = job.get(kind + '_reviewed_at')
    if timestamp(recorded): return recorded
    for entry in reversed(job.get('log') or []):
        prefix = 'analytics ' + kind + '_review: '
        if not str(entry.get('text', '')).startswith(prefix) or not timestamp(entry.get('at')): continue
        try: saved = json.loads(entry['text'][len(prefix):])
        except (TypeError, ValueError): continue
        if isinstance(saved, dict) and all(review.get(key) == value for key, value in saved.items()): return entry['at']
    return None


def goal_cards(snapshot):
    """Present canonical commitments with matching saved coach examples and execution units."""
    units = {row['goal_id']: row['unit'] for row in snapshot.get('quests', [])}
    result = []
    for goal in snapshot.get('goals_next', []):
        start = goal.get('start') or day(snapshot['generated_at']).isoformat()
        identity = goal_id(dict(goal, start=start), snapshot['week'])
        matches = [review for review in snapshot.get('reviews', {}).values()
                   if review.get('goal_ref') in (identity, goal['kpi']) and review.get('evidence_lead_ids')
                   and isinstance(review.get('example'), str) and review['example'].strip()]
        example = matches[0]['example'] if len(matches) == 1 else None
        unit = units.get(identity)
        result.append({'goal_id': identity, 'kpi': goal['kpi'], 'cue': goal['cue'], 'action': goal['action'],
            'coach_example': example, 'example_state': 'saved' if example else 'unknown',
            'example_prompt': None if example else 'Supply a coach example selected for this goal.',
            'execution_unit': unit, 'review_on': goal['review_on'],
            'measurement': f"Review completed {unit} on {goal['review_on']}; execution and effect are checked separately." if unit else None})
    return result


def saved_snapshot_view(snapshot):
    """Retire only gamification fields and duplicated conversation points in a copy."""
    result = copy.deepcopy(snapshot)
    presentation = result.get('presentation') or {}
    containers = [result, presentation, result.get('voyage'), result.get('community_card'),
                  presentation.get('voyage'), presentation.get('progress_strip')]
    for container in containers:
        if isinstance(container, dict):
            container.pop('rank', None)
            container.pop('rank_progress', None)
    def content_points(item):
        if isinstance(item, dict):
            if isinstance(item.get('points'), dict):
                for key in ('fast_answer', 'follow_ups'): item['points'].pop(key, None)
            for value in item.values(): content_points(value)
        elif isinstance(item, list):
            for value in item: content_points(value)
    for key in ('conversation_review', 'conversations'):
        content_points(result.get(key))
    content_points(result.get('reviews', {}).get('conversation'))
    return result


def call_cards(snapshot, jobs=None):
    review = snapshot.get('reviews', {}).get('call', {})
    by_id = {str(job['id']): job for job in (pipeline.load() if jobs is None else jobs)}
    cards = []
    rubrics = list(review.get('rubric', [])); reviewed = {str(item['lead_id']) for item in rubrics}
    for jid, job in by_id.items():
        if jid not in reviewed and event(job, 'call_held') and inside(event(job, 'call_held'), (day(snapshot['generated_at']) - dt.timedelta(days=28), day(snapshot['generated_at']))):
            saved = job.get('call_review') if not _RECONSTRUCTING.get() else None
            rubrics.append(dict(saved, lead_id=jid) if isinstance(saved, dict) else {'lead_id': jid, 'reviewable': False, 'points': []})
    for item in rubrics:
        job = by_id.get(str(item['lead_id']), {})
        read_path = pipeline.jobs_dir() / str(item['lead_id']) / 'call-review.md'
        read_text = read_source(read_path) or ''
        def section(*names):
            for name in names:
                match = re.search(r'^## ' + name + r'\s*\n(.*?)(?=^## |\Z)', read_text, re.M | re.S | re.I)
                if match and match[1].strip() and not _RECONSTRUCTING.get(): return match[1].strip()
            return None
        coach_read = section('Coach.s read')
        agreed_step = section('Next step agreed on the call', 'Agreed step', 'Next step on Upwork', 'Next step')
        next_message = section('Next message')
        if next_message is not None: short_text(next_message, 100, 'Call next message')
        path = pipeline.jobs_dir() / str(item['lead_id']) / 'call.md'
        stats = call_stats.analyze(read_source(path) or '')
        duration = stats.get('duration_s', job.get('call_duration_s'))
        card = {'lead_id': item['lead_id'], 'label': 'Call review',
                'date': day(event(job, 'call_held')).isoformat() if event(job, 'call_held') else None,
                'duration_minutes': duration / 60 if number(duration) else None,
                'talk_share': stats.get('talk_share_pct', job.get('talk_share_pct')),
                'questions': stats.get('question_counts', job.get('question_counts')),
                'reviewable': bool(item.get('reviewable') and stats.get('transcript_complete') is True and stats.get('member_attributed') is True)}
        # Compatibility aliases read by the current private card component.
        coach_read = (coach_read or item.get('free_read')) if card['reviewable'] else None
        if coach_read is not None: short_text(coach_read, 180, 'Call free read', optional=True)
        reviewed_at = saved_review_time(job, item)
        card.update(as_of=reviewed_at, reviewed_at=reviewed_at,
                    coach_read=coach_read, coach_read_state='present' if coach_read else 'unknown', coach_read_prompt='No review yet: run /call-review ' + str(item['lead_id']))
        card.update(agreed_step=agreed_step or item.get('agreed_step') or item.get('next_step'),
                    next_message=next_message or item.get('next_message'),
                    source_prompt='Paste a transcript or run /call-review ' + str(item['lead_id']))
        if card['next_message'] is not None: short_text(card['next_message'], 100, 'Call next message')
        card.update(duration_min=card['duration_minutes'], question_count=(card['questions'] or {}).get('member'))
        if not card['reviewable']:
            card.update(reason='Not reviewable: complete labelled call evidence is missing.', points=[], moments=[],
                        fix='', example='', next_step=None, agreed_step=None, next_message=None)
        else:
            points = [dict(point=index, state=next((p['state'] for p in item['points'] if p['point'] == index), 'missing'),
                           reason=next((p.get('reason') for p in item['points'] if p['point'] == index), None),
                           quote=next((p.get('quote') for p in item['points'] if p['point'] == index), None)) for index in range(1, 10)]
            for point in points:
                point.update(label=CALL_POINT_LABELS[point['point']], definition=CALL_POINT_DEFINITIONS.get(point['point']))
                point['quote_state'] = 'supported' if point['quote'] else 'unknown'
            card.update(points=points, moments=[dict(moment, better=moment['better_wording']) for moment in item.get('moments', [])[:3]],
                        fix=item.get('fix', review.get('fix', '')), example=item.get('example', review.get('example', '')),
                        next_step=item.get('next_step'))
        cards.append(card)
    return cards


def progress_strip(snapshot):
    """Use comparable measured four-week scorecard movements, respecting each unit's direction."""
    candidates = []
    for row in snapshot.get('presentation', {}).get('scorecard', []):
        previous = row.get('change', {}).get('previous_value')
        # The scorecard owns the comparable four-week population, not weekly KPI deltas.
        change = row.get('change', {})
        previous = change.get('baseline', previous)
        value = row.get('value')
        if not (number(value) and number(previous)) or row.get('state') == 'missing': continue
        if not row.get('n', row.get('finished', {}).get('n')): continue
        direction = snapshot.get('kpis', {}).get(row['key'], {}).get('direction', 'up')
        movement = (value - previous) * (-1 if direction == 'down' else 1)
        if not movement: continue
        strength = movement / max(abs(previous), 1)
        candidates.append((strength, row['key'], {'key': row['key'], 'name': row['name'],
            'text': f"{row['name']}: {value:g}, was {previous:g}",
            'direction': 'gain' if movement > 0 else 'decline', 'value': value, 'previous': previous}))
    gains = [row for row in candidates if row[0] > 0]
    chosen = max(gains, default=None, key=lambda row: (row[0], row[1])) if gains else min(candidates, default=None, key=lambda row: (row[0], row[1]))
    stations = snapshot.get('presentation', {}).get('voyage', {}).get('stations', [])
    earned = [row for row in stations if row.get('earned')]
    latest_week = max((row.get('earned_week') or '' for row in earned), default='')
    contenders = [row for row in earned if (row.get('earned_week') or '') == latest_week]
    dated = [row for row in contenders if timestamp(row.get('earned_at'))]
    newest = None; basis = 'No earned badge recorded.'
    if contenders and len(dated) == len(contenders):
        latest_at = max(timestamp(row['earned_at']) for row in dated)
        latest = [row for row in dated if timestamp(row['earned_at']) == latest_at]
        newest = latest[0] if len(latest) == 1 else None
        basis = 'Latest recorded award timestamp.' if newest else 'Award timestamps tied; actual chronology unknown.'
    elif len(contenders) == 1 and latest_week:
        newest = contenders[0]; basis = 'Latest earned week; exact award time unknown.'
    elif contenders:
        basis = 'Earned week tied or unknown; actual chronology unknown.'
    return {'biggest_change': chosen[2] if chosen else None, 'newest_badge': copy.deepcopy(newest), 'newest_badge_basis': basis}


def conversations_fields(snapshot, jobs):
    """Project saved coaching and sent evidence; never turn source text into coach judgment."""
    sections = {'applications': [], 'chats': [], 'calls': copy.deepcopy(snapshot.get('call_cards', [])), 'proposals': []}
    statements = {}
    def supported_points(saved, text):
        points = saved.get('points', [])
        points = [dict(point, point=key) for key, point in points.items()] if isinstance(points, dict) else points
        return [copy.deepcopy(point) for point in points if isinstance(point, dict) and
                isinstance(point.get('quote'), str) and point['quote'].strip() and point['quote'] in text]
    def remember(stage, jid, text, points):
        for point in points:
            reason = str(point.get('reason') or '').strip()
            if reason:
                key = ' '.join(reason.casefold().split())
                record = {'lead_id': jid, 'stage': stage, 'quote': point['quote']}
                bucket = statements.setdefault(key, {'text': reason, 'quotes': []})
                if record not in bucket['quotes']: bucket['quotes'].append(record)
    chats = {row['lead_id']: row for row in conversation_reviews(jobs, day(snapshot['generated_at']), quiet_only=False)['threads']}
    for job in jobs:
        if job.get('imported'): continue
        jid = str(job['id']); folder = pipeline.jobs_dir() / jid
        for stage, kind, event_key, filename, prompt in (
                ('applications', 'application', 'applied', 'application.sent.md', 'Save the exact sent application with code/pipeline.py sent ' + jid + '; supply the Loom transcript when used.'),
                ('chats', 'conversation', 'replied', 'thread.json', 'Read and save every page of the Upwork thread, then record its three quoted content checks.'),
                ('proposals', 'proposal', 'proposal_sent', 'proposal.md', 'Save the exact sent proposal in jobs/' + jid + '/proposal.md and confirm proposal_sent through the pipeline.')):
            if not event(job, event_key): continue
            source = read_source(folder / filename) or ''
            saved = assessment(job, kind + '_review') or {}
            weekly = snapshot.get('reviews', {}).get(kind, {})
            rubric = next((row for row in weekly.get('rubric', []) if str(row.get('lead_id')) == jid), {})
            saved = dict(saved, **rubric)
            valid = bool(source) and not _RECONSTRUCTING.get()
            extra = {}
            if stage == 'applications':
                valid = valid and job.get('application_sent_verified') is True
                loom = read_source(folder / 'loom-transcript.txt') or read_source(folder / 'loom.md') or ''
                loom_used = bool(job.get('loom_url') or job.get('loom_duration_s') is not None or re.search(r'https?://(?:www\.)?loom\.com/', source))
                if loom_used and not loom:
                    valid = False
                    prompt = 'Supply the Loom transcript at jobs/' + jid + '/loom.md, or run code/loom.py ' + jid + ' <verified Loom URL>.'
                extra.update(sent_copy=source if job.get('application_sent_verified') is True and source else None,
                             loom_transcript=loom or None)
                source += '\n' + loom
            if stage == 'chats':
                thread = chats.get(jid, {})
                valid = valid and thread.get('read') is True
                saved = dict(saved, **thread)
                extra['last_writer'] = thread.get('last_writer', 'unknown')
                try:
                    raw = json.loads(source)
                    rooms = list((raw.get('rooms') or {}).values()) or [raw]
                    source = '\n'.join(str(turn.get('text') or '') for room in rooms for turn in room.get('messages', []) if turn.get('from') in ('me', 'client'))
                except (ValueError, TypeError): valid = False; source = ''
            points = supported_points(saved, source) if valid else []
            quote = saved.get('quote')
            quote = quote if valid and isinstance(quote, str) and quote.strip() and quote in source else next((p['quote'] for p in points), None)
            # Existing weekly examples are evidence only if they actually quote this sent source.
            if not quote and valid and jid in weekly.get('evidence_lead_ids', []):
                example = weekly.get('example')
                if isinstance(example, str) and example.strip() and example in source: quote = example
            reviewable = bool(valid and quote and (saved.get('read') is True or saved.get('reviewable') is True or saved.get('state') == 'pass'))
            if stage == 'proposals':
                # Only quoted saved judgments/facts; never guess terms from prose.
                for key in ('scope', 'price', 'decision_date'):
                    fact = saved.get(key)
                    extra[key] = fact if reviewable and isinstance(fact, str) and fact.strip() and fact in source else None
                if any(extra[key] is None for key in ('scope', 'price', 'decision_date')):
                    extra['source_prompt'] = 'Save quoted scope, price and decision date from the sent proposal; missing facts remain unknown.'
            read = saved.get('free_read') if reviewable else None
            next_message = saved.get('next_message') if reviewable else None
            if next_message is not None: short_text(next_message, 100, 'Coaching next message', optional=True)
            sections[stage].append({'lead_id': jid, 'label': job.get('title') or jid,
                'date': day(event(job, event_key)).isoformat(), 'reviewable': reviewable,
                'source_prompt': None if reviewable else prompt if not valid else 'Record a quoted ' + kind + ' content review for ' + jid + '.',
                'points': points if reviewable else [], 'quote': quote if reviewable else None,
                'read': read, 'next_message': next_message, 'as_of': saved_review_time(job, saved, kind),
                'reviewed_at': saved_review_time(job, saved, kind), **extra})
            if reviewable: remember(stage, jid, source, points)
    for card in sections['calls']:
        # Historical cards with unknown quotes do not supply patterns.
        if card.get('reviewable'):
            text = read_source(pipeline.jobs_dir() / str(card['lead_id']) / 'call.md') or ''
            remember('calls', str(card['lead_id']), text, supported_points(card, text))
    patterns = [row for row in statements.values() if len({q['stage'] for q in row['quotes']}) >= 2]
    patterns.sort(key=lambda row: (-len(row['quotes']), row['text']))
    return {'patterns': patterns[:3], 'sections': sections}


def voyage_fields(snapshot, history):
    history = [row for row in history if row.get('week') != snapshot['week']] + [snapshot]
    runs = {row['week'] for row in history}
    streak = badge_ledger.streak_history(history, week=snapshot['week'])
    anchors = set(streak['anchors_used'])
    calendar = []
    for row in snapshot.get('daily_applications', []):
        date = day(row['date']); iso = date.isocalendar(); week = f'{iso.year}-W{iso.week:02d}'
        calendar.append(dict(row, qualified_count=row['count'], evidence=row.get('lead_ids', []), week=week, run=week in runs,
                             anchor=week in anchors, commitment=bars()['weekly_volume'] / 5 if date.weekday() < 5 else None, completion=min(row['count'] / (bars()['weekly_volume'] / 5), 1) if number(row['count']) and date.weekday() < 5 and bars()['weekly_volume'] > 0 else None, level='unknown' if row['count'] is None else 'unplanned' if date.weekday() >= 5 else 'completed' if row['count'] >= bars()['weekly_volume'] / 5 else 'open'))
    goals = [dict(goal, week=row['week']) for row in sorted(history, key=lambda row: row['week']) for goal in row.get('goals_review', [])]
    base = {'calendar': calendar, 'calendar_period': {'start': calendar[0]['date'], 'end': calendar[-1]['date']} if calendar else None,
            'goals_history': goals, 'streak_weeks': streak['streak_weeks'], 'anchors_used': streak['anchors_used']}
    return badge_ledger.voyage(badge_ledger.read_ledger(), dict(snapshot, presentation={'voyage': base}))


def money_chart(snapshot, history):
    """Saved weekly results and the 30-day forecast actually issued in each week."""
    currency = snapshot.get('north_star', {}).get('currency')
    rows = {row['week']: row for row in history if row.get('week', '') < snapshot['week']}
    rows[snapshot['week']] = snapshot
    won, forecasts = [], []
    for week, row in sorted(rows.items())[-8:]:
        north, forecast = row.get('north_star', {}), row.get('forecast', {})
        compatible = north.get('currency') == currency
        won.append({'week': week, 'value': north.get('value') if compatible else None,
                    'currency': north.get('currency'), 'period': row.get('periods', {}).get('outcome'),
                    'evidence': north.get('evidence', []), 'reason': None if compatible else 'Different currency; no conversion.'})
        start = day(row.get('generated_at'))
        bounds = {'start': start.isoformat(), 'end': (start + dt.timedelta(days=30)).isoformat()} if start else None
        forecasts.append({'week': week, 'value': forecast.get('next_30_days') if compatible else None,
                          'period': bounds, 'evidence': sorted({str(jid) for stage in forecast.get('by_stage', []) for jid in stage.get('evidence', [])}),
                          'currency': north.get('currency')})
    return {'won': won, 'forecast': forecasts, 'baseline': snapshot.get('north_star', {}).get('baseline'),
            'currency': currency, 'forecast_label': '30-day forecast issued that week'}


def funnel_fields(snapshot, jobs=None):
    """Six observed stages from one application cohort; mature KPI rows stay separate."""
    jobs = pipeline.load() if jobs is None else jobs
    now = timestamp(snapshot['generated_at'])
    today = now.astimezone(local_zone()).date()
    bounds = span(today, 28)
    entered = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and inside(event(job, 'applied'), bounds)]
    definitions = (('applied', 'Applied', 'reply_rate'), ('replied', 'Replied', 'reply_to_call'),
                   ('call_booked', 'Call booked', 'booked_to_held'), ('call_held', 'Call held', 'held_to_proposal'),
                   ('proposal_sent', 'Proposal sent', 'proposal_to_won'), ('won', 'Won', 'won_value'))
    stages, prior = [], entered
    for index, (event_name, label, key) in enumerate(definitions):
        if index == 0: reached = prior
        else:
            previous_event = definitions[index - 1][0]
            reached = [job for job in prior if event(job, event_name) and event(job, previous_event) <= event(job, event_name) <= now]
        metric = snapshot['kpis'][key]
        stages.append({'key': key, 'label': label, 'count': len(reached), 'k': metric['k'], 'n': metric['n'],
            'value': metric['value'], 'conversion_text': f"{metric['k']} of {metric['n']} · mature KPI cohort" if key != 'won_value' else 'New contract value uses its own weekly period',
            'loss': len(prior) - len(reached) if index else None, 'loss_label': 'Not yet advanced along this path',
            'state': metric['state'], 'insight': metric.get('insight'), 'period': period(bounds),
            'metric_period': metric.get('entry_period') or snapshot.get('periods', {}).get('outcome'),
            'evidence': ids(reached), 'metric': metric, 'flow_note': 'Application entry cohort; observed stage counts, not mature conversion losses.'})
        stages[-1].update(name=SCORECARD_NAMES.get(key, label), lost_count=len(prior) - len(reached) if index else None, loss_evidence=ids([job for job in prior if job not in reached]), focus={'reason': snapshot['verdict'].get('sentence')} if snapshot['verdict'].get('kpi') == key else None)
        if metric['state'] == 'missing': stages[-1].update(count=None, lost_count=None, loss=None)
        prior = reached
    focus_key = snapshot['verdict'].get('kpi')
    focus_key = next((key for key, levers in FEEDING_LEVERS.items() if focus_key in levers), focus_key)
    for index, stage in enumerate(stages):
        following = stages[index + 1] if index + 1 < len(stages) else None
        difference = sorted(set(stage['evidence']) - set(following['evidence'])) if following else []
        stage.update(loss_evidence=difference, loss=len(difference) if following and stage['count'] is not None and following['count'] is not None else None, lost_count=len(difference) if following and stage['count'] is not None and following['count'] is not None else None, focus={'reason': snapshot['verdict'].get('sentence')} if stage['key'] == focus_key else None)
    all_wins = [job for job in entered if event(job, 'won') and event(job, 'applied') <= event(job, 'won') <= now]
    terminal_ids = set(ids(prior))
    bypass = [job for job in all_wins if str(job['id']) not in terminal_ids]
    inbound = []
    for key in ('invite_to_call', 'offer_to_contract'):
        metric = snapshot['kpis'][key]
        inbound.append({'key': key, 'label': metric['label'], 'count': metric['n'], 'k': metric['k'], 'n': metric['n'],
            'value': metric['value'], 'conversion_text': f"{metric['k']} of {metric['n']} · {metric['horizon_days']}-day follow-up",
            'loss': metric['n'] - metric['k'], 'loss_label': 'Did not advance within the fixed horizon', 'state': metric['state'],
            'insight': metric.get('insight'), 'period': metric['entry_period'], 'evidence': metric['evidence'], 'metric': metric})
    stages[-1]['bypass_wins'] = {'count': len(bypass), 'evidence': ids(bypass), 'note': 'Won without traversing every observed stage.'}
    return {'outbound': stages, 'inbound': inbound}


def proposal_context(jobs, today):
    """Observed flags are contextual; unread flags never imply no client view."""
    rows = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and inside(event(job, 'applied'), span(today, 28))]
    viewed = [job for job in rows if timestamp(job.get('proposal_viewed_at')) or (job.get('proposal_viewed') or {}).get('value') is True]
    checked = [job for job in rows if job in viewed or isinstance((job.get('proposal_viewed') or {}).get('value'), bool)]
    insights = [job for job in rows if isinstance(job.get('proposal_insights'), dict) and isinstance(job['proposal_insights'].get('data'), dict)]
    complete = bool(rows) and len(checked) == len(rows)
    return {'applied_to_viewed': {'k': len(viewed) if checked else None, 'n': len(rows),
        'value': rounded(100 * len(viewed) / len(rows)) if complete else None,
        'checked_n': len(checked), 'unknown_n': len(rows) - len(checked),
        'state': 'observed' if complete else 'unknown', 'period': period(span(today, 28)),
        'label': 'Applied → observed viewed flag', 'evidence': ids(viewed),
        'note': 'Persistent positive flag observed by Upwork polling; unknown flags are not zero, and this is not the actual view timestamp.'},
        'proposal_insights': {'checked_n': len(insights), 'unknown_n': len(rows) - len(insights),
            'evidence': ids(insights), 'source': 'upwork-proposal',
            'note': 'Post-submission competition and client activity are saved on these leads; open a lead for its source context.'}}


def finish_views(result, jobs, history, today, now=None):
    stage_keys = {'applied': 'reply_rate', 'replied': 'reply_to_call', 'call': 'proposal_to_won', 'offer': 'offer_to_contract'}
    for row in result['forecast']['by_stage']:
        kpi = result['kpis'][stage_keys[row['stage']]]
        if kpi['baseline_phase'] or kpi['state'] in ('missing', 'undecided'):
            row.update(own_rate=None, expected=None)
    result['forecast']['next_30_days'] = rounded(sum(row['expected'] for row in result['forecast']['by_stage'])) if all(row['expected'] is not None for row in result['forecast']['by_stage']) else None
    result['todos'] = lead_todos(jobs, today, result['goals_next'])
    result['call_to_won'] = call_to_won(jobs, today)
    for key in ('speed_10min', 'proposal_on_time'):
        if result['kpis'][key].get('unknown_n', 0):
            result['coverage']['missing'].append({'source': 'frozen posting age' if key == 'speed_10min' else 'call end time', 'blocks': [key], 'how_to_supply': 'Supply the verified posting time and application time.' if key == 'speed_10min' else 'Paste the call end timestamp or complete call duration.'})
    result['conversation_review'] = conversation_reviews(jobs, today)
    for thread in result['conversation_review']['threads']:
        if not thread['read']:
            result['coverage']['missing'].append({'source': 'messages or review:' + thread['lead_id'], 'blocks': ['conversation_review'], 'how_to_supply': 'Read the complete Upwork thread and record its three quoted content checks.'})
    result['funnel_score'] = funnel_score(result, history)
    result['community_card'] = community_card(jobs, today, result['kpis'], result['goals_review'], result['week'], result['streak_weeks'], now)
    coverage = result['reviews']['call'].get('coverage', [])
    points = {str(row['point']): rounded(100 * row['met'] / row['n']) if row['n'] else None for row in coverage}
    current = {'week': result['week'], 'points': {str(index): points.get(str(index)) for index in range(1, 10)},
               'calls': sum(item.get('reviewable', False) for item in result['reviews']['call'].get('rubric', []))}
    result['call_rubric_weeks'] = (result['call_rubric_weeks'] + [current])[-8:]
    result['badges'] = badge_results(result, jobs, history, today)
    top = {}
    for badge in result['badges']:
        if badge['badge'] not in top or TIERS.index(badge['tier']) > TIERS.index(top[badge['badge']]['tier']):
            top[badge['badge']] = badge
    result['community_card']['top_badges'] = sorted(top.values(), key=lambda row: (-TIERS.index(row['tier']), row['badge']))[:5]
    new = [row for row in result['badges'] if row['new']]
    result['community_card']['new_badge'] = max(new, key=lambda row: (TIERS.index(row['tier']), row['badge']), default=None)
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in coverage_sources(result['coverage'])):
        for row in result.get('daily_applications', []): row['count'] = None
    result['presentation'] = presentation_fields(result)
    result['community_card']['funnel_score'] = copy.deepcopy(result['funnel_score'])
    result['presentation']['scorecard'] = scorecard_fields(result, jobs, history, today)
    result['presentation']['money_chart'] = money_chart(result, history)
    result['presentation']['voyage'] = voyage_fields(result, history)
    result['presentation']['funnel'] = funnel_fields(result, jobs)
    result['stage_context'] = proposal_context(jobs, today)
    result['presentation']['funnel']['outbound'][0]['view_context'] = result['stage_context']['applied_to_viewed']
    result['daily_voyage'] = daily_voyage(jobs, today)
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in coverage_sources(result['coverage'])):
        result['daily_voyage'].update(applications=None, remaining=None, complete=None, state='unknown')
    result['quests'] = quest_progress(result, jobs, today)
    result['call_cards'] = call_cards(result, jobs)
    result['conversations'] = conversations_fields(result, jobs)
    result['presentation']['progress_strip'] = progress_strip(result)
    result['presentation']['goal_cards'] = goal_cards(result)
    return result


def gap_fields(history, today):
    current = today - dt.timedelta(days=today.weekday())
    current_iso = current.isocalendar(); current_week = f'{current_iso.year}-W{current_iso.week:02d}'
    latest = max((row for row in history if row.get('week', '') < current_week), key=lambda row: row['week'], default=None)
    if latest is None: return {'weeks_missed': 0, 'since': None}
    previous = badge_ledger._week_date(latest['week'])
    return {'weeks_missed': max(0, (current - previous).days // 7 - 1) if previous else 0,
            'since': latest.get('generated_at') or (previous.isoformat() if previous else None)}


_RECONSTRUCTING = contextvars.ContextVar('analytics_reconstructing', default=False)


@member_clock
def compute_catchup(today=None, jobs=None, now=None):
    """Build one snapshot for each missed full ISO week. No source or ledger writes."""
    run_at = run_timestamp(today, now); today = run_at.date(); jobs = pipeline.load() if jobs is None else jobs
    history = read_lines('analytics-history.jsonl'); gap = gap_fields(history, today)
    if not gap['weeks_missed']: return []
    monday = today - dt.timedelta(days=today.weekday()); snapshots = []
    token = _RECONSTRUCTING.set(True)
    try:
        for back in range(gap['weeks_missed'], 0, -1):
            start = monday - dt.timedelta(weeks=back); end = start + dt.timedelta(weeks=1)
            cutoff = dt.datetime.combine(end, dt.time(), local_zone())
            iso = start.isocalendar(); week = f'{iso.year}-W{iso.week:02d}'
            result = compute(end, jobs=jobs, now=cutoff, history_override=history + snapshots)
            result.update(week=week, gap=copy.deepcopy(gap))
            for source, blocks, supply in (
                ('point-in-time pipeline', ['pipeline', 'forecast'], 'Historical current statuses cannot be reconstructed from the saved source.'),
                ('point-in-time proposal status', ['proposal_viewed'], 'Historical proposal flags are unknown; reconnect Upwork for current flags.'),
                ('point-in-time Connects balance', ['connects_balance'], 'Only dated Connects transactions can be reconstructed.')):
                result['coverage']['missing'].append({'source': source, 'blocks': blocks, 'how_to_supply': supply})
            for row in result['pipeline'] if isinstance(result['pipeline'], list) else []: row['count'] = None
            if isinstance(result['pipeline'], dict):
                for rows in result['pipeline'].values():
                    for row in rows if isinstance(rows, list) else []:
                        for key, value in list(row.items()):
                            if number(value): row[key] = None
                        row['state'] = 'unknown'
            result['forecast']['next_30_days'] = None
            for row in result['forecast']['by_stage']: row.update(own_rate=None, expected=None)
            result['report'] = 'Catch-up snapshot from dated history. Point-in-time facts are unknown.'
            finish_views(result, jobs, history + snapshots, end, cutoff)
            result['forecast']['next_30_days'] = None
            for row in result['forecast']['by_stage']: row.update(own_rate=None, expected=None)
            result['presentation']['money_chart'] = money_chart(result, history + snapshots)
            result['stage_context']['applied_to_viewed'].update(k=None, value=None, state='unknown', checked_n=0)
            snapshots.append(result)
    finally:
        _RECONSTRUCTING.reset(token)
    return snapshots


@member_clock
def compute(today=None, jobs=None, now=None, history_override=None):
    run_at = run_timestamp(today, now)
    today = run_at.date()
    jobs = pipeline.load() if jobs is None else jobs
    kpis, north = calculate(jobs, today, now=run_at)
    baseline, _ = calculate(jobs, today - dt.timedelta(days=28), now=run_at)
    own_weeks = [calculate(jobs, today - dt.timedelta(weeks=index), now=run_at)[0]['won_value']['value'] for index in range(1, 5)]
    north['baseline'] = statistics.mean(own_weeks) if all(number(value) for value in own_weeks) else None
    for key, row in kpis.items():
        row['baseline'] = north['baseline'] if key == 'won_value' else baseline[key]['value']
        row['delta'] = rounded(row['value'] - row['baseline']) if number(row['value']) and number(row['baseline']) else None
        if key in FUNNEL:
            row['baseline_k'], row['baseline_n'] = baseline[key]['k'], baseline[key]['n']
            lo, hi = difference_bounds(baseline[key], row)
            row['delta_low'], row['delta_high'] = rounded(lo), rounded(hi)
            row['delta_pp'] = row['delta']
            row['trend'] = 'up' if number(lo) and lo > 0 else 'down' if number(hi) and hi < 0 else 'undecided'
        if key in ('won_value', 'value_per_100_connects') and row['state'] != 'missing' and number(row['value']):
            if number(row['target']):
                row['state'] = 'pass' if row['value'] >= row['target'] else 'fail'
            elif number(row['baseline']):
                row['state'] = 'undecided'
                row['reason'] = 'Descriptive money change; no inferential sales-performance claim.'
    history = read_lines('analytics-history.jsonl') if history_override is None else copy.deepcopy(history_override)
    original_gap = gap_fields(history, today)
    if history_override is None and not _RECONSTRUCTING.get() and original_gap['weeks_missed']:
        history += compute_catchup(today, jobs, run_at)
    iso = today.isocalendar()
    week = f'{iso.year}-W{iso.week:02d}'
    monday = today - dt.timedelta(days=today.weekday())
    previous_weeks = []
    for index in range(7, 0, -1):
        old = (monday - dt.timedelta(weeks=index)).isocalendar()
        previous_weeks.append(f'{old.year}-W{old.week:02d}')
    by_week = {row['week']: row for row in history if row.get('week') < week}
    history = list(by_week.values())
    apply_ladders(kpis, history, today, jobs, run_at)
    weekly_finished, _ = calculate(jobs, today, now=run_at, cohort_days=7)
    for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won'):
        kpis[key]['weekly_opportunities'] = weekly_finished[key]['n']
    for key, row in kpis.items():
        row['history'] = [by_week.get(old, {}).get('kpis', {}).get(key, {}).get('value') for old in previous_weeks] + [row['value']]
    north['history'] = [by_week.get(old, {}).get('north_star', {}).get('value') for old in previous_weeks] + [north['value']]
    reviews = goal_reviews(jobs, today, run_at)
    kpis['goal_effect'].update(k=sum(row['effect'] == 'worked' for row in reviews), n=len(reviews), value=None, evidence=sorted({jid for row in reviews for jid in row['outcome_evidence']}))
    kpis['goal_done'].update(k=0, n=len(reviews), value=0, target=len(reviews), target_text=f'{len(reviews)} commitments', state='undecided', reason='Execution evidence must be reviewed.')
    coverage, synced_at = source_coverage(jobs, today, run_at)
    streak = badge_ledger.streak(history, week=week, current={'week': week})
    result = {'week': week, 'generated_at': run_at.isoformat(),
            'window': period(span(today, 28)), 'periods': {'activity': period(span(today, 7)), 'cohort': period(span(today, 28)), 'outcome': period(span(today, 7)), 'synced_at': synced_at},
            'coverage': coverage_fields(coverage, jobs, today), 'pipeline': pipeline_counts(jobs, today), 'kpis': kpis,
            'verdict': verdict(kpis), 'verdict_history': [{'week': old, 'kpi': by_week[old].get('verdict', {}).get('kpi'), 'stage': by_week[old].get('verdict', {}).get('stage')} for old in previous_weeks if old in by_week],
            'north_star': north, 'goals_review': reviews, 'goals_next': [], 'findings': [],
            'reviews': {name: {'fix': '', 'example': '', 'evidence_lead_ids': [], 'goal_ref': None} for name in ('application', 'conversation', 'call', 'proposal')},
            'streak_weeks': streak, 'report': '', 'summary': [], 'gap': original_gap}
    saved_calls = []
    for job in jobs:
        review = job.get('call_review')
        if not isinstance(review, dict) or not review.get('reviewable') or not inside(event(job, 'call_held'), span(today, 28)) or _RECONSTRUCTING.get(): continue
        text = read_source(pipeline.jobs_dir() / str(job['id']) / 'call.md') or ''
        stats = call_stats.analyze(text)
        if stats.get('transcript_complete') and stats.get('member_attributed'):
            saved_calls.append(dict(review, lead_id=str(job['id'])))
    if saved_calls:
        review = result['reviews']['call']; review.update(rubric=saved_calls, evidence_lead_ids=[item['lead_id'] for item in saved_calls], fix=saved_calls[-1].get('fix', ''), example=saved_calls[-1].get('example', ''))
        review['coverage'] = rubric_coverage(saved_calls, today, 'call')
        kpis['call_review'].update(k=len(saved_calls), n=len(saved_calls), value='reviewed points', state='pass', evidence=review['evidence_lead_ids'], reason=None)
    result.update(explore_fields(jobs, today, history))
    return finish_views(result, jobs, history, today, run_at)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_goals(value):
    require(isinstance(value, dict) and set(value) == {'week', 'goals'}, 'Goals need week and goals only.')
    require(bool(re.fullmatch(r'\d{4}-W\d{2}', str(value['week']))), 'Goals need an ISO week.')
    dt.date.fromisocalendar(int(value['week'][:4]), int(value['week'][6:]), 1)
    goals = value['goals']
    require(isinstance(goals, list) and 1 <= len(goals) <= 3, 'Agree one to three goals.')
    keys = {'stage', 'kpi', 'change', 'start', 'primary', 'cue', 'action', 'fallback', 'review_on'}
    for goal in goals:
        require(isinstance(goal, dict) and set(goal) == keys, 'Each goal needs stage, kpi, change, start, primary, cue, action, fallback and review_on.')
        require(goal['kpi'] in LABELS and goal['stage'] == LABELS[goal['kpi']] and all(isinstance(goal[name], str) and goal[name].strip() for name in ('stage', 'change', 'cue', 'action', 'fallback')), 'Goals need a known KPI and nonempty commitments.')
        start, review_on = dt.date.fromisoformat(goal['start']), dt.date.fromisoformat(goal['review_on'])
        require(review_on >= start and isinstance(goal['primary'], bool), 'Goals need ordered start/review dates and boolean primary.')
    require(len({goal['stage'].strip().casefold() for goal in goals}) == len(goals) and len({goal['kpi'] for goal in goals}) == len(goals), 'Two goals cannot share one stage or KPI.')
    require(sum(goal['primary'] for goal in goals) == 1, 'Exactly one goal must be primary.')
    return value


def privacy(value, jobs=None):
    """Reject raw-client fields and known source strings, except member examples."""
    jobs = pipeline.load() if jobs is None else jobs
    forbidden = {'client_name', 'client_text', 'client', 'thread', 'messages', 'title', 'description', 'contract_client', 'quote'}
    source_text = set()
    client_text = set()
    for job in jobs:
        for key in ('client_name', 'contract_client', 'title', 'description'):
            if isinstance(job.get(key), str) and job[key].strip():
                source_text.add(job[key].strip())
                if key in ('title', 'description'):
                    client_text.add(job[key].strip())
        client = job.get('client')
        if isinstance(client, str) and client.strip():
            source_text.add(client.strip())
        if isinstance(client, dict) and isinstance(client.get('name'), str):
            source_text.add(client['name'])
    for path in pipeline.jobs_dir().glob('*/thread.json'):
        try: thread = json.loads(read_source(path) or '{}')
        except ValueError: thread = {}
        for item in thread.get('messages') or []:
            node = item.get('node', item)
            side = str(node.get('from_side') or node.get('from') or '').lower()
            if side in ('client', 'them'):
                if isinstance(node.get('name'), str) and node['name'].strip():
                    source_text.add(node['name'].strip())
                for key in ('text', 'message', 'content'):
                    if isinstance(node.get(key), str) and node[key].strip():
                        source_text.add(node[key].strip())
                        client_text.add(node[key].strip())
    for path in pipeline.jobs_dir().glob('*/call.md'):
        text = path.read_text(encoding='utf-8')
        member = re.search(r'^Member:\s*(.+)$', text, re.M | re.I)
        own = member[1].strip().casefold() if member else None
        for match in re.finditer(r'^([^:\n]{1,80}):\s*(.+)$', text, re.M):
            speaker, turn = match[1].strip(), match[2].strip()
            if speaker.casefold() in ('duration', 'member', 'call at', 'date', 'recorder', 'speakers', 'complete', 'language') or speaker.casefold() == own:
                continue
            source_text.add(turn)
            client_text.add(turn)
            if speaker.casefold() not in ('client', 'them', 'speaker 1', 'speaker 2'):
                source_text.add(speaker)
    def walk(item, path=()):
        # Private call cards/rubrics contain verified local quotes; never sent to community.
        if path == ('conversations',) or path == ('call_cards',) or path == ('reviews', 'call', 'rubric') or path == ('conversation_review',) or len(path) == 4 and path[:2] == ('presentation', 'scorecard') and path[3] == 'split':
            return
        if len(path) == 3 and path[0] == 'reviews' and path[2] == 'example':
            require(isinstance(item, str), 'Review examples need the member’s own wording.')
            require(not any(text.casefold() in item.casefold() for text in client_text), 'Review examples cannot quote the client’s wording.')
            return
        if isinstance(item, dict):
            require(not (set(item) & forbidden), 'Snapshot contains raw client fields at ' + '.'.join(map(str, path)) + ': ' + ', '.join(sorted(set(item) & forbidden)))
            for key, child in item.items():
                walk(child, path + (key,))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, path + (index,))
        elif isinstance(item, str):
            require(not any(text.casefold() in item.casefold() for text in source_text if text), 'Stored text contains a known client name or source text.')
    walk(value)


def ledger_transaction(function):
    @functools.wraps(function)
    def locked(*args, **kwargs):
        directory = pipeline.data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            return function(*args, **kwargs)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
    return locked


def atomic_lines(name, rows):
    path = data_path(name)
    encoded = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows)
    fd, temporary = tempfile.mkstemp(prefix='.' + name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


@ledger_transaction
def add_goals(value):
    validate_goals(value)
    privacy(value)
    rows = read_lines('goals.jsonl')
    require(not any(row.get('week') == value['week'] for row in rows), 'Goals already exist for this ISO week.')
    atomic_lines('goals.jsonl', rows + [value])
    return value


def rubric_coverage(rubric, today, name):
    require(isinstance(rubric, list), 'Rubric must be a list of lead judgments.')
    seen = set()
    jobs_by_id = {str(job['id']): job for job in pipeline.load()} if name == 'application' else {}
    uma_counts = {}
    counts = {point: {'point': point, 'met': 0, 'partly': 0, 'missing': 0, 'not_needed': 0, 'n': 0} for point in range(1, 10 if name == 'call' else 8)}
    for item in rubric:
        allowed = {'lead_id', 'reviewable', 'points', 'moments', 'fix', 'example', 'next_step', 'next_message', 'free_read'} | ({'agreed_step'} if name == 'call' else set())
        require(isinstance(item, dict) and {'lead_id', 'reviewable', 'points'} <= set(item) and set(item) <= allowed, 'Call rubric needs lead_id, reviewable and points.')
        require(item['lead_id'] not in seen and isinstance(item['reviewable'], bool), 'Call rubric needs unique leads and boolean reviewable.')
        seen.add(item['lead_id'])
        for field, limit in (('next_message', 100), ('free_read', 180 if name == 'call' else 150)):
            if field in item: short_text(item[field], limit, field, optional=True)
        path = pipeline.jobs_dir() / str(item['lead_id']) / ('call.md' if name == 'call' else 'application.sent.md')
        text = path.read_text(encoding='utf-8') if path.is_file() else ''
        utterances = '\n'.join(match[2] for match in re.finditer(r'^([^:\n]+):\s*(.+)$', text, re.M) if match[1].strip().lower() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language'))
        speakers = {match[1].strip() for match in re.finditer(r'^([^:\n]+):\s*\S', text, re.M) if match[1].strip().lower() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language')}
        if name == 'call':
            stats = call_stats.analyze(text)
            require(not item['reviewable'] or (len(speakers) >= 2 and stats.get('transcript_complete') is True and stats.get('member_attributed') is True), 'A reviewable call needs complete speaker labels and member identity.')
            require(item['reviewable'] or not any(str(item.get(field) or '').strip() for field in ('free_read', 'agreed_step', 'next_message')), 'An unreviewable call cannot have coaching text.')
        if name == 'call':
            require(isinstance(item.get('moments', []), list) and len(item.get('moments', [])) <= 3, 'At most three call moments.')
            for moment in item.get('moments', []):
                require(isinstance(moment, dict) and set(moment) == {'quote', 'better_wording'} and all(isinstance(v, str) and v.strip() for v in moment.values()) and moment['quote'] in utterances, 'Call moments need a local quote and better wording.')
            for key in ('fix', 'example', 'next_step', 'agreed_step'):
                require(key not in item or item[key] is None and key == 'next_step' or isinstance(item[key], str), 'Call card text must be a string.')
        points = item['points']
        require(isinstance(points, list), 'Call points must be a list.')
        if not item['reviewable']:
            require(not points, 'An unreviewable call cannot have point judgments.')
            continue
        job = jobs_by_id.get(str(item['lead_id']), {})
        uma = name == 'application' and job.get('application_modality') == 'uma'
        required = set(range(1, 4 if uma else 10 if name == 'call' else 7))
        got = {row.get('point') for row in points}
        require(got == required or (name == 'application' and not uma and got == required | {7}),
                'Review all nine call points; Uma requires its three answer/video points; text requires six application points plus optional Loom.')
        require(len(points) == len(got), 'Review each rubric point once.')
        if name == 'application' and (not path.is_file() or job.get('application_sent_verified') is not True):
            continue
        if uma and not uma_counts:
            uma_counts = {point: {'point': point, 'modality': 'uma', 'met': 0, 'partly': 0, 'missing': 0, 'not_needed': 0, 'n': 0} for point in range(1, 4)}
        for row in points:
            require({'point', 'state'} <= set(row) and set(row) <= ({'point', 'state', 'quote', 'reason'} if name == 'call' else {'point', 'state'}) and row['state'] in (('met', 'partly', 'missing', 'not needed') if name == 'call' else ('met', 'partly', 'missing')), 'Call point needs point and state only; quotes stay in lead evidence.')
            if name == 'call' and row['state'] == 'not needed':
                require(isinstance(row.get('reason'), str) and row['reason'].strip(), 'Every not needed call point needs a reason.')
            if name == 'call' and row.get('quote') is not None:
                require(isinstance(row['quote'], str) and row['quote'].strip() and row['quote'] in utterances, 'Call quote must occur in local call evidence.')
            target = (uma_counts if uma else counts)[row['point']]
            target[row['state'].replace(' ', '_')] += 1
            target['n'] += row['state'] != 'not needed'
    history = read_lines('analytics-history.jsonl')
    monday = today - dt.timedelta(days=today.weekday())
    by_week = {row['week']: row for row in history}
    result = list(counts.values()) + list(uma_counts.values())
    for row in result:
        point = row['point']
        values = []
        for back in range(7, 0, -1):
            iso = (monday - dt.timedelta(weeks=back)).isocalendar()
            week = f'{iso.year}-W{iso.week:02d}'
            old = next((item for item in by_week.get(week, {}).get('reviews', {}).get(name, {}).get('coverage', []) if item.get('point') == point and item.get('modality', 'text') == row.get('modality', 'text')), None)
            values.append(old['met'] / old['n'] * 100 if old and old['n'] else None)
        row['history'] = values + [row['met'] / row['n'] * 100 if row['n'] else None]
    return result


def call_coverage(rubric, today):
    return rubric_coverage(rubric, today, 'call')


def short_text(value, words, label, optional=False):
    require(isinstance(value, str) and (optional or bool(value.strip())) and len(value.split()) <= words,
            f'{label} needs at most {words} words.')
    return value


def validate_reference(reference):
    require(isinstance(reference, dict) and set(reference) == {'value', 'population', 'definition', 'source', 'date'} and
            number(reference['value']) and all(isinstance(reference[key], str) and reference[key].strip() for key in ('population', 'definition', 'source', 'date')),
            'External reference needs value, population, definition, source and date.')
    dt.date.fromisoformat(reference['date'])
    # Metadata must be grounded in a repository reference, not a generated citation.
    texts = [path.read_text(encoding='utf-8') for path in (ROOT / 'references').rglob('*.md')]
    require(any(all(str(reference[key]).casefold() in text.casefold() for key in ('population', 'definition', 'source', 'date')) and
                    re.search(r'(?<![\d.])' + re.escape(f"{reference['value']:g}") + r'(?![\d.])', text) for text in texts),
            'External reference must match a saved references/ benchmark including value and metadata.')
    return reference


PUBLIC_QUESTIONS = ("How do you practise this week's focus?", "What helped you improve this stage?", "How do you handle this commitment?")


def public_source_fragments(jobs):
    """Known identities and confidential source fragments; never exported."""
    forbidden = set()
    def collect(item, key=''):
        if isinstance(item, dict):
            for field, value in item.items(): collect(value, field)
        elif isinstance(item, list):
            for value in item: collect(value, key)
        elif isinstance(item, str) and key in ('name', 'client', 'client_name', 'contract_client', 'title', 'description', 'text', 'content', 'message') and item.strip():
            forbidden.add(item.strip().casefold())
    for job in jobs: collect(job)
    for path in pipeline.jobs_dir().glob('*/thread.json'):
        try: thread = json.loads(read_source(path) or '{}')
        except ValueError: thread = {}
        for item in thread.get('messages', []):
            node = item.get('node', item)
            side = str(node.get('from_side') or node.get('from') or '').casefold()
            if side in ('client', 'them'): collect(node)
    for path in pipeline.jobs_dir().glob('*/call.md'):
        text = path.read_text()
        own = re.search(r'^Member:\s*(.+)$', text, re.M | re.I)
        own = own[1].strip().casefold() if own else None
        for match in re.finditer(r'^([^:\n]{1,80}):\s*(.+)$', text, re.M):
            speaker, turn = match[1].strip(), match[2].strip()
            if speaker.casefold() in ('duration', 'member', 'call at', 'date', 'recorder', 'speakers', 'complete', 'language') or speaker.casefold() == own: continue
            forbidden.add(turn.casefold())
            if speaker.casefold() not in ('client', 'them', 'speaker 1', 'speaker 2'): forbidden.add(speaker.casefold())
    # A confidential excerpt is still client text when the full turn was not copied.
    fragments = set(forbidden)
    for text in forbidden:
        words = text.split()
        fragments.update(' '.join(words[index:index + 3]) for index in range(max(0, len(words) - 2)))
    return fragments


def safe_public_text(text, jobs, maximum=14):
    if not isinstance(text, str) or not text.strip() or len(text.split()) > maximum:
        return False
    lowered = text.casefold()
    if any(source in lowered for source in public_source_fragments(jobs)):
        return False
    return not re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d ()-]{7,}\d)', text)


def validate_community_card(card, jobs=None):
    jobs = pipeline.load() if jobs is None else jobs
    keys = {'member_name', 'week', 'applications', 'streak_weeks', 'goals_done', 'goals', 'next_focus', 'question',
            'new_badge', 'top_badges', 'reply_rate', 'reply_to_call', 'call_to_won',
            'first_reply_median_min', 'first_reply_target_min', 'biggest_improvement', 'won_value', 'booked_to_held', 'proposal_to_won', 'funnel_score'}
    require(isinstance(card, dict) and keys - {'member_name'} <= set(card) <= keys, 'Public card has unknown or missing fields.')
    require(card.get('member_name') is None or card['member_name'] == public_member_name(), 'Public member identity must derive from me.md.')
    def numeric(value): return value is None or number(value)
    require(re.fullmatch(r'\d{4}-W\d{2}', str(card['week'])), 'Invalid public week.')
    for key in ('applications', 'streak_weeks', 'first_reply_median_min', 'first_reply_target_min', 'won_value'):
        require(numeric(card[key]), 'Public numeric field must be a finite number or null.')
    require(re.fullmatch(r'\d+/\d+', str(card['goals_done'])), 'Invalid goal aggregate.')
    require(card['next_focus'] is None or card['next_focus'] in LABELS.values(), 'Public focus must be a fixed stage label.')
    approved = set()
    for row in read_lines('goals.jsonl'):
        for goal in row.get('goals', []): approved.add(' '.join(goal['change'].split()[:6]))
    for row in read_lines('analytics-history.jsonl'):
        for goal in row.get('goals_next', []): approved.add(' '.join(goal['change'].split()[:6]))
    library = ROOT / 'references/goal-library.md'
    if library.is_file():
        approved.update(' '.join(line.strip(' -|').split()[:6]) for line in library.read_text().splitlines() if line.strip())
    require(isinstance(card['goals'], list) and len(card['goals']) <= 3, 'Public goals must be the latest agreed set of at most three commitments.')
    for goal in card['goals']:
        require(isinstance(goal, dict) and set(goal) == {'text', 'done', 'k', 'n', 'state'} and goal['text'] in approved and
                isinstance(goal['done'], bool) and numeric(goal['k']) and numeric(goal['n']) and
                goal['state'] in ('unverified', 'no opportunity', 'complete', 'partial', 'undone'), 'Public goals need approved member/library text and computed execution.')
    for key in ('reply_rate', 'reply_to_call', 'call_to_won', 'booked_to_held', 'proposal_to_won'):
        rate = card[key]
        require(isinstance(rate, dict) and set(rate) == {'value', 'target', 'rung_reached', 'of', 'trend', 'k', 'n', 'state', 'horizon_days', 'entry_period', 'outcome_label', 'progression'}, 'Unknown public rate fields.')
        require(all(numeric(rate[field]) for field in ('value', 'target', 'rung_reached', 'of', 'k', 'n', 'horizon_days')) and
                rate['trend'] in ('up', 'down', 'undecided') and rate['state'] in ('pass', 'fail', 'missing', 'undecided'), 'Invalid public rate values.')
        require(rate['outcome_label'] == PUBLIC_OUTCOME_LABELS[key], 'Public outcome definition must use its fixed label.')
        require(rate['target'] == {'reply_rate': 20, 'reply_to_call': 50, 'call_to_won': 30, 'booked_to_held': 90, 'proposal_to_won': 30}[key] and rate['of'] == 3 and
                rate['horizon_days'] == {'reply_rate': 7, 'reply_to_call': 14, 'call_to_won': 28, 'booked_to_held': 2, 'proposal_to_won': 21}[key], 'Public targets and maturity are fixed for every member.')
        progression = rate['progression']
        require(progression is None or (isinstance(progression, dict) and set(progression) == {'booked_calls', 'held_calls', 'offer_or_contract_without_call'} and
                all(number(value) and value >= 0 for value in progression.values())), 'Public progression must contain fixed numeric counts only.')
        require(isinstance(rate['entry_period'], dict) and set(rate['entry_period']) == {'start', 'end'} and
                all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)) for value in rate['entry_period'].values()), 'Invalid public entry period.')
    entry_periods = [card[key]['entry_period'] for key in ('reply_rate', 'reply_to_call', 'call_to_won')]
    require(all(value == entry_periods[0] for value in entry_periods) and
            (dt.date.fromisoformat(entry_periods[0]['end']) - dt.date.fromisoformat(entry_periods[0]['start'])).days == 27,
            'Public conversion entries must share one complete 28-day window.')
    improvement = card['biggest_improvement']
    require(improvement is None or (isinstance(improvement, dict) and {'kpi', 'from', 'to'} <= set(improvement) <= {'kpi', 'from', 'to', 'reason'} and
            improvement['kpi'] in ('reply_rate', 'reply_to_call', 'call_to_won') and numeric(improvement['from']) and numeric(improvement['to'])), 'Invalid public improvement.')
    require(isinstance(card['top_badges'], list), 'Public badges need a list.')
    for badge in card['top_badges'] + ([card['new_badge']] if card['new_badge'] else []):
        require(isinstance(badge, dict) and set(badge) == {'badge', 'tier', 'earned_week', 'new', 'progress_to_next'} and
                badge['badge'] in BADGE_NAMES and badge['tier'] in TIERS and re.fullmatch(r'\d{4}-W\d{2}', str(badge['earned_week'])) and
                isinstance(badge['new'], bool) and (badge['progress_to_next'] in ('All tiers earned', 'One standout moment', 'One qualifying week', 'One call with 9 of 9 points') or
                re.fullmatch(r'Lower bound at least \d+ %|\d+ of \d+ (weeks|proposals|invites|calls|wins|returns)', badge['progress_to_next'])), 'Unknown public badge content.')
    score = card['funnel_score']
    require(isinstance(score, dict) and set(score) == {'score', 'previous', 'parts', 'dropped', 'baseline_only'} and
            all(score[field] is None or number(score[field]) and 0 <= score[field] <= 100 for field in ('score', 'previous')) and
            isinstance(score['baseline_only'], bool) and isinstance(score['parts'], dict) and set(score['parts']) == {'habits', 'results'} and
            all(value is None or number(value) and 0 <= value <= 100 for value in score['parts'].values()) and
            isinstance(score['dropped'], list) and all(isinstance(row, dict) and set(row) == {'part', 'reason'} and row['part'] in LEVERS + ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won') and row['reason'] in ('unknown source', 'No eligible cases yet', 'Baseline not set') for row in score['dropped']), 'Public Funnel Score must contain bounded computed parts only.')
    # Goals remain a rejecting allowlist. Dynamic optional prose is dropped.
    prose = [goal['text'].casefold() for goal in card['goals']]
    require(not any(source in text for source in public_source_fragments(jobs) for text in prose), 'Public goals contain client source material.')
    require(all(safe_public_text(goal['text'], jobs, 6) for goal in card['goals']), 'Public goal text cannot contain URLs or contact details.')
    if card['question'] is not None and not safe_public_text(card['question'], jobs):
        card['question'] = None
    if improvement is not None and 'reason' in improvement and not safe_public_text(improvement['reason'], jobs):
        improvement.pop('reason')

    return card


def validate_summary(summary, snapshot):
    """Validate supplied coach prose; code neither writes a story nor judges a cause."""
    require(isinstance(summary, list) and (not summary or len(summary) == 3), 'Summary needs exactly three sentences, or an empty unknown state.')
    numbers = set()
    def collect(item):
        if number(item):
            numbers.add(f'{item:g}'); numbers.add(f'{item:,.0f}')
        elif isinstance(item, dict):
            for key, value in item.items():
                if key not in ('summary', 'report', 'call_cards', 'conversation_review', 'conversations', 'reviews'): collect(value)
        elif isinstance(item, list):
            for value in item: collect(value)
    collect(snapshot)
    for sentence in summary:
        require(isinstance(sentence, str) and sentence.strip() and len(sentence.split()) <= 18 and
                '\n' not in sentence and '\r' not in sentence and '\u2014' not in sentence and
                re.search(r'[A-Za-z]', sentence) and sentence.rstrip().endswith(('.', '!', '?')) and
                not re.search(r'[.!?]\s+[A-Z]', sentence), 'Each English summary sentence needs at most 18 words, one sentence, and no em dash.')
        for token in re.findall(r'(?<![\w])\d[\d,]*(?:\.\d+)?(?![\w])', sentence):
            normalized = token.replace(',', '')
            require(normalized in numbers or token in numbers, 'Summary numbers must occur in the computed snapshot.')
    return copy.deepcopy(summary)


def claude_fields(result, value):
    if 'summary' in value:
        result['summary'] = validate_summary(value['summary'], result)
    for key, supplied in value.get('kpis', {}).items():
        require(key in result['kpis'] and isinstance(supplied, dict), 'Unknown KPI insight.')
        if 'insight' in supplied:
            require(key in FUNNEL, 'Insights belong to funnel KPIs.')
            result['kpis'][key]['insight'] = short_text(supplied['insight'], 12, 'KPI insight')
        if 'external_reference' in supplied:
            require(key in FUNNEL, 'External benchmarks belong to funnel evidence only.')
            result['kpis'][key]['external_reference'] = copy.deepcopy(validate_reference(supplied['external_reference']))
        if 'market_line' in supplied:
            require(key in FUNNEL and 'external_reference' in result['kpis'][key], 'Market lines need a saved external benchmark.')
            line = short_text(supplied['market_line'], 8, 'Market line')
            reference = result['kpis'][key]['external_reference']
            require(reference['source'].casefold() in line.casefold() or
                    any(name.casefold() in reference['source'].casefold() and name.casefold() in line.casefold() for name in ('GigRadar', 'Upwork')),
                    'Market line must name its benchmark source.')
            require(re.search(r'(?<![\d.])' + re.escape(f"{reference['value']:g}") + r'(?![\d.])', line), 'Market line must preserve its benchmark value.')
            result['kpis'][key]['market_line'] = line
    if 'insights_top' in value:
        insights = value['insights_top']
        require(isinstance(insights, list) and len(insights) <= 3, 'At most three top insights.')
        for insight in insights:
            require(isinstance(insight, dict) and set(insight) == {'kind', 'text', 'target'} and
                    insight['kind'] in ('leak', 'driver', 'trend', 'habit', 'pipeline', 'learning', 'market'), 'Unknown insight kind or fields.')
            short_text(insight['text'], 12, 'Top insight')
            require(isinstance(insight['target'], dict) and set(insight['target']) == {'view', 'element'} and
                    all(isinstance(insight['target'][key], str) and insight['target'][key].strip() for key in ('view', 'element')), 'Insight needs a view and element drill-down target.')
        result['insights_top'] = copy.deepcopy(insights)
    if 'findings' in value:
        findings = value['findings']
        require(isinstance(findings, list), 'Findings need a list.')
        for finding in findings:
            require(isinstance(finding, dict) and {'sentence', 'action', 'observed', 'expected', 'n', 'strength', 'status'} <= set(finding) and
                    set(finding) <= {'sentence', 'action', 'kpi', 'stage', 'observed', 'expected', 'n', 'strength', 'status'} and
                    ('kpi' in finding or 'stage' in finding), 'Findings need structured evidence and a KPI or stage.')
            require('kpi' not in finding or finding['kpi'] in LABELS, 'Finding needs a known KPI.')
            require('stage' not in finding or finding['stage'] in LABELS.values(), 'Finding needs a known stage.')
            require(all(isinstance(finding[key], str) and finding[key].strip() for key in ('sentence', 'action')) and
                    all(finding[key] is None or number(finding[key]) for key in ('observed', 'expected')) and
                    isinstance(finding['n'], int) and not isinstance(finding['n'], bool) and finding['n'] >= 0 and
                    finding['strength'] in ('emerging', 'holding') and finding.get('status', 'finding') in ('finding', 'emerging', 'confirmed'),
                    'Finding evidence types or strength are invalid.')
        result['findings'] = copy.deepcopy(findings)
    card = value.get('community_card', {})
    require(isinstance(card, dict) and set(card) <= set(result['community_card']), 'Community card has unknown fields.')
    if set(card) == set(result['community_card']): validate_community_card(card)
    else: require(set(card) <= {'next_focus', 'question', 'biggest_improvement'}, 'Partial public overlays may change only focus/question and improvement reason.')
    if card.get('next_focus') is not None:
        require(card['next_focus'] in LABELS.values(), 'Community focus needs a known stage label.')
        result['community_card']['next_focus'] = card['next_focus']
    if card.get('question') is not None:
        result['community_card']['question'] = card['question'] if safe_public_text(card['question'], pipeline.load()) else None
    if card.get('biggest_improvement') is not None:
        supplied = card['biggest_improvement']
        original = result['community_card']['biggest_improvement']
        require(isinstance(supplied, dict) and set(supplied) <= {'kpi', 'from', 'to', 'reason'} and original is not None, 'Improvement needs a computed change.')
        require(all(supplied.get(key, original[key]) == original[key] for key in ('kpi', 'from', 'to')), 'Improvement numbers must come from compute.')
        if 'reason' in supplied and safe_public_text(supplied['reason'], pipeline.load()): original['reason'] = supplied['reason']
    return result


def prepare_snapshot(value, today=None, now=None):
    """Apply human judgments, deriving their numbers before the coaching conversation."""
    require(isinstance(value, dict), 'Review input needs one JSON object.')
    today = as_today(today or day(value.get('generated_at')))
    now = now or value.get('generated_at')
    result = compute(today, now=now)
    known_ids = {str(job['id']) for job in pipeline.load()}
    for name, review in value.get('reviews', {}).items():
        require(name in result['reviews'] and isinstance(review, dict), 'Unknown weekly review.')
        require({'fix', 'example', 'evidence_lead_ids', 'goal_ref'} <= set(review) and set(review) <= {'fix', 'example', 'evidence_lead_ids', 'goal_ref', 'rubric', 'coverage'}, 'Review needs fix, example, evidence_lead_ids and goal_ref; optional call rubric.')
        require(isinstance(review['fix'], str) and isinstance(review['example'], str) and isinstance(review['evidence_lead_ids'], list), 'Review text and evidence types are invalid.')
        require(set(review['evidence_lead_ids']) <= known_ids and len(set(review['evidence_lead_ids'])) == len(review['evidence_lead_ids']), 'Review evidence must be unique known lead ids.')
        result['reviews'][name] = copy.deepcopy(review)
        row = result['kpis'][name + '_review']
        complete = bool(review['fix'].strip() and review['evidence_lead_ids'])
        relevant = [job for job in pipeline.load() if str(job['id']) in review['evidence_lead_ids']]
        files = {'application': 'application.sent.md', 'conversation': 'thread.json', 'call': 'call.md', 'proposal': 'proposal.md'}
        supported = bool(relevant) and all((pipeline.jobs_dir() / str(job['id']) / files[name]).is_file() for job in relevant)
        if name == 'application': supported = supported and all(job.get('application_sent_verified') is True for job in relevant)
        if name == 'call':
            supported = supported and all(event(job, 'call_held') for job in relevant)
            for job in relevant:
                call_path = pipeline.jobs_dir() / str(job['id']) / 'call.md'
                stats = call_stats.analyze(call_path.read_text()) if call_path.is_file() else {}
                supported = supported and stats.get('transcript_complete') is True and stats.get('member_attributed') is True and str(stats.get('language') or '').casefold() in ('en', 'english')
        if name == 'proposal': supported = supported and all(event(job, 'proposal_sent') for job in relevant)
        if name in ('call', 'application'):
            judgments = review.get('rubric', [])
            supported = supported and bool(judgments) and {item.get('lead_id') for item in judgments if item.get('reviewable')} == set(review['evidence_lead_ids'])
        complete = complete and supported
        row.update(k=int(complete), n=1, value='one fix' if complete else None, state='pass' if complete else 'undecided', reason=None if complete else 'No evidenced weekly fix yet.', evidence=review['evidence_lead_ids'])
        row['history'][-1] = row['value']
        if name in ('call', 'application'):
            rubric = review.get('rubric', [])
            require({item.get('lead_id') for item in rubric} <= set(review['evidence_lead_ids']), 'Rubric leads must be in call review evidence.')
            coverage = rubric_coverage(rubric, today, name)
            if 'coverage' in review:
                require(review['coverage'] == coverage, 'Coverage counts must be computed from the rubric.')
            result['reviews'][name]['coverage'] = coverage
            if review['evidence_lead_ids'] and (not rubric or not supported or not any(item['reviewable'] for item in rubric)):
                row.update(k=0, value=None, state='missing', reason='Calls have no complete speaker labels or submitted application copies are absent.')
                row['history'][-1] = None
    supplied = value.get('goals_review', result['goals_review'])
    require(len(supplied) == len(result['goals_review']), 'Review every previous goal.')
    for given, review in zip(supplied, result['goals_review']):
        require(isinstance(given, dict) and set(given) <= set(review), 'Goal review has unknown fields.')
        for key in set(review) - {'done_k', 'done_n', 'decision', 'evidence_lead_ids', 'done_lead_ids', 'execution_state'}:
            if key in given:
                require(given[key] == review[key], 'Goal effect and before/after numbers must come from compute.')
        evidence, done_ids = given.get('evidence_lead_ids', []), given.get('done_lead_ids', [])
        require(isinstance(evidence, list) and isinstance(done_ids, list) and len(set(evidence)) == len(evidence) and len(set(done_ids)) == len(done_ids) and set(done_ids) <= set(evidence) <= known_ids, 'Goal execution needs unique known evidence lead ids and a done subset.')
        review.update(evidence_lead_ids=evidence, done_lead_ids=done_ids, done_k=len(done_ids), done_n=len(evidence), decision=given.get('decision', 'adjust'),
                      execution_state='no opportunity' if not evidence else 'complete' if len(done_ids) == len(evidence) else 'partial' if done_ids else 'undone')
        require(review['decision'] in ('keep', 'adjust', 'stop'), 'Goal decision needs keep, adjust or stop.')
    done, opportunities = sum(row['done_k'] for row in result['goals_review']), sum(row['done_n'] for row in result['goals_review'])
    result['kpis']['goal_done'].update(k=done, n=opportunities, value=done / opportunities * 100 if opportunities else None,
        unit='%', target=100, target_text='Execution across eligible opportunities',
        state='pass' if opportunities and done == opportunities else 'fail' if opportunities else 'undecided',
        reason=None if opportunities else 'No verified execution opportunities.', evidence=sorted({jid for row in result['goals_review'] for jid in row['evidence_lead_ids']}))
    result['kpis']['goal_done']['history'][-1] = result['kpis']['goal_done']['value']
    for given in coverage_sources(value.get('coverage', [])):
        require(isinstance(given, dict) and {'source', 'state', 'fix'} <= set(given) and set(given) <= {'source', 'state', 'fix', 'affects'}, 'Source judgment needs source, state and fix.')
        source = next((row for row in coverage_sources(result['coverage']) if row['source'] == given['source']), None)
        require(source is not None and given['state'] in ('ok', 'missing', 'stale') and isinstance(given['fix'], str), 'Unknown source or invalid coverage judgment.')
        require('affects' not in given or given['affects'] == source['affects'], 'Source dependencies are computed.')
        require(source['state'] == given['state'] or given['state'] in ('missing', 'stale'), 'Live checks may degrade coverage; they cannot invent a missing saved source.')
        source.update(state=given['state'], fix=given['fix'])
        if source['state'] == 'missing':
            for key in source['affects']:
                row = result['kpis'][key]
                row.update(value=None, delta=None, state='missing', reason=f"{source['source']} source is absent. {source['fix']}")
                if 'delta_pp' in row:
                    row['delta_pp'] = None
                row['history'][-1] = None
            if source['source'] == 'upwork':
                result['north_star']['value'] = None
                result['north_star']['history'][-1] = None
            if source['source'] == 'earnings':
                result['north_star']['hourly_billed'] = None
    result['coverage'] = coverage_fields(coverage_sources(result['coverage']), pipeline.load(), today)
    result['verdict'] = verdict(result['kpis'])
    if 'verdict' in value:
        for key in ('sentence', 'next_action'):
            if key in value['verdict']:
                require(isinstance(value['verdict'][key], str) and value['verdict'][key].strip(), 'Verdict prose needs nonempty text.')
                result['verdict'][key] = value['verdict'][key]
    for key in ('goals_next', 'report'):
        if key in value:
            result[key] = copy.deepcopy(value[key])
    if result['goals_next']:
        validate_goals({'week': result['week'], 'goals': [dict(goal, start=today.isoformat()) if 'start' not in goal else goal for goal in result['goals_next']]})
    result['call_rubric_weeks'] = [row for row in result['call_rubric_weeks'] if row['week'] != result['week']]
    history = [row for row in read_lines('analytics-history.jsonl') if row.get('week', '') < result['week']]
    if not _RECONSTRUCTING.get() and result['gap']['weeks_missed']:
        history += compute_catchup(today, now=result['generated_at'])
    finish_views(result, pipeline.load(), history, today, result['generated_at'])
    claude_fields(result, value)
    prepared_voyage = result['presentation']['voyage']
    result['presentation'] = dict(presentation_fields(result), voyage=prepared_voyage, funnel=funnel_fields(result, pipeline.load()), money_chart=money_chart(result, history), scorecard=scorecard_fields(result, pipeline.load(), history, today))
    result['presentation']['funnel']['outbound'][0]['view_context'] = result['stage_context']['applied_to_viewed']
    result['presentation']['progress_strip'] = progress_strip(result)
    result['presentation']['goal_cards'] = goal_cards(result)
    validate_community_card(result['community_card'])
    privacy(result)
    return result


@ledger_transaction
def record_snapshot(value, replace=False):
    require(isinstance(value, dict), 'Snapshot needs one JSON object.')
    generated = timestamp(value.get('generated_at'))
    require(generated is not None, 'generated_at needs a valid zoned ISO timestamp.')
    today = generated.astimezone(local_zone()).date()
    base = compute(today, now=generated)
    require(set(value) == set(base), 'Snapshot has missing or unknown top-level keys.')
    require(set(value['reviews']) == set(base['reviews']), 'Snapshot needs all four weekly reviews.')
    result = prepare_snapshot(value, today, now=generated)
    require(value['week'] == result['week'], 'Week does not match generated_at.')
    goals = [dict(goal, start=today.isoformat()) if 'start' not in goal else goal for goal in result['goals_next']]
    validate_goals({'week': result['week'], 'goals': goals})
    agreed = next((row['goals'] for row in reversed(read_lines('goals.jsonl')) if row.get('week') == result['week']), None)
    require(agreed is None or goals == agreed, 'Snapshot goals must match the agreed goals saved for this ISO week.')
    focus = result['verdict']['kpi']
    require(focus is None or next(goal['kpi'] for goal in goals if goal['primary']) == focus, 'The focus KPI must be the primary goal.')
    require(isinstance(result['report'], str) and result['report'].strip(), 'Snapshot needs the chat report.')
    for review in result['reviews'].values():
        require(review['goal_ref'] is None or review['goal_ref'] in {goal['kpi'] for goal in goals}, 'Review goal_ref must refer to an agreed goal KPI.')
    require(result['community_card']['next_focus'] is not None, 'Claude must write the weekly community focus; unsafe questions are omitted under frozen §13.')
    for key in ('window', 'periods', 'pipeline', 'streak_weeks', 'verdict_history', 'cohorts', 'daily_applications', 'reply_time_hist', 'speed_curve', 'segments', 'forecast', 'call_rubric_weeks', 'badges', 'todos', 'call_to_won', 'presentation', 'daily_voyage', 'quests', 'call_cards', 'conversations', 'funnel_score', 'conversation_review', 'gap', 'badge_qualifying'):
        require(value[key] == result[key], f'{key} must come unchanged from compute.')
    require(value['coverage'] == result['coverage'], 'Coverage must come from reviewed compute.')
    require(value['north_star'] == result['north_star'], 'North star numbers must come from reviewed compute.')
    for key in set(result['verdict']) - {'sentence', 'next_action'}:
        require(value['verdict'].get(key) == result['verdict'][key], 'Verdict identity and state must come from compute.')
    require(set(value['kpis']) == set(result['kpis']), 'Snapshot needs all 24 KPI keys.')
    derived = {'application_review', 'conversation_review', 'call_review', 'proposal_review', 'goal_done'}
    for key, row in result['kpis'].items():
        supplied = copy.deepcopy(value['kpis'][key])
        require(supplied == row or (key in derived and supplied == base['kpis'][key]), f'{key} numbers must come from reviewed compute.')
    require(validate_community_card(copy.deepcopy(value['community_card'])) == result['community_card'], 'Community numbers, badges and goal marks must come from reviewed compute.')
    result['generated_at'] = value['generated_at']
    validate_community_card(result['community_card'])
    privacy(result)
    rows = read_lines('analytics-history.jsonl')
    duplicate = any(row.get('week') == result['week'] for row in rows)
    require(not duplicate or replace, 'This ISO week already has a snapshot; use --replace.')
    catchup = compute_catchup(today, now=generated)
    existing_weeks = {row.get('week') for row in rows}
    rows += [row for row in catchup if row['week'] not in existing_weeks]
    rows = [result if row.get('week') == result['week'] else row for row in rows] if replace and duplicate else rows + [result]
    rows.sort(key=lambda row: row['week'])
    atomic_lines('analytics-history.jsonl', rows)
    badge_ledger.award_weekly(result['badges'], week=result['week'], now=result['generated_at'])
    return result


def last():
    rows = read_lines('analytics-history.jsonl')
    return saved_snapshot_view(max(rows, key=lambda row: timestamp(row['generated_at']))) if rows else None


def due(today=None):
    date = as_today(today)
    snapshot = last()
    if snapshot is None: return True
    schedule = sections().get('Analytics day', 'Monday').casefold()
    names = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    weekday = next((index for index, name in enumerate(names) if name in schedule), 0)
    scheduled = date - dt.timedelta(days=(date.weekday() - weekday) % 7)
    return day(snapshot['generated_at']) < scheduled


def public_onepager_html(card):
    """Render only the independently validated public payload, never a snapshot."""
    card = validate_community_card(copy.deepcopy(card))
    esc = lambda text: html.escape(str(text), quote=True)
    fmt = lambda value, suffix='': 'unknown' if value is None else f'{value:,.1f}'.rstrip('0').rstrip('.') + suffix
    tokens = (ROOT / 'website/app/tokens.css').read_text(encoding='utf-8')
    assets = ROOT / 'website/public/badges'
    background = assets / 'card-background.webp'
    backdrop = f'url("{background.as_uri()}")' if background.is_file() else 'none'
    motifs = {'Harbour Master': 'harbour', 'First Mate': 'ship', 'Treasure Hunter': 'treasure',
        'Swift Sail': 'hourglass', "Ship’s Bell": 'bell', "Ship\'s Bell": 'bell', 'Lookout': 'spyglass',
        'Steady Anchor': 'anchor', 'Quick Draw': 'cannon', 'Message in a Bottle': 'bottle',
        'True North': 'compass', 'Navigator': 'wheel', 'Lighthouse Keeper': 'lighthouse',
        'First Doubloon': 'doubloon', 'Back on Course': 'storm'}
    colors = {'Bronze': '#A0673A', 'Silver': '#9AA3A8', 'Gold': '#C49A2C', 'Platinum': '#7FA6A9', 'Legend': '#8E1F1F'}
    def badge_html(badge):
        if not badge: return ''
        slug = re.sub(r'[^a-z0-9]+', '-', badge['badge'].casefold().replace("'", '')).strip('-')
        image = assets / f"{slug}-{badge['tier'].casefold()}.webp"
        if not image.is_file(): image = assets / f"badge-{motifs[badge['badge']]}.webp"
        picture = f'<img src="{esc(image.as_uri())}" alt="">' if image.is_file() else '<span class="seal">✦</span>'
        short = badge_ledger.catalogue_metadata().get(badge['badge'], {}).get('short')
        progress = badge.get('progress_to_next')
        if progress and progress.startswith('Lower bound'): progress = 'Next tier needs more finished cases'
        return f'<div class="badge"><div class="ring" style="border-color:{colors[badge["tier"]]}">{picture}</div><b>{esc(badge["badge"])}</b><small>{esc(badge["tier"])}</small>' + (f'<small>{esc(short)}</small>' if short else '') + (f'<small>{esc(progress)}</small>' if progress else '') + '</div>'
    bounds = card['reply_rate']['entry_period']
    rates = []
    labels = {'reply_rate': 'Reply rate', 'reply_to_call': 'Call rate', 'booked_to_held': 'Show-up rate', 'proposal_to_won': 'Win rate', 'call_to_won': 'Call to won'}
    for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won'):
        row = card[key]
        trend = {'up': '↑ Improving', 'down': '↓ Declining', 'undecided': 'No clear change'}[row['trend']]
        completed = 'unknown' if row['state'] == 'missing' else 'No eligible cases yet' if not row['n'] else f"{int(row['k'])} of {int(row['n'])}"
        rates.append(f'<div class="rate"><span>{labels[key]}</span><strong>{fmt(row["value"], "%")}</strong><small>{completed} · {row["horizon_days"]}-day follow-up</small><small>Target {row["target"]}% · {row["rung_reached"]}/3 steps · {trend}</small></div>')
    goals = ''.join(f'<li><span>{"✓" if goal["done"] else "○"}</span>{esc(goal["text"])}<small>{str(int(goal["k"])) + " of " + str(int(goal["n"])) if goal["n"] else "No eligible cases yet"}</small></li>' for goal in card['goals'])
    improvement = card['biggest_improvement']
    change = 'No clear improvement yet. Keep practising the focus.'
    if improvement:
        change = f'{labels[improvement["kpi"]]}: {fmt(improvement["from"], "%")} → {fmt(improvement["to"], "%")}'
        if improvement.get('reason'): change += f' · {esc(improvement["reason"])}'
    focus = esc(card['next_focus']) if card['next_focus'] else 'Choose the next focus in /analytics'
    question = f'<p class="question">{esc(card["question"])}</p>' if card['question'] else ''
    money = f'<div class="money">New contract value this week <b>{fmt(card["won_value"])}</b></div>' if card['won_value'] is not None and sections().get('Share money', '').strip().casefold() == 'yes' else ''
    new_badge = f'<div class="new"><b>New badge</b>{badge_html(card["new_badge"])}</div>' if card['new_badge'] else '<div class="new"><b>New badge</b><p>No new tier this week.</p></div>'
    score = card['funnel_score']; score_text = 'Funnel Score ' + fmt(score['score']) + (', was ' + fmt(score['previous']) if score['previous'] is not None else '')
    score_label = 'Habits only until your baseline is set' if score['baseline_only'] else 'Weekly Funnel Score'
    example_label = '<p class="period">Synthetic example. No member or client facts.</p>' if os.environ.get('BLUEPRINT_EXAMPLE_DATA') == '1' else ''
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weekly voyage · {esc(card['week'])}</title>
<style>{tokens}
*{{box-sizing:border-box}}html,body{{width:1080px;height:1350px;margin:0;overflow:hidden}}body{{font-family:var(--sans);color:var(--ink);background:var(--canvas)}}.card{{height:1350px;padding:58px 68px;background:linear-gradient(color-mix(in srgb,var(--canvas) 94%,transparent),color-mix(in srgb,var(--canvas) 96%,transparent)),{backdrop};background-size:cover}}header{{display:flex;justify-content:space-between;align-items:center}}h1{{font-family:var(--display);font-size:49px;letter-spacing:-1px;margin:8px 0 30px}}.eyebrow,small{{font-size:16px;color:var(--label)}}.activity{{display:flex;gap:45px;padding:22px 0;border-top:1px solid var(--ring);border-bottom:1px solid var(--ring)}}.activity strong{{font-size:35px;display:block}}.activity span{{font-size:18px}}h2{{font-size:20px;margin:25px 0 12px}}.period{{margin:10px 0 14px;font-size:16px;color:var(--label)}}.rates{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.rate{{padding:19px 17px;background:color-mix(in srgb,var(--ivory) 80%,transparent);border:1px solid var(--hairline-soft);border-radius:14px}}.rate span{{font-size:18px}}.rate strong{{font-size:32px;display:block;margin:14px 0 10px}}.rate small{{display:block;line-height:1.7;font-size:14px}}.reply{{display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding:13px 18px;background:color-mix(in srgb,var(--ivory) 65%,transparent);border-radius:10px;font-size:18px}}.reply b{{font-size:24px}}.goals{{list-style:none;padding:0;margin:0}}.goals li{{padding:9px 0;font-size:20px;display:flex;align-items:center;gap:14px}}.goals small{{margin-left:auto}}.improvement{{padding:15px 20px;background:var(--terracotta-soft);border-left:4px solid var(--terracotta);line-height:1.5;font-size:19px}}.badges{{display:flex;gap:13px;justify-content:space-around;align-items:flex-start}}.badge{{width:145px;text-align:center;display:flex;flex-direction:column;align-items:center}}.badge b{{font-size:15px;margin-top:6px}}.badge small{{font-size:13px;margin-top:4px}}.ring{{border:3px solid;border-radius:50%;width:87px;height:87px;padding:3px;background:var(--ivory)}}.ring img{{width:100%;height:100%;object-fit:contain;border-radius:50%}}.seal{{font-size:56px}}.new{{display:flex;align-items:center;gap:22px;padding:15px 0}}.new>.badge{{width:auto;flex-direction:row;gap:12px}}.new .ring{{width:54px;height:54px}}.new p{{margin:0;color:var(--label)}}.focus{{border-top:1px solid var(--ring);padding-top:18px;margin-top:18px}}.focus h2{{margin:0 0 9px}}.focus strong{{font-size:25px}}.question{{font-size:20px;margin:12px 0 0}}.money{{font-size:18px;margin-top:10px}}.money b{{margin-left:16px}}@media(max-width:1079px){{html,body{{width:100%;height:auto;overflow:visible}}.card{{height:auto;min-height:100vh;padding:28px 22px}}h1{{font-size:36px}}header{{gap:16px;flex-wrap:wrap}}.activity{{flex-wrap:wrap;gap:22px}}.activity strong{{font-size:27px;overflow-wrap:anywhere}}.rates{{grid-template-columns:repeat(2,minmax(0,1fr))}}.rate{{min-width:0;padding:14px 11px}}.rate span{{font-size:16px}}.rate strong{{font-size:30px}}.reply{{flex-wrap:wrap;gap:9px}}.goals li{{flex-wrap:wrap;font-size:18px}}.goals small{{margin-left:0;width:100%;padding-left:30px}}.new{{flex-wrap:wrap}}.focus strong{{font-size:23px}}}}</style>
<main class="card"><header><span class="eyebrow">UPWORK BLUEPRINT · WEEKLY VOYAGE</span><b>{esc(card['week'])}</b></header><h1>{esc(card.get('member_name') or 'Progress worth sharing.')}</h1>{example_label}
<div class="activity"><div><strong>{int(card['applications']) if card['applications'] is not None else 'unknown'}</strong><span>Applications this week</span></div><div><strong>{esc(score_text)}</strong><span>{esc(score_label)}</span></div></div>
<h2>How conversations moved forward</h2><p class="period">{esc(bounds['start'])} – {esc(bounds['end'])} · Finished cases in the same 28-day window</p><div class="rates">{''.join(rates)}</div>
<div class="reply"><span>Typical first reply · same 28-day window</span><b>{fmt(card['first_reply_median_min'], ' min')}</b><small>Target ≤ 5 min</small></div>{money}
<h2>Last agreed goals</h2>{'<ul class="goals">'+goals+'</ul>' if goals else '<p class="period">No previous goals. Agree the first goals in /analytics.</p>'}
<h2>Biggest improvement</h2><div class="improvement">{change}</div>{new_badge}
<div class="focus"><h2>Next focus</h2><strong>{focus}</strong>{question}</div></main></html>'''


def onepager(file, week=None, output=None):
    """Export a selected weekly public card to local HTML and a 1080×1350 PNG."""
    text = sys.stdin.read() if file == '-' else pathlib.Path(file).read_text(encoding='utf-8')
    try: payload = json.loads(text)
    except json.JSONDecodeError: payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    rows = payload if isinstance(payload, list) else [payload]
    require(rows and all(isinstance(row, dict) for row in rows), 'One-pager input needs a snapshot or snapshot ledger.')
    candidates = [row for row in rows if week is None or row.get('week') == week]
    require(candidates, 'No snapshot exists for the requested week.')
    snapshot = max(candidates, key=lambda row: (str(row.get('week', '')), str(row.get('generated_at', ''))))
    require('community_card' in snapshot, 'Snapshot has no community card; run analytics first.')
    card = validate_community_card(copy.deepcopy(snapshot['community_card']))
    # Share-money consent is rechecked at export, even for an older snapshot.
    if sections().get('Share money', '').strip().casefold() != 'yes': card['won_value'] = None
    path = pathlib.Path(output) if output else ROOT / 'outputs/analytics' / f"{card['week']}.html"
    if path.suffix.lower() not in ('.html', '.png'): path = path / f"{card['week']}.html"
    path = path.with_suffix('.html').resolve()
    png = path.with_suffix('.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(public_onepager_html(card), encoding='utf-8')
    browsers = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        shutil.which('chromium'), shutil.which('chromium-browser'), shutil.which('google-chrome')]
    chrome = next((browser for browser in browsers if browser and pathlib.Path(browser).is_file()), None)
    if not chrome: return {'week': card['week'], 'html': str(path), 'png': None, 'note': 'No Chrome or Chromium installed; screenshot the HTML at 1080×1350.'}
    with tempfile.TemporaryDirectory(prefix='blueprint-card-browser-') as profile:
        capture = pathlib.Path(profile) / 'card.png'
        run = subprocess.run([chrome, '--headless', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
            '--no-default-browser-check', '--allow-file-access-from-files', '--force-device-scale-factor=1',
            '--disable-background-networking', f'--user-data-dir={profile}', '--window-size=1080,1350',
            f'--screenshot={capture}', path.as_uri()], capture_output=True, text=True, timeout=45)
        require(run.returncode == 0 and capture.is_file(), 'Headless browser failed to produce the one-pager PNG; HTML is saved.')
        header = capture.read_bytes()[:24]
        require(header[:8] == b'\x89PNG\r\n\x1a\n' and len(header) == 24 and struct.unpack('>II', header[16:24]) == (1080, 1350), 'One-pager PNG dimensions must be 1080×1350.')
        os.replace(capture, png)
    return {'week': card['week'], 'html': str(path), 'png': str(png)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    calc = sub.add_parser('compute'); calc.add_argument('--today'); calc.add_argument('--now'); calc.add_argument('--file'); calc.add_argument('--catch-up', action='store_true')
    record = sub.add_parser('record'); record.add_argument('--file', required=True); record.add_argument('--replace', action='store_true')
    goals = sub.add_parser('goals').add_subparsers(dest='action', required=True)
    goals.add_parser('add').add_argument('--file', required=True)
    sub.add_parser('last')
    card_parser = sub.add_parser('onepager'); card_parser.add_argument('--file', required=True); card_parser.add_argument('--week'); card_parser.add_argument('--output')
    due_parser = sub.add_parser('due'); due_parser.add_argument('--today')
    args = parser.parse_args(argv)
    try:
        if args.command == 'compute':
            overlay = json.load(sys.stdin) if args.file == '-' else json.loads(pathlib.Path(args.file).read_text(encoding='utf-8')) if args.file else None
            result = prepare_snapshot(overlay, args.today, args.now) if overlay is not None else compute_catchup(args.today, now=args.now) if args.catch_up else compute(args.today, now=args.now)
        elif args.command == 'onepager':
            result = onepager(args.file, args.week, args.output)
        elif args.command == 'last':
            result = last()
        elif args.command == 'due':
            result = due(args.today)
        else:
            value = json.load(sys.stdin) if args.file == '-' else json.loads(pathlib.Path(args.file).read_text(encoding='utf-8'))
            result = record_snapshot(value, args.replace) if args.command == 'record' else add_goals(value)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(f'ABORT: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
