"""Tests for the automatic Vercel audit publisher."""

import importlib.util
import pathlib
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lead_magnet_deploy', CODE / 'lead_magnet_deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class LeadMagnetDeployTest(unittest.TestCase):
    def test_audit_uses_a_stable_nested_route(self):
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp) / 'lead-magnet.html'
            source.write_text('<html></html>', encoding='utf-8')
            route, pages = deploy.pages_for('123456', source, [])
            self.assertEqual(route, '123456/audit')
            self.assertEqual(pages, {'123456/audit': source})

    def test_shared_site_can_stage_pitch_and_audit_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            pitch = root / 'pitch.html'
            audit = root / 'audit.html'
            pitch.write_text('<html>pitch</html>', encoding='utf-8')
            audit.write_text('<html>audit</html>', encoding='utf-8')
            stage = root / 'stage'
            pitch_deploy = deploy.pitch_deploy
            pitch_deploy.write_site(stage, [('123456', pitch), ('123456/audit', audit)], '123456/audit')
            self.assertEqual((stage / '123456' / 'index.html').read_text(), '<html>pitch</html>')
            self.assertEqual((stage / '123456' / 'audit' / 'index.html').read_text(), '<html>audit</html>')
            self.assertEqual((stage / 'index.html').read_text(), '<html>audit</html>')


if __name__ == '__main__':
    unittest.main()
