#!/usr/bin/env python3
"""A won job becomes a client, with delivery blueprints beside their facts.

    python3 code/client_workspace.py new <job id> [--slug <name>] [--blueprint seo|ads|cro|<github url>]...
    python3 code/client_workspace.py where <job id> [--slug <name>]
    python3 code/client_workspace.py check <job id>
    python3 code/client_workspace.py list

Client folders live outside this repository, in the Clients folder from context/me.md
or in the repository's sibling clients/ folder. Each has its own git repository:
CLAUDE.md holds the client facts, brief.md copies the handover, inputs/upwork/ keeps
sales files, and work/ and delivered/ hold delivery. Blueprint subfolders are separate
clones, excluded from the client's git repository. Reruns create missing pieces only.
"""
import argparse
import datetime
import io
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse

import pipeline

ROOT = pathlib.Path(__file__).resolve().parents[1]
FOLDERS = ('inputs/upwork', 'work', 'delivered')
BLUEPRINTS = {
    'seo': {'url': 'https://github.com/automatable-skool/seo-blueprint-day7',
            'next': '/context-layer'},
    'ads': {'url': 'https://github.com/automatable-skool/ads-blueprint-day7',
            'next': '/account-setup'},
    'cro': {'url': 'https://github.com/skool-automatable-month-2-83075/cro-blueprint',
            'next': '/audit check <site>'},
}
SALES_FILES = ('application.md', 'proposal.md', 'proposal.html', 'proposal.pdf', 'pitch.html',
               'thread.json', 'call-transcript.md', 'call-prep.md')
UNKNOWN = '_not recorded yet_'
RESERVED_BLUEPRINT_NAMES = frozenset(('.', '..', '.git', '.gitignore', '.client.json',
                                      '.client.json.tmp', 'inputs', 'work', 'delivered',
                                      'claude.md', 'brief.md'))


def valid_blueprint_name(name):
    stripped = name[:-4] if name.lower().endswith('.git') else name
    return (bool(re.fullmatch(r'[A-Za-z0-9_.-]+', name))
            and name.lower() not in RESERVED_BLUEPRINT_NAMES
            and bool(stripped) and stripped.lower() not in RESERVED_BLUEPRINT_NAMES)


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def outside_repo(path):
    return not path.resolve().is_relative_to(ROOT.resolve())


def clients_root():
    """Use the member's destination, resolving relative paths beside the Upwork repo."""
    try:
        text = (ROOT / 'context' / 'me.md').read_text(encoding='utf-8')
    except FileNotFoundError:
        text = ''
    match = re.search(r'^[ \t]*\*\*Clients folder:\*\*[ \t]*([^\n]*)', text, re.M)
    value = match.group(1).strip() if match else ''
    if value.lower() in ('', 'not answered yet', '_not answered yet_', UNKNOWN):
        value = 'clients'
    path = pathlib.Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT.parent / path
    path = path.resolve()
    if not outside_repo(path):
        abort(f'Clients folder {path} is inside the Upwork repository. Choose a folder outside it.')
    return path


def slugify(text):
    slug = re.sub(r'[^a-z0-9]+', '-', str(text or '').lower()).strip('-')
    return slug[:48].rstrip('-') or 'client'


def client_name(job):
    if job.get('contract_client'):
        return str(job['contract_client'])
    try:
        thread = json.loads((pipeline.jobs_dir() / str(job['id']) / 'thread.json').read_text(encoding='utf-8'))
        for message in thread.get('messages') or []:
            if message.get('from') == 'client' and message.get('name'):
                return str(message['name'])
    except (OSError, ValueError):
        pass
    client = job.get('client') or {}
    for key in ('company_name', 'name'):
        if client.get(key):
            return str(client[key])
    return str(job.get('title') or f'job-{job.get("id")}')


def get_job(job_id):
    job = next((j for j in pipeline.load() if str(j.get('id')) == str(job_id)), None)
    if not job:
        abort(f'no job {job_id} in the pipeline.')
    return job


def client_folder(job, slug=''):
    """The clients root, the slug and the folder: one rule for new, check and where."""
    slug = slugify(slug or job.get('client_slug') or client_name(job))
    root = clients_root()
    return root, slug, root / slug


