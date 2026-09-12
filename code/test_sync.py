"""Tests for code/sync.py: Upwork's evidence moves jobs forward, never back.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.jobs, self.jobdir, self.data = base / 'jobs.json', base / 'jobfiles', base / 'data'
        self.env = dict(os.environ, BLUEPRINT_JOBS=str(self.jobs), BLUEPRINT_JOBDIR=str(self.jobdir),
                        BLUEPRINT_DATA=str(self.data))
        for rec in ({'id': '100001', 'title': 'Roofing CRM'}, {'id': '100002', 'title': 'Bakery bot'},
                    {'id': '100003', 'title': 'Zapier cleanup'}, {'id': '100004', 'title': 'Won already'}):
            self.cli('pipeline.py', 'add', '--file', '-', stdin=json.dumps(rec))
        self.cli('pipeline.py', 'set', '100002', 'applied')
        self.cli('pipeline.py', 'set', '100003', 'applied')
        self.cli('pipeline.py', 'set', '100004', 'won')

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, script, *args, stdin=None):
        return subprocess.run([sys.executable, str(CODE / script), *args], input=stdin,
                              capture_output=True, text=True, env=self.env)

    def status(self):
        return {j['id']: j for j in json.loads(self.jobs.read_text(encoding='utf-8'))}

    def test_snapshot_moves_saves_adds_and_records(self):
        self.cli('pipeline.py', 'set', '100002', 'replied')
        for job_id in ('100002', '100004'):
            folder = self.jobdir / job_id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'thread.json').write_text(json.dumps({'room_id': f'room-{job_id}'}), encoding='utf-8')
        self.cli('pipeline.py', 'follow-up', '100002', 'plan', '--lane', 'warm',
                 '--due', '2026-09-12', '--reason', 'Waiting for a decision')
        self.cli('pipeline.py', 'follow-up', '100004', 'plan', '--lane', 'reactivation',
                 '--due', '2026-09-12', '--reason', 'Previous client check-in')
        snapshot = {
            'proposals': [{'job_id': '100001', 'status': 'Accepted'},
                          {'job_id': '100003', 'status': 'Declined'},
                          {'job_id': '100004', 'status': 'Declined'},
                          {'job_id': '100009', 'title': 'Sent from the website', 'status': 'Accepted'}],
            'threads': [{'job_id': '100002', 'room_id': 'r1', 'awaiting_reply_from': 'you',
                         'messages': [{'from': 'client', 'name': 'Dana', 'at': '2026-09-12T10:00:00Z', 'text': 'Can we talk?'}]},
                        {'job_id': '100004', 'room_id': 'r4', 'awaiting_reply_from': 'you',
                         'messages': [{'from': 'client', 'name': 'Chris', 'at': '2026-09-12T11:00:00Z', 'text': 'One more thing.'}]}],
        }
        r = self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertEqual(r.returncode, 0, r.stderr)
        jobs = self.status()
        self.assertEqual(jobs['100001']['status'], 'applied')
        self.assertEqual(jobs['100002']['status'], 'replied')
        self.assertEqual(jobs['100002']['next_follow_up'], datetime.date.today().isoformat())
        self.assertNotIn('follow_up_plan', jobs['100002'])
        self.assertEqual(jobs['100002']['follow_up_history'][-1]['action'], 'cleared')
        self.assertEqual(jobs['100004']['next_follow_up'], datetime.date.today().isoformat())
        self.assertNotIn('follow_up_plan', jobs['100004'])
        self.assertEqual(jobs['100003']['status'], 'lost')
        self.assertEqual(jobs['100004']['status'], 'won')
        self.assertEqual(jobs['100009']['status'], 'applied')
        thread = json.loads((self.jobdir / '100002' / 'thread.json').read_text(encoding='utf-8'))
        self.assertEqual(thread['messages'][0]['text'], 'Can we talk?')
        record = json.loads((self.data / 'sync.json').read_text(encoding='utf-8'))
        self.assertEqual(record['added'], ['100009'])
        self.assertEqual(record['awaiting_you'], ['100002', '100004'])

    def test_offers_and_contracts_match_by_title_and_never_move_back(self):
        snapshot = {'offers': [{'title': 'bakery bot', 'state': 'awaiting_your_acceptance'}],
                    'contracts': [{'title': 'Roofing CRM', 'status': 'ACTIVE'}],
                    'proposals': [{'job_id': '100004', 'status': 'Accepted'}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        jobs = self.status()
        self.assertEqual(jobs['100002']['status'], 'offer')
        self.assertEqual(jobs['100001']['status'], 'won')
        self.assertEqual(jobs['100004']['status'], 'won')
        self.assertNotEqual(self.cli('sync.py', 'last').stdout.strip(), 'Never synced.')

    def test_ambiguous_title_does_not_award_the_wrong_contract(self):
        self.cli('pipeline.py', 'add', '--file', '-', stdin=json.dumps({'id': '100005', 'title': 'Roofing CRM'}))
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps({'contracts': [{'title': 'Roofing CRM', 'status': 'ACTIVE'}]}))
        self.assertEqual(self.status()['100001']['status'], 'new')
        self.assertEqual(self.status()['100005']['status'], 'new')


if __name__ == '__main__':
    unittest.main()
