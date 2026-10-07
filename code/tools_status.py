#!/usr/bin/env python3
"""What this machine can do, and what each part of it buys.

    python3 code/tools_status.py [--json]

`setup.sh` prints what is missing. That answers "what do I install" and leaves
the other question open: a member looking at a gap cannot tell whether it stops
them today, next week or never. This prints every tool with the same three
facts, present or not, so the answer is visible without installing anything.

One entry is not measurable from here. Whether the Upwork connector is logged in
is visible to Claude, which sees its tools, and to nobody else, so it is listed
with the state `ask-claude` and /about-me fills it in.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pitch_deploy  # noqa: E402


def env_with_files():
    env = dict(os.environ)
    pitch_deploy.load_dotenv(ROOT / '.env', env)
    pitch_deploy.load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
    return env


def has_key(env, *names):
    return any(str(env.get(name) or '').strip() for name in names)


def python_packages():
    """Both packages and the browser, because either one alone stops the run."""
    try:
        import PIL  # noqa: F401
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception:
        return False
    return True


def chrome(env):
    named = env.get('CHROME_BIN')
    if named and pathlib.Path(named).is_file():
        return True
    if shutil.which('google-chrome') or shutil.which('chromium'):
        return True
    return pathlib.Path('/Applications/Google Chrome.app').is_dir()


def vercel_signed_in():
    if not shutil.which('vercel'):
        return False
    done = subprocess.run(['vercel', 'whoami'], capture_output=True, text=True)
    return not done.returncode and bool(done.stdout.strip())


def rows(env):
    """Every tool, in the order a member meets it."""
    return [
        ('Upwork connector', 'ask-claude', 'required',
         'reads your profile and the job market',
         '/profile, /find-jobs, /brief', 'nothing replaces it, and only you can connect it'),
        ('Node.js', shutil.which('node') is not None, 'optional',
         'runs the cockpit and builds the report template',
         '/dashboard, /lead-magnet', 'install from nodejs.org, or work from the chat'),
        ('Python packages', python_packages(), 'optional',
         'opens a client page the way their customer sees it',
         '/lead-magnet, /proposal',
         "pip install -r requirements.txt, then playwright install chromium. The audit "
         "cannot start without them"),
        ('Google Chrome', chrome(env), 'optional',
         'screenshots a page before you send it',
         '/proposal, /sales-call-proposal', 'without it you check the page by eye'),
        ('Vercel', vercel_signed_in() or has_key(env, 'VERCEL_TOKEN'), 'required',
         'puts your pitch page and audit on a link a client can open',
         '/proposal, /lead-magnet',
         "npm i -g vercel, then vercel login. Without it you still get the cover letter "
         "and the bid, with no page to link, and /lead-magnet cannot publish an audit at all"),
        ('Firecrawl', has_key(env, 'FIRECRAWL_API_KEY'), 'optional',
         "reads the client's website",
         '/lead-magnet', 'firecrawl.dev. The audit cannot start without it'),
        ('Apify', has_key(env, 'APIFY_API_TOKEN', 'APIFY_TOKEN', 'APIFY_API_TOKEN_PAID'),
         'optional', 'reads their Google Business Profile',
         '/lead-magnet', 'apify.com. The audit cannot start without it'),
        ('DataForSEO', has_key(env, 'DATAFORSEO_LOGIN') and has_key(env, 'DATAFORSEO_PASSWORD'),
         'optional', 'reads where they rank and who outranks them',
         '/lead-magnet', 'dataforseo.com, one dollar of free credit, no card'),
        ('PageSpeed or Lighthouse', has_key(env, 'PAGESPEED_API_KEY') or
         shutil.which('lighthouse') is not None, 'optional',
         'measures how fast their page loads',
         '/lead-magnet', 'either one is enough, and Lighthouse is free and local'),
        ('OpenAI', has_key(env, 'OPENAI_API_KEY'), 'optional',
         'adds two chapters: whether AI search names them, and what their worst reviews say',
         '/lead-magnet', 'without it those two say "not measured" and the rest is unaffected'),
        ('kie.ai', has_key(env, 'KIE_AI_API_KEY'), 'optional',
         'draws the sketch on the proposal page',
         '/sales-call-proposal', 'without it the command prints the prompt for any image model you have'),
    ]


def state(value):
    if value == 'ask-claude':
        return 'ask-claude'
    return 'ready' if value else 'missing'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='machine-readable')
    args = parser.parse_args(argv)
    entries = [{'tool': name, 'state': state(ok), 'need': need, 'buys': buys,
                'used_by': used, 'without_it': without}
               for name, ok, need, buys, used, without in rows(env_with_files())]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    width = max(len(e['tool']) for e in entries)
    for e in entries:
        line = f"{e['state']:<10} {e['tool']:<{width}}  {e['buys']}  ({e['used_by']})"
        print(line if e['state'] == 'ready' else f"{line}\n{'':<10} {'':<{width}}  {e['without_it']}")
    missing = [e['tool'] for e in entries if e['state'] == 'missing']
    print(f"\n{len(entries) - len(missing) - 1} ready, {len(missing)} missing, "
          f"1 only Claude can see. Nothing here is required by /about-me.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
