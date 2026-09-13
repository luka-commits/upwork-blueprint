"""Tests for code/pitch_check.py and code/pitch/generate.py helpers, on fictional input.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
import pitch_check  # noqa: E402

spec = importlib.util.spec_from_file_location('generate', CODE / 'pitch' / 'generate.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PROOF = """# Your proof

## Upwork track record · connector

- $10K+ earned, 19 completed jobs, 13 reviews
- Repeat clients: two

## Reviews · real client words, 5 stars each

- "Sharp and fast." · CRM build, $300
- "Would hire again." · funnel

## Credentials

- MBA in Marketing
"""


class PitchCheckTest(unittest.TestCase):
    def check(self, page):
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
            f.write(page)
        return pitch_check.check_page(f.name)

    def test_clean_page_passes(self):
        page = ('<html><style>a{color:red}</style><body><h1>Your CRM, rebuilt</h1>'
                '<a href="https://www.upwork.com/freelancers/~01abc">Upwork profile</a>'
                '<img src="data:image/png;base64,AAAA"><script>var x = "mailto:no@no.io";</script></body></html>')
        self.assertEqual(self.check(page), [])

    def test_contact_channels_fail(self):
        for bad in ('<a href="mailto:me@site.com">x</a>', '<a href="https://calendly.com/me">x</a>',
                    '<a href="https://wa.me/4915">x</a>', '<p>Reach me at me@site.com</p>',
                    '<p>Call +49 170 1234567</p>', '<p>Book a call with me</p>',
                    '<a href="https://www.linkedin.com/in/me">x</a>'):
            self.assertTrue(self.check(f'<html><body>{bad}</body></html>'), bad)

    def test_placeholder_fails(self):
        self.assertTrue(self.check('<p>{{HOOK}}</p>'))

    def test_loom_length(self):
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
            f.write('# Loom script\n\n' + ' '.join(['word'] * 480) + '\nSend it to me here on Upwork.')
        problems, words = pitch_check.check_loom(f.name)
        self.assertEqual(problems, [])
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
            f.write('# Loom script\n\n' + ' '.join(['word'] * 900) + '\nThanks.')
        problems, _ = pitch_check.check_loom(f.name)
        self.assertEqual(len(problems), 2)

    def test_loom_rejects_contact_routes(self):
        spoken = ' '.join(['word'] * 450)
        for contact in ('Email me at me@example.com.', 'Book a call with me.',
                        'See https://example.com/demo.'):
            with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
                f.write(f'# Loom script\n\n{spoken} {contact}\nReply here on Upwork.')
            problems, _ = pitch_check.check_loom(f.name)
            self.assertTrue(problems, contact)


class GenerateHelpersTest(unittest.TestCase):
    def test_client_job_title_cannot_break_the_copy_gate(self):
        self.assertEqual(gen.safe_job_title('CRM' + chr(0x2014) + 'Automation'), 'CRM-Automation')

    def test_pitch_defaults_to_three_reviews(self):
        parser_source = (CODE / 'pitch' / 'generate.py').read_text(encoding='utf-8')
        self.assertIn("add_argument('--max-reviews', type=int, default=3)", parser_source)

    def test_reviews_come_from_the_proof_file(self):
        r = gen.reviews(PROOF, 0)
        self.assertEqual([x['quote'] for x in r], ['Sharp and fast.', 'Would hire again.'])
        self.assertTrue(r[0]['stars'])

    def test_cv_block_builds_stats_from_the_track_record(self):
        block = gen.cv_block(PROOF, '**Languages:** German and English')
        self.assertIn('<strong>$10K+</strong><span>earned</span>', block)
        self.assertIn('MBA in Marketing', block)
        self.assertIn('German and English', block)

    def test_graph_validation(self):
        data, _ = gen.build_graph('{"nodes":[{"id":"a","label":"Form","kind":"source"},'
                                  '{"id":"b","label":"CRM","owner":"client"}],"edges":[{"from":"a","to":"b"}]}')
        self.assertIn('"CRM"', data)
        with self.assertRaises(SystemExit):
            gen.build_graph('{"nodes":[{"id":"a","label":"x"}],"edges":[{"from":"a","to":"zz"}]}')

    def test_graph_rejects_more_than_twelve_client_level_steps(self):
        nodes = ','.join(f'{{"id":"n{i}","label":"Step {i}"}}' for i in range(13))
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            gen.build_graph('{"nodes":[' + nodes + '],"edges":[]}')
        self.assertIn('12 or fewer', stderr.getvalue())

    def test_markers_strip_a_section(self):
        page = 'a<!-- videos:start -->YT<!-- videos:end -->b'
        self.assertEqual(gen.keep_or_strip(page, 'videos', False), 'ab')
        self.assertEqual(gen.keep_or_strip(page, 'videos', True), 'aYTb')

    def test_flow_builder_has_three_resting_actions_and_details_on_demand(self):
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        diagram = (CODE / 'pitch' / 'diagram.js').read_text(encoding='utf-8')
        artifact_bar = template.split('<div class="artifact-bar">', 1)[1].split('</div>', 1)[0]
        self.assertEqual(artifact_bar.count('data-dg='), 3)
        self.assertIn('data-dg="play"', artifact_bar)
        self.assertIn('data-dg="edit"', artifact_bar)
        self.assertIn('data-dg="full"', artifact_bar)
        self.assertIn('class="dg-inspector"', template)
        self.assertIn('.dg-foot[hidden] { display: none; }', template)
        self.assertIn("if (!editing) { sel = [id]; render(); return; }", diagram)
        self.assertNotIn('function noteCards()', diagram)


if __name__ == '__main__':
    unittest.main()
