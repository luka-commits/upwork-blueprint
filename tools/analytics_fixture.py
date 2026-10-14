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


def feature_command(name, include_base=True):
    """Assert the foreign command's hook, then inspect its relocated feature steps."""
    text = (ROOT / '.claude/commands' / name).read_text()
    if name in ('analytics.md', 'call-review.md'):
        return text + '\n' + (ROOT / 'references/call-transcript.md').read_text()
    assert 'references/analytics-capture.md' in text, name
    baseline = ORIGINAL_RUN(['git', 'diff', '--numstat', 'f7e43b0', '--', '.claude/commands/' + name],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    assert len(baseline) == 1 and int(baseline[0].split()[0]) <= 3 and baseline[0].split()[1] == '0', (name, baseline)
    capture = (ROOT / 'references/analytics-capture.md').read_text()
    title = name[:-3].replace('-', ' ').capitalize()
    marker = '\n## ' + title + '\n'
    assert marker in capture, name
    section = capture.split(marker, 1)[1].split('\n## ', 1)[0]
    shared = capture.split('\n## About me\n', 1)[0]
    result = (text if include_base else '') + '\n' + shared + '\n' + section
    if name in ('brief.md', 'sales-call-proposal.md'):
        assert 'call-transcript.md' in result
        result += '\n' + (ROOT / 'references/call-transcript.md').read_text()
    return result


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
    # Frozen snapshot-only cockpit: retain every legacy numeric proof through pure
    # helpers in this fixture adapter, and prove the real CLI omits live analytics.
    import cockpit
    actual = json.loads(run('cockpit.py', 'state').stdout)
    legacy = {'funnel', 'outreach', 'consistency', 'profile', 'timings', 'bottleneck'}
    assert not legacy.intersection(actual), actual.keys()
    jobs = list(records().values())
    daily, profile, timing = cockpit.consistency(jobs), cockpit.profile_history(), cockpit.timings(jobs)
    return dict(actual, funnel=cockpit.funnel(jobs), outreach=cockpit.outreach(jobs),
                consistency=daily, profile=profile, timings=timing,
                bottleneck=cockpit.bottleneck(jobs, daily, profile, timing))


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
        assert stats == {'duration_s': 300.0, 'talk_share_pct': 41.7, 'question_counts': {'member': 2, 'client': 1}, 'talk_share_basis': 'words', 'transcript_complete': None, 'language': None, 'member_attributed': True}, stats
        (jobdir / 'call.md').write_text('Duration: 300\nNo speaker labels in this synthetic recorder export.\n')
        run('call_stats.py', '995000001')
        stats = records()['995000001']['call_stats']
        assert stats['duration_s'] == 300 and set(stats) == {'duration_s', 'note', 'transcript_complete', 'language'}
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
    sales = feature_command('sales-call-proposal.md')
    proposal = feature_command('proposal.md')
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
                    'references/jobs.md', 'references/goal-library.md', 'references/analytics-capture.md',
                    'references/call-transcript.md', 'references/coach-brief.md', '.claude/commands/call-review.md',
                    '.claude/commands/about-me.md', '.claude/commands/profile.md', '.claude/commands/onboarding.md',
                    '.claude/commands/dashboard.md'}
        legacy = [row for row in result.stdout.splitlines() if row.split('\t')[-1] not in package2]
        delta = sum(int(row.split()[0]) - int(row.split()[1]) for row in legacy)
        if relative == '.claude/commands':
            allowed = {'.claude/commands/brief.md', '.claude/commands/proposal.md',
                       '.claude/commands/sales-call-proposal.md'}
            assert all(row.split('\t')[-1] in allowed for row in legacy)
            assert delta <= 45, (relative, delta)
        else:
            assert delta <= 0, (relative, delta)
    find_jobs = feature_command('find-jobs.md')
    assert find_jobs.count('Analytics due: run /analytics') == 1 and 'code/analytics.py due' in find_jobs
    settings = (ROOT / 'references/jobs.md').read_text()
    assert all(key in settings for key in ('## Bars', '## Analytics day', '## Weekly goal', '## Working hours'))
    assert (commands / 'analytics.md').is_file() and (ROOT / 'references/goal-library.md').is_file()
    application = (CODE / 'application_check.py').read_text()
    assert application.index('import pipeline') < application.index('def ')
    analytics = (ROOT / 'website/components/AnalyticsPage.tsx').read_text()
    # Frozen UI now reads saved focus, k/n and uncertainty; legacy49/50 pure proofs remain.
    assert 'No saved weekly review yet.' in analytics
    assert 'scorecard={list(p.scorecard)}' in analytics and 'snapshot.verdict' in analytics
    # Items17/32 replace the generic metric drawer with the scorecard detail.
    # Bounds stay checked against the writer in rendered_ui; the UI owner verifies display.
    assert 'FunnelScorecard' in analytics and 'onConversations' in analytics
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


def this_week_height_budget(width, total_height, first_screen_bottom):
    """Final browser worker supplies measured CSS pixels, with disclosures closed.

    Height is a reading guideline; do not shorten source text to pass it.
    The first-screen measurement is the bottom of the current-goals section.
    """
    guideline, failure = (1900, 2470) if width == 1440 else (3400, 4420) if width == 390 else (None, None)
    if guideline is None:
        raise ValueError('Measure the agreed 1440 or 390 viewport width.')
    return {'page': 'FAIL' if total_height > failure else 'WARN' if total_height > guideline else 'PASS',
            'first_screen': 'FAIL' if first_screen_bottom > 1170 else 'WARN' if first_screen_bottom > 900 else 'PASS',
            'measured': {'width':width, 'height':total_height, 'first_screen_bottom':first_screen_bottom},
            'limits': {'page_warning':guideline,'page_failure':failure,'first_screen_warning':900,'first_screen_failure':1170}}


def rendered_ui():
    if not (ROOT / 'website/node_modules').is_dir():
        print('audit engineer: rendered UI preflight PASS — SKIP rendered UI: website/node_modules absent; no unrelated dependency fallback')
        return
    with fixture('rendered-ui') as folder:
        me = folder / 'context/me.md'
        me.write_text('Name: Maya Rivers\n' + me.read_text())
        s = dashboard_fixture()
        import analytics
        analytics_sync_marker(pathlib.Path(os.environ['BLUEPRINT_DATA']).parent)
        snapshot = analytics.compute(ANALYTICS_TODAY, now='2026-10-14T15:00:00+02:00')
        js = r"""const assert=require('node:assert/strict');const fs=require('node:fs');
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const {transformSync}=require('next/dist/build/swc');
(async()=>{const funnel=await import('./lib/funnel.mjs');
const {code}=transformSync(fs.readFileSync('components/AnalyticsPage.tsx','utf8'),{
filename:'AnalyticsPage.tsx',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},
target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}});
let current, selected=null, hook=0, injected=false, tab=0, expand=false;const mod={exports:{}};
const contract={exports:{}};
const contractCode=transformSync(fs.readFileSync('lib/analytics-contract.ts','utf8'),{filename:'analytics-contract.ts',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript'},target:'es2020'},module:{type:'commonjs'}}).code;
new Function('require','module','exports',contractCode)(require,contract,contract.exports);
function runtimeRequire(name){
 if(name==='@/lib/analytics-contract')return contract.exports;
 if(name==='react/jsx-runtime'){const jsx=require(name);const wrap=fn=>(type,props,...rest)=>fn(type,expand&&type==='details'?{...props,open:true}:props,...rest);return {...jsx,jsx:wrap(jsx.jsx),jsxs:wrap(jsx.jsxs)};}
 if(name==='react')return {...React,useState:initial=>{const pair=React.useState(initial);return expand&&Array.isArray(initial)&&initial.length===0?[(current?.analytics?.latest?.presentation?.scorecard||[]).map(row=>row.key),pair[1]]:pair;}};
 return require(name);
}
const compiledScorecard={exports:{}};
const scorecardCode=transformSync(fs.readFileSync('components/FunnelScorecard.tsx','utf8'),{filename:'FunnelScorecard.tsx',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}}).code;
new Function('require','module','exports',scorecardCode)(runtimeRequire,compiledScorecard,compiledScorecard.exports);
const compiledCopy={exports:{}};
const copyCode=transformSync(fs.readFileSync('components/CopyButton.tsx','utf8'),{filename:'CopyButton.tsx',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}}).code;
new Function('require','module','exports',copyCode)(name=>name==='@/lib/context'?{useCockpit:()=>({toast:()=>{}})}:require(name),compiledCopy,compiledCopy.exports);
new Function('require','module','exports',code)(name=>{
if(name==='@/lib/analytics-contract')return contract.exports;
if(name==='./FunnelScorecard')return compiledScorecard.exports;
if(name==='./CopyButton')return compiledCopy.exports;
if(name==='@/lib/context')return {useCockpit:()=>({state:current,openDrawer:()=>{}})};
if(name==='react')return {...React,useState:initial=>{const pair=React.useState(initial);hook++;return initial===0?[tab,pair[1]]:!injected&&initial===null&&selected?(injected=true,[selected,pair[1]]):pair;}};
return runtimeRequire(name);},mod,mod.exports);
function render(state){current=state;hook=0;injected=false;return renderToStaticMarkup(React.createElement(mod.exports.default));}
const payload=JSON.parse(process.argv[1]);const populated=payload.legacy, snapshot=payload.snapshot;
const modern={...populated,analytics:{latest:snapshot,history:[snapshot]}};
const html=render(modern);const focusLabel='This week&#x27;s focus';assert(html.includes(focusLabel));
assert(html.indexOf(focusLabel)<html.indexOf('Your funnel, stage by stage'));
assert(html.includes(snapshot.presentation.scorecard.find(row=>row.key===snapshot.verdict.kpi)?.name || snapshot.kpis[snapshot.verdict.kpi].label));
assert(html.includes('Top · finding and applying')&&html.includes('Middle · replies and calls')&&html.includes('Bottom · proposals and wins'));
assert(html.includes('Your funnel, stage by stage')&&!html.includes('Show all numbers')&&!html.includes('More insights'));
assert(html.includes('Funnel Score'));
const callDetail=html.match(/<tr class="sc-detail" id="scorecard-reply_to_call"[^>]*><td[^>]*>([^]*?)<\/td><\/tr>/);
assert(callDetail);assert.equal(callDetail[1],'<button class="an-text-button">Why these replies stalled → Conversations</button>');
tab=1;const conversations=render(modern);assert(conversations.includes('Across your conversations'));
assert(conversations.includes('Applications')&&conversations.includes('Chats')&&conversations.includes('Calls')&&conversations.includes('Proposals'));tab=0;
assert(!/0 of 0/.test(html));assert(html.includes('No opportunities yet'));assert(html.includes('unknown')||html.includes('Not enough evidence'));
const missingMoney={...snapshot,north_star:{...snapshot.north_star,value:null,known_subtotal:0,unknown_value_wins:['synthetic-unknown'],hourly_billed:null}};
const missingMoneyHtml=render({...modern,analytics:{latest:missingMoney,history:[]}});
assert.match(missingMoneyHtml, /Won this week[^]*?Value unknown<\/button>/);
assert.match(missingMoneyHtml, /Billed this week: Value unknown[^]*?separate from won value/);
const missing=render({...modern,analytics:{latest:null,history:[]}});
assert(missing.includes('No saved weekly review yet.'));
const empty=render({...modern,analytics:{latest:{...snapshot,kpis:{},presentation:{},goals_next:[]},history:[]}});
assert(!empty.includes('No saved weekly review yet.'));assert(empty.includes('Scorecard unknown.'));
// Original49/50 and populated66% semantics stay proved against the pure legacy helper.
assert.equal(funnel.funnelSteps(populated.funnel,funnel.PROPOSAL_STEPS).at(-1).overall,100);
assert.equal(funnel.funnelSteps({applied:49,replied:20,call:15},funnel.APPLICATION_STEPS)[1].rate,null);
assert.equal(funnel.funnelSteps({applied:50,replied:20,call:15},funnel.APPLICATION_STEPS)[1].rate,40);
assert.equal(funnel.funnelSteps(populated.funnel,funnel.APPLICATION_STEPS).at(-1).overall,66);
const samples=fs.readFileSync('../tools/sample-snapshots.jsonl','utf8').trim().split('\n').map(JSON.parse);
assert.equal(samples.length,8);
for(const example of samples){const rendered=render({...modern,analytics:{latest:example,history:samples}});
assert(rendered.includes(example.week));assert(rendered.includes('Synthetic example'));
assert(rendered.includes(example.presentation.scorecard.find(row=>row.key===example.verdict.kpi)?.name || example.kpis[example.verdict.kpi].label));}
// Frozen scorecard detail replaces the generic metric drawer; retain k/n, unknown state and source.
const detail={...snapshot,presentation:{...snapshot.presentation,scorecard:snapshot.presentation.scorecard.map(row=>row.key==='reply_rate'?{...row,finished:{k:5,n:18},state:'undecided',insight:'Not enough evidence; observed (call history)',uncertainty:{low:11.4,high:50.9}}:row)}};
const uncertain=render({...modern,analytics:{latest:detail,history:[]}});
assert(uncertain.includes('5 of 18'));
assert(uncertain.includes('Not enough evidence'));assert(uncertain.includes('observed (call history)'));
assert(populated.timings.call_to_proposal.values.some(row=>row.call_source==='observed'));
// PART3 checks rendered member text, including opened details, without attributes or comments.
function memberText(markup){return markup.replace(/<(style|script|title)[^>]*>[^]*?<\/\1>/gi,'').replace(/<!--[^]*?-->/g,'').replace(/<[^>]*>/g,' ').replace(/&#x([0-9a-f]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16))).replace(/&#([0-9]+);/g,(_,n)=>String.fromCodePoint(+n)).replace(/&(?:quot|apos|amp|lt|gt);/g,v=>({'&quot;':'"','&apos;':"'",'&amp;':'&','&lt;':'<','&gt;':'>'}[v])).replace(/\s+/g,' ').trim();}
const forbidden=['not supplied','undecided','eligible',"Writer's",'cohort','Execution and effect apart','stage starts',...Object.keys(contract.exports.ANALYTICS_FIELD_LABELS)];
function forbiddenProof(markup,label){const text=memberText(markup);for(const term of forbidden)assert(!text.toLowerCase().includes(term.toLowerCase()),`${label}: ${term}: ${text}`);assert(!text.includes('—'),label);assert(!/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/i.test(text),`${label}: internal field name: ${text}`);return text;}
expand=true;
for(const [label,state] of [['This week',modern],['Missing money',{...modern,analytics:{latest:missingMoney,history:[]}}],['Missing snapshot',{...modern,analytics:{latest:null,history:[]}}],['Missing data',{...modern,analytics:{latest:{...snapshot,kpis:{},presentation:{},goals_next:[],conversations:{}},history:[]}}]]){
 tab=0;forbiddenProof(render(state),label);tab=1;forbiddenProof(render(state),label+' Conversations');
}
tab=0;
for(const sample of samples)forbiddenProof(render({...modern,analytics:{latest:sample,history:samples}}),'Saved example');
const maya=payload.maya;
const mayaState={...modern,analytics:{latest:maya,history:[],goals:null}};
const mayaHtml=render(mayaState),mayaText=forbiddenProof(mayaHtml,'Maya');
for(const expected of ['88', 'was 81', '$4,200', '3 new contracts', '$3,500', '11 live leads', '31 applications this week against a goal of 25', '26 sent within 10 minutes', 'Reply rate 18% → 21%', 'Swift Sail', 'Silver', 'Turn replies into calls','29 replies led to 9 booked calls','did it 7 of 9','did it 1 of 4','29 of 140','9 of 29','8 of 9','3 of 8','8 of 8'])assert(mayaText.includes(expected),expected);
const goalCards=[...mayaHtml.matchAll(/<article class="an-goal">([^]*?)<\/article>/g)].map(match=>memberText(match[1]));
assert.equal(goalCards.length,3);assert.equal(new Set(goalCards).size,3);
for(const [index,goal] of maya.presentation.goal_cards.entries()){
 assert(goalCards[index].includes(goal.change));assert(goalCards[index].includes('When '+goal.cue));
 assert(goalCards[index].includes('“'+goal.coach_example+'”'));assert(goalCards[index].includes('Checked: '+goal.measurement));
}
assert(!mayaText.includes('Smaller action'));assert(!mayaText.includes('Coach example'));
const duplicate={...maya,goals_next:[...maya.goals_next,maya.goals_next[0]]};
assert.equal((render({...mayaState,analytics:{latest:duplicate}}).match(/class="an-goal"/g)||[]).length,3);
for(const n of [0,1,2,3]){const subset={...maya,goals_next:maya.goals_next.slice(0,n)};assert.equal((render({...mayaState,analytics:{latest:subset}}).match(/class="an-goal"/g)||[]).length,n);}
const zeroGoal={...maya,goals_review:[{change:'Offer two call times',done_k:0,done_n:0,effect:'undecided'}]};
const zeroText=forbiddenProof(render({...mayaState,analytics:{latest:zeroGoal}}),'Zero opportunities');
assert(zeroText.includes('No opportunities this week'));assert(!zeroText.includes('did it 0 of 0'));
// Quotes are source evidence: demonstrate that presentation mapping never rewrites them.
for(const row of maya.presentation.scorecard.filter(row=>['reply_rate','reply_to_call','booked_to_held','proposal_to_won'].includes(row.key)))assert.deepEqual([row.finished.k,row.finished.n],({reply_rate:[29,140],reply_to_call:[9,29],booked_to_held:[8,9],proposal_to_won:[3,8]})[row.key]);
const verifiedQuote="The reply_rate cohort is undecided — eligible is the client's word.";
selected={title:'Quoted review',review:{quote:verifiedQuote,example:verifiedQuote},kind:'chats',evidence:[]};
assert(memberText(render(modern)).includes(verifiedQuote));selected=null;
// Check each actual evidence drawer and call card with every disclosure opened.
for(const selection of [{title:'Missing evidence',evidence:[]},{title:'Call',call:{}},
 {title:'All badges',badges:[{name:'Swift Sail',tier:'Silver',rule:'reply_rate cohort undecided',progress_text:'not supplied'}],history:[{change:'Offer times',done_k:0,done_n:0,effect:'undecided'}]},
 ...['applications','chats','proposals'].flatMap(kind=>[{title:kind,kind,review:{}},{title:kind,kind,review:{last_writer:'not supplied',points:[{key:'answered_question',state:'undecided',reason:'reply_rate cohort'}],missing_sources:[{source:'proposal_sent_at'}]}}]),
 ...Object.entries(snapshot.conversations?.sections||{}).flatMap(([kind,entries])=>entries.map(entry=>({title:entry.label||kind,kind,...(kind==='calls'?{call:entry}:{review:entry}),evidence:[]})))]){
 selected=selection;forbiddenProof(render(modern),'Evidence drawer '+selection.title);
}
selected=null;current=modern;
for(const card of [{},...(snapshot.call_cards||[])])forbiddenProof(renderToStaticMarkup(React.createElement(mod.exports.CallCard,{card})),'Call card');
// Render the owning lead drawer as well; local helper imports and effects make no requests.
let drawerJob=null;
const drawerLibs={};for(const name of ['stages','job-brief','job-facts','next-step','application-review','plain-text','artifact-content'])drawerLibs['@/lib/'+name+'.mjs']=await import('./lib/'+name+'.mjs');
const drawerModule={exports:{}};
const drawerCode=transformSync(fs.readFileSync('components/Drawer.tsx','utf8'),{filename:'Drawer.tsx',swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}}).code;
new Function('require','module','exports',drawerCode)(name=>{
 if(name==='./drawer.css')return {};
 if(name==='./AnalyticsPage')return mod.exports;
 if(name==='./CopyButton')return compiledCopy.exports;
 if(name==='@/lib/context')return {useCockpit:()=>({state:modern,drawerId:'maya-lead',closeDrawer:()=>{},api:()=>{throw Error('Unexpected request')},toast:()=>{}})};
 if(name==='react')return {...React,useState:initial=>{const pair=React.useState(initial);return initial===null?[drawerJob,pair[1]]:pair;}};
 if(drawerLibs[name])return drawerLibs[name];return runtimeRequire(name);
},drawerModule,drawerModule.exports);
for(const job of [null,{id:'maya-lead',title:'Booking flow',status:'call',artifacts:[],call_cards:[{}],lead_context:{proposal_insights:{data:{reply_rate:'undecided',proposal_sent_at:'not supplied'}}}},{id:'maya-lead',title:'Booking flow',status:'new',artifacts:[]}]){
 drawerJob=job;forbiddenProof(renderToStaticMarkup(React.createElement(drawerModule.exports.default)),'Lead drawer');
}
for(const [label,markup] of Object.entries(payload.public_cards))forbiddenProof(markup,'Community '+label);
console.log('PART3 rendered member copy prepared: This week, Conversations, both drawers, calls and community; details open, missing sources and zero opportunities; verified quotes unchanged');
console.log('SYNTHETIC rendered UI PASS: current saved focus first/k/n; missing vs empty snapshot; eight samples; legacy66% and49/50 pure helper; observed call source and Wilson uncertainty');
})().catch(error=>{console.error(error);process.exitCode=1});"""
        from analytics_replay import maya_card_example
        maya = maya_card_example(snapshot)
        public_cards = {'missing':analytics.public_onepager_html(snapshot['community_card'])}
        analytics.add_goals({'week':'2026-W43','goals':[dict(goal,start='2026-10-19') for goal in maya['goals_next']]})
        public_cards['Maya'] = analytics.public_onepager_html(analytics.snapshot_public_card(maya,[]))
        result = ORIGINAL_RUN(['node', '-e', js, json.dumps({'legacy':s,'snapshot':snapshot,'maya':maya,'public_cards':public_cards})], cwd=ROOT / 'website', capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        import analytics
        rates,_=analytics.calculate(list(records().values()),analytics.day(snapshot['generated_at']),now=snapshot['generated_at'],activity_bounds=analytics.span(analytics.day(snapshot['generated_at']),28))
        for row in snapshot['presentation']['scorecard']:
            assert row['uncertainty']=={key:rates[row['key']].get(key) for key in ('low','high')}
        print(result.stdout.strip())
        print('audit engineer E20: rendered UI preflight PASS — executed using declared website dependencies')


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
        run('pipeline.py', 'sent', '982000001', '--confirmed-match')
        application.write_text('SYNTHETIC revision')
        assert run('pipeline.py', 'sent', '982000001', '--confirmed-match', success=False).returncode != 0
        assert (jobdir / 'application.sent.md').read_bytes() == b'SYNTHETIC submitted letter\r\n'
        assert records()['982000001']['application_sent_copy'] is True
        assert run('pipeline.py', 'sent', '982000002', success=False).returncode != 0
        assert 'application_sent_copy' not in records()['982000002']
        assert 'code/pipeline.py sent <id>' in feature_command('proposal.md')
        print('SYNTHETIC F2 PASS: submitted byte copy is immutable; missing source fails without a marker; command wired')
    # The existing media fixture executes Loom with mocked binaries and model; no downloads.
    proposal = feature_command('proposal.md')
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
        assert jobs['985000002']['source'] == 'unknown' and jobs['985000003']['source'] == 'invite'
        assert jobs['985000004']['application_facts']['source'] == 'outbound'
        invited_proposal = {'invitations': [dict(snapshot['invitations'][0], job_id='985000005')],
                            'proposals': [dict(snapshot['proposals'][0], job_id='985000005')]}
        run('sync.py', 'apply', '--file', '-', value=invited_proposal)
        facts = records()['985000005']['application_facts']
        assert facts['source'] == 'invite'
        record('985000005', {'source': 'direct_offer'})
        assert records()['985000005']['application_facts']['source'] == 'direct_offer'
        assert all(records()['985000005']['application_facts'][key] == value for key, value in facts.items() if key != 'source')
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
        assert jobs['986000002']['call_scheduled_at'] == stamp(-86400 * 2) and 'call_held_at' not in jobs['986000002']
        assert '986000002' in run('pipeline.py', 'summary').stdout and 'no_show_candidate' in run('pipeline.py', 'list').stdout
        assert json.loads(run('pipeline.py', 'get', '986000003').stdout)['no_show_candidate'] is True
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()
        assert run('pipeline.py', 'observe', '986000004', 'call_booked', future, '--source', 'upwork-thread', '--verified', success=False).returncode != 0
        record('986000004', {'call_scheduled_at': future})
        run('pipeline.py', 'observe', '986000004', 'call_booked', stamp(), '--source', 'upwork-thread', '--verified')
        first = records()['986000004']['call_booked_observation']
        assert run('pipeline.py', 'observe', '986000004', 'call_booked', future, '--source', 'upwork-thread', '--verified', success=False).returncode != 0
        record('986000004', {'call_scheduled_at': future})
        run('pipeline.py', 'observe', '986000004', 'call_booked', stamp(), '--source', 'upwork-thread', '--verified')
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
        sales = feature_command('sales-call-proposal.md')
        assert 'get_full_transcript' in sales and 'Notes may support a proposal' in sales and 'Speaker: words' in sales
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
        assert 'observe <id> proposal_sent <ISO time>' in feature_command('sales-call-proposal.md')
        print('SYNTHETIC F9 PASS: confirmed proposal-sent observation is stable, preserves stage/history and command uses it')
    with fixture('f10') as folder:
        snapshot = {'contracts': [{'job_id': '980000001', 'contract_id': 'fixed-1', 'status': 'active',
                                  'terms': {'type': 'fixed', 'fixed_amount': 2500, 'currency': 'USD', 'start_date': day.isoformat()}},
                                 {'job_id': '980000002', 'contract_id': 'hourly-1', 'status': 'active',
                                  'terms': {'type': 'hourly', 'hourly_rate': 60, 'currency': 'EUR', 'start_date': day.isoformat()}}],
                    'earnings': [{'week_start': day.isoformat(), 'contract_id': 'fixed-1', 'billed': 1200, 'currency': 'USD', 'client_text': 'discard'},
                                 {'week_start': day.isoformat(), 'contract_id': 'hourly-1', 'billed': 900, 'currency': 'EUR'}]}
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
                                 {'at': stamp(60), 'amount': 10, 'reason': 'SYNTHETIC receipt: verbatim', 'job_id': None}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot); run('sync.py', 'apply', '--file', '-', value=snapshot)
        rows = [json.loads(line) for line in (folder / 'data/connects.jsonl').read_text().splitlines()]
        assert rows == [{key: entry[key] for key in ('at', 'amount', 'reason', 'job_id')} for entry in snapshot['connects'][:2]]
        assert sum(row['amount'] for row in rows) == -6
        print('SYNTHETIC F11 PASS: signed spend/receipt, verbatim reason, four-key dedup, no raw job payload and invalid number skipped')
    brief = feature_command('brief.md')
    assert all(text in brief for text in ('Read invitations', 'list_contracts action=get', 'action=summary',
                                         'action=connects_balance', 'amount.rawValue', 'previous four weeks on every refresh'))
    print('SYNTHETIC F12 PASS: invitations, terms, earnings and Connects reads/snapshot wired with bounded read-only pacing')


