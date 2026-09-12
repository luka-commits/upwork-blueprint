'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  COLS, GROUPS, Icon, LABEL, ORDER, SPACES, STAGES,
  DueChip, Score, View, Filter, ago, budgetText, clientText,
  describeFilter, filterActive, isDue, todoBucket,
} from '@/lib/model';
import { useCockpit } from '@/lib/context';

type SpaceName = 'jobs';
type SpaceState = { view: View; saved: View[] };
type SpacesState = Partial<Record<SpaceName, SpaceState>>;
type Menu = 'views' | 'filters' | 'columns' | null;

const PAGE = 50;
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

function S(spaces: SpacesState, space: SpaceName): SpaceState {
  const sp = SPACES[space];
  const st = spaces[space] || (spaces[space] = { view: clone(sp.presets[0]), saved: [] });
  const v = st.view;
  v.cols = (v.cols || []).filter(c => sp.cols.includes(c));
  if (!v.cols.includes('job')) v.cols.splice(1, 0, 'job');
  v.filters = Object.fromEntries(Object.entries(v.filters || {}).filter(([k]) => COLS[k] && COLS[k].filter));
  v.widths = v.widths || {};
  if (!sp.board) v.layout = 'list';
  return st;
}

function saveSpaces(spaces: SpacesState) {
  try { localStorage.setItem('cockpit-spaces', JSON.stringify(spaces)); } catch { /* The list still works when storage is unavailable. */ }
}

function viewSource(st: SpaceState, space: SpaceName) {
  return [...SPACES[space].presets, ...st.saved].find(x => x.name === st.view.name);
}

function edited(st: SpaceState, space: SpaceName) {
  const src = viewSource(st, space);
  if (!src) return true;
  const strip = (o: View) => JSON.stringify({ ...o, name: undefined, query: undefined });
  return strip(src) !== strip(st.view);
}

function byUrgency(a: any, b: any) {
  return (Number(isDue(b)) - Number(isDue(a))) || (b.score || 0) - (a.score || 0);
}

