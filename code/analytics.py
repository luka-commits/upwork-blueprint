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

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULTS = {'won_value': None, 'value_per_100_connects': None, 'reply_rate': 20, 'reply_to_call': 50, 'booked_to_held': 90,
            'held_to_proposal': 90, 'proposal_to_won': 30, 'invite_to_call': 50,
            'offer_to_contract': 80, 'weekly_volume': 25, 'speed_10min': 80,
            'first_reply': 5, 'first_reply_p75': 15, 'follow_ups_on_time': 100,
            'proposal_on_time': 90, 'job_fit': 100}
LEGACY_BARS = {'Volume': 10, 'Profile': 100, 'Proposal': 10, 'Loom': 100, 'Speed': 2,
               'Messaging': 30, 'Sales call': 80, 'Call proposal': 90, 'Opened': 80}
FUNNEL = ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal',
          'proposal_to_won', 'invite_to_call', 'offer_to_contract')
LABELS = {'won_value': 'New contract value won this week', 'value_per_100_connects': 'Period contract value per 100 net Connects',
          'reply_rate': 'Applied → reply', 'reply_to_call': 'Reply → call',
          'booked_to_held': 'Booked → held', 'held_to_proposal': 'Held → proposal',
          'proposal_to_won': 'Proposal → won', 'invite_to_call': 'Invite → call',
          'offer_to_contract': 'Offer → contract', 'weekly_volume': 'Weekly applications',
          'speed_10min': 'Applied within 10 minutes', 'first_reply': 'Our first reply',
          'follow_ups_on_time': 'Follow-ups on their due day', 'proposal_on_time': 'Proposal within 30 minutes',
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
         'booked_to_held': (90,), 'held_to_proposal': (90,),
         'proposal_to_won': (20, 25, 30), 'invite_to_call': (50,),
         'offer_to_contract': (80,)}
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
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.is_file() else []


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
                valid = value.get('state') in ('pass', 'fail', 'unclear') if key == 'job_fit' else value.get('kind') in ('stated', 'observed', 'unknown')
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
    low, high = exact_bounds(k, n)
    return 'undecided' if not n else 'pass' if n >= 20 and low + 1e-9 >= target else 'fail' if high + 1e-9 < target else 'undecided'


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
    result['low'], result['high'] = map(rounded, exact_bounds(k, n))
    result['interval_method'] = 'exact binomial; descriptive pointwise interval'
    result['cases_needed_assumption'] = 'Stationary observed rate with additional cases; not a promise.'
    result['cases_needed'] = cases_needed(k, n, target) if result['state'] == 'undecided' else 0
    if result['state'] == 'undecided':
        result['reason'] = ('No mature cases; a current rate cannot be estimated.' if not n else 'At the target rate, more cases at this rate cannot decide the result.' if k / n == target / 100 else 'Fewer than 20 mature leads; no outcome pass or promotion.' if n < 20 else 'Too few cases to decide against the target.')
    return result


PUBLIC_OUTCOME_LABELS = {'reply_rate': 'Applied → reply within 7 days',
    'reply_to_call': 'Reply → booked call, held call, offer or contract within 14 days',
    'invite_to_call': 'Invite → booked call, held call, offer or contract within 14 days',
    'call_to_won': 'Held call → won within 21 days'}


