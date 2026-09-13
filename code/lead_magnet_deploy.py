#!/usr/bin/env python3
"""Publish one checked SEO audit to the shared Vercel site and save its URL."""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import lead_magnet_check
import pitch_check
import pitch_deploy


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def pages_for(current_id, source, records):
    route = f'{current_id}/audit'
    pages = {route: source}
    for record in records:
        job_id = str(record.get('id') or '')
        pitch = ROOT / 'jobs' / job_id / 'pitch.html'
        if record.get('pitch_url') and pitch.is_file():
            problems = pitch_check.check_page(pitch)
            if problems:
                abort(f'the previously published pitch {job_id} failed its gate: ' + '; '.join(problems))
            pages[job_id] = pitch
        audit = ROOT / 'jobs' / job_id / 'lead-magnet.html'
        if record.get('lead_magnet_url') and job_id != current_id and audit.is_file():
            problems = lead_magnet_check.check_page(audit)
            if problems:
                abort(f'the previously published audit {job_id} failed its gate: ' + '; '.join(problems))
            pages[f'{job_id}/audit'] = audit
    return route, pages


def publish(job_id):
    if not re.fullmatch(r'[0-9]{6,25}', job_id):
        abort('the job id is not valid.')
    source = ROOT / 'jobs' / job_id / 'lead-magnet.html'
    if not source.is_file():
        abort(f'jobs/{job_id}/lead-magnet.html does not exist.')
    problems = lead_magnet_check.check_page(source)
    if problems:
        abort('the SEO audit failed its public gate: ' + '; '.join(problems))

    try:
        records = json.loads((ROOT / 'data' / 'jobs.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        records = []
    route, pages = pages_for(job_id, source, records)

    vercel = shutil.which('vercel')
    if not vercel:
        abort('install the Vercel CLI before building a paid audit.')
    config = pitch_deploy.deployment_config()
    options = pitch_deploy.auth_args(config)
    inspect = subprocess.run(
        [vercel, 'project', 'inspect', config['project'], *options],
        env=config['env'], capture_output=True, text=True,
    )
    if inspect.returncode:
        abort('the Vercel project was not available after preflight.')
    with tempfile.TemporaryDirectory(prefix='upwork-audit-') as temp:
        stage = pathlib.Path(temp)
        pitch_deploy.write_site(stage, sorted(pages.items()), route)
        pitch_deploy.run(
            [vercel, 'link', '--yes', '--project', config['project'], '--cwd', str(stage), *options], config)
        pitch_deploy.run([vercel, 'deploy', '--yes', '--prod', '--cwd', str(stage), *options], config)
        url = f'https://{config["domain"]}/{route}'

    title = re.search(r'<title>(.*?)</title>', source.read_text(encoding='utf-8'), re.I | re.S)
    pitch_deploy.verify_public(url, title.group(1).strip() if title else '')
    pitch_deploy.run(
        [sys.executable, str(ROOT / 'code' / 'pipeline.py'), 'lead-magnet-url', job_id, url], config, ROOT)
    print(f'Published {url}')
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    args = parser.parse_args()
    publish(args.job_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
