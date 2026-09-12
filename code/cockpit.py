#!/usr/bin/env python3
"""The cockpit: your jobs, your pipeline and buttons that run the commands, in the browser.

    python3 code/cockpit.py [--port 4321] [--no-open]   start it (installs and builds on first run)
    python3 code/cockpit.py state                         the list data as JSON
    python3 code/cockpit.py job <id>                      one job in full as JSON

The page itself is a small Next.js app in cockpit/. This script starts it, and it
is also where the app reads its data from, so the numbers the page shows come from
the same tested Python as everything else. The app runs on this computer only
(127.0.0.1): a page that can start Claude with your Upwork connector must not be
reachable by anyone else. Every status change goes through code/pipeline.py.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)

APP = ROOT / 'cockpit'
JOBS_DIR = pipeline.jobs_dir()


def daily_target():
    me = ROOT / 'context' / 'me.md'
    if me.is_file():
        m = re.search(r'Applications per day:\*\*\s*(\d+)', me.read_text(encoding='utf-8'))
        if m:
            return int(m.group(1))
    return None


def artifacts(job_id):
    folder = JOBS_DIR / job_id
    if not folder.is_dir():
        return []
    internal = {'thread.json', 'replies.json', 'outbox.json'}
    return sorted(p.name for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith('.') and p.name not in internal)


def read_json(folder, name):
    file = folder / name
    try:
        return json.loads(file.read_text(encoding='utf-8')) if file.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def job_view(job_id):
    """One job for the full lead view: the record, its files with dates, the saved thread."""
    job = next((j for j in pipeline.load() if j.get('id') == job_id), None)
    if not job:
        return None
    j = dict(job)
    folder = JOBS_DIR / job_id
    j['files'] = [{'name': name, 'at': datetime.datetime.fromtimestamp(
        (folder / name).stat().st_mtime, datetime.timezone.utc).isoformat(timespec='seconds')}
        for name in artifacts(job_id)]
    j['thread'] = read_json(folder, 'thread.json')
    j['replies'] = read_json(folder, 'replies.json')
    j['outbox'] = read_json(folder, 'outbox.json')
    return j


def card(job):
    """A record as the list needs it: everything but the full posting."""
    j = {k: v for k, v in job.items() if k not in ('description',)}
    details = dict(job.get('details') or {})
    j['has_posting'] = bool(details.pop('description', None) or job.get('description'))
    j['details'] = details
    j['artifacts'] = artifacts(job.get('id', ''))
    return j


# --- tracker and insights, carried over from the day dashboard's Upwork tab ------

# How far a job got. A lost job was often applied to and talked to first, so the
# highest stage it ever reached comes from its history, not its current status.
# Counting only current statuses would drop every lost job and flatter each rate.
RANK = {'new': 0, 'applied': 1, 'replied': 2, 'offer': 3, 'won': 4}


def parse_day(stamp):
    try:
        return datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).date()
    except ValueError:
        return None


def applied_dates(jobs):
    """Every day an application went out, from the history (applied_at as fallback)."""
    out = []
    for j in jobs:
        stamps = [h.get('at') for h in j.get('history', []) if h.get('status') == 'applied']
        if not stamps and j.get('applied_at'):
            stamps = [j['applied_at']]
        out += [d for d in (parse_day(s) for s in stamps) if d]
    return out


def streak(counts, goal, today, weekdays_only=True):
    """Days in a row the target was met. Today never breaks it: zero at 9 am is normal."""
    run, day = 0, today
    if counts.get(day, 0) < goal:
        day -= datetime.timedelta(days=1)
    for _ in range(3660):
        if weekdays_only and day.weekday() >= 5:
            day -= datetime.timedelta(days=1)
            continue
        if counts.get(day, 0) < goal:
            break
        run += 1
        day -= datetime.timedelta(days=1)
    return run


def tracker(jobs, goal, today):
    """Target, progress, streak and this week's days, Monday to Sunday."""
    counts = {}
    for d in applied_dates(jobs):
        counts[d] = counts.get(d, 0) + 1
    week_start = today - datetime.timedelta(days=today.weekday())
    week = [{'day': (week_start + datetime.timedelta(days=i)).isoformat(),
             'count': counts.get(week_start + datetime.timedelta(days=i), 0),
             'future': week_start + datetime.timedelta(days=i) > today} for i in range(7)]
    return {'goal': goal, 'done': counts.get(today, 0), 'week': week,
            'week_done': sum(d['count'] for d in week),
            'streak': streak(counts, goal, today) if goal else 0}


def reached(job):
    ranks = [RANK[h['status']] for h in job.get('history', []) if h.get('status') in RANK]
    if job.get('status') in RANK:
        ranks.append(RANK[job['status']])
    if not ranks and job.get('applied_at'):
        ranks.append(1)
    return max(ranks) if ranks else 0