HORIZONS = {'reply_rate': 7, 'reply_to_call': 14, 'booked_to_held': 2,
            'held_to_proposal': 7, 'proposal_to_won': 21, 'invite_to_call': 14,
            'offer_to_contract': 21, 'call_to_won': 21}


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
    rows = cohort(jobs, 'call_held', 21, today, span(today, 28), strand)
    result = rate_metric('proposal_to_won', rows, lambda job: has_after(job, 'won', event(job, 'call_held'), event(job, 'call_held') + dt.timedelta(days=21)), 30)
    result.update(label='Held call → won within 21 days', outcome_label=PUBLIC_OUTCOME_LABELS['call_to_won'], progression=None, strand=strand, horizon_days=21,
                  entry_period=period(tuple(value - dt.timedelta(days=21) for value in span(today, 28))),
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
    currencies = {job['won_value']['currency'] for job in valued}
    currency = next(iter(currencies)) if len(currencies) == 1 else 'USD' if not currencies else None
    subtotal = sum(contract_value(job) for job in valued)
    unknown = len(wins) - len(valued)
    bills = [row for row in latest_earnings(earnings) if inside(row.get('week_start'), bounds) and number(row.get('billed'))]
    bill_currencies = {row.get('currency') for row in bills}
    billed = sum(row['billed'] for row in bills) if len(bill_currencies) <= 1 else None
    fixed = sum(contract_value(job) for job in valued if job['won_value']['type'] == 'fixed')
    hourly = sum(contract_value(job) for job in valued if job['won_value']['type'] == 'hourly')
    return {'value': subtotal if currency and not unknown else None,
            'known_subtotal': subtotal if currency else None, 'fixed_value': fixed if currency else None,
            'hourly_contract_value': hourly if currency else None, 'hourly_billed': billed,
            'billed_currency': next(iter(bill_currencies), 'USD') if len(bill_currencies) <= 1 else None,
            'currency': currency, 'evidence': ids(wins), 'wins': len(wins), 'valued_wins': len(valued),
            'value_unknown_n': unknown, 'hourly_wins_unknown': sum((job.get('won_value') or {}).get('type') == 'hourly' and contract_value(job) is None for job in wins),
            'hourly_note': 'Value unknown for wins without complete agreed terms.' if unknown else 'Multiple currencies need a verified exchange rate.' if not currency else None}


def source_coverage(jobs, today, now=None):
    sync_path = data_path('sync.json')
    sync = json.loads(sync_path.read_text(encoding='utf-8')) if sync_path.is_file() else {}
    synced = timestamp(sync.get('synced_at'))
    cutoff = run_timestamp(now=now)
    upwork = 'missing' if sync.get('status') == 'error' or not synced or synced > cutoff else 'stale' if cutoff - synced >= dt.timedelta(hours=24) else 'ok'
    jobdir = pipeline.jobs_dir()
    recorder = bool(sections().get('Call recorder') or sections().get('Recorder') or any(event(job, 'call_held') for job in jobs) or any(jobdir.glob('*/call.md')))
    loom = bool(any(jobdir.glob('*/loom.md')) or any(job.get('loom_hook') for job in jobs))
    loom_used = any(job.get('loom_url') for job in jobs) or any(re.search(r'https?://(?:www\.)?(?:loom\.com|youtu\.be|youtube\.com)/', path.read_text(encoding='utf-8')) for path in jobdir.glob('*/application.sent.md'))
    tracking = bool(os.environ.get('BLOB_READ_WRITE_TOKEN') or any(job.get('pitch_url') or event(job, 'opened') or event(job, 'pitch_opened') for job in jobs))
    rows = []
    for source, state, affects, fix in (
        ('upwork', upwork, list(LABELS)[:15], 'Run /brief to sync Upwork.'),
        ('recorder', 'ok' if recorder else 'missing', ['call_review'], 'Add a labelled call transcript or confirm held calls.'),
        ('tracking', 'ok' if tracking else 'missing', [], 'Check the tracking link and its saved click source.'),
        ('loom', 'ok' if loom else 'missing', ['application_review'] if loom_used else [], 'Add the Loom transcript when the application uses Loom.'),
        ('earnings', 'ok' if data_path('earnings.jsonl').is_file() else 'missing', [], 'Read the earnings summary in /brief.'),
        ('connects', 'ok' if data_path('connects.jsonl').is_file() else 'missing', ['value_per_100_connects'], 'Read the Connects history in /brief.')):
        rows.append({'source': source, 'state': state, 'affects': affects, 'fix': fix if state != 'ok' else ''})
    return rows, sync.get('synced_at')


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
def calculate(jobs, today, since=None, now=None, cohort_days=28):
    limits, bounds, activity = bars(), span(today, cohort_days), span(today, 7)
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
                if not job.get('imported') and route(job) == 'outbound' and scheduled and not session.get('cancelled') and (since is None or day(scheduled) >= since) and inside(scheduled, tuple(value - dt.timedelta(days=2) for value in bounds)):
                    held_at = timestamp(session.get('held_at')) if session else event(job, 'call_held')
                    rows.append(dict(job, attendance_entry_at=scheduled.isoformat(), attendance_held_at=held_at.isoformat() if held_at else None))
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
    passed = (median_high is not None and p75_high is not None and not open_n
              and median_high <= limits['first_reply'] and p75_high <= limits['first_reply_p75'])
    failed = bool(values and (median_low > limits['first_reply'] or p75_low > limits['first_reply_p75']))
    state = 'pass' if passed else 'fail' if failed else 'undecided'
    kpis['first_reply'] = metric('first_reply', sum(not pending and value <= limits['first_reply'] for _, value, pending in reply_rows),
        len(values), median, limits['first_reply'], state, ids([job for job, _, _ in reply_rows]),
        None if state != 'undecided' else 'Quantile uncertainty or unanswered client messages; open ages are lower bounds.')
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
        if row['n'] and row['state'] != 'missing':
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
    total = financial(jobs, [], bounds)
    connects = [row for row in read_lines('connects.jsonl') if number(row.get('amount')) and inside(row.get('at'), bounds)
               and (since is None or day(row.get('at')) >= since)]
    # The period ratio is descriptive, never acquisition ROI. Only refunds offset spend;
    # grants and purchases do not offset application charges.
    debit = sum(-row['amount'] for row in connects if row['amount'] < 0)
    refunds = sum(row['amount'] for row in connects if row['amount'] > 0 and 'refund' in str(row.get('purpose') or row.get('type') or row.get('description', '')).casefold())
    spend = max(0, debit - refunds)
    kpis['value_per_100_connects'] = metric('value_per_100_connects', total['wins'], spend,
        total['value'] / spend * 100 if spend and total['value'] is not None else None, limits['value_per_100_connects'],
        'undecided', total['evidence'], 'Descriptive period ratio; not attributable acquisition ROI.')
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
        before = calculate(jobs, start + dt.timedelta(days=horizon), now=now, cohort_days=7)[0][key]
        # A full post-change entry week must have the complete KPI follow-up.
        mature = today >= start + dt.timedelta(days=7 + horizon)
        post = copy.deepcopy(jobs)
        for job in post:
            for name in ('applied', 'replied', 'call_booked', 'call_held', 'proposal_sent', 'invited', 'first_reply'):
                if day(job.get(name + '_at')) and day(job[name + '_at']) < start: job.pop(name + '_at', None)
            job['history'] = [item for item in job.get('history', []) if day(item.get('at')) and day(item['at']) >= start]
            job['follow_up_history'] = [item for item in job.get('follow_up_history', []) if day(item.get('due_on')) and day(item['due_on']) >= start]
            if day((job.get('won_value') or {}).get('start_date')) and day(job['won_value']['start_date']) < start: job.pop('won_value', None)
        # Compare one pre-change week and one post-change week; funnel entry populations
        # each span 28 days and have equal follow-up, with no pre-start observations.
        after_date = min(today, start + dt.timedelta(days=7 + horizon))
        after = calculate(post, after_date, since=start, now=now, cohort_days=7)[0][key]
        low, high = difference_bounds(before, after)
        effect = 'undecided'
        if mature and before['state'] != 'missing' and after['state'] != 'missing':
            if key in ('follow_ups_on_time', 'job_fit', 'speed_10min', 'proposal_on_time', 'weekly_volume') and number(before['value']) and number(after['value']) and before.get('n') and after.get('n') and before['state'] in ('pass', 'fail') and after['state'] in ('pass', 'fail'):
                effect = 'worked' if after['value'] > before['value'] else 'not' if after['value'] < before['value'] else 'undecided'
            elif key == 'first_reply' or key in FUNNEL:
                if key == 'first_reply' and (before.get('open_n') or after.get('open_n')): low, high = None, None
                if number(low) and number(high):
                    effect = ('worked' if high < 0 else 'not' if low > 0 else 'undecided') if before['direction'] == 'down' else ('worked' if low > 0 else 'not' if high < 0 else 'undecided')
        rows.append({'goal_id': goal['goal_id'], 'start': start.isoformat(), 'review_on': goal['review_on'],
            'change': goal['change'], 'kpi': key, 'done_k': 0, 'done_n': 0, 'effect': effect, 'mature': mature,
            'before': before['value'], 'after': after['value'], 'decision': 'adjust', 'before_k': before['k'],
            'before_n': before['n'], 'after_k': after['k'], 'after_n': after['n'], 'state': after['state'],
            'attainment': after['state'], 'difference_low': rounded(low), 'difference_high': rounded(high),
            'effect_note': 'Observed before/after change, not causal attribution.',
            'execution_state': 'unverified', 'evidence_lead_ids': [], 'done_lead_ids': [], 'outcome_evidence': after['evidence']})
    return rows


def apply_ladders(kpis, history, today, jobs, now=None):
    dates = [event(job, name).astimezone(local_zone()).date() for job in jobs if not job.get('imported')
             for name in ('applied', 'invited', 'offer') if event(job, name)]
    dates += [dt.date.fromisocalendar(int(row['week'][:4]), int(row['week'][6:]), 1) for row in history]
    start = min(dates, default=today)
    start -= dt.timedelta(days=start.weekday())
    phase = today < start + dt.timedelta(weeks=4)
    first_four = calculate(jobs, start + dt.timedelta(weeks=4), now=now)[0]
    for key in FUNNEL:
        row = kpis[key]
        rungs = list(RUNGS[key])
        rungs[-1] = bars()[key]
        # A top-rung override must not reverse the ladder.
        require(len(rungs) == 1 or rungs[-1] > rungs[-2], f'{key} top rung must exceed its previous rung.')
        previous = [item.get('kpis', {}).get(key, {}) for item in sorted(history, key=lambda item: item['week'])]
        reached = max([sum(rate_state(row['k'], row['n'], rung) == 'pass' for rung in rungs)] +
                      [min(len(rungs), item.get('rung_reached', 0)) for item in previous if not item.get('baseline_phase', False)])
        target = rungs[min(reached, len(rungs) - 1)]
        benchmark = row['value'] if phase else first_four[key]['value']
        if reached and not phase:
            benchmark = rungs[reached - 1]
        avg = row.get('average_won_value')
        row['lost_revenue'] = max(0, target - row['value']) / 100 * row['n'] * row['downstream_to_won'] * avg if number(row['value']) and number(avg) and number(row.get('downstream_to_won')) else None
        row.update(own_benchmark=benchmark, initial_benchmark=first_four[key]['value'], rungs=rungs, rung_reached=reached, target=target,
                   ladder_mode='maintain' if reached == len(rungs) else 'advance', promotion_policy='Exact pointwise coaching evidence; historical attainment, not lifetime confidence',
                   target_text=f'{target:g} %', baseline_phase=phase, baseline_ready=not phase and row['n'] >= 20)
        if row['state'] != 'missing':
            row['state'] = 'undecided' if phase else rate_state(row['k'], row['n'], target)
            row['cases_needed'] = cases_needed(row['k'], row['n'], target) if row['state'] == 'undecided' else 0
            row['reason'] = 'Weeks 1–4 collect your own baseline; no rate verdict.' if phase else (
                'Fewer than 20 mature leads; no outcome pass or promotion.' if row['state'] == 'undecided' and row['n'] < 20 else 'Too few mature cases to decide against the next rung.' if row['state'] == 'undecided' else None)


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
        rows = [job for job in jobs if not job.get('imported') and route(job) == 'outbound' and inside(event(job, 'applied'), (date, date))]
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


def community_card(jobs, today, kpis, reviews, week, streak, now=None):
    current, previous = calculate(jobs, today, now=now)[0], calculate(jobs, today - dt.timedelta(days=28), now=now)[0]
    bounds = span(today, 28)
    cutoff = dt.datetime.combine(today, dt.time(), local_zone())
    now_call, old_call = call_to_won(jobs, today), call_to_won(jobs, today - dt.timedelta(days=28))
    result = {'week': week, 'applications': sum(qualified(job) for job in cohort(jobs, 'applied', 0, today, span(today, 7), 'outbound')),
              'streak_weeks': streak, 'goals_done': f"{sum(row['done_n'] > 0 and row['done_k'] == row['done_n'] for row in reviews)}/{sum(row['done_n'] > 0 for row in reviews)}",
              'goals': [{'text': ' '.join(row['change'].split()[:6]), 'done': row['done_n'] > 0 and row['done_k'] == row['done_n'],
                        'k': row['done_k'], 'n': row['done_n'], 'state': row.get('execution_state', 'unverified')} for row in reviews],
              'next_focus': None, 'question': None, 'new_badge': None, 'top_badges': []}
    improvements = []
    for name, row, old, rungs in (('reply_rate', current['reply_rate'], previous['reply_rate'], (11, 15, 20)),
                                 ('reply_to_call', current['reply_to_call'], previous['reply_to_call'], (30, 40, 50)),
                                 ('call_to_won', now_call, old_call, (20, 25, 30))):
        value, prior = row['value'], old['value']
        low, high = difference_bounds(old, row)
        trend = 'up' if number(low) and low > 0 else 'down' if number(high) and high < 0 else 'undecided'
        result[name] = {'value': value, 'target': rungs[-1], 'rung_reached': sum(rate_state(row['k'], row['n'], rung) == 'pass' for rung in rungs), 'of': 3, 'trend': trend,
                        'k': row['k'], 'n': row['n'], 'state': row['state'], 'horizon_days': HORIZONS[name],
                        'entry_period': row['entry_period'], 'outcome_label': row['outcome_label'], 'progression': row.get('progression')}
        if trend == 'up':
            improvements.append({'kpi': name, 'from': prior, 'to': value})
    reply_cases = response_cases(jobs, bounds, run_timestamp(today, now))
    values = [value for _, value, _ in reply_cases]
    result['first_reply_median_min'] = statistics.median(values) if values and not any(pending for _, _, pending in reply_cases) else None
    result['first_reply_target_min'] = 5
    result['biggest_improvement'] = next(iter(improvements), None)
    result['won_value'] = financial(jobs, read_lines('earnings.jsonl'), bounds)['value'] if sections().get('Share money', '').strip().casefold() == 'yes' else None
    return result


def badge_results(snapshot, jobs, history, today):
    """Earned tiers persist; consecutive counters only use uninterrupted ISO weeks."""
    week = snapshot['week']
    old = {}
    earned_history = history + [row for row in read_lines('analytics-history.jsonl') if row.get('week') == week]
    for row in sorted(earned_history, key=lambda item: item['week']):
        for badge in row.get('badges', []):
            if badge.get('tier') in TIERS:
                old.setdefault((badge['badge'], badge['tier']), dict(badge, new=False))
    prior = {row['week']: row for row in history}
    monday = today - dt.timedelta(days=today.weekday())
    def week_run(test):
        count = 0
        for back in range(53):
            iso = (monday - dt.timedelta(weeks=back)).isocalendar()
            key = f'{iso.year}-W{iso.week:02d}'
            row = snapshot if back == 0 else prior.get(key)
            if row is None or not test(row):
                break
            count += 1
        return count
    def lever_ratio(row, key, target):
        item = row.get('kpis', {}).get(key, {})
        return item.get('state') == 'pass' and number(item.get('value')) and item.get('n', 0) > 0 and item['value'] >= target
    def consecutive(values):
        count = 0
        for value in reversed(values):
            if not value:
                break
            count += 1
        return count
    rows = [job for job in jobs if not job.get('imported')]
    applied = sorted([job for job in rows if qualified(job, reviewed_unclear=False) and event(job, 'applied') and event(job, 'applied').astimezone(local_zone()).date() < today], key=lambda job: event(job, 'applied'))
    first = [job for job in rows if timestamp(job.get('first_reply_at')) and day(job['first_reply_at']) < today and number(job.get('first_reply_s'))]
    proposals = sorted([job for job in rows if proposal_eligible(job) and call_end(job) and call_end(job) + dt.timedelta(minutes=30) < dt.datetime.combine(today, dt.time(), local_zone())], key=lambda job: event(job, 'call_held'))
    proposal_times = [(event(job, 'proposal_sent') - call_end(job)).total_seconds() / 60 if event(job, 'proposal_sent') else math.inf for job in proposals]
    invites = sorted([job for job in rows if route(job) == 'invite' and event(job, 'invited') and
                      (timestamp(job.get('first_reply_at')) or event(job, 'invited') + dt.timedelta(hours=1) < dt.datetime.combine(today, dt.time(), local_zone()))], key=lambda job: event(job, 'invited'))
    invite_times = [(timestamp(job['first_reply_at']) - event(job, 'invited')).total_seconds() / 60
                    if timestamp(job.get('first_reply_at')) else math.inf for job in invites]
    weeks = span(today, 7)
    proposal_week = [value for job, value in zip(proposals, proposal_times) if inside(event(job, 'call_held'), weeks)]
    invite_week = [value for job, value in zip(invites, invite_times) if inside(event(job, 'invited'), weeks)]
    call_points = []
    for row in sorted(history, key=lambda item: item['week']) + [snapshot]:
        if row.get('kpis', {}).get('call_review', {}).get('state') != 'pass':
            continue
        for review in row.get('reviews', {}).get('call', {}).get('rubric', []):
            if review.get('reviewable'):
                call_points.append((str(review['lead_id']), 9 * sum(item['state'] == 'met' for item in review['points']) / max(1, sum(item['state'] != 'not needed' for item in review['points']))))
    # A reviewed call earns once even if it appears in several rolling reviews.
    points_by_id = dict(call_points)
    calls = sorted(points_by_id, key=lambda jid: event(next((job for job in jobs if str(job['id']) == jid), {}), 'call_held') or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
    call_values = [points_by_id[jid] for jid in calls]
    revival = False
    for job in rows:
        path = pipeline.jobs_dir() / str(job['id']) / 'thread.json'
        thread = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        answers = [timestamp(item.get('at')) for item in thread.get('messages', []) if item.get('from') == 'client' and item.get('kind', 'message') == 'message']
        answers += [event(job, 'replied')]
        for item in job.get('follow_up_history', []):
            sent = timestamp(item.get('at') or item.get('on'))
            if item.get('lane') == 'silent' and item.get('action') == 'sent' and sent and any(answer and answer > sent for answer in answers):
                revival = True
    speed_run = week_run(lambda row: lever_ratio(row, 'speed_10min', 80))
    reply_run = week_run(lambda row: row.get('kpis', {}).get('first_reply', {}).get('state') == 'pass')
    follow_run = week_run(lambda row: lever_ratio(row, 'follow_ups_on_time', 100))
    anchor_run = week_run(lambda row: row.get('kpis', {}).get('weekly_volume', {}).get('state') == 'pass')
    nav_run = week_run(lambda row: all(row.get('kpis', {}).get(key, {}).get('state') == 'pass' for key in LEVERS))
    streak = snapshot['streak_weeks']
    wins = sum(bool(event(job, 'won') and day(event(job, 'won')) < today) for job in jobs)
    won_thresholds = (1, 5, 10, 25, 50)
    missed = False
    if history:
        latest = max(dt.date.fromisocalendar(int(row['week'][:4]), int(row['week'][6:]), 1) for row in history)
        missed = (monday - latest).days >= 21
    recovered_before = any(row.get('badge') == 'Back on Course' for row in old.values())
    tests = {
        'Swift Sail': ([any(number(job.get('speed_to_lead_s')) and 0 <= job['speed_to_lead_s'] <= 120 for job in applied)] + [speed_run >= n for n in (1, 4, 12, 26)], speed_run, (None, 1, 4, 12, 26), 'weeks'),
        "Ship's Bell": ([any(0 <= job['first_reply_s'] <= 60 for job in first)] + [reply_run >= n for n in (1, 4, 12, 26)], reply_run, (None, 1, 4, 12, 26), 'weeks'),
        'Lookout': ([revival] + [follow_run >= n for n in (1, 4, 12, 26)], follow_run, (None, 1, 4, 12, 26), 'weeks'),
        'Steady Anchor': ([anchor_run >= n for n in (1, 2, 4, 12, 26)], anchor_run, (1, 2, 4, 12, 26), 'weeks'),
        'Quick Draw': ([any(0 <= value <= 10 for value in proposal_times), bool(proposal_week) and sum(0 <= value <= 30 for value in proposal_week) / len(proposal_week) >= .9] + [consecutive([0 <= value <= 30 for value in proposal_times]) >= n for n in (5, 15, 40)], consecutive([0 <= value <= 30 for value in proposal_times]), (None, None, 5, 15, 40), 'proposals'),
        'Message in a Bottle': ([any(0 <= value <= 5 for value in invite_times), bool(invite_week) and all(0 <= value <= 60 for value in invite_week)] + [consecutive([0 <= value <= 60 for value in invite_times]) >= n for n in (5, 15, 40)], consecutive([0 <= value <= 60 for value in invite_times]), (None, None, 5, 15, 40), 'invites'),
        'True North': ([any(value >= 7 for value in call_values), any(value == 9 for value in call_values)] + [consecutive([value == 9 for value in call_values]) >= n for n in (3, 10, 25)], consecutive([value == 9 for value in call_values]), (None, None, 3, 10, 25), 'calls'),
        'Navigator': ([nav_run >= n for n in (1, 2, 4, 12, 26)], nav_run, (1, 2, 4, 12, 26), 'weeks'),
        'Lighthouse Keeper': ([streak >= n for n in (2, 4, 8, 26, 52)], streak, (2, 4, 8, 26, 52), 'weeks'),
        'First Doubloon': ([wins >= n for n in won_thresholds], wins, won_thresholds, 'wins'),
        'Back on Course': ([missed or recovered_before], int(missed or recovered_before), (1,), 'returns')}
    result = []
    for name in BADGE_NAMES:
        if name in OUTCOME_BADGES:
            key, thresholds = OUTCOME_BADGES[name]
            if key == 'call_to_won':
                item = snapshot['call_to_won']
                low = item['low']
                phase = snapshot['kpis']['proposal_to_won']['baseline_phase']
                available = snapshot['kpis']['proposal_to_won']['state'] != 'missing'
            else:
                item = snapshot['kpis'][key]
                low, phase, available = item['low'], item['baseline_phase'], item['state'] != 'missing'
            earned_weeks = {row['earned_week'] for row in old.values() if row.get('badge') == name}
            used = set()
            for earlier in earned_history:
                if earlier['week'] in earned_weeks:
                    measure = earlier.get('call_to_won', {}) if key == 'call_to_won' else earlier.get('kpis', {}).get(key, {})
                    used.update(measure.get('evidence', []))
            fresh = not used.intersection(item.get('evidence', []))
            review_index = len({row['week'] for row in history if row['week'] < week}) + 1
            promotion_low = exact_bounds(item['k'], item['n'], .05 / (3 * 5 * review_index * (review_index + 1)))[0] if item.get('n') else None
            tier_qualified = [available and not phase and item.get('n', 0) >= 20 and fresh and number(promotion_low) and promotion_low >= threshold for threshold in thresholds]
            highest = max([index for index, tier in enumerate(TIERS) if (name, tier) in old or tier_qualified[index]], default=-1)
            progress = f'Lower bound at least {thresholds[highest + 1]} %' if highest < 4 else 'All tiers earned'
        else:
            tier_qualified, count, thresholds, unit = tests[name]
            highest = max([index for index, tier in enumerate(TIERS[:len(tier_qualified)]) if (name, tier) in old or tier_qualified[index]], default=-1)
            next_index = highest + 1
            progress = ('All tiers earned' if next_index >= len(tier_qualified) else
                        f'{min(count, thresholds[next_index])} of {thresholds[next_index]} {unit}' if thresholds[next_index] is not None else
                        'One standout moment' if next_index == 0 else 'One qualifying week' if name != 'True North' else 'One call with 9 of 9 points')
        for index in range(len(tier_qualified)):
            tier = TIERS[index]
            earned = old.get((name, tier))
            if earned or tier_qualified[index]:
                result.append({'badge': name, 'tier': tier, 'earned_week': earned['earned_week'] if earned else week,
                               'new': earned is None or earned['earned_week'] == week, 'progress_to_next': progress})
    return result


def finish_views(result, jobs, history, today, now=None):
    stage_keys = {'applied': 'reply_rate', 'replied': 'reply_to_call', 'call': 'proposal_to_won', 'offer': 'offer_to_contract'}
    for row in result['forecast']['by_stage']:
        kpi = result['kpis'][stage_keys[row['stage']]]
        if kpi['baseline_phase'] or kpi['state'] in ('missing', 'undecided'):
            row.update(own_rate=None, expected=None)
    result['forecast']['next_30_days'] = rounded(sum(row['expected'] for row in result['forecast']['by_stage'])) if all(row['expected'] is not None for row in result['forecast']['by_stage']) else None
    result['todos'] = lead_todos(jobs, today, result['goals_next'])
    result['call_to_won'] = call_to_won(jobs, today)
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
    return result


@member_clock
def compute(today=None, jobs=None, now=None):
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
    history = read_lines('analytics-history.jsonl')
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
    for key, row in kpis.items():
        row['history'] = [by_week.get(old, {}).get('kpis', {}).get(key, {}).get('value') for old in previous_weeks] + [row['value']]
    north['history'] = [by_week.get(old, {}).get('north_star', {}).get('value') for old in previous_weeks] + [north['value']]
    reviews = goal_reviews(jobs, today, run_at)
    kpis['goal_effect'].update(k=sum(row['effect'] == 'worked' for row in reviews), n=len(reviews), value=None, evidence=sorted({jid for row in reviews for jid in row['outcome_evidence']}))
    kpis['goal_done'].update(k=0, n=len(reviews), value=0, target=len(reviews), target_text=f'{len(reviews)} commitments', state='undecided', reason='Execution evidence must be reviewed.')
    coverage, synced_at = source_coverage(jobs, today, run_at)
    streak = 1
    back = 1
    while True:
        old_iso = (monday - dt.timedelta(weeks=back)).isocalendar()
        if f'{old_iso.year}-W{old_iso.week:02d}' not in by_week:
            break
        streak += 1
        back += 1
    result = {'week': week, 'generated_at': run_at.isoformat(),
            'window': period(span(today, 28)), 'periods': {'activity': period(span(today, 7)), 'cohort': period(span(today, 28)), 'outcome': period(span(today, 7)), 'synced_at': synced_at},
            'coverage': coverage, 'pipeline': pipeline_counts(jobs, today), 'kpis': kpis,
            'verdict': verdict(kpis), 'verdict_history': [{'week': old, 'kpi': by_week[old].get('verdict', {}).get('kpi'), 'stage': by_week[old].get('verdict', {}).get('stage')} for old in previous_weeks if old in by_week],
            'north_star': north, 'goals_review': reviews, 'goals_next': [], 'findings': [],
            'reviews': {name: {'fix': '', 'example': '', 'evidence_lead_ids': [], 'goal_ref': None} for name in ('application', 'conversation', 'call', 'proposal')},
            'streak_weeks': streak, 'report': ''}
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
        thread = json.loads(path.read_text(encoding='utf-8'))
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
        if len(path) == 3 and path[0] == 'reviews' and path[2] == 'example':
            require(isinstance(item, str), 'Review examples need the member’s own wording.')
            require(not any(text.casefold() in item.casefold() for text in client_text), 'Review examples cannot quote the client’s wording.')
            return
        if isinstance(item, dict):
            require(not (set(item) & forbidden), 'Snapshot contains raw client fields.')
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
        require(isinstance(item, dict) and set(item) == {'lead_id', 'reviewable', 'points'}, 'Call rubric needs lead_id, reviewable and points.')
        require(item['lead_id'] not in seen and isinstance(item['reviewable'], bool), 'Call rubric needs unique leads and boolean reviewable.')
        seen.add(item['lead_id'])
        path = pipeline.jobs_dir() / str(item['lead_id']) / ('call.md' if name == 'call' else 'application.sent.md')
        text = path.read_text(encoding='utf-8') if path.is_file() else ''
        speakers = {match[1].strip() for match in re.finditer(r'^([^:\n]+):\s*\S', text, re.M) if match[1].strip().lower() not in ('call at', 'duration', 'member', 'speakers', 'date', 'recorder', 'complete', 'language')}
        if name == 'call':
            require(not item['reviewable'] or (len(speakers) >= 2 and 'talk_share_basis' in call_stats.analyze(text)), 'A reviewable call needs complete speaker labels and member identity.')
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
            require(set(row) == {'point', 'state'} and row['state'] in (('met', 'partly', 'missing', 'not needed') if name == 'call' else ('met', 'partly', 'missing')), 'Call point needs point and state only; quotes stay in lead evidence.')
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


def validate_community_card(card, jobs=None):
    jobs = pipeline.load() if jobs is None else jobs
    keys = {'week', 'applications', 'streak_weeks', 'goals_done', 'goals', 'next_focus', 'question',
            'new_badge', 'top_badges', 'reply_rate', 'reply_to_call', 'call_to_won',
            'first_reply_median_min', 'first_reply_target_min', 'biggest_improvement', 'won_value'}
    require(isinstance(card, dict) and set(card) == keys, 'Public card has unknown or missing fields.')
    def numeric(value): return value is None or number(value)
    require(re.fullmatch(r'\d{4}-W\d{2}', str(card['week'])), 'Invalid public week.')
    for key in ('applications', 'streak_weeks', 'first_reply_median_min', 'first_reply_target_min', 'won_value'):
        require(numeric(card[key]), 'Public numeric field must be a finite number or null.')
    require(re.fullmatch(r'\d+/\d+', str(card['goals_done'])), 'Invalid goal aggregate.')
    require(card['next_focus'] is None or card['next_focus'] in LABELS.values(), 'Public focus must be a fixed stage label.')
    require(card['question'] is None or card['question'] in PUBLIC_QUESTIONS, 'Public questions must use a fixed approved label.')
    approved = set()
    for row in read_lines('goals.jsonl'):
        for goal in row.get('goals', []): approved.add(' '.join(goal['change'].split()[:6]))
    for row in read_lines('analytics-history.jsonl'):
        for goal in row.get('goals_next', []): approved.add(' '.join(goal['change'].split()[:6]))
    library = ROOT / 'references/goal-library.md'
    if library.is_file():
        approved.update(' '.join(line.strip(' -|').split()[:6]) for line in library.read_text().splitlines() if line.strip())
    require(isinstance(card['goals'], list), 'Public goals must be a list.')
    for goal in card['goals']:
        require(isinstance(goal, dict) and set(goal) == {'text', 'done', 'k', 'n', 'state'} and goal['text'] in approved and
                isinstance(goal['done'], bool) and numeric(goal['k']) and numeric(goal['n']) and
                goal['state'] in ('unverified', 'no opportunity', 'complete', 'partial', 'undone'), 'Public goals need approved member/library text and computed execution.')
    for key in ('reply_rate', 'reply_to_call', 'call_to_won'):
        rate = card[key]
        require(isinstance(rate, dict) and set(rate) == {'value', 'target', 'rung_reached', 'of', 'trend', 'k', 'n', 'state', 'horizon_days', 'entry_period', 'outcome_label', 'progression'}, 'Unknown public rate fields.')
        require(all(numeric(rate[field]) for field in ('value', 'target', 'rung_reached', 'of', 'k', 'n', 'horizon_days')) and
                rate['trend'] in ('up', 'down', 'undecided') and rate['state'] in ('pass', 'fail', 'missing', 'undecided'), 'Invalid public rate values.')
        require(rate['outcome_label'] == PUBLIC_OUTCOME_LABELS[key], 'Public outcome definition must use its fixed label.')
        progression = rate['progression']
        require(progression is None or (isinstance(progression, dict) and set(progression) == {'booked_calls', 'held_calls', 'offer_or_contract_without_call'} and
                all(number(value) and value >= 0 for value in progression.values())), 'Public progression must contain fixed numeric counts only.')
        require(isinstance(rate['entry_period'], dict) and set(rate['entry_period']) == {'start', 'end'} and
                all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)) for value in rate['entry_period'].values()), 'Invalid public entry period.')
    improvement = card['biggest_improvement']
    require(improvement is None or (isinstance(improvement, dict) and set(improvement) == {'kpi', 'from', 'to'} and
            improvement['kpi'] in ('reply_rate', 'reply_to_call', 'call_to_won') and numeric(improvement['from']) and numeric(improvement['to'])), 'Invalid public improvement.')
    require(isinstance(card['top_badges'], list), 'Public badges need a list.')
    for badge in card['top_badges'] + ([card['new_badge']] if card['new_badge'] else []):
        require(isinstance(badge, dict) and set(badge) == {'badge', 'tier', 'earned_week', 'new', 'progress_to_next'} and
                badge['badge'] in BADGE_NAMES and badge['tier'] in TIERS and re.fullmatch(r'\d{4}-W\d{2}', str(badge['earned_week'])) and
                isinstance(badge['new'], bool) and (badge['progress_to_next'] in ('All tiers earned', 'One standout moment', 'One qualifying week', 'One call with 9 of 9 points') or
                re.fullmatch(r'Lower bound at least \d+ %|\d+ of \d+ (weeks|proposals|invites|calls|wins|returns)', badge['progress_to_next'])), 'Unknown public badge content.')
    # Member-authored goal wording cannot smuggle a known client identity/title/text.
    forbidden = set()
    def collect(item, key=''):
        if isinstance(item, dict):
            for field, value in item.items(): collect(value, field)
        elif isinstance(item, list):
            for value in item: collect(value, key)
        elif isinstance(item, str) and key in ('name', 'client_name', 'contract_client', 'title', 'description', 'text', 'content', 'message') and item.strip():
            forbidden.add(item.strip().casefold())
    for job in jobs: collect(job)
    for path in pipeline.jobs_dir().glob('*/thread.json'):
        thread = json.loads(path.read_text())
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
    prose = [goal['text'].casefold() for goal in card['goals']]
    require(not any(source in text for source in fragments for text in prose), 'Public goals contain client source material.')
    require(not any(re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d ()-]{7,}\d)', text) for text in prose), 'Public goal text cannot contain URLs or contact details.')
    return card