export default function ListPage({ space }: { space: SpaceName }) {
  const { state, move, toast, load, drawerId, openDrawer, closeDrawer } = useCockpit();
  const spacesRef = useRef<SpacesState>({});
  const hydrated = useRef(false);
  const resizing = useRef<{ id: string; x: number; w: number; now?: number; grip: HTMLElement } | null>(null);
  const dragCol = useRef<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [st, setSt] = useState<SpaceState>(() => S({}, space));
  const [menu, setMenu] = useState<Menu>(null);
  const [colFilter, setColFilter] = useState<string | null>(null);
  const [optSearch, setOptSearch] = useState('');
  const [viewName, setViewName] = useState('');
  const [queryInput, setQueryInput] = useState(st.view.query);
  const [pageNo, setPageNo] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dropCol, setDropCol] = useState<{ id: string; after: boolean } | null>(null);
  const [dropStage, setDropStage] = useState<string | null>(null);
  const [liveWidth, setLiveWidth] = useState<{ id: string; width: number } | null>(null);

  useEffect(() => {
    let spaces: SpacesState = {};
    try { spaces = JSON.parse(localStorage.getItem('cockpit-spaces') || '{}') || {}; } catch { spaces = {}; }
    // A link like /?view=Clients opens that ready-made view, for example the way back from a client page.
    const wanted = SPACES[space].presets.find(p => p.name === new URLSearchParams(window.location.search).get('view'));
    if (wanted) spaces[space] = { view: clone(wanted), saved: spaces[space]?.saved || [] };
    try {
      const next = S(spaces, space);
      spacesRef.current = spaces;
      hydrated.current = true;
      setSt(clone(next));
      setQueryInput(next.view.query || '');
    } catch {
      spaces = {};
      const next = S(spaces, space);
      spacesRef.current = spaces;
      hydrated.current = true;
      setSt(clone(next));
      setQueryInput(next.view.query || '');
    }
  }, [space]);

  useEffect(() => {
    setSelected(new Set());
    setPageNo(0);
    setMenu(null);
    setColFilter(null);
  }, [space]);

  useEffect(() => {
    const click = (event: MouseEvent) => {
      const target = event.target as Element | null;
      if (!target?.closest('.menu, [data-open-colfilter]')) {
        setMenu(null);
        setColFilter(null);
      }
    };
    const key = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || (!menu && !colFilter)) return;
      event.preventDefault();
      setMenu(null);
      setColFilter(null);
    };
    document.addEventListener('click', click);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('click', click);
      document.removeEventListener('keydown', key);
    };
  }, [menu, colFilter]);

  const update = (change: (draft: SpaceState) => void) => {
    setSt(current => {
      const next = clone(current);
      change(next);
      S({ [space]: next }, space);
      const holder = spacesRef.current;
      holder[space] = next;
      if (hydrated.current) saveSpaces(holder);
      return next;
    });
  };

  const closePops = () => {
    setMenu(null);
    setColFilter(null);
    setOptSearch('');
  };

  const toggleMenu = (next: Exclude<Menu, null>) => {
    if (menu === next) return closePops();
    setMenu(next);
    if (next !== 'filters') setColFilter(null);
    setOptSearch('');
    if (next === 'views') setViewName(edited(st, space) ? '' : (st.view.name || ''));
  };

  const applyView = (next: View) => {
    update(draft => { draft.view = clone(next); });
    setQueryInput(next.query || '');
    closePops();
  };

  const saveView = () => {
    const name = viewName.trim();
    if (!name) return rootRef.current?.querySelector<HTMLInputElement>('#viewName')?.focus();
    update(draft => {
      draft.view.name = name;
      draft.saved = draft.saved.filter(x => x.name !== name).concat(clone(draft.view));
    });
    closePops();
    toast(`View "${name}" saved.`);
  };

  const passes = (j: any, except?: string) => {
    const v = st.view;
    if (!SPACES[space].base(j)) return false;
    for (const [id, f] of Object.entries(v.filters)) {
      if (id === except || !filterActive(f)) continue;
      const val = COLS[id].value!(j);
      if (f.kind === 'multi') {
        const vals = (Array.isArray(val) ? val : [val]).map(String);
        if (!vals.some(x => f.values.includes(x))) return false;
      } else {
        if (val == null) return false;
        if (f.min != null && val < f.min) return false;
        if (f.max != null && val > f.max) return false;
      }
    }
    if (v.query && except !== '__query') {
      const hay = [j.title, j.summary, j.rationale, j.notes, j.trap, (j.client || {}).country, ...(j.tasks || []).map((t: any) => t.text)].join(' ').toLowerCase();
      if (!v.query.toLowerCase().split(/\s+/).every(word => hay.includes(word))) return false;
    }
    return true;
  };

  const sorted = (jobs: any[]) => {
    const sort = st.view.sort;
    if (!sort || !COLS[sort.id]) {
      return jobs.sort(byUrgency);
    }
    const value = COLS[sort.id].sort;
    const direction = sort.desc ? -1 : 1;
    return jobs.sort((a, b) => {
      const x = value(a), y = value(b);
      return (x < y ? -1 : x > y ? 1 : 0) * direction;
    });
  };

  const jobs = useMemo(() => sorted((state?.jobs || []).filter((j: any) => passes(j))), [state, st, space]);
  const all = (state?.jobs || []).filter((j: any) => SPACES[space].base(j)).length;
  const pages = Math.max(1, Math.ceil(jobs.length / PAGE));
  const page = Math.min(pageNo, pages - 1);
  const shown = jobs.slice(page * PAGE, (page + 1) * PAGE);
  const shownIds = shown.map((j: any) => String(j.id));
  const noun = 'job';
  const dueNow = (state?.jobs || []).filter((j: any) => todoBucket(j) === 'Due now').length;
  const activeFilters = Object.entries(st.view.filters).filter(([, f]) => filterActive(f));

  useEffect(() => {
    if (pageNo >= pages) setPageNo(pages - 1);
  }, [pageNo, pages]);

  const chooseLayout = (layout: 'list' | 'board') => {
    update(draft => { draft.view.layout = layout; });
    closePops();
  };

  const toggleSort = (id: string) => {
    update(draft => {
      const first = !COLS[id].asc;
      const sort = draft.view.sort;
      if (!sort || sort.id !== id) draft.view.sort = { id, desc: first };
      else if (sort.desc === first) draft.view.sort = { id, desc: !first };
      else draft.view.sort = null;
    });
  };

  const openFilter = (id: string) => {
    if (menu === 'filters' && colFilter === id) return closePops();
    setMenu('filters');
    setColFilter(id);
    setOptSearch('');
  };

  const reorder = (fromId: string, targetId: string) => {
    if (fromId === targetId) return;
    update(draft => {
      const cols = draft.view.cols;
      const from = cols.indexOf(fromId);
      if (from < 0) return;
      cols.splice(from, 1);
      const target = cols.indexOf(targetId);
      const to = target + (from <= target ? 1 : 0);
      cols.splice(to, 0, fromId);
    });
  };

  const columnDragStart = (event: React.DragEvent, id: string) => {
    if (resizing.current) return event.preventDefault();
    dragCol.current = id;
    event.dataTransfer.setData('text/col', id);
    event.dataTransfer.effectAllowed = 'move';
  };

  const columnDragOver = (event: React.DragEvent, id: string) => {
    const from = dragCol.current;
    if (!from || from === id) return;
    event.preventDefault();
    setDropCol({ id, after: st.view.cols.indexOf(from) < st.view.cols.indexOf(id) });
  };

  const columnDrop = (event: React.DragEvent, id: string) => {
    const from = dragCol.current || event.dataTransfer.getData('text/col');
    if (!from) return;
    event.preventDefault();
    reorder(from, id);
    dragCol.current = null;
    setDropCol(null);
  };

  const columnDragEnd = () => {
    dragCol.current = null;
    setDropCol(null);
  };

  const resizeStart = (event: React.PointerEvent<HTMLSpanElement>, id: string) => {
    event.preventDefault();
    event.stopPropagation();
    const grip = event.currentTarget;
    const th = grip.closest('th');
    if (!th) return;
    resizing.current = { id, x: event.clientX, w: th.getBoundingClientRect().width, grip };
    grip.classList.add('active');
    grip.setPointerCapture(event.pointerId);
  };

  useEffect(() => {
    const pointerMove = (event: PointerEvent) => {
      const r = resizing.current;
      if (!r) return;
      const width = Math.max(56, Math.min(720, Math.round(r.w + event.clientX - r.x)));
      r.now = width;
      setLiveWidth({ id: r.id, width });
    };
    const pointerUp = () => {
      const r = resizing.current;
      if (!r) return;
      r.grip.classList.remove('active');
      if (r.now) update(draft => { draft.view.widths[r.id] = r.now!; });
      setLiveWidth(null);
      setTimeout(() => { resizing.current = null; }, 0);
    };
    window.addEventListener('pointermove', pointerMove);
    window.addEventListener('pointerup', pointerUp);
    return () => {
      window.removeEventListener('pointermove', pointerMove);
      window.removeEventListener('pointerup', pointerUp);
    };
  });

  const openRow = (id: string) => drawerId === id ? closeDrawer() : openDrawer(id);

  const rowClick = (event: React.MouseEvent<HTMLTableRowElement>, id: string) => {
    const target = event.target as Element;
    if (target.closest('a, button, select, input, label, .sel-cell')) return;
    openRow(id);
  };

  const rowKey = (event: React.KeyboardEvent, id: string) => {
    if (event.target !== event.currentTarget) return;
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    openDrawer(id);
  };

  const bulkMove = async (status: string) => {
    if (!status) return;
    const ids = [...selected];
    for (const id of ids) {
      await move(id, status, status === 'applied' ? '+3d' : null, status === 'skipped' ? 'not a fit' : null);
    }
    setSelected(new Set());
    toast(`${ids.length} moved to ${LABEL[status]}.`);
    await load();
  };

  if (!state) return null;

  const tracker = state.tracker || {};

  return <div ref={rootRef}>
    {space === 'jobs' && tracker.goal ? <>
      <div className="today"><span className="today-lbl">Applications today</span><span className="today-n"><b>{tracker.done}</b> <span>/ {tracker.goal}</span></span>
        <span className="today-meta">{tracker.streak}-day streak · {tracker.week_done} this week</span></div>
      <div className="today-bar"><span style={{ width: `${Math.min(100, 100 * tracker.done / tracker.goal)}%` }} /></div>
    </> : null}

    <div className="toolbar">
      {SPACES[space].board ? <div className="seg" role="group" aria-label="Layout">
        <button onClick={() => chooseLayout('list')} aria-pressed={st.view.layout === 'list'}>List</button>
        <button onClick={() => chooseLayout('board')} aria-pressed={st.view.layout === 'board'}>Board</button>
      </div> : null}

      <div className="menu" id="menu-views">
        <button className="tool" onClick={() => toggleMenu('views')} aria-expanded={menu === 'views'}><Icon name="bookmark" /> Saved views{st.saved.length ? ` · ${st.saved.length}` : ''}</button>
        {menu === 'views' ? <div className="pop left views-pop">
          <div><div className="pop-group">Ready-made</div><div className="view-chips">
            {SPACES[space].presets.map((v, i) => <ViewChip key={`preset-${i}`} view={v} pressed={st.view.name === v.name && !edited(st, space)} onApply={() => applyView(v)} />)}
          </div></div>
          {st.saved.length ? <div><div className="pop-group">Yours</div><div className="view-chips">
            {st.saved.map((v, i) => <ViewChip key={`saved-${i}-${v.name}`} view={v} pressed={st.view.name === v.name && !edited(st, space)} onApply={() => applyView(v)}
              onDelete={() => update(draft => { draft.saved.splice(i, 1); })} />)}
          </div></div> : null}
          <div className="save-row"><input id="viewName" maxLength={40} placeholder="View name" aria-label="View name" value={viewName}
            onChange={e => setViewName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') saveView(); }} /><button onClick={saveView}>Save</button></div>
        </div> : null}
      </div>

      {dueNow ? <button className="tool due-now" onClick={() => applyView(SPACES[space].presets.find(p => p.name === 'To do')!)}
        title="Follow-ups and tasks due today or earlier">{dueNow} due now</button> : null}

      <label className="search-box"><span className="sr-only" hidden>Search</span><Icon name="search" size={15} />
        <input type="search" id="search" placeholder="Search jobs, clients, notes and tasks" aria-label="Search" value={queryInput}
          onChange={e => { const raw = e.target.value; setQueryInput(raw); setPageNo(0); update(draft => { draft.view.query = raw.trim(); }); }} />
      </label>

      <span className="count" id="count" aria-live="polite">{jobs.length} {noun}{jobs.length === 1 ? '' : 's'}{jobs.length !== all ? ` of ${all}` : ''}
        {pages > 1 ? <span className="page">page {page + 1} of {pages}</span> : null}</span>
      <span id="pager">{pages > 1 ? <span className="pager"><button onClick={() => setPageNo(Math.max(0, page - 1))} aria-label="Previous page" disabled={page === 0}>‹</button>
        <button onClick={() => setPageNo(Math.min(pages - 1, page + 1))} aria-label="Next page" disabled={page >= pages - 1}>›</button></span> : null}</span>

      <div className="menu" id="menu-filters">
        <button className={`tool${activeFilters.length ? ' on' : ''}`} onClick={() => toggleMenu('filters')} aria-expanded={menu === 'filters'}><Icon name="filter" /> Filters{activeFilters.length ? ` · ${activeFilters.length}` : ''}</button>
        {menu === 'filters' ? <FilterPanel space={space} st={st} jobs={state.jobs || []} colFilter={colFilter} optSearch={optSearch}
          setOptSearch={setOptSearch} setColFilter={id => { setColFilter(id); setOptSearch(''); }} close={closePops} update={update} passes={passes} /> : null}
      </div>

      {st.view.layout === 'list' ? <div className="menu" id="menu-columns">
        <button className="tool" onClick={() => toggleMenu('columns')} aria-expanded={menu === 'columns'}>Columns · {st.view.cols.length}</button>
        {menu === 'columns' ? <ColumnsPanel space={space} st={st} update={update} dropCol={dropCol}
          onDragStart={columnDragStart} onDragOver={columnDragOver} onDrop={columnDrop} onDragEnd={columnDragEnd} /> : null}
      </div> : null}
    </div>

    <div id="chips-row">
      {activeFilters.length ? <div className="active-filters" aria-label="Active filters"><span>Filters</span>
        {activeFilters.map(([id, f]) => <button key={id} className="af-chip" aria-label={`Remove ${COLS[id].label} filter`}
          onClick={() => update(draft => { delete draft.view.filters[id]; })}>{COLS[id].label}: {describeFilter(f)} <Icon name="x" size={11} /></button>)}
        <button className="link" onClick={() => update(draft => { draft.view.filters = {}; })}>Clear all</button>
      </div> : null}
      {selected.size ? <div className="bulk-bar">{selected.size} selected
        <select aria-label="Move the selected jobs" defaultValue="" onChange={e => bulkMove(e.target.value)}><option value="">Move to…</option>
          {ORDER.map(k => <option key={k} value={k}>{LABEL[k]}</option>)}</select>
        <button className="link" onClick={() => setSelected(new Set())}>Clear selection</button>
      </div> : null}
    </div>

    <div id="results">
      {st.view.layout === 'board'
        ? <Board jobs={jobs} drawerId={drawerId} openDrawer={openDrawer} closeDrawer={closeDrawer} move={move} dropStage={dropStage} setDropStage={setDropStage} />
        : jobs.length
          ? <Table jobs={shown} st={st} drawerId={drawerId} selected={selected} setSelected={setSelected} menu={menu} colFilter={colFilter}
            openFilter={openFilter} toggleSort={toggleSort} rowClick={rowClick} rowKey={rowKey} liveWidth={liveWidth}
            resizeStart={resizeStart} dropCol={dropCol} onDragStart={columnDragStart} onDragOver={columnDragOver} onDrop={columnDrop} onDragEnd={columnDragEnd} />
          : <p className="empty">{all ? 'Nothing matches this view. Loosen a filter or clear the search.' : 'No jobs yet. Press Find jobs.'}</p>}
    </div>
  </div>;
}

