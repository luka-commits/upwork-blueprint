#!/usr/bin/env python3
"""Frozen final contract regressions. Synthetic sources, isolated temporary storage."""
import copy
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import run_checks, fixture, run, seed, record, records, analytics_stamp, EXAMPLE_CALL_READ

POINTS = ('answered_question', 'qualifying_question', 'call_times')

def assert_rank_projection(snapshot):
    """The same code-owned stable rank reaches private and allowlisted public views."""
    import analytics
    rank = snapshot['rank']
    assert rank in dict(analytics.RANK_LEVELS)
    assert snapshot['rank_progress']['rank'] == rank
    assert snapshot['rank_progress']['required_weeks'] == 4
    assert snapshot['presentation']['voyage']['rank'] == rank
    assert snapshot['community_card']['rank'] == rank
    assert snapshot['community_card']['rank_progress'] == snapshot['rank_progress']

def rank_contract():
    import analytics
    end = dt.date(2026, 10, 12)
    def weeks(values):
        return [{'week': (end-dt.timedelta(weeks=len(values)-1-index)).strftime('%G-W%V'),
                 'funnel_score': {'score': value}} for index, value in enumerate(values)]
    def result(values):
        rows = weeks(values)
        return analytics.rank_fields(rows[-1], rows[:-1])
    for score, expected in ((0,'Deckhand'),(39.999,'Deckhand'),(40,'Boatswain'),
                            (59.999,'Boatswain'),(60,'Officer'),(74.999,'Officer'),
                            (75,'Captain'),(89.999,'Captain'),(90,'Admiral'),(100,'Admiral')):
        row = result([score]*7)
        assert row['rank'] == expected, (score, row)
        assert row['required_weeks'] == 4 and 0 <= row['progress'] <= 100
        if expected == 'Admiral': assert row['next_rank'] is None
    assert result([100]*4)['rank'] == 'Deckhand', 'One complete average cannot prove four holds.'
    assert result([100]*6)['held_weeks'] == 3
    assert result([0,0,0,100,100,100,100])['rank'] == 'Deckhand', 'Use rolling averages, never latest score.'
    assert result([60,100,100,100,60,100,100])['rank'] == 'Admiral', 'Each rolling mean is 90.'
    assert result([100,100,None,100,100,100,100])['rank'] == 'Deckhand'
    rows = weeks([100]*7)
    missing = rows[:2]+rows[3:]
    assert analytics.rank_fields(missing[-1], missing[:-1])['rank'] == 'Deckhand'
    future = {'week':'2026-W43','funnel_score':{'score':100}}
    assert analytics.rank_fields(rows[-1], rows[:-1]+[future]) == analytics.rank_fields(rows[-1], rows[:-1])
    for bad in (-1,101,float('inf'),float('nan'),True):
        assert result([100,100,bad,100,100,100,100])['rank'] == 'Deckhand', bad

