#!/usr/bin/env python3
"""The plan diagram as a drawing, before anyone renders it.

    python3 code/graph_sketch.py jobs/<id>/pitch-graph.json
    python3 code/graph_sketch.py jobs/<id>/pitch-graph.json --list

A one-pager's diagram is the part a client studies in the Loom, and judging it first
as a rendered page is the wrong moment: by then the page exists, and changing the flow
means building it again.

So it is drawn here, in boxes and arrows, from the same file the page is built from. An
indented list is not a diagram and cannot be judged like one: a fork that does not fork,
a step that leads nowhere and a phase with one box are all obvious in a drawing and
invisible in a list. `--list` prints the flat version when a flow is too wide to draw.
"""
import argparse
import collections
import json
import pathlib
import sys
import textwrap

KIND_MARK = {'source': '>', 'sink': '=', 'decision': '?', 'datastore': '#',
             'service': '~', 'actor': '@', 'note': '-', 'milestone': '*', 'step': '.'}
OWNER_TAG = {'client': 'client runs it', 'thirdparty': 'third party'}
INNER = 24          # characters inside a box
GAP = 3             # spaces between two boxes in a row


def load(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except OSError as error:
        sys.exit(f'ABORT: {path} could not be read: {error}')
    except json.JSONDecodeError as error:
        sys.exit(f'ABORT: {path} is not valid JSON at line {error.lineno}.')
    if not isinstance(value, dict):
        sys.exit('ABORT: the graph must be a JSON object with nodes, edges and groups.')
    return value


def read(graph):
    nodes = {str(n.get('id')): n for n in graph.get('nodes') or [] if isinstance(n, dict)}
    edges = [e for e in graph.get('edges') or [] if isinstance(e, dict)
             and str(e.get('from')) in nodes and str(e.get('to')) in nodes]
    return nodes, edges


def layers(nodes, edges):
    """Shortest path from a start: the first moment a step can happen.

    A real plan loops (a failed check goes round again) and a longest-path walk lets one
    loop drag a whole branch to the bottom, which draws a flow nobody would recognise.
    The first moment a step is reachable is the moment a reader expects to see it, so a
    loop stays what it is: an edge pointing back, listed under the drawing.
    """
    after = collections.defaultdict(list)
    incoming = collections.Counter()
    for edge in edges:
        after[str(edge['from'])].append(str(edge['to']))
        incoming[str(edge['to'])] += 1
    starts = [node for node in nodes if not incoming[node]] or [next(iter(nodes))]
    depth = {node: 0 for node in starts}
    queue = collections.deque(starts)
    while queue:
        node = queue.popleft()
        for target in after[node]:
            if target not in depth:
                depth[target] = depth[node] + 1
                queue.append(target)
    for node in nodes:                      # anything the walk never reached
        depth.setdefault(node, max(depth.values(), default=0) + 1)
    rows = collections.defaultdict(list)
    for node, level in sorted(depth.items(), key=lambda kv: (kv[1], kv[0])):
        rows[level].append(node)
    return [rows[level] for level in sorted(rows)], depth


def box(node_id, node):
    """One node as four to six lines of exactly INNER + 2 characters."""
    mark = KIND_MARK.get(str(node.get('kind')), '.')
    label = f'{mark} {node.get("label") or node_id}'
    body = textwrap.wrap(label, INNER - 2)[:3] or [label[:INNER - 2]]
    tag = OWNER_TAG.get(str(node.get('owner')))
    if tag:
        body.append(tag.rjust(INNER - 2))
    top = '+' + '-' * INNER + '+'
    return [top] + [f'| {line.ljust(INNER - 2)} |' for line in body] + [top]


def row(ids, nodes):
    """A whole layer side by side, plus the centre column of each box."""
    boxes = [box(i, nodes[i]) for i in ids]
    height = max(len(b) for b in boxes)
    boxes = [b + [' ' * (INNER + 2)] * (height - len(b)) for b in boxes]
    lines = [(' ' * GAP).join(part) for part in zip(*boxes)]
    centres = [index * (INNER + 2 + GAP) + (INNER + 2) // 2 for index in range(len(ids))]
    return lines, dict(zip(ids, centres))


def place(text, column, width):
    """One label written into a blank line at a column, kept inside the width."""
    column = max(0, min(column, width - len(text)))
    return column, text


def columns_of(nodes, edges, graph):
    """One column per phase, which is how the page itself lays the diagram out.

    Layers would be truer to the flow and unreadable in a terminal: nine layers is two
    hundred characters wide. The phases are the client-facing structure anyway, so the
    sketch and the rendered page argue about nothing.
    """
    groups = [g for g in graph.get('groups') or [] if isinstance(g, dict)]
    if groups:
        cols = [[str(i) for i in (g.get('nodes') or []) if str(i) in nodes] for g in groups]
        heads = [str(g.get('label') or f'Phase {n}') for n, g in enumerate(groups, 1)]
        placed = {i for col in cols for i in col}
        loose = [i for i in nodes if i not in placed]
        if loose:
            cols.append(loose)
            heads.append('in no phase')
        return cols, heads
    rows, _ = layers(nodes, edges)
    return rows, [f'Step {n}' for n in range(1, len(rows) + 1)]


def draw(nodes, edges, graph):
    """The whole thing left to right: phases across, their steps down inside a phase."""
    cols, heads = columns_of(nodes, edges, graph)
    boxes = {i: box(i, nodes[i]) for col in cols for i in col}
    inner_edges, cross = [], []
    for edge in edges:
        source, target = str(edge['from']), str(edge['to'])
        here = next((n for n, col in enumerate(cols) if source in col), None)
        there = next((n for n, col in enumerate(cols) if target in col), None)
        if here is not None and here == there and abs(cols[here].index(source) - cols[here].index(target)) == 1:
            inner_edges.append((source, target, edge))
        else:
            cross.append((source, target, edge, here, there))
    grid, tops = [], []
    for index, col in enumerate(cols):
        lines = [heads[index][:INNER + 2].center(INNER + 2)]
        first_box = 1
        for position, node_id in enumerate(col):
            if position:
                label = next((str(e.get('label') or '') for s, t, e in inner_edges
                              if s == col[position - 1] and t == node_id), '')
                lines.append('v'.rjust((INNER + 2) // 2 + 1).ljust(INNER + 2))
                if label:
                    lines.append(label[:INNER].center(INNER + 2))
            lines.extend(boxes[node_id])
        grid.append(lines)
        tops.append(first_box)
    height = max(len(lines) for lines in grid)
    grid = [lines + [' ' * (INNER + 2)] * (height - len(lines)) for lines in grid]
    out = []
    for row_index in range(height):
        parts = []
        for col_index, lines in enumerate(grid):
            parts.append(lines[row_index])
        # An arrow between two phases sits on the first box row of the column it leaves.
        joiner = []
        for col_index in range(len(grid) - 1):
            forward = [c for c in cross if c[3] == col_index and c[4] == col_index + 1]
            mark = ' -> ' if forward and row_index == 2 else '    '
            joiner.append(mark)
        line = parts[0]
        for col_index in range(1, len(parts)):
            line += joiner[col_index - 1] + parts[col_index]
        out.append(line.rstrip())
    jumps = []
    for source, target, edge, here, there in cross:
        if here is not None and there == here + 1:
            continue
        label = f' [{edge["label"]}]' if edge.get('label') else ''
        if here is not None and there == here:
            # Same phase, not the next box down: a second exit of a fork, or a skip.
            forward = cols[here].index(target) > cols[here].index(source)
            way = 'also down to' if forward else 'loops back to'
        elif there is not None and here is not None and there < here:
            way = 'loops back to'
        else:
            way = 'jumps ahead to'
        jumps.append(f'  {nodes[source].get("label") or source} {way} '
                     f'{nodes[target].get("label") or target}{label}')
    return out, jumps


def flat(nodes, edges, graph):
    after = collections.defaultdict(list)
    for edge in edges:
        after[str(edge['from'])].append(edge)
    lines = []
    for index, group in enumerate(graph.get('groups') or [], 1):
        lines.append(f'\nPHASE {index}: {group.get("label") or "(no label)"}')
        for node_id in [str(i) for i in group.get('nodes') or []]:
            node = nodes.get(node_id)
            if not node:
                lines.append(f'   ! {node_id} is in this phase and not in nodes')
                continue
            tag = OWNER_TAG.get(str(node.get('owner')), 'you')
            lines.append(f'   [{KIND_MARK.get(str(node.get("kind")), ".")}] '
                         f'{node.get("label") or node_id}   ({tag})')
            for edge in after.get(node_id, []):
                label = f' -- {edge["label"]}' if edge.get('label') else ''
                arrow = '..>' if edge.get('dashed') else '-->'
                lines.append(f'        {arrow} {nodes[str(edge["to"])].get("label")}{label}')
    return lines


def proofs(nodes, edges):
    out = collections.defaultdict(list)
    for edge in edges:
        out[str(edge['from'])].append(edge)
    decisions = [n for n, node in nodes.items() if str(node.get('kind')) == 'decision']
    labelled = [n for n in decisions if len(out[n]) >= 2 and all(e.get('label') for e in out[n])]
    bare = [n for n in decisions if n not in labelled]
    client = [n for n, node in nodes.items() if str(node.get('owner')) == 'client']
    questions = [n for n, node in nodes.items() if str(node.get('kind')) == 'note']
    dead = [n for n, node in nodes.items() if not out[n] and str(node.get('kind')) not in ('sink', 'note')]
    unreached = [n for n in nodes if not any(str(e.get('to')) == n for e in edges)
                 and str(nodes[n].get('kind')) != 'source']
    # A fork whose exits meet again immediately decided nothing: it draws a choice the
    # client does not have, which is worse than no fork at all.
    fake = [n for n in decisions if len(out[n]) >= 2
            and len({str(e.get('to')) for e in out[n]}) == 1]
    # The failure path is the role everybody leaves out, and it is what a client is
    # buying: one ending means nobody drew what happens when the normal path does not.
    ends = [n for n, node in nodes.items()
            if str(node.get('kind')) == 'sink' or (not out[n] and str(node.get('kind')) != 'note')]
    return labelled, bare, client, questions, dead, unreached, fake, ends


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('graph')
    ap.add_argument('--list', action='store_true', help='the flat version, for a flow too wide to draw')
    args = ap.parse_args(argv)
    graph = load(args.graph)
    nodes, edges = read(graph)
    if not nodes:
        sys.exit('ABORT: the graph has no nodes.')
    if args.list:
        print('\n'.join(flat(nodes, edges, graph)).lstrip('\n'))
    else:
        drawn, jumps = draw(nodes, edges, graph)
        print('\n'.join(drawn))
        if jumps:
            print('\nedges that skip or loop back:')
            print('\n'.join(jumps))
    labelled, bare, client, questions, dead, unreached, fake, ends = proofs(nodes, edges)
    print(f'\n{len(nodes)} nodes, {len(edges)} edges, {len(graph.get("groups") or [])} phases. '
          f'Key: > start  . step  ? fork  # store  ~ service  @ actor  * milestone  - question  = end')
    print(f'earns its place: {len(labelled)} labelled fork(s), {len(client)} node(s) the client '
          f'already runs, {len(questions)} open question(s). One of the three is enough.')
    for label, group in (('fork(s) with one exit or an unlabelled exit', bare),
                         ('fork(s) whose exits meet again straight away', fake),
                         ('step(s) that lead nowhere', dead),
                         ('node(s) nothing points at', unreached)):
        if group:
            print(f'FIX: {label}: {", ".join(nodes[n].get("label") or n for n in group)}')
    if len(ends) < 2:
        print('FIX: one ending only, so nothing shows what happens when the normal path fails. '
              'That path is the one a client is actually buying.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