ANALYTICS_TODAY = dt.date(2026, 10, 14)


def analytics_stamp(day, hour=10, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute), ZoneInfo('Europe/Berlin')).isoformat()


def analytics_sync_marker(folder):
    import analytics
    (folder / 'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(ANALYTICS_TODAY).isoformat()}))


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
                    if name == 'call_booked': row[name + '_observation']['kind'] = 'booking-confirmed'
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
                        row['call_scheduled_at'] = analytics_stamp(day + dt.timedelta(days=1), 11)
                    if index < 22:
                        event('call_held', analytics_stamp(day + dt.timedelta(days=1), 11))
                        event('call_ended', analytics_stamp(day + dt.timedelta(days=1), 11, 5))
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
                        event('offered', analytics_stamp(day + dt.timedelta(days=1), 12))
                        row['history'].append({'status': 'offer', 'at': analytics_stamp(day + dt.timedelta(days=1), 12)})
                    won = index < 10
                else:
                    row['application_date_unknown'] = True
                    event('offered', analytics_stamp(day))
                    row['history'].append({'status': 'offer', 'at': analytics_stamp(day)})
                    won = index < 16
                if won:
                    row['status'] = 'won'
                    row['contract_id'] = 'synthetic-' + jid
                    event('won', analytics_stamp(day + dt.timedelta(days=2)))
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


def analytics_exact_interval(k, n):
    # Independent binomial-tail inversion, avoiding the producer's implementation.
    import math
    if not n: return None, None
    def tail(p, lower):
        terms = range(k, n + 1) if lower else range(k + 1)
        return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)) for i in terms)
    def solve(lower):
        lo, hi = 0., 1.
        for _ in range(60):
            mid = (lo + hi) / 2
            if (tail(mid, lower) < .025) == lower: lo = mid
            else: hi = mid
        return 100 * (lo + hi) / 2
    return (0. if k == 0 else solve(True), 100. if k == n else solve(False))


def analytics_rate_state(k, n, target):
    # Frozen final spec §3: Wilson decides performance; exact oracle remains for descriptive bounds.
    low, high = analytics_interval(k, n)
    return 'undecided' if not n else 'pass' if low >= target else 'fail' if high < target else 'undecided'


