#!/usr/bin/env python3
"""Frozen final contract regressions. Synthetic sources, isolated temporary storage."""
import copy
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import fixture, run, seed, record, records, analytics_stamp

POINTS = ('answered_question', 'qualifying_question', 'call_times')


def thread_references():
    with fixture('final-thread-references') as folder:
        jid = '945000001'
        seed({'id': jid, 'status': 'applied', 'source': 'outbound', 'applied_at': '2026-10-01T08:00:00+00:00'})
        source = {'threads': [{'job_id': jid, 'room_id': 'room-a', 'messages_complete': True,
                              'messages': [{'from': 'client', 'at': '2026-10-01T09:00:00+00:00', 'text': 'Can you help?'},
                                           {'from': 'me', 'at': '2026-10-01T09:01:00+00:00', 'text': 'Yes, Tuesday at ten or Wednesday at two.'}]}]}
        run('sync.py', 'apply', '--file', '-', value=source)
        lead = records()[jid]
        ref = lead['thread_refs']['room-a']
        assert ref['messages_complete'] is True and ref['last_writer'] == 'me' and ref['source'] == 'upwork-thread'
        dt.datetime.fromisoformat(ref['fetched_at'])
        raw = json.loads((folder / 'jobs' / jid / 'thread.json').read_text())
        assert raw['messages_complete'] is True and raw['rooms']['room-a']['messages_complete'] is True
        review = {'read': True, 'last_writer': 'me', 'points': {key: {'state': 'missing', 'quote': '', 'reason': 'Not found in complete messages.'} for key in POINTS}}
        review['points']['call_times'] = {'state': 'met', 'quote': 'Tuesday at ten or Wednesday at two', 'reason': 'Two times offered.'}
        record(jid, {'conversation_review': review})
        assert records()[jid]['conversation_review'] == review
        for change in ('unknown-field', 'missing-point', 'unread-positive', 'no-quote', 'not-needed-no-reason', 'invented-quote'):
            broken = copy.deepcopy(review)
            if change == 'unknown-field': broken['guess'] = True
            elif change == 'missing-point': broken['points'].pop('answered_question')
            elif change == 'unread-positive': broken['read'] = False
            elif change == 'no-quote': broken['points']['call_times']['quote'] = ''
            elif change == 'invented-quote': broken['points']['call_times']['quote'] = 'This sentence was never written.'
            else: broken['points']['answered_question'].update(state='not_needed', reason='')
            result = run('pipeline.py', 'record', jid, '--file', '-', value={'conversation_review': broken}, success=False)
            assert result.returncode != 0, change
        # A partial refresh must not imply that an unread window is a complete thread.
        source['threads'][0].update(room_id='room-b', messages_complete=False)
        source['threads'][0]['messages'].append({'from':'client','at':'2026-10-01T09:02:00+00:00','text':'Please wait for the other inputs.'})
        run('sync.py', 'apply', '--file', '-', value=source)
        refs = records()[jid]['thread_refs']
        assert set(refs) == {'room-a', 'room-b'} and refs['room-a']['messages_complete'] is True
        assert refs['room-b']['messages_complete'] is False
        raw = json.loads((folder / 'jobs' / jid / 'thread.json').read_text())
        assert set(raw['rooms']) == {'room-a', 'room-b'} and raw['rooms']['room-b']['messages_complete'] is False
        assert raw['messages_complete'] is False
        assert run('pipeline.py','record',jid,'--file','-',value={'conversation_review':review},success=False).returncode != 0
        import analytics
        unread=analytics.conversation_reviews([records()[jid]],dt.date(2026,10,14))['threads'][0]
        assert unread['read'] is False and unread['last_writer']=='client'
        assert all(point['state']=='missing' for point in unread['points'].values())
        for change in ('missing-identity', 'fake-source', 'not-boolean', 'bad-time'):
            broken = copy.deepcopy(refs)
            if change == 'missing-identity': broken['room-a']['room_id'] = ''
            elif change == 'fake-source': broken['room-a']['source'] = 'guess'
            elif change == 'not-boolean': broken['room-a']['messages_complete'] = 1
            else: broken['room-a']['fetched_at'] = 'yesterday'
            result = run('pipeline.py', 'record', jid, '--file', '-', value={'thread_refs': broken}, success=False)
            assert result.returncode != 0, change
    print('PASS E: stable room references, complete/partial preservation, three-point content schema, unread and unsupported finding refusal.')


