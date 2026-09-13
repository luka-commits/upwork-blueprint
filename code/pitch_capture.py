#!/usr/bin/env python3
"""Capture or remove the temporary desktop preview for one pitch page.

    python3 code/pitch_capture.py <job_id>
    python3 code/pitch_capture.py <job_id> --clean
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def browser_path():
    candidates = [
        os.environ.get('CHROME_BIN'),
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    return next((str(path) for path in candidates if path and pathlib.Path(path).is_file()), None)


def paths(job_id):
    if not job_id.isdigit():
        raise ValueError('job id must contain digits only.')
    folder = ROOT / 'jobs' / job_id
    return folder / 'pitch.html', folder / '.pitch-preview.png'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args(argv)
    try:
        page, output = paths(args.job_id)
    except ValueError as exc:
        parser.error(str(exc))
    if args.clean:
        output.unlink(missing_ok=True)
        print(f'Removed {output.relative_to(ROOT)}.')
        return 0
    if not page.is_file():
        parser.error(f'pitch page not found: {page.relative_to(ROOT)}')
    browser = browser_path()
    if not browser:
        parser.error('Chrome or Chromium is not installed.')
    with tempfile.TemporaryDirectory(prefix='upwork-pitch-browser-') as profile:
        result = subprocess.run([
            browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
            '--window-size=1440,1200', f'--user-data-dir={profile}',
            f'--screenshot={output}', page.resolve().as_uri(),
        ], capture_output=True, text=True, timeout=60)
    if result.returncode or not output.is_file() or output.stat().st_size < 1000:
        detail = (result.stderr or result.stdout or '').strip().splitlines()
        parser.error(f'Chrome did not create the preview{f": {detail[-1]}" if detail else "."}')
    print(f'Preview: {output.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
