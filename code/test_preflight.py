"""Tests for connection and balance checks that run before paid work."""

import pathlib
import subprocess
import unittest

import preflight


class PreflightTest(unittest.TestCase):
    def test_firecrawl_requires_measurable_credit(self):
        env = {'FIRECRAWL_API_KEY': 'key'}
        self.assertEqual(preflight.firecrawl_error(
            env, fetch=lambda *_args, **_kwargs: {'success': True, 'data': {'remainingCredits': 20}}), '')
        self.assertIn('at least 3', preflight.firecrawl_error(
            env, fetch=lambda *_args, **_kwargs: {'success': True, 'data': {'remainingCredits': 2}}))

    def test_apify_uses_the_hard_limit_headroom(self):
        env = {'APIFY_API_TOKEN': 'token'}
        good = {'data': {'limits': {'maxMonthlyUsageUsd': 20}, 'current': {'monthlyUsageUsd': 10}}}
        low = {'data': {'limits': {'maxMonthlyUsageUsd': 20}, 'current': {'monthlyUsageUsd': 18.5}}}
        self.assertEqual(preflight.apify_error(env, fetch=lambda *_args, **_kwargs: good), '')
        self.assertIn('1.50 USD left', preflight.apify_error(env, fetch=lambda *_args, **_kwargs: low))

    def test_dataforseo_requires_a_successful_task_and_balance(self):
        env = {'DATAFORSEO_LOGIN': 'login', 'DATAFORSEO_PASSWORD': 'password'}
        good = {'status_code': 20000, 'tasks_error': 0,
                'tasks': [{'status_code': 20000, 'result': [{'money': {'balance': 5}}]}]}
        low = {'status_code': 20000, 'tasks_error': 0,
               'tasks': [{'status_code': 20000, 'result': [{'money': {'balance': 0.5}}]}]}
        self.assertEqual(preflight.dataforseo_error(env, fetch=lambda *_args, **_kwargs: good), '')
        self.assertIn('0.50 USD left', preflight.dataforseo_error(env, fetch=lambda *_args, **_kwargs: low))

    def test_vercel_authenticates_and_creates_a_missing_project_before_paid_work(self):
        calls = []

        def run(command, **_kwargs):
            calls.append(command[1:3])
            if command[1:3] == ['whoami', '--no-color']:
                return subprocess.CompletedProcess(command, 0, 'member\n', '')
            if command[1:3] == ['project', 'inspect'] and calls.count(['project', 'inspect']) == 1:
                return subprocess.CompletedProcess(command, 1, '', 'missing')
            return subprocess.CompletedProcess(command, 0, 'ok\n', '')

        error = preflight.vercel_error(
            {'VERCEL_PITCH_PROJECT': 'member-pitches'}, which=lambda _name: '/bin/vercel', runner=run)
        self.assertEqual(error, '')
        self.assertIn(['project', 'add'], calls)
        self.assertEqual(calls.count(['project', 'inspect']), 2)

    def test_missing_credentials_fail_without_provider_calls(self):
        calls = []
        fetch = lambda *_args, **_kwargs: calls.append(True) or {}
        self.assertIn('FIRECRAWL_API_KEY', preflight.firecrawl_error({}, fetch=fetch))
        self.assertIn('APIFY_API_TOKEN', preflight.apify_error({}, fetch=fetch))
        self.assertIn('DATAFORSEO_LOGIN', preflight.dataforseo_error({}, fetch=fetch))
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
