#!/usr/bin/env bash
# Run once, right after cloning. Creates your working files, then tells you exactly what is
# missing for which command and how to get it.
#
# Why this exists: everything it creates is gitignored, so it is YOURS. When an update ships
# you run `git pull` and it lands cleanly, because your files and the repo's files never touch
# the same paths. Nothing here talks to Upwork, and nothing here blocks: a missing tool costs
# you one command, not the package.
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 is missing. Install Python 3, then run this again."; exit 1; }

python3 code/workspace.py

[ -f .env ] || { cp .env.example .env; echo "created .env from the example."; }

python3 - <<'PY'
import pathlib
import re
import secrets
import string
import sys
sys.path.insert(0, 'code')
from pitch_deploy import load_dotenv

path = pathlib.Path('.env')
env = {}
load_dotenv(path, env)
if not env.get('VERCEL_PITCH_PROJECT'):
    suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    lines = [line for line in path.read_text(encoding='utf-8').splitlines()
             if not re.match(r'^\s*VERCEL_PITCH_PROJECT\s*=', line)]
    lines.append(f'VERCEL_PITCH_PROJECT=upwork-pitches-{suffix}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY
echo "Vercel is required for /proposal and /lead-magnet; vercel login connects it, and the project is created on the first publish."

# The commands read .env first and ~/.config/credentials.env after it, so a key kept
# centrally is a key the run will find. Checking only .env reported gaps that were not
# there, and a member who trusts that list buys a second key they already own.
env_has() {
  python3 - "$1" <<'PY'
import os
import pathlib
import sys
sys.path.insert(0, 'code')
from pitch_deploy import load_dotenv

env = dict(os.environ)
load_dotenv(pathlib.Path('.env'), env)
load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
raise SystemExit(0 if str(env.get(sys.argv[1]) or '').strip() else 1)
PY
}
missing=0
note() { echo "  · $1"; missing=$((missing + 1)); }

if python3 -c 'import sys; sys.path.insert(0, "code"); import lead_magnet_render; raise SystemExit(0 if lead_magnet_render.needs_build() else 1)'; then
  if command -v npm >/dev/null; then
    echo "Building the audit report template, about a minute. I'd tell you a construction joke, but I'm still working on it."
    # set -e is on, so an unguarded npm failure used to exit here and swallow the
    # whole list below. A member then saw a stack trace and never learned which
    # keys or tools he still needs. The build is optional; the list is not.
    if (cd templates/lead-magnet && npm install --silent && npm run build --silent); then
      echo "built templates/lead-magnet/dist/index.html"
    else
      note "the audit report template did not build: /lead-magnet cannot render a report until it does. Run 'cd templates/lead-magnet && npm install && npm run build' and read npm's own error. Everything else below still applies."
    fi
  else
    note "Node.js is missing: /lead-magnet cannot render its report and /dashboard will not start. Install it from https://nodejs.org, then run this again."
  fi
fi

echo
echo "What each command still needs from you:"

command -v node >/dev/null || note "node: /dashboard needs it. https://nodejs.org"

# The first real run of /lead-magnet stopped here, not on a key: its fail-closed
# preflight wants a browser it can drive, and that is two installs, not one.
if ! python3 -c "import playwright, PIL" >/dev/null 2>&1; then
  note "Python packages: /lead-magnet needs them to read a page the way a customer sees it. Run 'python3 -m pip install -r requirements.txt'. If pip refuses because the system Python is managed, make a virtual environment first: 'python3 -m venv .venv && source .venv/bin/activate', then run setup.sh again."
elif ! python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p: p.chromium.launch().close()
" >/dev/null 2>&1; then
  note "the browser for those packages: run 'python3 -m playwright install chromium'. Without it /lead-magnet stops before its first paid call."
fi

if ! command -v google-chrome >/dev/null && ! command -v chromium >/dev/null \
   && [ ! -d "/Applications/Google Chrome.app" ] && ! env_has CHROME_BIN; then
  note "Google Chrome: /proposal checks the finished page on a phone screen with it, and /sales-call-proposal draws its sketch with it. Install it from google.com/chrome, or put the path in CHROME_BIN."
fi

if [ ! -d website/node_modules ] && command -v npm >/dev/null; then
  note "the cockpit installs its own packages on the first /dashboard run, which takes a few minutes once. Run 'cd website && npm install' now if you would rather wait for it here."
fi

if ! command -v vercel >/dev/null; then
  note "vercel: /proposal and /lead-magnet require it to publish. Install with 'npm i -g vercel', then 'vercel login'."
elif ! vercel whoami >/dev/null 2>&1 && ! env_has VERCEL_TOKEN; then
  note "vercel is installed but not signed in. Run 'vercel login', or put a VERCEL_TOKEN in .env."
fi

env_has FIRECRAWL_API_KEY || note "FIRECRAWL_API_KEY in .env: /lead-magnet reads the client's site with it. firecrawl.dev"
env_has APIFY_API_TOKEN || note "APIFY_API_TOKEN in .env: /lead-magnet reads the Google Business Profile with it. apify.com"
env_has DATAFORSEO_LOGIN || note "DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in .env: /lead-magnet reads rankings with them. dataforseo.com, one dollar of free credit, no card"
env_has PAGESPEED_API_KEY || command -v lighthouse >/dev/null || note "PAGESPEED_API_KEY in .env, or Lighthouse installed locally: /lead-magnet measures how fast the client's page loads with one of them. pagespeed is free from Google Cloud"
env_has KIE_AI_API_KEY || note "KIE_AI_API_KEY in .env: lets /sales-call-proposal draw the plan for the client's trade without leaving the terminal. kie.ai. Skip it if you already have an image model: /sales-call-proposal prints the prompt for you to paste anywhere, and the page picks the picture up from jobs/<id>/proposal-sketch.png whoever drew it."
env_has OPENAI_API_KEY || note "OPENAI_API_KEY in .env: /lead-magnet adds two chapters with it, whether AI search names the business and what its worst reviews complain about. Without it both say 'not measured' and the rest of the report is unaffected. platform.openai.com"

[ "$missing" -eq 0 ] && echo "  nothing is missing. This checks that a key exists, never that it still
  has credit, and never which account a token belongs to. Before the first run
  that spends money: 'python3 code/preflight.py lead-magnet'."

echo
echo "Your context, data and job files are yours now; git will not touch them."
echo
echo "Upwork is next. Open this folder in Claude Code (VS Code or terminal) and it walks you through connecting it."
echo "(I'd tell you a joke about the connector, but it takes a few tries to get through.)"
echo
echo "Then /about-me. It reads this same list and tells you which of it you need"
echo "now and which can wait, then asks about your background. After that: /profile"
