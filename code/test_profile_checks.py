"""Tests for code/profile_checks.py, on two fictional profiles.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location(
    'profile_checks', pathlib.Path(__file__).resolve().parent / 'profile_checks.py')
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

WEAK = {
    'data': {
        'personalData': {
            'title': '<untrusted_participant_content>\nShopify Expert, Klaviyo, Email Marketing\n</untrusted_participant_content>',
            'description': "Hi there, I'm a passionate marketer.\nI love helping stores grow.\nThanks!",
            'chargeRate': {'rawValue': '45.00'},
        },
        'skills': [{'prettyName': 'Email Marketing'}, {'prettyName': 'Copywriting'}],
        'employmentRecords': [],
        'educationRecords': [{'degree': 'BA'}],
    },
    'languages': [{'language_code': 'en'}],
}
WEAK_HIGHLIGHTS = {'certificates': [], 'portfolio_projects': [{'title': 'Store redesign'}]}

STRONG = {
    'data': {
        'personalData': {
            'title': 'Shopify Expert | Klaviyo Email Flows | Conversion Rate Optimization',
            'description': (
                'Stores I work with add 30% more revenue from email within 90 days.\n'
                '✅ 212 stores served, $4M in tracked email revenue\n'
                '✅ Welcome flow for a skincare brand: 41% open rate, $80K in month one\n'
                '✅ Abandoned cart rebuild: recovered 18% of carts\n'
                'Tools: Shopify, Klaviyo, Postscript, Gorgias, Recharge, Triple Whale, Figma\n'
                'Send me your store URL and the one number you want to move.'),
            'chargeRate': {'rawValue': '95.00'},
        },
        'skills': [{'prettyName': n} for n in (
            'Shopify', 'Klaviyo', 'Email Marketing', 'Conversion Rate Optimization', 'Copywriting',
            'Email Automation', 'Ecommerce', 'Shopify Plus', 'SMS Marketing', 'A/B Testing',
            'Marketing Automation', 'Email Design', 'Customer Retention', 'Figma', 'Postscript')],
        'employmentRecords': [{'companyName': 'Agency'}],
        'educationRecords': [{'degree': 'BA'}],
    },
    'languages': [{'language_code': 'en'}],
}
STRONG_HIGHLIGHTS = {'certificates': [{'id': '1', 'name': 'Klaviyo Partner'}],
                     'portfolio_projects': [{'title': '41% open rate welcome flow'},
                                            {'title': '$80K in 30 days from one campaign'}]}


def by_id(results):
    return {r['id']: r for r in results}


class ProfileChecksTest(unittest.TestCase):
    def test_strong_profile_passes_everything(self):
        results = by_id(pc.run_checks(pc.normalize(STRONG, STRONG_HIGHLIGHTS)))
        failed = [k for k, r in results.items() if not r['passed']]
        self.assertEqual(failed, [])

    def test_weak_profile_fails_where_it_should(self):
        results = by_id(pc.run_checks(pc.normalize(WEAK, WEAK_HIGHLIGHTS)))
        for check in ('skills_cover_title', 'title_blocks', 'opening_no_greeting',
                      'opening_has_number', 'results_with_numbers', 'no_banned_phrases',
                      'closing_ask', 'skills_count', 'portfolio_count', 'portfolio_outcomes',
                      'certificates', 'complete'):
            self.assertFalse(results[check]['passed'], check)
        self.assertTrue(results['rate_set']['passed'])

    def test_untrusted_tags_are_stripped(self):
        self.assertEqual(pc.normalize(WEAK, WEAK_HIGHLIGHTS)['title'],
                         'Shopify Expert, Klaviyo, Email Marketing')

    def test_uncovered_title_terms_are_named(self):
        results = by_id(pc.run_checks(pc.normalize(WEAK, WEAK_HIGHLIGHTS)))
        detail = results['skills_cover_title']['detail']
        self.assertIn('Shopify', detail)
        self.assertIn('Klaviyo', detail)
        self.assertNotIn('Email Marketing', detail)

    def test_every_check_names_its_source(self):
        for r in pc.run_checks(pc.normalize(STRONG, STRONG_HIGHLIGHTS)):
            self.assertIn(r['source'], ('upwork', 'top-earners'))


if __name__ == '__main__':
    unittest.main()
