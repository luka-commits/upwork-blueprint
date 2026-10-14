#!/usr/bin/env python3
"""Synthetic analytics proof. No Upwork, downloads, deploys, credentials or real data writes."""
import contextlib
import datetime as dt
import hashlib
import importlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODE = ROOT / 'code'
sys.path.insert(0, str(CODE))
ORIGINAL_RUN = subprocess.run
REAL_JOBS = ROOT / 'data' / 'jobs.json'
REAL_HASH = hashlib.sha256(REAL_JOBS.read_bytes()).hexdigest() if REAL_JOBS.exists() else None
REAL_DATA_HASHES = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (ROOT / 'data').rglob('*') if path.is_file()}
TODAY = dt.datetime.now(ZoneInfo('Europe/Berlin')).date()
BASE = dt.datetime.combine(TODAY - dt.timedelta(days=2), dt.time(12), dt.timezone.utc)


def stamp(seconds=0):
    return (BASE + dt.timedelta(seconds=seconds)).isoformat()


@contextlib.contextmanager
def fixture(label):
    with tempfile.TemporaryDirectory(prefix=f'blueprint-synthetic-{label}-') as temp:
        path = pathlib.Path(temp)
        env = dict(os.environ)
        for key in ('BLOB_READ_WRITE_TOKEN', 'WHISPER_MODEL'):
            env.pop(key, None)
        env.update(BLUEPRINT_CONTEXT=str(path / 'context'), BLUEPRINT_DATA=str(path / 'data'),
                   BLUEPRINT_JOBS=str(path / 'data' / 'jobs.json'), BLUEPRINT_JOBDIR=str(path / 'jobs'),
                   KEEP_CHAT_HOURS='24', TZ='Europe/Berlin')
        for name in ('context', 'data', 'jobs'):
            (path / name).mkdir()
        (path / 'context' / 'me.md').write_text('# SYNTHETIC analytics fixture\n', encoding='utf-8')
        with mock.patch.dict(os.environ, env, clear=True):
            time.tzset()
            yield path
    time.tzset()


def run(script, *args, value=None, env=None, success=True):
    result = ORIGINAL_RUN([sys.executable, str(CODE / script), *map(str, args)],
                          input=json.dumps(value) if value is not None else None,
                          text=True, capture_output=True, env=env)
    if success and result.returncode:
        raise AssertionError(f'{script} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}')
    return result


def seed(rows):
    run('pipeline.py', 'add', '--file', '-', value=rows)


def state():
    return json.loads(run('cockpit.py', 'state').stdout)


def records():
    import pipeline
    return {job['id']: job for job in pipeline.load()}


def record(jid, values):
    return run('pipeline.py', 'record', jid, '--file', '-', value=values)


def timing_core(timing):
    return {key: {'n': row['n'], 'median_s': row['median_s']} for key, row in timing.items()}


def assert_dashboard(s, counts, timing_n, medians, daily_counts, goal=5, profile=None):
    assert s['funnel'] == counts, s['funnel']
    assert timing_core(s['timings']) == {key: {'n': timing_n[key], 'median_s': medians[key]} for key in timing_n}, s['timings']
    days = s['consistency']['days']
    assert len(days) == 14
    expected_dates = [(TODAY - dt.timedelta(days=13 - index)).isoformat() for index in range(14)]
    assert [row['date'] for row in days] == expected_dates
    assert [row['count'] for row in days] == daily_counts, days
    assert s['consistency']['goal'] == goal
    assert s['consistency']['days_on_goal'] == sum(count >= goal for count in daily_counts)
    assert s['consistency']['total_days'] == 14
    assert s['tracker'] == {'goal': goal, 'done': daily_counts[-1]}
    expected_weeks = {}
    monday = TODAY - dt.timedelta(days=TODAY.weekday())
    for back in range(11, -1, -1):
        expected_weeks[(monday - dt.timedelta(weeks=back)).isoformat()] = 0
    for day, count in zip(expected_dates, daily_counts):
        date = dt.date.fromisoformat(day)
        expected_weeks[(date - dt.timedelta(days=date.weekday())).isoformat()] += count
    assert s['outreach'] == [{'week': day, 'count': count} for day, count in expected_weeks.items()], s['outreach']
    assert s['profile'] == (profile or {'latest': None, 'history': []}), s['profile']
    assert len(s['jobs']) == counts['applied']


TIMING_VALUES = {'speed_to_lead': 120, 'client_reply': 600, 'our_reply': 300,
                 'time_to_close': 7200, 'call_to_proposal': 1800}


def cohorts():
    for n in (5, 25, 60, 120):
        with fixture(f'n{n}'):
            rows = []
            for index in range(n):
                rows.append({'id': str(990000000 + index), 'title': f'SYNTHETIC n={n} lead {index}',
                             'status': 'won', 'found_at': stamp(), 'applied_at': stamp(),
                             'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
                             'replied_at': stamp(600),
                             'replied_observation': {'verified': True, 'source': 'upwork-thread'},
                             'speed_to_lead_s': 120, 'reply_gaps_s': [300],
                             'proposal_sent_at': stamp(5400), 'opened_at': stamp(6000),
                             'history': [{'status': 'applied', 'at': stamp()},
                                         {'status': 'replied', 'at': stamp(600)},
                                         {'status': 'call', 'at': stamp(3600)},
                                         {'status': 'won', 'at': stamp(7200)}]})
            seed(rows)
            s = state()
            assert s['timings']['call_to_proposal']['values'] == [{'seconds': 1800.0, 'call_source': 'observed', 'proposal_source': 'member'}] * n
            daily = [0] * 14
            daily[11] = n
            counts = {key: n for key in ('applied', 'replied', 'call', 'offer', 'won', 'proposal_sent', 'opened')}
            assert_dashboard(s, counts, {key: n for key in TIMING_VALUES},
                             {key: value if n >= 20 else None for key, value in TIMING_VALUES.items()}, daily)
            js = '''const assert=require('node:assert/strict');
(async()=>{const {funnelSteps,APPLICATION_STEPS,PROPOSAL_STEPS}=await import(process.argv[1]);
const s=JSON.parse(process.argv[2]); const n=Number(process.argv[3]);
for(const definitions of [APPLICATION_STEPS,PROPOSAL_STEPS]) {
 const steps=funnelSteps(s.funnel,definitions);
 assert.equal(steps[0].count,n); assert.equal(steps[0].rate,null);
 for(const step of steps.slice(1)) {
  assert.equal(step.count,n); assert.equal(step.n,n);
  assert.equal(step.rate,n>=50?100:null);
  assert.deepEqual(step.interval,n===60?[94,100]:null);
  assert.equal(step.overall,n>=50?100:null);
 }
}
const counts={applied:n,replied:Math.floor(n/2),call:0};
const step=funnelSteps(counts)[1];
assert.equal(step.n,n); assert.equal(step.rate,n>=50?50:null);
assert.deepEqual(step.interval,n===60?[38,62]:null);
})().catch(e=>{console.error(e);process.exitCode=1});'''
            result = ORIGINAL_RUN(['node', '-e', js, str(ROOT / 'website/lib/funnel.mjs'), json.dumps(s), str(n)],
                                  capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            print(f'SYNTHETIC n={n} PASS: both funnels, all five timings, rate bands, daily/weekly counts and tracker')


def eligibility():
    with fixture('eligibility'):
        seed([
            {'id': '991000001', 'title': 'SYNTHETIC verified', 'status': 'applied', 'found_at': stamp(),
             'posted_date': stamp(-120)},
            {'id': '991000002', 'title': 'SYNTHETIC unverified', 'status': 'applied', 'found_at': stamp(),
             'applied_at': stamp(), 'speed_to_lead_s': 999,
             'applied_observation': {'verified': False}, 'replied_at': stamp(999),
             'replied_observation': {'verified': False}},
            {'id': '991000003', 'title': 'SYNTHETIC naive', 'status': 'applied', 'found_at': stamp(),
             'applied_at': stamp().split('+')[0], 'speed_to_lead_s': 999,
             'applied_observation': {'verified': True}},
            {'id': '991000004', 'title': 'SYNTHETIC imported, no counted application', 'imported': True,
             'status': 'new', 'found_at': stamp()},
        ])
        run('pipeline.py', 'observe', '991000001', 'applied', stamp(), '--source', 'upwork-proposal', '--verified')
        run('pipeline.py', 'observe', '991000001', 'replied', stamp(600), '--source', 'upwork-thread', '--verified')
        assert run('pipeline.py', 'observe', '991000002', 'applied', stamp(), success=False).returncode != 0
        s = state()
        assert s['funnel'] == {'applied': 3, 'replied': 0, 'call': 0, 'offer': 0, 'won': 0, 'proposal_sent': 0, 'opened': 0}
        assert timing_core(s['timings']) == {key: {'n': 1 if key in ('speed_to_lead', 'client_reply') else 0,
                                              'median_s': None} for key in TIMING_VALUES}
        import cockpit
        assert timing_core(cockpit.timings([{'applied_at': stamp(), 'applied_observation': {'verified': True},
                                'speed_to_lead_s': -1, 'replied_at': stamp(-1),
                                'replied_observation': {'verified': True},
                                'history': [{'status': 'won', 'at': stamp(-1)}]}])) == {
                                    key: {'n': 0, 'median_s': None} for key in TIMING_VALUES}
        for n, expected in [(19, None), (20, 150)]:
            values = [{'reply_gaps_s': [100 if i % 2 == 0 else 200]} for i in range(n)]
            assert cockpit.timings(values)['our_reply'] == {'n': n, 'median_s': expected}
        print('SYNTHETIC eligibility PASS: verified/unverified, naive/negative times, imported rows, n=19/20 and even median')


def reply_and_proposal():
    with fixture('reply'):
        seed([{'id': '992000001', 'title': 'SYNTHETIC reply gaps', 'status': 'call', 'found_at': stamp(),
               'history': [{'status': 'call', 'at': stamp(3600)}]}])
        import sync
        messages = [{'node': {'id': 'c1', 'from_side': 'client', 'createdDateTime': stamp(), 'message': 'Question?'}},
                    {'node': {'id': 'c2', 'from_side': 'client', 'createdDateTime': stamp(60), 'message': 'More?'}},
                    {'node': {'id': 'event', 'from_side': 'system', 'createdDateTime': stamp(100), 'message': 'Notice'}},
                    {'node': {'id': 'm1', 'from_side': 'freelancer', 'createdDateTime': stamp(300), 'message': 'Answer.'}},
                    {'node': {'id': 'm2', 'from_side': 'freelancer', 'createdDateTime': stamp(400), 'message': 'Follow-up.'}},
                    {'node': {'id': 'c3', 'from_side': 'client', 'createdDateTime': stamp(600), 'message': 'Unanswered?'}}]
        thread = {'job_id': '992000001', 'room_id': 'synthetic-room', 'messages_complete': True,
                  'messages': list(reversed(messages)) + [messages[0]]}
        assert sync.reply_gaps(thread) == [300]
        assert sync.reply_gaps(dict(thread, invitation_room=True)) == []
        invite = json.loads(json.dumps(thread))
        invite['messages'][-1]['node']['kind'] = 'invite'
        assert sync.reply_gaps(invite) == []
        assert sync.reply_gaps(dict(thread, messages_complete=False)) is None
        assert sync.reply_gaps(dict(thread, messages=[None])) is None
        assert sync.reply_gaps(dict(thread, messages=[{'node': {'from_side': 'unknown'}}])) is None
        run('sync.py', 'apply', '--file', '-', value={'threads': [thread]})
        assert records()['992000001']['reply_gaps_s'] == [300]
        run('sync.py', 'apply', '--file', '-', value={'threads': [thread]})
        assert records()['992000001']['reply_gaps_s'] == [300]
        run('sync.py', 'apply', '--file', '-', value={'threads': [dict(thread, messages_complete=False)]})
        assert records()['992000001']['reply_gaps_s'] == [300]
        other_room = dict(thread, room_id='synthetic-second-room', messages_complete=False)
        changed_room = dict(thread, messages=[messages[0], messages[3]])
        run('sync.py', 'apply', '--file', '-', value={'threads': [changed_room, other_room]})
        assert records()['992000001']['reply_gaps_s'] == [300]
        assert record('992000001', {'reply_gaps_s': [1, 2]}).returncode == 0
        assert run('pipeline.py', 'record', '992000001', '--file', '-', value={'reply_gaps_s': [True]}, success=False).returncode != 0
        before = records()['992000001']
        run('pipeline.py', 'observe', '992000001', 'proposal_sent', stamp(5400))
        run('pipeline.py', 'observe', '992000001', 'proposal_sent', stamp(5500))
        after = records()['992000001']
        assert after['history'] == before['history'] and after['status'] == before['status']
        assert after['proposal_sent_at'] == stamp(5400)
        assert state()['timings']['call_to_proposal'] == {'n': 1, 'median_s': None, 'values': [{'seconds': 1800.0, 'call_source': 'observed', 'proposal_source': 'member'}]}
        print('SYNTHETIC S3/S9 PASS: raw sender sides, system/invite rooms, dedup/replay/partial sync; proposal observation preserves history')


def daily():
    with fixture('daily') as folder:
        vector = [0, 5, 0, 7, 1, 0, 5, 0, 2, 0, 5, 0, 6, 0]
        rows = []
        for offset, count in enumerate(vector):
            day = TODAY - dt.timedelta(days=13 - offset)
            for index in range(count):
                at = dt.datetime.combine(day, dt.time(12), dt.timezone.utc)
                if offset == 12 and index == 0:
                    at = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(23, 30), dt.timezone.utc)
                rows.append({'id': str(993000000 + len(rows)), 'title': 'SYNTHETIC local-day application',
                             'status': 'applied', 'found_at': at.isoformat(), 'applied_at': at.isoformat()})
        seed(rows)
        s = state()
        assert [row['count'] for row in s['consistency']['days']] == vector
        assert s['consistency']['days_on_goal'] == 5 and s['consistency']['total_days'] == 14
        assert s['tracker'] == {'goal': 5, 'done': 0}
        assert sum(vector) == 31 and max(vector) == 7
        assert any(dt.date.fromisoformat(row['date']).weekday() >= 5 and row['count'] for row in s['consistency']['days'])
        (folder / 'context' / 'me.md').write_text('**Applications per day:** 7\n')
        assert state()['consistency']['goal'] == 7
        assert state()['consistency']['days_on_goal'] == 1
        print('SYNTHETIC S5 PASS: 14 days [0,5,0,7,1,0,5,0,2,0,5,0,6,0], total=31, on-goal=5/14, local midnight, weekend, override=7')


def profile_and_retention():
    with fixture('profile') as folder:
        old = stamp(-10 * 86400)
        seed([{'id': '994000001', 'title': 'SYNTHETIC retained member details', 'status': 'call', 'found_at': old,
               'details': {'connects_cost': 16, 'description': 'SYNTHETIC expired posting',
                           'fetched_at': old, '_cached_at': {'description': old}},
               'reply_gaps_s': [300], 'loom_duration_s': 120, 'loom_wpm': 5,
               'call_stats': {'duration_s': 300}}])
        profile = {'data': {'personalData': {'photo': 'synthetic-photo', 'description': 'SYNTHETIC overview'},
                            'skills': [{'prettyName': 'Python'}, {'prettyName': 'Analytics'}],
                            'employmentRecords': [{}], 'educationRecords': [], 'video': ''}}
        highlights = {'portfolio_projects': [{'title': 'SYNTHETIC portfolio'}] * 4, 'certificates': []}
        p = folder / 'data' / 'profile.json'
        h = folder / 'data' / 'highlights.json'
        p.write_text(json.dumps(profile)); h.write_text(json.dumps(highlights))
        result = json.loads(run('profile_checks.py', p, h, '--json').stdout)
        missing = ['Additional employment', 'Education', 'Intro video', 'Linked account', 'Certificates', 'Other experience']
        assert result['completeness'] == {'pct': 80, 'missing': missing}
        import profile_checks
        empty = json.loads(json.dumps(profile))
        empty['data']['personalData']['video'] = 'SYNTHETIC stale fallback'
        assert profile_checks.normalize(empty, highlights)['video'] == ''
        without_photo = json.loads(json.dumps(profile))
        without_photo['data']['personalData'].pop('photo')
        assert profile_checks.completeness(profile_checks.normalize(without_photo, highlights))['pct'] == 30
        rich = profile_checks.normalize(profile, highlights)
        rich.update(employment=[{}] * 8, education=[{}] * 8, video='SYNTHETIC video',
                    linked_accounts=[{}], certificates=[{}] * 8, other_experience=[{}])
        assert profile_checks.completeness(rich)['pct'] == 100
        history_path = folder / 'data' / 'profile-history.jsonl'
        snapshots = [{'date': (TODAY - dt.timedelta(days=10)).isoformat(), 'pct': 40, 'missing': ['Photo']},
                     {'date': (TODAY - dt.timedelta(days=5)).isoformat(), 'pct': 65, 'missing': ['Intro video']}]
        history_path.write_text(''.join(json.dumps(row) + '\n' for row in snapshots))
        run('profile_checks.py', p, h, '--json')
        latest = {'date': TODAY.isoformat(), 'pct': 80, 'missing': missing}
        snapshots.append(latest)
        s = state()
        assert s['profile'] == {'latest': latest, 'history': snapshots}
        assert s['profile']['latest']['pct'] - s['profile']['history'][0]['pct'] == 40
        jobdir = folder / 'jobs' / '994000001'
        jobdir.mkdir()
        for name in ('loom.md', 'call.md', 'clicks.json'):
            (jobdir / name).write_text('[]' if name.endswith('.json') else 'SYNTHETIC retained source\n')
        expired = time.time() - 10 * 86400
        for path in (p, h): os.utime(path, (expired, expired))
        run('pipeline.py', 'prune', '--hours', '24')
        job = records()['994000001']
        assert job['details']['connects_cost'] == 16 and 'description' not in job['details']
        assert job['reply_gaps_s'] == [300] and job['loom_duration_s'] == 120 and job['loom_wpm'] == 5
        assert job['call_stats'] == {'duration_s': 300}
        assert not p.exists() and not h.exists()
        assert history_path.exists() and state()['profile'] == s['profile']
        assert all((jobdir / name).exists() for name in ('loom.md', 'call.md', 'clicks.json'))
        print('SYNTHETIC S4/S6 PASS: listed cost=16 retained; completeness=80%, trend=40→65→80 (+40), named gaps, empty video, caps and prune')


