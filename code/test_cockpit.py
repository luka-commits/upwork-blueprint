"""Tests for code/cockpit.py: the state it serves and the doors it keeps shut.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import http.client
import json
import os
import pathlib
import sys
import tempfile
import threading
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
             'history': []}]), encoding='utf-8')
        os.environ['BLUEPRINT_JOBS'] = str(cls.jobs)
        cls.jobdir = pathlib.Path(cls.tmp.name) / 'jobfiles'
        (cls.jobdir / '111111').mkdir(parents=True)
        (cls.jobdir / '111111' / 'pitch.html').write_text('<h1>pitch</h1>', encoding='utf-8')
        (cls.jobdir / '111111' / 'thread.json').write_text(
            json.dumps({'messages': [{'from': 'client', 'text': 'Hi'}]}), encoding='utf-8')
        os.environ['BLUEPRINT_JOBDIR'] = str(cls.jobdir)
        sys.path.insert(0, str(CODE))
        import cockpit
        cls.cockpit = cockpit
        cls.server = cockpit.http.server.ThreadingHTTPServer(('127.0.0.1', 0), cockpit.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        os.environ.pop('BLUEPRINT_JOBS', None)
        os.environ.pop('BLUEPRINT_JOBDIR', None)
        cls.tmp.cleanup()

    def request(self, method, path, body=None, token=True, host='127.0.0.1'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Host': host, 'Content-Type': 'application/json'}
        if token:
            headers['X-Cockpit-Token'] = self.cockpit.TOKEN
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        r = conn.getresponse()
        data = r.read().decode('utf-8')
        conn.close()
        return r.status, data

    def test_state_hides_the_posting_and_counts_follow_ups(self):
        status, data = self.request('GET', '/api/state')
        self.assertEqual(status, 200)
        state = json.loads(data)
        first = next(j for j in state['jobs'] if j['id'] == '111111')
        self.assertTrue(first['has_posting'])
        self.assertNotIn('description', first['details'])
        self.assertEqual(state['today']['follow_ups_due'], ['222222'])

    def test_page_embeds_the_token(self):
        status, data = self.request('GET', '/', token=False)
        self.assertEqual(status, 200)
        self.assertIn(self.cockpit.TOKEN, data)

    def test_api_refuses_without_token_or_from_another_host(self):
        self.assertEqual(self.request('GET', '/api/state', token=False)[0], 403)
        self.assertEqual(self.request('GET', '/api/state', host='evil.example')[0], 403)
        self.assertEqual(self.request('POST', '/api/status', {'id': '111111', 'status': 'skipped'},
                                      token=False)[0], 403)

    def test_status_change_goes_through_the_pipeline(self):
        status, data = self.request('POST', '/api/status', {'id': '111111', 'status': 'skipped', 'note': 'too small'})
        self.assertEqual(status, 200, data)
        record = next(j for j in json.loads(self.jobs.read_text(encoding='utf-8')) if j['id'] == '111111')
        self.assertEqual(record['status'], 'skipped')
        self.assertIn('too small', record['notes'])

    def test_full_view_carries_files_and_thread(self):
        status, data = self.request('GET', '/api/job/111111')
        self.assertEqual(status, 200)
        job = json.loads(data)
        self.assertEqual([f['name'] for f in job['files']], ['pitch.html'])
        self.assertEqual(job['thread']['messages'][0]['text'], 'Hi')

    def test_note_and_video_go_through_the_pipeline(self):
        self.assertEqual(self.request('POST', '/api/note', {'id': '222222', 'text': 'Call on Tuesday'})[0], 200)
        self.assertEqual(self.request('POST', '/api/video', {'id': '222222', 'url': 'https://evil.example'})[0], 400)
        self.assertEqual(self.request('POST', '/api/video', {'id': '222222',
                                                             'url': 'https://www.loom.com/share/abc'})[0], 200)
        record = next(j for j in json.loads(self.jobs.read_text(encoding='utf-8')) if j['id'] == '222222')
        self.assertEqual(record['log'][0]['text'], 'Call on Tuesday')
        self.assertEqual(record['video'], 'https://www.loom.com/share/abc')

    def test_tasks_go_through_the_pipeline(self):
        self.assertEqual(self.request('POST', '/api/task', {'id': '222222', 'action': 'add', 'text': 'Send kickoff',
                                                            'due': '+1d'})[0], 200)
        self.assertEqual(self.request('POST', '/api/task', {'id': '222222', 'action': 'done', 'task': 1})[0], 200)
        self.assertEqual(self.request('POST', '/api/task', {'id': '222222', 'action': 'rm', 'text': 'x'})[0], 400)
        record = next(j for j in json.loads(self.jobs.read_text(encoding='utf-8')) if j['id'] == '222222')
        self.assertTrue(record['tasks'][0]['done_at'])

    def test_no_button_can_submit_to_upwork(self):
        for name, spec in self.cockpit.RUNNABLE.items():
            self.assertNotIn('mcp__upwork__upwork__confirm_preview', spec['tools'], name)
            self.assertFalse(any('send_message' in t or 'confirm_draft' in t for t in spec['tools']), name)

    def test_runs_list_is_empty_when_idle(self):
        status, data = self.request('GET', '/api/runs')
        self.assertEqual((status, json.loads(data)), (200, []))

    def test_unknown_or_unbuilt_command_is_refused(self):
        self.assertEqual(self.request('POST', '/api/run', {'command': 'rm-rf'})[0], 400)

    def test_artifact_path_cannot_escape(self):
        self.assertEqual(self.request('GET', '/jobs/111111/..%2F..%2Fcode%2Fcockpit.py', token=False)[0], 404)

    def test_streak_skips_weekends_and_never_breaks_on_today(self):
        import datetime as dt
        friday = dt.date(2026, 9, 11)
        monday = dt.date(2026, 9, 14)
        counts = {friday: 5, dt.date(2026, 9, 10): 5, dt.date(2026, 9, 9): 2}
        self.assertEqual(self.cockpit.streak(counts, 5, monday), 2)
        counts[monday] = 5
        self.assertEqual(self.cockpit.streak(counts, 5, monday), 3)

    def test_funnel_counts_the_highest_stage_ever_reached(self):
        import datetime as dt
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

    def test_stream_json_parsing(self):
        ev = self.cockpit.parse_event(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': 'Searching'}, {'type': 'tool_use', 'name': 'find_jobs'}]}}))
        self.assertEqual([e['kind'] for e in ev], ['text', 'tool'])
        done = self.cockpit.parse_event(json.dumps({'type': 'result', 'result': 'ok', 'is_error': False}))
        self.assertEqual(done['kind'], 'done')


if __name__ == '__main__':
    unittest.main()
