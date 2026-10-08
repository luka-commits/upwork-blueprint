#!/usr/bin/env python3
"""A won job becomes a client, and a client gets a folder of their own.

    python3 code/client_workspace.py new <job id> [--slug <name>]
    python3 code/client_workspace.py list

A job folder is a sales artefact: it holds the pitch, the letter and the proposal, and it
stops mattering the day the contract starts. Delivery needs something else, the same thing
every other system here needs: one place per client, with the facts at the top and the work
beside them.

    clients/<slug>/
    ├── context.md    who they are, what was sold, what was promised, where access lives
    ├── brief.md      the handover brief, copied once from the job folder
    ├── inputs/       what the client sends
    ├── work/         drafts in progress
    └── delivered/    what went out, dated

Everything under clients/ is the member's own work and gitignored, exactly like context/,
data/ and jobs/. The pipeline record keeps the slug, so the cockpit can point at it later.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

import pipeline

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENTS = ROOT / 'clients'
FOLDERS = ('inputs', 'work', 'delivered')


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def slugify(text):
    slug = re.sub(r'[^a-z0-9]+', '-', str(text or '').lower()).strip('-')
    return slug[:48] or 'client'


def client_name(job):
    if job.get('contract_client'):
        return str(job['contract_client'])
    try:
        thread = json.loads((pipeline.jobs_dir() / str(job['id']) / 'thread.json').read_text(encoding='utf-8'))
        for message in thread.get('messages') or []:
            if message.get('from') == 'client' and message.get('name'):
                return str(message['name'])
    except (OSError, json.JSONDecodeError):
        pass
    client = job.get('client') or {}
    for key in ('company_name', 'name'):
        if client.get(key):
            return str(client[key])
    return str(job.get('title') or f'job-{job.get("id")}')


def context_text(job, slug):
    """The facts a delivery run needs, and a marked gap where the call has not filled one."""
    client = job.get('client') or {}
    today = datetime.date.today().strftime('%d %B %Y')
    open_line = '_not recorded yet_'
    return f'''# {client_name(job)}

Opened {today} from Upwork job `{job.get("id")}`. This file is the client's facts; the pipeline
keeps their stage. When the two disagree, the pipeline is right about the stage and this file is
right about the work.

## Who

**Client:** {client_name(job)}
**Country and timezone:** {client.get("country") or open_line}
**Where we talk:** Upwork messages on this contract. Nothing moves off Upwork.
**Upwork job:** {job.get("url") or open_line}

## What was sold

**The outcome:** {open_line}
**Deliverables:** {open_line}
**Not included:** {open_line}
**Price and milestones:** {open_line}
**Dates:** {open_line}

## How it runs

**Reporting:** {open_line}
**Approvals:** each milestone is approved before the next begins.
**Access the client owes:** {open_line}

## Open questions

Nothing recorded yet. A question that survives the kickoff belongs here, with the date it was
asked and who owes the answer.
'''


def cmd_new(args):
    job = next((j for j in pipeline.load() if str(j.get('id')) == str(args.job_id)), None)
    if not job:
        abort(f'no job {args.job_id} in the pipeline.')
    if job.get('status') != 'won':
        abort(f'job {args.job_id} is "{job.get("status")}", not won. A client folder is for a '
              'started contract, not for a hope.')

    slug = slugify(args.slug or job.get('client_slug') or client_name(job))
    folder = CLIENTS / slug
    result = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'),
                             'record', str(args.job_id), '--file', '-'],
                            input=json.dumps({'client_slug': slug}), capture_output=True, text=True)
    if result.returncode:
        abort(result.stderr.strip())
    if folder.exists():
        # /onboarding runs a second time after delivery, so an existing folder is the normal
        # case then, not a collision. Opening it again would duplicate the client.
        print(f'clients/{slug} is already open. Nothing changed. '
              f'Pass --slug only when this really is a second engagement.')
        return 0

    for name in FOLDERS:
        (folder / name).mkdir(parents=True, exist_ok=True)
    (folder / 'context.md').write_text(context_text(job, slug), encoding='utf-8')

    brief = pipeline.jobs_dir() / str(args.job_id) / 'project.md'
    if brief.is_file():
        (folder / 'brief.md').write_text(brief.read_text(encoding='utf-8'), encoding='utf-8')
        copied = 'brief.md copied from the job folder'
    else:
        copied = 'no project.md yet: run /onboarding first, then copy the brief in'

    pipeline.main(['note', str(args.job_id), f'client workspace clients/{slug}'])
    print(f'clients/{slug} opened with context.md and {", ".join(FOLDERS)}. {copied}.')
    print('Fill the open lines in context.md from the proposal before the first delivery day.')
    return 0


def cmd_list(args):
    if not CLIENTS.is_dir():
        print('No clients yet. A won job opens the first one.')
        return 0
    rows = sorted(p for p in CLIENTS.iterdir() if p.is_dir())
    if not rows:
        print('No clients yet. A won job opens the first one.')
        return 0
    for folder in rows:
        context = folder / 'context.md'
        first = context.read_text(encoding='utf-8').splitlines()[0].lstrip('# ') if context.is_file() else 'no context.md'
        open_count = context.read_text(encoding='utf-8').count('_not recorded yet_') if context.is_file() else 0
        print(f'{folder.name}: {first} | {open_count} fact(s) still open')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('new', help='open a client folder for a won job')
    new.add_argument('job_id')
    new.add_argument('--slug', default='', help='folder name, defaults to the client name')
    new.set_defaults(func=cmd_new)
    sub.add_parser('list', help='every client and what is still open').set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
