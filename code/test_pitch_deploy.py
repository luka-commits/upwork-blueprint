"""Tests for the isolated Vercel pitch publisher."""
import importlib.util
import pathlib
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pitch_deploy', CODE / 'pitch_deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class PitchDeployTest(unittest.TestCase):
    def test_extracts_the_immutable_vercel_deployment_url(self):
        stdout = 'https://upwork-pitches-a1b2-team.vercel.app\n'
        stderr = 'Production: https://upwork-pitches.vercel.app'
        self.assertEqual(deploy.deployment_url(stdout, stderr), 'https://upwork-pitches-a1b2-team.vercel.app')

    def test_staging_contains_only_the_public_page_and_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / 'pitch.html'
            source.write_text('<!doctype html><html><h1>Pitch</h1></html>', encoding='utf-8')
            stage = root / 'stage'
            deploy.write_site(stage, [('123456', source)], '123456')
            self.assertEqual({path.name for path in stage.iterdir()}, {'123456', 'index.html', 'vercel.json'})
            self.assertEqual((stage / 'index.html').read_text(encoding='utf-8'), source.read_text(encoding='utf-8'))
            self.assertEqual((stage / '123456' / 'index.html').read_text(encoding='utf-8'),
                             source.read_text(encoding='utf-8'))

    def test_configuration_is_transferable_and_validated(self):
        value = deploy.deployment_config({'VERCEL_TOKEN': 'token', 'VERCEL_SCOPE': 'team',
                                          'VERCEL_PITCH_PROJECT': 'member-pitches'})
        self.assertEqual(value['project'], 'member-pitches')
        self.assertEqual(value['domain'], 'member-pitches.vercel.app')
        self.assertEqual(value['scope'], 'team')
        with self.assertRaises(SystemExit):
            deploy.deployment_config({'VERCEL_PITCH_PROJECT': 'Not valid'})


if __name__ == '__main__':
    unittest.main()
