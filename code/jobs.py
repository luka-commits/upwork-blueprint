#!/usr/bin/env python3
"""The counting half of /find-jobs. The judging half (does this job fit you?) is Claude's.

    python3 code/jobs.py window                                   # hours to search back
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
PIPELINE = ROOT / 'code' / 'pipeline.py'
TAG = re.compile(r'</?untrusted_participant_content>')
MIN_WINDOW, MAX_WINDOW = 10, 72
FIT_GATE = 20
TRAP_CAP = 60


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


def member_rate():
    """Your hourly rate, from the profile /audit saved. 30 when there is none yet."""
    profile = load_json(DATA / 'profile.json', {})
    personal = profile.get('data', {}).get('personalData', {})
    return money_value((personal.get('chargeRate') or {}).get('rawValue')) or 30.0


# --- window -----------------------------------------------------------------

def cmd_window(args):
    """Hours since the newest job in the pipeline, between 10 and 72.

    Ten hours is the floor because a job older than that already has a day of
    proposals on it. The window stretches to cover the gap since the last run, so
    skipping a weekend never leaves a hole nobody sees.
    """
    raw = load_json(jobs_file(), [])
    stamps = [parse_time(j.get('found_at')) for j in raw if j.get('found_at')]
    stamps = [s for s in stamps if s]
    # A first run has no last run to measure from: look back one day.
    hours = 24 if not stamps else (now() - max(stamps)).total_seconds() / 3600
    print(int(max(MIN_WINDOW, min(MAX_WINDOW, round(hours + 0.5)))))
    return 0


# --- candidates -------------------------------------------------------------

def normalize(job, track):
    c = job.get('client') or {}
    proposals = job.get('proposal_count')
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
        'snippet': clean(job.get('description_snippet'))[:400],
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


def trust_points(c):
    pts = 5 if c.get('verified') else 0
    r = c.get('rating')
    pts += 5 if r is None else 10 if r >= 4.8 else 7 if r >= 4.5 else 4 if r >= 4.0 else 0
    s = c.get('spent')
    pts += 2 if not s else 10 if s >= 10_000 else 7 if s >= 1_000 else 4
    hires, posted = c.get('hires'), c.get('posted_jobs')
    if hires is not None and posted:
        ratio = hires / posted
        pts += 5 if ratio >= 0.5 else 3 if ratio >= 0.2 else 0
    else:
        pts += 2
    return pts


def deal_points(job, rate):
    budget = str(job.get('budget') or '')
    values = numbers(budget)
    if '/hr' in budget or (job.get('job_type') == 'hourly' and values):
        top = max(values) if values else None
        base = 6 if top is None else 14 if top >= rate else 9 if top >= 0.6 * rate else 3
    elif values:
        top = max(values)
        base = 14 if top >= 1000 else 10 if top >= 300 else 5 if top >= 100 else 1
    else:
        base = 6
    if values:
        base += 3
    # Ongoing work is worth more than a one-off. "Less than 1 month" is not ongoing.
    if re.search(r'(1 to 3|3 to 6|more than 6) months', str(job.get('duration') or ''), re.I):
        base += 3
    if str(job.get('engagement') or '').upper() == 'FULL_TIME':
        base -= 8
    return max(0, min(20, base))


def cmd_candidates(args):
    rate = member_rate()
    merged, dropped = {}, {'applied': 0, 'outside window': 0, 'unverified payment': 0}
    for f in args.files:
        track = pathlib.Path(f).stem
        for job in load_json(f, {}).get('jobs', []):
            n = normalize(job, track)
            if n['id'] in merged:
                merged[n['id']]['found_via'].append(track)
                continue
            if n['applied']:
                dropped['applied'] += 1
                continue
            if not n['client']['verified']:
                dropped['unverified payment'] += 1
                continue
            rec = recency_points(n['posted_date'], args.window_hours)
            if rec is None:
                dropped['outside window'] += 1
                continue
            n.update(recency=rec, client_trust=trust_points(n['client']), deal_quality=deal_points(n, rate))
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
              f'${c["spent"] or 0:,.0f} spent · points trust {j["client_trust"]}, '
              f'deal {j["deal_quality"]}, recency {j["recency"]}')
        print(f'    {j["snippet"][:220]}')
    gone = ', '.join(f'{v} {k}' for k, v in dropped.items() if v) or 'none'
    print(f'\n{len(fresh)} new candidate(s), {len(known)} already in the pipeline, dropped: {gone}.')
    print('Next: judge niche fit 0 to 40 for each and write data/fit.json, then run score.')
    return 0


# --- score ------------------------------------------------------------------

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
        niche = max(0, min(40, int(f.get('fit', 0))))
        total = niche + c['client_trust'] + c['deal_quality'] + c['recency']
        # A named trap caps the score: a great client must not lift a disguised
        # full-time or operator role above a real build.
        if f.get('trap'):
            total = min(total, TRAP_CAP)
        ranked.append((total, niche, c, f))
        if niche >= FIT_GATE and total >= args.min:
            record = {k: c[k] for k in ('id', 'title', 'url', 'posted_date', 'found_via', 'budget',
                                         'job_type', 'engagement', 'skills', 'proposals', 'client')}
            record.update(score=total, niche_fit=niche, client_trust=c['client_trust'],
                          deal_quality=c['deal_quality'], recency=c['recency'],
                          rationale=f.get('rationale', ''), summary=f.get('summary', c['snippet'][:280]),
                          trap=f.get('trap'))
            logged.append(record)
    if logged:
        out = pipeline('add', '--file', '-', stdin=json.dumps(logged))
        if out.returncode:
            print(out.stderr, file=sys.stderr)
            return 1
    for total, niche, c, f in sorted(ranked, key=lambda r: r[0], reverse=True):
        mark = 'LOGGED' if any(r['id'] == c['id'] for r in logged) else 'skip  '
        why = f.get('trap') or f.get('rationale', '')
        print(f'{mark} {total:3d} (fit {niche:2d})  {c["title"][:60]}  · {why[:90]}')
    print(f'\n{len(logged)} of {len(ranked)} logged (fit at least {FIT_GATE} and score at least {args.min}).')
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


def cmd_clean(args):
    """Deletes this run's raw responses. Only our own scores and records stay."""
    import shutil
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
    print(f'{gone} raw file(s) from this run removed.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('clean')
    p.set_defaults(func=cmd_clean)
    p = sub.add_parser('window')
    p.set_defaults(func=cmd_window)
    p = sub.add_parser('candidates')
    p.add_argument('files', nargs='+')
    p.add_argument('--window-hours', type=float, default=MIN_WINDOW)
    p.set_defaults(func=cmd_candidates)
    p = sub.add_parser('score')
    p.add_argument('--min', type=int, default=50)
    p.set_defaults(func=cmd_score)
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
