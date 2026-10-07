#!/usr/bin/env python3
"""Does this repo work for a stranger who just cloned it? The release gate.

Mechanical checks only, the kind that surfaced as breaks on a real clone of the
repo this one grew out of:

    1. No personal data survived: names, domains, ids, machine paths
    2. Nothing shipped speaks German, not even an identifier
    3. No em-dashes in anything shipped
    4. Every path a command mentions exists, or is the member's own file
    5. Every `python3 code/X.py cmd` a command calls is a real subcommand
    6. Every starter lands on a gitignored path, so a member never commits it
    7. Every command has a description in its frontmatter

Exit 1 on any finding, so it gates a release rather than being read politely.

    python3 tools/check_repo.py [--quiet]
"""
import ast
import pathlib
import json
import os
import re
import subprocess
import sys
import contextlib
import shutil
import tempfile
import fnmatch

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / '.claude' / 'commands'
SELF = 'tools/check_repo.py'

# Traces of the machine this was built on. A hit means the separation missed something.
# The names themselves live in tools/leaks.txt, which does not ship: a gate that
# prints "remove this name" is the last place that name should be written down,
# and the person this package is handed to would read their own name in it.
def _private_patterns():
    listed = pathlib.Path(__file__).with_name('leaks.txt')
    if not listed.is_file():
        return []
    out = []
    for line in listed.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            # From the right: the pattern itself may contain alternations.
            pattern, _, label = line.rpartition('|')
            out.append((pattern.strip(), (label or 'private material').strip()))
    return out


LEAKS = _private_patterns() + [
    (r'~0[0-9a-f]{17}', 'an Upwork profile id'),
    (r'/Users/[a-z]+/', 'an absolute home directory'),
]

# German function words and orthography. A shipped line carrying one is text a
# member will read in the wrong language.
# The list started with the words a translator forgets and missed whole sentences that
# happened to avoid them: "Der Link geht auf die echte Ausschreibung" carries no umlaut
# and none of the originals. These are German function words that are not English words,
# so "die", "man", "was" and "war" stay out however German they look.
GERMAN = re.compile(
    r'[äöüßÄÖÜ]|\b(nicht|keine[rnms]?|kein|eine[rnms]?|und|oder|wird|werden|weil|damit|'
    r'sondern|statt|schon|noch|Datei|Ordner|Zeile|erledigt|fehlt|liegt|gibt|nichts|'
    r'etwas|dieser|diesem|diesen|deine[rnms]?|selbst|bereits|jeder|jede[nrms]?|'
    r'der|das|den|dem|des|ist|sind|auf|sich|wenn|dass|muss|soll|auch|aber|vor|'
    r'nach|ohne|durch|beim|vom|zum|zur|wurde|wurden|haben|hatte|seine|ihre|dann|'
    r'hier|dort|immer|wieder|zwischen|jedoch|deshalb|dabei|darauf|geht|steht)\b',
    re.IGNORECASE)
# Lowercase only, because MIT is a licence and a university while mit is a preposition.
GERMAN_CASED = re.compile(r'\bmit\b')
LANGUAGE_DATA_MARKER = '# multilingual-data'

# German identifiers survive a translation because no gate reads them. A member
# who opens the file to change one number should not have to guess at the words.
GERMAN_PARTS = {
    'abschnitt', 'anlauf', 'anzahl', 'auswahl', 'begriff', 'begriffe', 'bericht', 'branche',
    'ergebnis', 'fehler', 'inhalt', 'kopf', 'laden', 'pfad', 'quelle', 'seite', 'seiten',
    'titel', 'versuch', 'ziel',
    'branchen', 'datei', 'fehlend', 'fuellwort', 'fuellworte', 'gemessen', 'lauf',
    'laeufe', 'leer', 'mindestrest', 'mitte', 'ordner', 'ortsfrei', 'ortsfreier',
    'passwort', 'pruefe', 'pruefen', 'stichwort', 'suchbegriff', 'verlauf', 'wert',
    'werte', 'zeile',
}

# Files a member creates or a command writes at runtime. A command may point at
# them although a fresh clone does not have them yet.
MEMBER_PATHS = ('context/', 'data/', 'jobs/')


# The cockpit app's own source. Its texts reach the member like any command does.
COCKPIT = ('cockpit/**/*.ts', 'cockpit/**/*.tsx', 'cockpit/**/*.mjs', 'cockpit/**/*.css')
# A member edits these to change what a client reads, so they are shipped text too.
TEMPLATES = ('templates/**/*.tsx', 'templates/**/*.ts', 'templates/**/*.css', 'templates/**/*.html')


def glob_matches(parts, pattern):
    """Match each path segment so a single star never crosses a slash."""
    if not pattern:
        return not parts
    if pattern[0] == '**':
        return (glob_matches(parts, pattern[1:])
                or bool(parts) and glob_matches(parts[1:], pattern))
    return (bool(parts) and fnmatch.fnmatchcase(parts[0], pattern[0])
            and glob_matches(parts[1:], pattern[1:]))


def shipped(*globs):
    """Every tracked-or-trackable file matching the globs: what a stranger receives."""
    found = []
    private = {'context', 'data', 'jobs', 'clients', 'outputs'}
    for folder, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories
                          if name not in ('.git', 'node_modules', '__pycache__')
                          and not (pathlib.Path(folder) == ROOT and name in private)]
        for name in files:
            path = pathlib.Path(folder) / name
            rel = path.relative_to(ROOT).as_posix()
            if rel == 'profile.md':
                continue
            if any(glob_matches(rel.split('/'), g.split('/')) for g in globs):
                found.append(path)
    if not found:
        return []
    rels = [str(p.relative_to(ROOT)) for p in found]
    r = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT,
                       input='\n'.join(rels), capture_output=True, text=True)
    ignored = set(r.stdout.split('\n'))
    return [p for p, rel in zip(found, rels) if rel not in ignored and rel != SELF]


def lines_of(p):
    try:
        return p.read_text(encoding='utf-8').splitlines()
    except (UnicodeDecodeError, OSError):
        return []


def check_leaks():
    findings = []
    # No file is exempt. The vendored report shell used to be, for its German
    # comments, but no leak pattern was ever labelled German, so the exemption
    # matched nothing and would have raised on the first template file it reached.
    # Comments in another language are check_language's and the build's business.
    for p in shipped('**/*.md', '**/*.py', '**/*.html', '**/*.json', '**/*.js',
                     'templates/**/*.ts', 'templates/**/*.tsx', *COCKPIT):
        for i, line in enumerate(lines_of(p), 1):
            for pattern, what in LEAKS:
                m = re.search(pattern, line)
                if m:
                    findings.append(f'{p.relative_to(ROOT)}:{i} carries {what}: {m.group(0)}')
    return findings


