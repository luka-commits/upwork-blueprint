"""Tests for code/benchmark.py, on fictional profiles.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location('benchmark', CODE / 'benchmark.py')
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)


def other(name, badge, earnings, reviews, title, words, skills, rate):
    overview = 'Clients get 30% more booked calls.\n' + ' '.join(['word'] * words) + '\nSend me your URL?'
    return {'data': {'talentProfileByProfileKey': {
        'personalData': {'firstName': name, 'lastName': 'X.', 'title': title,
                         'description': overview, 'chargeRate': {'rawValue': str(rate)}},
        'skills': [{'prettyName': f'Skill {i}'} for i in range(skills)],
        'profileAggregates': {'top_rated': badge, 'totalEarnings': earnings,
                              'totalFeedback': reviews, 'totalJobs': reviews * 2},
    }}}


class BenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.files = []
        for i, args in enumerate([
            ('Ana', 'Top Rated Plus', '$1M+', 300, 'A | B | C', 300, 20, 100),
            ('Ben', 'Top Rated', '$100K+', 130, 'A | B | C | D', 200, 15, 50),
            ('Cy', None, '$10K+', 12, 'Just a sentence title', 100, 10, 30),
            ('Di', 'Top Rated', '$200K+', 90, 'A | B', 250, 18, 75),
        ]):
            f = d / f'p{i}.json'
            f.write_text(json.dumps(other(*args)), encoding='utf-8')
            self.files.append(f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_earnings_buckets(self):
        self.assertEqual(bm.earnings_value('$100K+'), 100_000)
        self.assertEqual(bm.earnings_value('$1M+'), 1_000_000)
        self.assertEqual(bm.earnings_value('$10K+'), 10_000)
        self.assertEqual(bm.earnings_value(None), 0)

    def test_rank_badge_then_earnings(self):
        order = sorted((bm.summary(f) for f in self.files), key=bm.strength, reverse=True)
        self.assertEqual([s['name'] for s in order], ['Ana X.', 'Di X.', 'Ben X.', 'Cy X.'])

    def test_targets_are_average_plus_minus_a_fifth(self):
        low, avg, high = bm.band([100, 50, 75])
        self.assertEqual((low, avg, high), (60.0, 75, 90.0))
        self.assertEqual(bm.verdict(59.76, low, high), 'below')
        self.assertEqual(bm.verdict(80, low, high), 'on target')
        self.assertEqual(bm.verdict(None, low, high), 'not set')

    def test_measure_needs_exactly_three(self):
        self.assertEqual(bm.main(['measure', str(self.files[0])]), 1)

    def test_check_gate(self):
        good = ('# Benchmark\n\nMeasured today\n**Next:** run /profile\n\n# Targets\n'
                '**Title length:** 60 to 90 characters\n**Overview:** 200 to 300 words\n'
                '**Skills:** 15 to 22\n**Rate:** 60 to 90 dollars\n\n'
                + ''.join(f'## Profile {i} · X\n**Measured:** 12 September, 100 reviews\n\n' for i in (1, 2, 3)))
        bad = good.replace('## Profile 3 · X\n**Measured:** 12 September, 100 reviews\n\n', '')
        d = pathlib.Path(self.tmp.name)
        (d / 'good.md').write_text(good, encoding='utf-8')
        (d / 'bad.md').write_text(bad + '| a | b |\n', encoding='utf-8')
        self.assertEqual(bm.main(['check', str(d / 'good.md')]), 0)
        self.assertEqual(bm.main(['check', str(d / 'bad.md')]), 1)


if __name__ == '__main__':
    unittest.main()