def progress_calculations():
    import analytics
    def row(key, value, previous, unit='%'):
        return {'key':key,'name':key.replace('_',' ').title(),'value':value,'state':'observed',
                'finished':{'n':20},'change':{'previous_value':previous},'series':{'unit':unit}}
    model={'week':'2026-W42','kpis':{'first_reply':{'direction':'down'}},'presentation':{
        'scorecard':[row('missing_baseline',10000,None),row('reply_rate',21.428571,18.333333)],
        'voyage':{'stations':[]}}}
    gain=analytics.progress_strip(model)['biggest_change']
    assert gain['key']=='reply_rate' and gain['previous']==18.333333
    assert gain['value']==21.428571, 'Only display is rounded; preserve measured precision.'
    half_percent={'week':'2026-W42','kpis':{},'presentation':{'scorecard':[row('reply_rate',18.5,12.5)]}}
    assert half_percent['presentation']['scorecard'][0]['value']==18.5
    assert half_percent['presentation']['scorecard'][0]['change']['previous_value']==12.5
    assert analytics.check_report('Reply rate 19%, up from 13%.',half_percent)['status']=='PASS'
    for wrong in ('Reply rate 18%, up from 13%.','Reply rate 19%, up from 12%.'):
        assert analytics.check_report(wrong,half_percent)['status']=='FAIL'
    rounded_display={'week':'2026-W42','kpis':{'first_reply':{'value':4.25,'state':'pass'}},
        'north_star':{'value':4200.5,'wins':3,'currency':'USD'}}
    for correct in ('First replies took 4.3 minutes on median.',
                    'You signed 3 new contracts worth $4,201.'):
        assert analytics.check_report(correct,rounded_display)['status']=='PASS'
    for wrong in ('First replies took 4.4 minutes on median.',
                  'You signed 3 new contracts worth $4,202.'):
        assert analytics.check_report(wrong,rounded_display)['status']=='FAIL'
    assert rounded_display['kpis']['first_reply']['value']==4.25
    assert rounded_display['north_star']['value']==4200.5
    model['presentation']['scorecard']=[row('missing_baseline',10000,None),row('reply_rate',10,20)]
    assert analytics.progress_strip(model)['biggest_change']['direction']=='decline'
    model['presentation']['scorecard']=[row('missing_baseline',10000,None)]
    assert analytics.progress_strip(model)['biggest_change'] is None
    empty_previous=row('reply_rate',50,0)
    empty_previous['change']['previous_n']=0
    model['presentation']['scorecard']=[empty_previous]
    assert analytics.progress_strip(model)['biggest_change'] is None, 'An empty prior rate is not a zero-percent baseline.'
    from analytics_fixture import analytics_sync_marker
    with fixture('new-finished-rate') as folder:
        analytics_sync_marker(folder)
        snapshot=analytics.compute(dt.date(2026,10,14),jobs=[{'id':'new-rate','source':'outbound',
            'applied_at':'2026-09-30T10:00:00+02:00','replied_at':'2026-10-01T10:00:00+02:00'}],now='2026-10-14T15:00:00+02:00')
        first=next(r for r in snapshot['presentation']['scorecard'] if r['key']=='reply_rate')
        assert first['finished']=={'k':1,'n':1} and first['change']['previous_n']==0
        assert first['change']['previous_value'] is None and first['change']['new'] is True
    model['presentation']['voyage']['stations']=[{'badge':'Swift Sail','earned':True,'earned_week':'2026-W41'}]
    assert analytics.progress_strip(model)['newest_badge'] is None, 'Badge highlight is this week only.'
    model['presentation']['voyage']['stations'][0]['earned_week']='2026-W42'
    assert analytics.progress_strip(model)['newest_badge']['badge']=='Swift Sail'

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
        assert all(len(row['series']['points']) == 8 for row in scorecard)
        assert 'held_to_proposal' not in {row['key'] for row in scorecard}
        proposal = next(row for row in scorecard if row['key'] == 'proposal_on_time')
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
        path=folder/'jobs'/'945000010';path.mkdir()
        (path/'call-review.md').write_text("## Coach's read\n\nEXAMPLE evidence read.\n\n## Nine points\n\nSaved below.\n\n## Next step\n\nConfirm Friday.\n")
        private=dict(snapshot, reviews={'call': {'rubric':[{'lead_id':'945000010','reviewable':False,'points':[]}]}})
        call=analytics.call_cards(private,jobs)[0]
        assert call['coach_read'] is None and call['coach_read_state'] == 'unknown'
        assert call['agreed_step'] is None and call['next_message'] is None
        (path/'call-review.md').unlink()
        assert analytics.call_cards(private,jobs)[0]['coach_read'] is None

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
        assert_rank_projection(base)
        points=[{'point':p,'state':'met','quote':'Proof'} for p in range(1,10)]
        points[8].update(state='not needed',reason='Informed disqualification; proposal not appropriate.')
        assert badges._call_fraction(points)==1
        points[8].pop('reason')
        assert badges._call_fraction(points) is None

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
        approved=analytics_payload(current, agree=False)
        analytics.add_goals({'week':approved['week'], 'goals':[dict(goal,start=today.isoformat()) for goal in approved['goals_next']]})
        saved=analytics.record_snapshot(approved)
        persisted=[json.loads(line) for line in (folder/'data/analytics-history.jsonl').read_text().splitlines()]
        assert [row['week'] for row in persisted]==['2026-W38','2026-W39','2026-W40','2026-W41','2026-W42']
        assert len({row['week'] for row in persisted})==5 and saved['gap']['weeks_missed']==3
        assert analytics.compute_catchup(today,jobs=[])==[]