def media():
    with fixture('media') as folder:
        seed([{'id': '995000001', 'title': 'SYNTHETIC local Loom and call', 'status': 'call', 'found_at': stamp()}])
        env = dict(os.environ, PATH=str(folder / 'empty-bin'))
        skip = run('loom.py', '995000001', 'https://www.loom.com/share/synthetic', env=env)
        assert 'SKIP' in skip.stdout and 'brew install yt-dlp' in skip.stdout
        binary = folder / 'empty-bin' / 'yt-dlp'
        binary.parent.mkdir(); binary.write_text('#!/bin/sh\nexit 1\n'); binary.chmod(0o755)
        skip = run('loom.py', '995000001', 'https://www.loom.com/share/synthetic', env=env)
        assert 'SKIP' in skip.stdout and 'brew install whisper.cpp' in skip.stdout
        model = folder / 'synthetic-model.bin'; model.write_text('SYNTHETIC; never executed')
        import loom
        def fake_run(args, **kwargs):
            if args[0] == 'yt-dlp':
                if '--dump-single-json' in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps({'duration': 120}), '')
                path = args[args.index('-o') + 1].replace('%(ext)s', 'wav')
                pathlib.Path(path).write_bytes(b'SYNTHETIC; not downloaded')
                return subprocess.CompletedProcess(args, 0, '', '')
            if args[0] == 'whisper-cli':
                output = pathlib.Path(args[args.index('-of') + 1])
                output.with_suffix('.txt').write_text('Your client loses leads. Could we review one working demo?')
                output.with_suffix('.srt').write_text('1\n00:00:00,000 --> 00:00:15,000\nYour client loses leads.\n')
                return subprocess.CompletedProcess(args, 0, '', '')
            kwargs['capture_output'] = True
            return ORIGINAL_RUN(args, **kwargs)
        with mock.patch.dict(os.environ, WHISPER_MODEL=str(model)), mock.patch.object(loom.shutil, 'which', return_value='/synthetic/bin'), mock.patch.object(loom.subprocess, 'run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
            assert loom.main(['995000001', 'https://www.loom.com/share/synthetic']) == 0
        job = records()['995000001']
        assert job['loom_duration_s'] == 120 and job['loom_wpm'] == 5
        assert 'duration_s' not in job and 'wpm' not in job
        jobdir = folder / 'jobs' / '995000001'
        assert '00:00:15' in (jobdir / 'loom.md').read_text()
        (jobdir / 'call.md').write_text('Duration: 300\nMember: Alex\nAlex: What hurts?\nClient: Too many lost leads every day.\nAlex: Shall we try?\nClient: Yes?\n')
        run('call_stats.py', '995000001')
        stats = records()['995000001']['call_stats']
        assert stats == {'duration_s': 300.0, 'talk_share_pct': 41.7, 'question_counts': {'member': 2, 'client': 1}, 'talk_share_basis': 'words'}, stats
        (jobdir / 'call.md').write_text('Duration: 300\nNo speaker labels in this synthetic recorder export.\n')
        run('call_stats.py', '995000001')
        stats = records()['995000001']['call_stats']
        assert stats['duration_s'] == 300 and set(stats) == {'duration_s', 'note'}
        assert 'Duration only' in stats['note']
        print('SYNTHETIC S7/S8 PASS: missing-tool skips, mocked Loom duration=120/wpm=5 (no downloads), labelled call=300s/41.7%/2:1 questions; unlabelled duration only')


def clicks():
    with fixture('clicks') as folder:
        seed([{'id': '996000001', 'title': 'SYNTHETIC application and proposal openings',
               'status': 'call', 'found_at': stamp(), 'applied_at': stamp(), 'proposal_sent_at': stamp(200),
               'pitch_url': 'https://synthetic.example/996000001'},
              {'id': '996000002', 'title': 'SYNTHETIC application opening only',
               'status': 'call', 'found_at': stamp(), 'applied_at': stamp()},
              {'id': '996000003', 'title': 'SYNTHETIC bot-only proposal',
               'status': 'call', 'found_at': stamp(), 'proposal_sent_at': stamp(200)}])
        skipped = run('clicks.py')
        assert 'BLOB_READ_WRITE_TOKEN is missing' in skipped.stdout
        args = ['996000001', 'loom', 'https://www.loom.com/share/synthetic', '--base', 'https://synthetic.example', '--kind', 'application', '--approved']
        skipped = run('clicks.py', 'register', *args)
        assert 'Keep the original untracked link' in skipped.stdout
        assert not (folder / 'jobs/996000001/tracking-links.json').exists()
        assert run('clicks.py', 'register', '996000001', 'loom', 'https://www.loom.com/share/synthetic', '--base', 'https://synthetic.example', '--approved', success=False).returncode != 0
        import clicks as click_module
        token = 'vercel_blob_rw_synthetic'
        with mock.patch.dict(os.environ, BLOB_READ_WRITE_TOKEN=token), mock.patch.object(click_module, 'preflight', return_value=False), contextlib.redirect_stdout(io.StringIO()):
            assert click_module.register(args) == 0
        assert not (folder / 'jobs/996000001/tracking-links.json').exists()
        links = [('996000001', 'loom', 'https://www.loom.com/share/synthetic', 'application'),
                 ('996000001', 'pitch', 'https://synthetic.example/996000001', 'application'),
                 ('996000001', 'proposal', 'https://synthetic.example/996000001/proposal', 'proposal'),
                 ('996000002', 'pitch', 'https://synthetic.example/996000002', 'application'),
                 ('996000003', 'proposal', 'https://synthetic.example/996000003/proposal', 'proposal')]
        with mock.patch.dict(os.environ, BLOB_READ_WRITE_TOKEN=token), mock.patch.object(click_module, 'preflight', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            for jid, slug, target, kind in links:
                assert click_module.register([jid, slug, target, '--base', 'https://synthetic.example', '--kind', kind, '--approved']) == 0
        registry_path = folder / 'jobs/996000001/tracking-links.json'
        registry = json.loads(registry_path.read_text())
        assert registry['loom']['kind'] == 'application' and registry['proposal']['kind'] == 'proposal'
        hits = [{'job': '996000001', 'slug': 'loom', 'at': stamp(-60), 'bot': False},
                {'job': '996000001', 'slug': 'loom', 'at': stamp(10), 'bot': True},
                {'job': '996000001', 'slug': 'loom', 'at': stamp(60), 'bot': False},
                {'job': '996000001', 'slug': 'proposal', 'at': stamp(100), 'bot': False},
                {'job': '996000001', 'slug': 'proposal', 'at': stamp(200), 'bot': False},
                {'job': '996000001', 'slug': 'proposal', 'at': stamp(220), 'bot': True},
                {'job': '996000001', 'slug': 'proposal', 'at': stamp(300), 'bot': False},
                {'job': '996000001', 'slug': 'proposal', 'at': stamp(240), 'bot': False},
                {'job': '996000002', 'slug': 'pitch', 'at': stamp(60), 'bot': False},
                {'job': '996000003', 'slug': 'proposal', 'at': stamp(240), 'bot': True}]
        log = folder / 'synthetic-clicks.jsonl'
        log.write_text(''.join(json.dumps(row) + '\n' for row in hits[:6]))
        run('clicks.py', '--log', log)
        assert 'opened_at' not in records()['996000001']
        assert records()['996000001']['pitch_opened_at'] == stamp(60)
        log.write_text(''.join(json.dumps(row) + '\n' for row in hits))
        run('clicks.py', '--log', log)
        run('clicks.py', '--log', log)
        jobs = records()
        assert jobs['996000001']['pitch_opened_at'] == stamp(60)
        assert jobs['996000001']['opened_at'] == stamp(240)
        assert jobs['996000002']['pitch_opened_at'] == stamp(60) and 'opened_at' not in jobs['996000002']
        assert 'opened_at' not in jobs['996000003']
        stored = json.loads((folder / 'jobs/996000001/clicks.json').read_text())
        assert len(stored) == 8 and all(set(row) == {'job', 'slug', 'at', 'bot'} for row in stored)
        assert state()['funnel']['opened'] == 1
        import application_check
        assert application_check.has_video('https://synthetic.example/go/996000001/loom')
        assert not application_check.has_video('https://unregistered.example/go/996000001/loom')
        with mock.patch.object(application_check, 'tracking_target', return_value='https://linkedin.com/in/synthetic'):
            assert application_check.pc_contacts('https://synthetic.example/go/996000001/social')
        rejected = False
        with mock.patch.dict(os.environ, BLOB_READ_WRITE_TOKEN=token), mock.patch.object(click_module, 'preflight', return_value=True), contextlib.redirect_stderr(io.StringIO()):
            try:
                click_module.register(['996000001', 'social', 'https://linkedin.com/in/synthetic', '--base', 'https://synthetic.example', '--kind', 'proposal', '--approved'])
            except SystemExit as exc:
                rejected = exc.code != 0
        assert rejected
        responses = [{'blobs': [{'url': 'https://synthetic.private.blob.vercel-storage.com/a'}], 'hasMore': True, 'cursor': 'next'}, hits[0],
                     {'blobs': [{'url': 'https://synthetic.private.blob.vercel-storage.com/b'}], 'hasMore': False}, hits[1]]
        requests = []
        def fake_urlopen(request, **kwargs):
            requests.append(request)
            return io.StringIO(json.dumps(responses.pop(0)))
        with mock.patch.object(click_module.urllib.request, 'urlopen', side_effect=fake_urlopen):
            assert list(click_module.remote_hits(token)) == hits[:2]
        assert 'cursor=next' in requests[2].full_url and requests[0].get_header('X-api-version') == '12'
        with mock.patch.object(click_module.urllib.request, 'urlopen', return_value=io.StringIO('{"blobs":[]}')):
            assert click_module.preflight(token)
        import pitch_deploy
        pitch = folder / 'jobs/996000001/pitch.html'; pitch.write_text('<p>SYNTHETIC page</p>')
        stage = folder / 'staged-pitch'
        pitch_deploy.write_site(stage, [('996000001', pitch)], '996000001')
        assert (stage / 'api/go.js').is_file() and (stage / 'api/_tracking-links.json').is_file()
        assert not (stage / 'tracking-links.json').exists()
        config = json.loads((stage / 'vercel.json').read_text())
        assert config['rewrites'] == [{'source': '/go/:job/:slug', 'destination': '/api/go?job=:job&slug=:slug'}]
        assert config['functions'] == {'api/go.js': {'includeFiles': 'api/_tracking-links.json'}}
        staged_registry = json.loads((stage / 'api/_tracking-links.json').read_text())
        targets = [link['target'] for entries in staged_registry.values() for link in entries.values()]
        for path in stage.rglob('*'):
            if path.is_file() and path.relative_to(stage).parts[0] != 'api':
                assert not any(target in path.read_text() for target in targets), path
        js = '''const assert=require('node:assert/strict');const handler=require(process.argv[1]);
const fs=require('node:fs');process.env.TRACKING_LINKS_PATH=process.argv[2];
const now=Date.parse('2026-01-01T12:00:00Z');Date.now=()=>now;
fs.writeFileSync(process.argv[2],JSON.stringify({'996000001':{loom:{target:'https://www.loom.com/share/synthetic',created_at:new Date(now).toISOString(),kind:'application'}}}));
const bots=['slackbot','linkedinbot','googlebot','bingbot','preview','curl','python-requests'];
for(const bot of bots) assert.equal(handler.isBot(bot),true);
assert.equal(handler.isBot('Mozilla',new Date(now).toISOString(),now),false);
let writes=[];global.fetch=async(url,options)=>{writes.push(JSON.parse(options.body));return {ok:true}};
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v},status(code){this.code=code;return this},end(text){this.text=text}}}
(async()=>{process.env.BLOB_READ_WRITE_TOKEN='vercel_blob_rw_synthetic';
for(const req of [{method:'HEAD',query:{job:'996000001',slug:'loom'}},{method:'GET',query:{job:'996000001',slug:'loom',check:'1'}}]) {
const res=response();await handler(req,res);assert.equal(res.code,302);assert.equal(res.headers.Location,'https://www.loom.com/share/synthetic');assert.equal(writes.length,0);assert.match(res.headers['X-Tracking-Status'],/not logged/);}
delete process.env.BLOB_READ_WRITE_TOKEN;let res=response();await handler({method:'GET',query:{job:'996000001',slug:'loom'},headers:{}},res);
assert.equal(res.code,302);assert.equal(writes.length,0);assert.match(res.headers['X-Tracking-Status'],/missing/);
process.env.BLOB_READ_WRITE_TOKEN='vercel_blob_rw_synthetic';res=response();await handler({method:'GET',query:{job:'996000001',slug:'loom'},headers:{'user-agent':'Mozilla'}},res);
assert.equal(res.code,302);assert.deepEqual(Object.keys(writes[0]).sort(),['at','bot','job','slug']);assert.equal(writes[0].bot,false);
for(const bot of bots){res=response();await handler({method:'GET',query:{job:'996000001',slug:'loom'},headers:{'user-agent':bot}},res);assert.equal(writes[writes.length-1].bot,true);}
global.fetch=async()=>({ok:false});res=response();await handler({method:'GET',query:{job:'996000001',slug:'loom'},headers:{}},res);assert.equal(res.code,302);assert.match(res.headers['X-Tracking-Status'],/failed/);
res=response();await handler({method:'GET',query:{job:'bad',slug:'loom'},headers:{}},res);assert.equal(res.code,404);
})().catch(e=>{console.error(e);process.exitCode=1});'''
        result = ORIGINAL_RUN(['node', '-e', js, str(ROOT / 'api/go.js'), str(stage / 'api/_tracking-links.json')], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        print('SYNTHETIC fixes 1–3 PASS: private bundled registry; HEAD/check bypass logs; link kinds; strict post-send openings; preview/curl/Python bots; no creation-age rule')


def dashboard_fixture():
    """One populated dashboard, including every new card and all five timings."""
    vector = [0, 5, 0, 7, 1, 0, 5, 0, 2, 0, 5, 0, 6, 0]
    rows = []
    old = dt.datetime.combine(TODAY - dt.timedelta(days=30), dt.time(12), dt.timezone.utc)
    def at(seconds=0):
        return (old + dt.timedelta(seconds=seconds)).isoformat()
    for index in range(60):
        rows.append({'id': str(997000000 + index), 'title': 'SYNTHETIC measured dashboard lead',
                     'status': 'won', 'found_at': at(), 'applied_at': at(),
                     'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
                     'replied_at': at(600), 'replied_observation': {'verified': True, 'source': 'upwork-thread'},
                     'speed_to_lead_s': 120, 'reply_gaps_s': [300],
                     'proposal_sent_at': at(5400), 'opened_at': at(6000),
                     'history': [{'status': 'call', 'at': at(3600)}, {'status': 'won', 'at': at(7200)}]})
    for offset, count in enumerate(vector):
        date = TODAY - dt.timedelta(days=13 - offset)
        for index in range(count):
            at_day = dt.datetime.combine(date, dt.time(12), dt.timezone.utc).isoformat()
            rows.append({'id': str(998000000 + len(rows)), 'title': 'SYNTHETIC daily dashboard lead',
                         'status': 'applied', 'found_at': at_day, 'applied_at': at_day})
    seed(rows)
    history = [{'date': (TODAY - dt.timedelta(days=10)).isoformat(), 'pct': 40, 'missing': ['Photo']},
               {'date': (TODAY - dt.timedelta(days=5)).isoformat(), 'pct': 65, 'missing': ['Intro video']},
               {'date': TODAY.isoformat(), 'pct': 80, 'missing': ['Intro video', 'Certificates']}]
    pathlib.Path(os.environ['BLUEPRINT_DATA'], 'profile-history.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in history), encoding='utf-8')
    s = state()
    assert s['funnel'] == {'applied': 91, 'replied': 60, 'call': 60, 'offer': 60, 'won': 60,
                           'proposal_sent': 60, 'opened': 60}
    assert timing_core(s['timings']) == {key: {'n': 60, 'median_s': value} for key, value in TIMING_VALUES.items()}
    assert s['profile'] == {'latest': history[-1], 'history': history}
    assert s['profile']['latest']['pct'] - history[0]['pct'] == 40
    assert s['consistency'] == {'goal': 5, 'days': [
        {'date': (TODAY - dt.timedelta(days=13-index)).isoformat(), 'count': count}
        for index, count in enumerate(vector)], 'days_on_goal': 5, 'total_days': 14}
    assert s['tracker'] == {'goal': 5, 'done': 0}
    monday = TODAY - dt.timedelta(days=TODAY.weekday())
    weeks = {(monday - dt.timedelta(weeks=back)).isoformat(): 0 for back in range(11, -1, -1)}
    weeks[(old.date() - dt.timedelta(days=old.weekday())).isoformat()] += 60
    for index, count in enumerate(vector):
        date = TODAY - dt.timedelta(days=13-index)
        weeks[(date - dt.timedelta(days=date.weekday())).isoformat()] += count
    assert s['outreach'] == [{'week': day, 'count': count} for day, count in weeks.items()]
    assert sum(row['count'] for row in s['outreach']) == 91
    assert max(row['count'] for row in s['outreach']) == 60
    active_weeks = {(old.date() - dt.timedelta(days=old.weekday())).isoformat()}
    for index, count in enumerate(vector):
        if count:
            day = TODAY - dt.timedelta(days=13-index)
            active_weeks.add((day - dt.timedelta(days=day.weekday())).isoformat())
    assert sum(row['count'] == 0 for row in s['outreach']) == 12 - len(active_weeks)
    js = """const assert=require('node:assert/strict');
(async()=>{const {funnelSteps,PROPOSAL_STEPS}=await import(process.argv[1]);
const counts=JSON.parse(process.argv[2]);const first=funnelSteps(counts);
assert.equal(first[1].rate,66);assert.deepEqual(first[1].interval,[56,75]);
assert.equal(first[2].rate,100);assert.deepEqual(first[2].interval,[94,100]);
for(const step of funnelSteps(counts,PROPOSAL_STEPS).slice(1)) {
assert.equal(step.n,60);assert.equal(step.rate,100);assert.deepEqual(step.interval,[94,100]);}
})().catch(e=>{console.error(e);process.exitCode=1});"""
    result = ORIGINAL_RUN(['node', '-e', js, str(ROOT / 'website/lib/funnel.mjs'), json.dumps(s['funnel'])],
                          capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return s


def review_proofs():
    with fixture('review') as folder:
        seed([{'id': '999000001', 'title': 'SYNTHETIC review fixes', 'status': 'call', 'found_at': stamp(),
               'applied_at': stamp(), 'history': [{'status': 'call', 'at': stamp(1200)}]}])
        import pipeline
        import sync
        block = {'job_id': '999000001', 'room_id': 'synthetic-blocks', 'messages_complete': True,
                 'messages': [{'from': 'me', 'at': stamp(), 'text': 'Opening'},
                              {'from': 'client', 'at': stamp(60), 'text': 'First question'},
                              {'from': 'client', 'at': stamp(100), 'text': 'Second question'},
                              {'from': 'system', 'at': stamp(120), 'text': 'System event'},
                              {'from': 'me', 'at': stamp(300), 'text': 'Answer'},
                              {'from': 'client', 'at': stamp(360), 'text': 'New block'},
                              {'from': 'client', 'at': stamp(400), 'text': 'More'},
                              {'from': 'me', 'at': stamp(600), 'text': 'Answer'}]}
        assert sync.reply_gaps(block) == [240, 240]
        original = sync.subprocess.run
        checked = []
        def fail_clicks(args, **kwargs):
            if 'clicks.py' in str(args[1]):
                checked.append(kwargs.get('check'))
                return subprocess.CompletedProcess(args, 1, '', 'SYNTHETIC Blob failure')
            return original(args, **kwargs)
        output = io.StringIO()
        with mock.patch.object(sync.subprocess, 'run', side_effect=fail_clicks), mock.patch.object(sys, 'argv', ['sync.py', 'apply', '--file', '-']), mock.patch.object(sys, 'stdin', io.StringIO(json.dumps({'threads': [block]}))), contextlib.redirect_stdout(output):
            sync.main()
        assert checked == [False]
        assert output.getvalue().count('Click sync failed;') == 1
        assert 'threads saved' in output.getvalue()
        assert records()['999000001']['reply_gaps_s'] == [240, 240]
        record('999000001', {'loom_hook': 'pass', 'call_next_step': True})
        assert records()['999000001']['loom_hook'] == 'pass' and records()['999000001']['call_next_step'] is True
        for payload in ({'loom_hook': True}, {'loom_hook': 'maybe'}, {'call_next_step': 1}, {'call_next_step': 'true'}, {'duration_s': 120}, {'wpm': 5}):
            assert run('pipeline.py', 'record', '999000001', '--file', '-', value=payload, success=False).returncode != 0
        jobdir = folder / 'jobs/999000001'
        (jobdir / 'call.md').write_text(f'Call at: {stamp(3600)}\nDuration: 300\nMember: Alex\nAlex: Next step?\nClient: Send it.\n')
        run('call_stats.py', '999000001')
        job = records()['999000001']
        assert job['call_at'] == stamp(3600) and job['call_observation']['source'] == 'recorder'
        run('pipeline.py', 'observe', '999000001', 'proposal_sent', stamp(5400))
        assert state()['timings']['call_to_proposal']['values'] == [{'seconds': 1800.0, 'call_source': 'recorder', 'proposal_source': 'member'}]
        run('pipeline.py', 'set', '999000001', 'offer', '--note', 'SYNTHETIC stage change')
        assert records()['999000001']['call_at'] == stamp(3600)
        assert run('pipeline.py', 'set', '999000001', 'call', '--call-at', (TODAY + dt.timedelta(days=1)).isoformat(), success=False).returncode != 0
        assert records()['999000001']['call_at'] == stamp(3600)
        seed([{'id': '999000002', 'title': 'SYNTHETIC naive recorder', 'status': 'call', 'found_at': stamp(),
               'history': [{'status': 'call', 'at': stamp(1200)}], 'proposal_sent_at': stamp(5400)}])
        other = folder / 'jobs/999000002'; other.mkdir()
        (other / 'call.md').write_text('Call at: 2026-01-01T12:00:00\nDuration: 300\nUnlabelled text.\n')
        run('call_stats.py', '999000002')
        assert 'call_at' not in records()['999000002']
        value = state()['timings']['call_to_proposal']['values'][1]
        assert value == {'seconds': 4200.0, 'call_source': 'observed', 'proposal_source': 'member'}
        import cockpit
        scheduled = {'call_at': stamp(2400), 'history': [{'status': 'call', 'at': stamp(1200)}]}
        observed_at, source = cockpit.call_time(scheduled)
        assert observed_at.isoformat() == stamp(1200) and source == 'observed'
        assert cockpit.timings([dict(scheduled, proposal_sent_at=stamp(5400))])['call_to_proposal']['values'] == [{'seconds': 4200.0, 'call_source': 'observed', 'proposal_source': 'member'}]
        import loom
        models = folder / 'models'; models.mkdir()
        for name in ('ggml-base.en.bin', 'ggml-small.bin', 'ggml-for-tests-base.bin'):
            (models / name).write_text('SYNTHETIC model; never executed')
        with mock.patch.object(loom, 'MODEL_DIRS', (models,)):
            assert loom.find_model().name == 'ggml-small.bin'
            (models / 'ggml-base.bin').write_text('SYNTHETIC model; never executed')
            assert loom.find_model().name == 'ggml-base.bin'
            with mock.patch.dict(os.environ, WHISPER_MODEL=str(models / 'ggml-base.en.bin')):
                assert loom.find_model().name == 'ggml-base.en.bin'
            for path in models.glob('*.bin'):
                if 'for-tests-' not in path.name:
                    path.unlink()
            assert loom.find_model() is None
            output = io.StringIO()
            with mock.patch.object(loom.shutil, 'which', return_value='/synthetic/bin'), mock.patch.object(loom.subprocess, 'run') as no_download, contextlib.redirect_stdout(output):
                assert loom.main(['999000001', 'https://www.loom.com/share/synthetic']) == 0
            no_download.assert_not_called()
            assert loom.MODEL_DOWNLOAD in output.getvalue() and 'ggml-base.bin' in output.getvalue()
        valid_model = folder / 'synthetic-model.bin'; valid_model.write_text('SYNTHETIC')
        for duration in (True, float('nan'), float('inf')):
            with mock.patch.dict(os.environ, WHISPER_MODEL=str(valid_model)), mock.patch.object(loom.shutil, 'which', return_value='/synthetic/bin'), mock.patch.object(loom.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps({'duration': duration}), '')) as downloader, contextlib.redirect_stderr(io.StringIO()):
                assert loom.main(['999000001', 'https://www.loom.com/share/synthetic']) == 1
                assert downloader.call_count == 1
        import profile_checks
        custom_data = folder / 'custom-data'
        custom_data.mkdir()
        previous = (TODAY - dt.timedelta(days=1)).isoformat()
        (custom_data / 'profile-history.jsonl').write_text(json.dumps({'date': previous, 'pct': 20, 'missing': ['Photo']}) + '\n' + json.dumps({'date': previous, 'pct': 30, 'missing': ['Photo']}) + '\n')
        with mock.patch.object(pipeline, 'data_dir', return_value=custom_data):
            profile_checks.save_completeness({'pct': 40, 'missing': ['Photo']})
            profile_checks.save_completeness({'pct': 80, 'missing': ['Intro video']})
        rows = [json.loads(line) for line in (custom_data / 'profile-history.jsonl').read_text().splitlines()]
        assert rows == [{'date': previous, 'pct': 30, 'missing': ['Photo']}, {'date': TODAY.isoformat(), 'pct': 80, 'missing': ['Intro video']}]
        # Profile inputs may be anywhere; snapshots always use the pipeline data directory.
        profile_path = folder / 'outside-profile.json'; highlights = folder / 'outside-highlights.json'
        profile_path.write_text('{"data":{}}'); highlights.write_text('{}')
        run('profile_checks.py', profile_path, highlights, '--json')
        run('profile_checks.py', profile_path, highlights, '--json')
        assert len((folder / 'data/profile-history.jsonl').read_text().splitlines()) == 1
        assert not (folder / 'profile-history.jsonl').exists()
        print('SYNTHETIC fixes 4/5/8/9 + S9 PASS: click failure preserves sync summary/writes; client blocks; named Loom metrics/model discovery/no downloads; one snapshot/date in pipeline data; recorder time wins and survives stage changes; observed fallback')
    with fixture('application-days'):
        local = dt.datetime.combine(TODAY, dt.time(0, 30), ZoneInfo('Europe/Berlin')).astimezone(dt.timezone.utc).isoformat()
        seed([{'id': '999100001', 'title': 'SYNTHETIC applied at local midnight', 'status': 'applied', 'applied_at': local, 'found_at': stamp()},
              {'id': '999100002', 'title': 'SYNTHETIC first applied history', 'status': 'applied', 'found_at': stamp(),
               'history': [{'status': 'applied', 'at': local}, {'status': 'applied', 'at': stamp()}]},
              {'id': '999100003', 'title': 'SYNTHETIC imported', 'imported': True, 'status': 'applied', 'applied_at': local, 'found_at': stamp()},
              {'id': '999100004', 'title': 'SYNTHETIC date unknown', 'application_date_unknown': True, 'status': 'applied', 'applied_at': local, 'found_at': stamp()},
              {'id': '999100005', 'title': 'SYNTHETIC found only', 'status': 'replied', 'found_at': stamp()},
              {'id': '999100006', 'title': 'SYNTHETIC later stage only', 'status': 'call', 'found_at': stamp(), 'status_updated_at': local,
               'history': [{'status': 'call', 'at': local}]}])
        jobs = list(records().values())
        assert pipeline.applied_on(jobs, TODAY.isoformat()) == 2
        s = state()
        assert s['tracker']['done'] == pipeline.applied_on(jobs, TODAY.isoformat())
        assert s['consistency']['days'][-1]['count'] == 2
        assert sum(day['count'] for day in s['consistency']['days']) == 2
        assert pipeline.application_day(records()['999100002']) == TODAY.isoformat()
        print('SYNTHETIC fix 6 PASS: only applied timestamp/first applied history; imported/unknown/found/later-stage rows excluded; local-day tracker == pipeline.applied_on')
    commands = ROOT / '.claude/commands'
    onboarding = (commands / 'onboarding.md').read_text()
    sales = (commands / 'sales-call-proposal.md').read_text()
    proposal = (commands / 'proposal.md').read_text()
    assert 'recorder' not in onboarding.lower()
    assert 'get_full_transcript' in sales and 'Enterprise' in sales and 'contract' in sales
    assert 'loom_hook' in proposal and 'Call at:' in sales
    assert 'code/call_stats.py' in sales and 'call_held' in sales
    for relative in ('.claude/commands', 'references'):
        result = ORIGINAL_RUN(['git', 'diff', '--numstat', '--', relative], cwd=ROOT, capture_output=True, text=True, check=True)
        # Keep the earlier repair's limits on its scope; package 2 explicitly
        # authorizes the weekly reminder and these member-setting docs. The analytics
        # goal library is excluded from this older repair's reference-size budget.
        package2 = {'.claude/commands/find-jobs.md', '.claude/commands/analytics.md',
                    '.claude/commands/brief.md', '.claude/commands/sales-call-proposal.md',
                    'references/jobs.md', 'references/goal-library.md'}
        legacy = [row for row in result.stdout.splitlines() if row.split('\t')[-1] not in package2]
        delta = sum(int(row.split()[0]) - int(row.split()[1]) for row in legacy)
        if relative == '.claude/commands':
            allowed = {'.claude/commands/brief.md', '.claude/commands/proposal.md',
                       '.claude/commands/sales-call-proposal.md'}
            assert all(row.split('\t')[-1] in allowed for row in legacy)
            assert delta <= 45, (relative, delta)
        else:
            assert delta <= 0, (relative, delta)
    find_jobs = (commands / 'find-jobs.md').read_text()
    assert find_jobs.count('Analytics due: run /analytics') == 1 and 'code/analytics.py due' in find_jobs
    settings = (ROOT / 'references/jobs.md').read_text()
    assert all(key in settings for key in ('## Bars', '## Analytics day', '## Weekly goal', '## Working hours'))
    assert (commands / 'analytics.md').is_file() and (ROOT / 'references/goal-library.md').is_file()
    application = (CODE / 'application_check.py').read_text()
    assert application.index('import pipeline') < application.index('def ')
    analytics = (ROOT / 'website/components/AnalyticsPage.tsx').read_text()
    assert 'No applications yet. The funnel fills as /brief records them.' in analytics
    assert "counts.applied >= MIN_RATE" in analytics and 'overall win rate' in analytics
    assert "observed (call history)" in analytics
    print('SYNTHETIC fixes 7/10 PASS: recorder transcript/fallback in sales command, hook writer, import cleanup, existing UI contracts; legacy command/reference budgets retained (analytics goal-library excluded); authorized analytics reminder/settings/files verified')


def bottlenecks():
    stages = ['Volume', 'Profile', 'Proposal', 'Loom', 'Speed', 'Messaging', 'Sales call', 'Call proposal', 'Opened']
    for failing in stages + [None]:
        with fixture('bottleneck') as folder:
            rows = []
            for index in range(100):
                day = TODAY - dt.timedelta(days=12 - index // 10)
                applied = dt.datetime.combine(day, dt.time(12), dt.timezone.utc)
                if failing == 'Volume':
                    applied = BASE
                call = applied + dt.timedelta(seconds=3600)
                sent = call + dt.timedelta(seconds=1800)
                if failing == 'Call proposal' and index >= 89:
                    sent = call + dt.timedelta(seconds=86401)
                had_reply = failing != 'Proposal' or index < 9
                had_call = had_reply and (failing != 'Messaging' or index < 29)
                row = {'id': str(999200000 + index), 'title': f'SYNTHETIC first failing {failing}',
                       'status': 'call' if had_call else 'replied' if had_reply else 'applied',
                       'found_at': applied.isoformat(), 'applied_at': applied.isoformat(),
                       'loom_hook': 'fail' if failing == 'Loom' and index == 0 else 'pass',
                       'call_next_step': not (failing == 'Sales call' and index >= 79),
                       'reply_gaps_s': [9000 if failing == 'Speed' else 300],
                       'history': [{'status': 'call', 'at': call.isoformat()}] if had_call else [],
                       'proposal_sent_at': sent.isoformat()}
                if failing != 'Opened' or index < 79:
                    row['opened_at'] = (sent + dt.timedelta(seconds=600)).isoformat()
                rows.append(row)
            seed(rows)
            profile = {'date': TODAY.isoformat(), 'pct': 80 if failing == 'Profile' else 100, 'missing': []}
            (folder / 'data/profile-history.jsonl').write_text(json.dumps(profile) + '\n')
            s = state()
            result = s['bottleneck']
            assert result['stage'] == failing, (failing, result)
            if failing:
                expected = {'Volume': (1, 10, 14), 'Profile': (80, 100, 1), 'Proposal': (9, 10, 100),
                            'Loom': (99, 100, 100), 'Speed': (2.5, 2, 100), 'Messaging': (29, 30, 100),
                            'Sales call': (79, 80, 100), 'Call proposal': (89, 90, 100), 'Opened': (79, 80, 100)}[failing]
                assert (result['value'], result['bar'], result['n']) == expected, result
                assert result['reasoned'] == (failing not in ('Volume', 'Profile'))
                assert result['next_action']
            if failing == 'Speed':
                (folder / 'context/me.md').write_text('# SYNTHETIC bars\nSpeed: 1\n## Bars\nSpeed: 3\nProposal: 101\nVolume: 15\nUnknown: 5\n## Other\nSpeed: 0\n')
                assert state()['bottleneck']['stage'] is None
                import cockpit
                assert cockpit.bars()['Speed'] == 3 and cockpit.bars()['Proposal'] == 10 and cockpit.bars()['Volume'] == 10
                (folder / 'context/me.md').write_text('## Bars\nSpeed: ' + '9' * 400 + '\n')
                assert cockpit.bars()['Speed'] == 2
            if failing is None:
                assert result['unmeasured'] == []
            print(f'SYNTHETIC S11 PASS: first failing stage={failing or "none"}')
    with fixture('under-minimum') as folder:
        (folder / 'context/me.md').write_text('# SYNTHETIC lower daily goal\n**Applications per day:** 1\n')
        seed([{'id': str(999300000 + index), 'title': 'SYNTHETIC under minimum n', 'status': 'applied',
               'applied_at': dt.datetime.combine(TODAY - dt.timedelta(days=12-index), dt.time(12), dt.timezone.utc).isoformat(),
               'found_at': stamp(), 'reply_gaps_s': [300]} for index in range(10)])
        s = state()
        assert s['consistency']['days_on_goal'] == 10
        assert s['bottleneck']['stage'] is None
        assert s['bottleneck']['unmeasured'] == stages[1:]
        import cockpit
        jobs = list(records().values())
        calls = [{'id': str(index), 'status': 'call', 'applied_at': stamp(), 'call_at': stamp(1200),
                  'call_observation': {'source': 'recorder', 'verified': True}, 'proposal_sent_at': stamp(87600)} for index in range(50)]
        # Exactly 24h passes; unsent calls contribute no success to the literal denominator.
        daily = {'days_on_goal': 10}; profile = {'latest': {'pct': 100}}
        timing = {'our_reply': {'n': 20, 'median_s': 7200}}
        decision = cockpit.bottleneck(calls, daily, profile, timing)
        assert decision['stage'] != 'Call proposal'
        calls[0].pop('proposal_sent_at')
        (folder / 'context/me.md').write_text('## Bars\nCall proposal: 100\n')
        assert cockpit.bottleneck(calls, daily, profile, timing)['stage'] == 'Call proposal'
        print('SYNTHETIC S11 PASS: all stages after Volume under n; scoped overrides; invalid bars ignored; 24h boundary; unsent call denominator')


def rendered_ui():
    with fixture('rendered-ui'):
        s = dashboard_fixture()
        js = r"""const assert=require('node:assert/strict');const fs=require('node:fs');
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const {transformSync}=require('next/dist/build/swc');
(async()=>{const funnel=await import('./lib/funnel.mjs');
const {code}=transformSync(fs.readFileSync('components/AnalyticsPage.tsx','utf8'),{
filename:'AnalyticsPage.tsx',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},
target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}});
let current;const mod={exports:{}};
new Function('require','module','exports',code)(name=>{
if(name==='@/lib/context')return {useCockpit:()=>({state:current})};
if(name==='@/lib/funnel.mjs')return funnel;return require(name);},mod,mod.exports);
function render(state){current=state;return renderToStaticMarkup(React.createElement(mod.exports.default));}
const populated=JSON.parse(process.argv[1]);const html=render(populated);
assert(html.startsWith('<p class="funnel-headline" aria-label="Bottleneck">'));
assert(html.indexOf('Bottleneck')<html.indexOf('Win the call'));
assert.match(html,/<strong>Volume<\/strong>: 5 days against 10 days · n=14/);
const deal=html.match(/<section[^>]*aria-label="Win the deal">([\s\S]*?)<\/section>/)[1];
assert.match(deal,/66% overall win rate/);assert.match(html,/observed \(call history\)/);
const empty=render({...populated,funnel:{},outreach:[],profile:{latest:null,history:[]},timings:{}});
assert(empty.includes('No applications yet. The funnel fills as /brief records them.'));
assert(!render({...populated,funnel:{applied:49,replied:20,call:15,proposal_sent:15,opened:12,won:10}}).includes('overall win rate'));
assert(render({...populated,funnel:{applied:50,replied:20,call:15,proposal_sent:15,opened:12,won:20}}).includes('40% overall win rate'));
const reasoned=render({...populated,bottleneck:{stage:'Speed',value:2.5,bar:2,n:100,reasoned:true,next_action:'Answer sooner.',unmeasured:['Loom']}});
assert(reasoned.includes('reasoned bar'));assert(reasoned.includes('Not measured yet: Loom.'));
console.log('SYNTHETIC rendered UI PASS: bottleneck first/value/bar/n/reasoned/unmeasured; empty state; win rate=66%, hidden at49, shown at50; observed call source');
})().catch(error=>{console.error(error);process.exitCode=1});"""
        result = ORIGINAL_RUN(['node', '-e', js, json.dumps(s)], cwd=ROOT / 'website', capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip())


def package1():
    with fixture('f1'):
        seed([{'id': '981000001', 'status': 'new', 'found_at': stamp(-86400 * 10),
               'budget': '$1,000', 'job_type': 'fixed', 'proposals': 8, 'lane': 'automation',
               'posted_date': stamp(-300), 'client': {'hires': 4, 'posted_jobs': 10, 'spent': 4000, 'verified': True},
               'details': {'bid_amount': 1200, 'connects_cost': 16}},
              {'id': '981000002', 'status': 'new'},
              {'id': '981000003', 'status': 'new', 'found_at': 'unusable', 'proposals': 123,
               'client': {'spent': 25000}, 'budget': '$300'}])
        run('pipeline.py', 'observe', '981000001', 'applied', stamp(), '--source', 'upwork-proposal', '--verified')
        facts = records()['981000001']['application_facts']
        assert facts == dict(captured_at=facts['captured_at'], source='outbound', budget_band='500-2000',
                            job_type='fixed', proposals_band='5-15', client_hire_rate_band='30-70%',
                            client_spent_band='1k-10k', payment_verified=True, posted_age_band='<10m',
                            lane='automation', bid_band='above', connects_cost=16), facts
        run('pipeline.py', 'detail', '981000001', '--file', '-', value={'bid_amount': 800})
        run('pipeline.py', 'observe', '981000001', 'applied', stamp(-60), '--source', 'upwork-proposal', '--verified')
        assert records()['981000001']['application_facts'] == facts
        run('pipeline.py', 'set', '981000002', 'applied', '--applied-at', stamp())
        unknown = records()['981000002']['application_facts']
        assert all(unknown[key] == 'unknown' for key in ('budget_band', 'job_type', 'proposals_band',
                   'client_hire_rate_band', 'client_spent_band', 'payment_verified', 'posted_age_band',
                   'lane', 'bid_band', 'connects_cost'))
        import pipeline
        for index, (budget, proposals, hires, spent, age, bid, expected) in enumerate([
            ('$499', 4, 0, 0, 599, 200, ('<500', '<5', 'none', '0', '<10m', 'below')),
            ('$500', 5, 2, 999, 600, 500, ('500-2000', '5-15', '<30%', '<1k', '10-60m', 'within')),
            ('$2,000', 15, 3, 1000, 3600, 2500, ('500-2000', '15-50', '30-70%', '1k-10k', '1-6h', 'above')),
            ('$2,001', 50, 7, 10000, 21600, None, ('>2000', '50+', '30-70%', '1k-10k', '1-6h', 'unknown')),
            ('$20-$40/hr', None, 8, 10001, 21601, 30, ('hourly', 'unknown', '>70%', '>10k', '>6h', 'within')),
        ]):
            job = {'applied_at': stamp(), 'posted_date': stamp(-age), 'budget': budget,
                   'proposals': proposals, 'client': {'hires': hires, 'posted_jobs': 10, 'spent': spent},
                   'details': {'bid_amount': bid}}
            pipeline.freeze_application_facts(job)
            assert tuple(job['application_facts'][key] for key in ('budget_band', 'proposals_band',
                         'client_hire_rate_band', 'client_spent_band', 'posted_age_band', 'bid_band')) == expected
        run('pipeline.py', 'prune')
        assert records()['981000001']['application_facts'] == facts
        assert all(key not in records()['981000001'] for key in ('client', 'budget', 'proposals', 'posted_date'))
        assert all(key not in records()['981000003'] for key in ('client', 'budget', 'proposals'))
        print('SYNTHETIC F1 PASS: bucket boundaries, unknowns, member/verified writers, freeze-once and raw-data prune')
    with fixture('f2') as folder:
        seed([{'id': '982000001'}, {'id': '982000002'}])
        jobdir = folder / 'jobs/982000001'; jobdir.mkdir()
        application = jobdir / 'application.md'; application.write_bytes(b'SYNTHETIC submitted letter\r\n')
        run('pipeline.py', 'sent', '982000001')
        application.write_text('SYNTHETIC revision')
        run('pipeline.py', 'sent', '982000001')
        assert (jobdir / 'application.sent.md').read_bytes() == b'SYNTHETIC submitted letter\r\n'
        assert records()['982000001']['application_sent_copy'] is True
        assert run('pipeline.py', 'sent', '982000002', success=False).returncode != 0
        assert 'application_sent_copy' not in records()['982000002']
        assert 'code/pipeline.py sent <id>' in (ROOT / '.claude/commands/proposal.md').read_text()
        print('SYNTHETIC F2 PASS: submitted byte copy is immutable; missing source fails without a marker; command wired')
    # The existing media fixture executes Loom with mocked binaries and model; no downloads.
    proposal = (ROOT / '.claude/commands/proposal.md').read_text()
    assert 'code/loom.py <id> <url>' in proposal and 'within 15 s' in proposal and 'one ask at the end' in proposal
    with fixture('f3'):
        seed([{'id': '983000001'}])
        record('983000001', {'loom_hook': 'pass'})
        assert records()['983000001']['loom_hook'] == 'pass'
        assert run('pipeline.py', 'record', '983000001', '--file', '-', value={'loom_hook': 'unknown'}, success=False).returncode != 0
        print('SYNTHETIC F3 PASS: Loom execution/skips proven above; transcript hook criteria and pass/fail writer wired')
    with fixture('f4'):
        seed([{'id': '984000001', 'status': 'replied'}, {'id': '984000002', 'status': 'replied'}])
        thread = {'job_id': '984000001', 'room_id': 'synthetic-invite', 'messages_complete': True,
                  'invitation_room': True, 'messages': [
                      {'node': {'id': 'sys', 'from_side': 'system', 'createdDateTime': stamp(-1), 'message': 'Notice'}},
                      {'node': {'id': 'invite', 'from_side': 'client', 'createdDateTime': stamp(), 'kind': 'invite', 'message': 'Invite'}},
                      {'node': {'id': 'answer', 'from_side': 'freelancer', 'createdDateTime': stamp(300), 'message': 'Yes'}}]}
        run('sync.py', 'apply', '--file', '-', value={'threads': [thread]})
        job = records()['984000001']
        assert job['first_reply_s'] == 300 and job['first_reply_at'] == stamp(300) and job['reply_gaps_s'] == []
        run('sync.py', 'apply', '--file', '-', value={'threads': [dict(thread, messages_complete=False, messages=[])]})
        assert records()['984000001']['first_reply_s'] == 300
        zero = dict(thread, job_id='984000002', room_id='synthetic-zero', messages=[
            {'from': 'client', 'at': stamp(), 'text': 'Question'}, {'from': 'me', 'at': stamp(), 'text': 'Answer'}])
        run('sync.py', 'apply', '--file', '-', value={'threads': [zero]})
        assert records()['984000002']['first_reply_s'] == 0
        print('SYNTHETIC F4 PASS: first answer=300s and zero; invitation included, system skipped, partial preserves evidence')
    with fixture('f5'):
        snapshot = {'invitations': [{'job_id': '985000001', 'invitation_id': 'invite-1', 'room_id': 'room-invite',
                                    'title': 'SYNTHETIC invitation', 'url': 'https://synthetic.example/job', 'invited_at': stamp()}],
                    'offers': [{'job_id': '985000002', 'offer_id': 'offer-1', 'state': 'awaiting_your_acceptance'},
                               {'job_id': '985000003', 'offer_id': 'offer-2', 'state': 'awaiting_your_acceptance', 'source': 'invite'}],
                    'proposals': [{'job_id': '985000004', 'proposal_id': 'proposal-1', 'status': 'accepted', 'applied_at': stamp()}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot)
        run('sync.py', 'apply', '--file', '-', value=snapshot)
        jobs = records()
        assert len(jobs) == 4 and jobs['985000001']['source'] == 'invite'
        assert jobs['985000001']['invited_at'] == stamp() and jobs['985000001']['invitation_id'] == 'invite-1'
        assert jobs['985000001']['room_id'] == 'room-invite'
        assert jobs['985000002']['source'] == 'direct_offer' and jobs['985000003']['source'] == 'invite'
        assert jobs['985000004']['application_facts']['source'] == 'outbound'
        invited_proposal = {'invitations': [dict(snapshot['invitations'][0], job_id='985000005')],
                            'proposals': [dict(snapshot['proposals'][0], job_id='985000005')]}
        run('sync.py', 'apply', '--file', '-', value=invited_proposal)
        facts = records()['985000005']['application_facts']
        assert facts['source'] == 'invite'
        record('985000005', {'source': 'direct_offer'})
        assert records()['985000005']['application_facts'] == facts
        print('SYNTHETIC F5 PASS: invitation intake/replay, direct and invite offers, outbound default through sole writer')
    with fixture('f6'):
        seed([{'id': '986000001', 'status': 'call', 'call_at': stamp(-86400 * 2),
               'call_observation': {'source': 'recorder', 'verified': True}},
              {'id': '986000002', 'status': 'call', 'call_at': stamp(-86400 * 2)},
              {'id': '986000003', 'status': 'call', 'call_at': (TODAY - dt.timedelta(days=4)).isoformat()},
              {'id': '986000004', 'status': 'replied'}, {'id': '986000005', 'status': 'call'}])
        before = pathlib.Path(os.environ['BLUEPRINT_JOBS']).read_bytes()
        jobs = records()
        assert pathlib.Path(os.environ['BLUEPRINT_JOBS']).read_bytes() == before
        assert jobs['986000001']['call_held_at'] == stamp(-86400 * 2) and 'call_booked_at' not in jobs['986000001']
        assert jobs['986000002']['call_booked_at'] == stamp(-86400 * 2) and 'call_held_at' not in jobs['986000002']
        assert '986000002' in run('pipeline.py', 'summary').stdout and 'no_show_candidate' in run('pipeline.py', 'list').stdout
        assert json.loads(run('pipeline.py', 'get', '986000003').stdout)['no_show_candidate'] is True
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()
        run('pipeline.py', 'observe', '986000004', 'call_booked', future, '--source', 'upwork-thread', '--verified')
        first = records()['986000004']['call_booked_observation']
        run('pipeline.py', 'observe', '986000004', 'call_booked', future, '--source', 'upwork-thread', '--verified')
        assert records()['986000004']['call_booked_observation'] == first
        record('986000002', {'call_no_show': True})
        assert 'no_show_candidate' not in json.loads(run('pipeline.py', 'get', '986000002').stdout)
        run('pipeline.py', 'observe', '986000005', 'call_held', stamp())
        assert 'call_booked_at' not in records()['986000005']
        print('SYNTHETIC F6 PASS: recorder/scheduled/date-only migration, future booking replay, overdue candidate and confirmed no-show')
    with fixture('f7') as folder:
        seed([{'id': '987000001', 'status': 'call'}, {'id': '987000002', 'status': 'call'}])
        jobdir = folder / 'jobs/987000001'; jobdir.mkdir()
        (jobdir / 'call.md').write_text(f'Call at: {stamp()}\nDuration: 300\nMember: Alex\nAlex: Next step?\nClient: Send it.\n')
        run('call_stats.py', '987000001')
        assert records()['987000001']['call_held_at'] == stamp()
        assert records()['987000001']['call_held_observation']['source'] == 'recorder'
        run('call_stats.py', '987000002')
        assert 'call_held_at' not in records()['987000002']
        sales = (ROOT / '.claude/commands/sales-call-proposal.md').read_text()
        assert 'get_full_transcript' in sales and 'Notes alone still work' in sales and 'Speaker: line' in sales
        print('SYNTHETIC F7 PASS: normalised transcript writes recorder-held event/stats; notes alone do not; fallback command wired')
    with fixture('f8'):
        import pipeline
        day = TODAY - dt.timedelta(days=40)
        day -= dt.timedelta(days=day.weekday())
        def at_day(day, hour=12):
            return dt.datetime.combine(day, dt.time(hour), dt.timezone.utc).isoformat()
        jid = '988000001'
        seed([{'id': jid, 'status': 'replied'}])
        client_at, first_at, anchor = at_day(day, 10), at_day(day, 11), at_day(day)
        messages = [{'from': 'client', 'at': client_at, 'text': 'Question'},
                    {'from': 'me', 'at': first_at, 'text': 'Answer'}, {'from': 'me', 'at': anchor, 'text': 'Details'}]
        def apply(messages, waiting='them'):
            run('sync.py', 'apply', '--file', '-', value={'threads': [{
                'job_id': jid, 'room_id': 'synthetic-silent', 'messages_complete': True,
                'awaiting_reply_from': waiting, 'messages': messages}]})
        apply(messages)
        due3 = pipeline.add_business_days(day, 3)
        due7 = pipeline.add_business_days(day, 7)
        assert records()[jid]['follow_up_plan']['lane'] == 'silent'
        assert records()[jid]['follow_up_plan']['anchor_at'] == anchor
        assert records()[jid]['next_follow_up'] == due3.isoformat()
        late = pipeline.add_business_days(day, 4)
        apply(messages + [{'from': 'me', 'at': at_day(late), 'text': 'SYNTHETIC first follow-up'}])
        job = records()[jid]
        assert job['next_follow_up'] == due7.isoformat() and job['follow_up_history'][-1]['due_on'] == due3.isoformat()
        all_messages = messages + [{'from': 'me', 'at': at_day(late), 'text': 'First follow-up'},
                                   {'from': 'me', 'at': at_day(due7), 'text': 'Second follow-up'}]
        apply(all_messages); apply(all_messages)
        job = records()[jid]
        assert not job.get('follow_up_plan') and job['next_follow_up'] is None
        assert [entry['due_on'] for entry in job['follow_up_history'] if entry['action'] == 'sent'] == [due3.isoformat(), due7.isoformat()]
        reply = pipeline.add_business_days(day, 8)
        apply(all_messages + [{'from': 'client', 'at': at_day(reply), 'text': 'Back now'}], 'you')
        assert records()[jid]['follow_up_plan']['lane'] == 'active'
        assert pipeline.FOLLOW_UP_GAPS['active'] == (1,) and pipeline.FOLLOW_UP_GAPS['reactivation'] == (30, 60)
        print('SYNTHETIC F8 PASS: last-message anchor, business day3/day7, late first send keeps day7, due_on, stop/replay and active reply')
    with fixture('f9'):
        seed([{'id': '989000001', 'status': 'call'}])
        before = records()['989000001']
        run('pipeline.py', 'observe', '989000001', 'proposal_sent', stamp())
        run('pipeline.py', 'observe', '989000001', 'proposal_sent', stamp(60))
        job = records()['989000001']
        assert job['proposal_sent_at'] == stamp() and job['history'] == before['history'] and job['status'] == 'call'
        assert 'observe <id> proposal_sent <ISO time>' in (ROOT / '.claude/commands/sales-call-proposal.md').read_text()
        print('SYNTHETIC F9 PASS: confirmed proposal-sent observation is stable, preserves stage/history and command uses it')
    with fixture('f10') as folder:
        snapshot = {'contracts': [{'job_id': '980000001', 'contract_id': 'fixed-1', 'status': 'active',
                                  'terms': {'type': 'fixed', 'fixed_amount': 2500, 'currency': 'USD', 'start_date': day.isoformat()}},
                                 {'job_id': '980000002', 'contract_id': 'hourly-1', 'status': 'active',
                                  'terms': {'type': 'hourly', 'hourly_rate': 60, 'currency': 'EUR', 'start_date': day.isoformat()}}],
                    'earnings': [{'week_start': day.isoformat(), 'contract_id': 'fixed-1', 'billed': 1200, 'currency': 'USD', 'client_text': 'discard'},
                                 {'week_start': day.isoformat(), 'contract_id': 'hourly-1', 'billed': 900, 'currency': 'EUR'},
                                 {'week_start': day.isoformat(), 'contract_id': 'invalid', 'billed': True, 'currency': 'USD'}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot); run('sync.py', 'apply', '--file', '-', value=snapshot)
        jobs = records()
        assert jobs['980000001']['won_value'] == {'type': 'fixed', 'amount': 2500, 'currency': 'USD', 'start_date': day.isoformat()}
        assert jobs['980000002']['won_value']['amount'] == 60 and jobs['980000002']['won_value']['type'] == 'hourly'
        incomplete = dict(snapshot['contracts'][0], terms={'type': 'fixed', 'fixed_amount': None})
        run('sync.py', 'apply', '--file', '-', value={'contracts': [incomplete]})
        assert records()['980000001']['won_value'] == jobs['980000001']['won_value']
        rows = [json.loads(line) for line in (folder / 'data/earnings.jsonl').read_text().splitlines()]
        assert len(rows) == 2 and all(set(row) == {'week_start', 'contract_id', 'billed', 'currency'} for row in rows)
        print('SYNTHETIC F10 PASS: fixed value/hourly rate, incomplete terms preserve value; numeric earnings dedup and raw text discarded')
    with fixture('f11') as folder:
        snapshot = {'connects': [{'at': stamp(), 'amount': -16, 'reason': 'Application submitted', 'job_id': '980000001', 'jobPost': {'text': 'discard'}},
                                 {'at': stamp(60), 'amount': 10, 'reason': 'SYNTHETIC receipt: verbatim', 'job_id': None},
                                 {'at': stamp(120), 'amount': float('nan'), 'reason': 'invalid', 'job_id': None}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot); run('sync.py', 'apply', '--file', '-', value=snapshot)
        rows = [json.loads(line) for line in (folder / 'data/connects.jsonl').read_text().splitlines()]
        assert rows == [{key: entry[key] for key in ('at', 'amount', 'reason', 'job_id')} for entry in snapshot['connects'][:2]]
        assert sum(row['amount'] for row in rows) == -6
        print('SYNTHETIC F11 PASS: signed spend/receipt, verbatim reason, four-key dedup, no raw job payload and invalid number skipped')
    brief = (ROOT / '.claude/commands/brief.md').read_text()
    assert all(text in brief for text in ('Read invitations', 'list_contracts action=get', 'action=summary',
                                         'action=connects_balance', 'amount.rawValue', 'since last sync'))
    print('SYNTHETIC F12 PASS: invitations, terms, earnings and Connects reads/snapshot wired with bounded read-only pacing')


ANALYTICS_TODAY = dt.date(2026, 10, 14)


def analytics_stamp(day, hour=10, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute), ZoneInfo('Europe/Berlin')).isoformat()


def analytics_sync_marker(folder):
    (folder / 'data/sync.json').write_text(json.dumps({'synced_at': analytics_stamp(ANALYTICS_TODAY, 11)}))


def analytics_rows():
    """Eight weekly cohorts; every expected event is fixed before running analytics."""
    rows = []
    for week in range(8):
        day = dt.date(2026, 8, 24) + dt.timedelta(weeks=week)
        for source, count in (('outbound', 40), ('invite', 20), ('direct_offer', 20)):
            for index in range(count):
                jid = str(970000000 + week * 1000 + len(rows) % 1000)
                row = {'id': jid, 'source': source, 'title': 'SYNTHETIC PRIVATE CLIENT TITLE',
                       'client': {'name': 'SYNTHETIC PRIVATE CLIENT NAME'},
                       'description': 'SYNTHETIC PRIVATE CLIENT WORDS',
                       'found_at': analytics_stamp(day), 'status': 'applied',
                       'history': [], 'last_activity_at': analytics_stamp(day),
                       'notes': 'SYNTHETIC member evidence',
                       'log': [{'at': analytics_stamp(day), 'text': 'analytics job_fit: ' +
                                json.dumps({'state': 'pass' if index < 36 else 'fail',
                                            'reason': 'Fits the member lane'})}]}
                def event(name, at):
                    row[name + '_at'] = at
                    row[name + '_observation'] = {'source': 'member', 'verified': True}
                if source == 'outbound':
                    event('applied', analytics_stamp(day))
                    row['application_facts'] = {'source': source, 'posted_age_band': '<10m' if index < 32 else '10-60m',
                                                'proposals_band': '<5' if index < 30 else '5-15'}
                    row['history'].append({'status': 'applied', 'at': row['applied_at']})
                    if index < 32:
                        event('replied', analytics_stamp(day, 10, 1))
                        row.update(first_reply_s=180, first_reply_at=analytics_stamp(day, 10, 4))
                    if index < 24:
                        event('call_booked', analytics_stamp(day + dt.timedelta(days=1)))
                    if index < 22:
                        event('call_held', analytics_stamp(day + dt.timedelta(days=1), 11))
                    if index < 21:
                        event('proposal_sent', analytics_stamp(day + dt.timedelta(days=1), 11, 10))
                    won = index < 18
                    if index in (22, 23):
                        row['call_no_show'] = True
                    row['follow_up_history'] = [{'action': 'sent', 'lane': 'silent',
                                                 'due_on': (day + dt.timedelta(days=1)).isoformat(),
                                                 'on': (day + dt.timedelta(days=1 if index < 36 else 2)).isoformat(),
                                                 'at': analytics_stamp(day + dt.timedelta(days=1 if index < 36 else 2))}]
                elif source == 'invite':
                    row['application_date_unknown'] = True
                    row['invited_at'] = analytics_stamp(day)
                    if index < 15:
                        event('call_booked', analytics_stamp(day + dt.timedelta(days=1)))
                    if index < 12:
                        row['history'].append({'status': 'offer', 'at': analytics_stamp(day + dt.timedelta(days=1), 12)})
                    won = index < 10
                else:
                    row['application_date_unknown'] = True
                    row['history'].append({'status': 'offer', 'at': analytics_stamp(day)})
                    won = index < 16
                if won:
                    row['status'] = 'won'
                    row['contract_id'] = 'synthetic-' + jid
                    row['history'].append({'status': 'won', 'at': analytics_stamp(day + dt.timedelta(days=2))})
                    row['won_value'] = {'type': 'fixed', 'amount': 100, 'currency': 'USD',
                                        'start_date': (day + dt.timedelta(days=2)).isoformat()}
                elif row.get('call_booked_at'):
                    row['status'] = 'call'
                elif source != 'outbound':
                    row['status'] = 'offer' if row['history'] else 'new'
                elif row.get('replied_at'):
                    row['status'] = 'replied'
                rows.append(row)
    return rows


def analytics_interval(k, n):
    """Independent Wilson oracle, in percent, from the frozen formula."""
    if not n:
        return None, None
    z = 1.959963984540054
    p = k / n
    divisor = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / divisor
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / divisor
    return 100 * (centre - half), 100 * (centre + half)


def analytics_rate_state(k, n, target):
    low, high = analytics_interval(k, n)
    return 'undecided' if not n else 'pass' if low >= target else 'fail' if high < target else 'undecided'


def analytics_event(row, event):
    if row.get(event + '_at'):
        return dt.datetime.fromisoformat(row[event + '_at'])
    values = [dt.datetime.fromisoformat(item['at']) for item in row.get('history', [])
              if item.get('status') == event]
    return min(values) if values else None


def analytics_rate_oracle(rows, today, baseline=False):
    end = dt.datetime.combine(today - dt.timedelta(days=28 if baseline else 0), dt.time(), ZoneInfo('Europe/Berlin'))
    start = end - dt.timedelta(days=28)
    cutoff = end
    definitions = {
        'reply_rate': ('applied', 7, 20, ('replied',), 'outbound'),
        'reply_to_call': ('replied', 14, 50, ('call_booked', 'offer', 'won'), None),
        'booked_to_held': ('call_booked', 2, 90, ('call_held',), None),
        'held_to_proposal': ('call_held', 7, 90, ('proposal_sent',), None),
        'proposal_to_won': ('proposal_sent', 21, 30, ('won',), None),
        'invite_to_call': ('invited', 14, 50, ('call_booked', 'offer', 'won'), 'invite'),
        'offer_to_contract': ('offer', 21, 80, ('won',), None),
    }
    expected = {}
    for key, (entry, maturity, target, successes, source) in definitions.items():
        cohort = [row for row in rows if not row.get('imported')
                  and (source is None or row.get('source', 'outbound') == source)
                  and analytics_event(row, entry) and start <= analytics_event(row, entry) < end
                  and analytics_event(row, entry) + dt.timedelta(days=maturity) <= cutoff]
        k = sum(any(analytics_event(row, event) and analytics_event(row, entry) <= analytics_event(row, event) < cutoff
                    for event in successes) and not (key == 'booked_to_held' and row.get('call_no_show'))
                for row in cohort)
        expected[key] = (k, len(cohort), target)
    return expected


def analytics_payload(snapshot):
    """A member-approved synthetic coaching addition, without client words."""
    value = json.loads(json.dumps(snapshot))
    primary = value['verdict'].get('kpi') or 'reply_rate'
    keys = [primary] + [key for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal')
                        if key != primary][:2]
    value['goals_next'] = [{'stage': value['kpis'][key]['label'], 'kpi': key,
                            'change': 'Use the agreed next step', 'primary': index == 0,
                            'cue': 'When this stage starts', 'action': 'Offer the agreed next step',
                            'fallback': 'Offer one smaller next step',
                            'review_on': (dt.date.fromisoformat(value['window']['end']) + dt.timedelta(days=8)).isoformat()}
                           for index, key in enumerate(keys)]
    value['report'] = 'SYNTHETIC weekly coaching report; nothing new this week.'
    value['community_card']['next_focus'] = value['kpis'][primary]['label']
    value['community_card']['question'] = 'How do you make the next step easier?'
    value['insights_top'] = [{'kind': 'habit', 'text': 'One clear next step keeps work moving',
                              'target': {'view': 'overview', 'element': primary}}]
    value['kpis']['reply_rate']['insight'] = 'One clear next step keeps work moving'
    value['reviews'] = {kind: {'fix': 'Make one next step clear',
                               'example': 'I can offer Tuesday at ten.',
                               'evidence_lead_ids': [], 'goal_ref': keys[index % 3]}
                        for index, kind in enumerate(('application', 'conversation', 'call', 'proposal'))}
    import analytics
    return analytics.prepare_snapshot(value, dt.date.fromisoformat(value['generated_at'][:10]))


def analytics_decisions():
    import analytics
    assert analytics.rate_state(5, 18, 30) == 'undecided'
    assert analytics.rate_state(0, 0, 30) == 'undecided'
    assert analytics.rate_state(0, 40, 30) == 'fail'
    assert analytics.rate_state(40, 40, 90) == 'pass'
    for k, n in ((5, 18), (0, 40), (40, 40), (17, 40), (96, 120)):
        low, high = analytics.wilson(k, n)
        expected = analytics_interval(k, n)
        assert abs(low - expected[0]) < .05 and abs(high - expected[1]) < .05, (k, n, low, high, expected)
    funnel = ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal',
              'proposal_to_won', 'invite_to_call', 'offer_to_contract')
    with fixture('analytics-verdict'):
        base = analytics.compute(ANALYTICS_TODAY)
        for selected in funnel:
            kpis = json.loads(json.dumps(base['kpis']))
            for key in funnel:
                kpis[key].update(k=40, n=40, value=100, low=91.2, high=100, state='pass')
            for key in ('speed_10min', 'first_reply', 'follow_ups_on_time', 'proposal_on_time'):
                kpis[key].update(state='pass')
            kpis[selected].update(k=0, n=40, value=0, low=0, high=8.8, state='fail')
            result = analytics.verdict(kpis)
            assert result['kpi'] == selected and result['state'] == 'confirmed', result
            assert result['mode'] == 'funnel' and result['label'] == "This week's focus", result
            print(f'SYNTHETIC A2 verdict PASS: first failing stage={selected}')
        kpis[funnel[0]].update(state='missing', reason='No measured source')
        kpis[funnel[1]].update(state='undecided')
        kpis[funnel[2]].update(state='fail')
        result = analytics.verdict(kpis)
        assert result['kpi'] == funnel[2]
        assert result['undecided_before'] == list(funnel[:2]), result
        for key in funnel:
            kpis[key].update(state='undecided')
        kpis['weekly_volume'].update(state='fail', value=2, k=2, n=25)
        result = analytics.verdict(kpis)
        assert result['mode'] == 'levers' and result['state'] == 'levers', result
        for key in funnel:
            kpis[key].update(state='pass')
        result = analytics.verdict(kpis)
        assert result['state'] == 'none', result
    print('SYNTHETIC A2 states PASS: independent Wilson intervals; 5 of 18 vs 30% undecided; earlier unknowns, cold-start levers and no failure')


def analytics_boundaries():
    import analytics
    with fixture('analytics-boundaries') as folder:
        analytics_sync_marker(folder)
        zone = ZoneInfo('Europe/Berlin')
        def at(text):
            return dt.datetime.fromisoformat(text).replace(tzinfo=zone).isoformat()
        entries = [('2026-09-16T00:00:00', False), ('2026-09-15T23:59:59', False),
                   ('2026-10-07T00:00:00', False), ('2026-10-07T00:00:01', False),
                   ('2026-10-14T00:00:00', False), ('2026-09-17T10:00:00', True),
                   ('2026-08-19T00:00:00', False), ('2026-09-09T00:00:00', False),
                   ('2026-09-09T00:00:01', False), ('2026-08-23T10:00:00', True)]
        rows = [{'id': str(971000000 + index), 'status': 'replied', 'source': 'outbound',
                 'found_at': at(text), 'applied_at': at(text), 'imported': imported,
                 'replied_at': (dt.datetime.fromisoformat(at(text)) + dt.timedelta(minutes=3)).isoformat(),
                 'history': [{'status': 'applied', 'at': at(text)}]}
                for index, (text, imported) in enumerate(entries)]
        seed(rows)
        before = (folder / 'data/jobs.json').read_bytes()
        result = analytics.compute(ANALYTICS_TODAY)
        reply = result['kpis']['reply_rate']
        assert (reply['k'], reply['n'], reply['value'], reply['baseline']) == (2, 2, 100, 100), reply
        assert set(reply['evidence']) == {'971000000', '971000002'}, reply
        assert (folder / 'data/jobs.json').read_bytes() == before
        no_ledger = result['kpis']['value_per_100_connects']
        assert no_ledger['state'] == 'missing' and no_ledger['value'] is None and no_ledger['reason'], no_ledger
        assert result['north_star']['hourly_billed'] is None
        assert any(row['source'] == 'connects' and row['state'] == 'missing' for row in result['coverage'])
        assert any(row['source'] == 'earnings' and row['state'] == 'missing' for row in result['coverage'])
    with fixture('analytics-pooled') as folder:
        analytics_sync_marker(folder)
        rows = []
        for week, count, success in ((0, 100, 10), (1, 10, 10)):
            day = dt.date(2026, 9, 22) + dt.timedelta(weeks=week)
            for index in range(count):
                row = {'id': str(972000000 + len(rows)), 'status': 'applied', 'source': 'outbound',
                       'applied_at': analytics_stamp(day), 'found_at': analytics_stamp(day)}
                if index < success:
                    row['replied_at'] = analytics_stamp(day, 10, 3)
                rows.append(row)
        seed(rows)
        rate = analytics.compute(ANALYTICS_TODAY)['kpis']['reply_rate']
        assert (rate['k'], rate['n']) == (20, 110) and abs(rate['value'] - 2000 / 110) < .01, rate
    with fixture('analytics-working-hours') as folder:
        analytics_sync_marker(folder)
        day = dt.date(2026, 10, 8)
        rows = []
        for index, minutes in enumerate([1] * 10 + [100]):
            start = dt.datetime.fromisoformat(analytics_stamp(day))
            rows.append({'id': str(973000000 + index), 'status': 'replied', 'source': 'outbound',
                         'first_reply_s': minutes * 60,
                         'first_reply_at': (start + dt.timedelta(minutes=minutes)).isoformat()})
        rows += [{'id': '973000011', 'status': 'replied', 'first_reply_s': 3600,
                  'first_reply_at': analytics_stamp(dt.date(2026, 10, 10), 11)},
                 {'id': '973000012', 'status': 'replied', 'first_reply_s': 300,
                  'first_reply_at': analytics_stamp(day, 9, 4)},
                 {'id': '973000013', 'status': 'replied', 'first_reply_s': 3600,
                  'first_reply_at': analytics_stamp(day, 20)},
                 {'id': '973000014', 'status': 'replied', 'first_reply_s': 0,
                  'first_reply_at': analytics_stamp(day, 18)}]
        seed(rows)
        first = analytics.compute(ANALYTICS_TODAY)['kpis']['first_reply']
        assert first['n'] == 11 and first['value'] == 1 and first['state'] == 'pass', first
        assert first['p75'] == 1, first
    print('SYNTHETIC A2 boundaries PASS: mature cutoffs/current/baseline, imports excluded from rates, missing ledgers, pooled 20/110 and business-hour median/p75')


def analytics_member():
    import analytics
    with fixture('analytics-eight-weeks') as folder:
        rows = analytics_rows()
        hourly = {'id': '979999999', 'status': 'won', 'source': 'direct_offer', 'imported': True,
                  'contract_id': 'synthetic-hourly', 'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 8, 1))}],
                  'won_value': {'type': 'hourly', 'amount': 9999, 'currency': 'USD', 'start_date': '2026-08-01'}}
        run('sync.py', 'apply', '--file', '-', value={
            'earnings': [{'week_start': (dt.date(2026, 8, 24) + dt.timedelta(weeks=index)).isoformat(),
                          'contract_id': 'synthetic-hourly', 'billed': 200, 'currency': 'USD'} for index in range(7)],
            'connects': [{'at': row['applied_at'], 'amount': -16, 'reason': 'Application submitted', 'job_id': row['id']}
                         for row in rows if row.get('applied_at')] +
                        [{'at': analytics_stamp(dt.date(2026, 10, 1)), 'amount': 100, 'reason': 'Receipt', 'job_id': None}]})
        seed(rows + [hourly])
        run('pipeline.py', 'note', rows[-80]['id'], 'analytics job_fit: ' + json.dumps({'state': 'pass', 'reason': 'Fits the member lane'}))
        before = (folder / 'data/jobs.json').read_bytes()
        result = json.loads(run('analytics.py', 'compute', '--today', ANALYTICS_TODAY).stdout)
        assert len(result['kpis']) == 24
        expected = analytics_rate_oracle(rows, ANALYTICS_TODAY)
        baseline = analytics_rate_oracle(rows, ANALYTICS_TODAY, baseline=True)
        for key, (k, n, target) in expected.items():
            row = result['kpis'][key]
            rungs = {'reply_rate': [11, 15, 20], 'reply_to_call': [30, 40, 50],
                     'proposal_to_won': [20, 25, 30], 'invite_to_call': [50]}.get(key, [target])
            target = next((rung for rung in rungs if 100 * k / n < rung), rungs[-1])
            assert (row['k'], row['n'], row['target'], row['state']) == (k, n, target, analytics_rate_state(k, n, target)), (key, row)
            assert row['rungs'] == rungs and row['baseline_phase'] is False, (key, row)
            assert abs(row['value'] - 100 * k / n) < .01, (key, row)
            bk, bn, _ = baseline[key]
            assert abs(row['baseline'] - 100 * bk / bn) < .01, (key, row)
            assert row['delta_pp'] == row['delta'] == 0, (key, row)
            assert row['history'] == [None] * 7 + [row['value']], (key, row)
            low, high = analytics_interval(k, n)
            assert abs(row['low'] - low) < .01 and abs(row['high'] - high) < .01, (key, row)
        other = {
            'won_value': (44, 44, 'undecided', 4600),
            'value_per_100_connects': (176, 2560, 'pass', 546.875),
            'weekly_volume': (40, 25, 'pass', 40),
            'speed_10min': (32, 40, 'pass', 80),
            'first_reply': (32, 32, 'pass', 3),
            'follow_ups_on_time': (36, 40, 'fail', 90),
            'proposal_on_time': (21, 22, 'pass', 2100 / 22),
            'job_fit': (36, 40, 'fail', 90),
            'application_review': (None, None, 'undecided', None),
            'conversation_review': (None, None, 'undecided', None),
            'call_review': (None, None, 'undecided', None),
            'proposal_review': (None, None, 'undecided', None),
            'segments': (None, None, 'undecided', 'nothing new'),
            'behaviour': (None, None, 'undecided', 'nothing new'),
            'lost_reasons': (0, 0, 'undecided', {'stated': 0, 'observed': 0, 'unknown': 0}),
            'goal_effect': (0, 0, 'undecided', None),
            'goal_done': (0, 0, 'undecided', None),
        }
        for key, values in other.items():
            row = result['kpis'][key]
            assert (row['k'], row['n'], row['state']) == values[:3], (key, row, values)
            if isinstance(values[3], (int, float)):
                assert row['baseline'] is not None, (key, row, values)
                assert abs(row['baseline'] - values[3]) < .001, (key, row, values)
            else:
                assert row['baseline'] == values[3], (key, row, values)
        assert result['kpis']['won_value']['value'] == 4600
        assert abs(result['kpis']['value_per_100_connects']['value'] - 710.9375) < .001
        assert result['kpis']['speed_10min']['proposals_under_5'] == {'k': 30, 'n': 40}
        assert result['kpis']['first_reply']['p75'] == 3
        assert result['north_star']['value'] == 4600 and result['north_star']['fixed_value'] == 4400
        assert result['north_star']['hourly_billed'] == 200 and result['north_star']['wins'] == 44
        assert result['north_star']['baseline'] == 4600
        assert result['periods']['activity'] == result['periods']['outcome'] == {'start': '2026-10-07', 'end': '2026-10-13'}
        assert result['periods']['cohort'] == result['window'] == {'start': '2026-09-16', 'end': '2026-10-13'}
        assert set(row['source'] for row in result['coverage']) == {'recorder', 'upwork', 'tracking', 'loom', 'earnings', 'connects'}
        assert result['verdict']['kpi'] == 'booked_to_held' and result['verdict']['state'] == 'confirmed'
        assert result['findings'] == []
        assert result['community_card']['applications'] == 40, result['community_card']
        assert all(set(row) == {'stage', 'count', 'known_value', 'oldest_days', 'stalled'}
                   for strand in result['pipeline'].values() for row in strand)
        assert sum(row['count'] for row in result['pipeline']['outbound']) == 8 * 22
        assert sum(row['count'] for row in result['pipeline']['inbound']) == 8 * 14
        assert (folder / 'data/jobs.json').read_bytes() == before
        analytics_storage(result, folder, rows)
    print('SYNTHETIC A2 member PASS: eight weeks/640 leads/three routes; every one of 24 KPI k/n/state/baseline; value4600=fixed4400+billed200; spend2560 and pooled cohorts')


def analytics_storage(snapshot, folder, rows):
    import analytics
    value = analytics_payload(snapshot)
    goal_input = {'week': value['week'], 'goals': [dict(goal, start='2026-10-14') for goal in value['goals_next']]}
    def rejected(command, payload, *extra):
        result = run('analytics.py', *command, '--file', '-', *extra, value=payload, success=False)
        assert result.returncode != 0, (command, payload, result.stdout)
    duplicate_stage = json.loads(json.dumps(goal_input))
    duplicate_stage['goals'][1]['stage'] = duplicate_stage['goals'][0]['stage']
    rejected(('goals', 'add'), duplicate_stage)
    invalid_primary = json.loads(json.dumps(goal_input))
    invalid_primary['goals'][1]['primary'] = True
    rejected(('goals', 'add'), invalid_primary)
    invalid_week = dict(goal_input, week='2026-W99')
    rejected(('goals', 'add'), invalid_week)
    missing_commitment = json.loads(json.dumps(goal_input))
    del missing_commitment['goals'][0]['fallback']
    rejected(('goals', 'add'), missing_commitment)
    run('analytics.py', 'goals', 'add', '--file', '-', value=goal_input)
    rejected(('goals', 'add'), goal_input)
    changed_agreement = json.loads(json.dumps(value))
    changed_agreement['goals_next'][0]['action'] = 'Change the agreed action without a new agreement'
    rejected(('record',), changed_agreement)
    stored_goals = [json.loads(line) for line in (folder / 'data/goals.jsonl').read_text().splitlines()]
    assert stored_goals == [goal_input]
    bad = dict(value, unexpected='client_text')
    rejected(('record',), bad)
    for timestamp_value in ('junk', '2026-99-99T12:00:00+02:00', '2026-10-14'):
        rejected(('record',), dict(value, generated_at=timestamp_value))
    bad = json.loads(json.dumps(value))
    bad['kpis']['reply_rate']['value'] = 99
    rejected(('record',), bad)
    for key, item in (('target', 777), ('baseline', 777), ('client_text', 'private')):
        bad = json.loads(json.dumps(value))
        bad['kpis']['goal_done'][key] = item
        rejected(('record',), bad)
    for name in ('SYNTHETIC PRIVATE CLIENT NAME', 'SYNTHETIC PRIVATE CLIENT WORDS', 'SYNTHETIC PRIVATE CLIENT TITLE'):
        rejected(('record',), dict(value, report='Do this for ' + name))
    bad = json.loads(json.dumps(value))
    bad['reviews']['application']['fix'] = 'SYNTHETIC PRIVATE CLIENT WORDS'
    rejected(('record',), bad)
    bad = json.loads(json.dumps(value))
    bad['reviews']['application']['example'] = 'SYNTHETIC PRIVATE CLIENT WORDS'
    rejected(('record',), bad)
    run('analytics.py', 'record', '--file', '-', value=value)
    rejected(('record',), value)
    run('analytics.py', 'record', '--file', '-', '--replace', value=value)
    lines = (folder / 'data/analytics-history.jsonl').read_text().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert json.loads(run('analytics.py', 'last').stdout) == stored
    assert analytics.due(ANALYTICS_TODAY + dt.timedelta(days=7)) is False
    assert analytics.due(ANALYTICS_TODAY + dt.timedelta(days=8)) is True
    assert json.loads(run('analytics.py', 'due', '--today', '2026-10-22').stdout) is True
    assert all(secret not in lines[0] for secret in ('SYNTHETIC PRIVATE CLIENT NAME', 'SYNTHETIC PRIVATE CLIENT WORDS', 'SYNTHETIC PRIVATE CLIENT TITLE'))
    assert stored['reviews']['application']['example'] == 'I can offer Tuesday at ten.'
    # Last week's goals separate execution from the independently measured outcome.
    previous = analytics_payload(analytics.compute(ANALYTICS_TODAY - dt.timedelta(days=7)))
    keys = ('booked_to_held', 'first_reply', 'follow_ups_on_time')
    previous_goals = {'week': previous['week'], 'goals': [dict(previous['goals_next'][index],
                      kpi=key, stage=snapshot['kpis'][key]['label'], start='2026-10-07')
                      for index, key in enumerate(keys)]}
    run('analytics.py', 'goals', 'add', '--file', '-', value=previous_goals)
    reviewed = analytics_payload(analytics.compute(ANALYTICS_TODAY))
    assert [goal['effect'] for goal in reviewed['goals_review']] == ['undecided', 'worked', 'not'], reviewed['goals_review']
    assert abs(reviewed['goals_review'][0]['before'] - 6600 / 117) < .001 and reviewed['goals_review'][0]['after'] is None
    assert [(goal['before'], goal['after']) for goal in reviewed['goals_review'][1:]] == [(3, 3), (90, 90)]
    evidence = [row['id'] for row in rows[-80:-76]]
    for index, goal in enumerate(reviewed['goals_review']):
        goal['evidence_lead_ids'] = evidence[:index + 2]
        goal['done_lead_ids'] = evidence[:2] if index < 2 else []
        goal['decision'] = ('adjust', 'keep', 'stop')[index]
    reviewed = analytics.prepare_snapshot(reviewed, ANALYTICS_TODAY)
    run('analytics.py', 'record', '--file', '-', '--replace', value=reviewed)
    stored = json.loads(run('analytics.py', 'last').stdout)
    assert [(goal['done_k'], goal['done_n']) for goal in stored['goals_review']] == [(2, 2), (2, 3), (0, 4)]
    assert [goal['effect'] for goal in stored['goals_review']] == ['undecided', 'worked', 'not']
    assert stored['kpis']['goal_effect']['k'] == 1 and stored['kpis']['goal_effect']['n'] == 3
    assert (stored['kpis']['goal_done']['k'], stored['kpis']['goal_done']['n'], stored['kpis']['goal_done']['state']) == (1, 3, 'fail')
    for key in ('application_review', 'conversation_review', 'call_review', 'proposal_review'):
        assert (stored['kpis'][key]['k'], stored['kpis'][key]['n'], stored['kpis'][key]['state'], stored['kpis'][key]['baseline']) == (0, 1, 'undecided', None)
    print('SYNTHETIC A2 storage PASS: exact schema/numbers/privacy, duplicate/replace and last/due; stage/commitment/week gates; goal execution 2/2,2/3,0/4 apart from undecided/worked/not outcomes')


def analytics_history_and_coaching():
    import analytics
    with fixture('analytics-history') as folder:
        (folder / 'data/earnings.jsonl').write_text('')
        (folder / 'data/connects.jsonl').write_text('')
        rows = []
        for index in range(8):
            day = dt.date(2026, 8, 24) + dt.timedelta(weeks=index)
            row = {'id': str(974000000 + index), 'status': 'won', 'source': 'outbound',
                   'found_at': analytics_stamp(day), 'first_reply_at': analytics_stamp(day, 10, index + 1),
                   'first_reply_s': 60 * (index + 1), 'pitch_url': 'https://synthetic.example/member-proof',
                   'won_value': {'type': 'fixed', 'amount': 100 * (index + 1), 'currency': 'USD', 'start_date': day.isoformat()},
                   'history': [{'status': 'won', 'at': analytics_stamp(day)}]}
            rows.append(row)
            path = folder / 'jobs' / row['id']
            path.mkdir()
            (path / 'call.md').write_text('Member: Alex\nAlex: What is the problem?\nClient: Too many manual steps.\n')
            (path / 'application.sent.md').write_text('SYNTHETIC sent member application')
            (path / 'loom.md').write_text('SYNTHETIC member Loom transcript')
        seed(rows)
        for index, row in enumerate(rows):
            today = dt.date(2026, 8, 26) + dt.timedelta(weeks=index)
            (folder / 'data/sync.json').write_text(json.dumps({'synced_at': analytics_stamp(today, 11)}))
            value = analytics_payload(analytics.compute(today))
            for review in value['reviews'].values():
                review['evidence_lead_ids'] = [row['id']]
            value['reviews']['call'].pop('coverage', None)
            value['reviews']['application'].pop('coverage', None)
            value['reviews']['call']['rubric'] = [{'lead_id': row['id'], 'reviewable': True,
                'points': [{'point': point, 'state': 'not needed' if point == 6 else 'met'} for point in range(1, 10)]}]
            value['reviews']['application']['rubric'] = [{'lead_id': row['id'], 'reviewable': True,
                'points': [{'point': point, 'state': 'met'} for point in range(1, 8)]}]
            reviewed = analytics.prepare_snapshot(value, today)
            for key in ('application_review', 'conversation_review', 'call_review', 'proposal_review'):
                assert (reviewed['kpis'][key]['k'], reviewed['kpis'][key]['n'], reviewed['kpis'][key]['state']) == (1, 1, 'pass')
                assert reviewed['kpis'][key]['baseline'] is None
            coverage = reviewed['reviews']['call']['coverage']
            assert coverage[0]['n'] == coverage[0]['met'] == 1 and coverage[0]['history'][-1] == 100
            assert coverage[5]['n'] == 0 and coverage[5]['not_needed'] == 1 and coverage[5]['history'][-1] is None
            assert reviewed['reviews']['application']['coverage'][0]['n'] == 1
            analytics.record_snapshot(reviewed)
        latest = analytics.last()
        assert latest['north_star']['history'] == [100, 200, 300, 400, 500, 600, 700, 800]
        assert latest['kpis']['first_reply']['history'] == list(range(1, 9))
        assert latest['reviews']['call']['coverage'][0]['history'] == [100] * 8
        assert latest['reviews']['application']['coverage'][0]['history'] == [100] * 8
        assert latest['streak_weeks'] == 8 and len(latest['verdict_history']) == 7
        assert latest['north_star']['baseline'] == 550
        no_labels = folder / 'jobs' / rows[-1]['id'] / 'call.md'
        no_labels.write_text('Unlabelled synthetic notes with no recorded speakers.')
        unknown = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        unknown['reviews']['call'].pop('coverage', None)
        unknown['reviews']['call'].update(evidence_lead_ids=[rows[-1]['id']],
            rubric=[{'lead_id': rows[-1]['id'], 'reviewable': False, 'points': []}])
        reviewed = analytics.prepare_snapshot(unknown, ANALYTICS_TODAY)
        assert reviewed['kpis']['call_review']['state'] == 'missing' and reviewed['kpis']['call_review']['k'] == 0
        unknown['reviews']['call']['rubric'][0].update(reviewable=True, points=[{'point': point, 'state': 'met'} for point in range(1, 10)])
        try:
            analytics.prepare_snapshot(unknown, ANALYTICS_TODAY)
        except ValueError:
            pass
        else:
            raise AssertionError('Unlabelled call was reviewable')
        # A skipped week leaves null in its position and stops the consecutive streak.
        path = folder / 'data/analytics-history.jsonl'
        old = [json.loads(line) for line in path.read_text().splitlines()]
        old = [row for row in old if row['week'] != '2026-W41']
        path.write_text(''.join(json.dumps(row) + '\n' for row in old))
        gap = analytics.compute(ANALYTICS_TODAY)
        assert gap['north_star']['history'][-2] is None and gap['streak_weeks'] == 1
    print('SYNTHETIC A2 history/coaching PASS: eight chronological snapshots, null gaps/streak/baseline550; all four review KPI counts; nine-point coverage/history and unlabelled-call gate')


def analytics_levers_and_imports():
    import analytics
    import cockpit
    with fixture('analytics-levers') as folder:
        analytics_sync_marker(folder)
        (folder / 'context/me.md').write_text('## Bars\nreply_rate: 25\nfirst_reply: 2\nfirst_reply_p75: 10\nweekly_volume: 30\nVolume: 8\nProposal: 33\nreply_to_call: 101\nunknown: 50\n## Weekly goal\n12\n## Working hours\n09:00-18:00 Mon-Fri Europe/Berlin\n')
        assert analytics.bars()['reply_rate'] == 25 and analytics.bars()['reply_to_call'] == 50
        assert analytics.bars()['first_reply'] == 2 and analytics.bars()['weekly_volume'] == 30
        assert cockpit.bars()['Volume'] == 8 and cockpit.bars()['Proposal'] == 33
        path = folder / 'context/me.md'
        path.write_text(path.read_text().replace('weekly_volume: 30\n', ''))
        assert analytics.bars()['weekly_volume'] == 12
        start = dt.datetime.fromisoformat(analytics_stamp(dt.date(2026, 10, 9), 17, 55))
        end = dt.datetime.fromisoformat(analytics_stamp(dt.date(2026, 10, 12), 9, 10))
        assert analytics.working_reply({'first_reply_at': end.isoformat(), 'first_reply_s': (end - start).total_seconds()}) == 15
        rows = [
            {'id': '975000001', 'status': 'applied', 'source': 'outbound', 'found_at': analytics_stamp(dt.date(2026, 10, 1)),
             'status_updated_at': analytics_stamp(dt.date(2026, 10, 1)), 'last_activity_at': analytics_stamp(dt.date(2026, 10, 13)),
             'details': {'price_estimate': 500}, 'next_follow_up': '2026-10-08', 'follow_up_plan': {'lane': 'silent'},
             'follow_up_history': [{'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-09', 'on': '2026-10-09'},
                                   {'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-09', 'on': '2026-10-09'},
                                   {'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-12', 'on': '2026-10-13'}]},
            {'id': '975000002', 'status': 'offer', 'source': 'direct_offer', 'imported': True,
             'found_at': analytics_stamp(dt.date(2026, 10, 2)), 'status_updated_at': analytics_stamp(dt.date(2026, 10, 2)),
             'last_activity_at': analytics_stamp(dt.date(2026, 10, 2)), 'details': {'bid_amount': 700}},
            {'id': '975000003', 'status': 'won', 'source': 'outbound', 'imported': True,
             'applied_at': analytics_stamp(dt.date(2026, 9, 20)), 'replied_at': analytics_stamp(dt.date(2026, 9, 21)),
             'won_value': {'type': 'fixed', 'amount': 700, 'currency': 'USD', 'start_date': '2026-10-08'},
             'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 10, 8))}]},
            {'id': '975000004', 'status': 'won', 'source': 'outbound', 'imported': True,
             'won_value': {'type': 'fixed', 'amount': 400, 'currency': 'USD', 'start_date': '2026-09-10'},
             'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 9, 10))}]},
            {'id': '975000005', 'status': 'lost', 'status_updated_at': analytics_stamp(dt.date(2026, 10, 8))}]
        seed(rows)
        run('pipeline.py', 'note', '975000005', 'analytics lost_reason: ' + json.dumps({'kind': 'stated', 'reason': 'Timing changed'}))
        (folder / 'data/earnings.jsonl').write_text('')
        value = analytics.compute(ANALYTICS_TODAY)
        assert value['north_star']['value'] == value['north_star']['fixed_value'] == 700
        assert value['north_star']['wins'] == 1 and value['north_star']['baseline'] == 100
        assert value['kpis']['reply_rate']['n'] == 0
        assert (value['kpis']['follow_ups_on_time']['k'], value['kpis']['follow_ups_on_time']['n']) == (1, 3)
        assert value['kpis']['lost_reasons']['value'] == {'stated': 1, 'observed': 0, 'unknown': 0}
        applied = next(row for row in value['pipeline']['outbound'] if row['stage'] == 'applied')
        offer = next(row for row in value['pipeline']['inbound'] if row['stage'] == 'offer')
        assert applied == {'stage': 'applied', 'count': 1, 'known_value': 500, 'oldest_days': 13, 'stalled': 0}
        assert offer == {'stage': 'offer', 'count': 1, 'known_value': 700, 'oldest_days': 12, 'stalled': 1}
        (folder / 'data/connects.jsonl').write_text(json.dumps({'at': analytics_stamp(dt.date(2026, 10, 8)),
            'amount': -100, 'reason': 'Application spend', 'job_id': '975000003'}) + '\n')
        path.write_text(path.read_text().replace('## Bars\n', '## Bars\nwon_value: 650\nvalue_per_100_connects: 800\n'))
        monetary = analytics.compute(ANALYTICS_TODAY)
        assert monetary['kpis']['won_value']['target'] == 650 and monetary['kpis']['won_value']['state'] == 'pass'
        assert monetary['kpis']['value_per_100_connects']['value'] == 700 and monetary['kpis']['value_per_100_connects']['target'] == 800
        assert monetary['kpis']['value_per_100_connects']['state'] == 'fail'
        live_missing = analytics.prepare_snapshot({'coverage': [{'source': 'upwork', 'state': 'missing', 'fix': 'Reconnect the connector'}]}, ANALYTICS_TODAY)
        assert live_missing['kpis']['reply_rate']['state'] == 'missing' and live_missing['north_star']['value'] is None
    needed = analytics.cases_needed(5, 18, 30)
    assert needed == 1575
    assert analytics_rate_state(round(5 / 18 * (18 + needed)), 18 + needed, 30) != 'undecided'
    assert analytics.cases_needed(3, 10, 30) is None
    print('SYNTHETIC A2 levers/imports PASS: overrides and legacy bars; weekend business clock15min; due lanes1/3 dedup; imported money700/baseline100 only; stage age vs movement; lost-note writer; live missing source and cases needed')


def analytics_source_and_timezone():
    import analytics
    with fixture('analytics-source-timezone') as folder:
        analytics_sync_marker(folder)
        (folder / 'data/earnings.jsonl').write_text('')
        seed([{'id': '976000001', 'status': 'applied', 'found_at': analytics_stamp(dt.date(2026, 10, 12)),
               'applied_at': analytics_stamp(dt.date(2026, 10, 12))}])
        optional = analytics.compute(ANALYTICS_TODAY)
        assert optional['kpis']['application_review']['state'] == 'undecided'
        assert optional['kpis']['proposal_review']['state'] == 'undecided'
        assert next(row for row in optional['coverage'] if row['source'] == 'tracking')['affects'] == []
        jobdir = folder / 'jobs/976000001'
        jobdir.mkdir()
        (jobdir / 'application.sent.md').write_text('Member wording: please see https://www.loom.com/share/synthetic')
        required = analytics.compute(ANALYTICS_TODAY)
        assert required['kpis']['application_review']['state'] == 'missing'
        (jobdir / 'loom.md').write_text('SYNTHETIC recorded member words')
        present = analytics.compute(ANALYTICS_TODAY)
        assert present['kpis']['application_review']['state'] == 'undecided'
        (folder / 'context/me.md').write_text('## Timezone\nAmerica/New_York\n## Working hours\n09:00-18:00 Mon-Fri\n')
        assert str(analytics.local_zone()) == 'America/New_York'
        # 15:00 UTC is inside New York working hours, but 18:30 UTC is also
        # outside Berlin's hours. The member's zone is authoritative.
        assert analytics.working_reply({'first_reply_at': '2026-10-08T18:30:00+00:00', 'first_reply_s': 300}) == 5
        local = analytics.compute(ANALYTICS_TODAY)
        assert dt.datetime.fromisoformat(local['generated_at']).utcoffset() == dt.timedelta(hours=-4)
    print('SYNTHETIC A2 sources/timezone PASS: optional Loom/tracking retain reviews; used Loom missing until transcript; member New York clock and zoned snapshot')


def package1b():
    import call_stats
    with fixture('meetings') as folder:
        jid = '969000001'
        seed([{'id': jid, 'status': 'call', 'found_at': stamp()}])
        snapshot = {'meetings': [{'job_id': jid, 'room_id': 'synthetic-meeting-room',
                    'booked_at': stamp(300), 'session_id': 'synthetic-session',
                    'held_at': stamp(360), 'duration_s': 300}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot)
        run('sync.py', 'apply', '--file', '-', value=snapshot)
        job = records()[jid]
        for event, at in (('call_booked', stamp(300)), ('call_held', stamp(360))):
            assert job[event + '_at'] == at, job
            assert job[event + '_observation']['source'] == 'upwork-meeting', job
            assert job[event + '_observation']['verified'] is True, job
        assert job.get('call_no_show') is not True
        pages = [{'segments': [{'speaker': 'Alex', 'text': 'What is the problem?'},
                               {'speaker': 'Client', 'text': 'Too many manual steps.'}]},
                 {'segments': [{'speaker': 'Alex', 'text': 'We can automate that.'},
                               {'speaker': 'Client', 'text': 'Please send the scope.'}]}]
        result = run('call_stats.py', jid, '--transcript-json', '-', '--call-at', stamp(360),
                     '--duration-s', '300', '--member', 'Alex', '--source', 'upwork-meeting', value=pages)
        call = folder / 'jobs' / jid / 'call.md'
        text = call.read_text()
        assert 'Call at: ' + stamp(360) in text and 'Duration: 300' in text, text
        assert text.count('Alex: ') == 2 and text.count('Client: ') == 2, text
        assert text.index('What is the problem?') < text.index('Please send the scope.'), text
        job = records()[jid]
        assert job['call_stats']['duration_s'] == 300, job
        assert job['call_held_observation']['source'] == 'upwork-meeting', job
        stats_before = json.loads(json.dumps(job['call_stats']))
        old = time.time() - 49 * 3600
        os.utime(call, (old, old))
        run('pipeline.py', 'prune')
        assert not call.exists() and records()[jid]['call_stats'] == stats_before
    for name in ('brief.md', 'sales-call-proposal.md', 'analytics.md'):
        command = (ROOT / '.claude' / 'commands' / name).read_text()
        assert 'manage_meetings' in command, name
        allowed = {'list', 'list_recaps', 'get_meeting_summary', 'get_full_transcript'}
        import re
        for line in command.splitlines():
            if 'manage_meetings' in line:
                actions = re.findall(r'action[=:]`?\s*([a-z_]+)', line)
                assert all(action in allowed for action in actions), (name, line)
        if name != 'brief.md':
            assert 'get_full_transcript' in command and 'Enterprise' in command and 'contract' in command
    print('SYNTHETIC B1-B4 PASS: meetings replay gives verified Upwork call events; all transcript pages normalize and call_stats reads; old call.md pruned, derived stats retained; commands use meeting read actions and conditional recorder fallback')


def assert_analytics_additions(value):
    """Validate the frozen additions, independently of analytics' record validator."""
    required = {'periods', 'coverage', 'pipeline', 'north_star', 'todos', 'cohorts',
                'daily_applications', 'reply_time_hist', 'speed_curve', 'segments', 'forecast',
                'call_rubric_weeks', 'insights_top', 'community_card', 'badges'}
    assert required <= value.keys(), required - value.keys()
    assert set(value['periods']) == {'activity', 'cohort', 'outcome', 'synced_at'}
    for name in ('activity', 'cohort', 'outcome'):
        for key in ('start', 'end'):
            dt.date.fromisoformat(value['periods'][name][key])
    for row in value['coverage']:
        assert {'source', 'state', 'affects', 'fix'} <= row.keys()
        assert row['source'] in ('recorder', 'upwork', 'tracking', 'loom', 'earnings', 'connects')
        assert row['state'] in ('ok', 'missing', 'stale') and isinstance(row['affects'], list)
    assert {'wins', 'fixed_value', 'hourly_billed'} <= value['north_star'].keys()
    assert set(value['pipeline']) == {'outbound', 'inbound'}
    for rows in value['pipeline'].values():
        assert all({'stage', 'count', 'known_value', 'oldest_days', 'stalled'} <= row.keys() for row in rows)
    assert value['verdict']['label'] == "This week's focus"
    assert value['verdict']['state'] in ('confirmed', 'levers', 'none')
    assert isinstance(value['verdict']['undecided_before'], list)
    for row in value['kpis'].values():
        if row['layer'] == 'funnel':
            assert 'cases_needed' in row
            assert {'delta_pp', 'bypass', 'own_benchmark', 'rungs', 'rung_reached', 'baseline_phase'} <= row.keys()
            assert 0 <= row['rung_reached'] <= len(row['rungs'])
    assert len(value['todos']) <= 7
    dues = []
    for row in value['todos']:
        assert {'text', 'lead_id', 'due', 'kind'} <= row.keys()
        assert row['kind'] in ('follow_up', 'stalled', 'no_show_confirm', 'proposal_due', 'goal')
        if row['due']:
            dt.date.fromisoformat(row['due'][:10])
            dues.append(row['due'])
    assert dues == sorted(dues), value['todos']
    assert len(value['cohorts']) <= 8 and len(value['daily_applications']) == 84
    for row in value['cohorts']:
        assert {'week', 'applied', 'replied', 'call', 'won', 'lead_ids'} <= row.keys()
        assert isinstance(row['lead_ids'], dict)
    for row in value['daily_applications']:
        assert {'date', 'count', 'lead_ids'} <= row.keys()
        dt.date.fromisoformat(row['date'])
        assert row['count'] == len(row['lead_ids'])
    assert {row['bucket'] for row in value['reply_time_hist']} == {'<5m', '5-15m', '15-60m', '1-4h', '>4h'}
    assert {row['bucket'] for row in value['speed_curve']} == {'<10m', '10-60m', '1-6h', '>6h'}
    for row in value['speed_curve']:
        assert {'bucket', 'k', 'n', 'rate', 'market_line'} <= row.keys()
        assert 0 <= row['k'] <= row['n']
    for row in value['segments']:
        assert {'dimension', 'value', 'k', 'n', 'observed', 'expected', 'lead_ids'} <= row.keys()
        assert row['expected'] is None
    assert {'next_30_days', 'by_stage'} <= value['forecast'].keys()
    for row in value['forecast']['by_stage']:
        assert {'stage', 'count', 'known_value', 'own_rate', 'expected'} <= row.keys()
        if row['own_rate'] is None:
            assert row['expected'] is None
    for row in value['call_rubric_weeks']:
        assert {'week', 'points', 'calls'} <= row.keys()
        assert set(row['points']) == set(map(str, range(1, 10)))
    assert len(value['insights_top']) <= 3
    for row in value['insights_top']:
        assert row['kind'] in ('leak', 'driver', 'trend', 'habit', 'pipeline', 'learning', 'market')
        assert len(row['text'].split()) <= 12 and set(row['target']) == {'view', 'element'}
    card = value['community_card']
    assert {'week', 'applications', 'reply_rate', 'reply_to_call', 'call_to_won',
            'first_reply_median_min', 'goals_done', 'goals', 'biggest_improvement',
            'streak_weeks', 'won_value', 'next_focus', 'question', 'new_badge', 'top_badges'} <= card.keys()
    for key in ('reply_rate', 'reply_to_call', 'call_to_won'):
        assert {'value', 'target', 'rung_reached', 'of', 'trend'} <= card[key].keys()
        assert card[key]['trend'] in ('up', 'flat', 'down')
    assert card['reply_rate']['target'] == 20 and card['reply_to_call']['target'] == 50
    assert card['call_to_won']['target'] == 30 and card['first_reply_target_min'] == 5
    assert len(card['top_badges']) <= 5
    for goal in card['goals']:
        assert set(goal) == {'text', 'done'} and len(goal['text'].split()) <= 6
        assert isinstance(goal['done'], bool)
    for badge in value['badges']:
        assert {'badge', 'tier', 'earned_week', 'new', 'progress_to_next'} <= badge.keys()
        assert badge['tier'] in ('Bronze', 'Silver', 'Gold', 'Platinum', 'Legend')
        assert isinstance(badge['new'], bool) and isinstance(badge['progress_to_next'], str)


def analytics_fix_round():
    import analytics
    for successes, target in ((6, 11), (12, 15)):
        with fixture(f'ladder-{successes}') as folder:
            analytics_sync_marker(folder)
            day = ANALYTICS_TODAY - dt.timedelta(days=14)
            rows = [{'id': str(968000000 + index), 'source': 'outbound', 'status': 'applied',
                     'applied_at': analytics_stamp(day), 'found_at': analytics_stamp(day),
                     'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}}
                    for index in range(100)]
            for row in rows[:successes]:
                row['replied_at'] = analytics_stamp(day, 10, 3)
            # Start the member ten weeks ago, outside the current cohort.
            rows.append({'id': '968999999', 'source': 'outbound', 'status': 'applied',
                         'applied_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(weeks=10))})
            seed(rows)
            value = analytics.compute(ANALYTICS_TODAY)
            assert value['kpis']['reply_rate']['target'] == target, value['kpis']['reply_rate']
            assert value['kpis']['reply_rate']['baseline_phase'] is False
            assert_analytics_additions(value)
    with fixture('baseline-four-weeks') as folder:
        analytics_sync_marker(folder)
        start = ANALYTICS_TODAY - dt.timedelta(weeks=3)
        seed([{'id': '967000001', 'source': 'outbound', 'status': 'applied', 'applied_at': analytics_stamp(start)}])
        for week in range(4):
            value = analytics.compute(start + dt.timedelta(weeks=week))
            for key in analytics.FUNNEL:
                assert value['kpis'][key]['baseline_phase'] is True, (week, key, value['kpis'][key])
                assert value['kpis'][key]['state'] not in ('pass', 'fail'), (week, key, value['kpis'][key])
            assert value['verdict']['kpi'] not in analytics.FUNNEL, value['verdict']
            assert value['kpis']['weekly_volume']['target'] == 25
            assert value['kpis']['speed_10min']['target'] == 80
            assert value['kpis']['first_reply']['target'] == 5
            assert value['kpis']['follow_ups_on_time']['target'] == 100
            assert value['kpis']['proposal_on_time']['target'] == 90
    with fixture('feeding-levers'):
        value = analytics.compute(ANALYTICS_TODAY)
        for outcome, levers in {'reply_rate': ('speed_10min',),
                                'reply_to_call': ('first_reply', 'follow_ups_on_time'),
                                'held_to_proposal': ('proposal_on_time',)}.items():
            for lever in levers:
                kpis = json.loads(json.dumps(value['kpis']))
                for key in analytics.FUNNEL:
                    kpis[key].update(state='pass', baseline_phase=False)
                for key in ('speed_10min', 'first_reply', 'follow_ups_on_time', 'proposal_on_time'):
                    kpis[key].update(state='pass')
                kpis[outcome].update(state='fail', k=0, n=100, value=0)
                kpis[lever].update(state='fail')
                verdict = analytics.verdict(kpis)
                assert verdict['kpi'] == lever and verdict['state'] == 'levers', (outcome, lever, verdict)
    with fixture('todos-bars-forecast') as folder:
        analytics_sync_marker(folder)
        (folder / 'context/me.md').write_text('## Bars\nreply_rate: 25\nreply_to_call: 60\nproposal_to_won: 40\nfirst_reply: 2\n')
        seed([{'id': str(966000000 + index), 'source': 'outbound', 'status': 'replied',
               'found_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(days=20)),
               'last_activity_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(days=1)),
               'next_follow_up': (ANALYTICS_TODAY - dt.timedelta(days=10 - index)).isoformat(),
               'follow_up_plan': {'lane': 'silent'}, 'details': {'price_estimate': 500}}
              for index in range(10)])
        value = analytics.compute(ANALYTICS_TODAY)
        assert_analytics_additions(value)
        assert len(value['todos']) == 7 and all(row['kind'] == 'follow_up' for row in value['todos']), value['todos']
        assert value['todos'][0]['due'] == (ANALYTICS_TODAY - dt.timedelta(days=10)).isoformat()
        assert value['kpis']['reply_rate']['rungs'][-1] == 25
        assert value['community_card']['won_value'] is None
        assert all(row['own_rate'] is None and row['expected'] is None for row in value['forecast']['by_stage'])
        assert value['forecast']['next_30_days'] is None
        payload = analytics_payload(value)
        payload['findings'] = [{'sentence': 'Due follow-ups need a clear next step',
            'action': 'Complete the oldest due follow-up', 'kpi': 'follow_ups_on_time',
            'observed': 0, 'expected': None, 'n': 10, 'strength': 'emerging', 'status': 'emerging'}]
        payload = analytics.prepare_snapshot(payload, ANALYTICS_TODAY)
        assert_analytics_additions(payload)
        for path, change in (('insight', ' '.join(['word'] * 13)), ('market_line', 'Unverified market source')):
            invalid = json.loads(json.dumps(payload))
            invalid['kpis']['reply_rate'][path] = change
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        invalid = json.loads(json.dumps(payload))
        invalid['community_card']['question'] = ' '.join(['word'] * 15)
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        invalid = json.loads(json.dumps(payload))
        invalid['insights_top'][0]['text'] = ' '.join(['word'] * 13)
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        for field in ('cohorts', 'daily_applications', 'reply_time_hist', 'speed_curve', 'segments',
                      'forecast', 'call_rubric_weeks', 'badges', 'todos'):
            invalid = json.loads(json.dumps(payload))
            invalid[field] = {'tampered': True}
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0, field
        invalid = json.loads(json.dumps(payload))
        invalid['kpis']['reply_rate']['external_reference'] = {'value': 11, 'population': 'fabricated',
            'definition': 'fabricated', 'source': 'https://unverified.example', 'date': '2026-10-14'}
        invalid['kpis']['reply_rate']['market_line'] = 'Market11 percent unverified source'
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        invalid = json.loads(json.dumps(payload))
        invalid['findings'] = [{'sentence': 'Unstructured private claim'}]
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        run('analytics.py', 'record', '--file', '-', value=payload)
        stored = json.loads(run('analytics.py', 'last').stdout)
        assert stored['community_card']['next_focus'] == payload['community_card']['next_focus']
        assert stored['community_card']['question'] == payload['community_card']['question']
        assert stored['insights_top'] == payload['insights_top']
        assert stored['findings'] == payload['findings']
        assert stored['kpis']['reply_rate']['insight'] == payload['kpis']['reply_rate']['insight']
    command = (ROOT / '.claude/commands/analytics.md').read_text()
    beats = ('1. What happened:', '2. Where you stand:', '3. Why:', '4. What now:')
    assert all(beat in command for beat in beats)
    assert [command.index(beat) for beat in beats] == sorted(command.index(beat) for beat in beats)
    assert all(text in command for text in ('short conversational markdown', 'community_card.next_focus',
        'community_card.question', 'at most 14 words', 'default targets', 'regardless of `## Bars`'))
    print('SYNTHETIC A2 fix round PASS: reply6%=target11%, reply12%=target15%; first four weeks no rate verdict; four mapped lever focuses; fixed lever targets; every added snapshot field schema-valid; urgent todos capped7; default card despite Bars; undecided forecast null; Claude insight/question/provenance/findings validation and persistence')


def analytics_badges():
    import analytics
    catalogue = ('Harbour Master', 'First Mate', 'Treasure Hunter', 'Swift Sail', "Ship's Bell", 'Lookout',
                 'Steady Anchor', 'Quick Draw', 'Message in a Bottle', 'True North', 'Navigator',
                 'Lighthouse Keeper', 'First Doubloon', 'Back on Course')
    source = (CODE / 'analytics.py').read_text()
    assert all(badge in source for badge in catalogue)
    with fixture('badge-fast-moment') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=2)
        seed([{'id': '965000001', 'source': 'outbound', 'status': 'applied',
               'applied_at': analytics_stamp(date), 'speed_to_lead_s': 120,
               'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}}])
        value = analytics.compute(ANALYTICS_TODAY)
        swift = [row for row in value['badges'] if row['badge'] == 'Swift Sail']
        assert any(row['tier'] == 'Bronze' and row['new'] is True for row in swift), swift
        assert value['community_card']['new_badge'] is not None
        assert not any(row['badge'] in catalogue[:3] for row in value['badges'])
        run('analytics.py', 'record', '--file', '-', value=analytics_payload(value))
        held = analytics.compute(ANALYTICS_TODAY + dt.timedelta(weeks=1))
        swift = [row for row in held['badges'] if row['badge'] == 'Swift Sail']
        assert any(row['tier'] == 'Bronze' and row['new'] is False for row in swift), swift
    with fixture('badge-fast-week') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=2)
        seed([{'id': str(964000000 + index), 'source': 'outbound', 'status': 'applied',
               'applied_at': analytics_stamp(date), 'speed_to_lead_s': 120,
               'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}} for index in range(100)])
        value = analytics.compute(ANALYTICS_TODAY)
        swift = [row for row in value['badges'] if row['badge'] == 'Swift Sail']
        assert any(row['tier'] == 'Silver' and row['new'] is True for row in swift), swift
        assert_analytics_additions(value)
        shelf = [row for row in value['community_card']['top_badges'] if row['badge'] == 'Swift Sail']
        assert len(shelf) == 1 and shelf[0]['tier'] == 'Silver', shelf
        assert not any(row['badge'] in catalogue[:3] for row in value['badges'])
    with fixture('badge-outcome-decidability') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=14)
        rows = [{'id': str(963000000 + index), 'source': 'outbound', 'status': 'replied',
                 'applied_at': analytics_stamp(date), 'replied_at': analytics_stamp(date, 10, 1)} for index in range(10)]
        rows += [{'id': '963999999', 'source': 'outbound', 'status': 'applied',
                  'applied_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(weeks=10))}]
        seed(rows)
        value = analytics.compute(ANALYTICS_TODAY)
        low, _ = analytics_interval(10, 10)
        tiers = {'Bronze': 11, 'Silver': 15, 'Gold': 20, 'Platinum': 25, 'Legend': 30}
        harbour = [row for row in value['badges'] if row['badge'] == 'Harbour Master']
        assert harbour and all(low >= tiers[row['tier']] for row in harbour), harbour
        # A single successful reply is insufficient for the top tier despite 100% observed.
        tiny = [{'id': '963000000', 'source': 'outbound', 'status': 'replied',
                 'applied_at': analytics_stamp(date), 'replied_at': analytics_stamp(date, 10, 1)}, rows[-1]]
        value = analytics.compute(ANALYTICS_TODAY, jobs=tiny)
        assert not any(row['badge'] == 'Harbour Master' and row['tier'] == 'Legend' for row in value['badges']), value['badges']
    print('SYNTHETIC badges PASS: all14 catalogue names; Swift Sail Bronze one120s application/Silver qualifying week; earned kept after broken run; next-tier progress and max5 shelf; outcome tier Wilson lower-bound gate')


def analytics_privacy_and_badge_replace():
    import analytics
    import pipeline
    with fixture('privacy-call') as folder:
        analytics_sync_marker(folder)
        seed([{'id': '962000001', 'source': 'outbound', 'status': 'call',
               'client': 'SYNTHETICSTRINGCLIENT', 'found_at': analytics_stamp(ANALYTICS_TODAY)}])
        jobdir = folder / 'jobs/962000001'
        jobdir.mkdir()
        (jobdir / 'call.md').write_text('Member: Alex\nAlex: I can offer Tuesday at ten.\n'
            'SYNTHETICCALLCLIENT: SYNTHETIC private spoken client sentence.\n')
        payload = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        for secret in ('SYNTHETICSTRINGCLIENT', 'SYNTHETICCALLCLIENT', 'SYNTHETIC private spoken client sentence.'):
            invalid = json.loads(json.dumps(payload))
            invalid['report'] = secret
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0, secret
        invalid = json.loads(json.dumps(payload))
        invalid['reviews']['call']['example'] = 'SYNTHETIC private spoken client sentence.'
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        run('analytics.py', 'record', '--file', '-', value=payload)
        assert json.loads(run('analytics.py', 'last').stdout)['reviews']['call']['example'] == 'I can offer Tuesday at ten.'
    with fixture('badge-same-week-replace') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=2)
        seed([{'id': '961000001', 'source': 'outbound', 'status': 'applied',
               'applied_at': analytics_stamp(date), 'speed_to_lead_s': 120,
               'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}}])
        payload = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        run('analytics.py', 'record', '--file', '-', value=payload)
        # Only pipeline writes synthetic jobs.json; simulate lost native evidence.
        pipeline.save([])
        replacement = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        assert any(row['badge'] == 'Swift Sail' and row['tier'] == 'Bronze'
                   for row in replacement['badges']), replacement['badges']
        run('analytics.py', 'record', '--replace', '--file', '-', value=replacement)
        stored = json.loads(run('analytics.py', 'last').stdout)
        assert any(row['badge'] == 'Swift Sail' and row['tier'] == 'Bronze' for row in stored['badges'])
    print('SYNTHETIC privacy/earned PASS: string-client and transcript-speaker/turn leaks rejected; member example retained; same-week replace preserves earned Swift Sail after native evidence disappears')


def main():
    with fixture('dashboard'):
        s = dashboard_fixture()
        quiet = sum(row['count'] == 0 for row in s['outreach'])
        print(f'SYNTHETIC dashboard PASS: 91→60→60; 60→60→60→60; five n=60 medians; profile=80%/+40; consistency=5/14; weekly total=91/best=60/quiet={quiet}')
    cohorts()
    eligibility()
    reply_and_proposal()
    daily()
    profile_and_retention()
    media()
    clicks()
    review_proofs()
    package1()
    bottlenecks()
    rendered_ui()
    analytics_decisions()
    analytics_boundaries()
    analytics_member()
    analytics_history_and_coaching()
    analytics_levers_and_imports()
    analytics_source_and_timezone()
    package1b()
    analytics_fix_round()
    analytics_badges()
    analytics_privacy_and_badge_replace()
    current = hashlib.sha256(REAL_JOBS.read_bytes()).hexdigest() if REAL_JOBS.exists() else None
    assert current == REAL_HASH, 'Real data/jobs.json changed'
    assert REAL_DATA_HASHES == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in (ROOT / 'data').rglob('*') if path.is_file()}, 'Real data files changed'
    print('PASS: dashboard and weekly analytics numbers reproduced by labelled synthetic fixtures; all real data files unchanged.')


if __name__ == '__main__':
    main()
