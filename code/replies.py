#!/usr/bin/env python3
"""Validate the machine file that /brief writes for the cockpit.

    python3 code/replies.py check <job_id>
    python3 code/replies.py sendable <job_id>
    python3 code/replies.py sent <job_id> --label <label> [--via brief|upwork] [--story-id <id>]
    python3 code/replies.py skipped <job_id>

The model chooses the words. This script checks the fixed contract around them:
valid JSON, two or three labeled non-empty options, distinct text, no em-dashes,
no number the evidence sections of context/me.md cannot back, and no way of
reaching the member off Upwork. It never sends: `sendable` is the guard before a
send, `sent` records one, `skipped` holds the drafts for today.

A draft is the one client-facing artifact that leaves this repo as a message, and
it used to be the only one with no gate on its content: the cover letter and the
pitch page were both scanned for unproven numbers and contact details while the
reply, which goes straight into a client's inbox, was checked for shape alone.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (jobs_dir only)
import threads  # noqa: E402  (atomic writes of the thread and the drafts)

ID = re.compile(r'^[0-9]{6,25}$')


def unbacked_numbers(text, proof_text):
    """Every result number in a draft that the member's evidence does not carry."""
    import profile_checks as pc  # noqa: E402  (same folder, imported where it is used)
    missing = set()
    for hit in pc.RESULT_NUMBER.finditer(text):
        core = re.search(r'\d[\d.,]*', hit.group(0)).group(0).rstrip('.,')
        if not re.search(r'(?<![\d.,])' + re.escape(core) + r'(?!\d)', proof_text):
            missing.add(hit.group(0).strip())
    return sorted(missing)


def off_upwork(text):
    """Contact details and invitations to move the conversation, as the letter gate reads them."""
    import application_check  # noqa: E402  (same folder, imported where it is used)
    return [problem.replace('in the letter', 'in the draft').replace('the letter asks', 'the draft asks')
            for problem in application_check.pc_contacts(text)]


def proof_text():
    """The evidence sections of the member's own file, and nothing else from it."""
    import context_check  # noqa: E402  (same folder, imported where it is used)
    me = ROOT / 'context' / 'me.md'
    return context_check.client_proof(me.read_text(encoding='utf-8')) if me.is_file() else ''


def already_told(job_id):
    """What this client already has from the member: the proposal sent and the member's own messages.

    A follow-up that repeats the price of the proposal on the table makes no new claim,
    so the number gate must not strip it out of the proposal reminder.
    """
    folder = pipeline.jobs_dir() / job_id
    parts = []
    try:
        parts.append((folder / 'proposal.md').read_text(encoding='utf-8'))
    except OSError:
        pass
    try:
        thread = json.loads((folder / 'thread.json').read_text(encoding='utf-8'))
        parts += [str(m.get('text') or '') for m in thread.get('messages') or []
                  if isinstance(m, dict) and m.get('from') == 'me']
    except (OSError, json.JSONDecodeError):
        pass
    return '\n'.join(parts)


def validate(value, proof=None):
    problems = []
    if not isinstance(value, dict):
        return ['the root must be an object']
    if not isinstance(value.get('generated_at'), str) or not value['generated_at'].strip():
        problems.append('generated_at must be a non-empty string')
    drafts = value.get('drafts')
    if not isinstance(drafts, list) or len(drafts) not in (2, 3):
        problems.append('drafts must contain two or three options')
        return problems
    texts = []
    for index, draft in enumerate(drafts, 1):
        if not isinstance(draft, dict):
            problems.append(f'draft {index} must be an object')
            continue
        label, text = draft.get('label'), draft.get('text')
        if not isinstance(label, str) or not label.strip():
            problems.append(f'draft {index} needs a label')
        if not isinstance(text, str) or not text.strip():
            problems.append(f'draft {index} needs reply text')
        elif '\u2014' in text:
            problems.append(f'draft {index} contains an em-dash')
        else:
            texts.append(text.strip())
            for number in unbacked_numbers(text, proof if proof is not None else proof_text()):
                problems.append(f'draft {index} claims "{number}", which the evidence sections of '
                                f'context/me.md do not carry: omit it or record where it can be checked')
            for problem in off_upwork(text):
                problems.append(f'draft {index}: {problem}')
    if len(texts) != len(set(texts)):
        problems.append('draft texts must be meaningfully different')
    return problems