def public_latest_goals_contract():
    import analytics
    with fixture('final-public-latest-goals'):
        today=dt.date(2026,10,14);snapshot=analytics.compute(today,jobs=[])
        reviews=[{'start':start,'change':f'{prefix} goal {index}','done_k':done,'done_n':1,'execution_state':'complete' if done else 'undone'}
                 for start,prefix,done in (('2026-09-30','Older',0),('2026-10-07','Recent',1)) for index in range(3)]
        for start,week in (('2026-09-30','2026-W40'),('2026-10-07','2026-W41')):
            keys=('weekly_volume','reply_rate','reply_to_call')
            libraries=('volume-sessions','reply-opener','call-times') if start=='2026-10-07' else ('volume-share','reply-proof','call-question')
            goals=[{'start':start,'kpi':keys[index],'goal_library_id':libraries[index],'stage':analytics.LABELS[keys[index]],'change':review['change'],'primary':index==0,'cue':'When the stage starts','action':'Use the agreed next step','fallback':'Use one smaller step','review_on':(dt.date.fromisoformat(start)+dt.timedelta(days=7)).isoformat()} for index,review in enumerate([row for row in reviews if row['start']==start])]
            analytics.add_goals({'week':week,'goals':goals})
            for goal,review in zip(goals,[row for row in reviews if row['start']==start]):
                review.update(goal_id=analytics.goal_id(goal,week),goal_library_id=goal['goal_library_id'])
        snapshot['goals_review']=reviews
        card=analytics.community_card([],today,snapshot['kpis'],reviews,snapshot['week'],0)
        card['funnel_score']=snapshot['funnel_score']
        assert len(snapshot['goals_review'])==6 and len(card['goals'])==3 and card['goals_done']=='3/3'
        latest_ids={row['goal_id'] for row in reviews if row['start']=='2026-10-07'}
        assert all(goal['goal_id'] in latest_ids and goal['text']==analytics.PUBLIC_GOAL_LIBRARY[goal['goal_library_id']][1] and goal['done'] for goal in card['goals'])
        assert all('Recent' not in goal['text'] and 'Older' not in goal['text'] for goal in card['goals'])
        assert analytics.validate_community_card(card)==card
        html=analytics.public_onepager_html(card)
        assert 'Last agreed goals' in html and 'Agreed goals carried out' not in html
        broken=copy.deepcopy(card);broken['goals'].append(copy.deepcopy(card['goals'][0]))
        try:analytics.validate_community_card(broken)
        except ValueError:pass
        else:raise AssertionError('Public card accepted more than three latest agreed goals.')


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
        minimum=dict(call,free_read='word '*120)
        record(jid,{'call_review':minimum})
        assert analytics.call_coverage([dict(minimum,lead_id=jid)],today)
        too_short=dict(call,free_read='word '*119)
        assert run('pipeline.py','record',jid,'--file','-',value={'call_review':too_short},success=False).returncode
        try:analytics.call_coverage([dict(too_short,lead_id=jid)],today)
        except ValueError:pass
        else:raise AssertionError('A 119-word full call read was accepted.')
        for field,limit in (('free_read',180),('next_message',100)):
            allowed=dict(call,**{field:'word '*limit})
            record(jid,{'call_review':allowed})
            assert analytics.call_coverage([dict(allowed,lead_id=jid)],today)
            broken=dict(call,**{field:'word '*(limit+1)})
            assert run('pipeline.py','record',jid,'--file','-',value={'call_review':broken},success=False).returncode
            try:analytics.call_coverage([dict(broken,lead_id=jid)],today)
            except ValueError:pass
            else:raise AssertionError((field,limit))
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
        (path/'call-review.md').write_text("## Coach's read\n\n"+EXAMPLE_CALL_READ+"\n")
        record(jid,{'call_review':call})
        snapshot=analytics.compute(today)
        card=snapshot['call_cards'][0]
        assert card['as_of']==card['reviewed_at']==records()[jid]['call_reviewed_at']
        application=snapshot['conversations']['sections']['applications'][0]
        assert application['reviewable'] and application['read']
        assert application['loom_status']=='not_sent' and application['loom_source_state']=='not_applicable'
        assert application['sent_copy']==quote and application['loom_transcript'] is None
        (path/'loom.md').write_text('Exact example Loom transcript.')
        application=analytics.conversations_fields(snapshot,list(records().values()))['sections']['applications'][0]
        assert application['reviewable'] and application['loom_transcript']=='Exact example Loom transcript.'
        lead=records()[jid]; saved=lead.pop('application_review')
        lead['log']=[{'at':analytics_stamp(today), 'text':'analytics application_review: '+json.dumps(saved)}]
        assert analytics.conversations_fields(snapshot,[lead])['sections']['applications'][0]['reviewable']
        lead['log'][0]['text']='analytics application_review: '+json.dumps(dict(saved,state='unverified'))
        assert not analytics.conversations_fields(snapshot,[lead])['sections']['applications'][0]['reviewable']
        stale=copy.deepcopy(snapshot)
        assert_rank_projection(snapshot)
        stale.update(proposal_insights={'rank':3})
        stale['conversation_review']['threads']=[{'points':{'answered_question':{'state':'met'},'fast_answer':{'state':'met'},'follow_ups':{'state':'met'}}}]
        stale['conversations']['sections']['chats']=[copy.deepcopy(stale['conversation_review']['threads'][0])]
        ledger=folder/'data/analytics-history.jsonl';ledger.write_text(json.dumps(stale)+'\n')
        before=hashlib.sha256(ledger.read_bytes()).hexdigest()
        views=[analytics.last(),cockpit.analytics_state(today)['latest'],cockpit.analytics_state(today)['history'][0]]
        for visible in views:
            assert visible['proposal_insights']['rank']==3
            assert visible['kpis']==stale['kpis'] and visible['coverage']==stale['coverage']
            assert_rank_projection(visible)
            assert visible['rank_progress']==stale['rank_progress']
            for container in (visible['conversation_review']['threads'][0],visible['conversations']['sections']['chats'][0]):
                assert set(container['points'])=={'answered_question'}
        assert hashlib.sha256(ledger.read_bytes()).hexdigest()==before
        try:analytics.validate_community_card(dict(snapshot['community_card'],rank='Secret Client Name'))
        except ValueError:pass
        else:raise AssertionError('Public rank leaked arbitrary identity.')
        goal={'stage':analytics.LABELS['reply_to_call'],'kpi':'reply_to_call','change':'Agree a useful call',
              'start':today.isoformat(),'review_on':(today+dt.timedelta(days=7)).isoformat(),
              'primary':True,'cue':'a client asks about the audit','action':'ask who owns it','fallback':'ask one question'}
        snapshot['goals_next']=[goal]
        snapshot['quests']=analytics.quest_progress(snapshot,list(records().values()),today)
        snapshot['reviews']['conversation'].update(goal_ref='reply_to_call',example='Who owns the audit?',evidence_lead_ids=[jid])
        projection=analytics.goal_cards(snapshot)[0]
        assert projection['goal_id']==analytics.goal_id(goal,snapshot['week']) and projection['kpi']==goal['kpi']
        assert projection['coach_example']=='Who owns the audit?' and projection['execution_unit']=='replies'
        snapshot['reviews']['conversation']['goal_ref']='reply_rate'
        assert analytics.goal_cards(snapshot)[0]['coach_example'] is None
        try:analytics.validate_goals({'week':snapshot['week'],'goals':[dict(goal,example='Arbitrary coaching')]})
        except ValueError:pass
        else:raise AssertionError('Canonical goal schema loosened.')
        assert analytics.CONVERSATION_POINTS==POINTS and set(analytics.CALL_POINT_LABELS)==set(range(1,10))
    model={'week':'2026-W42','presentation':{'voyage':{'stations':[
        {'badge':'First Doubloon','tier':'Gold','earned':True,'earned_week':'2026-W42','earned_at':'2026-10-13T10:00:00+02:00'},
        {'badge':'True North','tier':'Bronze','earned':True,'earned_week':'2026-W42','earned_at':'2026-10-14T10:00:00+02:00'}]}}}
    assert analytics.progress_strip(model)['newest_badge']['tier']=='Bronze'
    for row in model['presentation']['voyage']['stations']:row.pop('earned_at')
    model['week']='2026-W43'
    strip=analytics.progress_strip(model)
    assert strip['newest_badge'] is None and 'unknown' in strip['newest_badge_basis']
    model['week']='2026-W42'
    for row in model['presentation']['voyage']['stations']:row['earned_at']='2026-10-14T10:00:00+02:00'
    tied=analytics.progress_strip(model)
    assert tied['newest_badge']['badge']=='First Doubloon' and tied['newest_badge']['tier']=='Gold'

