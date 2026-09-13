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
import time
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
        cls.data = pathlib.Path(cls.tmp.name) / 'data'
        cls.data.mkdir()
        (cls.jobdir / '111111').mkdir(parents=True)
        (cls.jobdir / '111111' / 'pitch.html').write_text('<h1>pitch</h1>', encoding='utf-8')
        (cls.jobdir / '111111' / 'thread.json').write_text(
            json.dumps({'messages': [{'from': 'client', 'text': 'Hi'}]}), encoding='utf-8')
        (cls.jobdir / '111111' / 'replies.json').write_text(
            json.dumps({'drafts': [{'label': 'Direct', 'text': 'Hello'}]}), encoding='utf-8')
        (cls.jobdir / '111111' / 'outbox.json').write_text(
            json.dumps({'text': 'Hello'}), encoding='utf-8')
        cls.env = dict(os.environ, BLUEPRINT_JOBS=str(cls.jobs), BLUEPRINT_JOBDIR=str(cls.jobdir),
                       BLUEPRINT_DATA=str(cls.data))
        os.environ.update(BLUEPRINT_JOBS=str(cls.jobs), BLUEPRINT_JOBDIR=str(cls.jobdir),
                          BLUEPRINT_DATA=str(cls.data))
        sys.path.insert(0, str(CODE))
        import cockpit
        cls.cockpit = cockpit

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('BLUEPRINT_JOBS', None)
        os.environ.pop('BLUEPRINT_JOBDIR', None)
        os.environ.pop('BLUEPRINT_DATA', None)
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
        self.assertEqual(first['valid_artifacts'], ['pitch.html'])
        self.assertEqual(first['artifact_errors'], {})
        self.assertEqual(state['today']['follow_ups_due'], ['333333'])

    def test_full_view_carries_files_and_thread(self):
        r = self.cli('job', '111111')
        job = json.loads(r.stdout)
        self.assertEqual([f['name'] for f in job['files']], ['pitch.html'])
        self.assertEqual(job['valid_artifacts'], ['pitch.html'])
        self.assertRegex(job['files'][0]['version'], r'^\d+-\d+$')
        self.assertEqual(job['thread']['messages'][0]['text'], 'Hi')
        self.assertEqual(job['replies']['drafts'][0]['text'], 'Hello')
        self.assertEqual(job['outbox']['text'], 'Hello')
        self.assertEqual([f['name'] for f in job['files']], ['pitch.html'])
        self.assertEqual(self.cli('job', '999999').returncode, 1)

    def test_full_view_file_version_changes_when_an_artifact_is_revised(self):
        target = self.jobdir / '111111' / 'pitch.html'
        before = json.loads(self.cli('job', '111111').stdout)['files'][0]['version']
        original = target.read_text(encoding='utf-8')
        try:
            target.write_text('<h1>revised pitch with new content</h1>', encoding='utf-8')
            after = json.loads(self.cli('job', '111111').stdout)['files'][0]['version']
            self.assertNotEqual(before, after)
        finally:
            target.write_text(original, encoding='utf-8')

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

    @unittest.skipUnless(hasattr(time, 'tzset'), 'requires POSIX timezone control')
    def test_platform_timestamps_use_local_day_but_manual_dates_do_not_shift(self):
        previous = os.environ.get('TZ')
        try:
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            self.assertEqual(self.cockpit.parse_day('2026-01-01T23:30:00Z'), dt.date(2026, 1, 2))
            self.assertEqual(self.cockpit.parse_day('2026-01-01'), dt.date(2026, 1, 1))
            self.assertEqual(self.cockpit.parse_day('2026-01-01T23:30:00'), dt.date(2026, 1, 1))

            os.environ['TZ'] = 'America/Los_Angeles'
            time.tzset()
            self.assertEqual(self.cockpit.parse_day('2026-01-01T01:30:00Z'), dt.date(2025, 12, 31))
            self.assertEqual(self.cockpit.parse_day('2026-01-01'), dt.date(2026, 1, 1))
            self.assertEqual(self.cockpit.parse_day('2026-01-01T01:30:00'), dt.date(2026, 1, 1))
        finally:
            if previous is None:
                os.environ.pop('TZ', None)
            else:
                os.environ['TZ'] = previous
            time.tzset()

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
        self.assertEqual(counts['Found'], 3)
        self.assertEqual(counts['Replied'], 1)
        self.assertEqual(ins['funnel_scope'], 'all_saved')
        self.assertEqual(ins['applied_total'], 1)
        self.assertEqual(ins['replied_total'], 1)
        self.assertIsNone(ins['reply_rate'])
        self.assertIsNone(ins['reply_days'])
        self.assertEqual(ins['reply_time_sample'], 0)
        self.assertEqual(ins['reply_time_missing'], 1)

    def test_reply_delay_uses_only_verified_paired_event_times(self):
        def verified(applied, replied):
            return {'status': 'replied', 'applied_at': applied, 'replied_at': replied,
                    'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
                    'replied_observation': {'verified': True, 'source': 'upwork-thread'}}

        jobs = [
            verified('2026-09-01T10:00:00Z', '2026-09-01T22:00:00Z'),
            verified('2026-09-02T10:00:00Z', '2026-09-03T22:00:00Z'),
            {'status': 'replied', 'applied_at': '2026-09-04T10:00:00Z',
             'replied_at': '2026-09-04T11:00:00Z'},
            verified('2026-09-05T12:00:00Z', '2026-09-05T11:00:00Z'),
        ]
        ins = self.cockpit.insights(jobs, dt.date(2026, 9, 12))
        self.assertEqual(ins['reply_hours'], 24)
        self.assertEqual(ins['reply_days'], 1)

        self.assertEqual(ins['reply_time_sample'], 2)
        self.assertEqual(ins['reply_time_missing'], 2)

        short = self.cockpit.insights([
            verified('2026-09-01T10:00:00Z', '2026-09-01T10:02:00Z'),
        ], dt.date(2026, 9, 12))
        self.assertEqual(short['reply_hours'], 0.033)
        self.assertGreater(short['reply_days'], 0)

    def test_loom_quality_uses_only_bounded_saved_scores(self):
        jobs = [
            {'status': 'new', 'loom_review_score': 80},
            {'status': 'new', 'loom_review_score': 91},
            {'status': 'new', 'loom_review_score': 101},
            {'status': 'new', 'loom_review_score': True},
        ]
        ins = self.cockpit.insights(jobs, dt.date(2026, 9, 12))
        self.assertEqual(ins['loom_score'], 86)
        self.assertEqual(ins['loom_score_sample'], 2)
        empty = self.cockpit.insights([], dt.date(2026, 9, 12))
        self.assertIsNone(empty['loom_score'])
        self.assertEqual(empty['loom_score_sample'], 0)

    def test_28_day_applications_distinguish_zero_partial_and_unknown(self):
        today = dt.date(2026, 9, 12)
        empty = self.cockpit.insights([], today)
        self.assertEqual(empty['applications_28d'], 0)
        self.assertEqual(empty['applications_28d_known'], 0)
        self.assertTrue(empty['applications_28d_complete'])
        self.assertEqual(empty['per_week'], 0)

        jobs = [
            {'status': 'applied', 'applied_at': '2026-09-01T10:00:00Z'},
            {'status': 'won', 'application_date_unknown': True},
            {'status': 'replied', 'applied_at': '2099-01-01T10:00:00Z'},
            {'status': 'applied', 'applied_at': '2026-01-01T10:00:00Z'},
        ]
        partial = self.cockpit.insights(jobs, today)
        self.assertIsNone(partial['applications_28d'])
        self.assertEqual(partial['applications_28d_known'], 1)
        self.assertFalse(partial['applications_28d_complete'])
        self.assertEqual(partial['application_dates_unknown'], 2)
        self.assertIsNone(partial['per_week'])
        tracker = self.cockpit.tracker(jobs, 1, today)
        self.assertEqual(tracker['application_dates_unknown'], 2)
        self.assertEqual(tracker['week_done'], 0)

    def test_profile_standing_accepts_measured_and_legacy_shapes_with_cache_time(self):
        profile = self.data / 'profile.json'
        profile.write_text(json.dumps({
            'data': {
                'profileAggregates': {'totalEarnings': '$10K+', 'totalJobs': 12, 'totalFeedback': 9},
                'personalData': {'chargeRate': {'displayValue': '$80.00/hr'}},
            },
        }), encoding='utf-8')
        measured = self.cockpit.standing()
        self.assertEqual((measured['earned'], measured['jobs'], measured['reviews'], measured['rate']),
                         ('$10K+', 12, 9, '$80.00/hr'))
        self.assertIsNotNone(self.cockpit.parse_zoned_stamp(measured['profile_cached_at']))

        profile.write_text(json.dumps({
            'profileAggregates': {'totalEarnings': '$20K+', 'totalJobs': 20, 'totalFeedback': 15},
            'personalData': {'chargeRate': {'displayValue': '$95.00/hr'}},
        }), encoding='utf-8')
        legacy = self.cockpit.standing()
        self.assertEqual((legacy['earned'], legacy['jobs'], legacy['reviews'], legacy['rate']),
                         ('$20K+', 20, 15, '$95.00/hr'))


if __name__ == '__main__':
    unittest.main()