# Strings and regex literals: a character class naming German letters is code that
# handles German, not a sentence written in it.
QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'|`[^`]*`|(?<![\w)])/(?![/*])(?:\\.|\[[^\]]*\]|[^/\n\\])+/[gimsuy]*')


def strip_data(line, state=None):
    """The code and the comments on this line, with every string literal blanked out.

    A scanner rather than a pattern: the report nests template literals inside template
    literals, writes German inside regex character classes, and puts apostrophes in its
    English comments. A regex reads none of that the way a reader does, and an apostrophe
    in prose used to flip the whole rest of the line into "inside a string".

    Comments are kept, because a German comment is exactly what this is looking for, but
    they are scanned as prose so their apostrophes open nothing. `state` carries an
    unterminated template literal or block comment into the next line.
    """
    out, quote, depth, escaped, prev = [], state, 0, False, ''
    comment = quote == '*'
    if comment:
        quote = None
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if comment:
            if ch == '*' and line[i + 1:i + 2] == '/':
                comment, i = False, i + 2
                continue
            out.append(ch)
            i += 1
            continue
        if escaped:
            escaped, i = False, i + 1
            continue
        if ch == '\\':
            escaped, i = True, i + 1
            continue
        if quote == '`':
            if prev == '$' and ch == '{':
                depth, quote, prev = depth + 1, None, ''
                out.append('0')
            elif ch == '`':
                quote = None
            else:
                prev = ch if ch == '$' else ''
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and line[i + 1:i + 2] == '/':
            out.append(line[i:])
            break
        if ch == '/' and line[i + 1:i + 2] == '*':
            comment, i = True, i + 2
            continue
        if ch in '"\'`':
            quote = ch
            out.append('0')     # a stand-in, so the next character sees a value here
            i += 1
            continue
        # A regex literal, whose German character classes are code that reads German. The
        # previous non-space character has to be one that can precede a regex: a self
        # closing JSX tag ends in " />", and reading that as a regex start swallowed the
        # rest of the line and flipped every string pairing after it.
        before = next((c for c in reversed(out) if not c.isspace()), '')
        if ch == '/' and before in '(,=:!&|?[{':
            quote = '/'
            out.append('0')
            i += 1
            continue
        if ch == '}' and depth:
            depth, quote = depth - 1, '`'
            i += 1
            continue
        out.append(ch)
        i += 1
    carry = '*' if comment else ('`' if quote == '`' or depth else None)
    return ''.join(out), carry


def check_language():
    """Nothing a stranger reads speaks German, and the templates are read too.

    The report a client gets is deliberately bilingual, so a file that declares itself
    multilingual keeps its locale table: a `key: "value"` line there is data. Everything
    else, and every comment, is a sentence the next owner has to be able to read.
    """
    findings = []
    for p in shipped('**/*.md', '**/*.py', *COCKPIT, *TEMPLATES):
        if 'node_modules' in str(p) or f'{os.sep}dist{os.sep}' in str(p):
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        multilingual = LANGUAGE_DATA_MARKER in text
        carried = None                      # a template literal left open by a line above
        for i, line in enumerate(lines_of(p), 1):
            code, carried = strip_data(line, carried)
            if not (GERMAN.search(line) or GERMAN_CASED.search(line)) or LANGUAGE_DATA_MARKER in line:
                continue
            # In a file that declares its locale tables, German inside a string is the
            # German report; German outside one is a sentence the next owner cannot read.
            if multilingual and not (GERMAN.search(code) or GERMAN_CASED.search(code)):
                continue
            findings.append(f'{p.relative_to(ROOT)}:{i} is German: "{line.strip()[:60]}"')
            break
    return findings


def check_identifiers():
    """Names a member reads while editing: functions, constants, arguments."""
    findings = []
    for p in shipped('code/*.py', 'tools/*.py'):
        try:
            tree = ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        named = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                named.add((n.name, n.lineno))
                named |= {(a.arg, n.lineno) for a in n.args.args + n.args.kwonlyargs}
            elif isinstance(n, ast.ClassDef):
                named.add((n.name, n.lineno))
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                named.add((n.id, n.lineno))
        for name, line in sorted(named, key=lambda x: x[1]):
            parts = re.split(r'_|(?<=[a-z])(?=[A-Z])', name.lower())
            german = sorted(set(parts) & GERMAN_PARTS)
            if german:
                findings.append(f'{p.relative_to(ROOT)}:{line} names something in German: '
                                f'{name} ({", ".join(german)})')
    return findings


def check_em_dashes():
    findings = []
    for p in shipped('**/*.md', '**/*.py', '**/*.html', *COCKPIT):
        hits = [i for i, line in enumerate(lines_of(p), 1) if '—' in line]
        if hits:
            more = f' (+{len(hits) - 1} more)' if len(hits) > 1 else ''
            findings.append(f'{p.relative_to(ROOT)}:{hits[0]} has an em-dash{more}')
    return findings


def check_report_shell():
    """The built report is the only file a client ever opens. Nothing of ours in it.

    Both stylesheets live in a template literal, so their comments are string content
    that no minifier removes. The built report shipped its engineering commentary to
    the client until `templates/lead-magnet/vite.config.ts` started stripping it, and
    this check is what keeps that plugin in place.
    """
    built = ROOT / 'templates' / 'lead-magnet' / 'dist' / 'index.html'
    if not built.is_file():
        return []
    page = built.read_text(encoding='utf-8', errors='replace')
    findings = []
    # `/*!` is a bundler's licence banner and `/*$vite$` its own marker. Everything
    # else in a comment came from us.
    ours = [m for m in re.findall(r'/\*.{0,80}', page, re.S)
            if not m.startswith(('/*!', '/*$'))]
    if ours:
        findings.append('the built report carries source comments, so the strip plugin in '
                        f'templates/lead-magnet/vite.config.ts is not running: {ours[0][:60]!r}')
    for pattern, what in LEAKS:
        m = re.search(pattern, page)
        if m:
            findings.append(f'the built report carries {what}: {m.group(0)}')
    return findings


