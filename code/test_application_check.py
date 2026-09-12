"""Tests for code/application_check.py, on a fictional letter.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import application_check as ac  # noqa: E402

GOOD = """Hello,

I read your post for a Shopify Email Expert to rebuild your Klaviyo flows. Stores I work with add 30% more revenue from email within 90 days, and I have rebuilt flows for 212 stores.

Here's what I'll deliver:

1. A welcome flow with 3 emails live in 2 days
2. An abandoned cart flow with 2 reminders at 1 and 24 hours
3. A browse abandonment flow covering your 4 top categories
4. A post-purchase flow with 1 review ask after 10 days
5. A monthly report on the 5 numbers that matter

Here is my walkthrough of the plan: https://www.loom.com/share/example

I work in milestones, so you approve each phase before the next one.

Send me your store URL here on Upwork and I'll point out the first fix.
""" + ' '.join(['word'] * 240)

PROOF = '30% more revenue from email within 90 days · 212 stores'


class ApplicationCheckTest(unittest.TestCase):
    def test_good_letter_passes(self):
        fails, _, eye, words, _ = ac.check(GOOD, 'Shopify Email Expert', PROOF)
        self.assertEqual(fails, [], fails)
        self.assertTrue(all(found for _, found in eye))

    def test_failures_are_named(self):
        bad = GOOD.replace('Shopify Email Expert', 'job') + ' I would love to help. ' + chr(0x2014)
        fails, *_ = ac.check(bad, 'Shopify Email Expert', PROOF)
        text = ' '.join(fails)
        self.assertIn('generic phrasing', text)
        self.assertIn('em-dash', text)
        self.assertIn('job title', text)

    def test_unproven_past_result_fails(self):
        fails, *_ = ac.check(GOOD, 'Shopify Email Expert', PROOF.replace('212 stores', ''))
        self.assertTrue(any('212' in f for f in fails), fails)

    def test_screening_answers_do_not_count(self):
        text = GOOD + '\n\nScreening answers\n\n' + ' '.join(['answer'] * 500)
        _, _, _, words, has_screening = ac.check(text)
        self.assertTrue(has_screening)
        self.assertLess(words, 400)


if __name__ == '__main__':
    unittest.main()
