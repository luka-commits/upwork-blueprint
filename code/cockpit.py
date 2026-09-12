#!/usr/bin/env python3
"""The cockpit: your jobs, your pipeline and buttons that run the commands, in the browser.

    python3 code/cockpit.py [--port 4321] [--no-open]

Runs on this computer only (127.0.0.1) and never on the internet: a page that
can start Claude with your Upwork connector must not be reachable by anyone
else. Every status change goes through code/pipeline.py, the one writer, and
every button that needs Claude starts the same command you could type, with
only the tools that command needs. Nothing here sends anything to a client.
"""
import argparse
import datetime
import http.server
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_path)

PAGE = ROOT / 'code' / 'cockpit.html'
COMMANDS_DIR = ROOT / '.claude' / 'commands'
JOBS_DIR = pipeline.jobs_dir()
TOKEN = secrets.token_urlsafe(24)
ID = re.compile(r'^[0-9]{6,25}$')

UPWORK_READ = ['mcp__upwork__upwork__list_accounts', 'mcp__upwork__upwork__find_jobs',
               'mcp__upwork__upwork__get_profile']
FILES = ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'Bash(python3 code/*)']

# What a button may start. A command runs only when its file exists, and only
# with the tools listed here. No entry grants a tool that writes to Upwork: a
# send always happens in a session where the member reads the draft first.
RUNNABLE = {
    'find-jobs': {'prompt': '/find-jobs', 'tools': FILES + UPWORK_READ + ['WebSearch'], 'job': False},
    'pitch-page': {'prompt': '/pitch-page {job}', 'tools': FILES + UPWORK_READ + ['WebSearch', 'WebFetch'],
                   'job': True},
    # The draft run makes the proposal preview (Connects price, boost bids) and
    # stops. It never gets confirm_preview, so it cannot submit anything.
    'apply': {'prompt': '/apply {job} --draft-only', 'job': True,
              'tools': FILES + UPWORK_READ + ['mcp__upwork__upwork__list_freelancer_proposals',
                                              'mcp__upwork__upwork__manage_proposals']},
}

RUNS = {}
RUNS_LOCK = threading.Lock()


def available(name):
    return name in RUNNABLE and (COMMANDS_DIR / f'{name}.md').is_file()


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
    return sorted(p.name for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith('.') and p.name != 'thread.json')


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
    thread = folder / 'thread.json'
    try:
        j['thread'] = json.loads(thread.read_text(encoding='utf-8')) if thread.is_file() else None
    except (OSError, json.JSONDecodeError):
        j['thread'] = None
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
           and j.get('status') not in pipeline.CLOSED]
    goal = daily_target()
    return {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'jobs': [card(j) for j in jobs],
        'today': {'applied': pipeline.applied_on(jobs, today), 'target': goal, 'follow_ups_due': due},
        'tracker': tracker(jobs, goal, day),
        'insights': insights(jobs, day),
        'me': standing(),
        'commands': {name: available(name) for name in RUNNABLE},
        'statuses': list(pipeline.STATUSES),
    }


def claude_binary():
    found = shutil.which('claude')
    if found:
        return found
    fallback = pathlib.Path.home() / '.local' / 'bin' / 'claude'
    return str(fallback) if fallback.exists() else None


def parse_event(line):
    """One line of `claude --output-format stream-json`, reduced to what the panel shows."""
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return {'kind': 'text', 'text': line}
    if ev.get('type') == 'assistant':
        out = []
        for part in (ev.get('message') or {}).get('content') or []:
            if part.get('type') == 'text' and part.get('text', '').strip():
                out.append({'kind': 'text', 'text': part['text']})
            elif part.get('type') == 'thinking':
                out.append({'kind': 'status', 'text': 'thinking'})
            elif part.get('type') == 'tool_use':
                given = part.get('input') or {}
                detail = given.get('command') or given.get('file_path') or given.get('query') or given.get('action') or ''
                out.append({'kind': 'tool', 'text': part.get('name', 'tool'), 'detail': str(detail)[:120]})
        return out
    if ev.get('type') == 'result':
        return {'kind': 'done', 'text': ev.get('result') or '', 'error': bool(ev.get('is_error'))}
    return None


def start_run(name, job_id=None):
    spec = RUNNABLE[name]
    binary = claude_binary()
    if not binary:
        raise RuntimeError('Claude Code is not installed or not on the PATH.')
    prompt = spec['prompt'].format(job=job_id or '').strip()
    args = [binary, '-p', prompt, '--output-format', 'stream-json', '--verbose',
            '--permission-mode', 'acceptEdits', '--allowedTools', *spec['tools']]
    child = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    run_id = secrets.token_hex(6)
    run = {'id': run_id, 'command': name, 'job': job_id, 'events': [], 'done': False,
           'started': time.time()}

    def pump():
        for line in child.stdout:
            parsed = parse_event(line.strip())
            for ev in parsed if isinstance(parsed, list) else ([parsed] if parsed else []):
                run['events'].append(ev)
        err = child.stderr.read().strip()
        code = child.wait()
        if code and err:
            run['events'].append({'kind': 'error', 'text': err[-2000:]})
        if not any(e['kind'] == 'done' for e in run['events']):
            run['events'].append({'kind': 'done', 'text': f'Finished with exit code {code}.', 'error': code != 0})
        run['done'] = True

    threading.Thread(target=pump, daemon=True).start()
    with RUNS_LOCK:
        RUNS[run_id] = run
    return run_id