def check_paths():
    findings = []
    pat = re.compile(r'`((?:context|data|jobs|code|references|starters|templates|tools)/[\w./-]+)`')
    for p in sorted(COMMANDS.glob('*.md')):
        for m in pat.finditer(p.read_text(encoding='utf-8')):
            rel = m.group(1)
            if rel.startswith(MEMBER_PATHS) or (ROOT / rel).exists():
                continue
            findings.append(f'{p.name}: points at {rel}, which does not exist')
    return findings


def check_subcommands():
    findings = []
    pat = re.compile(r'python3 (code/[\w_]+\.py) ([a-z][\w-]*)')
    seen = set()
    with script_copy() as (root, env):
        for p in sorted(COMMANDS.glob('*.md')) + [ROOT / 'CLAUDE.md']:
            for m in pat.finditer(p.read_text(encoding='utf-8')):
                script, cmd = m.groups()
                if (script, cmd) in seen:
                    continue
                seen.add((script, cmd))
                if not (root / script).is_file():
                    findings.append(f'{p.name}: calls {script}, which does not exist')
                    continue
                r = subprocess.run([sys.executable, str(root / script), cmd, '--help'],
                                   capture_output=True, text=True, cwd=root, env=env)
                if r.returncode and 'invalid choice' in r.stderr:
                    findings.append(f'{p.name}: calls `{script} {cmd}`, not a valid subcommand')
    return findings


def check_starters_ignored():
    """Both halves of the git-pull promise: the starter ships, its copy never does.

    The first half failed once: a bare `context/` ignore pattern also matched
    starters/context/, so the starters silently never shipped.
    """
    findings = []
    starters = ROOT / 'starters'

    def ignored(rel):
        return subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT).returncode == 0

    for p in sorted(x for x in starters.rglob('*') if x.is_file()):
        rel = str(p.relative_to(starters))
        if ignored(f'starters/{rel}'):
            findings.append(f'starters/{rel} is gitignored itself, so it never ships')
        if not ignored(rel):
            findings.append(f'starters/{rel} lands on {rel}, which is not gitignored: '
                            f'a member filling it in would publish it')
    return findings


def check_frontmatter():
    findings = []
    for p in sorted(COMMANDS.glob('*.md')):
        head = p.read_text(encoding='utf-8')[:800]
        if not head.startswith('---') or 'description:' not in head:
            findings.append(f'{p.name}: no description in its frontmatter')
    return findings


def check_call_count():
    """Every command closes with the call count, the member's only rate-limit evidence."""
    findings = []
    for p in sorted(COMMANDS.glob('*.md')):
        if 'Upwork calls:' not in p.read_text(encoding='utf-8'):
            findings.append(f'{p.name}: no "Upwork calls:" line for the report to end on')
    return findings


def check_self_contained():
    """The package carries its own instructions.

    A reference that reaches for a skill or a path on the builder's machine works
    for exactly one person, and nothing tells the next member why their run came
    out different. This used to be a test; the test folder is gone, the rule is not.
    """
    findings = []
    if (ROOT / '.claude' / 'skills').exists():
        findings.append('.claude/skills/ exists: the commands are the only entry points')
    for p in sorted((ROOT / 'references').glob('*.md')) + sorted(COMMANDS.glob('*.md')):
        for i, line in enumerate(lines_of(p), 1):
            for outside in ('~/.claude', 'write-as-', '.claude/skills'):
                if outside in line:
                    findings.append(f'{p.relative_to(ROOT)}:{i} depends on {outside}, which no member has')
    return findings


def check_command_set():
    """The eight commands of the path plus the one helper, and nothing else."""
    expected = {'about-me', 'brief', 'cockpit', 'find-jobs', 'lead-magnet',
                'pitch-page', 'profile', 'proposal', 'won'}
    found = {p.stem for p in COMMANDS.glob('*.md')}
    findings = [f'command missing: /{name}' for name in sorted(expected - found)]
    findings += [f'command not in the documented set: /{name}' for name in sorted(found - expected)]
    # Whoever writes for a member or a client reads the same copy rules, or four
    # commands drift into four voices.
    for name in ('pitch-page', 'profile', 'proposal', 'brief'):
        p = COMMANDS / f'{name}.md'
        if p.is_file() and 'references/copy.md' not in p.read_text(encoding='utf-8'):
            findings.append(f'{name}.md writes for a reader without reading references/copy.md')
    return findings


def check_facts_contract():
    """A reference that carries numbers carries the day they were read.

    This used to check a structured fact file. Nothing read that file, and every
    number in it also lived in prose, so the file is gone and the rule moved to
    where the numbers actually are. A reference with a figure in it and no date
    anywhere is folklore that looks like measurement.
    """
    dated = re.compile(r'\b(?:[12]?\d|3[01]) (?:January|February|March|April|May|June|July|'
                       r'August|September|October|November|December) 20\d\d\b')
    has_number = re.compile(r'(?<![\w.])\d{2,}(?![\w.])')
    findings = []
    for path in sorted((ROOT / 'references').glob('*.md')):
        text = path.read_text(encoding='utf-8')
        # A figure inside backticks is an example of what to write, not a claim
        # about the world: `37 Google reviews` shows a sentence shape.
        text = re.sub(r'`[^`]*`', '', text)
        if has_number.search(text) and not dated.search(text):
            findings.append(f'references/{path.name} states figures with no date '
                            'anywhere: that is folklore, not a measurement')
    return findings


def check_vision():
    findings = []
    vision = ROOT / 'VISION.md'
    if not vision.is_file():
        return ['VISION.md is missing']
    value = vision.read_text(encoding='utf-8')
    for phrase in ('complete local Upwork operating system', 'No gimmicks', 'Review contract'):
        if phrase not in value:
            findings.append(f'VISION.md is missing "{phrase}"')
    links = {
        'CLAUDE.md': 'VISION.md',
        'cockpit/PRINCIPLES.md': '../VISION.md',
    }
    for path, link in links.items():
        if link not in (ROOT / path).read_text(encoding='utf-8'):
            findings.append(f'{path} does not link to {link}')
    return findings


WRITING_BUDGET = 3050  # raised once, 28.09.2026, to pay for /won's onboarding step


