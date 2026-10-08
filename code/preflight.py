#!/usr/bin/env python3
"""Fail before paid work when credentials or publishing are unavailable.

Every check reads its credentials first and returns without them, never calling the
provider: a check made with an empty key produces a request that proves nothing and
still counts against the account it could not authenticate.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import pitch_deploy


def get_json(url, headers, *, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers=headers)
    try:
        with opener(request, timeout=20) as response:
            return json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', 'replace')[:180]
        raise RuntimeError(f'HTTP {error.code}: {detail}') from error
    except Exception as error:
        raise RuntimeError(str(error)) from error


def kie_error(env, *, fetch=get_json):
    """The image service, checked the only way it can be checked for free.

    kie.ai publishes no balance endpoint this repo has measured, so this asks the
    endpoint the generator itself polls, with a task id that does not exist. A key
    that is wrong comes back as a rejection; a key that is right comes back as
    anything else, including "no such task", which is the answer we want. Guessing
    at a credit figure would be worse than admitting there is none: the run still
    reports what it spent when it is done.
    """
    key = str(env.get('KIE_AI_API_KEY') or '').strip()
    if not key:
        return 'Add KIE_AI_API_KEY to .env.'
    try:
        answer = fetch('https://api.kie.ai/api/v1/jobs/recordInfo?taskId=preflight-no-such-task',
                       {'Authorization': f'Bearer {key}'})
    except RuntimeError as error:
        return f'kie.ai did not answer: {error}'
    # Measured 28 September 2026: the service answers HTTP 200 either way and puts
    # the verdict in the body. A rejected key is code 401, an accepted key asking
    # for a task that does not exist is 422 "recordInfo is null". Reading the HTTP
    # status instead would wave a revoked key straight through to the first bill.
    if answer.get('code') in (401, 403):
        return f'kie.ai refused the key: {answer.get("msg") or answer.get("code")}'
    return ''


def last_line(text):
    """The account name, past the CLI's own banner line."""
    lines = [line.strip() for line in str(text or '').splitlines() if line.strip()]
    return lines[-1] if lines else ''


def vercel_error(env, *, which=shutil.which, runner=subprocess.run, ensure_project=True):
    vercel = which('vercel')
    if not vercel:
        return 'Install the Vercel CLI before starting.'
    try:
        config = pitch_deploy.deployment_config(env)
    except SystemExit:
        return 'Fix the Vercel project settings in .env.'
    options = pitch_deploy.auth_args(config)
    who = runner([vercel, 'whoami', *options], env=config['env'], capture_output=True, text=True)
    if who.returncode or not who.stdout.strip():
        return 'Vercel authentication failed. Log in or add a valid VERCEL_TOKEN.'
    # A token always beats the account behind `vercel login`, and nothing says so
    # while it works: a stale one publishes a client's page into a stranger's
    # Vercel and reports success. A token for a team is legitimate, and that case
    # names its team in VERCEL_SCOPE, so only the silent mismatch stops the run.
    if str(config['env'].get('VERCEL_TOKEN') or '').strip() and not str(
            config['env'].get('VERCEL_SCOPE') or '').strip():
        login = runner([vercel, 'whoami'], capture_output=True, text=True)
        named = last_line(who.stdout)
        signed_in = last_line(login.stdout) if not login.returncode else ''
        if signed_in and named and signed_in != named:
            return (f'your VERCEL_TOKEN publishes as {named}, but vercel login is {signed_in}. '
                    f'The token wins, so a client page would land in that account. Remove '
                    f'VERCEL_TOKEN to use your login, or set VERCEL_SCOPE if {named} is meant.')
    inspect = runner([vercel, 'project', 'inspect', config['project'], *options],
                     env=config['env'], capture_output=True, text=True)
    if not inspect.returncode:
        return ''
    if not ensure_project:
        return f'Vercel project {config["project"]} is not available.'
    added = runner([vercel, 'project', 'add', config['project'], *options],
                   env=config['env'], capture_output=True, text=True)
    if added.returncode:
        return f'Vercel project {config["project"]} could not be created or opened.'
    checked = runner([vercel, 'project', 'inspect', config['project'], *options],
                     env=config['env'], capture_output=True, text=True)
    return '' if not checked.returncode else f'Vercel project {config["project"]} is still unavailable.'


def checks(profile, env, *, fetch=get_json, which=shutil.which, runner=subprocess.run):
    if profile == 'vercel':
        return [('Vercel', vercel_error(env, which=which, runner=runner))]
    if profile == 'proposal':
        return [('kie.ai', kie_error(env, fetch=fetch))]
    raise ValueError(f'unknown preflight profile: {profile}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=('vercel', 'proposal'))
    args = parser.parse_args(argv)
    env = dict(os.environ)
    pitch_deploy.load_dotenv(ROOT / '.env', env)
    pitch_deploy.load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
    results = checks(args.profile, env)
    for name, problem in results:
        print(f'{"FAIL" if problem else "PASS"}  {name}{f": {problem}" if problem else ""}')
    return 1 if any(problem for _, problem in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
