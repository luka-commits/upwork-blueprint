#!/usr/bin/env python3
"""Mechanical checks on an Upwork profile: the half of an audit that needs no judgement.

Reads the two connector responses /profile saves, runs every check that can be
decided by counting, and prints the result. /profile later runs the same checks
on its drafts, so "better" means the same thing before and after.

    python3 code/profile_checks.py data/profile.json data/highlights.json [--json]

Where a check comes from matters, because members act on the tone:
  upwork       Upwork's own documentation says it
  top-earners  the pattern three top-earning profiles and a proven bio formula
               share. Practitioner evidence, not Upwork's word.
"""
import datetime
import json
import pathlib
import re
import sys

import pipeline

TAG = re.compile(r'</?untrusted_participant_content>')
GREETING = re.compile(r"^\W*(hi|hey|hello|dear|greetings|welcome|my name|i am|i'm|i´m)\b", re.I)
ASK = re.compile(r'\?|\b(send me|tell me|share|message me|invite me|let me know|drop me)\b', re.I)
# Words that describe a person rather than name a searchable thing.
STOP = {'expert', 'specialist', 'and', 'the', 'for', 'with', 'developer', 'consultant',
        'freelancer', 'pro', 'professional', 'services', 'service', 'certified', 'top',
        'senior', 'your', 'you', 'from', 'into'}
# A number that reads as a result: money, a percentage, a count with + or x, or a
# count of something. Tool names like n8n or A2P and bare years are not results;
# counting any digit made every automation profile pass the number checks.
RESULT_NUMBER = re.compile(
    r'\$\s?\d[\d.,]*\s?[KkMm]?\+?|\b\d[\d.,]*\s?(?:%|percent\b)|\b\d[\d.,]*\+|\b\d+(\.\d+)?x\b|\b\d{1,3}(,\d{3})+\b|'
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
        'photo': personal.get('photo') or personal.get('portrait') or data.get('photo'),
        'video': data.get('video') if 'video' in data else personal.get('video', profile.get('video')),
        'linked_accounts': data.get('linkedAccounts'),
        'other_experience': data.get('otherExperiences'),
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


def completeness(p):
    mandatory = [('Photo', bool(p.get('photo'))), ('Overview', bool(p['overview'])),
                 ('Employment', bool(p['employment'])), ('Skills', bool(p['skills']))]
    pct = 50 if all(present for _, present in mandatory) else 0
    missing = [name for name, present in mandatory if not present]
    optional = [
        ('Portfolio projects', min(len(p['portfolio'] or []) * 5, 20), 20),
        ('Additional employment', min(max(len(p['employment']) - 1, 0) * 10, 20), 20),
        ('Education', min(len(p['education']) * 10, 20), 20),
        ('Additional skills', 10 if len(p['skills']) > 1 else 0, 10),
        ('Intro video', 10 if p.get('video') else 0, 10),
        ('Linked account', 10 if p.get('linked_accounts') else 0, 10),
        ('Certificates', min(len(p['certificates'] or []) * 5, 10), 10),
        ('Other experience', 5 if p.get('other_experience') else 0, 5),
    ]
    for name, points, maximum in optional:
        pct += points
        if points < maximum:
            missing.append(name)
    return {'pct': min(pct, 100), 'missing': missing}


def save_completeness(result):
    data = pipeline.data_dir()
    data.mkdir(parents=True, exist_ok=True)
    snapshot = dict(date=datetime.date.today().isoformat(), **result)
    path = data / 'profile-history.jsonl'
    rows = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
                datetime.date.fromisoformat(row['date'])
                rows[row['date']] = row
            except (ValueError, KeyError, TypeError):
                continue
    rows[snapshot['date']] = snapshot
    temporary = path.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(rows[date], ensure_ascii=False) + '\n' for date in sorted(rows)), encoding='utf-8')
    temporary.replace(path)


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


# What members call a tool, and the name Upwork's skill list uses for it.
ALIASES = {'ghl': 'highlevel'}


def term_in_skills(term, skills):
    """A title term counts as covered when a word of it and a skill contain each other.

    Both directions, because Upwork's names are often shorter than what people
    write: the skill is "HighLevel", the title says "GoHighLevel".
    """
    squashed = [squash(s) for s in skills]
    for word in re.split(r'\s+', term):
        full = ALIASES.get(squash(word), squash(word))
        key = full[:6]
        if len(key) >= 3 and any(key in s or (len(s) >= 4 and s in full) for s in squashed):
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
    portfolio = p['portfolio'] or []
    certificates = p['certificates'] or []
    outcome_titles = [t for t in portfolio if RESULT_NUMBER.search(t)]
    ending = overview[-400:]

    checks = [
        ('skills_cover_title', 'Every tool or field in your title is also one of your skills', 'upwork',
         not uncovered,
         'all covered' if not uncovered else 'in the title but not in skills: ' + ', '.join(uncovered)),
        # Sixteen measured profiles carry two to five blocks, and four of them use no
        # pipe at all. A check that demanded three or four failed four strong profiles.
        ('title_blocks', 'Title is two to five searchable blocks split by |', 'top-earners',
         2 <= len(blocks) <= 5, f'{len(blocks)} block(s) split by |'),
        ('opening_no_greeting', 'First line states what the client gets, not a greeting or "I am"',
         'top-earners', not GREETING.search(first_line), f'starts: "{first_line[:60]}"'),
        ('opening_has_number', 'A hard number within the first 250 characters', 'top-earners',
         bool(opening_number), f'found: {opening_number.group(0)}' if opening_number else 'none'),
        ('results_with_numbers', 'At least three result lines carry a number', 'top-earners',
         len(numbered_lines) >= 3, f'{len(numbered_lines)} line(s) with a number'),
        ('closing_ask', 'Ends with a concrete next step for the client', 'top-earners',
         bool(ASK.search(ending)), 'found' if ASK.search(ending) else 'ends without an ask'),
        ('skills_count', f'At least {SKILLS_PASS} skills, ideally all {SKILLS_TARGET}', 'top-earners',
         len(p['skills']) >= SKILLS_PASS, f'{len(p["skills"])} skill(s)'),
        ('portfolio', 'At least two portfolio projects, half of them with a measurable result in the title',
         'upwork', len(portfolio) >= 2 and len(outcome_titles) * 2 >= len(portfolio),
         f'{len(portfolio)} project(s), {len(outcome_titles)} with a number'),
        # Only one of forty measured postings asked for a certificate, so this is not
        # about what clients want. It is here because Upwork's own partner
        # certification page says the certification feeds search and matching.
        ('certificates', 'A certification, which Upwork says feeds search and matching', 'upwork',
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
    normalized = normalize(profile, highlights)
    results = run_checks(normalized)
    score = completeness(normalized)
    save_completeness(score)
    passed = sum(r['passed'] for r in results)
    if '--json' in argv:
        print(json.dumps({'passed': passed, 'total': len(results), 'checks': results, 'completeness': score}, indent=2,
                         ensure_ascii=False))
        return 0
    print(f'Completeness: {score["pct"]}% · Missing: {", ".join(score["missing"]) or "none"}')
    for r in results:
        print(f'{"PASS" if r["passed"] else "FAIL"}  {r["label"]}  ({r["detail"]}; source: {r["source"]})')
    print(f'\nSCORE {passed} of {len(results)} checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
