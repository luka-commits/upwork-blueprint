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
        self.assertNotIn('replied_at', jobs['100002'])
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

    def test_declined_proposal_is_not_revived_by_an_old_conversation(self):
        snapshot = {'proposals': [{'job_id': '100002', 'status': 'Declined'}],
                    'threads': [{'job_id': '100002', 'room_id': 'room-2', 'messages': [{'from': 'client', 'text': 'Old message'}]}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertEqual(self.status()['100002']['status'], 'lost')

    def test_newly_imported_proposal_can_reach_its_contract_in_the_same_sync(self):
        snapshot = {'proposals': [{'job_id': '100099', 'status': 'Accepted'}],
                    'contracts': [{'job_id': '100099', 'status': 'ACTIVE'}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertEqual(self.status()['100099']['status'], 'won')
        self.assertTrue(self.status()['100099']['application_date_unknown'])

    def test_verified_creation_time_repairs_unknown_import_without_new_stage_history(self):
        first = {'proposals': [{'job_id': '100099', 'title': 'Imported', 'status': 'Accepted'}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(first))
        imported = self.status()['100099']
        self.assertTrue(imported['application_date_unknown'])
        history = imported['history']

        repaired = {'proposals': [{'job_id': '100099', 'status': 'Accepted',
                                   'applied_at': '2026-01-05T11:30:00+01:00'}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(repaired))
        imported = self.status()['100099']
        self.assertEqual(imported['applied_at'], '2026-01-05T10:30:00+00:00')
        self.assertNotIn('application_date_unknown', imported)
        self.assertEqual(imported['history'], history)
        self.assertTrue(imported['applied_observation']['verified'])

        later = {'proposals': [{'job_id': '100099', 'status': 'Accepted',
                                'applied_at': '2026-02-01T10:30:00Z'}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(later))
        self.cli('pipeline.py', 'set', '100099', 'replied')
        self.cli('pipeline.py', 'set', '100099', 'applied')
        self.assertEqual(self.status()['100099']['applied_at'], '2026-01-05T10:30:00+00:00')

    def test_unrecognized_proposal_status_never_certifies_creation_time(self):
        before = self.status()['100002']['applied_at']
        snapshot = {'proposals': [
            {'job_id': '100001', 'status': 'Draft', 'applied_at': '2026-01-01T10:00:00Z'},
            {'job_id': '100002', 'status': 'Unknown', 'applied_at': '2026-01-02T10:00:00Z'},
        ]}
        result = self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = self.status()
        self.assertNotIn('applied_at', jobs['100001'])
        self.assertNotIn('applied_observation', jobs['100001'])
        self.assertEqual(jobs['100002']['applied_at'], before)
        self.assertNotIn('applied_observation', jobs['100002'])

    def test_only_complete_explicit_client_history_records_first_reply(self):
        complete = {
            'proposals': [{'job_id': '100002', 'status': 'Accepted',
                           'applied_at': '2026-01-05T10:00:00Z'}],
            'threads': [{'job_id': '100002', 'room_id': 'room-2', 'messages_complete': True,
                         'messages': [
                             {'from': 'me', 'at': '2026-01-05T11:00:00Z', 'text': 'Hello'},
                             {'from': 'client', 'at': '2026-01-05T12:30:00+01:00', 'text': 'First'},
                             {'from': 'client', 'at': '2026-01-05T13:00:00Z', 'text': 'Second'},
                         ]}],
        }
        result = self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(complete))
        self.assertEqual(result.returncode, 0, result.stderr)
        job = self.status()['100002']
        self.assertEqual(job['replied_at'], '2026-01-05T11:30:00+00:00')
        self.assertEqual(job['replied_observation']['source'], 'upwork-thread')

        for messages_complete in (False, 'true'):
            snapshot = {'threads': [{'job_id': '100001', 'room_id': 'room-1',
                                      'messages_complete': messages_complete,
                                      'messages': [{'from': 'client', 'at': '2026-01-01T10:00:00Z'}]}]}
            self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
            self.assertNotIn('replied_at', self.status()['100001'])

    def test_complete_history_still_needs_client_authorship_and_valid_time(self):
        snapshot = {'threads': [{'job_id': '100001', 'room_id': 'room-1',
                                  'messages_complete': True,
                                  'messages': [{'from': 'me', 'at': '2026-01-01T09:00:00Z'},
                                               {'at': '2026-01-01T10:00:00Z'},
                                               {'from': 'client', 'at': '2026-01-01T11:00:00Z'}]}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertNotIn('replied_at', self.status()['100001'])

        bad_client_time = {'threads': [{'job_id': '100003', 'room_id': 'room-3',
                                         'messages_complete': True,
                                         'messages': [{'from': 'client', 'at': 'not-a-date'},
                                                      {'from': 'client', 'at': '2026-01-01T11:00:00Z'}]}]}
        self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(bad_client_time))
        self.assertNotIn('replied_at', self.status()['100003'])

    def test_malformed_message_is_ignored_for_stage_and_blocks_verified_timing(self):
        snapshot = {'threads': [{'job_id': '100002', 'room_id': 'room-2',
                                  'messages_complete': True,
                                  'messages': [None,
                                               {'from': 'client', 'at': '2026-01-01T11:00:00Z'}]}]}
        result = self.cli('sync.py', 'apply', '--file', '-', stdin=json.dumps(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('replied_at', self.status()['100002'])


if __name__ == '__main__':
    unittest.main()
