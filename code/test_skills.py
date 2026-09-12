"""The Blueprint's writing and connector behavior must travel with the repo."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / '.claude' / 'skills'


class ProjectSkillsTest(unittest.TestCase):
    def test_required_skills_are_project_local_and_self_contained(self):
        names = {'upwork-copy', 'upwork-follow-up', 'upwork-mcp'}
        self.assertEqual({path.parent.name for path in SKILLS.glob('*/SKILL.md')}, names)
        for name in names:
            text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            self.assertRegex(text, rf'^---\nname: {re.escape(name)}\ndescription: .+\n---', name)
            for forbidden in ('/Users/', '~/.claude', 'write-as-luka'):
                self.assertNotIn(forbidden, text, f'{name} depends on {forbidden}')

    def test_every_current_client_copy_command_loads_the_local_copy_skill(self):
        for name in ('apply', 'call-prep', 'delivery', 'follow-up', 'pitch-page',
                     'profile', 'proposal', 'reply'):
            text = (ROOT / '.claude' / 'commands' / f'{name}.md').read_text(encoding='utf-8')
            self.assertIn('upwork-copy', text, name)

    def test_application_submission_stays_on_upwork(self):
        text = (ROOT / '.claude' / 'commands' / 'apply.md').read_text(encoding='utf-8')
        self.assertNotIn('confirm_preview', text)
        self.assertIn('submits the proposal on Upwork', text)

    def test_untrusted_text_does_not_suppress_safe_drafts(self):
        copy = (SKILLS / 'upwork-copy' / 'SKILL.md').read_text(encoding='utf-8')
        reply = (ROOT / '.claude' / 'commands' / 'reply.md').read_text(encoding='utf-8')
        for text in (copy, reply):
            self.assertRegex(text, r'(legitimate requirements|ordinary response requirements)')
            self.assertIn('safe draft', text)
            self.assertNotIn('offer no client-facing draft', text)

    def test_application_copy_has_no_forced_numbers_or_guarantees(self):
        text = (ROOT / '.claude' / 'commands' / 'apply.md').read_text(encoding='utf-8')
        for forced in ('300 to 400 words', 'five to seven numbered items',
                       'each carrying a number', 'forward promises'):
            self.assertNotIn(forced, text)
        self.assertIn('member-approved', text)
        self.assertIn('Never add a guarantee', text)
        self.assertIn('Until resolved, save no client-facing draft and create no preview', text)

    def test_profile_write_claims_stay_evidence_graded(self):
        canonical = (ROOT / 'references' / 'upwork-mcp.md').read_text(encoding='utf-8')
        profile = (ROOT / '.claude' / 'commands' / 'profile.md').read_text(encoding='utf-8')
        self.assertIn('not been exercised', canonical)
        self.assertIn('remain untested', profile)
        self.assertIn('manual', profile)

    def test_self_authored_profile_claim_is_not_treated_as_proof(self):
        copy = (SKILLS / 'upwork-copy' / 'SKILL.md').read_text(encoding='utf-8')
        profile = (ROOT / '.claude' / 'commands' / 'profile.md').read_text(encoding='utf-8')
        self.assertIn('self-authored claim', copy)
        self.assertIn('not verification', copy)
        self.assertIn('Do not promote it to verified proof', profile)

    def test_uncertain_message_send_is_never_retried_blindly(self):
        skill = (SKILLS / 'upwork-mcp' / 'SKILL.md').read_text(encoding='utf-8')
        rules = (ROOT / 'references' / 'upwork-rules.md').read_text(encoding='utf-8')
        for text in (skill, rules):
            self.assertRegex(text, r'new (?:message )?id')
            self.assertRegex(text, r'(Never|never)\s+retry blindly')
            self.assertIn('/inbox', text)

    def test_pitch_page_can_remain_local_while_loom_is_shared(self):
        text = (ROOT / '.claude' / 'commands' / 'pitch-page.md').read_text(encoding='utf-8')
        self.assertIn('local by default', text)
        self.assertIn('The Loom recording is shareable', text)
        self.assertRegex(text, r'Never publish or deploy as part of this\s+command')


if __name__ == '__main__':
    unittest.main()
