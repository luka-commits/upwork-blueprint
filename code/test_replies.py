"""Tests for the reply draft file contract."""
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest

CODE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('replies', CODE / 'replies.py')
replies = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replies)


class RepliesTest(unittest.TestCase):
    def test_two_distinct_drafts_pass(self):
        value = {'generated_at': '2026-09-12T12:00:00Z', 'drafts': [
            {'label': 'Direct', 'text': 'Thanks, I will check.'},
            {'label': 'Warm', 'text': 'Thanks for this. I will check and get back to you.'},
        ]}
        self.assertEqual(replies.validate(value), [])

    def test_bad_shape_and_em_dash_fail(self):
        value = {'generated_at': '', 'drafts': [
            {'label': '', 'text': 'Same'},
            {'label': 'Warm', 'text': 'Same'},
            {'label': 'Extra', 'text': 'No\u2014thanks'},
            {'label': 'Too many', 'text': 'Fourth'},
        ]}
        self.assertIn('drafts must contain two or three options', replies.validate(value))
        self.assertTrue(replies.validate({'generated_at': 'now', 'drafts': value['drafts'][:3]}))

    def test_check_reads_the_job_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp) / '123456'
            folder.mkdir(parents=True)
            (folder / 'replies.json').write_text(json.dumps({
                'generated_at': 'now',
                'drafts': [{'label': 'One', 'text': 'First'}, {'label': 'Two', 'text': 'Second'}],
            }), encoding='utf-8')
            old = os.environ.get('BLUEPRINT_JOBDIR')
            os.environ['BLUEPRINT_JOBDIR'] = tmp
            try:
                self.assertEqual(replies.cmd_check(types.SimpleNamespace(job_id='123456')), 0)
            finally:
                if old is None:
                    os.environ.pop('BLUEPRINT_JOBDIR', None)
                else:
                    os.environ['BLUEPRINT_JOBDIR'] = old


if __name__ == '__main__':
    unittest.main()