function ViewChip({ view, pressed, onApply, onDelete }: { view: View; pressed: boolean; onApply: () => void; onDelete?: () => void }) {
  return <span className="view-chip"><button onClick={onApply} aria-pressed={pressed}>{view.name}</button>{onDelete
    ? <button onClick={onDelete} aria-label={`Delete view ${view.name}`}><Icon name="trash" size={12} /></button> : null}</span>;
}

function FilterPanel({ space, st, jobs, colFilter, optSearch, setOptSearch, setColFilter, close, update, passes }: {
  space: SpaceName; st: SpaceState; jobs: any[]; colFilter: string | null; optSearch: string;
  setOptSearch: (s: string) => void; setColFilter: (s: string | null) => void; close: () => void;
  update: (change: (draft: SpaceState) => void) => void; passes: (j: any, except?: string) => boolean;
}) {
  const fields = SPACES[space].cols.filter(id => COLS[id].filter);
  return <div className="pop filter-panel" role="region" aria-label="Column filters">
    <div className="fp-head"><select aria-label="Filter field" value={colFilter || ''} onChange={e => setColFilter(e.target.value || null)}>
      <option value="">Choose a field…</option>{fields.map(id => <option key={id} value={id}>{COLS[id].label}{filterActive(st.view.filters[id]) ? ' ·' : ''}</option>)}
    </select><button className="icon-btn" onClick={close} aria-label="Close filters"><Icon name="x" size={11} /></button></div>
    {colFilter ? <FieldPanel space={space} id={colFilter} st={st} jobs={jobs} optSearch={optSearch} setOptSearch={setOptSearch} update={update} passes={passes} close={close} /> : null}
  </div>;
}