def check_writing_budget():
    """The nine commands and the references share one line budget.

    Every session wants to add a sentence, and nothing ever wants to remove one, so a
    year of good intentions turns a command into a patchwork nobody reads to the end.
    A shared ceiling makes an addition cost a deletion, which is the only thing that
    forces a rule to be sharpened instead of duplicated. Raise it deliberately, in its
    own commit, or not at all.
    """
    files = sorted((ROOT / '.claude' / 'commands').glob('*.md')) + sorted((ROOT / 'references').glob('*.md'))
    counts = {path: len(path.read_text(encoding='utf-8').splitlines()) for path in files}
    total = sum(counts.values())
    if total <= WRITING_BUDGET:
        return []
    worst = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    names = ', '.join(f'{path.name} {n}' for path, n in worst)
    return [f'commands and references total {total} lines, over the budget of {WRITING_BUDGET} '
            f'(largest: {names}). Shorten something before adding more.']


def check_starter_fields():
    """Every field the code reads from me.md has to exist in the shipped empty.

    A field added to the code and not to the starter is the worst kind of missing: the
    member never sees a question, the command silently falls back to a constant, and the
    figure that decides his day is one nobody chose. Three fields had already drifted
    apart this way before this check existed.
    """
    starter = (ROOT / 'starters' / 'context' / 'me.md').read_text(encoding='utf-8')
    wanted = set()
    for path in sorted((ROOT / 'code').glob('*.py')):
        wanted.update(re.findall(r"me_number\(\s*['\"]([^'\"]+)['\"]", path.read_text(encoding='utf-8')))
    return [f'starters/context/me.md has no "**{name}:**", which code/ reads'
            for name in sorted(wanted) if f'**{name}:**' not in starter]


@contextlib.contextmanager
def script_copy():
    """Copy only shipped scripts and fixtures; never walk member directories."""
    with tempfile.TemporaryDirectory(prefix='blueprint-gate-') as temporary:
        root = pathlib.Path(temporary)
        shutil.copytree(ROOT / 'code', root / 'code',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'starters', root / 'starters')
        (root / 'tools').mkdir()
        shutil.copy2(ROOT / SELF, root / SELF)
        shutil.copytree(ROOT / 'tools' / 'fixtures', root / 'tools' / 'fixtures')
        shutil.copytree(ROOT / 'cockpit' / 'lib', root / 'cockpit' / 'lib')
        shutil.copytree(ROOT / 'templates' / 'proposal', root / 'templates' / 'proposal')
        shutil.copy2(ROOT / '.env.example', root / '.env.example')
        shutil.copy2(ROOT / 'setup.sh', root / 'setup.sh')
        env = {key: value for key, value in os.environ.items()
               if not key.startswith('BLUEPRINT_') and key not in ('PYTHONPATH', 'PYTHONHOME')}
        home = root / 'home'
        home.mkdir()
        (root / 'sitecustomize.py').write_text(
            'import socket\n'
            'def offline(*args, **kwargs):\n'
            '    raise RuntimeError("The release gate must not use the network.")\n'
            'socket.socket.connect = offline\n', encoding='utf-8')
        env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(root))
        yield root, env


