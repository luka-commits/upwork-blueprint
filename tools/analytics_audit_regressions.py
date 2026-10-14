#!/usr/bin/env python3
"""Audit privacy and review regressions, with synthetic sources and isolated ledgers."""
import copy
import datetime as dt
import json
import hashlib
import pathlib
import sys
import re
import struct
import html
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import run_checks, fixture, seed, record, records, run, analytics_sync_marker, EXAMPLE_CALL_READ, analytics_payload
import analytics

R2_PRIVACY_PROBES = (
    'Acme Corporation', 'What did acmecorporation request?', 'Secret, Client',
    'Migration', 'secretclient', 'migrationspecialistneeded', 'hiddenbudget',
    'ivoryworkflow', '$200/hour', 'Can I charge two hundred each session?',
    'Is two hundred a fair fee?', 'example.com', 'example[.]com', 'example dot com',
    'example。com', 'example．com', 'a\u200bcme', 'ivory workflow',
    'What did ivory workflow mean?', 'employer', 'client_slug',
    'What about "keep the launch secret"?', 'Upwork', 'Upwork Blueprint',
    'unknown lowercase company', 'unknown confidential phrase',
)

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
            assert analytics.validate_community_card(candidate, sources)['question_id'] is None, question
            assert analytics.validated_community({'question': question}, sources)['question_id'] is None, question
            snap = {'community_card': copy.deepcopy(card), 'community': {'question': question}}
            assert analytics.snapshot_public_card(snap, sources)['question_id'] is None, question
        own = folder / 'jobs/991999999'; own.mkdir()
        (own / 'call.md').write_text('Member: Maya\nComplete: yes\nMaya: My blue, ribbon promise is private.\nClient: Agreed.\n')
        assert not analytics.safe_public_text('What was the blue ribbon promise?', [])
        assert not analytics.safe_public_text('What was the blue, ribbon promise?', [])
        for question in ('reply_rate-1', 'reply_rate-2'):
            safe = copy.deepcopy(card); safe['question_id'] = question
            assert analytics.validate_community_card(safe, sources)['question_id'] == question
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
        assert 'Rank: ' + card['rank'] in analytics.public_onepager_html(card)
        for name in ('True North', 'First Doubloon'):
            awarded = copy.deepcopy(card)
            awarded['earned_badges'] = [{'badge': name, 'tier': 'Gold', 'earned_week': card['week'],
                                        'new': True, 'progress_to_next': 'All tiers earned'}]
            markup = analytics.public_onepager_html(awarded)
            assert 'data:image/webp;base64,' in markup and '<small>Gold</small>' in markup, name
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
        record(jid, {'call_review': {'reviewable': False, 'points': []}})
        assert records()[jid]['call_review'] == first

def closed_question_entries():
    today = dt.date(2026, 10, 14); now = '2026-10-14T15:00:00+02:00'
    with fixture('closed-question-entries') as folder:
        analytics_sync_marker(folder)
        base = analytics_payload(analytics.compute(today, jobs=[], now=now))
        base = analytics.prepare_snapshot(base, today, now=now)
        sources = [{'title': 'Migration Specialist Needed', 'company': 'Acme Corporation',
                    'client_name': 'Secret, Client', 'employer': 'private employer',
                    'client_slug': 'private slug', 'quote': 'hidden budget',
                    'messages': [{'body': 'ivory workflow'}]}]
        def capture(args, **kwargs):
            target = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--screenshot='))
            pathlib.Path(target).write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 1080, 1350))
            return __import__('subprocess').CompletedProcess(args, 0, '', '')
        clean=analytics.public_onepager_html(dict(base['community_card'],question_id=None))
        def no_injection(markup,probe,clean_template=clean):
            assert html.unescape(markup).casefold().count(probe.casefold()) <= html.unescape(clean).casefold().count(probe.casefold()),probe
            assert markup==clean_template, ('Private input changed public template',probe)
        for probe_index,probe in enumerate(R2_PRIVACY_PROBES):
            for field in ('question', 'question_id'):
                card = copy.deepcopy(base['community_card']); card['question_id'] = None; card[field] = probe
                checked = analytics.validate_community_card(copy.deepcopy(card), sources)
                assert checked['question_id'] is None and 'question' not in checked, (field, probe)
                direct = analytics.public_onepager_html(card)
                canary=f'PRIVATECANARY{probe_index}{field}'
                attack=copy.deepcopy(card);attack[field]=probe+' '+canary
                canary_output=analytics.public_onepager_html(attack)
                assert canary not in canary_output and canary not in html.unescape(canary_output)
                no_injection(canary_output,probe)
                no_injection(direct,probe)
                assert html.unescape(direct).casefold().count(probe.casefold()) <= html.unescape(clean).casefold().count(probe.casefold()), (field, probe)
                assert '<p class="question">' not in direct
                assert '<footer><span>Upwork Blueprint' in direct
                canonical = analytics.validated_community({field: probe}, sources)
                assert canonical == {'question_id': None}
                for overlay in ({'community_card': {'next_focus': analytics.LABELS['reply_rate'], field: probe}},
                                {'community': {field: probe}}):
                    result = copy.deepcopy(base); result['community_card']['question_id'] = None
                    analytics.claude_fields(result, overlay)
                    assert result['community_card']['question_id'] is None
                    rendered=analytics.public_onepager_html(analytics.snapshot_public_card(result,sources))
                    assert html.unescape(rendered).casefold().count(probe.casefold()) <= html.unescape(clean).casefold().count(probe.casefold()), (field,probe)
                    control=copy.deepcopy(base);control['community_card']['question_id']=None
                    clean_overlay=copy.deepcopy(overlay)
                    for inner in clean_overlay.values():inner[field]=None
                    analytics.claude_fields(control,clean_overlay)
                    clean_overlay_html=analytics.public_onepager_html(analytics.snapshot_public_card(control,sources))
                    no_injection(rendered,probe,clean_overlay_html)
                    assert '<p class="question">' not in rendered
                imported = copy.deepcopy(base); imported['community_card'] = copy.deepcopy(card)
                imported['community'] = {field: probe}
                assert analytics.snapshot_public_card(imported, sources)['question_id'] is None
                legacy = copy.deepcopy(imported); legacy.pop('community')
                assert analytics.snapshot_public_card(legacy, sources)['question_id'] is None
                prepared = analytics.prepare_snapshot(imported, today, now=now)
                analytics.record_snapshot(imported, replace=True)
                ledger = analytics.read_lines('analytics-history.jsonl')[-1]
                assert ledger['community_card']['question_id'] is None
                assert 'question' not in ledger['community_card']
                assert ledger.get('community', {}).get('question_id') is None
                assert 'question' not in ledger.get('community', {})
                for payload in (json.dumps(imported), json.dumps(legacy) + '\n' + json.dumps(imported) + '\n'):
                    src = folder / 'import.json'; src.write_text(payload)
                    with mock.patch.object(analytics.subprocess, 'run', side_effect=capture):
                        exported = analytics.onepager(str(src), output=str(folder / 'card.html'))
                    output = pathlib.Path(exported['html']).read_text()
                    assert html.unescape(output).casefold().count(probe.casefold()) <= html.unescape(clean).casefold().count(probe.casefold()), (field, probe)
                    control=copy.deepcopy(base);control['community_card']['question_id']=None
                    clean_export=analytics.public_onepager_html(analytics.snapshot_public_card(control,sources))
                    no_injection(output,probe,clean_export)
                    assert '<p class="question">' not in output
        counts = {}
        for ident, (stage, text) in analytics.PUBLIC_QUESTION_TEMPLATES.items():
            counts[stage] = counts.get(stage, 0) + 1
            assert len(text.split()) <= 14
            card = copy.deepcopy(base['community_card'])
            card.update(question_id=ident, next_focus=analytics.LABELS[stage])
            assert analytics.public_question_text(card) == text
            assert '<p class="question">' in analytics.public_onepager_html(card)
            card['next_focus'] = 'not a focus'
            assert analytics.public_question_text(card) is None
        assert all(2 <= count <= 3 for count in counts.values())

def approximate_number_contract():
    with fixture('approximate-numbers'):
        snapshot = analytics.compute(dt.date(2026, 10, 14), jobs=[], now='2026-10-14T15:00:00+02:00')
        for phrase, number in (('a dozen',12), ('dozen',12), ('a couple of',2), ('a pair of',2), ('a couple',2), ('a pair',2),
                               ('half a dozen',6), ('half-dozen',6), ('a hundred',100), ('two hundred',200)):
            assert analytics.report_number_value(phrase) == number
            text = 'You won ' + phrase + ' contracts this week.'
            negative = analytics.check_report(text, snapshot)
            assert negative['status'] == 'FAIL' and len(negative['errors']) == 1, (phrase,negative)
            with mock.patch.object(analytics, 'report_numeric_facts', return_value={'wins': number}):
                positive = analytics.check_report(text, snapshot)
            assert positive['status'] == 'PASS' and positive['checked_values'] == 1, (phrase,positive)
        for phrase in ('hundreds', 'hundreds of', 'several hundreds of', 'two hundreds of', 'many hundreds'):
            assert analytics.check_report('You won ' + phrase + ' contracts this week.', snapshot)['status'] == 'FAIL'

