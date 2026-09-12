"""Tests for code/profile_draft.py, on a fictional draft.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import pathlib
import sys
import unittest

CODE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location('profile_draft', CODE / 'profile_draft.py')
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)

FENCE = '`' * 3
DRAFT = f"""# Your profile

## Title

{FENCE}text
Shopify Expert | Klaviyo Email Flows | Conversion Rate Optimization
{FENCE}

## Overview

{FENCE}text
Stores I work with add 30% more revenue from email within 90 days.
✅ 212 stores served
✅ Welcome flow: 41% open rate
✅ Abandoned cart rebuild: recovered 18% of carts
Tools: Shopify, Klaviyo, Postscript, Gorgias, Recharge, Triple Whale, Figma
Send me your store URL and the one number you want to move.
{FENCE}

## Skills

""" + ''.join(f'- {s}\n' for s in (
    'Shopify', 'Klaviyo', 'Email Marketing', 'Conversion Rate Optimization', 'Copywriting',
    'Email Automation', 'Ecommerce', 'Shopify Plus', 'SMS Marketing', 'A/B Testing',
    'Marketing Automation', 'Email Design', 'Customer Retention', 'Figma', 'Postscript'))

PROOF = ('30% more revenue from email within 90 days · 212 stores · 41% open rate · '
         'recovered 18% of carts')


class ProfileDraftTest(unittest.TestCase):
    def test_parse_reads_sections(self):
        d = pd.parse(DRAFT)
        self.assertTrue(d['title'].startswith('Shopify Expert'))
        self.assertIn('Send me your store URL', d['overview'])
        self.assertEqual(len(d['skills']), 15)
        self.assertIsNone(d['portfolio'])

    def test_clean_draft_passes(self):
        self.assertEqual(pd.problems(pd.parse(DRAFT), PROOF, None), [])

    def test_unproven_number_fails(self):
        found = pd.problems(pd.parse(DRAFT), PROOF.replace('212 stores', ''), None)
        self.assertTrue(any('212' in f for f in found), found)

    def test_title_limit_and_em_dash(self):
        long = DRAFT.replace('Conversion Rate Optimization',
                             f'Conversion Rate Optimization For Every Store {chr(0x2014)} Always')
        found = pd.problems(pd.parse(long), PROOF, None)
        self.assertTrue(any('Upwork cuts at 70' in f for f in found), found)
        self.assertTrue(any('em-dash' in f for f in found), found)

    def test_targets_apply(self):
        targets = {'overview_words': {'label': 'Overview length', 'unit': 'words', 'kind': 'band',
                                      'low': 200, 'average': 250, 'high': 300}}
        found = pd.problems(pd.parse(DRAFT), PROOF, targets)
        self.assertTrue(any('Overview length' in f for f in found), found)

    def test_gohighlevel_title_is_covered_by_highlevel_skill(self):
        import profile_checks as pc
        self.assertTrue(pc.term_in_skills('GoHighLevel', ['HighLevel']))
        self.assertTrue(pc.term_in_skills('GHL', ['HighLevel']))
        self.assertFalse(pc.term_in_skills('GoHighLevel', ['Marketing']))


if __name__ == '__main__':
    unittest.main()
