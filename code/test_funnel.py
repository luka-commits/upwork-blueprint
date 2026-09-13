"""Functional acceptance tests for the conversation-to-delivery helper."""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parent
FUNNEL = CODE / 'funnel.py'
PIPELINE = CODE / 'pipeline.py'


class FunnelAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.jobs = root / 'jobs.json'
        self.jobdir = root / 'jobfiles'
        self.data = root / 'data'
        self.context = root / 'context'
        self.context.mkdir()
        (self.context / 'me.md').write_text('**Applications per day:** 5\n', encoding='utf-8')
        self.env = dict(os.environ, BLUEPRINT_JOBS=str(self.jobs),
                        BLUEPRINT_JOBDIR=str(self.jobdir), BLUEPRINT_DATA=str(self.data),
                        BLUEPRINT_CONTEXT=str(self.context))
        self.run_pipeline('add', '--file', '-', stdin=json.dumps({
            'id': '111111', 'title': 'Build the sales system', 'score': 84,
        }))
        self.run_pipeline('set', '111111', 'applied', '--applied-at', '2026-09-12T09:00:00+00:00')
        self.run_pipeline('set', '111111', 'replied', '--follow-up', '2026-09-12')
        # A later manual correction may revisit applied. Daily activity still
        # counts the first application once, never every repeated history event.
        self.run_pipeline('set', '111111', 'applied')
        self.run_pipeline('set', '111111', 'replied', '--follow-up', '2026-09-12')
        self.run_pipeline('task', '111111', 'add', 'Confirm access', '--due', '2026-09-12')
        folder = self.jobdir / '111111'
        folder.mkdir(parents=True)
        (folder / 'thread.json').write_text(json.dumps({
            'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'room_id': 'room-1', 'awaiting_reply_from': 'you',
            'messages': [{'from': 'client', 'kind': 'message', 'text': 'Can we talk tomorrow?',
                          'at': '2026-09-12T09:00:00+00:00'}],
        }), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def run_pipeline(self, *args, stdin=None):
        result = subprocess.run([sys.executable, str(PIPELINE), *args], input=stdin,
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def run_funnel(self, *args):
        return subprocess.run([sys.executable, str(FUNNEL), *args],
                              capture_output=True, text=True, env=self.env)

    def test_inbox_ranks_a_waiting_client_and_gives_the_real_next_command(self):
        result = self.run_funnel('inbox', '--today', '2026-09-12')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('the client is waiting for you', result.stdout)
        self.assertIn('Can we talk tomorrow?', result.stdout)
        self.assertIn('/reply 111111', result.stdout)

    def test_status_writes_a_readable_report_from_pipeline_evidence(self):
        self.run_pipeline('add', '--file', '-', stdin=json.dumps({
            'id': '222222', 'title': 'Not a fit after review', 'score': 30,
        }))
        self.run_pipeline('set', '222222', 'skipped', '--note', 'not a fit')
        target = self.data / 'status.md'
        result = self.run_funnel('status', '--today', '2026-09-12', '--write', str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = target.read_text(encoding='utf-8')
        self.assertIn('1 of 5 applications sent today', text)
        self.assertIn('1 client waiting', text)
        self.assertIn('Saved pipeline history', text)
        self.assertIn('- Found: 2', text)
        self.assertIn('- Replied: 1', text)
        self.assertIn('Reply to Build the sales system', text)

    def test_call_and_loom_transcripts_are_checked_without_copying_them(self):
        transcript = pathlib.Path(self.tmp.name) / 'call.txt'
        transcript.write_text(' '.join(['useful'] * 80), encoding='utf-8')
        for kind in ('call', 'loom'):
            result = self.run_funnel('transcript', kind, '111111', str(transcript))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('80 words', result.stdout)
        self.assertEqual(sorted(p.name for p in self.jobdir.joinpath('111111').iterdir()), ['thread.json'])

    def test_loom_transcript_can_be_created_from_the_saved_video(self):
        self.run_pipeline('video', '111111', 'https://www.loom.com/share/example')
        tools = pathlib.Path(self.tmp.name) / 'tools'
        tools.mkdir()
        downloader = tools / 'yt-dlp'
        downloader.write_text(
            '#!/usr/bin/env python3\n'
            'import pathlib, sys\n'
            'template = sys.argv[sys.argv.index("--output") + 1]\n'
            'pathlib.Path(template.replace("%(ext)s", "wav")).write_bytes(b"audio")\n',
            encoding='utf-8')
        whisper = tools / 'whisper'
        whisper.write_text(
            '#!/usr/bin/env python3\n'
            'import pathlib, sys\n'
            'folder = pathlib.Path(sys.argv[sys.argv.index("--output_dir") + 1])\n'
            '(folder / "source.txt").write_text(" ".join(["recorded"] * 80), encoding="utf-8")\n',
            encoding='utf-8')
        downloader.chmod(0o755)
        whisper.chmod(0o755)
        self.env['PATH'] = f'{tools}{os.pathsep}{self.env.get("PATH", "")}'

        result = self.run_funnel('transcript', 'loom', '111111')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('80 words', result.stdout)
        self.assertIn('jobs/111111/.loom-transcript.txt', result.stdout)
        saved = self.jobdir / '111111' / '.loom-transcript.txt'
        self.assertEqual(len(saved.read_text(encoding='utf-8').split()), 80)

    def test_every_funnel_artifact_contract_accepts_a_complete_fixture(self):
        folder = self.jobdir / '111111'
        for kind, (name, headings) in self.artifact_specs().items():
            sections = [f'{heading}\n\n' + ('84/100' if heading == '## Score' else 'A concrete recorded fact.')
                        for heading in headings]
            text = '\n'.join([
                f'# {kind.replace("-", " ").title()}',
                'Prepared Saturday 12 September 2026 from verified project evidence.',
                '**Next:** review this with the client on Upwork.',
                '',
                *sections,
                '',
            ])
            (folder / name).write_text(text, encoding='utf-8')
            result = self.run_funnel('check', kind, '111111')
            self.assertEqual(result.returncode, 0, f'{kind}: {result.stderr}')

    def test_artifact_gate_rejects_placeholders_and_missing_sections(self):
        (self.jobdir / '111111' / 'proposal.md').write_text(
            '# Proposal\nPrepared today.\n**Next:** review.\n\n## Outcome\n\nTBD', encoding='utf-8')
        result = self.run_funnel('check', 'proposal', '111111')
        self.assertEqual(result.returncode, 1)
        self.assertIn('contains a placeholder', result.stderr)
        self.assertIn('missing section: ## Scope', result.stderr)

    def test_artifact_gate_rejects_an_empty_required_section(self):
        headings = self.artifact_specs()['call-prep'][1]
        text = '\n'.join([
            '# Call prep',
            'Prepared Saturday 12 September 2026 from verified evidence.',
            '**Next:** use this during the call.',
            '',
            *[f'{heading}\n' + ('' if heading == '## Boundaries' else '\nA concrete fact.') for heading in headings],
        ])
        (self.jobdir / '111111' / 'call-prep.md').write_text(text, encoding='utf-8')
        result = self.run_funnel('check', 'call-prep', '111111')
        self.assertEqual(result.returncode, 1)
        self.assertIn('empty section: ## Boundaries', result.stderr)

    def test_loom_review_requires_a_bounded_numeric_score(self):
        headings = self.artifact_specs()['loom-review'][1]
        sections = [f'{heading}\n\n' + ('Excellent' if heading == '## Score' else 'A concrete finding.')
                    for heading in headings]
        (self.jobdir / '111111' / 'loom-review.md').write_text('\n'.join([
            '# Loom review', 'Reviewed today.', '**Next:** fix the recording.', '', *sections,
        ]), encoding='utf-8')
        result = self.run_funnel('check', 'loom-review', '111111')
        self.assertEqual(result.returncode, 1)
        self.assertIn('N/100', result.stderr)

    @staticmethod
    def artifact_specs():
        return {
            'call-prep': ('call-prep.md', ('## Decision', '## Goal for this call', '## What we know',
                                           '## Questions to ask', '## Proof to use', '## Boundaries', '## Close')),
            'call-review': ('call-review.md', ('## Verdict', '## Client need', '## Agreed scope',
                                               '## Evidence and assumptions', '## Commitments', '## Risks', '## Next step')),
            'loom-review': ('loom-review.md', ('## Score', '## Verdict', '## Message', '## Accuracy', '## Structure',
                                               '## Delivery', '## Fix before sending')),
            'proposal': ('proposal.md', ('## Outcome', '## Scope', '## Not included', '## Milestones',
                                         '## Timing', '## Price and payment', '## Client inputs',
                                         '## Acceptance', '## Next step')),
            'project': ('project.md', ('## Contract baseline', '## Outcome', '## Scope', '## Client inputs',
                                       '## Milestones', '## Communication', '## First actions')),
            'delivery': ('delivery.md', ('## Delivered', '## Evidence', '## Client action', '## Open items',
                                         '## Next check-in')),
            'handover': ('client-handover.md', ('## Delivered', '## Access and ownership', '## How to use it',
                                                '## Known limits', '## Support boundary', '## Acceptance', '## Next step')),
            'review-request': ('review-request.md', ('## What was completed', '## Result', '## Draft request')),
        }


if __name__ == '__main__':
    unittest.main()