def distinct_call_contract():
    for meeting in (True, False):
        with fixture('distinct-call') as folder:
            analytics_sync_marker(folder)
            jid = '991000031'; seed({'id':jid, 'source':'outbound', 'status':'call', 'call_held_at':'2026-10-12T10:00:00+02:00'})
            home = folder / 'jobs' / jid; home.mkdir()
            original = None
            saved_sessions = {}
            for index in (1,2):
                quote = 'We agree the next step for session ' + str(index) + '.'
                (home / 'call.md').write_text('Call at: 2026-10-' + str(11 + index) + 'T10:00:00+02:00\nMember: Maya\nComplete: yes\nLanguage: English\nMaya: What happens next?\nClient: ' + quote + '\n')
                review = {'reviewable':True, 'points':[{'point':n,'state':'met','quote':quote} for n in range(1,10)],
                          'free_read':EXAMPLE_CALL_READ, 'next_message':'Please confirm the next step.', 'agreed_step':quote}
                metadata = {'call_review':review}
                if meeting:
                    metadata.update(call_session_id='verified-meeting-' + str(index),
                                    call_sessions={**saved_sessions, 'verified-meeting-' + str(index): {'held_at': '2026-10-' + str(11 + index) + 'T10:00:00+02:00'}})
                record(jid, metadata)
                saved = records()[jid]
                saved_sessions = saved.get('call_sessions', {})
                if index == 1: original = copy.deepcopy(saved)
                assert saved['call_review'] == review
                immediate = json.loads(run('cockpit.py','job',jid).stdout)['call_cards'][0]
                assert immediate['points'][0]['quote'] == quote
                assert immediate['date'] == '2026-10-' + str(11 + index)
                weekly = analytics.compute(dt.date(2026,10,14), now='2026-10-14T15:00:00+02:00')['call_cards'][0]
                assert weekly['points'][0]['quote'] == quote
                assert weekly['date'] == immediate['date']
                second = copy.deepcopy(review); second['points'][0]['state'] = 'partly'
                record(jid, {'call_review':second})
                assert records()[jid]['call_review'] == review
            saved = records()[jid]
            assert len(saved['call_reviews']) == 2
            historical = saved['call_reviews'][original['call_review_session']]
            assert historical['review'] == original['call_review'] and historical['reviewed_at'] == original['call_reviewed_at']

def legacy_session_contract():
    with fixture('legacy-context-first') as folder:
        analytics_sync_marker(folder)
        jid = '991000041'; home = folder / 'jobs' / jid; home.mkdir()
        (home / 'call-review.md').write_text('## Agreed step\n\nFirst call agreement.\n')
        def review(quote):
            return {'reviewable': True, 'points': [{'point': n, 'state': 'met', 'quote': quote} for n in range(1, 10)],
                    'free_read': EXAMPLE_CALL_READ, 'next_message': 'Please confirm.', 'agreed_step': quote}
        first = review('First call agreement.'); second = review('Second distinct call agreement.')
        exact = '2026-10-12T14:22:33+00:00'
        seed({'id': jid, 'status': 'call', 'source': 'outbound', 'call_review': first,
              'call_reviewed_at': exact, 'call_held_at': '2026-10-12T10:00:00+02:00',
              'call_sessions': {'first': {'held_at': '2026-10-12T10:00:00+02:00'},
                                'second': {'held_at': '2026-10-13T10:00:00+02:00'},
                                'third': {'held_at': '2026-10-14T10:00:00+02:00'}, 'unverified': {}}})
        record(jid, {'call_session_id': 'second'})
        saved = records()[jid]
        assert saved['call_reviews']['legacy:first']['review'] == first
        assert saved['call_reviews']['legacy:first']['reviewed_at'] == exact
        assert 'call_review' not in saved and 'call_review_session' not in saved
        for index, payload in ((2, second), (1, first)):
            session = 'second' if index == 2 else 'first'
            (home / 'call.md').write_text('Call at: 2026-10-' + str(11+index) + 'T10:00:00+02:00\nMember: Maya\nComplete: yes\nLanguage: English\nMaya: What happens next?\nClient: ' + payload['agreed_step'] + '\n')
            record(jid, {'call_review': payload} if index == 2 else {'call_session_id': session, 'call_review': payload})
        first_saved = copy.deepcopy(records()[jid])
        record(jid, {'call_session_id': 'second'})
        saved = records()[jid]; second_time = saved['call_reviewed_at']
        assert saved['call_review'] == second and saved['call_review_session'] == 'meeting:second'
        assert second_time == saved['call_reviews']['meeting:second']['reviewed_at']
        card = json.loads(run('cockpit.py', 'job', jid).stdout)['call_cards'][0]
        assert card['date'] == '2026-10-13'
        assert card['points'][0]['quote_state'] == 'unknown' and 'quote' not in card['points'][0]
        assert saved['call_review']['points'][0]['quote'] == second['agreed_step']
        record(jid, {'call_session_id': 'first'})
        assert records()[jid]['call_review'] == first
        assert records()[jid]['call_reviewed_at'] == first_saved['call_reviewed_at']
        record(jid, {'call_session_id': 'third'})
        assert 'call_review' not in records()[jid] and 'call_review_session' not in records()[jid]
        card = json.loads(run('cockpit.py', 'job', jid).stdout)['call_cards'][0]
        assert not card['reviewable'] and not card['points'] and card['coach_read'] is None
        (home / 'call-review.md').unlink()
        import cockpit
        stale_card = dict(card, reviewable=True, points=first['points'], coach_read=EXAMPLE_CALL_READ)
        with mock.patch.object(cockpit, 'analytics_state', return_value={'latest': {'call_cards': [stale_card]}, 'errors': [], 'status': 'fresh'}):
            cleared = cockpit.job_view(jid)['call_cards'][0]
        assert not cleared['reviewable'] and not cleared['points'] and cleared['coach_read'] is None
        for invalid in ('does-not-exist', 'unverified'):
            before = (folder / 'data/jobs.json').read_bytes()
            for extra in ({}, {'call_review': first}):
                result = run('pipeline.py', 'record', jid, '--file', '-', value={'call_session_id': invalid, **extra}, success=False)
                assert result.returncode != 0
                assert (folder / 'data/jobs.json').read_bytes() == before
        assert records()[jid]['call_reviews']['legacy:first']['reviewed_at'] == exact

def report_identifier_contract():
    with fixture('report-identifiers') as folder:
        analytics_sync_marker(folder)
        snapshot = analytics.compute(dt.date(2026, 10, 14), jobs=[], now='2026-10-14T15:00:00+02:00')
        assert snapshot['north_star']['wins'] == 0
        references = (
            'job 2018814616722536175', 'Reference 2018814616722536175',
            'Reference 123456789012', 'Use `3`', 'Use `won 3 contracts`', 'Use ``value `3` here``',
            'See https://www.upwork.com/jobs/123?offset=3', 'See www.example.com/3',
            'See /tmp/reports/3.md', 'See ./reports/3.md', 'See ../reports/3.md',
            'See ~/reports/3.md', 'See jobs/123/application.sent.md',
            'See C:\\reports\\3.md', 'See report-3.md', 'See /tmp/2026/10/report-3.json',
            'See reports/2026/10/report-3.json', 'See analytics-2026-10-14.json',
            'See 123.json', 'See 2026/10/report-3.json', 'See 2026\\10\\report-3.json',
            'Saved 2026-10-14', 'Saved 2026-10-14T15:30:12+02:00',
            'Saved 2026-10-14T15:30:12.123Z', 'Saved 15:30', 'Saved 15:30:12+02:00',
            'job 123', 'job ID 123', 'id 123', '#123', 'JOB ID: 123', 'job **123**',
        )
        for reference in references:
            checked = analytics.check_report(reference, snapshot)
            assert checked['status'] == 'PASS' and checked['checked_values'] == 0, (reference, checked)
            for claim, expected in (('You won 0 contracts.', 'PASS'),
                                    ('You won 3 contracts.', 'FAIL')):
                for report in (reference + '; ' + claim, claim + ' ' + reference):
                    checked = analytics.check_report(report, snapshot)
                    assert checked['status'] == expected and checked['checked_values'] + len(checked['errors']) == 1, (report, checked)
        zero = analytics.check_report('You won 0 contracts.', snapshot)
        assert zero['status'] == 'PASS' and zero['checked_values'] == 1, zero
        for claim in ('You won 3 contracts', 'Unverified value 3', 'Unverified value 12345678901',
                      'paid 3', 'grid 3', 'valid 3', 'Unverified ratio 3/4',
                      'You won three contracts this week.', 'You won $3 this week.', 'Reply rate 3%'):
            assert analytics.check_report(claim, snapshot)['status'] == 'FAIL', claim