def insights(jobs, today):
    """A real cohort funnel plus three numbers. A number without enough data says
    what unlocks it: a reply rate from two applications is worse than none."""
    stages = [('Found', 0), ('Applied', 1), ('Replied', 2), ('Offer', 3), ('Won', 4)]
    levels = [reached(j) for j in jobs if j.get('status') != 'skipped' or reached(j) >= 1]
    funnel = [{'stage': label, 'count': sum(1 for r in levels if r >= rank)} for label, rank in stages]
    applied = [j for j in jobs if reached(j) >= 1]
    replied = [j for j in jobs if reached(j) >= 2]
    spans = []
    for j in replied:
        h = {e['status']: e['at'] for e in j.get('history', []) if e.get('status') in ('applied', 'replied')}
        a, b = parse_day(h.get('applied')), parse_day(h.get('replied'))
        if a and b:
            spans.append((b - a).days)
    spans.sort()
    recent = [d for d in applied_dates(jobs) if (today - d).days < 28]
    skipped = [j for j in jobs if j.get('status') == 'skipped']
    return {
        'funnel': funnel,
        'reply_rate': round(100 * len(replied) / len(applied)) if len(applied) >= 5 else None,
        'reply_rate_hint': (f'{5 - len(applied)} more applications to go' if len(applied) < 5
                            else f'{len(replied)} of {len(applied)} replied'),
        'reply_days': spans[len(spans) // 2] if spans else None,
        'reply_days_hint': f'median of {len(spans)}' if spans else 'once a client replies',
        'per_week': round(len(recent) / 4, 1) if recent else None,
        'skipped': {'total': len(skipped),
                    'filled': sum(1 for j in skipped if 'already filled' in (j.get('notes') or '')),
                    'bar': sum(1 for j in skipped if 'wants ' in (j.get('notes') or '')),
                    'not_fit': sum(1 for j in skipped if 'not a fit' in (j.get('notes') or ''))},
    }


def standing():
    """Your numbers, the ones a client's minimums test against, from what /audit saved."""
    me_file = ROOT / 'context' / 'me.md'
    text = me_file.read_text(encoding='utf-8') if me_file.is_file() else ''
    jss = re.search(r'Job Success Score:\*\*\s*(\d+)', text)
    out = {'jss': int(jss.group(1)) if jss else None}
    try:
        profile = json.loads((ROOT / 'data' / 'profile.json').read_text(encoding='utf-8'))
        agg = profile.get('profileAggregates') or {}
        rate = (profile.get('data', {}).get('personalData', {}).get('chargeRate') or {}).get('displayValue')
        out.update(earned=agg.get('totalEarnings'), jobs=agg.get('totalJobs'),
                   reviews=agg.get('totalFeedback'), rate=rate)
    except (OSError, json.JSONDecodeError):
        pass
    return out


def build_state():
    jobs = pipeline.load()
    day = datetime.date.today()
    today = day.isoformat()
    due = [j['id'] for j in jobs if j.get('next_follow_up') and j['next_follow_up'] <= today
           and j.get('status') not in ('lost', 'skipped')]
    goal = daily_target()
    return {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'jobs': [card(j) for j in jobs],
        'today': {'applied': pipeline.applied_on(jobs, today), 'target': goal, 'follow_ups_due': due},
        'tracker': tracker(jobs, goal, day),
        'insights': insights(jobs, day),
        'me': standing(),
        'sync': last_sync(),
    }


def last_sync():
    """When /sync last brought the pipeline in line with Upwork, and what it found."""
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


def serve(port, open_browser):
    # An older cockpit still holding the port would answer for us with stale files
    # and a page stuck on "Loading.", so a busy port stops the start instead.
    if port_busy(port):
        print(f'Port {port} is taken, most likely by a cockpit that is still running. '
              f'Stop that one (Ctrl+C in its terminal) or start this one with --port {port + 1}.', file=sys.stderr)
        return 1
    if not (APP / 'node_modules').is_dir():
        print('First start: installing the cockpit (about a minute, only this once).')
        cmd, shell = npm('install', '--no-audit', '--no-fund')
        subprocess.run(cmd, cwd=APP, check=True, shell=shell)
    if needs_build():
        print('Building the cockpit (about a minute after each update).')
        cmd, shell = npm('run', 'build')
        subprocess.run(cmd, cwd=APP, check=True, shell=shell)
    cmd, shell = npm('run', 'start', '--', '-p', str(port))
    env = dict(os.environ, BLUEPRINT_ROOT=str(ROOT))
    child = subprocess.Popen(cmd, cwd=APP, env=env, shell=shell)
    url = f'http://127.0.0.1:{port}/'
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except OSError:
            if child.poll() is not None:
                return child.returncode
            time.sleep(0.5)
    print(f'Cockpit running at {url}  (Ctrl+C stops it)')
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
