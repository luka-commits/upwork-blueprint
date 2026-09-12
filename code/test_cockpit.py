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

    def test_unknown_or_unbuilt_command_is_refused(self):
        self.assertEqual(self.request('POST', '/api/run', {'command': 'rm-rf'})[0], 400)

    def test_artifact_path_cannot_escape(self):
        self.assertEqual(self.request('GET', '/jobs/111111/..%2F..%2Fcode%2Fcockpit.py', token=False)[0], 404)

    def test_stream_json_parsing(self):
        ev = self.cockpit.parse_event(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': 'Searching'}, {'type': 'tool_use', 'name': 'find_jobs'}]}}))
        self.assertEqual([e['kind'] for e in ev], ['text', 'tool'])
        done = self.cockpit.parse_event(json.dumps({'type': 'result', 'result': 'ok', 'is_error': False}))
        self.assertEqual(done['kind'], 'done')


if __name__ == '__main__':
    unittest.main()