def script_import(path):
    """Import by path under its ordinary module name, without running main()."""
    import importlib.util
    sys.path.insert(0, str(ROOT / 'code'))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def fixture_candidates():
    import datetime
    fixture = ROOT / 'tools' / 'fixtures' / 'jobs.json'
    rows = json.loads(fixture.read_text(encoding='utf-8'))
    for row in rows['jobs']:
        row['published_date'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fixture.write_text(json.dumps(rows), encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'code' / 'jobs.py'), 'candidates', str(fixture)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    candidates = json.loads((ROOT / 'data' / 'candidates.json').read_text(encoding='utf-8'))
    assert {row['id'] for row in candidates} == {'700001', '700002'}, result.stdout


def fixture_env():
    import pitch_deploy
    shutil.copy2(ROOT / '.env.example', ROOT / '.env')
    settings = pitch_deploy.deployment_config({'VERCEL_PITCH_PROJECT': 'upwork-pitches-fixture'})
    assert settings['project'] == 'upwork-pitches-fixture'
    assert settings['domain'] == ''
    fallback = pathlib.Path.home() / '.config' / 'credentials.env'
    fallback.parent.mkdir()
    fallback.write_text('VERCEL_PITCH_PROJECT=upwork-pitches-fallback\n'
                        'VERCEL_PITCH_DOMAIN=upwork-pitches-fallback.vercel.app\n'
                        'VERCEL_TOKEN=fixture-token\nVERCEL_SCOPE=fixture-scope\n', encoding='utf-8')
    (ROOT / '.env').write_text('VERCEL_PITCH_PROJECT="   "\nVERCEL_PITCH_DOMAIN=   \n', encoding='utf-8')
    settings = pitch_deploy.deployment_config({})
    assert settings['project'] == 'upwork-pitches-fallback'
    assert settings['domain'] == 'upwork-pitches-fallback.vercel.app'
    exported = {'VERCEL_PITCH_PROJECT': 'upwork-pitches-exported',
                'VERCEL_PITCH_DOMAIN': 'upwork-pitches-exported.vercel.app'}
    settings = pitch_deploy.deployment_config(exported)
    assert settings['project'] == exported['VERCEL_PITCH_PROJECT']
    assert settings['domain'] == exported['VERCEL_PITCH_DOMAIN']
    settings = pitch_deploy.deployment_config({'VERCEL_TOKEN': '   ', 'VERCEL_SCOPE': ''})
    assert settings['token'] == 'fixture-token'
    assert settings['scope'] == 'fixture-scope'


def fixture_onboarding():
    """The starter and saved search format must pass their own readers."""
    import context_check
    import jobs
    starter = (ROOT / 'starters' / 'context' / 'me.md').read_text(encoding='utf-8')
    filled = starter.replace('not answered yet', 'Fixture answer')
    filled = re.sub(r'(?ms)(^## Your background\s*\n).*?(?=^## )',
                    r'\1\n2019-2024: Built websites for local businesses.\n\n', filled)
    blocks = {
        'Results': '**Website conversion**\n- Result: Increased inquiries by 30%.\n'
                   '- Where it can be checked: Fixture client report.\n'
                   '- Date: 2025-01-10\n- Status: verified',
        'Reviews': '**Website client review**\n- Words: Clear work and handover.\n'
                   '- Rating: 5/5\n- Source: https://www.upwork.com/fixture-review\n'
                   '- Status: verified',
        'Credentials': '**Tool certification**\n- Certificate: Fixture platform, 2024.\n'
                       '- Where it can be checked: Fixture credential register.\n'
                       '- Status: verified',
    }
    for section, body in blocks.items():
        filled = re.sub(rf'(?ms)(^## {section}\s*\n).*?(?=^## |\Z)',
                        lambda match: match.group(1) + '\n' + body + '\n\n', filled)
    me = ROOT / 'context' / 'me.md'
    me.parent.mkdir()
    me.write_text(filled, encoding='utf-8')
    assert context_check.check_me(filled) == []
    assert context_check.check_proof(context_check.proof_only(filled)) == []
    assert context_check.status(filled) == ('complete', len(context_check.REQUIRED), 3, 0)
    command = [sys.executable, str(ROOT / 'code' / 'context_check.py')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout or result.stderr
    incomplete = re.sub(r'(?m)^(\*\*Tools and systems you can name confidently:\*\*).*$',
                        r'\1', filled)
    me.write_text(incomplete, encoding='utf-8')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 1 and 'Tools and systems' in result.stdout, result.stdout
    assert context_check.status(incomplete)[0] == 'partial'
    me.write_text('## Job search tracks\n\n'
                  '- Websites: WordPress · Webflow (keep, reviewed 2026-10-05)\n\n'
                  'Review: keep these terms.\n', encoding='utf-8')
    themes = jobs.member_search_themes()
    assert len(themes) == 1 and themes[0]['terms'] == ['WordPress', 'Webflow'], themes
    assert themes[0]['query'] == 'WordPress, Webflow', themes


def fixture_setup():
    import pitch_deploy
    source = (ROOT / 'setup.sh').read_text(encoding='utf-8')
    script = source.split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    for value in ('', '"   "', "'   '"):
        shutil.copy2(ROOT / '.env.example', ROOT / '.env')
        with (ROOT / '.env').open('a', encoding='utf-8') as handle:
            handle.write(f'\nVERCEL_PITCH_PROJECT={value}\n')
        subprocess.run([sys.executable, '-c', script], cwd=ROOT, check=True)
        settings = {}
        pitch_deploy.load_dotenv(ROOT / '.env', settings)
        assert re.fullmatch(r'upwork-pitches-[a-z0-9]{6}', settings['VERCEL_PITCH_PROJECT'])
        first = (ROOT / '.env').read_bytes()
        subprocess.run([sys.executable, '-c', script], cwd=ROOT, check=True)
        assert (ROOT / '.env').read_bytes() == first
    (ROOT / '.env').write_text('VERCEL_PITCH_PROJECT=existing-member-project\n', encoding='utf-8')
    subprocess.run([sys.executable, '-c', script], cwd=ROOT, check=True)
    assert (ROOT / '.env').read_text(encoding='utf-8') == 'VERCEL_PITCH_PROJECT=existing-member-project\n'


def fixture_publish():
    import pitch_deploy
    from types import SimpleNamespace
    from unittest.mock import patch
    fixtures = ROOT / 'tools' / 'fixtures'
    stdout = (fixtures / 'vercel-deploy.txt').read_text(encoding='utf-8')
    assert pitch_deploy.production_host(stdout) == 'upwork-pitches-fixture-a1b2c3.vercel.app'
    assert pitch_deploy.production_host('https://example.com') == ''
    config = pitch_deploy.deployment_config({'VERCEL_PITCH_PROJECT': 'upwork-pitches-fixture'})
    deployment = SimpleNamespace(stdout=stdout)
    # The shape Vercel CLI 50.1.6 returned on a live deploy on 5 October 2026: the
    # short project alias is public, the longer team alias sits behind Vercel login.
    inspected = SimpleNamespace(returncode=0, stdout=json.dumps({'aliases': [
        'upwork-pitches-fixture-team-projects.vercel.app', 'upwork-pitches-fixture.vercel.app']}))
    with patch.object(pitch_deploy.subprocess, 'run', return_value=inspected) as runner:
        assert pitch_deploy.resolve_host('vercel', config, deployment) == 'upwork-pitches-fixture.vercel.app'
        assert runner.call_args.args[0][1:4] == ['inspect', stdout.strip(), '--json']
    legacy = SimpleNamespace(returncode=0, stdout=json.dumps({'alias': ['member-stable.vercel.app']}))
    with patch.object(pitch_deploy.subprocess, 'run', return_value=legacy):
        assert pitch_deploy.resolve_host('vercel', config, deployment) == 'member-stable.vercel.app'
    # Resolving keeps nothing; only a host that just opened publicly is saved.
    assert pitch_deploy.deployment_config({'VERCEL_PITCH_PROJECT': config['project']})['domain'] == ''
    pitch_deploy.save_host('member-stable.vercel.app', config)
    assert pitch_deploy.deployment_config({'VERCEL_PITCH_PROJECT': config['project']})['domain'] == 'member-stable.vercel.app'
    for inspected in (SimpleNamespace(returncode=0, stdout='{bad json'),
                      SimpleNamespace(returncode=1, stdout=''),
                      SimpleNamespace(returncode=0, stdout=json.dumps({'alias': ['untrusted.example.com']}))):
        with patch.object(pitch_deploy.subprocess, 'run', return_value=inspected):
            assert pitch_deploy.resolve_host('vercel', config, deployment) == pitch_deploy.production_host(stdout)
    with patch.object(pitch_deploy.subprocess, 'run') as runner:
        try:
            pitch_deploy.resolve_host('vercel', config, SimpleNamespace(stdout='https://example.com'))
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError('An unknown public address must stop publishing.')
        runner.assert_not_called()
    for source in (ROOT / 'code').glob('*.py'):
        assert not re.search(r'\{[^}]*project[^}]*\}\.vercel\.app', source.read_text(encoding='utf-8')), source.name
    output = ROOT / 'site'
    pitch_deploy.write_site(output, [('700001', fixtures / 'client-page.html')], '700001')
    root_page = (output / 'index.html').read_text(encoding='utf-8')
    for private in ('Fixture Company', 'Fixture client job', 'Score: 72', 'Fixture Member'):
        assert private not in root_page, private
    assert (output / '700001' / 'index.html').read_bytes() == (fixtures / 'client-page.html').read_bytes()


def fixture_retention():
    import datetime
    import pipeline
    now = datetime.datetime.now(datetime.timezone.utc)
    old = (now - datetime.timedelta(hours=48)).isoformat()
    records = []
    for index in range(6):
        row = {'id': str(710001 + index), 'title': 'Fixture lead', 'status': 'new',
               'found_at': old, 'status_updated_at': old, 'found_via': ['query-fixture'],
               'notes': 'not a fit: Fixture skip reason.'}
        row.update({field: {'fixture': 'cached'} if field in ('client', 'details') else 'cached'
                    for field in pipeline.CACHED_FIELDS})
        records.append(row)
    records[0]['pitch_url'] = 'https://upwork-pitches-fixture.vercel.app/710001'
    records[1]['lead_magnet_url'] = 'https://upwork-pitches-fixture.vercel.app/710002-audit'
    records[3]['status'] = 'skipped'
    records[4]['found_at'] = now.isoformat()
    application = ROOT / 'jobs' / records[2]['id'] / 'application.md'
    application.parent.mkdir(parents=True)
    application.write_text('Fixture application', encoding='utf-8')
    data = ROOT / 'data'
    data.mkdir()
    jobs = data / 'jobs.json'
    jobs.write_text(json.dumps(records), encoding='utf-8')
    contracts = data / 'contracts.json'
    contracts.write_text('[{"client": "Fixture client"}]', encoding='utf-8')
    expired = now.timestamp() - 48 * 3600
    os.utime(contracts, (expired, expired))
    command = [sys.executable, str(ROOT / 'code' / 'pipeline.py')]
    subprocess.run(command + ['reset-search', '--with-skipped'], cwd=ROOT,
                   capture_output=True, text=True, check=True)
    saved = json.loads(jobs.read_text(encoding='utf-8'))
    assert {row['id'] for row in saved} == {row['id'] for row in records[:-1]}
    archives = list((data / 'search-resets').glob('*/jobs.json'))
    assert len(archives) == 1
    archived = json.loads(archives[0].read_text(encoding='utf-8'))
    assert [row['id'] for row in archived] == [records[-1]['id']]
    assert archived[0]['skip_reason'] == 'Fixture skip reason'
    allowed = {'id', 'title', 'status', 'skip_reason'}
    for row in archived:
        assert not set(row) & set(pipeline.CACHED_FIELDS), row
        assert all(key in allowed or key.endswith(('_at', '_date')) for key in row), row
    subprocess.run(command + ['prune'], cwd=ROOT, capture_output=True, text=True, check=True)
    assert {row['id'] for row in json.loads(jobs.read_text(encoding='utf-8'))} == {row['id'] for row in saved}
    assert application.read_text(encoding='utf-8') == 'Fixture application'
    pruned = json.loads(jobs.read_text(encoding='utf-8'))
    assert pruned[0]['pitch_url'] == records[0]['pitch_url']
    assert pruned[1]['lead_magnet_url'] == records[1]['lead_magnet_url']
    for row in pruned[:-1]:
        assert not set(row) & set(pipeline.CACHED_FIELDS), row
    assert not contracts.exists()
    contracts.write_text('[]', encoding='utf-8')
    subprocess.run(command + ['prune'], cwd=ROOT, capture_output=True, text=True, check=True)
    assert contracts.exists()
    overflow = records[:-1] + [dict(records[-1], id=str(720001 + index))
                               for index in range(pipeline.KEEP + 1)]
    trimmed, removed = pipeline.trim(overflow)
    assert {row['id'] for row in records[:-1]} <= {row['id'] for row in trimmed}
    assert len(trimmed) == pipeline.KEEP and removed == len(overflow) - pipeline.KEEP


def fixture_pipeline():
    """The application-to-won contract, entirely on this worker's throwaway copy."""
    import datetime
    import io
    import pipeline
    import cockpit
    import sync as sync_io
    from types import SimpleNamespace
    from unittest.mock import patch
    now = datetime.datetime.now(datetime.timezone.utc)
    old = (now - datetime.timedelta(days=20)).isoformat()
    reviewed = (now - datetime.timedelta(days=2)).isoformat()
    sent = (now - datetime.timedelta(days=1)).isoformat()
    command = [sys.executable, str(ROOT / 'code' / 'pipeline.py')]
    analytics_rows = [{'status': stage, 'found_at': reviewed}
                      for stage in ('applied', 'replied', 'call', 'offer')]
    analytics_rows += [{'status': 'lost', 'found_at': reviewed,
                        'history': [{'status': 'applied', 'at': sent}] * 2},
                       {'status': 'won', 'found_at': reviewed, 'imported': True}]
    assert cockpit.funnel(analytics_rows)['applied'] == 5
    assert sum(week['count'] for week in cockpit.outreach(analytics_rows)) == 5

    def run(arguments, value=None, success=True, script='pipeline.py'):
        call = command if script == 'pipeline.py' else [sys.executable, str(ROOT / 'code' / script)]
        result = subprocess.run(call + arguments, input=json.dumps(value) if value is not None else None,
                                cwd=ROOT, capture_output=True, text=True)
        assert (result.returncode == 0) == success, result.stderr or result.stdout
        return result

    def apply_in_process(snapshot, no_writes=False):
        calls = []

        def run_local(*arguments, stdin=None):
            calls.append(arguments)
            with patch.object(sys, 'stdin', io.StringIO(stdin or '')):
                return pipeline.main(list(arguments)) == 0

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sync_io, 'run_pipeline', side_effect=run_local))
            stack.enter_context(patch.object(sys, 'stdin', io.StringIO(json.dumps(snapshot))))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if no_writes:
                stack.enter_context(patch.object(pipeline, 'save', side_effect=AssertionError(
                    'Replaying a snapshot must not write the pipeline.')))
            sync_io.cmd_apply(SimpleNamespace(file='-'))
        return calls

    rows = [
        {'id': '730001', 'title': 'Fixture call', 'status': 'call', 'found_at': old,
         'call_at': '2030-01-01', 'next_follow_up': '2030-01-02'},
        {'id': '730002', 'title': 'Fixture offer', 'status': 'offer', 'found_at': old},
        {'id': '730003', 'title': 'Fixture sequence', 'status': 'replied', 'found_at': old,
         'follow_up_plan': {'lane': 'reactivation', 'step': 2, 'max_steps': 2,
                            'reviewed_at': reviewed, 'reason': 'Fixture close'},
         'next_follow_up': sent[:10]},
        {'id': '730006', 'title': 'Fixture first reply', 'status': 'applied', 'found_at': old},
    ]
    run(['add', '--file', '-'], rows)
    before = pipeline.find(pipeline.load(), '730001')
    assert '--force' in run(['set', '730001', 'replied'], success=False).stderr
    assert pipeline.find(pipeline.load(), '730001') == before
    run(['acted', '730001', '--note', 'Fixture activity'])
    acted = pipeline.find(pipeline.load(), '730001')
    assert acted['last_activity_at'] > before['last_activity_at']
    assert acted['notes'] == 'Fixture activity'
    assert {k: v for k, v in acted.items() if k not in ('last_activity_at', 'notes')} == {
        k: v for k, v in before.items() if k not in ('last_activity_at', 'notes')}
    run(['set', '730001', 'replied', '--force'])
    assert pipeline.find(pipeline.load(), '730001')['status'] == 'replied'
    run(['record', '730001', '--file', '-'], {'follow_up_source': 'waiting'})
    run(['set', '730001', 'replied', '--follow-up', '2030-01-02'])
    assert 'follow_up_source' not in pipeline.find(pipeline.load(), '730001')

    snapshot = {
        'offers': [{'job_id': '730002', 'state': 'expired'}],
        'contracts': [{'contract_id': 'contract-fixture', 'title': 'Fixture repeat project',
                       'status': 'ACTIVE', 'client_name': 'Fixture Repeat Client'}],
        'proposals': [{'job_id': '730004', 'proposal_id': 'proposal-fixture', 'room_id': 'room-fixture',
                       'title': 'Fixture historical hire', 'status': 'hired', 'applied_at': now.isoformat()}],
        'threads': [{'job_id': '730003', 'room_id': 'sequence-room', 'awaiting_reply_from': 'them',
                     'messages': [{'from': 'me', 'name': 'Fixture Member', 'at': sent, 'text': 'Closing the loop.'}]},
                    {'job_id': '730006', 'room_id': 'reply-room', 'awaiting_reply_from': 'you',
                     'messages_complete': True,
                     'messages': [{'from': 'client', 'name': 'Fixture Client', 'at': sent, 'text': 'Can we talk?'}]},
                    {'job_id': '730001', 'room_id': 'manual-room', 'awaiting_reply_from': 'them', 'messages': []}],
    }
    run(['apply', '--file', '-'], snapshot, script='sync.py')
    saved = pipeline.load()
    assert pipeline.find(saved, '730002')['status'] == 'lost'
    complete = pipeline.find(saved, '730003')
    assert not complete.get('follow_up_plan') and not complete.get('next_follow_up')
    assert len(complete['follow_up_history']) == 1 and complete['follow_up_history'][0]['completed']
    assert complete['last_activity_at'] == sent
    first_reply = pipeline.find(saved, '730006')
    assert first_reply['status'] == 'replied' and first_reply['last_activity_at'] == sent
    assert first_reply['history'][-1]['at'] > first_reply['last_activity_at']
    assert first_reply['follow_up_source'] == 'waiting'
    assert first_reply['next_follow_up'] == now.date().isoformat()
    assert pipeline.find(saved, '730001')['next_follow_up'] == '2030-01-02'
    imported = next(row for row in saved if row.get('contract_id') == 'contract-fixture')
    assert imported['status'] == 'won' and imported['imported'] is True
    hired = pipeline.find(saved, '730004')
    assert hired['proposal_id'] == 'proposal-fixture' and hired['room_id'] == 'room-fixture'
    assert hired['imported'] is True
    assert all(value == 0 for value in cockpit.funnel([hired, imported]).values())
    assert all(week['count'] == 0 for week in cockpit.outreach([hired, imported]))
    assert pipeline.applied_on([hired], now.date().isoformat()) == 0
    calls = apply_in_process(snapshot, no_writes=True)
    assert len(pipeline.load()) == len(saved)
    assert pipeline.find(pipeline.load(), '730003') == complete
    assert not any(call[0] in ('acted', 'follow-up') for call in calls), calls
    no_waiting = {'threads': [dict(snapshot['threads'][1], awaiting_reply_from='them')]}
    run(['apply', '--file', '-'], no_waiting, script='sync.py')
    no_longer_waiting = pipeline.find(pipeline.load(), '730006')
    assert no_longer_waiting['next_follow_up'] is None and 'follow_up_source' not in no_longer_waiting
    apply_in_process(no_waiting, no_writes=True)
    later_contract = dict(snapshot['contracts'][0], job_id='740001')
    run(['apply', '--file', '-'], {'contracts': [later_contract]}, script='sync.py')
    assert len(pipeline.load()) == len(saved)
    assert next(row for row in pipeline.load() if row.get('contract_id') == 'contract-fixture')['id'] == imported['id']
    active_import = {'proposals': [{'job_id': '730007', 'title': 'Fixture imported conversation', 'status': 'accepted'}],
                     'threads': [{'job_id': '730007', 'room_id': 'import-room', 'awaiting_reply_from': 'them',
                                  'messages': [{'from': 'client', 'at': sent, 'text': 'Fixture answer'}]}]}
    run(['apply', '--file', '-'], active_import, script='sync.py')
    assert pipeline.find(pipeline.load(), '730007')['last_activity_at'] == sent
    run(['add', '--file', '-'], {'id': '730008', 'title': 'Fixture message window', 'status': 'replied', 'found_at': old})
    history = [{'from': 'me', 'at': (now - datetime.timedelta(days=21, minutes=index)).isoformat(),
                'text': 'Already recorded.'} for index in range(20)]
    history += [{'from': 'client', 'at': reviewed, 'text': 'New question.'},
                {'from': 'me', 'at': sent, 'text': 'New answer.'}]
    activity_snapshot = {'threads': [{'job_id': '730008', 'room_id': 'activity-room',
                                     'awaiting_reply_from': 'them', 'messages': history}]}
    calls = apply_in_process(activity_snapshot)
    assert sum(call[0] == 'acted' for call in calls) == 1, calls
    assert pipeline.find(pipeline.load(), '730008')['last_activity_at'] == sent
    assert not apply_in_process(activity_snapshot, no_writes=True)
    for action in ('plan', 'sent', 'clear'):
        run(['record', '730008', '--file', '-'], {'follow_up_source': 'waiting'})
        arguments = ['follow-up', '730008', action]
        if action == 'plan':
            arguments += ['--lane', 'active', '--due', '2030-01-02', '--reason', 'Fixture sequence']
        run(arguments)
        assert 'follow_up_source' not in pipeline.find(pipeline.load(), '730008')
    unknown = run(['apply', '--file', '-'], {'offers': [{'job_id': '730002', 'state': 'unknown-fixture'}]}, script='sync.py')
    assert 'unknown offers status' in unknown.stderr
    run(['prune'])
    retained = pipeline.find(pipeline.load(), '730004')
    assert retained['proposal_id'] == hired['proposal_id'] and retained['room_id'] == hired['room_id']
    run(['new', imported['id']], script='client_workspace.py')
    assert pipeline.find(pipeline.load(), imported['id'])['client_slug'] == 'fixture-repeat-client'
    run(['new', imported['id']], script='client_workspace.py')
    assert len(list((ROOT / 'clients').iterdir())) == 1
    run(['record', imported['id'], '--file', '-'], {'result_recorded_at': reviewed})
    run(['record', imported['id'], '--file', '-'], {'result_recorded_at': sent})
    assert pipeline.find(pipeline.load(), imported['id'])['result_recorded_at'] == reviewed

    with patch.dict(os.environ, {}, clear=True):
        (ROOT / '.env').unlink(missing_ok=True)
        assert pipeline.chat_keep_hours() == 2160
        for raw, expected in [('24 # strict', 24), ('"24"', 24), ('0', 0), ('invalid', 24)]:
            (ROOT / '.env').write_text(f'KEEP_CHAT_HOURS={raw}\n', encoding='utf-8')
            assert pipeline.chat_keep_hours() == expected
        with patch.dict(os.environ, {'KEEP_CHAT_HOURS': '"0" # strict'}):
            assert pipeline.chat_keep_hours() == 0

    proposal = {'member': 'Fixture Freelancer', 'client': 'Fixture Client', 'headline': 'Fixture plan',
                'problem': 'Fixture problem', 'cost': {'text': 'Fixture cost', 'note': 'Fixture split'}}
    run(['730001', '--file', '-'], proposal, script='proposal_generate.py')
    page = (ROOT / 'jobs' / '730001' / 'proposal.html').read_text(encoding='utf-8')
    assert '{{' not in page and 'class="missing"' in page and '<a class="video"' not in page
    assert 'member' not in page.lower() and 'class="cta"' not in page
    assert 'href=""' not in page and 'href="#"' not in page and '<small>Fixture split</small>' in page
    run(['730001', '--file', '-'], dict(proposal, video={'href': 'https://www.loom.com/share/x', 'length': '1:10'},
                                        cta_href='https://www.upwork.com'), script='proposal_generate.py')
    page = (ROOT / 'jobs' / '730001' / 'proposal.html').read_text(encoding='utf-8')
    assert 'href="https://www.loom.com/share/x"' in page and 'href="https://www.upwork.com"' in page
    run(['730001', '--file', '-'], dict(proposal, video={'href': 'loom.com/x'}), success=False, script='proposal_generate.py')
    run(['730001', '--file', '-'], dict(proposal, next_steps=['a', 'b', 'c', 'd']), success=False, script='proposal_generate.py')
    run(['730001', '--file', '-'], dict(proposal, cta_href='#'), success=False, script='proposal_generate.py')
    node = subprocess.run(['node', str(ROOT / 'tools' / 'fixtures' / 'pipeline.mjs')],
                          input=json.dumps({'before': before, 'acted': acted, 'complete': complete, 'hired': hired}),
                          cwd=ROOT, capture_output=True, text=True)
    assert node.returncode == 0, node.stderr or node.stdout


