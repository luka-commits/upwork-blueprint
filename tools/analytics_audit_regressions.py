#!/usr/bin/env python3
"""Audit privacy and review regressions, with synthetic sources and isolated ledgers."""
import copy
import datetime as dt
import json
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import fixture, seed, record, records, run, analytics_sync_marker, EXAMPLE_CALL_READ
import analytics


def refused(action, label):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Unsafe public value accepted: ' + label)


def privacy_contract():
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    with fixture('audit-privacy') as folder:
        card = analytics.compute(today, jobs=[], now=now)['community_card']
        assert analytics.validate_community_card(copy.deepcopy(card), [])
        sources = [{'title': 'Migration Specialist Needed', 'company': 'Acme Corporation',
                    'client_name': 'Secret Client', 'aliases': ['Scarlet Partners'],
                    'quote': 'We have a hidden budget for the internal launch',
                    'messages': [{'text': 'The ivory workflow is confidential'}]}]
        # Every measured bypass from r-privacy, including both root and canonical paths.
        unsafe = ('What did Acme Corporation request?', 'What did acme, corporation request?',
                  'What did Secret, Client request?', 'Can migration work better?',
                  'What is the hidden budget?', 'What did the ivory workflow show?',
                  'What did scarlet partners request?', 'Can I charge $200/hour?',
                  'Can I ask for euros?', 'Can I work hourly?', 'Can cad work?',
                  'Can aud work?', 'Can chf work?', 'Can I ask for rupees?',
                  'Can I ask for ₿?', 'Can ٢ changes help?', 'Can ２ changes help?', 'Can ² changes help?', 'Can ② changes help?',
                  'Can Ⅳ changes help?', 'Can hiddenBudget help?', 'Can secretClient help?',
                  'Can I charge per-hour?', 'Can I use kWh?', 'Can I use pixels?', 'Should I visit example.com?',
                  'Should I visit https://example.com?', 'Should I visit www.example.com?',
                  'Should I use mailto:client@example.com?', 'Can 2 changes help?',
                  'What helps Quality improve?', 'What helps today with kg?',
                  ' '.join(['word'] * 15))
        for question in unsafe:
            candidate = copy.deepcopy(card)
            candidate['question'] = question
            assert analytics.validate_community_card(candidate, sources)['question'] is None, question
            assert analytics.validated_community({'question': question}, sources)['question'] is None, question
            snap = {'community_card': copy.deepcopy(card), 'community': {'question': question}}
            assert analytics.snapshot_public_card(snap, sources)['question'] is None, question
        own = folder / 'jobs/991999999'; own.mkdir()
        (own / 'call.md').write_text('Member: Maya\nComplete: yes\nMaya: My blue, ribbon promise is private.\nClient: Agreed.\n')
        assert not analytics.safe_public_text('What was the blue ribbon promise?', [])
        assert not analytics.safe_public_text('What was the blue, ribbon promise?', [])
        for question in ("What helped you improve this stage?", 'How can I answer on Upwork?',
                         ' '.join(['word'] * 14)):
            assert analytics.safe_public_text(question, sources), question
            safe = copy.deepcopy(card); safe['question'] = question
            assert analytics.validate_community_card(safe, sources)['question'] == question
        # A library prefix alone and a copied history entry authorize nothing.
        legacy_goal = {'text': 'When choosing proof → use one', 'done': False, 'k': 0,
                       'n': 1, 'state': 'undone'}
        unagreed = copy.deepcopy(card); unagreed['goals'] = [legacy_goal]
        refused(lambda: analytics.validate_community_card(unagreed, []), 'unagreed library prefix')
        goal = {'stage': analytics.LABELS['reply_rate'], 'kpi': 'reply_rate',
                'change': 'Ask Acme Corporation for $200/hour', 'start': '2026-10-01',
                'primary': True, 'cue': 'Before submitting', 'action': 'Use the approved proof',
                'fallback': 'Use one sample', 'review_on': '2026-10-08',
                'goal_library_id': 'reply-proof'}
        analytics.validate_goals({'week': '2026-W40', 'goals': [goal]})
        identity = analytics.goal_id(goal, '2026-W40')
        public_goal = {'goal_id': identity, 'goal_library_id': 'reply-proof',
                       'text': 'Use one relevant proof', 'done': False, 'k': 0,
                       'n': 1, 'state': 'undone'}
        candidate = copy.deepcopy(card); candidate['goals'] = [public_goal]
        refused(lambda: analytics.validate_community_card(copy.deepcopy(candidate), []), 'no agreed ledger')
        (folder / 'data/analytics-history.jsonl').write_text(json.dumps({'week': '2026-W40', 'goals_next': [goal]}) + '\n')
        refused(lambda: analytics.validate_community_card(copy.deepcopy(candidate), []), 'history is not agreement')
        (folder / 'data/goals.jsonl').write_text(json.dumps({'week': '2026-W40', 'goals': [goal]}) + '\n')
        validated = analytics.validate_community_card(copy.deepcopy(candidate), sources)
        markup = analytics.public_onepager_html(validated)
        assert 'Use one relevant proof' in markup and 'Acme' not in markup and '$200/hour' not in markup
        for bypass in ('Ask Acme Corporation for $200/hour', 'Ask Secret, Client about work',
                       'Review Migration', 'Review the hidden budget', 'Visit example.com',
                       'When choosing proof → use one'):
            attack = copy.deepcopy(candidate); attack['goals'][0]['text'] = bypass
            refused(lambda: analytics.validate_community_card(attack, sources), bypass)
        for field, value in (('goal_id', 'unagreed'), ('goal_library_id', 'reply-opener')):
            attack = copy.deepcopy(candidate); attack['goals'][0][field] = value
            refused(lambda: analytics.validate_community_card(attack, sources), field)
        for reason in ('Applications explain the outcome clearly', '$200/hour', 'Secret, Client', 'example.com'):
            attack = copy.deepcopy(card)
            attack['biggest_improvement'] = {'kpi': 'reply_rate', 'from': 10, 'to': 20, 'reason': reason}
            refused(lambda: analytics.validate_community_card(attack, sources), 'arbitrary improvement reason')
        # Rank is an explicit owner decision and stays on the card.
        assert 'Rank: ' + card['rank'] in analytics.public_onepager_html(card)
        for name in ('True North', 'First Doubloon'):
            awarded = copy.deepcopy(card)
            awarded['earned_badges'] = [{'badge': name, 'tier': 'Gold', 'earned_week': card['week'],
                                        'new': True, 'progress_to_next': 'All tiers earned'}]
            markup = analytics.public_onepager_html(awarded)
            assert 'data:image/webp;base64,' in markup and '<small>Gold</small>' in markup, name
        # The recording path cannot substitute snapshot goals for member agreement.
        (folder / 'data/goals.jsonl').unlink()
        (folder / 'data/analytics-history.jsonl').unlink()
        current = analytics.compute(today, jobs=[], now=now)
        current['goals_next'] = [dict(goal, start=today.isoformat(), review_on='2026-10-21')]
        current['report'] = 'The records are missing.'
        current['community_card']['next_focus'] = analytics.LABELS['reply_rate']
        try:
            analytics.record_snapshot(current)
        except ValueError as error:
            assert 'agreed goals' in str(error), error
        else:
            raise AssertionError('Snapshot without agreed goals was recorded')
    print('PASS audit privacy: every reported bypass rejected; ID-only agreed goals; fixed improvement; strict canonical/legacy question; retained rank; every displayed award has an image.')