def job_fit_contract():
    import analytics
    today = dt.date(2026, 10, 19)
    start = today - dt.timedelta(days=84)
    midpoint = start + dt.timedelta(days=42)
    def planted(only_old=False, size=100):
        rows = []
        for half, date in enumerate((start + dt.timedelta(days=4), midpoint + dt.timedelta(days=4))):
            for band in ('<500', '>2000'):
                for i in range(size):
                    applied = dt.datetime.combine(date, dt.time(10), analytics.local_zone())
                    reply = i < round(size * (.9 if band == '<500' and (not only_old or half == 0) else .1))
                    row = {'id': str(len(rows)), 'source': 'invite', 'applied_at': applied.isoformat(),
                           'application_facts': {'source': 'outbound', 'budget_band': band, 'connects_cost': 12},
                           'budget': 99999, 'proposals': 1}
                    if reply: row['replied_at'] = (applied + dt.timedelta(days=1)).isoformat()
                    rows.append(row)
        return rows
    both = analytics.job_fit_fields(planted(), today)
    row = next(row for row in both['apply'] if row['band'] == '<500')
    assert row['state'] == 'confirmed' and row['n'] == 200 and row['k'] == 180
    assert row['connects_total'] == 2400 and row['connects_per_reply'] == analytics.rounded(2400 / 180)
    assert (row['low'], row['high']) == tuple(map(analytics.rounded, analytics.wilson(180, 200)))
    assert both['windows']['discovery']['end'] == (midpoint - dt.timedelta(days=1)).isoformat()
    assert both['windows']['confirmation']['start'] == midpoint.isoformat()
    assert both['period'] == analytics.period(analytics.span(today, 84))
    one = analytics.job_fit_fields(planted(only_old=True), today)
    assert not any(row['state'] == 'confirmed' for row in one['apply'] + one['skip'])
    assert any(row['state'] == 'early_signal' and str(row['n']) in row['text'] for row in one['apply'])
    small = analytics.job_fit_fields(planted(size=7), today)
    assert not small['apply'] and not small['skip'] and not small['patterns']
    assert next(row for row in small['bands'] if row['band'] == '<500')['n'] == 14
    unknown = planted()
    for job in unknown:
        job['application_facts']['budget_band'] = 'unknown'
        job.update(budget=100, budget_band='<500')
    empty = analytics.job_fit_fields(unknown, today)
    assert all(row['n'] == 0 and row['discovery']['reference']['n'] == 0 for row in empty['bands'])
    assert not empty['patterns']
    missing_source = planted()
    for job in missing_source:
        job['source'] = 'outbound'
        job['application_facts'].pop('source')
    assert analytics.job_fit_fields(missing_source, today)['finished_n'] == 0
    no_replies = planted()
    for job in no_replies: job.pop('replied_at', None)
    silent = analytics.job_fit_fields(no_replies, today)
    assert all(row['connects_per_reply'] is None for row in silent['bands'])
    assert not silent['patterns']
    frozen = planted()
    before = analytics.job_fit_fields(frozen, today)
    for job in frozen: job.update(budget=0, proposals_band='50+', connects_cost=999, client={'spent': 999999}, posted_date='2026-10-19')
    assert analytics.job_fit_fields(frozen, today) == before
    incomplete = planted(); incomplete[0]['application_facts']['connects_cost'] = 'unknown'
    incomplete_row = next(row for row in analytics.job_fit_fields(incomplete, today)['apply'] if row['band'] == '<500')
    assert incomplete_row['connects_per_reply'] is None and incomplete_row['connects_total'] is None
    assert incomplete_row['connects_known_n'] == 199
    zero = planted()
    for job in zero: job['application_facts']['connects_cost'] = 0
    assert analytics.job_fit_fields(zero, today)['apply'][0]['connects_per_reply'] == 0
    cutoff = dt.datetime.combine(today, dt.time(), analytics.local_zone())
    def case(jid, applied, reply_delta=1, source='outbound'):
        return {'id': jid, 'applied_at': applied.isoformat(), 'replied_at': (applied + dt.timedelta(days=reply_delta)).isoformat(),
                'application_facts': {'source': source, 'budget_band': '<500', 'connects_cost': 12}}
    edges = [case('start', dt.datetime.combine(start, dt.time(), analytics.local_zone())),
             case('before', dt.datetime.combine(start, dt.time(), analytics.local_zone()) - dt.timedelta(microseconds=1)),
             case('split', dt.datetime.combine(midpoint, dt.time(), analytics.local_zone())),
             case('exact', cutoff - dt.timedelta(days=7), 7),
             case('late', cutoff - dt.timedelta(days=8), 7 + 1/86400),
             case('pending', cutoff - dt.timedelta(days=7) + dt.timedelta(seconds=1)),
             case('invite', cutoff - dt.timedelta(days=8), source='invite'),
             case('future', cutoff)]
    edges.append(dict(edges[0], id='imported', imported=True))
    measured = analytics.job_fit_fields(edges, today)
    band = next(row for row in measured['bands'] if row['band'] == '<500')
    assert measured['finished_n'] == 4 and measured['pending_n'] == 1
    assert band['n'] == 4 and band['k'] == 3
    assert band['discovery']['evidence'] == ['start']
    assert set(band['confirmation']['evidence']) == {'split', 'exact', 'late'}
    all_bands = planted()
    for job in all_bands:
        high = job['application_facts']['budget_band'] == '<500'
        for dimension, values in analytics.pipeline.APPLICATION_BANDS.items():
            if dimension != 'budget_band': job['application_facts'][dimension] = values[0] if high else values[-2]
    capped = analytics.job_fit_fields(all_bands, today)
    assert len(capped['apply']) == 2 and len(capped['skip']) == 1 and len(capped['patterns']) == 2
    assert len(analytics.facts_sheet({'week': '2026-W43', 'kpis': {}, 'insights': {'job_fit': capped}})['job_fit']['patterns']) == 2
    assert all(not any(word in row['text'].casefold() for word in ('wilson', 'binomial', 'cohort', 'hypothesis', 'statistic', '\u2014')) for row in capped['apply'] + capped['skip'])
    with fixture('part2-job-fit-record'):
        value = analytics.compute(today)
        assert value['insights']['job_fit']['patterns'] == []
        reply = next(row for row in value['presentation']['scorecard'] if row['key'] == 'reply_rate')
        assert reply['job_fit'] == value['insights']['job_fit']
        from analytics_fixture import analytics_payload
        prepared = analytics.prepare_snapshot(analytics_payload(value, agree=False), today)
        analytics.add_goals({'week':prepared['week'], 'goals':[dict(goal,start=today.isoformat()) for goal in prepared['goals_next']]})
        assert prepared['insights']['job_fit'] == value['insights']['job_fit']
        assert analytics.facts_sheet(prepared)['job_fit']['patterns'] == []
        mismatch=copy.deepcopy(prepared)
        mismatch['goals_next'][0]['change']='Use a different agreed next step'
        try: analytics.record_snapshot(mismatch)
        except ValueError as error: assert 'matching agreed goals' in str(error), str(error)
        else: raise AssertionError('Snapshot changed the member agreement')
        saved=analytics.record_snapshot(prepared)
        assert saved['insights']==prepared['insights'] and saved['segments']==prepared['segments']
        tampered = copy.deepcopy(prepared)
        tampered['insights']['job_fit']['finished_n'] = 999
        try: analytics.record_snapshot(tampered)
        except ValueError as error: assert 'insights must come unchanged' in str(error), str(error)
        else: raise AssertionError('Computed job fit was replaceable')
    assert abs(analytics.job_fit_exact_p(20, 20, .5) - 2 / 2**20) < 1e-12
    assert analytics.job_fit_exact_p(0, 20, 0) == 1 and analytics.job_fit_exact_p(20, 20, 1) == 1

