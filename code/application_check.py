#!/usr/bin/env python3
"""The gate for an Upwork application before the member reads it.

    python3 code/application_check.py jobs/<id>/application.md [--job-title "..."] [--proof context/proof.md]

Counts what can be counted, on the cover letter alone (screening answers after a
"Screening answers" heading do not count toward its length):

    300 to 400 words              a skimmed letter that still says enough
    none of the generic phrases   the tells that mark a letter as a template
    no em-dashes                  the fastest tell of machine writing
    the saved Loom or YouTube URL the application links to the finished video
    at least 5 list items with a number, 7 is the target
    the job title in the first three sentences, when --job-title is given
    every past result number is in the proof file

Risk reversal and the ask are reported for a human eye, not scored: no pattern
can tell a real risk reversal from a sentence that contains the word "refund",
and a checker that cries wolf gets ignored.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANNED = ('i would love to', "i'm excited", 'i am excited', 'what stood out', 'passionate',
          'results-driven', 'i want in', 'rockstar', 'ninja', 'i hope this finds you')
VIDEO = ('loom.com', 'youtu.be', 'youtube.com')
RISK = ("you don't pay", 'you do not pay', 'risk-free', 'risk free', 'full refund', 'only pay',
        'approve each', 'milestones, not', 'milestone')
ASK = ('send me', 'reply with', 'when works', 'let me know', 'tell me', 'here on upwork')
LIST_MARKER = re.compile(r'^(\d+[.)]|[-*•✅])\s+')
MIN_WORDS, MAX_WORDS = 300, 400


def split_letter(text):
    m = re.search(r'^\W*screening (answers|question)', text, re.I | re.M)
    return (text[:m.start()], text[m.start():]) if m else (text, None)


def letter_body(text):
    """The part the client reads: without a leading title line or file header."""
    lines = text.splitlines()
    while lines and (lines[0].startswith('#') or not lines[0].strip()):
        lines.pop(0)
    return '\n'.join(lines)


def check(text, job_title='', proof_text=''):
    letter, screening = split_letter(text)
    letter = letter_body(letter)
    low = letter.lower()
    fails, notes = [], []
    words = len(re.findall(r"\b[\w'$%+-]+\b", letter))
    if words > MAX_WORDS:
        fails.append(f'cover letter is {words} words, the cap is {MAX_WORDS}: cut {words - MAX_WORDS}')
    elif words < MIN_WORDS:
        notes.append(f'cover letter is {words} words, the target starts at {MIN_WORDS}: thin, not a fail')
    hits = [b for b in BANNED if b in low]
    if hits:
        fails.append('generic phrasing: ' + ', '.join(f'"{h}"' for h in hits))
    if chr(0x2014) in text:
        fails.append('em-dash present: use a colon, comma or full stop')
    if not any(v in low for v in VIDEO):
        fails.append('no Loom or YouTube link: include the finished walkthrough URL')
    items = [LIST_MARKER.sub('', l.strip()) for l in letter.splitlines() if LIST_MARKER.match(l.strip())]
    numbered = [i for i in items if re.search(r'\d', i)]
    if len(numbered) < 5:
        fails.append(f'{len(numbered)} of {len(items)} list items carry a number: at least 5 needed, 7 is the target')
    if job_title:
        opening = ' '.join(re.split(r'(?<=[.!?])\s+', letter.strip())[:3]).lower()
        if job_title.lower() not in opening:
            fails.append(f'the job title "{job_title}" is not in the first three sentences')
    if proof_text:
        draft = {'title': '', 'overview': letter, 'portfolio': None}
        import profile_draft  # noqa: E402  (shares the number rule with /profile)
        missing = profile_draft.unproven_numbers(draft, proof_text)
        # Forward promises ("under 5 minutes") are allowed; past results are not.
        # Only a number inside a sentence about the past has to be in the proof file.
        past = [n for n in missing if re.search(rf'(got|saved|raised|increase|built|delivered|'
                                                rf'contacted|helped|grew|cut)[^.]*{re.escape(n)}', low)]
        for n in past:
            fails.append(f'"{n}" reads as a past result but is not in your proof file')
    eye = [('risk reversal', any(r in low for r in RISK)), ('a specific ask', any(a in low for a in ASK))]
    return fails, notes, eye, words, screening is not None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('draft')
    ap.add_argument('--job-title', default='')
    ap.add_argument('--proof', default=str(ROOT / 'context' / 'proof.md'))
    args = ap.parse_args(argv)
    text = pathlib.Path(args.draft).read_text(encoding='utf-8')
    proof = pathlib.Path(args.proof)
    fails, notes, eye, words, has_screening = check(
        text, args.job_title, proof.read_text(encoding='utf-8') if proof.is_file() else '')
    for n in notes:
        print(f'note  {n}')
    for f in fails:
        print(f'FAIL  {f}')
    for label, found in eye:
        print(f'eye   {label}: {"looks present" if found else "NOT FOUND, check"}')
    if not has_screening:
        print('eye   no screening answers: correct only if the job asks no questions')
    print(f'\n{"PASS" if not fails else f"{len(fails)} problem(s)."}  {words} words in the letter')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
