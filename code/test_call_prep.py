#!/usr/bin/env python3
"""Offline fixtures and mocked boundary tests for call-prep evidence collection."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import call_prep as prep

HTML = '''<html><head><title> Our &amp; Gym </title>
<meta name="description" content="Train &amp; grow">
<script src="/wp-content/theme.js"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-ABC12345"></script>
<script>fbq('init', '123456789012'); hidden_script</script>
<style>hidden_style</style></head><body><h1>Get <b>strong</b></h1>
<noscript>hidden_noscript</noscript><svg><text>hidden_svg</text></svg>
<template><div>hidden_template</div></template><iframe>hidden_iframe</iframe>
<a href="https://app.wodify.com/book">Book a class</a>
<a href="tel:+12345678">Call</a><a href="mailto:hi@gym.test?subject=Hello">Mail</a>
<a href="https://instagram.com/gym/?utm_source=site">Instagram</a>
<form><input name="name"></form><p>Visible &amp; useful</p></body></html>'''

DOSSIER = '''# Example gym call
Confirm the owner's priority and agree the next step.

## Call agenda
1. Confirm the goal.
2. Walk through the evidence.
3. Agree the next step.

## What we know
### Website
- The site has classes. [Website](https://gym.test/classes)
  * Booking is available. [Book](https://app.wodify.com/book)

## Openers
What prompted the call?

## Watch out
Confirm who owns the website.

## Before the call
- Open the website (free).
- Review the proposed $0.50 pull.

## Sources
- https://gym.test/classes
- https://app.wodify.com/book
'''


def lighthouse_report():
    return {'categories': {'performance': {'score': 0.87}}, 'audits': {
        'largest-contentful-paint': {'numericValue': 2345},
        'first-contentful-paint': {'numericValue': 1234},
        'total-blocking-time': {'numericValue': 123.456},
        'cumulative-layout-shift': {'numericValue': 0.12345},
        'speed-index': {'numericValue': 4567}}}


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.network = patch('urllib.request.urlopen',
                             side_effect=AssertionError('network forbidden in offline tests'))
        self.network.start()
        self.addCleanup(self.network.stop)


class SiteTests(OfflineTest):
    def test_raw_stack_and_identifiers(self):
        result = prep.detect_stack(HTML)
        self.assertIn('WordPress', result['stack'])
        self.assertIn('Wodify', result['stack'])
        self.assertIn('Meta Pixel', result['stack'])
        self.assertEqual(result['ids']['ga4'], ['G-ABC12345'])
        self.assertEqual(result['ids']['meta_pixel'], ['123456789012'])
        self.assertIn('Google Tag Manager', result['not_found'])
        self.assertNotIn('Google Analytics 4', result['not_found'])
        self.assertNotIn('Meta Pixel', result['not_found'])
        self.assertTrue(all(len(snippet) <= 80 for evidence in result['stack'].values()
                            for snippet in evidence))

    def test_absent_meta_pixel(self):
        result = prep.detect_stack('<p>Only a website</p>')
        self.assertIn('Meta Pixel', result['not_found'])

    def test_icon_fonts_and_common_words_are_not_tools(self):
        raw = ('<style>.fa-squarespace:before{content:"x"}.fa-hubspot:before{}</style>'
               '<i class="fa-brands fa-hotjar"></i><p>An individual podium finish.</p>'
               '<button class="g-recaptcha">Send</button>')
        stack = prep.detect_stack(raw)['stack']
        for name in ('Squarespace', 'HubSpot', 'Hotjar', 'Divi', 'Podium', 'Google Analytics 4'):
            self.assertNotIn(name, stack)

    def test_visible_text_metadata_and_hidden_content(self):
        page, links, forms = prep.parse_html(HTML, 'https://gym.test/')
        self.assertEqual(page['title'], 'Our & Gym')
        self.assertEqual(page['meta_description'], 'Train & grow')
        self.assertEqual(page['h1'], ['Get strong'])
        self.assertIn('Visible & useful', page['text'])
        self.assertNotIn('hidden_', page['text'])
        self.assertEqual(forms, 1)
        self.assertTrue(links)
        capped = prep.parse_html('<p>' + 'x' * 13000 + '</p>', 'https://gym.test/')[0]
        self.assertEqual(len(capped['text']), 12000)

    def test_page_ranking_and_exclusions(self):
        links = [{'href': href, 'text': text} for href, text in [
            ('/blog/post-1', 'Blog'), ('/logo.png', 'Logo'), ('mailto:hi@gym.test', 'Mail'),
            ('/pricing', 'Plans'), ('/about', 'About'), ('/about#team', 'Team'),
            ('/other', 'Our staff'), ('#top', 'Top'), ('https://other.test/about', 'About')]]
        picked = prep.pick_pages('https://gym.test/', links, 3)
        self.assertEqual(picked, ['https://gym.test/about', 'https://gym.test/other'])
        picked = prep.pick_pages('https://gym.test/', links, 6)
        self.assertLess(picked.index('https://gym.test/pricing'), picked.index('https://gym.test/blog/post-1'))
        self.assertFalse(any('logo.png' in url or 'mailto:' in url for url in picked))
        self.assertEqual(prep.pick_pages('https://gym.test/', links, 1), [])

    def test_contacts_social_tracking_and_booking(self):
        _, links, forms = prep.parse_html(HTML, 'https://gym.test/')
        links += [{'href': 'https://youtube.com/watch?v=123&utm_campaign=site', 'text': ''},
                  {'href': 'https://facebook.com/sharer.php?u=abc', 'text': ''},
                  {'href': 'https://twitter.com/intent/tweet?text=abc', 'text': ''}]
        result = prep.extract_contact([('https://gym.test/', links + links, forms)])
        self.assertEqual(result['contact']['phones'], ['+12345678'])
        self.assertEqual(result['contact']['emails'], ['hi@gym.test'])
        self.assertEqual(result['contact']['forms'], {'https://gym.test/': 1})
        self.assertEqual(result['contact']['booking_links'], ['https://app.wodify.com/book'])
        self.assertEqual(result['socials'], ['https://instagram.com/gym/', 'https://youtube.com/watch?v=123'])

    def test_site_failure_writes_evidence_and_zero_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(id='123456', url='https://gym.test/', max_pages=6, env={})
            stdout = io.StringIO()
            with patch.object(prep.pipeline, 'jobs_dir', return_value=Path(temporary)), \
                    patch.object(prep, 'fetch_html', side_effect=urllib.error.URLError('private request')), \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(prep.cmd_site(args), 0)
            path = Path(temporary) / '123456' / 'call-prep' / 'site.json'
            result = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(result['url'], args.url)
            self.assertIn('error', result)
            self.assertIn('fetched_at', result)
            self.assertEqual(stdout.getvalue().splitlines()[-1], str(path))

    def test_site_redirect_and_page_errors(self):
        args = argparse.Namespace(id='123456', url='https://gym.test', max_pages=3, env={})
        raw = '<a href="/about">About</a><a href="/pricing">Pricing</a>'
        with patch.object(prep, 'fetch_html', side_effect=[(raw, 'https://www.gym.test/'),
                                                        ('<p>wp-content</p>', 'https://www.gym.test/about'),
                                                        urllib.error.URLError('unavailable')]) as fetch, \
                patch.object(prep, 'save_result', return_value=0) as save:
            self.assertEqual(prep.cmd_site(args), 0)
        result = save.call_args.args[2]
        self.assertEqual(result['final_url'], 'https://www.gym.test/')
        self.assertEqual(len(result['pages']), 2)
        self.assertEqual(result['errors'][0]['url'], 'https://www.gym.test/pricing')
        self.assertEqual(fetch.call_args_list[1].args[0], 'https://www.gym.test/about')

    def test_html_request_timeout_and_size_limit(self):
        response = Mock()
        response.read.return_value = b'a' * prep.MAX_PAGE_BYTES
        response.headers.get_content_charset.return_value = 'utf-8'
        response.geturl.return_value = 'https://gym.test/'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('urllib.request.urlopen', return_value=response) as opened:
            raw, _ = prep.fetch_html('https://gym.test/')
            self.assertEqual(len(raw), prep.MAX_PAGE_BYTES)
        self.assertEqual(opened.call_args.kwargs['timeout'], 20)
        response.read.assert_called_once_with(prep.MAX_PAGE_BYTES)


class SpeedTests(OfflineTest):
    def test_mobile_metrics_and_rounding(self):
        result = prep.parse_speed({'lighthouseResult': lighthouse_report()}, 'pagespeed')
        self.assertEqual(result, {'source': 'pagespeed', 'strategy': 'mobile', 'performance': 87,
                                 'lcp_s': 2.3, 'fcp_s': 1.2, 'tbt_ms': 123.456,
                                 'cls': 0.123, 'speed_index_s': 4.6})

    def test_missing_key_and_local_lighthouse(self):
        with patch.object(prep.shutil, 'which', return_value=None), patch.object(prep, 'get_json') as get:
            self.assertEqual(prep.measure_speed('https://gym.test/', {}), {'skipped': prep.NO_SPEED})
            get.assert_not_called()
        run = subprocess.CompletedProcess([], 0, json.dumps(lighthouse_report()), '')
        with patch.object(prep.shutil, 'which', return_value='/mock/lighthouse'), \
                patch.object(prep.subprocess, 'run', return_value=run) as process:
            self.assertEqual(prep.measure_speed('https://gym.test/', {})['source'], 'lighthouse')
        self.assertEqual(process.call_args.kwargs['timeout'], 180)
        self.assertIn('--chrome-flags=--headless=new', process.call_args.args[0])

    def test_api_request_and_error_fallback(self):
        with patch.object(prep, 'get_json', return_value={'lighthouseResult': lighthouse_report()}) as get:
            result = prep.measure_speed('https://gym.test/', {'PAGESPEED_API_KEY': 'test-key'})
        self.assertEqual(result['performance'], 87)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(get.call_args.args[0]).query)
        self.assertEqual(query['strategy'], ['mobile'])
        self.assertEqual(get.call_args.kwargs['timeout'], 90)
        self.assertNotIn('test-key', json.dumps(result))
        for status in (403, 429):
            with self.subTest(status=status), patch.object(prep, 'get_json', side_effect=
                    urllib.error.HTTPError('secret-url', status, 'error', {}, None)), \
                    patch.object(prep.shutil, 'which', return_value=None):
                self.assertIn('skipped', prep.measure_speed('https://gym.test/', {'PAGESPEED_API_KEY': 'test-key'}))
        with patch.object(prep, 'get_json', side_effect=
                urllib.error.HTTPError('secret-url', 500, 'error', {}, None)), \
                patch.object(prep.shutil, 'which') as local:
            self.assertEqual(prep.measure_speed('https://gym.test/', {'PAGESPEED_API_KEY': 'test-key'}),
                             {'skipped': 'HTTP 500'})
            local.assert_not_called()


class ApifyTests(OfflineTest):
    def test_missing_token_and_unreadable_budget(self):
        with patch.object(prep, 'get_json') as get:
            result = prep.apify_pull(prep.REVIEWS_ACTOR, 0.5, {}, {})
            self.assertEqual(result['skipped'], prep.NO_APIFY)
            self.assertEqual(result['actor'], prep.REVIEWS_ACTOR)
            self.assertEqual(result['cap_usd'], 0.5)
            get.assert_not_called()
        with patch.object(prep, 'get_json', return_value={}) as get:
            self.assertEqual(prep.apify_pull(prep.ADS_ACTOR, 0.1, {}, {'APIFY_TOKEN': 'test-token'})['skipped'],
                             prep.NO_BUDGET)
            self.assertEqual(get.call_count, 1)

    def test_low_budget_prevents_run(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 10}, 'current': {'monthlyUsageUsd': 9.1}}}
        with patch.object(prep, 'get_json', return_value=limits) as get:
            result = prep.apify_pull(prep.ADS_ACTOR, 0.1, {}, {'APIFY_TOKEN': 'test-token'})
        self.assertIn('$0.90', result['skipped'])
        self.assertEqual(get.call_count, 1)

    def test_budget_cap_poll_dataset_cost_and_token_precedence(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 10}, 'current': {'monthlyUsageUsd': 9}}}
        ready = {'data': {'id': 'mock-run', 'status': 'READY'}}
        succeeded = {'data': {'id': 'mock-run', 'status': 'SUCCEEDED',
                              'defaultDatasetId': 'mock-data', 'usageTotalUsd': 0.08}}
        with patch.object(prep, 'get_json', side_effect=[limits, ready, succeeded, [{'ad_archive_id': '1'}]]) as get, \
                patch.object(prep.time, 'sleep') as sleep:
            result = prep.apify_pull(prep.ADS_ACTOR, 0.1, {'count': 10},
                                     {'APIFY_API_TOKEN': 'first-token', 'APIFY_TOKEN': 'second-token'})
        self.assertEqual(get.call_args_list[0].args[0], prep.APIFY_API + '/users/me/limits')
        self.assertIn('maxTotalChargeUsd=0.10', get.call_args_list[1].args[0])
        self.assertEqual(get.call_args_list[1].kwargs['data'], {'count': 10})
        self.assertEqual(get.call_args_list[0].args[1], {'Authorization': 'Bearer first-token'})
        self.assertIn('/actor-runs/mock-run', get.call_args_list[2].args[0])
        self.assertTrue(get.call_args_list[3].args[0].endswith('/items?clean=true&format=json'))
        sleep.assert_called_once_with(5)
        self.assertEqual(result['cost_usd'], 0.08)
        self.assertNotIn('first-token', json.dumps(result))

    def test_failed_run_and_poll_timeout(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 10}, 'current': {'monthlyUsageUsd': 0}}}
        with patch.object(prep, 'get_json', side_effect=[limits, {'data': {'status': 'FAILED'}}]) as get:
            result = prep.apify_pull(prep.REVIEWS_ACTOR, 0.5, {}, {'APIFY_API_TOKEN_PAID': 'test-token'})
            self.assertIn('FAILED', result['skipped'])
            self.assertEqual(get.call_count, 2)

    def test_poll_failure_keeps_last_measured_cost(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 10}, 'current': {'monthlyUsageUsd': 0}}}
        started = {'data': {'id': 'mock-run', 'status': 'RUNNING', 'usageTotalUsd': 0.03}}
        with patch.object(prep, 'get_json', side_effect=[limits, started,
                urllib.error.URLError('request with private token')]), patch.object(prep.time, 'sleep'):
            result = prep.apify_pull(prep.ADS_ACTOR, 0.1, {}, {'APIFY_TOKEN': 'test-token'})
        self.assertEqual(result['cost_usd'], 0.03)
        self.assertIn('skipped', result)
        with patch.object(prep, 'get_json', side_effect=[limits, {'data': {'status': 'RUNNING'}}]) as get, \
                patch.object(prep.time, 'monotonic', side_effect=[0, 241]):
            result = prep.apify_pull(prep.REVIEWS_ACTOR, 0.5, {}, {'APIFY_TOKEN': 'test-token'})
            self.assertIn('timed out', result['skipped'])
            self.assertEqual(get.call_count, 2)


class ReviewTests(OfflineTest):
    def test_exact_domain_match_with_www(self):
        items = [{'title': 'Wrong gym', 'website': 'https://other.test', 'placeId': 'other'},
                 {'title': 'Right gym', 'website': 'https://www.gym.test/path', 'placeId': 'right',
                  'totalScore': 4.8, 'reviewsCount': 41, 'reviewsTags': ['friendly'], 'reviews': [
                      {'stars': 2, 'text': 'x' * 700, 'responseFromOwnerText': 'Thanks'},
                      {'stars': 5, 'text': 'Great'}]}]
        result = prep.select_reviews(items, 'https://gym.test/')
        self.assertEqual(result['place']['title'], 'Right gym')
        self.assertEqual(result['place']['reviewsTags'], ['friendly'])
        self.assertEqual(len(result['reviews'][0]['text']), 600)
        self.assertTrue(result['reviews'][0]['owner_replied'])
        self.assertFalse(result['reviews'][1]['owner_replied'])
        self.assertEqual(len(result['low_star']), 1)

    def test_no_match_reports_candidates_without_guessing(self):
        items = [{'title': 'Wrong gym', 'website': 'https://other.test'}] * 8
        result = prep.select_reviews(items, 'https://gym.test/')
        self.assertEqual(result['skipped'], 'no Google profile lists gym.test as its website')
        self.assertEqual(len(result['candidates']), 5)
        self.assertNotIn('place', result)

    def test_deduplication_ambiguity_city_and_review_limit(self):
        first = {'title': 'North', 'website': 'https://gym.test', 'placeId': 'north',
                 'address': 'Berlin', 'reviews': [{'stars': 5}] * 50}
        second = {'title': 'South', 'website': 'https://www.gym.test', 'placeId': 'south', 'city': 'Munich'}
        self.assertEqual(len(prep.select_reviews([first, first], 'https://gym.test')['reviews']), 40)
        ambiguous = prep.select_reviews([first, first, second], 'https://gym.test')
        self.assertIn('several Google profiles', ambiguous['skipped'])
        self.assertEqual(len(ambiguous['candidates']), 2)
        self.assertEqual(prep.select_reviews([first, second], 'https://gym.test', 'MUNICH')['place']['title'], 'South')

    def test_actor_input(self):
        body = prep.reviews_input('https://www.gym.test/', 'Gym', 'Berlin')
        self.assertEqual(body['searchStringsArray'], ['gym.test', 'Gym Berlin'])
        self.assertEqual(body['maxCrawledPlacesPerSearch'], 5)
        self.assertEqual(body['maxReviews'], 40)
        self.assertEqual(body['reviewsSort'], 'newest')
        self.assertFalse(body['scrapeContacts'])
        self.assertEqual(prep.reviews_input('https://gym.test', 'Gym')['searchStringsArray'], ['gym.test'])


class AdsTests(OfflineTest):
    def test_not_found_and_other_error(self):
        result = prep.parse_ads([{'error': 'Ads not found', 'errorCode': 'ADS_NOT_FOUND', 'url': 'mock'}])
        self.assertFalse(result['found'])
        self.assertEqual(result['ads'], [])
        self.assertEqual(result['note'], 'Ad Library shows no active ads for this search')
        self.assertEqual(prep.parse_ads([{'error': 'Actor failed'}]), {'skipped': 'Actor failed'})

    def test_ad_ids_snapshot_template_text_and_page_counts(self):
        ad = {'ad_archive_id': '123', 'page_name': 'Gym', 'status': 'inactive',
              'publisher_platform': ['facebook'], 'snapshot': {
                  'body': {'text': '{{product.brand}} ' + 'x' * 400},
                  'page_profile_uri': 'https://facebook.com/gym', 'cta_text': 'Book now'}}
        result = prep.parse_ads([{'status': 'active'}, ad])
        self.assertTrue(result['found'])
        self.assertEqual(len(result['ads']), 1)
        self.assertEqual(result['ads'][0]['page_name'], 'Gym')
        self.assertEqual(len(result['ads'][0]['snapshot']['body']['text']), 300)
        self.assertTrue(result['ads'][0]['snapshot']['body']['text'].startswith('{{product.brand}}'))
        self.assertEqual(result['pages'], [{'page_name': 'Gym',
                                           'page_profile_uri': 'https://facebook.com/gym', 'ad_count': 1}])

    def test_page_url_keyword_url_and_capped_actor_input(self):
        page_url = 'https://www.facebook.com/gym'
        self.assertEqual(prep.ads_query(page_url), page_url)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(prep.ads_query('Gym & club', 'DE')).query)
        self.assertEqual(query['q'], ['Gym & club'])
        self.assertEqual(query['country'], ['DE'])
        args = argparse.Namespace(id='123456', term='Gym', country='US', env={})
        with patch.object(prep, 'apify_pull', return_value={'actor': prep.ADS_ACTOR,
                'cap_usd': 0.1, 'skipped': prep.NO_APIFY}) as pull, \
                patch.object(prep, 'save_result', return_value=0):
            self.assertEqual(prep.cmd_ads(args), 0)
        self.assertEqual(pull.call_args.args[:2], (prep.ADS_ACTOR, 0.1))
        self.assertEqual(pull.call_args.args[2]['count'], 10)
        self.assertFalse(pull.call_args.args[2]['scrapeAdDetails'])


class DossierTests(OfflineTest):
    def test_valid_dossier(self):
        self.assertEqual(prep.check_dossier(DOSSIER), [])

    def test_markdown_link_title_and_subheading_scope(self):
        titled = DOSSIER.replace('[Website](https://gym.test/classes)',
                                 '[Website](https://gym.test/classes "Classes")')
        self.assertEqual(prep.check_dossier(titled), [])
        extra_heading = DOSSIER.replace('## Call agenda\n', '## Call agenda\n### Extra\n')
        self.assertTrue(any('subheadings' in finding for finding in prep.check_dossier(extra_heading)))

    def test_required_failure_fixtures(self):
        variants = [
            DOSSIER.replace('[Website](https://gym.test/classes)', 'Website'),
            DOSSIER.replace('- https://app.wodify.com/book\n', ''),
            DOSSIER.replace('Confirm the goal.', 'Confirm \u2014 the goal.'),
            DOSSIER.replace('## Openers', '## TEMP').replace('## Watch out', '## Openers').replace('## TEMP', '## Watch out'),
        ]
        for index, text in enumerate(variants):
            with self.subTest(index=index):
                findings = prep.check_dossier(text)
                self.assertTrue(findings)
                self.assertTrue(all(line.startswith('FIX: ') for line in findings))

    def test_limits_title_sources_and_nested_bullets(self):
        self.assertTrue(prep.check_dossier(DOSSIER.replace('1. Confirm the goal.\n', '')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('(free)', '(paid)')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('# Example gym call\n', '')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('Confirm the owner\'s priority and agree the next step.', '')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('## Openers', '## Extra\n\n## Openers')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('[Book](https://app.wodify.com/book)', 'Book')))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('## Openers', '## Openers\n' + 'word ' * 901)))
        self.assertTrue(prep.check_dossier(DOSSIER.replace('## Before the call\n',
                        '## Before the call\n' + '- free check\n' * 6)))
        self.assertEqual(prep.check_dossier(DOSSIER.replace('- Open the website (free).\n', '')
                         .replace('- Review the proposed $0.50 pull.\n', '')), [])

    def test_check_uses_jobs_dir_writes_nothing_and_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dossier = root / '123456' / 'call-prep.md'
            dossier.parent.mkdir()
            dossier.write_text(DOSSIER, encoding='utf-8')
            stdout = io.StringIO()
            with patch.object(prep.pipeline, 'jobs_dir', return_value=root), contextlib.redirect_stdout(stdout):
                self.assertEqual(prep.cmd_check(argparse.Namespace(id='123456')), 0)
            self.assertEqual(stdout.getvalue(), 'PASS call-prep 123456\n')
            self.assertEqual(list(dossier.parent.iterdir()), [dossier])
            dossier.write_bytes(b'\xff')
            with patch.object(prep.pipeline, 'jobs_dir', return_value=root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(prep.cmd_check(argparse.Namespace(id='123456')), 1)


class CliTests(OfflineTest):
    def test_invalid_id_and_help_for_every_command(self):
        for value in ('12345', '1' * 26, '../123456', 'abcdef', '\u0661' * 6):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    prep.main(['check', value])
                self.assertEqual(error.exception.code, 2)
        for command in (None, 'site', 'speed', 'reviews', 'ads', 'check'):
            with self.subTest(command=command), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    prep.main(([command] if command else []) + ['--help'])
                self.assertEqual(error.exception.code, 0)

    def test_env_loading_order_without_real_credentials(self):
        with patch.dict(prep.os.environ, {'EXAMPLE': 'exported'}, clear=True), \
                patch.object(prep.env_file, 'load_dotenv') as load, \
                patch.object(prep, 'cmd_check', return_value=0):
            self.assertEqual(prep.main(['check', '123456']), 0)
        self.assertEqual(load.call_args_list[0].args[0], prep.ROOT / '.env')
        self.assertEqual(load.call_args_list[1].args[0], Path.home() / '.config' / 'credentials.env')
        self.assertEqual(load.call_args_list[0].args[1], {'EXAMPLE': 'exported'})

    def test_credentials_are_redacted_in_json_and_stdout(self):
        env = {'APIFY_API_TOKEN': 'private/mock token', 'PAGESPEED_API_KEY': 'private-key'}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(prep.pipeline, 'jobs_dir', return_value=Path(temporary)):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                prep.save_result('123456', 'ads', {'skipped': 'private/mock token private-key\u2014error'},
                                 ['private-key\u2014error'], env)
            stored = (Path(temporary) / '123456' / 'call-prep' / 'ads.json').read_text()
            self.assertNotIn('private/mock token', stored)
            self.assertNotIn('private-key', stored + stdout.getvalue())
            self.assertNotIn('\u2014', stored + stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
