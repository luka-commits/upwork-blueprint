"""Tests for code/threads.py: Upwork's raw messages become a clean chat.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import pathlib
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
            node(3, '2026-01-11T10:00:00Z', 'Yes let&#39;s do it!\n1\\. First step', side='freelancer', me=True, name='Luka K.'),
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


if __name__ == '__main__':
    unittest.main()
