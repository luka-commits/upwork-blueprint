#!/usr/bin/env python3
"""Eight example weeks through real pipeline/analytics writers in retained temp storage.
No external providers and no writes to the repository's data/ or jobs/.
"""
import argparse
import contextlib
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
from analytics_fixture import analytics_rows, analytics_payload, run
import analytics


def protected_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('data', 'jobs') for p in (ROOT / directory).rglob('*') if p.is_file()}


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
               BLUEPRINT_JOBS=str(folder/'data/jobs.json'), BLUEPRINT_JOBDIR=str(folder/'jobs'), PYTHONDONTWRITEBYTECODE='1')
    for name in ('data', 'jobs', 'context'): (folder/name).mkdir()
    (folder/'context/me.md').write_text('Name: Maya Example\n\n## Weekly goal\n25\n\n## Analytics day\nMonday\n\n## Working hours\nMon-Fri 09:00-18:00 Europe/Berlin\n\nAll events and reviews below are synthetic example data.\n')
    rows = analytics_rows()
    table = ['| Week | Funnel Score | Baseline only | New badges | Earned badges |', '|---|---:|---|---|---|']
    quote = 'Manual checks cost three hours each week.'
    own = 'What outcome would make this worthwhile?'
    with mock.patch.dict(os.environ, env, clear=True):
        for index in range(8):
            start = dt.date(2026, 8, 24) + dt.timedelta(weeks=index)
            today = start + dt.timedelta(days=7)
            new = [row for row in rows if row['found_at'][:10] == start.isoformat()]
            for row in new:
                if row.get('applied_at'):
                    row['speed_to_lead_s'] = 600 if row.get('application_facts', {}).get('posted_age_band') == '<10m' else 1200
                    row['application_sent_verified'] = True
                    row['application_review'] = {'state': 'pass', 'reason': 'Example coach confirms relevant submitted audit copy'}
                path = folder/'jobs'/row['id'];path.mkdir()
                if row.get('applied_at'):
                    (path/'application.sent.md').write_text('EXAMPLE submitted application: I can map your audit gaps and agree a clear scope.\n')
                if row.get('proposal_sent_at'): (path/'proposal.md').write_text('EXAMPLE sent audit scope and agreed next step.\n')
                if row.get('call_held_at'):
                    (path/'call.md').write_text('Member: Maya\nComplete: yes\nLanguage: English\nMaya: '+own+'\nClient: '+quote+'\nMaya: Let us agree the next step.\n')
                    (path/'call-review.md').write_text("## Coach's read\n\nExample review: the client wants fewer manual checks. The stated cost is three hours each week. The question made the desired outcome concrete. Ask who will own the audit inputs. Confirm the review date before sending the scope.\n\n## Nine points\n\nSee the saved nine-point rubric.\n\n## Next step\n\nClient reviews scope on Friday.\n")
            run('pipeline.py', 'add', '--file', '-', value=new)
            run('sync.py', 'apply', '--file', '-', value={'connects': [{'at': row['applied_at'], 'amount': -12, 'reason': 'Example application', 'job_id': row['id']} for row in new if row.get('applied_at')], 'earnings': [{'week_start': start.isoformat(), 'contract_id': 'example-weekly', 'billed': 0, 'currency': 'USD'}]})
            (folder/'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(today).isoformat()}))
            value = analytics_payload(analytics.compute(today))
            call = next(row for row in new if row.get('call_held_at'))
            item = {'lead_id': call['id'], 'reviewable': True, 'points': [{'point': point, 'state': 'met', 'quote': quote} for point in range(1,10)],
                    'moments': [{'quote': quote, 'better_wording': 'Ask how the saved time changes the weekly work.'}],
                    'fix': 'Agree the review date', 'example': own, 'next_step': 'Client reviews scope on Friday'}
            value['reviews']['call'].pop('coverage', None)
            value['reviews']['application'].pop('coverage', None)
            value['reviews']['call'].update(evidence_lead_ids=[call['id']], rubric=[item])
            value['reviews']['application'].update(evidence_lead_ids=[call['id']], rubric=[{'lead_id': call['id'], 'reviewable': True, 'points': [{'point': p, 'state': 'met'} for p in range(1,7)]}])
            value['reviews']['proposal']['evidence_lead_ids']=[call['id']]
            value['summary']=[f"This example week won {value['north_star']['wins']} new contracts.",
                              f"Qualified applications reached {value['kpis']['weekly_volume']['k']} against a commitment of {value['kpis']['weekly_volume']['target']:g}.",
                              'Next, use the agreed next step with each fitting lead.']
            value['report']='EXAMPLE synthetic week. This is isolated replay data, not a real member account.'
            snapshot = analytics.prepare_snapshot(value, today)
            analytics.add_goals({'week': snapshot['week'], 'goals': [dict(goal, start=today.isoformat()) for goal in snapshot['goals_next']]})
            saved = analytics.record_snapshot(snapshot)
            new_badges = ', '.join(row['badge']+' '+row['tier'] for row in saved['badges'] if row['new']) or 'none'
            earned = ', '.join(row['badge']+' '+row['tier'] for row in saved['badges']) or 'none'
            score=saved['funnel_score']
            table.append(f"| {saved['week']} | {score['score']} | {str(score['baseline_only']).lower()} | {new_badges} | {earned} |")
            (folder/f"{saved['week']}.json").write_text(json.dumps(saved, indent=2)+'\n')
        last = analytics.last()
        (folder/'latest.json').write_text(json.dumps(last, indent=2)+'\n')
    assert len((folder/'data/analytics-history.jsonl').read_text().splitlines()) == 8
    assert protected_hashes() == before, 'Repository data or jobs changed.'
    proof = {'root': str(folder), 'environment': {key: env[key] for key in ('BLUEPRINT_CONTEXT','BLUEPRINT_DATA','BLUEPRINT_JOBS','BLUEPRINT_JOBDIR')}, 'week': last['week'], 'call_id': call['id'], 'snapshots': 8, 'protected_files': len(before), 'protected_unchanged': True}
    (folder/'replay-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    (folder/'replay-table.md').write_text('\n'.join(table)+'\n')
    print('\n'.join(table));print(json.dumps(proof, indent=2))


if __name__ == '__main__': main()
