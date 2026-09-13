#!/usr/bin/env python3
"""Assembles the pitch page for one job: headline, walkthrough video, fit points,
reviews, background, the live editable diagram, scope, and the next step.

Pure assembly. The diagram plan and every sentence are written by Claude from the
job posting before this runs; this script checks them and fills the template.
Reviews and background come from context/proof.md, so the page can never claim
something the proof file does not hold.

    python3 code/pitch/generate.py <job_id> \\
        --hook "..." \\
        --build-lede "..." \\
        --fit-point "200%|more website leads|for local businesses" (three times) \\
        --graph data/pitch-graph-<job_id>.json \\
        --tool "GoHighLevel" --tool "n8n" \\
        --timeline "Day 1-2|What ships;;Day 3-5|What ships" \\
        --budget "..." --kickoff "..." --kickoff "..." \\
        [--loom-url https://www.loom.com/share/...] [--video-length "3 minute"] \\
        [--hero-illustration path] [--live-artifact "Label|URL"] \\
        [--proof-link "Label|Detail|URL"] [--next-step "..."] \\
        [--showcase "Title|Teaser|URL|CTA" --showcase-point "..." --showcase-image path]

Writes jobs/<job_id>/pitch.html. Exits 1 on anything missing or malformed: a half
page with a silent gap is worse than a stop that names the cause.
"""
import argparse
import base64
import datetime
import html
import json
import math
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = HERE / 'template.html'
DIAGRAM_JS = HERE / 'diagram.js'
LOGO_DIR = HERE / 'logos'
DITHER = HERE / 'ink-plume.png'
REPORT_COVER = HERE / 'report-cover-example.jpg'
PIPELINE = ROOT / 'code' / 'pipeline.py'
PROOF = ROOT / 'context' / 'proof.md'
ME = ROOT / 'context' / 'me.md'
VIDEOS = ROOT / 'context' / 'videos.json'
PROFILE = ROOT / 'data' / 'profile.json'
LIBRARY = ROOT / 'data' / 'pitch-library'

GRAPH_KINDS = {'source', 'step', 'sink', 'service', 'decision', 'note', 'datastore', 'milestone', 'actor'}
GRAPH_OWNERS = {'you', 'client', 'thirdparty'}
DEFAULT_NEXT = ("Send me your website or a screenshot of your current setup here on Upwork, "
                "and I'll reply with the first three things I would build.")

