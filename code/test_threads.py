"""Tests for code/threads.py: Upwork's raw messages become a clean chat.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest

CODE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('threads', CODE / 'threads.py')
threads = importlib.util.module_from_spec(spec)
spec.loader.exec_module(threads)

W = '<untrusted_participant_content>\n{}\n</untrusted_participant_content>'


def node(i, at, text, side='client', me=False, name='Dana K.'):
    n = {'id': f's{i}', 'createdDateTime': at, 'from': W.format(name), 'from_side': side, 'message': W.format(text)}
    if me:
        n['from_self'] = True
    return {'cursor': f's{i}', 'node': n}


class ThreadsTest(unittest.TestCase):
    def test_raw_edges_become_a_clean_chat_oldest_first(self):
        raw = {'data': {'roomStories': {'edges': [
            node(4, '2026-01-12T10:00:00Z', 'System event: ended. View this conversation on upwork.com for full context.'),
            node(3, '2026-01-11T10:00:00Z', 'Yes let&#39;s do it!\n1\\. First step', side='freelancer', me=True, name='Sam K.'),
            node(2, '2026-01-10T10:00:00Z', 'The freelancer accepted your offer. Please check your offers for details.', side='freelancer', me=True),
            node(1, '2026-01-09T10:00:00Z', 'Hi, can we talk?'),
            node(1, '2026-01-09T10:00:00Z', 'Hi, can we talk?'),
        ]}}}
        messages = threads.normalize(threads.edges_of(raw))
        self.assertEqual([m['id'] for m in messages], ['s1', 's2', 's3', 's4'])
        self.assertEqual(messages[0], {'id': 's1', 'from': 'client', 'name': 'Dana K.', 'at': '2026-01-09T10:00:00Z',
                                       'text': 'Hi, can we talk?', 'kind': 'message'})
        self.assertEqual((messages[1]['kind'], messages[1]['text']), ('event', 'The freelancer accepted your offer.'))
        self.assertEqual((messages[2]['from'], messages[2]['text']), ('me', "Yes let's do it!\n1. First step"))
        self.assertEqual((messages[3]['kind'], messages[3]['text']), ('event', 'Contract ended'))

    def test_clean_messages_pass_through(self):
        clean = [{'from': 'client', 'name': 'Dana', 'at': '2026-01-09T10:00:00Z', 'text': 'Hi'}]
        self.assertEqual(threads.normalize(clean)[0]['kind'], 'message')

    def test_confirm_saves_thread_and_removes_fixed_transfer_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            jobdir = root / 'jobfiles'
            folder = jobdir / '123456'
            folder.mkdir(parents=True)
            jobs = root / 'jobs.json'
            jobs.write_text(json.dumps([{'id': '123456'}]), encoding='utf-8')
            transfer = folder / '.thread-confirm.json'
            transfer.write_text(json.dumps({'messages': [
                {'id': 'new-1', 'from': 'me', 'at': '2026-09-12T12:00:00Z', 'text': 'Thanks.'},
            ]}), encoding='utf-8')
            (folder / 'outbox.json').write_text(json.dumps({
                'room_id': 'room-7', 'text': 'Thanks.', 'written_at': '2026-09-12T11:59:59Z', 'known_message_ids': [],
            }), encoding='utf-8')
            old_jobs, old_dir = os.environ.get('BLUEPRINT_JOBS'), os.environ.get('BLUEPRINT_JOBDIR')
            os.environ['BLUEPRINT_JOBS'], os.environ['BLUEPRINT_JOBDIR'] = str(jobs), str(jobdir)
            try:
                args = types.SimpleNamespace(job_id='123456', room='room-7', awaiting='them')
                self.assertEqual(threads.cmd_confirm(args), 0)
            finally:
                if old_jobs is None:
                    os.environ.pop('BLUEPRINT_JOBS', None)
                else:
                    os.environ['BLUEPRINT_JOBS'] = old_jobs
                if old_dir is None:
                    os.environ.pop('BLUEPRINT_JOBDIR', None)
                else:
                    os.environ['BLUEPRINT_JOBDIR'] = old_dir
            saved = json.loads((folder / 'thread.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['room_id'], 'room-7')
            self.assertEqual(saved['messages'][0]['text'], 'Thanks.')
            self.assertFalse(transfer.exists())
            outbox = json.loads((folder / 'outbox.json').read_text(encoding='utf-8'))
            self.assertIn('confirmed_at', outbox)

    def test_confirmation_requires_a_new_exact_message_after_approval(self):
        outbox = {'text': '  Thanks.  ', 'written_at': '2026-09-12T12:00:00Z', 'known_message_ids': ['old']}
        def message(id='new', at='2026-09-12T12:00:01Z', text='  Thanks.  ', side='me'):
            return {'id': id, 'at': at, 'text': text, 'from': side}
        self.assertIsNotNone(threads.confirmed_message([message()], outbox))
        for item in (message(id='old'), message(at='2026-09-12T11:59:00Z'), message(text='Thanks.'), message(side='client')):
            self.assertIsNone(threads.confirmed_message([item], outbox))
        wrapped = node(20, '2026-09-12T12:00:01Z', '  Thanks.  ', side='freelancer')
        self.assertIsNotNone(threads.confirmed_message([wrapped], outbox))

    def test_confirm_rejects_a_room_without_the_exact_approved_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            jobdir = root / 'jobfiles'
            folder = jobdir / '123456'
            folder.mkdir(parents=True)
            jobs = root / 'jobs.json'
            jobs.write_text(json.dumps([{'id': '123456'}]), encoding='utf-8')
            transfer = folder / '.thread-confirm.json'
            transfer.write_text(json.dumps({'messages': [
                {'from': 'me', 'at': '2026-09-12T12:00:00Z', 'text': 'Different text.'},
            ]}), encoding='utf-8')
            (folder / 'outbox.json').write_text(json.dumps({
                'room_id': 'room-7', 'text': 'Approved text.',
            }), encoding='utf-8')
            old_jobs, old_dir = os.environ.get('BLUEPRINT_JOBS'), os.environ.get('BLUEPRINT_JOBDIR')
            os.environ['BLUEPRINT_JOBS'], os.environ['BLUEPRINT_JOBDIR'] = str(jobs), str(jobdir)
            try:
                args = types.SimpleNamespace(job_id='123456', room='room-7', awaiting='them')
                self.assertEqual(threads.cmd_confirm(args), 1)
            finally:
                if old_jobs is None:
                    os.environ.pop('BLUEPRINT_JOBS', None)
                else:
                    os.environ['BLUEPRINT_JOBS'] = old_jobs
                if old_dir is None:
                    os.environ.pop('BLUEPRINT_JOBDIR', None)
                else:
                    os.environ['BLUEPRINT_JOBDIR'] = old_dir
            self.assertFalse((folder / 'thread.json').exists())
            self.assertTrue(transfer.exists())


if __name__ == '__main__':
    unittest.main()