def score_contract():
    import analytics
    def snapshot():
        kpis = {key: {'value': 100, 'target': 100, 'n': 10, 'state': 'pass'} for key in analytics.LEVERS}
        kpis['first_reply'].update(value=5, target=5)
        kpis.update({key: {'n': 10, 'state': 'pass', 'rung_reached': 3, 'baseline_phase': False}
                     for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won')})
        return {'week': '2026-W42', 'kpis': kpis}
    full = snapshot()
    assert analytics.funnel_score(full)['score'] == 100
    above = copy.deepcopy(full)
    for key in analytics.LEVERS:
        above['kpis'][key]['value'] = 1 if key == 'first_reply' else 1000
    assert analytics.funnel_score(above)['score'] == 100, 'Nothing extra above target.'
    half = copy.deepcopy(full)
    half['kpis']['speed_10min'].update(value=50)
    assert analytics.funnel_score(half)['score'] == 94
    # One unavailable twelve-point part drops out; remaining 88 points become 100.
    half['kpis']['speed_10min'].update(n=0, value=None)
    score = analytics.funnel_score(half)
    assert score['score'] == 100 and any(row['part'] == 'speed_10min' for row in score['dropped'])
    empty = snapshot()
    for key, row in empty['kpis'].items(): row.update(n=0, value=None, target=0)
    assert analytics.funnel_score(empty)['score'] is None, 'Never award 0 of 0.'
    baseline = snapshot()
    for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'proposal_to_won'):
        baseline['kpis'][key].update(baseline_phase=True, rung_reached=0)
    score = analytics.funnel_score(baseline)
    assert score['baseline_only'] is True and score['score'] == 100 and score['parts']['results'] is None
    undecided = snapshot()
    undecided['kpis']['reply_rate'].update(state='undecided', rung_reached=2)
    assert analytics.funnel_score(undecided)['score'] == 97, 'An undecided next rung retains the lower level.'
    partial_source=copy.deepcopy(full)
    partial_source['kpis']['speed_10min'].update(unknown_n=1,value=80,n=100)
    score=analytics.funnel_score(partial_source)
    assert score['score']==100 and {'part':'speed_10min','reason':'unknown source'} in score['dropped']
    mature_without_week=copy.deepcopy(full)
    mature_without_week['kpis']['reply_rate'].update(n=100,weekly_opportunities=0,rung_reached=0)
    score=analytics.funnel_score(mature_without_week)
    assert score['score']==100 and any(part['part']=='reply_rate' for part in score['dropped']), 'A mature rolling cohort does not invent this-week opportunities.'
    previous = [{'week': '2026-W40', 'funnel_score': {'score': 70}}, {'week': '2026-W41', 'funnel_score': {'score': 81}}]
    assert analytics.funnel_score(full, previous)['previous'] == 81
    with fixture('final-baseline-boundary') as folder:
        from analytics_fixture import analytics_sync_marker
        analytics_sync_marker(folder)
        start=dt.date(2026,8,24)
        jobs=[{'id':'945000099','source':'outbound','applied_at':analytics_stamp(start),'speed_to_lead_s':120,'job_fit':{'state':'pass','reason':'Fits'}}]
        for week in range(1,5):
            assert analytics.compute(start+dt.timedelta(weeks=week),jobs=jobs)['funnel_score']['baseline_only'] is True
        assert analytics.compute(start+dt.timedelta(weeks=5),jobs=jobs)['funnel_score']['baseline_only'] is False
    print('PASS L: rescaling, 0-of-0, baseline-only, undecided lower rung, previous score and cap above target.')


def scorecard_missing_and_cards():
    import analytics
    from analytics_fixture import analytics_sync_marker
    today = dt.date(2026, 10, 14)
    with fixture('final-scorecard-and-missing') as folder:
        analytics_sync_marker(folder)
        jobs = [{'id': '945000010', 'source': 'outbound', 'status': 'won',
                 'applied_at': '2026-09-18T10:00:00+02:00', 'replied_at': '2026-09-18T10:03:00+02:00',
                 'call_held_at': '2026-09-19T10:00:00+02:00', 'won_at': '2026-09-20T10:00:00+02:00'},
                {'id': '945000011', 'source': 'outbound', 'status': 'replied',
                 'applied_at': '2026-10-12T10:00:00+02:00', 'replied_at': '2026-10-12T10:03:00+02:00'}]
        snapshot = analytics.compute(today, jobs=jobs)
        required = {'key','group','name','stage_label','period_label','value','finished','pending','change','series','target','next_action','split','focus','market'}
        scorecard = snapshot['presentation']['scorecard']
        assert scorecard and all(required <= row.keys() for row in scorecard)
        assert len({row['key'] for row in scorecard}) == len(scorecard)
        assert set(row['group'] for row in scorecard) == {'top','middle','bottom'}
        assert len({row['period_label'] for row in scorecard}) == 1
        assert all(len(row['series']['points']) == 8 for row in scorecard)
        assert {row['name'] for row in scorecard if row['key'] in ('reply_rate','reply_to_call','booked_to_held','proposal_to_won')} == {'Reply rate','Call rate','Show-up rate','Win rate'}
        assert 'held_to_proposal' not in {row['key'] for row in scorecard}
        proposal = next(row for row in scorecard if row['key'] == 'proposal_on_time')
        assert proposal['name'] == 'Proposal within 30 min of call end' and proposal['split']
        assert all(not any(word in row['change']['comparison_label'].lower().split() for word in ('pp','points')) for row in scorecard)
        missing = snapshot['coverage']['missing']
        assert missing and all(set(row) == {'source','blocks','how_to_supply'} and row['how_to_supply'] for row in missing)
        assert any(row['source'] == 'call transcript:945000010' for row in missing)
        assert any(row['source'] == 'contract terms:945000010' for row in missing)
        assert any(row['source'] == 'sent copy:945000010' for row in missing)
        review = snapshot['conversation_review']['threads'][0]
        assert review['lead_id'] == '945000011' and review['read'] is False
        assert all(point['state'] == 'missing' for point in review['points'].values())
        call_rate = next(row for row in scorecard if row['key']=='reply_to_call')
        assert call_rate['split'] == [] and call_rate['content_link']['view'] == 'conversations'
        card=snapshot['community_card']
        assert card['funnel_score'] == snapshot['funnel_score']
        assert {'reply_rate','reply_to_call','booked_to_held','proposal_to_won'} <= card.keys()
        assert analytics.validate_community_card(card) == card
        assert 'Funnel Score' in analytics.public_onepager_html(card) and 'weeks in a row' not in analytics.public_onepager_html(card)
        # Coach text is read from the same private saved call file, never reconstructed from a summary.
        path=folder/'jobs'/'945000010';path.mkdir()
        (path/'call-review.md').write_text("## Coach's read\n\nEXAMPLE evidence read.\n\n## Nine points\n\nSaved below.\n\n## Next step\n\nConfirm Friday.\n")
        private=dict(snapshot, reviews={'call': {'rubric':[{'lead_id':'945000010','reviewable':False,'points':[]}]}})
        call=analytics.call_cards(private,jobs)[0]
        assert call['coach_read'] is None and call['coach_read_state'] == 'unknown'
        assert call['agreed_step'] is None and call['next_message'] is None
        (path/'call-review.md').unlink()
        assert analytics.call_cards(private,jobs)[0]['coach_read'] is None
        assert call['coach_read_prompt'] == 'No review yet: run /call-review 945000010'
    print('PASS A/F/M: scorecard groups/names/period/8 points, integrated proposal stage, missing-source inventory, unread threads, canonical public score/rates, saved Coach read and fallback.')


def badge_calibration():
    import analytics, badges
    from analytics_fixture import analytics_sync_marker
    today=dt.date(2026,10,14)
    with fixture('final-qualifying-weeks') as folder:
        analytics_sync_marker(folder)
        jobs=[{'id':'945000020','source':'outbound','applied_at':'2026-10-12T10:00:00+02:00','job_fit':{'state':'pass','reason':'Fits'},
               'application_review':{'state':'pass','reason':'Reviewed submitted content'},'speed_to_lead_s':120,'application_facts':{'posted_age_band':'<10m'}}]
        base=analytics.compute(today,jobs=jobs)
        base['kpis']['speed_10min'].update(state='pass',value=100,n=1,k=1)
        base.pop('badge_qualifying',None)
        # Each independent case has exactly the count of qualifying weeks, with pauses between.
        for weeks,tier in ((1,'Bronze'),(3,'Silver'),(6,'Gold'),(13,'Platinum'),(26,'Legend')):
            history=[dict(base, week=(today-dt.timedelta(weeks=i+1)).strftime('%G-W%V'),badges=[],badge_qualifying={'Swift Sail':True}) for i in range(weeks-1)]
            actual=analytics.badge_results(copy.deepcopy(base),jobs,history,today)
            swift=[row for row in actual if row['badge']=='Swift Sail']
            assert swift and swift[-1]['tier']==tier, (weeks,swift)
            assert len([row for row in actual if row['new']]) <= 2 if weeks==1 else True
        pauses=[dict(base,week='2026-W39',badges=[],badge_qualifying={'Swift Sail':True}),
                dict(base,week='2026-W40',badges=[],badge_qualifying={'Swift Sail':False}),
                dict(base,week='2026-W41',badges=[],badge_qualifying={'Swift Sail':True})]
        actual=analytics.badge_results(copy.deepcopy(base),jobs,pauses,today)
        assert [row for row in actual if row['badge']=='Swift Sail'][-1]['tier']=='Silver'
        low_quality=copy.deepcopy(jobs);low_quality[0].pop('application_review')
        assert not any(row['badge']=='Swift Sail' for row in analytics.badge_results(copy.deepcopy(base),low_quality,[],today))
        none=copy.deepcopy(base);none['kpis']['speed_10min'].update(n=0,value=None,state='no opportunities')
        assert not any(row['badge']=='Swift Sail' for row in analytics.badge_results(none,[],[],today))
        assert not hasattr(badges, 'rank')
        assert 'rank' not in base and 'rank' not in base['presentation']['voyage']
        points=[{'point':p,'state':'met','quote':'Proof'} for p in range(1,10)]
        points[8].update(state='not needed',reason='Informed disqualification; proposal not appropriate.')
        assert badges._call_fraction(points)==1
        points[8].pop('reason')
        assert badges._call_fraction(points) is None
    print('PASS B/K: accumulated1/3/6/13/26, pauses retain progress, first-week max2, content gate, zero-opportunity neutrality, rank absent and reasoned disqualification.')


def catchup_contract():
    import analytics
    from analytics_fixture import analytics_sync_marker
    today=dt.date(2026,10,14)
    with fixture('final-missed-weeks') as folder:
        analytics_sync_marker(folder)
        baseline=analytics.compute(dt.date(2026,9,16),jobs=[])
        (folder/'data/analytics-history.jsonl').write_text(json.dumps(baseline)+'\n')
        goal={'kpi':'weekly_volume','stage':analytics.LABELS['weekly_volume'],'change':'Protect application time','start':'2026-09-16','primary':True,
              'cue':'At the start of each day','action':'Apply to fitting jobs','fallback':'Apply to one fitting job','review_on':'2026-09-23'}
        gap_keys=('weekly_volume','reply_rate','speed_10min')
        gap_goals=[dict(goal,kpi=key,stage=analytics.LABELS[key],change=f'Review gap commitment {index}',primary=index==0) for index,key in enumerate(gap_keys)]
        analytics.add_goals({'week':'2026-W38','goals':gap_goals})
        missed=analytics.compute_catchup(today,jobs=[])
        assert [row['week'] for row in missed]==['2026-W39','2026-W40','2026-W41']
        assert all(row['gap']['weeks_missed']==3 for row in missed)
        assert all({'point-in-time pipeline','point-in-time proposal status','point-in-time Connects balance'} <= {gap['source'] for gap in row['coverage']['missing']} for row in missed)
        assert all(row['forecast']['next_30_days'] is None for row in missed)
        current=analytics.compute(today,jobs=[])
        assert current['gap']['weeks_missed']==3 and current['goals_review']
        assert {review['kpi'] for review in current['goals_review']}==set(gap_keys)
        assert all(review['start']=='2026-09-16' for review in current['goals_review'])
        assert len((folder/'data/analytics-history.jsonl').read_text().splitlines())==1, 'Pure catch-up never records.'
        from analytics_fixture import analytics_payload
        saved=analytics.record_snapshot(analytics_payload(current))
        persisted=[json.loads(line) for line in (folder/'data/analytics-history.jsonl').read_text().splitlines()]
        assert [row['week'] for row in persisted]==['2026-W38','2026-W39','2026-W40','2026-W41','2026-W42']
        assert len({row['week'] for row in persisted})==5 and saved['gap']['weeks_missed']==3
        assert analytics.compute_catchup(today,jobs=[])==[]
    print('PASS G: atomic catch-up storage and deduplication, exactly one snapshot per missed full week; historical point-in-time facts unknown; gap goal retained for full-period review; pure catch-up never writes.')

def immediate_call_review_writer():
    with fixture('final-immediate-call-review') as folder:
        jid='945000030'
        seed({'id':jid,'source':'outbound','status':'call','call_held_at':'2026-10-12T10:00:00+02:00'})
        path=folder/'jobs'/jid;path.mkdir()
        quote='Three hours of manual work each week.'
        text='Member: Maya\nComplete: yes\nLanguage: English\nMaya: What changes when this is solved?\nClient: '+quote+'\n'
        (path/'call.md').write_text(text)
        (path/'call-review.md').write_text("## Coach's read\n\nExample saved call review.\n\n## Nine points\n\nSaved via pipeline.\n\n## Next step\n\nReview Friday.\n")
        review={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote} for p in range(1,10)],
                'moments':[{'quote':quote,'better_wording':'Ask what the saved time enables.'}],
                'fix':'Confirm the owner','example':'Who owns the next step?','next_step':'Review Friday.'}
        record(jid,{'call_review':review})
        view=json.loads(run('cockpit.py','job',jid).stdout)
        assert not (folder/'data/analytics-history.jsonl').exists()
        card=view['call_cards'][0]
        assert card['coach_read']=='Example saved call review.' and len(card['points'])==9
        assert all(point['quote']==quote for point in card['points'])
        for change in ('duplicate','invented-quote','not-needed-no-reason','partial-source'):
            broken=copy.deepcopy(review)
            if change=='duplicate':broken['points'][-1]['point']=1
            elif change=='invented-quote':broken['points'][0]['quote']='Invented turn.'
            elif change=='not-needed-no-reason':broken['points'][0]['state']='not needed'
            else:(path/'call.md').write_text(text.replace('Complete: yes','Complete: no'))
            assert run('pipeline.py','record',jid,'--file','-',value={'call_review':broken},success=False).returncode != 0
    print('PASS M/22: immediate pipeline call-review writer, complete transcript and quote validators, live lead card before any weekly snapshot.')


