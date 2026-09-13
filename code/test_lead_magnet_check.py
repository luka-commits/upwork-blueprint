"""Tests for the public SEO audit gate."""

import pathlib
import tempfile
import unittest

import lead_magnet_check


class LeadMagnetCheckTest(unittest.TestCase):
    def page(self, extra=''):
        return ('<!doctype html><html><head>'
                '<meta name="lead-magnet-template" content="upwork-lead-magnet-v1">'
                '<meta http-equiv="Content-Security-Policy" content="connect-src \'none\'">'
                '</head><body>'
                '<section data-audit-section="maps"></section>'
                '<section data-audit-section="profile"></section>'
                '<section data-audit-section="website"></section>'
                f'<p>Reply here on Upwork.</p>{extra}</body></html>')

    def problems(self, page):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / 'audit.html'
            path.write_text(page, encoding='utf-8')
            return lead_magnet_check.check_page(path)

    def test_accepts_the_current_self_contained_report(self):
        self.assertEqual(self.problems(self.page()), [])

    def test_rejects_external_resources_and_member_contact_routes(self):
        external = self.problems(self.page('<img src="https://example.com/a.jpg">'))
        self.assertTrue(any('external HTTP resource' in problem for problem in external))
        contact = self.problems(self.page('<p>Email me at member@example.com</p>'))
        self.assertTrue(any('email address' in problem for problem in contact))


if __name__ == '__main__':
    unittest.main()
