#!/usr/bin/env python3
"""Mechanical checks on an Upwork profile: the half of an audit that needs no judgement.

Reads the two connector responses /audit saves, runs every check that can be
decided by counting, and prints the result. /profile later runs the same checks
on its drafts, so "better" means the same thing before and after.

    python3 code/profile_checks.py data/profile.json data/highlights.json [--json]

Where a check comes from matters, because members act on the tone:
  upwork       Upwork's own documentation says it
  top-earners  the pattern three top-earning profiles and a proven bio formula
               share. Practitioner evidence, not Upwork's word.
"""
import json
import pathlib
import re
import sys

TAG = re.compile(r'</?untrusted_participant_content>')
GREETING = re.compile(r"^\W*(hi|hey|hello|dear|greetings|welcome|my name|i am|i'm|i´m)\b", re.I)
BANNED = ('i would love to', "i'm excited", 'i am excited', 'passionate', 'results-driven',
          'rockstar', 'ninja')
ASK = re.compile(r'\?|\b(send me|tell me|share|message me|invite me|let me know|drop me)\b', re.I)
# Words that describe a person rather than name a searchable thing.
STOP = {'expert', 'specialist', 'and', 'the', 'for', 'with', 'developer', 'consultant',
        'freelancer', 'pro', 'professional', 'services', 'service', 'certified', 'top',
        'senior', 'your', 'you', 'from', 'into'}
# A number that reads as a result: money, a percentage, a count with + or x, or a
# count of something. Tool names like n8n or A2P and bare years are not results;
# counting any digit made every automation profile pass the number checks.
RESULT_NUMBER = re.compile(
    r'\$\s?\d|\d\s?%|\d\+|\b\d+(\.\d+)?x\b|\b\d{1,3}(,\d{3})+\b|'
    r'\b\d+\s?(?:[a-z-]+\s)?(hours?|hrs|clients?|leads?|projects?|jobs?|patients?|customers?|stores?|'
    r'funnels?|sales|signups?|bookings?|calls?|days?|weeks?|months?|minutes?|times|'
    r'stars?|reviews?)\b', re.I)
OPENING = 250
SKILLS_TARGET = 20
SKILLS_PASS = 15


def clean(value):
    return TAG.sub('', value or '').strip()


def normalize(profile, highlights=None):
    """The fields the checks read, from the raw get_profile and list_highlights responses.

    Your own profile sits under `data`; another freelancer's (read by profile_key)
    under `data.talentProfileByProfileKey`. Highlights exist only for your own
    profile, so without them portfolio and certificates are None: not measured,
    which is different from empty.
    """
    data = profile.get('data', {})
    data = data.get('talentProfileByProfileKey', data)
    personal = data.get('personalData', {})
    return {
        'name': f'{personal.get("firstName", "")} {personal.get("lastName", "")}'.strip(),
        'title': clean(personal.get('title')),
        'overview': clean(personal.get('description')),
        'rate': (personal.get('chargeRate') or {}).get('rawValue'),
        'skills': [s.get('prettyName', '') for s in data.get('skills', [])],
        'employment': data.get('employmentRecords', []),
        'education': data.get('educationRecords', []),
        'languages': profile.get('languages', []),
        'aggregates': data.get('profileAggregates') or profile.get('profileAggregates') or {},
        'portfolio': None if highlights is None else
        [clean(p.get('title')) for p in highlights.get('portfolio_projects', [])],
        'certificates': None if highlights is None else highlights.get('certificates', []),
    }


