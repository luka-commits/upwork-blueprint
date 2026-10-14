#!/usr/bin/env python3
"""Offline client handover fixtures with local git clones and disposable pipeline files."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client_workspace as workspace

REAL_RUN = subprocess.run
REGISTRY = {name: dict(value) for name, value in workspace.BLUEPRINTS.items()}


class ClientWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / 'upwork'
        (self.repo / 'context').mkdir(parents=True)
        self.me = self.repo / 'context' / 'me.md'
        self.me.write_text('## How you work\n**Clients folder:** not answered yet\n', encoding='utf-8')
        self.jobs = self.base / 'jobs'
        self.data = self.base / 'data'
        self.jobs.mkdir()
        self.data.mkdir()
        self.pipeline_path = self.data / 'jobs.json'
        self.job = {'id': '123456', 'status': 'won', 'contract_client': 'Example Gym',
                    'url': 'https://www.upwork.com/jobs/~123456'}
        self.pipeline_path.write_text(json.dumps([self.job]), encoding='utf-8')
        self.source = self.jobs / self.job['id']
        self.source.mkdir()
        (self.source / 'project.md').write_text('# Gym handover\nAgreed delivery facts.\n', encoding='utf-8')
        self.registry = {}
        self.commands = []
        isolation = patch.dict(os.environ, {'BLUEPRINT_JOBS': str(self.pipeline_path),
                                            'BLUEPRINT_JOBDIR': str(self.jobs),
                                            'BLUEPRINT_DATA': str(self.data),
                                            'PYTHONDONTWRITEBYTECODE': '1',
                                            'GIT_ALLOW_PROTOCOL': 'file',
                                            'GIT_CONFIG_NOSYSTEM': '1',
                                            'GIT_CONFIG_GLOBAL': os.devnull,
                                            'GIT_TERMINAL_PROMPT': '0'})
        isolation.start()
        self.addCleanup(isolation.stop)
        for name, value in REGISTRY.items():
            self.registry[name] = {**value, 'url': self.fake_blueprint(name).as_uri()}
        for patcher in (
                patch.object(workspace, 'ROOT', self.repo),
                patch.object(workspace.pipeline, 'ROOT', self.repo),
                patch.object(workspace, 'BLUEPRINTS', self.registry),
                patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')),
                patch.object(workspace.subprocess, 'run', side_effect=self.offline_run)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *args, cwd):
        result = REAL_RUN(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
                           '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                           *args], cwd=cwd,
                          capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def fake_blueprint(self, name, fail=False):
        folder = self.base / 'blueprints' / name
        (folder / 'starters' / 'context').mkdir(parents=True)
        (folder / 'starters' / 'context' / 'business.md').write_text('# Business\n', encoding='utf-8')
        script = '#!/bin/sh\nset -eu\nprintf "%s\\n" "$PWD" >> setup-runs\n'
        if fail:
            script += 'test -f allow-setup || { echo "fixture setup failure" >&2; exit 7; }\n'
        script += 'mkdir -p context\ncp -n starters/context/business.md context/business.md\n'
        (folder / 'setup.sh').write_text(script, encoding='utf-8')
        (folder / 'setup.sh').chmod(0o755)
        self.git('init', cwd=folder)
        self.git('add', '.', cwd=folder)
        self.git('commit', '-m', 'Offline starter', cwd=folder)
        return folder

    def offline_run(self, command, **kwargs):
        self.commands.append((list(command), kwargs.get('cwd')))
        cwd = Path(kwargs['cwd']).resolve()
        self.assertTrue(cwd.is_relative_to(self.base), str(cwd))
        if command[0] == './setup.sh':
            self.assertEqual(command, ['./setup.sh'])
            self.assertNotEqual(cwd, self.repo)
            self.assertIn(cwd.name, self.registry)
        else:
            self.assertEqual(command[0], 'git')
            if len(command) > 1 and command[1] == 'clone':
                self.assertTrue(command[-2].startswith('file://'), 'remote clone forbidden')
                self.assertTrue(Path(command[-1]).resolve().is_relative_to(self.base))
        return REAL_RUN(command, **kwargs)

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = workspace.main(list(args))
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def new(self, *args):
        result = self.invoke('new', self.job['id'], *args)
        self.assertEqual(result[0], 0, result[2])
        return result

    @property
    def folder(self):
        return workspace.clients_root() / 'example-gym'

    def manifest(self):
        return json.loads((self.folder / '.client.json').read_text(encoding='utf-8'))

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def test_default_sibling_root(self):
        self.assertEqual(workspace.clients_root(), self.base / 'clients')
        self.me.write_text('**Clients folder:**\n## Next section\n', encoding='utf-8')
        self.assertEqual(workspace.clients_root(), self.base / 'clients')
        self.me.unlink()
        self.assertEqual(workspace.clients_root(), self.base / 'clients')

    def test_clients_folder_override_relative_absolute_and_tilde(self):
        for value, expected in [('delivery/clients', self.base / 'delivery' / 'clients'),
                                (str(self.base / 'absolute'), self.base / 'absolute')]:
            with self.subTest(value=value):
                self.me.write_text(f'**Clients folder:** {value}\n', encoding='utf-8')
                self.assertEqual(workspace.clients_root(), expected)
        self.me.write_text('**Clients folder:** ~/home-clients\n', encoding='utf-8')
        self.assertEqual(workspace.clients_root(), (Path.home() / 'home-clients').resolve())

    def test_inside_root_and_symlink_root_rejected_without_writes(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        for value in (str(self.repo), 'upwork/clients', str(alias / 'clients')):
            with self.subTest(value=value):
                self.me.write_text(f'**Clients folder:** {value}\n', encoding='utf-8')
                before = self.snapshot(self.repo)
                code, _, error = self.invoke('new', self.job['id'])
                self.assertEqual(code, 1)
                self.assertIn('inside the Upwork repository', error)
                self.assertEqual(self.snapshot(self.repo), before)
                code, output, _ = self.invoke('check', self.job['id'])
                self.assertEqual(code, 1)
                self.assertIn('FAIL clients root', output)
        self.assertNotIn('client_slug', workspace.pipeline.load()[0])

    def test_no_blueprint_layout_template_and_metadata(self):
        self.new()
        self.assertTrue(workspace.git_repo(self.folder))
        for name in ('inputs/upwork', 'work', 'delivered'):
            self.assertTrue((self.folder / name).is_dir())
        self.assertTrue((self.folder / '.gitignore').is_file())
        self.assertFalse((self.folder / 'context.md').exists())
        text = (self.folder / 'CLAUDE.md').read_text(encoding='utf-8')
        lines = [line for line in text.splitlines() if line.strip()]
        self.assertEqual(lines[0], '# Example Gym')
        self.assertTrue(lines[1].startswith('Recorded '))
        self.assertTrue(lines[2].startswith('**Next:**'))
        self.assertEqual([line for line in lines if line.startswith('## ')],
                         ['## The business', '## What was sold', '## How it runs',
                          '## Access the client owes', '## Where things are', '## Blueprints here'])
        self.assertIn('Pending access stays pending.', text)
        self.assertNotIn('each milestone is approved', text)
        self.assertNotIn('\u2014', text)
        self.assertEqual((self.folder / 'brief.md').read_bytes(), (self.source / 'project.md').read_bytes())
        value = self.manifest()
        self.assertEqual(set(value), {'job_id', 'job_url', 'created_at', 'blueprints'})
        self.assertEqual(value['job_id'], self.job['id'])
        self.assertEqual(value['job_url'], self.job['url'])
        self.assertEqual(value['blueprints'], [])
        self.assertNotIn('handover_done_at', workspace.pipeline.load()[0])

    def test_two_blueprints_setup_cwd_origins_commits_ignores_and_commands(self):
        _, output, _ = self.new('--blueprint', 'cro', '--blueprint', 'seo')
        self.assertEqual([i['name'] for i in self.manifest()['blueprints']], ['cro', 'seo'])
        for item in self.manifest()['blueprints']:
            clone = self.folder / item['name']
            self.assertTrue((clone / 'context' / 'business.md').is_file())
            self.assertEqual((clone / 'setup-runs').read_text().strip(), str(clone))
            self.assertEqual(item['commit'], self.git('rev-parse', 'HEAD', cwd=clone))
            self.assertEqual(item['url'], self.git('remote', 'get-url', 'origin', cwd=clone))
            self.assertTrue(workspace.ignored(self.folder, item['name']))
            self.assertIn(self.registry[item['name']]['next'], output)
            self.assertIn(self.registry[item['name']]['next'], (self.folder / 'CLAUDE.md').read_text())
        self.assertEqual([cmd for cmd, _ in self.commands if cmd[0] == './setup.sh'],
                         [['./setup.sh'], ['./setup.sh']])
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_registry_is_frozen(self):
        self.assertEqual(REGISTRY, {
            'seo': {'url': 'https://github.com/automatable-skool/seo-blueprint-day7', 'next': '/context-layer'},
            'ads': {'url': 'https://github.com/automatable-skool/ads-blueprint-day7', 'next': '/account-setup'},
            'cro': {'url': 'https://github.com/skool-automatable-month-2-83075/cro-blueprint', 'next': '/audit check <site>'}})

    def test_typed_github_clone_never_runs_setup(self):
        remotes = {name: self.fake_blueprint(name) for name in
                   ('-blueprint', 'custom-blueprint', '.github', '_blueprint')}
        urls = {f'https://github.com/member/{name}': remote for name, remote in remotes.items()}

        def routed(command, **kwargs):
            if command[:2] == ['git', 'clone'] and command[-2] in urls:
                url = command[-2]
                saved = self.manifest()['blueprints']
                self.assertTrue(any(item['url'] == url and item['commit'] == '' for item in saved))
                result = self.offline_run([*command[:-2], urls[url].as_uri(), command[-1]], **kwargs)
                if result.returncode == 0:
                    self.git('remote', 'set-url', 'origin', url, cwd=Path(command[-1]))
                return result
            return self.offline_run(command, **kwargs)

        with patch.object(workspace.subprocess, 'run', side_effect=routed):
            for name in remotes:
                with self.subTest(name=name):
                    url = f'https://github.com/member/{name}'
                    _, output, _ = self.new('--blueprint', url + '.git/')
                    clone = self.folder / name
                    self.assertTrue(workspace.git_repo(clone))
                    self.assertFalse((clone / 'context' / 'business.md').exists())
                    self.assertFalse((clone / 'setup-runs').exists())
                    self.assertIn('README', output)
                    self.assertIn(url, [item['url'] for item in self.manifest()['blueprints']])
                    self.assertEqual(self.invoke('check', self.job['id'])[0], 0)
            self.new()
        self.assertIn('cd ./-blueprint && claude', (self.folder / 'CLAUDE.md').read_text())
        self.assertFalse(any(cmd[0] == './setup.sh' for cmd, _ in self.commands))

    def test_reserved_blueprint_names_rejected_before_writes(self):
        names = ('.', '..', '.git', '.gitignore', '.client.json', '.client.json.tmp',
                 'inputs', 'work', 'delivered', 'CLAUDE.md', 'brief.md')
        before = self.snapshot(self.base)
        for name in names:
            for variant in (name, name.upper(), name + '.git', name.upper() + '.GIT'):
                with self.subTest(name=variant):
                    code, _, _ = self.invoke('new', self.job['id'], '--blueprint',
                                             f'https://github.com/member/{variant}')
                    self.assertEqual(code, 1)
                    self.assertEqual(self.snapshot(self.base), before)
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.commands)

    def test_metadata_rejects_same_reserved_names_before_writes(self):
        self.new()
        names = ('.', '..', '.git', '.gitignore', '.client.json', '.client.json.tmp',
                 'inputs', 'work', 'delivered', 'CLAUDE.md', 'brief.md')
        value = self.manifest()
        for name in names:
            for variant in (name, name.upper(), name + '.git', name.upper() + '.GIT'):
                with self.subTest(name=variant):
                    value['blueprints'] = [{'name': variant, 'url': 'https://github.com/member/repo'}]
                    (self.folder / '.client.json').write_text(json.dumps(value), encoding='utf-8')
                    before = self.snapshot(self.base)
                    self.assertEqual(self.invoke('new', self.job['id'])[0], 1)
                    self.assertEqual(self.invoke('check', self.job['id'])[0], 1)
                    self.assertEqual(self.snapshot(self.base), before)

    def test_output_quotes_full_cd_path_with_spaces(self):
        self.me.write_text(f'**Clients folder:** {self.base / "client roots"}\n', encoding='utf-8')
        _, output, _ = self.new('--blueprint', 'seo')
        path = str(self.folder / 'seo')
        expected = f'cd {shlex.quote(path)} && claude'
        self.assertIn(expected, output)
        self.assertEqual(shlex.split(expected), ['cd', path, '&&', 'claude'])
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_typed_github_validation_rejects_non_repository_links(self):
        bad = ['file:///tmp/repo', 'http://github.com/a/repo', 'https://example.test/a/repo',
               'https://github.com.evil.test/a/repo', 'https://user@github.com/a/repo',
               'https://github.com:443/a/repo', 'https://github.com/a/repo/tree/main',
               'https://github.com/a/repo?x=y', 'https://github.com/a/repo#main',
               'git@github.com:a/repo.git', 'https://github.com/a/../repo',
               'https://github.com/a/work', 'seo;echo bad']
        for value in bad:
            with self.subTest(value=value):
                self.assertEqual(self.invoke('new', self.job['id'], '--blueprint', value)[0], 1)
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.commands)

    def test_rerun_no_mutation_and_missing_clone_repair(self):
        self.new('--blueprint', 'seo', '--blueprint', 'ads')
        before = self.snapshot(self.folder)
        pipeline_before = self.snapshot(self.data)
        self.commands.clear()
        self.new()
        self.assertEqual(self.snapshot(self.folder), before)
        self.assertEqual(self.snapshot(self.data), pipeline_before)
        self.assertFalse(any(cmd[0] == './setup.sh' or cmd[:2] == ['git', 'clone'] for cmd, _ in self.commands))
        shutil.rmtree(self.folder / 'seo')
        kept = self.snapshot(self.folder / 'ads')
        self.new()
        self.assertTrue((self.folder / 'seo' / 'context' / 'business.md').is_file())
        self.assertEqual(self.snapshot(self.folder / 'ads'), kept)
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_missing_client_pieces_repair_preserves_existing_facts(self):
        self.new()
        context = self.folder / 'CLAUDE.md'
        context.write_text('# Member facts\nKeep these exact facts.\n', encoding='utf-8')
        (self.folder / 'brief.md').unlink()
        shutil.rmtree(self.folder / 'work')
        self.new()
        self.assertEqual(context.read_text(), '# Member facts\nKeep these exact facts.\n')
        self.assertTrue((self.folder / 'brief.md').exists())
        self.assertTrue((self.folder / 'work').is_dir())

    def test_slug_collision_does_not_change_folder_or_pipeline(self):
        self.new()
        before, pipeline_before = self.snapshot(self.folder), self.snapshot(self.data)
        with patch.object(workspace, 'get_job', return_value={**self.job, 'id': '654321'}):
            code, _, error = self.invoke('new', '654321')
        self.assertEqual(code, 1)
        self.assertIn('--slug', error)
        self.assertEqual(self.snapshot(self.folder), before)
        self.assertEqual(self.snapshot(self.data), pipeline_before)

    def test_where_prints_destination_writes_nothing_and_names_taken(self):
        code, out, _ = self.invoke('where', self.job['id'])
        self.assertEqual((code, out.strip()), (0, str(self.folder)))
        self.assertFalse(self.folder.exists())
        self.new()
        before = self.snapshot(self.folder)
        with patch.object(workspace, 'get_job', return_value={**self.job, 'id': '654321'}):
            code, out, _ = self.invoke('where', '654321')
            self.assertEqual(code, 1)
            self.assertIn('TAKEN', out)
            code, out, _ = self.invoke('where', '654321', '--slug', 'second-gym')
            self.assertEqual((code, out.strip()), (0, str(self.folder.parent / 'second-gym')))
        self.assertEqual(self.snapshot(self.folder), before)

    def test_slug_trim_and_explicit_slug(self):
        self.assertEqual(workspace.slugify('a' * 47 + ' b'), 'a' * 47)
        self.assertEqual(workspace.slugify('!!!'), 'client')
        self.new('--slug', 'Second Engagement')
        self.assertTrue((workspace.clients_root() / 'second-engagement' / '.client.json').is_file())
        self.assertEqual(workspace.pipeline.load()[0]['client_slug'], 'second-engagement')
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_clone_failure_keeps_first_and_resumes_selection(self):
        self.registry['ads']['url'] = (self.base / 'missing-blueprint').as_uri()
        code, _, error = self.invoke('new', self.job['id'], '--blueprint', 'seo', '--blueprint', 'ads')
        self.assertEqual(code, 1)
        self.assertIn('does not appear to be a git repository', error)
        self.assertTrue((self.folder / 'seo' / 'context' / 'business.md').is_file())
        self.assertEqual(len(self.manifest()['blueprints']), 2)
        self.assertNotIn('client_slug', workspace.pipeline.load()[0])
        self.assertNotIn('handover_done_at', workspace.pipeline.load()[0])
        kept = self.snapshot(self.folder / 'seo')
        self.assertEqual(self.invoke('check', self.job['id'])[0], 1)
        # Restore the unavailable source at the same URL without changing the saved selection.
        self.git('clone', self.registry['seo']['url'], str(self.base / 'missing-blueprint'), cwd=self.base)
        self.new()
        self.assertEqual(self.snapshot(self.folder / 'seo'), kept)
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_setup_failure_keeps_first_and_resumes_without_recloning(self):
        remote = self.fake_blueprint('failing-ads', fail=True)
        self.registry['ads']['url'] = remote.as_uri()
        code, _, error = self.invoke('new', self.job['id'], '--blueprint', 'seo', '--blueprint', 'ads')
        self.assertEqual(code, 1)
        self.assertIn('fixture setup failure', error)
        self.assertTrue(workspace.git_repo(self.folder / 'ads'))
        self.assertEqual(len(self.manifest()['blueprints'][1]['commit']), 40)
        self.assertNotIn('client_slug', workspace.pipeline.load()[0])
        kept = self.snapshot(self.folder / 'seo')
        (self.folder / 'ads' / 'allow-setup').touch()
        self.commands.clear()
        self.new()
        self.assertFalse(any(cmd[:2] == ['git', 'clone'] for cmd, _ in self.commands))
        self.assertEqual(self.snapshot(self.folder / 'seo'), kept)
        self.assertEqual(len((self.folder / 'ads' / 'setup-runs').read_text().splitlines()), 2)
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_successful_setup_without_business_file_is_failure(self):
        remote = self.fake_blueprint('empty-setup')
        (remote / 'setup.sh').write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
        self.git('add', '.', cwd=remote)
        self.git('commit', '-m', 'No business output', cwd=remote)
        self.registry['seo']['url'] = remote.as_uri()
        code, _, error = self.invoke('new', self.job['id'], '--blueprint', 'seo')
        self.assertEqual(code, 1)
        self.assertIn('did not create context/business.md', error)
        self.assertNotIn('client_slug', workspace.pipeline.load()[0])

    def test_sales_files_copied_once_and_job_files_unchanged(self):
        for name in workspace.SALES_FILES:
            (self.source / name).write_bytes(b'fixture-' + name.encode())
        evidence = self.source / 'call-prep' / 'nested' / 'site.json'
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b'{"fixture":true}')
        (self.source / 'private.env').write_bytes(b'do not copy')
        before = self.snapshot(self.source)
        self.new()
        copies = self.folder / 'inputs' / 'upwork'
        for name in (*workspace.SALES_FILES, 'call-prep/nested/site.json'):
            self.assertEqual((copies / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual(self.snapshot(self.source), before)
        self.assertFalse((copies / 'project.md').exists())
        self.assertFalse((copies / 'private.env').exists())
        self.assertEqual(len(self.snapshot(copies)), len(workspace.SALES_FILES) + 1)
        text = (self.folder / 'CLAUDE.md').read_text()
        for name in (*workspace.SALES_FILES, 'call-prep/nested/site.json'):
            self.assertIn(f'inputs/upwork/{name}', text)
        copied = self.snapshot(copies)
        (self.source / 'proposal.md').write_bytes(b'new source version')
        self.new()
        self.assertEqual(self.snapshot(copies), copied)

    def test_record_and_note_happen_after_client_metadata_exists(self):
        original = workspace.pipeline.main
        calls = []

        def observe(args):
            self.assertTrue((self.folder / '.client.json').is_file())
            self.assertTrue((self.folder / 'seo' / 'context' / 'business.md').is_file())
            calls.append(list(args))
            return original(args)

        with patch.object(workspace.pipeline, 'main', side_effect=observe):
            self.new('--blueprint', 'seo')
        self.assertEqual([call[0] for call in calls], ['record', 'note'])
        self.assertEqual(workspace.pipeline.load()[0]['client_slug'], 'example-gym')
        self.assertEqual(workspace.pipeline.load()[0]['log'][0]['text'], f'client workspace {self.folder}')
        self.assertNotIn('handover_done_at', workspace.pipeline.load()[0])

    def test_check_all_requirements_and_unknowns_are_informational(self):
        self.new('--blueprint', 'seo')
        before = self.snapshot(self.folder)
        code, output, error = self.invoke('check', self.job['id'])
        self.assertEqual((code, error), (0, ''))
        for message in ('clients root outside', 'client folder is a git repository', 'CLAUDE.md exists',
                        'brief.md exists', '.client.json names this job', 'seo is a blueprint clone',
                        'seo origin matches', 'seo context/business.md exists', '.gitignore excludes seo/'):
            self.assertIn('PASS ' + message, output)
        self.assertIn('INFO 11 fact(s)', output)
        self.assertNotIn('FAIL', output)
        self.assertEqual(self.snapshot(self.folder), before)

    def test_check_missing_clone_fails_every_related_requirement(self):
        self.new('--blueprint', 'seo')
        shutil.rmtree(self.folder / 'seo')
        code, output, _ = self.invoke('check', self.job['id'])
        self.assertEqual(code, 1)
        for message in ('seo is a blueprint clone', 'seo origin matches', 'seo context/business.md exists'):
            self.assertIn('FAIL ' + message, output)
        self.assertIn('PASS .gitignore excludes seo/', output)

    def test_check_origin_mismatch_and_ignore_negation_fail(self):
        self.new('--blueprint', 'seo')
        self.git('remote', 'set-url', 'origin', (self.base / 'wrong-origin').as_uri(), cwd=self.folder / 'seo')
        (self.folder / '.gitignore').write_text('/seo/\n!/seo/\n', encoding='utf-8')
        code, output, _ = self.invoke('check', self.job['id'])
        self.assertEqual(code, 1)
        self.assertIn('FAIL seo origin matches', output)
        self.assertIn('FAIL .gitignore excludes seo/', output)
        code, _, error = self.invoke('new', self.job['id'])
        self.assertEqual(code, 1)
        self.assertIn('origin does not match', error)
        self.assertTrue(workspace.ignored(self.folder, 'seo'))

    def test_git_local_exclude_does_not_replace_client_gitignore(self):
        self.new('--blueprint', 'seo')
        (self.folder / '.gitignore').write_text('', encoding='utf-8')
        (self.folder / '.git' / 'info' / 'exclude').write_text('/seo/\n', encoding='utf-8')
        code, output, _ = self.invoke('check', self.job['id'])
        self.assertEqual(code, 1)
        self.assertIn('FAIL .gitignore excludes seo/', output)
        self.new()
        self.assertIn('/seo/', (self.folder / '.gitignore').read_text().splitlines())
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_git_global_exclude_does_not_replace_client_gitignore(self):
        self.new('--blueprint', 'seo')
        member_rules = '# Member rules\n/member-private/\n'
        (self.folder / '.gitignore').write_text(member_rules, encoding='utf-8')
        excludes = self.base / 'global-excludes'
        excludes.write_text('/seo/\n', encoding='utf-8')
        self.git('config', '--local', 'core.excludesFile', str(excludes), cwd=self.folder)
        code, output, _ = self.invoke('check', self.job['id'])
        self.assertEqual(code, 1)
        self.assertIn('FAIL .gitignore excludes seo/', output)
        self.new()
        self.assertEqual((self.folder / '.gitignore').read_text(), member_rules + '\n/seo/\n')
        self.assertEqual(excludes.read_text(), '/seo/\n')
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_existing_gitignore_broad_and_pattern_rules_preserved(self):
        self.new('--blueprint', 'seo')
        for rule in ('*/', '/s*/'):
            with self.subTest(rule=rule):
                text = f'# Member rules\n/member-private/\n{rule}\n'
                (self.folder / '.gitignore').write_text(text, encoding='utf-8')
                self.assertTrue(workspace.ignored(self.folder, 'seo'))
                self.assertEqual(self.invoke('check', self.job['id'])[0], 0)
                self.new()
                self.assertEqual((self.folder / '.gitignore').read_text(), text)

    def test_symlink_client_or_clone_cannot_run_setup_elsewhere(self):
        workspace.clients_root().mkdir()
        self.folder.symlink_to(self.repo, target_is_directory=True)
        before = self.snapshot(self.repo)
        self.assertEqual(self.invoke('new', self.job['id'])[0], 1)
        self.assertEqual(self.snapshot(self.repo), before)
        self.folder.unlink()
        self.new('--blueprint', 'seo')
        shutil.rmtree(self.folder / 'seo')
        (self.folder / 'seo').symlink_to(self.base / 'blueprints' / 'seo', target_is_directory=True)
        self.commands.clear()
        self.assertEqual(self.invoke('new', self.job['id'])[0], 1)
        self.assertEqual(self.invoke('check', self.job['id'])[0], 1)
        self.assertFalse(any(cmd[0] == './setup.sh' for cmd, _ in self.commands))

    def test_check_missing_base_files_git_and_business_fail(self):
        self.new('--blueprint', 'seo')
        for name in ('CLAUDE.md', 'brief.md', 'seo/context/business.md'):
            (self.folder / name).unlink()
        shutil.rmtree(self.folder / '.git')
        code, output, _ = self.invoke('check', self.job['id'])
        self.assertEqual(code, 1)
        for message in ('client folder is a git repository', 'CLAUDE.md exists', 'brief.md exists',
                        'seo context/business.md exists', '.gitignore excludes seo/'):
            self.assertIn('FAIL ' + message, output)

    def test_missing_brief_is_reported_then_repaired(self):
        (self.source / 'project.md').unlink()
        _, output, _ = self.new()
        self.assertIn('No project.md yet', output)
        self.assertEqual(self.invoke('check', self.job['id'])[0], 1)
        (self.source / 'project.md').write_text('Later brief', encoding='utf-8')
        self.new()
        self.assertEqual((self.folder / 'brief.md').read_text(), 'Later brief')
        self.assertEqual(self.invoke('check', self.job['id'])[0], 0)

    def test_check_missing_corrupt_or_wrong_job_metadata_fails(self):
        self.new()
        path = self.folder / '.client.json'
        for value in (None, 'broken json', json.dumps({**self.manifest(), 'job_id': 'another'})):
            with self.subTest(value=value):
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(value, encoding='utf-8')
                self.assertEqual(self.invoke('check', self.job['id'])[0], 1)

    def test_list_external_and_legacy_counts_and_empty(self):
        self.assertIn('No clients yet', self.invoke('list')[1])
        self.new()
        legacy = self.repo / 'clients' / 'older-client'
        legacy.mkdir(parents=True)
        (legacy / 'context.md').write_text('# Older Client\n_not recorded yet_\n', encoding='utf-8')
        code, output, _ = self.invoke('list')
        self.assertEqual(code, 0)
        self.assertIn('example-gym: Example Gym | 11 fact(s)', output)
        self.assertIn('older-client (legacy): Older Client | 1 fact(s)', output)
        self.assertIn(str(self.folder), output)
        self.assertIn(str(legacy), output)

    def test_won_gate_and_unknown_job_do_not_create_folder(self):
        self.pipeline_path.write_text(json.dumps([{**self.job, 'status': 'offer'}]), encoding='utf-8')
        self.assertEqual(self.invoke('new', self.job['id'])[0], 1)
        self.assertEqual(self.invoke('new', '999999')[0], 1)
        self.assertFalse((self.base / 'clients').exists())
        self.assertNotIn('client_slug', workspace.pipeline.load()[0])

    def test_duplicate_blueprints_and_name_collision(self):
        self.new('--blueprint', 'seo', '--blueprint', 'seo')
        self.assertEqual(len(self.manifest()['blueprints']), 1)
        before = self.snapshot(self.folder)
        code, _, error = self.invoke('new', self.job['id'], '--blueprint', 'https://github.com/other/seo')
        self.assertEqual(code, 1)
        self.assertIn('already belongs to another repository', error)
        self.assertEqual(self.snapshot(self.folder), before)

    def test_existing_non_clone_is_preserved_and_not_setup(self):
        self.new()
        clone = self.folder / 'seo'
        clone.mkdir()
        (clone / 'member.txt').write_text('Keep this', encoding='utf-8')
        code, _, error = self.invoke('new', self.job['id'], '--blueprint', 'seo')
        self.assertEqual(code, 1)
        self.assertIn('not a blueprint clone', error)
        self.assertEqual((clone / 'member.txt').read_text(), 'Keep this')
        self.assertFalse(any(cmd[0] == './setup.sh' for cmd, _ in self.commands))

    def test_client_name_fallbacks(self):
        job = {**self.job, 'contract_client': '', 'client': {'company_name': 'Company', 'name': 'Person'}}
        self.assertEqual(workspace.client_name(job), 'Company')
        (self.source / 'thread.json').write_text(json.dumps({'messages': [
            {'from': 'me', 'name': 'Member'}, {'from': 'client', 'name': 'Thread Client'}]}), encoding='utf-8')
        self.assertEqual(workspace.client_name(job), 'Thread Client')
        (self.source / 'thread.json').write_text('invalid json', encoding='utf-8')
        self.assertEqual(workspace.client_name({**job, 'client': {}}), 'job-123456')


if __name__ == '__main__':
    unittest.main()