def custom_coverage_contract():
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    with fixture('custom-coverage') as folder:
        analytics_sync_marker(folder)
        base = analytics.prepare_snapshot({}, today, now=now)
        gaps = [
            {'source': 'proposal_insights', 'what': 'Proposal insights unavailable', 'blocks': ['proposal_views'], 'how_to_supply': 'Supply proposal insights export.'},
            {'source': 'offers_pagination', 'what': 'Offers limited to the first page', 'blocks': ['proposal_to_won'], 'how_to_supply': 'Supply every page of offers.'},
            {'source': 'older_chats', 'what': 'Older chats unread', 'blocks': ['conversation_review'], 'how_to_supply': 'Supply the complete older chat threads.'},
            {'source': 'hourly_hours', 'what': 'Hourly hours unknown', 'blocks': ['won_value', 'forecast'], 'how_to_supply': 'Supply agreed hourly contract hours.'},
        ]
        snapshot = analytics.prepare_snapshot({'coverage': {'missing': gaps}}, today, now=now)
        for row in gaps:
            assert row in snapshot['coverage']['missing'], row
            assert row in analytics.facts_sheet(snapshot)['coverage']['missing'], row
        assert snapshot['coverage']['sources'][:6] == base['coverage']['sources'], 'Six known sources retain their wording and dependencies.'
        assert [row for row in snapshot['coverage']['missing'] if row['source'] in {source['source'] for source in base['coverage']['sources']}] == base['coverage']['missing']
        assert all(set(row) == {'source', 'blocks', 'how_to_supply'} for row in base['coverage']['missing'])
        assert len(base['coverage']['sources']) == 6
        for source in base['coverage']['sources']:
            canonical = dict(source=source['source'], what='Source unavailable',
                             blocks=source['affects'], how_to_supply=source['fix'])
            legacy = dict(source=source['source'], state='missing', affects=source['affects'], fix=source['fix'])
            expected = analytics.prepare_snapshot({'coverage': [legacy]}, today, now=now)['coverage']
            three_field = {key: value for key, value in canonical.items() if key != 'what'}
            for row in (canonical, three_field):
                for coverage in ([row], {'missing': [row]}):
                    accepted = analytics.prepare_snapshot({'coverage': coverage}, today, now=now)['coverage']
                    assert accepted == expected, source['source']
                    assert all('what' not in gap for gap in accepted['missing']), source['source']
                    assert all('what' not in row for row in accepted['sources']), source['source']
            for invalid in ('', ' ', None, 3, [], {}):
                broken = dict(canonical, what=invalid)
                for coverage in ([broken], {'missing': [broken]}):
                    refused(lambda: analytics.prepare_snapshot({'coverage': coverage}, today, now=now), 'known invalid what ' + source['source'])
            overridden = dict(canonical, blocks=source['affects'] + ['dependency_override'])
            for coverage in ([overridden], {'missing': [overridden]}):
                refused(lambda: analytics.prepare_snapshot({'coverage': coverage}, today, now=now), 'known computed dependencies ' + source['source'])
        for key in ('proposal_to_won', 'conversation_review', 'won_value'):
            assert snapshot['kpis'][key]['state'] == 'missing' and snapshot['kpis'][key]['value'] is None, key
        replayed = analytics.prepare_snapshot(snapshot, today, now=now)
        assert replayed['coverage'] == snapshot['coverage'], 'Custom gaps survive snapshot readback/revalidation.'
        legacy = [dict(source=row['source'], state='missing', what=row['what'], affects=row['blocks'], fix=row['how_to_supply']) for row in gaps]
        for coverage in (gaps, legacy, {'sources': base['coverage']['sources'], 'missing': gaps},
                         {'sources': legacy, 'missing': gaps}, base['coverage']['sources'] + gaps):
            assert analytics.prepare_snapshot({'coverage': coverage}, today, now=now)['coverage'] == snapshot['coverage'], coverage
        other = dict(gaps[0], what='Proposal rankings unavailable', blocks=['ranking_review'])
        shared = analytics.prepare_snapshot({'coverage': {'missing': gaps + [other]}}, today, now=now)
        assert [row for row in shared['coverage']['missing'] if row['source'] == 'proposal_insights'] == [gaps[0], other]
        assert analytics.prepare_snapshot(shared, today, now=now)['coverage'] == shared['coverage']
        for field in ('source', 'what', 'blocks', 'how_to_supply'):
            broken = dict(gaps[0]); broken.pop(field)
            for coverage in ([broken], {'missing': [broken]}, {'sources': legacy, 'missing': [gaps[0], broken]}):
                refused(lambda: analytics.prepare_snapshot({'coverage': coverage}, today, now=now), 'missing ' + field)
        for field, values in (('source', ('UpperCase', 'has spaces', 'bad__name', 'x' * 65, '', None, [], {})),
                              ('what', ('', ' ', None, 3, [], {})),
                              ('blocks', ([], '', None, [''], [' '], [3], {})),
                              ('how_to_supply', ('', ' ', None, 3, [], {}))):
            for invalid in values:
                broken = dict(gaps[0]); broken[field] = invalid
                for coverage in ([broken], {'missing': [broken]}):
                    refused(lambda: analytics.prepare_snapshot({'coverage': coverage}, today, now=now), 'invalid ' + field)
        for field in ('what', 'affects', 'fix'):
            broken = dict(legacy[0]); broken.pop(field)
            refused(lambda: analytics.prepare_snapshot({'coverage': [broken]}, today, now=now), 'legacy missing ' + field)
        for state in ('ok', 'unknown'):
            refused(lambda: analytics.prepare_snapshot({'coverage': [dict(legacy[0], state=state)]}, today, now=now), 'custom state ' + state)
        for malformed in (None, '', {}, [None], [3], [{}], [dict(gaps[0], unexpected=True)]):
            refused(lambda: analytics.prepare_snapshot({'coverage': {'missing': malformed}}, today, now=now), 'malformed missing')
        stale = analytics.prepare_snapshot({'coverage': [dict(legacy[0], state='stale')]}, today, now=now)
        assert stale['coverage']['sources'][-1]['state'] == 'stale'
        assert not any(row['source'] == gaps[0]['source'] for row in stale['coverage']['missing'])
        known_live = analytics.prepare_snapshot({'coverage': [{'source': 'upwork', 'state': 'missing', 'fix': 'Reconnect the connector.'}]}, today, now=now)
        assert known_live['kpis']['reply_rate']['state'] == 'missing'
        assert analytics.prepare_snapshot(known_live, today, now=now)['coverage'] == known_live['coverage']
        recorded = analytics_payload(shared)
        tampered = copy.deepcopy(recorded)
        next(row for row in tampered['coverage']['missing'] if row['source'] == 'proposal_insights')['what'] = 'Changed only in missing'
        refused(lambda: analytics.record_snapshot(tampered), 'coverage exact comparison')
        assert not analytics.read_lines('analytics-history.jsonl')
        saved = analytics.record_snapshot(recorded)
        assert saved['coverage'] == recorded['coverage']
        assert analytics.read_lines('analytics-history.jsonl')[-1]['coverage'] == saved['coverage']
        assert analytics.facts_sheet(saved)['coverage']['missing'] == saved['coverage']['missing']

def review_fixture_jobs(folder):
    """Exercise actual source projection, never a prewritten presentation object."""
    jobs = []
    repeated = 'Confirm the input owner before agreeing a date'
    for index, state in enumerate(('met', 'partly', 'missing', 'not_needed')):
        jid = str(991100100 + index)
        home = folder / 'jobs' / jid; home.mkdir()
        quote = f'The audit of our {index + 1} collection pages needs a named owner.'
        first = repeated if index < 2 else f'Keep the agreed scope for audit {index + 1}'
        review = {'state': 'pass', 'read': True, 'reviewable': True,
                  'quote': quote, 'key_finding': first,
                  'free_read': 'Use this free read only as fallback. Ignore its second sentence.',
                  'points': [{'point': p, 'state': state if p == 1 else 'met',
                              'quote': quote, 'reason': repeated if index < 2 else 'A point reason must never become the key finding.'}
                             for p in range(1, 8)]}
        if index < 2:
            review.update(pattern_sentence='the input owner was not confirmed before offering a date.',
                          better_line='Who will supply the audit inputs before we agree the date?')
        chat = dict(review, points={key: {'state': state if key == 'answered_question' else 'met',
                                         'quote': quote, 'reason': repeated if index < 2 else 'Separate criterion reason.'}
                                    for key in analytics.CONVERSATION_POINTS})
        call = dict(review, free_read=EXAMPLE_CALL_READ,
                    next_message='Please confirm the audit owner here on Upwork.',
                    agreed_step='Client confirms the audit owner on Upwork by Friday.',
                    points=[{'point': p, 'state': ('not needed' if state == 'not_needed' else state) if p == 1 else 'met',
                             'quote': quote, 'reason': repeated if index < 2 else 'Separate call reason.'}
                            for p in range(1, 10)])
        proposal = dict(review, points=[dict(point, label=('Scope', 'Price', 'Decision date')[i]) for i, point in enumerate(review['points'][:3])])
        for filename in ('application.sent.md', 'proposal.md'):
            (home / filename).write_text(quote)
        (home / 'thread.json').write_text(json.dumps({'messages_complete': True, 'messages': [
            {'from': 'me', 'at': '2026-10-13T10:00:00+02:00', 'text': quote}]}))
        (home / 'call.md').write_text('Member: Maya\nComplete: yes\nLanguage: English\nMaya: Who owns the inputs?\nClient: ' + quote + '\n')
        job = {'id': jid, 'title': f'Collection SEO audit {index + 1}', 'source': 'outbound',
               'applied_at': '2026-10-12T09:00:00+02:00', 'replied_at': '2026-10-13T10:00:00+02:00',
               'call_held_at': '2026-10-13T11:00:00+02:00', 'proposal_sent_at': '2026-10-13T12:00:00+02:00',
               'application_sent_verified': True, 'application_review': review, 'conversation_review': chat,
               'call_review': call, 'proposal_review': proposal}
        jobs.append(job)
    return jobs

