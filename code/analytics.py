#!/usr/bin/env python3
"""Weekly analytics. Read the pipeline; write only weekly snapshots and goals.

    python3 code/analytics.py compute [--today YYYY-MM-DD]
    python3 code/analytics.py record --file - [--replace]
    python3 code/analytics.py goals add --file -
    python3 code/analytics.py last
    python3 code/analytics.py due [--today YYYY-MM-DD]
"""
import argparse
import base64
import copy
import contextvars
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP, localcontext
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
import unicodedata
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
BADGE_NAMES = tuple(OUTCOME_BADGES) + ('Swift Sail', "Ship's Bell", 'Lookout', 'Steady Hand',
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


def whole_percent(value):
    """Member percentages match the browser's positive half-up rounding."""
    return math.floor(value + .5) if number(value) else value


def display_number(value, places=0):
    """Match displayed money and time precision without altering stored numbers."""
    amount = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(28, len(amount.as_tuple().digits) + places + 2, amount.adjusted() + places + 2)
        return float(amount.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def metric(key, k=None, n=None, value=None, target=None, state='undecided', evidence=None, reason=None):
    order = list(LABELS).index(key) + 1
    layer = 'result' if order < 3 else 'funnel' if order < 10 else 'lever' if order < 16 else 'insight' if order in (20, 21) else 'coaching'
    unit = 'usd' if order < 3 else 'min' if key == 'first_reply' else 'count' if key in ('weekly_volume', 'goal_done') else 'text' if order >= 16 else '%'
    return {'label': LABELS[key], 'layer': layer, 'strand': 'outbound' if order in (3, 4, 5, 6, 7) else 'inbound' if order in (8, 9) else None,
            'order': order, 'unit': unit, 'value': rounded(value), 'k': k, 'n': n, 'low': None, 'high': None,
            'target': target, 'target_text': f'{whole_percent(target)}%' if number(target) and unit == '%' else str(target) if target is not None else 'one fix' if order in (16, 17, 18, 19) else 'up vs own four weeks' if order < 3 else None,
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
        ('upwork', upwork, list(LABELS)[:15] + ['segments','behaviour'], 'Run /brief to sync Upwork.'),
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


def coverage_fields(sources, jobs, today, include_available=False):
    missing = [dict({'source': row['source'], 'blocks': row['affects'], 'how_to_supply': row['fix']},
                    **({'what': row['what']} if 'what' in row else {}))
               for row in sources if row['state'] == 'missing']
    def absent(source, blocks, supply):
        entry = {'source': source, 'blocks': blocks, 'how_to_supply': supply}
        if entry not in missing: missing.append(entry)
    for job in jobs:
        jid = str(job['id']); folder = pipeline.jobs_dir() / jid
        if event(job, 'applied') and not job.get('imported'):
            if include_available or not read_source(folder / 'application.sent.md') or job.get('application_sent_verified') is not True:
                absent('sent copy:' + jid, ['application_review'], 'Open the submitted Upwork application and save its sent copy.')
            if job.get('loom_url') and (include_available or not read_source(folder / 'loom.md')):
                absent('Loom:' + jid, ['application_review'], 'Paste the Loom transcript for ' + jid + '.')
        if event(job, 'call_held'):
            text = read_source(folder / 'call.md')
            stats = call_stats.analyze(text) if text else {}
            if include_available or not text or not stats.get('transcript_complete') or not stats.get('member_attributed'):
                absent('call transcript:' + jid, ['call_review'], 'Paste a transcript or run /call-review ' + jid + '.')
        if event(job, 'won') and (include_available or contract_value(job) is None):
            absent('contract terms:' + jid, ['won_value', 'value_per_100_connects', 'forecast'], 'Reconnect Upwork and read the agreed contract amount or hourly hours for ' + jid + '.')
    return {'sources': copy.deepcopy(sources), 'missing': missing}


CONVERSATION_POINTS = ('answered_question', 'qualifying_question', 'call_times')
APPLICATION_POINT_LABELS = dict(enumerate(('Posted problem', 'Matching proof', 'Screening answers',
    'Bid and scope', 'Concise application', 'Easy closing question', 'Loom (when used)'), 1))
CHAT_POINT_LABELS = dict(zip(CONVERSATION_POINTS, ('Answered question', 'Qualifying question', 'Call proposal when useful')))
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
            points[name] = copy.deepcopy(point) if supported else {
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


RANK_LEVELS = (('Deckhand', 0), ('Boatswain', 40), ('Officer', 60), ('Captain', 75), ('Admiral', 90))


def rank_fields(snapshot, history=None):
    """A rank is the four-week average held for four consecutive weekly checks.

    Seven dated scores are needed to prove four complete rolling averages. A
    missed or unknown week breaks the hold; no missing score is filled with zero.
    """
    rows = {row['week']: row for row in (history or []) if row.get('week', '') <= snapshot.get('week', '')}
    rows[snapshot['week']] = snapshot
    end = badge_ledger._week_date(snapshot['week'])
    rolling = []
    for back in range(3, -1, -1):
        anchor = end - dt.timedelta(weeks=back)
        values = []
        for offset in range(3, -1, -1):
            iso = (anchor - dt.timedelta(weeks=offset)).isocalendar()
            row = rows.get(f'{iso.year}-W{iso.week:02d}', {})
            value = row.get('funnel_score', {}).get('score')
            values.append(value if number(value) and 0 <= value <= 100 else None)
        rolling.append(statistics.mean(values) if all(number(value) for value in values) else None)
    stable = 0
    for index, (_, threshold) in enumerate(RANK_LEVELS[1:], 1):
        if all(number(value) and value >= threshold for value in rolling): stable = index
    name, threshold = RANK_LEVELS[stable]
    next_name, next_threshold = RANK_LEVELS[stable + 1] if stable + 1 < len(RANK_LEVELS) else (None, None)
    held = 0
    if next_threshold is not None:
        for value in reversed(rolling):
            if not number(value) or value < next_threshold: break
            held += 1
    score = rounded(rolling[-1])
    progress = min(100, max(0, 100 * score / next_threshold)) if number(score) and next_threshold else 100 if next_threshold is None else 0
    return {'rank': name, 'score': score, 'next_rank': next_name, 'next_threshold': next_threshold,
            'held_weeks': held, 'required_weeks': 4, 'progress': rounded(progress)}


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


def attendance_start(job):
    session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
    return None if session.get('cancelled') else timestamp(session.get('scheduled_at') or job.get('call_scheduled_at'))


def habit_comparison(jobs, bounds):
    """Mean of four distinct prior weekly observations; never include the current week."""
    weeks = []
    token = _RECONSTRUCTING.set(True)
    try:
        for back in range(4, 0, -1):
            window = tuple(date - dt.timedelta(weeks=back) for date in bounds)
            check = window[1] + dt.timedelta(days=1)
            metrics, _ = calculate(jobs, check, now=dt.datetime.combine(check, dt.time(), local_zone()), activity_bounds=window)
            weeks.append(metrics)
    finally:
        _RECONSTRUCTING.reset(token)
    result = {}
    for key in LEVERS:
        rows = [week[key] for week in weeks]
        known = [row['value'] for row in rows if number(row.get('value'))]
        unknown = any(row.get('state') == 'missing' or row.get('unknown_n', 0) for row in rows)
        value = statistics.mean(known) if known and not unknown else None
        result[key] = dict(rows[-1], value=value, k=sum(row.get('k', 0) for row in rows),
            n=sum(row.get('k', 0) if key == 'weekly_volume' else row.get('n', 0) for row in rows),
            evidence=sorted({jid for row in rows for jid in row.get('evidence', [])}),
            low=None, high=None, unknown_n=sum(row.get('unknown_n', 0) for row in rows),
            observed_weeks=len(known), state='missing' if unknown else 'no opportunities' if value is None else
                'pass' if (value <= rows[-1]['target'] if key == 'first_reply' else value >= rows[-1]['target']) else 'fail')
    return result


def scorecard_fields(snapshot, jobs, history, today):
    """Reported weekly habits beside unchanged 28-day result populations."""
    now = snapshot['generated_at']; current, _ = calculate(jobs, today, now=now, activity_bounds=span(today, 28))
    historic_token = _RECONSTRUCTING.set(True)
    try:
        previous, _ = calculate(jobs, today - dt.timedelta(days=28), now=dt.datetime.combine(today - dt.timedelta(days=28), dt.time(), local_zone()), activity_bounds=span(today - dt.timedelta(days=28), 28))
    finally:
        _RECONSTRUCTING.reset(historic_token)
    activity = snapshot.get('periods', {}).get('activity') or period(span(today, 7))
    habit_bounds = (day(activity['start']), day(activity['end']))
    prior_bounds = (habit_bounds[0] - dt.timedelta(weeks=4), habit_bounds[0] - dt.timedelta(days=1))
    habit_prior = habit_comparison(jobs, habit_bounds)
    # History carries actual weekly KPI observations. Legacy snapshots fall back
    # to the ISO week's Monday, never a week number interpreted as a date.
    old_by_date = {}
    for old in history:
        saved_activity = old.get('periods', {}).get('activity') or {}
        date = day(saved_activity.get('start')) or badge_ledger._week_date(old.get('week', ''))
        if date and date < habit_bounds[0]: old_by_date[date - dt.timedelta(days=date.weekday())] = old
    label_start = habit_bounds[0] - dt.timedelta(days=habit_bounds[0].weekday())
    labels = [(label_start - dt.timedelta(weeks=back)).isoformat() for back in range(7, -1, -1)]
    groups = {'top': ('job_fit', 'weekly_volume', 'speed_10min', 'reply_rate'),
        'middle': ('first_reply', 'follow_ups_on_time', 'reply_to_call', 'booked_to_held', 'invite_to_call'),
        'bottom': ('proposal_on_time', 'proposal_to_won', 'offer_to_contract', 'value_per_100_connects')}
    focus = snapshot.get('verdict', {}).get('kpi'); rows = []
    entry_names = {'reply_rate': 'applied', 'reply_to_call': 'replied', 'booked_to_held': 'call_booked', 'proposal_to_won': 'proposal_sent', 'invite_to_call': 'invited', 'offer_to_contract': 'offer'}
    for group, keys in groups.items():
        for key in keys:
            frozen = snapshot['kpis'][key]
            habit = key in LEVERS
            row = copy.deepcopy(frozen if habit else current[key])
            prior = habit_prior[key] if habit else previous[key]
            opportunities = row.get('k', 0) if key == 'weekly_volume' else row.get('n', 0)
            current_week = dict(period(habit_bounds), kind='week', value=row.get('value'),
                                k=row.get('k'), n=opportunities) if habit else None
            if key == 'weekly_volume': row['n'] = opportunities
            sparse = habit and opportunities < 3
            sample_note = None
            if sparse:
                row = copy.deepcopy(prior)
                sample_note = f"This week has {opportunities} opportunities; showing the prior four-week average."
                if row.get('value') is None: sample_note += ' Prior observations are unavailable.'
            main_period = dict(period(prior_bounds if sparse else habit_bounds), kind='four_week_average' if sparse else 'week') if habit else copy.deepcopy(snapshot['window'])
            comparison_period = dict(period(prior_bounds), kind='four_week_average') if habit else period(span(today - dt.timedelta(days=28), 28))
            if key in FUNNEL:
                for field in ('target', 'rungs', 'rung_reached', 'baseline_phase', 'state', 'reason'):
                    row[field] = frozen.get(field)
            if frozen['state'] == 'missing' and not sparse: row.update(state='missing', value=None, reason=frozen.get('reason'))
            if row.get('unknown_n', 0): row.update(state='missing', value=None, reason='Some source observations are unknown. Supply the missing timestamps or call end evidence.')
            def pending_start(job):
                return attendance_start(job) if key == 'booked_to_held' else event(job, entry_names.get(key, ''))
            pending = [job for job in jobs if key in entry_names and not job.get('imported') and route(job) == ('invite' if key == 'invite_to_call' else 'inbound' if key == 'offer_to_contract' else 'outbound') and inside(pending_start(job), span(today, 28)) and pending_start(job) + dt.timedelta(days=HORIZONS[key]) > timestamp(now)]
            until = max((pending_start(job) + dt.timedelta(days=HORIZONS[key]) for job in pending), default=None)
            previous_n = prior.get('n')
            previous_value = prior.get('value') if prior.get('state') != 'missing' and not (key in FUNNEL and previous_n == 0) and (habit or not snapshot['kpis']['reply_rate'].get('baseline_phase', True)) else None
            comparison = f"New: {row.get('n', 0)} finished cases" if key in FUNNEL and previous_n == 0 and row.get('n') else ('Prior four-week average unavailable' if habit else 'Previous 28-day comparison unavailable') if previous_value is None else 'unchanged' if row.get('value') == previous_value else 'was ' + (f'{whole_percent(previous_value)}%' if row['unit'] == '%' else f'{display_number(previous_value, 1):.1f} min' if row['unit'] == 'min' else f'{display_number(previous_value):,.0f}')
            split = []
            if key == 'proposal_on_time':
                split = [dict(label='Held calls to proposal (last 28 days)', k=current['held_to_proposal']['k'], n=current['held_to_proposal']['n'], evidence=current['held_to_proposal']['evidence'])]
            market = None
            if key == 'reply_rate': market = {'value': '5% agency reply rate, rounded; different population', 'source': 'GigRadar Q2 2026, 30 July 2026: https://gigradar.io/upwork/reports/2026/q2/all-industries'}
            if key == 'proposal_to_won': market = {'value': '34% sales proposal close rate; not Upwork', 'source': 'Proposify State of Proposals 2026: https://www.proposify.com/state-of-proposals-2026'}
            points = []
            for label in labels[:-1]:
                old = old_by_date.get(day(label), {})
                if habit:
                    observation = old.get('kpis', {}).get(key, {})
                    points.append(observation.get('value') if observation.get('state') != 'missing' and not observation.get('unknown_n', 0) else None)
                else:
                    points.append(next((item.get('value') for item in old.get('presentation', {}).get('scorecard', []) if item.get('key') == key), None))
            points.append(current_week['value'] if habit and frozen.get('state') != 'missing' and not frozen.get('unknown_n', 0) else None if habit else row.get('value'))
            rows.append({'key': key, 'group': group, 'name': SCORECARD_NAMES[key], 'stage_label': SCORECARD_STAGE.get(key),
                'period_label': 'Prior four-week average' if sparse else 'This week' if habit else 'Last 28 days', 'sample_note': sample_note, 'habit_period': dict(period(habit_bounds), kind='week') if habit else None, 'current_week': current_week, 'counting': ('Average of the four weekly observations before this week; counts sum those four weeks. Weeks without opportunities are omitted, except weekly application volume includes zero weeks.' if sparse else {'weekly_volume': 'Qualified applications this week; the target is the weekly commitment.', 'job_fit': 'All sent outbound applications in the last 28 days, with a saved lane and rate fit review.', 'speed_10min': 'Qualified applications this week with frozen posting age; unknown ages remain unknown.', 'first_reply': 'Client messages received this week; unanswered messages count at their working-hours age.', 'follow_ups_on_time': 'Distinct silent-lane obligations due this week; a sent follow-up counts on its due business day.', 'proposal_on_time': 'All fitting held calls this week; sent within 30 min of call end. Clean disqualifications and offer or contract bypasses are excluded.', 'value_per_100_connects': 'Known new contract value divided by net Connects spent in the last 28 days, multiplied by 100. Zero spend is not measurable.'}.get(key) or f'Each case has {HORIZONS.get(key, 0)} days for a result. Counts include cases with and without a result after that time, with starting dates across 28 days.'), 'period': main_period, 'value': row.get('value'),
                'finished': {'k': row.get('k'), 'n': row.get('n')}, 'pending': {'n': len(pending), 'until': until.date().isoformat() if until else None},
                'uncertainty': {'low': row.get('low'), 'high': row.get('high')},
                'change': {'previous_value': previous_value, 'previous': previous_value,
                           'previous_n': previous_n, 'n': row.get('n'),
                           'new': bool(key in FUNNEL and previous_n == 0 and row.get('n')), 'comparison_label': 'Prior four-week average' if habit else 'Previous 28 days', 'comparison_period': comparison_period, 'text': comparison},
                'series': {'label': 'Last eight weekly checks', 'unit': row['unit'], 'points': points, 'labels': labels},
                'target': {'kind': 'ladder' if key in FUNNEL else 'habit', 'value': row.get('target'), 'level': frozen.get('rung_reached'), 'thresholds': frozen.get('rungs', [])},
                'next_action': {'text': (snapshot.get('verdict', {}).get('next_action') if key == focus else None) or ACTIONS.get(key, 'Review these leads.'), 'lead_filter': {'kpi': key, 'lead_ids': scorecard_action_ids(key, row, jobs, today, now)}},
                'job_fit': copy.deepcopy(snapshot.get('insights', {}).get('job_fit')) if key == 'reply_rate' else None,
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


def working_dates(monday):
    """ISO-week schedule from Working hours; unknown weekdays default to Mon-Fri.

    Planned off days / Holidays accept ISO dates and inclusive ISO date ranges.
    No inferred national holidays or daily application target.
    """
    config = sections()
    hours = config.get('Working hours', '')
    names = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
    days = set()
    if re.search(r'every day|daily', hours, re.I): days = set(range(7))
    for match in re.finditer(r'\b(Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)(?:\s*[-–]\s*(Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?))?', hours, re.I):
        start = names.index(match[1][:3].lower())
        end = names.index(match[2][:3].lower()) if match[2] else start
        days.update((start + step) % 7 for step in range((end - start) % 7 + 1))
    if not days: days = set(range(5))
    off = '\n'.join(value for key, value in config.items() if key.casefold() in ('planned off days', 'off days', 'holidays', 'planned holidays'))
    ranges = []
    for match in re.finditer(r'(\d{4}-\d{2}-\d{2})(?:\s*(?:to|through|[-–])\s*(\d{4}-\d{2}-\d{2}))?', off):
        start, end = day(match[1]), day(match[2] or match[1])
        if start and end and start <= end: ranges.append((start, end))
    return [monday + dt.timedelta(days=index) for index in range(7) if index in days and
            not any(start <= monday + dt.timedelta(days=index) <= end for start, end in ranges)]


def accountability_fields(snapshot, jobs, history):
    today = day(snapshot['generated_at'])
    bounds = badge_ledger.commitment_period(snapshot)
    start = day(bounds.get('start')) or today - dt.timedelta(days=today.weekday())
    end = day(bounds.get('end')) or start + dt.timedelta(days=6)
    monday = start - dt.timedelta(days=start.weekday())
    dates = []
    while monday <= end:
        dates.extend(date for date in working_dates(monday) if start <= date <= end)
        monday += dt.timedelta(weeks=1)
    applied = {day(event(job, 'applied')) for job in jobs if not job.get('imported') and
               route(job) == 'outbound' and qualified(job) and day(event(job, 'applied')) and day(event(job, 'applied')) <= today}
    working = {'k': len(set(dates) & applied), 'n': len(dates),
               'dates': [date.isoformat() for date in dates],
               'applied_dates': [date.isoformat() for date in dates if date in applied]}
    # Count the reported application period, retaining its saved commitment target.
    entries = {str(job['id']) for job in jobs if not job.get('imported') and route(job) == 'outbound' and
               qualified(job) and inside(event(job, 'applied'), (start, min(end, today)))}
    current = dict(snapshot, accountability={'working_days': working}, kpis=dict(snapshot['kpis']))
    current['kpis']['weekly_volume'] = dict(snapshot['kpis']['weekly_volume'], value=len(entries), k=len(entries),
                                                   period={'start': start.isoformat(), 'end': end.isoformat()})
    streak = badge_ledger.streak_history(history, week=snapshot['week'], current=current)
    return {'working_days': working, 'application_streak': {'current': streak['streak_weeks'],
            'best': streak['best_streak_weeks'], 'weeks': streak['weeks']}}


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
def calculate(jobs, today, since=None, now=None, cohort_days=28, activity_bounds=None, source_now=None):
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
                scheduled = attendance_start(job)
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
    engine = insight_fields(jobs, today)
    for key, dimension in (('segments', 'segment'), ('behaviour', 'behaviour')):
        confirmed = [row for row in engine['findings'] if (row['dimension'] == 'behaviour') == (dimension == 'behaviour')]
        observed = engine['behaviour' if key == 'behaviour' else 'segments']
        kpis[key].update(k=len(confirmed), n=len(observed), value=len(confirmed), state='observed',
                         evidence=sorted({jid for row in confirmed for jid in row['evidence']}),
                         reason='Confirmed across separate six-week periods.' if confirmed else 'No confirmed pattern yet.')
    lost = [job for job in jobs if job.get('status') == 'lost' and inside(job.get('status_updated_at') or next((item.get('at') for item in reversed(job.get('history') or []) if item.get('status') == 'lost'), None), activity)]
    reasons = {kind: sum((assessment(job, 'lost_reason') or {}).get('kind', 'unknown') == kind for job in lost) for kind in ('stated', 'observed', 'unknown')}
    kpis['lost_reasons'].update(k=len(lost) - reasons['unknown'], n=len(lost), value=reasons, evidence=ids(lost))
    coverage, _ = source_coverage(jobs, today, source_now or now)
    for source in coverage:
        if source['state'] == 'ok':
            continue
        for key in source['affects']:
            if source['state'] == 'stale' and kpis[key]['n']:
                continue
            # Optional Loom/tracking absence leaves the whole review explicitly missing.
            kpis[key].update(state='missing', reason=f"{source['source']} source is absent. {source['fix']}", value=None)
            if key in ('segments','behaviour') and source['state']=='missing':
                kpis[key].update(k=None,n=None)
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
                    f"{kpis[failure]['label']} is below its {whole_percent(kpis[failure]['target'])}% target.")
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
                    scheduled = attendance_start(job)
                    if attended: held += 1
                    elif not session.get('cancelled') and (scheduled or event(job, 'call_booked')): booked += 1
                row.update(booked=booked, held=held, unknown_call=len(rows) - booked - held)
            result[strand].append(row)
    return result


def goal_id(goal, week):
    if goal.get('goal_id'): return goal['goal_id']
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
        # Freeze both entries and observed outcomes at the goal's maturity date.
        after_cutoff = min(today, mature_on)
        after_days = max(1, (after_cutoff - start).days - horizon)
        after_bounds = (start, max(start, after_cutoff - dt.timedelta(days=1)))
        after = calculate(jobs, after_cutoff, since=start, now=dt.datetime.combine(after_cutoff, dt.time(), local_zone()), source_now=now or run_timestamp(today), cohort_days=after_days,
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
            'after_period': period((start, min(today, mature_on))), 'after_entry_period': after.get('entry_period', period(after_bounds)),
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
                   target_text=f'{whole_percent(target)}%' + (' · top rung held' if reached == len(rungs) else ''), baseline_phase=phase, baseline_ready=not phase and row['n'] > 0)
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



# PART2: fixed, outcome-blind application-time categories only. No live job fields.
JOB_FIT_LABELS = {
    'budget_band': ('the budget is below $500', 'the budget is $500 to $2,000', 'the budget is above $2,000', 'payment is hourly'),
    'proposals_band': ('fewer than 5 people applied', '5 to 15 people applied', '15 to 50 people applied', '50 or more people applied'),
    'client_hire_rate_band': ('clients have never hired', 'clients hired on fewer than 30% of posts', 'clients hired on 30% to 70% of posts', 'clients hired on more than 70% of posts'),
    'client_spent_band': ('clients have spent nothing', 'clients have spent less than $1,000', 'clients have spent $1,000 to $10,000', 'clients have spent over $10,000'),
    'posted_age_band': ('jobs were posted under 10 minutes before you applied', 'jobs were posted 10 to 60 minutes before you applied', 'jobs were posted 1 to 6 hours before you applied', 'jobs were posted over 6 hours before you applied'),
    'bid_band': ('your bid was below the listed budget', 'your bid was within the listed budget', 'your bid was above the listed budget'),
}


@functools.lru_cache(maxsize=8192)
def job_fit_exact_p(k, n, p):
    """Two-sided exact binomial probability, probability-ordering definition."""
    if not n: return 1.0
    if p == 0: return 1.0 if k == 0 else 0.0
    if p == 1: return 1.0 if k == n else 0.0
    def mass(i):
        return math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)
    observed = mass(k)
    return min(1.0, math.fsum(math.exp(mass(i)) for i in range(n + 1) if mass(i) <= observed + 1e-12))


def job_fit_fields(jobs, today):
    """Last 84 application days, disjoint 42-day halves, seven-day reply horizon.

    Item 14.8 requires two halves and a fifteen-case display floor. The full
    statistical gate belongs to the separate general insight engine.
    Unknown bands are excluded from that dimension, including its own-rate reference.
    Connects per reply is total frozen listed application cost / all replies, including
    costs of unsuccessful applications; incomplete cost coverage is never extrapolated.
    """
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    bounds = span(today, 84)
    middle = bounds[0] + dt.timedelta(days=42)
    windows = {'discovery': (bounds[0], middle - dt.timedelta(days=1)), 'confirmation': (middle, bounds[1])}
    candidates = [job for job in jobs if not job.get('imported') and
                  (job.get('application_facts') or {}).get('source') == 'outbound' and inside(event(job, 'applied'), bounds)]
    finished = [job for job in candidates if event(job, 'applied') + dt.timedelta(days=7) <= cutoff]
    def measure(rows):
        k = sum(has_after(job, 'replied', event(job, 'applied'), event(job, 'applied') + dt.timedelta(days=7)) for job in rows)
        costs = [(job.get('application_facts') or {}).get('connects_cost') for job in rows]
        known = [cost for cost in costs if number(cost) and cost >= 0]
        low, high = wilson(k, len(rows))
        return {'k': k, 'n': len(rows), 'reply_rate': rounded(100 * k / len(rows)) if rows else None,
                'low': rounded(low), 'high': rounded(high), 'connects_known_n': len(known),
                'connects_total': sum(known) if len(known) == len(rows) and rows else None,
                'connects_per_reply': rounded(sum(known) / k) if k and len(known) == len(rows) else None,
                'evidence': ids(rows)}
    bands = []
    for dimension, labels in JOB_FIT_LABELS.items():
        values = pipeline.APPLICATION_BANDS[dimension][:-1]
        known = [job for job in finished if job['application_facts'].get(dimension) in values]
        for value, label in zip(values, labels):
            selected = [job for job in known if job['application_facts'][dimension] == value]
            row = dict(dimension=dimension, band=value, label=label, **measure(selected))
            for name, window in windows.items():
                reference = measure([job for job in known if inside(event(job, 'applied'), window)])
                part = measure([job for job in selected if inside(event(job, 'applied'), window)])
                p = reference['k'] / reference['n'] if reference['n'] else None
                part.update(reference=reference, effect=(part['k'] / part['n'] / p) if part['n'] and p else None)
                row[name] = part
            bands.append(row)
    recommendations = []
    for row in bands:
        effects = [row[name]['effect'] for name in windows]
        up = all(value is not None and value > 1 for value in effects)
        down = all(value is not None and value < 1 for value in effects)
        confirmed = (up or down) and all(row[name]['n'] > 0 for name in windows)
        reference = sum(row[name]['reference']['k'] for name in windows)
        reference_n = sum(row[name]['reference']['n'] for name in windows)
        ratio = row['k'] / row['n'] / (reference / reference_n) if row['n'] and reference else None
        direction = 'apply' if ratio is not None and ratio > 1 else 'skip' if ratio is not None and ratio < 1 else None
        if row['n'] < 15 or not direction: continue
        state = 'confirmed' if confirmed else 'early_signal'
        prefix = 'Prioritize jobs where' if direction == 'apply' else 'Consider skipping jobs where'
        caution = 'This held in both six-week periods.' if confirmed else 'Early signal only; this has not held in both six-week periods.'
        cost = f"{row['connects_per_reply']:.2f} Connects per reply" if row['connects_per_reply'] is not None else 'Connects per reply unknown'
        interval = f"range {whole_percent(row['low'])}% to {whole_percent(row['high'])}%"
        text = f"{prefix} {row['label']}. {row['k']} replies from {row['n']} applications ({whole_percent(row['reply_rate'])}%, {interval}), {cost}. {caution}"
        recommendations.append(dict(row, action=direction, state=state, text=text))
    def priority(row): return row['state'] != 'confirmed', -row['n'], row['dimension'], row['band']
    recommendations.sort(key=priority)
    apply = [row for row in recommendations if row['action'] == 'apply'][:2]
    skip = [row for row in recommendations if row['action'] == 'skip'][:1]
    return {'period': period(bounds), 'windows': {name: period(window) for name, window in windows.items()},
            'reply_horizon_days': 7, 'finished_n': len(finished), 'pending_n': len(candidates) - len(finished),
            'bands': bands, 'apply': apply, 'skip': skip, 'patterns': sorted(apply + skip, key=priority)[:2],
            'empty_text': 'No job patterns to recommend yet. Each needs at least 15 finished applications.',
            'note': 'Application dates in the last 12 weeks. Recent applications wait seven days; only replies within seven days count. Frozen bands and listed Connects costs only.'}


def bh_accept(p_values, level=.1):
    """Benjamini-Hochberg step-up over the entire registered family."""
    ordered = sorted(enumerate(p_values), key=lambda item: (item[1], item[0]))
    last = max((i for i, (_, p) in enumerate(ordered, 1) if p <= level * i / len(ordered)), default=0)
    return {index for index, _ in ordered[:last]}


INSIGHT_BEHAVIOURS = {'first_reply_under_5m': 'Reply within five minutes',
                     'two_call_times': 'Offer two call times', 'follow_up_on_day': 'Follow up on the due day'}
KNOWN_INSIGHT_DIMENSIONS = {'proposals_band', 'posted_age_band', 'payment_verified', 'client_spent_band'}


def insight_fields(jobs, today):
    """Outcome-blind fixed groups, disjoint six-week tests, possible-only behaviour."""
    bounds = span(today, 84)
    middle = bounds[0] + dt.timedelta(days=42)
    windows = {'discovery': (bounds[0], middle - dt.timedelta(days=1)), 'confirmation': (middle, bounds[1])}
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    candidates = [job for job in jobs if not job.get('imported') and
                  (job.get('application_facts') or {}).get('source') == 'outbound']
    finished = [job for job in candidates if inside(event(job, 'applied'), bounds) and event(job, 'applied') + dt.timedelta(days=7) <= cutoff]
    # Families are assembled from source categories alone, never from successes.
    registry = [(dimension, value) for dimension in JOB_FIT_LABELS for value in pipeline.APPLICATION_BANDS[dimension][:-1]]
    registry += [('payment_verified', flag) for flag in (False, True)]
    registry += [('lane', lane) for lane in sorted({str(job['application_facts'].get('lane')) for job in candidates
                  if job['application_facts'].get('lane') not in (None, '', 'unknown')})]
    tag_names = sorted({name for job in candidates for name in (job['application_facts'].get('tags') or {})
                        if day(job['application_facts'].get('tags_registered_at')) and day(job['application_facts']['tags_registered_at']) <= bounds[0]})
    registry += [('tag', name) for name in tag_names]
    def summarize(rows, entry, horizon, outcomes):
        k = sum(any(has_after(job, outcome, entry(job), entry(job) + dt.timedelta(days=horizon)) for outcome in outcomes) for job in rows)
        return {'k': k, 'n': len(rows), 'rate': 100 * k / len(rows) if rows else None, 'evidence': ids(rows)}
    def tested(part, reference):
        p = reference['k'] / reference['n'] if reference['n'] else None
        return dict(part, reference=reference, effect=part['k'] / part['n'] / p if part['n'] and p else None,
                    p=job_fit_exact_p(part['k'], part['n'], p) if p is not None and part['n'] >= 20 else 1.0)
    segments = []
    for dimension, value in registry:
        def known(job):
            facts = job['application_facts']
            if dimension == 'tag':
                registered = timestamp(facts.get('tags_registered_at'))
                return registered is not None and registered <= event(job, 'applied') and value in (facts.get('tags') or {}) and isinstance(facts['tags'][value], bool)
            if dimension == 'payment_verified': return isinstance(facts.get(dimension), bool)
            if dimension == 'lane': return facts.get(dimension) not in (None, '', 'unknown')
            return facts.get(dimension) in pipeline.APPLICATION_BANDS[dimension][:-1]
        population = [job for job in finished if known(job)]
        selected = [job for job in population if (job['application_facts']['tags'][value] is True if dimension == 'tag' else job['application_facts'].get(dimension) == value)]
        row = {'dimension': dimension, 'value': value, 'known_pattern': dimension in KNOWN_INSIGHT_DIMENSIONS,
               **summarize(selected, lambda job: event(job, 'applied'), 7, ('replied',))}
        for name, window in windows.items():
            ref = summarize([job for job in population if inside(event(job, 'applied'), window)], lambda job: event(job, 'applied'), 7, ('replied',))
            part = summarize([job for job in selected if inside(event(job, 'applied'), window)], lambda job: event(job, 'applied'), 7, ('replied',))
            row[name] = tested(part, ref)
        reference_k = sum(row[name]['reference']['k'] for name in windows)
        reference_n = sum(row[name]['reference']['n'] for name in windows)
        row.update(observed=row['rate'], expected=100 * reference_k / reference_n if reference_n else None, lead_ids=row['evidence'])
        segments.append(row)
    behaviours = []
    for key, label in INSIGHT_BEHAVIOURS.items():
        possible = []
        for job in jobs:
            if job.get('imported'): continue
            observation = (job.get('behaviour_observations') or {}).get(key)
            if not isinstance(observation, dict) or not isinstance(observation.get('met'), bool): continue
            start, exposure = timestamp(observation.get('possible_at')), timestamp(observation.get('exposure_at'))
            reply = event(job, 'replied') or timestamp(job.get('first_client_message_at'))
            next_stage = min((event(job, name) for name in ('call_booked', 'call_held', 'offer', 'won') if event(job, name)), default=None)
            if not (start and exposure and reply and reply <= start <= exposure and inside(exposure, bounds)
                    and exposure + dt.timedelta(days=14) <= cutoff and (next_stage is None or exposure < next_stage)): continue
            possible.append(dict(job, behaviour_entry_at=exposure.isoformat(), behaviour_met=observation['met']))
        selected = [job for job in possible if job['behaviour_met']]
        row = {'dimension': 'behaviour', 'value': key, 'label': label, 'known_pattern': False,
               'population': 'Leads with a dated opportunity and exposure before the next stage', 'horizon_days': 14,
               **summarize(selected, lambda job: event(job, 'behaviour_entry'), 14, ('call_booked', 'call_held', 'offer', 'won'))}
        for name, window in windows.items():
            ref = summarize([job for job in possible if inside(event(job, 'behaviour_entry'), window)], lambda job: event(job, 'behaviour_entry'), 14, ('call_booked', 'call_held', 'offer', 'won'))
            part = summarize([job for job in selected if inside(event(job, 'behaviour_entry'), window)], lambda job: event(job, 'behaviour_entry'), 14, ('call_booked', 'call_held', 'offer', 'won'))
            row[name] = tested(part, ref)
        behaviours.append(row)
    rows = segments + behaviours
    for name in windows:
        accepted = bh_accept([row[name]['p'] for row in rows])
        for index, row in enumerate(rows): row[name]['accepted'] = index in accepted
    findings, known_patterns = [], []
    for row in rows:
        effects = [row[name]['effect'] for name in windows]
        direction = 'up' if all(effect is not None and effect >= 1.5 for effect in effects) else 'down' if all(effect is not None and effect <= .67 for effect in effects) else None
        confirmed = direction is not None and all(row[name]['n'] >= 20 and row[name]['accepted'] for name in windows)
        row.update(state='confirmed' if confirmed else 'emerging' if row['discovery']['accepted'] and row['discovery']['n'] >= 20 and row['discovery']['effect'] is not None and (row['discovery']['effect'] >= 1.5 or row['discovery']['effect'] <= .67) else 'unknown', direction=direction)
        if not confirmed: continue
        finding = dict(row, status='confirmed' if row['known_pattern'] else 'finding',
                       action=('Use this more often' if direction == 'up' else 'Try a different approach'),
                       target={'view': 'leads', 'lead_ids': row['evidence']})
        (known_patterns if row['known_pattern'] else findings).append(finding)
    return {'period': period(bounds), 'windows': {name: period(window) for name, window in windows.items()},
            'minimum_per_window': 20, 'bh_level': .1, 'segments': segments, 'behaviour': behaviours,
            'findings': findings, 'known_patterns': known_patterns[:1], 'tag_names': tag_names,
            'note': 'Observed associations against your own rate, checked in separate periods. No causal claim.'}


def facts_sheet(snapshot):
    """All deterministic report inputs, separate from coaching text and client data."""
    keys = ('week', 'generated_at', 'periods', 'north_star', 'funnel_score', 'rank', 'rank_progress',
            'kpis', 'pipeline', 'forecast', 'coverage', 'gap', 'goals_review', 'goals_next', 'badges',
            'call_to_won', 'stage_context', 'conversation_review', 'call_cards', 'conversations', 'reviews')
    result = {key: copy.deepcopy(snapshot.get(key)) for key in keys}
    fit = snapshot.get('insights', {}).get('job_fit', {})
    result['job_fit'] = {key: copy.deepcopy(fit.get(key)) for key in
                        ('period', 'windows', 'reply_horizon_days', 'finished_n', 'pending_n', 'patterns', 'empty_text', 'note')}
    result['insights'] = copy.deepcopy(snapshot.get('insights', {}))
    result['scorecard'] = copy.deepcopy(snapshot.get('presentation', {}).get('scorecard', []))
    result['report_facts'] = report_numeric_facts(snapshot)
    return result


def report_numeric_facts(snapshot):
    """Named numerical facts prevent a value from being borrowed from another metric."""
    kpis = snapshot.get('kpis', {})
    def metric(key, field='value'):
        row = kpis.get(key, {})
        return None if row.get('state') == 'missing' else row.get(field)
    rows = {row['key']: row for row in snapshot.get('presentation', {}).get('scorecard', [])}
    def card(key, field='value'):
        row = rows.get(key, {})
        if row.get('state') == 'missing': return None
        return row.get('finished', {}).get(field) if field in ('k', 'n') else row.get(field)
    activity = snapshot.get('periods', {}).get('activity') or {}
    bounds = (day(activity.get('start')), day(activity.get('end')))
    weekly_calls = [row for row in snapshot.get('call_cards', []) if all(bounds) and inside(row.get('date'), bounds)]
    missing_sources = {row.get('source') for row in coverage_sources(snapshot.get('coverage', {})) if row.get('state') == 'missing'}
    calls_known = all(bounds) and 'upwork' not in missing_sources
    transcripts_known = calls_known and 'recorder' not in missing_sources and all(row.get('reviewable') is True for row in weekly_calls)
    result = {'weekly': {'applications': metric('weekly_volume', 'k'), 'goal': metric('weekly_volume', 'target'),
                'fast': metric('speed_10min', 'k'), 'fast_minutes': 10, 'first_reply_minutes': metric('first_reply'),
                'followups_done': metric('follow_ups_on_time', 'k'), 'followups_due': metric('follow_ups_on_time', 'n'), 'fast_proposals': metric('proposal_on_time', 'k'),
                'calls': len(weekly_calls) if calls_known else None,
                'transcripts_read': sum(row.get('reviewable') is True for row in weekly_calls) if transcripts_known else None},
        'four_weeks': {'applications': card('reply_rate', 'n'), 'replies': card('reply_rate', 'k'), 'reply_rate': card('reply_rate'),
                'previous_reply_rate': rows.get('reply_rate', {}).get('change', {}).get('previous_value'),
                'booked_calls': card('reply_to_call', 'k'), 'held_calls': card('booked_to_held', 'k'),
                'proposals': (card('proposal_to_won', 'n') + rows.get('proposal_to_won', {}).get('pending', {}).get('n', 0)) if number(card('proposal_to_won', 'n')) else None, 'proposal_wins': card('proposal_to_won', 'k'),
                'fast_proposals': snapshot.get('report_facts', {}).get('four_weeks', {}).get('fast_proposals', card('proposal_on_time', 'k') if rows.get('proposal_on_time', {}).get('period_label') == 'Last 28 days' else None), 'fast_proposal_minutes': 30},
        'forecast': {'days': 30, 'value': snapshot.get('forecast', {}).get('next_30_days')},
        'score': snapshot.get('funnel_score', {}).get('score'),
        'previous_score': snapshot.get('funnel_score', {}).get('previous'),
        'wins': snapshot.get('north_star', {}).get('wins'), 'won_value': snapshot.get('north_star', {}).get('value'),
        'previous_goals': len(snapshot.get('goals_review', [])), 'next_goals': len(snapshot.get('goals_next', []))}
    # The writer computes these source details. On record the complete object is
    # compared with a fresh source projection; supplied prose cannot change them.
    if isinstance(snapshot.get('report_facts'), dict):
        def merge(target, supplied):
            for key, value in supplied.items():
                if isinstance(value, dict): merge(target.setdefault(key, {}), value)
                elif number(value) or value is None: target[key] = value
        merge(result, snapshot['report_facts'])
    return result


def report_source_facts(snapshot, jobs, today):
    """Private, plain counts from dated sources; missing observations stay unknown."""
    activity, bounds = span(today, 7), span(today, 28)
    source_missing = any(row.get('source') == 'upwork' and row.get('state') == 'missing' for row in coverage_sources(snapshot.get('coverage', {})))
    weekly_wins = [job for job in jobs if not job.get('imported') and inside(event(job, 'won'), activity)]
    invites = [job for job in jobs if not job.get('imported') and route(job) == 'invite' and inside(event(job, 'invited'), activity)]
    response_by_id = {}; answered_ids = set()
    cutoff = timestamp(snapshot['generated_at'])
    for job in invites:
        rooms = job.get('room_reply_metrics')
        observations = list(rooms.values()) if isinstance(rooms, dict) and rooms else [job]
        candidates = []
        for item in observations:
            reply = timestamp(item.get('first_reply_at'))
            client = timestamp(item.get('first_client_at') or item.get('first_client_message_at'))
            seconds = item.get('first_reply_s')
            if not client and reply and number(seconds): client = reply - dt.timedelta(seconds=seconds)
            if client and inside(client, activity): candidates.append((client, reply))
        if candidates:
            client, reply = min(candidates, key=lambda row: row[0])
            if reply and client <= reply <= cutoff:
                answered_ids.add(str(job['id']))
                response_by_id[str(job['id'])] = (reply - client).total_seconds() / 60
    answered = [job for job in invites if str(job['id']) in answered_ids]
    all_live = [job for job in jobs if not job.get('imported') and job.get('status') in ('applied', 'replied', 'call', 'offer')]
    live_proposals = [job for job in all_live if event(job, 'proposal_sent')]
    live_chats = [job for job in all_live if job.get('status') == 'replied' and not event(job, 'proposal_sent')]
    live_calls = [job for job in all_live if job.get('status') == 'call' and not event(job, 'proposal_sent')]
    quiet_ids = {str(row['lead_id']) for row in conversation_reviews(live_chats, today)['threads']}
    quiet_live = [job for job in live_chats if str(job['id']) in quiet_ids]
    result = {'weekly': {'proposal_wins': sum(bool(event(job, 'proposal_sent')) for job in weekly_wins),
                'direct_offer_wins': sum(route(job) == 'direct_offer' for job in weekly_wins),
                'invites': len(invites), 'invites_answered': len(answered),
                'invites_within_hour': sum(response_by_id[str(job['id'])] <= 60 for job in answered) if len(response_by_id) == len(invites) else None,
                'invite_calls': sum(bool(event(job, 'call_booked')) and event(job, 'call_booked') <= cutoff for job in invites),
                'invite_reply_minutes': max((response_by_id[str(job['id'])] for job in answered), default=None)},
              'live': {'total': len(all_live), 'chats': len(live_chats), 'calls': len(live_calls), 'proposals': len(live_proposals),
                       'proposal_lead_ids': [str(job['id']) for job in live_proposals],
                       'quiet_lead_ids': [str(job['id']) for job in quiet_live],
                       'quiet_to_reopen': len(quiet_live)}}
    activity_kpis, _ = calculate(jobs, today, now=snapshot['generated_at'], activity_bounds=bounds)
    result['four_weeks'] = {'fast_proposals': None if source_missing or activity_kpis['proposal_on_time'].get('unknown_n', 0) else activity_kpis['proposal_on_time']['k']}
    call_facts = report_numeric_facts(dict(snapshot, report_facts={}))['weekly']
    result['weekly'].update(calls=call_facts['calls'], transcripts_read=call_facts['transcripts_read'])
    goals = snapshot.get('goals_review', [])
    times = [row for row in goals if row.get('kpi') == 'reply_to_call']
    budget = [row for row in goals if row.get('kpi') == 'call_review']
    goal_facts = {}
    if len(times) == 1:
        goal = times[0]
        goal_facts.update(offered_times=goal.get('done_k'), replies=goal.get('done_n'))
        done = set(map(str, goal.get('done_lead_ids', [])))
        measured = set(map(str, goal.get('evidence_lead_ids', [])))
        if goal.get('execution_state') not in (None, 'unverified'):
            matching = [job for job in jobs if str(job['id']) in measured]
            goal_facts['booked'] = sum(bool(event(job, 'call_booked')) for job in matching if str(job['id']) in done)
            goal_facts['no_times'] = len(measured - done)
            goal_facts['no_times_booked'] = sum(bool(event(job, 'call_booked')) for job in matching if str(job['id']) not in done)
    if len(budget) == 1:
        goal_facts.update(budget_first=budget[0].get('done_k'), calls=budget[0].get('done_n'))
    if goal_facts: result['goal'] = goal_facts
    if source_missing:
        for values in result.values():
            for key in values: values[key] = None
    return result


REPORT_NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                       'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twice': 2, 'both': 2,
                       'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
                       'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
                       'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60,
                       'seventy': 70, 'eighty': 80, 'ninety': 90, 'hundred': 100,
                       'thousand': 1000, 'million': 1000000, 'billion': 1000000000}
REPORT_WORD_NUMBER = r'\b(?:' + '|'.join(sorted(REPORT_NUMBER_WORDS, key=len, reverse=True)) + r')\b'
REPORT_APPROX_NUMBER = r'\b(?:half[ -]+(?:a[ -]+)?dozen|a[ -]+couple(?:[ -]+of)?|a[ -]+pair(?:[ -]+of)?|(?:a[ -]+)?dozen|(?:a[ -]+hundred|hundreds)|(?:several|many|a[ -]+few|[a-z]+)[ -]+hundreds(?:[ -]+of)?)\b'
REPORT_NUMBER = r'(?:' + REPORT_APPROX_NUMBER + r'|\d(?:[\d,]*\d)?(?:\.\d+)?|' + REPORT_WORD_NUMBER + r'(?:(?:[ -]+(?:and[ -]+)?)' + REPORT_WORD_NUMBER + r')*)'


def report_number_value(token):
    token = token.casefold().replace(',', '').replace('-', ' ')
    if re.fullmatch(r'\d+(?:\.\d+)?', token): return float(token)
    if token in ('dozen', 'a dozen'): return 12
    if token in ('half a dozen', 'half dozen'): return 6
    if token in ('a couple', 'a pair', 'a couple of', 'a pair of'): return 2
    if token == 'a hundred': return 100
    if 'hundreds' in token: return None
    total, group = 0, 0
    for word in re.split(r'[\s-]+', token):
        if word == 'and': continue
        value = REPORT_NUMBER_WORDS.get(word)
        if value is None: return None
        if value == 100: group = max(1, group) * value
        elif value >= 1000: total += max(1, group) * value; group = 0
        else: group += value
    return total + group


def report_claim_text(text):
    """Mask identifiers and source references before matching measured claims."""
    patterns = (
        r'(`+)[\s\S]*?\1',
        r'\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>`"“”]+',
        r'(?<![\w])(?:[A-Za-z]:[\\/]|(?:~|\.{1,2})?[\\/]|[A-Za-z_.-][\w.-]*[\\/])[^\s<>`"“”]+',
        r'(?<![\w])\d[\w.-]*(?:[\\/][\w.-]+)*[\\/][\w.-]+\.[A-Za-z][A-Za-z0-9]*\b',
        r'\b[A-Za-z0-9_][\w.-]*\.[A-Za-z][A-Za-z0-9]*\b',
        r'\b\d{4}-\d{2}-\d{2}(?:[Tt]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[Zz]|[+-]\d{2}:?\d{2})?)?\b',
        r'\b\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[Zz]|[+-]\d{2}:?\d{2})?\b',
        r'(?<!\d)\d{12,}(?!\d)',
        r'(?:\b(?:job(?:\s+ID)?|id)\s*[:#]?\s*|#\s*)[*_]*\d+\b',
    )
    for pattern in patterns:
        text = re.sub(pattern, lambda match: re.sub(r'[^\n]', ' ', match.group()), text, flags=re.I)
    return re.sub(r'[*_]', '', text)


def check_report(text, snapshot):
    """Check stated numbers by their metric and period, never grade the prose.

    Unsupported numerical claims fail closed. Dates/times in a quoted suggested
    message and numbered plan labels are instructions, not observed results.
    Every checked claim returns its named fact path for an auditable result.
    """
    text = report_claim_text(text)
    facts = report_numeric_facts(snapshot)
    checked, errors, covered = [], [], set()
    def value(path):
        current = facts
        for part in path.split('.'):
            if not isinstance(current, dict): return None
            current = current.get(part)
        return current
    def as_number(token):
        return report_number_value(token)
    # Patterns identify quantities by meaning, not by whether their number occurs
    # somewhere else in the snapshot. More specific multi-value clauses go first.
    rules = [
        (r'Funnel Score(?: is)? {a}(?:\s*,?\s*(?:was|up from|down from) {b})?', {'a':'score','b':'previous_score'}),
        (r'(?:signed|won) {a} new contracts? worth\s*\$?{b}', {'a':'wins','b':'won_value'}),
        (r'{a} from proposals? and {b} from a direct offer', {'a':'weekly.proposal_wins','b':'weekly.direct_offer_wins'}),
        (r'(?:sent|submitted) {a} applications? this week against (?:your|a) goal of {b}', {'a':'weekly.applications','b':'weekly.goal'}),
        (r'{a} of them within {b} minutes?', {'a':'weekly.fast','b':'weekly.fast_minutes'}),
        (r'{a} of your {b} applications? got a reply[^.\n]*?that.s {c}%[^.\n]*?(?:from|was) {d}%', {'a':'four_weeks.replies','b':'four_weeks.applications','c':'four_weeks.reply_rate','d':'four_weeks.previous_reply_rate'}),
        (r'(?:started|began) in week {a}', {'a':'pattern.start_week'}),
        (r'First replies took {a} minutes? on median', {'a':'weekly.first_reply_minutes'}),
        (r'{a} of {b} follow-ups', {'a':'weekly.followups_done','b':'weekly.followups_due'}),
        (r'{a} replies led to {b} booked calls?', {'a':'four_weeks.replies','b':'four_weeks.booked_calls'}),
        (r'(?<!neither )Of the other {a}', {'a': lambda: value('four_weeks.replies') - value('four_weeks.booked_calls') if all(number(value(key)) for key in ('four_weeks.replies','four_weeks.booked_calls')) else None}),
        (r'{a} are still talking[^.\n]*?{b} went quiet[^.\n]*?{c} said no', {'a':'four_weeks.active_chats','b':'four_weeks.quiet_chats','c':'four_weeks.declined_chats'}),
        (r'Of the {a} calls, {b} happened and {c} was a no-show', {'a':'four_weeks.booked_calls','b':'four_weeks.held_calls','c':'four_weeks.no_shows'}),
        (r'(?:read|reviewed) {a} of this week.s {b} transcripts?', {'a':'weekly.transcripts_read','b':'weekly.calls'}),
        (r'in {a} of the {b} you quoted before', {'a':'weekly.price_before_budget','b':'weekly.price_read_calls'}),
        (r'{a} the client went careful', {'a':'weekly.cautious_clients'}),
        (r'those {a} calls all led to a proposal, {b} within {c} minutes?', {'a':'four_weeks.held_calls','b':'four_weeks.fast_proposals','c':'four_weeks.fast_proposal_minutes'}),
        (r'{a} signed, {b} of them this week, {c} are still open and {d} were lost', {'a':'four_weeks.proposal_wins','b':'weekly.proposal_wins','c':'four_weeks.open_proposals','d':'four_weeks.lost_proposals'}),
        (r'Only {a} of the {b} had a decision date', {'a':'four_weeks.decision_dates','b':'four_weeks.proposals'}),
        (r'the {a} who said no and the {b} lost proposals[^.\n]*?{c} leads ended[^.\n]*?{d} of them cited price[^.\n]*?under\s*\${e}', {'a':'four_weeks.declined_chats','b':'four_weeks.lost_proposals','c':'four_weeks.ended_leads','d':'four_weeks.price_losses','e':'four_weeks.fixed_price_ceiling'}),
        (r'{a} invites? and you answered all within the hour', {'a':'weekly.invites'}),
        (r'{a} (?:is|are) now (?:a )?calls?', {'a':'weekly.invite_calls'}),
        (r'(?:spent|paid)\s*\${a} on Connects[^.\n]*?(?:signed|won)\s*\${b}', {'a':'four_weeks.connects_spend','b':'four_weeks.application_contract_value'}),
        (r'{a}%\s*vs\s*{b}% across {c} jobs', {'a':'pattern.reply_rate','b':'pattern.comparison_reply_rate','c':'pattern.jobs'}),
        (r'{a} live leads:\s*{b} still talking, {c} calls booked and {d} proposals waiting', {'a':'live.total','b':'live.chats','c':'live.calls','d':'live.proposals'}),
        (r'(?:roughly|about|forecast(?: is| of)?|expect(?:ed)?(?: value)?(?: is| of)?)\s*\${a}[^.\n]*?(?:next|over) {b} days', {'a':'forecast.value','b':'forecast.days'}),
        (r'Last week you set {a} goals', {'a':'previous_goals'}),
        (r'Two call times:\s*you offered them to {a} of the {b} clients', {'a':'goal.offered_times','b':'goal.replies'}),
        (r'{a} of those {b} booked a call and neither of the other {c} did', {'a':'goal.booked','b':'goal.offered_times','c':'goal.no_times'}),
        (r'but {a} conversations? are too few', {'a':'goal.offered_times'}),
        (r'Budget before price happened in only {a} of {b} calls', {'a':'goal.budget_first','b':'goal.calls'}),
        (r'ask {a} open proposals', {'a':'live.proposals'}),
        (r'(?:reopen|review) the {a} quiet conversations', {'a':'live.quiet_to_reopen'}),
        (r'Then {a} habits', {'a':'next_goals'}),
        (r'of the {a} quiet replies', {'a':'four_weeks.quiet_chats'}),
        (r'last {a} weeks', {'a':lambda: 4}),
        (r'{a} weeks before', {'a':lambda: 4}),
        (r'those same {a} weeks', {'a':lambda: 4}),
        (r'Over the {a} weeks', {'a':lambda: 4}),
        (r'about {a} as often', {'a':lambda: round(value('pattern.reply_rate') / value('pattern.comparison_reply_rate')) if number(value('pattern.reply_rate')) and value('pattern.comparison_reply_rate') else None}),
        (r'{a} call times:', {'a':lambda: 2}),
        (r'the {a} replies that went quiet', {'a':'four_weeks.quiet_chats'}),
        # Short independent claims also catch wrong-metric value substitutions.
        (r'Reply rate(?: is| of|:)?\s*{a}%', {'a':'four_weeks.reply_rate'}),
        (r'(?:sent|submitted) {a} applications', {'a':'weekly.applications'}),
        (r'(?:won|signed) {a}(?: new)? contracts?', {'a':'wins'}),
        (r'(?:won|signed)(?: value| work| contracts?| worth| is| of|:)*\s*\${a}', {'a':'won_value'}),
        (r'(?:forecast|expected new work)(?: value| is| of|:)*\s*\${a}', {'a':'forecast.value'}),
        (r'Call rate(?: is| of|:)?\s*{a}%', {'a':lambda: card_rate('reply_to_call')}),
        (r'Show-up rate(?: is| of|:)?\s*{a}%', {'a':lambda: card_rate('booked_to_held')}),
        (r'Win rate(?: is| of|:)?\s*{a}%', {'a':lambda: card_rate('proposal_to_won')}),
    ]
    def card_rate(key):
        row = next((row for row in snapshot.get('presentation', {}).get('scorecard', []) if row.get('key') == key), {})
        return row.get('value')
    def previous_rate(key):
        row = next((row for row in snapshot.get('presentation', {}).get('scorecard', []) if row.get('key') == key), {})
        return row.get('change', {}).get('previous_value')
    comparisons = []
    for label, key in (('Reply rate', 'reply_rate'), ('Call rate', 'reply_to_call'), ('Show-up rate', 'booked_to_held'), ('Win rate', 'proposal_to_won')):
        comparisons.append((re.escape(label) + r' {a}%\s*(?:->|→)\s*{b}%',
                            {'a': lambda key=key: previous_rate(key), 'b': lambda key=key: card_rate(key)}))
        comparisons.append((re.escape(label) + r' {a}%\s*,?\s*(?:was|up from|down from) {b}%',
                            {'a': lambda key=key: card_rate(key), 'b': lambda key=key: previous_rate(key)}))
    rules = comparisons + rules
    def claim_context(match):
        prefix = text[:match.start()]
        # Decimal points do not terminate a statement.
        before = list(re.finditer(r'[.!?](?!\d)|\n', prefix))
        start = before[-1].end() if before else 0
        after = re.search(r'[.!?](?!\d)|\n', text[match.end():])
        end = match.end() + after.start() if after else len(text)
        return text[start:end].casefold()
    def stated_period(context):
        if re.search(r'last week|previous week|week before|last month|previous month', context): return 'previous'
        if re.search(r'this week|current week|last seven days|last 7 days', context): return 'weekly'
        if re.search(r'last (?:four|4) weeks|last 28 days|same (?:four|4) weeks|over (?:the )?(?:four|4) weeks', context): return 'four_weeks'
        return None
    def expected_period(path, match):
        if isinstance(path, str):
            if path.startswith('weekly.') or path in ('wins', 'won_value'): return 'weekly'
            if path.startswith('four_weeks.'): return 'four_weeks'
        # Generic result rates still use the finished last-28-day scorecard.
        if re.search(r'(?:Reply|Call|Show-up|Win) rate', match.group(), re.I): return 'four_weeks'
        return None
    for template, mapping in rules:
        pattern = template
        for name in mapping: pattern = pattern.replace('{' + name + '}', '(?P<' + name + '>' + REPORT_NUMBER + ')')
        for match in re.finditer(pattern, text, re.I):
            for name, path in mapping.items():
                if match[name] is None: continue
                start, end = match.span(name)
                if any(index in covered for index in range(start, end)): continue
                observed = as_number(match[name]); expected = path() if callable(path) else value(path)
                # All member-facing percentages are rounded to whole percentages.
                is_rate = text[end:end+1] == '%' or isinstance(path, str) and path.endswith('reply_rate')
                expected_display = whole_percent(expected) if is_rate and number(expected) else expected
                display_measure = isinstance(path, str) and (path in ('won_value', 'forecast.value') or path.endswith(('_minutes', '_value', 'connects_spend')))
                if not is_rate and display_measure and number(expected):
                    stated_token = match[name].replace(',', '')
                    places = len(stated_token.split('.', 1)[1]) if '.' in stated_token else 0
                    expected_display = display_number(expected, places)
                context = claim_context(match)
                period_claim, period_fact = stated_period(context), expected_period(path, match)
                period_ok = period_claim is None or period_fact is None or period_claim == period_fact
                mapped_periods = {expected_period(mapped, match) for mapped in mapping.values()} - {None}
                if len(mapped_periods) > 1 and period_claim != 'previous': period_ok = True
                # Previous 28-day values belong to the comparison inside the same
                # four-week statement, not to this week's result.
                if path == 'four_weeks.previous_reply_rate' and period_claim == 'four_weeks': period_ok = True
                success = number(expected_display) and observed == expected_display and period_ok
                record = {'text': match.group(), 'stated': observed, 'expected': expected_display,
                          'fact': path if isinstance(path, str) else 'derived linked counts', 'offset': start}
                if not period_ok: record.update(reason='The stated period does not match this fact.', stated_period=period_claim, expected_period=period_fact)
                if '$' in match.group() and isinstance(path, str) and (path in ('won_value', 'forecast.value') or path.endswith(('connects_spend', 'application_contract_value'))):
                    currency = snapshot.get('north_star', {}).get('currency')
                    explicit_other = re.search(r'\b(?:EUR|GBP|CAD|AUD|euro|euros|pounds)\b', context)
                    if currency != 'USD' or explicit_other:
                        success = False; record.update(reason='The stated currency does not match this fact.', expected_currency=currency)
                if is_rate and re.search(r'including (?:the )?pending|pending (?:cases )?count(?:ed)? as lost|counting (?:the )?pending', context):
                    success = False; record['reason'] = 'Rates count finished cases; pending cases are excluded.'
                if re.search(r'(?:Funnel Score|Reply rate|Call rate|Show-up rate|Win rate)', match.group(), re.I) and match.groupdict().get('b') is not None:
                    score, previous = as_number(match['a']), as_number(match['b'])
                    if ('down from' in match.group().casefold() and number(score) and number(previous) and score >= previous or 'up from' in match.group().casefold() and number(score) and number(previous) and score <= previous):
                        success = False; record['reason'] = 'The stated direction contradicts the two scores.'
                (checked if success else errors).append(record)
                covered.update(range(start, end))
    # A suggested message's times and numbers are copy, rather than measurements.
    for match in re.finditer(r'["“]([^"”\n]+)["”]', text):
        before = text[max(0, match.start()-100):match.start()].casefold()
        if any(word in before for word in ('like ', 'say ', 'example', 'message', 'write ', 'offer ')):
            covered.update(range(*match.span()))
    for match in re.finditer(r'^\s*\d+[.)]\s+', text, re.M): covered.update(range(*match.span()))
    # The plan's two concrete times express the fixed coaching action, not a KPI.
    for match in re.finditer(r'offer two concrete times', text, re.I): covered.update(range(*match.span()))
    for match in re.finditer(r'\$?' + REPORT_NUMBER + r'%?', text, re.I):
        if all(index in covered for index in range(match.start(), match.end()) if text[index].isalnum()): continue
        # Words used as a pronoun/determiner are not numerical claims.
        token = match.group().casefold()
        tail = text[match.end():match.end()+35].casefold()
        head = text[max(0,match.start()-35):match.start()].casefold()
        if token in ('one','two','three','both') and (tail.startswith((' thing', ' priority', ' carries over', ' specific question', ' pattern'))): continue
        errors.append({'text': match.group(), 'offset': match.start(), 'fact': None, 'reason': 'No matching metric and period in the facts sheet.'})
    # Quantifiers also have measured meanings when linked to reported counts.
    if re.search(r'answered all within the hour', text, re.I):
        answered, invites = value('weekly.invites_answered'), value('weekly.invites')
        if not number(answered) or answered != invites:
            errors.append({'text':'answered all', 'fact':'weekly.invites_answered', 'expected': invites, 'stated': answered})
        within, minutes = value('weekly.invites_within_hour'), value('weekly.invite_reply_minutes')
        if not number(within) or within != invites or not number(minutes) or minutes > 60:
            errors.append({'text':'within the hour', 'fact':'weekly.invites_within_hour', 'expected': invites, 'stated': within, 'longest_minutes': minutes})
    if re.search(r'neither of the other', text, re.I) and value('goal.no_times_booked') != 0:
        errors.append({'text':'neither booked', 'fact':'goal.no_times_booked', 'expected': 0, 'stated': value('goal.no_times_booked')})
    return {'status': 'PASS' if not errors else 'FAIL', 'week': snapshot.get('week'),
            'checked_values': len(checked), 'checks': checked, 'errors': errors,
            'scope': 'Stated numerical facts only; wording and coaching judgment are not graded.'}


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
    approved = public_agreed_goals(week)
    safe_reviews = [row for row in reviews if row.get('goal_id') in approved]
    latest_start = max((row.get('start', '') for row in safe_reviews), default='')
    reviews = [row for row in safe_reviews if row.get('start', '') == latest_start][:3]
    # Frozen §13: all public conversion entries share the oldest (28-day)
    # maturity window. Activity applications remain a separate seven-day count.
    bounds = tuple(value - dt.timedelta(days=28) for value in span(today, 28))
    def public_rate(key, entry, outcomes, horizon, window, target):
        rows = cohort(jobs, entry, 0, today, window, 'outbound')
        if key == 'booked_to_held':
            rows = []
            cutoff = run_timestamp(today, now)
            for job in jobs:
                session = (job.get('call_sessions') or {}).get(job.get('call_session_id')) or {}
                scheduled = attendance_start(job)
                if (not job.get('imported') and route(job) == 'outbound' and scheduled and inside(scheduled, window)
                        and scheduled + dt.timedelta(days=2) <= cutoff and not session.get('cancelled')):
                    held = timestamp(session.get('held_at')) if session else event(job, 'call_held')
                    rows.append(dict(job, attendance_entry_at=scheduled.isoformat(), attendance_held_at=held.isoformat() if held else None))
            entry, outcomes = 'attendance_entry', ('attendance_held',)
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
              'activity_period': period(span(today, 7)), 'streak_weeks': streak, 'goals_done': f"{sum(row['done_n'] > 0 and row['done_k'] == row['done_n'] for row in reviews)}/{len(reviews)}",
              'goals': [{'goal_id': row['goal_id'], 'goal_library_id': approved[row['goal_id']],
                        'text': PUBLIC_GOAL_LIBRARY[approved[row['goal_id']]][1], 'done': row['done_n'] > 0 and row['done_k'] == row['done_n'],
                        'k': row['done_k'], 'n': row['done_n'], 'state': row.get('execution_state', 'unverified')} for row in reviews],
              'next_focus': None, 'question_id': None, 'new_badge': None, 'top_badges': [], 'member_name': public_member_name()}
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
    now_stamp = run_timestamp(today, now)
    entries = {name: cohort(jobs, event_key, 0, today, bounds, 'outbound') for name, event_key in
               (('applications', 'applied'), ('replies', 'replied'), ('calls_booked', 'call_booked'), ('calls_held', 'call_held'), ('proposals', 'proposal_sent'))}
    result['stage_counts'] = {name: len(rows) for name, rows in entries.items()}
    result['stage_counts']['won'] = result['proposal_to_won']['k']
    result['stage_counts']['pending_proposals'] = sum(event(job, 'proposal_sent') + dt.timedelta(days=21) > now_stamp for job in entries['proposals'])
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in source_coverage(jobs, today, now)[0]):
        for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won', 'call_to_won'):
            result[key].update(value=None, k=None, n=None, state='missing')
        result['applications'] = None
        result['first_reply_median_min'] = None
        result['stage_counts'] = {name: None for name in result['stage_counts']}
    return result


def badge_results(snapshot, jobs, history, today, snapshot_only=False):
    """Retain tiers; Steady Hand uses best commitment streak, others qualifying weeks."""
    week = snapshot['week']; prior = {row['week']: row for row in history if row.get('week', '') < week}
    all_rows = list(prior.values()) + [snapshot]
    old = {}
    for row in all_rows[:-1]:
        for badge in row.get('badges', []):
            badge = dict(badge, badge=badge_ledger.canonical_name(badge.get('badge')))
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
        if name == 'Steady Hand':
            volume = row.get('kpis', {}).get('weekly_volume', {})
            return number(volume.get('value')) and number(volume.get('target')) and volume['target'] > 0 and volume['value'] >= volume['target']
        if name in recorded: return recorded[name] is True
        kpis = row.get('kpis', {})
        if name in OUTCOME_BADGES:
            key, thresholds = OUTCOME_BADGES[name]
            item = row.get('call_to_won', {}) if key == 'call_to_won' else kpis.get(key, {})
            phase = kpis.get('proposal_to_won' if key == 'call_to_won' else key, {}).get('baseline_phase', True)
            return not phase and item.get('state') != 'missing' and (item.get('n') or 0) > 0 and wilson(item['k'], item['n'])[0] >= thresholds[0]
        mapping = {'Swift Sail': 'speed_10min', "Ship's Bell": 'first_reply', 'Lookout': 'follow_ups_on_time', 'Quick Draw': 'proposal_on_time'}
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
    streak = snapshot.get('accountability', {}).get('application_streak')
    if streak is None:
        replay = badge_ledger.streak_history(history, week=week, current=snapshot)
        streak = {'current': replay['streak_weeks'], 'best': replay['best_streak_weeks'], 'weeks': replay['weeks']}
    qualifying['Steady Hand'] = any(row['week'] == badge_ledger.commitment_week(snapshot) and row['state'] == 'met' for row in streak['weeks'])
    qualifying['Navigator'] = qualifying['Navigator'] and all(qualifying[name] for name in ('Swift Sail', "Ship's Bell", 'Lookout', 'Steady Hand', 'Quick Draw'))
    if snapshot_only:
        qualifying.update({badge_ledger.canonical_name(name): value for name, value in snapshot.get('badge_qualifying', {}).items() if badge_ledger.canonical_name(name) in BADGE_NAMES and name not in ('Steady Anchor', 'Steady Hand')})
    snapshot['badge_qualifying'] = qualifying
    counts = {name: sum(criterion(row, name) for row in all_rows) for name in BADGE_NAMES}
    counts['Steady Hand'] = streak['best']
    snapshot['badge_progress'] = {}
    first_week = not prior
    first_names = {name for name, tier in old if old[(name, tier)].get('earned_week') == week}
    result = []
    priority = ('Steady Hand', 'Swift Sail', "Ship's Bell", 'Lookout', 'Quick Draw', 'True North') + tuple(name for name in BADGE_NAMES if name not in ('Steady Hand', 'Swift Sail', "Ship's Bell", 'Lookout', 'Quick Draw', 'True North'))
    for name in priority:
        limit = 1 if name == 'Back on Course' else 5
        thresholds = (1,) if limit == 1 else badge_ledger.QUALIFYING_WEEKS
        reached = max([index for index, threshold in enumerate(thresholds) if counts[name] >= threshold] +
                      [TIERS.index(tier) for old_name, tier in old if old_name == name], default=-1)
        next_index = reached + 1
        progress_count = streak['current'] if name == 'Steady Hand' else counts[name]
        progress = 'All tiers earned' if next_index >= limit else f'{min(progress_count, thresholds[next_index])} of {thresholds[next_index]} ' + ('returns' if name == 'Back on Course' else 'weeks')
        target = thresholds[min(next_index, limit - 1)]
        numeric_progress = {'current': progress_count, 'target': target,
                            'remaining': max(0, target - progress_count), 'unit': 'returns' if name == 'Back on Course' else 'weeks'}
        if next_index >= limit: numeric_progress['remaining'] = 0
        snapshot['badge_progress'][name] = numeric_progress
        for index in range(reached + 1):
            tier = TIERS[index]; earned = old.get((name, tier))
            if earned is None and first_week and name not in first_names and len(first_names) >= 2: continue
            if earned is None and first_week: first_names.add(name)
            result.append({'badge': name, 'tier': tier, 'earned_week': earned['earned_week'] if earned else week,
                           'new': earned is None or earned['earned_week'] == week, 'progress_to_next': progress,
                           'progress': numeric_progress})
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
        result.append({'goal_id': identity, 'kpi': goal['kpi'], 'change': goal['change'], 'text': goal['change'], 'cue': goal['cue'], 'action': goal['action'],
            'coach_example': example, 'example_state': 'saved' if example else 'unknown',
            'example_prompt': None if example else 'Supply a coach example selected for this goal.',
            'execution_unit': unit, 'review_on': goal['review_on'],
            'measurement': f"Review completed {unit} on {goal['review_on']}; execution and effect are checked separately." if unit else None})
    return result


def canonical_badge_view(value):
    """Normalize legacy names in a read copy, including badge-keyed progress maps."""
    if isinstance(value, dict):
        return {badge_ledger.canonical_name(key): badge_ledger.canonical_name(item) if
                key in ('badge', 'name') and isinstance(item, str) else canonical_badge_view(item)
                for key, item in value.items()}
    if isinstance(value, list): return [canonical_badge_view(item) for item in value]
    return value


def saved_snapshot_view(snapshot, history=None):
    """Keep stable product ranks and remove duplicated timing points in a copy."""
    result = canonical_badge_view(copy.deepcopy(snapshot))
    if not result.get('badge_progress') and result.get('week') and result.get('kpis'):
        replay = copy.deepcopy(result)
        badge_results(replay, [], read_lines('analytics-history.jsonl') if history is None else history,
                      day(result.get('generated_at')) or as_today(), snapshot_only=True)
        result['badge_progress'] = replay['badge_progress']
        for voyage in (result.get('voyage'), result.get('presentation', {}).get('voyage')):
            if isinstance(voyage, dict):
                for station in voyage.get('stations', []):
                    station['progress'] = copy.deepcopy(result['badge_progress'].get(station.get('badge')))
    if re.fullmatch(r'\d{4}-W\d{2}', str(result.get('week', ''))):
        rank = rank_fields(result, read_lines('analytics-history.jsonl') if history is None else history)
        result.update(rank=rank['rank'], rank_progress=rank)
        presentation = result.get('presentation')
        if isinstance(presentation, dict):
            presentation.update(rank=rank['rank'], rank_progress=copy.deepcopy(rank))
            for name in ('voyage', 'progress_strip'):
                if isinstance(presentation.get(name), dict): presentation[name].update(rank=rank['rank'], rank_progress=copy.deepcopy(rank))
            if isinstance(presentation.get('scorecard'), list): presentation['progress_strip'] = dict(presentation.get('progress_strip') or {}, **progress_strip(result))
        if isinstance(result.get('voyage'), dict): result['voyage'].update(rank=rank['rank'], rank_progress=copy.deepcopy(rank))
        if isinstance(result.get('community_card'), dict): result['community_card'].update(rank=rank['rank'], rank_progress=copy.deepcopy(rank))
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


def call_quote_time(quote, transcript):
    """Return only a recorded timecode for the exact quoted transcript turn."""
    if not isinstance(quote, str) or not quote.strip(): return None
    current = None
    for line in transcript.splitlines():
        stamp = re.match(r'^\s*(?:(?:[^:\n]{1,80}:\s*)?\[(\d{1,2}:\d{2}(?::\d{2})?)\]|(\d{1,2}:\d{2}(?::\d{2})?)(?=\s|$))', line)
        if stamp: current = stamp[1] or stamp[2]
        if quote in line: return current
    return None


def reviewed_call_at(job):
    saved = (job.get('call_reviews') or {}).get(job.get('call_review_session')) or {}
    return timestamp(saved.get('call_at')) or event(job, 'call_held')


def merge_review(canonical, weekly):
    """Overlay recorded fields, retaining omitted canonical point metadata by ID."""
    saved = dict(canonical, **weekly)
    if 'points' not in weekly: return saved
    def indexed(points):
        rows = [dict(point, point=key) for key, point in points.items()] if isinstance(points, dict) else points
        return {str(point['point']): copy.deepcopy(point) for point in rows if isinstance(point, dict) and 'point' in point}
    points = indexed(canonical.get('points', []))
    for key, point in indexed(weekly['points']).items():
        original = points.get(key, {})
        points[key] = dict(original, **point)
        if 'point' in original: points[key]['point'] = original['point']
    saved['points'] = list(points.values())
    return saved


def call_cards(snapshot, jobs=None):
    review = snapshot.get('reviews', {}).get('call', {})
    by_id = {str(job['id']): job for job in (pipeline.load() if jobs is None else jobs)}
    cards = []
    rubrics = list(review.get('rubric', [])); reviewed = {str(item['lead_id']) for item in rubrics}
    for jid, job in by_id.items():
        if jid not in reviewed and reviewed_call_at(job) and inside(reviewed_call_at(job), (day(snapshot['generated_at']) - dt.timedelta(days=28), day(snapshot['generated_at']))):
            saved = job.get('call_review') if not _RECONSTRUCTING.get() else None
            rubrics.append(dict(saved, lead_id=jid) if isinstance(saved, dict) else {'lead_id': jid, 'reviewable': False, 'points': []})
    for item in rubrics:
        job = by_id.get(str(item['lead_id']), {})
        item = merge_review(assessment(job, 'call_review') or {}, item)
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
        transcript = read_source(path) or ''
        stats = call_stats.analyze(transcript)
        duration = stats.get('duration_s', job.get('call_duration_s'))
        card = {'lead_id': item['lead_id'], 'label': job.get('title') or 'Untitled job', 'title': job.get('title') or 'Untitled job',
                'date': day(reviewed_call_at(job)).isoformat() if reviewed_call_at(job) else None,
                'duration_minutes': duration / 60 if number(duration) else None,
                'talk_share': stats.get('talk_share_pct', job.get('talk_share_pct')),
                'questions': stats.get('question_counts', job.get('question_counts')),
                'reviewable': bool(item.get('reviewable') and stats.get('transcript_complete') is True and stats.get('member_attributed') is True)}
        # Compatibility aliases read by the current private card component.
        coach_read = (item.get('free_read') or coach_read) if card['reviewable'] else None
        if coach_read is not None:
            short_text(coach_read, 180, 'Call free read')
            require(len(coach_read.split()) >= 120, 'Call free read needs 120 to 180 words.')
        reviewed_at = saved_review_time(job, item)
        card.update(as_of=reviewed_at, reviewed_at=reviewed_at,
            coach_read=coach_read, coach_read_state='present' if coach_read else 'unknown', coach_read_prompt='No review yet: run /call-review ' + str(item['lead_id']))
        card.update(agreed_step=item.get('agreed_step') or item.get('next_step') or agreed_step,
                    next_message=item.get('next_message') or next_message,
                    source_prompt=('Run /call-review ' + str(item['lead_id']) + ' to review the full saved transcript.' if stats.get('transcript_complete') is True and stats.get('member_attributed') is True else 'Paste the full speaker-labelled transcript into jobs/' + str(item['lead_id']) + '/call.md, then run /call-review ' + str(item['lead_id'])))
        if card['next_message'] is not None: short_text(card['next_message'], 100, 'Call next message')
        card.update(duration_min=card['duration_minutes'], question_count=(card['questions'] or {}).get('member'))
        if not card['reviewable']:
            card.update(reason=('Not reviewed. Call review missing.' if stats.get('transcript_complete') is True and stats.get('member_attributed') is True else 'Not reviewed. Transcript missing or incomplete.'), points=[], moments=[],
                        fix='', example='', next_step=None, agreed_step=None, next_message=None)
        else:
            points = [dict(next((p for p in item['points'] if p['point'] == index),
                           {'state': 'missing', 'reason': None, 'quote': None}), point=index) for index in range(1, 10)]
            for point in points:
                point.update(label=CALL_POINT_LABELS[point['point']], definition=CALL_POINT_DEFINITIONS.get(point['point']))
                point['quote_state'] = 'supported' if point.get('quote') and point['quote'] in call_utterances(transcript) else 'unknown'
                point['quote_at'] = call_quote_time(point.get('quote'), transcript)
                if point['quote_state'] != 'supported': point.pop('quote', None)
            card.update(points=points, moments=[dict(moment, better=moment['better_wording'], quote_at=call_quote_time(moment.get('quote'), transcript)) for moment in item.get('moments', [])[:3]],
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
        value = row.get('value')
        if change.get('previous_n') == 0: continue
        if not (number(value) and number(previous)) or row.get('state') == 'missing': continue
        if not row.get('n', row.get('finished', {}).get('n')): continue
        direction = snapshot.get('kpis', {}).get(row['key'], {}).get('direction', 'up')
        movement = (value - previous) * (-1 if direction == 'down' else 1)
        if not movement: continue
        strength = movement / max(abs(previous), 1)
        unit = row.get('series', {}).get('unit') or snapshot.get('kpis', {}).get(row['key'], {}).get('unit', '')
        display = lambda value: f'{whole_percent(value)}%' if unit == '%' else f'{display_number(value):.0f} min' if unit == 'min' else f'${display_number(value):,.0f}' if unit == '$' else f'{display_number(value):,.0f}'
        candidates.append((strength, row['key'], {'key': row['key'], 'name': row['name'],
            'text': f"{row['name']} {display(previous)} -> {display(value)}", 'change_text': 'vs the 4 weeks before',
            'direction': 'gain' if movement > 0 else 'decline', 'value': value, 'previous': previous,
            'previous_n': change.get('previous_n'), 'n': row.get('finished', {}).get('n', row.get('n'))}))
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
    if newest is None and contenders and latest_week == snapshot.get('week'):
        newest = min(contenders, key=lambda row: (-TIERS.index(row['tier']) if row.get('tier') in TIERS else 0, row.get('badge', '')))
        basis = 'Earned this week; selected by tier and name, no chronology claimed.'
    return {'biggest_change': chosen[2] if chosen else None,
            'newest_badge': copy.deepcopy(newest) if newest and newest.get('earned_week') == snapshot.get('week') else None,
            'newest_badge_basis': basis}


def application_loom_fields(job, folder, sent, transcript):
    """Sent copy establishes delivery; saved job instructions establish the request."""
    post = read_source(folder / 'job.md') or job.get('description') or ''
    mentions = [line for line in re.split(r'[.\n]', post) if re.search(r'\b(?:loom|walkthrough|video)\b', line, re.I)]
    requested = any(re.search(r'\b(?:please|include|send|record|provide|required|must|need|request)\b', line, re.I)
                    and not re.search(r'\b(?:optional|not required|not needed|no need|do not|don.t)\b', line, re.I) for line in mentions)
    known = bool(sent.strip()) and job.get('application_sent_verified') is True and not _RECONSTRUCTING.get()
    # A stale loom_url on the job cannot override the exact sent application.
    positive = [line for line in re.split(r'[.\n]', sent) if not re.search(r'\b(?:not|no|never|haven.t|didn.t|without)\b', line, re.I)]
    sent_loom = bool(re.search(r'https?://(?:www\.)?(?:loom\.com|youtu\.be|youtube\.com)/', sent, re.I) or
        re.search(r'\b(?:my|this|the|a)\s+(?:short\s+)?loom\s+(?:shows|covers|walks|explains)|\b(?:included|attached)\s+(?:a\s+|the\s+|my\s+)?(?:short\s+)?loom\b', '\n'.join(positive), re.I))
    status = 'unknown' if not known else 'sent' if sent_loom else 'requested_not_sent' if requested else 'not_sent'
    return {'loom_status': status, 'loom_requested': bool(requested),
            'loom_source_state': 'present' if status == 'sent' and transcript else 'unknown' if status in ('sent', 'unknown') else 'not_applicable'}


def conversations_fields(snapshot, jobs):
    """Project saved coaching and sent evidence; never turn source text into coach judgment."""
    sections = {'applications': [], 'chats': [], 'calls': copy.deepcopy(snapshot.get('call_cards', [])), 'proposals': []}
    statements = {}
    saved_by_entry = {}
    def full_points(saved, stage):
        points = saved.get('points', [])
        points = [dict(point, point=key) for key, point in points.items()] if isinstance(points, dict) else points
        labels = APPLICATION_POINT_LABELS if stage == 'applications' else CHAT_POINT_LABELS if stage == 'chats' else CALL_POINT_LABELS if stage == 'calls' else {}
        return [dict(copy.deepcopy(point), label=labels.get(point.get('point')) or point.get('label'))
                for point in points if isinstance(point, dict)]
    def supported_points(saved, text):
        points = saved.get('points', [])
        points = [dict(point, point=key) for key, point in points.items()] if isinstance(points, dict) else points
        return [copy.deepcopy(point) for point in points if isinstance(point, dict) and
                isinstance(point.get('quote'), str) and point['quote'].strip() and point['quote'] in text]
    def remember(stage, row, saved, text):
        if not row.get('date') or row.get('title') == 'Untitled job': return
        points = full_points(saved, stage)
        finding = public_normalized(row['key_finding'])
        for point in points:
            sentence = saved.get('pattern_sentence') or point.get('pattern_sentence') or point.get('reason')
            better = (point.get('better_line') if point.get('pattern_sentence') else None) or saved.get('better_line') or point.get('better_line') or saved.get('example')
            reason = str(point.get('reason') or '').strip()
            if not isinstance(better, str) or not better.strip() or not pipeline.count_free_pattern(sentence): continue
            key = ('finding', finding) if saved.get('pattern_sentence') else ('point', public_normalized(reason or point.get('pattern_sentence')))
            bucket = statements.setdefault(key, {'sentence': sentence, 'better_line': better, 'entries': set(), 'quotes': []})
            bucket['entries'].add((stage, str(row['lead_id'])))
            if not isinstance(point.get('quote'), str) or not point['quote'].strip() or point['quote'] not in text: continue
            record = {key: row[key] for key in ('lead_id', 'title', 'date')}
            record.update(stage=stage, quote=point['quote'])
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
            saved = merge_review(saved, rubric)
            valid = bool(source) and not _RECONSTRUCTING.get()
            extra = {}
            if stage == 'applications':
                valid = valid and job.get('application_sent_verified') is True
                loom = read_source(folder / 'loom-transcript.txt') or read_source(folder / 'loom.md') or ''
                extra.update(application_loom_fields(job, folder, source, loom))
                loom_used = extra['loom_status'] == 'sent'
                if loom_used and not loom:
                    valid = False
                    prompt = 'Supply the Loom transcript at jobs/' + jid + '/loom.md, or run code/loom.py ' + jid + ' <verified Loom URL>.'
                extra.update(sent_copy=source if job.get('application_sent_verified') is True and source else None,
                             loom_transcript=loom or None)
                source += '\n' + loom
            if stage == 'chats':
                thread = chats.get(jid, {})
                valid = valid and thread.get('read') is True
                saved = dict(saved, **{key: value for key, value in thread.items() if key != 'points' and
                                      (key not in ('free_read', 'next_message') or key not in saved)})
                extra['last_writer'] = thread.get('last_writer', 'unknown')
                try:
                    raw = json.loads(source)
                    rooms = list((raw.get('rooms') or {}).values()) or [raw]
                    source = '\n'.join(str(turn.get('text') or '') for room in rooms for turn in room.get('messages', []) if turn.get('from') in ('me', 'client'))
                except (ValueError, TypeError): valid = False; source = ''
            saved_by_entry[(stage, jid)] = (saved, source)
            points = full_points(saved, stage)
            supported = supported_points(saved, source) if valid else []
            quote = saved.get('quote')
            quote = quote if valid and isinstance(quote, str) and quote.strip() and quote in source else next((p['quote'] for p in supported), None)
            # Existing weekly examples are evidence only if they actually quote this sent source.
            if not quote and valid and jid in weekly.get('evidence_lead_ids', []):
                example = weekly.get('example')
                if isinstance(example, str) and example.strip() and example in source: quote = example
            supported_review = not any(point.get('quote') and (not isinstance(point['quote'], str) or point['quote'] not in source) for point in points)
            reviewable = bool(valid and points and supported_review and (saved.get('read') is True or saved.get('reviewable') is True or saved.get('state') in ('pass', 'fail', 'unclear')))
            for point in points:
                if not valid or not isinstance(point.get('quote'), str) or point['quote'] not in source:
                    point.pop('quote', None)
            if stage == 'proposals':
                # Only quoted saved judgments/facts; never guess terms from prose.
                for key in ('scope', 'price', 'decision_date'):
                    fact = saved.get(key)
                    extra[key] = fact if reviewable and isinstance(fact, str) and fact.strip() and fact in source else None
                if any(extra[key] is None for key in ('scope', 'price', 'decision_date')):
                    extra['source_prompt'] = 'Save quoted scope, price and decision date from the sent proposal; missing facts remain unknown.'
            if stage == 'applications' and reviewable and not loom_used and not any(point.get('point') == 7 for point in points):
                points.append({'point': 7, 'label': APPLICATION_POINT_LABELS[7],
                               'state': 'not_needed', 'reason': 'No Loom used'})
            read = saved.get('free_read') if reviewable else None
            next_message = saved.get('next_message') if reviewable else None
            if next_message is not None: short_text(next_message, 100, 'Coaching next message', optional=True)
            sections[stage].append({'lead_id': jid, 'label': job.get('title') or 'Untitled job', 'title': job.get('title') or 'Untitled job',
                'date': day(event(job, event_key)).isoformat(), 'reviewable': reviewable,
                'source_prompt': None if reviewable else prompt if not valid else 'Record a quoted ' + kind + ' content review for ' + jid + '.',
                'points': points, 'quote': quote if reviewable else None,
                'read': read, 'next_message': next_message, 'as_of': saved_review_time(job, saved, kind),
                'reviewed_at': saved_review_time(job, saved, kind), **extra})
    reported_period = badge_ledger.commitment_period(snapshot)
    week_start = day(reported_period.get('start')) or day(snapshot['generated_at']) - dt.timedelta(days=day(snapshot['generated_at']).weekday())
    week_end = day(reported_period.get('end')) or day(snapshot['generated_at'])
    by_id = {str(job['id']): job for job in jobs}
    for stage, rows in sections.items():
        for row in rows:
            job = by_id.get(str(row['lead_id']), {})
            kind = {'applications': 'application', 'chats': 'conversation', 'calls': 'call', 'proposals': 'proposal'}[stage]
            saved = assessment(job, kind + '_review') or {}
            rubric = next((item for item in snapshot.get('reviews', {}).get(kind, {}).get('rubric', []) if str(item.get('lead_id')) == str(row['lead_id'])), {})
            saved = merge_review(saved, rubric)
            if stage == 'calls': saved_by_entry[(stage, str(row['lead_id']))] = (dict(saved, points=row.get('points', [])), call_utterances(read_source(pipeline.jobs_dir() / str(row['lead_id']) / 'call.md') or ''))
            points = row.get('points', [])
            points = list(points.values()) if isinstance(points, dict) else points
            weakness = next((point for point in points if point.get('state') in ('missing', 'partly')), None)
            finding = saved.get('key_finding')
            if not finding:
                read = saved.get('free_read') or row.get('coach_read') or row.get('read') or ''
                finding = re.split(r'(?<=[.!?])\s+', read.strip(), maxsplit=1)[0]
            if not row.get('reviewable'):
                finding = 'Supply the source to get a review'
            elif not finding:
                finding = 'Open the review for the coach’s read'
            row['key_finding'] = ' '.join(str(finding).split()[:12]).rstrip(' ,;:')
            row['title'] = job.get('title') or row.get('title') or row.get('label') or 'Untitled job'
            row['marker'] = 'not reviewed' if not row.get('reviewable') else 'needs work' if weakness else 'keep'
            labels = APPLICATION_POINT_LABELS if stage == 'applications' else CHAT_POINT_LABELS if stage == 'chats' else CALL_POINT_LABELS if stage == 'calls' else {}
            for point in points: point['label'] = labels.get(point.get('point')) or point.get('label')
            required = set(labels) - ({7} if stage == 'applications' else set())
            if row.get('reviewable') and (not points or required - {p.get('point') for p in points} or any(p.get('state') not in ('met', 'not needed', 'not_needed') for p in points)):
                row['marker'] = 'needs work'
            row['better_line'] = saved.get('better_line') or saved.get('example') or row.get('example')
            row['pattern_sentence'] = saved.get('pattern_sentence')
            row['importance'] = 0 if row['marker'] == 'needs work' else 1
            observed = day(row.get('date'))
            row['this_week'] = bool(observed and week_start <= observed <= week_end)
        rows.sort(key=lambda row: (row['importance'], -(day(row.get('date')) or dt.date.min).toordinal(), row['title']))
    # Display the same finding once at the first stage while retaining later evidence.
    first_findings = {}
    for stage in ('applications', 'chats', 'calls', 'proposals'):
        for row in sections[stage]:
            if not row.get('reviewable'): continue
            identity = (str(row['lead_id']), public_normalized(row['key_finding']))
            first_stage = first_findings.setdefault(identity, stage)
            if first_stage != stage: row['duplicate_of_stage'] = first_stage
    # One entry per job/stage. Repeated input rows never inflate a denominator.
    for stage, rows in sections.items():
        sections[stage] = list({str(row['lead_id']): row for row in rows}.values())
        for row in sections[stage]:
            if row.get('reviewable'):
                saved, source = saved_by_entry.get((stage, str(row['lead_id'])), ({}, ''))
                remember(stage, row, saved, source)
    patterns = []
    for key, bucket in statements.items():
        stages = {stage for stage, jid in bucket['entries']}
        if len(stages) < 2: continue
        reviewed = [(stage, row) for stage in stages for row in sections[stage] if row.get('reviewable')]
        entries = {(stage, str(row['lead_id'])) for stage, row in reviewed if
                   public_normalized(row['key_finding']) == key[1]} if key[0] == 'finding' else bucket['entries']
        k, n = len(entries), len(reviewed)
        if k < 2 or not n: continue
        sentence = bucket['sentence'].replace('{k}', str(k)).replace('{n}', str(n)).strip()
        quotes, seen = [], set()
        for quote in bucket['quotes']:
            identity = public_normalized(quote['quote'])
            if identity in seen: continue
            seen.add(identity); quotes.append(quote)
            if len(quotes) == 2: break
        if not quotes: continue
        patterns.append({'text': f'In {k} of {n} reviewed conversations, {sentence}', 'k': k, 'n': n,
                         'better_line': bucket['better_line'], 'quotes': quotes})
    patterns.sort(key=lambda row: (-row['k'], row['text']))
    return {'patterns': patterns[:3], 'sections': sections, 'criteria': conversation_criteria(sections)}


def call_utterances(text):
    return '\n'.join(match[2] for match in re.finditer(r'^([^:\n]+):\s*(.+)$', text, re.M)
        if match[1].strip().casefold() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language'))


def conversation_criteria(sections):
    result = {}
    for stage, rows in sections.items():
        reviewed = list({str(row['lead_id']): row for row in rows if row.get('reviewable')}.values())
        labels = dict(APPLICATION_POINT_LABELS if stage == 'applications' else CHAT_POINT_LABELS if stage == 'chats' else CALL_POINT_LABELS if stage == 'calls' else {})
        for row in reviewed:
            for point in row.get('points', []):
                if point.get('label'): labels.setdefault(point['point'], point['label'])
        aggregate = []
        for point, label in labels.items():
            counts = dict(met=0, partly=0, missing=0, not_needed=0)
            leads, reasons = [], []
            for row in reviewed:
                judgment = next((p for p in row.get('points', []) if p.get('point') == point), None)
                if judgment is None: continue
                state = str(judgment.get('state', '')).replace(' ', '_')
                if state not in counts: continue
                counts[state] += 1
                if state != 'not_needed': leads.append(str(row['lead_id']))
                if state in ('missing', 'partly') and judgment.get('reason'):
                    reasons.append((state != 'missing', str(judgment['reason'])))
            aggregate.append({'point': point, 'label': label, **counts, 'k': counts['met'],
                'n': sum(counts[state] for state in ('met', 'partly', 'missing')), 'lead_ids': sorted(set(leads)),
                'reason': min(reasons)[1] if reasons else None})
        result[stage] = {'points': aggregate, 'reviewed_n': len(reviewed), 'too_few': len(reviewed) < 3}
    return result


def voyage_fields(snapshot, history):
    history = [row for row in history if row.get('week') != snapshot['week']] + [snapshot]
    runs = {row['week'] for row in history}
    saved = snapshot.get('accountability', {}).get('application_streak')
    streak = {'streak_weeks': saved['current'], 'best_streak_weeks': saved['best'], 'anchors_used': []} if saved else badge_ledger.streak_history(history, week=snapshot['week'])
    anchors = set(streak['anchors_used'])
    calendar = []
    for row in snapshot.get('daily_applications', []):
        date = day(row['date']); iso = date.isocalendar(); week = f'{iso.year}-W{iso.week:02d}'
        calendar.append(dict(row, qualified_count=row['count'], evidence=row.get('lead_ids', []), week=week, run=week in runs,
                             anchor=week in anchors, commitment=bars()['weekly_volume'] / 5 if date.weekday() < 5 else None, completion=min(row['count'] / (bars()['weekly_volume'] / 5), 1) if number(row['count']) and date.weekday() < 5 and bars()['weekly_volume'] > 0 else None, level='unknown' if row['count'] is None else 'unplanned' if date.weekday() >= 5 else 'completed' if row['count'] >= bars()['weekly_volume'] / 5 else 'open'))
    goals = [dict(goal, week=row['week']) for row in sorted(history, key=lambda row: row['week']) for goal in row.get('goals_review', [])]
    base = {'calendar': calendar, 'calendar_period': {'start': calendar[0]['date'], 'end': calendar[-1]['date']} if calendar else None,
            'goals_history': goals, 'streak_weeks': streak['streak_weeks'], 'best_streak_weeks': streak['best_streak_weeks'], 'anchors_used': []}
    awards = badge_ledger.read_ledger()
    retained = {(row['badge'], row['tier']) for row in awards}
    # The same weekly awards will be persisted at generated_at. Project them now
    # so saving once cannot change the identical snapshot's chronology or images.
    awards += [{'badge': row['badge'], 'tier': row['tier'], 'lead_id': None,
                'at': snapshot['generated_at'], 'reason': 'Weekly analytics criteria met.'}
               for row in snapshot.get('badges', []) if row.get('new') and
               (row['badge'], row['tier']) not in retained]
    return badge_ledger.voyage(awards, dict(snapshot, presentation={'voyage': base}))


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


def review_coverage_gaps(result, include_available=False):
    gaps = []
    for key in ('speed_10min', 'proposal_on_time'):
        if include_available or result['kpis'][key].get('unknown_n', 0):
            gaps.append({'source': 'frozen posting age' if key == 'speed_10min' else 'call end time', 'blocks': [key], 'how_to_supply': 'Supply the verified posting time and application time.' if key == 'speed_10min' else 'Paste the call end timestamp or complete call duration.'})
    for thread in result['conversation_review']['threads']:
        if include_available or not thread['read']:
            gaps.append({'source': 'messages or review:' + thread['lead_id'], 'blocks': ['conversation_review'], 'how_to_supply': 'Read the complete Upwork thread and record its three quoted content checks.'})
    return gaps


def finish_views(result, jobs, history, today, now=None):
    result['accountability'] = accountability_fields(result, jobs, history)
    application_streak = result['accountability']['application_streak']
    result.update(streak_weeks=application_streak['current'], best_streak_weeks=application_streak['best'])
    stage_keys = {'applied': 'reply_rate', 'replied': 'reply_to_call', 'call': 'proposal_to_won', 'offer': 'offer_to_contract'}
    for row in result['forecast']['by_stage']:
        kpi = result['kpis'][stage_keys[row['stage']]]
        if kpi['baseline_phase'] or kpi['state'] in ('missing', 'undecided'):
            row.update(own_rate=None, expected=None)
    result['forecast']['next_30_days'] = rounded(sum(row['expected'] for row in result['forecast']['by_stage'])) if all(row['expected'] is not None for row in result['forecast']['by_stage']) else None
    result['todos'] = lead_todos(jobs, today, result['goals_next'])
    result['call_to_won'] = call_to_won(jobs, today)
    result['conversation_review'] = conversation_reviews(jobs, today)
    result['coverage']['missing'].extend(review_coverage_gaps(result))
    result['funnel_score'] = funnel_score(result, history)
    result['rank_progress'] = rank_fields(result, history)
    result['rank'] = result['rank_progress']['rank']
    result['community_card'] = community_card(jobs, today, result['kpis'], result['goals_review'], result['week'], result['streak_weeks'], now)
    result['community_card']['working_days'] = {key: result['accountability']['working_days'][key] for key in ('k', 'n')}
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
    # Chronology precedes tier: a later Bronze award can follow an earlier Gold.
    awards = {(row['badge'], row['tier']): timestamp(row.get('at')) for row in badge_ledger.read_ledger()}
    award_time = run_timestamp(today, now)
    result['community_card']['new_badge'] = max(new, key=lambda row: (awards.get((row['badge'], row['tier'])) or award_time,
        row['earned_week'], TIERS.index(row['tier']), row['badge']), default=None)
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in coverage_sources(result['coverage'])):
        for row in result.get('daily_applications', []): row['count'] = None
    result['presentation'] = presentation_fields(result)
    result['presentation']['accountability'] = copy.deepcopy(result['accountability'])
    result['community_card']['funnel_score'] = copy.deepcopy(result['funnel_score'])
    result.setdefault('insights', {})['job_fit'] = job_fit_fields(jobs, today)
    result['insights']['general'] = insight_fields(jobs, today)
    result['segments'] = copy.deepcopy(result['insights']['general']['segments'])
    result['presentation']['scorecard'] = scorecard_fields(result, jobs, history, today)
    result['presentation']['money_chart'] = money_chart(result, history)
    result['presentation']['voyage'] = voyage_fields(result, history)
    result['presentation']['voyage'].update(rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
    card = result['community_card']
    earned = sorted((row for row in result['badges'] if row.get('earned_week') == result['week']),
                    key=lambda row: (-TIERS.index(row['tier']), row['badge']))
    card['earned_badges'] = copy.deepcopy(earned[:3])
    card['more_badges'] = max(0, len(earned) - 3)
    card.update(rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
    reaching = []
    for station in result['presentation']['voyage'].get('stations', []):
        match = re.fullmatch(r'(\d+) of (\d+) weeks', station.get('progress_to_next') or '')
        if match and station.get('next_tier'):
            weeks = max(0, int(match[2]) - int(match[1]))
            reaching.append((weeks, station['badge'], {'name': station['badge'], 'tier': station['next_tier'], 'weeks_remaining': weeks}))
        elif station.get('locked'):
            reaching.append((1, station['badge'], {'name': station['badge'], 'tier': 'Bronze', 'weeks_remaining': 1}))
    card['next_badge'] = min(reaching, default=(None, None, None))[2]
    result['presentation']['funnel'] = funnel_fields(result, jobs)
    result['stage_context'] = proposal_context(jobs, today)
    result['presentation']['funnel']['outbound'][0]['view_context'] = result['stage_context']['applied_to_viewed']
    result['daily_voyage'] = daily_voyage(jobs, today)
    if any(row['source'] == 'upwork' and row['state'] == 'missing' for row in coverage_sources(result['coverage'])):
        result['daily_voyage'].update(applications=None, remaining=None, complete=None, state='unknown')
    result['quests'] = quest_progress(result, jobs, today)
    result['call_cards'] = call_cards(result, jobs)
    result['conversations'] = conversations_fields(result, jobs)
    result['presentation']['progress_strip'] = dict(progress_strip(result), rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
    result['presentation'].update(rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
    result['presentation']['goal_cards'] = goal_cards(result)
    result['report_facts'] = report_source_facts(result, jobs, today)
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
        if not isinstance(review, dict) or not review.get('reviewable') or not inside(reviewed_call_at(job), span(today, 28)) or _RECONSTRUCTING.get(): continue
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
        require(isinstance(goal, dict) and keys <= set(goal) <= keys | {'goal_library_id', 'goal_id'}, 'Each goal needs stage, kpi, change, start, primary, cue, action, fallback and review_on; goal_library_id and goal_id are optional for private goals.')
        require('goal_id' not in goal or isinstance(goal['goal_id'], str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', goal['goal_id'])), 'Goal ID must be a nonempty stable identifier.')
        require('goal_library_id' not in goal or goal['goal_library_id'] in PUBLIC_GOAL_LIBRARY and PUBLIC_GOAL_LIBRARY[goal['goal_library_id']][0] == goal.get('kpi'), 'Goal library ID must belong to its KPI.')
        require(goal['kpi'] in LABELS and goal['stage'] == LABELS[goal['kpi']] and all(isinstance(goal[name], str) and goal[name].strip() for name in ('stage', 'change', 'cue', 'action', 'fallback')), 'Goals need a known KPI and nonempty commitments.')
        start, review_on = dt.date.fromisoformat(goal['start']), dt.date.fromisoformat(goal['review_on'])
        require(review_on >= start and isinstance(goal['primary'], bool), 'Goals need ordered start/review dates and boolean primary.')
    require(len({goal['stage'].strip().casefold() for goal in goals}) == len(goals) and len({goal['kpi'] for goal in goals}) == len(goals), 'Two goals cannot share one stage or KPI.')
    require(len({goal_id(goal, value['week']) for goal in goals}) == len(goals), 'Goal IDs must be distinct.')
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
    for goal in value['goals']: goal['goal_id'] = goal_id(goal, value['week'])
    atomic_lines('goals.jsonl', rows + [value])
    return value


def rubric_coverage(rubric, today, name):
    require(isinstance(rubric, list), 'Rubric must be a list of lead judgments.')
    if name in ('conversation', 'proposal'):
        seen, rows = set(), []
        for item in rubric:
            allowed = {'lead_id', 'reviewable', 'read', 'last_writer', 'points', 'fix', 'example', 'next_message', 'free_read', 'scope', 'price', 'decision_date'} | pipeline.REVIEW_METADATA
            require(isinstance(item, dict) and {'lead_id', 'reviewable', 'points'} <= set(item) <= allowed and isinstance(item['reviewable'], bool), 'Review needs lead_id, reviewable and recorded points.')
            require(item['lead_id'] not in seen, 'Review each lead once.')
            seen.add(item['lead_id']); pipeline.validate_review_metadata(item)
            for field, limit in (('free_read', 150), ('next_message', 100)):
                if field in item: short_text(item[field], limit, field, optional=True)
            points = item['points']
            points = [dict(point, point=key) for key, point in points.items()] if isinstance(points, dict) else points
            require(isinstance(points, list), 'Review points need a list or named conversation points.')
            require(item['reviewable'] or not points, 'An unreviewable source has no point judgments.')
            text = read_source(pipeline.jobs_dir() / str(item['lead_id']) / ('thread.json' if name == 'conversation' else 'proposal.md')) or ''
            if name == 'conversation':
                try:
                    thread = json.loads(text); rooms = list((thread.get('rooms') or {}).values()) or [thread]
                    complete = bool(rooms) and all(room.get('messages_complete') is True for room in rooms)
                    text = '\n'.join(turn.get('text', '') for room in rooms for turn in room.get('messages', []) if turn.get('from') in ('me', 'client'))
                except (ValueError, TypeError): complete = False; text = ''
                require(not item['reviewable'] or complete and {point.get('point') for point in points} == set(CONVERSATION_POINTS), 'Reviewed chats require complete messages and all three content points.')
            require(not item['reviewable'] or bool(text.strip()) and bool(points), 'Reviewed proposals require the sent source and recorded criteria.')
            identities = set()
            for point in points:
                require(isinstance(point, dict) and {'point', 'state'} <= set(point) <= ({'point', 'state', 'quote', 'reason', 'label'} | pipeline.REVIEW_METADATA), 'Unknown review point fields.')
                require(isinstance(point['point'], (str, int)) and not isinstance(point['point'], bool) and point['point'] not in identities, 'Review each point once.')
                identities.add(point['point']); pipeline.validate_review_metadata(point)
                require(point['state'] in ('met', 'partly', 'missing', 'not needed', 'not_needed'), 'Unknown review point state.')
                if name == 'proposal': require(isinstance(point.get('label'), str) and point['label'].strip(), 'Proposal points require the original review labels.')
                if point['state'] in ('not needed', 'not_needed'): require(isinstance(point.get('reason'), str) and point['reason'].strip(), 'Not needed requires a reason.')
                if point.get('quote'): require(isinstance(point['quote'], str) and point['quote'] in text, 'Review quotes must occur in the saved source.')
            rows.append(dict(item, points=points))
        stage = 'chats' if name == 'conversation' else 'proposals'
        return conversation_criteria({stage: rows})[stage]['points']
    seen = set()
    jobs_by_id = {str(job['id']): job for job in pipeline.load()} if name == 'application' else {}
    uma_counts = {}
    counts = {point: {'point': point, 'met': 0, 'partly': 0, 'missing': 0, 'not_needed': 0, 'n': 0} for point in range(1, 10 if name == 'call' else 8)}
    for item in rubric:
        allowed = {'lead_id', 'reviewable', 'points', 'moments', 'fix', 'example', 'next_step', 'next_message', 'free_read'} | pipeline.REVIEW_METADATA | ({'agreed_step'} if name == 'call' else set())
        require(isinstance(item, dict) and {'lead_id', 'reviewable', 'points'} <= set(item) and set(item) <= allowed, 'Call rubric needs lead_id, reviewable and points.')
        require(item['lead_id'] not in seen and isinstance(item['reviewable'], bool), 'Call rubric needs unique leads and boolean reviewable.')
        seen.add(item['lead_id'])
        pipeline.validate_review_metadata(item)
        for field, limit in (('next_message', 100), ('free_read', 180 if name == 'call' else 150)):
            if field in item: short_text(item[field], limit, field, optional=True)
        path = pipeline.jobs_dir() / str(item['lead_id']) / ('call.md' if name == 'call' else 'application.sent.md')
        text = path.read_text(encoding='utf-8') if path.is_file() else ''
        utterances = '\n'.join(match[2] for match in re.finditer(r'^([^:\n]+):\s*(.+)$', text, re.M) if match[1].strip().lower() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language'))
        speakers = {match[1].strip() for match in re.finditer(r'^([^:\n]+):\s*\S', text, re.M) if match[1].strip().lower() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language')}
        if name == 'call':
            if item.get('reviewable') and item.get('free_read') is not None:
                require(len(item['free_read'].split()) >= 120, 'Call free read needs 120 to 180 words.')
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
            require({'point', 'state'} <= set(row) and set(row) <= ({'point', 'state', 'quote', 'reason', 'label'} | pipeline.REVIEW_METADATA) and row['state'] in ('met', 'partly', 'missing', 'not needed', 'not_needed'), 'Review points need point and state with optional source quote and reason.')
            pipeline.validate_review_metadata(row)
            if row['state'] in ('not needed', 'not_needed'):
                require(isinstance(row.get('reason'), str) and row['reason'].strip(), 'Every not needed call point needs a reason.')
            if row.get('quote'):
                source = utterances if name == 'call' else text + '\n' + (read_source(path.parent / 'loom.md') or read_source(path.parent / 'loom-transcript.txt') or '')
                require(isinstance(row['quote'], str) and row['quote'] in source, 'Review quote must occur in local source evidence.')
            target = (uma_counts if uma else counts)[row['point']]
            target[row['state'].replace(' ', '_')] += 1
            target['n'] += row['state'] not in ('not needed', 'not_needed')
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


PUBLIC_QUESTION_TEMPLATES = {
    'reply_rate-1': ('reply_rate', 'What made the jobs that replied different from the rest?'),
    'reply_rate-2': ('reply_rate', 'Which proof helped clients reply?'),
    'reply_to_call-1': ('reply_to_call', 'What helped turn replies into useful calls?'),
    'reply_to_call-2': ('reply_to_call', 'Which question helped you agree a call?'),
    'booked_to_held-1': ('booked_to_held', 'What helped clients attend the meeting?'),
    'booked_to_held-2': ('booked_to_held', 'How did you confirm the meeting beforehand?'),
    'proposal_to_won-1': ('proposal_to_won', 'What helped clients decide on the proposal?'),
    'proposal_to_won-2': ('proposal_to_won', 'Which scope made the decision easier?'),
    'held_to_proposal-1': ('held_to_proposal', 'What helped you prepare the proposal after the call?'),
    'held_to_proposal-2': ('held_to_proposal', 'How did you confirm the scope together?'),
    'proposal_on_time-1': ('proposal_on_time', 'What helped you send the proposal promptly?'),
    'proposal_on_time-2': ('proposal_on_time', 'Which preparation saved time after the call?'),
    'invite_to_call-1': ('invite_to_call', 'What helped you respond to useful invitations?'),
    'invite_to_call-2': ('invite_to_call', 'Which proof helped you agree a call?'),
    'offer_to_contract-1': ('offer_to_contract', 'What helped you confirm the offer terms?'),
    'offer_to_contract-2': ('offer_to_contract', 'Which check helped you reach an agreement?'),
    'weekly_volume-1': ('weekly_volume', 'What helped you keep your application sessions?'),
    'weekly_volume-2': ('weekly_volume', 'Which routine helped you find fitting jobs?'),
    'job_fit-1': ('job_fit', 'What helped you recognise fitting jobs?'),
    'job_fit-2': ('job_fit', 'Which requirement helped you decide where to apply?'),
    'speed_10min-1': ('speed_10min', 'What helped you check fit and apply promptly?'),
    'speed_10min-2': ('speed_10min', 'Which preparation made applying easier?'),
    'first_reply-1': ('first_reply', 'What helped you answer client messages promptly?'),
    'first_reply-2': ('first_reply', 'Which routine helped you keep conversations moving?'),
    'follow_ups_on_time-1': ('follow_ups_on_time', 'What helped you follow up as planned?'),
    'follow_ups_on_time-2': ('follow_ups_on_time', 'Which follow up helped restart a conversation?'),
    'call_review-1': ('call_review', 'Which question helped you understand the client?'),
    'call_review-2': ('call_review', 'What helped you agree the next step?'),
}
PUBLIC_QUESTIONS = tuple(PUBLIC_QUESTION_TEMPLATES)

def public_question_id(value):
    return value if isinstance(value, str) and value in PUBLIC_QUESTION_TEMPLATES else None

def public_question_text(card):
    entry = PUBLIC_QUESTION_TEMPLATES.get(card.get("question_id"))
    return entry[1] if entry and LABELS.get(entry[0]) == card.get("next_focus") else None


# Stable goal-library IDs select fixed public words, never the agreed private prose.
PUBLIC_GOAL_LIBRARY = {
    'reply-opener': ('reply_rate', 'Name the posted problem'),
    'reply-proof': ('reply_rate', 'Use one relevant proof'),
    'reply-observation': ('reply_rate', 'Add one useful job observation'),
    'reply-close': ('reply_rate', 'Ask one useful closing question'),
    'reply-video': ('reply_rate', 'Show one relevant point'),
    'speed-qualified': ('speed_10min', 'Apply promptly after checking fit'),
    'fit-check': ('job_fit', 'Check fit before applying'),
    'volume-sessions': ('weekly_volume', 'Keep agreed application sessions'),
    'volume-share': ('weekly_volume', 'Submit the agreed qualified share'),
    'volume-replan': ('weekly_volume', 'Replan missed application sessions'),
    'call-times': ('reply_to_call', 'Offer two useful call times'),
    'first-answer': ('first_reply', 'Answer within agreed working hours'),
    'call-question': ('reply_to_call', 'Resolve the blocking question'),
    'call-free-offer': ('reply_to_call', 'Confirm terms before the offer'),
    'followup-first': ('follow_ups_on_time', 'Follow up on the agreed day'),
    'followup-last': ('follow_ups_on_time', 'Send one final useful question'),
    'meeting-confirm': ('booked_to_held', 'Confirm the meeting and agenda'),
    'meeting-remind': ('booked_to_held', 'Confirm the meeting before it starts'),
    'meeting-reschedule': ('booked_to_held', 'Offer replacement times after absence'),
    'call-opening': ('call_review', 'Confirm the goal and agenda'),
    'call-impact': ('call_review', 'Ask about the problem impact'),
    'call-budget': ('call_review', 'Confirm budget before naming price'),
    'call-step': ('call_review', 'Agree the next step and owner'),
    'proposal-prompt': ('proposal_on_time', 'Send the complete proposal promptly'),
    'proposal-fit': ('held_to_proposal', 'Record the evidenced fit decision'),
    'proposal-scope': ('proposal_to_won', 'Offer one complete fitting scope'),
    'proposal-value': ('proposal_to_won', 'Explain price with the agreed scope'),
    'proposal-decision': ('proposal_to_won', 'Confirm the next decision step'),
    'proposal-objection': ('proposal_to_won', 'Clarify the price concern'),
    'invite-answer': ('first_reply', 'Answer the immediate invite request'),
    'invite-proof': ('invite_to_call', 'Share proof before booking'),
    'offer-check': ('offer_to_contract', 'Check the offer against the agreement'),
}


def public_agreed_goals(week):
    """Only an explicit agreement in the goals ledger authorizes a public goal."""
    approved = {}
    for row in read_lines('goals.jsonl'):
        if row.get('week', '') > week: continue
        for goal in row.get('goals', []):
            library_id = goal.get('goal_library_id')
            if library_id in PUBLIC_GOAL_LIBRARY and PUBLIC_GOAL_LIBRARY[library_id][0] == goal.get('kpi'):
                approved[goal_id(goal, row['week'])] = library_id
    return approved


def public_normalized(text):
    return ' '.join(re.findall(r"[^\W_]+", text.casefold(), re.UNICODE))


def public_source_fragments(jobs):
    """Normalized known identities, title words and short source excerpts; never exported."""
    forbidden = set()
    identity_keys = {'name', 'client', 'client_name', 'contract_client', 'company', 'company_name',
                     'business_name', 'organization', 'organisation', 'alias', 'aliases', 'title', 'job_title'}
    source_keys = {'description', 'text', 'content', 'message', 'quote'}
    def collect(item, key=''):
        if isinstance(item, dict):
            for field, value in item.items(): collect(value, field.casefold())
        elif isinstance(item, list):
            for value in item: collect(value, key)
        elif isinstance(item, str) and key in identity_keys | source_keys and item.strip():
            normalized = public_normalized(item)
            if not normalized: return
            forbidden.add(normalized)
            words = normalized.split()
            if key in identity_keys:
                # A single identifying title/name word is still an identifying excerpt.
                forbidden.update(word for word in words)
            else:
                forbidden.update(words)
                forbidden.update(' '.join(words[index:index + 2]) for index in range(len(words) - 1))
    for job in jobs: collect(job)
    for path in pipeline.jobs_dir().glob('*/thread.json'):
        try: thread = json.loads(read_source(path) or '{}')
        except ValueError: thread = {}
        collect(thread)
    for path in pipeline.jobs_dir().glob('*/call*.md'):
        text = read_source(path) or ''
        own = re.search(r'^Member:\s*(.+)$', text, re.M | re.I)
        own = own[1].strip().casefold() if own else None
        for match in re.finditer(r'^(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)?([^:\n]{1,80}):\s*(.+)$', text, re.M):
            speaker, turn = match[1].strip(), match[2].strip()
            if speaker.casefold() in ('duration', 'member', 'call at', 'date', 'recorder', 'speakers', 'complete', 'language'): continue
            collect(turn, 'quote')
            if speaker.casefold() != own and speaker.casefold() not in ('client', 'them', 'speaker 1', 'speaker 2'): collect(speaker, 'name')
    return forbidden


PUBLIC_CURRENCY_CODES = frozenset("AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD XDR XOF XPD XPF XPT XSU XUA XXX YER ZAR ZMW ZWL".casefold().split())

def safe_public_text(text, jobs, maximum=14):
    """Question policy fails closed; unsafe optional questions are omitted."""
    if not isinstance(text, str) or not text.strip() or len(text.split()) > maximum:
        return False
    if any(char.isdigit() or char.isnumeric() for char in text): return False
    if any(unicodedata.category(char) == 'Sc' for char in text): return False
    if any(word in PUBLIC_CURRENCY_CODES for word in public_normalized(text).split()): return False
    if re.search(r'\d|[$€£¥₹₽₩¢]|(?:[a-z][a-z0-9+.-]*:)|www\.|[\w.+-]+@[\w.-]+|\b[\w-]+(?:\.[\w-]+)+\b', text, re.I):
        return False
    if re.search(r'\b(?:usd|eur|gbp|dollars?|euros?|pounds?|yen|cents?|currency|francs?|rupees?|dinars?|dirhams?|pesos?|rands?|won|rials?|riyals?|rubles?|roubles?|liras?|zloty|kroner|krona|baht|ringgit|taka|shekels?|dong|manat|leu|lev|kuna|kwacha|shillings?|pula|forint|bitcoin|btc|ether|eth|satoshis?|hours?|hourly|hrs?|minutes?|mins?|seconds?|secs?|days?|daily|weeks?|weekly|months?|monthly|years?|annual|yearly|percent|percentage|rates?|kilograms?|kg|g|mg|lb|lbs|oz|km|cm|mm|metres?|meters?|miles?|feet|inches?|litres?|liters?|ml|gallons?|watts?|kilowatts?|kwh|hz|celsius|fahrenheit|degrees?|mb|gb|tb|bytes?|bits?|pixels?|px)\b|[%/]', text, re.I):
        return False
    words = re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text, re.UNICODE)
    if any(any(char.isupper() for char in word) and index != 0 and word not in ('I', 'Upwork') for index, word in enumerate(words)):
        return False
    normalized = ' ' + public_normalized(text) + ' '
    return not any(' ' + source + ' ' in normalized for source in public_source_fragments(jobs))


def validate_community_card(card, jobs=None):
    jobs = pipeline.load() if jobs is None else jobs
    require(isinstance(card, dict), 'Public card needs an object.')
    card.pop('question', None)  # Legacy prose is never a public input.
    card.setdefault('question_id', None)
    keys = {'member_name', 'week', 'applications', 'streak_weeks', 'goals_done', 'goals', 'next_focus', 'question_id',
            'new_badge', 'top_badges', 'reply_rate', 'reply_to_call', 'call_to_won',
            'first_reply_median_min', 'first_reply_target_min', 'biggest_improvement', 'won_value', 'booked_to_held', 'proposal_to_won', 'funnel_score', 'activity_period', 'rank', 'rank_progress', 'earned_badges', 'more_badges', 'next_badge', 'stage_counts', 'working_days'}
    require(isinstance(card, dict) and keys - {'member_name', 'activity_period', 'rank', 'rank_progress', 'earned_badges', 'more_badges', 'next_badge', 'stage_counts', 'working_days'} <= set(card) <= keys, 'Public card has unknown or missing fields.')
    if 'working_days' in card:
        working = card['working_days']
        require(isinstance(working, dict) and set(working) == {'k', 'n'} and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in working.values()) and 0 <= working['k'] <= working['n'] <= 7, 'Public working_days needs numeric k/n only.')
    require(isinstance(card.get('streak_weeks'), int) and not isinstance(card['streak_weeks'], bool) and card['streak_weeks'] >= 0, 'Public streak_weeks needs a nonnegative whole number.')
    require(card.get('member_name') is None or card['member_name'] == public_member_name(), 'Public member identity must derive from me.md.')
    if 'activity_period' in card:
        activity = card['activity_period']
        require(isinstance(activity, dict) and set(activity) == {'start', 'end'} and all(day(value) for value in activity.values()) and
                (day(activity['end']) - day(activity['start'])).days == 6, 'Public activity needs a seven-day date range.')
    def numeric(value): return value is None or number(value)
    if 'stage_counts' in card:
        volumes = card['stage_counts']
        require(isinstance(volumes, dict) and set(volumes) == {'applications', 'replies', 'calls_booked', 'calls_held', 'proposals', 'won', 'pending_proposals'} and
                all(value is None or number(value) and value >= 0 and int(value) == value for value in volumes.values()), 'Public stage counts need fixed nonnegative whole counts or unknown.')
    require(re.fullmatch(r'\d{4}-W\d{2}', str(card['week'])), 'Invalid public week.')
    for key in ('applications', 'streak_weeks', 'first_reply_median_min', 'first_reply_target_min', 'won_value'):
        require(numeric(card[key]), 'Public numeric field must be a finite number or null.')
    require(re.fullmatch(r'\d+/\d+', str(card['goals_done'])), 'Invalid goal aggregate.')
    require(card['next_focus'] is None or card['next_focus'] in LABELS.values(), 'Public focus must be a fixed stage label.')
    approved = public_agreed_goals(card['week'])
    require(isinstance(card['goals'], list) and len(card['goals']) <= 3, 'Public goals must be the latest agreed set of at most three commitments.')
    require(len({str(goal.get('goal_id', '')) for goal in card['goals'] if isinstance(goal, dict)}) == len(card['goals']), 'Public goals must be distinct.')
    for goal in card['goals']:
        require(isinstance(goal, dict) and set(goal) == {'goal_id', 'goal_library_id', 'text', 'done', 'k', 'n', 'state'} and
                approved.get(goal['goal_id']) == goal['goal_library_id'] and goal['goal_library_id'] in PUBLIC_GOAL_LIBRARY and
                goal['text'] == PUBLIC_GOAL_LIBRARY[goal['goal_library_id']][1] and
                isinstance(goal['done'], bool) and numeric(goal['k']) and numeric(goal['n']) and
                goal['state'] in ('unverified', 'no opportunity', 'complete', 'partial', 'undone'), 'Public goals require an agreed goal ID and its fixed library label.')
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
    entry_periods = [card[key]['entry_period'] for key in ('reply_rate', 'reply_to_call', 'call_to_won', 'booked_to_held', 'proposal_to_won')]
    require(all(value == entry_periods[0] for value in entry_periods) and
            (dt.date.fromisoformat(entry_periods[0]['end']) - dt.date.fromisoformat(entry_periods[0]['start'])).days == 27,
            'Public conversion entries must share one complete 28-day window.')
    improvement = card['biggest_improvement']
    require(improvement is None or (isinstance(improvement, dict) and set(improvement) == {'kpi', 'from', 'to'} and
            improvement['kpi'] in ('reply_rate', 'reply_to_call', 'call_to_won', 'booked_to_held', 'proposal_to_won') and numeric(improvement['from']) and numeric(improvement['to'])), 'Invalid public improvement.')
    require(isinstance(card['top_badges'], list), 'Public badges need a list.')
    earned = card.get('earned_badges', [])
    require(isinstance(earned, list) and len(earned) <= 3, 'Public weekly badges show at most three.')
    require(all(badge.get('earned_week') == card['week'] for badge in earned), 'Public weekly badges must belong to this week.')
    require(isinstance(card.get('more_badges', 0), int) and not isinstance(card.get('more_badges', 0), bool) and card.get('more_badges', 0) >= 0, 'Public extra badge count must be nonnegative.')
    for badge in card['top_badges'] + earned + ([card['new_badge']] if card['new_badge'] else []):
        require(isinstance(badge, dict) and {'badge', 'tier', 'earned_week', 'new', 'progress_to_next'} <= set(badge) <= {'badge', 'tier', 'earned_week', 'new', 'progress_to_next', 'progress'} and
                badge['badge'] in BADGE_NAMES and badge['tier'] in TIERS and re.fullmatch(r'\d{4}-W\d{2}', str(badge['earned_week'])) and
                isinstance(badge['new'], bool) and (badge['progress_to_next'] in ('All tiers earned', 'One standout moment', 'One qualifying week', 'One call with 9 of 9 points') or
                re.fullmatch(r'Lower bound at least \d+ %|\d+ of \d+ (weeks|proposals|invites|calls|wins|returns)', badge['progress_to_next'])), 'Unknown public badge content.')
        if 'progress' in badge:
            progress = badge['progress']
            require(isinstance(progress, dict) and set(progress) == {'current', 'target', 'remaining', 'unit'} and progress['unit'] == ('returns' if badge['badge'] == 'Back on Course' else 'weeks') and all(isinstance(progress[key], int) and not isinstance(progress[key], bool) and progress[key] >= 0 for key in ('current', 'target', 'remaining')), 'Badge progress needs numeric current, target, remaining and the badge-specific unit.')
    if 'rank' in card or 'rank_progress' in card:
        rank = card.get('rank_progress')
        require(isinstance(rank, dict) and set(rank) == {'rank', 'score', 'next_rank', 'next_threshold', 'held_weeks', 'required_weeks', 'progress'}, 'Public rank needs fixed computed progress fields.')
        names = [name for name, _ in RANK_LEVELS]
        require(card.get('rank') in names and rank['rank'] == card['rank'], 'Public rank must use the computed level.')
        index = names.index(rank['rank'])
        next_level = RANK_LEVELS[index + 1] if index + 1 < len(RANK_LEVELS) else (None, None)
        require((rank['next_rank'], rank['next_threshold']) == next_level and rank['required_weeks'] == 4 and isinstance(rank['held_weeks'], int) and 0 <= rank['held_weeks'] <= 4, 'Public rank progression has fixed thresholds and a four-week hold.')
        require((rank['score'] is None or number(rank['score']) and 0 <= rank['score'] <= 100) and number(rank['progress']) and 0 <= rank['progress'] <= 100, 'Public rank scores must be bounded.')
    reach = card.get('next_badge')
    require(reach is None or isinstance(reach, dict) and {'name', 'tier', 'weeks_remaining'} <= set(reach) <= {'name', 'tier', 'weeks_remaining', 'progress'} and reach['name'] in BADGE_NAMES and reach['tier'] in TIERS and isinstance(reach['weeks_remaining'], int) and not isinstance(reach['weeks_remaining'], bool) and reach['weeks_remaining'] >= 0, 'Public next badge must use a known name, tier and qualifying-week count.')
    if reach is not None and 'progress' in reach:
        progress = reach['progress']
        require(isinstance(progress, dict) and set(progress) == {'current', 'target', 'remaining', 'unit'} and progress['unit'] == ('returns' if reach['name'] == 'Back on Course' else 'weeks') and all(isinstance(progress[key], int) and not isinstance(progress[key], bool) and progress[key] >= 0 for key in ('current', 'target', 'remaining')), 'Next badge progress needs numeric current, target, remaining and the badge-specific unit.')
    score = card['funnel_score']
    require(isinstance(score, dict) and set(score) == {'score', 'previous', 'parts', 'dropped', 'baseline_only'} and
            all(score[field] is None or number(score[field]) and 0 <= score[field] <= 100 for field in ('score', 'previous')) and
            isinstance(score['baseline_only'], bool) and isinstance(score['parts'], dict) and set(score['parts']) == {'habits', 'results'} and
            all(value is None or number(value) and 0 <= value <= 100 for value in score['parts'].values()) and
            isinstance(score['dropped'], list) and all(isinstance(row, dict) and set(row) == {'part', 'reason'} and row['part'] in LEVERS + ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won') and row['reason'] in ('unknown source', 'No eligible cases yet', 'Baseline not set') for row in score['dropped']), 'Public Funnel Score must contain bounded computed parts only.')
    # Fixed goal labels and computed improvement fields have no prose input.
    card['question_id'] = public_question_id(card.get('question_id'))

    return card


def validated_community(value, jobs):
    """Only a finite template ID survives; legacy free text is dropped on read."""
    require(isinstance(value, dict) and set(value) <= {'question_id', 'question'}, 'Community writer accepts only question_id.')
    return {'question_id': public_question_id(value.get('question_id'))}


def snapshot_public_card(snapshot, jobs=None):
    """Project canonical template IDs; drop legacy free-text questions."""
    jobs = pipeline.load() if jobs is None else jobs
    card = canonical_badge_view(copy.deepcopy(snapshot['community_card']))
    if 'community' in snapshot:
        card['question_id'] = validated_community(snapshot['community'], jobs)['question_id']
    return validate_community_card(card, jobs)


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
    card = copy.deepcopy(value.get('community_card', {}))
    require(isinstance(card, dict), 'Community card needs an object.')
    card.pop('question', None)
    require(isinstance(card, dict) and set(card) <= set(result['community_card']), 'Community card has unknown fields.')
    if set(result['community_card']) - {'activity_period'} <= set(card): validate_community_card(card)
    else: require(set(card) <= {'next_focus', 'question_id', 'biggest_improvement'}, 'Partial public overlays may supply only focus/question and unchanged computed improvement.')
    if card.get('next_focus') is not None:
        require(card['next_focus'] in LABELS.values(), 'Community focus needs a known stage label.')
        result['community_card']['next_focus'] = card['next_focus']
    if 'question_id' in card:
        result['community_card']['question_id'] = public_question_id(card['question_id'])
    if 'community' in value:
        result['community'] = validated_community(value['community'], pipeline.load())
        result['community_card']['question_id'] = result['community']['question_id']
    if card.get('biggest_improvement') is not None:
        supplied = card['biggest_improvement']
        original = result['community_card']['biggest_improvement']
        require(isinstance(supplied, dict) and set(supplied) <= {'kpi', 'from', 'to'} and original is not None, 'Improvement needs a computed change.')
        require(all(supplied.get(key, original[key]) == original[key] for key in ('kpi', 'from', 'to')), 'Improvement numbers must come from compute.')
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
        if name in ('call', 'application', 'conversation', 'proposal'):
            judgments = review.get('rubric', [])
            supported = supported and bool(judgments) and {item.get('lead_id') for item in judgments if item.get('reviewable')} == set(review['evidence_lead_ids'])
        complete = complete and supported
        row.update(k=int(complete), n=1, value='one fix' if complete else None, state='pass' if complete else 'undecided', reason=None if complete else 'No evidenced weekly fix yet.', evidence=review['evidence_lead_ids'])
        row['history'][-1] = row['value']
        if name in ('call', 'application', 'conversation', 'proposal'):
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
    known_sources = {row['source'] for row in coverage_sources(result['coverage'])}
    supplied_coverage = value.get('coverage', [])
    require(isinstance(supplied_coverage, (dict, list)), 'Coverage needs a source list or an object with sources/missing lists.')
    judgments = coverage_sources(supplied_coverage)
    missing = supplied_coverage.get('missing', []) if isinstance(supplied_coverage, dict) else []
    require(isinstance(judgments, list) and isinstance(missing, list), 'Coverage sources and missing must be lists.')
    judgments = copy.deepcopy(judgments)
    computed_gaps = coverage_fields([], pipeline.load(), today, include_available=True)['missing'] + review_coverage_gaps(result, include_available=True)
    for gap in missing:
        # Regenerate exact built-in gaps, including those whose source was just supplied.
        if gap in result['coverage']['missing'] or gap in computed_gaps: continue
        require(isinstance(gap, dict) and set(gap) in ({'source', 'blocks', 'how_to_supply'},
                {'source', 'what', 'blocks', 'how_to_supply'}), 'Missing coverage needs source, what, blocks and how_to_supply.')
        judgments.append(gap)
    for given in judgments:
        require(isinstance(given, dict) and isinstance(given.get('source'), str), 'Source judgment needs a source name.')
        if 'blocks' in given or 'how_to_supply' in given:
            fields = {'source', 'blocks', 'how_to_supply'} | ({'what'} if given['source'] not in known_sources or 'what' in given else set())
            require(set(given) == fields, 'Custom missing coverage needs source, what, blocks and how_to_supply.')
            if 'what' in given:
                require(isinstance(given['what'], str) and given['what'].strip(), 'Missing coverage needs nonempty what.')
            given = dict(source=given['source'], state='missing', affects=given['blocks'], fix=given['how_to_supply'],
                         **({'what': given['what']} if given['source'] not in known_sources else {}))
        fields = {'source', 'state', 'fix'} | ({'what', 'affects'} if given['source'] not in known_sources else set())
        require(fields <= set(given) <= fields | {'affects'}, 'Custom source needs explicit what, affected checks and an exact supply step.')
        require(given['state'] in ('ok', 'missing', 'stale') and isinstance(given['fix'], str), 'Invalid coverage judgment.')
        if given['source'] not in known_sources:
            require(len(given['source']) <= 64 and re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', given['source']), 'Custom source needs a short snake_case name.')
            require(isinstance(given['what'], str) and given['what'].strip() and
                    given['state'] in ('missing', 'stale') and given['fix'].strip() and
                    isinstance(given.get('affects'), list) and given['affects'] and
                    all(isinstance(key, str) and key.strip() for key in given['affects']),
                    'Custom source needs nonempty what, affected checks and an exact supply step; it cannot claim checked coverage.')
            source = next((row for row in coverage_sources(result['coverage']) if row == given), None)
            if source is None:
                source = copy.deepcopy(given)
                coverage_sources(result['coverage']).append(source)
        else:
            source = next(row for row in coverage_sources(result['coverage']) if row['source'] == given['source'])
        require('affects' not in given or given['affects'] == source['affects'], 'Source dependencies are computed.')
        require(source['state'] == given['state'] or given['state'] in ('missing', 'stale'), 'Live checks may degrade coverage; they cannot invent a missing saved source.')
        source.update(state=given['state'], fix=given['fix'])
        if source['state'] == 'missing':
            for key in source['affects']:
                if key not in result['kpis']: continue
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
    result['presentation']['progress_strip'] = dict(progress_strip(result), rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
    result['presentation'].update(rank=result['rank'], rank_progress=copy.deepcopy(result['rank_progress']))
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
    require(set(base) <= set(value) <= set(base) | {'community'}, 'Snapshot has missing or unknown top-level keys.')
    require(set(value['reviews']) == set(base['reviews']), 'Snapshot needs all four weekly reviews.')
    result = prepare_snapshot(value, today, now=generated)
    require(value['week'] == result['week'], 'Week does not match generated_at.')
    goals = [dict(goal, start=today.isoformat()) if 'start' not in goal else goal for goal in result['goals_next']]
    validate_goals({'week': result['week'], 'goals': goals})
    agreed = next((row['goals'] for row in reversed(read_lines('goals.jsonl')) if row.get('week') == result['week']), None)
    canonical = lambda items: [dict(goal, goal_id=goal_id(goal, result['week'])) for goal in items]
    require(agreed is not None and canonical(goals) == canonical(agreed), 'Snapshot needs the matching agreed goals saved for this ISO week.')
    focus = result['verdict']['kpi']
    require(focus is None or next(goal['kpi'] for goal in goals if goal['primary']) == focus, 'The focus KPI must be the primary goal.')
    require(isinstance(result['report'], str) and result['report'].strip(), 'Snapshot needs the chat report.')
    for review in result['reviews'].values():
        require(review['goal_ref'] is None or review['goal_ref'] in {goal['kpi'] for goal in goals}, 'Review goal_ref must refer to an agreed goal KPI.')
    require(result['community_card']['next_focus'] is not None, 'Claude must write the weekly community focus; unsafe questions are omitted under frozen §13.')
    for key in ('window', 'periods', 'pipeline', 'streak_weeks', 'verdict_history', 'cohorts', 'daily_applications', 'reply_time_hist', 'speed_curve', 'segments', 'forecast', 'call_rubric_weeks', 'badges', 'todos', 'call_to_won', 'presentation', 'daily_voyage', 'quests', 'call_cards', 'conversations', 'funnel_score', 'rank', 'rank_progress', 'report_facts', 'conversation_review', 'gap', 'badge_qualifying', 'insights'):
        require(value[key] == result[key], f'{key} must come unchanged from compute.')
    for key in ('accountability', 'best_streak_weeks', 'badge_progress'):
        if key in value: require(value[key] == result[key], f'{key} must come unchanged from compute.')
    require(value['coverage'] == result['coverage'], 'Coverage must come from reviewed compute.')
    require(value['north_star'] == result['north_star'], 'North star numbers must come from reviewed compute.')
    for key in set(result['verdict']) - {'sentence', 'next_action'}:
        require(value['verdict'].get(key) == result['verdict'][key], 'Verdict identity and state must come from compute.')
    require(set(value['kpis']) == set(result['kpis']), 'Snapshot needs all 24 KPI keys.')
    derived = {'application_review', 'conversation_review', 'call_review', 'proposal_review', 'goal_done'}
    for key, row in result['kpis'].items():
        supplied = copy.deepcopy(value['kpis'][key])
        require(supplied == row or (key in derived and supplied == base['kpis'][key]), f'{key} numbers must come from reviewed compute.')
    supplied_card = snapshot_public_card(value)
    supplied_card.setdefault('activity_period', result['community_card']['activity_period'])
    require(supplied_card == result['community_card'], 'Community numbers, badges and goal marks must come from reviewed compute.')
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
    """Render the validated public allowlist in the frozen compact community design."""
    card = validate_community_card(copy.deepcopy(card))
    esc = lambda text: html.escape(str(text), quote=True)
    fmt = lambda value, suffix='': 'unknown' if value is None else (f'{whole_percent(value):,}' if suffix == '%' else f'{display_number(value, 1):,.1f}'.rstrip('0').rstrip('.')) + suffix
    tokens = (ROOT / 'website/app/tokens.css').read_text(encoding='utf-8')
    labels = {'reply_rate': 'Reply rate', 'reply_to_call': 'Call rate', 'booked_to_held': 'Show-up rate',
              'proposal_to_won': 'Win rate', 'call_to_won': 'Call to won'}
    # Each stage counts entries in the same window, not one linked application journey.
    volumes = card.get('stage_counts') or {}
    stages = [('Applications', volumes.get('applications', card['reply_rate']['n']), 'reply_rate'),
              ('Replies', volumes.get('replies', card['reply_to_call']['n']), 'reply_to_call'),
              ('Calls booked', volumes.get('calls_booked', card['booked_to_held']['n']), 'booked_to_held'),
              ('Calls held', volumes.get('calls_held', card['booked_to_held']['k']), None),
              ('Proposals', volumes.get('proposals'), 'proposal_to_won'),
              ('Won', volumes.get('won', card['proposal_to_won']['k']), None)]
    maximum = max([count for _, count, _ in stages if number(count)] + [1])
    funnel = []; previous_width = 100
    for index, (label, count, key) in enumerate(stages):
        width = min(previous_width, max(12, 100 * math.sqrt(count / maximum))) if number(count) and count else 0
        previous_width = width if width else previous_width
        funnel.append(f'<div class="stage"><span>{label}</span><div class="bar-track"><i style="width:{width:.1f}%;opacity:{1-index*.12:.2f}"></i></div><b>{fmt(count)}</b></div>')
        if key:
            row = card[key]
            leak = card['next_focus'] == LABELS[key]
            trend = {'up': '↑ Improving', 'down': '↓ Declining', 'undecided': 'Not clear yet'}[row['trend']]
            outcomes = {'reply_rate': 'replied', 'reply_to_call': 'booked a call or received an offer',
                        'booked_to_held': 'attended', 'proposal_to_won': 'won'}
            count_text = 'unknown' if row['state'] == 'missing' else 'No opportunities' if not row['n'] else f"{fmt(row['k'])} of {fmt(row['n'])} {outcomes[key]}"
            value = 'No opportunities' if row['state'] != 'missing' and not row['n'] else fmt(row['value'], '%')
            if key == 'proposal_to_won':
                pending = volumes.get('pending_proposals')
                if number(pending) and pending: count_text += f" · {fmt(pending)} still open"
            funnel.append(f'<div class="rate{ " leak" if leak else ""}"><span>{labels[key]} <b>{value}</b>{" · leak" if leak else ""}</span><small>{count_text} · {trend}</small></div>')
    goals = []
    for goal in card['goals']:
        state = 'done' if goal['done'] else 'partly' if goal['state'] == 'partial' else 'not yet'
        mark = '✓' if goal['done'] else '◐' if state == 'partly' else '○'
        count = 'No opportunities' if not goal['n'] else f"{fmt(goal['k'])} of {fmt(goal['n'])}" if goal['k'] is not None else 'Not checked'
        goals.append(f'<li class="{state}"><i>{mark}</i><span>{esc(goal["text"])}</span><small>{state} · {count}</small></li>')
    goals_html = '<ul class="goals">'+''.join(goals)+'</ul>' if goals else '<p class="meta">No previous goals. Agree the first goals in /analytics.</p>'
    improvement = card['biggest_improvement']
    change = 'Not clear yet'
    if improvement:
        change = f'{labels[improvement["kpi"]]} {fmt(improvement["from"], "%")} → {fmt(improvement["to"], "%")}'
    weekly_badges = card.get('earned_badges', [])
    if not weekly_badges and card.get('new_badge') and card['new_badge']['earned_week'] == card['week']: weekly_badges = [card['new_badge']]
    badge_html = ''
    for badge in weekly_badges[:3]:
        slug = re.sub(r'[^a-z0-9]+', '-', badge['badge'].casefold().replace("'", '')).strip('-')
        asset = ROOT / 'website/public/badges' / f"{slug}-{badge['tier'].casefold()}.webp"
        if not asset.is_file():
            motifs = ('harbour', 'ship', 'treasure', 'hourglass', 'bell', 'spyglass', 'anchor', 'cannon', 'bottle', 'compass', 'wheel', 'lighthouse', 'doubloon', 'storm')
            asset = ROOT / 'website/public/badges' / f'badge-{motifs[BADGE_NAMES.index(badge["badge"])]}.webp'
        require(asset.is_file(), 'Displayed public badge needs its tier image or motif fallback.')
        picture = f'<img src="data:image/webp;base64,{base64.b64encode(asset.read_bytes()).decode()}" alt="" width="48" height="48">'
        badge_html += f'<div class="badge">{picture}<div><span class="eyebrow">New badge</span><b>{esc(badge["badge"])}</b><small>{esc(badge["tier"])}</small></div></div>'
    if card.get('more_badges', 0): badge_html += f'<small>+{card["more_badges"]} more</small>'
    if not weekly_badges and card.get('next_badge'):
        reach = card['next_badge']
        badge_html = f'<div class="badge"><small>{reach["weeks_remaining"]} weeks to {esc(reach["name"])} {esc(reach["tier"])}</small></div>'
    rank_html = f'<small>Rank: {esc(card["rank"])}</small>' if card.get('rank') else ''
    working = card.get('working_days')
    accountability_html = (f'<p class="meta">Working days {working["k"]} of {working["n"]} · Application streak {card["streak_weeks"]} weeks</p>' if working else f'<p class="meta">Application streak {card["streak_weeks"]} weeks</p>')
    score = card['funnel_score']
    score_text = 'Funnel Score ' + fmt(score['score']) + (', was ' + fmt(score['previous']) if score['previous'] is not None else '')
    baseline = '<small>Habits only until your baseline is set</small>' if score['baseline_only'] else ''
    week_date = dt.date.fromisocalendar(int(card['week'][:4]), int(card['week'][-2:]), 1)
    week_end = week_date + dt.timedelta(days=6)
    bounds = card['reply_rate']['entry_period']
    activity = card.get('activity_period')
    activity_label = f"7-day activity: {esc(activity['start'])} to {esc(activity['end'])}" if activity else '7-day activity; dates unknown'
    focus = esc(card['next_focus']) if card['next_focus'] else 'Choose the next focus in /analytics'
    question_text = public_question_text(card)
    question = f'<p class="question">{esc(question_text)}</p>' if question_text else ''
    money = f'<p class="meta">New contract value this week <b>{fmt(card["won_value"])}</b></p>' if card['won_value'] is not None and sections().get('Share money', '').strip().casefold() == 'yes' else ''
    footer = 'Upwork Blueprint · example' if os.environ.get('BLUEPRINT_EXAMPLE_DATA') == '1' else 'Upwork Blueprint'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weekly community card · {esc(card['week'])}</title>
<style>{tokens}
*{{box-sizing:border-box}}body{{margin:0;padding:32px 16px;background:var(--sand);color:var(--ink);font-family:var(--sans);font-variant-numeric:tabular-nums;display:flex;justify-content:center}}.card{{width:min(100%,600px);border-radius:24px;border-top:6px solid var(--terracotta);background:var(--ivory);padding:28px 38px 22px;box-shadow:0 8px 40px #14141312;overflow-wrap:anywhere}}.identity{{display:flex;justify-content:space-between;gap:16px;align-items:baseline}}h1{{font-family:var(--display);font-size:31px;font-weight:400;letter-spacing:-.5px;margin:0}}.week,.eyebrow,h2{{font-family:var(--mono);font-size:10px;color:var(--label);letter-spacing:.1em;text-transform:uppercase}}.week{{font-size:12px;white-space:nowrap}}.meta{{font-size:11px;line-height:1.45;color:var(--label);margin:5px 0}}.activity{{font-size:14px;color:var(--body);margin:5px 0}}.score{{font-size:16px;margin-top:10px}}.score small{{display:block;font-size:11px;color:var(--label)}}h2{{font-weight:400;margin:19px 0 8px}}.stage{{display:grid;grid-template-columns:94px minmax(0,1fr) 44px;gap:10px;align-items:center;min-height:27px}}.stage>span{{font-size:12px;color:var(--body)}}.stage>b{{font-family:var(--display);font-weight:400;font-size:21px}}.bar-track{{height:26px}}.bar-track i{{display:block;height:100%;background:var(--ink);border-radius:6px}}.rate{{border-left:2px solid var(--ring);margin:4px 0 7px 104px;padding-left:10px;font-size:11px;line-height:1.4;color:var(--body)}}.rate span{{display:block}}.rate small{{display:block;font-size:9px;color:var(--label)}}.rate.leak{{border-color:var(--terracotta)}}.rate.leak>span{{color:var(--terracotta-text)}}.goals{{list-style:none;margin:0;padding:0}}.goals li{{display:grid;grid-template-columns:20px minmax(0,1fr) auto;gap:8px;align-items:center;padding:5px 0;font-size:13px}}.goals i{{font-style:normal}}.goals small{{font-size:10px;color:var(--label)}}.highlight{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;background:var(--terracotta-soft);border-radius:14px;padding:12px 16px;margin-top:16px}}.highlight-copy>.eyebrow{{display:block}}.highlight-copy>b{{display:block;font-family:var(--display);font-weight:400;font-size:22px;margin-top:4px}}.highlight small{{display:block;font-family:var(--sans);font-size:11px;color:var(--body);margin-top:4px}}.focus{{margin-top:12px;padding-top:12px;border-top:1px solid var(--ring)}}.focus h2{{margin:0 0 5px}}.focus>b{{font-family:var(--display);font-weight:400;font-size:21px}}.question{{font-size:14px;line-height:1.4;margin:5px 0 0}}.badge{{display:flex;align-items:center;gap:10px}}.badge img{{object-fit:contain}}.badge b,.badge small{{display:block;font-size:13px}}.badge small{{font-size:11px;color:var(--label)}}footer{{display:flex;justify-content:space-between;gap:12px;border-top:1px solid var(--ring);margin-top:14px;padding-top:10px;font-family:var(--mono);font-size:10px;color:var(--label)}}@media(max-width:480px){{body{{padding:16px 12px}}.card{{padding:23px 20px 18px}}h1{{font-size:28px}}.stage{{grid-template-columns:78px minmax(0,1fr) 35px;gap:8px}}.stage>span{{font-size:11px}}.rate{{margin-left:86px}}.goals li{{grid-template-columns:18px minmax(0,1fr)}}.goals small{{grid-column:2}}.week{{font-size:10px}}}}
</style><main class="card"><header><div class="identity"><h1>{esc(card.get('member_name') or 'Weekly progress')}</h1><span class="week">{esc(card['week'])}</span></div>
<p class="activity">{fmt(card['applications'])} Applications this week</p><p class="meta">Week: {week_date.isoformat()} to {week_end.isoformat()} · {activity_label}</p><div class="score">{esc(score_text)}{baseline}{rank_html}</div></header>
<h2>Funnel · 28 days</h2><p class="meta">{esc(bounds['start'])} to {esc(bounds['end'])} · Same 28 days</p><div class="funnel">{''.join(funnel)}</div><p class="meta">Each row counts when that step started. Later results are counted for a fixed number of days.</p>
<h2>Last agreed goals</h2>{goals_html}<div class="highlight"><div class="highlight-copy"><span class="eyebrow">Biggest improvement</span><b>{change}</b></div>{badge_html}</div>{accountability_html}{money}
<div class="focus"><h2>Next focus</h2><b>{focus}</b>{question}</div><footer><span>{footer}</span></footer></main></html>'''


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
    card = snapshot_public_card(snapshot)
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
    facts = sub.add_parser('facts'); facts.add_argument('--today'); facts.add_argument('--file', '--snapshot', dest='snapshot')
    check = sub.add_parser('check-report'); check.add_argument('file'); check.add_argument('--snapshot'); check.add_argument('--today')
    card_parser = sub.add_parser('onepager'); card_parser.add_argument('--file', required=True); card_parser.add_argument('--week'); card_parser.add_argument('--output')
    due_parser = sub.add_parser('due'); due_parser.add_argument('--today')
    args = parser.parse_args(argv)
    try:
        if args.command == 'compute':
            overlay = json.load(sys.stdin) if args.file == '-' else json.loads(pathlib.Path(args.file).read_text(encoding='utf-8')) if args.file else None
            result = prepare_snapshot(overlay, args.today, args.now) if overlay is not None else compute_catchup(args.today, now=args.now) if args.catch_up else compute(args.today, now=args.now)
        elif args.command == 'onepager':
            result = onepager(args.file, args.week, args.output)
        elif args.command in ('facts', 'check-report'):
            snapshot = json.loads(pathlib.Path(args.snapshot).read_text(encoding='utf-8')) if args.snapshot else compute(args.today)
            result = facts_sheet(snapshot) if args.command == 'facts' else check_report(pathlib.Path(args.file).read_text(encoding='utf-8'), snapshot)
            if args.command == 'check-report' and result['status'] == 'FAIL':
                print(json.dumps(result, ensure_ascii=False, allow_nan=False)); return 1
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
