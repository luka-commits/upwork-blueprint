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

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)

WRAPPER = re.compile(r'</?untrusted_participant_content>')
SYSTEM_EVENT = re.compile(r'^System event: (\w+)\.')
# Only the event whose meaning the room card confirms gets a plain name; the rest
# stay as Upwork says them rather than as a guess.
EVENT_WORDS = {'ended': 'Contract ended'}
NOTICE = re.compile(r'(\*\*[^*]+\*\* (ended the contract|wants to schedule[^\n]*))|accepted your offer', re.I)


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


def save(job_id, raw, room_id=None, awaiting=None):
    folder = pipeline.jobs_dir() / job_id
    folder.mkdir(parents=True, exist_ok=True)
    messages = normalize(edges_of(raw))
    record = {'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'room_id': room_id, 'awaiting_reply_from': awaiting, 'messages': messages}
    (folder / 'thread.json').write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
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
    messages = save(args.job_id, raw, args.room, args.awaiting)
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
