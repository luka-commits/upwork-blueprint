"""Tests for the internal job price guide."""
import importlib.util
import pathlib
import unittest

CODE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pricing', CODE / 'pricing.py')
pricing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pricing)


class PricingTest(unittest.TestCase):
    def test_medium_confidence_adds_visible_scope_buffer(self):
        value = pricing.calculate(
            60, (8, 12, 18), 'medium',
            [{'label': 'Foundation', 'hours': 4}, {'label': 'Build and QA', 'hours': 8}],
            ['One account'], 'fixed')
        self.assertEqual(value['recommended_total'], 850)
        self.assertEqual(value['price_range'], {'low': 500, 'high': 1250})
        self.assertEqual(sum(item['amount'] for item in value['roadmap']), 850)
        self.assertEqual(value['risk_buffer_percent'], 15)

    def test_hourly_job_keeps_the_profile_rate(self):
        value = pricing.calculate(
            59.76, (4, 6, 9), 'high',
            [{'label': 'Audit', 'hours': 2}, {'label': 'Build', 'hours': 4}],
            ['Access is ready'], 'hourly')
        self.assertEqual(value['recommended_hourly_bid'], 59.76)
        self.assertEqual(value['recommended_total'], 400)

    def test_milestones_must_explain_likely_hours(self):
        with self.assertRaisesRegex(SystemExit, 'must equal the likely estimate'):
            pricing.calculate(60, (8, 12, 18), 'medium',
                              [{'label': 'Build', 'hours': 8}, {'label': 'QA', 'hours': 2}],
                              ['One account'], 'fixed')

    def test_small_milestones_never_over_allocate_the_total(self):
        value = pricing.calculate(
            20, (1, 2, 3), 'high',
            [{'label': 'One', 'hours': 0.5}, {'label': 'Two', 'hours': 0.5},
             {'label': 'Three', 'hours': 0.5}, {'label': 'Four', 'hours': 0.5}],
            ['One account'], 'fixed')
        amounts = [item['amount'] for item in value['roadmap']]
        self.assertEqual(sum(amounts), value['recommended_total'])
        self.assertTrue(all(amount >= 0 for amount in amounts))


if __name__ == '__main__':
    unittest.main()
