#!/usr/bin/env python3
"""Sync pitch link hits, or register a link after member approval.

clicks.py [job_id] [--log synthetic.jsonl]
clicks.py register job_id slug target --base https://pitch-host --kind application|proposal --approved
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import pipeline


def blob_headers(token):
    parts = token.split('_')
    return {'Authorization': f'Bearer {token}', 'x-api-version': '12',
            'x-vercel-blob-store-id': parts[3] if len(parts) > 3 else ''}


def remote_hits(token, job_id=None):
    cursor = None
    while True:
        query = {'prefix': f'clicks/{job_id}/' if job_id else 'clicks/', 'limit': 1000}
        if cursor:
            query['cursor'] = cursor
        request = urllib.request.Request('https://vercel.com/api/blob?' + urllib.parse.urlencode(query),
                                         headers=blob_headers(token))
        with urllib.request.urlopen(request, timeout=15) as response:
            page = json.load(response)
        for blob in page.get('blobs', []):
            url = blob.get('url', '')
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.private.blob.vercel-storage.com'):
                raise ValueError('Blob returned an unexpected private URL')
            request = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
            with urllib.request.urlopen(request, timeout=15) as response:
                yield json.load(response)
        if not page.get('hasMore'):
            return
        next_cursor = page.get('cursor')
        if not next_cursor or next_cursor == cursor:
            raise ValueError('Blob pagination did not advance')
        cursor = next_cursor


def clean_hit(row):
    if not isinstance(row, dict) or set(row) != {'job', 'slug', 'at', 'bot'}:
        raise ValueError('Click rows need only job, slug, at and bot')
    if (not isinstance(row['job'], str) or not re.fullmatch(r'\d{6,25}', row['job'])
            or not isinstance(row['slug'], str) or not re.fullmatch(r'[a-z0-9-]{1,80}', row['slug'])
            or not isinstance(row['bot'], bool)):
        raise ValueError('Click row has invalid fields')
    stamp = pipeline.verified_timestamp(row['at'])
    return dict(row, at=stamp)


def sync_hits(rows, job_id=None):
    jobs = {job['id']: job for job in pipeline.load()}
    grouped = {}
    for row in rows:
        row = clean_hit(row)
        if row['job'] in jobs and (job_id is None or row['job'] == job_id):
            grouped.setdefault(row['job'], []).append(row)
    synced = 0
    for jid, hits in grouped.items():
        folder = pipeline.jobs_dir() / jid
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'clicks.json'
        old = [clean_hit(row) for row in json.loads(path.read_text(encoding='utf-8'))] if path.exists() else []
        unique = {json.dumps(row, sort_keys=True): row for row in old + hits}
        merged = sorted(unique.values(), key=lambda row: row['at'])
        path.write_text(json.dumps(merged, indent=2) + '\n', encoding='utf-8')
        registry_path = folder / 'tracking-links.json'
        links = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {}
        for kind, send, event in [('application', 'applied_at', 'pitch_opened'),
                                 ('proposal', 'proposal_sent_at', 'opened')]:
            sent = pipeline.parse_verified_timestamp(jobs[jid].get(send))
            human = next((row for row in merged if not row['bot'] and
                          links.get(row['slug'], {}).get('kind') == kind and sent and row['at'] > sent), None)
            if human:
                subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('pipeline.py')),
                                'observe', jid, event, human['at'], '--source', 'pitch-click', '--verified'],
                               check=True, capture_output=True, text=True)
        synced += len(hits)
    return synced


def preflight(token):
    request = urllib.request.Request('https://vercel.com/api/blob?limit=1', headers=blob_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            page = json.load(response)
        return isinstance(page.get('blobs'), list)
    except (OSError, ValueError):
        return False


def register(argv):
    parser = argparse.ArgumentParser(description='Register only after member approval; test one real proposal before making tracking a default.')
    parser.add_argument('job_id')
    parser.add_argument('slug')
    parser.add_argument('target')
    parser.add_argument('--base', required=True)
    parser.add_argument('--kind', required=True, choices=('application', 'proposal'))
    parser.add_argument('--approved', action='store_true', required=True)
    args = parser.parse_args(argv)
    pipeline.find(pipeline.load(), args.job_id)
    if not os.environ.get('BLOB_READ_WRITE_TOKEN'):
        print('Tracking skipped: BLOB_READ_WRITE_TOKEN is missing. Keep the original untracked link.')
        return 0
    if not preflight(os.environ['BLOB_READ_WRITE_TOKEN']):
        print('Tracking skipped: Blob store/token preflight failed. Keep the original untracked link.')
        return 0
    if not re.fullmatch(r'[a-z0-9-]{1,80}', args.slug):
        parser.error('slug must use lowercase letters, digits and hyphens')
    target, base = urllib.parse.urlparse(args.target), urllib.parse.urlparse(args.base)
    if (target.scheme != 'https' or not target.hostname or target.username or target.password
            or base.scheme != 'https' or not base.hostname or base.username or base.password
            or base.path not in ('', '/') or base.query or base.fragment):
        parser.error('target and base need HTTPS addresses; base is the pitch host only')
    from pitch_check import CONTACT_LINKS, EMAIL
    if CONTACT_LINKS.search(args.target) or EMAIL.search(args.target):
        parser.error('the destination links a way to reach you off Upwork')
    if target.hostname == base.hostname and target.path.startswith('/go/'):
        parser.error('a tracking route cannot target another tracking route')
    folder = pipeline.jobs_dir() / args.job_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'tracking-links.json'
    links = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    old = links.get(args.slug)
    if old and (old['target'] != args.target or old.get('kind') != args.kind):
        parser.error('this slug already names another target; choose a new slug')
    links[args.slug] = old or {'target': args.target, 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'base': args.base.rstrip('/'), 'kind': args.kind}
    path.write_text(json.dumps(links, indent=2) + '\n', encoding='utf-8')
    print(f'{args.base.rstrip("/")}/go/{args.job_id}/{args.slug}')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'register':
        return register(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id', nargs='?')
    parser.add_argument('--log', type=pathlib.Path, help='local synthetic JSONL log; no network')
    args = parser.parse_args(argv)
    if args.job_id:
        pipeline.find(pipeline.load(), args.job_id)
    token = os.environ.get('BLOB_READ_WRITE_TOKEN')
    if not args.log and not token:
        print('Click sync skipped: BLOB_READ_WRITE_TOKEN is missing. Links remain untracked.')
        return 0
    try:
        rows = ([json.loads(line) for line in args.log.read_text(encoding='utf-8').splitlines() if line.strip()]
                if args.log else remote_hits(token, args.job_id))
        print(f'Click sync: {sync_hits(rows, args.job_id)} hits read; bots excluded from opened.')
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Click sync failed: {type(exc).__name__}. Existing data kept.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