def summary_contract():
    import analytics
    with fixture('final-summary-input'):
        snapshot=analytics.compute(dt.date(2026,10,14),jobs=[])
        supplied=['This example uses isolated synthetic evidence.', 'Sources that are missing remain unknown.', 'Agree the next useful action at the weekly review.']
        assert analytics.validate_summary(supplied,snapshot)==supplied
        assert analytics.validate_summary([],snapshot)==[]
        value=copy.deepcopy(snapshot);value['summary']=supplied
        assert analytics.prepare_snapshot(value,dt.date(2026,10,14))['summary']==supplied
        for broken in (supplied[:2],supplied+['Another sentence.'],['word '*19+'.']+supplied[1:],
                       ['Two sentences. Another sentence.']+supplied[1:],['Unknown number 9988776655.']+supplied[1:],
                       ['This has an em dash — here.']+supplied[1:]):
            try:analytics.validate_summary(broken,snapshot)
            except ValueError:pass
            else:raise AssertionError('Malformed or unsupported summary accepted.')
    print('PASS M summary: supplied three short English sentences, unknown default, unsupported-number and malformed-prose refusal.')


def public_latest_goals_contract():
    import analytics
    with fixture('final-public-latest-goals'):
        today=dt.date(2026,10,14);snapshot=analytics.compute(today,jobs=[])
        reviews=[{'start':start,'change':f'{prefix} goal {index}','done_k':done,'done_n':1,'execution_state':'complete' if done else 'undone'}
                 for start,prefix,done in (('2026-09-30','Older',0),('2026-10-07','Recent',1)) for index in range(3)]
        for start,week in (('2026-09-30','2026-W40'),('2026-10-07','2026-W41')):
            keys=('weekly_volume','reply_rate','reply_to_call')
            goals=[{'start':start,'kpi':keys[index],'stage':analytics.LABELS[keys[index]],'change':review['change'],'primary':index==0,'cue':'When the stage starts','action':'Use the agreed next step','fallback':'Use one smaller step','review_on':(dt.date.fromisoformat(start)+dt.timedelta(days=7)).isoformat()} for index,review in enumerate([row for row in reviews if row['start']==start])]
            analytics.add_goals({'week':week,'goals':goals})
        snapshot['goals_review']=reviews
        card=analytics.community_card([],today,snapshot['kpis'],reviews,snapshot['week'],0)
        card['funnel_score']=snapshot['funnel_score']
        assert len(snapshot['goals_review'])==6 and len(card['goals'])==3 and card['goals_done']=='3/3'
        assert all(goal['text'].startswith('Recent') and goal['done'] for goal in card['goals'])
        assert analytics.validate_community_card(card)==card
        html=analytics.public_onepager_html(card)
        assert 'Last agreed goals' in html and 'Agreed goals carried out' not in html
        broken=copy.deepcopy(card);broken['goals'].append(copy.deepcopy(card['goals'][0]))
        try:analytics.validate_community_card(broken)
        except ValueError:pass
        else:raise AssertionError('Public card accepted more than three latest agreed goals.')
    print('PASS M public goals: latest three agreed goals and checks only; all six private reviews retained; oversized public goal list refused.')