def claude_fields(result, value):
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
    else: require(set(card) <= {'next_focus', 'question'}, 'Partial public overlays may change only fixed focus/question labels.')
    if card.get('next_focus') is not None:
        require(card['next_focus'] in LABELS.values(), 'Community focus needs a known stage label.')
        result['community_card']['next_focus'] = card['next_focus']
    if card.get('question') is not None:
        require(card['question'] in PUBLIC_QUESTIONS, 'Public question must use an approved fixed label.')
        result['community_card']['question'] = card['question']
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
    for given in value.get('coverage', []):
        require(isinstance(given, dict) and {'source', 'state', 'fix'} <= set(given) and set(given) <= {'source', 'state', 'fix', 'affects'}, 'Source judgment needs source, state and fix.')
        source = next((row for row in result['coverage'] if row['source'] == given['source']), None)
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
    finish_views(result, pipeline.load(), history, today, result['generated_at'])
    claude_fields(result, value)
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
    require(result['community_card']['next_focus'] is not None and result['community_card']['question'] is not None, 'Claude must write the weekly community focus and question.')
    for key in ('window', 'periods', 'pipeline', 'streak_weeks', 'verdict_history', 'cohorts', 'daily_applications', 'reply_time_hist', 'speed_curve', 'segments', 'forecast', 'call_rubric_weeks', 'badges', 'todos', 'call_to_won'):
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
    require(value['community_card'] == result['community_card'], 'Community numbers, badges and goal marks must come from reviewed compute.')
    result['generated_at'] = value['generated_at']
    validate_community_card(result['community_card'])
    privacy(result)
    rows = read_lines('analytics-history.jsonl')
    duplicate = any(row.get('week') == result['week'] for row in rows)
    require(not duplicate or replace, 'This ISO week already has a snapshot; use --replace.')
    rows = [result if row.get('week') == result['week'] else row for row in rows] if replace and duplicate else rows + [result]
    atomic_lines('analytics-history.jsonl', rows)
    return result