function FieldPanel({ space, id, st, jobs, optSearch, setOptSearch, update, passes, close }: {
  space: SpaceName; id: string; st: SpaceState; jobs: any[]; optSearch: string; setOptSearch: (s: string) => void;
  update: (change: (draft: SpaceState) => void) => void; passes: (j: any, except?: string) => boolean; close: () => void;
}) {
  const col = COLS[id];
  const current = st.view.filters[id] || (col.filter === 'multi'
    ? { kind: 'multi', values: [] } as Filter
    : { kind: 'range', min: null, max: null } as Filter);

  let body: React.ReactNode;
  if (col.filter === 'multi') {
    const f = current as Extract<Filter, { kind: 'multi' }>;
    const seen = new Set<string>(), counts = new Map<string, number>();
    const each = (j: any, fn: (x: string) => void) => {
      const value = col.value!(j);
      (Array.isArray(value) ? value : [value]).forEach(x => fn(String(x)));
    };
    jobs.filter(SPACES[space].base).forEach(j => each(j, x => seen.add(x)));
    jobs.filter(j => passes(j, id)).forEach(j => each(j, x => counts.set(x, (counts.get(x) || 0) + 1)));
    const options = (id === 'stage' ? ORDER.map(k => LABEL[k]) : [...seen].sort()).filter(option => seen.has(option));
    const visible = options.filter(option => option.toLowerCase().includes(optSearch.trim().toLowerCase()));
    body = <fieldset><legend>{col.label}</legend>
      {options.length > 8 ? <input type="search" placeholder="Find a value…" aria-label={`Search ${col.label} values`} value={optSearch} onChange={e => setOptSearch(e.target.value)} /> : null}
      <div className="opt-list">{visible.map(option => {
        const count = counts.get(option) || 0, on = f.values.includes(option);
        return <label key={option} className={`opt${on ? ' on' : ''}${!count && !on ? ' zero' : ''}`}><input type="checkbox" checked={on} onChange={e => update(draft => {
          const old = draft.view.filters[id];
          const next = old?.kind === 'multi' ? old : { kind: 'multi' as const, values: [] };
          next.values = e.target.checked ? [...new Set([...next.values, option])] : next.values.filter(x => x !== option);
          draft.view.filters[id] = next;
        })} /><span>{option}</span><span className="n">{count}</span></label>;
      })}</div>
    </fieldset>;
  } else {
    const f = current as Extract<Filter, { kind: 'range' }>;
    const values = jobs.filter(SPACES[space].base).map(col.value!).filter((x: any) => x != null);
    const lo = values.length ? Math.min(...values) : '', hi = values.length ? Math.max(...values) : '';
    const setRange = (key: 'min' | 'max', raw: string) => update(draft => {
      const old = draft.view.filters[id];
      const next = old?.kind === 'range' ? old : { kind: 'range' as const, min: null, max: null };
      next[key] = raw === '' ? null : Number(raw);
      draft.view.filters[id] = next;
    });
    body = <fieldset><legend>{col.label}{col.unit ? ` · ${col.unit}` : ''}</legend><div className="range">
      <input type="number" placeholder={String(lo)} value={f.min ?? ''} aria-label="From" onChange={e => setRange('min', e.target.value)} /> to
      <input type="number" placeholder={String(hi)} value={f.max ?? ''} aria-label="To" onChange={e => setRange('max', e.target.value)} />
    </div><p className="fp-hint">Values in this list run from {lo} to {hi}.</p></fieldset>;
  }

  return <><div className="fp-body">{body}</div><div className="fp-foot"><button disabled={!filterActive(current)} onClick={() => update(draft => { delete draft.view.filters[id]; })}>Clear</button>
    <button className="primary" onClick={close}>Done</button></div></>;
}