def backend_final_audit_contract():
    import math
    import analytics
    import pipeline
    from analytics_fixture import analytics_sync_marker
    today = dt.date(2026, 10, 19)
    start = today - dt.timedelta(days=84)
    middle = start + dt.timedelta(days=42)
    def stamp(date): return dt.datetime.combine(date, dt.time(10), analytics.local_zone()).isoformat()
    def planted(size=20, old_only=False, behaviour=False):
        jobs = []
        for half, date in enumerate((start + dt.timedelta(days=4), middle + dt.timedelta(days=4))):
            for exposed in (False, True):
                for index in range(size):
                    hit = exposed and (not old_only or half == 0)
                    job = {'id': str(len(jobs)), 'applied_at': stamp(date),
                           'application_facts': {'source': 'outbound', 'budget_band': '<500' if exposed else '>2000',
                               'connects_cost': 12, 'tags': {'names_tool': exposed}, 'tags_registered_at': stamp(start-dt.timedelta(days=1))}}
                    if behaviour:
                        job['replied_at'] = stamp(date+dt.timedelta(days=1))
                        job['behaviour_observations'] = {'two_call_times': {'possible_at': job['replied_at'],
                            'exposure_at': stamp(date+dt.timedelta(days=2)), 'met': exposed}}
                        if hit: job['call_booked_at'] = stamp(date+dt.timedelta(days=3))
                    elif hit: job['replied_at'] = stamp(date+dt.timedelta(days=1))
                    jobs.append(job)
        return jobs
    with fixture('backend-final-audit') as folder:
        analytics_sync_marker(folder)
        public_start = today - dt.timedelta(days=56)
        public_end = today - dt.timedelta(days=29)
        scheduled = public_end - dt.timedelta(days=3)
        late_booking = [{'id':'late-booked', 'source':'outbound', 'call_booked_at':stamp(public_start-dt.timedelta(days=4)),
                         'call_scheduled_at':stamp(scheduled), 'call_held_at':stamp(scheduled+dt.timedelta(days=1))},
                        {'id':'late-held', 'source':'outbound','call_booked_at':stamp(public_start),
                         'call_scheduled_at':stamp(scheduled), 'call_held_at':stamp(scheduled+dt.timedelta(days=3))},
                        {'id':'cancelled','source':'outbound','call_scheduled_at':stamp(scheduled),
                         'call_session_id':'s','call_sessions':{'s':{'scheduled_at':stamp(scheduled),'cancelled':True}}},
                        {'id':'before','source':'outbound','call_scheduled_at':stamp(public_start-dt.timedelta(days=1))},
                        {'id':'after','source':'outbound','call_scheduled_at':stamp(public_end+dt.timedelta(days=1))}]
        card = analytics.community_card(late_booking,today,{},[], '2026-W43',0)
        assert (card['booked_to_held']['k'],card['booked_to_held']['n']) == (1,2), card
        assert card['booked_to_held']['entry_period'] == analytics.period((public_start,public_end))
        snapshot = analytics.compute(today,jobs=[])
        missing = copy.deepcopy(snapshot)
        for source in missing['coverage']['sources']:
            if source['source'] in ('upwork','recorder'): source['state']='missing'
        missing.pop('report_facts',None)
        facts = analytics.facts_sheet(missing)['report_facts']['weekly']
        assert facts['calls'] is None and facts['transcripts_read'] is None, facts
        (folder/'data'/'sync.json').unlink()
        full_missing = analytics.compute(today,jobs=[])
        assert full_missing['report_facts']['weekly']['calls'] is None
        assert full_missing['report_facts']['weekly']['transcripts_read'] is None
        for key in ('segments','behaviour'):
            assert full_missing['kpis'][key]['state']=='missing'
            assert all(full_missing['kpis'][key][field] is None for field in ('k','n','value'))
        assert any({'segments','behaviour'} <= set(row['blocks']) for row in full_missing['coverage']['missing'] if row['source']=='upwork')
        for text in ('twelve', 'eleven', 'nineteen', 'twenty-one', 'twenty one', 'ninety nine',
                     'one hundred and twenty-three', 'two thousand', 'one million'):
            check = analytics.check_report('You won '+text+' contracts this week.', snapshot)
            assert check['status']=='FAIL' and check['errors'], (text,check)
        truthful = copy.deepcopy(snapshot); truthful['north_star']['wins']=123
        assert analytics.check_report('You won one hundred and twenty-three contracts this week.',truthful)['status']=='PASS'
        assert analytics.check_report('1. Offer two concrete times: "Tuesday 12:00 or Thursday 14:00?"',snapshot)['status']=='PASS'
        rows = planted()
        general = analytics.insight_fields(rows,today)
        tag = next(row for row in general['findings'] if row['dimension']=='tag')
        assert tag['discovery']['n']==tag['confirmation']['n']==20
        assert tag['target']['lead_ids']==tag['evidence'] and not set(tag['discovery']['evidence']) & set(tag['confirmation']['evidence'])
        assert len(general['known_patterns']) <= 1
        assert general['windows']['discovery']['end']==(middle-dt.timedelta(days=1)).isoformat()
        assert general['windows']['confirmation']['start']==middle.isoformat()
        nineteen = analytics.insight_fields(planted(19),today)
        assert not nineteen['findings'] and all(row['state']!='confirmed' for row in nineteen['segments'])
        early = analytics.insight_fields(planted(old_only=True),today)
        assert not early['findings'] and any(row['state']=='emerging' for row in early['segments'])
        no_opportunity = planted(behaviour=True)
        for index in range(200): no_opportunity.append({'id':'impossible'+str(index), 'applied_at':stamp(start+dt.timedelta(days=4)),
            'application_facts':{'source':'outbound'}, 'behaviour_observations':{'two_call_times':{'possible_at':stamp(start),
                'exposure_at':stamp(start+dt.timedelta(days=1)), 'met':True}}})
        behaviour = next(row for row in analytics.insight_fields(no_opportunity,today)['findings'] if row['dimension']=='behaviour')
        assert behaviour['discovery']['reference']['n']==behaviour['confirmation']['reference']['n']==40
        assert not any(jid.startswith('impossible') for jid in behaviour['evidence'])
        inbound=planted(behaviour=True)
        for job in inbound:
            job.pop('application_facts')
            job.pop('applied_at')
            job['source']='invite'
        inbound += [{'id':'no-reply','source':'invite','behaviour_observations':{'two_call_times':{
            'possible_at':stamp(start+dt.timedelta(days=5)), 'exposure_at':stamp(start+dt.timedelta(days=6)), 'met':True}}},
            {'id':'no-opportunity','source':'direct_offer','replied_at':stamp(start+dt.timedelta(days=5))},
            dict(inbound[0],id='imported-inbound',imported=True)]
        inbound_result=analytics.insight_fields(inbound,today)
        inbound_behaviour=next(row for row in inbound_result['findings'] if row['dimension']=='behaviour')
        assert inbound_behaviour['discovery']['reference']['n']==inbound_behaviour['confirmation']['reference']['n']==40
        assert inbound_behaviour['discovery']['n']==inbound_behaviour['confirmation']['n']==20
        assert not {'no-reply','no-opportunity','imported-inbound'} & set(inbound_behaviour['evidence'])
        assert all(row['n']==0 for row in inbound_result['segments']), 'Inbound behaviour does not enter application segments.'
        retrospective = planted()
        for row in retrospective: row['application_facts']['tags_registered_at']=stamp(middle)
        assert not any(row['dimension']=='tag' for row in analytics.insight_fields(retrospective,today)['segments'])
        # Independent exact probability and near-cutoff BH step-up, including equality.
        probability = sum(math.comb(20,i)*.5**20 for i in range(21) if math.comb(20,i)<=math.comb(20,15))
        assert abs(analytics.job_fit_exact_p(15,20,.5)-probability)<1e-12
        assert analytics.bh_accept([.025,.05,.9,1]) == {0,1}
        assert analytics.bh_accept([.02501,.05001,.9,1]) == set()
        assert analytics.bh_accept([.0251,.0499,.9,1]) == {0,1}, 'Step-up includes earlier p values.'
        assert analytics.bh_accept([probability,.001,.9,1]) == {0,1}
        # Independent Wilson formula and the exact fifteen-case display boundary.
        fit = analytics.job_fit_fields(planted(15),today)
        recommendation = next(row for row in fit['apply'] if row['band']=='<500')
        assert recommendation['state']=='confirmed' and 'range' in recommendation['text']
        n,k,z=30,30,1.959963984540054
        p=k/n; denominator=1+z*z/n
        centre=(p+z*z/(2*n))/denominator
        radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
        assert abs(recommendation['low']-100*(centre-radius))<.02
        assert abs(recommendation['high']-100*(centre+radius))<.02
        total15 = planted(8)
        total15 = [row for row in total15 if row['id']!='24']
        band15 = next(row for row in analytics.job_fit_fields(total15,today)['apply'] if row['band']=='<500')
        assert band15['n']==15 and band15['state']=='confirmed'
        assert not analytics.job_fit_fields(planted(7),today)['apply']
        only_half = [row for row in planted(15) if analytics.day(row['applied_at']) < middle]
        half15 = next(row for row in analytics.job_fit_fields(only_half,today)['apply'] if row['band']=='<500')
        assert half15['n']==15 and half15['state']=='early_signal'
        # Real pipeline writer, isolated only: register before apply and freeze once.
        source = {'id':'945997001','title':'Example posting','status':'new'}
        run('pipeline.py','add','--file','-',value=source)
        run('pipeline.py','record',source['id'],'--file','-',value={'tags':{'names_tool':True}})
        run('pipeline.py','set',source['id'],'applied')
        frozen = next(row for row in pipeline.load() if row['id']==source['id'])['application_facts']
        assert frozen['tags']=={'names_tool':True} and frozen['tags_registered_at']
        rejected = run('pipeline.py','record',source['id'],'--file','-',value={'tags':{'late':True}},success=False)
        assert 'before applying' in rejected.stderr
        clock=dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=2)
        observation={'two_call_times':{'possible_at':clock.isoformat(), 'exposure_at':(clock+dt.timedelta(seconds=1)).isoformat(), 'met':False}}
        run('pipeline.py','record',source['id'],'--file','-',value={'first_client_message_at':clock.isoformat(),'behaviour_observations':observation})
        written=next(row for row in pipeline.load() if row['id']==source['id'])
        measured=analytics.insight_fields([written],clock.date()+dt.timedelta(days=28))
        exposed=next(row for row in measured['behaviour'] if row['value']=='two_call_times')
        assert sum(exposed[name]['reference']['n'] for name in ('discovery','confirmation'))==1
        changed=copy.deepcopy(observation);changed['two_call_times']['met']=True
        refused=run('pipeline.py','record',source['id'],'--file','-',value={'behaviour_observations':changed},success=False)
        assert refused.returncode and 'immutable' in refused.stderr
        imported_tags=run('pipeline.py','add','--file','-',value={'id':'945997002','status':'applied',
            'applied_at':stamp(start),'tags':{'late':True},'tags_registered_at':stamp(start-dt.timedelta(days=1))},success=False)
        assert imported_tags.returncode and 'before applying' in imported_tags.stderr
        for jobs in ([{'tags':{f'tag{i}':True for i in range(6)}}],
                     [{'tags':{f'tag{i}':True}} for i in range(13)]):
            try: pipeline.validate_insight_tags(jobs)
            except SystemExit: pass
            else: raise AssertionError('Insight tag cap accepted')
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':analytics.run_timestamp(today).isoformat()}))
        projected=analytics.compute(today,jobs=rows)
        assert projected['insights']['general']['findings'] and projected['kpis']['segments']['k']>=1
        assert analytics.facts_sheet(projected)['insights']['general']==projected['insights']['general']

CHECKS = (rank_contract, progress_calculations, score_contract, scorecard_missing_and_cards, badge_calibration, catchup_contract, public_latest_goals_contract, supervised_corrections, job_fit_contract, backend_final_audit_contract,)

if __name__ == "__main__":
    run_checks(CHECKS)
