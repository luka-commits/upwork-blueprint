#!/usr/bin/env python3
"""Client threads: turns what Upwork's message list returns into the cockpit's chat.

    python3 code/threads.py save <job_id> --file <list_messages.json>|-
    python3 code/threads.py confirm <job_id> --room <room_id> --awaiting them

Upwork hands messages back newest first, each wrapped in a marker for untrusted
text, with HTML entities, escaped markdown and system events ("System event:
ended", "Kyle ended the contract") mixed in with real messages. This script is
the one place that cleans them: oldest first, plain text, your messages marked as
yours, events as events. The result is jobs/<id>/thread.json, which the cockpit's
chat window reads. It is Upwork content, so `pipeline.py prune` deletes it after
24 hours.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys
import os
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)

WRAPPER = re.compile(r'</?untrusted_participant_content>')
SYSTEM_EVENT = re.compile(r'^System event: (\w+)\.')
# Only the event whose meaning the room card confirms gets a plain name; the rest
# stay as Upwork says them rather than as a guess.
EVENT_WORDS = {'ended': 'Contract ended'}
NOTICE = re.compile(r'(\*\*[^*]+\*\* (ended the contract|wants to schedule[^\n]*))|accepted your offer', re.I)


def write_json(target, record):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, prefix='.thread-', delete=False) as handle:
        temp = pathlib.Path(handle.name)
        json.dump(record, handle, indent=2, ensure_ascii=False)
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def clean(text):
    text = html.unescape(WRAPPER.sub('', text or '')).strip()
    return re.sub(r'\\([.\-*_#()\[\]])', r'\1', text)


def normalize(items):
    """Raw list_messages edges or already clean messages in, clean messages out, oldest first."""
    out, seen = [], set()
    for item in items or []:
        node = item.get('node', item) if isinstance(item, dict) else {}
        if 'createdDateTime' in node or 'from_side' in node:
            text = clean(node.get('message'))
            event = SYSTEM_EVENT.match(text)
            kind = 'event' if event or NOTICE.search(text) else 'message'
            if event:
                text = EVENT_WORDS.get(event.group(1), f'Upwork: {event.group(1)}')
            elif kind == 'event':
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text).replace('Please check your offers for details.', '').strip()
            side = 'me' if node.get('from_self') or node.get('from_side') == 'freelancer' else 'client'
            message = {'id': node.get('id'), 'from': 'system' if kind == 'event' else side,
                       'name': clean(node.get('from')), 'at': node.get('createdDateTime'), 'text': text, 'kind': kind}
        else:
            message = {**node, 'kind': node.get('kind', 'message')}
        key = message.get('id') or (message.get('at'), message.get('text'))
        if key in seen:
            continue
        seen.add(key)
        out.append(message)
    out.sort(key=lambda m: str(m.get('at') or ''))
    return out


def edges_of(raw):
    """Accepts the whole list_messages response, its edges, or a plain list."""
    if isinstance(raw, list):
        return raw
    data = raw.get('data', raw)
    return ((data.get('roomStories') or {}).get('edges')) or data.get('messages') or []


def confirmed_message(raw, outbox):
    """A same-text historical message is not evidence that this send landed."""
    try:
        approved = datetime.datetime.fromisoformat(outbox['written_at'].replace('Z', '+00:00'))
        approved = approved.astimezone(datetime.timezone.utc).replace(microsecond=0)
    except (KeyError, TypeError, ValueError):
        return None
    known = set(outbox.get('known_message_ids') or [])
    for edge in edges_of(raw):
        node = edge.get('node', edge)
        message = normalize([edge])[0]
        if (message.get('from') != 'me' or message.get('kind') != 'message'
                or not message.get('id') or message['id'] in known):
            continue
        try:
            stamp = datetime.datetime.fromisoformat(message['at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp < approved:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        # Decode transport wrapping without trimming the member's whitespace.
        text = node.get('message') if 'message' in node else node.get('text', '')
        wrapped = re.fullmatch(r'<untrusted_participant_content>\n?(.*?)\n?</untrusted_participant_content>', text, re.S)
        candidates = [text]
        if wrapped:
            decoded = html.unescape(wrapped.group(1))
            candidates.extend([decoded, re.sub(r'\\([.\-*_#()\[\]])', r'\1', decoded)])
        if outbox.get('text') in candidates:
            return message
    return None


def save(job_id, raw, room_id=None, awaiting=None):
    folder = pipeline.jobs_dir() / job_id
    folder.mkdir(parents=True, exist_ok=True)
    messages = normalize(edges_of(raw))
    record = {'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'room_id': room_id, 'awaiting_reply_from': awaiting, 'messages': messages}
    write_json(folder / 'thread.json', record)
    # A later read can resolve a successful send whose original confirmation
    # failed. Absence is never used to release an approval automatically.
    outbox_file = folder / 'outbox.json'
    try:
        outbox = json.loads(outbox_file.read_text(encoding='utf-8'))
        matched = confirmed_message(raw, outbox) if outbox.get('room_id') == room_id else None
        if matched and not outbox.get('confirmed_at') and not outbox.get('cancelled_at'):
            outbox.update(confirmed_at=record['fetched_at'], confirmed_message_id=matched['id'])
            write_json(outbox_file, outbox)
    except (OSError, json.JSONDecodeError):
        pass
    return messages


def cmd_save(args):
    if not any(j.get('id') == args.job_id for j in pipeline.load()):
        print(f'ABORT: job "{args.job_id}" is not in the pipeline.', file=sys.stderr)
        return 1
    raw = json.loads(sys.stdin.read() if args.file == '-' else pathlib.Path(args.file).read_text(encoding='utf-8'))
    messages = save(args.job_id, raw, args.room, args.awaiting)
    events = sum(1 for m in messages if m['kind'] == 'event')
    print(f'{args.job_id}: {len(messages) - events} messages and {events} events saved.')
    return 0


def cmd_confirm(args):
    """Save the post-send room read and remove its fixed, hidden transfer file."""
    if not any(j.get('id') == args.job_id for j in pipeline.load()):
        print(f'ABORT: job "{args.job_id}" is not in the pipeline.', file=sys.stderr)
        return 1
    transfer = pipeline.jobs_dir() / args.job_id / '.thread-confirm.json'
    if not transfer.is_file():
        print('ABORT: the confirmed room response is missing.', file=sys.stderr)
        return 1
    raw = json.loads(transfer.read_text(encoding='utf-8'))
    messages = normalize(edges_of(raw))
    outbox_file = pipeline.jobs_dir() / args.job_id / 'outbox.json'
    try:
        outbox = json.loads(outbox_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        print('ABORT: the approved outbox is missing.', file=sys.stderr)
        return 1
    if str(outbox.get('room_id') or '') != args.room:
        print('ABORT: the confirmed room does not match the approved outbox.', file=sys.stderr)
        return 1
    matched = confirmed_message(raw, outbox)
    if not matched:
        print('ABORT: a new message with the exact approved text was not found. Check Upwork before retrying.', file=sys.stderr)
        return 1
    messages = save(args.job_id, raw, args.room, args.awaiting)
    outbox['confirmed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    outbox['confirmed_message_id'] = matched['id']
    write_json(outbox_file, outbox)
    transfer.unlink()
    events = sum(1 for m in messages if m['kind'] == 'event')
    print(f'{args.job_id}: {len(messages) - events} messages and {events} events confirmed and saved.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('save', help='Save one client thread for the cockpit.')
    p.add_argument('job_id')
    p.add_argument('--file', required=True, help='The list_messages response as JSON. "-" reads stdin.')
    p.add_argument('--room', help='The room id, so a reply can find its way back.')
    p.add_argument('--awaiting', choices=('you', 'them'), help="The room card's awaiting_reply_from.")
    p.set_defaults(func=cmd_save)
    p = sub.add_parser('confirm', help='Save the fixed post-send room response and remove the transfer file.')
    p.add_argument('job_id')
    p.add_argument('--room', required=True, help='The room id used for the send.')
    p.add_argument('--awaiting', choices=('you', 'them'), required=True)
    p.set_defaults(func=cmd_confirm)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
