#!/usr/bin/env python3
"""Fills a one-page roadmap with the live flowchart of the pitch page.

    python3 code/roadmap_build.py templates/roadmap/gohighlevel.html \
        --graph templates/pitch/graphs/ghl-funnel.json --out jobs/<id>/pitch.html [--title "..."]

A roadmap template that carries a flowchart holds three markers: {{DIAGRAM_CSS}} in its
<style>, {{DIAGRAM_BLOCK}} where the chart sits, and {{DIAGRAM_SCRIPTS}} before </body>.
They are filled from templates/pitch/, so the chart is the very component the pitch page
uses (drag, zoom, run the flow, select a step for its note), not a second drawing.

The graph follows the rules of the pitch page and is checked by the same code. Pure
assembly: nothing is written outside --out.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pitch_generate as pg  # noqa: E402

PITCH = ROOT / 'templates' / 'pitch' / 'template.html'
KEEP = re.compile(r'\.dg-|\.artifact|\.sw\b|\.sw-|#dg')


def rules(css):
    """Top-level CSS blocks as (selector, text); nested @media stays one block."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, depth, start = [], 0, 0
    for i, ch in enumerate(css):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                block = css[start:i + 1].strip()
                out.append((block.split('{', 1)[0].strip(), block))
                start = i + 1
    return out


def diagram_css():
    style = re.search(r'<style>(.*?)</style>', PITCH.read_text(encoding='utf-8'), re.S).group(1)
    keep = [text for selector, text in rules(style)
            if selector == ':root' or selector.startswith('html[data-theme') or KEEP.search(text)]
    return '\n'.join(keep)


def diagram_block(title, fallback):
    page = PITCH.read_text(encoding='utf-8')
    figure = re.search(r'<figure class="artifact" id="dg".*?</figure>', page, re.S).group(0)
    return figure.replace('{{JOB_TITLE}}', pg.esc(title)).replace('{{DIAGRAM_FALLBACK}}', fallback)


def scripts(data, nodes):
    js = pg.DIAGRAM_JS.read_text(encoding='utf-8').replace('{{LOGOS_JSON}}', pg.logos_json(nodes))
    return (f'<script type="application/json" id="dg-data">{data.replace("</", "<\\/")}</script>\n'
            f'<script>{js}</script>')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('template', help='a roadmap template with the three diagram markers')
    ap.add_argument('--graph', required=True, help='the flowchart as JSON, or a path to it')
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='Lead-to-cash system', help='the name on the chart bar')
    args = ap.parse_args(argv)
    template = pathlib.Path(args.template)
    html = template.read_text(encoding='utf-8')
    for marker in ('{{DIAGRAM_CSS}}', '{{DIAGRAM_BLOCK}}', '{{DIAGRAM_SCRIPTS}}'):
        if marker not in html:
            raise SystemExit(f'{template} has no {marker}: it carries no flowchart.')
    data, fallback = pg.build_graph(args.graph)
    import json
    nodes = json.loads(data)['nodes']
    html = (html.replace('{{DIAGRAM_CSS}}', diagram_css())
                .replace('{{DIAGRAM_BLOCK}}', diagram_block(args.title, fallback))
                .replace('{{DIAGRAM_SCRIPTS}}', scripts(data, nodes)))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(f'{out} written: {len(nodes)} steps')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
