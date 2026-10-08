#!/usr/bin/env python3
"""The counting half of /find-jobs. The judging half (does this job fit you?) is Claude's.

    python3 code/jobs.py window                                   # hours to search back, starts the run
    python3 code/jobs.py pause                                    # five seconds between Upwork calls
    python3 code/jobs.py candidates data/search/*.json [--window-hours 10]
    python3 code/jobs.py score [--min 50]                         # merges data/fit.json, logs
    python3 code/jobs.py detail <job_id> <find_jobs-get-response.json>
    python3 code/jobs.py lessons                                  # your past calls, to calibrate

A job's score is out of 100: niche fit 40 (Claude, from data/fit.json), client
trust 30, deal quality 20, recency 10 (all three counted here). A job under 20
on niche fit is never logged, whatever the rest says: a great client does not
rescue an irrelevant job.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# BLUEPRINT_DATA points tests at a throwaway folder, like BLUEPRINT_JOBS does for the pipeline.
DATA = pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')
CANDIDATES = DATA / 'candidates.json'
FIT = DATA / 'fit.json'
# What the gate turned down, kept across runs. `clean` deletes a run's raw
# responses; this is not one of them.
DECISIONS = DATA / 'decisions.jsonl'
# When this account last searched. The member's own record of their own runs, so
# `prune` leaves it alone: it holds no Upwork content, only a timestamp.
LAST_SEARCH = DATA / 'last-search.json'
# What the member's own outcomes have taught, written by learn.py lessons.
LESSONS = DATA / 'lessons.json'
PIPELINE = ROOT / 'code' / 'pipeline.py'
ME = pathlib.Path(os.environ.get('BLUEPRINT_ME') or ROOT / 'context' / 'me.md')
LANES = ROOT / 'templates' / 'profile' / 'lanes.md'
TAG = re.compile(r'</?untrusted_participant_content>')
MIN_WINDOW, MAX_WINDOW = 10, 12
RUN_FLOOR = 2          # the smallest window a repeat run asks for, in hours
# Everything a member reads about a job is one number out of ten, so there is no
# second scale to translate, no "points" behind a "grade", and nothing for the
# cockpit to print twice.
FIT_GATE = 6           # below this the job is not the member's work, whatever else is true
TRAP_CAP = 6           # a named trap can never reach the gate
MIN_SCORE = 7          # the gate, and the floor of the shortlist
MAX_DEDUCTION = 2      # doubts shave a fit, they never outweigh it: on a ten-point scale
                       # three would let a nine fail, and a nine is the member's own work
LESSON_CAP = 1         # what measured outcomes may move a score, in either direction
BEGINNER_DEDUCTION = 1 # the cap while the evidence sections are still empty
MIN_CLIENT_RATING = 3.0
FIXED_FLOOR = 250      # hard no below this on fixed price
HOURLY_FLOOR = 0.6     # hard no below this share of the member's own rate


def clean(text):
    return TAG.sub('', text or '').strip()


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_time(stamp):
    try:
        return datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None


def numbers(text):
    return [float(n.replace(',', '')) for n in re.findall(r'\d[\d,]*(?:\.\d+)?', str(text or ''))]


def money_value(text):
    found = numbers(text)
    return found[0] if found else None


def pipeline(*args, stdin=None):
    return subprocess.run([sys.executable, str(PIPELINE), *args], input=stdin,
                          capture_output=True, text=True)


def jobs_file():
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBS') or DATA / 'jobs.json')


def load_json(path, default):
    path = pathlib.Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def me_number(label):
    """One `**Label:**` figure from context/me.md, or None when it is not answered."""
    if not ME.is_file():
        return None
    match = re.search(rf'(?im)^\*\*{re.escape(label)}:\*\*[ \t]*\$?([\d,.]+)', ME.read_text(encoding='utf-8'))
    return float(match.group(1).replace(',', '')) if match else None


def member_rate():
    """Your hourly rate: the live profile first, then the file you filled in.

    The profile is the truth while it is fresh, but `prune` deletes it after a day,
    and without a rate two of the hard no's silently stop applying. So the answer in
    `context/me.md` is the fallback rather than nothing.
    """
    profile = load_json(DATA / 'profile.json', {})
    personal = profile.get('data', {}).get('personalData', {})
    return money_value((personal.get('chargeRate') or {}).get('rawValue')) or me_number('Hourly rate')


def member_floor():
    """The smallest project the member said is worth taking, or the shipped default."""
    return me_number('Smallest project worth taking') or FIXED_FLOOR


def member_limits():
    """The hard no's, the member's own answers first and the shipped starting points after.

    None of these is a number this repository gets to decide for everybody. A member
    without a single review wins nothing in a queue of forty proposals, so their cap
    belongs lower than an established one's; a member at sixty dollars an hour loses
    nothing by refusing fifteen. `/about-me` proposes per person, the member answers,
    and this reads the answer. `missing` names every limit that is switched off
    because the figure behind it is unknown, because a silent limit is worse than a
    loose one.
    """
    rate = member_rate()
    share = me_number('Lowest share of your rate')
    proposals = me_number('Maximum proposals on a job')
    fixed_floor = me_number('Smallest project worth taking')
    limits = {
        'rate': rate,
        'proposals': proposals,   # None unless the member set a maximum: no default cap
        'fixed_floor': fixed_floor or FIXED_FLOOR,
        'hourly_share': (share / 100 if share else HOURLY_FLOOR),
        'min_rating': MIN_CLIENT_RATING,
    }
    limits['missing'] = [] if rate else ['hourly floor, because no rate is known']
    limits['defaults'] = []
    if not fixed_floor:
        limits['defaults'].append(f'smallest fixed-price project: ${FIXED_FLOOR}')
    if not share:
        limits['defaults'].append(f'lowest share of your rate: {int(HOURLY_FLOOR * 100)}%')
    return limits


# --- window -----------------------------------------------------------------

def last_search():
    """When this account last searched, from the stamp `clean` leaves behind."""
    return parse_time(load_json(LAST_SEARCH, {}).get('at'))


def record_search():
    """Stamp this run, so the next one asks for the hours since it and no more."""
    DATA.mkdir(exist_ok=True)
    LAST_SEARCH.write_text(json.dumps({'at': now().isoformat()}, indent=2), encoding='utf-8')


def search_window_hours():
    """The hours to look back: since the last run, never past twelve hours.

    The stamp is the honest source, because a run that found nothing still covered
    its hours. The newest saved lead is the fallback for an account whose stamp was
    never written, and the twelve-hour ceiling the fallback for a first run. The floor is small on
    purpose: searching four times a day should cost four small windows, not four
    overlapping ten-hour ones.
    """
    stamp = last_search()
    if stamp:
        hours = (now() - stamp).total_seconds() / 3600
        return int(max(RUN_FLOOR, min(MAX_WINDOW, round(hours + 0.5))))
    raw = load_json(jobs_file(), [])
    stamps = [parse_time(j.get('found_at')) for j in raw if j.get('found_at')]
    stamps = [s for s in stamps if s]
    hours = 24 if not stamps else (now() - max(stamps)).total_seconds() / 3600
    return int(max(MIN_WINDOW, min(MAX_WINDOW, round(hours + 0.5))))


RUN_START = DATA / 'run-start.json'


def cmd_window(args):
    """Hours to search back, and the start of this run.

    The window runs from the last finished run, at most twelve hours: a posting older
    than that already carries a queue of proposals. A longer gap is named on a second
    line, so a member who searches once a day sees what the window left out. Raw search
    files an aborted run left behind are cleared here, because this run appends pages
    to fresh ones.
    """
    import shutil
    hours = search_window_hours()
    DATA.mkdir(exist_ok=True)
    RUN_START.write_text(json.dumps({'at': now().isoformat()}), encoding='utf-8')
    if (DATA / 'search').is_dir():
        shutil.rmtree(DATA / 'search')
    print(hours)
    stamp = last_search()
    if stamp:
        since = (now() - stamp).total_seconds() / 3600
        if since > MAX_WINDOW + 1:
            print(f'gap: {int(since - hours)} hours before the window were not searched')
    return 0


def cmd_pause(args):
    """Waits between two Upwork calls.

    Upwork restricted search on 8 October 2026 after about 45 searches in two minutes,
    partly parallel. It names no safe pace, so five seconds is reasoned, not measured.
    """
    import time
    time.sleep(args.seconds)
    return 0


def theme(label, terms):
    slug = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
    return {'label': label, 'slug': slug, 'terms': terms, 'query': ', '.join(terms)}


def branch_themes(text):
    """One theme per picked branch, straight from its Search line in lanes.md.

    Nothing is written to the member's file for this: the branches are their answer,
    the terms are ours, and a run rebuilds them every time. Only what the member
    adds themselves (a custom direction, an industry) lives under "Job search tracks".
    """
    match = re.search(r'^\*\*Branches you picked:\*\*[ \t]*(.*)$', text, re.M | re.I)
    if not match or 'not answered yet' in match.group(1).lower():
        return []
    try:
        lanes = LANES.read_text(encoding='utf-8')
    except OSError:
        return []
    search = {}
    for block in re.split(r'(?m)^## ', lanes)[1:]:
        heading = re.sub(r'^\d+\.\s*', '', block.splitlines()[0]).strip()
        line = re.search(r'(?m)^Search:\s*(.+)$', block)
        if line:
            search[heading.lower()] = (heading, [t.strip() for t in re.split(r'\s*·\s*', line.group(1)) if t.strip()])
    themes = []
    for name in re.split(r'\s*[·|]\s*', match.group(1)):
        found = search.get(re.sub(r'^\d+\.\s*', '', name.strip()).lower())
        if found:
            themes.append(theme(*found))
    return themes


def member_search_themes():
    try:
        text = ME.read_text(encoding='utf-8')
    except OSError:
        return []
    match = re.search(r'(?ms)^## Job search tracks\s*\n(.*?)(?=^## |\Z)', text)
    themes = []
    for line in (match.group(1).splitlines() if match else []):
        if not line.startswith('- ') or not line[2:].strip():
            continue
        item = line[2:].strip()
        if ':' in item:
            label, raw_terms = (part.strip() for part in item.split(':', 1))
            # Older runs put a dated verdict in parentheses beside the terms.
            # It is a decision about the theme, never part of a search query.
            raw_terms = re.sub(r'\s*\([^)]*\)', '', raw_terms)
            terms = [term.strip() for term in re.split(r'\s*[·|]\s*', raw_terms) if term.strip()]
        else:
            label, terms = item, [item]
        if label and terms:
            themes.append(theme(label, terms))
    # The member's own lines win over a branch theme of the same name; the branches
    # come first in their order, then whatever the member added, five at most.
    own = {t['slug']: t for t in themes}
    merged = [own.pop(t['slug'], t) for t in branch_themes(text)]
    return (merged + list(own.values()))[:5]


def source_matches_theme(source, theme):
    """Match current query slugs and the older per-term search file names."""
    source = str(source or '').lower()
    if not source.startswith(('query-', 'title-', 'search-')):
        return False
    source = re.sub(r'^(?:query|title|search)-', '', source).split('--')[0]
    source_key = re.sub(r'[^a-z0-9]+', '', source)
    keys = [theme.get('slug', '')] + theme.get('terms', [])
    return source_key in {re.sub(r'[^a-z0-9]+', '', str(key).lower()) for key in keys}


def query_performance(themes):
    """Observed downstream outcomes for saved leads, grouped by search theme."""
    jobs = load_json(jobs_file(), [])
    performance = []
    for theme in themes:
        matched = [job for job in jobs if any(source_matches_theme(source, theme)
                   for source in job.get('found_via', []))]
        applied = [job for job in matched if job.get('applied_at') or
                   job.get('status') in ('applied', 'replied', 'call', 'offer', 'won')]
        conversations = [job for job in matched if job.get('status') in ('replied', 'call', 'offer', 'won')]
        won = [job for job in matched if job.get('status') == 'won']
        skipped = [job for job in matched if job.get('status') == 'skipped']
        reasons = {}
        for job in skipped:
            for reason in re.findall(r'not a fit:\s*([^.]*(?:\.|$))', job.get('notes') or '', re.I):
                reason = reason.strip().rstrip('.')
                if reason:
                    reasons[reason] = reasons.get(reason, 0) + 1
        performance.append({
            'label': theme['label'],
            'saved': len(matched),
            'applied': len(applied),
            'conversations': len(conversations),
            'won': len(won),
            'skipped': len(skipped),
            'not_fit_reasons': [{'reason': reason, 'count': count}
                                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:3]],
        })
    return performance


def cmd_rules(args):
    """The live search and ranking contract, for people and the cockpit."""
    themes = member_search_themes()
    _LIMITS = member_limits()
    print(json.dumps({
        'tracks': [theme['label'] for theme in themes],
        'themes': themes,
        'query_mode': 'Job title match per term, plus one meaning-based query page per theme',
        'performance': query_performance(themes),
        'performance_scope': 'Downstream outcomes for saved leads only. Upwork retrieval totals are not retained.',
        'window_hours': search_window_hours(),
        'window_bounds': [MIN_WINDOW, MAX_WINDOW],
        'sources': ['Upwork recommendations', 'Title search per term', 'Query search per theme'],
        'filters': ['Already applied', 'Already in the pipeline', 'Outside the search window',
                    'Unverified payment', 'Full-time role',
                    *([f'More than {_LIMITS["proposals"]:g} proposals'] if _LIMITS['proposals'] else []),
                    f'Client rated under {MIN_CLIENT_RATING} by at least 3 freelancers',
                    f'Fixed price under ${_LIMITS["fixed_floor"]:g}',
                    f'Hourly top under {int(_LIMITS["hourly_share"] * 100)}% of the member rate'],
        'ranking': [
            {'label': 'Fit', 'points': 10,
             'uses': 'What the job is against what the member sells, judged with their own '
                     'application history. The fit is the score.'},
            {'label': 'Deductions', 'points': -MAX_DEDUCTION,
             'uses': 'Proposal count, a client who never hires or has no history, a missing or '
                     'low budget. They shave a fit, they never outweigh it.'},
        ],
        'gate': {'fit': FIT_GATE, 'score': MIN_SCORE, 'trap_cap': TRAP_CAP},
    }, ensure_ascii=False))
    return 0


# --- candidates -------------------------------------------------------------

def normalize(job, track):
    c = job.get('client') or {}
    proposals = job.get('proposal_count')
    # A search with include_full_details carries the whole posting; the field name is
    # documented, not yet seen, so both spellings are read and the snippet is the fallback.
    full = next((v for v in (job.get('description'), job.get('full_description')) if isinstance(v, str) and v.strip()), '')
    return {
        'id': str(job.get('id')),
        'title': clean(job.get('title')),
        'url': job.get('url'),
        'posted_date': job.get('published_date') or job.get('created_date'),
        'found_via': [track],
        'budget': job.get('budget') or job.get('hourly_budget_type') or '',
        'job_type': job.get('job_type'),
        'engagement': job.get('engagement'),
        'duration': job.get('duration'),
        'experience_level': job.get('experience_level'),
        'skills': job.get('skills') or [],
        'snippet': clean(full or job.get('description_snippet'))[:400],
        'description': clean(full or job.get('description_snippet')),
        'preview_only': not full,
        'proposals': proposals if proposals is not None else job.get('proposals_tier'),
        'applied': bool(job.get('applied')),
        'client': {
            'country': c.get('country'), 'rating': c.get('rating'), 'reviews': c.get('total_reviews'),
            'spent': money_value(c.get('total_spent')), 'posted_jobs': c.get('total_posted_jobs'),
            'hires': c.get('total_hires'), 'verified': c.get('verification_status') == 'VERIFIED',
        },
    }


def recency_points(posted, window_hours):
    t = parse_time(posted)
    if not t:
        return None
    age = (now() - t).total_seconds() / 3600
    if age > window_hours:
        return None
    return max(0, min(10, round(10 * (1 - age / window_hours))))


def budget_top(job):
    """The highest number the posting states, and whether it is an hourly figure."""
    budget = str(job.get('budget') or '')
    values = numbers(budget)
    hourly = '/hr' in budget or job.get('job_type') == 'hourly'
    return (max(values) if values else None), hourly


def drop_kind(reason, limits):
    """One line per kind of drop in the run summary, not one per figure.

    `disqualified` names the job's own number so a single lead reads clearly; summed
    over a run, "54 proposals" and "52 proposals" are the same reason.
    """
    if 'proposals, over your cap' in reason:
        return f'over your cap of {limits["proposals"]:g} proposals'
    if reason.startswith('pays '):
        return 'hourly top under your share of your rate'
    if reason.startswith('fixed budget of'):
        return f'fixed budget under your floor of {limits["fixed_floor"]:g}'
    if reason.startswith('client rated'):
        return 'client rated low by freelancers'
    return reason


def disqualified(job, limits):
    """The short list of hard no's. A reason, or None when the posting stays in.

    Points are for ranking what could be applied to. These are the cases where no
    score should be computed at all, because no fit saves them: the client cannot
    pay, the posting is an employment ad, the queue is too long to be worth
    Connects, or the money is below what the member said they work for. Every one
    of them is also a search filter, so this is the net under the filters, not a
    second opinion.
    """
    c = job.get('client') or {}
    if not c.get('verified'):
        return 'unverified payment'
    if str(job.get('engagement') or '').upper() == 'FULL_TIME':
        return 'full-time role, not a project'
    proposals = job.get('proposals')
    if (limits['proposals'] and isinstance(proposals, (int, float))
            and proposals > limits['proposals']):
        return f'{int(proposals)} proposals, over your cap of {limits["proposals"]:g}'
    rating, reviews = c.get('rating'), c.get('reviews')
    if rating is not None and rating < limits['min_rating'] and (reviews or 0) >= 3:
        return f'client rated {rating} by freelancers'
    top, hourly = budget_top(job)
    if top is not None:
        rate = limits['rate']
        if hourly and rate and top < limits['hourly_share'] * rate:
            return f'pays {top:g} against your rate of {rate:g}'
        if not hourly and top < limits['fixed_floor']:
            return f'fixed budget of {top:g} under your floor of {limits["fixed_floor"]:g}'
    return None


def lesson_points(job):
    """What the member's own outcomes have earned this job, capped and named.

    `learn.py lessons` measures the reply rate per bucket (the track that found it,
    the client's country, the job type) and emits a bucket only once eight
    applications stand behind it, so this cannot learn from a single bad week. It is
    capped at one point either way, which is enough to tilt a ranking and never
    enough to overturn a fit. The reasons come back with it, because a member has to
    be able to read why a lesson moved their list rather than trust that it did.
    """
    rows = load_json(LESSONS, {}).get('lessons') or []
    if not rows:
        return 0, []
    import learn
    mine = set(learn.dimensions(job))
    hits = [r for r in rows if (r.get('dimension'), r.get('value')) in mine and r.get('points')]
    if not hits:
        return 0, []
    total = max(-LESSON_CAP, min(LESSON_CAP, sum(int(r['points']) for r in hits)))
    reasons = [f'{r["value"]}: {r["replied"]} replies in {r["applied"]} applications' for r in hits]
    return total, reasons


def deductions(job, rate):
    """What shaves a fit score, with the reason for each. Never a bonus.

    The fit is the score. These are the facts a member would hold against a job
    they otherwise want, and they are worth points only because a run has to rank
    twenty jobs that all fit. Capped, so no pile of small doubts can outweigh what
    the job actually is.
    """
    out = []
    c = job.get('client') or {}
    if c.get('hires') == 0 and (c.get('posted_jobs') or 0) >= 2:
        out.append((1, 'has posted before and never hired'))
    elif not c.get('rating') and not c.get('spent'):
        out.append((1, 'no client history at all'))
    top, hourly = budget_top(job)
    if top is None:
        out.append((1, 'no budget stated'))
    elif hourly and rate and top < rate:
        out.append((2, f'tops out under your rate ({top:g} against {rate:g})'))
    elif not hourly and top < 500:
        out.append((1, f'small fixed budget ({top:g})'))
    total = min(MAX_DEDUCTION, sum(points for points, _ in out))
    # Every one of these doubts describes the market a member without reviews actually
    # wins: a new client with no history, no budget written down, a dozen applicants.
    # Stacked at full weight they put the gate out of reach on day one, so while the
    # evidence sections are empty they can cost at most one point between them.
    if not has_evidence():
        total = min(total, BEGINNER_DEDUCTION)
    return total, [reason for _, reason in out]


def has_evidence():
    """True when the member has anything in the evidence sections of their own file."""
    if not ME.is_file():
        return False
    try:
        import context_check  # noqa: E402  (same folder, imported where it is used)
        proof = context_check.proof_only(ME.read_text(encoding='utf-8'))
    except Exception:
        return False
    lines = [l.strip() for l in proof.splitlines()
             if l.strip() and not l.startswith('#') and 'othing recorded yet' not in l]
    return bool(lines)


def cmd_candidates(args):
    limits = member_limits()
    rate = limits['rate']
    merged, dropped = {}, collections.Counter()
    for f in args.files:
        track = pathlib.Path(f).stem
        for job in load_json(f, {}).get('jobs', []):
            n = normalize(job, track)
            if n['id'] in merged:
                merged[n['id']]['found_via'].append(track)
                continue
            if n['applied']:
                dropped['already applied'] += 1
                continue
            rec = recency_points(n['posted_date'], args.window_hours)
            if rec is None:
                dropped['outside window'] += 1
                continue
            no = disqualified(n, limits)
            if no:
                dropped[drop_kind(no, limits)] += 1
                continue
            shaved, reasons = deductions(n, rate)
            n.update(recency=rec, deduction=shaved, deduction_reasons=reasons)
            merged[n['id']] = n
    known = set()
    if merged:
        out = pipeline('add', '--check', *merged)
        known = {line.split()[-1] for line in out.stdout.splitlines() if line.startswith('KNOWN')}
    fresh = [j for j in merged.values() if j['id'] not in known]
    DATA.mkdir(exist_ok=True)
    CANDIDATES.write_text(json.dumps(fresh, indent=2, ensure_ascii=False), encoding='utf-8')
    for j in sorted(fresh, key=lambda j: j['recency'], reverse=True):
        c = j['client']
        print(f'{j["id"]}  {j["title"][:70]}')
        print(f'    via {",".join(j["found_via"])} · {j["budget"] or "no budget"} · {j["engagement"] or ""} · '
              f'proposals {j["proposals"]} · client {c["rating"] or "unrated"}, '
              f'${c["spent"] or 0:,.0f} spent · {j["recency"]}/10 fresh')
        shaved = f'-{j["deduction"]} ({"; ".join(j["deduction_reasons"])})' if j['deduction'] else 'nothing against it'
        print(f'    deduction {shaved}')
        print(f'    {"(preview only) " if j.get("preview_only") else ""}{j["snippet"][:220]}')
    for off in limits['missing']:
        print(f'LIMIT OFF: {off}')
    for default in limits['defaults']:
        print(f'DEFAULT LIMIT: {default}')
    gone = ', '.join(f'{v} {k}' for k, v in dropped.most_common()) or 'none'
    print(f'\n{len(fresh)} new candidate(s), {len(known)} already in the pipeline, dropped: {gone}.')
    previews = sum(1 for j in fresh if j.get('preview_only'))
    if previews:
        print(f'{previews} candidate(s) came without the full posting: judged on the preview only.')
    print(f'Next: judge fit 0 to 10 for each and write data/fit.json, then run score. '
          f'The score is that fit minus the deduction above; the gate is {MIN_SCORE}.')
    return 0


# --- score ------------------------------------------------------------------

def grade(total):
    """Kept so older records still render: the score has been the member's number since
    the scale became 0 to 10, and there is nothing left to translate."""
    return total


def record_rejections(ranked, kept, minimum):
    """Write one line per candidate the gate turned down, with the numbers behind it.

    The member never sees this step and never types anything for it. It is the half
    of the record that costs nothing: thirty labelled no's per run against the two or
    three yes's that reach the pipeline.
    """
    kept_ids = {record['id'] for record in kept}
    today = datetime.date.today().isoformat()
    lines = []
    for total, niche, candidate, verdict in ranked:
        if candidate['id'] in kept_ids:
            continue
        lines.append(json.dumps({
            'at': today,
            'id': candidate['id'],
            'title': candidate.get('title', ''),
            'found_via': candidate.get('found_via', ''),
            'decision': 'gate',
            'failed': 'fit' if niche < FIT_GATE else 'score',
            'score': total,
            'grade': grade(total),
            'niche_fit': niche,
            'deduction': candidate.get('deduction') or 0,
            'deduction_reasons': candidate.get('deduction_reasons') or [],
            'recency': candidate['recency'],
            'reason': (verdict.get('trap') or verdict.get('rationale', ''))[:300],
        }, ensure_ascii=False))
    if not lines:
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    with DECISIONS.open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return len(lines)


def cmd_score(args):
    candidates = load_json(CANDIDATES, [])
    fit = load_json(FIT, {})
    missing = [c['id'] for c in candidates if c['id'] not in fit]
    if missing:
        print(f'ABORT: no niche fit in data/fit.json for {len(missing)} candidate(s): {", ".join(missing[:5])}',
              file=sys.stderr)
        return 1
    ranked, logged = [], []
    for c in candidates:
        f = fit[c['id']]
        niche = max(0, min(10, int(f.get('fit', 0))))
        lesson, lesson_why = lesson_points(c)
        total = max(0, min(10, niche - int(c.get('deduction') or 0) + lesson))
        # A named trap caps the score: a great client must not lift a disguised
        # full-time or operator role above a real build.
        if f.get('trap'):
            total = min(total, TRAP_CAP)
        ranked.append((total, niche, c, f))
        if niche >= FIT_GATE and total >= args.min:
            record = {k: c[k] for k in ('id', 'title', 'url', 'posted_date', 'found_via', 'budget',
                                         'job_type', 'engagement', 'skills', 'proposals', 'client')}
            record.update(score=total, grade=grade(total), niche_fit=niche, recency=c['recency'],
                          deduction=c.get('deduction') or 0,
                          deduction_reasons=c.get('deduction_reasons') or [],
                          lesson=lesson, lesson_reasons=lesson_why,
                          rationale=f.get('rationale', ''), summary=f.get('summary', c['snippet'][:280]),
                          headline=f.get('headline', ''), trap=f.get('trap'))
            logged.append(record)
    if logged:
        out = pipeline('add', '--file', '-', stdin=json.dumps(logged))
        if out.returncode:
            print(out.stderr, file=sys.stderr)
            return 1
    for total, niche, c, f in sorted(ranked, key=lambda r: r[0], reverse=True):
        mark = 'LOGGED' if any(r['id'] == c['id'] for r in logged) else 'skip  '
        why = f.get('trap') or f.get('rationale', '')
        print(f'{mark} {total:2d}/10 (fit {niche}, minus {c.get("deduction") or 0})  {c["title"][:60]}  · {why[:90]}')
    turned_down = record_rejections(ranked, logged, args.min)
    print(f'\n{len(logged)} of {len(ranked)} logged (fit at least {FIT_GATE} and score at least {args.min}).')
    if turned_down:
        print(f'{turned_down} rejection(s) recorded in {DECISIONS.name}: what the gate says no to, '
              f'and why. `python3 code/learn.py report` reads them.')
    return 0


def cmd_reassess(args):
    """Apply one fit decision rewritten after reading the full posting."""
    fit = load_json(FIT, {}).get(args.job_id)
    job = next((j for j in load_json(jobs_file(), []) if str(j.get('id')) == args.job_id), None)
    if not isinstance(fit, dict) or not job:
        print(f'ABORT: job {args.job_id} needs both a pipeline record and data/fit.json entry.', file=sys.stderr)
        return 1
    try:
        niche = max(0, min(10, int(fit.get('fit'))))
    except (TypeError, ValueError):
        print(f'ABORT: job {args.job_id} needs an integer fit from 0 to 10.', file=sys.stderr)
        return 1
    lesson, _ = lesson_points(job)
    total = max(0, min(10, niche - int(job.get('deduction') or 0) + lesson))
    if fit.get('trap'):
        total = min(total, TRAP_CAP)
    assessment = {
        'niche_fit': niche,
        'score': max(0, min(100, total)),
        'rationale': fit.get('rationale') or '',
        'summary': fit.get('summary') or job.get('summary') or '',
        'headline': fit.get('headline') or job.get('headline') or '',
        'trap': fit.get('trap') or '',
    }
    out = pipeline('assess', args.job_id, '--file', '-', stdin=json.dumps(assessment))
    if out.returncode:
        print(out.stderr, file=sys.stderr)
        return 1
    print(out.stdout.strip())
    if niche < FIT_GATE or total < MIN_SCORE:
        # The same prefix the member writes by hand. query_performance counts a
        # reason only when it carries it, so an automatic skip without the prefix
        # is a lead removed and a lesson lost.
        reason = fit.get('trap') or 'full posting does not meet the search gate'
        moved = pipeline('set', args.job_id, 'skipped', '--note', f'not a fit: {reason}')
        if moved.returncode:
            print(moved.stderr, file=sys.stderr)
            return 1
        print(moved.stdout.strip())
    return 0


# --- detail -----------------------------------------------------------------

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            hit = find_key(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_key(v, key)
            if hit is not None:
                return hit
    return None


def member_standing():
    """Your numbers the client's minimums are compared against."""
    profile = load_json(DATA / 'profile.json', {})
    agg = profile.get('profileAggregates') or profile.get('data', {}).get('profileAggregates') or {}
    me = (ROOT / 'context' / 'me.md')
    jss = None
    if me.is_file():
        m = re.search(r'Job Success Score:\*\*\s*(\d+)', me.read_text(encoding='utf-8'))
        jss = int(m.group(1)) if m else None
    return {'earnings': money_value(agg.get('totalEarnings')), 'jss': jss}


def clean_brief(raw):
    brief = find_key(raw, 'brief')
    if not isinstance(brief, dict):
        return None
    outcome = clean(brief.get('outcome')) if isinstance(brief.get('outcome'), str) else ''
    scope = [clean(item) for item in (brief.get('scope') if isinstance(brief.get('scope'), list) else []) if isinstance(item, str) and clean(item)]
    requirements = [clean(item) for item in (brief.get('requirements') if isinstance(brief.get('requirements'), list) else [])
                    if isinstance(item, str) and clean(item)]
    return {k: v for k, v in {'outcome': outcome, 'scope': scope, 'requirements': requirements}.items() if v}


def cmd_detail(args):
    raw = load_json(args.file, {})
    activity = find_key(raw, 'jobActivity') or {}
    bids = find_key(raw, 'applicationsBidStats') or {}
    quals = find_key(raw, 'preferred_qualifications') or {}
    terms = find_key(raw, 'contractTerms') or {}
    company = find_key(raw, 'clientCompanyPublic') or {}
    timezone = find_key(company, 'timezone')
    details = {
        'experience_level': find_key(terms, 'experienceLevel'),
        'engagement_type': find_key(terms, 'engagementType'),
        'client_city': find_key(company, 'city'),
        'client_timezone': timezone if isinstance(timezone, str) else None,
        'connects_cost': find_key(raw, 'connects_cost'),
        'can_apply': find_key(raw, 'can_apply'),
        'total_hired': activity.get('totalHired'),
        'invites_sent': activity.get('invitesSent'),
        'interviewing': activity.get('totalInvitedToInterview'),
        'offers': activity.get('totalOffered'),
        'bid_avg': money_value(bids.get('avgRateBid')), 'bid_min': money_value(bids.get('minRateBid')),
        'bid_max': money_value(bids.get('maxRateBid')),
        'min_jss': quals.get('min_job_success_score'), 'min_earnings': quals.get('min_earnings'),
        'client_record': find_key(raw, 'client_record'),
        'description': clean(find_key(raw, 'description') if isinstance(find_key(raw, 'description'), str) else ''),
        'brief': clean_brief(raw),
    }
    details = {k: v for k, v in details.items() if v not in (None, '', {})}
    out = pipeline('detail', args.job_id, '--file', '-', stdin=json.dumps(details))
    if out.returncode:
        print(out.stderr, file=sys.stderr)
        return 1
    current = next((job for job in load_json(jobs_file(), []) if str(job.get('id')) == args.job_id), {})
    if details.get('can_apply') is False and current.get('status') == 'new':
        pipeline('set', args.job_id, 'skipped', '--note', 'Upwork says you cannot apply')
        print(f'{args.job_id}: skipped, Upwork says you cannot apply')
        return 0
    # A posting can hire more than one person. Preferred qualifications are
    # signals for a human decision, not proof that an application is forbidden.
    reasons = []
    if (details.get('total_hired') or 0) >= 1:
        reasons.append(f'{details["total_hired"]} already hired; check whether more people are needed')
    me = member_standing()
    if details.get('min_jss') and me['jss'] is not None and details['min_jss'] > me['jss']:
        reasons.append(f'wants Job Success {details["min_jss"]}, you have {me["jss"]}')
    need = money_value(details.get('min_earnings'))
    if need and me['earnings'] is not None and need > me['earnings']:
        reasons.append(f'wants {details["min_earnings"]} earned, you have ${me["earnings"]:,.0f}+')
    if reasons:
        print(f'{args.job_id}: advisory, {"; ".join(reasons)}')
    print(f'{args.job_id}: details saved. {details.get("connects_cost", "?")} Connects to apply, '
          f'{details.get("invites_sent", 0)} invites, {details.get("interviewing", 0)} interviewing, '
          f'bids average {details.get("bid_avg", "?")}.')
    return 0


# --- lessons ----------------------------------------------------------------

def cmd_lessons(args):
    """Your own past decisions: the anchors Claude scores new jobs against."""
    jobs = load_json(jobs_file(), [])
    decided = [j for j in jobs if j.get('status') != 'new']
    decided.sort(key=lambda j: j.get('status_updated_at') or '', reverse=True)
    if not decided:
        print('No decisions yet. Every job you apply to or skip becomes an anchor here.')
        return 0
    for j in decided[:args.limit]:
        note = f' · {j["notes"]}' if j.get('notes') else ''
        print(f'{j.get("status"):<8} scored {j.get("score", "?"):>3}  {j.get("title", "")[:70]}{note}')
    return 0


RUNS = DATA / 'runs.jsonl'


def log_run(calls):
    """One line per run: when, how many Upwork calls, how many minutes since `window`.

    Upwork names no safe pattern, only that polling which resembles scraping is punished,
    so the record of runs that passed is the only measure of what a member can safely do.
    Counts only, never Upwork content, so prune leaves it alone.
    """
    start = parse_time(load_json(RUN_START, {}).get('at'))
    minutes = round((now() - start).total_seconds() / 60, 1) if start else None
    if RUN_START.is_file():
        RUN_START.unlink()
    with RUNS.open('a', encoding='utf-8') as out:
        out.write(json.dumps({'at': now().isoformat(), 'calls': calls, 'minutes': minutes}) + '\n')
    return minutes


def cmd_clean(args):
    """Deletes this run's raw responses. Only our own scores and records stay."""
    import shutil
    if args.calls is not None:
        minutes = log_run(args.calls)
        print(f'Run logged: {args.calls} Upwork calls' + (f' over about {minutes} minutes.' if minutes is not None else '.'))
    gone = 0
    for name in ('search', 'details'):
        folder = DATA / name
        if folder.is_dir():
            gone += sum(1 for _ in folder.glob('*.json'))
            shutil.rmtree(folder)
    for f in (CANDIDATES, FIT):
        if f.is_file():
            f.unlink()
            gone += 1
    record_search()
    print(f'{gone} raw file(s) from this run removed. Search time stamped, so the next '
          f'run looks back only as far as this one.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('clean')
    p.add_argument('--calls', type=int, help='Upwork calls this run made, logged to data/runs.jsonl')
    p.set_defaults(func=cmd_clean)
    p = sub.add_parser('window')
    p.set_defaults(func=cmd_window)
    p = sub.add_parser('pause')
    p.add_argument('seconds', nargs='?', type=float, default=5)
    p.set_defaults(func=cmd_pause)
    p = sub.add_parser('rules')
    p.set_defaults(func=cmd_rules)
    p = sub.add_parser('candidates')
    p.add_argument('files', nargs='+')
    p.add_argument('--window-hours', type=float, default=MIN_WINDOW)
    p.set_defaults(func=cmd_candidates)
    p = sub.add_parser('score')
    p.add_argument('--min', type=int, default=MIN_SCORE)
    p.set_defaults(func=cmd_score)
    p = sub.add_parser('reassess')
    p.add_argument('job_id')
    p.set_defaults(func=cmd_reassess)
    p = sub.add_parser('detail')
    p.add_argument('job_id')
    p.add_argument('file')
    p.set_defaults(func=cmd_detail)
    p = sub.add_parser('lessons')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=cmd_lessons)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