def run_pipeline(*args):
    r = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), *args],
                       capture_output=True, text=True, cwd=ROOT)
    return r.returncode == 0, (r.stdout or r.stderr).strip().removeprefix('ABORT: ')


def set_status(job_id, status, note=None, follow_up=None):
    args = ['set', job_id, status]
    if note:
        args += ['--note', note]
    if follow_up:
        args += ['--follow-up', follow_up]
    return run_pipeline(*args)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'Cockpit/1'

    def log_message(self, fmt, *args):
        pass

    def local_only(self):
        host = (self.headers.get('Host') or '').split(':')[0]
        return host in ('127.0.0.1', 'localhost')

    def send_json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return self.local_only() and secrets.compare_digest(self.headers.get('X-Cockpit-Token') or '', TOKEN)

    def do_GET(self):
        if not self.local_only():
            return self.send_json({'error': 'local only'}, 403)
        path = urllib.parse.urlparse(self.path).path
        if path == '/':
            html = PAGE.read_text(encoding='utf-8').replace('__COCKPIT_TOKEN__', TOKEN)
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if not self.authorized() and not path.startswith('/jobs/'):
            return self.send_json({'error': 'missing token'}, 403)
        if path == '/api/state':
            return self.send_json(build_state())
        if path == '/api/runs':
            with RUNS_LOCK:
                active = [{k: r[k] for k in ('id', 'command', 'job', 'started')} for r in RUNS.values() if not r['done']]
            return self.send_json(active)
        m = re.match(r'^/api/job/([0-9]+)$', path)
        if m:
            job = job_view(m.group(1))
            return self.send_json(job or {'error': 'not found'}, 200 if job else 404)
        m = re.match(r'^/api/run/([0-9a-f]+)$', path)
        if m:
            return self.stream_run(m.group(1))
        m = re.match(r'^/jobs/([0-9]+)/([\w.\-]+)$', path)
        if m and ID.match(m.group(1)):
            target = (JOBS_DIR / m.group(1) / m.group(2)).resolve()
            if JOBS_DIR.resolve() in target.parents and target.is_file():
                body = target.read_bytes()
                kind = {'.html': 'text/html', '.pdf': 'application/pdf', '.md': 'text/plain',
                        '.png': 'image/png'}.get(target.suffix, 'application/octet-stream')
                self.send_response(200)
                self.send_header('Content-Type', f'{kind}; charset=utf-8' if kind.startswith('text') else kind)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
        return self.send_json({'error': 'not found'}, 404)

    def stream_run(self, run_id):
        run = RUNS.get(run_id)
        if not run:
            return self.send_json({'error': 'no such run'}, 404)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        sent = 0
        try:
            while True:
                events = run['events']
                while sent < len(events):
                    self.wfile.write(f'data: {json.dumps(events[sent], ensure_ascii=False)}\n\n'.encode('utf-8'))
                    sent += 1
                self.wfile.flush()
                if run['done'] and sent >= len(run['events']):
                    break
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.authorized():
            return self.send_json({'error': 'missing token'}, 403)
        length = int(self.headers.get('Content-Length') or 0)
        try:
            data = json.loads(self.rfile.read(length) or b'{}')
        except json.JSONDecodeError:
            return self.send_json({'error': 'bad json'}, 400)
        path = urllib.parse.urlparse(self.path).path
        job_id = str(data.get('id') or data.get('job') or '')
        if path == '/api/status':
            if not ID.match(job_id) or data.get('status') not in pipeline.STATUSES:
                return self.send_json({'error': 'bad job or status'}, 400)
            ok, message = set_status(job_id, data['status'], data.get('note'), data.get('follow_up'))
            return self.send_json({'ok': ok, 'message': message}, 200 if ok else 400)
        if path in ('/api/note', '/api/video'):
            value = str(data.get('text') if path == '/api/note' else data.get('url') or '')
            if not ID.match(job_id) or not value.strip():
                return self.send_json({'error': 'bad job or empty value'}, 400)
            ok, message = run_pipeline(path.rsplit('/', 1)[1], job_id, value)
            return self.send_json({'ok': ok, 'message': message}, 200 if ok else 400)
        if path == '/api/task':
            action, value = data.get('action'), str(data.get('text') or data.get('task') or '').strip()
            if not ID.match(job_id) or action not in ('add', 'done', 'reopen', 'delete') or not value:
                return self.send_json({'error': 'bad job, action or empty task'}, 400)
            args = ['task', job_id, action, value] + (['--due', str(data['due'])] if data.get('due') else [])
            ok, message = run_pipeline(*args)
            return self.send_json({'ok': ok, 'message': message}, 200 if ok else 400)
        if path == '/api/run':
            name = data.get('command')
            if not available(name):
                return self.send_json({'error': f'/{name} is not built yet'}, 400)
            if RUNNABLE[name]['job'] and not ID.match(job_id):
                return self.send_json({'error': 'this command needs a job'}, 400)
            try:
                run_id = start_run(name, job_id if RUNNABLE[name]['job'] else None)
            except RuntimeError as e:
                return self.send_json({'error': str(e)}, 500)
            return self.send_json({'run': run_id})
        return self.send_json({'error': 'not found'}, 404)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=4321)
    ap.add_argument('--no-open', action='store_true')
    args = ap.parse_args(argv)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Cockpit running at {url}  (Ctrl+C stops it)')
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
