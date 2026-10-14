#!/usr/bin/env python3
"""Show a fully filled example of the /analytics page without any Upwork data.

Builds eight weeks of fictional data for "Daniel K." in a fresh temporary folder,
through the real pipeline and analytics writers, then starts the cockpit on it.
Nothing touches a real member's data/, jobs/ or context/. The eight weeks end with the current
week (Monday of today in Lisbon), so "This week" is always filled.

    python3 tools/demo_analytics.py [--port 4370] [--no-serve]
"""
import argparse
import copy as fixture_copy
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def run(script, *args, value=None):
    """Call one of the real writer scripts, as a member's command would."""
    p = subprocess.run([sys.executable, str(ROOT / 'code' / script), *map(str, args)],
                       input=json.dumps(value) if value is not None else None,
                       text=True, capture_output=True, env=os.environ)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    return p


def build(OUT, today=None):
    """Write Daniel's eight example weeks into OUT; returns the last analytics record."""
    sys.path.insert(0, str(ROOT / 'code'))
    # The data was authored for the week of 12 Oct 2026. One offset (whole weeks) moves it so that
    # its last week is the current week in the member's time zone; every date goes through day().
    now = dt.datetime.now(zoneinfo.ZoneInfo('Europe/Lisbon')) if today is None else dt.datetime.combine(today, dt.time(12))
    shift = dt.timedelta(days=(now.date() - dt.timedelta(days=now.weekday()) - dt.date(2026, 10, 12)).days)

    def day(y, m, d):
        return dt.date(y, m, d) + shift

    def when(y, m, d, weekday=True):
        v = day(y, m, d)
        return f"{v:%A} " * weekday + f"{v:%B} {v.day}"
    for name in ('data', 'jobs', 'context'):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    import analytics as a
    # Fixture adapter, adapted independently from reference; no original generator imports.
    orig_calc=a.calculate
    @a.member_clock
    def calc(jobs,today,since=None,now=None,cohort_days=28,activity_bounds=None,**kw):
        k,north=orig_calc(jobs,today,since=since,now=now,cohort_days=cohort_days,activity_bounds=activity_bounds,**kw)
        bounds=activity_bounds or a.span(today,cohort_days)
        for key,entry,exit in [('reply_rate','applied','replied'),('reply_to_call','replied','call_booked'),('booked_to_held','call_booked','call_held'),('held_to_proposal','call_held','proposal_sent'),('proposal_to_won','proposal_sent','won')]:
            rows=[j for j in jobs if j.get('source')=='outbound' and a.inside(a.event(j,entry),bounds)]
            if key=='proposal_to_won':rows=[j for j in rows if j.get('status') in ('won','lost')]
            metric=a.rate_metric(key,rows,lambda j:bool(a.event(j,exit)) and a.event(j,exit)<=a.run_timestamp(today,now),a.bars()[key])
            k[key].update({f:metric[f] for f in ('k','n','value','low','high','state','evidence')});k[key]['reason']='Fictional preview: observed conversions in the stated window.'
        return k,north
    a.calculate=calc
    orig_score=a.funnel_score
    series=[58,60,63,66,69,71,74,76]
    def score(s,history=None):
        r=orig_score(s,history);i=max(0,min(7,(dt.date.fromisoformat(s['generated_at'][:10])-day(2026,8,24)).days//7));r.update(score=series[i],previous=series[i-1] if i else None,baseline_only=False);return r
    a.funnel_score=score
    orig_conv=a.conversations_fields
    def conversations(s,jobs):
        projected=fixture_copy.deepcopy(s)
        r=orig_conv(projected,jobs)
        for rows in r['sections'].values():
            for row in rows:row['this_week']=bool(row.get('date') and s['periods']['activity']['start']<=row['date']<=s['periods']['activity']['end'])
        return r
    a.conversations_fields=conversations
    orig_sources=a.source_coverage
    def sources(jobs,today,now=None):
        rows,_=orig_sources(jobs,today,dt.datetime.now(a.local_zone()))
        return rows,a.run_timestamp(today,now).isoformat()
    a.source_coverage=sources
    orig_sc=a.scorecard_fields
    def sc(s,j,h,t):
        r=orig_sc(s,j,h,t)
        for row in r:
            if row['key'] in a.FUNNEL:row['counting']='Fictional preview: observed conversions; wins use decided proposals only.'
        return r
    a.scorecard_fields=sc
    # Recognition projection: event-week instant awards appear in the next Monday review.
    orig_ledger=a.badge_ledger.read_ledger
    def ledger():
        rows=orig_ledger();byid={str(job['id']):job for job in a.pipeline.load()}
        for r in rows:
            if r['badge']=='First Doubloon':
                event=a.event(byid.get(str(r.get('lead_id')),{}),'won')
                if event:
                    d=event.astimezone(a.local_zone()).date();monday=d+dt.timedelta(days=7-d.weekday())
                    r['at']=dt.datetime.combine(monday,dt.time(9),a.local_zone()).isoformat()
        return rows
    a.badge_ledger.read_ledger=ledger
    orig_badges=a.badge_results
    def badges(s,j,h,t):
        s.pop('badge_qualifying',None)
        return orig_badges(s,j,h,t)
    a.badge_results=badges
    orig_cards=a.goal_cards
    def cards(s):
        rows=orig_cards(s)
        for r in rows:
            if r['kpi']=='call_review':r.update(execution_unit='calls',measurement='Check each call transcript: budget before price. Review on '+r['review_on']+'.')
        return rows
    a.goal_cards=cards
    (OUT/'context/me.md').write_text('Name and location: Daniel K., Lisbon\n\n## Weekly goal\n20\n\n## Analytics day\nMonday\n\n## Working hours\nMon-Fri 09:00-18:00 Europe/Lisbon\n\n## Services\nWebflow and Framer marketing websites for B2B SaaS and agencies; $65/h or $2,500-$6,000 fixed.\n\nFictional preview account. No real-account claims.\n')
    (OUT/'data/example-mode.json').write_text(json.dumps({'member':'Daniel K.','basis':'Fictional observed conversions, 28-day window','score':'Illustrative coaching score','preview_only':True}))
    def stamp(d,h=10,m=0):return dt.datetime.combine(d,dt.time(h,m),dt.timezone(dt.timedelta(hours=1))).isoformat()
    def ev(r,key,d,h=10,m=0):
        r[key+'_at']=stamp(d,h,m);r[key+'_observation']={'source':'member','verified':True}
        if key=='call_booked':r[key+'_observation']['kind']='booking-confirmed'
    names=['Beatrice','Celeste','Dominic','Elodie','Felicity','Gabriel','Henrietta','Imogen','Joachim','Katarina','Leonora','Meredith','Nikolai','Octavia','Penelope','Quentin','Rosalie','Sebastian','Tabitha','Viola']
    titles=['Webflow pricing page for a workflow SaaS','Framer launch site for a research agency','Webflow demo funnel for a logistics SaaS','Framer case-study library for a brand agency','Webflow migration for an invoicing SaaS','Framer positioning site for a strategy agency','Webflow integrations pages for a data SaaS','Framer service pages for a content agency','Webflow CMS for a scheduling SaaS','Framer landing page for a design agency','Webflow conversion rebuild for a reporting SaaS','Framer lead capture for a growth agency','Webflow resource hub for a procurement SaaS','Framer mobile rebuild for a creative agency','Webflow product tour for a support SaaS','Framer offer page for a video agency','Webflow localization for a planning SaaS','Framer accessibility refresh for an insights agency','Webflow comparison pages for a security SaaS','Framer homepage for a partnership agency']
    problems=['Visitors miss the pricing comparison','The launch story buries the buyer benefit','Demo requests fall on mobile','Case studies lack a clear next step','The CMS migration must retain URLs']
    rows=[]
    for w in range(8):
        start=day(2026,8,17)+dt.timedelta(weeks=w);n=20 if w==7 else 23 if w in (4,5) else 25;reply_n=3 if w<4 else 5
        for i in range(n):
            d=start+dt.timedelta(days=i%5);jid=str(970000000+w*1000+i);problem=problems[i%5]
            r={'id':jid,'source':'outbound','title':titles[i%20],'client':{'name':names[i%20]},'status':'lost','found_at':stamp(d,9,55),'last_activity_at':stamp(d),'history':[],'application_sent_verified':True,'application_facts':{'source':'outbound','posted_age_band':'<10m','proposals_band':'<5','lane':'Webflow and Framer marketing websites','connects_cost':12},'log':[{'at':stamp(d),'text':'analytics job_fit: '+json.dumps({'state':'pass','reason':'B2B SaaS or agency marketing website within Daniel’s service and $65/h rate.'})}]}
            ev(r,'applied',d)
            if i<reply_n:ev(r,'replied',d,11);r.update(first_reply_at=stamp(d,11,4 if w==7 else 20),first_reply_s=240 if w==7 else 1200)
            rows.append(r)
    # Three steady bookings per week; one historical attendance dip.
    for w in range(7):
        batch=[r for r in rows if int(r['id'])//1000==(970000000+w*1000)//1000 and r.get('replied_at')]
        for i,r in enumerate(batch[:3]):
            d=dt.date.fromisoformat(r['replied_at'][:10]);ev(r,'call_booked',d,12);r['call_scheduled_at']=stamp(d+dt.timedelta(days=1),14)
            if not(w==4 and i==2):ev(r,'call_held',d+dt.timedelta(days=1),14);ev(r,'call_ended',d+dt.timedelta(days=1),14,30)
            else:r['call_no_show']=True
    # Final five calls on older applications, distinct from the five current chats.
    callrows=[r for r in rows if r['id'] in ['970005003','970005004','970006003','970006004','970004003']]
    for i,r in enumerate(callrows):
        r['client']['name']=['Beatrice','Celeste','Dominic','Elodie','Felicity'][i]
        r['title']=['Webflow pricing rebuild for a workflow SaaS','Framer launch website for a creative agency','Webflow mobile demo flow for a reporting SaaS','Webflow resource hub for a procurement SaaS','Framer website scope for a growth agency'][i]
        r['price_estimate']=[2500,3800,5200,4200,3500][i]
        d=day(2026,10,5)+dt.timedelta(days=i);ev(r,'call_booked',day(2026,10,4) if i<2 else d-dt.timedelta(days=1),12);ev(r,'call_held',d,14);ev(r,'call_ended',d,14,30);r['call_scheduled_at']=stamp(d,14)
        r['status']='offer' if i<3 else 'won' if i==3 else 'call'
        if i<3:ev(r,'proposal_sent',d,15,0);r['proposal_required']=True;r['call_outcome']='proposal_required'
        if i==3:ev(r,'won',day(2026,10,8));r.update(contract_id='fictional-'+r['id'],won_value={'type':'fixed','amount':4200,'currency':'USD','start_date':day(2026,10,8).isoformat()},call_outcome='direct_win',proposal_required=False)
    # Second won contract, no current proposal; exactly two wins and $7,800.
    r=next(r for r in rows if r['id']=='970004004');ev(r,'proposal_sent',day(2026,9,18));ev(r,'won',day(2026,10,9));r.update(status='won',contract_id='fictional-'+r['id'],won_value={'type':'fixed','amount':3600,'currency':'USD','start_date':day(2026,10,9).isoformat()})
    for r in rows:
        if r['applied_at'][:10]>=day(2026,10,5).isoformat() and r.get('replied_at'):r['status']='replied';r['price_estimate']=3200
    run('pipeline.py','add','--file','-',value=rows)
    for r in rows:
        folder=OUT/'jobs'/r['id'];folder.mkdir(exist_ok=True)
        (folder/'job.md').write_text(f"# {r['title']}\nFictional brief: {problems[int(r['id'])%5]}. B2B SaaS or agency marketing site. Budget $2,500-$6,000 or $65/h.\n")
        (folder/'source.md').write_text('Source: local fictional fixture; no marketplace request or outgoing action.\n')

        if r.get('replied_at'):
            current=r['replied_at'][:10]>=day(2026,10,5).isoformat();i=int(r['id'])%1000
            client=['Could we edit the CMS without a developer?','How would you preserve our old URLs?','Will the pricing toggle work on a phone?','Which pages would you prioritize for our launch?','I am ready to approve this scope without a call.'][i%5]
            own=['Yes, I will use native collections and document the fields.','I will map every old URL and test its redirect.','Yes. I would build an accessible toggle and test it at 390px. Shall we review it Tuesday 10:00 or Wednesday 15:00 Lisbon time?','Which buyer segment must understand the offer first? Tuesday 10:00 or Wednesday 15:00 Lisbon time?','Agreed: $3,200 fixed for the three launch pages. Please confirm the scope here before sending the offer.'][i%5] if current else 'I will map the CMS fields first. Tuesday 10:00 or Wednesday 15:00 Lisbon time?'
            run('sync.py','apply','--file','-',value={'threads':[{'job_id':r['id'],'room_id':'fictional-'+r['id'],'messages_complete':True,'messages':[{'from':'client','at':r['replied_at'],'text':client},{'from':'me','at':r['first_reply_at'],'text':own}]}]})
            if current:
                run('sync.py','apply','--file','-',value={'threads':[{'job_id':r['id'],'room_id':'fictional-scope-'+r['id'],'messages_complete':True,'messages':[{'from':'client','at':stamp(dt.date.fromisoformat(r['replied_at'][:10]),13),'text':'Can our content owner edit the page headings after handover?'},{'from':'me','at':stamp(dt.date.fromisoformat(r['replied_at'][:10]),13,4),'text':'Yes. Native editable heading fields and a short handover will cover that.'}]}]})
            pts={key:{'state':'met','quote':own,'reason':f'{names[i%20]}: '+['Answer the CMS ownership question directly','Explain the redirect check before discussing schedule','Answer the mobile interaction question with a concrete test','Qualify the priority buyer before choosing page order','Confirm written terms when the client declines a call'][i%5]} for key in a.CONVERSATION_POINTS}
            if current and i<2:pts['call_times'].update(state='missing',reason='Agree one clear next action (5 quoted cases across four stages)')
            if current and i in (0,1,2):pts['qualifying_question'].update(state='missing',reason='Ask which buyer decision this page must support')
            if current and i==4:pts['qualifying_question'].update(state='not_needed',reason='The client already confirms the scope and direct approval route')
            if current and i==4:pts['call_times'].update(state='not_needed',reason='Client explicitly chooses written scope approval without a call')
            run('pipeline.py','record',r['id'],'--file','-',value={'conversation_review':{'read':True,'last_writer':'me','free_read':f'{names[i%20]} asks: {client} '+(['You answered the substance but left the next action open. Offer two useful times after this answer.','Keep the direct technical answer and tie the invitation to one decision.','The mobile test answers the actual question and makes the meeting useful.','The buyer question qualifies the page hierarchy instead of adding generic discovery.','A call is not needed because the client chooses written approval. Check terms before the offer.'][i%5]),'next_message':own if i>=2 else 'Would Tuesday 10:00 or Wednesday 15:00 Lisbon time work for a 15-minute scope review?','points':pts}})
    reads=[
    "Beatrice explains that buyers abandon the pricing comparison because they cannot see which plan covers their team. You established the current page and the desired decision before suggesting a layout. The strongest moment was asking what the lost demo requests cost; that made the comparison grid a business decision rather than a visual preference. Budget came before your price, so keep that order. The proof was relevant because it showed a similar plan comparison, although the transcript does not establish a measured conversion uplift. Your objection invitation was brief and could have tested whether the CMS handover worried the client. The next step is specific: you send a fixed proposal by 15:00 and Beatrice reviews it Thursday. Keep that agreement in the message rather than promising a build date. In the next call, ask one follow-up about who maintains the pricing table before you close.",
    "Celeste needs a launch page that explains the agency offer before visitors reach the case studies. You gave the call a useful agenda and checked which buyer segment matters first. The launch deadline was clear, but its business cost stayed vague; ask what happens if the existing page remains in place for another month. You quoted a price before establishing the available budget. That creates an avoidable second negotiation even though the scope sounds plausible. Your portfolio example matched the agency context, which is more useful than a tour of unrelated work. Celeste raised an editing concern and you answered it with native CMS training, so retain that concrete response. The agreement is to send the fixed scope today and let Celeste decide Friday. Your next message should repeat training and the review checkpoint, then ask the unanswered budget question. Do not add extra pages or a delivery promise that the call did not settle.",
    "Dominic describes mobile visitors losing the demo action when they use the product comparison. You connected that behavior to the immediate launch goal and asked which interaction must work first. That gave the proposal a practical boundary: demo flow, mobile QA and event mapping. Budget was confirmed before price, which kept the number tied to the agreed scope. The proof needs tightening: a responsive page alone does not show that a complex toggle works with keyboard and touch input. Ask for the relevant interaction example on your next call. You invited concerns, but the client response was brief and you moved on without checking the approval process. The agreed step is a proposal today; no decision date was set. Preserve that distinction in the follow-up. Ask Dominic who signs off and when they can review the proposal, rather than assuming launch urgency means immediate approval or promising results from a page that has not been built.",
    "Elodie is ready to choose a compact resource site and prefers to approve the agreement directly. You checked the content owner and made the CMS handover part of the scope. The call covered the present workflow and the desired result, but the cost of manual updates was only touched on; one concrete weekly time estimate would have strengthened the value discussion. Price arrived before a budget question, so that sequence remains the main correction even though the client accepted the terms. Your example showed editable resource categories and answered the actual maintenance concern. Elodie is the decision maker, which removes the need for a separate approval meeting. The next step is a fixed client offer for the agreed pages and handover, confirmed in the platform thread today. Keep the message focused on checking those terms. Do not send a second proposal or add a call merely to follow a routine when the client has already chosen the direct route."
    ]
    for idx,r in enumerate(callrows):
        folder=OUT/'jobs'/r['id']
        if idx==4:
            run('pipeline.py','record',r['id'],'--file','-',value={'call_review':{'reviewable':False,'points':[]}});continue
        person=['Beatrice','Celeste','Dominic','Elodie'][idx]
        utterances=[f'00:00 Daniel: Let us confirm the website goal, the scope and the next step in fifteen minutes.',f'01:10 {person}: '+['Buyers cannot compare the plans on our pricing page.','Our agency launch page buries the buyer benefit.','On mobile the comparison toggle hides the demo action.','We need editable resource categories without manual updates.'][idx],f'03:20 {person}: '+['We lose demo requests because teams cannot find the right plan.','The launch is this month; we have not measured the cost of waiting.','We lose mobile demo requests and spend five hours explaining the product.','Manual updates take time, but we have not measured the weekly total.'][idx],f'05:10 Daniel: '+['The scope is the pricing page, comparison grid and CMS handover.','The scope is the launch homepage, two case studies and CMS training.','The scope is the demo flow, mobile QA and event mapping.','The scope is the resource pages and CMS handover.'][idx],f'07:00 {person}: The available budget is $4,000.' if idx%2==0 else f'07:00 Daniel: My price is $4,200; we have not discussed your budget yet.',f'09:00 {person}: I approve the work myself and want to review it this week.',f'11:00 Daniel: '+['This editable comparison example addresses your maintenance concern.','This native CMS case-study example shows how your team can update pages.','This responsive example shows the layout, but not the keyboard toggle.','This resource category example shows editable labels and filters.'][idx],f'12:00 Daniel: What would stop you from choosing this scope?',f'14:00 {person}: Yes, send the fixed proposal by 15:00 today; I will review it '+('Thursday.' if idx==0 else 'Friday.' if idx==1 else 'when I have time.' if idx==2 else 'as a direct client offer today.')]
        utterances=[re.sub(r'^(\d\d:\d\d) ([^:]+): ',r'\2: [\1] ',u) for u in utterances]
        transcript='Member: Daniel\nComplete: yes\nLanguage: English\nCall at: '+r['call_held_at']+'\nDuration: 900\n'+'\n'.join(utterances)+'\n'
        (folder/'call.md').write_text(transcript)
        # Quotes are complete verbatim speech excerpts, including timestamps.
        points=[]
        states=[['met','met','met','met','met','not needed','met','partly','met'],['met','met','partly','met','missing','met','met','met','met'],['met','met','met','met','met','partly','partly','met','missing'],['met','met','partly','met','missing','not needed','met','met','met']][idx]
        for p,state in enumerate(states):
            reason=['Keep the agenda connected to the buyer decision','Current site evidence is concrete','Quantify the cost of the current problem','The page boundary is agreed','Confirm budget before quoting the fixed price','The approving client is present','Match proof to the stated buying concern','Invite and explore the actual objection','Ask one easy question before asking for a call'][p]
            reason=('Agree one clear next action (5 quoted cases across four stages)' if idx==2 and p==8 else person+': '+reason)
            points.append({'point':p+1,'state':state,'quote':utterances[p].split(': ',1)[1],'reason':reason})
        agreed=f'Daniel sends the fixed '+('client offer terms' if idx==3 else 'proposal')+' by 15:00 today; '+person+' agreed to '+('approve the direct offer today.' if idx==3 else 'review Thursday.' if idx==0 else 'review Friday.' if idx==1 else 'review, but gave no decision date.')
        review={'reviewable':True,'points':points,'moments':[{'quote':utterances[4].split(': ',1)[1],'better_wording':'Before I quote, what budget range should this scope fit?'}],'fix':['Explore the editing objection','Budget before price','Agree the decision date','Budget before price'][idx],'example':'Before I quote, what budget range should this scope fit?','free_read':reads[idx],'next_message':['Here is the pricing-page scope we agreed. You will review Thursday. Is there any concern about editing the comparison table that I should resolve first?','Here is the launch scope including CMS training. You will review Friday. Before we settle the price, what budget range has been approved?',f'Here is the demo-flow scope we agreed. Who signs off, and can we agree {when(2026,10,12)} as the decision date?','Please confirm the fixed offer covers the resource pages and CMS handover we discussed. Once those terms match, you can approve directly here.'][idx],'agreed_step':agreed,'next_step':agreed}
        (folder/'call-review.md').write_text('## Coach’s read\n'+reads[idx]+'\n\n## Agreed step\n'+agreed+'\n\n## Next message\n'+review['next_message']+'\n')
        run('pipeline.py','record',r['id'],'--file','-',value={'call_review':review})
    run('sync.py','apply','--file','-',value={'connects':[{'at':r['applied_at'],'amount':-12,'reason':'Fictional application debit','job_id':r['id']} for r in rows],'earnings':[{'week_start':day(2026,10,5).isoformat(),'contract_id':'fictional-billing','billed':0,'currency':'USD'}]})
    # Historical source coverage: full labelled fictional transcripts, no invented coaching.
    for r in rows:
        if r.get('call_held_at') and r not in callrows:
            folder=OUT/'jobs'/r['id'];person=r['client']['name']
            (folder/'call.md').write_text('Member: Daniel\nComplete: yes\nLanguage: English\nDuration: 900\nCall at: '+r['call_held_at']+'\nDaniel: [00:00] Let us confirm the website goal and the buyer decision.\n'+person+': [02:00] '+problems[int(r['id'])%5]+'.\nDaniel: [04:00] Which page is the priority for launch?\n'+person+': [06:00] The homepage and CMS handover come first.\nDaniel: [08:00] What budget range should the work fit?\n'+person+': [09:00] We have $4,000 available for the agreed pages.\nDaniel: [11:00] I will show one relevant editable page example.\n'+person+': [13:00] Please send the scope for review before Friday.\nDaniel: [14:00] I will confirm the scope in the thread today.\n')
    # Historical and final weekly snapshots# Snapshots use the same validators and writers.
    for w in range(8):
        today=day(2026,8,24)+dt.timedelta(weeks=w)
        # The sync writer records freshness; adapter avoids writing fabricated sync JSON.
        run('sync.py','apply','--file','-',value={})
        value=a.compute(today)
        focus=value['verdict'].get('kpi');keys=['reply_to_call','first_reply','speed_10min'] if w==6 else ['reply_to_call','call_review','proposal_to_won']
        keys=([focus]+[k for k in keys if k!=focus])[:3] if focus else keys
        actions={'reply_to_call':('Offer two useful times','When the client shows interest','Answer the real question, then offer two useful call times','call-times'),'first_reply':('Answer promptly','When a client asks a question','Answer the client within five working minutes','first-answer'),'speed_10min':('Apply after fit check','When a fitting website brief appears','Check fit and send the tailored application within ten minutes','speed-qualified'),'call_review':('Budget before price','Before quoting a website price','Confirm scope and budget before naming the price','call-budget'),'proposal_to_won':('Decision checkpoint','When sending the scope','Confirm the decision owner and review date','proposal-decision')}
        for k in keys:actions.setdefault(k,('Keep the routine','When this stage starts','Use the agreed next step','' ))
        value['goals_next']=[dict(stage=a.LABELS[k],kpi=k,change=actions[k][0],start=today.isoformat(),cue=actions[k][1],action=actions[k][2],fallback='Resolve one blocking question in the platform thread',review_on=(today+dt.timedelta(days=7)).isoformat(),primary=i==0,**({'goal_library_id':actions[k][3]} if actions[k][3] else {})) for i,k in enumerate(keys)]
        value['community_card']['next_focus']=value['verdict']['stage']
        value['report']=f"Funnel Score {series[w]}. Daniel’s fictional website practice is reviewed for the preceding Monday through Sunday. The priority is to turn interested replies into an agreed next step. Confirm the page scope, budget and decision checkpoint. This is a local demonstration with no real-account claims."
        selected=[r for r in rows if a.inside(a.event(r,'applied'),a.span(today,7))]
        examples={'conversation':('reply_to_call','Would Tuesday 10:00 or Wednesday 15:00 Lisbon time work for a 15-minute scope review?'),'call':('call_review','Before I quote, what budget range should this scope fit?')}
        jobs=a.pipeline.load()
        for kind,(key,example) in examples.items():
            eventname={'conversation':'replied','call':'call_held'}[kind]
            ids=[r['id'] for r in rows if a.inside(a.event(r,eventname),a.span(today,7)) and (kind!='call' or next(j for j in jobs if j['id']==r['id']).get('call_review',{}).get('reviewable'))]
            review=value['reviews'][kind];review.update(fix={'conversation':'Offer two useful times after answering','call':'Confirm budget before price'}[kind],example=example,evidence_lead_ids=ids,goal_ref=key if key in keys else None)
            if kind=='call':review.pop('coverage',None);review['rubric']=[dict(next(j for j in jobs if j['id']==jid)['call_review'],lead_id=jid) for jid in ids]
        for g in value['goals_review']:
            ids=[r['id'] for r in selected if r.get('replied_at')] if g['kpi']=='first_reply' else [r['id'] for r in selected] if g['kpi']=='speed_10min' else [r['id'] for r in selected if r.get('replied_at')]
            g.update(evidence_lead_ids=ids,done_lead_ids=ids if g['kpi'] in ('first_reply','speed_10min') else ids[2:],decision='keep' if g['effect']=='worked' else 'adjust')
        value=a.prepare_snapshot(value,today)
        a.add_goals({'week':value['week'],'goals':value['goals_next']})
        value=a.prepare_snapshot(value,today)
        a.record_snapshot(value)
    return a.last()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=4370)
    ap.add_argument('--no-serve', action='store_true', help='only build the data and print the folder')
    ap.add_argument('--today', type=dt.date.fromisoformat, help='build as if run on this date (YYYY-MM-DD), for testing')
    args = ap.parse_args()
    out = pathlib.Path(tempfile.mkdtemp(prefix='analytics-example-'))
    paths = dict(BLUEPRINT_ROOT=str(ROOT), BLUEPRINT_DATA=str(out / 'data'), BLUEPRINT_JOBS=str(out / 'data/jobs.json'),
                 BLUEPRINT_JOBDIR=str(out / 'jobs'), BLUEPRINT_CONTEXT=str(out / 'context'), BLUEPRINT_EXAMPLE_DATA='1')
    serve_env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **paths)
    os.environ.update(paths, PYTHONDONTWRITEBYTECODE='1', TZ='Europe/Lisbon')
    time.tzset()
    build(out, args.today)
    print(f'Example data: {out}', flush=True)
    if args.no_serve:
        return 0
    print(f'Starting the cockpit. Open http://127.0.0.1:{args.port}/analytics', flush=True)
    try:
        return subprocess.run([sys.executable, 'code/cockpit.py', '--port', str(args.port), '--no-open'],
                              cwd=ROOT, env=serve_env).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
