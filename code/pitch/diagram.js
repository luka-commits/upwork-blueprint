/* Diagram editor for the pitch page.
 *
 * A small node-graph editor in the shape real tools have settled on
 * (React Flow, Excalidraw, FigJam): drag nodes freely, pull an edge out of a
 * handle onto another node, select, delete, undo, snap to a grid, tidy up,
 * and a minimap for orientation. It replaces an exported image, which could
 * be neither read at phone size nor changed by the person reading it.
 *
 * Two decisions worth keeping:
 *
 * 1. One coordinate system. The viewBox always matches the stage in CSS
 *    pixels, so one SVG unit is one pixel, and every pan/zoom lives in the
 *    scene transform alone. Screen-to-world is then a subtraction and a
 *    divide, instead of also unwinding a viewBox scale.
 *
 * 2. Theme tokens are resolved once into concrete colours rather than left as
 *    var(--x) on the attributes. A re-themed page still re-themes the diagram
 *    (the values are re-read on render), and the PNG export works, which it
 *    cannot when the serialised SVG carries CSS variables out of the document.
 */
(function () {
  var host = document.getElementById('dg');
  var stage = document.getElementById('dg-stage');
  var raw = document.getElementById('dg-data');
  if (!host || !stage || !raw) return;

  var base;
  try { base = JSON.parse(raw.textContent); } catch (e) { return; }
  if (!base || !base.nodes || !base.nodes.length) return;

  var NS = 'http://www.w3.org/2000/svg';
  var NW = 184, NH = 76, GRID = 20;
  var COLS = 3, GAPX = 60, GAPY = 116;

  var ILLUS_W = 460, ILLUS_H = 0, ILLUS_GAP = 78;
  var ILLUSTRATION = '{{ILLUSTRATION_SRC}}';

  // Vom Generator eingesetzt: slug -> innerer SVG-Inhalt der Marke.
  var LOGOS = {{LOGOS_JSON}};

  var state, view = { k: 1, x: 0, y: 0 }, sel = [], edited = false, editing = false;
  var svg, scene, gGroups, gEdges, gNodes, gTemp, gAside, mini, miniView;
  var undo = [], redo = [];
  var P = {}, statusTimer = 0;

  // ---------------------------------------------------------------- helpers
  function el(n, a) {
    var e = document.createElementNS(NS, n);
    for (var k in a) if (a[k] != null) e.setAttribute(k, a[k]);
    return e;
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  // Editorial skin, after the diagram-design system (MIT, Cathryn Lavery):
  // hairline strokes, one accent, small monospace sublabels, crisp corners.
  var MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
  var HAIR = 1, HAIR_ON = 1.75, RADIUS = 6;
  function tok(name, fb) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fb;
  }
  function readTokens() {
    P = {
      card: tok('--card', '#fbf9f4'), border: tok('--border', '#e2d9c8'),
      text: tok('--text', '#262019'), muted: tok('--text-3', '#6f6656'),
      accent: tok('--accent', '#c1663e'), tint: tok('--dg-tint', '#f3e4db'),
      tintStroke: tok('--dg-tint-stroke', '#d8b69f'), edge: tok('--dg-edge', '#898276'),
      bg: tok('--bg', '#f3efe6'), bgBand: tok('--bg-band', '#ece5d7'),
      text2: tok('--text-2', '#5c5347')
    };
  }
  function snap(v) { return Math.round(v / GRID) * GRID; }
  function byId(id) {
    for (var i = 0; i < state.nodes.length; i++) if (state.nodes[i].id === id) return state.nodes[i];
    return null;
  }
  function uid(p) { return p + Math.random().toString(36).slice(2, 8); }

  function announce(message, hold) {
    var status = document.getElementById('dg-status');
    if (!status) return;
    clearTimeout(statusTimer);
    status.textContent = message;
    status.dataset.active = 'true';
    statusTimer = setTimeout(function () {
      status.dataset.active = 'false';
      updateInspector();
    }, hold || 2200);
  }

  function syncControls() {
    var undoButton = host.querySelector('[data-dg="undo"]');
    var redoButton = host.querySelector('[data-dg="redo"]');
    var deleteButton = host.querySelector('[data-dg="del"]');
    if (undoButton) undoButton.disabled = !undo.length;
    if (redoButton) redoButton.disabled = !redo.length;
    if (deleteButton) deleteButton.disabled = !sel.length;
  }

  // Greedy wrap: the node is a fixed width, so the only question is how many
  // words fit. Three lines is the cap; a fourth means it is a sentence and
  // belongs in the pitch text rather than in a box.
  function wrap(text, max) {
    var words = String(text).split(/\s+/), lines = [], cur = '';
    for (var i = 0; i < words.length; i++) {
      var t = cur ? cur + ' ' + words[i] : words[i];
      if (t.length > max && cur) { lines.push(cur); cur = words[i]; } else cur = t;
    }
    if (cur) lines.push(cur);
    if (lines.length > 3) { lines = lines.slice(0, 3); lines[2] = lines[2].slice(0, -1) + '…'; }
    return lines;
  }

  // ---------------------------------------------------------------- history
  function mark() {
    undo.push(clone(state));
    if (undo.length > 60) undo.shift();
    redo.length = 0;
    edited = true;
    reflectEdited();
    syncControls();
  }
  function doUndo() {
    if (!undo.length) { announce('Nothing to undo.'); return; }
    redo.push(clone(state)); state = undo.pop(); sel = []; render(); announce('Last change undone.');
  }
  function doRedo() {
    if (!redo.length) { announce('Nothing to redo.'); return; }
    undo.push(clone(state)); state = redo.pop(); sel = []; render(); announce('Change restored.');
  }

  function reflectEdited() {
    host.querySelectorAll('[data-dg="reset"], [data-dg="share"]').forEach(function (b) { b.hidden = !edited; });
    var hint = document.getElementById('dg-hint');
    if (hint && edited) hint.textContent = 'This is your version. Copy it and send it to me, and I will build from it.';
  }

  function reflectMode() {
    host.classList.toggle('is-editing', editing);
    host.querySelectorAll('[data-dg-editbar]').forEach(function (bar) { bar.hidden = !editing; });
    var button = host.querySelector('[data-dg="edit"]');
    if (button) {
      button.textContent = editing ? 'Done editing' : 'Edit plan';
      button.setAttribute('aria-pressed', editing ? 'true' : 'false');
    }
  }

  function updateInspector() {
    var selected = sel.length === 1 ? byId(sel[0]) : null;
    var owner = document.getElementById('dg-inspector-owner');
    var kind = document.getElementById('dg-inspector-kind');
    var title = document.getElementById('dg-inspector-title');
    var note = document.getElementById('dg-inspector-note');
    var tip = host.querySelector('.dg-inspector-tip');
    if (!owner || !kind || !title || !note) return;
    if (!selected) {
      owner.textContent = 'Plan'; kind.textContent = 'Step details'; title.textContent = 'Select any step';
      note.textContent = 'The explanation and ownership will appear here without crowding the canvas.';
      if (tip && tip.dataset.active !== 'true') tip.textContent = 'Click a step or press Tab';
      return;
    }
    owner.textContent = selected.owner === 'client' ? 'Already in place'
      : selected.owner === 'thirdparty' ? 'Third-party service' : 'Included in the build';
    kind.textContent = selected.kind || 'step';
    title.textContent = selected.label;
    note.textContent = selected.note || 'This step is included in the proposed flow. The exact setup is confirmed before build.';
    if (tip && tip.dataset.active !== 'true') tip.textContent = editing ? 'Drag to move or press Enter to rename' : 'Select another step';
  }

  function kindCue(d) {
    if (d.kind === 'source') return 'START';
    if (d.kind === 'sink') return 'OUTCOME';
    if (d.kind === 'decision') return 'DECISION';
    if (d.kind === 'milestone') return 'MILESTONE';
    return '';
  }

  function nodeAria(d) {
    var owner = d.owner === 'client' ? 'already in place'
      : d.owner === 'thirdparty' ? 'third-party service' : 'included in the build';
    return (kindCue(d) ? kindCue(d).toLowerCase() + ', ' : '') + d.label + ', ' + owner;
  }

  /* ---------------------------------------------------------------- layout
     Layered, left to right: a node's column is the longest path that reaches
     it, and everything sharing a column is stacked and centred in it. An
     implementation plan is a graph, not a chain, so the earlier index-based
     placement collided the moment a branch appeared (a nurture step landed on
     top of a service). Ranks cannot collide by construction. */
  function autoLayout() {
    var nodes = state.nodes, edges = state.edges || [], i;
    var rank = {}, incoming = {}, out = {};
    nodes.forEach(function (d) { rank[d.id] = 0; incoming[d.id] = 0; out[d.id] = []; });
    edges.forEach(function (e) {
      if (out[e.from] && rank[e.to] != null) { out[e.from].push(e.to); incoming[e.to]++; }
    });

    // Longest-path ranking, relaxed repeatedly. The iteration cap is what
    // keeps a cyclic graph from spinning instead of merely looking odd.
    for (i = 0; i < nodes.length + 2; i++) {
      var moved = false;
      edges.forEach(function (e) {
        if (rank[e.to] < rank[e.from] + 1) { rank[e.to] = rank[e.from] + 1; moved = true; }
      });
      if (!moved) break;
    }

    var cols = {};
    nodes.forEach(function (d) { (cols[rank[d.id]] = cols[rank[d.id]] || []).push(d); });

    /* One band, left to right, however deep the plan runs. Wrapping ranks into
       rows was tried and removed: it fits more on screen but sends the edges
       that cross a row boundary all the way back across the canvas, and a
       reader following an arrow backwards learns less than one who has to pan.
       Depth is handled by the view (zoom, pan, minimap), not by folding the
       graph. */
    var ROWH = NH + 44;
    var keys = Object.keys(cols).map(Number).sort(function (a, b) { return a - b; });
    var tallest = 1;
    keys.forEach(function (k) { tallest = Math.max(tallest, cols[k].length); });
    // Innerhalb eines Rangs nach Phase sortieren, sonst zerfaellt ein
    // Phasen-Rahmen in ein Band, das quer durch fremde Knoten laeuft.
    var groupOf = {};
    (state.groups || []).forEach(function (g2, gi) {
      (g2.nodes || []).forEach(function (id) { groupOf[id] = gi; });
    });
    keys.forEach(function (k) {
      cols[k].sort(function (a, b) {
        return (groupOf[a.id] == null ? 99 : groupOf[a.id]) - (groupOf[b.id] == null ? 99 : groupOf[b.id]);
      });
    });

    // Der Sketch sitzt links NEBEN dem Band, also faengt das Band erst hinter
    // ihm an. Verschoben wird beim Layout, nicht beim Zeichnen -- sonst waeren
    // Kanten, Ziehen und die Minimap gegen andere Koordinaten gerechnet.
    var xShift = ILLUSTRATION ? ILLUS_W + ILLUS_GAP : 0;
    keys.forEach(function (k, ci) {
      var col = cols[k], span = col.length;
      col.forEach(function (d, j) {
        d.x = xShift + ci * (NW + GAPX);
        d.y = (j - (span - 1) / 2) * ROWH + (tallest - 1) / 2 * ROWH;
      });
    });
  }

  function illusRect() {
    if (!ILLUSTRATION || !ILLUS_H) return null;
    var y1 = 1e9, y2 = -1e9;
    state.nodes.forEach(function (d) { y1 = Math.min(y1, d.y); y2 = Math.max(y2, d.y + NH); });
    if (y1 > y2) { y1 = 0; y2 = NH; }
    return { x: 0, y: (y1 + y2) / 2 - ILLUS_H / 2, w: ILLUS_W, h: ILLUS_H };
  }

  function bounds() {
    var b = { x1: 1e9, y1: 1e9, x2: -1e9, y2: -1e9 };
    state.nodes.forEach(function (d) {
      b.x1 = Math.min(b.x1, d.x); b.y1 = Math.min(b.y1, d.y);
      b.x2 = Math.max(b.x2, d.x + NW); b.y2 = Math.max(b.y2, d.y + NH);
    });
    var ir = illusRect();
    if (ir) {
      b.x1 = Math.min(b.x1, ir.x); b.y1 = Math.min(b.y1, ir.y);
      b.x2 = Math.max(b.x2, ir.x + ir.w); b.y2 = Math.max(b.y2, ir.y + ir.h);
    }
    if (b.x1 > b.x2) b = { x1: 0, y1: 0, x2: NW, y2: NH };
    return b;
  }

  /* ------------------------------------------------------------- shapes
     A plan drawn as one repeated rectangle makes the reader work out what
     each box is from its wording. A shape vocabulary does that work for
     them: a decision looks like a decision before it is read.

     Ownership drives the fill, and that is a sales argument rendered as
     colour rather than as a sentence: what you build is accented, what the
     client already runs is left plain, third-party services stay dashed. It
     answers "what am I actually paying for" at a glance. */
  function ownerFill(d, base) {
    if (d.owner === 'client') return P.card;
    if (d.owner === 'thirdparty') return P.card;
    return base;
  }

  function shapeFor(d, on) {
    var k = d.kind, stroke = on ? P.accent : P.border, sw = on ? HAIR_ON : HAIR, dash = null;
    var fill = P.card;

    // What you build is tinted, across every kind, not only source, sink and
    // milestone: steps and datastores are most of a real build, and leaving
    // them plain made the whole plan look monotone.
    if (d.owner !== 'client' && d.owner !== 'thirdparty') {
      fill = P.tint; if (!on) stroke = P.tintStroke;
    }
    if (k === 'service' || d.owner === 'thirdparty') dash = '5 4';
    if (d.owner === 'client' && !on) stroke = P.tintStroke;
    fill = ownerFill(d, fill);

    if (k === 'decision') {
      // Chamfered rather than a true diamond: a diamond of this width holds
      // about three words before the text spills past its edges.
      var c = 22;
      return el('path', {
        d: 'M' + c + ',0 H' + (NW - c) + ' L' + NW + ',' + (NH / 2) + ' L' + (NW - c) + ',' + NH +
           ' H' + c + ' L0,' + (NH / 2) + ' Z',
        fill: P.tint, stroke: on ? P.accent : P.tintStroke, 'stroke-width': sw
      });
    }
    if (k === 'datastore') {
      var ry = 9;
      return el('path', {
        d: 'M0,' + ry + ' a' + (NW / 2) + ',' + ry + ' 0 0 1 ' + NW + ',0 V' + (NH - ry) +
           ' a' + (NW / 2) + ',' + ry + ' 0 0 1 -' + NW + ',0 Z',
        fill: fill, stroke: stroke, 'stroke-width': sw, 'stroke-dasharray': dash
      });
    }
    if (k === 'note') {
      var f = 18;
      return el('path', {
        d: 'M0,0 H' + (NW - f) + ' L' + NW + ',' + f + ' V' + NH + ' H0 Z',
        fill: P.bgBand || P.tint, stroke: on ? P.accent : P.tintStroke,
        'stroke-width': sw, 'stroke-dasharray': dash
      });
    }
    if (k === 'milestone') {
      return el('rect', { width: NW, height: NH, rx: NH / 2,
        fill: fill, stroke: stroke, 'stroke-width': sw, 'stroke-dasharray': dash });
    }
    if (k === 'actor') {
      return el('rect', { width: NW, height: NH, rx: RADIUS * 2,
        fill: fill, stroke: stroke, 'stroke-width': sw, 'stroke-dasharray': '1 5',
        'stroke-linecap': 'round' });
    }
    return el('rect', { width: NW, height: NH, rx: RADIUS,
      fill: fill, stroke: stroke, 'stroke-width': sw, 'stroke-dasharray': dash });
  }

  // Elbow router: leave along whichever axis dominates, so a mostly-sideways
  // link exits the side and a mostly-vertical one exits the bottom.
  function edgePath(a, bn) {
    var ax = a.x + NW / 2, ay = a.y + NH / 2, bx = bn.x + NW / 2, by = bn.y + NH / 2;
    var dx = bx - ax, dy = by - ay, PAD = 9;
    if (Math.abs(dx) >= Math.abs(dy)) {
      var sx = dx > 0 ? a.x + NW : a.x, ex = dx > 0 ? bn.x - PAD : bn.x + NW + PAD;
      var mx = (sx + ex) / 2;
      return 'M' + sx + ',' + ay + ' H' + mx + ' V' + by + ' H' + ex;
    }
    var sy = dy > 0 ? a.y + NH : a.y, ey = dy > 0 ? bn.y - PAD : bn.y + NH + PAD;
    var my = (sy + ey) / 2;
    return 'M' + ax + ',' + sy + ' V' + my + ' H' + bx + ' V' + ey;
  }

  // ---------------------------------------------------------------- render
  function render(focusId) {
    if (playing) stopPlayback(true);
    readTokens();
    // Nur die eigene Zeichnung ersetzen: ein textContent='' nahm die Minimap
    // gleich mit, die als Kind der Buehne liegt.
    stage.querySelectorAll('.dg-edit, svg.dg-canvas, .dg-fallback').forEach(function (n) { n.remove(); });

    var w = stage.clientWidth || 800, h = stage.clientHeight || 380;
    svg = el('svg', { class: 'dg-canvas', viewBox: '0 0 ' + w + ' ' + h, width: w, height: h });

    var defs = el('defs');
    var pat = el('pattern', { id: 'dgGrid', width: GRID, height: GRID, patternUnits: 'userSpaceOnUse' });
    pat.appendChild(el('circle', { cx: 1, cy: 1, r: 1, fill: P.border }));
    defs.appendChild(pat);
    ['dgArrow', 'dgArrowSel'].forEach(function (id, i) {
      var m = el('marker', { id: id, viewBox: '0 0 10 10', refX: 9, refY: 5,
        markerWidth: 6.5, markerHeight: 6.5, orient: 'auto-start-reverse' });
      m.appendChild(el('path', { d: 'M0,0 L10,5 L0,10 z', fill: i ? P.accent : P.edge }));
      defs.appendChild(m);
    });
    // A soft lift off the dotted paper -- confirmed 14.08.2026 that flat
    // outlined shapes on the same dotted-cream ground read as "monotone" even
    // after the fill-tint bug (below) was fixed. A shadow gives every node
    // real visual weight regardless of its fill color, so it stops depending
    // on hue alone to separate itself from the background.
    var shadow = el('filter', { id: 'dgNodeShadow', x: '-40%', y: '-40%', width: '180%', height: '220%' });
    shadow.appendChild(el('feDropShadow', {
      dx: 0, dy: 2, stdDeviation: 3.2, 'flood-color': P.text, 'flood-opacity': 0.14
    }));
    defs.appendChild(shadow);
    svg.appendChild(defs);

    scene = el('g');
    scene.appendChild(el('rect', { x: -4000, y: -4000, width: 8000, height: 8000, fill: 'url(#dgGrid)' }));
    gGroups = el('g'); gEdges = el('g'); gNodes = el('g'); gTemp = el('g');
    // Sketch und Notizen sind Beiwerk auf dem Board: sie fangen keine Klicks,
    // damit Ziehen, Verbinden und Auswaehlen genau so bleiben wie vorher.
    gAside = el('g', { 'pointer-events': 'none' });
    scene.appendChild(gGroups); scene.appendChild(gEdges);
    scene.appendChild(gNodes); scene.appendChild(gAside); scene.appendChild(gTemp);
    svg.appendChild(scene);
    stage.insertBefore(svg, stage.firstChild);

    /* Phasen-Rahmen. Sie umfassen, was ihre Mitglieder gerade einnehmen,
       statt eine eigene gespeicherte Geometrie zu haben -- damit sitzt der
       Rahmen auch dann noch richtig, wenn der Leser einen Knoten
       herauszieht, und kann gar nicht veralten. */
    (state.groups || []).forEach(function (grp) {
      var mem = (grp.nodes || []).map(byId).filter(Boolean);
      if (!mem.length) return;
      var PADX = 22, PADT = 34, PADB = 20;
      var x1 = 1e9, y1 = 1e9, x2 = -1e9, y2 = -1e9;
      mem.forEach(function (d2) {
        x1 = Math.min(x1, d2.x); y1 = Math.min(y1, d2.y);
        x2 = Math.max(x2, d2.x + NW); y2 = Math.max(y2, d2.y + NH);
      });
      var gg = el('g');
      gg.appendChild(el('rect', {
        x: x1 - PADX, y: y1 - PADT, width: (x2 - x1) + PADX * 2, height: (y2 - y1) + PADT + PADB,
        rx: 16, fill: 'none', stroke: P.tintStroke, 'stroke-width': 1.4, 'stroke-dasharray': '2 6'
      }));
      var lw = (grp.label || '').length * 6.6 + 20;
      gg.appendChild(el('rect', { x: x1 - PADX + 12, y: y1 - PADT - 10, width: lw, height: 21,
        rx: 6, fill: P.tint, stroke: P.tintStroke, 'stroke-width': 1 }));
      var lt = el('text', { x: x1 - PADX + 22, y: y1 - PADT + 5, fill: P.text,
        'font-size': 11, 'font-weight': 600, 'font-family': MONO, 'letter-spacing': '.04em' });
      lt.textContent = grp.label || '';
      gg.appendChild(lt);
      gGroups.appendChild(gg);
    });

    (state.edges || []).forEach(function (e, i) {
      var a = byId(e.from), b = byId(e.to);
      if (!a || !b) return;
      var on = sel.indexOf('e' + i) >= 0;
      var g = el('g', { class: 'dg-edge-hit' });
      g.dataset.edge = i;
      g.appendChild(el('path', { d: edgePath(a, b), fill: 'none', stroke: 'transparent', 'stroke-width': 14 }));
      g.appendChild(el('path', {
        d: edgePath(a, b), fill: 'none', stroke: on ? P.accent : P.edge,
        'stroke-width': on ? HAIR_ON : 1.2,
        'stroke-dasharray': e.dashed ? '5 4' : null,
        'marker-end': 'url(#' + (on ? 'dgArrowSel' : 'dgArrow') + ')'
      }));
      /* The condition on the branch. Without it a fork is just two arrows and
         the reader cannot tell which case goes where, so the label was always
         part of the data format even while nothing drew it. Sits on a chip so
         it stays readable where it crosses a line. */
      if (e.label) {
        var mx = (a.x + NW / 2 + b.x + NW / 2) / 2, my = (a.y + NH / 2 + b.y + NH / 2) / 2;
        var w = e.label.length * 6.4 + 14;
        g.appendChild(el('rect', { x: mx - w / 2, y: my - 10, width: w, height: 20, rx: 6,
          fill: P.card, stroke: P.border, 'stroke-width': 1 }));
        var lt = el('text', { x: mx, y: my + 4, 'text-anchor': 'middle',
          fill: P.muted, 'font-size': 10.5, 'font-weight': 500, 'font-family': MONO });
        lt.textContent = e.label;
        g.appendChild(lt);
      }
      gEdges.appendChild(g);
    });

    state.nodes.forEach(function (d) {
      var on = sel.indexOf(d.id) >= 0;
      var g = el('g', { class: 'dg-node', transform: 'translate(' + d.x + ',' + d.y + ')',
        tabindex: 0, role: 'button', 'aria-label': nodeAria(d), 'aria-pressed': on ? 'true' : 'false' });
      g.dataset.id = d.id;
      var shape = shapeFor(d, on);
      shape.setAttribute('filter', 'url(#dgNodeShadow)');
      g.appendChild(shape);

      var hasLogo = d.logo && LOGOS[d.logo];
      var textX = hasLogo ? NW / 2 + 13 : NW / 2;
      var lines = wrap(d.label, hasLogo ? 20 : 23);
      var cue = kindCue(d);
      var t = el('text', { x: textX, y: NH / 2 - (lines.length - 1) * 8 + (cue ? 10 : 5),
        'text-anchor': 'middle', fill: P.text, 'font-size': 13, 'font-weight': 600 });
      lines.forEach(function (ln, i) {
        var ts = el('tspan', { x: textX, dy: i ? 16 : 0 });
        ts.textContent = ln;
        t.appendChild(ts);
      });
      g.appendChild(t);

      if (cue) {
        var eyebrow = el('text', { x: NW / 2, y: 17, 'text-anchor': 'middle',
          fill: on ? P.accent : P.muted, 'font-size': 9.5, 'font-weight': 700,
          'font-family': MONO, 'letter-spacing': '.08em' });
        eyebrow.textContent = cue;
        g.appendChild(eyebrow);
      }

      // The real brand mark, where one exists. A client recognises the n8n or
      // HubSpot logo before reading anything; a drawn stand-in never gets read
      // as that tool at all, so an unknown tool shows no mark rather than a
      // wrong one.
      if (hasLogo) {
        var holder = el('g', { transform: 'translate(14,' + (NH / 2 - 11) + ') scale(0.92)' });
        holder.innerHTML = LOGOS[d.logo];
        g.appendChild(holder);
      }
      // Handles: the grab points a connection is pulled from.
      [[NW, NH / 2, 'r'], [0, NH / 2, 'l'], [NW / 2, NH, 'b'], [NW / 2, 0, 't']].forEach(function (p) {
        var c = el('circle', { cx: p[0], cy: p[1], r: 5.5, fill: P.card, stroke: P.accent,
          'stroke-width': 1.6, class: 'dg-handle' });
        c.dataset.handle = p[2];
        c.dataset.id = d.id;
        g.appendChild(c);
      });
      gNodes.appendChild(g);
    });

    drawAside();
    applyView();
    drawMini();
    updateInspector();
    syncControls();
    if (focusId) {
      var target = gNodes.querySelector('[data-id="' + focusId + '"]');
      if (target) target.focus({ preventScroll: true });
    }
  }

  /* Der Sketch und die Notizzettel. Beides gehoert zum Board, beides faengt
     keine Klicks, und beides wird aus denselben Koordinaten gerechnet wie der
     Flow -- damit zoomt, pannt und exportiert es mit. */
  function drawAside() {
    var ir = illusRect();
    if (ir) {
      // Papierflaeche unter dem Sketch, sonst schwimmt eine freigestellte
      // Illustration ohne Kante auf dem gepunkteten Raster.
      gAside.appendChild(el('rect', {
        x: ir.x - 14, y: ir.y - 14, width: ir.w + 28, height: ir.h + 28, rx: 14,
        fill: P.card, stroke: P.border, 'stroke-width': 1.2, filter: 'url(#dgNodeShadow)'
      }));
      var im = el('image', { x: ir.x, y: ir.y, width: ir.w, height: ir.h,
        preserveAspectRatio: 'xMidYMid meet' });
      im.setAttributeNS('http://www.w3.org/1999/xlink', 'href', ILLUSTRATION);
      im.setAttribute('href', ILLUSTRATION);
      gAside.appendChild(im);

      var cap = el('text', { x: ir.x + ir.w / 2, y: ir.y + ir.h + 26,
        'text-anchor': 'middle', fill: P.muted, 'font-size': 10.5, 'font-weight': 500, 'font-family': MONO });
      cap.textContent = 'The short version';
      gAside.appendChild(cap);
    }

  }

  function applyView() {
    if (scene) scene.setAttribute('transform', 'translate(' + view.x + ',' + view.y + ') scale(' + view.k + ')');
    drawMiniView();
  }

  /* Fit, but never below the point where the labels stop being readable.
     A deep plan shrunk to fit is a picture of a plan rather than a plan; past
     that floor the view starts at the beginning of the flow instead, and the
     reader pans or zooms out deliberately. The minimap keeps the whole shape
     visible either way. */
  var MIN_READABLE = 1;
  function fit() {
    var b = bounds(), w = stage.clientWidth || 800, h = stage.clientHeight || 380, m = 46;
    var k = Math.min((w - m * 2) / Math.max(1, b.x2 - b.x1), (h - m * 2) / Math.max(1, b.y2 - b.y1));
    view.k = Math.min(1.6, k);
    if (view.k < MIN_READABLE) {
      view.k = MIN_READABLE;
      view.x = m - b.x1 * view.k;                       // anchor on the start
      view.y = h / 2 - ((b.y1 + b.y2) / 2) * view.k;
    } else {
      view.x = w / 2 - ((b.x1 + b.x2) / 2) * view.k;
      view.y = h / 2 - ((b.y1 + b.y2) / 2) * view.k;
    }
    applyView();
  }
  function zoom(f, cx, cy) {
    var k2 = Math.min(3, Math.max(.25, view.k * f));
    if (cx == null) { cx = stage.clientWidth / 2; cy = stage.clientHeight / 2; }
    var r = k2 / view.k;
    view.x = cx - (cx - view.x) * r; view.y = cy - (cy - view.y) * r; view.k = k2;
    applyView();
  }
  function toWorld(e) {
    var r = stage.getBoundingClientRect();
    return { x: (e.clientX - r.left - view.x) / view.k, y: (e.clientY - r.top - view.y) / view.k };
  }

  // ---------------------------------------------------------------- minimap
  function drawMini() {
    mini = document.getElementById('dg-mini');
    if (!mini) return;
    mini.textContent = '';
    var b = bounds(), pad = 30;
    var bw = (b.x2 - b.x1) + pad * 2, bh = (b.y2 - b.y1) + pad * 2;
    var m = el('svg', { viewBox: (b.x1 - pad) + ' ' + (b.y1 - pad) + ' ' + bw + ' ' + bh });
    state.nodes.forEach(function (d) {
      m.appendChild(el('rect', { x: d.x, y: d.y, width: NW, height: NH, rx: 8,
        fill: d.kind === 'service' ? 'none' : P.tintStroke, stroke: P.tintStroke, 'stroke-width': 3 }));
    });
    miniView = el('rect', { fill: 'none', stroke: P.accent, 'stroke-width': 4, rx: 6 });
    m.appendChild(miniView);
    mini.appendChild(m);
    drawMiniView();
  }
  function drawMiniView() {
    if (!miniView) return;
    var w = stage.clientWidth || 800, h = stage.clientHeight || 380;
    miniView.setAttribute('x', -view.x / view.k);
    miniView.setAttribute('y', -view.y / view.k);
    miniView.setAttribute('width', w / view.k);
    miniView.setAttribute('height', h / view.k);
  }

  // ---------------------------------------------------------------- editing
  function closeEdit(commit) {
    var inp = stage.querySelector('.dg-edit');
    if (!inp) return;
    var d = byId(inp.dataset.id), v = inp.value.trim();
    inp.remove();
    if (commit && d && v && v !== d.label) { mark(); d.label = v; render(); }
  }
  function openEdit(id) {
    closeEdit(true);
    var g = gNodes.querySelector('[data-id="' + id + '"]');
    var d = byId(id);
    if (!g || !d) return;
    var r = g.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    var inp = document.createElement('input');
    inp.className = 'dg-edit';
    inp.value = d.label;
    inp.dataset.id = id;
    inp.style.left = (r.left - sr.left) + 'px';
    inp.style.top = (r.top - sr.top + r.height / 2 - 17) + 'px';
    inp.style.width = r.width + 'px';
    stage.appendChild(inp);
    inp.focus(); inp.select();
    inp.addEventListener('keydown', function (ev) {
      ev.stopPropagation();
      if (ev.key === 'Enter') closeEdit(true);
      if (ev.key === 'Escape') closeEdit(false);
    });
    inp.addEventListener('blur', function () { closeEdit(true); });
  }

  function removeSelected() {
    if (!sel.length) { announce('Select a step or connection first.'); return; }
    var removed = sel.length;
    mark();
    var nodeIds = sel.filter(function (s) { return s.indexOf('e') !== 0 || byId(s); });
    var edgeIdx = sel.filter(function (s) { return /^e\d+$/.test(s) && !byId(s); })
      .map(function (s) { return +s.slice(1); });
    state.edges = (state.edges || []).filter(function (e, i) {
      return edgeIdx.indexOf(i) < 0 && nodeIds.indexOf(e.from) < 0 && nodeIds.indexOf(e.to) < 0;
    });
    state.nodes = state.nodes.filter(function (d) { return nodeIds.indexOf(d.id) < 0; });
    sel = [];
    render();
    announce(removed === 1 ? 'Selection deleted.' : removed + ' items deleted.');
  }

  function addNode() {
    mark();
    var b = bounds();
    var d = { id: uid('u'), label: 'Your step', kind: 'step', x: snap(b.x1), y: snap(b.y2 + 60) };
    state.nodes.push(d);
    sel = [d.id];
    render(d.id);
    announce('Step added. Press Enter to rename it.');
  }

  // ---------------------------------------------------------------- pointer
  var drag = null, conn = null, panning = null;
  /* Zwei-Finger-Zoom. Vorher gab es nur das Mausrad, also auf dem Telefon gar
     keinen Zoom -- bei einem Dokument, das Kunden ueberwiegend am Telefon
     oeffnen, ist das keine fehlende Feinheit, sondern die halbe Bedienung. */
  var touches = {}, pinch = null;
  function pinchDist() {
    var k = Object.keys(touches);
    if (k.length < 2) return null;
    var a = touches[k[0]], b = touches[k[1]];
    return { d: Math.hypot(a.x - b.x, a.y - b.y),
             cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
  }

  stage.addEventListener('pointerdown', function (e) {
    touches[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (Object.keys(touches).length === 2) {
      drag = null; panning = null; conn = null;
      pinch = pinchDist();
      pinch.k = view.k;
      return;
    }
    closeEdit(true);
    var handle = e.target.closest('.dg-handle');
    var node = e.target.closest('.dg-node');
    var edge = e.target.closest('.dg-edge-hit');
    stage.setPointerCapture(e.pointerId);

    if (editing && handle) {                       // pull a new connection
      conn = { from: handle.dataset.id, to: null };
      conn.line = el('path', { fill: 'none', stroke: P.accent, 'stroke-width': 2,
        'stroke-dasharray': '5 4', 'marker-end': 'url(#dgArrowSel)' });
      gTemp.appendChild(conn.line);
      return;
    }
    if (node) {
      var id = node.dataset.id;
      if (!editing) { sel = [id]; render(id); return; }
      if (e.shiftKey) { if (sel.indexOf(id) < 0) sel.push(id); }
      else if (sel.indexOf(id) < 0) sel = [id];
      var start = toWorld(e);
      drag = { x: start.x, y: start.y, moved: false,
        origin: sel.map(function (s) { var d = byId(s); return d ? { id: s, x: d.x, y: d.y } : null; }).filter(Boolean) };
      render(id);
      return;
    }
    if (editing && edge) { sel = ['e' + edge.dataset.edge]; render(); return; }

    sel = [];
    panning = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    stage.dataset.drag = 'true';
    render();
  });

  stage.addEventListener('pointermove', function (e) {
    if (touches[e.pointerId]) { touches[e.pointerId].x = e.clientX; touches[e.pointerId].y = e.clientY; }
    if (pinch) {
      var now = pinchDist();
      if (now && pinch.d > 0) {
        var r = stage.getBoundingClientRect();
        var target = Math.min(3, Math.max(.25, pinch.k * (now.d / pinch.d)));
        var f = target / view.k;
        var cx = now.cx - r.left, cy = now.cy - r.top;
        view.x = cx - (cx - view.x) * f;
        view.y = cy - (cy - view.y) * f;
        view.k = target;
        applyView();
      }
      return;
    }
    if (conn) {
      var a = byId(conn.from), p = toWorld(e);
      if (a) conn.line.setAttribute('d', 'M' + (a.x + NW / 2) + ',' + (a.y + NH / 2) + ' L' + p.x + ',' + p.y);
      var over = e.target.closest('.dg-node');
      conn.to = over && over.dataset.id !== conn.from ? over.dataset.id : null;
      return;
    }
    if (drag) {
      var w = toWorld(e), dx = w.x - drag.x, dy = w.y - drag.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        if (!drag.moved) { drag.moved = true; mark(); }
        drag.origin.forEach(function (o) {
          var d = byId(o.id);
          if (d) { d.x = snap(o.x + dx); d.y = snap(o.y + dy); }
        });
        // move only the affected groups rather than rebuilding the whole scene
        drag.origin.forEach(function (o) {
          var g = gNodes.querySelector('[data-id="' + o.id + '"]'), d = byId(o.id);
          if (g && d) g.setAttribute('transform', 'translate(' + d.x + ',' + d.y + ')');
        });
        redrawEdges();
        if (state.groups && state.groups.length) render();
      }
      return;
    }
    if (panning) {
      view.x = panning.vx + (e.clientX - panning.x);
      view.y = panning.vy + (e.clientY - panning.y);
      applyView();
    }
  });

  function redrawEdges() {
    (state.edges || []).forEach(function (e, i) {
      var g = gEdges.querySelector('[data-edge="' + i + '"]');
      var a = byId(e.from), b = byId(e.to);
      if (!g || !a || !b) return;
      var d = edgePath(a, b);
      g.childNodes.forEach(function (p) { p.setAttribute('d', d); });
    });
    drawMini();
  }

  stage.addEventListener('pointerup', function (e) {
    delete touches[e.pointerId];
    if (Object.keys(touches).length < 2) pinch = null;
    if (conn) {
      if (conn.to) {
        mark();
        state.edges = state.edges || [];
        state.edges.push({ from: conn.from, to: conn.to });
      }
      conn.line.remove(); conn = null; render();
    }
    if (drag && drag.moved) drawMini();
    drag = null; panning = null; stage.dataset.drag = 'false';
  });
  stage.addEventListener('pointercancel', function (e) {
    delete touches[e.pointerId]; pinch = null;
    if (conn) { conn.line.remove(); conn = null; }
    drag = null; panning = null; stage.dataset.drag = 'false';
  });

  stage.addEventListener('dblclick', function (e) {
    var node = e.target.closest('.dg-node');
    if (editing && node) openEdit(node.dataset.id);
  });

  stage.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = stage.getBoundingClientRect();
    zoom(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  // ---------------------------------------------------------------- keyboard
  function nearestNode(id, key) {
    var current = byId(id);
    if (!current) return null;
    var cx = current.x + NW / 2, cy = current.y + NH / 2;
    var best = null, bestScore = Infinity;
    state.nodes.forEach(function (candidate) {
      if (candidate.id === id) return;
      var dx = candidate.x + NW / 2 - cx, dy = candidate.y + NH / 2 - cy;
      var valid = key === 'ArrowRight' ? dx > 1 : key === 'ArrowLeft' ? dx < -1
        : key === 'ArrowDown' ? dy > 1 : dy < -1;
      if (!valid) return;
      var primary = key === 'ArrowRight' || key === 'ArrowLeft' ? Math.abs(dx) : Math.abs(dy);
      var secondary = key === 'ArrowRight' || key === 'ArrowLeft' ? Math.abs(dy) : Math.abs(dx);
      var score = primary + secondary * 0.45;
      if (score < bestScore) { bestScore = score; best = candidate; }
    });
    return best;
  }

  stage.addEventListener('focusin', function (e) {
    var node = e.target.closest && e.target.closest('.dg-node');
    if (!node) return;
    var id = node.dataset.id;
    if (sel.length !== 1 || sel[0] !== id) { sel = [id]; render(id); }
  });

  document.addEventListener('keydown', function (e) {
    if (/^(INPUT|TEXTAREA)$/.test((e.target.tagName || ''))) return;
    var inView = host.contains(document.activeElement) || host.matches(':hover') ||
                 host.classList.contains('dg-full') || document.fullscreenElement === host;
    if (!inView) return;
    var focusedNode = e.target.closest && e.target.closest('.dg-node');
    if (focusedNode && /^Arrow(Left|Right|Up|Down)$/.test(e.key)) {
      e.preventDefault();
      var next = nearestNode(focusedNode.dataset.id, e.key);
      if (next) { sel = [next.id]; render(next.id); }
    } else if (focusedNode && (e.key === 'Enter' || e.key === 'F2')) {
      e.preventDefault();
      sel = [focusedNode.dataset.id];
      if (editing) openEdit(focusedNode.dataset.id); else updateInspector();
    } else if (focusedNode && e.key === ' ') {
      e.preventDefault(); sel = [focusedNode.dataset.id]; updateInspector();
    } else if (editing && (e.key === 'Delete' || e.key === 'Backspace')) { e.preventDefault(); removeSelected(); }
    else if (editing && (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault(); e.shiftKey ? doRedo() : doUndo();
    } else if (e.key === 'Escape') {
      if (host.classList.contains('dg-full')) host.classList.remove('dg-full');
      sel = []; render();
    }
  });

  /* ---------------------------------------------------------------- play
     One lead walking the path, once. A static plan asks the reader to
     simulate it in their head; this shows the thing running, which is the
     moment a diagram stops being documentation and starts being a promise.
     It follows the real edge paths, so it can never drift from the drawing.

     Deliberately not looping: a permanent moving dot competes with the copy
     for attention, and the point is made after one pass. */
  var playing = null;
  function setPlayState(running) {
    var button = host.querySelector('[data-dg="play"]');
    if (!button) return;
    button.setAttribute('aria-pressed', running ? 'true' : 'false');
    button.textContent = running ? '\u25a0 Stop' : '\u25b6 Run flow';
  }

  function stopPlayback(silent) {
    if (!playing) return;
    cancelAnimationFrame(playing.raf);
    (playing.dots || []).forEach(function (dot) { if (dot.parentNode) dot.remove(); });
    (playing.paths || []).forEach(function (path) { if (path.parentNode) path.remove(); });
    (playing.visuals || []).forEach(function (visual) {
      visual.node.setAttribute('stroke', visual.stroke);
      visual.node.setAttribute('stroke-width', visual.width);
    });
    playing = null;
    setPlayState(false);
    if (!silent) announce('Playback stopped.');
  }

  function playFlow() {
    if (playing) { stopPlayback(false); return; }
    var edges = state.edges || [];
    if (!edges.length) { announce('Connect at least two steps to run the flow.'); return; }
    var indegree = {}, outgoing = {}, readyAt = {};
    state.nodes.forEach(function (node) {
      indegree[node.id] = 0; outgoing[node.id] = []; readyAt[node.id] = 0;
    });
    edges.forEach(function (edge, index) {
      if (!outgoing[edge.from] || indegree[edge.to] == null) return;
      outgoing[edge.from].push({ edge: edge, index: index });
      indegree[edge.to]++;
    });
    var starts = state.nodes.filter(function (d2) {
      return indegree[d2.id] === 0;
    });
    if (!starts.length) { announce('This flow has a loop and no starting step.'); return; }

    /* Build a topological schedule. Every root starts together, sibling
       branches run together, and a merged path waits until all incoming work
       has arrived. One serialized dot would tell the wrong story for both a
       multi-source plan and a real fork. */
    var queue = starts.map(function (node) { return node.id; });
    var segments = [], paths = [], visuals = [], SPEED = 320, head = 0;
    while (head < queue.length) {
      var id = queue[head++];
      outgoing[id].forEach(function (item) {
        var a = byId(item.edge.from), b = byId(item.edge.to);
        if (!a || !b) return;
        var path = el('path', { d: edgePath(a, b), fill: 'none', stroke: 'none' });
        gTemp.appendChild(path);
        paths.push(path);
        var duration = Math.max(420, path.getTotalLength() / SPEED * 1000);
        segments.push({ path: path, edge: item, start: readyAt[id], duration: duration, dot: null, done: false });
        readyAt[item.edge.to] = Math.max(readyAt[item.edge.to], readyAt[id] + duration);
        indegree[item.edge.to]--;
        if (indegree[item.edge.to] === 0) queue.push(item.edge.to);
      });
    }
    if (segments.length !== edges.length) {
      paths.forEach(function (path) { path.remove(); });
      announce('This edited flow contains a loop. Remove it before playback.');
      return;
    }

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      paths.forEach(function (path) { path.remove(); });
      announce('Flow ready: ' + starts.length + ' starting ' + (starts.length === 1 ? 'point' : 'points') +
        ' connect through ' + edges.length + ' paths.', 3200);
      return;
    }

    setPlayState(true);
    var totalDuration = segments.reduce(function (longest, segment) {
      return Math.max(longest, segment.start + segment.duration);
    }, 0);
    announce('Running ' + starts.length + ' starting ' + (starts.length === 1 ? 'point' : 'points') +
      ' through ' + edges.length + ' connections.', totalDuration + 1000);
    var t0 = null, dots = [];

    function step(ts) {
      if (!t0) t0 = ts;
      var elapsed = ts - t0, finished = 0;
      segments.forEach(function (segment) {
        if (elapsed < segment.start) return;
        if (elapsed >= segment.start + segment.duration) {
          if (!segment.done) {
            segment.done = true;
            if (segment.dot) segment.dot.remove();
            var completedVisual = gEdges.querySelector('[data-edge="' + segment.edge.index + '"] path:nth-of-type(2)');
            if (completedVisual) {
              completedVisual.setAttribute('stroke', P.edge);
              completedVisual.setAttribute('stroke-width', 1.2);
            }
          }
          finished++;
          return;
        }
        if (!segment.dot) {
          segment.dot = el('circle', { r: 6, fill: P.accent, opacity: .96, 'pointer-events': 'none' });
          dots.push(segment.dot); gTemp.appendChild(segment.dot);
          var visual = gEdges.querySelector('[data-edge="' + segment.edge.index + '"] path:nth-of-type(2)');
          if (visual) {
            visuals.push({ node: visual, stroke: visual.getAttribute('stroke'), width: visual.getAttribute('stroke-width') });
            visual.setAttribute('stroke', P.accent); visual.setAttribute('stroke-width', HAIR_ON);
          }
        }
        var progress = (elapsed - segment.start) / segment.duration;
        var len = segment.path.getTotalLength();
        var pt = segment.path.getPointAtLength(len * progress);
        segment.dot.setAttribute('cx', pt.x); segment.dot.setAttribute('cy', pt.y);
      });
      if (finished === segments.length) {
        stopPlayback(true);
        announce('Flow complete: ' + starts.length + ' starting ' + (starts.length === 1 ? 'point' : 'points') +
          ', ' + edges.length + ' connections.', 3200);
        return;
      }
      playing.raf = requestAnimationFrame(step);
    }
    playing = { dots: dots, paths: paths, visuals: visuals, raf: requestAnimationFrame(step) };
  }

  // ---------------------------------------------------------------- export
  function exportPNG() {
    var b = bounds(), pad = 40, scale = 2;
    var w = (b.x2 - b.x1) + pad * 2, h = (b.y2 - b.y1) + pad * 2;
    var out = svg.cloneNode(true);
    out.setAttribute('viewBox', (b.x1 - pad) + ' ' + (b.y1 - pad) + ' ' + w + ' ' + h);
    out.setAttribute('width', w); out.setAttribute('height', h);
    var sc = out.querySelector('g');
    sc.setAttribute('transform', '');                       // export the diagram, not the view
    sc.querySelector('rect').setAttribute('fill', P.card);  // grid rect becomes the page
    out.querySelectorAll('.dg-handle').forEach(function (n) { n.remove(); });
    var s = new XMLSerializer().serializeToString(out);
    var img = new Image();
    img.onload = function () {
      var c = document.createElement('canvas');
      c.width = w * scale; c.height = h * scale;
      var cx = c.getContext('2d');
      cx.fillStyle = P.card; cx.fillRect(0, 0, c.width, c.height);
      cx.drawImage(img, 0, 0, c.width, c.height);
      var a = document.createElement('a');
      a.download = 'proposed-build.png';
      a.href = c.toDataURL('image/png');
      a.click();
    };
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(s)));
  }

  // ---------------------------------------------------------------- toolbar
  host.addEventListener('click', function (e) {
    var b = e.target.closest('[data-dg]');
    if (!b) return;
    var a = b.dataset.dg;
    if (e.detail === 0) {
      host.classList.add('dg-instant');
      requestAnimationFrame(function () { host.classList.remove('dg-instant'); });
    }
    if (a === 'edit') {
      editing = !editing; reflectMode(); updateInspector();
      announce(editing ? 'Editing on. Select a step, then press Enter to rename it.' : 'Editing finished.');
    }
    else if (a === 'in') { zoom(1.25); announce('Zoom ' + Math.round(view.k * 100) + '%.'); }
    else if (a === 'out') { zoom(1 / 1.25); announce('Zoom ' + Math.round(view.k * 100) + '%.'); }
    else if (a === 'fit') { fit(); announce('View returned to the start of the flow.'); }
    else if (a === 'add') addNode();
    else if (a === 'del') removeSelected();
    else if (a === 'undo') doUndo();
    else if (a === 'redo') doRedo();
    else if (a === 'tidy') { mark(); autoLayout(); render(); fit(); announce('Steps tidied into phases.'); }
    else if (a === 'png') { exportPNG(); announce('Preparing the PNG download.'); }
    else if (a === 'play') playFlow();
    else if (a === 'reset') {
      state = clone(base); autoLayout(); sel = []; undo = []; redo = [];
      edited = false; reflectEdited();
      var hint = document.getElementById('dg-hint');
      if (hint) hint.textContent = 'Drag steps, pull a dot to connect, double-click to rename.';
      history.replaceState(null, '', location.pathname + location.search);
      render(); fit();
      announce('Original plan restored.');
    } else if (a === 'share') {
      var payload = btoa(unescape(encodeURIComponent(JSON.stringify(state))));
      var url = location.href.split('#')[0] + '#d=' + payload;
      location.hash = 'd=' + payload;
      var original = b.textContent;
      b.textContent = 'Copying...';
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () {
          b.textContent = 'Link copied';
          announce('Link copied. Send it here on Upwork.');
          setTimeout(function () { b.textContent = original; }, 2200);
        }).catch(function () {
          b.textContent = 'Copy blocked';
          announce('Copy was blocked. Copy the page address from your browser.', 4000);
          setTimeout(function () { b.textContent = original; }, 3000);
        });
      } else {
        b.textContent = 'Copy blocked';
        announce('Copy is unavailable here. Copy the page address from your browser.', 4000);
        setTimeout(function () { b.textContent = original; }, 3000);
      }
    } else if (a === 'full') {
      if (document.fullscreenElement) { document.exitFullscreen(); }
      else if (host.requestFullscreen) {
        host.requestFullscreen().catch(function () { host.classList.toggle('dg-full'); });
      } else host.classList.toggle('dg-full');
      setTimeout(function () { render(); fit(); }, 120);
    }
  });

  var rt = 0;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(function () { render(); }, 150);
  });
  document.addEventListener('fullscreenchange', function () { setTimeout(function () { render(); fit(); }, 60); });

  // ---------------------------------------------------------------- boot
  (function boot() {
    var m = location.hash.match(/d=([^&]+)/);
    if (m) {
      try {
        state = JSON.parse(decodeURIComponent(escape(atob(m[1]))));
        edited = true;
        var bn = document.createElement('div');
        bn.className = 'dg-banner';
        bn.textContent = 'You are looking at an edited version of this diagram.';
        host.insertBefore(bn, stage);
      } catch (err) { state = clone(base); }
    } else state = clone(base);

    if (!state.edges) {          // a plain chain is the default reading order
      state.edges = [];
      var mains = state.nodes.filter(function (d) { return d.kind !== 'service'; });
      for (var i = 0; i < mains.length - 1; i++) state.edges.push({ from: mains[i].id, to: mains[i + 1].id });
      state.nodes.filter(function (d) { return d.kind === 'service'; }).forEach(function (s) {
        var at = mains[Math.min(s.at != null ? s.at : 1, mains.length - 1)];
        if (at) state.edges.push({ from: at.id, to: s.id, dashed: true });
      });
    }
    if (state.nodes.some(function (d) { return d.x == null; })) autoLayout();
    var first = state.nodes.filter(function (d) { return d.kind === 'source'; })[0] || state.nodes[0];
    if (!sel.length && first) sel = [first.id];
    reflectEdited(); reflectMode();
    render();
    fit();

    /* Die Hoehe des Sketches kommt aus dem Bild selbst, nicht aus einer im
       Generator mitgeschriebenen Zahl -- die waere beim naechsten Austausch
       des Bildes still falsch. Bis das Bild geladen ist, rechnet das Layout
       ohne es; danach einmal neu setzen. */
    if (ILLUSTRATION) {
      var probe = new Image();
      probe.onload = function () {
        ILLUS_H = Math.round(ILLUS_W * (probe.naturalHeight / probe.naturalWidth));
        render();
        fit();
      };
      probe.src = ILLUSTRATION;
    }
  })();
})();
