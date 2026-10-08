#!/usr/bin/env python3
"""The diagram helpers the roadmap page draws with: a checked graph spec, its logos, escaping.

roadmap_build.py imports this. The graph spec is written by Claude from the job
posting; build_graph checks its shape before anything is drawn, and stops with the
cause rather than drawing half a diagram.
"""
import html
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'templates' / 'pitch'
DIAGRAM_JS = ASSETS / 'diagram.js'
LOGO_DIR = ASSETS / 'logos'
GRAPH_KINDS = {'source', 'step', 'sink', 'service', 'decision', 'note', 'datastore', 'milestone', 'actor'}
GRAPH_OWNERS = {'you', 'client', 'thirdparty'}


def abort(msg):
    print(f'ABORT: {msg}', file=sys.stderr)
    sys.exit(1)


def esc(text):
    return html.escape(str(text), quote=True)


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
    if len(nodes) > 20:
        abort(f'--graph has {len(nodes)} nodes; keep the client-level plan to 20 or fewer and move implementation detail into notes.')
    if groups and len(nodes) < 2 * len(groups):
        abort(f'--graph has {len(nodes)} nodes across {len(groups)} groups. One node per phase is a '
              'numbered list; give each phase at least two steps or use fewer phases.')
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
        if len(n['label']) > 69:
            abort(f'node "{n["id"]}" label is over 69 characters, which is all the renderer draws '
                  '(three lines of 23); move the detail into its note.')
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
