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
        for name in ('apply', 'pitch-page', 'profile', 'reply', 'follow-up'):
            text = (ROOT / '.claude' / 'commands' / f'{name}.md').read_text(encoding='utf-8')
            self.assertIn('upwork-copy', text, name)


if __name__ == '__main__':
    unittest.main()