def script_worker(name, path=None):
    import socket
    def offline(*args, **kwargs):
        raise RuntimeError('The release gate must not use the network.')
    socket.socket.connect = offline
    sys.path.insert(0, str(ROOT / 'code'))
    if name == 'import':
        script_import(pathlib.Path(path))
    else:
        {'candidates': fixture_candidates, 'env': fixture_env, 'onboarding': fixture_onboarding, 'setup': fixture_setup,
         'publish': fixture_publish, 'retention': fixture_retention, 'pipeline': fixture_pipeline}[name]()


def check_scripts_run():
    findings = []
    tasks = [('import', path.name) for path in sorted((ROOT / 'code').glob('*.py'))]
    tasks += [(name, None) for name in ('candidates', 'env', 'onboarding', 'setup', 'publish', 'retention', 'pipeline')]
    for name, filename in tasks:
        with script_copy() as (root, env):
            command = [sys.executable, str(root / SELF), '--script-check', name]
            if filename:
                command.append(str(root / 'code' / filename))
            try:
                result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                        text=True, timeout=30)
            except subprocess.TimeoutExpired:
                findings.append(f'{filename or name}: script check timed out after 30 seconds')
                continue
            if result.returncode:
                findings.append(f'{filename or name}: script check failed:\n'
                                f'{(result.stderr or result.stdout).strip()}')
    return findings


