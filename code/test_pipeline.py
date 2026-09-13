"""Tests for code/pipeline.py and code/workspace.py. Never touch the real pipeline.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import datetime
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
PIPELINE = CODE / 'pipeline.py'


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, CODE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs = pathlib.Path(self.tmp.name) / 'jobs.json'
        self.jobdir = pathlib.Path(self.tmp.name) / 'jobfiles'
        self.env = dict(os.environ, BLUEPRINT_JOBS=str(self.jobs), BLUEPRINT_JOBDIR=str(self.jobdir))

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(PIPELINE), *args], input=stdin,
                              capture_output=True, text=True, env=self.env)

    def data(self):
        return json.loads(self.jobs.read_text(encoding='utf-8'))

    def add(self, record):
        r = self.run_cli('add', '--file', '-', stdin=json.dumps(record))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def room(self, job_id='J1'):
        folder = self.jobdir / job_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'thread.json').write_text(json.dumps({'room_id': 'room-1', 'messages': []}), encoding='utf-8')

    def confirmed(self, stamp, job_id='J1'):
        folder = self.jobdir / job_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'outbox.json').write_text(json.dumps({
            'job_id': job_id, 'confirmed_at': stamp, 'text': 'Approved text',
        }), encoding='utf-8')

    def test_add_stamps_and_skips_duplicates(self):
        self.add({'id': 'J1', 'title': 'Build a funnel', 'score': 80})
        job = self.data()[0]
        self.assertEqual(job['status'], 'new')
        self.assertEqual(job['history'][0]['status'], 'new')
        self.assertTrue(job['found_at'])
        r = self.add({'id': 'J1', 'title': 'changed'})
        self.assertIn('duplicate', r.stdout)
        self.assertEqual(len(self.data()), 1)
        self.assertEqual(self.data()[0]['title'], 'Build a funnel')

    def test_describe_only_revises_the_member_summary(self):
        self.add({'id': 'J1', 'summary': 'Old wording', 'rationale': 'A good fit.', 'details': {'description': 'Original posting.'}})
        before = self.data()[0]
        result = self.run_cli('describe', 'J1', '  Build a booking system.\n Test its reminders.  ')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.data()[0], {**before, 'summary': 'Build a booking system. Test its reminders.'})
        saved = self.jobs.read_bytes()
        self.assertNotEqual(self.run_cli('describe', 'J1', '  ').returncode, 0)
        self.assertNotEqual(self.run_cli('describe', 'missing', 'New summary').returncode, 0)
        self.assertEqual(self.jobs.read_bytes(), saved)

    def test_parallel_notes_do_not_lose_changes(self):
        self.add({'id': 'J1'})
        children = [subprocess.Popen([sys.executable, str(PIPELINE), 'note', 'J1', f'Note {i}'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env) for i in range(12)]
        for child in children:
            _, stderr = child.communicate(timeout=20)
            self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual({entry['text'] for entry in self.data()[0]['log']}, {f'Note {i}' for i in range(12)})

    def test_pitch_link_rejects_local_preview(self):
        self.add({'id': 'J1'})
        for value in ('http://localhost:4321/pitch', 'https://127.0.0.1/page', 'https://host.local/page', 'https://localhost./pitch', 'https://127.1/pitch'):
            self.assertNotEqual(self.run_cli('pitch-url', 'J1', value).returncode, 0)
        self.assertEqual(self.run_cli('pitch-url', 'J1', 'https://example.com/pitch').returncode, 0)
        self.assertEqual(self.data()[0]['pitch_url'], 'https://example.com/pitch')

    def test_loom_score_is_saved_as_owned_analytics_data(self):
        self.add({'id': 'J1'})
        result = self.run_cli('loom-score', 'J1', '86')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.data()[0]['loom_review_score'], 86)
        self.assertTrue(self.data()[0]['loom_reviewed_at'])
        before = self.jobs.read_bytes()
        self.assertNotEqual(self.run_cli('loom-score', 'J1', '101').returncode, 0)
        self.assertEqual(self.jobs.read_bytes(), before)

    def test_loom_review_preference_is_explicit_and_defaults_outside_storage(self):
        self.add({'id': 'J1'})
        self.assertNotIn('loom_review_enabled', self.data()[0])
        self.assertEqual(self.run_cli('loom-review', 'J1', 'off').returncode, 0)
        self.assertFalse(self.data()[0]['loom_review_enabled'])
        self.assertEqual(self.run_cli('loom-review', 'J1', 'on').returncode, 0)
        self.assertTrue(self.data()[0]['loom_review_enabled'])

    def test_lead_magnet_source_is_explicit_local_business_data(self):
        self.add({'id': 'J1', 'status': 'replied'})
        invalid = self.run_cli('lead-magnet-source', 'J1', 'http://localhost:3000', '--location', 'Berlin, Germany')
        self.assertNotEqual(invalid.returncode, 0)
        result = self.run_cli(
            'lead-magnet-source', 'J1', 'https://example.com',
            '--location', 'Berlin, Germany', '--place-id', 'ChIJ-example', '--language', 'English',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.data()[0]['lead_magnet_source']
        self.assertEqual(source, {
            'website': 'https://example.com',
            'location': 'Berlin, Germany',
            'place_id': 'ChIJ-example',
            'language': 'English',
        })
        self.assertTrue(self.data()[0]['lead_magnet_source_updated_at'])
        self.run_cli('prune', '--hours', '0')
        self.assertEqual(self.data()[0]['lead_magnet_source'], source)

    def test_lead_magnet_source_is_not_available_before_a_conversation(self):
        self.add({'id': 'J1', 'status': 'new'})
        result = self.run_cli('lead-magnet-source', 'J1', 'https://example.com', '--location', 'Berlin, Germany')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('lead_magnet_source', self.data()[0])

    def test_check_writes_nothing(self):
        self.add({'id': 'J1'})
        before = self.jobs.read_text(encoding='utf-8')
        r = self.run_cli('add', '--check', 'J1', 'J2')
        self.assertIn('KNOWN  J1', r.stdout)
        self.assertIn('NEW    J2', r.stdout)
        self.assertEqual(self.jobs.read_text(encoding='utf-8'), before)

    def test_detail_merges(self):
        self.add({'id': 'J1'})
        self.run_cli('detail', 'J1', '--file', '-', stdin='{"connects_cost": 22}')
        self.run_cli('detail', 'J1', '--file', '-', stdin='{"bid_avg": 17.74}')
        details = self.data()[0]['details']
        self.assertEqual(details['connects_cost'], 22)
        self.assertEqual(details['bid_avg'], 17.74)
        self.assertIn('fetched_at', details)

    def test_refreshed_detail_survives_pruning_of_an_old_discovery(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)).isoformat()
        self.add({'id': 'J1', 'found_at': old, 'description': 'old', 'details': {'client_city': 'Old city'}})
        self.run_cli('detail', 'J1', '--file', '-', stdin='{"connects_cost": 20}')
        self.run_cli('prune')
        job = self.data()[0]
        self.assertNotIn('description', job)
        self.assertNotIn('client_city', job['details'])
        self.assertEqual(job['details']['connects_cost'], 20)

    def test_applied_at_is_set_once(self):
        self.add({'id': 'J1'})
        blocked = self.run_cli('set', 'J1', 'applied', '--follow-up', '+3d')
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.data()[0]['status'], 'new')
        self.run_cli('set', 'J1', 'applied')
        job = self.data()[0]
        first = job['applied_at']
        self.assertIsNone(job['next_follow_up'])
        self.run_cli('set', 'J1', 'replied')
        self.run_cli('set', 'J1', 'applied')
        self.assertEqual(self.data()[0]['applied_at'], first)

    def test_applied_stage_clears_a_legacy_follow_up(self):
        self.add({'id': 'J1', 'status': 'applied', 'next_follow_up': '2026-09-20',
                  'follow_up_plan': {'lane': 'light', 'step': 1, 'max_steps': 2}})
        result = self.run_cli('set', 'J1', 'applied')
        self.assertEqual(result.returncode, 0, result.stderr)
        job = self.data()[0]
        self.assertIsNone(job['next_follow_up'])
        self.assertNotIn('follow_up_plan', job)

    def test_verified_observations_are_zoned_nonfuture_and_never_move_stage(self):
        self.add({'id': 'J1', 'status': 'applied', 'application_date_unknown': True})
        before_history = self.data()[0]['history']
        for args in (
            ('applied', '2026-01-02T10:00:00', '--source', 'upwork-proposal', '--verified'),
            ('applied', '2099-01-02T10:00:00Z', '--source', 'upwork-proposal', '--verified'),
            ('applied', '2026-01-02T10:00:00Z', '--source', 'upwork-proposal'),
            ('applied', '2026-01-02T10:00:00Z', '--source', 'up', '--verified'),
            ('applied', '2026-01-02T10:00:00Z', '--source', 'upwork-thread', '--verified'),
        ):
            self.assertNotEqual(self.run_cli('observe', 'J1', *args).returncode, 0)
        result = self.run_cli('observe', 'J1', 'applied', '2026-01-02T11:00:00+01:00',
                              '--source', 'upwork-proposal', '--verified')
        self.assertEqual(result.returncode, 0, result.stderr)
        job = self.data()[0]
        self.assertEqual(job['status'], 'applied')
        self.assertEqual(job['history'], before_history)
        self.assertEqual(job['applied_at'], '2026-01-02T10:00:00+00:00')
        self.assertNotIn('application_date_unknown', job)
        self.assertEqual(job['applied_observation']['source'], 'upwork-proposal')
        self.assertTrue(job['applied_observation']['verified'])

        # A later read may correct the first event backward, never forward.
        self.run_cli('observe', 'J1', 'applied', '2025-12-01T10:00:00Z',
                     '--source', 'upwork-proposal', '--verified')
        self.assertEqual(self.data()[0]['applied_at'], '2025-12-01T10:00:00+00:00')
        self.run_cli('observe', 'J1', 'applied', '2026-02-01T10:00:00Z',
                     '--source', 'upwork-proposal', '--verified')
        self.assertEqual(self.data()[0]['applied_at'], '2025-12-01T10:00:00+00:00')

        result = self.run_cli('observe', 'J1', 'replied', '2026-01-03T10:00:00Z',
                              '--source', 'upwork-thread', '--verified')
        self.assertEqual(result.returncode, 0, result.stderr)
        job = self.data()[0]
        self.assertEqual(job['status'], 'applied')
        self.assertEqual(job['history'], before_history)
        self.assertEqual(job['replied_at'], '2026-01-03T10:00:00+00:00')

        self.add({'id': 'J2', 'status': 'applied', 'applied_at': 'not-a-date',
                  'applied_observation': {'verified': True, 'source': 'wrong-source'}})
        repaired = self.run_cli('observe', 'J2', 'applied', '2026-01-04T10:00:00Z',
                                '--source', 'upwork-proposal', '--verified')
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(self.data()[1]['applied_at'], '2026-01-04T10:00:00+00:00')

    def test_closing_clears_follow_up_and_history_records_each_step(self):
        self.add({'id': 'J1'})
        self.run_cli('set', 'J1', 'applied')
        self.run_cli('set', 'J1', 'lost')
        job = self.data()[0]
        self.assertIsNone(job['next_follow_up'])
        self.assertEqual([h['status'] for h in job['history']], ['new', 'applied', 'lost'])

    def test_follow_up_sequence_advances_on_business_days_and_stops(self):
        self.add({'id': 'J1'})
        self.run_cli('set', 'J1', 'replied')
        self.room()
        r = self.run_cli('follow-up', 'J1', 'plan', '--lane', 'warm',
                         '--due', '2026-09-14', '--reason', '  They reviewed the solution  ')
        self.assertEqual(r.returncode, 0, r.stderr)
        job = self.data()[0]
        self.assertEqual(job['follow_up_plan']['step'], 1)
        self.assertEqual(job['next_follow_up'], '2026-09-14')

        self.confirmed('2026-09-18T12:00:00+00:00')
        self.run_cli('follow-up', 'J1', 'sent', '--on', '2026-09-18')
        job = self.data()[0]
        self.assertEqual(job['follow_up_plan']['step'], 2)
        self.assertEqual(job['next_follow_up'], '2026-09-25')
        repeated = self.run_cli('follow-up', 'J1', 'sent', '--on', '2026-09-18')
        self.assertIn('already recorded', repeated.stdout)
        self.assertEqual(self.data()[0]['follow_up_plan']['step'], 2)
        self.confirmed('2026-09-25T12:00:00+00:00')
        self.run_cli('follow-up', 'J1', 'sent', '--on', '2026-09-25')
        self.assertEqual(self.data()[0]['next_follow_up'], '2026-10-09')
        self.confirmed('2026-10-09T12:00:00+00:00')
        self.run_cli('follow-up', 'J1', 'sent', '--on', '2026-10-09')
        job = self.data()[0]
        self.assertIsNone(job['next_follow_up'])
        self.assertNotIn('follow_up_plan', job)
        self.assertEqual([item['step'] for item in job['follow_up_history']], [1, 2, 3])

    def test_follow_up_lanes_match_pipeline_stage(self):
        self.add({'id': 'J1'})
        self.assertEqual(self.run_cli('follow-up', 'J1', 'plan', '--lane', 'warm',
                                     '--due', '2026-09-14', '--reason', 'No room').returncode, 1)
        self.run_cli('set', 'J1', 'won')
        self.room()
        self.assertEqual(self.run_cli('follow-up', 'J1', 'plan', '--lane', 'warm',
                                     '--due', '2026-09-14', '--reason', 'Past client').returncode, 1)
        self.assertEqual(self.run_cli('follow-up', 'J1', 'plan', '--lane', 'reactivation',
                                     '--due', '2026-09-14', '--reason', 'Past client').returncode, 0)
        self.run_cli('follow-up', 'J1', 'clear', '--reason', 'Moved to another channel')
        self.assertNotIn('follow_up_plan', self.data()[0])
        self.assertIsNone(self.data()[0]['next_follow_up'])

    def test_same_status_twice_adds_no_history(self):
        self.add({'id': 'J1'})
        self.run_cli('set', 'J1', 'applied')
        self.run_cli('set', 'J1', 'applied')
        self.assertEqual(len(self.data()[0]['history']), 2)

    def test_unknown_id_and_status_fail_loudly(self):
        self.add({'id': 'J1'})
        self.assertEqual(self.run_cli('set', 'NOPE', 'applied').returncode, 1)
        self.assertEqual(self.run_cli('set', 'J1', 'notified').returncode, 1)
        self.assertEqual(self.run_cli('get', 'NOPE').returncode, 1)

    def test_notes_land_on_the_timeline(self):
        self.add({'id': 'J1'})
        self.run_cli('note', 'J1', '  Call   booked for Tuesday ')
        self.assertEqual(self.data()[0]['log'][0]['text'], 'Call booked for Tuesday')
        self.assertEqual(self.run_cli('note', 'J1', '   ').returncode, 1)

    def test_tasks_add_tick_and_delete(self):
        self.add({'id': 'J1'})
        self.run_cli('task', 'J1', 'add', 'Send the kickoff checklist', '--due', '+2d', '--time', '14:30')
        self.run_cli('task', 'J1', 'add', 'Ask for a review')
        tasks = self.data()[0]['tasks']
        self.assertEqual([t['id'] for t in tasks], [1, 2])
        self.assertEqual(tasks[0]['due'], (datetime.date.today() + datetime.timedelta(days=2)).isoformat())
        self.assertEqual(tasks[0]['due_time'], '14:30')
        self.assertIsNone(tasks[1]['due_time'])
        self.run_cli('task', 'J1', 'done', '1')
        self.assertTrue(self.data()[0]['tasks'][0]['done_at'])
        self.run_cli('task', 'J1', 'delete', '2')
        self.assertEqual(len(self.data()[0]['tasks']), 1)
        self.assertEqual(self.run_cli('task', 'J1', 'done', '9').returncode, 1)

    def test_task_time_requires_a_date_and_valid_24_hour_time(self):
        self.add({'id': 'J1'})
        self.assertEqual(self.run_cli('task', 'J1', 'add', 'No date', '--time', '14:30').returncode, 1)
        self.assertEqual(self.run_cli('task', 'J1', 'add', 'Bad time', '--due', '+1d', '--time', '24:00').returncode, 1)
        self.assertFalse(self.data()[0].get('tasks'))

    def test_video_takes_only_loom_or_youtube(self):
        self.add({'id': 'J1'})
        self.assertEqual(self.run_cli('video', 'J1', 'https://evil.example/x').returncode, 1)
        self.assertEqual(self.run_cli('video', 'J1', 'https://www.loom.com/share/abc123').returncode, 0)
        self.assertEqual(self.data()[0]['video'], 'https://www.loom.com/share/abc123')
        self.run_cli('video', 'J1', '-')
        self.assertNotIn('video', self.data()[0])

    def test_recording_links_are_small_safe_and_owned(self):
        self.add({'id': 'J1'})
        links = [{'label': 'GHL workflow', 'url': 'https://app.gohighlevel.com/location/123/workflows'}]
        result = self.run_cli('recording-links', 'J1', json.dumps(links))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.data()[0]['recording_links'], links)
        before = self.jobs.read_bytes()
        for invalid in (
            'not json',
            json.dumps([{'label': 'Bad', 'url': 'javascript:alert(1)'}]),
            json.dumps([{'label': '', 'url': 'https://example.com'}]),
        ):
            self.assertNotEqual(self.run_cli('recording-links', 'J1', invalid).returncode, 0)
            self.assertEqual(self.jobs.read_bytes(), before)
        self.assertEqual(self.run_cli('recording-links', 'J1', '[]').returncode, 0)
        self.assertNotIn('recording_links', self.data()[0])

    def test_prune_removes_upwork_content_keeps_own_work(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)).isoformat()
        self.add({'id': 'OLD', 'found_at': old, 'description': 'client text', 'budget': 500,
                  'details': {'connects_cost': 16}, 'score': 77, 'rationale': 'good fit'})
        self.add({'id': 'FRESH', 'description': 'fresh text'})
        for name, age in (('OLD', 30), ('FRESH', 1)):
            thread = self.jobdir / name / 'thread.json'
            thread.parent.mkdir(parents=True)
            thread.write_text('{"messages": []}', encoding='utf-8')
            stamp = (datetime.datetime.now() - datetime.timedelta(hours=age)).timestamp()
            os.utime(thread, (stamp, stamp))
        r = self.run_cli('prune')
        self.assertIn('1 jobs pruned, 3 cached fields removed, 1 saved threads deleted', r.stdout)
        self.assertFalse((self.jobdir / 'OLD' / 'thread.json').exists())
        self.assertTrue((self.jobdir / 'FRESH' / 'thread.json').exists())
        by_id = {j['id']: j for j in self.data()}
        self.assertNotIn('description', by_id['OLD'])
        self.assertNotIn('details', by_id['OLD'])
        self.assertEqual(by_id['OLD']['score'], 77)
        self.assertEqual(by_id['OLD']['rationale'], 'good fit')
        self.assertEqual(by_id['FRESH']['description'], 'fresh text')

    def test_disqualification_reason_survives_pruning_and_reaches_search_lessons(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)).isoformat()
        self.add({'id': 'NOFIT', 'title': 'Fictional CRM support', 'found_at': old,
                  'notes': 'Prior decision.', 'description': 'Cached job content',
                  'next_follow_up': '2026-10-01', 'follow_up_plan': {'step': 1}})
        reason = 'not a fit: Ongoing support, not an implementation project.'
        result = self.run_cli('set', 'NOFIT', 'skipped', '--note', reason)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_cli('prune').returncode, 0)
        saved = self.data()[0]
        self.assertEqual(saved['status'], 'skipped')
        self.assertEqual(saved['notes'], f'Prior decision. {reason}')
        self.assertIsNone(saved['next_follow_up'])
        self.assertNotIn('follow_up_plan', saved)
        self.assertNotIn('description', saved)
        lessons = subprocess.run([sys.executable, str(CODE / 'jobs.py'), 'lessons'],
                                 capture_output=True, text=True, env=self.env)
        self.assertEqual(lessons.returncode, 0, lessons.stderr)
        self.assertIn(reason, lessons.stdout)
        self.assertIn('Fictional CRM support', lessons.stdout)
        before = self.data()
        self.assertEqual(self.run_cli('set', 'NOFIT', 'new').returncode, 0)
        self.assertEqual(self.data()[0]['notes'], before[0]['notes'])

    def test_disqualification_without_reason_never_invents_one(self):
        self.add({'id': 'NOFIT'})
        self.assertEqual(self.run_cli('set', 'NOFIT', 'skipped', '--note', 'not a fit').returncode, 0)
        self.assertEqual(self.data()[0]['notes'], 'not a fit')

    def test_trim_keeps_live_pipeline(self):
        pipeline = load_module('pipeline')
        jobs = [{'id': f'OLD-{i}', 'status': 'new', 'found_at': f'2020-01-01T00:00:{i:02d}+00:00'}
                for i in range(5)]
        jobs += [{'id': f'N-{i}', 'status': 'new', 'found_at': f'2026-01-01T00:00:00+00:00'}
                 for i in range(pipeline.KEEP)]
        jobs += [{'id': 'LIVE', 'status': 'applied', 'found_at': '2019-01-01T00:00:00+00:00'}]
        kept, dropped = pipeline.trim(jobs)
        ids = {j['id'] for j in kept}
        self.assertEqual(dropped, 6)
        self.assertIn('LIVE', ids)
        self.assertNotIn('OLD-0', ids)


class WorkspaceTest(unittest.TestCase):
    def test_copies_once_and_never_overwrites(self):
        workspace = load_module('workspace')
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / 'root'
            starters = pathlib.Path(tmp) / 'starters'
            (starters / 'context').mkdir(parents=True)
            (starters / 'context' / 'me.md').write_text('starter', encoding='utf-8')
            self.assertEqual(workspace.ensure(root, starters), ['context/me.md'])
            (root / 'context' / 'me.md').write_text('mine', encoding='utf-8')
            self.assertEqual(workspace.ensure(root, starters), [])
            self.assertEqual((root / 'context' / 'me.md').read_text(encoding='utf-8'), 'mine')


if __name__ == '__main__':
    unittest.main()