FIT_ICON = ('<svg class="icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<circle cx="12" cy="12" r="12"/><path d="M7 12.5L10.5 16L17 8.5" stroke="white" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
YT_PLAY = ('<svg viewBox="0 0 28 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
           '<path fill="#FF0000" d="M27.4 3.1A3.51 3.51 0 0 0 24.9.6C22.7 0 14 0 14 0S5.3 0 3.1.6'
           'A3.51 3.51 0 0 0 .6 3.1C0 5.3 0 10 0 10s0 4.7.6 6.9a3.51 3.51 0 0 0 2.5 2.5C5.3 20 14 20 14 20'
           's8.7 0 10.9-.6a3.51 3.51 0 0 0 2.5-2.5C28 14.7 28 10 28 10s0-4.7-.6-6.9z"/>'
           '<path fill="#ffffff" d="M11.2 14.29 18.5 10l-7.3-4.29z"/></svg>')


def abort(msg):
    print(f'ABORT: {msg}', file=sys.stderr)
    sys.exit(1)


def esc(text):
    return html.escape(str(text), quote=True)


def safe_job_title(text):
    """Client titles are data, but the generated page follows our copy rules."""
    return str(text or '').replace(chr(0x2014), '-')


def data_uri(path, mime=None):
    p = pathlib.Path(path)
    if not p.is_file():
        abort(f'image "{p}" does not exist.')
    mime = mime or ('image/jpeg' if p.suffix.lower() in ('.jpg', '.jpeg') else 'image/png')
    return f'data:{mime};base64,{base64.b64encode(p.read_bytes()).decode("ascii")}'


def load_job(job_id):
    r = subprocess.run([sys.executable, str(PIPELINE), 'get', job_id], capture_output=True, text=True)
    if r.returncode:
        abort(r.stderr.strip() or f'job "{job_id}" is not in the pipeline.')
    return json.loads(r.stdout)


def section(text, heading):
    m = re.search(rf'^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return (m.group(0).split('\n', 1)[0], m.group(1)) if m else ('', '')


def bullets(block):
    return [l[2:].strip() for l in block.splitlines() if l.startswith('- ')]


def reviews(proof_text, limit):
    """Real client words from the proof file's Reviews section: - "quote" · job."""
    head, block = section(proof_text, 'Reviews')
    five = '5 star' in head.lower()
    out = []
    for line in bullets(block):
        m = re.match(r'^"(.+)"\s*·\s*(.+)$', line)
        if m:
            out.append({'quote': m.group(1), 'job': m.group(2), 'stars': five})
    return out[:limit] if limit else out


def cv_block(proof_text, me_text):
    """Background from the proof and facts files. Nothing here is typed in by hand."""
    _, record = section(proof_text, 'Upwork track record')
    _, creds = section(proof_text, 'Credentials')
    parts = []
    stats = []
    for line in bullets(record)[:1]:
        for chunk in line.split(','):
            m = re.match(r'\s*(\$?[\d.,]+[KkMm]?\+?%?)\s+(.+)', chunk)
            if m:
                stats.append(f'<div><strong>{esc(m.group(1))}</strong><span>{esc(m.group(2).strip())}</span></div>')
    if stats:
        parts.append(f'<div class="cv-stats">{"".join(stats)}</div>')
    more = bullets(record)[1:]
    if more:
        parts.append('<p class="cv-sub">Track record</p><ul class="cv-list">'
                     + ''.join(f'<li>{esc(b)}</li>' for b in more) + '</ul>')
    if bullets(creds):
        parts.append('<p class="cv-sub">Background</p><ul class="cv-list">'
                     + ''.join(f'<li>{esc(b)}</li>' for b in bullets(creds)) + '</ul>')
    lang = re.search(r'\*\*Languages:\*\*\s*(.+)', me_text)
    if lang:
        parts.append(f'<p class="cv-lang">{esc(lang.group(1).strip())}</p>')
    if not parts:
        return ''
    return ('<details class="cv"><summary>More about my background</summary>'
            f'<div class="cv-body">{"".join(parts)}</div></details>')


def profile_url():
    try:
        data = json.loads(PROFILE.read_text(encoding='utf-8'))
        key = data.get('data', {}).get('identity', {}).get('ciphertext')
        return f'https://www.upwork.com/freelancers/{key}' if key else ''
    except (OSError, json.JSONDecodeError):
        return ''


def build_graph(spec):
    try:
        if str(spec).lstrip().startswith(('{', '[')):
            source = spec
        else:
            p = pathlib.Path(spec)
            source = p.read_text(encoding='utf-8') if p.is_file() else spec
        g = json.loads(source)
    except OSError as e:
        abort(f'--graph could not be read: {e}')
    except json.JSONDecodeError as e:
        abort(f'--graph is not valid JSON: {e}')
    if not isinstance(g, dict):
        abort('--graph must be a JSON object with nodes, edges and optional groups.')
    nodes = g.get('nodes', [])
    edges = g.get('edges', [])
    groups = g.get('groups', [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(groups, list):
        abort('--graph nodes, edges and groups must be arrays.')
    if not nodes:
        abort('--graph has no nodes.')
    if len(nodes) > 12:
        abort(f'--graph has {len(nodes)} nodes; keep the client-level plan to 12 or fewer and move implementation detail into notes.')
    ids = set()
    for n in nodes:
        if not isinstance(n, dict):
            abort(f'each node must be an object, got: {n!r}')
        if not isinstance(n.get('id'), str) or not isinstance(n.get('label'), str):
            abort(f'node without id or label: {n}')
        n['id'], n['label'] = n['id'].strip(), n['label'].strip()
        if not n['id'] or not n['label']:
            abort(f'node without id or label: {n}')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', n['id']) or re.fullmatch(r'e\d+', n['id']):
            abort(f'node id "{n["id"]}" must use 1-64 letters, numbers, _ or - and cannot look like an edge id.')
        if len(n['label']) > 80:
            abort(f'node "{n["id"]}" label is over 80 characters; move detail into its note.')
        if n['id'] in ids:
            abort(f'duplicate node id "{n["id"]}".')
        ids.add(n['id'])
        if not isinstance(n.setdefault('kind', 'step'), str) or n['kind'] not in GRAPH_KINDS:
            abort(f'unknown kind "{n["kind"]}". Allowed: {sorted(GRAPH_KINDS)}')
        if n.get('owner') is not None and (not isinstance(n['owner'], str) or n['owner'] not in GRAPH_OWNERS):
            abort(f'unknown owner "{n["owner"]}". Allowed: {sorted(GRAPH_OWNERS)}')
        if 'note' in n and (not isinstance(n['note'], str) or not n['note'].strip()):
            abort(f'node "{n["id"]}" note must be non-empty text.')
        if len(n.get('note', '')) > 800:
            abort(f'node "{n["id"]}" note is over 800 characters.')
        if 'why' in n and (not isinstance(n['why'], str) or not n['why'].strip()):
            abort(f'node "{n["id"]}" why must be non-empty text.')
        if len(n.get('why', '')) > 400:
            abort(f'node "{n["id"]}" why is over 400 characters.')
        if 'logo' in n and (not isinstance(n['logo'], str) or not re.fullmatch(r'[a-z0-9-]+', n['logo'])):
            abort(f'node "{n["id"]}" logo must be a lowercase slug.')
        positioned = [axis in n for axis in ('x', 'y')]
        if any(positioned) and not all(positioned):
            abort(f'node "{n["id"]}" must provide both x and y, or neither.')
        if all(positioned) and any(isinstance(n[axis], bool) or not isinstance(n[axis], (int, float))
                                   or not math.isfinite(n[axis]) for axis in ('x', 'y')):
            abort(f'node "{n["id"]}" x and y must be finite numbers.')

    pairs = set()
    linked = set()
    adjacency = {node_id: [] for node_id in ids}
    indegree = {node_id: 0 for node_id in ids}
    for e in edges:
        if not isinstance(e, dict):
            abort(f'each edge must be an object, got: {e!r}')
        for side in ('from', 'to'):
            if not isinstance(e.get(side), str) or e[side] not in ids:
                abort(f'edge points at unknown node "{e.get(side)}".')
        pair = (e['from'], e['to'])
        if pair[0] == pair[1]:
            abort(f'node "{pair[0]}" cannot connect to itself.')
        if pair in pairs:
            abort(f'duplicate edge "{pair[0]}" to "{pair[1]}".')
        pairs.add(pair)
        linked.update(pair)
        adjacency[pair[0]].append(pair[1])
        indegree[pair[1]] += 1
        if 'dashed' in e and not isinstance(e['dashed'], bool):
            abort(f'edge "{pair[0]}" to "{pair[1]}" dashed must be true or false.')
        if 'label' in e and (not isinstance(e['label'], str) or not e['label'].strip()
                             or len(e['label']) > 48):
            abort(f'edge "{pair[0]}" to "{pair[1]}" label must be 1-48 characters.')
        if 'label' in e:
            e['label'] = e['label'].strip()

    if len(nodes) > 1:
        isolated = sorted(ids - linked)
        if isolated:
            abort(f'disconnected node "{isolated[0]}"; connect it or remove it from the client flow.')

    # The layout and one-shot playback both rely on a forward-moving plan.
    # Reject a loop here instead of silently drawing it in an arbitrary rank.
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node_id = ready.pop()
        visited += 1
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(nodes):
        abort('--graph contains a cycle; this client-level plan must move forward without loops.')

    grouped = set()
    group_labels = set()
    for grp in groups:
        if not isinstance(grp, dict) or not isinstance(grp.get('label'), str) or not grp['label'].strip():
            abort(f'group without label: {grp}')
        grp['label'] = grp['label'].strip()
        if len(grp['label']) > 60:
            abort(f'group label "{grp["label"]}" is over 60 characters.')
        if grp['label'] in group_labels:
            abort(f'duplicate group label "{grp["label"]}".')
        group_labels.add(grp['label'])
        members = grp.get('nodes') or []
        if not isinstance(members, list) or not members:
            abort(f'group "{grp["label"]}" must name at least one node.')
        for nid in members:
            if not isinstance(nid, str) or nid not in ids:
                abort(f'group "{grp["label"]}" names unknown node "{nid}".')
            if nid in grouped:
                abort(f'node "{nid}" belongs to more than one group.')
            grouped.add(nid)
    data = json.dumps({'nodes': nodes, 'edges': edges, 'groups': groups},
                      ensure_ascii=False)
    fallback = '\n            '.join(f'<li>{esc(n["label"])}</li>' for n in nodes)
    return data, fallback


def logos_json(nodes):
    """Only the logos this graph names, not all of them."""
    out = {}
    for slug in sorted({n.get('logo') for n in nodes if n.get('logo')}):
        f = LOGO_DIR / f'{slug}.svg'
        if not f.is_file():
            print(f'  note: no logo "{slug}", the node shows its shape only.', file=sys.stderr)
            continue
        inner = re.sub(r'^.*?<svg[^>]*>|</svg>\s*$', '', f.read_text(encoding='utf-8'), flags=re.S)
        out[slug] = re.sub(r'<title>.*?</title>', '', inner, flags=re.S).strip()
    return json.dumps(out, ensure_ascii=False)


def videos_block():
    """Your own videos from context/videos.json: [{"id", "title", "thumb"}], thumbs beside it."""
    if not VIDEOS.is_file():
        return '', ''
    cfg = json.loads(VIDEOS.read_text(encoding='utf-8'))
    cards = []
    for v in cfg.get('videos', []):
        thumb = VIDEOS.parent / v.get('thumb', '')
        img = f'<img src="{data_uri(thumb, "image/jpeg")}" alt="{esc(v["title"])}">' if thumb.is_file() else ''
        cards.append(f'<a class="yt-card" href="https://www.youtube.com/watch?v={esc(v["id"])}" '
                     f'target="_blank" rel="noopener"><span class="yt-thumb">{img}'
                     f'<span class="pin">{YT_PLAY}</span></span><p>{esc(v["title"])}</p></a>')
    return '\n        '.join(cards), cfg.get('channel', '')


def keep_or_strip(page, name, keep):
    start, end = f'<!-- {name}:start -->', f'<!-- {name}:end -->'
    if start not in page or end not in page:
        abort(f'template lost its {name} markers.')
    if keep:
        return page.replace(start, '').replace(end, '')
    return re.sub(re.escape(start) + '.*?' + re.escape(end), '', page, flags=re.S)


def fit_html(point):
    parts = [t.strip() for t in point.split('|')]
    if len(parts) >= 3:
        return (f'<li><span class="fit-num">{esc(parts[0])}</span><span class="fit-label">{esc(parts[1])}</span>'
                f'<span class="fit-ctx">{esc(" ".join(parts[2:]))}</span></li>')
    return f'<li>{FIT_ICON}<span>{esc(point)}</span></li>'


def timeline_html(text):
    if '|' not in text:
        return f'<p class="plan-body">{esc(text)}</p>'
    rows = []
    for i, step in enumerate([s.strip() for s in text.split(';;') if s.strip()], 1):
        when, _, what = step.partition('|')
        rows.append(f'<li><span class="ms-num">{i:02d}</span><span class="ms-when">{esc(when.strip())}</span>'
                    f'<span class="ms-what">{esc(what.strip())}</span></li>')
    return f'<ol class="milestones">{"".join(rows)}</ol>'


def budget_html(text):
    head, _, rest = text.partition('. ')
    if rest:
        return f'<p class="plan-lead">{esc(head.strip())}.</p><p class="plan-body">{esc(rest.strip())}</p>'
    return f'<p class="plan-body">{esc(text)}</p>'


def split_label(raw, parts, flag):
    bits = [b.strip() for b in raw.split('|')]
    if len(bits) != parts or not all(bits):
        abort(f'{flag} needs {parts} parts split by |, got: {raw!r}')
    return bits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job_id')
    ap.add_argument('--hook', required=True, help='the one headline, unmistakably about this job')
    ap.add_argument('--build-lede', required=True, help='one job-specific sentence explaining the proposed flow')
    ap.add_argument('--fit-point', action='append', required=True, help='"number|label|context", three times')
    ap.add_argument('--graph', required=True, help='the plan as JSON, or a path to it')
    ap.add_argument('--tool', action='append', required=True)
    ap.add_argument('--timeline', required=True)
    ap.add_argument('--budget', required=True)
    ap.add_argument('--kickoff', action='append', required=True)
    ap.add_argument('--loom-url', default='')
    ap.add_argument('--video-length', default='3 minute')
    ap.add_argument('--hero-illustration', default='')
    ap.add_argument('--live-artifact', action='append', default=[], help='"Label|URL" of something already built')
    ap.add_argument('--proof-link', default='', help='"Label|Detail|URL" of past work, no contact details on it')
    ap.add_argument('--next-step', default=DEFAULT_NEXT)
    ap.add_argument('--showcase', default='', help='"Title|Teaser|URL|CTA" for a sample of your work')
    ap.add_argument('--showcase-point', action='append', default=[])
    ap.add_argument('--showcase-image', default='')
    ap.add_argument('--max-reviews', type=int, default=3)
    ap.add_argument('--out')
    args = ap.parse_args(argv)

    if len(args.fit_point) != 3:
        abort(f'exactly 3 --fit-point expected, got {len(args.fit_point)}.')
    job = load_job(args.job_id)
    proof_text = PROOF.read_text(encoding='utf-8') if PROOF.is_file() else ''
    me_text = ME.read_text(encoding='utf-8') if ME.is_file() else ''
    diagram_data, diagram_fallback = build_graph(args.graph)
    url = profile_url()

    dither = data_uri(DITHER) if DITHER.is_file() else ''
    # The illustration belongs inside the plan canvas, beside the live flow.
    # A second hero block above the page repeated the same idea without adding
    # context, while the board placement makes the image part of the proposal.
    illustration_src = data_uri(args.hero_illustration) if args.hero_illustration else ''
    hero_art = ''

    live = ''
    if args.live_artifact:
        items = []
        for raw in args.live_artifact:
            label, link = split_label(raw, 2, '--live-artifact')
            items.append(f'<li><a href="{esc(link)}" target="_blank" rel="noopener">{esc(label)}'
                         f'<span class="arrow" aria-hidden="true">&rarr;</span></a></li>')
        live = ('<div class="live-artifacts"><p class="live-lede">Already built, not just drawn. '
                f'Open it yourself:</p><ul>{"".join(items)}</ul></div>')

    proof_link = ''
    if args.proof_link:
        label, detail, link = split_label(args.proof_link, 3, '--proof-link')
        proof_link = (f'<a class="proof-link" href="{esc(link)}" target="_blank" rel="noopener">'
                      f'<span class="proof-copy"><strong>{esc(label)}</strong><span>{esc(detail)}</span></span>'
                      '<span class="arrow" aria-hidden="true">→</span></a>')

    found = reviews(proof_text, args.max_reviews)
    if found:
        reviews_html = '<div class="testimonials">' + ''.join(
            f'<div class="testimonial"><p class="quote">"{esc(r["quote"])}"</p><p class="meta">'
            + (f'<span class="stars">★★★★★</span>' if r['stars'] else '')
            + f'<span class="job">{esc(r["job"])}</span></p></div>' for r in found) + '</div>'
    else:
        reviews_html = ''

    videos, channel = videos_block()
    footer = [f'<a href="{esc(url)}" target="_blank" rel="noopener">Upwork profile</a>'] if url else []
    if channel:
        footer.append(f'<a href="{esc(channel)}" target="_blank" rel="noopener">YouTube</a>')

    page = TEMPLATE.read_text(encoding='utf-8')
    page = keep_or_strip(page, 'videos', bool(videos))
    page = keep_or_strip(page, 'showcase', bool(args.showcase))
    showcase = split_label(args.showcase, 4, '--showcase') if args.showcase else ['', '', '', '']
    showcase_image = pathlib.Path(args.showcase_image) if args.showcase_image else REPORT_COVER
    if args.showcase and not showcase_image.is_file():
        abort(f'lead magnet cover "{showcase_image}" does not exist.')

    js = (DIAGRAM_JS.read_text(encoding='utf-8')
          .replace('{{LOGOS_JSON}}', logos_json(json.loads(diagram_data)['nodes']))
          .replace('{{ILLUSTRATION_SRC}}', illustration_src))
    fills = {
        '{{BODY_CLASS}}': '' if args.loom_url else 'no-video',
        '{{JOB_TITLE}}': esc(safe_job_title(job.get('title'))),
        '{{HOOK}}': esc(args.hook),
        '{{BUILD_LEDE}}': esc(args.build_lede),
        '{{HERO_ART}}': hero_art,
        '{{LOOM_URL}}': esc(args.loom_url or '#'),
        '{{VIDEO_LENGTH}}': esc(args.video_length),
        '{{FIT_POINTS}}': '\n        '.join(fit_html(p) for p in args.fit_point),
        '{{CV_BLOCK}}': cv_block(proof_text, me_text),
        '{{TOOLS}}': '\n            '.join(f'<li>{esc(t)}</li>' for t in args.tool),
        '{{TIMELINE_BLOCK}}': timeline_html(args.timeline),
        '{{BUDGET_BLOCK}}': budget_html(args.budget),
        '{{KICKOFF_ITEMS}}': '\n            '.join(f'<li>{esc(k)}</li>' for k in args.kickoff),
        '{{LIVE_ARTIFACTS}}': live,
        '{{PROOF_LINK}}': proof_link,
        '{{TESTIMONIALS_BLOCK}}': reviews_html,
        '{{VIDEOS_BLOCK}}': videos,
        '{{VIDEOS_NOTE}}': 'A few recent builds from my channel.',
        '{{CHANNEL_URL}}': esc(channel),
        '{{SHOWCASE_TITLE}}': esc(showcase[0]),
        '{{LEAD_MAGNET_TEASER}}': esc(showcase[1]),
        '{{LEAD_MAGNET_URL}}': esc(showcase[2]),
        '{{LEAD_MAGNET_CTA}}': esc(showcase[3]),
        '{{SHOWCASE_POINTS}}': ''.join(f'<li>{esc(p)}</li>' for p in args.showcase_point),
        '{{REPORT_COVER_SRC}}': data_uri(showcase_image, 'image/jpeg') if args.showcase else '',
        '{{NEXT_STEP}}': esc(args.next_step),
        '{{PROFILE_URL}}': esc(url or '#'),
        '{{FOOTER_LINKS}}': '<span class="dot">·</span>'.join(footer),
        '{{PLAN_IMG_TOOLS}}': '', '{{PLAN_IMG_TIMELINE}}': '', '{{PLAN_IMG_BUDGET}}': '', '{{PLAN_IMG_KICKOFF}}': '',
        '{{DITHER_SRC_NEXT}}': dither, '{{DITHER_SRC}}': dither,
        '{{DIAGRAM_FALLBACK}}': diagram_fallback,
    }
    for key, value in fills.items():
        page = page.replace(key, value)
    # Last, because the diagram carries user text that must never be re-scanned for placeholders.
    page = page.replace('{{DIAGRAM_DATA}}', diagram_data.replace('</', '<\\/')).replace('{{DIAGRAM_JS}}', js)
    left = sorted(set(re.findall(r'\{\{[A-Z_]+\}\}', page)))
    if left:
        abort(f'unfilled placeholders: {", ".join(left)}')

    out = pathlib.Path(args.out) if args.out else ROOT / 'jobs' / args.job_id / 'pitch.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    LIBRARY.mkdir(parents=True, exist_ok=True)
    (LIBRARY / f'{args.job_id}.json').write_text(diagram_data, encoding='utf-8')
    print(f'written: {out}  ({len(page) // 1024} KB, {len(json.loads(diagram_data)["nodes"])} diagram nodes, '
          f'{len(found)} reviews, video: {"yes" if args.loom_url else "not yet"})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
