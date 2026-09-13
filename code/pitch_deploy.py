#!/usr/bin/env python3
"""Publish one checked pitch page to Vercel and save its public URL.

    python3 code/pitch_deploy.py <job id>

The deployment contains only the generated pitch.html. Job drafts and member
context never enter the upload directory.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,99}$')
URL_RE = re.compile(r'https://[a-z0-9][a-z0-9.-]*\.vercel\.app(?:/[^\s]*)?', re.IGNORECASE)


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_dotenv(path, env):
    """Load simple KEY=VALUE lines without replacing exported values."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value[:1] in ('"', "'"):
            value = value[1:-1]
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            env.setdefault(key, value)


def deployment_config(env=None):
    env = dict(os.environ if env is None else env)
    load_dotenv(ROOT / '.env', env)
    project = env.get('VERCEL_PITCH_PROJECT', 'upwork-pitches').strip()
    if not PROJECT_RE.fullmatch(project):
        abort('VERCEL_PITCH_PROJECT must use lowercase letters, numbers and hyphens.')
    return {
        'token': env.get('VERCEL_TOKEN', '').strip(),
        'scope': env.get('VERCEL_SCOPE', '').strip(),
        'project': project,
        'env': env,
    }


def auth_args(config):
    args = ['--no-color']
    if config['scope']:
        args += ['--scope', config['scope']]
    if config['token']:
        args += ['--token', config['token']]
    return args


def deployment_url(output, fallback=''):
    """Prefer the CLI's stdout URL over progress and alias URLs on stderr."""
    urls = URL_RE.findall(output or '') or URL_RE.findall(fallback or '')
    if not urls:
        abort('Vercel finished without returning a deployment URL.')
    return urls[-1].rstrip('/')


def write_site(folder, source):
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, folder / 'index.html')
    (folder / 'vercel.json').write_text(json.dumps({
        'cleanUrls': True,
        'trailingSlash': False,
    }), encoding='utf-8')


def run(command, config, cwd=None):
    result = subprocess.run(command, cwd=cwd, env=config['env'], capture_output=True, text=True)
    if result.returncode:
        message = (result.stderr or result.stdout or 'Vercel command failed.').strip()
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        abort(' '.join(lines[-6:]))
    return result


def verify_public(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Automatable-Cockpit/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(65536).lower()
            status = response.status
    except Exception as error:
        abort(f'the deployment could not be opened publicly: {error}')
    if status != 200 or b'<html' not in body:
        abort(f'the public deployment returned HTTP {status} without the pitch page.')


def make_project_public(config):
    """Disable Vercel Authentication for the dedicated public pitch project."""
    if not config['token']:
        return
    query = ''
    if config['scope']:
        key = 'teamId' if config['scope'].startswith('team_') else 'slug'
        query = '?' + urllib.parse.urlencode({key: config['scope']})
    url = f"https://api.vercel.com/v9/projects/{urllib.parse.quote(config['project'])}{query}"
    request = urllib.request.Request(
        url,
        data=json.dumps({'ssoProtection': None}).encode('utf-8'),
        headers={'Authorization': f"Bearer {config['token']}", 'Content-Type': 'application/json'},
        method='PATCH',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                abort(f'Vercel could not make the pitch project public (HTTP {response.status}).')
    except Exception as error:
        abort(f'Vercel could not make the pitch project public: {error}')


def publish(job_id):
    if not re.fullmatch(r'[0-9]{6,25}', job_id):
        abort('the job id is not valid.')
    source = ROOT / 'jobs' / job_id / 'pitch.html'
    if not source.is_file():
        abort(f'jobs/{job_id}/pitch.html does not exist.')

    sys.path.insert(0, str(ROOT / 'code'))
    import pitch_check
    problems = pitch_check.check_page(source)
    if problems:
        abort('the pitch page failed its gate: ' + '; '.join(problems))

    vercel = shutil.which('vercel')
    if not vercel:
        abort('install the Vercel CLI, then run the pitch again.')
    config = deployment_config()
    options = auth_args(config)

    inspect = subprocess.run(
        [vercel, 'project', 'inspect', config['project'], *options],
        env=config['env'], capture_output=True, text=True,
    )
    if inspect.returncode:
        run([vercel, 'project', 'add', config['project'], *options], config)
    make_project_public(config)

    with tempfile.TemporaryDirectory(prefix='upwork-pitch-') as temp:
        stage = pathlib.Path(temp)
        write_site(stage, source)
        run([vercel, 'link', '--yes', '--project', config['project'], '--cwd', str(stage), *options], config)
        deployed = run([vercel, 'deploy', '--yes', '--prod', '--cwd', str(stage), *options], config)
        url = deployment_url(deployed.stdout, deployed.stderr)

    verify_public(url)
    run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), 'pitch-url', job_id, url], config, ROOT)
    print(f'Published {url}')
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    args = parser.parse_args()
    publish(args.job_id)
    return 0


if __name__ == '__main__':
    sys.exit(main())