def analytics_event(row, event):
    if event == 'offer' and row.get('offered_at'):
        return dt.datetime.fromisoformat(row['offered_at'])
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
        'reply_to_call': ('replied', 14, 50, ('call_booked', 'offer', 'won'), 'outbound'),
        'booked_to_held': ('call_booked', 2, 90, ('call_held',), 'outbound'),
        'held_to_proposal': ('call_held', 7, 90, ('proposal_sent',), 'outbound'),
        'proposal_to_won': ('proposal_sent', 21, 30, ('won',), 'outbound'),
        'invite_to_call': ('invited', 14, 50, ('call_booked', 'offer', 'won'), 'invite'),
        'offer_to_contract': ('offer', 21, 80, ('won',), 'inbound'),
    }
    expected = {}
    for key, (entry, maturity, target, successes, source) in definitions.items():
        cohort = [row for row in rows if not row.get('imported')
                  and (source is None or (source == 'inbound' and row.get('source', 'outbound') != 'outbound') or row.get('source', 'outbound') == source)
                  and analytics_event(row, entry) and start - dt.timedelta(days=maturity) <= analytics_event(row, entry) < end - dt.timedelta(days=maturity)]
        k = sum(any(analytics_event(row, event) and analytics_event(row, entry) <= analytics_event(row, event) <= analytics_event(row, entry) + dt.timedelta(days=maturity)
                    for event in successes)
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
    value['community_card']['question'] = "How do you practise this week's focus?"
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
        kpis['weekly_volume'].update(state='pass')
        result = analytics.verdict(kpis)
        assert result['state'] == 'none', result
    print('SYNTHETIC A2 states PASS: independent Wilson endpoint and performance classification oracles; 5 of 18 vs 30% undecided; earlier unknowns, cold-start levers and no failure')


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
        assert (reply['k'], reply['n'], reply['value'], reply['baseline']) == (4, 4, 100, 100), reply
        assert set(reply['evidence']) == {'971000000', '971000001', '971000007', '971000008'}, reply
        assert (folder / 'data/jobs.json').read_bytes() == before
        no_ledger = result['kpis']['value_per_100_connects']
        assert no_ledger['state'] == 'missing' and no_ledger['value'] is None and no_ledger['reason'], no_ledger
        assert result['north_star']['hourly_billed'] is None
        assert any(row['source'] == 'connects' and row['state'] == 'missing' for row in analytics.coverage_sources(result['coverage']))
        assert any(row['source'] == 'earnings' and row['state'] == 'missing' for row in analytics.coverage_sources(result['coverage']))
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
        # Frozen §13.6: observed median/p75 decide at n>=10; retain quantile data coverage.
        assert first['n'] == 11 and first['value'] == 1 and first['state'] == 'pass', first
        assert first['p75'] == 1, first
    print('SYNTHETIC A2 boundaries PASS: mature cutoffs/current/baseline, imports excluded from rates, missing ledgers, weighted outbound20/110 and business-hour quantile evidence')


def analytics_member():
    import analytics
    with fixture('analytics-eight-weeks') as folder:
        rows = analytics_rows()
        hourly = {'id': '979999999', 'status': 'won', 'source': 'direct_offer', 'imported': True,
                  'contract_id': 'synthetic-hourly', 'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 8, 1))}],
                  'won_value': {'type': 'hourly', 'amount': 9999, 'currency': 'USD', 'start_date': '2026-08-01'}}
        run('sync.py', 'apply', '--file', '-', value={
            'earnings': [{'week_start': (dt.date(2026, 8, 24) + dt.timedelta(weeks=index)).isoformat(),
                          'contract_id': 'synthetic-hourly', 'billed': 200, 'currency': 'USD'} for index in range(8)],
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
                     'booked_to_held': [70, 80, 90], 'held_to_proposal': [70, 80, 90],
                     'proposal_to_won': [20, 25, 30], 'invite_to_call': [30, 40, 50],
                     'offer_to_contract': [60, 70, 80]}.get(key, [target])  # Frozen §13.1 supplies these rungs.
            target = next((rung for rung in rungs if 100 * k / n < rung), rungs[-1])
            assert (row['k'], row['n'], row['target'], row['state']) == (k, n, target, analytics_rate_state(k, n, target)), (key, row)
            assert row['rungs'] == rungs and row['baseline_phase'] is False, (key, row)
            assert abs(row['value'] - 100 * k / n) < .01, (key, row)
            bk, bn, _ = baseline[key]
            assert abs(row['baseline'] - 100 * bk / bn) < .01, (key, row)
            assert row['delta_pp'] == row['delta'] == 0, (key, row)
            assert row['history'] == [None] * 7 + [row['value']], (key, row)
            # Frozen whiskers use Wilson; preserve the independent exact description proof.
            low, high = analytics_interval(k, n)
            assert abs(row['low'] - low) < .01 and abs(row['high'] - high) < .01
            exact_low, exact_high = analytics_exact_interval(k, n)
            assert abs(row['exact_low'] - exact_low) < .01 and abs(row['exact_high'] - exact_high) < .01, (key, row)
        other = {
            'won_value': (44, 44, 'undecided', 4400),
            'value_per_100_connects': (176, 2560, 'undecided', 515.625),
            'weekly_volume': (36, 25, 'pass', 36),
            'speed_10min': (32, 36, 'pass', 3200 / 36),
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
        assert result['kpis']['won_value']['value'] == 4400
        assert abs(result['kpis']['value_per_100_connects']['value'] - 687.5) < .001
        assert result['kpis']['speed_10min']['proposals_under_5'] == {'k': 30, 'n': 36}
        assert result['kpis']['first_reply']['p75'] == 3
        assert result['north_star']['value'] == 4400 and result['north_star']['fixed_value'] == 4400
        assert result['north_star']['hourly_billed'] == 200 and result['north_star']['wins'] == 44
        assert result['north_star']['baseline'] == 4400
        assert result['periods']['activity'] == result['periods']['outcome'] == {'start': '2026-10-07', 'end': '2026-10-13'}
        assert result['periods']['cohort'] == result['window'] == {'start': '2026-09-16', 'end': '2026-10-13'}
        assert set(row['source'] for row in analytics.coverage_sources(result['coverage'])) == {'recorder', 'upwork', 'tracking', 'loom', 'earnings', 'connects'}
        assert result['verdict']['kpi'] == 'follow_ups_on_time' and result['verdict']['state'] == 'levers'
        assert result['findings'] == []
        assert result['community_card']['applications'] == 36, result['community_card']
        assert all(set(row) == ({'stage', 'count', 'known_value', 'oldest_days', 'stalled', 'proposals_out'} |
                    ({'booked', 'held', 'unknown_call'} if row['stage'] == 'call' else set()))
                   for strand in result['pipeline'].values() for row in strand)
        assert sum(row['count'] for row in result['pipeline']['outbound']) == 8 * 22
        assert sum(row['count'] for row in result['pipeline']['inbound']) == 8 * 14
        assert (folder / 'data/jobs.json').read_bytes() == before
        analytics_storage(result, folder, rows)
    print('SYNTHETIC A2 member PASS: eight weeks/640 leads/three routes; every one of 24 KPI k/n/state/baseline; value4400=fixed4400; billed200 separate; spend2560; strand-specific fixed-horizon cohorts')


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
    assert analytics.due(ANALYTICS_TODAY + dt.timedelta(days=7)) is True
    assert analytics.due(ANALYTICS_TODAY + dt.timedelta(days=8)) is True
    assert json.loads(run('analytics.py', 'due', '--today', '2026-10-22').stdout) is True
    # Frozen31 explicitly introduces private quoted content/lead labels in Conversations.
    # Preserve the original source-leak guard everywhere outside that named private container.
    guarded=json.dumps({key:item for key,item in stored.items() if key!='conversations'})
    assert all(secret not in guarded for secret in ('SYNTHETIC PRIVATE CLIENT NAME', 'SYNTHETIC PRIVATE CLIENT WORDS', 'SYNTHETIC PRIVATE CLIENT TITLE'))
    assert 'SYNTHETIC PRIVATE CLIENT TITLE' in json.dumps(stored['conversations'])
    assert 'SYNTHETIC PRIVATE CLIENT TITLE' not in json.dumps(stored['community_card'])
    assert stored['reviews']['application']['example'] == 'I can offer Tuesday at ten.'
    # Last week's goals separate execution from the independently measured outcome.
    previous = analytics_payload(analytics.compute(ANALYTICS_TODAY - dt.timedelta(days=7)))
    keys = ('booked_to_held', 'first_reply', 'follow_ups_on_time')
    previous_goals = {'week': previous['week'], 'goals': [dict(previous['goals_next'][index],
                      kpi=key, stage=snapshot['kpis'][key]['label'], start='2026-10-07')
                      for index, key in enumerate(keys)]}
    run('analytics.py', 'goals', 'add', '--file', '-', value=previous_goals)
    reviewed = analytics_payload(analytics.compute(ANALYTICS_TODAY))
    # Frozen §13.7: immature remains open; unchanged mature effects are no effect.
    assert [goal['effect'] for goal in reviewed['goals_review']] == ['undecided', 'not', 'not'], reviewed['goals_review']
    assert (reviewed['goals_review'][0]['before_k'], reviewed['goals_review'][0]['before_n']) == (88, 96)  # Frozen §13.7: full28days before start.
    assert abs(reviewed['goals_review'][0]['before'] - 2200 / 24) < .001 and reviewed['goals_review'][0]['after'] is None
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
    # Frozen §13.7: preserve outcome checks independently of execution.
    assert [goal['effect'] for goal in stored['goals_review']] == ['undecided', 'not', 'not']
    assert stored['kpis']['goal_effect']['k'] == 0 and stored['kpis']['goal_effect']['n'] == 3
    assert (stored['kpis']['goal_done']['k'], stored['kpis']['goal_done']['n'], stored['kpis']['goal_done']['state']) == (4, 9, 'fail')
    for key in ('application_review', 'conversation_review', 'call_review', 'proposal_review'):
        assert (stored['kpis'][key]['k'], stored['kpis'][key]['n'], stored['kpis'][key]['state'], stored['kpis'][key]['baseline']) == (0, 1, 'undecided', None)
    print('SYNTHETIC A2 storage PASS: exact schema/numbers/privacy, duplicate/replace and last/due; stage/commitment/week gates; goal execution 2/2,2/3,0/4 apart from mature unchanged no-effect and immature open outcomes; partial actions count4/9')


def analytics_history_and_coaching():
    import analytics
    with fixture('analytics-history') as folder:
        (folder / 'data/earnings.jsonl').write_text('')
        (folder / 'data/connects.jsonl').write_text('')
        rows = []
        for index in range(8):
            day = dt.date(2026, 8, 24) + dt.timedelta(weeks=index)
            row = {'id': str(974000000 + index), 'status': 'won', 'source': 'outbound',
                   'found_at': analytics_stamp(day), 'call_held_at': analytics_stamp(day),
                   'proposal_sent_at': analytics_stamp(day, 11), 'application_sent_verified': True,
                   'first_reply_at': analytics_stamp(day, 10, index + 1),
                   'first_reply_s': 60 * (index + 1), 'pitch_url': 'https://synthetic.example/member-proof',
                   'won_value': {'type': 'fixed', 'amount': 100 * (index + 1), 'currency': 'USD', 'start_date': day.isoformat()},
                   'history': [{'status': 'won', 'at': analytics_stamp(day)}]}
            rows.append(row)
            path = folder / 'jobs' / row['id']
            path.mkdir()
            (path / 'call.md').write_text('Member: Alex\nComplete: yes\nLanguage: English\nAlex: What is the problem?\nClient: Too many manual steps.\n')
            (path / 'thread.json').write_text('{}')
            (path / 'proposal.md').write_text('Synthetic member sent proposal')
            (path / 'application.sent.md').write_text('SYNTHETIC sent member application')
            (path / 'loom.md').write_text('SYNTHETIC member Loom transcript')
        seed(rows)
        for index, row in enumerate(rows):
            today = dt.date(2026, 8, 26) + dt.timedelta(weeks=index)
            (folder / 'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(today).isoformat()}))
            value = analytics_payload(analytics.compute(today))
            for review in value['reviews'].values():
                review['evidence_lead_ids'] = [row['id']]
            value['reviews']['call'].pop('coverage', None)
            value['reviews']['application'].pop('coverage', None)
            value['reviews']['call']['rubric'] = [{'lead_id': row['id'], 'reviewable': True,
                'points': [{'point': point, 'state': 'not needed' if point == 6 else 'met', 'reason': 'No separate objection occurred' if point == 6 else ''} for point in range(1, 10)]}]
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
        # Final §19: a skipped full week is reconstructed from dated sources; missing current-state facts stay unknown.
        path = folder / 'data/analytics-history.jsonl'
        old = [json.loads(line) for line in path.read_text().splitlines()]
        reconstructed_value = next(row['north_star']['value'] for row in old if row['week']=='2026-W41')
        old = [row for row in old if row['week'] != '2026-W41']
        path.write_text(''.join(json.dumps(row) + '\n' for row in old))
        gap = analytics.compute(ANALYTICS_TODAY)
        assert gap['north_star']['history'][-2] == reconstructed_value and gap['streak_weeks'] == 8  # Dated history fills the missed week.
        assert gap['gap']['weeks_missed']==1 and len(path.read_text().splitlines())==7, 'Compute catches up without recording.'
    print('SYNTHETIC A2 history/coaching PASS: eight chronological snapshots, reconstructed dated gaps/baseline550; all four review KPI counts; nine-point coverage/history and unlabelled-call gate')


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
        assert applied == {'stage': 'applied', 'count': 1, 'known_value': 500, 'oldest_days': 13, 'stalled': 0, 'proposals_out': 0}
        assert offer == {'stage': 'offer', 'count': 1, 'known_value': 700, 'oldest_days': 12, 'stalled': 1, 'proposals_out': 0}
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
    assert isinstance(needed, int) and needed > 0
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
        assert next(row for row in analytics.coverage_sources(optional['coverage']) if row['source'] == 'tracking')['affects'] == []
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
        command = feature_command(name)
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
    for row in __import__('analytics').coverage_sources(value['coverage']):
        assert {'source', 'state', 'affects', 'fix'} <= row.keys()
        assert row['source'] in ('recorder', 'upwork', 'tracking', 'loom', 'earnings', 'connects')
        assert row['state'] in ('ok', 'missing', 'stale') and isinstance(row['affects'], list)
    assert {'wins', 'fixed_value', 'hourly_billed'} <= value['north_star'].keys()
    assert set(value['pipeline']) == {'outbound', 'inbound'}
    for rows in value['pipeline'].values():
        assert all({'stage', 'count', 'known_value', 'oldest_days', 'stalled', 'proposals_out'} <= row.keys() for row in rows)
        for row in rows:
            assert 0 <= row['proposals_out'] <= row['count']
            if row['stage'] == 'call':
                assert row['booked'] + row['held'] + row['unknown_call'] == row['count']
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
        assert card[key]['trend'] in ('up', 'undecided', 'down')
    assert card['reply_rate']['target'] == 20 and card['reply_to_call']['target'] == 50
    assert card['call_to_won']['target'] == 30 and card['first_reply_target_min'] == 5
    assert len(card['top_badges']) <= 5
    for goal in card['goals']:
        assert set(goal) == {'text', 'done', 'k', 'n', 'state'} and len(goal['text'].split()) <= 6
        assert isinstance(goal['done'], bool)
    for badge in value['badges']:
        assert {'badge', 'tier', 'earned_week', 'new', 'progress_to_next'} <= badge.keys()
        assert badge['tier'] in ('Bronze', 'Silver', 'Gold', 'Platinum', 'Legend')
        assert isinstance(badge['new'], bool) and isinstance(badge['progress_to_next'], str)


def analytics_fix_round():
    import analytics
    for successes, target in ((6, 11), (12, 11)):
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
        # Frozen §13.4: drop unsafe optional free text without aborting valid compute.
        assert analytics.prepare_snapshot(invalid, ANALYTICS_TODAY)['community_card']['question'] is None
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
    # Frozen21's expert brief supersedes16's fixed paragraph order; every sourced beat remains required.
    assert 'references/coach-brief.md' in command and 'references/chat-report-example.md' in command
    report_command = command.split('## Step 4 · Weekly coaching and report',1)[1]
    assert all(beat in report_command for beat in ('won value versus own history', 'selection, volume',
        'booked and held calls', 'call coaching', 'execution, effect', 'proposed commitments', 'newly earned badges', 'three useful follow-up questions'))
    assert 'No fixed paragraph order' in report_command
    # Frozen public source guards supersede exact old wording; target behavior is numerically tested.
    assert all(text in command for text in ('No graph, forecast chart', 'community_card.next_focus',
        '≤14 words', 'automatic check', 'common 28-day community window', 'Bars'))
    print('SYNTHETIC A2 fix round PASS: reply6%=target11%, reply12%=target11% until Wilson evidence supports promotion; first four weeks no rate verdict; four mapped lever focuses; configurable reasoned lever targets; every added snapshot field schema-valid; urgent todos capped7; default card despite Bars; undecided forecast null; Claude insight/question/provenance/findings validation and persistence')


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
               'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
               'job_fit': {'state': 'pass', 'reason': 'Verified lane and rate fit'},
               'application_review': {'state': 'pass', 'reason': 'Submitted copy fits the agreed problem and offer'},
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
               'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
               'job_fit': {'state': 'pass', 'reason': 'Verified lane and rate fit'},
               'application_review': {'state': 'pass', 'reason': 'Submitted copy fits the agreed problem and offer'},
               'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}} for index in range(100)])
        value = analytics.compute(ANALYTICS_TODAY)
        swift = [row for row in value['badges'] if row['badge'] == 'Swift Sail']
        assert any(row['tier'] == 'Bronze' and row['new'] is True for row in swift) and not any(row['tier'] == 'Silver' for row in swift), swift
        assert_analytics_additions(value)
        shelf = [row for row in value['community_card']['top_badges'] if row['badge'] == 'Swift Sail']
        assert len(shelf) == 1 and shelf[0]['tier'] == 'Bronze', shelf
        assert not any(row['badge'] in catalogue[:3] for row in value['badges'])
    with fixture('badge-outcome-decidability') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=14)
        rows = [{'id': str(963000000 + index), 'source': 'outbound', 'status': 'replied',
                 'applied_at': analytics_stamp(date), 'replied_at': analytics_stamp(date, 10, 1)} for index in range(20)]
        rows += [{'id': '963999999', 'source': 'outbound', 'status': 'applied',
                  'applied_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(weeks=10))}]
        seed(rows)
        value = analytics.compute(ANALYTICS_TODAY)
        low, _ = analytics_exact_interval(20, 20)
        tiers = {'Bronze': 11, 'Silver': 15, 'Gold': 20, 'Platinum': 25, 'Legend': 30}
        harbour = [row for row in value['badges'] if row['badge'] == 'Harbour Master']
        assert harbour and all(low >= tiers[row['tier']] for row in harbour), harbour
        # A single successful reply is insufficient for the top tier despite 100% observed.
        tiny = [{'id': '963000000', 'source': 'outbound', 'status': 'replied',
                 'applied_at': analytics_stamp(date), 'replied_at': analytics_stamp(date, 10, 1)}, rows[-1]]
        value = analytics.compute(ANALYTICS_TODAY, jobs=tiny)
        assert not any(row['badge'] == 'Harbour Master' and row['tier'] == 'Legend' for row in value['badges']), value['badges']
    print('SYNTHETIC badges PASS: all14 catalogue names; Swift Sail Bronze one quality-checked qualifying week; Silver requires three qualifying weeks; earned kept after broken run; next-tier progress and max5 shelf; outcome tier Wilson lower-bound gate')


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
               'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
               'job_fit': {'state': 'pass', 'reason': 'Verified lane and rate fit'},
               'application_review': {'state': 'pass', 'reason': 'Submitted copy fits the agreed problem and offer'},
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



def audit_command_and_publication():
    import application_check
    import pitch_deploy
    import pitch_check
    application = 'Your reporting dashboard needs reliable source data. I can map the fields and build a small sample. Which source should the sample use?'
    assert application_check.check(application, ready=True)[0] == []
    assert application_check.check(application, ready=True, video_required=True)[0]
    assert application_check.check('Answer: ' + 'relevant ' * 180, modality='uma', ready=True)[0] == []
    assert application_check.check(application + ' [LOOM LINK]', ready=True)[0]
    command = (ROOT / '.claude/commands/analytics.md').read_text()
    assert 'For Uma, points 1–3' in command and 'submitted video meets the requested format' in command
    print('audit freelancer F11: application modality PASS — concise text without video accepted; required video enforced; Uma answers use their own length; unresolved placeholder refused')
    command = (ROOT / '.claude/commands/analytics.md').read_text()
    assert '`worked | not | undecided`' in command
    assert 'observed improvement, decline, or unresolved change' in command
    print('audit engineer E13 / stats S19 / freelancer F7 / product P2: goal effect command contract PASS — compatible enum means measured improvement/decline/unresolved, independently of attainment')
    assert 'screening answer, proof, bid/scope, opener or video close' in command
    assert 'rewrite one first sentence' not in command
    print('audit freelancer F20: application repair matches defect PASS — eligibility blocker and actual artifact repair, not unconditional opener')
    assert 'language and transcript completeness' in command and 'unsupported' in command and 'whole-call verdict' in command
    assert ('references/call-transcript.md' in command or '[call-transcript.md](call-transcript.md)' in command) and '--member' in (ROOT/'references/call-transcript.md').read_text()
    print('audit freelancer F19: attributable complete call evidence PASS — known member, language/completeness and unsupported-points gate')
    assert 'at most\nfive cases' in command and 'routine checks have no measured duration claim' in command
    assert 'fifteen minutes' not in command
    print('audit product P11: bounded routine PASS — first-run preparation distinguished; routine focus sample capped at five plus urgent exceptions; no unmeasured duration promise')
    assert 'one to three' in command and 'One to three different stages' in command
    print('audit freelancer F10 / product P5: one to three distinct-stage goals PASS — plan decision retained; no exact-three mandate')
    sales = feature_command('sales-call-proposal.md')
    assert 'agreed proposal next step' in sales and 'scope/pricing options' in sales
    assert 'proposal needs something both sides said yes to' not in feature_command('sales-call-proposal.md', include_base=False)
    print('audit freelancer F21: proposal next-step gate PASS — requested options accepted; assumptions distinguished from accepted delivery scope')
    assert 'reasoned defaults' in command and 'feasible availability' in command and 'require case evidence' in command
    print('audit freelancer F12: feasible reasoned speed commitments PASS — targets configurable; speed misses require case evidence before causal coaching')
    brief = feature_command('brief.md')
    assert 'previous four weeks on every refresh' in brief
    assert 'never claim fresh coverage from a partial write' in brief
    assert 'meeting start as `scheduled_at`' in brief and 'verified booking agreement time' in brief
    assert 'verified `offered_at`' in brief and 'verified `started_at`' in brief
    print('audit engineer E6 / stats S17 / freelancer F4: earnings command refresh PASS — current and recent corrected weeks reread')
    with fixture('audit-publication') as folder:
        seed([{'id': '961000001', 'status': 'new'}, {'id': '961000002', 'status': 'call'}])
        for jid in ('961000001', '961000002'):
            path = folder / 'jobs' / jid
            path.mkdir(exist_ok=True)
            (path / 'pitch.html').write_text('<html><title>Safe</title></html>')
            (path / 'proposal.html').write_text('<html>SYNTHETIC confidential call quotation</html>')
            (path / 'tracking-links.json').write_text(json.dumps({'proposal': {'target': f'https://unrelated.example/{jid}/proposal'}}))
        pages = []
        class Captured(Exception): pass
        def capture(stage, items, current):
            pages.extend(items)
            raise Captured()
        config = {'env': dict(os.environ), 'scope': '', 'token': '', 'project': 'synthetic', 'domain': ''}
        with mock.patch.object(pitch_deploy, 'ROOT', folder), mock.patch.object(pitch_check, 'check_page', return_value=[]), mock.patch.object(pitch_deploy.shutil, 'which', return_value='/synthetic/vercel'), mock.patch.object(pitch_deploy, 'deployment_config', return_value=config), mock.patch.object(pitch_deploy.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), mock.patch.object(pitch_deploy, 'write_site', side_effect=capture):
            try: pitch_deploy.publish('961000001')
            except Captured: pass
        assert pages == [('961000001', folder / 'jobs/961000001/pitch.html')], pages
    print('audit privacy V3: proposal publication leak PASS — registered proposal routes on any host never enter pitch upload; no proposal publication path')


def audit_ingestion():
    import argparse
    import call_stats
    import pipeline
    import sync
    with fixture('audit-identity') as folder:
        run('sync.py', 'apply', '--file', '-', value={})
        terms = {'type': 'fixed', 'fixed_amount': 1200, 'currency': 'USD', 'start_date': (TODAY - dt.timedelta(days=3)).isoformat()}
        contract = {'contract_id': 'audit-c1', 'status': 'active', 'title': 'Same title', 'client_name': 'Client A', 'terms': terms}
        run('sync.py', 'apply', '--file', '-', value={'contracts': [contract]})
        alias = next(iter(records()))
        workspace = folder / 'jobs' / alias
        workspace.mkdir()
        (workspace / 'member-notes.md').write_text('Member-authored evidence')
        seed([{'id': '997200001', 'title': 'Same title', 'status': 'new', 'contract_client': 'Different Client'}])
        run('sync.py', 'apply', '--file', '-', value={'offers': [{'offer_id': 'unrelated-offer', 'state': 'awaiting_your_acceptance', 'title': 'Same title', 'client_name': 'Client B'}]})
        assert records()['997200001']['status'] == 'new'
        real = dict(contract, job_id='997200002')
        proposal = {'job_id': '997200002', 'proposal_id': 'audit-p1', 'status': 'accepted', 'applied_at': stamp(-86400 * 6)}
        run('sync.py', 'apply', '--file', '-', value={'proposals': [proposal], 'contracts': [real]})
        job = records()['997200002']
        assert alias not in records() and job['status'] == 'won' and job['contract_id'] == 'audit-c1'
        assert job['applied_at'] == proposal['applied_at'] and job['won_value']['amount'] == 1200
        assert (folder / 'jobs/997200002/member-notes.md').read_text() == 'Member-authored evidence'
        assert json.loads(run('pipeline.py', 'get', alias).stdout)['id'] == '997200002'
        registry_path=folder/'jobs/997200002/tracking-links.json'
        registry={'preserved-slug': {'kind':'application', 'target':'https://synthetic.example/pitch'}}
        registry_path.write_text(json.dumps(registry))
        import clicks
        click_at=stamp(-86400*6+60)
        clicks.sync_hits([{'job':alias,'slug':'preserved-slug','at':click_at,'bot':False}])
        assert records()['997200002']['pitch_opened_at']==click_at
        assert json.loads((folder/'jobs/997200002/clicks.json').read_text())[0]['job']==alias
        assert json.loads(registry_path.read_text())==registry
        import pitch_deploy
        staged=folder/'staged-alias-site'
        pitch_deploy.write_site(staged, [], '997200002')
        bundled=json.loads((staged/'api/_tracking-links.json').read_text())
        assert bundled[alias]['preserved-slug']['target']==registry['preserved-slug']['target']
        assert bundled['997200002']==bundled[alias]==registry
        assert not list(staged.glob('**/proposal*'))
        print('audit engineer E3: issued alias registry staging PASS — canonical and original public route retain exact target; proposals absent from staged site')
        print('audit engineer E3: alias command/tracking references PASS — old CLI ID and issued-link hit resolve to canonical lead; original URL/hit identity unchanged')
        run('pipeline.py', 'reconcile', alias, '997200002')
        assert records()['997200002']['contract_id'] == 'audit-c1'
        before = len(records())
        run('sync.py', 'apply', '--file', '-', value={'proposals': [proposal], 'contracts': [real]})
        assert len(records()) == before
        run('sync.py', 'apply', '--file', '-', value={'contracts': [dict(contract, contract_id='audit-c2', job_id='997200003')]})
        run('sync.py', 'apply', '--file', '-', value={'contracts': [dict(contract, contract_id='audit-c2')]})
        assert len([j for j in records().values() if j.get('contract_id') == 'audit-c2']) == 1
        print('audit engineer E3: synthetic reconciliation PASS — both discovery orders, replay, observations and workspace preserved')
        print('audit engineer E4: title identity PASS — same-title different-client lead remains unchanged; stable offer identity persisted')
    with fixture('audit-imports') as folder:
        run('sync.py', 'apply', '--file', '-', value={})
        snapshot = {'invitations': [{'job_id': '997200011', 'invitation_id': 'new-invite', 'invited_at': stamp()}],
                    'offers': [{'job_id': '997200012', 'offer_id': 'new-offer', 'state': 'awaiting_your_acceptance', 'source': 'direct_offer', 'offered_at': stamp()}],
                    'contracts': [{'job_id': '997200013', 'contract_id': 'new-contract', 'status': 'active', 'started_at': stamp(), 'terms': {'type': 'hourly', 'hourly_rate': 50, 'weekly_hours': 10, 'currency': 'USD', 'start_date': TODAY.isoformat()}}]}
        run('sync.py', 'apply', '--file', '-', value=snapshot)
        jobs = records()
        assert all(jobs[jid]['imported'] is False for jid in ('997200011', '997200012', '997200013'))
        assert jobs['997200011']['source'] == 'invite' and jobs['997200012']['source'] == 'direct_offer'
        assert jobs['997200013']['source'] == 'unknown'
        assert jobs['997200012']['offered_at'] == stamp() and jobs['997200013']['won_at'] == stamp()
        assert jobs['997200013']['won_value']['amount'] == 50 and jobs['997200013']['won_value']['weekly_hours'] == 10
        import analytics
        assert analytics.contract_value(jobs['997200013']) == 2000
        seed([{'id': '997200014', 'status': 'applied', 'applied_at': stamp()}])
        record('997200014', {'source': 'invite'})
        assert records()['997200014']['application_facts']['source'] == 'invite'
        seed([{'id': '997200016', 'status': 'applied', 'applied_at': stamp(), 'source': 'invite', 'application_facts': {'source': 'outbound'}}])
        record('997200016', {'source': 'invite'})
        assert records()['997200016']['application_facts']['source'] == 'invite'
        print('audit stats S5 / freelancer F2: live imports PASS — new invites, explicit direct offers and contracts after observation start stay eligible')
        print('audit freelancer F2: live inbound source correction PASS — unknown offer origin remains unknown; frozen application source corrected')
        print('audit stats S6: outcome event time PASS — offers/contracts use verified platform times rather than sync discovery')
        print('audit freelancer F1 / stats S15: hourly contract terms PASS — agreed weekly hours retained with rate for booked-value calculation')
    with fixture('audit-financials') as folder:
        empty = {'earnings': [], 'connects': []}
        run('sync.py', 'apply', '--file', '-', value=empty)
        assert (folder / 'data/earnings.jsonl').read_text() == '' and (folder / 'data/connects.jsonl').read_text() == ''
        week = (TODAY - dt.timedelta(days=TODAY.weekday())).isoformat()
        for amount in (100, 250, 125, 125):
            run('sync.py', 'apply', '--file', '-', value={'earnings': [{'week_start': week, 'contract_id': 'money-c1', 'currency': 'USD', 'billed': amount}]})
            rows = [json.loads(line) for line in (folder / 'data/earnings.jsonl').read_text().splitlines()]
            assert len(rows) == 1 and rows[0]['billed'] == amount
        transaction = {'at': stamp(), 'amount': -10, 'reason': 'application', 'job_id': '997200015', 'transaction_id': 'debit-1', 'purpose': 'application', 'settled': False}
        run('sync.py', 'apply', '--file', '-', value={'connects': [transaction]})
        run('sync.py', 'apply', '--file', '-', value={'connects': [dict(transaction, amount=-6, settled=True)]})
        ledger = [json.loads(line) for line in (folder / 'data/connects.jsonl').read_text().splitlines()]
        assert len(ledger) == 1 and ledger[0]['amount'] == -6 and ledger[0]['settled'] is True
        print('audit engineer E7: checked-empty financials PASS — validated empty ledgers exist; omitted sources stay unavailable')
        print('audit engineer E6 / stats S17 / freelancer F4: earnings replace PASS — increases, downward corrections and replay keep the latest contract/week total')
        print('audit stats S17: earnings corrections PASS — authoritative revisions replace provisional observations')
        print('audit freelancer F3 / stats S18: Connects settlement identity PASS — transaction correction replaces rather than double-counts a debit')
    with fixture('audit-partial-sync') as folder:
        run('sync.py', 'apply', '--file', '-', value={})
        before = json.loads((folder / 'data/sync.json').read_text())['synced_at']
        seed([{'id': '997200021', 'status': 'new'}])
        original = sync.subprocess.run
        def rejected(command, *args, **kwargs):
            if len(command) > 2 and str(command[1]).endswith('pipeline.py') and command[2] == 'observe':
                return subprocess.CompletedProcess(command, 1, '', 'SYNTHETIC rejected observation')
            return original(command, *args, **kwargs)
        snapshot = {'proposals': [{'job_id': '997200021', 'proposal_id': 'partial-p1', 'status': 'accepted', 'applied_at': stamp()}]}
        with mock.patch.object(sync.subprocess, 'run', side_effect=rejected), mock.patch.object(sys, 'stdin', io.StringIO(json.dumps(snapshot))), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = sync.cmd_apply(argparse.Namespace(file='-'))
        info = json.loads((folder / 'data/sync.json').read_text())
        assert result == 1 and info['status'] == 'error' and info['errors'] and info['synced_at'] == before
        assert records()['997200021']['status'] == 'applied' and records()['997200021']['application_date_unknown'] is True
        print('audit engineer E5: pipeline failure freshness PASS — partial mutation failure returns nonzero and does not refresh successful sync time')
    with fixture('audit-rooms') as folder:
        seed([{'id': '997200031', 'status': 'won'}])
        def room(rid, offset, delay=None):
            messages = [{'from': 'client', 'at': stamp(offset), 'text': 'Question'}]
            if delay is not None:
                messages.append({'from': 'me', 'at': stamp(offset + delay), 'text': 'Answer'})
            return {'job_id': '997200031', 'room_id': rid, 'messages_complete': True, 'messages': messages}
        run('sync.py', 'apply', '--file', '-', value={'threads': [room('first-room', 0, 300)]})
        run('sync.py', 'apply', '--file', '-', value={'threads': [room('second-room', 86400, 3600)]})
        job = records()['997200031']
        assert job['first_reply_s'] == 300 and sorted(job['reply_gaps_s']) == [300, 3600]
        run('sync.py', 'apply', '--file', '-', value={'threads': [room('pending-room', 86400 + 7200)]})
        job = records()['997200031']
        assert job['room_reply_metrics']['pending-room']['first_reply_at'] is None
        run('sync.py', 'apply', '--file', '-', value={'threads': [dict(room('first-room', 0), messages_complete=False)]})
        assert records()['997200031']['room_reply_metrics']['first-room']['first_reply_s'] == 300
        saved = json.loads((folder / 'jobs/997200031/thread.json').read_text())
        assert set(saved['rooms']) == {'first-room', 'second-room', 'pending-room'}
        print('audit engineer E10: room timing PASS — earlier first answer, gaps and raw room identities survive later/partial room refresh')
        print('audit stats S11: unanswered first replies PASS — complete rooms retain open client-arrival observations')
    with fixture('audit-meetings') as folder:
        seed([{'id': '997200041', 'status': 'replied'}])
        old_schedule = stamp(-86400 * 3)
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat()
        meeting = {'job_id': '997200041', 'session_id': 'session-1', 'booked_at': stamp(-86400 * 5), 'scheduled_at': old_schedule}
        run('sync.py', 'apply', '--file', '-', value={'meetings': [meeting]})
        assert pipeline.no_show_candidate(records()['997200041']) is True
        run('sync.py', 'apply', '--file', '-', value={'meetings': [dict(meeting, scheduled_at=future)]})
        job = records()['997200041']
        assert job['call_booked_at'] == meeting['booked_at'] and job['call_scheduled_at'] == future
        assert pipeline.no_show_candidate(job) is False
        record('997200041', {'call_no_show': True})
        run('sync.py', 'apply', '--file', '-', value={'meetings': [dict(meeting, session_id='session-2', scheduled_at=stamp(), held_at=stamp(), duration_s=3600)]})
        job = records()['997200041']
        assert job['call_no_show'] is False and job['call_ended_at'] == stamp(3600)
        assert set(job['call_sessions']) == {'session-1', 'session-2'}
        text = f'Call at: {stamp()}\nDuration: 3600\nMember: Alex\nComplete: yes\nLanguage: English\nAlex: Next step?\nClient: Yes.\n'
        result = call_stats.analyze(text)
        assert result['call_ended_at'] == stamp(3600) and result['transcript_complete'] is True and result['member_attributed'] is True
        assert 'call_ended_at' not in call_stats.analyze(text.replace('Duration: 3600\n', ''))
        record('997200041', {'call_outcome': 'disqualified', 'proposal_required': False})
        assert records()['997200041']['proposal_required'] is False
        seed([{'id': '997213001', 'status': 'call', 'call_booked_at': stamp(), 'call_booked_observation': {'source': 'upwork-meeting', 'verified': True}}])
        legacy = records()['997213001']
        assert legacy['call_scheduled_at'] == stamp() and 'call_booked_at' not in legacy
        run('pipeline.py', 'observe', '997213001', 'call_booked', stamp(-86400), '--source', 'upwork-meeting', '--verified')
        legacy = records()['997213001']
        assert legacy['call_booked_at'] == stamp(-86400) and legacy['call_booked_observation']['kind'] == 'booking-confirmed' and legacy['call_scheduled_at'] == stamp()
        print('audit stats S8 / freelancer F14: legacy booking PASS — old meeting start never masquerades as agreement; new verified agreement preserves schedule')
        print('audit engineer E11 / freelancer F13: booking reschedule PASS — current scheduled start replaces old schedule without changing booking event')
        print('audit stats S8 / S10 / freelancer F14: booking event and session attendance PASS — future scheduled call counts as booked; replacement attendance clears no-show')
        print('audit engineer E18 / stats S9 / freelancer F15: proposal call end PASS — verified start plus duration yields end; missing duration remains unmeasurable')
        print('audit freelancer F19: attributable complete call record PASS — normalized completeness, language and member identity preserved')
        print('audit stats S10 / freelancer F16 / product P3: clean disqualification writer PASS — qualified proposal requirement recorded separately from held-call evidence')
    import analytics
    for pending_overdue in (False, True):
        for newest_first in (True, False):
            with fixture(f'audit-session-order-{pending_overdue}-{newest_first}') as folder:
                jid='997200042'
                pending_schedule=stamp(-86400*3) if pending_overdue else (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=7)).isoformat()
                seed([{'id':jid,'source':'outbound','status':'call'}])
                old={'job_id':jid,'room_id':'old-room','session_id':'old-held',
                     'booked_at':stamp(-86400*16),'scheduled_at':stamp(-86400*14),
                     'held_at':stamp(-86400*14),'duration_s':300}
                pending={'job_id':jid,'room_id':'new-room','session_id':'new-pending',
                         'booked_at':stamp(-86400*8),'scheduled_at':pending_schedule}
                meetings=[pending,old] if newest_first else [old,pending]
                run('sync.py','apply','--file','-',value={'meetings':meetings})
                run('sync.py','apply','--file','-',value={'meetings':meetings})
                current=records()[jid]
                assert current['call_session_id']=='new-pending',current
                assert current['call_scheduled_at']==pending_schedule,current
                assert not current['call_sessions']['new-pending'].get('held_at'),current
                assert current['call_sessions']['old-held']['held_at']==old['held_at'],current
                assert pipeline.no_show_candidate(current) is pending_overdue
                snapshot=analytics.compute(TODAY,now=dt.datetime.now(analytics.local_zone()))
                attendance=snapshot['kpis']['booked_to_held']
                assert (attendance['k'],attendance['n'])==(0,1 if pending_overdue else 0),attendance
                assert any(todo['kind']=='no_show_confirm' for todo in snapshot['todos']) is pending_overdue
    print('audit engineer E11 / freelancer F13 / stats S8,S10: meeting input order PASS — both orders/replay preserve current pending session; overdue attendance0/1 with no-show task; future0/0 without task; historical held preserved')
    with fixture('audit-followup') as folder:
        seed([{'id': '997200051', 'status': 'replied', 'next_follow_up': (TODAY - dt.timedelta(days=3)).isoformat(),
               'follow_up_plan': {'lane': 'silent', 'step': 1, 'reviewed_at': stamp(-86400 * 7)}}])
        run('pipeline.py', 'follow-up', '997200051', 'clear', '--at', stamp(-86400), '--reason', 'Client replied after the due date')
        cleared = next(entry for entry in records()['997200051']['follow_up_history'] if entry.get('due_on'))
        assert cleared['lane'] == 'silent' and cleared['step'] == 1 and cleared['due_on'] == (TODAY - dt.timedelta(days=3)).isoformat()
        assert cleared['cancelled_at'] == stamp(-86400) and cleared['obligation_id']
        print('audit stats S13: cancelled overdue obligations PASS — original lane, due date, immutable identity and cancellation time survive clearing')
    with fixture('audit-submission') as folder:
        seed([{'id': '997200061'}])
        jobdir = folder / 'jobs/997200061'
        jobdir.mkdir()
        draft = jobdir / 'application.md'
        draft.write_text('Synthetic member draft')
        assert run('pipeline.py', 'sent', '997200061', success=False).returncode != 0
        actual = folder / 'actual.txt'; actual.write_text('Synthetic submitted member wording')
        answers = folder / 'answers.json'; answers.write_text(json.dumps({'screening': 'Submitted answer'}))
        run('pipeline.py', 'sent', '997200061', '--file', actual, '--answers-file', answers, '--bid', '1250')
        assert (jobdir / 'application.sent.md').read_text() == actual.read_text()
        assert json.loads((jobdir / 'answers.sent.json').read_text())['screening'] == 'Submitted answer'
        assert records()['997200061']['submission_bid'] == 1250 and records()['997200061']['application_sent_verified'] is True
        record('997200061', {'application_modality': 'uma'})
        assert records()['997200061']['application_modality'] == 'uma'
        print('audit freelancer F17: submitted evidence PASS — draft-only confirmation refused; actual submitted words, answers and bid retained')
        print('audit freelancer F11: application modality writer PASS — Uma/text stored without requiring sales-call evidence')
    with fixture('audit-member-clock') as folder:
        (folder / 'context/me.md').write_text('# Member\n\n## Timezone\nEurope/Berlin\n')
        assert pipeline.local_day('2026-01-01T23:30:00+00:00') == dt.date(2026, 1, 2)
        assert pipeline.local_day('2026-07-01T22:30:00+00:00') == dt.date(2026, 7, 2)
        (folder / 'context/me.md').write_text('# Member\n\n## Timezone\nAmerica/Los_Angeles\n')
        assert pipeline.local_day('2026-01-01T03:00:00+00:00') == dt.date(2025, 12, 31)
        assert pipeline.application_day({'applied_at': '2026-01-01T03:00:00+00:00'}) == '2025-12-31'
        print('audit engineer E19: member time zone PASS — IANA DST offsets and ISO-year boundary apply to events and application days')


def audit_analytics():
    import analytics
    import concurrent.futures
    import copy
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    def passed(label): print('SYNTHETIC audit ' + label + ' PASS')
    def ts(date, hour=10, minute=0): return analytics_stamp(date, hour, minute)
    def marker(folder):
        (folder / 'data/sync.json').write_text(json.dumps({'synced_at': now}))
        (folder / 'data/earnings.jsonl').write_text('')
        (folder / 'data/connects.jsonl').write_text('')
    def goal(key='reply_rate', start='2026-09-01'):
        return {'kpi': key, 'stage': analytics.LABELS[key], 'change': 'Offer two concrete call times',
                'start': start, 'primary': True, 'cue': 'When clients reply', 'action': 'Offer two call times',
                'fallback': 'Offer one time', 'review_on': (dt.date.fromisoformat(start) + dt.timedelta(days=7)).isoformat()}
    with fixture('audit-analytics') as folder:
        marker(folder)
        assert abs(analytics.exact_bounds(1, 1)[0] - 2.5) < 1e-8
        assert abs(analytics.exact_bounds(0, 1)[1] - 97.5) < 1e-8
        # Frozen final clarification: no n20 gate; only the Wilson bound decides.
        assert analytics.rate_state(1, 1, 20) == analytics.rate_state(2, 2, 30) == 'pass'
        assert analytics.rate_state(1, 1, 30) == 'undecided'
        assert analytics.rate_state(2, 2, 11) == analytics.rate_state(10, 10, 11) == 'pass'
        assert analytics.rate_state(20, 20, 11) == 'pass'
        assert analytics.wilson(10,10)[1] == 100 and analytics.wilson(0,10)[0] == 0
        assert analytics.exact_bounds(1000000, 1000000)[1] == 100
        passed('stats S2 / engineer E12 / stats S3 / product P1: exact tiny n and Wilson endpoints')
        jobs=[{'id':'920000001','source':'outbound','applied_at':ts(today-dt.timedelta(days=4)),
               'job_fit':{'state':'pass','reason':'Member lane'},'application_facts':{'source':'outbound','posted_age_band':'<10m'},
               'follow_up_history':[{'lane':'silent','due_on':'2026-10-10','on':'2026-10-10','action':'sent'}]}]
        kpis,_=analytics.calculate(jobs,today,now=now)
        assert kpis['follow_ups_on_time']['state']==kpis['job_fit']['state']=='pass'
        passed('engineer E12 / stats S3 / product P1: perfect compliance census')
        # Distinct route populations; a late reply is not seven-day progression.
        entry=today-dt.timedelta(days=30)
        out={'id':'920000002','source':'outbound','applied_at':ts(entry), 'replied_at':ts(entry+dt.timedelta(days=9)),
             'call_booked_at':ts(entry+dt.timedelta(days=10)), 'call_scheduled_at':ts(today+dt.timedelta(days=7))}
        inbound=dict(out,id='920000003',source='invite',invited_at=ts(entry),replied_at=ts(entry+dt.timedelta(days=1)))
        one=analytics.calculate([out],today,now=now)[0]
        mixed=analytics.calculate([out,inbound],today,now=now)[0]
        assert one['reply_rate']['n']==1 and one['reply_rate']['k']==0
        for key in ('reply_rate','reply_to_call','booked_to_held','held_to_proposal','proposal_to_won'):
            assert (one[key]['k'],one[key]['n'])==(mixed[key]['k'],mixed[key]['n'])
        assert one['booked_to_held']['n']==0
        assert one['reply_to_call']['k']==1
        assert not any(row['kind']=='no_show_confirm' for row in analytics.lead_todos([dict(out,status='call')],today,[]))
        assert analytics.event({'history':[{'status':'won','at':now}], 'won_value':{'start_date':'2026-09-02'}},'won').date()==dt.date(2026,9,2)
        passed('stats S4 / engineer E9 / stats S6-S8 / freelancer F6,F14: horizon strands outcome time and future booking')
        held=ts(today-dt.timedelta(days=2),10)
        end=ts(today-dt.timedelta(days=2),11)
        proposal=ts(today-dt.timedelta(days=2),11,5)
        base={'id':'920000004','source':'outbound','call_held_at':held,'call_ended_at':end,'proposal_sent_at':proposal}
        disq=dict(base,id='920000005',call_outcome='disqualified');disq.pop('proposal_sent_at')
        bypass=dict(base,id='920000006',won_at=ts(today-dt.timedelta(days=1)));bypass.pop('proposal_sent_at')
        latency=analytics.calculate([base,disq,bypass],today,now=now)[0]['proposal_on_time']
        assert (latency['k'],latency['n'],latency['excluded_n'])==(1,1,2)
        assert not any(row['kind']=='proposal_due' for row in analytics.lead_todos([dict(disq,status='call')],today,[]))
        passed('engineer E18 / stats S9-S10 / freelancer F15,F16 / product P3: call end and proposal eligibility')
        responses=[]
        for index in range(10):
            responses.append({'id':str(920100000+index),'first_reply_at':ts(today-dt.timedelta(days=1),10,6),
                              'first_reply_s':60*(4 if index<5 else 6)})
        measured=analytics.calculate(responses,today,now=now)[0]['first_reply']
        # Frozen §13.6: median5/p756 meets observed first-reply targets at n=10.
        assert measured['state']=='pass' and measured['median_low']==4 and measured['median_high']==6
        responses += [{'id':str(920200000+index),'first_client_message_at':ts(today-dt.timedelta(days=1),10)} for index in range(20)]
        measured=analytics.calculate(responses,today,now=now)[0]['first_reply']
        assert measured['n']==30 and measured['open_n']==20 and measured['state']!='pass'
        passed('stats S11-S12: open client cases and quantile uncertainty')
        cleared={'id':'920000007','follow_up_history':[{'lane':'silent','due_on':'2026-10-08','cancelled_at':'2026-10-09T12:00:00+02:00'},
                  {'lane':'silent','due_on':'2026-10-10','cancelled_at':'2026-10-09T12:00:00+02:00'}]}
        compliance=analytics.calculate([cleared],today,now=now)[0]['follow_ups_on_time']
        assert (compliance['k'],compliance['n'])==(0,1)
        obligations={'id':'920000077','follow_up_history':[
            {'obligation_id':'first','lane':'silent','due_on':'2026-10-08','on':'2026-10-08','action':'sent'},
            {'obligation_id':'first','lane':'silent','due_on':'2026-10-08','cancelled_at':'2026-10-09T12:00:00+02:00'},
            {'obligation_id':'second','lane':'silent','due_on':'2026-10-08'}]}
        obligations_result=analytics.calculate([obligations],today,now=now)[0]['follow_ups_on_time']
        assert (obligations_result['k'],obligations_result['n'])==(1,2)
        passed('stats S13: obligation identity preserves completion revisions and distinct same-day misses')

        raw=jobs+[dict(jobs[0],id='920000008',job_fit={'state':'fail','reason':'Wrong lane'})]+[dict(jobs[0],id='920000009',job_fit={'state':'unclear','reason':'Reviewed context missing'})]
        measured=analytics.calculate(raw,today,now=now)[0]
        assert measured['weekly_volume']['value']==2 and measured['job_fit']['n']==3
        passed('stats S13-S14 / freelancer F9 / product P8: retained misses qualified volume and fit coverage')
        fixed={'id':'920000010','won_at':ts(today-dt.timedelta(days=1)), 'won_value':{'type':'fixed','amount':200,'currency':'USD','start_date':'2026-10-13'}}
        old={'id':'920000011','won_value':{'type':'fixed','amount':100,'currency':'EUR','start_date':'2026-10-06'}}
        hourly={'id':'920000012','won_value':{'type':'hourly','amount':50,'weekly_hours':10,'currency':'USD','start_date':'2026-10-12'}}
        bills=[{'contract_id':'old','week_start':'2026-10-12','currency':'EUR','billed':100}, {'contract_id':'old','week_start':'2026-10-12','currency':'EUR','billed':250}]
        finance=analytics.financial([fixed,old,hourly],bills,analytics.span(today,7))
        assert finance['value']==2200 and finance['hourly_billed']==250 and finance['currency']=='USD'
        unknown=analytics.financial([dict(fixed,id='920000013',won_value=None)],[],analytics.span(today,7))
        assert unknown['value'] is None and unknown['value_unknown_n']==1 and unknown['known_subtotal']==0
        assert 'not attributable acquisition ROI' in measured['value_per_100_connects']['reason']
        passed('engineer E8 / stats S15-S18 / freelancer F1,F3,F5: new booked value unknown terms period ratio and billing revisions')
        for delta,expected in ((dt.timedelta(hours=23,minutes=59),'ok'),(dt.timedelta(hours=24),'stale'),(dt.timedelta(hours=25),'stale'),(-dt.timedelta(seconds=1),'missing')):
            (folder / 'data/sync.json').write_text(json.dumps({'synced_at':(analytics.timestamp(now)-delta).isoformat()}))
            assert analytics.source_coverage([],today,now)[0][0]['state']==expected
        marker(folder)
        assert analytics.day('2026-10-07T22:30:00+00:00')==dt.date(2026,10,8)
        assert analytics.local_zone().utcoffset(dt.datetime(2026,1,1))==dt.timedelta(hours=1)
        passed('engineer E17,E19: exact runtime freshness member midnight and DST')
        before=analytics.rate_metric('reply_rate',[{'id':str(i)} for i in range(1)],lambda row:False,20)
        after=analytics.rate_metric('reply_rate',[{'id':str(i)} for i in range(1)],lambda row:True,20)
        lo,hi=analytics.difference_bounds(before,after)
        assert lo<0<hi
        passed('stats S20: tiny delta cannot establish improvement')
        base_snapshot=analytics.compute(today,now=now)
        v=copy.deepcopy(base_snapshot['kpis'])
        for key in analytics.FUNNEL:v[key].update(state='undecided')
        v['reply_rate'].update(state='pass')
        assert 'No bottleneck' not in analytics.verdict(v)['sentence']
        assert analytics.verdict(v)['undecided_before']==[]
        v['weekly_volume'].update(state='fail',value=0,target=25)
        v['first_reply'].update(state='fail',value=6,target=5,p75=6)
        assert analytics.verdict(v)['kpi']=='weekly_volume'
        v['reply_rate'].update(state='fail',lost_revenue=100)
        v['offer_to_contract'].update(state='fail',lost_revenue=500)
        for lever in analytics.LEVERS:v[lever].update(state='pass')
        assert analytics.verdict(v)['kpi']=='offer_to_contract'
        passed('stats S22-S23 / freelancer F8: honest unknown verdict unit-free levers economic focus')
        (folder/'context/me.md').write_text('## Bars\nreply_rate: 30\n')
        entry=today-dt.timedelta(days=35)
        flow=[]
        for index in range(100):
            row={'id':str(930000000+index),'source':'outbound','applied_at':ts(entry)}
            if index<20: row['replied_at']=ts(entry+dt.timedelta(days=1))
            if index<5: row.update(won_at=ts(entry+dt.timedelta(days=5)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(entry+dt.timedelta(days=5)).isoformat()})
            flow.append(row)
        losses=analytics.calculate(flow,today,now=now)[0]
        assert losses['reply_rate']['downstream_to_won']==.25
        assert losses['reply_rate']['lost_revenue']==2500
        terminal=[]
        for index in range(100):
            row={'id':str(930100000+index),'source':'outbound','proposal_sent_at':ts(entry)}
            if index<20:row.update(won_at=ts(entry+dt.timedelta(days=5)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(entry+dt.timedelta(days=5)).isoformat()})
            terminal.append(row)
        loss=analytics.calculate(terminal,today,now=now)[0]['proposal_to_won']
        assert loss['downstream_to_won']==1 and abs(loss['lost_revenue']-10000)<.01
        passed('stats S23 / freelancer F8: computed lost revenue uses conditional exit conversion and terminal factor one')
        (folder/'context/me.md').write_text('# Synthetic member\n')

        g=goal()
        analytics.add_goals({'week':'2026-W36','goals':[g]})
        assert len(analytics.latest_goals(today))==1
        early=analytics.goal_reviews([],dt.date(2026,9,8),now=now)[0]
        assert early['effect']=='undecided' and not early['mature']
        analytics.validate_goals({'week':'2026-W36','goals':[g]})
        passed('engineer E13-E14 / stats S19 / freelancer F7,F10 / product P2,P5,P6: effect pending mature goals one-to-three')
        # All four review kinds cannot pass just because a fix names an existing lead.
        seed([{'id':'920000001','title':'SYNTHETIC review lead'}])
        payload=analytics_payload(analytics.compute(today,now=now))
        for review in payload['reviews'].values():review['evidence_lead_ids']=['920000001']
        prepared=analytics.prepare_snapshot(payload,today,now=now)
        assert all(prepared['kpis'][key]['state']!='pass' for key in ('application_review','conversation_review','call_review','proposal_review'))
        passed('engineer E15: review-specific source and complete rubric gate')
        # Independent public schema: arbitrary fields/text and nested client source are refused.
        card=copy.deepcopy(base_snapshot['community_card'])
        card['question']=analytics.PUBLIC_QUESTIONS[0]
        analytics.validate_community_card(card,[])
        for mutation in ({'title':'Private title'},{'question':'What about Private Client?'},{'report':'Hidden source'}):
            bad=dict(card,**mutation)
            if 'question' in mutation:  # Frozen §13.4: optional unsafe dynamic question is dropped.
                assert analytics.validate_community_card(bad,[{'title':'Private Client'}])['question'] is None
            else:
                try:analytics.validate_community_card(bad,[])
                except ValueError:pass
                else:raise AssertionError('Public payload bypass accepted')
        bad=copy.deepcopy(card);bad['goals']=[{'text':'Offer two concrete call times','done':False,'k':0,'n':1,'state':'undone'}]
        try:analytics.validate_community_card(bad,[{'details':{'client':{'name':'Offer two concrete'}}}])
        except ValueError:pass
        else:raise AssertionError('Nested public identity accepted')
        passed('privacy V13: closed community payload fixed questions nested client rejection')
        # Directory flock protects duplicate checks; atomic rename preserves prior bytes on failure.
        atomic_input={'week':'2026-W42','goals':[goal('weekly_volume','2026-10-14')]}
        def add_once(_):
            try:analytics.add_goals(atomic_input);return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(add_once,range(2)))==1
        previous_bytes=(folder/'data/goals.jsonl').read_bytes()
        with mock.patch.object(analytics.os,'replace',side_effect=OSError('synthetic interruption')):
            try:analytics.atomic_lines('goals.jsonl',[])
            except OSError:pass
        assert (folder/'data/goals.jsonl').read_bytes()==previous_bytes
        assert not list((folder/'data').glob('*analytics*.lock')) and not list((folder/'data').glob('*goals*.lock'))
        passed('engineer E16: concurrent goals duplicate and interrupted atomic replacement')
        # Current weekly cue is due by local date, regardless of prior review's clock time.
        analytics.atomic_lines('analytics-history.jsonl',[{'week':'2026-W41','generated_at':'2026-10-07T18:00:00+02:00'}])
        assert analytics.due('2026-10-14')
        passed('product P7: weekly scheduled date cue')


def audit_analytics_extended():
    import analytics
    import copy
    import concurrent.futures
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    def passed(label):print('SYNTHETIC audit '+label+' PASS')
    def setup(folder):
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
    def commitment(key,start='2026-09-01'):
        return {'kpi':key,'stage':analytics.LABELS[key],'change':'Review applications once','start':start,
                'primary':True,'cue':'When reviewing the week','action':'Review applications once',
                'fallback':'Review one application','review_on':(dt.date.fromisoformat(start)+dt.timedelta(days=7)).isoformat()}
    with fixture('audit-real-effects') as folder:
        setup(folder)
        for before_min,after_min,expected in ((1,3,'not'),(10,6,'worked'),(3,3,'not')):  # Frozen §13.7: unchanged is no effect.
            rows=[]
            for phase,value in ((0,before_min),(1,after_min)):
                date=dt.date(2026,8,28) if phase==0 else dt.date(2026,9,3)
                for index in range(100):
                    rows.append({'id':str(931000000+phase*1000+index),'first_reply_at':analytics_stamp(date,10,value),'first_reply_s':value*60})
            analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[commitment('first_reply')]}])
            review=analytics.goal_reviews(rows,today,now=now)[0]
            assert review['effect']==expected,(before_min,after_min,review)
            assert (review['before'],review['after'])==(before_min,after_min)
        # Target attainment is deliberately irrelevant: 20% can improve below a 30% target.
        for bk,bn,ak,an,expected in ((0,200,40,200,'worked'),(20,20,16,20,'not')):  # Frozen §13.7: after Wilson wholly below before rate.
            rows=[]
            for phase,k,n in ((0,bk,bn),(1,ak,an)):
                date=dt.date(2026,8,28) if phase==0 else dt.date(2026,9,3)
                for index in range(n):
                    row={'id':str(932000000+phase*1000+index),'source':'outbound','applied_at':analytics_stamp(date)}
                    if index<k:row['replied_at']=analytics_stamp(date+dt.timedelta(days=1))
                    rows.append(row)
            analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[commitment('reply_rate')]}])
            review=analytics.goal_reviews(rows,today,now=now)[0]
            assert review['effect']==expected,(bk,bn,ak,an,review)
            if bk==20:assert review['effect']!='worked'
        passed('engineer E13 / stats S19 / freelancer F7 / product P2: real worse improved unchanged goal effects and independent interval')
    with fixture('audit-partial-execution') as folder:
        setup(folder)
        rows=[{'id':str(933000000+index),'title':'SYNTHETIC eligible lead'} for index in range(27)]
        seed(rows)
        analytics.add_goals({'week':'2026-W36','goals':[commitment('reply_rate')]})
        for done,eligible,state in ((22,27,'partial'),(0,27,'undone'),(0,0,'no opportunity')):
            value=analytics.compute(today,now=now)
            review=value['goals_review'][0]
            review['evidence_lead_ids']=[row['id'] for row in rows[:eligible]]
            review['done_lead_ids']=[row['id'] for row in rows[:done]]
            prepared=analytics.prepare_snapshot(value,today,now=now)
            execution=prepared['kpis']['goal_done']
            assert (execution['k'],execution['n'])==(done,eligible)
            assert prepared['goals_review'][0]['execution_state']==state
            public=prepared['community_card']['goals'][0]
            assert (public['k'],public['n'],public['state'])==(done,eligible,state)
            if not eligible:assert execution['state']=='undecided'
        passed('product P4: partial22/27 undone0/27 and no-opportunity0/0 preserved privately and publicly')
    with fixture('audit-badges-forecast') as folder:
        setup(folder)
        rows=[]
        for index in range(10):
            date=today-dt.timedelta(days=2)
            rows.append({'id':str(934000000+index),'source':'outbound','call_held_at':analytics_stamp(date,10),
                         'call_ended_at':analytics_stamp(date,11),'proposal_sent_at':analytics_stamp(date,11,5) if index<9 else analytics_stamp(date,12),
                         'proposal_review':{'state':'pass','reason':'Reviewed relevant scope and next step'}})
        snapshot=analytics.compute(today,jobs=rows,now=now)
        snapshot['kpis']['call_review']['state']='pass'  # Unit input: validated review; source gating has a separate negative case.
        snapshot['reviews']['call']['rubric']=[{'lead_id':rows[0]['id'],'reviewable':True,
          'points':[{'point':point,'state':'not needed' if point==6 else 'met','reason':'No separate objection occurred' if point==6 else ''} for point in range(1,10)]}]
        badges=analytics.badge_results(snapshot,rows,[],today)
        # Final calibration: 90% quality-checked proposals qualify one Bronze week; Silver needs three.
        assert any(badge['badge']=='Quick Draw' and badge['tier']=='Bronze' for badge in badges) and not any(badge['badge']=='Quick Draw' and badge['tier']=='Silver' for badge in badges)
        assert any(badge['badge']=='True North' and badge['tier']=='Bronze' for badge in badges) and not any(badge['badge']=='True North' and badge['tier']=='Silver' for badge in badges)
        poor={'id':'934000020','source':'outbound','applied_at':analytics_stamp(today-dt.timedelta(days=1)),
              'speed_to_lead_s':60,'job_fit':{'state':'fail','reason':'Wrong lane'}}
        snapshot=analytics.compute(today,jobs=[poor],now=now)
        assert not any(badge['badge']=='Swift Sail' for badge in snapshot['badges'])
        # Standalone held-call denominator has a proposal-free win and a clean disqualification.
        old=today-dt.timedelta(days=32)  # Frozen §13.1: held-call win maturity is28 days.
        callrows=[{'id':'934000030','source':'outbound','call_held_at':analytics_stamp(old),'won_at':analytics_stamp(old+dt.timedelta(days=4)),
                   'won_value':{'type':'fixed','amount':1000,'currency':'USD','start_date':(old+dt.timedelta(days=4)).isoformat()}},
                  {'id':'934000031','source':'outbound','call_held_at':analytics_stamp(old),'call_outcome':'disqualified'}]
        calculated=analytics.call_to_won(callrows,today)
        assert (calculated['k'],calculated['n'],calculated['bypass_n'])==(1,2,1)
        card_snapshot=analytics.compute(today,jobs=callrows,now=now)
        call_card=card_snapshot['community_card']['call_to_won']
        assert (call_card['k'],call_card['n'],call_card['horizon_days'])==(1,2,28)  # Frozen §13.1 (21+7).
        assert call_card['value']==calculated['value'] and call_card['entry_period']==calculated['entry_period']
        assert card_snapshot['kpis']['proposal_to_won']['n']==0
        passed('stats S31 / freelancer F22 / product P10: public card preserves actual held-call k/n horizon and bypass denominator')

        # Forecast gets average OWN won value, not sum of OPEN estimates or multiplied stage sum.
        past=[]
        for index in range(100):
            date=today-dt.timedelta(days=35)
            row={'id':str(934100000+index),'source':'outbound','applied_at':analytics_stamp(date),'status':'won' if index<20 else 'lost'}
            if index<20:row.update(won_at=analytics_stamp(date+dt.timedelta(days=2)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(date+dt.timedelta(days=2)).isoformat()})
            past.append(row)
        opens=[{'id':str(934200000+index),'source':'outbound','status':'applied','price_estimate':9999} for index in range(10)]
        forecast=analytics.explore_fields(past+opens,today,[])['forecast']['by_stage'][0]
        assert forecast['own_rate']==.2 and forecast['average_won_value']==1000 and forecast['expected']==2000
        tiny=analytics.explore_fields(past[:1]+opens,today,[])['forecast']['by_stage'][0]
        assert tiny['own_rate'] is None and tiny['expected'] is None
        passed('product P8-P10 / freelancer F9,F22 / stats S25: qualified speed QuickDraw all-within30m applicable TrueNorth held-call-to-win and forecast units')
        # No tiny cohort may earn an outcome tier, and repeated-look policy uses summable spend.
        tiny=analytics.compute(today,jobs=callrows[:1],now=now)
        assert not any(badge['badge']=='Treasure Hunter' for badge in tiny['badges'])
        # Frozen §3/§13: Wilson performance/promotion, exact intervals remain descriptive.
        assert all(row['promotion_policy'].startswith('Wilson') for key,row in snapshot['kpis'].items() if key in analytics.FUNNEL)
        assert all(row['ladder_mode'] in ('maintain', 'advance') for key,row in snapshot['kpis'].items() if key in analytics.FUNNEL)
        assert all(row['initial_benchmark'] is not None or row['own_benchmark'] is None for key,row in snapshot['kpis'].items() if key in analytics.FUNNEL)
        passed('stats S2,S21,S24: complete Wilson rung policies and tiny outcome achievement refused; exact descriptions retained')
    with fixture('audit-record-race') as folder:
        setup(folder)
        goal=commitment('weekly_volume','2026-10-14')
        analytics.add_goals({'week':'2026-W42','goals':[goal]})
        value=analytics.compute(today,now=now)
        value['goals_next']=[goal];value['report']='Weekly measured review.'
        value['community_card']['next_focus']=analytics.LABELS['weekly_volume'];value['community_card']['question']=analytics.PUBLIC_QUESTIONS[0]
        prepared=analytics.prepare_snapshot(value,today,now=now)
        payload=json.dumps(prepared)
        commands=[sys.executable,str(CODE/'analytics.py'),'record','--file','-']
        workers=[subprocess.Popen(commands,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[worker.communicate(payload) for worker in workers]
        assert sorted(worker.returncode for worker in workers)==[0,1],results
        ledger=folder/'data/analytics-history.jsonl'
        assert len(ledger.read_text().splitlines())==1
        before=ledger.read_bytes()
        with mock.patch.object(analytics.os,'replace',side_effect=OSError('synthetic interrupted record')):
            try:analytics.record_snapshot(prepared,replace=True)
            except OSError:pass
        assert ledger.read_bytes()==before
        passed('engineer E16: concurrent record duplicate rejected interruption preserves full history')
        # Existing minimal legacy history can still be read alongside the new producer.
        legacy={'week':'2026-W41','generated_at':'2026-10-07T12:00:00+02:00','kpis':{},'north_star':{}}
        analytics.atomic_lines('analytics-history.jsonl',[legacy])
        migrated=analytics.compute(today,now=now)
        assert migrated['north_star']['history'][-2] is None and migrated['verdict_history'][0]['stage'] is None
        assert 'community_card' in migrated and 'call_to_won' in migrated and 'forecast' in migrated
        passed('engineer E21: old missing producer fields remain null new fields computed without reader migration')
        migrated['goals_next']=[goal]; migrated['report']='Corrected weekly measured review.'
        migrated['community_card']['next_focus']=analytics.LABELS['weekly_volume']
        migrated['community_card']['question']=analytics.PUBLIC_QUESTIONS[0]
        corrected=analytics.prepare_snapshot(migrated,today,now=now)
        analytics.record_snapshot(corrected)
        replace_commands=commands + ['--replace']
        workers=[subprocess.Popen(replace_commands,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[worker.communicate(json.dumps(corrected)) for worker in workers]
        assert all(worker.returncode==0 for worker in workers),results
        complete_history=[json.loads(line) for line in ledger.read_text().splitlines()]
        assert [row['week'] for row in complete_history]==['2026-W41','2026-W42']
        assert complete_history[0]==legacy and complete_history[1]['report']==corrected['report']
        passed('engineer E16: concurrent replacements preserve prior weeks and one corrected current row')



def audit_producer_followup():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-producer-followup') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        rows=[{'id':'937000001','source':'outbound','status':'call','call_booked_at':'2026-10-12T10:00:00+02:00','call_scheduled_at':'2026-10-20T10:00:00+02:00'},
              {'id':'937000002','source':'outbound','status':'call','call_held_at':'2026-10-12T10:00:00+02:00','proposal_sent_at':'2026-10-12T11:00:00+02:00'},
              {'id':'937000003','source':'outbound','status':'call'},
              {'id':'937000004','source':'outbound','status':'offer','proposal_sent_at':'2026-10-11T11:00:00+02:00'},
              {'id':'937000005','source':'invite','status':'call','call_held_at':'2026-10-12T10:00:00+02:00'}]
        counts=analytics.pipeline_counts(rows,today)
        call=next(row for row in counts['outbound'] if row['stage']=='call')
        offer=next(row for row in counts['outbound'] if row['stage']=='offer')
        inbound=next(row for row in counts['inbound'] if row['stage']=='call')
        assert (call['count'],call['booked'],call['held'],call['unknown_call'],call['proposals_out'])==(3,1,1,1,1)
        assert call['booked']+call['held']+call['unknown_call']==call['count']
        assert offer['proposals_out']==1 and inbound['held']==1
        assert sum(row['count'] for row in counts['outbound'])==4
        print('SYNTHETIC audit engineer E21: producer booked/held/unknown partitions and open sent-proposal counts PASS')
        entry=today-dt.timedelta(days=20)
        direct={'id':'937000010','source':'outbound','replied_at':analytics_stamp(entry),
                'offered_at':analytics_stamp(entry+dt.timedelta(days=1))}
        actual={'id':'937000011','source':'outbound','replied_at':analytics_stamp(entry),
                'call_held_at':analytics_stamp(entry+dt.timedelta(days=1))}
        invitation=dict(direct,id='937000012',source='invite',invited_at=analytics_stamp(entry))
        result=analytics.compute(today,jobs=[direct,actual,invitation],now=now)
        row=result['kpis']['reply_to_call']
        assert (row['k'],row['n'])==(2,2)
        assert row['label']=='Call rate'
        assert row['outcome_label']=='Reply → booked call, held call, offer or contract within 14 days'
        assert row['progression']=={'booked_calls':0,'held_calls':1,'offer_or_contract_without_call':1}
        invite=result['kpis']['invite_to_call']
        assert (invite['k'],invite['n'])==(1,1) and invite['progression']['offer_or_contract_without_call']==1
        public=result['community_card']['reply_to_call']
        # Frozen §13.3: the common mature28-day public population excludes these20-day-old entries.
        assert public['outcome_label']==row['outcome_label'] and public['progression']=={'booked_calls':0,'held_calls':0,'offer_or_contract_without_call':0}
        analytics.validate_community_card(result['community_card'],[direct,actual,invitation])
        poisoned=copy.deepcopy(result['community_card']);poisoned['reply_to_call']['outcome_label']='Private client text'
        try:analytics.validate_community_card(poisoned,[])
        except ValueError:pass
        else:raise AssertionError('Public fixed definition was overwritten')
        print('SYNTHETIC audit stats S7,S31: composite progression exposes actual call and offer bypass with fixed public definition PASS')
        fitrows=[{'id':str(937001000+index),'source':'outbound','applied_at':'2026-10-12T10:00:00+02:00',
                  **({'job_fit':{'state':'pass','reason':'Member lane'}} if index==0 else {})} for index in range(10)]
        fit=analytics.calculate(fitrows,today,now=now)[0]['job_fit']
        assert (fit['k'],fit['n'],fit['coverage_low'],fit['coverage_high'],fit['known_n'])==(1,10,10,100,1)
        assert fit['state']=='undecided' and fit['value'] is None
        for row in fitrows:row['job_fit']={'state':'pass','reason':'Member lane'}
        assert analytics.calculate(fitrows,today,now=now)[0]['job_fit']['state']=='pass'
        for row in fitrows:row.pop('job_fit')
        assert analytics.calculate(fitrows,today,now=now)[0]['job_fit']['state']=='missing'
        print('SYNTHETIC audit stats S14: one assessed nine unknown fit bounds preserve undecided all-pass census and all-unknown missing PASS')


def audit_uma_review():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-uma-review') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='938000001'
        seed([{'id':jid,'title':'SYNTHETIC Uma requirement','status':'applied','source':'outbound'}])
        record(jid,{'application_modality':'uma','application_sent_verified':True})
        path=folder/'jobs'/jid
        path.mkdir(exist_ok=True)
        sent=path/'application.sent.md';sent.write_text('SYNTHETIC submitted interview answers and video evidence')
        value=analytics.compute(today,now=now)
        value['reviews']['application'].update(fix='Keep specific evidence in answers',example='I implemented this workflow.',evidence_lead_ids=[jid],
            rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':point,'state':'met'} for point in range(1,4)]}])
        reviewed=analytics.prepare_snapshot(value,today,now=now)
        assert reviewed['kpis']['application_review']['state']=='pass'
        coverage=[row for row in reviewed['reviews']['application']['coverage'] if row.get('modality')=='uma']
        assert [row['point'] for row in coverage]==[1,2,3]
        assert all(row['n']==row['met']==1 for row in coverage)
        assert all(not row['n'] for row in reviewed['reviews']['application']['coverage'] if row.get('modality')!='uma')
        bad=copy.deepcopy(value)
        bad['reviews']['application']['rubric'][0]['points']=[{'point':point,'state':'met'} for point in range(1,7)]
        try:analytics.prepare_snapshot(bad,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Uma accepted cover-letter rubric')
        sent.unlink()
        missing=analytics.prepare_snapshot(value,today,now=now)
        assert missing['kpis']['application_review']['state']=='missing'
        assert all(not row['n'] for row in missing['reviews']['application']['coverage'])
        print('SYNTHETIC audit freelancer F11: verified Uma answers/video use three applicable points; cover-letter rubric refused; absent submitted artifact missing PASS')
    with fixture('audit-incomplete-call-badge') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='938020001'
        seed([{'id':jid,'source':'outbound','status':'call','call_held_at':'2026-10-12T10:00:00+02:00'}])
        path=folder/'jobs'/jid;path.mkdir(exist_ok=True)
        (path/'call.md').write_text('Member: Alex\nComplete: no\nLanguage: English\nDuration: 3600\nAlex: What is the next step?\nClient: Synthetic response unique to partial call 938020001.\n')
        value=analytics.compute(today,now=now)
        value['reviews']['call'].update(fix='Verify the missing call segments',example='What is the next step?',evidence_lead_ids=[jid],
            rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':point,'state':'met'} for point in range(1,10)]}])
        try:analytics.prepare_snapshot(value,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Incomplete transcript accepted as reviewed.')
        value['reviews']['call']['rubric'][0].update(reviewable=False,points=[])
        reviewed=analytics.prepare_snapshot(value,today,now=now)
        assert reviewed['kpis']['call_review']['state']=='missing'
        assert not any(badge['badge']=='True North' for badge in reviewed['badges'])
        print('SYNTHETIC audit engineer E15 / freelancer F19 / product P9: incomplete call cannot earn True North despite a declared all-met rubric PASS')



def audit_call_badge_evidence():
    import analytics
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-call-badge-evidence') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='938100001'
        seed([{'id':jid,'title':'SYNTHETIC call evidence','source':'outbound','status':'call',
               'call_held_at':'2026-10-12T10:00:00+02:00'}])
        path=folder/'jobs'/jid;path.mkdir(exist_ok=True)
        transcript=path/'call.md'
        text='Language: English\nMember: Alex\nAlex: Which workflow is slow?\nClient: The intake takes time.\nAlex: What outcome matters?\n'
        transcript.write_text('Complete: no\n'+text)
        value=analytics.compute(today,now=now)
        value['reviews']['call'].update(fix='Clarify the outcome once',example='What outcome matters?',evidence_lead_ids=[jid],
            rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':point,'state':'met'} for point in range(1,10)]}])
        try:analytics.prepare_snapshot(value,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Incomplete transcript accepted as reviewed.')
        unavailable=__import__('copy').deepcopy(value)
        unavailable['reviews']['call']['rubric'][0].update(reviewable=False,points=[])
        incomplete=analytics.prepare_snapshot(unavailable,today,now=now)
        assert incomplete['kpis']['call_review']['state']=='missing'
        assert not any(badge['badge']=='True North' for badge in incomplete['badges'])
        transcript.write_text('Complete: yes\n'+text)
        complete=analytics.prepare_snapshot(value,today,now=now)
        assert complete['kpis']['call_review']['state']=='pass'
        assert any(badge['badge']=='True North' and badge['tier']=='Bronze' for badge in complete['badges']) and not any(badge['badge']=='True North' and badge['tier']=='Silver' for badge in complete['badges'])
        degraded=analytics.prepare_snapshot(dict(value,coverage=[{'source':'recorder','state':'missing','fix':'Recorder source unavailable'}]),today,now=now)
        assert degraded['kpis']['call_review']['state']=='missing'
        assert not any(badge['badge']=='True North' for badge in degraded['badges'])
        print('SYNTHETIC audit engineer E15 / freelancer F19 / product P9: True North requires complete computed call review; incomplete transcript and missing recorder cannot earn PASS')


def analytics_final_numerical():
    """Independent final §13 boundary/interval/cohort checks; no live recording."""
    import analytics
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    with fixture('final-numerical') as folder:
        analytics_sync_marker(folder)
        (folder / 'data/connects.jsonl').write_text('')
        (folder / 'data/earnings.jsonl').write_text('')
        expected_rungs = {'reply_rate': (11, 15, 20), 'reply_to_call': (30, 40, 50),
            'booked_to_held': (70, 80, 90), 'held_to_proposal': (70, 80, 90),
            'proposal_to_won': (20, 25, 30), 'invite_to_call': (30, 40, 50),
            'offer_to_contract': (60, 70, 80)}
        assert analytics.RUNGS == expected_rungs
        rows = [dict(id=str(940000000+i), source='outbound',
                     applied_at=analytics_stamp(today-dt.timedelta(days=35)),
                     replied_at=analytics_stamp(today-dt.timedelta(days=34))) for i in range(100)]
        top = analytics.compute(today, jobs=rows, now=now)['kpis']['reply_rate']
        assert top['target'] == 20 and top['rung_reached'] == 3, top
        assert top['ladder_mode'] == 'maintain', top
        for k, n, target in ((0, 20, 11), (5, 20, 11), (17, 40, 50), (20, 20, 90)):
            lo, hi = analytics_interval(k, n)
            expected = 'pass' if lo >= target else 'fail' if hi < target else 'undecided'
            assert analytics.rate_state(k, n, target) == expected, (k, n, target)
            measured = analytics.rate_metric('reply_rate', [{'id':str(i)} for i in range(n)],
                lambda row: int(row['id']) < k, target)
            exact_lo, exact_hi = analytics_exact_interval(k, n)
            assert abs(measured['exact_low'] - exact_lo) < .01 and abs(measured['exact_high'] - exact_hi) < .01
            assert abs(measured['low'] - lo) < .01 and abs(measured['high'] - hi) < .01
            assert abs(measured['performance_low'] - lo) < .01 and abs(measured['performance_high'] - hi) < .01
        booked = [{'id':'940100001', 'source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=50)),
                   'call_scheduled_at':analytics_stamp(today-dt.timedelta(days=3)),
                   'call_held_at':analytics_stamp(today-dt.timedelta(days=3))},
                  {'id':'940100002','source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=5)),
                   'call_scheduled_at':analytics_stamp(today+dt.timedelta(days=3))},
                  {'id':'940100003','source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=50)),
                   'call_scheduled_at':analytics_stamp(today-dt.timedelta(days=1))}]
        attendance = analytics.calculate(booked, today, now=now)[0]['booked_to_held']
        assert (attendance['k'],attendance['n']) == (1,1), attendance
        assert attendance['evidence'] == ['940100001']
        callrows = []
        for offset, win_day in ((29,28),(29,29),(27,1),(57,1)):
            held = today-dt.timedelta(days=offset)
            callrows.append({'id':str(940200000+len(callrows)), 'source':'outbound',
                             'call_held_at':analytics_stamp(held),
                             'won_at':analytics_stamp(held+dt.timedelta(days=win_day))})
        call = analytics.call_to_won(callrows,today)
        assert (call['k'],call['n'],call['horizon_days']) == (1,2,28), call
        assert analytics.lever_shortfall({'direction':'up','value':80,'target':100}) == .2
        assert analytics.lever_shortfall({'direction':'down','value':6,'target':5}) == .2
        goal={'kpi':'reply_rate','stage':analytics.LABELS['reply_rate'],'change':'Make the next step explicit',
              'start':'2026-09-01','primary':True,'cue':'When applying','action':'Make the next step explicit',
              'fallback':'Ask one question','review_on':'2026-09-08'}
        analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[goal]}])
        effectrows=[]
        for entry,replied,count in ((dt.date(2026,8,15),False,40),(dt.date(2026,8,2),True,40),
                                   (dt.date(2026,9,3),True,40),(dt.date(2026,10,9),False,40)):
            for i in range(count):
                row={'id':str(940250000+len(effectrows)),'source':'outbound','applied_at':analytics_stamp(entry)}
                if replied:row['replied_at']=analytics_stamp(entry+dt.timedelta(days=1))
                effectrows.append(row)
        reviewed=analytics.goal_reviews(effectrows,today,now=now)[0]
        assert (reviewed['before_k'],reviewed['before_n'],reviewed['after_k'],reviewed['after_n'],reviewed['effect']) == (0,40,40,40,'worked'),reviewed
        assert reviewed['before_period']=={'start':'2026-08-04','end':'2026-08-31'}
        assert reviewed['after_period']=={'start':'2026-09-01','end':'2026-10-06'}
        empty = analytics.compute(today,jobs=[],now=now)
        assert empty['kpis']['value_per_100_connects']['state'] == 'not measurable'
        assert empty['kpis']['value_per_100_connects']['value'] is None
        for key in ('first_reply','follow_ups_on_time','proposal_on_time','speed_10min','job_fit'):
            assert empty['kpis'][key]['state'] == 'no opportunities', (key,empty['kpis'][key])
        response = [{'id':str(940300000+i),'first_reply_at':analytics_stamp(today-dt.timedelta(days=1),10,5),
                     'first_reply_s':300} for i in range(10)]
        first = analytics.calculate(response,today,now=now)[0]['first_reply']
        assert (first['n'],first['value'],first['p75'],first['state']) == (10,5,5,'pass')
        assert analytics.calculate(response[:9],today,now=now)[0]['first_reply']['state'] == 'undecided'
        for row in response[-3:]: row['first_reply_s'] = 16*60
        assert analytics.calculate(response,today,now=now)[0]['first_reply']['state'] == 'fail'
        for row in response[-3:]: row['first_reply_s'] = 15*60
        assert analytics.calculate(response,today,now=now)[0]['first_reply']['state'] == 'pass'
        pending = response+[{'id':'940399999','first_client_message_at':analytics_stamp(today-dt.timedelta(days=1),10)}]
        first = analytics.calculate(pending,today,now=now)[0]['first_reply']
        assert first['n'] == 11 and first['open_n'] == 1
        wins = [{'id':str(940400000+i),'source':'outbound','won_at':analytics_stamp(today-dt.timedelta(days=2)),
                 'won_value':{'type':'fixed','amount':amount,'currency':currency,'start_date':(today-dt.timedelta(days=2)).isoformat()}}
                for i,(currency,amount) in enumerate((('EUR',100),('EUR',200),('EUR',300),('USD',9000)))]
        wins.append({'id':'940499999','source':'outbound','won_at':analytics_stamp(today-dt.timedelta(days=1))})
        star = analytics.compute(today,jobs=wins,now=now)['north_star']
        assert star['currency'] == 'EUR' and star['value'] == 600, star
        assert star['value_unknown_n'] == 1 and 'unknown' in star['hourly_note'].casefold(), star
        assert any(row['currency'] == 'USD' and row['value'] == 9000 for row in star['other_totals']), star
    print('SYNTHETIC frozen §13 numerical PASS: supplied/top-held rungs; Wilson performance/exact description; scheduled+2d; held-call28d; zero neutrality; median/p75 equality and unanswered age; separate currencies/unknown wins')


def analytics_event_ledger_contract():
    import badges
    import concurrent.futures
    import copy
    now = '2026-10-14T15:00:00+02:00'
    today = dt.date(2026,10,14)
    points = [{'point':i,'state':'met' if i<8 else 'not needed' if i==9 else 'missing',
               'quote':'Synthetic local proof','reason':'Informed disqualification' if i==9 else ''} for i in range(1,10)]
    with fixture('final-badge-events') as folder:
        rows = [{'id':'941000001','source':'outbound','applied_at':analytics_stamp(today,10),
                 'speed_to_lead_s':120,'applied_observation':{'verified':True,'source':'upwork-proposal'},'job_fit':{'state':'pass','reason':'Fits lane'}},
                {'id':'941000002','source':'outbound','first_reply_at':analytics_stamp(today,10,1),'first_reply_s':60},
                {'id':'941000003','source':'outbound','follow_up_history':[{'lane':'silent','action':'sent','at':analytics_stamp(today,10)}]},
                {'id':'941000004','source':'outbound','call_held_at':analytics_stamp(today,10),
                 'call_ended_at':analytics_stamp(today,11),'proposal_sent_at':analytics_stamp(today,11,10)},
                {'id':'941000005','source':'invite','invited_at':analytics_stamp(today,10),
                 'first_reply_at':analytics_stamp(today,10,5),'first_reply_s':300},
                {'id':'941000006','source':'outbound','won_at':analytics_stamp(today,10)},
                {'id':'941000007','source':'outbound','call_held_at':analytics_stamp(today,10),
                 'call_review':{'reviewable':True,'points':points}},
                {'id':'941000008','source':'outbound','applied_at':analytics_stamp(today,10),
                 'speed_to_lead_s':1,'job_fit':{'state':'fail','reason':'Wrong lane'}}]
        call_folder=folder/'jobs'/'941000007';call_folder.mkdir()
        (call_folder/'call.md').write_text('Member: Alex\nComplete: yes\nLanguage: English\nAlex: What is the next step?\nClient: Synthetic local proof\n')
        assert badges.check(jobs=rows,lead_id='941000008',now=now) == []
        assert badges.check(jobs=rows,lead_id='941000003',now=now) == [], 'A follow-up send is not client revival.'
        assert badges.check(jobs=rows,since='2026-10-15T00:00:00+02:00',now=now) == []
        awards = badges.check(jobs=rows,now=now)
        expected = {'First Doubloon','True North'}  # Speed and volume badges require qualifying weekly evidence.
        assert {row['badge'] for row in awards} == expected, awards
        assert all(set(row) == {'badge','tier','lead_id','at','reason'} and row['tier'] == 'Bronze' for row in awards)
        assert badges.check(jobs=rows,now=now) == []
        assert badges.read_ledger() == awards
        rows[2]['replied_at'] = analytics_stamp(today,10,5)
        revival = badges.check(jobs=rows,lead_id='941000003',now=now)
        assert revival == [], 'A client revival is measured; Lookout is awarded from weekly follow-up compliance.'
        assert badges.check(jobs=rows,lead_id='941000003',now=now) == []
        before = (folder/'data/badges.jsonl').read_bytes()
        poor = copy.deepcopy(rows); poor[0]['job_fit']['state']='fail'
        assert badges.check(jobs=poor,lead_id='941000001',now=now) == []
        assert (folder/'data/badges.jsonl').read_bytes() == before
        weekly = [{'badge':'Quick Draw','tier':'Silver','earned_week':'2026-W42','new':True,'progress_to_next':'0 of 5 calls'}]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: badges.award_weekly(weekly,week='2026-W43',now='2026-10-21T15:00:00+02:00'),range(2)))
        assert sorted(len(result) for result in results) == [0,1], results
        assert len(badges.read_ledger()) == 3
        assert badges.award_weekly(weekly,week='2026-W43',now='2026-10-21T15:00:00+02:00') == []
        cli = run('badges.py','check','--all-since','2026-10-15T00:00:00+02:00')
        assert cli.stdout == ''
        assert not (folder/'data/jobs.json').exists(), 'Badge writer must not write jobs.'
        assert not (folder/'data/analytics-history.jsonl').exists(), 'Badge writer must not write weekly snapshots.'
    for tier in badges.TIERS:
        rows=[{'badge':name,'tier':tier} for name in ('Swift Sail','Quick Draw','True North')]
        view=badges.voyage(rows)
        assert all(row['tier']==tier for row in view['stations'] if row['earned'])
        assert not {'rank','rank_progress'} & view.keys()
    assert not hasattr(badges, 'rank')
    history=[{'week':week} for week in ('2026-W37','2026-W38','2026-W40','2026-W41')]
    saved=badges.streak_history(history,week='2026-W41')
    assert saved == {'streak_weeks':4,'anchors_used':['2026-W39']}, saved
    assert badges.streak(history,week='2026-W41') == 4
    same_month=badges.streak_history([{'week':week} for week in ('2026-W41','2026-W44')],week='2026-W44')
    assert same_month['streak_weeks'] == 1 and same_month['anchors_used'] == ['2026-W42'], same_month
    print('SYNTHETIC frozen badge ledger PASS: measured Bronze moments/equality; send-only and weak-fit refusal; replay/since; atomic concurrent weekly award; only badge writer; retained tiers; rank absent; monthly first-miss anchor')


def analytics_final_reader_contract():
    import analytics
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('final-reader-contract') as folder:
        analytics_sync_marker(folder)
        rows=[{'id':str(942000000+i),'source':'outbound','applied_at':analytics_stamp(today,10),
               'job_fit':{'state':state,'reason':reason},'speed_to_lead_s':speed,
               'application_facts':{'posted_age_band':'<10m' if speed<=600 else '10-60m'}}
              for i,(state,reason,speed) in enumerate((('pass','Fits',120),('unclear','Reviewed context',600),
                                                      ('fail','Wrong lane',30),('unclear','',90),('pass','Fits',900)))]
        rows += [{'id':'942000099','source':'invite','applied_at':analytics_stamp(today,10),
                  'job_fit':{'state':'pass','reason':'Fits'},'speed_to_lead_s':60},
                 {'id':'942000100','source':'outbound','follow_up_plan':{'lane':'silent','due_on':today.isoformat()},
                  'follow_up_history':[{'lane':'silent','due_on':today.isoformat(),'on':today.isoformat(),'action':'sent'}]},
                 {'id':'942000101','source':'outbound','follow_up_plan':{'lane':'silent','due_on':today.isoformat()}}]
        voyage=analytics.daily_voyage(rows,today=today,weekly_goal=25)
        assert {'date','applications','goal','fast','followups_due','followups_done','evidence'} <= voyage.keys()
        assert (voyage['applications'],voyage['goal'],voyage['fast'],voyage['followups_due'],voyage['followups_done']) == (3,5,2,2,1),voyage
        snapshot=analytics.compute(today,jobs=rows,now=now)
        presentation=snapshot['presentation']
        # Frozen sparse selection never pads with ineligible or missing-baseline KPIs.
        assert len(presentation['number_keys']) == len(set(presentation['number_keys'])) < 6
        assert presentation['number_gap']
        assert all(key in snapshot['kpis'] for key in presentation['number_keys'])
        assert presentation['number_keys'][-1] == 'value_per_100_connects'
        assert presentation['number_keys'][0] == snapshot['verdict']['kpi']
        assert len(presentation['insights']) <= 3
        assert set(presentation['kpi_groups']) == {'top','middle','bottom'}
        groups=[key for keys in presentation['kpi_groups'].values() for key in keys]
        assert len(groups) == len(set(groups)) == len(snapshot['kpis']) and set(groups) == set(snapshot['kpis'])
        snapshot['goals_next']=[{'kpi':'weekly_volume','change':'Meet qualified application goal'},
                                {'kpi':'follow_ups_on_time','change':'Complete due follow-ups'}]
        quests=analytics.quest_progress(snapshot,rows,today=today)
        assert len(quests) == 2 and all({'kpi','change','done_k','done_n','unit','evidence'} <= row.keys() for row in quests)
        assert quests[0]['done_k'] == 3 and quests[0]['done_n'] == 25,quests
        assert (quests[1]['done_k'],quests[1]['done_n']) == (1,2),quests
        ranked=__import__('copy').deepcopy(snapshot)
        for row in ranked['kpis'].values(): row.update(state='undecided',n=0,delta=None,baseline=None)
        ranked['verdict']['kpi']='weekly_volume'
        for key,delta in (('first_reply',-9),('reply_rate',5),('proposal_to_won',-8),('reply_to_call',-4)):
            ranked['kpis'][key].update(n=10,delta=delta,baseline=10,target=10)
        ranked['kpis']['won_value'].update(n=9,delta=100)
        assert analytics.presentation_fields(ranked)['number_keys']==['weekly_volume','first_reply','reply_rate','proposal_to_won','reply_to_call','value_per_100_connects']
        # Relative cross-unit selection, stable overlap filling and different weekly winners.
        assert analytics.presentation_fields(ranked)['number_gap'] is None
        first_week=analytics.presentation_fields(ranked)['number_keys']
        ranked['kpis']['won_value'].update(n=10,baseline=10000,delta=100,target=None)
        assert 'won_value' not in analytics.presentation_fields(ranked)['number_keys']
        ranked['kpis']['won_value'].update(delta=100000)
        next_week=analytics.presentation_fields(ranked)['number_keys']
        assert 'won_value' in next_week and next_week != first_week
        ranked['verdict']['kpi']='first_reply'
        overlap=analytics.presentation_fields(ranked)['number_keys']
        assert len(overlap)==len(set(overlap))==6 and overlap[0]=='first_reply'
        # One-sided movement still fills from next eligible magnitude, not arbitrary padding.
        for key in ('proposal_to_won','reply_to_call'): ranked['kpis'][key]['delta']=abs(ranked['kpis'][key]['delta'])
        onesided=analytics.presentation_fields(ranked)['number_keys']
        assert len(onesided)==len(set(onesided))==6
        ranked['kpis']['won_value']['baseline']=None
        missing=analytics.presentation_fields(ranked)
        assert 'won_value' not in missing['number_keys'] and missing['number_gap']
        for row in ranked['kpis'].values(): row.update(delta=None,baseline=None,n=0,state='undecided')
        sparse=analytics.presentation_fields(ranked)
        assert sparse['number_keys']==['first_reply','value_per_100_connects'] and sparse['number_gap']
        full=snapshot['presentation']['voyage']
        assert len(full['stations'])==14 and len(full['calendar'])==84
        assert all(row['locked'] for row in full['stations']) and not {'rank','rank_progress'} & full.keys()
        assert all({'date','week','run','anchor','count','evidence'}<=row.keys() for row in full['calendar'])
        chart=snapshot['presentation']['money_chart']
        assert len(chart['won'])==len(chart['forecast'])==1
        assert chart['won'][0]['value']==snapshot['north_star']['value']
        assert chart['forecast'][0]['value']==snapshot['forecast']['next_30_days']
        history=[dict(snapshot,week=f'2026-W{week:02d}') for week in range(33,42)]
        history[0]['north_star']=dict(snapshot['north_star'],currency='EUR',value=999)
        money=analytics.money_chart(snapshot,history)
        assert len(money['won'])==len(money['forecast'])==8
        assert money['won'][-1]['week']==snapshot['week'] and money['forecast'][-1]['period']['end']=='2026-11-13'
        incompatible=analytics.money_chart(snapshot,[dict(snapshot,week='2026-W41',north_star={'currency':'EUR','value':999})])
        assert incompatible['won'][0]['value'] is None and incompatible['won'][0]['reason']
        assert set(snapshot['presentation']['funnel'])=={'outbound','inbound'}
        for rows_in_strand in snapshot['presentation']['funnel'].values():
            assert all({'key','label','count','k','n','value','conversion_text','loss','state','insight','period','evidence','metric'}<=row.keys() for row in rows_in_strand)
        import badges
        wrapper=badges.cockpit_progress(rows,today=today,snapshot=snapshot,
            goals=[{'kpi':'weekly_volume','change':'Current saved weekly goal','start':today.isoformat()}])
        assert wrapper['daily_voyage']['applications']==3 and len(wrapper['quests'])==1
        assert wrapper['quests'][0]['change']=='Current saved weekly goal' and wrapper['quests'][0]['done_k']==3
        assert badges.cockpit_progress(rows,today=today,snapshot=snapshot,goals=[])['quests']==[]
        assert not (folder/'data/analytics-history.jsonl').exists(), 'Pure helpers must not record.'
        assert not (folder/'data/badges.jsonl').exists(), 'Computing and pure helpers must not award.'
    print('SYNTHETIC frozen presentation/helpers PASS: six unique focus/delta/efficiency keys; all KPIs grouped once; at most3 insights; qualified daily3/5/fast2; due2/done1; goal-specific units; read-only counts')


def analytics_public_onepager_contract():
    import analytics
    import copy
    import struct
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('final-public-onepager') as folder:
        analytics_sync_marker(folder)
        snapshot=analytics.compute(today,jobs=[],now=now)
        card=copy.deepcopy(snapshot['community_card'])
        card['next_focus']=analytics.LABELS['weekly_volume']
        card['question']='Which habits help you keep useful conversations moving?'
        assert analytics.validate_community_card(card,[])['question'] == card['question']
        windows=[card[key]['entry_period'] for key in ('reply_rate','reply_to_call','call_to_won')]
        assert windows[0] == windows[1] == windows[2]
        assert (dt.date.fromisoformat(windows[0]['end'])-dt.date.fromisoformat(windows[0]['start'])).days == 27
        sources=[{'title':'Secret Tender Redtail','details':{'client':{'name':'Private Rowan'}},
                  'description':'Confidential workflow replaces manual invoice reconciliation'}]
        for question in ('What did Private Rowan request?', 'Could Secret Tender Redtail be improved?',
                         'Who uses manual invoice reconciliation?', ' '.join(['word']*15),
                         'Contact me at private@example.test'):
            candidate=copy.deepcopy(card);candidate['question']=question
            assert analytics.validate_community_card(candidate,sources)['question'] is None,question
        improvement=copy.deepcopy(card)
        improvement['biggest_improvement']={'kpi':'reply_rate','from':10,'to':20,'reason':'Applications explain the relevant outcome clearly'}
        assert analytics.validate_community_card(improvement,[])['biggest_improvement']['reason']
        improvement['biggest_improvement']['reason']='Private Rowan liked the application'
        assert 'reason' not in analytics.validate_community_card(improvement,sources)['biggest_improvement']
        improvement['biggest_improvement']['reason']=' '.join(['word']*15)
        assert 'reason' not in analytics.validate_community_card(improvement,[])['biggest_improvement']
        for mutation in ({'client_name':'Private Rowan'},{'report':'Private source'},{'unknown':0}):
            invalid=dict(card,**mutation)
            try: analytics.validate_community_card(invalid,[])
            except ValueError: pass
            else: raise AssertionError('Unknown public root field accepted')
        (folder/'context/me.md').write_text('**Name and location:** Alex Rowan, Berlin\n')
        named=analytics.compute(today,jobs=[],now=now)['community_card']
        assert named['member_name']=='Alex R.' and 'Alex R.' in analytics.public_onepager_html(named)
        forged=copy.deepcopy(named);forged['member_name']='Client Person'
        try:analytics.validate_community_card(forged,[])
        except ValueError:pass
        else:raise AssertionError('Caller-supplied public name accepted')
        badge={'badge':'Swift Sail','tier':'Gold','earned_week':'2026-W42','new':False,'progress_to_next':'All tiers earned'}
        named['top_badges']=[badge]
        assert 'Swift Sail' not in analytics.public_onepager_html(named), 'Public card renders only newly earned tiers.'
        named['new_badge']=dict(badge,tier='Silver',new=True)
        html=analytics.public_onepager_html(named)
        assert html.count('Swift Sail')==1 and '<small>Silver</small>' in html
        invalid=copy.deepcopy(card);invalid['reply_rate']['target']=99
        try:analytics.validate_community_card(invalid,[])
        except ValueError:pass
        else:raise AssertionError('Variable public target accepted')
        invalid=copy.deepcopy(card);invalid['call_to_won']['horizon_days']=21
        try:analytics.validate_community_card(invalid,[])
        except ValueError:pass
        else:raise AssertionError('Superseded public horizon accepted')
        private_canaries=['PRIVATE_FULL_SNAPSHOT_CANARY','CLIENT_QUOTATION_NEVER_PUBLIC','PRIVATE_ROWAN_SENTENCE']
        snapshot.update(report=private_canaries[0],call_cards=[{'quote':private_canaries[1]}],
                        reviews={'call':{'example':private_canaries[2]}})
        snapshot['community_card']=card
        source=folder/'snapshot.jsonl'
        previous=copy.deepcopy(snapshot);previous['week']='2026-W41';previous['community_card']['week']='2026-W41'
        source.write_text(json.dumps(previous)+'\n'+json.dumps(snapshot)+'\n')
        rendered=analytics.onepager(source,week='2026-W42',output=folder/'proof.html')
        html=pathlib.Path(rendered['html']).read_text()
        assert rendered['week']=='2026-W42' and all(value not in html for value in private_canaries)
        assert 'Applications this week' in html and 'Same 28 days' in html
        assert 'data-period-contract' not in html
        assert not any(term.casefold() in html.casefold() for term in ('not supplied','eligible',"Writer's",'Execution and effect apart','stage starts'))
        assert card['question'] in html and "Last agreed goals" in html and "No previous goals." in html and "Last week's 0 agreed goals" not in html
        assert 'New contract value this week' not in html
        assert rendered['png'] is not None,rendered
        header=pathlib.Path(rendered['png']).read_bytes()[:24]
        assert header[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24])==(1080,1350)
        snapshot['community_card']['won_value']=987654
        source.write_text(json.dumps(snapshot))
        hidden=analytics.onepager(source,output=folder/'hidden.html')
        assert '987,654' not in pathlib.Path(hidden['html']).read_text()
        (folder/'context/me.md').write_text('## Share money\nyes\n')
        shared=analytics.onepager(source,output=folder/'shared.html')
        assert '987,654' in pathlib.Path(shared['html']).read_text()
        cli=run('analytics.py','onepager','--file',source,'--week','2026-W42','--output',folder/'cli.html')
        assert json.loads(cli.stdout)['png'] == str((folder/'cli.png').resolve())
        assert not (folder/'data/analytics-history.jsonl').exists() and not (folder/'data/badges.jsonl').exists()
    print('SYNTHETIC frozen public onepager PASS: same28day/fixed targets/horizon; safe dynamic prose; optional unsafe names/source/contact dropped; unknown fields rejected; only public allowlist rendered; Share money opt-in; JSONL/week/CLI; measured1080x1350PNG')


def analytics_private_call_cards_contract():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('final-private-call-cards') as folder:
        analytics_sync_marker(folder)
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='943000001'
        seed([{'id':jid,'source':'outbound','status':'call','call_held_at':analytics_stamp(today-dt.timedelta(days=2)),
               'title':'Private call card client title'}])
        path=folder/'jobs'/jid;path.mkdir(exist_ok=True)
        quote='PRIVATE_CLIENT_QUOTATION_CANARY costs three hours weekly.'
        own='What outcome would make this worthwhile?'
        (path/'call.md').write_text('Member: Alex\nComplete: yes\nLanguage: English\nAlex: '+own+'\nClient: '+quote+'\nAlex: Let us agree the next step.\n')
        value=analytics.compute(today,now=now)
        item={'lead_id':jid,'reviewable':True,
              'points':[{'point':point,'state':'not needed' if point==6 else 'met','reason':'No separate objection occurred' if point==6 else '','quote':quote} for point in range(1,10)],
              'moments':[{'quote':quote,'better_wording':'Clarify the measured cost and desired outcome'} for _ in range(3)],
              'fix':'Clarify the outcome once','example':own,'next_step':'Client reviews scope on Friday'}
        value['reviews']['call'].update(fix=item['fix'],example=own,evidence_lead_ids=[jid],rubric=[item])
        prepared=analytics.prepare_snapshot(value,today,now=now)
        assert prepared['kpis']['call_review']['state']=='pass'
        assert len(prepared['call_cards'])==1
        card=prepared['call_cards'][0]
        assert card['lead_id']==jid and [point['point'] for point in card['points']]==list(range(1,10))
        assert all(point['quote']==quote for point in card['points']) and card['points'][5]['state']=='not needed'
        assert len(card['moments'])==3 and all(moment['better_wording'] for moment in card['moments'])
        assert (card['fix'],card['example'],card['next_step'])==(item['fix'],own,item['next_step'])
        assert {'label','date','duration_minutes','talk_share','questions','reviewable'}<=card.keys()
        assert all(point['quote_state']=='supported' for point in card['points'])
        unreviewed=copy.deepcopy(value);unreviewed['reviews']['call']['rubric'][0].update(reviewable=False,points=[],moments=[])
        unavailable=analytics.prepare_snapshot(unreviewed,today,now=now)['call_cards'][0]
        assert unavailable['reviewable'] is False and unavailable['reason'] and unavailable['points']==[]
        legacy=copy.deepcopy(value)
        for point in legacy['reviews']['call']['rubric'][0]['points']:point.pop('quote')
        oldcard=analytics.prepare_snapshot(legacy,today,now=now)['call_cards'][0]
        assert all(point['quote'] is None and point['quote_state']=='unknown' for point in oldcard['points'])
        assert quote not in json.dumps(prepared['community_card'])
        assert quote not in analytics.public_onepager_html(prepared['community_card'])
        analytics.privacy(prepared)
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['points'][0]['quote']='Invented unsupported quotation'
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Unsupported call quotation accepted')
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['points'][0]['quote']='Complete: yes'
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Transcript metadata accepted as supporting speech')
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['moments'].append({'quote':quote,'better_wording':own})
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('More than three call moments accepted')
    print('SYNTHETIC frozen private call card PASS: full9 local quotes/status; exactly3 moments/better wording; fix/example/agreed next step; unsupported quotes/moment4 rejected; private quotation absent from public allowlist')



def analytics_pipeline_probe_contract():
    import analytics
    import badges
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('stable-platform-probes') as folder:
        analytics_sync_marker(folder)
        first=analytics.timestamp(analytics_stamp(today-dt.timedelta(days=2))).astimezone(dt.timezone.utc).isoformat(); earlier=analytics.timestamp(analytics_stamp(today-dt.timedelta(days=3))).astimezone(dt.timezone.utc).isoformat()
        seed([{'id':str(944000000+i),'status':'new','source':'outbound'} for i in range(8)])
        insights={'data':{'rank':3,'competitors':8},'fetched_at':first,'source':'upwork-proposal'}
        proposal={'job_id':'944000000','proposal_id':'probe-p','status':'pending','applied_at':first,
                  'viewedByClient':True,'proposal_insights':insights}
        unseen=dict(proposal,job_id='944000001',proposal_id='probe-unseen',viewedByClient=False)
        sync={'proposals':[proposal,unseen],'earnings':[], 'connects':[
            {'transaction_id':'application','at':first,'amount':-16,'reason':'Proposal debit','job_id':'944000000'},
            {'transaction_id':'paid-invite','at':first,'amount':-4,'reason':'Paid invitation badge','purpose':'invitation badge'},
            {'transaction_id':'grant','at':first,'amount':10,'reason':'Monthly allocation'}]}
        run('sync.py','apply','--file','-',value=sync)
        job=records()['944000000'];observation=job['proposal_viewed_observation']; observed=job['proposal_viewed_at']
        assert job['proposal_viewed']['value'] is True and job['proposal_viewed']['source']=='upwork-proposal'
        assert observation['kind']=='flag-observed' and observation['event_time_known'] is False and observation['verified'] is True
        assert 'proposal_viewed_at' not in records()['944000001']
        changed=copy.deepcopy(sync);changed['proposals'][0].update(viewedByClient=False,
            proposal_insights=dict(insights,data={'rank':999}))
        run('sync.py','apply','--file','-',value=changed)
        job=records()['944000000']
        assert job['proposal_viewed']['value'] is False and job['proposal_viewed_at']==observed
        expected_insights=dict(insights,fetched_at=analytics.timestamp(first).astimezone(dt.timezone.utc).isoformat())
        assert job['proposal_insights']==expected_insights, 'First insights read is immutable.'
        result=analytics.compute(today,jobs=list(records().values()),now=now)
        viewed=result['stage_context']['applied_to_viewed']
        assert (viewed['k'],viewed['n'],viewed['value'])==(1,2,50) and viewed['evidence']==['944000000'], (viewed, records())
        assert 'not the actual view timestamp' in viewed['note']
        assert result['kpis']['value_per_100_connects']['n']==20, 'Every negative ledger debit, including paid invitation badges.'
        # Old exact invitation timestamp stays exact; fallback has explicit provenance.
        invitation={'job_id':'944000002','invitation_id':'probe-i','invited_at':earlier}
        fallback={'job_id':'944000003','invitation_id':'probe-f'}
        run('sync.py','apply','--file','-',value={'invitations':[invitation,fallback]})
        jobs=records();assert jobs['944000002']['invited_at']==earlier and jobs['944000002']['invited_at_source']=='room'
        fallback_at=jobs['944000003']['invited_at'];assert jobs['944000003']['invited_at_source']=='sync'
        run('sync.py','apply','--file','-',value={'invitations':[{'job_id':'944000002','invitation_id':'probe-i'},fallback]})
        assert records()['944000002']['invited_at']==earlier and records()['944000003']['invited_at']==fallback_at
        room={'job_id':'944000003','room_id':'probe-room','messages_complete':True,
              'messages':[{'from':'client','text':'Invitation details','at':earlier}]}
        run('sync.py','apply','--file','-',value={'invitations':[fallback],'threads':[room]})
        assert records()['944000003']['invited_at']==earlier and records()['944000003']['invited_at_source']=='room'
        request={'job_id':'944000004','session_id':'pending-session','request_id':'request-one','status':'pending',
                 'booked_at':first,'scheduled_at':analytics_stamp(today+dt.timedelta(days=2))}
        run('sync.py','apply','--file','-',value={'meetings':[request]})
        pending=records()['944000004'];requested_at=pending['call_requested_at']
        assert pending['call_request']['requested_at_source']=='sync' and 'call_booked_at' not in pending
        run('sync.py','apply','--file','-',value={'meetings':[request]})
        assert records()['944000004']['call_requested_at']==requested_at and 'call_booked_at' not in records()['944000004']
        held={'job_id':'944000005','session_id':'held','booked_at':earlier,'held_at':first,'duration_s':300}
        noshow={'job_id':'944000006','session_id':'absent','booked_at':earlier,'scheduled_at':first,'no_show':True}
        run('sync.py','apply','--file','-',value={'meetings':[held,noshow]})
        before={jid:copy.deepcopy(records()[jid]) for jid in ('944000005','944000006')}
        result=run('sync.py','apply','--file','-',value={'recaps':[{'job_id':jid,'recap_state':'unknown','recap_reason':'Read unavailable'} for jid in before]})
        assert result.returncode==0
        for jid,prior in before.items():
            current=records()[jid]
            assert current['recap_state']=='unknown' and current['call_sessions']==prior['call_sessions']
            assert current.get('call_held_at')==prior.get('call_held_at') and current.get('no_show')==prior.get('no_show')
        # CLI's ordinary note writer carries explicit human action proof, never inferred conversions.
        goal={'kpi':'reply_to_call','change':'Offer two concrete times','start':today.isoformat()}
        identity=analytics.goal_id(goal,'2026-W42');goal['goal_id']=identity
        for jid in ('944000000','944000001'):
            run('pipeline.py','observe',jid,'replied',analytics_stamp(today,0),'--source','upwork-thread','--verified')
        action={'goal_id':identity,'kpi':'reply_to_call','at':analytics_stamp(today,1),'evidence':'Member confirmed two times offered'}
        run('pipeline.py','note','944000000','analytics goal_action: '+json.dumps(action))
        run('pipeline.py','note','944000000','analytics goal_action: '+json.dumps(action))
        for bad in (dict(action,goal_id='wrong-goal'),dict(action,kpi='reply_rate'),dict(action,at=earlier),dict(action,evidence='')):
            run('pipeline.py','note','944000001','analytics goal_action: '+json.dumps(bad))
        quest=analytics.quest_progress({'week':'2026-W42','goals_next':[goal]},list(records().values()),today)[0]
        assert (quest['goal_id'],quest['done_k'],quest['done_n'],quest['execution_state'])==(identity,1,2,'partial'),quest
        unknown=analytics.quest_progress({'week':'2026-W42','goals_next':[dict(goal,goal_id='unknown-goal')]},list(records().values()),today)[0]
        assert unknown['done_k'] is None and unknown['done_n']==2 and unknown['execution_state']=='unverified' and unknown['note']
        native=records()['944000007'];native.update(applied_at=analytics_stamp(today,2),speed_to_lead_s=120,job_fit={'state':'pass','reason':'Fits'})
        assert badges.check(jobs=[native],now=now)==[], 'Unknown event source earns nothing.'
        native['applied_observation']={'source':'upwork-proposal','verified':True}
        native['application_date_unknown']=True
        assert badges.check(jobs=[native],now=now)==[]
        native.pop('application_date_unknown');native['imported']=True
        assert badges.check(jobs=[native],now=now)==[]
        native.pop('imported');awards=badges.check(jobs=[native],now=now)
        assert awards==[] and badges.award_lines(awards)==[], 'A single fast application never bypasses the weekly content criterion.'
        base=result if isinstance(result,dict) else analytics.compute(today,jobs=[],now=now)
        overlay=badges.voyage(badges.read_ledger(),base)
        assert len(overlay['stations'])==14
        station=next(row for row in overlay['stations'] if row['badge']=='Swift Sail')
        assert not station['earned'] and station['tier'] is None and station['next_tier']=='Bronze'
        assert overlay['calendar']==base['presentation']['voyage']['calendar']
        assert overlay['goals_history']==base['presentation']['voyage']['goals_history']
    print('SYNTHETIC final platform probes PASS: true/false persistent viewed context; immutable insights; exact/fallback/repair invitation; request not booking/replay; nonfatal unknown recap preserves held/no-show; all Connects debits; unique explicit goal action; confirmed/import/unknown badge gates; immediate pure14station ledger overlay')

def main():
    for path in sorted((ROOT/'.claude/commands').glob('*.md')):
        if path.name not in ('analytics.md','call-review.md'): feature_command(path.name)
    print('SYNTHETIC command hooks PASS: all eight foreign commands +3/-0 maximum against f7e43b0; corresponding feature references required.')
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
    audit_command_and_publication()
    audit_ingestion()
    audit_analytics()
    audit_analytics_extended()
    audit_producer_followup()
    audit_uma_review()
    audit_call_badge_evidence()
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
    analytics_final_numerical()
    analytics_event_ledger_contract()
    analytics_final_reader_contract()
    analytics_public_onepager_contract()
    analytics_private_call_cards_contract()
    analytics_pipeline_probe_contract()
    current = hashlib.sha256(REAL_JOBS.read_bytes()).hexdigest() if REAL_JOBS.exists() else None
    assert current == REAL_HASH, 'Real data/jobs.json changed'
    assert REAL_DATA_HASHES == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in (ROOT / 'data').rglob('*') if path.is_file()}, 'Real data files changed'
    print('PASS: dashboard and weekly analytics numbers reproduced by labelled synthetic fixtures; all real data files unchanged.')


if __name__ == '__main__':
    main()
