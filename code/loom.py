#!/usr/bin/env python3
"""Transcribe a sent Loom locally: loom.py <job_id> <url>. Score a review: loom.py score <state> x4."""
import argparse
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

import pipeline


MODEL_DIRS = (pathlib.Path.home() / '.cache' / 'whisper-cpp',
              pathlib.Path('/opt/homebrew/share/whisper-cpp'))
MODEL_DOWNLOAD = ('mkdir -p ~/.cache/whisper-cpp && curl -L '
                  'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin '
                  '-o ~/.cache/whisper-cpp/ggml-base.bin')


def find_model():
    explicit = os.environ.get('WHISPER_MODEL')
    if explicit:
        model = pathlib.Path(explicit).expanduser()
        return model if model.is_file() else None
    models = [path for folder in MODEL_DIRS for path in folder.glob('ggml-*.bin')
              if path.is_file() and 'for-tests-' not in path.name]
    priority = {'ggml-base.bin': 0, 'ggml-small.bin': 1}
    models.sort(key=lambda path: (priority.get(path.name, 2), '.en' in path.name, path.name, str(path)))
    return models[0] if models else None


def words(text):
    return re.findall(r"\b[\w]+(?:['’-]\w+)*\b", text)


LOOM_POINTS = ('opens with the client problem', 'shows something relevant to this job',
               'length fits', 'ends with one easy ask')


def loom_score(states):
    """Loom Score 0 to 100, computed here and never by Claude: met and half of partly over applicable points."""
    states = [str(state).replace(' ', '_') for state in states]
    if len(states) != len(LOOM_POINTS) or any(state not in ('met', 'partly', 'missing', 'not_needed') for state in states):
        raise ValueError('four states needed: met, partly, missing or not_needed')
    met, partly = states.count('met'), states.count('partly')
    applicable = met + partly + states.count('missing')
    if not applicable: return {'score': None, 'met': met, 'partly': partly, 'applicable': 0}
    return {'score': math.floor(100 * (met + 0.5 * partly) / applicable + .5), 'met': met, 'partly': partly, 'applicable': applicable}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['score']:
        try: print(json.dumps(loom_score(argv[1:])))
        except ValueError as exc: print(exc, file=sys.stderr); return 2
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('url')
    args = parser.parse_args(argv)
    pipeline.find(pipeline.load(), args.job_id)
    for binary, install in [('yt-dlp', 'brew install yt-dlp'),
                            ('whisper-cli', 'brew install whisper.cpp')]:
        if not shutil.which(binary):
            print(f'SKIP Loom: {binary} is missing. Install: {install}')
            return 0
    model = find_model()
    if model is None:
        print('SKIP Loom: no local Whisper model found. Download: ' + MODEL_DOWNLOAD)
        return 0
    if urllib.parse.urlparse(args.url).scheme not in ('https', 'http'):
        parser.error('a video URL is required')
    try:
        info = subprocess.run(['yt-dlp', '--no-playlist', '--skip-download',
                               '--dump-single-json', args.url], check=True,
                              capture_output=True, text=True)
        duration = json.loads(info.stdout).get('duration')
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                or not math.isfinite(duration) or duration <= 0):
            raise ValueError('the video has no measured duration')
        with tempfile.TemporaryDirectory(prefix='blueprint-loom-') as temp:
            folder = pathlib.Path(temp)
            subprocess.run(['yt-dlp', '--no-playlist', '-x', '--audio-format', 'wav',
                            '-o', str(folder / 'audio.%(ext)s'), args.url], check=True,
                           capture_output=True, text=True)
            audio = folder / 'audio.wav'
            output = folder / 'transcript'
            subprocess.run(['whisper-cli', '-m', str(model), '-f', str(audio),
                            '-otxt', '-osrt', '-of', str(output)], check=True,
                           capture_output=True, text=True)
            text = output.with_suffix('.txt').read_text(encoding='utf-8').strip()
            if not words(text):
                raise ValueError('whisper-cli produced no transcript words')
            srt = output.with_suffix('.srt')
            turns = srt.read_text(encoding='utf-8').strip() if srt.exists() else text
        metrics = {'loom_duration_s': round(duration, 2),
                   'loom_wpm': round(len(words(text)) * 60 / duration, 1)}
        folder = pipeline.jobs_dir() / args.job_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'loom.md').write_text(
            f'# Loom transcript\n\nDuration: {metrics["loom_duration_s"]} seconds\n'
            f'Words per minute: {metrics["loom_wpm"]}\n\n{turns}\n', encoding='utf-8')
        print(json.dumps(metrics))
        return 0
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        detail = (exc.stderr or str(exc)).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f'Loom measurement failed: {detail}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
