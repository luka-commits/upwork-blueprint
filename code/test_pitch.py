"""Tests for code/pitch_check.py and code/pitch/generate.py helpers, on fictional input.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import importlib.util
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

CODE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
import pitch_check  # noqa: E402

spec = importlib.util.spec_from_file_location('generate', CODE / 'pitch' / 'generate.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

capture_spec = importlib.util.spec_from_file_location('pitch_capture', CODE / 'pitch_capture.py')
capture = importlib.util.module_from_spec(capture_spec)
capture_spec.loader.exec_module(capture)

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

    def test_graph_validates_job_specific_what_happens_copy(self):
        data, _ = gen.build_graph('{"nodes":[{"id":"a","label":"Roofing form",'
                                  '"note":"GoHighLevel Forms creates the roofing opportunity."}],"edges":[]}')
        self.assertIn('GoHighLevel Forms', data)
        with self.assertRaises(SystemExit):
            gen.build_graph('{"nodes":[{"id":"a","label":"Roofing form","note":""}],"edges":[]}')

    def test_graph_rejects_malformed_structure_and_ambiguous_ids(self):
        bad_graphs = (
            '[]',
            '{"nodes":{}}',
            '{"nodes":["not a node"]}',
            '{"nodes":[{"id":"e0","label":"Reserved"}]}',
            '{"nodes":[{"id":"a","label":"A","x":10}]}',
            '{"nodes":[{"id":"a","label":"A","kind":[]}]}',
            '{"nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],'
            '"edges":[{"from":[],"to":"b"}]}',
        )
        for graph in bad_graphs:
            with self.subTest(graph=graph), self.assertRaises(SystemExit):
                gen.build_graph(graph)

    def test_graph_rejects_cycles_duplicates_and_overlapping_groups(self):
        bad_graphs = (
            '{"nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],'
            '"edges":[{"from":"a","to":"b"},{"from":"b","to":"a"}]}',
            '{"nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],'
            '"edges":[{"from":"a","to":"b"},{"from":"a","to":"b"}]}',
            '{"nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],'
            '"edges":[{"from":"a","to":"b"}],"groups":['
            '{"label":"One","nodes":["a"]},{"label":"Two","nodes":["a","b"]}]}',
        )
        for graph in bad_graphs:
            with self.subTest(graph=graph), self.assertRaises(SystemExit):
                gen.build_graph(graph)

    def test_real_branching_fixture_passes_graph_gate(self):
        fixture = CODE.parent / 'data' / 'pitch-graph-2098510962412502381.json'
        data, fallback = gen.build_graph(str(fixture))
        graph = json.loads(data)
        self.assertEqual(len(graph['nodes']), 9)
        self.assertEqual(len(graph['edges']), 8)
        self.assertTrue(all(node.get('note') for node in graph['nodes']))
        self.assertIn('Message storm-hit areas', fallback)

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
        self.assertNotIn('id="dg-roadmap"', template)
        self.assertNotIn('Why it helps', template)
        self.assertIn('class="dg-inspector-mark"', template)
        self.assertIn('id="dg-inspector-form"', template)
        self.assertIn('.dg-foot[hidden] { display: none; }', template)
        self.assertIn("if (!editing) { sel = [id]; render(id); return; }", diagram)
        self.assertIn("tabindex: 0, role: 'button'", diagram)
        self.assertIn("var queue = starts.map", diagram)
        self.assertIn('function layoutByGroups()', diagram)
        self.assertNotIn('function renderRoadmap()', diagram)
        self.assertIn('function saveInspectorForm()', diagram)
        self.assertIn('if (layoutByGroups()) return;', diagram)
        self.assertIn('id="dg-status" role="status"', template)
        self.assertIn('var MIN_READABLE = .88;', diagram)
        self.assertNotIn('function noteCards()', diagram)

    def test_hero_illustration_is_embedded_only_in_the_hero(self):
        generator = (CODE / 'pitch' / 'generate.py').read_text(encoding='utf-8')
        diagram = (CODE / 'pitch' / 'diagram.js').read_text(encoding='utf-8')
        self.assertIn('<div class="hero-art" data-settle>', generator)
        self.assertNotIn('ILLUSTRATION_SRC', diagram)
        self.assertIn("REPORT_COVER = HERE / 'report-cover-example.jpg'", generator)

    def test_showcase_prefers_the_live_report_and_keeps_safe_fallbacks(self):
        generator = (CODE / 'pitch' / 'generate.py').read_text(encoding='utf-8')
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        self.assertIn("ap.add_argument('--showcase-html'", generator)
        self.assertIn('class="cover-face audit-frame"', generator)
        self.assertIn('sandbox="allow-scripts" loading="lazy"', generator)
        self.assertIn("ap.add_argument('--showcase-video'", generator)
        self.assertIn('autoplay muted loop playsinline', generator)
        self.assertIn('{{SHOWCASE_MEDIA}}', template)
        self.assertIn('grid-template-columns: minmax(250px, 310px) minmax(0, 1fr)', template)
        self.assertIn('height: 548px', template)
        self.assertIn('.showcase-preview .audit-frame { width: 390px; height: 717px;', template)
        self.assertIn('.audit-overlay .audit-window { width: min(404px, calc(100vw - 40px));', template)
        self.assertIn('.audit-overlay .audit-frame { width: 100%;', template)
        self.assertIn('data-audit-expand', template)
        self.assertIn('data-audit-dialog', template)
        self.assertIn('source.cloneNode(true)', template)
        self.assertIn('.audit-overlay .audit-window', template)
        self.assertIn('.showcase-copy { grid-column: 2;', template)
        self.assertIn('data-theme="{{THEME}}"', template)
        self.assertIn("choices=('warm', 'steel', 'signal', 'growth', 'calm')", generator)
        self.assertIn('class="audit-window"', template)
        self.assertNotIn('cover-book', template)
        self.assertNotIn('cover-sheet', template)
        self.assertIn('Cover of an example website audit', generator)

    def test_dither_can_use_job_specific_industry_art(self):
        generator = (CODE / 'pitch' / 'generate.py').read_text(encoding='utf-8')
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        self.assertIn("ap.add_argument('--dither-source'", generator)
        self.assertIn("'.svg': 'image/svg+xml'", generator)
        self.assertIn("dither_fit = '1.05' if args.dither_source else ''", generator)
        self.assertIn('data-fit="{{DITHER_FIT}}"', template)
        self.assertIn("Number.isFinite(requestedFit)", template)

    def test_recognizable_dither_art_is_never_vertically_flipped(self):
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        command = (CODE.parent / '.claude' / 'commands' / 'pitch-page.md').read_text(encoding='utf-8')
        self.assertNotIn('scaleY(-1)', template)
        self.assertIn('.band-next .dither-next { position: absolute; inset: 0; width: 100%; height: 100%;', template)
        self.assertIn('linear-gradient(180deg, #000 0%, #000 88%, transparent 100%)', template)
        self.assertIn('vertical flipping is not', command)
        self.assertIn('inspect its actual crop on the finished', command)
        self.assertIn('Name it as a free audit', command)

    def test_capture_accepts_a_valid_preview_when_chrome_does_not_exit(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = pathlib.Path(raw)
            page = folder / 'pitch.html'
            output = folder / '.pitch-preview.png'
            page.write_text('<!doctype html><title>Pitch</title>', encoding='utf-8')

            def create_then_timeout(*args, **kwargs):
                output.write_bytes(b'\x89PNG\r\n\x1a\n' + b'x' * 1000)
                raise capture.subprocess.TimeoutExpired(args[0], kwargs['timeout'])

            with mock.patch.object(capture, 'paths', return_value=(page, output)), \
                    mock.patch.object(capture, 'ROOT', folder), \
                    mock.patch.object(capture, 'browser_path', return_value='/bin/true'), \
                    mock.patch.object(capture.subprocess, 'run', side_effect=create_then_timeout), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(['123']), 0)

    def test_showcase_html_requires_the_current_safe_report(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = pathlib.Path(raw)
            current = folder / 'current.html'
            current.write_text('<meta name="lead-magnet-template" content="upwork-lead-magnet-v1">'
                               '<meta http-equiv="Content-Security-Policy" content="connect-src \'none\'">'
                               '<details data-audit-section="maps">Get found</details>'
                               '<details data-audit-section="profile">Build trust</details>'
                               '<details data-audit-section="website">Win enquiries</details>', encoding='utf-8')
            media = gen.showcase_media(current, '', folder / 'missing.jpg')
            self.assertIn('data:text/html;base64,', media)
            self.assertIn('Interactive example website audit', media)
            unsafe = folder / 'unsafe.html'
            unsafe.write_text(current.read_text(encoding='utf-8') + '<img src="https://example.com/a.jpg">', encoding='utf-8')
            with self.assertRaises(SystemExit):
                gen.showcase_media(unsafe, '', folder / 'missing.jpg')
            unsafe.write_text(current.read_text(encoding='utf-8') + '<a href="tel:+10000000000">Call</a>', encoding='utf-8')
            with self.assertRaises(SystemExit):
                gen.showcase_media(unsafe, '', folder / 'missing.jpg')
            bundled = folder / 'bundled.html'
            bundled.write_text(current.read_text(encoding='utf-8') + '<script>const protocol = "tel:";</script>', encoding='utf-8')
            self.assertIn('data:text/html;base64,', gen.showcase_media(bundled, '', folder / 'missing.jpg'))
            branded = folder / 'branded.html'
            branded.write_text(current.read_text(encoding='utf-8') + 'Pocket CEO', encoding='utf-8')
            with self.assertRaises(SystemExit):
                gen.showcase_media(branded, '', folder / 'missing.jpg')

    def test_proof_section_reserves_a_freelancer_photo(self):
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        self.assertIn('class="profile-story"', template)
        self.assertIn('{{PROFILE_MEDIA}}', template)
        self.assertLess(template.index('class="fit-list"'), template.index('{{PROFILE_MEDIA}}'))
        self.assertIn('aria-label="Freelancer photo placeholder"', gen.profile_media(''))

    def test_profile_media_embeds_a_member_supplied_action_photo(self):
        with tempfile.TemporaryDirectory() as td:
            photo = pathlib.Path(td) / 'member.webp'
            photo.write_bytes(b'photo')
            media = gen.profile_media(photo)
            self.assertIn('data:image/webp;base64,', media)
            self.assertIn('class="freelancer-photo has-photo"', media)
            self.assertIn('The person behind the build', media)

    def test_cv_uses_icons_for_verified_achievements(self):
        block = gen.cv_block(
            '## Upwork track record\n\n- $10K+ earned, 19 completed jobs, 13 reviews\n'
            '- Repeat clients\n\n## Credentials\n\n- MBA in Marketing and AI\n',
            '**Languages:** German and English',
        )
        self.assertEqual(block.count('class="cv-stat"'), 3)
        self.assertIn('class="cv-stat-icon"', block)
        self.assertIn('Proven experience behind your build', block)
        self.assertNotIn('<details', block)
        self.assertNotIn('<summary', block)

    def test_working_together_follows_the_lead_magnet_without_budget_or_timeline(self):
        template = (CODE / 'pitch' / 'template.html').read_text(encoding='utf-8')
        self.assertLess(template.index('id="proof"'), template.index('id="plan"'))
        self.assertIn('{{PLAN_CARDS}}', template)
        self.assertIn('{{PLAN_LEDE}}', template)
        self.assertEqual(gen.plan_lede(['audit']), 'Three clear steps from the first audit to a working system.')
        self.assertEqual(gen.plan_lede([]), 'Two clear steps from kickoff to a working system.')
        self.assertNotIn('<p class="plan-label">Budget</p>', template)
        self.assertNotIn('<p class="plan-label">Timeline</p>', template)
        self.assertEqual(
            gen.updates_html('Twice a week|Upwork, then ClickUp'),
            '<dl class="work-details"><div><dt>Cadence</dt><dd>Twice a week</dd></div>'
            '<div><dt>Platform</dt><dd>Upwork, then ClickUp</dd></div></dl>',
        )

    def test_working_together_repeats_the_upfront_audit_as_step_one(self):
        showcase = ['Your free roofing SEO audit', 'Send the site. I will audit it upfront.', '#next', 'Send it']
        cards = gen.plan_cards(
            showcase,
            ['GoHighLevel access', 'Roofing pipeline rules'],
            'Twice a week|Upwork, then ClickUp',
            ['See where roofing leads drop', 'Start with one build plan', 'Know what happens next'],
            [],
            'Roofing CRM',
        )
        self.assertEqual(cards.count('class="plan-item"'), 3)
        self.assertIn('<span class="plan-step">01</span>', cards)
        self.assertIn('Send the site. I will audit it upfront.', cards)
        self.assertIn('See where roofing leads drop', cards)
        self.assertLess(cards.index('Upfront audit'), cards.index('Onboarding'))

    def test_plan_cards_need_one_outcome_and_image_per_card(self):
        showcase = ['Audit', 'Audit it upfront.', '#next', 'Send it']
        with self.assertRaises(SystemExit):
            gen.plan_cards(showcase, ['Access'], 'Weekly|Upwork', ['Only one'], [], 'Roofing CRM')
        with self.assertRaises(SystemExit):
            gen.plan_cards(showcase, ['Access'], 'Weekly|Upwork', [], ['one.png'], 'Roofing CRM')


if __name__ == '__main__':
    unittest.main()
