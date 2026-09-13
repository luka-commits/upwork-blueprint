#!/usr/bin/env python3
"""The gate for an Upwork application before the member reads it.

    python3 code/application_check.py jobs/<id>/application.md [--job-title "..."] [--proof context/proof.md]

Counts what can be counted, on the cover letter alone (screening answers after a
"Screening answers" heading do not count toward its length):

    at most 140 words            a compact pitch, not a method essay
    none of the generic phrases   the tells that mark a letter as a template
    no em-dashes                  the fastest tell of machine writing
    the saved Loom or YouTube URL the application links to the finished video
    unsupported past numbers     also checked in screening answers

Job specificity, commitments and the ask are reported for a human eye, not scored: no pattern
can tell a real risk reversal from a sentence that contains the word "refund",
and a checker that cries wolf gets ignored.
"""
import argparse
import pathlib
import re
import sys
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANNED = ('i would love to', "i'm excited", 'i am excited', 'what stood out', 'passionate',
          'results-driven', 'i want in', 'rockstar', 'ninja', 'i hope this finds you')
RISK = ("you don't pay", 'you do not pay', 'risk-free', 'risk free', 'full refund', 'only pay',
        'approve each', 'milestones, not', 'milestone')
ASK = ('send me', 'reply with', 'when works', 'let me know', 'tell me', 'here on upwork')
MAX_WORDS = 140


def has_video(text):
    for candidate in re.findall(r'https://[^\s<>]+', text):
        url = urlparse(candidate.rstrip(').,]'))
        if url.username or url.password:
            continue
        if url.hostname in ('loom.com', 'www.loom.com') and re.fullmatch(r'/share/[^/]+', url.path):
            return True
        if url.hostname == 'youtu.be' and len(url.path.strip('/')) > 0:
            return True
        if url.hostname in ('youtube.com', 'www.youtube.com') and url.path == '/watch' and parse_qs(url.query).get('v'):
            return True
    return False


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
    if not words:
        fails.append('the cover letter is empty')
    authored = '\n'.join(line for line in text.splitlines() if not re.match(r'^\s*#', line))
    hits = [b for b in BANNED if b in authored.lower()]
    if hits:
        fails.append('generic phrasing: ' + ', '.join(f'"{h}"' for h in hits))
    if chr(0x2014) in text:
        fails.append('em-dash present: use a colon, comma or full stop')
    if not has_video(letter):
        fails.append('no Loom or YouTube link: include the finished walkthrough URL')
    if job_title:
        opening = ' '.join(re.split(r'(?<=[.!?])\s+', letter.strip())[:3]).lower()
        if job_title.lower() not in opening:
            notes.append('check the opening names this client\'s actual problem; the literal job title is optional')
    import profile_draft  # noqa: E402
    # This catches suspect numbers, not fabricated qualitative claims or a number
    # copied from unrelated proof. The member must verify claim-to-proof relevance.
    for sentence in re.split(r'(?<=[.!?])\s+|\n', text):
        if not re.search(r'\b(got|saved|raised|increased|built|delivered|rebuilt|contacted|helped|grew|cut|worked|managed|generated|achieved|have|has)\b', sentence, re.I):
            continue
        missing = profile_draft.unproven_numbers({'title': '', 'overview': sentence, 'portfolio': None}, proof_text)
        for number in missing:
            fails.append(f'"{number}" reads as a past result but is not in your proof file')
    notes.append('human review: match each claim to relevant proof, and confirm scope, rate and commitments')
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
