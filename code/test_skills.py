"""The Blueprint's writing and connector behavior must travel with the repo."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / '.claude' / 'skills'


class ProjectSkillsTest(unittest.TestCase):
    def test_required_skills_are_project_local_and_self_contained(self):
        names = {'lead-magnet', 'upwork-copy', 'upwork-follow-up', 'upwork-mcp'}
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

    def test_pitch_page_must_publish_only_the_checked_page(self):
        text = (ROOT / '.claude' / 'commands' / 'pitch-page.md').read_text(encoding='utf-8')
        self.assertIn('python3 code/pitch_deploy.py <id>', text)
        self.assertIn('Publishing is part of this command', text)
        self.assertIn('Never upload the job folder', text)

    def test_blank_profile_has_a_saved_handoff_instead_of_an_audit_loop(self):
        audit = (ROOT / '.claude' / 'commands' / 'audit.md').read_text(encoding='utf-8')
        profile = (ROOT / '.claude' / 'commands' / 'profile.md').read_text(encoding='utf-8')
        empty_branch = audit.split('**No title and no overview?**', 1)[1].split('## Step 2', 1)[0]
        self.assertRegex(empty_branch, r'Save\s+`audit-report.md`')
        self.assertIn('No profile text to score yet', empty_branch)
        self.assertIn('Do not invent a', empty_branch)
        self.assertIn('from-scratch', profile)
        self.assertIn('rather than sending them back', profile)

    def test_cockpit_command_uses_the_ready_url_and_names_the_send_boundary(self):
        text = (ROOT / '.claude' / 'commands' / 'cockpit.md').read_text(encoding='utf-8')
        self.assertIn('ROADMAP', text)
        self.assertIn('exact URL printed', text)
        self.assertIn('no command run is active', text)
        self.assertIn('Upwork calls: 0', text)
        self.assertIn('exact reply the member approves', text)
        self.assertNotIn('Nothing on that page sends anything', text)

    def test_list_commands_do_not_duplicate_the_full_list_in_chat(self):
        find_jobs = (ROOT / '.claude' / 'commands' / 'find-jobs.md').read_text(encoding='utf-8')
        inbox = (ROOT / '.claude' / 'commands' / 'inbox.md').read_text(encoding='utf-8')
        self.assertIn('complete scored list in the cockpit', find_jobs)
        self.assertIn('actual Upwork call count', find_jobs)
        self.assertNotIn('every job scored 70 or more', find_jobs)
        self.assertIn('full waiting list', inbox)
        self.assertIn('count and the first client', inbox)

    def test_direct_application_command_rejects_a_bare_video_link(self):
        text = (ROOT / '.claude' / 'commands' / 'apply.md').read_text(encoding='utf-8')
        gate = text.split('## Step 0', 1)[1].split('## Step 1', 1)[0]
        self.assertIn('valid HTTPS', gate)
        self.assertIn('including its video id', gate)
        self.assertIn('or invalid, write nothing', gate)

    def test_lead_magnet_is_local_paid_and_never_sent(self):
        skill = (SKILLS / 'lead-magnet' / 'SKILL.md').read_text(encoding='utf-8')
        command = (ROOT / '.claude' / 'commands' / 'lead-magnet.md').read_text(encoding='utf-8')
        for service in ('Firecrawl', 'Apify', 'DataForSEO'):
            self.assertIn(service, skill)
        self.assertIn('never retry', skill.casefold())
        self.assertIn('Never publish', skill)
        self.assertIn('Upwork calls: 0', command)


if __name__ == '__main__':
    unittest.main()
