"""Focused startup tests for code/cockpit.py. No app process is started."""
import io
import pathlib
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

CODE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
import cockpit  # noqa: E402


class Child:
    def __init__(self, polls=None, wait_result=0):
        self.polls = iter(polls or [None])
        self.returncode = None
        self.wait_result = wait_result
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        try:
            self.returncode = next(self.polls)
        except StopIteration:
            pass
        return self.returncode

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if isinstance(self.wait_result, BaseException):
            raise self.wait_result
        return self.wait_result

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class CockpitStartTest(unittest.TestCase):
    def run_serve(self, child, urlopen, *, open_browser=True):
        opened = mock.Mock()
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(cockpit, 'port_busy', return_value=False), \
                mock.patch.object(cockpit, 'needs_build', return_value=False), \
                mock.patch.object(cockpit, 'npm', return_value=(['npm'], False)), \
                mock.patch.object(cockpit.subprocess, 'Popen', return_value=child), \
                mock.patch.object(cockpit.urllib.request, 'urlopen', side_effect=urlopen), \
                mock.patch.object(cockpit.time, 'sleep'), \
                mock.patch.object(cockpit.webbrowser, 'open', opened), \
                redirect_stdout(output), redirect_stderr(errors):
            # Pretend dependencies already exist without touching the real app tree.
            with mock.patch.object(pathlib.Path, 'is_dir', return_value=True):
                result = cockpit.serve(4322, open_browser)
        return result, output.getvalue(), errors.getvalue(), opened

    def test_reports_and_opens_only_after_http_is_ready(self):
        response = mock.Mock()
        child = Child(wait_result=0)
        result, output, errors, opened = self.run_serve(child, [OSError(), response])
        self.assertEqual(result, 0)
        self.assertIn('Cockpit running at http://127.0.0.1:4322/', output)
        self.assertEqual(errors, '')
        opened.assert_called_once_with('http://127.0.0.1:4322/')
        response.close.assert_called_once_with()
        self.assertFalse(child.terminated)

    def test_early_clean_exit_is_still_a_start_failure(self):
        child = Child(polls=[0])
        result, output, errors, opened = self.run_serve(child, [OSError()])
        self.assertEqual(result, 1)
        self.assertEqual(output, '')
        self.assertIn('server exited with code 0', errors)
        opened.assert_not_called()

    def test_early_nonzero_exit_is_propagated(self):
        child = Child(polls=[7])
        result, output, errors, opened = self.run_serve(child, [OSError()])
        self.assertEqual(result, 7)
        self.assertEqual(output, '')
        self.assertIn('server exited with code 7', errors)
        opened.assert_not_called()

    def test_timeout_stops_only_the_spawned_child_and_never_opens(self):
        child = Child(polls=[None] * 60, wait_result=0)
        result, output, errors, opened = self.run_serve(child, [OSError()] * 60)
        self.assertEqual(result, 1)
        self.assertEqual(output, '')
        self.assertIn('did not become ready during startup', errors)
        self.assertTrue(child.terminated)
        self.assertFalse(child.killed)
        self.assertEqual(child.wait_timeouts, [5])
        opened.assert_not_called()

    def test_timeout_kills_a_child_that_ignores_termination(self):
        child = Child(polls=[None] * 60, wait_result=subprocess.TimeoutExpired('next', 5))
        result, output, errors, opened = self.run_serve(child, [OSError()] * 60)
        self.assertEqual(result, 1)
        self.assertTrue(child.terminated)
        self.assertTrue(child.killed)
        self.assertEqual(child.wait_timeouts, [5, 5])
        opened.assert_not_called()

    def test_busy_port_returns_before_spawning_or_stopping_anything(self):
        with mock.patch.object(cockpit, 'port_busy', return_value=True), \
                mock.patch.object(cockpit.subprocess, 'Popen') as popen, \
                mock.patch.object(cockpit, 'stop_child') as stop:
            self.assertEqual(cockpit.serve(4321, False), 1)
        popen.assert_not_called()
        stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