def squash(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def title_terms(title):
    """The searchable things a title names: blocks split on | and commas, minus job words."""
    terms = []
    for block in re.split(r'[|,/]', title):
        words = [w for w in re.split(r'[\s&+]+', block) if w and squash(w) not in STOP]
        if words:
            terms.append(' '.join(words))
    return terms


def term_in_skills(term, skills):
    """A title term counts as covered when any of its words starts a skill's words."""
    squashed = [squash(s) for s in skills]
    for word in re.split(r'\s+', term):
        key = squash(word)[:6]
        if len(key) >= 3 and any(key in s for s in squashed):
            return True
    return False


def structured_lines(overview):
    """Lines that open with a bullet, an emoji or Unicode bold: how structure survives
    Upwork stripping markdown."""
    count = 0
    for line in overview.splitlines():
        s = line.strip()
        if not s:
            continue
        first = s[0]
        if 0x1D400 <= ord(first) <= 0x1D7FF or not first.isalnum() and first not in '"\'(':
            count += 1
    return count


def has_keyword_line(overview):
    for line in overview.splitlines():
        items = [i.strip() for i in line.split(',') if i.strip()]
        if len(items) >= 6 and all(len(i.split()) <= 4 for i in items[1:-1]):
            return True
    return False


def run_checks(p):
    overview = p['overview']
    opening = overview[:OPENING]
    first_line = next((l for l in overview.splitlines() if l.strip()), '')
    lower = overview.lower()
    blocks = [b for b in p['title'].split('|') if b.strip()]
    uncovered = [t for t in title_terms(p['title']) if not term_in_skills(t, p['skills'])]
    numbered_lines = [l for l in overview.splitlines() if RESULT_NUMBER.search(l)]
    opening_number = RESULT_NUMBER.search(opening)
    banned = [b for b in BANNED if b in lower]
    portfolio = p['portfolio'] or []
    certificates = p['certificates'] or []
    outcome_titles = [t for t in portfolio if RESULT_NUMBER.search(t)]
    ending = overview[-400:]

    checks = [
        ('skills_cover_title', 'Every tool or field in your title is also one of your skills', 'upwork',
         not uncovered,
         'all covered' if not uncovered else 'in the title but not in skills: ' + ', '.join(uncovered)),
        ('title_blocks', 'Title is three or four searchable blocks split by |', 'top-earners',
         3 <= len(blocks) <= 4, f'{len(blocks)} block(s) split by |'),
        ('opening_no_greeting', 'First line states what the client gets, not a greeting or "I am"',
         'top-earners', not GREETING.search(first_line), f'starts: "{first_line[:60]}"'),
        ('opening_has_number', 'A hard number within the first 250 characters', 'top-earners',
         bool(opening_number), f'found: {opening_number.group(0)}' if opening_number else 'none'),
        ('results_with_numbers', 'At least three result lines carry a number', 'top-earners',
         len(numbered_lines) >= 3, f'{len(numbered_lines)} line(s) with a number'),
        ('no_banned_phrases', 'None of the phrases every top earner avoids', 'top-earners',
         not banned, 'none' if not banned else 'found: ' + ', '.join(banned)),
        ('visual_structure', 'Visible structure: bullets, emoji or bold headers', 'top-earners',
         structured_lines(overview) >= 3, f'{structured_lines(overview)} structured line(s)'),
        ('keyword_block', 'A line listing the tools you work with, for search', 'top-earners',
         has_keyword_line(overview), 'found' if has_keyword_line(overview) else 'none'),
        ('closing_ask', 'Ends with a concrete next step for the client', 'top-earners',
         bool(ASK.search(ending)), 'found' if ASK.search(ending) else 'ends without an ask'),
        ('skills_count', f'At least {SKILLS_PASS} skills, ideally all {SKILLS_TARGET}', 'top-earners',
         len(p['skills']) >= SKILLS_PASS, f'{len(p["skills"])} skill(s)'),
        ('portfolio_count', 'At least two portfolio projects', 'upwork',
         len(portfolio) >= 2, f'{len(portfolio)} project(s)'),
        ('portfolio_outcomes', 'At least half the portfolio titles name a measurable result',
         'top-earners', bool(portfolio) and len(outcome_titles) * 2 >= len(portfolio),
         f'{len(outcome_titles)} of {len(portfolio)} carry a number'),
        ('certificates', 'At least one certificate', 'top-earners',
         len(certificates) >= 1, f'{len(certificates)} certificate(s)'),
        ('rate_set', 'An hourly rate is set', 'upwork', bool(p['rate']), f'rate: {p["rate"] or "none"}'),
        ('complete', 'Employment, education and languages all filled in', 'upwork',
         bool(p['employment'] and p['education'] and p['languages']),
         f'{len(p["employment"])} employment, {len(p["education"])} education, '
         f'{len(p["languages"])} language(s)'),
    ]
    return [dict(id=c[0], label=c[1], source=c[2], passed=bool(c[3]), detail=c[4]) for c in checks]


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    profile, highlights = (json.loads(pathlib.Path(a).read_text(encoding='utf-8')) for a in args)
    results = run_checks(normalize(profile, highlights))
    passed = sum(r['passed'] for r in results)
    if '--json' in argv:
        print(json.dumps({'passed': passed, 'total': len(results), 'checks': results}, indent=2,
                         ensure_ascii=False))
        return 0
    for r in results:
        print(f'{"PASS" if r["passed"] else "FAIL"}  {r["label"]}  ({r["detail"]}; source: {r["source"]})')
    print(f'\nSCORE {passed} of {len(results)} checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