def last():
    rows = read_lines('analytics-history.jsonl')
    return max(rows, key=lambda row: timestamp(row['generated_at'])) if rows else None


def due(today=None):
    date = as_today(today)
    snapshot = last()
    if snapshot is None: return True
    schedule = sections().get('Analytics day', 'Wednesday').casefold()
    names = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    weekday = next((index for index, name in enumerate(names) if name in schedule), 2)
    scheduled = date - dt.timedelta(days=(date.weekday() - weekday) % 7)
    return day(snapshot['generated_at']) < scheduled


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    calc = sub.add_parser('compute'); calc.add_argument('--today'); calc.add_argument('--now'); calc.add_argument('--file')
    record = sub.add_parser('record'); record.add_argument('--file', required=True); record.add_argument('--replace', action='store_true')
    goals = sub.add_parser('goals').add_subparsers(dest='action', required=True)
    goals.add_parser('add').add_argument('--file', required=True)
    sub.add_parser('last')
    due_parser = sub.add_parser('due'); due_parser.add_argument('--today')
    args = parser.parse_args(argv)
    try:
        if args.command == 'compute':
            overlay = json.load(sys.stdin) if args.file == '-' else json.loads(pathlib.Path(args.file).read_text(encoding='utf-8')) if args.file else None
            result = prepare_snapshot(overlay, args.today, args.now) if overlay is not None else compute(args.today, now=args.now)
        elif args.command == 'last':
            result = last()
        elif args.command == 'due':
            result = due(args.today)
        else:
            value = json.load(sys.stdin) if args.file == '-' else json.loads(pathlib.Path(args.file).read_text(encoding='utf-8'))
            result = record_snapshot(value, args.replace) if args.command == 'record' else add_goals(value)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f'ABORT: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
