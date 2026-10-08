#!/usr/bin/env python3
"""Publish one checked pitch page to Vercel and save its public URL.

    python3 code/pitch_deploy.py <job id>

The deployment contains only checked pitch pages. Job drafts and member context
never enter the upload directory. Each published job keeps a stable URL path.
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
from pipeline import jobs_dir
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,99}$')
HOST_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*\.vercel\.app$')


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_dotenv(path, env):
    """Load simple KEY=VALUE lines without replacing exported values.

    An empty value does not count as a value. `.env` is copied from
    `.env.example`, which lists every key with nothing after the equals sign, so
    plain setdefault let that placeholder shadow the real key in
    `~/.config/credentials.env`: setup.sh found the key, the preflight did not,
    and the member was told to buy a service they already pay for.
    """
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
        if value.strip() and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) and not str(env.get(key) or '').strip():
            env[key] = value


def deployment_config(env=None):
    env = dict(os.environ if env is None else env)
    load_dotenv(ROOT / '.env', env)
    # The same second place the preflight reads. Without it a member
    # who keeps their keys centrally passes every check and then fails to publish.
    load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
    project = env.get('VERCEL_PITCH_PROJECT', '').strip()
    if not PROJECT_RE.fullmatch(project):
        abort('run ./setup.sh to set VERCEL_PITCH_PROJECT, using lowercase letters, numbers and hyphens.')
    domain = env.get('VERCEL_PITCH_DOMAIN', '').strip().lower()
    if domain and not HOST_RE.fullmatch(domain):
        abort('VERCEL_PITCH_DOMAIN must be a vercel.app hostname without a path.')
    return {
        'token': env.get('VERCEL_TOKEN', '').strip(),
        'scope': env.get('VERCEL_SCOPE', '').strip(),
        'project': project,
        'domain': domain,
        'env': env,
    }


def auth_args(config):
    args = ['--no-color']
    if config['scope']:
        args += ['--scope', config['scope']]
    if config['token']:
        args += ['--token', config['token']]
    return args


def write_site(folder, pages, current_id):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'index.html').write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Private pages</title></head><body><p>Open the link you were given.</p>'
        '</body></html>', encoding='utf-8')
    for route, source in pages:
        target = folder / route
        target.mkdir(parents=True)
        shutil.copy2(source, target / 'index.html')
    (folder / 'vercel.json').write_text(json.dumps({
        'cleanUrls': True,
        'trailingSlash': False,
    }), encoding='utf-8')


def production_host(stdout):
    """Read a deployment URL from CLI output, never guess from a project name."""
    for url in re.findall(r'https://[a-z0-9.-]+(?:/[^\s]*)?', stdout, re.I):
        host = urllib.parse.urlparse(url).hostname or ''
        if HOST_RE.fullmatch(host):
            return host
    return ''


def save_host(host, config):
    path = ROOT / '.env'
    lines = path.read_text(encoding='utf-8').splitlines() if path.is_file() else []
    lines = [line for line in lines if not re.match(r'^\s*VERCEL_PITCH_DOMAIN\s*=', line)]
    lines.append(f'VERCEL_PITCH_DOMAIN={host}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    config['domain'] = host
    config['env']['VERCEL_PITCH_DOMAIN'] = host


def resolve_host(vercel, config, deployment):
    """Prefer the production alias returned by inspect --json, then the deployment."""
    host = production_host(deployment.stdout)
    if not host:
        abort('Vercel did not return a deployment URL; the public address is unknown.')
    result = subprocess.run(
        [vercel, 'inspect', f'https://{host}', '--json', *auth_args(config)],
        env=config['env'], capture_output=True, text=True)
    aliases = []
    if not result.returncode:
        try:
            info = json.loads(result.stdout)
            # Vercel CLI 50 names the list `aliases`; older output used `alias`.
            aliases = (info.get('aliases') or info.get('alias') or []) if isinstance(info, dict) else []
        except json.JSONDecodeError:
            pass
    aliases = aliases if isinstance(aliases, list) else []
    aliases = [alias.lower() for alias in aliases
               if isinstance(alias, str) and HOST_RE.fullmatch(alias.lower())]
    # A production deploy gets the short project alias and longer team aliases that
    # Vercel may put behind its login; the short one is the public address.
    plain = [alias for alias in aliases if alias.split('.')[0] == config['project']]
    if aliases:
        host = (config['domain'] if config['domain'] in aliases
                else plain[0] if plain else min(aliases, key=len))
    if not HOST_RE.fullmatch(host):
        abort('Vercel returned an invalid public hostname.')
    return host


def run(command, config, cwd=None):
    result = subprocess.run(command, cwd=cwd, env=config['env'], capture_output=True, text=True)
    if result.returncode:
        message = (result.stderr or result.stdout or 'Vercel command failed.').strip()
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        abort(' '.join(lines[-6:]))
    return result


def verify_public(url, expected_title=''):
    request = urllib.request.Request(url, headers={'User-Agent': 'Automatable-Cockpit/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(65536).lower()
            status = response.status
            final_url = response.geturl()
    except Exception as error:
        abort(f'the deployment could not be opened publicly: {error}')
    final = urllib.parse.urlparse(final_url)
    if final.hostname == 'vercel.com' or final.path.startswith('/login'):
        abort('the production URL redirects to Vercel login instead of opening publicly.')
    title = expected_title.encode('utf-8').lower() if expected_title else b''
    if status != 200 or b'<html' not in body or (title and title not in body):
        abort(f'the public deployment returned HTTP {status} without the pitch page.')


def publish(job_id):
    if not re.fullmatch(r'[0-9]{6,25}', job_id):
        abort('the job id is not valid.')
    source = jobs_dir() / job_id / 'pitch.html'
    if not source.is_file():
        abort(f'jobs/{job_id}/pitch.html does not exist.')

    sys.path.insert(0, str(ROOT / 'code'))
    import pitch_check
    problems = pitch_check.check_page(source)
    if problems:
        abort('the pitch page failed its gate: ' + '; '.join(problems))

    pages = {job_id: source}
    try:
        records = json.loads((ROOT / 'data' / 'jobs.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        records = []
    for record in records:
        published_id = str(record.get('id') or '')
        published = jobs_dir() / published_id / 'pitch.html'
        if record.get('pitch_url') and published_id != job_id and published.is_file():
            old_problems = pitch_check.check_page(published)
            if old_problems:
                abort(f'the previously published pitch {published_id} failed its gate: ' + '; '.join(old_problems))
            pages[published_id] = published

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
    with tempfile.TemporaryDirectory(prefix='upwork-pitch-') as temp:
        stage = pathlib.Path(temp)
        write_site(stage, sorted(pages.items()), job_id)
        run([vercel, 'link', '--yes', '--project', config['project'], '--cwd', str(stage), *options], config)
        deployment = run([vercel, 'deploy', '--yes', '--prod', '--cwd', str(stage), *options], config)
        host = resolve_host(vercel, config, deployment)
        url = f'https://{host}/{job_id}'

    title = re.search(r'<title>(.*?)</title>', source.read_text(encoding='utf-8'), re.I | re.S)
    verify_public(url, title.group(1).strip() if title else '')
    # Only an address that just opened publicly is kept for the next run.
    save_host(host, config)
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
