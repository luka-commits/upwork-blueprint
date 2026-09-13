"""Contract tests for the portable, evidence-only lead magnet renderer."""

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDERER = ROOT / '.claude' / 'skills' / 'lead-magnet' / 'scripts' / 'render_report.py'
BUILDER = ROOT / '.claude' / 'skills' / 'lead-magnet' / 'scripts' / 'build.py'
DEMO = ROOT / '.claude' / 'skills' / 'lead-magnet' / 'scripts' / 'demo.py'
SKILL = ROOT / '.claude' / 'skills' / 'lead-magnet'
PIPELINE = ROOT / 'code' / 'pipeline.py'
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'code'))
spec = importlib.util.spec_from_file_location('lead_magnet_renderer', RENDERER)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
build_spec = importlib.util.spec_from_file_location('lead_magnet_builder', BUILDER)
builder = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(builder)
search_spec = importlib.util.spec_from_file_location('lead_magnet_search', SKILL / 'code' / 'pull_search.py')
search = importlib.util.module_from_spec(search_spec)
search_spec.loader.exec_module(search)
profile_spec = importlib.util.spec_from_file_location('lead_magnet_profile', SKILL / 'scripts' / 'gbp_rich.py')
profile = importlib.util.module_from_spec(profile_spec)
profile_spec.loader.exec_module(profile)
keywords_spec = importlib.util.spec_from_file_location('lead_magnet_keywords', SKILL / 'code' / 'proposal_keywords.py')
keywords = importlib.util.module_from_spec(keywords_spec)
keywords_spec.loader.exec_module(keywords)


