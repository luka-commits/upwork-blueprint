#!/usr/bin/env python3
"""The gate for the one file every other command writes from.

    python3 code/context_check.py [--quiet]
    python3 code/context_check.py --status

/about-me fills context/me.md. Everything after it, from the profile to a
proposal, quotes that file, so a starter line left in place turns
into "not answered yet" inside something a client reads. This counts what is
still open.

What the member said themselves needs no status: it is theirs. A proof entry is
marked `pending` only while it is something pulled from elsewhere (a file, an
email, the web) that they have not confirmed, and `verified` only when it also
names where it can be checked.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ME = ROOT / 'context' / 'me.md'
STARTER = 'not answered yet'
EMPTY_SECTION = 'nothing recorded yet'
# The three sections that hold evidence. Everything else in the file is what the
# member says about themselves, which is not the same thing and must never be
# read as if it were.
PROOF_SECTIONS = ('Results', 'Reviews', 'Credentials')

# Without these, a later command either invents the answer or stops mid-run.
REQUIRED = (
    'Profession',
    'The one thing you want to be hired for',
    'Services you sell',
    'Tools and systems you can name confidently',
    'Timezone and hours you answer messages',
)
# The proof interview /about-me puts to every member: one line per question under
# "## Proof interview". "none" is an answer. A missing line is not, so a file
# written before the interview existed reads as open until it has run, and
# /profile does not write from a file whose interview is unfinished.
INTERVIEW = (
    'Press and stage',
    'Recognizable brands',
    'Biggest companies',
    'Own business',
    'Biggest responsibility',
    'Video testimonials',
    'Written recommendations',
    'Case studies',
    'Upwork status',
    'Top project results',
    'Projects completed',
    'Hours saved',
    'Money earned',
    'People helped',
    'Years of experience',
    'Certifications',
    'Awards and promotions',
    'Online following',
    'Outcomes you deliver',
    'Daily tools and languages',
)
INTERVIEW_FINDING = 'proof interview'
CHECKABLE = re.compile(r'(where to check|where it can be checked|checked at|source:|https?://|upwork\.com)', re.I)


def proof_only(text):
    """Just the evidence sections, for anything that verifies a claim.

    The draft gate looks up every number it is about to print in this text.
    Handed the whole file it would also see the hourly rate, the applications
    per day and the years in a CV, so an invented "40%" would pass because the
    rate happens to be 40. Whoever checks a claim gets the evidence and nothing
    else.
    """
    kept, inside = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            inside = line[3:].strip() in PROOF_SECTIONS
        if inside:
            kept.append(line)
    return '\n'.join(kept)


def field(text, label):
    """The value behind a bold label, or None when the label is missing."""
    match = re.search(rf'^\*\*{re.escape(label)}[^:\n]*:\*\*[ \t]*(.*)$', text, re.M | re.I)
    return match.group(1).strip() if match else None


def check_me(text):
    findings = []
    for label in REQUIRED:
        value = field(text, label)
        if value is None:
            findings.append(f'me.md has no "{label}" line')
        elif not value or STARTER in value.lower():
            findings.append(f'me.md: {label} is still unanswered')
    background = re.search(r'^## Your background\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    body = re.sub(r'^\*\*[^:\n]+:\*\*[^\n]*', '', background.group(1), flags=re.M).strip() if background else ''
    if not body or re.search(r'not filled in yet|not answered yet', body, re.I):
        findings.append('me.md: Your background is still unanswered')
    findings.extend(f'me.md: {INTERVIEW_FINDING}, {label} is still unanswered'
                    for label in interview_open(text))
    return findings


def interview_open(text):
    """The interview questions with no answer on file, in the order they are asked."""
    values = ((label, field(text, label)) for label in INTERVIEW)
    return [label for label, value in values if not value or STARTER in value.lower()]


def entries(text):
    """Every proof entry, with its status and source kept in the same block."""
    blocks, lines = [], []
    current = None
    for line in text.splitlines():
        boundary = line.startswith(('## ', '### ')) or not line.strip()
        if line.startswith('**') and ':**' not in line:
            boundary = True
        # A named metadata bullet stays with its entry. Consecutive unlabelled
        # top-level bullets also support the older single-line entry format.
        metadata = re.match(r'^- (?:\*\*)?[^:\n]{1,60}:', line)
        if (line.startswith('- ') and lines and lines[0].startswith('- ')
                and not metadata and not re.match(r'^- (?:\*\*)?(verified|pending)\b', line, re.I)):
            boundary = True
        if boundary and lines:
            blocks.append((current, '\n'.join(lines).strip()))
            lines = []
        if line.startswith('## '):
            current = line[3:].strip()
            continue
        if current and line.strip():
            lines.append(line)
    if lines:
        blocks.append((current, '\n'.join(lines).strip()))
    return blocks


def check_proof(text):
    findings = []
    body = [(section, line) for section, line in entries(proof_only(text))
            if EMPTY_SECTION not in line.lower() and not line.startswith('One block per')]
    for section, line in body:
        if re.search(r'\bverified\b', line, re.I) and not CHECKABLE.search(line):
            findings.append(f'me.md, {section}: verified with no place to check it: "{line[:50]}"')
    return findings


def answered(me_text):
    """How many of the required lines carry an answer rather than the starter."""
    values = (field(me_text, label) for label in REQUIRED)
    return sum(1 for v in values if v and STARTER not in v.lower())


def proof_entries(text):
    """Proof blocks the member wrote, without the starter's own instructions."""
    return [line for _, line in entries(proof_only(text))
            if EMPTY_SECTION not in line.lower() and not line.startswith('One block per')]