def product_review_computations():
    repeated = 'Confirm the input owner before agreeing a date'
    with fixture('product-review-computations') as folder:
        jobs = review_fixture_jobs(folder)
        snapshot = {'week': '2026-W42', 'generated_at': '2026-10-14T15:00:00+02:00', 'reviews': {}}
        snapshot['call_cards'] = analytics.call_cards(snapshot, jobs)
        projected = analytics.conversations_fields(snapshot, jobs)
        assert set(projected['criteria']) == {'applications', 'chats', 'calls', 'proposals'}
        for kind, entries in projected['sections'].items():
            assert len(entries) == 4 and all(row['reviewable'] for row in entries), (kind, entries)
            for row in entries:
                expected = jobs[int(row['lead_id']) - 991100100]['application_review']['key_finding']
                assert row['key_finding'] == expected and len(row['key_finding'].split()) <= 12
                if kind != 'applications': assert row['duplicate_of_stage'] == 'applications', (kind, row)
            chart = projected['criteria'][kind]
            assert chart['reviewed_n'] == 4 and chart['too_few'] is False, chart
            point = chart['points'][0]
            assert (point['met'], point['partly'], point['missing'], point['not_needed'], point['k'], point['n']) == (1, 1, 1, 1, 1, 3), (kind, point)
            assert all(p['n'] == p['met'] + p['partly'] + p['missing'] for p in chart['points'])
        patterns = projected['patterns']
        assert patterns, 'The repeated, source-backed cross-stage finding disappeared.'
        pattern = next(row for row in patterns if row['better_line'] == 'Who will supply the audit inputs before we agree the date?')
        assert (pattern['k'], pattern['n']) == (8, 16), pattern
        assert isinstance(pattern['better_line'], str) and pattern['better_line'].strip(), pattern
        assert len({q['quote'] for q in pattern['quotes']}) == len(pattern['quotes']), pattern
        assert 1 <= len(pattern['quotes']) <= 2
        for support in pattern['quotes']:
            assert support['title'] and support['date'] and support['lead_id']
            assert support['quote'] in (folder / 'jobs' / support['lead_id'] / {'applications': 'application.sent.md', 'chats': 'thread.json', 'calls': 'call.md', 'proposals': 'proposal.md'}[support['stage']]).read_text()
        canonical = copy.deepcopy(jobs)
        original_threads = {}
        stage_kinds = {'applications':'application', 'chats':'conversation', 'calls':'call', 'proposals':'proposal'}
        thin = dict(snapshot, reviews={})
        for stage, kind in stage_kinds.items():
            thin['reviews'][kind] = {'rubric': []}
            for index, job in enumerate(canonical):
                saved = job[kind + '_review']
                saved['better_line'] = f'Please confirm the input owner for this {kind} audit before we agree a date.'
                points = saved['points']
                items = list(points.items()) if isinstance(points, dict) else [(point['point'], point) for point in points]
                if stage == 'chats':
                    own = f'I will check collection {index + 1}; who will share the audit inputs?'
                    saved.pop('quote', None)  # Exercise own-reply point fallback.
                    thread_path = folder/'jobs'/job['id']/'thread.json'
                    original_threads[thread_path] = thread_path.read_text()
                    thread_path.write_text(json.dumps({'messages_complete':True, 'messages':[
                        {'from':'client','at':'2026-10-13T09:00:00+02:00','text':'Can you check this collection?'},
                        {'from':'me','at':'2026-10-13T10:00:00+02:00','text':own}]}))
                    for _, point in items: point['quote'] = own
                for point_id, point in items:
                    point['better_line'] = f'Please confirm the input owner for {kind} check {point_id} on audit {index + 1}.'
                    point['pattern_sentence'] = f'the {kind} check needs its recorded input owner.'
                overlay = [{'point':point_id, 'state':('missing' if point['state']=='met' else 'met')}
                           for point_id, point in reversed(items)]
                if stage == 'chats' and index % 2 == 0:
                    overlay = {point['point']:{'state':point['state']} for point in overlay}
                if stage == 'applications': overlay = [point for point in overlay if point['point'] != 7]
                thin['reviews'][kind]['rubric'].append({'lead_id':job['id'], 'reviewable':True, 'points':overlay})
        assert 'quote' not in json.dumps(thin['reviews']), 'Weekly fixture must remain quote-free.'
        thin['call_cards'] = analytics.call_cards(thin, canonical)
        overlaid = analytics.conversations_fields(thin, canonical)
        for stage, kind in stage_kinds.items():
            rows = overlaid['sections'][stage]
            assert len(rows) == 4 and all(row['reviewable'] for row in rows), (stage, rows)
            for row in rows:
                job = next(job for job in canonical if job['id'] == row['lead_id'])
                saved = job[kind + '_review']
                assert row['key_finding'] == saved['key_finding'], (stage, row)
                assert row['better_line'] == saved['better_line'], (stage, row)
                original = saved['points']
                original = original if isinstance(original, dict) else {point['point']:point for point in original}
                weekly = next(item['points'] for item in thin['reviews'][kind]['rubric'] if item['lead_id']==job['id'])
                weekly = weekly if isinstance(weekly, dict) else {point['point']:point for point in weekly}
                actual = {point['point']:point for point in row['points']}
                assert set(actual) == set(original), (stage, actual)
                path = folder/'jobs'/job['id']/{'applications':'application.sent.md','chats':'thread.json','calls':'call.md','proposals':'proposal.md'}[stage]
                artifact = path.read_text()
                for point_id, point in original.items():
                    for field in ('quote','reason','better_line','pattern_sentence'):
                        assert actual[point_id].get(field) == point[field], (stage, job['id'], point_id, field, actual[point_id])
                    assert point['quote'] in artifact, (stage, path, point)
                    assert actual[point_id]['state'] == weekly.get(point_id,point)['state'], (stage, point_id, actual[point_id])
                if stage == 'chats':
                    own_messages = [message['text'] for message in json.loads(artifact)['messages'] if message['from']=='me']
                    assert row['quote'] in own_messages and all(point['quote'] in own_messages for point in row['points']), row
        assert len({row['quote'] for row in overlaid['sections']['chats']}) == 4
        for path, source in original_threads.items(): path.write_text(source)
        duplicate_input = analytics.conversations_fields(dict(snapshot,call_cards=snapshot['call_cards']*2), jobs*2)
        assert [(p['k'],p['n']) for p in duplicate_input['patterns']] == [(p['k'],p['n']) for p in patterns], 'Duplicate input inflated a pattern count.'
        for field, value in (('pattern_sentence','In 99 of 100 reviews, the owner was missing.'),('better_line','')):
            malformed=copy.deepcopy(jobs)
            for job in malformed:
                for kind in ('application','conversation','call','proposal'):
                    job[kind+'_review'][field]=value
            invalid_snapshot=dict(snapshot,call_cards=analytics.call_cards(snapshot,malformed))
            assert analytics.conversations_fields(invalid_snapshot,malformed)['patterns']==[], field
        sparse = analytics.conversations_fields(dict(snapshot, call_cards=snapshot['call_cards'][:2]), jobs[:2])
        assert all(chart['too_few'] and chart['reviewed_n'] == 2 for chart in sparse['criteria'].values())
        for dedicated, free, expected in (
                ('Use the dedicated finding', 'Fallback comes second. Extra sentence.', 'Use the dedicated finding'),
                (None, 'Use the first sentence. Never include this second sentence.', 'Use the first sentence.'),
                (' '.join(['word'] * 20), 'Fallback.', ' '.join(['word'] * 12))):
            changed = copy.deepcopy(jobs[:1]); review = changed[0]['application_review']
            review['key_finding'] = dedicated; review['free_read'] = free
            rows = analytics.conversations_fields(snapshot, changed)['sections']['applications']
            assert rows[0]['key_finding'] == expected, rows[0]
        changed = copy.deepcopy(jobs[:1]); changed[0]['application_review'].update(key_finding=None, free_read=None)
        row = analytics.conversations_fields(snapshot, changed)['sections']['applications'][0]
        assert repeated not in row['key_finding'], 'A rubric point reason leaked into the finding.'
        (folder / 'jobs' / jobs[0]['id'] / 'application.sent.md').unlink()
        absent = analytics.conversations_fields(snapshot, jobs)['sections']['applications']
        missing = next(row for row in absent if row['lead_id'] == jobs[0]['id'])
        assert missing['marker'] == 'not reviewed' and not missing['reviewable']
        markers = {row['lead_id']: row['marker'] for row in projected['sections']['applications']}
        assert markers[jobs[0]['id']] == markers[jobs[3]['id']] == 'keep'
        assert markers[jobs[1]['id']] == markers[jobs[2]['id']] == 'needs work'

def weekly_accountability_contract():
    import badges
    def week(number, count, target=5):
        return {'week': f'2026-W{number}', 'generated_at': dt.date.fromisocalendar(2026, number, 7).isoformat() + 'T18:00:00+02:00',
                'kpis': {'weekly_volume': {'k': count, 'value': count, 'n': target, 'target': target, 'state': 'pass' if count >= target else 'fail'}},
                'accountability': {'working_days': {'k': 1 if count else 0, 'n': 5}}}
    with fixture('weekly-accountability') as folder:
        (folder / 'context/me.md').write_text('## Weekly goal\n5\n\n## Working hours\nMon-Fri 09:00-18:00 Europe/Berlin\n\n## Planned off days\n2026-10-14\n')
        history = [week(39, 5), week(40, 5), week(41, 2, 2)]
        current = week(42, 0)
        current['generated_at'] = '2026-10-14T15:00:00+02:00'
        streak = badges.streak_history(history, week=current['week'], current=current)
        assert (streak['streak_weeks'], streak['best_streak_weeks']) == (3, 3), streak
        current['kpis']['weekly_volume'].update(k=5, value=5, state='pass')
        streak = badges.streak_history(history, week=current['week'], current=current)
        assert (streak['streak_weeks'], streak['best_streak_weeks']) == (4, 4), streak
        missed = badges.streak_history(history[:1] + [week(40, 0)] + history[2:], week='2026-W42', current=current)
        assert missed['streak_weeks'] == 2 and missed['best_streak_weeks'] == 2, missed
        retained = badges.streak_history([week(n,5) for n in range(36,40)]+[week(40,0),week(41,5)],week='2026-W42',current=current)
        assert (retained['streak_weeks'],retained['best_streak_weeks'])==(2,4),retained
        off=week(40,0);off['accountability']['working_days']['n']=0
        rested=badges.streak_history([week(39,5),off,week(41,5)],week='2026-W42',current=current)
        assert rested['streak_weeks']==rested['best_streak_weeks']==3 and rested['weeks'][1]['state']=='off',rested
        gap = badges.streak_history([week(39, 5), week(41, 5)], week='2026-W42', current=current)
        assert gap['streak_weeks'] == 2 and gap['anchors_used'] == [], gap
        jobs = [{'id': 'a', 'source': 'outbound', 'job_fit': {'state': 'pass'}, 'applied_at': '2026-10-12T10:00:00+02:00'},
                {'id': 'b', 'source': 'outbound', 'job_fit': {'state': 'pass'}, 'applied_at': '2026-10-12T11:00:00+02:00'},
                {'id': 'c', 'source': 'outbound', 'job_fit': {'state': 'pass'}, 'applied_at': '2026-10-14T11:00:00+02:00'},
                {'id': 'd', 'source': 'invite', 'applied_at': '2026-10-13T10:00:00+02:00'},
                {'id': 'e', 'source': 'outbound', 'job_fit': {'state': 'fail'}, 'applied_at': '2026-10-13T11:00:00+02:00'}]
        measured = analytics.accountability_fields(current, jobs, history)
        assert measured['working_days'] == {'k': 1, 'n': 4, 'dates': ['2026-10-12', '2026-10-13', '2026-10-15', '2026-10-16'], 'applied_dates': ['2026-10-12']}, measured
        assert len(badges.BADGE_NAMES) == 14 and 'Steady Hand' in badges.BADGE_NAMES
        assert 'Steady Anchor' not in badges.BADGE_NAMES
        assert badges.canonical_name('Steady Anchor') == 'Steady Hand'
        monday = week(42,5)
        monday.update(generated_at='2026-10-12T10:00:00+02:00',activity_period={'start':'2026-10-05','end':'2026-10-11'})
        monday['kpis']['weekly_volume']['period'] = dict(monday['activity_period'])
        reported_jobs = [{'id':f'reported-{i}','source':'outbound','job_fit':{'state':'pass'},
                          'applied_at':f'2026-10-{5+i:02d}T10:00:00+02:00'} for i in range(5)]
        reported = analytics.accountability_fields(monday,reported_jobs,[])
        assert reported['working_days'] == {'k':5,'n':5,'dates':[f'2026-10-{5+i:02d}' for i in range(5)],
                                           'applied_dates':[f'2026-10-{5+i:02d}' for i in range(5)]},reported
        assert reported['application_streak']['weeks'][0]['week'] == '2026-W41',reported
        analytics_sync_marker(folder)
        full = analytics.compute(dt.date(2026, 10, 14), jobs=jobs, now='2026-10-14T15:00:00+02:00')
        assert full['accountability'] == full['presentation']['accountability']
        card = analytics.snapshot_public_card(full, jobs)
        assert card['working_days'] == {key: full['accountability']['working_days'][key] for key in ('k', 'n')}
        assert set(card['working_days']) == {'k', 'n'}
        assert 'weeks steady' not in analytics.public_onepager_html(card)
        assert not any(field in card for field in ('dates', 'applied_dates', 'client', 'key_finding'))
        assert card['streak_weeks'] == full['accountability']['application_streak']['current']
        old = dict(week(40,0),badges=[{'badge':'Steady Anchor','tier':'Silver','earned_week':'2026-W39'}])
        resumed = copy.deepcopy(full)
        resumed['accountability']['application_streak'] = {'current':1,'best':4,'weeks':[{'week':'2026-W42','state':'met'}]}
        earned = analytics.badge_results(resumed,jobs,[old],dt.date(2026,10,14))
        steady = [row for row in earned if row['badge']=='Steady Hand']
        assert steady[-1]['tier']=='Silver' and not any(row['tier']=='Gold' for row in steady),steady
        assert steady[-1]['progress']=={'current':1,'target':6,'remaining':5,'unit':'weeks'},steady
        assert not any(row['badge']=='Steady Anchor' for row in earned)
        for working in ({'k':1,'n':4,'dates':['2026-10-12']},{'k':5,'n':4},{'k':True,'n':4},{'k':-1,'n':4}):
            attack=copy.deepcopy(card);attack['working_days']=working
            refused(lambda:analytics.validate_community_card(attack,jobs),'Public working-day payload '+str(working))
        metadata = badges.catalogue_metadata()
        assert 'Steady Hand' in metadata, 'Canonical weekly Steady Hand metadata is missing.'
        assert 'daily' not in metadata['Steady Hand']['criterion'].casefold()