def repeated_conversation_pattern():
    import analytics
    with fixture('final-repeated-conversation-pattern') as folder:
        jobs=[]
        for index in range(2):
            jid=str(945000040+index)
            row={'id':jid,'source':'outbound','status':'replied','replied_at':'2026-10-01T10:00:00+02:00'}
            seed(row)
            messages=[{'from':'client','at':'2026-10-01T10:00:00+02:00','text':'How does the audit scope work?'},
                      {'from':'me','at':'2026-10-01T10:01:00+02:00','text':'The scope covers the agreed audit inputs. Which input is ready?'}]
            run('sync.py','apply','--file','-',value={'threads':[{'job_id':jid,'room_id':'pattern-'+jid,'messages_complete':True,'messages':messages}]})
            points={key:{'state':'met','quote':messages[1]['text'],'reason':'Supported by the saved member answer.'} for key in POINTS}
            points['call_times']={'state':'missing','quote':'','reason':'No two concrete call times offered.'}
            record(jid,{'conversation_review':{'points':points,'read':True,'last_writer':'me'}})
            jobs.append(records()[jid])
            result=analytics.conversation_reviews(jobs,dt.date(2026,10,14))
            if index==0:assert result['pattern'] is None, 'One quiet thread is not a repeated pattern.'
            else:assert result['pattern']=='In 2 of 2 quiet threads, a useful call proposal was missing.'
            assert all(thread['read'] for thread in result['threads'])
    print('PASS E repeated pattern: one reviewed thread stays a single finding; two quoted reviewed threads produce the counted repeated pattern.')


