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
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import fixture, seed, record, records, run, analytics_sync_marker, EXAMPLE_CALL_READ, analytics_payload
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


# All synthetic attack strings identified in r2-privacy, including fragments and
# the fixed brand as an attempted dynamic injection (the static footer stays).
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
        # Exercise the real import/export selection and HTML writer. Browser raster
        # capture is stubbed here; the full fixture separately measures a real PNG.
        def capture(args, **kwargs):
            target = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--screenshot='))
            pathlib.Path(target).write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 1080, 1350))
            return __import__('subprocess').CompletedProcess(args, 0, '', '')
        for probe in R2_PRIVACY_PROBES:
            # Unknown question IDs and legacy text each fail closed through all paths.
            for field in ('question', 'question_id'):
                card = copy.deepcopy(base['community_card']); card['question_id'] = None; card[field] = probe
                checked = analytics.validate_community_card(copy.deepcopy(card), sources)
                assert checked['question_id'] is None and 'question' not in checked, (field, probe)
                direct = analytics.public_onepager_html(card)
                assert '<p class="question">' not in direct
                assert '<footer><span>Upwork Blueprint' in direct
                canonical = analytics.validated_community({field: probe}, sources)
                assert canonical == {'question_id': None}
                for overlay in ({'community_card': {'next_focus': analytics.LABELS['reply_rate'], field: probe}},
                                {'community': {field: probe}}):
                    result = copy.deepcopy(base); result['community_card']['question_id'] = None
                    analytics.claude_fields(result, overlay)
                    assert result['community_card']['question_id'] is None
                    assert '<p class="question">' not in analytics.public_onepager_html(analytics.snapshot_public_card(result, sources))
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
                    assert '<p class="question">' not in pathlib.Path(exported['html']).read_text()
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
    print('PASS owner question entries: all 27 r2 probes x legacy/ID; direct renderer, both overlays, record/ledger, JSON/JSONL import/export; fixed brand retained; finite templates only.')