def verified_proof(text):
    """Entries the member stated or confirmed: everything not still waiting for their yes."""
    return '\n\n'.join(block for block in proof_entries(text)
                       if not re.search(r'\bpending\b', block, re.I))


def usable_proof(text):
    """Entries the member stated with a concrete figure, verified or not.

    A client-facing profile may carry the member's own numbers. Only entries with
    no figure, and the starter's instructions, stay out.
    """
    return '\n\n'.join(block for block in proof_entries(text) if re.search(r'\d', block))


def status(text):
    """untouched, partial or complete, so /about-me knows which command it is.

    Asking a member a second time for what they already answered is the fastest
    way to lose them, and running the interview against a file that is still the
    shipped starter is the only case where every question is new. The line is
    read by a command, so it keeps the same three words.
    """
    filled, proofs = answered(text), len(proof_entries(text))
    open_points = len(check_me(text) + check_proof(proof_only(text)))
    if not filled and not proofs:
        return 'untouched', filled, proofs, open_points
    return ('complete' if not open_points else 'partial'), filled, proofs, open_points


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('me', nargs='?', default=ME, type=pathlib.Path,
                        help='context/me.md by default')
    parser.add_argument('--quiet', action='store_true', help='print nothing when clean')
    parser.add_argument('--status', action='store_true',
                        help='untouched, partial or complete, for the start of /about-me')
    args = parser.parse_args(argv)
    if not args.me.is_file():
        if args.status:
            print('untouched: the context file does not exist yet. '
                  'Run python3 code/workspace.py')
            return 0
        print(f'FAIL  {args.me} is missing. Run python3 code/workspace.py')
        return 1
    text = args.me.read_text(encoding='utf-8')
    if args.status:
        state, filled, proofs, open_points = status(text)
        asked = len(INTERVIEW) - len(interview_open(text))
        print(f'{state}: {filled} of {len(REQUIRED)} answers, {proofs} proof entries, '
              f'{open_points} open, proof interview {asked} of {len(INTERVIEW)} answered')
        return 0
    findings = check_me(text) + check_proof(proof_only(text))
    if findings:
        for f in findings:
            print(f'FAIL  {f}')
        print(f'\n{len(findings)} open. Ask the member, never fill it in for them.')
        return 1
    if not args.quiet:
        print('PASS: your file answers what every command needs.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
