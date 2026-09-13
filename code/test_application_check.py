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
"""

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
        self.assertNotIn('job title', text)

    def test_unproven_past_result_fails(self):
        fails, *_ = ac.check(GOOD, 'Shopify Email Expert', PROOF.replace('212 stores', ''))
        self.assertTrue(any('212' in f for f in fails), fails)

    def test_screening_answers_do_not_count(self):
        text = GOOD + '\n\nScreening answers\n\n' + ' '.join(['answer'] * 500)
        _, _, _, words, has_screening = ac.check(text)
        self.assertTrue(has_screening)
        self.assertLess(words, 140)

    def test_short_specific_letter_needs_no_numeric_bullet_quota(self):
        text = 'Your checkout needs to assign the right membership after payment. I would first trace that handoff in a test account. Walkthrough: https://www.loom.com/share/demo'
        self.assertEqual(ac.check(text)[0], [])

    def test_fake_video_host_is_rejected(self):
        for fake in ('https://loom.com.attacker.test/share/a', 'loom.com', 'https://loom.com/share/'):
            self.assertTrue(any('link' in f for f in ac.check(GOOD.replace('https://www.loom.com/share/example', fake), proof_text=PROOF)[0]))

    def test_screening_proof_and_empty_proof_are_checked(self):
        text = GOOD + '\n\n## Screening answers\n\n### Similar work?\nI delivered 999 projects.'
        self.assertTrue(any('999' in f for f in ac.check(text, proof_text=PROOF)[0]))
        self.assertTrue(any('212' in f for f in ac.check(GOOD)[0]))

    def test_client_screening_question_is_not_authored_copy(self):
        text = GOOD + '\n\n## Screening answers\n\n### What makes you passionate about this?\nI enjoy making a checkout understandable.'
        self.assertEqual(ac.check(text, proof_text=PROOF)[0], [])


if __name__ == '__main__':
    unittest.main()
