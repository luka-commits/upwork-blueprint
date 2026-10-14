#!/usr/bin/env python3
"""Two chronological weeks with two reviewed cases each through real pipeline/analytics writers.
No external providers and no writes to the repository's data/ or jobs/.
"""
import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import io
import importlib
import json
import os
import pathlib
import sys
import tempfile
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'code')]
from analytics_fixture import analytics_rows, analytics_payload, run, EXAMPLE_CALL_READ, ORIGINAL_RUN
import analytics


DEFERRED = {'badge_refreshes':0, 'click_syncs':0, 'nested_pipeline_dispatches':0}

def isolated_writer(script, *args, value):
    module=importlib.import_module(pathlib.Path(script).stem)
    def local_subprocess(command, **kwargs):
        import subprocess
        if len(command)>1 and pathlib.Path(command[1]).name=='clicks.py':
            DEFERRED['click_syncs']+=1
            return subprocess.CompletedProcess(command,0,'','')
        if len(command)>1 and pathlib.Path(command[1]).name=='pipeline.py':
            DEFERRED['nested_pipeline_dispatches']+=1
            import pipeline
            out,err=io.StringIO(),io.StringIO()
            with mock.patch.object(sys,'stdin',io.StringIO(kwargs.get('input') or '')),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                try:code=pipeline.main(command[2:])
                except SystemExit as error:code=error.code
            return subprocess.CompletedProcess(command,code or 0,out.getvalue(),err.getvalue())
        return ORIGINAL_RUN(command,**kwargs)
    with contextlib.ExitStack() as stack:
        if script=='sync.py':
            stack.enter_context(mock.patch.object(module.subprocess,'run',side_effect=local_subprocess))
        import pipeline
        def defer_badges(*args,**kwargs):DEFERRED['badge_refreshes']+=1
        stack.enter_context(mock.patch.object(pipeline,'check_badges',side_effect=defer_badges))
        stack.enter_context(mock.patch.object(sys,'stdin',io.StringIO(json.dumps(value))))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        result=module.main(list(map(str,args)))
    assert result in (None,0), (script,args,result)


def protected_hashes():
    paths = [p for directory in ('code','data','jobs') for p in (ROOT/directory).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts]
    assert paths and any(p.is_relative_to(ROOT/'code') for p in paths), 'Protected source set is empty'
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def replay_storage(folder):
    folder = pathlib.Path(folder).resolve()
    assert any(folder.is_relative_to(root) for root in (pathlib.Path(tempfile.gettempdir()).resolve(),pathlib.Path('/tmp').resolve())), 'Replay storage must be temporary'
    assert folder not in (pathlib.Path(tempfile.gettempdir()).resolve(),pathlib.Path('/tmp').resolve()) and not folder.is_relative_to(ROOT), 'Replay must not use repository or temp root'
    assert not folder.exists() or not any(folder.iterdir()), 'Replay storage must be empty'
    return folder

