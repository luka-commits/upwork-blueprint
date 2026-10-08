#!/usr/bin/env python3
"""The gate for an Upwork application before the member reads it.

    python3 code/application_check.py jobs/<id>/application.md [--job-title "..."] [--proof context/me.md]

Counts what can be counted, on the cover letter alone (screening answers after a
"Screening answers" heading do not count toward its length):

    at most 220 words            a compact pitch, not a method essay (numbered screening answers inside the letter do not count)
    none of the generic phrases   the tells that mark a letter as a template
    no em-dashes                  the fastest tell of machine writing
    the saved Loom or YouTube URL the application links to the finished video

A video link counts only on an exact host, loom.com or youtube.com with or without
www., and a non-empty path. "loom.com.example.test" is somebody else's domain.
The client's screening question is the client's wording, not the member's, so the
phrase and em-dash checks read the answer lines only.
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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_check
BANNED = ('i would love to', "i'm excited", 'i am excited', 'what stood out', 'passionate',
          'results-driven', 'i want in', 'rockstar', 'ninja', 'i hope this finds you')
RISK = ("you don't pay", 'you do not pay', 'risk-free', 'risk free', 'full refund', 'only pay',
        'approve each', 'milestones, not', 'milestone')
ASK = ('send me', 'reply with', 'when works', 'let me know', 'tell me', 'here on upwork',
       'jump on a call', 'hearing from you')
MAX_WORDS = 220
LOOM_PLACEHOLDER = '[LOOM LINK]'
# The applicant card shows about 230 to 240 characters, so the client decides whether to
# open the letter from its first words. These openings spend them on nothing.
CARD_WORDS = 45
FILLER_OPENERS = (r'i hope', r'hope you', r'my name is',
                  r'with (over )?\d+ years', r'allow me to', r'i came across',
                  r'just saw your', r'greetings')


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
    m = re.search(r'^\W*(?:answers to your )?screening (answers|question)', text, re.I | re.M)
    return (text[:m.start()], text[m.start():]) if m else (text, None)


def letter_body(text):
    """The part the client reads: without a leading title line or file header."""
    lines = text.splitlines()
    while lines and (lines[0].startswith('#') or not lines[0].strip()):
        lines.pop(0)
    return '\n'.join(lines)


def pc_contacts(text):
    """Every way of reaching the member off Upwork, found in the letter itself.

    The walkthrough video is the exception the application is built around, so a
    Loom or YouTube link is not a contact detail. Everything else is.
    """
    import pitch_check  # noqa: E402  (same folder, imported where it is used)
    body = re.sub(r'https?://(www\.)?(loom\.com|youtu\.be|youtube\.com)\S*', ' ', text, flags=re.I)
    problems = []
    if pitch_check.EMAIL.search(body):
        problems.append('an email address is in the letter: Upwork bans contact details before a contract')
    if pitch_check.phone_hit(body):
        problems.append('a phone number is in the letter: Upwork bans contact details before a contract')
    hit = pitch_check.CONTACT_LINKS.search(body)
    if hit:
        problems.append(f'a way to reach you off Upwork is in the letter: "{hit.group(0)}"')
    ask = pitch_check.BOOKING_WORDS.search(body)
    if ask:
        problems.append(f'the letter asks to move off Upwork: "{ask.group(0)}"')
    return problems


def check(text, job_title='', proof_text='', ready=False):
    letter, screening = split_letter(text)
    letter = letter_body(letter)
    low = letter.lower()
    fails, notes = [], []
    counted = '\n'.join(l for l in letter.splitlines() if not re.match(r'^\s*\d+\.\s', l))
    words = len(re.findall(r"\b[\w'$%+-]+\b", counted))
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
    # Contact details violate the pre-contract rule, so the application gate
    # refuses them just as the pitch-page gate does.
    for problem in pc_contacts(text):
        fails.append(problem)
    if not has_video(letter) and LOOM_PLACEHOLDER not in letter:
        fails.append('no Loom or YouTube link: include the walkthrough URL or the [LOOM LINK] placeholder')
    # The placeholder is correct while the letter is being written and wrong the moment
    # it is pasted: a client who reads "[LOOM LINK]" learns that nobody read it back.
    # Only the submit check refuses it, so writing stays possible before the Loom exists.
    if ready and LOOM_PLACEHOLDER in letter:
        fails.append('the [LOOM LINK] placeholder is still in the letter: paste the real '
                     'walkthrough URL before you submit')
    card = ' '.join(re.findall(r"\b[\w'$%+-]+\b", letter)[:CARD_WORDS]).lower()
    spent = [p for p in FILLER_OPENERS if re.search(p, card)]
    if spent:
        fails.append(f'the first {CARD_WORDS} words are all the client sees on the applicant card, '
                     f'and they open with filler: {", ".join(repr(p) for p in spent)}')
    if job_title:
        own = [w for w in re.findall(r"[\w']+", job_title.lower()) if len(w) > 3]
        if own and not any(w in card for w in own):
            notes.append(f'none of this job\'s own words appear in the first {CARD_WORDS} words, '
                         'which is all the client sees before deciding to open it')
    import profile_draft  # noqa: E402
    # This catches suspect numbers, not fabricated qualitative claims or a number
    # copied from unrelated proof. The member must verify claim-to-proof relevance.
    for sentence in re.split(r'(?<=[.!?])\s+|\n', text):
        if not re.search(r'\b(got|saved|raised|increased|built|delivered|rebuilt|contacted|helped|grew|cut|worked|managed|generated|achieved|have|has)\b', sentence, re.I):
            continue
        missing = profile_draft.unproven_numbers({'title': '', 'overview': sentence, 'portfolio': None}, proof_text)
        for number in missing:
            fails.append(f'"{number}" reads as a past result but is not in the evidence sections of context/me.md')
    notes.append('human review: match each claim to relevant proof, and confirm scope, rate and commitments')
    eye = [('risk reversal', any(r in low for r in RISK)), ('a specific ask', any(a in low for a in ASK))]
    return fails, notes, eye, words, screening is not None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('draft')
    ap.add_argument('--job-title', default='')
    ap.add_argument('--proof', default=str(ROOT / 'context' / 'me.md'))
    ap.add_argument('--ready', action='store_true',
                    help='check the letter as it will be pasted: the Loom placeholder is then a failure')
    args = ap.parse_args(argv)
    text = pathlib.Path(args.draft).read_text(encoding='utf-8')
    proof = pathlib.Path(args.proof)
    fails, notes, eye, words, has_screening = check(
        text, args.job_title,
        context_check.client_proof(proof.read_text(encoding='utf-8')) if proof.is_file() else '',
        ready=args.ready)
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
