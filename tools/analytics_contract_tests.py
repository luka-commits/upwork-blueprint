#!/usr/bin/env python3
"""Frozen final contract regressions. Synthetic sources, isolated temporary storage."""
import copy
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytics_fixture import fixture, run, seed, record, records, analytics_stamp, EXAMPLE_CALL_READ

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
    print('PASS rank: thresholds, rolling averages, four holds, missing/invalid/future history.')


def progress_and_layout_contract():
    import analytics
    from analytics_fixture import this_week_height_budget, feature_command, ROOT
    from analytics_forbidden_terms import self_check
    self_check()
    def row(key, value, previous, unit='%'):
        return {'key':key,'name':key.replace('_',' ').title(),'value':value,'state':'observed',
                'finished':{'n':20},'change':{'previous_value':previous},'series':{'unit':unit}}
    model={'week':'2026-W42','kpis':{'first_reply':{'direction':'down'}},'presentation':{
        'scorecard':[row('missing_baseline',10000,None),row('reply_rate',21.428571,18.333333)],
        'voyage':{'stations':[]}}}
    gain=analytics.progress_strip(model)['biggest_change']
    assert gain['key']=='reply_rate' and gain['previous']==18.333333
    assert gain['text']=='Reply Rate 18% -> 21%' and gain['change_text']=='vs the 4 weeks before'
    assert gain['value']==21.428571, 'Only display is rounded; preserve measured precision.'
    half_percent={'week':'2026-W42','kpis':{},'presentation':{'scorecard':[row('reply_rate',18.5,12.5)]}}
    assert analytics.progress_strip(half_percent)['biggest_change']['text']=='Reply Rate 13% -> 19%'
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
    model['presentation']['voyage']['stations']=[{'badge':'Swift Sail','earned':True,'earned_week':'2026-W41'}]
    assert analytics.progress_strip(model)['newest_badge'] is None, 'Badge highlight is this week only.'
    model['presentation']['voyage']['stations'][0]['earned_week']='2026-W42'
    assert analytics.progress_strip(model)['newest_badge']['badge']=='Swift Sail'
    for width, guideline, fail in ((1440,1900,2470),(390,3400,4420)):
        assert this_week_height_budget(width,guideline,900)['page']=='PASS'
        assert this_week_height_budget(width,guideline+1,900)['page']=='WARN'
        assert this_week_height_budget(width,fail,900)['page']=='WARN'
        assert this_week_height_budget(width,fail+1,900)['page']=='FAIL'
        assert this_week_height_budget(width,guideline,2000)['first_screen']=='WARN'
    for path in (ROOT/'.claude/commands').glob('*.md'):
        if path.name not in ('analytics.md','call-review.md'):
            # Unchanged commands need no analytics hook; changed commands keep main plus <=3 lines.
            baseline=__import__('subprocess').run(['git','diff','--numstat','f7e43b0','--',str(path)],
                cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
            if baseline: feature_command(path.name)
    print('PASS regressions: missing baseline never wins, whole-percent display, one-week badge, height warning/+30%, command footprint.')


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
        assert_rank_projection(base)
        points=[{'point':p,'state':'met','quote':'Proof'} for p in range(1,10)]
        points[8].update(state='not needed',reason='Informed disqualification; proposal not appropriate.')
        assert badges._call_fraction(points)==1
        points[8].pop('reason')
        assert badges._call_fraction(points) is None
    print('PASS B/K: accumulated1/3/6/13/26, pauses retain progress, first-week max2, content gate, zero-opportunity neutrality, stable rank projection and reasoned disqualification.')


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
        (path/'call-review.md').write_text("## Coach's read\n\n"+EXAMPLE_CALL_READ+"\n\n## Nine points\n\nSaved via pipeline.\n\n## Next step\n\nReview Friday.\n")
        review={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote} for p in range(1,10)],
                'moments':[{'quote':quote,'better_wording':'Ask what the saved time enables.'}],
                'fix':'Confirm the owner','example':'Who owns the next step?','next_step':'Review Friday.'}
        record(jid,{'call_review':review})
        view=json.loads(run('cockpit.py','job',jid).stdout)
        assert not (folder/'data/analytics-history.jsonl').exists()
        card=view['call_cards'][0]
        assert card['coach_read']==EXAMPLE_CALL_READ and 120<=len(card['coach_read'].split())<=180 and len(card['points'])==9
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
        seed({'id':jid,'title':'Build an audit dashboard in Airtable','source':'outbound','status':'call','applied_at':analytics_stamp(today-dt.timedelta(days=2)),
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
        (path/'call-review.md').write_text("## Coach's read\n\n"+EXAMPLE_CALL_READ+"\n\n## Next message\n\nCan you confirm the audit owner?\n\n## Next step agreed on the call\n\nClient confirms the owner by Friday.\n\n## Nine points\n\nSaved below.\n")
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
            required={'lead_id','label','date','reviewable','source_prompt','points','quote','read','next_message','as_of','reviewed_at','title','key_finding','marker','importance','this_week'}
            assert set(entry)==required | {'applications':{'sent_copy','loom_transcript'},'chats':{'last_writer'},'proposals':{'scope','price','decision_date'}}[stage]
        # Frozen section14 rows add titles, short findings, week filter and importance.
        for rows in sections.values():
            assert [row['importance'] for row in rows]==sorted(row['importance'] for row in rows)
            for row in rows:
                assert row['title']=='Build an audit dashboard in Airtable'
                assert 0<len(row['key_finding'].split())<=12
                assert row['marker'] in ('needs work','keep') and isinstance(row['this_week'],bool)
        assert all({key:value for key,value in row.items() if key not in ('title','key_finding','marker','importance','this_week')} == {key:value for key,value in saved.items() if key not in ('title','key_finding','marker','importance','this_week')}
                   for row,saved in zip(sections['calls'],snapshot['call_cards']))
        card=sections['calls'][0]
        assert card['agreed_step']=='Client confirms the owner by Friday.'
        assert card['next_message']=='Can you confirm the audit owner?'
        assert [p['label'] for p in card['points'] if p['point'] in (7,9)]==['Why you','Next step on Upwork']
        patterns=snapshot['conversations']['patterns']
        assert len(patterns)==1 and patterns[0]['text']==reason
        assert {q['stage'] for q in patterns[0]['quotes']}=={'applications','chats','calls','proposals'}
        assert all(q['quote']==quote for q in patterns[0]['quotes'])
        assert_rank_projection(snapshot)
        visible=cockpit.snapshot_view(snapshot)
        assert_rank_projection(visible)
        assert visible['rank_progress']==snapshot['rank_progress']
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
    assert strip['biggest_change']=={'key':'first_reply','name':'first_reply','text':'first_reply 10 -> 2','change_text':'vs the 4 weeks before','direction':'gain','value':2,'previous':10}
    model['presentation']['scorecard']=[mover('first_reply',20,10),mover('reply_rate',9,10)]
    assert analytics.progress_strip(model)['biggest_change']['key']=='first_reply'
    assert analytics.progress_strip(model)['biggest_change']['direction']=='decline'
    model['presentation']['scorecard']=[mover('reply_rate',100,None),mover('first_reply',1,10,0),mover('reply_rate',100,10,state='missing')]
    assert analytics.progress_strip(model)=={'biggest_change':None,'newest_badge':None,'newest_badge_basis':'No earned badge recorded.'}
    print('PASS frozen25–34: exact content keys and limits, retained gate, parsed call fields, quoted four-stage projection/patterns, source refusals, gain/decline/unknown, short catalogue and rank preservation.')


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
        (path/'call-review.md').write_text("## Coach's read\n\n"+EXAMPLE_CALL_READ+"\n")
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
        assert projection['review_on'] in projection['measurement'] and 'completed replies' in projection['measurement']
        snapshot['reviews']['conversation']['goal_ref']='reply_rate'
        assert analytics.goal_cards(snapshot)[0]['coach_example'] is None
        try:analytics.validate_goals({'week':snapshot['week'],'goals':[dict(goal,example='Arbitrary coaching')]})
        except ValueError:pass
        else:raise AssertionError('Canonical goal schema loosened.')
        assert analytics.CONVERSATION_POINTS==POINTS and set(analytics.CALL_POINT_LABELS)==set(range(1,10))
        assert analytics.CALL_POINT_LABELS[7]=='Why you' and analytics.CALL_POINT_LABELS[9]=='Next step on Upwork'
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
    assert 'no chronology claimed' in tied['newest_badge_basis']
    print('PASS supervised corrections:180/181 and100/101; summary/incomplete/unread source gates; Loom source refusal; exact projections; log assessment verification; read-only historical migration preserves statistical rank and funnel evidence; strict goals/matching example/measurement; timestamp chronology and tie unknown; canonical rubric definitions.')


def compact_community_contract():
    import analytics
    from analytics_forbidden_terms import assert_member_copy, self_check
    from analytics_fixture import analytics_payload, analytics_sync_marker
    from analytics_replay import maya_card_example
    self_check()
    def plain_member_text(markup):
        return assert_member_copy(markup, 'community', (
            '7-day follow-up', '3/3 steps', 'steps', 'No clear change',
            'finished cases', 'window', 'Target ', '—',
        ))
    today=dt.date(2026,10,14)
    with fixture('part1-compact-community') as folder:
        analytics_sync_marker(folder)
        (folder/'context/me.md').write_text('Name: Maya Rivers\n')
        snapshot=analytics.compute(today,jobs=[])
        value=analytics_payload(snapshot)
        example=maya_card_example(value)
        analytics.add_goals({'week':'2026-W43','goals':[dict(goal,start='2026-10-19',review_on='2026-10-26') for goal in example['goals_next']]})
        card=analytics.snapshot_public_card(example,[])
        assert card['member_name']=='Maya R.' and card['applications']==31
        assert [(card[key]['k'],card[key]['n']) for key in ('reply_rate','reply_to_call','booked_to_held','proposal_to_won')] == [(29,140),(9,29),(8,9),(3,6)]
        html=analytics.public_onepager_html(card)
        text=plain_member_text(html)
        assert 'Funnel Score 88, was 81' in html.split('</header>')[0] and 'weeks in a row' not in html
        assert all(label in text for label in ('Reply rate','Call rate','Show-up rate','Win rate','leak'))
        assert all(label in text for label in ('Applications', 'Replies', 'Calls booked', 'Calls held', 'Proposals', 'Won'))
        assert all(count in text for count in ('29 of 140', '9 of 29', '8 of 9', '3 of 6'))
        win_row=next(row for row in example['presentation']['scorecard'] if row['key']=='proposal_to_won')
        assert win_row['finished']=={'k':3,'n':6} and win_row['pending']=={'n':2}
        assert win_row['finished']['n']+win_row['pending']['n']==8
        assert card['reply_rate']['entry_period']=={'start':'2026-09-21','end':'2026-10-18'}
        assert '2026-10-12 to 2026-10-18' in text and '2026-09-21 to 2026-10-18' in text and 'width:min(100%,600px)' in html
        top_steps=copy.deepcopy(card);top_steps['reply_rate']['rung_reached']=3
        assert plain_member_text(analytics.public_onepager_html(top_steps))==text
        import base64
        badge_bytes=(analytics.ROOT/'website/public/badges/swift-sail-silver.webp').read_bytes()
        assert 'data:image/webp;base64,'+base64.b64encode(badge_bytes).decode() in html and html.count('Swift Sail')==1
        assert len(card['goals'])==len({goal['text'] for goal in card['goals']})==3
        assert 'partly' in html and 'not yet' in html and '—' not in html
        reviews=[{'start':'2026-10-07','change':goal['text'],'done_k':goal['k'],'done_n':goal['n'],'execution_state':goal['state']} for goal in card['goals']]
        reviews += [dict(reviews[0]),dict(reviews[1]),dict(reviews[2])]
        projected=analytics.community_card([],today,snapshot['kpis'],reviews,snapshot['week'],0)
        assert len(projected['goals'])==len({goal['text'] for goal in projected['goals']})==3
        projected['funnel_score']=copy.deepcopy(snapshot['funnel_score'])
        actual_text=plain_member_text(analytics.public_onepager_html(projected))
        bounds=projected['reply_rate']['entry_period']
        assert bounds==analytics.period(tuple(date-dt.timedelta(days=28) for date in analytics.span(today,28)))
        assert f"{bounds['start']} to {bounds['end']}" in actual_text
        assert 'Funnel · 28 days' in actual_text and 'last 28 days' not in actual_text.casefold()
        for mutation in ('four','duplicate'):
            bad=copy.deepcopy(card)
            if mutation=='four': bad['goals'].append(copy.deepcopy(card['goals'][0]))
            else: bad['goals'][2]=copy.deepcopy(card['goals'][0])
            try: analytics.validate_community_card(bad,[])
            except ValueError: pass
            else: raise AssertionError('Public cap or distinct goal rule weakened')
        legacy=copy.deepcopy(example);legacy.pop('community')
        legacy['community_card']['question']='What helped you improve this stage?'
        assert analytics.snapshot_public_card(legacy,[])['question']==legacy['community_card']['question']
        for canonical in ({},{'question':None}):
            absent=dict(legacy,community=canonical)
            absent_card=analytics.snapshot_public_card(absent,[])
            assert absent_card['question'] is None
            assert 'class="question"' not in analytics.public_onepager_html(absent_card)
        canonical=dict(legacy,community={'question':'How do you offer two useful call times?'})
        prepared=analytics.prepare_snapshot(dict(value,community=canonical['community']),today)
        assert prepared['community']['question']==prepared['community_card']['question']==canonical['community']['question']
        sources=[{'title':'Private Tender Name','client':{'name':'Secret Client Name'},'description':'Confidential spoken client material'}]
        for question in ('What did Secret Client Name request?','Who owns Private Tender Name?',
                         'Could confidential spoken client material change?', ' '.join(['word']*15),'Email private@example.test'):
            assert analytics.snapshot_public_card(dict(legacy,community={'question':question}),sources)['question'] is None
        assert card['rank'] in dict(analytics.RANK_LEVELS) and 'Rank: '+card['rank'] in text
        badge_names=('Swift Sail','Quick Draw','True North')
        for count in (0,1,3):
            weekly=copy.deepcopy(card)
            weekly['new_badge']=None
            weekly['earned_badges']=[{'badge':name,'tier':'Bronze','earned_week':card['week'],
                'new':True,'progress_to_next':'1 of 3 weeks'} for name in badge_names[:count]]
            weekly['more_badges']=2 if count==3 else 0
            weekly['next_badge']={'name':'Swift Sail','tier':'Gold','weeks_remaining':2}
            output=plain_member_text(analytics.public_onepager_html(weekly))
            assert ('+2 more' in output)==(count==3)
            if count==0: assert '2 weeks to Swift Sail Gold' in output
            else:
                assert '2 weeks to Swift Sail Gold' not in output
                for name in badge_names[:count]: assert name in output
        for mutation in ('bad-rank','private-rank-field','bad-score','bad-hold','four-badges','wrong-week'):
            bad=copy.deepcopy(card)
            if mutation=='bad-rank': bad['rank']='Secret Client Name'
            elif mutation=='private-rank-field': bad['rank_progress']['client_name']='Secret Client Name'
            elif mutation=='bad-score': bad['rank_progress']['score']=101
            elif mutation=='bad-hold': bad['rank_progress']['held_weeks']=5
            elif mutation=='four-badges': bad['earned_badges']*=4
            else: bad['earned_badges'][0]['earned_week']='2026-W41'
            try: analytics.validate_community_card(bad,[])
            except ValueError: pass
            else: raise AssertionError(('Public rank/badge boundary accepted',mutation))
        empty=copy.deepcopy(snapshot['community_card'])
        html=analytics.public_onepager_html(empty)
        text=plain_member_text(html)
        assert 'No opportunities' in text and 'Not clear yet' in text and '0 of 0' not in text and '0/0' not in text and '0/3 steps' not in text
    print('PASS PART1 community: compact frozen card, canonical optional question, legacy safety, privacy, distinct three-goal cap, score, Maya example and truthful periods.')



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
    # Four required cases, plus accounting, caps and clock boundaries.
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
    # Exercise all six dimensions together to enforce independent recommendation caps.
    all_bands = planted()
    for job in all_bands:
        high = job['application_facts']['budget_band'] == '<500'
        for dimension, values in analytics.pipeline.APPLICATION_BANDS.items():
            if dimension != 'budget_band': job['application_facts'][dimension] = values[0] if high else values[-2]
    capped = analytics.job_fit_fields(all_bands, today)
    assert len(capped['apply']) == 2 and len(capped['skip']) == 1 and len(capped['patterns']) == 2
    assert len(analytics.facts_sheet({'week': '2026-W43', 'kpis': {}, 'insights': {'job_fit': capped}})['job_fit']['patterns']) == 2
    assert all(not any(word in row['text'].casefold() for word in ('wilson', 'binomial', 'cohort', 'hypothesis', 'statistic', '\u2014')) for row in capped['apply'] + capped['skip'])
    # Job-fit fields survive real compute/prepare/record and cannot be overwritten by prose.
    with fixture('part2-job-fit-record'):
        value = analytics.compute(today)
        assert value['insights']['job_fit']['patterns'] == []
        reply = next(row for row in value['presentation']['scorecard'] if row['key'] == 'reply_rate')
        assert reply['job_fit'] == value['insights']['job_fit']
        from analytics_fixture import analytics_payload
        prepared = analytics.prepare_snapshot(analytics_payload(value), today)
        assert prepared['insights']['job_fit'] == value['insights']['job_fit']
        assert analytics.facts_sheet(prepared)['job_fit']['patterns'] == []
        tampered = copy.deepcopy(prepared)
        tampered['insights']['job_fit']['finished_n'] = 999
        try: analytics.record_snapshot(tampered)
        except ValueError as error: assert 'insights must come unchanged' in str(error), str(error)
        else: raise AssertionError('Computed job fit was replaceable')
    assert abs(analytics.job_fit_exact_p(20, 20, .5) - 2 / 2**20) < 1e-12
    assert analytics.job_fit_exact_p(0, 20, 0) == 1 and analytics.job_fit_exact_p(20, 20, 1) == 1
    print('PASS PART2 job fit: both halves confirmed, single half early, small/unknown silent, frozen-only bands/costs, seven-day/date boundaries, caps and plain member copy.')


def maya_numeric_truth_contract():
    import analytics
    from analytics_replay import maya_card_example
    from analytics_fixture import ROOT
    from analytics_forbidden_terms import member_text
    with fixture('maya-numeric-truth') as folder:
        me=folder/'context/me.md'
        me.write_text('Name: Maya Rivers\n'+me.read_text())
        example=maya_card_example(analytics.compute(dt.date(2026,10,19)))
        analytics.add_goals({'week':'2026-W43','goals':[dict(goal,start='2026-10-19',review_on='2026-10-26') for goal in example['goals_next']]})
        rows={row['key']:row for row in example['presentation']['scorecard']}
        assert all(row['period_label']=='Last 28 days' for row in rows.values())
        for key in ('speed_10min','job_fit','first_reply','follow_ups_on_time'):
            assert rows[key]['value'] is None and rows[key]['state']=='missing'
            assert rows[key]['finished']=={'k':None,'n':None}
        assert rows['speed_10min']['known_weekly']=={'k':26,'n':31}
        efficiency=rows['value_per_100_connects']
        assert efficiency['value'] is None and efficiency['finished']=={'k':None,'n':None}
        assert example['report_facts']['four_weeks']['connects_spend']==384
        assert example['report_facts']['four_weeks']['application_contract_value']==4400
        assert '$384' in efficiency['counting'] and 'quantity' in efficiency['counting']
        assert rows['proposal_to_won']['finished']=={'k':3,'n':6}
        assert rows['proposal_to_won']['pending']=={'n':2}
        assert example['community_card']['proposal_to_won']['value']==50
        assert example['community_card']['first_reply_median_min'] is None
        assert example['report_facts']['weekly']['first_reply_minutes']==4
        volumes=example['community_card']['stage_counts']
        assert volumes=={'applications':140,'replies':29,'calls_booked':9,'calls_held':8,
                         'proposals':8,'won':3,'pending_proposals':2}
        public_html=analytics.public_onepager_html(example['community_card'])
        for label in ('Calls held','Proposals'):
            assert __import__('re').search(r'<div class="stage"><span>'+label+r'</span>.*?<b>8</b>',public_html),label
        assert '2 still open' in public_html and '3 of 6' in public_html
        assert '4 min first reply' not in public_html
        half_public=copy.deepcopy(example['community_card'])
        half_public['reply_rate'].update(value=18.5,k=37,n=200)
        half_public['stage_counts'].update(applications=200,replies=37)
        half_public['biggest_improvement']={'kpi':'reply_rate','from':12.5,'to':18.5}
        half_html=analytics.public_onepager_html(half_public)
        half_text=member_text(half_html)
        assert '13% → 19%' in half_text and 'Reply rate 19%' in half_text
        assert half_public['reply_rate']['value']==18.5
        text=(ROOT/'references/chat-report-example.md').read_text()
        checked=analytics.check_report(text,example)
        assert checked['status']=='PASS' and checked['checked_values']>=70,checked
        for wrong in (text.replace('31 applications this week','25 applications this week'),
                      text.replace('**$4,200**','**$3,500**'),
                      text.replace("that's 21%","that's 18%"),
                      'Last week you sent 31 applications.',
                      'Last month you won $4,200.',
                      'Funnel Score 88, down from 81.',
                      text.replace('4 minutes on median','4 minutes on average'),
                      text.replace('one is now a call on Thursday','two are now calls on Thursday'),
                      text+'\nYou sent 42 applications this week.'):
            rejected=analytics.check_report(wrong,example)
            assert rejected['status']=='FAIL' and rejected['errors'],rejected
        slow=copy.deepcopy(example)
        slow['report_facts']['weekly'].update(invite_reply_minutes=120,invites_within_hour=3)
        rejected=analytics.check_report(text,slow)
        assert rejected['status']=='FAIL' and rejected['errors'],rejected
        wrong_currency=copy.deepcopy(example)
        wrong_currency['north_star']['currency']='EUR'
        rejected=analytics.check_report(text,wrong_currency)
        assert rejected['status']=='FAIL' and rejected['errors'],rejected
        rejected=analytics.check_report(text.replace('**$4,200**','**EUR 4,200**'),example)
        assert rejected['status']=='FAIL' and rejected['errors'],rejected
    print('PASS Maya facts: weekly observations stay weekly; incomplete 28-day habits and Connects quantity unknown; 3/6 finished wins plus 2 pending; actual stage volumes; report metric, period, direction, statistic, currency and invite negative controls.')


def main():
    maya_numeric_truth_contract()
    rank_contract()
    progress_and_layout_contract()
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
    compact_community_contract()
    job_fit_contract()


if __name__ == '__main__':
    main()
