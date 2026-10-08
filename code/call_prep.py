#!/usr/bin/env python3
"""Fetch call-prep evidence and validate a call dossier.

    python3 code/call_prep.py site <job_id> <url> [--max-pages 6]
    python3 code/call_prep.py speed <job_id> <url>
    python3 code/call_prep.py reviews <job_id> <url> [--name <business>] [--city <town>]
    python3 code/call_prep.py ads <job_id> <term or facebook page url> [--country US]
    python3 code/call_prep.py check <job_id>

/call-prep researches with web search; this script does what a model cannot do
reliably. Web fetching returns processed text, measured 8 October 2026 as nothing
but the page title on a heavy gym site, and never shows script tags, so the prices
and the tech stack (pixel, analytics, booking tool) come from the raw HTML here.
Maps, Yelp, Facebook and the Ad Library block plain fetching, so reviews and ads
are paid Apify pulls, each capped and run only after the remaining budget is read.
A skipped pull writes its reason and exits 0: it is never a gate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import env_file  # noqa: E402
import pipeline  # noqa: E402

USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/155.0.8059.39 Safari/537.36')
ID = re.compile(r'^[0-9]{6,25}$')
TIMEOUT = 20
MAX_PAGE_BYTES = 3 * 1024 * 1024
APIFY_API = 'https://api.apify.com/v2'
MIN_REST_USD = 1.0
REVIEWS_ACTOR = 'compass~crawler-google-places'
REVIEWS_CAP_USD = 0.50
ADS_ACTOR = 'curious_coder~facebook-ads-library-scraper'
ADS_CAP_USD = 0.10
NO_APIFY = 'no Apify token; add APIFY_API_TOKEN to .env to run this pull'
NO_BUDGET = 'Apify budget not readable; refusing to spend blind'
NO_SPEED = ('no PAGESPEED_API_KEY and no local Lighthouse; a free key from '
            'Google Cloud (PageSpeed Insights API) enables this')
HEADINGS = ['Call agenda', 'What we know', 'Openers', 'Watch out',
            'Before the call', 'Sources']
PRIORITY_WORDS = ('about', 'team', 'staff', 'coach', 'our-story', 'pricing',
                  'price', 'membership', 'rates', 'plans', 'services',
                  'programs', 'classes', 'contact', 'book', 'schedule',
                  'locations', 'faq')
FINGERPRINTS = {
    'cms': {
        'WordPress': r'wp-content|wp-includes', 'Wix': r'wixstatic|wix\.com',
        'Squarespace': r'squarespace', 'Webflow': r'webflow',
        'Shopify': r'cdn\.shopify|shopify\.theme',
        'Duda': r'dudaone|multiscreensite', 'GoDaddy Builder': r'img1\.wsimg\.com',
        'Framer': r'framerusercontent', 'Elementor': r'elementor',
        'Divi': r'et_pb_|/themes/Divi/', 'Avada': r'avada|fusion-builder',
    },
    'analytics': {
        'Google Analytics 4': r'gtag/js\?id=G-|[\'"](?-i:G-[A-Z0-9]{6,})',
        'Universal Analytics': r'(?-i:UA-\d{4,}-\d+)',
        'Google Tag Manager': r'googletagmanager\.com/gtm\.js|(?-i:GTM-[A-Z0-9]{4,})',
        'MonsterInsights': r'monsterinsights', 'Hotjar': r'hotjar',
        'Microsoft Clarity': r'clarity\.ms',
    },
    'ads': {
        'Meta Pixel': r'fbevents\.js|fbq\([\'"]init',
        'Google Ads': r'(?-i:AW-\d{6,})|googleadservices',
        'TikTok Pixel': r'analytics\.tiktok\.com',
        'LinkedIn Insight': r'snap\.licdn\.com',
    },
    'tracking': {'CallRail': r'callrail', 'WhatConverts': r'whatconverts',
                 'CallTrackingMetrics': r'calltrackingmetrics|tctm\.co'},
    'booking': {
        'Mindbody': r'mindbody|healcode', 'Wodify': r'wodify',
        'PushPress': r'pushpress', 'Zen Planner': r'zenplanner|zen planner',
        'Glofox': r'glofox', 'Calendly': r'calendly',
        'Acuity': r'acuityscheduling',
        'Square Appointments': r'squareup\.com/appointments|square\.site',
        'Vagaro': r'vagaro', 'Booksy': r'booksy', 'OpenTable': r'opentable',
        'Resy': r'resy\.com', 'Toast': r'toasttab',
        'Jobber': r'getjobber|jobber\.com', 'Housecall Pro': r'housecallpro',
        'ServiceTitan': r'servicetitan',
    },
    'chat': {
        'Intercom': r'widget\.intercom\.io|intercomcdn', 'Drift': r'drift\.com|js\.driftt',
        'Tawk': r'tawk\.to', 'Crisp': r'crisp\.chat', 'Tidio': r'code\.tidio|tidio\.co',
        'LiveChat': r'livechatinc', 'Zendesk': r'zdassets|zendesk',
        'Podium': r'podium\.com|podium-webchat',
    },
    'crm_funnel': {
        'GoHighLevel': r'leadconnectorhq|msgsndr|highlevel|gohighlevel',
        'HubSpot': r'hs-scripts|hsforms|hubspot',
        'Mailchimp': r'mailchimp|list-manage\.com', 'Klaviyo': r'klaviyo',
        'ActiveCampaign': r'activecampaign', 'Keap': r'infusionsoft|keap\.(?:app|com)',
        'ClickFunnels': r'clickfunnels', 'Typeform': r'typeform',
        'Jotform': r'jotform',
    },
    'seo': {
        'Rank Math': r'rank-math|rankmath', 'Yoast': r'yoast',
        'All in One SEO': r'aioseo',
        'schema.org LocalBusiness':
            r'"@type"\s*:\s*"[A-Za-z]*(LocalBusiness|HealthClub|ExerciseGym|Restaurant|Dentist|Store)"',
    },
    'reviews_widget': {
        'Elfsight': r'elfsight', 'Trustindex': r'trustindex',
        'Birdeye': r'birdeye', 'Trustpilot': r'trustpilot',
    },
}


def unique(values):
    return list(dict.fromkeys(values))


def clean_text(value):
    return ' '.join(html.unescape(value).split())


def host(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or '').lower()
    except ValueError:
        return ''


def domain(url):
    return host(url).removeprefix('www.')


class PageParser(HTMLParser):
    """Collect visible text and links without allowing hidden content through."""

    HIDDEN = {'script', 'style', 'noscript', 'svg', 'template', 'iframe'}
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.text = []
        self.title = []
        self.in_title = False
        self.description = ''
        self.h1 = []
        self.heading = None
        self.links = []
        self.link = None
        self.forms = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.hidden:
            if tag not in self.VOID:
                self.hidden.append(tag)
            return
        if tag in self.HIDDEN:
            self.hidden.append(tag)
            return
        if tag == 'title':
            self.in_title = True
        elif tag == 'meta' and attrs.get('name', '').lower() == 'description':
            self.description = attrs.get('content') or ''
        elif tag == 'h1':
            self.heading = []
        elif tag == 'a' and attrs.get('href'):
            if self.link:
                self.links.append(self.link)
            self.link = {'href': attrs['href'], 'text': ''}
        elif tag == 'form':
            self.forms += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
                del self.hidden[index:]
            return
        if tag == 'title':
            self.in_title = False
        elif tag == 'h1' and self.heading is not None:
            self.h1.append(clean_text(' '.join(self.heading)))
            self.heading = None
        elif tag == 'a' and self.link:
            self.links.append(self.link)
            self.link = None

    def handle_data(self, value):
        if self.hidden:
            return
        self.text.append(value)
        if self.in_title:
            self.title.append(value)
        if self.heading is not None:
            self.heading.append(value)
        if self.link:
            self.link['text'] += ' ' + value


def parse_html(raw, url):
    parser = PageParser()
    parser.feed(raw)
    parser.close()
    if parser.link:
        parser.links.append(parser.link)
    page = {'url': url, 'title': clean_text(' '.join(parser.title)),
            'meta_description': clean_text(parser.description), 'h1': parser.h1,
            'text': clean_text(' '.join(parser.text))[:12000]}
    return page, parser.links, parser.forms


def detect_stack(raw_pages):
    if isinstance(raw_pages, str):
        raw_pages = [raw_pages]
    # Icon fonts name brands they have nothing to do with: inline Font Awesome CSS on a
    # WordPress gym site produced Squarespace, HubSpot, Hotjar and Yoast (8 Oct 2026).
    raw_pages = [re.sub(r'\bfa-[\w-]+', ' ',
                        re.sub(r'<style\b[^>]*>.*?</style>', ' ', raw, flags=re.I | re.S))
                 for raw in raw_pages]
    stack = {}
    for category, patterns in FINGERPRINTS.items():
        for name, pattern in patterns.items():
            for raw in raw_pages:
                match = re.search(pattern, raw, re.I)
                if match:
                    start = max(0, match.start() - 20)
                    snippet = clean_text(raw[start:match.end() + 40])[:80]
                    stack[name] = [snippet]
                    break
    raw = '\n'.join(raw_pages)
    patterns = {'ga4': r'G-[A-Z0-9]{6,}', 'ua': r'UA-\d{4,}-\d+',
                'gtm': r'GTM-[A-Z0-9]{4,}',
                'meta_pixel': r'fbq\(\s*[\'"]init[\'"]\s*,\s*[\'"](\d{8,})',
                'google_ads': r'AW-\d{6,}'}
    ids = {name: unique(re.findall(pattern, raw))
           for name, pattern in patterns.items()}
    checks = [('Meta Pixel', 'ads'), ('Google Tag Manager', 'analytics'),
              ('Google Analytics 4', 'analytics'), ('Google Ads', 'ads')]
    not_found = [name for name, category in checks if name not in stack]
    for name, category in [('call tracking', 'tracking'), ('chat widget', 'chat'),
                           ('booking tool', 'booking')]:
        if not any(fingerprint in stack for fingerprint in FINGERPRINTS[category]):
            not_found.append(name)
    return {'stack': stack, 'ids': ids, 'not_found': not_found}


def pick_pages(home_url, links, max_pages=6):
    picked = []
    seen = {urllib.parse.urlsplit(home_url).path.rstrip('/') or '/'}
    for link in links:
        href = link['href'].strip()
        if not href or href.startswith('#'):
            continue
        try:
            url = urllib.parse.urljoin(home_url, href)
            parts = urllib.parse.urlsplit(url)
        except ValueError:
            continue
        if parts.scheme not in ('http', 'https') or host(url) != host(home_url):
            continue
        path = parts.path.rstrip('/') or '/'
        if path in seen or re.search(r'\.(pdf|jpg|png|svg|webp|css|js|zip)$', path, re.I):
            continue
        seen.add(path)
        haystack = (parts.path + ' ' + link.get('text', '')).casefold()
        rank = next((i for i, word in enumerate(PRIORITY_WORDS) if word in haystack),
                    len(PRIORITY_WORDS))
        picked.append((rank, len(picked), urllib.parse.urlunsplit(parts._replace(fragment=''))))
    picked.sort()
    return [url for _, _, url in picked[:max(0, max_pages - 1)]]


def clean_social_url(url):
    parts = urllib.parse.urlsplit(url)
    query = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query,
             keep_blank_values=True) if not key.lower().startswith('utm_')
             and key.lower() not in {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'igshid'}]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query),
                                                 fragment=''))


def extract_contact(pages):
    phones, emails, forms, booking, socials = [], [], {}, [], []
    social_hosts = ('facebook.com', 'instagram.com', 'linkedin.com', 'youtube.com',
                    'tiktok.com', 'x.com', 'twitter.com',
                    'maps.app.goo.gl', 'yelp.com')
    for url, links, form_count in pages:
        if form_count:
            forms[url] = form_count
        for link in links:
            href = link['href'].strip()
            if href.lower().startswith('tel:'):
                phones.append(urllib.parse.unquote(href[4:].split('?')[0]))
                continue
            if href.lower().startswith('mailto:'):
                emails.append(urllib.parse.unquote(href[7:].split('?')[0]))
                continue
            try:
                target = urllib.parse.urljoin(url, href)
                parts = urllib.parse.urlsplit(target)
            except ValueError:
                continue
            if parts.scheme not in ('http', 'https'):
                continue
            target_host = host(target)
            if target_host != host(url) and any(re.search(pattern, target_host, re.I)
                    for pattern in FINGERPRINTS['booking'].values()):
                booking.append(target)
            is_social = any(target_host == item or target_host.endswith('.' + item)
                            for item in social_hosts)
            is_social |= (target_host in ('google.com', 'www.google.com')
                          and parts.path.startswith('/maps'))
            if is_social and not re.search(r'sharer|intent/tweet', target, re.I):
                socials.append(clean_social_url(target))
    return {'contact': {'phones': unique(phones), 'emails': unique(emails),
                        'forms': forms, 'booking_links': unique(booking)},
            'socials': unique(socials)}


def error_reason(exc):
    """Never echo request URLs, headers, response bodies or subprocess output."""
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP {exc.code}'
    if isinstance(exc, subprocess.TimeoutExpired):
        return 'Lighthouse timed out'
    if isinstance(exc, json.JSONDecodeError):
        return 'invalid JSON response'
    if isinstance(exc, urllib.error.URLError):
        return 'request failed'
    return type(exc).__name__


def get_json(url, headers=None, data=None, timeout=TIMEOUT):
    request_headers = {'User-Agent': USER_AGENT, **(headers or {})}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=body, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_html(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(MAX_PAGE_BYTES)
        charset = response.headers.get_content_charset() or 'utf-8'
        try:
            raw = data.decode(charset, errors='replace')
        except LookupError:
            raw = data.decode('utf-8', errors='replace')
        return raw, response.geturl()


def redact(value, env):
    secrets = [secret for name, secret in env.items() if secret and
               (name.endswith(('API_KEY', 'TOKEN', 'TOKEN_PAID')))]
    if isinstance(value, str):
        value = value.replace('\u2014', '-')
        for secret in sorted(secrets, key=len, reverse=True):
            for spelling in unique([secret, urllib.parse.quote(secret, safe=''),
                                    urllib.parse.quote_plus(secret)]):
                value = value.replace(spelling, '[redacted]')
        return value
    if isinstance(value, dict):
        return {redact(key, env): redact(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, env) for item in value]
    return value


def save_result(job_id, command, result, summary, env=None):
    result = redact(result, env or {})
    summary = redact(summary, env or {})
    result = dict(result)
    result['fetched_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    folder = pipeline.jobs_dir() / job_id / 'call-prep'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{command}.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8')
    for line in summary[:11]:
        print(line)
    print(redact(str(path), env or {}))
    return 0


def cmd_site(args):
    try:
        raw, final_url = fetch_html(args.url)
    except Exception as exc:
        reason = error_reason(exc)
        return save_result(args.id, 'site', {'url': args.url, 'error': reason},
                           [f'Site: {reason}'], args.env)
    page, links, forms = parse_html(raw, final_url)
    pages, raw_pages = [page], [raw]
    contacts = [(final_url, links, forms)]
    errors = []
    for url in pick_pages(final_url, links, args.max_pages):
        try:
            raw, actual_url = fetch_html(url)
            page, page_links, forms = parse_html(raw, actual_url)
            pages.append(page)
            raw_pages.append(raw)
            contacts.append((actual_url, page_links, forms))
        except Exception as exc:
            reason = error_reason(exc)
            errors.append({'url': url, 'error': reason})
    result = {'url': args.url, 'final_url': final_url, 'pages': pages,
              **detect_stack(raw_pages), **extract_contact(contacts), 'errors': errors}
    summary = [f'Site: {len(pages)} pages']
    for category, fingerprints in FINGERPRINTS.items():
        names = [name for name in fingerprints if name in result['stack']]
        if names:
            summary.append(f'{category}: {", ".join(names)}')
    summary += ['Not found: ' + ', '.join(result['not_found']) +
                f'; socials: {len(result["socials"])}']
    return save_result(args.id, 'site', result, summary, args.env)


def parse_speed(payload, source):
    report = payload['lighthouseResult'] if source == 'pagespeed' else payload
    audits = report['audits']

    def metric(name, divisor=1, digits=None):
        value = audits[name]['numericValue']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('invalid speed metric')
        return round(value / divisor, digits) if digits is not None else value

    score = report['categories']['performance']['score']
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise ValueError('invalid performance score')
    return {'source': source, 'strategy': 'mobile', 'performance': round(score * 100),
            'lcp_s': metric('largest-contentful-paint', 1000, 1),
            'fcp_s': metric('first-contentful-paint', 1000, 1),
            'tbt_ms': metric('total-blocking-time'),
            'cls': metric('cumulative-layout-shift', digits=3),
            'speed_index_s': metric('speed-index', 1000, 1)}


def measure_speed(url, env):
    key = env.get('PAGESPEED_API_KEY', '').strip()
    if key:
        query = urllib.parse.urlencode({'url': url, 'strategy': 'mobile',
                                       'category': 'performance', 'key': key})
        try:
            payload = get_json('https://www.googleapis.com/pagespeedonline/v5/runPagespeed?' + query,
                               timeout=90)
            return parse_speed(payload, 'pagespeed')
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429):
                return {'skipped': error_reason(exc)}
        except Exception as exc:
            return {'skipped': error_reason(exc)}
    lighthouse = shutil.which('lighthouse')
    if not lighthouse:
        return {'skipped': NO_SPEED}
    command = [lighthouse, url, '--quiet', '--output=json', '--output-path=stdout',
               '--only-categories=performance', '--form-factor=mobile',
               '--screenEmulation.mobile', '--chrome-flags=--headless=new']
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=180, check=True)
        return parse_speed(json.loads(run.stdout), 'lighthouse')
    except Exception as exc:
        return {'skipped': error_reason(exc)}


def cmd_speed(args):
    result = {'url': args.url, **measure_speed(args.url, args.env)}
    if 'skipped' in result:
        summary = ['Speed skipped: ' + result['skipped']]
    else:
        summary = [f'Speed: {result["performance"]}/100 mobile ({result["source"]})',
                   f'LCP {result["lcp_s"]} s; FCP {result["fcp_s"]} s; '
                   f'TBT {result["tbt_ms"]} ms; CLS {result["cls"]}; '
                   f'Speed index {result["speed_index_s"]} s']
    return save_result(args.id, 'speed', result, summary, args.env)


def remaining_budget(payload):
    try:
        maximum = payload['data']['limits']['maxMonthlyUsageUsd']
        current = payload['data']['current']['monthlyUsageUsd']
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value < 0 for value in (maximum, current)):
            return None
        return maximum - current
    except (KeyError, TypeError):
        return None


def apify_pull(actor, cap_usd, actor_input, env):
    result = {'actor': actor, 'cap_usd': cap_usd}
    token = next((env.get(name, '').strip() for name in
                  ('APIFY_API_TOKEN', 'APIFY_TOKEN', 'APIFY_API_TOKEN_PAID')
                  if env.get(name, '').strip()), '')
    if not token:
        return {**result, 'skipped': NO_APIFY}
    headers = {'Authorization': 'Bearer ' + token}
    try:
        budget = remaining_budget(get_json(APIFY_API + '/users/me/limits', headers))
    except Exception:
        budget = None
    if budget is None:
        return {**result, 'skipped': NO_BUDGET}
    if budget < MIN_REST_USD:
        return {**result, 'skipped': f'Apify budget remaining ${budget:.2f}; '
                                    f'need at least ${MIN_REST_USD:.2f}'}
    try:
        payload = get_json(f'{APIFY_API}/acts/{actor}/runs?maxTotalChargeUsd={cap_usd:.2f}',
                           headers, data=actor_input)
        run = payload['data']
        result['cost_usd'] = run.get('usageTotalUsd', 0)
        deadline = time.monotonic() + 240
        while run.get('status') in ('READY', 'RUNNING'):
            rest = deadline - time.monotonic()
            if rest <= 0:
                return {**result, 'cost_usd': run.get('usageTotalUsd', 0),
                        'skipped': f'Apify run timed out (status {run.get("status")})'}
            time.sleep(min(5, rest))
            rest = deadline - time.monotonic()
            if rest <= 0:
                return {**result, 'cost_usd': run.get('usageTotalUsd', 0),
                        'skipped': f'Apify run timed out (status {run.get("status")})'}
            run = get_json(f'{APIFY_API}/actor-runs/{run["id"]}', headers,
                           timeout=min(TIMEOUT, rest))['data']
            result['cost_usd'] = run.get('usageTotalUsd', 0)
        result['cost_usd'] = run.get('usageTotalUsd', 0)
        if run.get('status') != 'SUCCEEDED':
            return {**result, 'skipped': f'Apify run status {run.get("status", "unknown")}'}
        items = get_json(f'{APIFY_API}/datasets/{run["defaultDatasetId"]}/items?clean=true&format=json',
                         headers)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            return {**result, 'skipped': 'invalid Apify dataset'}
        return {**result, 'items': items}
    except Exception as exc:
        return {**result, 'skipped': 'Apify pull failed: ' + error_reason(exc)}


def reviews_input(url, name=None, city=None):
    searches = [domain(url)]
    if name and city:
        searches.append(f'{name} {city}')
    return {'searchStringsArray': searches, 'maxCrawledPlacesPerSearch': 5,
            'scrapePlaceDetailPage': True, 'scrapeContacts': False, 'maxReviews': 40,
            'reviewsSort': 'newest', 'maxImages': 0, 'includeWebResults': False,
            'language': 'en'}


def select_reviews(items, url, city=None):
    target = domain(url)
    matches = []
    seen = set()
    for item in items:
        if not item.get('website') or domain(item['website']) != target:
            continue
        if city and city.casefold() not in (str(item.get('address') or '') + ' '
                                           + str(item.get('city') or '')).casefold():
            continue
        place_id = item.get('placeId')
        if place_id and place_id in seen:
            continue
        if place_id:
            seen.add(place_id)
        matches.append(item)

    def candidates(values):
        return [{field: item.get(field) for field in ('title', 'address', 'website')}
                for item in values[:5]]

    if not matches:
        return {'skipped': f'no Google profile lists {target} as its website',
                'candidates': candidates(items)}
    if len(matches) > 1:
        return {'skipped': f'several Google profiles use {target}; pass --city',
                'candidates': candidates(matches)}
    item = matches[0]
    fields = ('title', 'address', 'url', 'placeId', 'categoryName', 'totalScore',
              'reviewsCount', 'reviewsDistribution', 'reviewsTags', 'website')
    place = {field: item.get(field) for field in fields}
    reviews = []
    for review in (item.get('reviews') or [])[:40]:
        reviews.append({'stars': review.get('stars'), 'text': str(review.get('text') or '')[:600],
                        'publishedAtDate': review.get('publishedAtDate'),
                        'reviewUrl': review.get('reviewUrl'),
                        'owner_replied': bool(review.get('responseFromOwnerText'))})
    low_star = [review for review in reviews if isinstance(review['stars'], (int, float))
                and review['stars'] <= 3]
    return {'place': place, 'reviews': reviews, 'low_star': low_star}


def cmd_reviews(args):
    result = apify_pull(REVIEWS_ACTOR, REVIEWS_CAP_USD,
                        reviews_input(args.url, args.name, args.city), args.env)
    items = result.pop('items', None)
    if items is not None:
        try:
            result.update(select_reviews(items, args.url, args.city))
        except Exception as exc:
            result['skipped'] = 'invalid reviews data: ' + error_reason(exc)
    if 'skipped' in result:
        summary = ['Reviews skipped: ' + result['skipped']]
    else:
        reviews = result['reviews']
        share = sum(review['owner_replied'] for review in reviews) / len(reviews) if reviews else 0
        summary = [f'Reviews: {result["place"]["totalScore"]} rating; '
                   f'{result["place"]["reviewsCount"]} total',
                   f'Owner replies: {share:.0%} of {len(reviews)} newest reviews',
                   f'Low-star reviews: {len(result["low_star"])}']
    return save_result(args.id, 'reviews', result, summary, args.env)


def ads_query(term, country='US'):
    if term.startswith('http') and 'facebook.com/' in term and '/ads/library' not in term:
        return term
    query = urllib.parse.urlencode({'active_status': 'active', 'ad_type': 'all',
                                    'country': country, 'q': term,
                                    'search_type': 'keyword_unordered', 'media_type': 'all'})
    return 'https://www.facebook.com/ads/library/?' + query


def parse_ads(items):
    for item in items:
        if item.get('error') and item.get('errorCode') != 'ADS_NOT_FOUND':
            return {'skipped': str(item['error'])}
    ads = []
    pages = {}
    fields = ('ad_archive_id', 'page_name', 'page_id', 'is_active',
              'start_date_formatted', 'end_date_formatted', 'publisher_platform',
              'ad_library_url', 'collation_count')
    for item in items:
        if not item.get('ad_archive_id'):
            continue
        ad = {field: item.get(field) for field in fields}
        snapshot = item.get('snapshot') or {}
        body = snapshot.get('body') or {}
        ad['snapshot'] = {'body': {'text': str(body.get('text') or '')[:300]},
                          **{field: snapshot.get(field) for field in
                             ('title', 'link_url', 'cta_text', 'page_profile_uri')}}
        ads.append(ad)
        identity = (item.get('page_name'), snapshot.get('page_profile_uri'))
        if identity not in pages:
            pages[identity] = {'page_name': identity[0], 'page_profile_uri': identity[1],
                               'ad_count': 0}
        pages[identity]['ad_count'] += 1
    result = {'found': bool(ads), 'ads': ads, 'pages': list(pages.values())}
    if not ads:
        result['note'] = 'Ad Library shows no active ads for this search'
    return result


def cmd_ads(args):
    query_url = ads_query(args.term, args.country)
    result = apify_pull(ADS_ACTOR, ADS_CAP_USD,
                        {'urls': [{'url': query_url}], 'count': 10,
                         'scrapeAdDetails': False}, args.env)
    items = result.pop('items', None)
    result['query_url'] = query_url
    if items is not None:
        try:
            result.update(parse_ads(items))
        except Exception as exc:
            result['skipped'] = 'invalid ads data: ' + error_reason(exc)
    if 'skipped' in result:
        summary = ['Ads skipped: ' + result['skipped']]
    elif not result['found']:
        summary = [result['note']]
    else:
        ads = result['ads']
        dates = [str(ad['start_date_formatted']) for ad in ads if ad['start_date_formatted']]
        platforms = unique(str(platform) for ad in ads for platform in
                           (ad['publisher_platform'] or []))
        ctas = unique(str(ad['snapshot']['cta_text']) for ad in ads if ad['snapshot']['cta_text'])
        summary = [f'Active ads: {len(ads)}',
                   'Pages: ' + ', '.join(str(page['page_name']) for page in result['pages']),
                   'Earliest start: ' + (min(dates) if dates else 'unknown'),
                   'Platforms: ' + ', '.join(platforms), 'CTAs: ' + ', '.join(ctas)]
        if 'note' in result:
            summary.append(result['note'])
    return save_result(args.id, 'ads', result, summary, args.env)


def markdown_urls(text):
    return unique(url.rstrip('.,;:') for url in re.findall(r'https?://[^\s<>\)\]\}\"\']+', text))


def check_dossier(text):
    findings = []
    if '\u2014' in text:
        findings.append('remove U+2014')
    headings = list(re.finditer(r'^##[ \t]+(.+?)[ \t]*$', text, re.M))
    names = [match.group(1) for match in headings]
    if names != HEADINGS:
        findings.append('use exactly these ## headings in order: ' + ', '.join(HEADINGS))
    intro = text[:headings[0].start()] if headings else text
    lines = [line.strip() for line in intro.splitlines() if line.strip()]
    title_lines = [line for line in lines if re.match(r'^#\s+\S', line)]
    prose = [line for line in lines if not re.match(r'^#\s+', line)]
    if len(title_lines) != 1 or not lines or lines[0] != title_lines[0]:
        findings.append('start with one # title before the first ## heading')
    if not 1 <= len(prose) <= 3 or any(re.match(r'^(?:#|[-*+]\s|\d+[.)]\s|>)', line)
                                     for line in prose):
        findings.append('add 1-3 non-empty prose lines before the first ## heading')
    sections = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.setdefault(match.group(1), text[match.end():end])
    for name, section in sections.items():
        if name != 'What we know' and re.search(r'^###[ \t]+', section, re.M):
            findings.append('### subheadings are only allowed inside What we know: ' + name)
    agenda = re.findall(r'^\s*\d+\.\s+\S.*$', sections.get('Call agenda', ''), re.M)
    if not 3 <= len(agenda) <= 7:
        findings.append('Call agenda needs 3-7 numbered items')
    for bullet in re.findall(r'^[ \t]*[-*][ \t]+.*$', sections.get('What we know', ''), re.M):
        if not re.search(r'\]\(https?://[^\s)]+', bullet):
            findings.append('What we know bullet needs a markdown source link: ' + bullet.strip()[:60])
    before = re.findall(r'^[ \t]*[-*][ \t]+.*$', sections.get('Before the call', ''), re.M)
    if len(before) > 5:
        findings.append('Before the call allows 0-5 bullets')
    for bullet in before:
        if not re.search(r'free|\$', bullet, re.I):
            findings.append('Before the call bullet needs free or $: ' + bullet.strip()[:60])
    source_heading = next((match for match in headings if match.group(1) == 'Sources'), None)
    above = text[:source_heading.start()] if source_heading else text
    source_urls = set(markdown_urls(sections.get('Sources', '')))
    for url in markdown_urls(above):
        if url not in source_urls:
            findings.append('Sources is missing URL: ' + url)
    if len(above.split()) > 900:
        findings.append(f'keep everything above Sources within 900 words ({len(above.split())})')
    return [('FIX: ' + finding).replace('\u2014', '-') for finding in findings]


def cmd_check(args):
    path = pipeline.jobs_dir() / args.id / 'call-prep.md'
    try:
        findings = check_dossier(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError) as exc:
        findings = [f'FIX: cannot read UTF-8 dossier {path} ({type(exc).__name__})']
    if findings:
        for finding in findings:
            print(redact(finding, getattr(args, 'env', {})))
        return 1
    print(f'PASS call-prep {args.id}')
    return 0


def job_id(value):
    if not ID.fullmatch(value):
        raise argparse.ArgumentTypeError('id must contain 6-25 digits')
    return value


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('must be a positive integer') from None
    if number < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return number


def http_url(value):
    try:
        parts = urllib.parse.urlsplit(value)
        valid = parts.scheme in ('http', 'https') and parts.hostname
        parts.port
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError('url must be an absolute HTTP(S) URL')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    site = sub.add_parser('site', help='Fetch website pages and detect the tech stack')
    site.add_argument('id', type=job_id)
    site.add_argument('url', type=http_url)
    site.add_argument('--max-pages', type=positive_int, default=6)
    site.set_defaults(func=cmd_site)
    speed = sub.add_parser('speed', help='Measure mobile PageSpeed or local Lighthouse')
    speed.add_argument('id', type=job_id)
    speed.add_argument('url', type=http_url)
    speed.set_defaults(func=cmd_speed)
    reviews = sub.add_parser('reviews', help='Pull capped Google reviews via Apify')
    reviews.add_argument('id', type=job_id)
    reviews.add_argument('url', type=http_url)
    reviews.add_argument('--name')
    reviews.add_argument('--city')
    reviews.set_defaults(func=cmd_reviews)
    ads = sub.add_parser('ads', help='Pull capped Facebook Ad Library results via Apify')
    ads.add_argument('id', type=job_id)
    ads.add_argument('term', metavar='term-or-facebook-page-url')
    ads.add_argument('--country', default='US')
    ads.set_defaults(func=cmd_ads)
    check = sub.add_parser('check', help='Validate the call dossier without writing files')
    check.add_argument('id', type=job_id)
    check.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    args.env = dict(os.environ)
    env_file.load_dotenv(ROOT / '.env', args.env)
    env_file.load_dotenv(Path.home() / '.config' / 'credentials.env', args.env)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