def name_and_pending_contract():
    with fixture('name-pending') as folder:
        for full, expected in (('Maya Chen', 'Maya C.'), ('Maya', 'Maya'), ('Maya Jane Chen', 'Maya C.')):
            (folder / 'context/me.md').write_text('Name: ' + full + '\n')
            assert analytics.public_member_name() == expected
            card = analytics.compute(dt.date(2026, 10, 19), jobs=[], now='2026-10-19T12:00:00+02:00')['community_card']
            assert card['member_name'] == expected and expected in analytics.public_onepager_html(card)
        analytics_sync_marker(folder)
        job = {'id': '991000021', 'source': 'outbound', 'status': 'call',
               'call_booked_at': '2026-10-01T09:00:00+02:00',
               'call_scheduled_at': '2026-10-18T10:00:00+02:00',
               'call_session_id': 'meeting-pending',
               'call_sessions': {'meeting-pending': {'scheduled_at': '2026-10-18T10:00:00+02:00'}}}
        seed(job)
        snapshot = analytics.compute(dt.date(2026, 10, 19), now='2026-10-19T12:00:00+02:00')
        assert snapshot['kpis']['booked_to_held']['n'] == 0
        row = next(row for row in snapshot['presentation']['scorecard'] if row['key'] == 'booked_to_held')
        assert row['finished']['n'] == 0 and row['pending'] == {'n': 1, 'until': '2026-10-20'}, row
        # Render the actual TSX consumer with the computed pending row.
        node = r"""
const fs=require('fs'), React=require('react'), {renderToStaticMarkup}=require('react-dom/server');
const {transformSync}=require('next/dist/build/swc');
function load(file, req=require){const module={exports:{}};const code=transformSync(fs.readFileSync(file,'utf8'),{filename:file,swcrc:false,configFile:false,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2020',transform:{react:{runtime:'automatic'}}},module:{type:'commonjs'}}).code;new Function('require','module','exports',code)(req,module,module.exports);return module.exports;}
const contract=load('lib/analytics-contract.ts');
const Card=load('components/FunnelScorecard.tsx',name=>name==='@/lib/analytics-contract'?contract:require(name)).default;
const snapshot=JSON.parse(process.argv[1]);
const markup=renderToStaticMarkup(React.createElement(Card,{scorecard:snapshot.presentation.scorecard,kpis:snapshot.kpis,jobs:[],choose:()=>{},onConversations:()=>{}}));
if(!markup.includes('+1 pending until 2026-10-20'))throw Error('Scheduled pending case not displayed');
console.log('PASS rendered Show-up: +1 pending until 2026-10-20');
"""
        __import__('subprocess').run(['node','-e',node,json.dumps(snapshot)], cwd=analytics.ROOT / 'website', check=True)
        ended = analytics.compute(dt.date(2026, 10, 21), now='2026-10-21T12:00:00+02:00')
        row = next(row for row in ended['presentation']['scorecard'] if row['key'] == 'booked_to_held')
        assert row['finished']['n'] == 1 and row['pending']['n'] == 0
    print('PASS owner name/pending: two/one/multiple tokens; Oct1 booking/Oct18 meeting remains pending Oct19, matures Oct20; scorecard consumes pending.')


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
    print('PASS owner number words: dozen/couple/pair/half-dozen/hundred mapped once; zero-win lies and unprovable quantified hundreds fail.')


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
    print('PASS owner distinct calls: meeting-ID and transcript identities; second call current in cockpit/weekly; each session immutable; historical first retained.')


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
        # No prior session pointer: the legacy review must never acquire second's identity.
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
        assert card['points'][0]['quote'] == second['agreed_step'] and card['date'] == '2026-10-13'
        record(jid, {'call_session_id': 'first'})
        assert records()[jid]['call_review'] == first
        assert records()[jid]['call_reviewed_at'] == first_saved['call_reviewed_at']
        record(jid, {'call_session_id': 'third'})
        assert 'call_review' not in records()[jid] and 'call_review_session' not in records()[jid]
        card = json.loads(run('cockpit.py', 'job', jid).stdout)['call_cards'][0]
        assert not card['reviewable'] and not card['points'] and card['coach_read'] is None
        # A snapshot card must also clear when no markdown companion exists.
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
    print('PASS independent findings: legacy context FIRST archives first exact timestamp; second owns current review; context-only switches restore matching timestamps or clear card; unknown/unverified IDs reject before persisted mutation.')


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
    print('PASS explicit question IDs: unknown/missing/null/malformed suppressed; retained and removed private sources both reject legacy/injected text.')


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
    print('PASS report identifiers: long IDs, backticks, URLs, paths, ISO dates/times and job/job ID/id/# tokens ignored; adjacent true values pass and false counts/money/rates still fail.')


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
        command = (analytics.ROOT / '.claude/commands/analytics.md').read_text()
        assert all(fragment in command for fragment in ('{coverage: {missing: [{source: "proposal_insights", what:',
            'blocks: ["proposal_views"], how_to_supply:', 'all three nonempty fields',
            "Include every custom gap's `what`, blocked KPI/review,", '**What I couldn\'t check** and the facts sheet'))
    print('PASS custom coverage: canonical/live/legacy input; four full gaps and same-source distinct gaps persist in facts/readback/record; all six known canonical four-field gaps match legacy coverage with computed dependencies protected and no added what; omissions/empty/invalid/malformed inputs rejected; exact record comparison and chat directive enforced.')


def run_all():
    report_identifier_contract()
    custom_coverage_contract()
    approximate_number_contract()
    legacy_session_contract()
    missing_question_source_contract()
    name_and_pending_contract()
    distinct_call_contract()
    closed_question_entries()
    privacy_contract()
    review_contract()
    once_review_contract()


if __name__ == '__main__':
    run_all()
