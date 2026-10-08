#!/usr/bin/env python3
"""Copies missing starters and places new empty fields in the member's me.md.

Every command runs this first. Everything it creates is gitignored, so it is
the member's alone: `git pull` updates the machinery and never touches their
files. Existing answers are never overwritten, so running it twice is safe.

    python3 code/workspace.py
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STARTERS = ROOT / 'starters'
STARTER = 'not answered yet'
LABEL = re.compile(r'^\*\*([^\n]+?):\*\*[ \t]*(.*)$')
# Older runs appended missing fields here, at the end of the file. Readers that
# take the first match and readers that take the last then disagreed.
SETUP = re.compile(r'\n*^## Setup fields\n(.*?)(?=^## |\Z)', re.M | re.S)


def answered(value):
    return bool(value) and STARTER not in value.lower()


def place_missing(text, starter):
    """me.md with every starter field it lacks, each in the section the starter puts it in.

    `## Setup fields` blocks from older runs are folded back first: an answer in
    one fills that field where it belongs. Nothing the member wrote is dropped;
    when that cannot be shown, the file is left as it was.
    """
    carried = {}
    for block in SETUP.findall(text):
        for line in block.splitlines():
            match = LABEL.match(line)
            if match and (answered(match.group(2)) or match.group(1).lower() not in carried):
                carried[match.group(1).lower()] = match.group(2).strip()
    lines = SETUP.sub('\n', text).rstrip('\n').splitlines()

    def position(label):
        return next((i for i, line in enumerate(lines)
                     if (m := LABEL.match(line)) and m.group(1).lower() == label.lower()), None)

    for label, value in carried.items():
        i = position(label)
        if i is not None and answered(value) and not answered(LABEL.match(lines[i]).group(2)):
            lines[i] = f'**{LABEL.match(lines[i]).group(1)}:** {value}'

    starter_lines = starter.splitlines()
    headings = [line for line in starter_lines if line.startswith('## ')]
    order, heading = [], None
    for line in starter_lines:
        heading = line if line.startswith('## ') else heading
        if (match := LABEL.match(line)):
            order.append((heading, match.group(1)))

    def fill(label):
        value = carried.get(label.lower(), '')
        return f'**{label}:** {value if answered(value) else STARTER}'

    for k, (heading, label) in enumerate(order):
        if position(label) is not None:
            continue
        if heading in lines:
            h = lines.index(heading)
            end = next((j for j in range(h + 1, len(lines)) if lines[j].startswith('## ')), len(lines))
            anchor = next((i for _, earlier in reversed([o for o in order[:k] if o[0] == heading])
                           if (i := position(earlier)) is not None and h < i < end), None)
            at = anchor + 1 if anchor is not None else h + 2 if h + 1 < len(lines) and not lines[h + 1] else h + 1
            lines.insert(at, fill(label))
            continue
        # The whole section is missing: the starter's own, before the next section the file has.
        start = starter_lines.index(heading)
        stop = next((j for j in range(start + 1, len(starter_lines)) if starter_lines[j].startswith('## ')),
                    len(starter_lines))
        section = [fill(m.group(1)) if (m := LABEL.match(line)) else line
                   for line in starter_lines[start:stop]]
        later = [h for h in headings[headings.index(heading) + 1:] if h in lines]
        at = lines.index(later[0]) if later else len(lines)
        if at == len(lines) or (at and lines[at - 1]):
            section = [''] + section
        lines[at:at] = [line for line in section] + ([] if section[-1] == '' else [''])
    placed = '\n'.join(lines).rstrip('\n') + '\n'

    # Every answer in the old file, Setup blocks included, must still be there.
    kept = all(f'**{m.group(1)}:** {m.group(2).strip()}'.lower() in placed.lower()
               or not answered(m.group(2))
               for line in text.splitlines() if (m := LABEL.match(line)))
    body = [line for line in SETUP.sub('\n', text).splitlines() if line.strip() and not LABEL.match(line)]
    return placed if kept and all(line in placed for line in body) else text


def ensure(root=ROOT, starters=STARTERS):
    """Copies every starter whose target does not exist yet. Returns what it created."""
    created = []
    (root / 'data').mkdir(exist_ok=True)  # the live profile and job files land here
    for source in sorted(p for p in starters.rglob('*') if p.is_file()):
        relative = source.relative_to(starters)
        target = root / relative
        if target.exists():
            if relative == pathlib.Path('context/me.md'):
                text = target.read_text(encoding='utf-8')
                placed = place_missing(text, source.read_text(encoding='utf-8'))
                if placed != text:
                    target.write_text(placed, encoding='utf-8')
                    created.append(f'{relative} (new empty fields, each in its section)')
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