def owner_habit_period_contract():
    today = dt.date(2026, 10, 12)
    now = '2026-10-12T10:00:00+02:00'
    with fixture('owner-habit-periods') as folder:
        (folder / 'data/connects.jsonl').write_text('')
        jobs, history = [], []
        for back, volume, minutes in [(4, 4, 2), (3, 6, 4), (2, 8, 6), (1, 10, 8), (0, 3, 1)]:
            start = dt.date(2026, 10, 5) - dt.timedelta(weeks=back)
            for index in range(volume):
                success = index < (volume if back in (1, 3) else volume // 2 if back else 2)
                client = dt.datetime.combine(start, dt.time(10), analytics.local_zone())
                held = client + dt.timedelta(days=1)
                ended = held + dt.timedelta(minutes=15)
                due = (start + dt.timedelta(days=2)).isoformat()
                job = {'id': f'habit-{back}-{index}', 'title': 'Website review', 'source': 'outbound',
                       'applied_at': client.isoformat(), 'replied_at': (client + dt.timedelta(minutes=minutes)).isoformat(),
                       'first_client_message_at': client.isoformat(), 'first_reply_at': (client + dt.timedelta(minutes=minutes)).isoformat(),
                       'job_fit': {'state': 'pass'}, 'application_facts': {'source': 'outbound', 'posted_age_band': '<10m' if success else '10-30m'},
                       'call_held_at': held.isoformat(), 'call_ended_at': ended.isoformat(),
                       'proposal_sent_at': (ended + dt.timedelta(minutes=20 if success else 40)).isoformat(),
                       'follow_up_history': [{'lane': 'silent', 'due_on': due, 'action': 'sent' if success else 'missed', 'on': due}]}
                jobs.append(job)
            check = start + dt.timedelta(days=7)
            (folder / 'data/sync.json').write_text(json.dumps({'synced_at': dt.datetime.combine(check, dt.time(9), analytics.local_zone()).isoformat()}))
            metrics, _ = analytics.calculate(jobs, check, now=dt.datetime.combine(check, dt.time(10), analytics.local_zone()))
            if back:
                history.append({'week': check.strftime('%G-W%V'), 'periods': {'activity': analytics.period((start, check - dt.timedelta(days=1)))}, 'kpis': metrics})
        kpis, _ = analytics.calculate(jobs, today, now=now)
        snapshot = {'week': '2026-W42', 'generated_at': now, 'kpis': kpis, 'window': analytics.period(analytics.span(today, 28)),
                    'periods': {'activity': analytics.period(analytics.span(today, 7))}, 'verdict': {}, 'reviews': {}, 'coverage': {'sources': []}}
        score = analytics.funnel_score(snapshot, history)
        rows = {row['key']: row for row in analytics.scorecard_fields(snapshot, jobs, history, today)}
        assert rows['weekly_volume']['value'] == 3 and rows['weekly_volume']['finished']['n'] == 3, (kpis['weekly_volume'], rows['weekly_volume'])
        assert rows['weekly_volume']['target']['value'] == kpis['weekly_volume']['target']
        expected = {'weekly_volume': 7, 'speed_10min': 75, 'first_reply': 5, 'follow_ups_on_time': 75, 'proposal_on_time': 75}
        for key in analytics.LEVERS:
            row = rows[key]
            assert row['value'] == kpis[key]['value'], (key, row['value'], kpis[key]['value'])
            assert row['change']['previous_value'] == expected[key], (key, row['change'])
            assert row['period_label'] == 'This week' and row['period'] == {'kind': 'week', 'start': '2026-10-05', 'end': '2026-10-11'}
            assert row['habit_period']['kind'] == 'week' and row['sample_note'] is None
            assert row['change']['comparison_period'] == {'kind': 'four_week_average', 'start': '2026-09-07', 'end': '2026-10-04'}
            assert row['series']['labels'][-5:] == ['2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05']
            assert row['series']['points'][-1] == kpis[key]['value']
        assert rows['weekly_volume']['series']['points'][-5:] == [4, 6, 8, 10, 3]
        assert rows['first_reply']['series']['points'][-5:] == [2, 4, 6, 8, 1]
        assert analytics.funnel_score(snapshot, history) == score
        result_keys = ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won', 'offer_to_contract', 'invite_to_call', 'job_fit', 'value_per_100_connects')
        current28, _ = analytics.calculate(jobs, today, now=now, activity_bounds=analytics.span(today, 28))
        token = analytics._RECONSTRUCTING.set(True)
        try:
            previous28, _ = analytics.calculate(jobs, today - dt.timedelta(days=28), now=dt.datetime.combine(today - dt.timedelta(days=28), dt.time(), analytics.local_zone()), activity_bounds=analytics.span(today - dt.timedelta(days=28), 28))
        finally:
            analytics._RECONSTRUCTING.reset(token)
        for key in result_keys:
            assert rows[key]['value'] == current28[key]['value'], key
            assert rows[key]['finished'] == {field: current28[key][field] for field in ('k', 'n')}, key
            assert rows[key]['period_label'] == 'Last 28 days'
            assert rows[key]['change']['comparison_period'] == {'start': '2026-08-17', 'end': '2026-09-13'}
            assert len(rows[key]['series']['labels']) == len(rows[key]['series']['points']) == 8
        for n in (0, 2):
            sparse_jobs = [job for job in jobs if not job['id'].startswith('habit-0-') or int(job['id'].rsplit('-', 1)[1]) < n]
            sparse_kpis, _ = analytics.calculate(sparse_jobs, today, now=now)
            sparse = dict(snapshot, kpis=sparse_kpis)
            sparse_rows = {row['key']: row for row in analytics.scorecard_fields(sparse, sparse_jobs, history, today)}
            for key in analytics.LEVERS:
                row = sparse_rows[key]
                assert row['value'] == expected[key], (n, key, row['value'])
                assert row['period_label'] == 'Prior four-week average' and f'{n} opportunities' in row['sample_note']
                assert row['current_week']['n'] == n and row['series']['points'][-1] == sparse_kpis[key]['value']
                assert row['period'] == row['change']['comparison_period']
        legacy = {'week': '2026-W40', 'kpis': {'weekly_volume': {'value': 12}},
                  'presentation': {'scorecard': [{'key': 'weekly_volume', 'value': 99}]}}
        old_rows = {row['key']: row for row in analytics.scorecard_fields(snapshot, jobs, [legacy], today)}
        idx = old_rows['weekly_volume']['series']['labels'].index('2026-09-28')
        assert old_rows['weekly_volume']['series']['points'][idx] == 12
        snapshot.update(funnel_score=score, call_cards=[], goals_review=[], goals_next=[])
        facts = analytics.report_source_facts(snapshot, jobs, today)
        snapshot['report_facts'] = facts
        numeric = analytics.report_numeric_facts(snapshot)
        assert numeric['weekly']['fast_proposals'] == 2
        assert numeric['four_weeks']['fast_proposals'] == current28['proposal_on_time']['k'] == 22
        assert numeric['weekly']['applications'] == 3





PREVIEW2_BACKEND_SLICE = {'agreement': {'week': '2026-W42',
               'goals': [{'stage': 'Call rate',
                          'kpi': 'reply_to_call',
                          'change': 'Offer two useful times',
                          'start': '2026-10-12',
                          'cue': 'When the client shows interest',
                          'action': 'Answer the real question, then offer two useful call times',
                          'fallback': 'Resolve one blocking question in the platform thread',
                          'review_on': '2026-10-19',
                          'primary': True,
                          'goal_library_id': 'call-times'},
                         {'stage': 'Call review',
                          'kpi': 'call_review',
                          'change': 'Budget before price',
                          'start': '2026-10-12',
                          'cue': 'Before quoting a website price',
                          'action': 'Confirm scope and budget before naming the price',
                          'fallback': 'Resolve one blocking question in the platform thread',
                          'review_on': '2026-10-19',
                          'primary': False,
                          'goal_library_id': 'call-budget'},
                         {'stage': 'Win rate',
                          'kpi': 'proposal_to_won',
                          'change': 'Decision checkpoint',
                          'start': '2026-10-12',
                          'cue': 'When sending the scope',
                          'action': 'Confirm the decision owner and review date',
                          'fallback': 'Resolve one blocking question in the platform thread',
                          'review_on': '2026-10-19',
                          'primary': False,
                          'goal_library_id': 'proposal-decision'}]},
 'badges': [{'badge': 'Steady Anchor',
             'tier': 'Bronze',
             'earned_week': '2026-W35',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'Steady Anchor',
             'tier': 'Silver',
             'earned_week': '2026-W37',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'Steady Anchor',
             'tier': 'Gold',
             'earned_week': '2026-W40',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'True North',
             'tier': 'Bronze',
             'earned_week': '2026-W42',
             'new': True,
             'progress_to_next': '1 of 3 weeks'},
            {'badge': 'Harbour Master',
             'tier': 'Bronze',
             'earned_week': '2026-W41',
             'new': False,
             'progress_to_next': '2 of 3 weeks'},
            {'badge': 'First Mate',
             'tier': 'Bronze',
             'earned_week': '2026-W39',
             'new': False,
             'progress_to_next': '4 of 6 weeks'},
            {'badge': 'First Mate',
             'tier': 'Silver',
             'earned_week': '2026-W41',
             'new': False,
             'progress_to_next': '4 of 6 weeks'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Bronze',
             'earned_week': '2026-W35',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Silver',
             'earned_week': '2026-W37',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Gold',
             'earned_week': '2026-W40',
             'new': False,
             'progress_to_next': '8 of 13 weeks'},
            {'badge': 'First Doubloon',
             'tier': 'Bronze',
             'earned_week': '2026-W36',
             'new': False,
             'progress_to_next': '3 of 6 weeks'},
            {'badge': 'First Doubloon',
             'tier': 'Silver',
             'earned_week': '2026-W42',
             'new': True,
             'progress_to_next': '3 of 6 weeks'}],
 'awards': [{'badge': 'First Doubloon',
             'tier': 'Bronze',
             'lead_id': '970004004',
             'at': '2026-10-12T09:00:00+01:00',
             'reason': 'First won contract.'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Bronze',
             'lead_id': None,
             'at': '2026-08-24T10:11:57.657460+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W35.'},
            {'badge': 'Steady Anchor',
             'tier': 'Bronze',
             'lead_id': None,
             'at': '2026-08-24T10:11:57.657460+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W35.'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Silver',
             'lead_id': None,
             'at': '2026-09-07T10:12:07.983468+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W37.'},
            {'badge': 'Steady Anchor',
             'tier': 'Silver',
             'lead_id': None,
             'at': '2026-09-07T10:12:07.983468+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W37.'},
            {'badge': 'First Mate',
             'tier': 'Bronze',
             'lead_id': None,
             'at': '2026-09-21T10:12:23.617258+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W39.'},
            {'badge': 'Lighthouse Keeper',
             'tier': 'Gold',
             'lead_id': None,
             'at': '2026-09-28T10:12:33.578511+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W40.'},
            {'badge': 'Steady Anchor',
             'tier': 'Gold',
             'lead_id': None,
             'at': '2026-09-28T10:12:33.578511+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W40.'},
            {'badge': 'First Mate',
             'tier': 'Silver',
             'lead_id': None,
             'at': '2026-10-05T10:12:44.238656+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W41.'},
            {'badge': 'Harbour Master',
             'tier': 'Bronze',
             'lead_id': None,
             'at': '2026-10-05T10:12:44.238656+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W41.'},
            {'badge': 'True North',
             'tier': 'Bronze',
             'lead_id': None,
             'at': '2026-10-12T10:12:56.258360+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W42.'},
            {'badge': 'First Doubloon',
             'tier': 'Silver',
             'lead_id': None,
             'at': '2026-10-12T10:29:31.063616+01:00',
             'reason': 'Weekly analytics criteria met for 2026-W42.'}],
 'applications': [{'job': {'id': '970007009',
                           'source': 'outbound',
                           'title': 'Framer landing page for a design agency',
                           'application_sent_verified': True,
                           'application_review': {'state': 'fail',
                                                  'reviewable': True,
                                                  'quote': 'I have not included the requested mobile walkthrough.',
                                                  'free_read': 'Include the mobile walkthrough explicitly requested in '
                                                               'the post. Keep the other specific passages.',
                                                  'next_message': 'Which part of the website should resolve “the cms '
                                                                  'migration must retain urls” first?',
                                                  'points': [{'point': 1,
                                                              'state': 'met',
                                                              'quote': 'The CMS migration must retain URLs. I would '
                                                                       'put that buyer decision first.',
                                                              'reason': 'The first line names the posted buyer '
                                                                        'problem'},
                                                             {'point': 2,
                                                              'state': 'met',
                                                              'quote': 'My relevant example shows a framer landing '
                                                                       'page with editable content and mobile QA.',
                                                              'reason': 'The example matches this page and editing '
                                                                        'concern'},
                                                             {'point': 3,
                                                              'state': 'met',
                                                              'quote': 'Your team will edit native CMS fields; I will '
                                                                       'document them and include a short handover.',
                                                              'reason': 'The screening answer explains native CMS '
                                                                        'ownership'},
                                                             {'point': 4,
                                                              'state': 'met',
                                                              'quote': 'The fixed scope is the agreed marketing page, '
                                                                       'mobile QA and CMS handover; I quote $65/h or '
                                                                       '$2,500-$6,000 after confirming the page count.',
                                                              'reason': 'The bid states the scope and rate boundary'},
                                                             {'point': 5,
                                                              'state': 'met',
                                                              'quote': 'I would keep the first step focused on the '
                                                                       'page decision.',
                                                              'reason': 'The application stays focused and concise'},
                                                             {'point': 6,
                                                              'state': 'met',
                                                              'quote': 'Which buyer objection should this page answer '
                                                                       'first?',
                                                              'reason': 'One easy buyer question closes the '
                                                                        'application'},
                                                             {'point': 7,
                                                              'state': 'missing',
                                                              'quote': 'I have not included the requested mobile '
                                                                       'walkthrough.',
                                                              'reason': 'Include the mobile walkthrough explicitly '
                                                                        'requested in the post'}]},
                           'applied_at': '2026-10-09T10:00:00+01:00'},
                   'sent': 'The CMS migration must retain URLs. I would put that buyer decision first.\n'
                           'My relevant example shows a framer landing page with editable content and mobile QA.\n'
                           'Your team will edit native CMS fields; I will document them and include a short handover.\n'
                           'The fixed scope is the agreed marketing page, mobile QA and CMS handover; I quote $65/h or '
                           '$2,500-$6,000 after confirming the page count.\n'
                           'Which buyer objection should this page answer first?\n'
                           'I would keep the first step focused on the page decision.\n'
                           'I have not included the requested mobile walkthrough.\n',
                   'post': '# Framer landing page for a design agency\n'
                           'Fictional brief: The CMS migration must retain URLs. B2B SaaS or agency marketing site. '
                           'Budget $2,500-$6,000 or $65/h.\n'
                           '\n'
                           'Please include a short Loom showing the mobile comparison interaction.\n'
                           '\n'
                           'Please include a short Loom showing the mobile comparison interaction.\n'
                           '\n'
                           'Screening question: How will our team edit the content after handover?\n'},
                  {'job': {'id': '970007019',
                           'source': 'outbound',
                           'title': 'Framer homepage for a partnership agency',
                           'application_sent_verified': True,
                           'application_review': {'state': 'pass',
                                                  'reviewable': True,
                                                  'quote': 'A Loom is optional here; the written plan covers the '
                                                           'decision.',
                                                  'free_read': 'Keep the problem-led opener, matching proof and '
                                                               'specific CMS answer. The close asks one useful buyer '
                                                               'question.',
                                                  'next_message': 'Which part of the website should resolve “the cms '
                                                                  'migration must retain urls” first?',
                                                  'points': [{'point': 1,
                                                              'state': 'met',
                                                              'quote': 'The CMS migration must retain URLs. I would '
                                                                       'put that buyer decision first.',
                                                              'reason': 'The first line names the posted buyer '
                                                                        'problem'},
                                                             {'point': 2,
                                                              'state': 'met',
                                                              'quote': 'My relevant example shows a framer homepage '
                                                                       'with editable content and mobile QA.',
                                                              'reason': 'The example matches this page and editing '
                                                                        'concern'},
                                                             {'point': 3,
                                                              'state': 'met',
                                                              'quote': 'Your team will edit native CMS fields; I will '
                                                                       'document them and include a short handover.',
                                                              'reason': 'The screening answer explains native CMS '
                                                                        'ownership'},
                                                             {'point': 4,
                                                              'state': 'met',
                                                              'quote': 'The fixed scope is the agreed marketing page, '
                                                                       'mobile QA and CMS handover; I quote $65/h or '
                                                                       '$2,500-$6,000 after confirming the page count.',
                                                              'reason': 'The bid states the scope and rate boundary'},
                                                             {'point': 5,
                                                              'state': 'met',
                                                              'quote': 'I would keep the first step focused on the '
                                                                       'page decision.',
                                                              'reason': 'The application stays focused and concise'},
                                                             {'point': 6,
                                                              'state': 'met',
                                                              'quote': 'Which buyer objection should this page answer '
                                                                       'first?',
                                                              'reason': 'One easy buyer question closes the '
                                                                        'application'}]},
                           'applied_at': '2026-10-09T10:00:00+01:00'},
                   'sent': 'The CMS migration must retain URLs. I would put that buyer decision first.\n'
                           'My relevant example shows a framer homepage with editable content and mobile QA.\n'
                           'Your team will edit native CMS fields; I will document them and include a short handover.\n'
                           'The fixed scope is the agreed marketing page, mobile QA and CMS handover; I quote $65/h or '
                           '$2,500-$6,000 after confirming the page count.\n'
                           'Which buyer objection should this page answer first?\n'
                           'I would keep the first step focused on the page decision.\n'
                           'A Loom is optional here; the written plan covers the decision.\n',
                   'post': '# Framer homepage for a partnership agency\n'
                           'Fictional brief: The CMS migration must retain URLs. B2B SaaS or agency marketing site. '
                           'Budget $2,500-$6,000 or $65/h.\n'
                           '\n'
                           'A Loom is optional; a specific written approach is sufficient.\n'
                           '\n'
                           'Screening question: How will our team edit the content after handover?\n'}],
 'call': {'job': {'id': '970006003',
                  'title': 'Webflow resource hub for a procurement SaaS',
                  'call_held_at': '2026-10-08T14:00:00+01:00',
                  'call_ended_at': '2026-10-08T14:30:00+01:00',
                  'call_reviews': {'transcript:65bef56ddb33ec99458ec26f6a6a80748810a4a8ffb4acafe06dccc6b01c68ab': {'reviewed_at': '2026-10-14T09:23:52.134243+00:00',
                                                                                                                   'call_at': '2026-10-08T13:00:00+00:00'}},
                  'call_review_session': 'transcript:65bef56ddb33ec99458ec26f6a6a80748810a4a8ffb4acafe06dccc6b01c68ab',
                  'call_review': {'reviewable': True,
                                  'points': [{'point': 1,
                                              'state': 'met',
                                              'quote': '[00:00] Let us confirm the resource-site goal, scope and next '
                                                       'step.',
                                              'reason': 'Elodie: Keep the agenda connected to the buyer decision'},
                                             {'point': 2,
                                              'state': 'met',
                                              'quote': '[01:10] We need editable resource categories without manual '
                                                       'updates.',
                                              'reason': 'Elodie: Current site evidence is concrete'},
                                             {'point': 3,
                                              'state': 'partly',
                                              'quote': '[03:20] Manual updates take time, but we have not measured the '
                                                       'weekly total.',
                                              'reason': 'Elodie: Quantify the cost of the current problem'},
                                             {'point': 4,
                                              'state': 'met',
                                              'quote': '[05:10] The scope is the resource pages and CMS handover to '
                                                       'you.',
                                              'reason': 'Elodie: The page boundary is agreed'},
                                             {'point': 5,
                                              'state': 'missing',
                                              'quote': '[07:00] My fixed price is $4,200. We have not discussed your '
                                                       'available budget yet.',
                                              'reason': 'A price was named before the available budget was asked'},
                                             {'point': 6,
                                              'state': 'not needed',
                                              'quote': '[09:00] I approve the work myself. Those terms work and I '
                                                       'prefer a direct client offer today.',
                                              'reason': 'Elodie: The approving client is present'},
                                             {'point': 7,
                                              'state': 'met',
                                              'quote': '[11:00] This editable resource-category example shows labels '
                                                       'and filters you can maintain yourself.',
                                              'reason': 'Elodie: Match proof to the stated buying concern'},
                                             {'point': 8,
                                              'state': 'met',
                                              'quote': '[12:00] What concern would stop you approving those terms?',
                                              'reason': 'Elodie: Invite and explore the actual objection'},
                                             {'point': 9,
                                              'state': 'met',
                                              'quote': '[14:00] Yes, confirm the resource pages and CMS handover in '
                                                       'the platform thread by 15:00 today. I will approve the fixed '
                                                       'client offer for $4,200 today; no separate proposal is needed.',
                                              'reason': 'A concrete owner, platform action and time are agreed'}],
                                  'moments': [{'quote': '[07:00] My fixed price is $4,200. We have not discussed your '
                                                        'available budget yet.',
                                               'better_wording': 'Before I quote, what budget range should this scope '
                                                                 'fit?'}],
                                  'fix': 'Budget before price',
                                  'example': 'Before I quote, what budget range should this scope fit?',
                                  'free_read': 'Elodie is ready to choose a compact resource site and prefers to '
                                               'approve the agreement directly. You checked the content owner and made '
                                               'the CMS handover part of the scope. The call covered the present '
                                               'workflow and the desired result, but the cost of manual updates was '
                                               'only touched on; one concrete weekly time estimate would have '
                                               'strengthened the value discussion. Price arrived before a budget '
                                               'question, so that sequence remains the main correction even though the '
                                               'client accepted the terms. Your example showed editable resource '
                                               'categories and answered the actual maintenance concern. Elodie is the '
                                               'decision maker, which removes the need for a separate approval '
                                               'meeting. The next step is a fixed client offer for the agreed pages '
                                               'and handover, confirmed in the platform thread today. Keep the message '
                                               'focused on checking those terms. Do not send a second proposal or add '
                                               'a call merely to follow a routine when the client has already chosen '
                                               'the direct route.',
                                  'next_message': 'Please confirm the fixed offer covers the resource pages and CMS '
                                                  'handover we discussed. Once those terms match, you can approve '
                                                  'directly here.',
                                  'agreed_step': 'Daniel confirms the resource pages and CMS handover by 15:00 today; '
                                                 'Elodie agreed to approve the fixed $4,200 client offer today, '
                                                 'without a separate proposal.',
                                  'next_step': 'Daniel confirms the resource pages and CMS handover by 15:00 today; '
                                               'Elodie agreed to approve the fixed $4,200 client offer today, without '
                                               'a separate proposal.'},
                  'call_reviewed_at': '2026-10-14T09:23:52.134243+00:00'},
          'transcript': 'Member: Daniel\n'
                        'Complete: yes\n'
                        'Language: English\n'
                        'Call at: 2026-10-08T14:00:00+01:00\n'
                        'Duration: 900\n'
                        'Daniel: [00:00] Let us confirm the resource-site goal, scope and next step.\n'
                        'Elodie: [01:10] We need editable resource categories without manual updates.\n'
                        'Daniel: [02:00] Who will own the content and maintain the categories?\n'
                        'Elodie: [02:20] I will maintain the content myself.\n'
                        'Elodie: [03:20] Manual updates take time, but we have not measured the weekly total.\n'
                        'Daniel: [05:10] The scope is the resource pages and CMS handover to you.\n'
                        'Daniel: [07:00] My fixed price is $4,200. We have not discussed your available budget yet.\n'
                        'Elodie: [09:00] I approve the work myself. Those terms work and I prefer a direct client '
                        'offer today.\n'
                        'Daniel: [11:00] This editable resource-category example shows labels and filters you can '
                        'maintain yourself.\n'
                        'Daniel: [12:00] What concern would stop you approving those terms?\n'
                        'Elodie: [12:20] I only needed to know that I could maintain the categories. That example '
                        'answers it.\n'
                        'Elodie: [14:00] Yes, confirm the resource pages and CMS handover in the platform thread by '
                        '15:00 today. I will approve the fixed client offer for $4,200 today; no separate proposal is '
                        'needed.\n'}}

def owner_goal_join_contract():
    source = copy.deepcopy(PREVIEW2_BACKEND_SLICE['agreement'])
    with fixture('owner-goals'):
        legacy = [analytics.goal_id(goal, source['week']) for goal in source['goals']]
        assert legacy == [analytics.goal_id(dict(goal), source['week']) for goal in source['goals']]
        assert len(set(legacy)) == 3
        saved = analytics.add_goals(source)
        assert [goal['goal_id'] for goal in saved['goals']] == legacy
        snapshot = {'week': source['week'], 'generated_at': '2026-10-12T10:00:00+02:00',
                    'goals_next': saved['goals'], 'reviews': {}}
        snapshot['quests'] = analytics.quest_progress(snapshot, [], dt.date(2026, 10, 12))
        cards = analytics.goal_cards(snapshot)
        assert len(cards) == 3 and all(card['measurement'] for card in cards)
        assert [card['goal_id'] for card in cards] == legacy
        assert all(card['change'] == goal['change'] == card['text'] for card, goal in zip(cards, saved['goals']))
        assert [goal['goal_id'] for goal in analytics.latest_goals(dt.date(2026, 10, 19))] == legacy
        assert set(analytics.public_agreed_goals('2026-W43')) == set(legacy)
        explicit = dict(saved['goals'][0], goal_id='retained-owner-goal', change='Edited cue copy',
                        start='2026-10-19', review_on='2026-10-26')
        agreement = analytics.add_goals({'week': '2026-W43', 'goals': [explicit]})
        assert agreement['goals'][0]['goal_id'] == 'retained-owner-goal'
        edited = dict(explicit, change='Edit the wording again')
        assert analytics.goal_id(edited, '2026-W44') == 'retained-owner-goal'
        snapshot.update(week='2026-W43', goals_next=[edited], quests=[])
        assert analytics.goal_cards(snapshot)[0]['goal_id'] == 'retained-owner-goal'
        for field, value in [('invented_field', 'not allowed'), ('measurement', 'invented check'), ('goal_library_id', 'reply-opener'),
                             ('goal_id', ''), ('goal_id', 'spaces not allowed')]:
            refused(lambda field=field, value=value: analytics.validate_goals({'week': '2026-W43',
                    'goals': [dict(explicit, **{field: value})]}), field)
        refused(lambda: analytics.validate_goals({'week': '2026-W43', 'goals': [dict(explicit, review_on='2026-10-01')]}), 'dates')

def owner_badge_progress_contract():
    import badges
    snapshot = {'badges': copy.deepcopy(PREVIEW2_BACKEND_SLICE['badges']), 'badge_progress': {'First Mate': {'value': 4}}}
    before = copy.deepcopy(snapshot)
    awards = copy.deepcopy(PREVIEW2_BACKEND_SLICE['awards'])
    ledger_before = copy.deepcopy(awards)
    stations = {row['badge']: row for row in badges.voyage(awards, snapshot)['stations']}
    for name, expected in [('First Mate', '4 of 6 weeks'), ('Steady Anchor', '8 of 13 weeks'),
                           ('Lighthouse Keeper', '8 of 13 weeks'), ('First Doubloon', '3 of 6 weeks')]:
        name = badges.canonical_name(name)
        assert stations[name]['progress_to_next'] == expected, (name, stations[name])
    native = next(row for row in awards if row['badge'] == 'First Doubloon' and row['tier'] == 'Silver')
    assert stations['First Doubloon']['earned_at'] == native['at']
    assert stations['First Doubloon']['tier'] == 'Silver'
    lower = {'badge': 'First Mate', 'tier': 'Bronze', 'at': '2026-10-14T10:00:00+00:00'}
    row = next(row for row in badges.voyage([lower], snapshot)['stations'] if row['badge'] == 'First Mate')
    assert row['tier'] == 'Silver' and row['progress_to_next'] == '4 of 6 weeks' and row['earned_week'] == '2026-W41'
    assert snapshot == before and awards == ledger_before

def owner_review_fields_contract():
    with fixture('owner-review-fields') as folder:
        jobs = []
        for source in PREVIEW2_BACKEND_SLICE['applications']:
            job = copy.deepcopy(source['job']); jobs.append(job)
            home = folder / 'jobs' / str(job['id']); home.mkdir()
            (home / 'job.md').write_text(source['post'])
            (home / 'application.sent.md').write_text(source['sent'])
        snapshot = {'generated_at': '2026-10-12T10:00:00+02:00', 'reviews': {}, 'call_cards': []}
        rows = {row['lead_id']: row for row in analytics.conversations_fields(snapshot, jobs)['sections']['applications']}
        for jid, expected, requested in [('970007009', 'requested_not_sent', True), ('970007019', 'not_sent', False)]:
            row = rows[jid]
            assert row['reviewable'] and row['loom_status'] == expected and row['loom_requested'] is requested
            assert row['loom_transcript'] is None and row['loom_source_state'] == 'not_applicable'
        home = folder / 'jobs/970007019'
        job = dict(jobs[-1], loom_url='https://www.loom.com/share/stale-link')
        assert analytics.application_loom_fields(job, home, PREVIEW2_BACKEND_SLICE['applications'][-1]['sent'], '')['loom_status'] == 'not_sent'
        assert analytics.application_loom_fields(job, home, '', '')['loom_status'] == 'unknown'
        assert analytics.application_loom_fields(job, home, 'I have not included a Loom.', '')['loom_status'] == 'not_sent'
        for sent in ('https://www.loom.com/share/actual-sent', 'My short Loom shows the mobile pricing toggle.'):
            row = analytics.application_loom_fields(job, home, sent, '')
            assert row['loom_status'] == 'sent' and row['loom_source_state'] == 'unknown'
        call = PREVIEW2_BACKEND_SLICE['call']; job = copy.deepcopy(call['job'])
        home = folder / 'jobs' / str(job['id']); home.mkdir()
        (home / 'call.md').write_text(call['transcript'])
        card = analytics.call_cards(snapshot, [job])[0]
        assert card['reviewable']
        for field in ('fix', 'example', 'next_message', 'agreed_step'):
            assert card[field] == job['call_review'][field]
        assert len(card['moments']) == len(job['call_review']['moments']) == 1
        moment = card['moments'][0]
        assert moment['quote'] in analytics.call_utterances(call['transcript'])
        assert moment['better_wording'] == moment['better'] == job['call_review']['moments'][0]['better_wording']
        assert moment['quote_at'] == '07:00'
        assert len(card['points']) == 9 and len(card['coach_read'].split()) == 159

def missing_question_source_contract():
    with fixture('question-source-removal'):
        base = analytics.compute(dt.date(2026,10,14), jobs=[], now='2026-10-14T15:00:00+02:00')['community_card']
        for sources in ([{'messages': [{'body': 'ivory workflow'}], 'employer': 'Acme', 'client_slug': 'secret'}], []):
            for invalid in ('unknown-id', None, [], {}, 17, True):
                card = copy.deepcopy(base); card['question_id'] = invalid
                assert analytics.validate_community_card(card, sources)['question_id'] is None
                assert '<p class="question">' not in analytics.public_onepager_html(card)
            missing = copy.deepcopy(base); missing.pop('question_id', None)
            assert analytics.validate_community_card(missing, sources)['question_id'] is None
            for field in ('question', 'question_id'):
                card = copy.deepcopy(base); card[field] = 'What did ivory workflow mean?'
                assert analytics.validate_community_card(card, sources)['question_id'] is None
                assert analytics.snapshot_public_card({'community_card': card}, sources)['question_id'] is None
                assert '<p class="question">' not in analytics.public_onepager_html(card)

REFERENCES = pathlib.Path(__file__).resolve().parent.parent / 'references'

def report_structure_contract():
    """The approved summary has the fixed label order and one closing offer; check-report accepts it."""
    text = (REFERENCES / 'chat-report-example.md').read_text(encoding='utf-8')
    labels = ['**Your funnel**', "**What's working**", '**Where it leaks**', '**Pipeline & money**', "**Last week's goals**", '**This week**', "**Couldn't check**"]
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions), 'Weekly summary labels are out of order.'
    closing = text.strip().splitlines()[-1]
    assert closing.count('?') == 1 and 'earned' in closing, 'The closing is one badge line and ONE offer.'
    def row(key, value, k, n, previous, **extra):
        return dict(key=key, value=value, state='ok', finished=dict(k=k, n=n), pending=dict(n=0), change=dict(previous_value=previous), **extra)
    snapshot = {'week': '2026-W42', 'north_star': {'wins': 3, 'value': 4200, 'currency': 'USD'}, 'funnel_score': {'score': 88, 'previous': 81},
        'kpis': {'weekly_volume': {'k': 31, 'target': 25, 'state': 'ok'}, 'speed_10min': {'k': 26, 'state': 'ok'}}, 'forecast': {'next_30_days': 3500}, 'goals_review': [{}, {}], 'goals_next': [{}, {}],
        'presentation': {'scorecard': [row('reply_rate', 20.714, 29, 140, 18), row('reply_to_call', 31.03, 9, 29, 28), row('booked_to_held', 88.9, 8, 9, 90),
            dict(row('proposal_to_won', 50, 3, 6, 40), pending=dict(n=2)),
            dict(row('proposal_on_time', 100, 8, 8, None), split=[dict(k=8, n=8, value=100, previous_value=88)])]},
        'report_facts': {'weekly': dict(invites=4, invites_answered=4, invites_within_hour=4, invite_reply_minutes=30, invite_calls=1, price_before_budget=3, price_read_calls=4, cautious_clients=2),
            'four_weeks': dict(quiet_chats=9, connects_spend=384, application_contract_value=4400), 'live': dict(total=11, proposals=2),
            'goal': dict(offered_times=7, replies=9, booked=4, budget_first=1, calls=4), 'pattern': dict(reply_rate=31, comparison_reply_rate=15, jobs=64)}}
    checked = analytics.check_report(text, snapshot)
    assert checked['status'] == 'PASS', checked['errors']
    for old, new in (('| 28%', '| new'), ('| 29 of 140 | 21%', '| 29 of 140 | 25%'), ('went from 81', 'went from 80')):
        assert analytics.check_report(text.replace(old, new), snapshot)['status'] == 'FAIL', old
    review = (REFERENCES / 'call-review-example.md').read_text(encoding='utf-8')
    labels = ['**Call score: ', '**The moment that mattered**', '**Next time, try this**', '**Send this now**', '**Agreed next step**', '**The nine points**', "**Couldn't check**"]
    positions = [review.index(label) for label in labels]
    assert positions == sorted(positions), 'Call review labels are out of order.'