def review_contract():
    with fixture('audit-review') as folder:
        jid = '991000001'; home = folder / 'jobs' / jid; home.mkdir()
        quote = 'Please confirm who supplies the inputs.'
        finding = 'Confirm who supplies the inputs before agreeing a date'
        (home / 'application.sent.md').write_text(quote)
        (home / 'proposal.md').write_text(quote)
        (home / 'thread.json').write_text(json.dumps({'messages_complete': True, 'messages': [
            {'from': 'client', 'at': '2026-10-12T10:00:00+02:00', 'text': quote}]}))
        points = {key: {'state': 'partly', 'quote': quote, 'reason': finding} for key in analytics.CONVERSATION_POINTS}
        saved = {'read': True, 'reviewable': True, 'quote': quote, 'key_finding': finding,
                 'points': points, 'free_read': 'My read is that ownership needs clarification.'}
        job = {'id': jid, 'title': 'Reporting audit', 'applied_at': '2026-10-12T09:00:00+02:00',
               'replied_at': '2026-10-12T10:00:00+02:00', 'proposal_sent_at': '2026-10-12T12:00:00+02:00',
               'application_sent_verified': True, 'application_review': saved,
               'conversation_review': saved, 'proposal_review': saved}
        snapshot = {'generated_at': '2026-10-14T15:00:00+02:00', 'reviews': {}, 'call_cards': []}
        projected = analytics.conversations_fields(snapshot, [job])['sections']
        assert 'duplicate_of_stage' not in projected['applications'][0]
        assert projected['chats'][0]['duplicate_of_stage'] == 'applications'
        assert projected['proposals'][0]['duplicate_of_stage'] == 'applications'
        threads = analytics.conversation_reviews([job], dt.date(2026, 10, 14))['threads']
        assert tuple(threads[0]['points']) == ('answered_question', 'qualifying_question', 'call_times')
        assert not any('speed' in name or 'follow' in name for name in threads[0]['points'])
        missing = dict(job, id='991000002', call_held_at='2026-10-12T13:00:00+02:00')
        card = analytics.call_cards(snapshot, [missing])[0]
        assert not card['reviewable'] and card['reason'].startswith('Not reviewed.')
        assert '991000002/call.md' in card['source_prompt'] and '/call-review 991000002' in card['source_prompt']
        full = folder / 'jobs/991000002'; full.mkdir()
        (full / 'call.md').write_text('Member: Maya\nComplete: yes\nMaya: What do you need?\nClient: A full audit.\n')
        absent_review = analytics.call_cards(snapshot, [missing])[0]
        assert absent_review['reason'] == 'Not reviewed. Call review missing.'
        assert absent_review['source_prompt'].startswith('Run /call-review ') and 'Paste' not in absent_review['source_prompt']
        transcript = 'Call at: 2026-10-12T13:00:00+02:00\nClient: [06:12] Can we start with the booking page only?\nMember: [07:03] I will prepare the proposal for Friday.\n'
        assert analytics.call_quote_time('Can we start with the booking page only?', transcript) == '06:12'
        assert analytics.call_quote_time('I will prepare the proposal for Friday.', transcript) == '07:03'
        assert analytics.call_quote_time('Missing quote', transcript) is None
        assert analytics.call_quote_time('Can we start?', 'Call at: 2026-10-12T13:00:00+02:00\nClient: Can we start?') is None
    assert hashlib.sha256((analytics.ROOT / 'references/coach-brief.md').read_bytes()).hexdigest() == '0ed3ef00f15d82625858efb464b68e2d55656344654d57f7c4b7acda064d7044'
    print('PASS audit reviews: repeated finding tagged after first stage; exactly three content checks; missing transcript not graded; quote times from recorded turns; final brief byte-identical.')