def frozen_projection_contract():
    import analytics, badges, cockpit
    today=dt.date(2026,10,14)
    with fixture('frozen-content-projections') as folder:
        jid='945000080'; quote='The audit needs one agreed owner.'; reason='Confirm the owner before offering a date.'
        seed({'id':jid,'source':'outbound','status':'call','applied_at':analytics_stamp(today-dt.timedelta(days=2)),
              'replied_at':analytics_stamp(today-dt.timedelta(days=2)),
              'call_held_at':analytics_stamp(today-dt.timedelta(days=1)),
              'proposal_sent_at':analytics_stamp(today-dt.timedelta(days=1),11),
              'application_sent_verified':True,
              'application_review':{'state':'pass','quote':quote,'reason':reason,'free_read':'Saved application read.',
                  'points':[{'point':1,'state':'met','quote':quote,'reason':reason}]},
              'proposal_review':{'state':'pass','quote':quote,'reason':reason,'free_read':'Saved proposal read.',
                  'points':[{'point':1,'state':'met','quote':quote,'reason':reason}]}})
        path=folder/'jobs'/jid;path.mkdir()
        (path/'application.sent.md').write_text(quote)
        (path/'loom.md').write_text('EXAMPLE Loom source: '+quote)
        (path/'proposal.md').write_text(quote)
        (path/'call.md').write_text('Member: Maya\nComplete: yes\nLanguage: English\nMaya: Who owns the audit?\nClient: '+quote+'\n')
        (path/'call-review.md').write_text("## Coach's read\n\nSaved call read.\n\n## Next message\n\nCan you confirm the audit owner?\n\n## Next step agreed on the call\n\nClient confirms the owner by Friday.\n\n## Nine points\n\nSaved below.\n")
        call={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote,'reason':reason} for p in range(1,10)]}
        record(jid,{'call_review':call})
        run('sync.py','apply','--file','-',value={'threads':[{'job_id':jid,'room_id':'projection','messages_complete':True,
            'messages':[{'from':'me','at':analytics_stamp(today-dt.timedelta(days=2)),'text':quote}]}]})
        chat={'read':True,'last_writer':'me','free_read':'Saved chat read.','next_message':'Who owns the audit?',
              'points':{key:{'state':'met','quote':quote,'reason':reason} for key in POINTS}}
        chat['points']['call_times']={'state':'not_needed','quote':'','reason':'No useful call was needed.'}
        record(jid,{'conversation_review':chat})
        assert badges.content_pass(records()[jid],'conversation')
        for removed in ('fast_answer','follow_ups'):
            broken=copy.deepcopy(chat);broken['points'][removed]={'state':'met','quote':quote,'reason':reason}
            assert run('pipeline.py','record',jid,'--file','-',value={'conversation_review':broken},success=False).returncode
        for field,limit in (('free_read',150),('next_message',100)):
            broken=copy.deepcopy(chat);broken[field]='word '*(limit+1)
            assert run('pipeline.py','record',jid,'--file','-',value={'conversation_review':broken},success=False).returncode
        for writer in ('pipeline','weekly'):
            broken=dict(call,next_message='word '*101)
            if writer=='pipeline':
                assert run('pipeline.py','record',jid,'--file','-',value={'call_review':broken},success=False).returncode
            else:
                try:analytics.call_coverage([dict(broken,lead_id=jid)],today)
                except ValueError:pass
                else:raise AssertionError('Weekly call next message exceeded100 words.')
        jobs=list(records().values());snapshot=analytics.compute(today,jobs=jobs)
        sections=snapshot['conversations']['sections']
        for stage in ('applications','chats','proposals'):
            entry=sections[stage][0]
            assert entry['reviewable'] and entry['quote']==quote and entry['read'].startswith('Saved '), (stage,entry)
            required={'lead_id','label','date','reviewable','source_prompt','points','quote','read','next_message','as_of','reviewed_at'}
            assert set(entry)==required | {'applications':{'sent_copy','loom_transcript'},'chats':{'last_writer'},'proposals':{'scope','price','decision_date'}}[stage]
        assert sections['calls']==snapshot['call_cards']
        card=sections['calls'][0]
        assert card['agreed_step']=='Client confirms the owner by Friday.'
        assert card['next_message']=='Can you confirm the audit owner?'
        assert [p['label'] for p in card['points'] if p['point'] in (7,9)]==['Why you','Next step on Upwork']
        patterns=snapshot['conversations']['patterns']
        assert len(patterns)==1 and patterns[0]['text']==reason
        assert {q['stage'] for q in patterns[0]['quotes']}=={'applications','chats','calls','proposals'}
        assert all(q['quote']==quote for q in patterns[0]['quotes'])
        assert 'rank' not in snapshot and 'rank' not in snapshot['community_card']
        stale=dict(snapshot,rank='obsolete')
        stale['presentation']=dict(snapshot['presentation'],rank='obsolete',voyage={'rank':'obsolete','rank_progress':{}})
        visible=cockpit.snapshot_view(stale)
        assert 'rank' not in visible and 'rank' not in visible['presentation'] and 'rank' not in visible['presentation']['voyage']
        assert not hasattr(badges,'rank')
        catalogue=badges.catalogue_metadata()
        assert set(catalogue)==set(badges.BADGE_NAMES)
        for row in catalogue.values():
            assert row['short'].endswith('.') and 0<len(row['short'].split())<=8
            assert not any(word in row['short'].casefold() for word in ('wilson','cohort','mature','denominator','statistics'))
        assert all(station['short']==catalogue[station['badge']]['short'] for station in snapshot['presentation']['voyage']['stations'])
        # Quotation mismatch, missing sent source, unverified submission and partial thread all refuse judgment.
        jobs[0]['proposal_review']['points'][0]['quote']='Not in the proposal.'
        jobs[0]['proposal_review']['quote']='Not in the proposal.'
        (path/'application.sent.md').unlink()
        thread=json.loads((path/'thread.json').read_text());thread['rooms']['projection']['messages_complete']=False
        (path/'thread.json').write_text(json.dumps(thread))
        refused=analytics.conversations_fields(snapshot,jobs)
        # Force a fresh incomplete chat projection instead of the earlier saved projection.
        snapshot['conversation_review']=analytics.conversation_reviews(jobs,today)
        refused=analytics.conversations_fields(snapshot,jobs)
        assert all(not refused['sections'][stage][0]['reviewable'] for stage in ('applications','chats','proposals'))
        assert refused['patterns']==[]
        assert all(refused['sections'][stage][0]['source_prompt'] for stage in ('applications','chats','proposals'))
        (path/'call-review.md').write_text('## Next message\n\n'+'word '*101)
        try:analytics.call_cards(snapshot,jobs)
        except ValueError:pass
        else:raise AssertionError('Call file next message exceeded100 words.')
    def mover(key,value,previous,n=10,state='pass'):
        return {'key':key,'name':key,'value':value,'state':state,'finished':{'n':n},'change':{'previous_value':previous}}
    model={'kpis':{'first_reply':{'direction':'down'},'reply_rate':{'direction':'up'}},
           'presentation':{'scorecard':[mover('first_reply',2,10),mover('reply_rate',9,10)]}}
    strip=analytics.progress_strip(model)
    assert strip['biggest_change']=={'key':'first_reply','name':'first_reply','text':'first_reply: 2, was 10','direction':'gain','value':2,'previous':10}
    model['presentation']['scorecard']=[mover('first_reply',20,10),mover('reply_rate',9,10)]
    assert analytics.progress_strip(model)['biggest_change']['key']=='first_reply'
    assert analytics.progress_strip(model)['biggest_change']['direction']=='decline'
    model['presentation']['scorecard']=[mover('reply_rate',100,None),mover('first_reply',1,10,0),mover('reply_rate',100,10,state='missing')]
    assert analytics.progress_strip(model)=={'biggest_change':None,'newest_badge':None,'newest_badge_basis':'No earned badge recorded.'}
    print('PASS frozen25–34: exact content keys and limits, retained gate, parsed call fields, quoted four-stage projection/patterns, source refusals, gain/decline/unknown, short catalogue and rank absence.')


