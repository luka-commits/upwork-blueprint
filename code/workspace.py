#!/usr/bin/env python3
"""Copies the shipped starters into place the first time, and never again.

Every command runs this first. Everything it creates is gitignored, so it is
the member's alone: `git pull` updates the machinery and never touches their
files. An existing file is never overwritten, so running it twice is safe.

    python3 code/workspace.py
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STARTERS = ROOT / 'starters'


def ensure(root=ROOT, starters=STARTERS):
    """Copies every starter whose target does not exist yet. Returns what it created."""
    created = []
    for source in sorted(p for p in starters.rglob('*') if p.is_file()):
        relative = source.relative_to(starters)
        target = root / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        created.append(str(relative))
    return created


def main():
    created = ensure()
    if created:
        for rel in created:
            print(f'created {rel}')
        print('\nThese files are yours and gitignored. `git pull` will never touch them.')
    else:
        print('Nothing to create, your files are in place.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