def call_score_contract():
    """Call Score is computed in code: met and half of partly over applicable points; not needed is excluded."""
    def points(*states): return [{'point': index + 1, 'state': state} for index, state in enumerate(states)]
    assert analytics.call_score(points(*['met'] * 7, 'partly', 'not_needed'))['score'] == 94
    assert analytics.call_score(points('met', 'partly', 'missing', 'not needed')) == {'score': 50, 'met': 1, 'partly': 1, 'applicable': 3}
    assert analytics.call_score(points('not_needed', 'not needed'))['score'] is None
    assert analytics.call_score([])['score'] is None
    seven = analytics.call_score(points(*['met'] * 7, 'partly', 'not_needed'))
    card = {'call_score': seven}
    text = 'Call score: 94 · 7 of 8 points met, 1 partly'
    assert analytics.check_report(text, {'call_cards': [card]})['status'] == 'PASS'
    for wrong in ('Call score: 95', 'Call score: 94 · 6 of 8 points met, 1 partly'):
        assert analytics.check_report(wrong, {'call_cards': [card]})['status'] == 'FAIL', wrong
    assert 'call_score' in analytics.facts_sheet({'call_cards': [card]})['call_cards'][0]

CHECKS = (report_structure_contract, call_score_contract, missing_question_source_contract, owner_goal_join_contract, owner_badge_progress_contract, owner_review_fields_contract, privacy_contract, once_review_contract, closed_question_entries, approximate_number_contract, distinct_call_contract, legacy_session_contract, report_identifier_contract, custom_coverage_contract, product_review_computations, weekly_accountability_contract, owner_habit_period_contract,)

if __name__ == "__main__":
    run_checks(CHECKS)
