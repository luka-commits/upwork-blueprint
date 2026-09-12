"""Tests for code/cockpit.py: the data the cockpit page reads.

    python3 -m unittest discover -s code -p 'test_*.py'

The page and its server live in cockpit/ and have their own tests: npm test there.
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent


class CockpitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.jobs = pathlib.Path(cls.tmp.name) / 'jobs.json'
        cls.jobs.write_text(json.dumps([
            {'id': '111111', 'title': 'CRM build', 'status': 'new', 'score': 80, 'found_at': '2026-09-12T08:00:00+00:00',
             'details': {'description': 'long posting', 'connects_cost': 16}, 'history': []},
            {'id': '222222', 'title': 'Old one', 'status': 'applied', 'score': 60, 'next_follow_up': '2000-01-01',
             'history': []},
            {'id': '333333', 'title': 'Previous client', 'status': 'won', 'next_follow_up': '2000-01-02',
             'follow_up_plan': {'lane': 'reactivation', 'step': 1, 'max_steps': 2}, 'history': []}]), encoding='utf-8')
        cls.jobdir = pathlib.Path(cls.tmp.name) / 'jobfiles'
        (cls.jobdir / '111111').mkdir(parents=True)
        (cls.jobdir / '111111' / 'pitch.html').write_text('<h1>pitch</h1>', encoding='utf-8')
        (cls.jobdir / '111111' / 'thread.json').write_text(
            json.dumps({'messages': [{'from': 'client', 'text': 'Hi'}]}), encoding='utf-8')
        (cls.jobdir / '111111' / 'replies.json').write_text(
            json.dumps({'drafts': [{'label': 'Direct', 'text': 'Hello'}]}), encoding='utf-8')
        (cls.jobdir / '111111' / 'outbox.json').write_text(
            json.dumps({'text': 'Hello'}), encoding='utf-8')
        cls.env = dict(os.environ, BLUEPRINT_JOBS=str(cls.jobs), BLUEPRINT_JOBDIR=str(cls.jobdir))
        os.environ.update(BLUEPRINT_JOBS=str(cls.jobs), BLUEPRINT_JOBDIR=str(cls.jobdir))
        sys.path.insert(0, str(CODE))
        import cockpit
        cls.cockpit = cockpit

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('BLUEPRINT_JOBS', None)
        os.environ.pop('BLUEPRINT_JOBDIR', None)
        cls.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CODE / 'cockpit.py'), *args],
                              capture_output=True, text=True, env=self.env)

    def test_state_hides_the_posting_and_counts_follow_ups(self):
        r = self.cli('state')
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads(r.stdout)
        first = next(j for j in state['jobs'] if j['id'] == '111111')
        self.assertTrue(first['has_posting'])
        self.assertNotIn('description', first['details'])
        self.assertEqual(first['artifacts'], ['pitch.html'])
        self.assertEqual(state['today']['follow_ups_due'], ['222222', '333333'])

    def test_full_view_carries_files_and_thread(self):
        r = self.cli('job', '111111')
        job = json.loads(r.stdout)
        self.assertEqual([f['name'] for f in job['files']], ['pitch.html'])
        self.assertEqual(job['thread']['messages'][0]['text'], 'Hi')
        self.assertEqual(job['replies']['drafts'][0]['text'], 'Hello')
        self.assertEqual(job['outbox']['text'], 'Hello')
        self.assertEqual([f['name'] for f in job['files']], ['pitch.html'])
        self.assertEqual(self.cli('job', '999999').returncode, 1)

    def test_streak_skips_weekends_and_never_breaks_on_today(self):
        friday = dt.date(2026, 9, 11)
        monday = dt.date(2026, 9, 14)
        counts = {friday: 5, dt.date(2026, 9, 10): 5, dt.date(2026, 9, 9): 2}
        self.assertEqual(self.cockpit.streak(counts, 5, monday), 2)
        counts[monday] = 5
        self.assertEqual(self.cockpit.streak(counts, 5, monday), 3)

    def test_application_dates_never_count_a_stage_move_twice_or_guess_import_dates(self):
        events = [{'status': 'applied', 'at': '2026-09-12T10:00:00Z'}, {'status': 'applied', 'at': '2026-09-13T10:00:00Z'}]
        self.assertEqual(self.cockpit.applied_dates([{'history': events}]), [dt.date(2026, 9, 12)])
        self.assertEqual(self.cockpit.applied_dates([{'history': events, 'application_date_unknown': True}]), [])

    def test_funnel_counts_the_highest_stage_ever_reached(self):
        jobs = [
            {'status': 'lost', 'history': [{'status': 'new', 'at': '2026-09-01T00:00:00+00:00'},
                                            {'status': 'applied', 'at': '2026-09-01T00:00:00+00:00'},
                                            {'status': 'replied', 'at': '2026-09-03T00:00:00+00:00'},
                                            {'status': 'lost', 'at': '2026-09-05T00:00:00+00:00'}]},
            {'status': 'new', 'history': [{'status': 'new', 'at': '2026-09-01T00:00:00+00:00'}]},
            {'status': 'skipped', 'history': [{'status': 'new', 'at': '2026-09-01T00:00:00+00:00'}]},
        ]
        ins = self.cockpit.insights(jobs, dt.date(2026, 9, 12))
        counts = {f['stage']: f['count'] for f in ins['funnel']}
        self.assertEqual(counts['Found'], 2)
        self.assertEqual(counts['Replied'], 1)
        self.assertIsNone(ins['reply_rate'])
        self.assertEqual(ins['reply_days'], 2)


if __name__ == '__main__':
    unittest.main()