def cmd_check(args):
    if not ID.fullmatch(args.job_id):
        print('ABORT: that job id is not valid.', file=sys.stderr)
        return 1
    file = pipeline.jobs_dir() / args.job_id / 'replies.json'
    try:
        value = json.loads(file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print('ABORT: replies.json is missing.', file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f'ABORT: replies.json is not valid JSON at line {exc.lineno}.', file=sys.stderr)
        return 1
    problems = validate(value, proof_text() + '\n' + already_told(args.job_id))
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print(f'PASS: {len(value["drafts"])} reply drafts are valid.')
    return 0


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def load(job_id):
    """jobs/<id>/replies.json as (path, value); aborts with the reason when it cannot be used."""
    if not ID.fullmatch(job_id):
        raise SystemExit('ABORT: that job id is not valid.')
    file = pipeline.jobs_dir() / job_id / 'replies.json'
    try:
        return file, json.loads(file.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        raise SystemExit('ABORT: replies.json is missing or not valid JSON.')


def thread_of(job_id):
    try:
        return json.loads((pipeline.jobs_dir() / job_id / 'thread.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def cmd_sendable(args):
    """Whether these drafts may go out now: the last guard before send_message.

    A reply the client already has must never go out twice. The drafts are refused
    once one of them was sent or the member said not today, and when the saved room
    no longer waits on the member: their own message there means it already went out.
    """
    _, value = load(args.job_id)
    thread = thread_of(args.job_id)
    real = [m for m in thread.get('messages') or [] if isinstance(m, dict) and m.get('kind') != 'event']
    reason = (f'already sent at {value["sent"].get("at")}' if isinstance(value.get('sent'), dict)
              else f'held for today at {value["skipped_at"]}' if value.get('skipped_at')
              else 'no room_id in thread.json' if not thread.get('room_id')
              else 'the room does not wait on you' if thread.get('awaiting_reply_from') != 'you'
              else 'your message is the last one in the room' if real and real[-1].get('from') == 'me'
              else '')
    problems = [] if reason else validate(value, proof_text() + '\n' + already_told(args.job_id))
    if reason or problems:
        print(f'HOLD: {reason or problems[0]}', file=sys.stderr)
        return 1
    print(f'SENDABLE room {thread["room_id"]}: ' + ', '.join(str(d.get('label')) for d in value['drafts']))
    return 0


def cmd_sent(args):
    """Record which draft went to the client, in the draft's own words.

    The send itself is one connector call and leaves no trace here, so a week later
    nobody can say what was sent or whether it was the text the member approved.
    Taking the record from replies.json rather than from a retyped summary is the
    whole point: what is logged is provably the option they chose. The draft file
    keeps the exact text and time, the thread shows it as the member's message, and
    the pipeline timeline carries one line, so the next run cannot offer it again.
    """
    file, value = load(args.job_id)
    if isinstance(value.get('sent'), dict):
        print(f'ABORT: these drafts were already sent at {value["sent"].get("at")}.', file=sys.stderr)
        return 1
    drafts = [d for d in value.get('drafts') or [] if isinstance(d, dict)]
    picked = [d for d in drafts if str(d.get('label', '')).strip().lower() == args.label.strip().lower()]
    if not picked:
        labels = ', '.join(repr(str(d.get('label', ''))) for d in drafts) or 'none'
        print(f'ABORT: no draft labelled {args.label!r}. Labels present: {labels}', file=sys.stderr)
        return 1
    exact, at = str(picked[0].get('text', '')).strip(), now()
    out = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), 'acted', args.job_id,
                          '--note', f'sent to the client ({args.via}): {" ".join(exact.split())}'],
                         capture_output=True, text=True)
    if out.returncode:
        print(out.stderr.strip(), file=sys.stderr)
        return 1
    value['sent'] = {'label': picked[0].get('label'), 'text': exact, 'at': at, 'via': args.via,
                     'story_id': args.story_id}
    threads.write_json(file, value)
    thread = thread_of(args.job_id)
    if thread:
        thread.setdefault('messages', []).append({'id': args.story_id, 'from': 'me', 'name': '', 'at': at,
                                                  'text': exact, 'kind': 'message'})
        thread['awaiting_reply_from'] = 'them'
        threads.write_json(pipeline.jobs_dir() / args.job_id / 'thread.json', thread)
    print(f'Recorded the "{picked[0].get("label")}" draft as sent ({args.via}) at {at}.')
    return 0


def cmd_skipped(args):
    """The member said not today: these drafts are not offered again; the lead stays due."""
    file, value = load(args.job_id)
    value['skipped_at'] = now()
    threads.write_json(file, value)
    print(f'Held the drafts for {args.job_id}; the next /brief writes fresh ones if the lead is still due.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Validate jobs/<id>/replies.json.')
    check.add_argument('job_id')
    check.set_defaults(func=cmd_check)
    sendable = sub.add_parser('sendable', help='Whether the drafts may go out now; run before every send.')
    sendable.add_argument('job_id')
    sendable.set_defaults(func=cmd_sendable)
    sent = sub.add_parser('sent', help='Record which draft went out, from its own text.')
    sent.add_argument('job_id')
    sent.add_argument('--label', required=True, help='the label of the draft that went out')
    sent.add_argument('--via', choices=('brief', 'upwork'), default='upwork',
                      help='brief: sent by send_message on the yes; upwork: the member sent it themselves')
    sent.add_argument('--story-id', help='the story id send_message returned, when it returned one')
    sent.set_defaults(func=cmd_sent)
    skipped = sub.add_parser('skipped', help='The member said not today to these drafts.')
    skipped.add_argument('job_id')
    skipped.set_defaults(func=cmd_skipped)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