function ColumnsPanel({ space, st, update, dropCol, onDragStart, onDragOver, onDrop, onDragEnd }: {
  space: SpaceName; st: SpaceState; update: (change: (draft: SpaceState) => void) => void;
  dropCol: { id: string; after: boolean } | null; onDragStart: (e: React.DragEvent, id: string) => void;
  onDragOver: (e: React.DragEvent, id: string) => void; onDrop: (e: React.DragEvent, id: string) => void; onDragEnd: () => void;
}) {
  const groups = GROUPS.map(group => ({ ...group, cols: group.cols.filter(id => SPACES[space].cols.includes(id)) })).filter(group => group.cols.length);
  return <div className="pop columns-pop" role="region" aria-label="Choose columns">
    <div className="pop-title"><b>Columns</b><button className="link" onClick={() => update(draft => {
      const src = viewSource(draft, space) || SPACES[space].presets[0];
      draft.view.cols = clone(src.cols);
      draft.view.widths = {};
    })}>Reset columns</button></div>
    {groups.map(group => {
      const all = group.cols.every(id => st.view.cols.includes(id));
      return <div className="col-group" key={group.title}><div className="pop-group">{group.title} <button className="link" onClick={() => update(draft => {
        const cols = group.cols.filter(id => !COLS[id].fixed);
        draft.view.cols = cols.every(id => draft.view.cols.includes(id))
          ? draft.view.cols.filter(id => !cols.includes(id))
          : [...draft.view.cols, ...cols.filter(id => !draft.view.cols.includes(id))];
      })}>{all ? 'clear' : 'add all'}</button></div><div className="col-chips">
        {group.cols.map(id => <button key={id} className="col-chip" aria-pressed={st.view.cols.includes(id)} disabled={COLS[id].fixed} title={COLS[id].fixed ? 'Always visible' : undefined}
          onClick={() => update(draft => { draft.view.cols = draft.view.cols.includes(id) ? draft.view.cols.filter(c => c !== id) : [...draft.view.cols, id]; })}>{COLS[id].label}</button>)}
      </div></div>;
    })}
    <div className="order"><div className="pop-title"><b>Order</b><span className="hint">drag to reorder · left to right</span></div>
      {st.view.cols.map((id, i) => <div key={id} className={`order-row${dropCol?.id === id ? dropCol.after ? ' drop-after' : ' drop-before' : ''}`} draggable
        onDragStart={e => onDragStart(e, id)} onDragOver={e => onDragOver(e, id)} onDrop={e => onDrop(e, id)} onDragEnd={onDragEnd}>
        <span className="num">{i + 1}</span><span className="grow">{COLS[id].label}</span>
        <button aria-label={`Move ${COLS[id].label} left`} disabled={i === 0} onClick={() => update(draft => {
          const index = draft.view.cols.indexOf(id); [draft.view.cols[index], draft.view.cols[index - 1]] = [draft.view.cols[index - 1], draft.view.cols[index]];
        })}>↑</button>
        <button aria-label={`Move ${COLS[id].label} right`} disabled={i === st.view.cols.length - 1} onClick={() => update(draft => {
          const index = draft.view.cols.indexOf(id); [draft.view.cols[index], draft.view.cols[index + 1]] = [draft.view.cols[index + 1], draft.view.cols[index]];
        })}>↓</button>
      </div>)}
    </div>
  </div>;
}