def once_review_contract():
    with fixture('audit-call-once') as folder:
        analytics_sync_marker(folder)
        jid = '991000010'; quote = 'We will review the proposal on Friday.'
        seed({'id': jid, 'source': 'outbound', 'status': 'call',
              'call_held_at': '2026-10-12T10:00:00+02:00'})
        home = folder / 'jobs' / jid; home.mkdir()
        (home / 'call.md').write_text('Member: Maya\nComplete: yes\nLanguage: English\nMaya: [02:03] Who reviews this?\nClient: [02:10] ' + quote + '\n')
        (home / 'call-review.md').write_text("## Coach's read\n\n" + EXAMPLE_CALL_READ + '\n\n## Next message\n\nThanks. I will prepare the agreed proposal for Friday.\n\n## Agreed step\n\n' + quote + '\n')
        first = {'reviewable': True, 'points': [{'point': n, 'state': 'met', 'quote': quote} for n in range(1, 10)],
                 'moments': [{'quote': quote, 'better_wording': 'Confirm who reviews the proposal.'}],
                 'fix': 'Confirm the reviewer', 'example': 'Who reviews the proposal?',
                 'free_read': EXAMPLE_CALL_READ, 'next_message': 'Thanks. I will prepare the agreed proposal for Friday.',
                 'next_step': quote, 'agreed_step': quote}
        record(jid, {'call_review': first})
        first_job = copy.deepcopy(records()[jid])
        before = json.loads(run('cockpit.py', 'job', jid).stdout)['call_cards'][0]
        second = copy.deepcopy(first)
        second['points'][0]['state'] = 'partly'
        second['fix'] = 'A different valid read must not replace the first'
        record(jid, {'call_review': second})
        saved = records()[jid]
        # A changed markdown companion cannot substitute a second judgment for
        # canonical coaching already stored by the sole writer.
        (home / 'call-review.md').write_text("## Coach's read\n\n" + 'Changed ' * 120 + '\n\n## Next message\n\nA different next message.\n')
        assert saved['call_review'] == first == first_job['call_review']
        assert saved['call_reviewed_at'] == first_job['call_reviewed_at']
        after = json.loads(run('cockpit.py', 'job', jid).stdout)['call_cards'][0]
        assert before == after, 'Immediate card must reuse the identical first judgment'
        snapshot = analytics.compute(dt.date(2026, 10, 14), now='2026-10-14T15:00:00+02:00')
        card = snapshot['call_cards'][0]
        assert [dict(point=n['point'], state=n['state'], quote=n['quote']) for n in card['points']] == first['points']
        assert card['coach_read'] == before['coach_read'] == EXAMPLE_CALL_READ
        assert card['next_message'] == before['next_message'] == first['next_message']
        assert card['reviewed_at'] == before['reviewed_at'] == first_job['call_reviewed_at']
        assert all(point['quote_at'] == '02:10' for point in card['points'])
        # Reused coaching remains immutable even if a later valid record says unreviewable.
        record(jid, {'call_review': {'reviewable': False, 'points': []}})
        assert records()[jid]['call_review'] == first
    print('PASS audit once-only call: second complete valid review reuses first exact rubric/date; immediate cockpit and weekly card identical; unreviewable input cannot erase it.')


def run_all():
    privacy_contract()
    review_contract()
    once_review_contract()


if __name__ == '__main__':
    run_all()
