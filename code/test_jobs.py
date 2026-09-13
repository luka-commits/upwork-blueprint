"""Tests for code/jobs.py, on fictional jobs. Never touch the real pipeline.

    python3 -m unittest discover -s code -p 'test_*.py'
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
JOBS = CODE / 'jobs.py'


def iso(hours_ago):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)).isoformat()


def job(id_, hours_ago, **kw):
    base = {'id': id_, 'title': f'Job {id_}', 'url': f'https://www.upwork.com/jobs/~02{id_}',
            'created_date': iso(hours_ago), 'budget': '$500.00', 'job_type': 'fixed',
            'description_snippet': '<untrusted_participant_content>\nBuild a CRM\n</untrusted_participant_content>',
            'client': {'rating': 4.9, 'total_reviews': 20, 'total_spent': '$25,000.00',
                       'verification_status': 'VERIFIED', 'country': 'United States'}}
    base.update(kw)
    return base


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        (self.dir / 'search').mkdir()
        self.me = self.dir / 'me.md'
        self.me.write_text('# Member\n\n## Job search tracks\n\n- GoHighLevel\n- n8n\n', encoding='utf-8')
        self.env = dict(os.environ, BLUEPRINT_DATA=str(self.dir), BLUEPRINT_JOBS=str(self.dir / 'jobs.json'),
                        BLUEPRINT_ME=str(self.me))

    def tearDown(self):
        self.tmp.cleanup()

    def run_jobs(self, *args):
        return subprocess.run([sys.executable, str(JOBS), *args], capture_output=True, text=True, env=self.env)

    def test_candidates_filter_and_merge(self):
        (self.dir / 'search' / 'title-crm.json').write_text(json.dumps({'jobs': [
            job('1', 2), job('2', 30), job('3', 1, applied=True),
            job('4', 1, client={'verification_status': 'UNVERIFIED'})]}), encoding='utf-8')
        (self.dir / 'search' / 'recommended.json').write_text(json.dumps({'jobs': [job('1', 2)]}), encoding='utf-8')
        r = self.run_jobs('candidates', *map(str, sorted((self.dir / 'search').glob('*.json'))),
                          '--window-hours', '10')
        self.assertEqual(r.returncode, 0, r.stderr)
        cands = json.loads((self.dir / 'candidates.json').read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in cands], ['1'])
        self.assertEqual(sorted(cands[0]['found_via']), ['recommended', 'title-crm'])
        self.assertEqual(cands[0]['snippet'], 'Build a CRM')
        self.assertIn('1 applied', r.stdout)
        self.assertIn('1 outside window', r.stdout)

    def test_rules_explain_the_live_search_and_ranking_contract(self):
        r = self.run_jobs('rules')
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = json.loads(r.stdout)
        self.assertEqual(rules['tracks'], ['GoHighLevel', 'n8n'])
        self.assertEqual(rules['window_hours'], 24)
        self.assertEqual([part['points'] for part in rules['ranking']], [40, 30, 20, 10])
        self.assertEqual(rules['gate'], {'fit': 20, 'score': 50, 'trap_cap': 60})

    def test_score_gates_on_fit_and_logs(self):
        (self.dir / 'search' / 't.json').write_text(json.dumps({'jobs': [job('1', 1), job('2', 1)]}),
                                                    encoding='utf-8')
        self.run_jobs('candidates', str(self.dir / 'search' / 't.json'))
        (self.dir / 'fit.json').write_text(json.dumps({
            '1': {'fit': 35, 'rationale': 'core CRM build'},
            '2': {'fit': 10, 'trap': 'link building'}}), encoding='utf-8')
        r = self.run_jobs('score')
        self.assertEqual(r.returncode, 0, r.stderr)
        logged = json.loads((self.dir / 'jobs.json').read_text(encoding='utf-8'))
        self.assertEqual([j['id'] for j in logged], ['1'])
        self.assertEqual(logged[0]['niche_fit'], 35)
        self.assertEqual(logged[0]['score'], 35 + logged[0]['client_trust'] + logged[0]['deal_quality']
                         + logged[0]['recency'])

    def test_trap_caps_the_score(self):
        (self.dir / 'search' / 't.json').write_text(json.dumps({'jobs': [job('1', 0)]}), encoding='utf-8')
        self.run_jobs('candidates', str(self.dir / 'search' / 't.json'))
        (self.dir / 'fit.json').write_text(json.dumps({'1': {'fit': 30, 'trap': 'full-time role'}}),
                                           encoding='utf-8')
        self.run_jobs('score')
        logged = json.loads((self.dir / 'jobs.json').read_text(encoding='utf-8'))
        self.assertEqual(logged[0]['score'], 60)

    def test_score_refuses_without_fit(self):
        (self.dir / 'search' / 't.json').write_text(json.dumps({'jobs': [job('1', 1)]}), encoding='utf-8')
        self.run_jobs('candidates', str(self.dir / 'search' / 't.json'))
        self.assertEqual(self.run_jobs('score').returncode, 1)

    def test_hiring_progress_does_not_mean_a_multi_hire_job_is_closed(self):
        (self.dir / 'jobs.json').write_text(json.dumps([{'id': '9', 'status': 'new', 'title': 'x',
                                                          'found_at': iso(1)}]), encoding='utf-8')
        get = {'data': {'marketplaceJobPosting': {'activityStat': {'jobActivity': {'totalHired': 1}}},
                        'connects_cost': 16}}
        (self.dir / 'get.json').write_text(json.dumps(get), encoding='utf-8')
        r = self.run_jobs('detail', '9', str(self.dir / 'get.json'))
        self.assertIn('already hired', r.stdout)
        rec = json.loads((self.dir / 'jobs.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(rec['status'], 'new')
        self.assertEqual(rec['details']['connects_cost'], 16)

    def test_cannot_apply_skips_only_new_jobs_not_existing_conversations(self):
        get = self.dir / 'get.json'
        get.write_text(json.dumps({'can_apply': False, 'preferred_qualifications': {'min_job_success_score': 100}}), encoding='utf-8')
        for stage, expected in [('new', 'skipped'), ('replied', 'replied'), ('won', 'won')]:
            (self.dir / 'jobs.json').write_text(json.dumps([{'id': '9', 'status': stage, 'found_at': iso(1)}]), encoding='utf-8')
            self.assertEqual(self.run_jobs('detail', '9', str(get)).returncode, 0)
            self.assertEqual(json.loads((self.dir / 'jobs.json').read_text(encoding='utf-8'))[0]['status'], expected)

    def test_detail_saves_the_structured_job_brief(self):
        (self.dir / 'jobs.json').write_text(json.dumps([{'id': '8', 'status': 'new', 'title': 'x',
                                                          'found_at': iso(1)}]), encoding='utf-8')
        get = {'description': 'Build the complete system.', 'brief': {
            'outcome': 'A working lead system.',
            'scope': ['Build the pipeline.', '', 4, 'Test every route.'],
            'requirements': ['Five years of direct experience.'],
        }}
        (self.dir / 'get.json').write_text(json.dumps(get), encoding='utf-8')
        r = self.run_jobs('detail', '8', str(self.dir / 'get.json'))
        self.assertEqual(r.returncode, 0, r.stderr)
        brief = json.loads((self.dir / 'jobs.json').read_text(encoding='utf-8'))[0]['details']['brief']
        self.assertEqual(brief['outcome'], 'A working lead system.')
        self.assertEqual(brief['scope'], ['Build the pipeline.', 'Test every route.'])

    def test_points(self):
        sys.path.insert(0, str(CODE))
        import jobs
        self.assertEqual(jobs.recency_points(iso(0), 10), 10)
        self.assertIsNone(jobs.recency_points(iso(11), 10))
        self.assertEqual(jobs.trust_points({'verified': True, 'rating': 4.9, 'spent': 20000,
                                            'hires': 10, 'posted_jobs': 12}), 30)
        self.assertLess(jobs.deal_points({'budget': '$20.00/hr', 'job_type': 'hourly',
                                          'engagement': 'FULL_TIME'}, 60), 5)
        self.assertEqual(jobs.deal_points({'budget': '$20.00/hr', 'job_type': 'hourly'}, None), 9)


if __name__ == '__main__':
    unittest.main()
