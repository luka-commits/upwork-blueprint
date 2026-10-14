#!/usr/bin/env python3
"""Eight example weeks through real pipeline/analytics writers in retained temp storage.
No external providers and no writes to the repository's data/ or jobs/.
"""
import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'code')]
from analytics_fixture import analytics_rows, analytics_payload, run, EXAMPLE_CALL_READ
import analytics


def protected_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('data', 'jobs') for p in (ROOT / directory).rglob('*') if p.is_file()}


def maya_card_example(snapshot):
    """Illustrative card values from chat-report-example, never a recorded measurement.

    Illustrative entry dates cover the 28 days ending with the displayed week.
    These are invented example counts, not a mature measured cohort. Actual
    community cards retain their historical dates and fixed follow-up horizons.
    The caller must use isolated example storage and save its agreed goal texts.
    """
    # Public-only example envelope: never copy measured private KPIs into an illustration.
    value = {'community_card': copy.deepcopy(snapshot['community_card'])}
    value['week'] = '2026-W42'
    value['generated_at'] = '2026-10-18T18:00:00+02:00'
    value['report'] = 'Illustrative Maya community example, not a measured replay week.'
    value['community'] = {'question': 'What would you test to turn more replies into calls?'}
    card = value['community_card']
    card.update(week=value['week'], member_name='Maya R.', applications=31,
                activity_period={'start':'2026-10-12','end':'2026-10-18'},
                next_focus=analytics.LABELS['reply_to_call'], first_reply_median_min=None,
                biggest_improvement={'kpi':'reply_rate','from':18,'to':21}, won_value=None)
    bounds = analytics.period(analytics.span(dt.date(2026,10,19),28))
    for key, k, n in (('reply_rate',29,140),('reply_to_call',9,29),('booked_to_held',8,9),
                      ('call_to_won',3,6),('proposal_to_won',3,6)):
        row=card[key]
        row.update(k=k,n=n,value=round(100*k/n),entry_period=copy.deepcopy(bounds),
                   state=analytics.rate_state(k,n,row['target']),trend='undecided',
                   rung_reached=sum(analytics.rate_state(k,n,target)=='pass' for target in
                       {'reply_rate':(11,15,20),'reply_to_call':(30,40,50),'booked_to_held':(70,80,90),
                        'call_to_won':(20,25,30),'proposal_to_won':(20,25,30)}[key]))
    card['reply_to_call']['progression']={'booked_calls':9,'held_calls':8,'offer_or_contract_without_call':0}
    card['goals']=[{'text':text,'done':False,'k':k,'n':n,'state':'partial' if k else 'undone'}
                   for text,k,n in (('Offer two call times',7,9),('Budget before price',1,4),('Decision date',0,2))]
    card['goals_done']='0/3'
    card['funnel_score']={'score':88,'previous':81,'parts':{'habits':90,'results':85},'dropped':[],'baseline_only':False}
    card['new_badge']={'badge':'Swift Sail','tier':'Silver','earned_week':value['week'],
                       'new':True,'progress_to_next':'3 of 6 weeks'}
    card['top_badges']=[]
    card['stage_counts']={'applications':140,'replies':29,'calls_booked':9,
        'calls_held':8,'proposals':8,'won':3,'pending_proposals':2}
    # Frozen example scores 81 then 88 do not prove a four-week held rank.
    value['rank_progress']=analytics.rank_fields({'week':value['week'],'funnel_score':card['funnel_score']},
        [{'week':'2026-W41','funnel_score':{'score':81}}])
    value['rank']=value['rank_progress']['rank']
    card.update(rank=value['rank'],rank_progress=copy.deepcopy(value['rank_progress']),
        earned_badges=[copy.deepcopy(card['new_badge'])],more_badges=0,
        next_badge={'name':'Swift Sail','tier':'Gold','weeks_remaining':3})
    value['funnel_score']=copy.deepcopy(card['funnel_score'])
    commitments = [
        ('reply_to_call', 'Offer two call times', 'an interested client replies',
         "answer their question first, then offer two available Upwork meeting times in their time zone when a call helps them decide.",
         'Tue 10:00 or Wed 15:00 your time, 15 min on Upwork?',
         'Sent replies offered two available times after answering the client’s question.'),
        ('call_review', 'Budget before price', 'you are about to quote a price',
         'confirm the result, scope and budget, including any budget already agreed.',
         'For the booking flow we discussed, what budget range have you set aside?',
         'Full call transcripts show budget and scope confirmed before any price.'),
        ('proposal_to_won', 'Decision date', 'you send a proposal',
         'confirm who decides, agree a decision date and the next action on Upwork.',
         'Can you review this scope by Friday and confirm the decision here on Upwork?',
         'The Upwork thread shows an agreed decision date, rather than a date only requested.'),
    ]
    goal_displays=[{'stage':analytics.LABELS[key],'kpi':key,'change':title,
        'primary':index==0,'cue':cue,'action':action,'coach_example':example,'measurement':check,
        'fallback': 'Confirm the known budget or ask the range once.' if key=='call_review' else
                    'Offer one available time.' if key=='reply_to_call' else 'Confirm the next Upwork action.',
        'review_on':'2026-10-26'}
        for index,(key,title,cue,action,example,check) in enumerate(commitments)]
    value['goals_next']=[{key:goal[key] for key in ('stage','kpi','change','primary','cue','action','fallback','review_on')} for goal in goal_displays]
    value.update(synthetic=True, data_label='Maya example · illustrative, no member facts',
        periods={'activity':card['activity_period'],'cohort':bounds,'outcome':card['activity_period'],
                 'synced_at':value['generated_at']},
        north_star={'value':4200,'currency':'USD','wins':3,'value_unknown_n':0,'evidence':[]},
        forecast={'next_30_days':3500}, pipeline={'live':11},
        verdict={'kpi':'reply_to_call','headline':'Turn replies into calls',
                 'reason':'29 replies led to 9 booked calls over four weeks; 20 did not book. Of those, 6 are still talking, 9 went quiet and 5 said no or were not a fit.'},
        goals_review=[{'goal_id':'maya-last-call-times','kpi':'reply_to_call','change':'Offer two call times','done_k':7,'done_n':9,
            'effect':'undecided','effect_text':'4 of those 7 booked a call; neither of the other 2 did. Promising, but too few conversations to be sure.',
            'decision':'Keep it','evidence':[]},
            {'goal_id':'maya-last-budget','kpi':'call_review','change':'Budget before price','done_k':1,'done_n':4,
             'effect':'undecided','effect_text':'Price came before budget in 3 calls. Keep practising this week.',
             'decision':'Carry over','evidence':[]}])
    # Keep illustrative UI counts separate from the eight measured replay weeks.
    counts={'reply_rate':(29,140),'reply_to_call':(9,29),'booked_to_held':(8,9),
            'proposal_to_won':(3,6),'weekly_volume':(140,100),'job_fit':(31,31),
            'speed_10min':(26,31),'first_reply':(4,9),'follow_ups_on_time':(8,9),
            'proposal_on_time':(7,8),'invite_to_call':(1,4),'offer_to_contract':(1,1),
            'value_per_100_connects':(4400,384)}
    value['kpis']={}
    rows=[]
    for saved in snapshot.get('presentation',{}).get('scorecard',[]):
        key=saved['key']; k,n=counts[key]
        unit='min' if key=='first_reply' else '$' if key=='value_per_100_connects' else '' if key=='weekly_volume' else '%'
        current=4 if key=='first_reply' else 35 if key=='weekly_volume' else round(100*k/n)
        target=25 if key=='weekly_volume' else saved['target']['value']
        value['kpis'][key]={'label':saved['name'],'unit':unit,'direction':'down' if key=='first_reply' else 'up','target':target}
        rows.append({'key':key,'group':saved['group'],'name':saved['name'],'stage_label':saved.get('stage_label'),
            'period_label':'Last 28 days','value':None if key=='offer_to_contract' else current,
            'finished':{'k':None if key in ('first_reply','offer_to_contract') else k,'n':None if key in ('first_reply','offer_to_contract') else n},'pending':{'n':0},'state':'missing' if key=='offer_to_contract' else 'observed',
            'change':{'previous_value':18 if key=='reply_rate' else None,'comparison_label':'Previous four weeks'},
            'target':{'kind':saved['target']['kind'],'value':target,'level':card[key]['rung_reached'] if key in card and isinstance(card[key],dict) and 'rung_reached' in card[key] else saved['target']['level'],'thresholds':saved['target']['thresholds']},
            'series':{'label':'Example period','unit':unit,'points':[current]},'counting':f'Illustrative counts from {bounds["start"]} to {bounds["end"]}; these example results are not measured member outcomes.' if key in ('reply_rate','reply_to_call','booked_to_held','proposal_to_won') else saved['counting'],
            'split':[{'label':'Held calls to proposal','k':8,'n':8}] if key=='proposal_on_time' else [],
            'focus':{'reason':value['verdict']['reason']} if key=='reply_to_call' else None,
            'evidence':[], 'market':None,'next_action':None})
    # The brief supplies only this week's habits, not the earlier 109 application
    # observations. Missing older sources cannot become a four-week estimate.
    incomplete_habits = {'speed_10min', 'job_fit', 'first_reply', 'follow_ups_on_time'}
    for row in rows:
        if row['key'] == 'proposal_to_won':
            row['pending'] = {'n':2}
            row['counting'] = 'Three won and three lost proposals have finished. Two open proposals stay pending and never count as lost.'
        if row['key'] in incomplete_habits:
            row.update(value=None, state='missing', finished={'k':None,'n':None},
                known_weekly={'k':counts[row['key']][0], 'n':counts[row['key']][1]},
                counting='This week is known; earlier observations in the last 28 days are missing. Supply those records to compare four-week habits.')
        if row['key'] == 'value_per_100_connects':
            row.update(value=None, state='missing', finished={'k':None,'n':None},
                counting='The four-week cost is $384 and contract value is $4,400. The number of Connects is unknown; dollars spent cannot replace that quantity.')
    value['presentation']={'scorecard':rows,'focus':{'headline':value['verdict']['headline'],'reason':value['verdict']['reason']},
        'activity_summary':'31 applications this week against a goal of 25; 26 sent within 10 minutes. All fit your lane and rate.',
        'live_leads_text':'11 live leads: 6 still talking, 3 calls booked and 2 proposals waiting.',
        'goal_cards':copy.deepcopy(goal_displays),
        'progress_strip':{'score_history':[{'week':'2026-W41','value':81},{'week':value['week'],'value':88}],
            'biggest_change':{'key':'reply_rate','name':'Reply rate','previous':18,'value':21,'direction':'gain','text':'Reply rate 18% -> 21%','change_text':'vs the 4 weeks before'},
            'newest_badge':{'name':'Swift Sail','tier':'Silver','earned_week':value['week'],'short':'Quick, qualified applications',
                            'progress_text':'3 of 6 weeks to Gold'}},'next_run_day':'Monday'}
    # Private numeric truth for the freely written frozen Maya report. These are
    # illustrative facts, separate from the eight measured replay snapshots.
    value['report_facts'] = {
        'weekly': {'applications':31,'goal':25,'fast':26,'fast_minutes':10,
            'first_reply_minutes':4,'followups_done':8,'followups_due':9,
            'invites':4,'invites_answered':4,'invite_reply_minutes':60,
            'invites_within_hour':4,'invite_calls':1,
            'calls':5,'transcripts_read':4,'price_before_budget':3,'price_read_calls':4,
            'cautious_clients':2,'proposal_wins':2,'direct_offer_wins':1},
        'four_weeks': {'applications':140,'replies':29,'reply_rate':21,
            'previous_reply_rate':18,'booked_calls':9,'active_chats':6,'quiet_chats':9,
            'declined_chats':5,'held_calls':8,'no_shows':1,'proposals':8,
            'fast_proposals':7,'fast_proposal_minutes':30,'proposal_wins':3,
            'open_proposals':2,'lost_proposals':3,'decision_dates':2,'ended_leads':8,
            'price_losses':4,'fixed_price_ceiling':500,'connects_spend':384,
            'application_contract_value':4400},
        'pattern': {'reply_rate':31,'comparison_reply_rate':15,'jobs':64,'start_week':39},
        'live': {'total':11,'chats':6,'calls':3,'proposals':2,'quiet_to_reopen':4,'quiet_days':30},
        'goal': {'offered_times':7,'replies':9,'booked':4,'no_times':2,'no_times_booked':0,
            'budget_first':1,'calls':4},
        'forecast': {'days':30,'value':3500}}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='An empty directory under /tmp; defaults to a retained temp directory.')
    args = parser.parse_args()
    folder = pathlib.Path(args.output).resolve() if args.output else pathlib.Path(tempfile.mkdtemp(prefix='analytics-eight-week-', dir='/private/tmp'))
    if not str(folder).startswith(('/private/tmp/', '/tmp/')):
        raise SystemExit('Replay storage must be temporary, never repository data.')
    folder.mkdir(exist_ok=True, parents=True)
    if any(folder.iterdir()): raise SystemExit('Replay directory must be empty; retained proof is never overwritten.')
    before = protected_hashes()
    env = dict(os.environ)
    env.update(BLUEPRINT_CONTEXT=str(folder/'context'), BLUEPRINT_DATA=str(folder/'data'),
               BLUEPRINT_JOBS=str(folder/'data/jobs.json'), BLUEPRINT_JOBDIR=str(folder/'jobs'), PYTHONDONTWRITEBYTECODE='1', BLUEPRINT_EXAMPLE_DATA='1')
    for name in ('data', 'jobs', 'context'): (folder/name).mkdir()
    (folder/'context/me.md').write_text('Name: Maya Rivers\n\n## Weekly goal\n25\n\n## Analytics day\nMonday\n\n## Working hours\nMon-Fri 09:00-18:00 Europe/Berlin\n\nAll events and reviews below are synthetic example data.\n')
    rows = analytics_rows()
    table = ['| Week | Funnel Score | Baseline only | New badges | Earned badges |', '|---|---:|---|---|---|']
    job_fit_table = ['| Week | Finished applications | Waiting | Job fit |', '|---|---:|---:|---|']
    quote = 'Manual checks cost three hours each week.'
    own = 'What outcome would make this worthwhile?'
    pattern = 'Confirm the owner before offering a date.'
    with mock.patch.dict(os.environ, env, clear=True):
        for index in range(8):
            start = dt.date(2026, 8, 24) + dt.timedelta(weeks=index)
            today = start + dt.timedelta(days=7)
            new = [row for row in rows if row['found_at'][:10] == start.isoformat()]
            reviewed = [row['id'] for row in new if row.get('proposal_sent_at') and row.get('applied_at')][:4]
            for row in new:
                if row.get('applied_at'):
                    row['speed_to_lead_s'] = 600 if row.get('application_facts', {}).get('posted_age_band') == '<10m' else 1200
                    row['application_sent_verified'] = True
                    row['application_review'] = {'state': 'pass', 'reason': 'Example coach confirms relevant submitted audit copy'}
                if row['id'] in reviewed:
                    for kind in ('application', 'proposal'):
                        row[kind+'_review']={'state':'pass','reason':'Example saved content review.','quote':quote,
                            'free_read':'The saved example names the cost; confirm who owns the inputs.',
                            'next_message':'Who will own the audit inputs?',
                            'points':[{'point':1,'state':'met','quote':quote,'reason':pattern}]}
                path = folder/'jobs'/row['id'];path.mkdir()
                if row.get('applied_at'):
                    (path/'application.sent.md').write_text('EXAMPLE submitted application: '+quote+' I can map your audit gaps and agree a clear scope.\n')
                    if row['id'] in reviewed: (path/'loom.md').write_text('EXAMPLE Loom transcript: '+quote+'\n')
                if row.get('proposal_sent_at'): (path/'proposal.md').write_text('EXAMPLE sent audit scope: '+quote+' Client reviews the agreed next step Friday.\n')
                if row.get('call_held_at'):
                    (path/'call.md').write_text('Member: Maya\nComplete: yes\nLanguage: English\nMaya: '+own+'\nClient: '+quote+'\nMaya: Let us agree the next step.\n')
                    if row['id'] in reviewed:
                        (path/'call-review.md').write_text("## Coach's read\n\n"+EXAMPLE_CALL_READ+"\n\n## Next message\n\nWho will own the audit inputs before Friday?\n\n## Agreed step\n\nClient reviews scope on Friday.\n\n## Nine points\n\nSee the saved nine-point rubric.\n")
            run('pipeline.py', 'add', '--file', '-', value=new)
            rubrics=[]
            for jid in reviewed:
                review={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote,'reason':pattern} for p in range(1,10)],
                    'moments':[{'quote':quote,'better_wording':'Ask how the saved time changes the weekly work.'}],
                    'fix':'Agree the review date','example':own,'next_step':'Client reviews scope on Friday',
                    'next_message':'Who will own the audit inputs before Friday?'}
                run('pipeline.py','record',jid,'--file','-',value={'call_review':review})
                rubrics.append(dict(review,lead_id=jid))
                run('sync.py','apply','--file','-',value={'threads':[{'job_id':jid,'room_id':'example-'+jid,
                    'messages_complete':True,'messages':[{'from':'client','at':start.isoformat()+'T10:00:00+02:00','text':quote},
                    {'from':'me','at':start.isoformat()+'T10:03:00+02:00','text':own}]}]})
                chat={'read':True,'last_writer':'me','free_read':'The saved example states a cost; the owner remains the next question.',
                    'next_message':'Who will own the audit inputs?',
                    'points':{key:{'state':'met','quote':quote,'reason':pattern} for key in analytics.CONVERSATION_POINTS}}
                run('pipeline.py','record',jid,'--file','-',value={'conversation_review':chat})
            run('sync.py', 'apply', '--file', '-', value={'connects': [{'at': row['applied_at'], 'amount': -12, 'reason': 'Example application', 'job_id': row['id']} for row in new if row.get('applied_at')], 'earnings': [{'week_start': start.isoformat(), 'contract_id': 'example-weekly', 'billed': 0, 'currency': 'USD'}]})
            (folder/'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(today).isoformat()}))
            value = analytics_payload(analytics.compute(today))
            call = next(row for row in new if row.get('call_held_at'))
            value['reviews']['call'].pop('coverage', None)
            value['reviews']['application'].pop('coverage', None)
            value['reviews']['call'].update(evidence_lead_ids=reviewed, rubric=rubrics)
            value['reviews']['application'].update(evidence_lead_ids=reviewed, rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':p,'state':'met'} for p in range(1,7)]} for jid in reviewed])
            value['reviews']['proposal']['evidence_lead_ids']=reviewed
            value['summary']=[f"This example week won {value['north_star']['wins']} new contracts.",
                              f"Qualified applications reached {value['kpis']['weekly_volume']['k']} against a commitment of {value['kpis']['weekly_volume']['target']:g}.",
                              'Next, use the agreed next step with each fitting lead.']
            value['community']={'question': 'What helps you agree the next step in useful conversations?'}
            value['report']='EXAMPLE synthetic week. This is isolated replay data, not a real member account.'
            snapshot = analytics.prepare_snapshot(value, today)
            analytics.add_goals({'week': snapshot['week'], 'goals': [dict(goal, start=today.isoformat()) for goal in snapshot['goals_next']]})
            saved = analytics.record_snapshot(snapshot)
            new_badges = ', '.join(row['badge']+' '+row['tier'] for row in saved['badges'] if row['new']) or 'none'
            earned = ', '.join(row['badge']+' '+row['tier'] for row in saved['badges']) or 'none'
            score=saved['funnel_score']
            table.append(f"| {saved['week']} | {score['score']} | {str(score['baseline_only']).lower()} | {new_badges} | {earned} |")
            fit = saved['insights']['job_fit']
            fit_rows = fit['apply'] + fit['skip']
            description = ' / '.join(row['text'] for row in fit_rows) or fit['empty_text']
            job_fit_table.append(f"| {saved['week']} | {fit['finished_n']} | {fit['pending_n']} | {description} |")
            (folder/f"{saved['week']}.json").write_text(json.dumps(saved, indent=2)+'\n')
        last = analytics.last()
        (folder/'latest.json').write_text(json.dumps(last, indent=2)+'\n')
        counts={stage:sum(row.get('reviewable') is True for row in entries) for stage,entries in last['conversations']['sections'].items()}
        assert all(count>=4 for count in counts.values()), counts
        assert last['conversations']['patterns'] and all(len({quote['stage'] for quote in row['quotes']})>=2 for row in last['conversations']['patterns'])
        from analytics_contract_tests import assert_rank_projection
        assert_rank_projection(last)
        assert last['rank_progress'] == analytics.rank_fields(last, analytics.read_lines('analytics-history.jsonl'))
        (folder/'community-card.html').write_text(analytics.public_onepager_html(analytics.snapshot_public_card(last)), encoding='utf-8')
        example=maya_card_example(last)
        # Approve these synthetic texts in the isolated goal writer, never real data.
        example_goal_day = analytics.day(last['generated_at']) + dt.timedelta(days=7)
        example_iso = example_goal_day.isocalendar()
        example_goal_week = f'{example_iso.year}-W{example_iso.week:02d}'
        analytics.add_goals({'week':example_goal_week,'goals':[dict(goal,start=example_goal_day.isoformat(),
            review_on=(example_goal_day+dt.timedelta(days=7)).isoformat()) for goal in example['goals_next']]})
        (folder/'maya-community-example.json').write_text(json.dumps(example,indent=2)+'\n')
        (folder/'maya-community-example.html').write_text(analytics.public_onepager_html(analytics.snapshot_public_card(example)),encoding='utf-8')
    assert len((folder/'data/analytics-history.jsonl').read_text().splitlines()) == 8
    assert protected_hashes() == before, 'Repository data or jobs changed.'
    proof = {'root': str(folder), 'environment': {key: env[key] for key in ('BLUEPRINT_CONTEXT','BLUEPRINT_DATA','BLUEPRINT_JOBS','BLUEPRINT_JOBDIR')}, 'week': last['week'], 'call_id': call['id'], 'snapshots': 8, 'reviewable_entries':counts,'cross_stage_patterns':len(last['conversations']['patterns']), 'protected_files': len(before), 'protected_unchanged': True}
    (folder/'replay-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    (folder/'replay-table.md').write_text('\n'.join(table)+'\n')
    (folder/'job-fit-table.md').write_text('\n'.join(job_fit_table)+'\n')
    print('\n'.join(table));print('\n'.join(job_fit_table));print(json.dumps(proof, indent=2))


if __name__ == '__main__': main()