function Table({ jobs, st, drawerId, selected, setSelected, menu, colFilter, openFilter, toggleSort, rowClick, rowKey, liveWidth, resizeStart,
  dropCol, onDragStart, onDragOver, onDrop, onDragEnd }: {
  jobs: any[]; st: SpaceState; drawerId: string | null; selected: Set<string>; setSelected: React.Dispatch<React.SetStateAction<Set<string>>>;
  menu: Menu; colFilter: string | null; openFilter: (id: string) => void; toggleSort: (id: string) => void;
  rowClick: (e: React.MouseEvent<HTMLTableRowElement>, id: string) => void; rowKey: (e: React.KeyboardEvent, id: string) => void;
  liveWidth: { id: string; width: number } | null; resizeStart: (e: React.PointerEvent<HTMLSpanElement>, id: string) => void;
  dropCol: { id: string; after: boolean } | null;
  onDragStart: (e: React.DragEvent, id: string) => void; onDragOver: (e: React.DragEvent, id: string) => void;
  onDrop: (e: React.DragEvent, id: string) => void; onDragEnd: () => void;
}) {
  const router = useRouter();
  const ids = jobs.map(j => String(j.id));
  const allOn = ids.length > 0 && ids.every(id => selected.has(id));
  const width = (id: string) => liveWidth?.id === id ? liveWidth.width : st.view.widths[id] || COLS[id].w;
  const tableWidth = 44 + st.view.cols.reduce((sum, id) => sum + width(id), 0);
  return <div className="table-card"><div className="tabellen-feld"><table className="rt-table" id="table" style={{ minWidth: tableWidth }}>
    <colgroup><col style={{ width: 44 }} />{st.view.cols.map(id => <col key={id} data-colw={id}
      style={id === 'job' && !st.view.widths.job && liveWidth?.id !== 'job' ? undefined : { width: width(id) }} />)}</colgroup>
    <thead><tr><th className="sel-cell"><input type="checkbox" checked={allOn} onChange={e => setSelected(current => {
      const next = new Set(current); ids.forEach(id => e.target.checked ? next.add(id) : next.delete(id)); return next;
    })} aria-label="Select the visible jobs" /></th>
      {st.view.cols.map(id => {
        const col = COLS[id], on = st.view.sort?.id === id;
        const dropClass = dropCol?.id === id ? dropCol.after ? 'drop-after' : 'drop-before' : '';
        return <th key={id} data-col={id} draggable className={dropClass} aria-sort={on ? st.view.sort!.desc ? 'descending' : 'ascending' : 'none'}
          onDragStart={e => onDragStart(e, id)} onDragOver={e => onDragOver(e, id)} onDrop={e => onDrop(e, id)} onDragEnd={onDragEnd}>
          <div className="th"><button className="th-sort" data-aktiv={on ? 'ja' : undefined} aria-label={`Sort by ${col.label}`} onClick={() => toggleSort(id)}>
            <span>{col.label}{on ? st.view.sort!.desc ? ' ↓' : ' ↑' : ''}</span></button>
            {col.filter ? <button className={`th-filter${filterActive(st.view.filters[id]) ? ' on' : ''}`} data-open-colfilter={id}
              aria-label={`Filter by ${col.label}`} aria-expanded={menu === 'filters' && colFilter === id} onClick={() => openFilter(id)}>
              <Icon name="filter" size={12} filled={filterActive(st.view.filters[id])} /></button> : null}
          </div><span className="grip" role="separator" aria-orientation="vertical" aria-label={`Resize ${col.label} column`} onPointerDown={e => resizeStart(e, id)} />
        </th>;
      })}</tr></thead>
    <tbody>{jobs.map(j => {
      const id = String(j.id);
      // A click opens the side panel, a double click or the arrow opens the full page.
      return <tr key={id} className={`uw-row${isDue(j) ? ' due' : ''}${id === drawerId ? ' sel' : ''}`} tabIndex={0} onClick={e => rowClick(e, id)} onKeyDown={e => rowKey(e, id)}
        onDoubleClick={e => { if (!(e.target as Element).closest('a, button, select, input, label, .sel-cell')) router.push(`/job/${id}`); }}>
        <td className="sel-cell"><input type="checkbox" checked={selected.has(id)} onChange={e => setSelected(current => {
          const next = new Set(current); e.target.checked ? next.add(id) : next.delete(id); return next;
        })} aria-label={`Select ${j.title}`} /></td>
        {st.view.cols.map(colId => <td key={colId} data-column={colId}>{COLS[colId].cell(j)}{colId === 'job'
          ? <Link className="row-open" href={`/job/${id}`} aria-label={`Open ${j.title} on its full page`} title="Open full page" onClick={e => e.stopPropagation()}>↗</Link> : null}</td>)}
      </tr>;
    })}</tbody>
  </table></div></div>;
}

