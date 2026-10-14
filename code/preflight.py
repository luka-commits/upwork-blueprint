#!/usr/bin/env python3
"""Fail before paid work when a credential is missing or refused.

Every check reads its credentials first and returns without them, never calling the
provider: a check made with an empty key produces a request that proves nothing and
still counts against the account it could not authenticate.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


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