def blueprint(value):
    """A typed choice must be a plain HTTPS GitHub repository link, never a command."""
    if value in BLUEPRINTS:
        return {'name': value, 'url': BLUEPRINTS[value]['url'], 'commit': ''}
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or parsed.netloc != 'github.com'
            or parsed.query or parsed.fragment):
        abort('a blueprint needs seo, ads, cro or an HTTPS GitHub repository link.')
    match = re.fullmatch(r'/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+)/?', parsed.path)
    if not match:
        abort('use the GitHub repository link, without a branch or a page path.')
    owner, name = match.groups()
    if not valid_blueprint_name(name):
        abort('that blueprint name is reserved for client files. Choose another repository.')
    name = name[:-4] if name.lower().endswith('.git') else name
    return {'name': name, 'url': f'https://github.com/{owner}/{name}', 'commit': ''}


def registry_blueprint(item):
    return item['name'] in BLUEPRINTS and item['url'] == BLUEPRINTS[item['name']]['url']


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or
                           f'{command[0]} failed with exit {result.returncode}.')
    return result.stdout.strip()


def git_repo(folder):
    if not (folder / '.git').exists():
        return False
    try:
        return pathlib.Path(run(['git', 'rev-parse', '--show-toplevel'], folder)).resolve() == folder.resolve()
    except (OSError, RuntimeError):
        return False


def ignored(folder, name):
    result = subprocess.run(['git', 'check-ignore', '--verbose', '--no-index', '--', f'{name}/'],
                            cwd=folder, capture_output=True, text=True)
    rule = result.stdout.partition('\t')[0]
    parts = rule.split(':', 2)
    return (result.returncode == 0 and len(parts) == 3 and parts[0] == '.gitignore'
            and not parts[2].startswith('!'))


def metadata(folder):
    path = folder / '.client.json'
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not isinstance(value.get('blueprints'), list):
        raise ValueError(f'{path} needs a client record with a blueprints list.')
    for item in value['blueprints']:
        if (not isinstance(item, dict) or not isinstance(item.get('url'), str)
                or not valid_blueprint_name(str(item.get('name') or ''))):
            raise ValueError(f'{path} has an invalid blueprint entry.')
    return value


def write_metadata(folder, value):
    text = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    path = folder / '.client.json'
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        # Replace atomically so an interrupted clone can still resume from its selection.
        temporary = folder / '.client.json.tmp'
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(path)


def sales_files(source):
    files = [source / name for name in SALES_FILES if (source / name).is_file()]
    if (source / 'call-prep').is_dir():
        files.extend(sorted(p for p in (source / 'call-prep').rglob('*') if p.is_file()))
    return files


def context_text(job, items, files):
    """Facts to complete from the agreed brief, with no invented delivery or access terms."""
    today = datetime.date.today().strftime('%d %B %Y')
    locations = '\n'.join(f'- `inputs/upwork/{name.as_posix()}`' for name in files)
    choices = []
    for item in items:
        next_step = (BLUEPRINTS[item['name']]['next'] if registry_blueprint(item)
                     else 'Follow this repository\'s README for setup; no scripts were run.')
        relative = './' + item['name'] if item['name'].startswith('-') else item['name']
        choices.append(f'- `{item["name"]}`: `cd {shlex.quote(relative)} && claude`. Next: {next_step}')
    text = f'''# {client_name(job)}
Recorded {today}.
**Next:** Complete the open facts from the handover brief before delivery.

## The business

**Name:** {client_name(job)}
**Website:** {UNKNOWN}
**What they do:** {UNKNOWN}
**Where they serve:** {UNKNOWN}

## What was sold

**Outcome:** {UNKNOWN}
**Deliverables:** {UNKNOWN}
**Not included:** {UNKNOWN}
**Price and milestones:** {UNKNOWN}
**Dates:** {UNKNOWN}

## How it runs

**Upwork channel:** {job.get('url') or UNKNOWN}
**Update rhythm:** {UNKNOWN}
**Approvals as agreed in the contract:** {UNKNOWN}

## Access the client owes

**Item, owner and status:** {UNKNOWN}
Record each promised access item separately. Pending access stays pending.

## Where things are

- `brief.md`: the handover brief copied from the job folder.
{locations}

## Blueprints here

{chr(10).join(choices) or 'No delivery blueprint selected.'}

Inside a blueprint, its own `context/` files and rules lead; these facts describe the
client and do not override them.
'''
    return text.replace('\u2014', '-')