def protected_storage_guard():
    before = protected_hashes()
    with tempfile.TemporaryDirectory(prefix='analytics-protection-') as temporary:
        home = pathlib.Path(temporary)
        outside = home/'immutable'; outside.mkdir()
        for directory in ('code','data','jobs'):
            (outside/directory).mkdir()
            (outside/directory/'protected.txt').write_text('immutable '+directory)
        hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in outside.rglob('*') if p.is_file()}
        (home/'escape').symlink_to(ROOT, target_is_directory=True)
        for candidate in (ROOT, home/'escape', home/'escape/../escape', outside, pathlib.Path(tempfile.gettempdir())):
            try: replay_storage(candidate)
            except AssertionError: pass
            else: raise AssertionError(('Escaping/nonempty storage accepted',str(candidate)))
        assert hashes == {path:hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for path in hashes}
    assert protected_hashes() == before
    print(json.dumps({'protected_files':len(before),'isolated_code_data_job_files':len(hashes),'malicious_paths_rejected':5,'protected_unchanged':True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='An empty directory under /tmp; defaults to a retained temp directory.')
    parser.add_argument('--focus', choices=('protection',))
    args = parser.parse_args()
    if args.focus:
        protected_storage_guard(); return
    folder = replay_storage(args.output if args.output else tempfile.mkdtemp(prefix='analytics-two-week-', dir=tempfile.gettempdir()))
    folder.mkdir(exist_ok=True, parents=True)
    before = protected_hashes()
    env = dict(os.environ)
    env.update(BLUEPRINT_CONTEXT=str(folder/'context'), BLUEPRINT_DATA=str(folder/'data'),
               BLUEPRINT_JOBS=str(folder/'data/jobs.json'), BLUEPRINT_JOBDIR=str(folder/'jobs'), PYTHONDONTWRITEBYTECODE='1', BLUEPRINT_EXAMPLE_DATA='1')
    for name in ('data', 'jobs', 'context'): (folder/name).mkdir()
    (folder/'context/me.md').write_text('Name: Maya\n\n## Weekly goal\n25\n\n## Analytics day\nMonday\n\n## Working hours\nMon-Fri 09:00-18:00 Europe/Berlin\n\nAll events and reviews below are illustrative example data.\n')
    rows = analytics_rows()
    table = ['| Week | Funnel Score | Baseline only | New badges | Earned badges |', '|---|---:|---|---|---|']
    job_fit_table = ['| Week | Finished applications | Waiting | Job fit |', '|---|---:|---:|---|']
    quote = 'Manual checks cost three hours each week.'
    own = 'What outcome would make this worthwhile?'
    pattern = 'Confirm the owner before offering a date.'
    snapshots = habit_rows = series_rows = badge_refreshes = 0
    with mock.patch.dict(os.environ, env, clear=True):
        for index in range(2):
            start = dt.date(2026, 8, 24) + dt.timedelta(weeks=index)
            today = start + dt.timedelta(days=7)
            new = [row for row in rows if row['found_at'][:10] == start.isoformat()]
            reviewed = [row['id'] for row in new if row.get('proposal_sent_at') and row.get('applied_at')][:2]
            assert len(reviewed) == 2, reviewed
            quotes = {row['id']:f'Manual checks on page group {i+1} cost three hours each week.' for i,row in enumerate(new)}
            for row in new:
                quote=quotes[row['id']]
                if row.get('applied_at'):
                    row['speed_to_lead_s'] = 600 if row.get('application_facts', {}).get('posted_age_band') == '<10m' else 1200
                    row['application_sent_verified'] = True
                    row['application_review'] = {'state': 'pass', 'reason': 'Example coach confirms relevant submitted audit copy'}
                if row['id'] in reviewed:
                    for kind in ('application', 'proposal'):
                        row[kind+'_review']={'state':'pass','reason':'Example saved content review.','quote':quote,
                            'key_finding':pattern,'pattern_sentence':'the audit input owner was not confirmed.',
                            'better_line':'Who will supply the audit inputs before Friday?',
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
            isolated_writer('pipeline.py', 'add', '--file', '-', value=new)
            rubrics=[]
            for jid in reviewed:
                quote=quotes[jid]
                review={'reviewable':True,'points':[{'point':p,'state':'met','quote':quote,'reason':pattern} for p in range(1,10)],
                    'key_finding':pattern,'pattern_sentence':'the audit input owner was not confirmed.',
                    'better_line':'Who will supply the audit inputs before Friday?',
                    'moments':[{'quote':quote,'better_wording':'Ask how the saved time changes the weekly work.'}],
                    'fix':'Agree the review date','example':own,'next_step':'Client reviews scope on Friday',
                    'next_message':'Who will own the audit inputs before Friday?'}
                isolated_writer('pipeline.py','record',jid,'--file','-',value={'call_review':review})
                rubrics.append(dict(review,lead_id=jid))
                isolated_writer('sync.py','apply','--file','-',value={'threads':[{'job_id':jid,'room_id':'example-'+jid,
                    'messages_complete':True,'messages':[{'from':'client','at':start.isoformat()+'T10:00:00+02:00','text':quote},
                    {'from':'me','at':start.isoformat()+'T10:03:00+02:00','text':own}]}]})
                chat={'read':True,'last_writer':'me','free_read':'The saved example states a cost; the owner remains the next question.',
                    'key_finding':pattern,'pattern_sentence':'the audit input owner was not confirmed.',
                    'better_line':'Who will supply the audit inputs before Friday?',
                    'next_message':'Who will own the audit inputs?',
                    'points':{key:{'state':'met','quote':quote,'reason':pattern} for key in analytics.CONVERSATION_POINTS}}
                isolated_writer('pipeline.py','record',jid,'--file','-',value={'conversation_review':chat})
            isolated_writer('sync.py', 'apply', '--file', '-', value={'connects': [{'at': row['applied_at'], 'amount': -12, 'reason': 'Example application', 'job_id': row['id']} for row in new if row.get('applied_at')], 'earnings': [{'week_start': start.isoformat(), 'contract_id': 'example-weekly', 'billed': 0, 'currency': 'USD'}]})
            import pipeline
            pipeline.check_badges('--all-since',start.isoformat())
            badge_refreshes += 1
            (folder/'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(today).isoformat()}))
            value = analytics_payload(analytics.compute(today), agree=False)
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
            value['report']='Illustrative week from isolated example data.'
            snapshot = analytics.prepare_snapshot(value, today)
            analytics.add_goals({'week': snapshot['week'], 'goals': [dict(goal, start=today.isoformat()) for goal in snapshot['goals_next']]})
            saved = analytics.record_snapshot(snapshot)
            snapshots += 1
            for row in saved['presentation']['scorecard']:
                series_rows += 1
                assert len(row['series']['labels']) == len(row['series']['points']) == 8
                assert all(dt.date.fromisoformat(label).weekday() == 0 for label in row['series']['labels'])
                if row['key'] in analytics.LEVERS:
                    habit_rows += 1
                    raw = saved['kpis'][row['key']]
                    assert row['current_week']['value'] == raw['value']
                    assert row['series']['points'][-1] == raw['value']
                    assert row['change']['comparison_period']['end'] < row['habit_period']['start']
                    if row['current_week']['n'] >= 3:
                        assert row['value'] == raw['value'] and row['period_label'] == 'This week'
                else:
                    assert row['period_label'] == 'Last 28 days'
            assert all(goal.get('goal_id') for goal in analytics.read_lines('goals.jsonl')[-1]['goals'])
            print('PASS replay ' + saved['week'] + ': snapshot recorded through the isolated writer.', flush=True)
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
        assert json.loads(run('analytics.py','last').stdout) == last, 'CLI/direct last parity'
        (folder/'latest.json').write_text(json.dumps(last, indent=2)+'\n')
        counts={stage:sum(row.get('reviewable') is True for row in entries) for stage,entries in last['conversations']['sections'].items()}
        assert all(count>=4 for count in counts.values()), counts
        assert last['conversations']['patterns'], 'The replay must produce a counted, supported cross-stage pattern.'
        for pattern in last['conversations']['patterns']:
            assert isinstance(pattern['k'], int) and 0 < pattern['k'] <= pattern['n']
            assert pattern['better_line'] and len({quote['quote'] for quote in pattern['quotes']})==len(pattern['quotes'])
            assert all(quote['title'] and quote['date'] for quote in pattern['quotes'])
            stages={kind for kind,entries in last['conversations']['sections'].items()
                    if any(entry.get('reviewable') and entry.get('pattern_sentence')=='the audit input owner was not confirmed.' for entry in entries)}
            assert len(stages)>=2
            observations=[entry for kind in stages for entry in last['conversations']['sections'][kind] if entry['reviewable']]
            assert pattern['n']==len(observations)
            assert pattern['k']==sum(entry['key_finding']=='Confirm the owner before offering a date.' for entry in observations)
        assert last['rank_progress'] == analytics.rank_fields(last, analytics.read_lines('analytics-history.jsonl'))
        (folder/'community-card.html').write_text(analytics.public_onepager_html(analytics.snapshot_public_card(last)), encoding='utf-8')
    assert len((folder/'data/analytics-history.jsonl').read_text().splitlines()) == snapshots == 2
    assert (habit_rows, series_rows, badge_refreshes) == (10, 26, 2)
    assert protected_hashes() == before, 'Repository data or jobs changed.'
    proof = {'root': str(folder), 'environment': {key: env[key] for key in ('BLUEPRINT_CONTEXT','BLUEPRINT_DATA','BLUEPRINT_JOBS','BLUEPRINT_JOBDIR')}, 'week': last['week'], 'call_id': call['id'], 'snapshots': snapshots, 'weekly_habit_rows_checked':habit_rows, 'series_rows_checked':series_rows, 'reviewable_entries':counts, 'reviewed_cases_per_week':2,'cross_stage_patterns':len(last['conversations']['patterns']), 'protected_files': len(before), 'protected_unchanged': True, 'deferred_incidental_work':DEFERRED, 'actual_badge_refreshes':badge_refreshes}
    (folder/'replay-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    (folder/'replay-table.md').write_text('\n'.join(table)+'\n')
    (folder/'job-fit-table.md').write_text('\n'.join(job_fit_table)+'\n')
    print('\n'.join(table));print('\n'.join(job_fit_table));print(json.dumps(proof, indent=2))


if __name__ == '__main__': main()