CHECKS = [
    ('personal data', check_leaks),
    ('language', check_language),
    ('identifiers', check_identifiers),
    ('em-dashes', check_em_dashes),
    ('built report', check_report_shell),
    ('command paths', check_paths),
    ('script subcommands', check_subcommands),
    ('starters gitignored', check_starters_ignored),
    ('command frontmatter', check_frontmatter),
    ('call count line', check_call_count),
    ('self-contained', check_self_contained),
    ('command set', check_command_set),
    ('fact contract', check_facts_contract),
    ('product vision', check_vision),
    ('writing budget', check_writing_budget),
    ('starter fields', check_starter_fields),
    ('scripts run', check_scripts_run),
]


def main():
    quiet = '--quiet' in sys.argv
    total = 0
    for label, fn in CHECKS:
        found = fn()
        total += len(found)
        if found:
            print(f'\n{label}:')
            for f in found:
                print(f'  {f}')
        elif not quiet:
            print(f'ok  {label}')
    if not (pathlib.Path(__file__).with_name('leaks.txt')).is_file() and not quiet:
        # The list of private names cannot travel, so on anybody else's machine this gate
        # runs on the built-in patterns alone. Saying so beats a gate that looks stronger
        # than it is: a new owner passes "personal data" without it ever having looked
        # for theirs.
        print('\nnote  personal data ran on the built-in patterns only. Your own names, '
              'domains and ids are not among them: put one pattern per line, as '
              '"pattern | what it is", in tools/leaks.txt, which never leaves your machine.')
    if total:
        print(f'\n{total} finding(s). Fix before publishing.')
        return 1
    if not quiet:
        print('\nClean.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--script-check':
        script_worker(*sys.argv[2:])
    else:
        sys.exit(main())