def supervised_corrections():
    import analytics, badges, cockpit, hashlib
    today=dt.date(2026,10,14)
    with fixture('supervised-corrections') as folder:
        jid='945000090'; quote='The audit needs one agreed owner.'
        seed({'id':jid,'source':'outbound','status':'call','call_held_at':analytics_stamp(today),
              'applied_at':analytics_stamp(today-dt.timedelta(days=1)), 'application_sent_verified':True,
              'loom_url':'https://www.loom.com/share/example',
              'application_review':{'state':'pass','quote':quote,'reason':'Saved assessment',
                'free_read':'Saved application read.','points':[{'point':1,'state':'met','quote':quote,'reason':'Confirm the owner.'}]}})
        path=folder/'jobs'/jid;path.mkdir()
        transcript='Member: Maya\nComplete: yes\nLanguage: English\nMaya: Who owns the audit?\nClient: '+quote+'\n'
        (path/'call.md').write_text(transcript)
        (path/'application.sent.md').write_text(quote)
        call={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote} for p in range(1,10)]}
        for field,limit in (('free_read',180),('next_message',100)):
            allowed=dict(call,**{field:'word '*limit})
            record(jid,{'call_review':allowed})
            assert analytics.call_coverage([dict(allowed,lead_id=jid)],today)
            broken=dict(call,**{field:'word '*(limit+1)})
            assert run('pipeline.py','record',jid,'--file','-',value={'call_review':broken},success=False).returncode
            try:analytics.call_coverage([dict(broken,lead_id=jid)],today)
            except ValueError:pass
            else:raise AssertionError((field,limit))
        # No minimum is imposed on unknown-source records.
        record(jid,{'call_review':{'reviewable':False,'points':[]}})
        for field in ('free_read','agreed_step','next_message'):
            invalid={'reviewable':False,'points':[],field:'Unsupported coaching.'}
            assert run('pipeline.py','record',jid,'--file','-',value={'call_review':invalid},success=False).returncode
            try:analytics.call_coverage([dict(invalid,lead_id=jid)],today)
            except ValueError:pass
            else:raise AssertionError('Unread coaching accepted: '+field)
        for bad in ('Summary: The client liked the work.\n', transcript.replace('Complete: yes','Complete: no'),
                    transcript.replace('Maya: Who owns the audit?\n','')):
            (path/'call.md').write_text(bad)
            assert run('pipeline.py','record',jid,'--file','-',value={'call_review':call},success=False).returncode
            try:analytics.call_coverage([dict(call,lead_id=jid)],today)
            except ValueError:pass
            else:raise AssertionError('Source gate accepted incomplete or summary-only call.')
            (path/'call-review.md').write_text("## Coach's read\n\nMust remain hidden.\n")
            card=analytics.call_cards({'generated_at':analytics_stamp(today),'reviews':{'call':{'rubric':[dict(call,lead_id=jid)]}}},list(records().values()))[0]
            assert not card['reviewable'] and card['coach_read'] is None and card['agreed_step'] is None
        (path/'call.md').write_text(transcript)
        record(jid,{'call_review':call})
        snapshot=analytics.compute(today)
        card=snapshot['call_cards'][0]
        assert card['as_of']==card['reviewed_at']==records()[jid]['call_reviewed_at']
        application=snapshot['conversations']['sections']['applications'][0]
        assert not application['reviewable'] and application['read'] is None and 'Loom' in application['source_prompt']
        assert application['sent_copy']==quote and application['loom_transcript'] is None
        (path/'loom.md').write_text('Exact example Loom transcript.')
        application=analytics.conversations_fields(snapshot,list(records().values()))['sections']['applications'][0]
        assert application['reviewable'] and application['loom_transcript']=='Exact example Loom transcript.'
        # Log assessments are supported only with a saved state and a local source quotation.
        lead=records()[jid]; saved=lead.pop('application_review')
        lead['log']=[{'at':analytics_stamp(today), 'text':'analytics application_review: '+json.dumps(saved)}]
        assert analytics.conversations_fields(snapshot,[lead])['sections']['applications'][0]['reviewable']
        lead['log'][0]['text']='analytics application_review: '+json.dumps(dict(saved,state='unverified'))
        assert not analytics.conversations_fields(snapshot,[lead])['sections']['applications'][0]['reviewable']
        stale=copy.deepcopy(snapshot)
        stale.update(rank='Deckhand',rank_progress={'x':1},proposal_insights={'rank':3})
        for container in (stale['presentation'],stale['presentation']['voyage'],stale['community_card']):
            container.update(rank='Admiral',rank_progress={'x':2})
        stale['conversation_review']['threads']=[{'points':{'answered_question':{'state':'met'},'fast_answer':{'state':'met'},'follow_ups':{'state':'met'}}}]
        stale['conversations']['sections']['chats']=[copy.deepcopy(stale['conversation_review']['threads'][0])]
        ledger=folder/'data/analytics-history.jsonl';ledger.write_text(json.dumps(stale)+'\n')
        before=hashlib.sha256(ledger.read_bytes()).hexdigest()
        views=[analytics.last(),cockpit.analytics_state(today)['latest'],cockpit.analytics_state(today)['history'][0]]
        for visible in views:
            assert visible['proposal_insights']['rank']==3
            assert visible['kpis']==stale['kpis'] and visible['coverage']==stale['coverage']
            for container in (visible,visible['presentation'],visible['presentation']['voyage'],visible['community_card']):
                assert not {'rank','rank_progress'} & set(container)
            for container in (visible['conversation_review']['threads'][0],visible['conversations']['sections']['chats'][0]):
                assert set(container['points'])=={'answered_question'}
        assert hashlib.sha256(ledger.read_bytes()).hexdigest()==before
        try:analytics.validate_community_card(dict(snapshot['community_card'],rank='Admiral'))
        except ValueError:pass
        else:raise AssertionError('Public rank injection accepted.')
        goal={'stage':analytics.LABELS['reply_to_call'],'kpi':'reply_to_call','change':'Agree a useful call',
              'start':today.isoformat(),'review_on':(today+dt.timedelta(days=7)).isoformat(),
              'primary':True,'cue':'a client asks about the audit','action':'ask who owns it','fallback':'ask one question'}
        snapshot['goals_next']=[goal]
        snapshot['quests']=analytics.quest_progress(snapshot,list(records().values()),today)
        snapshot['reviews']['conversation'].update(goal_ref='reply_to_call',example='Who owns the audit?',evidence_lead_ids=[jid])
        projection=analytics.goal_cards(snapshot)[0]
        assert projection['goal_id']==analytics.goal_id(goal,snapshot['week']) and projection['kpi']==goal['kpi']
        assert projection['coach_example']=='Who owns the audit?' and projection['execution_unit']=='replies'
        assert projection['review_on'] in projection['measurement'] and 'completed replies' in projection['measurement']
        snapshot['reviews']['conversation']['goal_ref']='reply_rate'
        assert analytics.goal_cards(snapshot)[0]['coach_example'] is None
        try:analytics.validate_goals({'week':snapshot['week'],'goals':[dict(goal,example='Arbitrary coaching')]})
        except ValueError:pass
        else:raise AssertionError('Canonical goal schema loosened.')
        assert analytics.CONVERSATION_POINTS==POINTS and set(analytics.CALL_POINT_LABELS)==set(range(1,10))
        assert analytics.CALL_POINT_LABELS[7]=='Why you' and analytics.CALL_POINT_LABELS[9]=='Next step on Upwork'
    model={'presentation':{'voyage':{'stations':[
        {'badge':'First Doubloon','tier':'Gold','earned':True,'earned_week':'2026-W42','earned_at':'2026-10-13T10:00:00+02:00'},
        {'badge':'True North','tier':'Bronze','earned':True,'earned_week':'2026-W42','earned_at':'2026-10-14T10:00:00+02:00'}]}}}
    assert analytics.progress_strip(model)['newest_badge']['tier']=='Bronze'
    for row in model['presentation']['voyage']['stations']:row.pop('earned_at')
    strip=analytics.progress_strip(model)
    assert strip['newest_badge'] is None and 'unknown' in strip['newest_badge_basis']
    print('PASS supervised corrections:180/181 and100/101; summary/incomplete/unread source gates; Loom source refusal; exact projections; log assessment verification; read-only historical migration preserves statistical rank and funnel evidence; strict goals/matching example/measurement; timestamp chronology and tie unknown; canonical rubric definitions.')


def main():
    thread_references()
    score_contract()
    scorecard_missing_and_cards()
    badge_calibration()
    catchup_contract()
    immediate_call_review_writer()
    summary_contract()
    public_latest_goals_contract()
    repeated_conversation_pattern()
    frozen_projection_contract()
    supervised_corrections()


if __name__ == '__main__':
    main()