class LeadMagnetRendererTest(unittest.TestCase):
    def setUp(self):
        self.cro = {
            'elements': [
                {'label': 'Clear action', 'present': True, 'evidence': 'Book a call'},
                {'label': 'Fast mobile page', 'present': False, 'evidence': 'largest item appears after 5.2 s'},
                {'label': 'Not applicable', 'present': False, 'applies': False},
            ],
            'speed': {'ok': True, 'scores': {'performance': 61, 'seo': 92}, 'desktopScreenshot': 'javascript:bad'},
        }
        ranks = [1, 2, 8, 12, None] * 5
        self.search = {
            'geoGrid': {
                'keyword': 'roof repair', 'ranks': ranks, 'requestedPoints': 25,
                'checkedPoints': 25, 'winners': [{'name': 'Competitor', 'domain': 'competitor.test'}],
            },
            'gbp': {'auditRows': [
                {'label': 'Phone', 'value': 'A public phone is listed.', 'status': 'good'},
                {'label': 'Updates', 'value': 'No recent update was found.', 'status': 'warn'},
                {'label': 'Booking', 'value': 'No booking link was found.', 'status': 'bad'},
            ]},
        }
        self.site = {'pages': [
            {'path': '/', 'title': 'Example'},
            {'path': '/contact', 'title': 'Contact Example'},
        ]}

    def test_scores_use_only_measured_denominators(self):
        self.assertEqual(renderer.maps_score(self.search), (0.4, 10, 25))
        self.assertEqual(renderer.profile_score(self.search)[0], 0.5)
        self.assertEqual(renderer.website_score(self.cro)[0], 0.5)
        self.assertEqual(renderer.overall_score([0.5, None, 1.0]), 0.75)

    def test_builder_derives_location_from_confirmed_google_profile(self):
        self.assertEqual(
            builder.profile_location({'city': 'Berlin', 'country': 'Germany'}),
            'Berlin, Germany',
        )
        self.assertEqual(
            builder.profile_location({
                'city': 'Manchester',
                'address': '1 Example Road, Manchester, United Kingdom',
            }),
            'Manchester, United Kingdom',
        )
        with self.assertRaisesRegex(RuntimeError, 'did not provide a city and country'):
            builder.profile_location({'coordinate': '52.5,13.4'})

    def test_report_has_exactly_three_sections_and_no_outbound_route(self):
        page = renderer.render('Example & Sons', self.cro, self.search, '2026-09-13', site=self.site)
        self.assertEqual(page.count('data-audit-section="'), 3)
        self.assertIn('name="lead-magnet-template" content="upwork-lead-magnet-v1"', page)
        self.assertIn('Get found', page)
        self.assertIn('Build trust', page)
        self.assertIn('Win enquiries', page)
        self.assertIn('Example &amp; Sons', page)
        self.assertIn('Almost everyone loses money in the same three places', page)
        self.assertIn('Three steps, in this order', page)
        self.assertIn('Reply here on Upwork', page)
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn('javascript:bad', page)
        self.assertNotIn('mailto:', page)
        self.assertNotIn('calendly', page.casefold())
        self.assertNotIn('Pocket CEO', page)
        self.assertIsNone(re.search(r'(?:src|href|action)=["\']https?://', page, re.I))

    def test_missing_sources_stay_unmeasured(self):
        data = renderer.proposal_data('Example', {}, {}, '2026-09-13')
        self.assertIsNone(data['findings']['geoGrid']['ranks'])
        self.assertIsNone(data['findings']['gbp'])
        self.assertIsNone(data['cro'])
        self.assertEqual(data['heroLead'], 'The audit needs more evidence before it can draw a conclusion.')

    def test_partial_map_grid_is_not_scored_or_padded(self):
        partial = {'geoGrid': {'ranks': [1] * 24, 'requestedPoints': 25, 'checkedPoints': 24}}
        self.assertEqual(renderer.maps_score(partial), (None, 0, 0))
        self.assertIn('complete 25-point map grid was not measured', renderer.rank_grid(partial))

    def test_missing_speed_reason_is_visible(self):
        cro = dict(self.cro, speed={'ok': False, 'why': 'quota unavailable'})
        data = renderer.proposal_data('Example', cro, self.search, '2026-09-13', site=self.site)
        self.assertIsNone(data['cro']['speed'])
        self.assertEqual(data['cro']['sourcesLine'], 'Mobile speed not measured: quota unavailable.')

    def test_sparse_profile_fields_are_unknown_and_unscored(self):
        result = search.gbp_from_summary({}, 'Example')
        rows = result['auditRows']
        self.assertTrue(rows)
        self.assertTrue(all(row['status'] == 'unknown' for row in rows))
        self.assertIsNone(renderer.profile_score({'gbp': result})[0])
        copy = ' '.join(row['value'] for row in rows)
        self.assertNotIn('The profile is verified.', copy)
        self.assertNotIn('The profile has 0 Google reviews', copy)

    def test_sparse_apify_profile_does_not_grade_absent_fields(self):
        merged = profile.merge({}, {
            'placeId': 'place-1',
            'title': 'Example',
            'location': {'lat': 52.5, 'lng': 13.4},
        })
        result = search.gbp_from_summary(merged, 'Example')
        by_label = {row['label']: row for row in result['auditRows']}
        for label in ('Claimed', 'Address', 'Phone', 'Website', 'Hours', 'Photos',
                      'Reviews', 'Description', 'Categories', 'Services', 'Booking link',
                      'Attributes', 'Updates'):
            self.assertEqual(by_label[label]['status'], 'unknown', label)
        self.assertNotIn('The profile has 0 Google reviews', ' '.join(row['value'] for row in result['auditRows']))

    def test_paid_grid_point_has_no_retry_and_requires_all_25(self):
        calls = []

        def fail(path, body):
            calls.append((path, body))
            raise TimeoutError('timeout')

        _response, problem = search.fetch_grid_point({'keyword': 'roof repair'}, call=fail)
        self.assertEqual(len(calls), 1)
        self.assertIn('timeout', problem)
        with self.assertRaisesRegex(RuntimeError, '24 of 25 required'):
            search.validated_grid_tasks([({'tasks': [{'status_code': 20000}]}, None)] * 24)
        responses = [({'tasks': [{'status_code': 20000}]}, None)] * 24
        responses.append(({'tasks': []}, 'timeout'))
        with self.assertRaisesRegex(RuntimeError, '1 of 25 map checks failed'):
            search.validated_grid_tasks(responses)

    def test_labs_call_does_not_fallback_to_another_location(self):
        calls = []
        old = search.post
        search.post = lambda path, body: calls.append((path, body)) or {'tasks': [{'status_code': 40000, 'status_message': 'bad location'}]}
        try:
            with self.assertRaisesRegex(RuntimeError, 'refused'):
                search.labs_post('dataforseo_labs/google/ranked_keywords/live', {'location_name': 'Berlin, Germany'})
        finally:
            search.post = old
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1][0]['location_name'], 'Berlin, Germany')

    def test_keyword_discovery_refusal_stops_without_country_fallback(self):
        with tempfile.TemporaryDirectory() as raw:
            cro = pathlib.Path(raw) / 'cro.json'
            cro.write_text('{}', encoding='utf-8')
            args = types.SimpleNamespace(
                cro=str(cro), location='Berlin, Germany', domain='example.com',
                language='English', profile_json=None, business='Example',
                market='local', seeds=None,
            )
            calls = []

            def refuse(path, body):
                calls.append((path, body))
                return {'tasks': [{'status_code': 40501, 'status_message': 'invalid location'}]}

            with self.assertRaisesRegex(RuntimeError, 'ranked keywords refused'):
                keywords.discover(args, call=refuse)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1][0]['location_name'], 'Berlin, Germany')

    def test_keyword_expansion_refusal_stops_before_later_paid_phases(self):
        cache = {
            'selectedSeeds': ['locksmith'], 'primaryCategory': '', 'business': 'Example',
            'market': 'local', 'location': 'Berlin, Germany', 'language': 'English',
            'gbpCategories': [], 'errors': [], 'spend': 0, 'profileCity': 'Berlin',
        }
        calls = []

        def refuse(path, body):
            calls.append((path, body))
            return {'tasks': [{'status_code': 40501, 'status_message': 'invalid location'}]}

        args = types.SimpleNamespace(seeds=None, market='local', exclude_place=[], served_place=[], country_code=None)
        with self.assertRaisesRegex(RuntimeError, 'keyword expansion refused'):
            keywords.expand(args, cache, call=refuse, get_call=lambda _path: {})
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(body[0]['location_name'] == 'Berlin, Germany' for _, body in calls))

    def test_organic_serp_refusal_stops_keyword_run(self):
        cache = {
            'selectedSeeds': ['locksmith'], 'primaryCategory': 'Locksmith', 'business': 'Example',
            'market': 'local', 'location': 'Berlin, Germany', 'language': 'English',
            'gbpCategories': ['Locksmith'], 'errors': [], 'spend': 0,
            'profileCity': 'Berlin', 'domain': 'example.com',
        }
        calls = []

        def respond(path, body):
            calls.append(path)
            if '/organic/' in path:
                return {'tasks': [{'status_code': 40501, 'status_message': 'SERP unavailable'}]}
            return {'tasks': [{'status_code': 20000, 'result': [{'items': [{
                'keyword_data': {'keyword': 'locksmith', 'keyword_info': {'search_volume': 100, 'cpc': 2}},
            }]}]}]}

        args = types.SimpleNamespace(seeds=None, market='local', exclude_place=[], served_place=[], country_code=None)
        with self.assertRaisesRegex(RuntimeError, 'SERP task refused'):
            keywords.expand(args, cache, call=respond, get_call=lambda _path: {})
        self.assertEqual(calls.count('serp/google/organic/live/advanced'), 1)

    def test_apify_budget_lookup_fails_closed(self):
        with mock.patch.object(profile.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertIn('could not verify', profile.apify_leer('token'))

    def test_runtime_preflight_requires_a_speed_source(self):
        env = {'PAGESPEED_API_KEY': ''}
        available = lambda _module: object()
        self.assertIn('PAGESPEED_API_KEY', builder.runtime_error(env, find_spec=available, which=lambda _name: None))

    def test_paid_apify_token_alias_satisfies_credentials(self):
        env = {
            'FIRECRAWL_API_KEY': 'firecrawl',
            'APIFY_API_TOKEN_PAID': 'apify',
            'DATAFORSEO_LOGIN': 'login',
            'DATAFORSEO_PASSWORD': 'password',
        }
        self.assertEqual(builder.missing_credentials(env), [])

    def test_current_audit_without_url_retries_only_automatic_publish(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = pathlib.Path(raw) / '123456'
            folder.mkdir()
            report = folder / 'lead-magnet.html'
            report.write_text('<html></html>', encoding='utf-8')
            job = {
                'id': '123456',
                'status': 'replied',
                'lead_magnet_source': {
                    'website': 'https://example.com',
                    'location': 'Berlin, Germany',
                },
                'lead_magnet_source_updated_at': '2020-01-01T00:00:00+00:00',
            }
            commands = []
            with mock.patch.object(builder, 'get_job', return_value=job), \
                    mock.patch.object(builder, 'load_env'), \
                    mock.patch.object(builder, 'jobs_dir', return_value=pathlib.Path(raw)), \
                    mock.patch.object(builder, 'command', side_effect=lambda parts, **_kwargs: commands.append(parts) or ''), \
                    mock.patch.object(builder, 'publish', return_value='https://upwork-pitches.vercel.app/123456/audit'):
                self.assertEqual(builder.run('123456'), report)
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][-1], 'vercel')

    def test_site_evidence_requires_a_reachable_page(self):
        with tempfile.TemporaryDirectory() as raw:
            path = pathlib.Path(raw) / 'site.json'
            path.write_text('{"pages": []}', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'no reachable pages'):
                builder.validate_site(path)
            path.write_text('{"pages": [{"path": "/"}]}', encoding='utf-8')
            self.assertEqual(builder.validate_site(path)['pages'][0]['path'], '/')

    def test_main_writes_self_contained_html(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = pathlib.Path(raw)
            (folder / 'cro.json').write_text(json.dumps(self.cro), encoding='utf-8')
            (folder / 'search.json').write_text(json.dumps(self.search), encoding='utf-8')
            (folder / 'site.json').write_text(json.dumps(self.site), encoding='utf-8')
            output = folder / 'lead-magnet.html'
            old = sys.argv
            try:
                sys.argv = ['render_report.py', '--business', 'Example', '--evidence', raw, '--output', str(output)]
                self.assertEqual(renderer.main(), 0)
            finally:
                sys.argv = old
            self.assertTrue(output.is_file())
            page = output.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'(?:src|href|action)=["\']https?://', page, re.I))
            self.assertIn("connect-src 'none'", page)

    def test_demo_is_a_safe_current_format_report(self):
        with tempfile.TemporaryDirectory() as raw:
            output = pathlib.Path(raw) / 'lead-magnet-example.html'
            result = subprocess.run(
                [sys.executable, str(DEMO), str(output)],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding='utf-8')
            self.assertEqual(page.count('data-audit-section="'), 3)
            self.assertIn('Example website audit', page)
            self.assertIn('Get found', page)
            self.assertIn('Build trust', page)
            self.assertIn('Win enquiries', page)
            self.assertIn('Almost everyone loses money in the same three places', page)
            self.assertIn('Three steps, in this order', page)
            self.assertNotIn('Pocket CEO', page)
            self.assertIsNone(re.search(r'(?:src|href|action)=["\']https?://', page, re.I))
            self.assertIn('<script', page)
            self.assertIn("connect-src 'none'", page)

    def test_builder_dry_run_names_paid_services_without_calling_them(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = pathlib.Path(raw)
            env = dict(os.environ, BLUEPRINT_JOBS=str(folder / 'jobs.json'), BLUEPRINT_JOBDIR=str(folder / 'jobs'))
            added = subprocess.run(
                [sys.executable, str(PIPELINE), 'add', '--file', '-'],
                input=json.dumps({'id': '123456', 'title': 'Local SEO', 'status': 'replied'}),
                text=True, capture_output=True, env=env,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            saved = subprocess.run(
                [sys.executable, str(PIPELINE), 'lead-magnet-source', '123456', 'https://example.com'],
                text=True, capture_output=True, env=env,
            )
            self.assertEqual(saved.returncode, 0, saved.stderr)
            result = subprocess.run(
                [sys.executable, str(BUILDER), '123456', '--dry-run'],
                text=True, capture_output=True, env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['paid_services'], ['Firecrawl', 'Apify', 'DataForSEO'])
            self.assertEqual(plan['location'], 'derived from the confirmed Google profile')
            self.assertFalse(plan['would_send_or_publish'])
            self.assertTrue(plan['production_run_publishes'])
            self.assertFalse((folder / 'jobs' / '123456' / 'lead-magnet.html').exists())


if __name__ == '__main__':
    unittest.main()