def record_slug(job_id, slug):
    previous = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({'client_slug': slug}))
        return pipeline.main(['record', str(job_id), '--file', '-'])
    finally:
        sys.stdin = previous


def cmd_new(args):
    job = get_job(args.job_id)
    if job.get('status') != 'won':
        abort(f'job {args.job_id} is "{job.get("status")}", not won. A client folder needs a started contract.')
    root, slug, folder = client_folder(job, args.slug)
    if not outside_repo(folder) or folder.resolve().parent != root:
        abort(f'client folder {folder} resolves outside its clients root. Choose another --slug.')
    value = metadata(folder)
    if value and str(value.get('job_id')) != str(args.job_id):
        abort(f'{folder} belongs to another job. Choose a different --slug.')
    items = list(value['blueprints']) if value else []
    for choice in args.blueprint:
        item = blueprint(choice)
        existing = next((i for i in items if i['name'] == item['name']), None)
        if existing and existing['url'] != item['url']:
            abort(f'blueprint folder {item["name"]} already belongs to another repository.')
        if not existing:
            items.append(item)
    source = pipeline.jobs_dir() / str(args.job_id)
    files = sales_files(source)
    for name in FOLDERS:
        (folder / name).mkdir(parents=True, exist_ok=True)
    if not git_repo(folder):
        run(['git', 'init'], folder)
    ignore = folder / '.gitignore'
    if not ignore.exists():
        ignore.write_text('', encoding='utf-8')
    for item in items:
        line = f'/{item["name"]}/'
        if not ignored(folder, item['name']):
            with ignore.open('a', encoding='utf-8') as handle:
                handle.write(f'\n{line}\n')
    context = folder / 'CLAUDE.md'
    if not context.exists():
        context.write_text(context_text(job, items, [p.relative_to(source) for p in files]), encoding='utf-8')
    if (source / 'project.md').is_file() and not (folder / 'brief.md').exists():
        shutil.copy2(source / 'project.md', folder / 'brief.md')
    for path in files:
        target = folder / 'inputs' / 'upwork' / path.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    value = value or {'job_id': str(args.job_id), 'job_url': job.get('url') or '',
                      'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'blueprints': items}
    value['blueprints'] = items
    write_metadata(folder, value)
    try:
        for item in items:
            clone = folder / item['name']
            if clone.resolve().parent != folder.resolve():
                raise RuntimeError(f'{clone} resolves outside the client folder. Repair it before rerunning.')
            if not clone.exists():
                run(['git', 'clone', '--', item['url'], str(clone)], folder)
            if not git_repo(clone):
                raise RuntimeError(f'{clone} is not a blueprint clone. Preserve its files and repair it before rerunning.')
            if run(['git', 'remote', 'get-url', 'origin'], clone) != item['url']:
                raise RuntimeError(f'{clone} origin does not match {item["url"]}.')
            if not item.get('commit'):
                item['commit'] = run(['git', 'rev-parse', 'HEAD'], clone)
            if registry_blueprint(item) and not (clone / 'context' / 'business.md').is_file():
                run(['./setup.sh'], clone)
                if not (clone / 'context' / 'business.md').is_file():
                    raise RuntimeError(f'{clone}: setup did not create context/business.md. Rerun after fixing setup.')
    finally:
        # Finalize commits after attempts, retaining unfinished selections for a failure resume.
        write_metadata(folder, value)
    if record_slug(args.job_id, slug):
        return 1
    note = f'client workspace {folder}'
    if not any(entry.get('text') == note for entry in job.get('log', [])):
        if pipeline.main(['note', str(args.job_id), note]):
            return 1
    print(f'Client folder: {folder}')
    for item in items:
        next_step = (BLUEPRINTS[item['name']]['next'] if registry_blueprint(item)
                     else 'Read its README for setup; no scripts were run.')
        print(f'{item["name"]}: cd {shlex.quote(str(folder / item["name"]))} && claude. Next: {next_step}')
    if not (folder / 'brief.md').is_file():
        print('No project.md yet. Complete the handover brief, then rerun to copy it.')
    print('Complete the open facts in CLAUDE.md, then run the client folder check.')
    return 0


def cmd_where(args):
    """Print the destination before anything is created, or say whose it already is."""
    job = get_job(args.job_id)
    _, _, folder = client_folder(job, args.slug)
    value = metadata(folder)
    if value and str(value.get('job_id')) != str(args.job_id):
        print(f'TAKEN {folder} belongs to job {value.get("job_id")}. Choose a different --slug.')
        return 1
    print(folder)
    return 0


def open_count(text):
    return sum(UNKNOWN in line for line in text.splitlines())


def cmd_check(args):
    failed = False

    def report(ok, message):
        nonlocal failed
        failed = failed or not ok
        print(f'{"PASS" if ok else "FAIL"} {message}')

    try:
        root = clients_root()
    except SystemExit:
        report(False, 'clients root must be outside the Upwork repository')
        return 1
    report(True, f'clients root outside the Upwork repository: {root}')
    job = get_job(args.job_id)
    _, _, folder = client_folder(job)
    report(outside_repo(folder) and folder.resolve().parent == root, f'client folder stays in its external root: {folder}')
    report(git_repo(folder), f'client folder is a git repository: {folder}')
    for name in ('CLAUDE.md', 'brief.md'):
        report((folder / name).is_file(), f'{name} exists')
    try:
        value = metadata(folder)
        report(value is not None and str(value.get('job_id')) == str(args.job_id), '.client.json names this job')
    except (OSError, ValueError) as error:
        value = None
        report(False, f'.client.json: {error}')
    for item in (value or {}).get('blueprints', []):
        clone = folder / item['name']
        report(clone.resolve().parent == folder.resolve() and git_repo(clone),
               f'{item["name"]} is a blueprint clone')
        try:
            origin = run(['git', 'remote', 'get-url', 'origin'], clone)
        except (OSError, RuntimeError):
            origin = None
        report(origin == item['url'], f'{item["name"]} origin matches {item["url"]}')
        if registry_blueprint(item):
            report((clone / 'context' / 'business.md').is_file(), f'{item["name"]} context/business.md exists')
        report(ignored(folder, item['name']), f'.gitignore excludes {item["name"]}/')
    if (folder / 'CLAUDE.md').is_file():
        text = (folder / 'CLAUDE.md').read_text(encoding='utf-8')
        print(f'INFO {open_count(text)} fact(s) still open in CLAUDE.md')
    return int(failed)


def cmd_list(args):
    roots = ((clients_root(), ''), (ROOT / 'clients', ' (legacy)'))
    shown = False
    for root, label in roots:
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            context = folder / 'CLAUDE.md'
            if not context.is_file():
                context = folder / 'context.md'
            text = context.read_text(encoding='utf-8') if context.is_file() else ''
            first = next((line.lstrip('# ') for line in text.splitlines() if line.strip()), 'no client facts')
            print(f'{folder.name}{label}: {first} | {open_count(text)} fact(s) still open | {folder}')
            shown = True
    if not shown:
        print('No clients yet. A won job opens the first one.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('new', help='open a client folder for a won job')
    new.add_argument('job_id')
    new.add_argument('--slug', default='', help='folder name, defaults to the client name')
    new.add_argument('--blueprint', action='append', default=[], help='seo, ads, cro or a GitHub repository link; repeat to choose several')
    new.set_defaults(func=cmd_new)
    where = sub.add_parser('where', help='print the client folder new would use, writing nothing')
    where.add_argument('job_id')
    where.add_argument('--slug', default='', help='folder name, defaults to the client name')
    where.set_defaults(func=cmd_where)
    check = sub.add_parser('check', help='check the client folder and every blueprint')
    check.add_argument('job_id')
    check.set_defaults(func=cmd_check)
    sub.add_parser('list', help='every client and what is still open').set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