function Board({ jobs, drawerId, openDrawer, closeDrawer, move, dropStage, setDropStage }: {
  jobs: any[]; drawerId: string | null; openDrawer: (id: string) => void; closeDrawer: () => void;
  move: (id: string, status: string, follow?: string | null, note?: string | null) => Promise<boolean>;
  dropStage: string | null; setDropStage: (s: string | null) => void;
}) {
  const router = useRouter();
  return <div className="board">{STAGES.map(stage => {
    const list = jobs.filter(j => j.status === stage.key);
    return <section key={stage.key} className={`col${dropStage === stage.key ? ' drop' : ''}`}
      onDragOver={e => { if (!e.dataTransfer.types.includes('text/col')) { e.preventDefault(); setDropStage(stage.key); } }}
      onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDropStage(null); }}
      onDrop={e => {
        if (e.dataTransfer.types.includes('text/col')) return;
        e.preventDefault(); setDropStage(null);
        const id = e.dataTransfer.getData('text/plain'), job = jobs.find(j => String(j.id) === id);
        if (job && job.status !== stage.key) move(id, stage.key, stage.key === 'applied' ? '+3d' : null);
      }}>
      <div className="col-head" style={{ borderTopColor: `color-mix(in srgb, var(--brand) ${stage.mix}%, var(--card))` }}>
        <div><div className="col-title">{stage.label}</div><div className="col-hint">{stage.hint}</div></div><span className="col-count">{list.length}</span>
      </div><ul className="col-body">{list.length ? list.map(j => {
        const id = String(j.id);
        return <li key={id} className={`card${isDue(j) ? ' due' : ''}${id === drawerId ? ' sel' : ''}`} draggable tabIndex={0}
          onDragStart={e => { e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move'; }}
          onDragEnd={() => setDropStage(null)} onClick={() => drawerId === id ? closeDrawer() : openDrawer(id)}
          onDoubleClick={() => router.push(`/job/${id}`)}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDrawer(id); } }}>
          <div className="card-top"><Score j={j} /><span className="card-title">{j.title}</span></div>
          <div className="card-meta">{[clientText(j), budgetText(j), ago(j.posted_date)].filter(Boolean).join(' · ')}</div><DueChip j={j} />
        </li>;
      }) : <li className="col-empty">Drop a job here</li>}</ul>
    </section>;
  })}</div>;
}
