'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useCockpit } from '@/lib/context';
import { DueChip, Score, StageSelect } from '@/lib/model';
import { BoostBlock, Facts, FilesChecklist, NextStep, TasksBlock } from './JobParts';

export default function Drawer() {
  const { state, api, toast, drawerId, closeDrawer } = useCockpit();
  const [job, setJob] = useState<any>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const loadedId = useRef<string | null>(null);

  useEffect(() => {
    document.body.classList.toggle('drawer-open', !!drawerId);
    return () => document.body.classList.remove('drawer-open');
  }, [drawerId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && drawerId) closeDrawer();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerId, closeDrawer]);

  useEffect(() => {
    if (!drawerId) { setJob(null); loadedId.current = null; return; }
    let cancelled = false;
    const preserveScroll = loadedId.current === drawerId;
    const scroll = preserveScroll ? bodyRef.current?.scrollTop || 0 : 0;
    if (!preserveScroll) setJob(null);
    loadedId.current = drawerId;
    api(`/api/job/${drawerId}`).then(result => {
      if (cancelled) return;
      if (!result.ok) {
        if (!preserveScroll) toast('Could not load that job.');
        closeDrawer();
        return;
      }
      const card = state?.jobs?.find((item: any) => item.id === drawerId) || {};
      setJob({ ...result.data, artifacts: card.artifacts || (result.data.files || []).map((file: any) => file.name) });
      if (preserveScroll) requestAnimationFrame(() => { if (bodyRef.current) bodyRef.current.scrollTop = scroll; });
    });
    return () => { cancelled = true; };
  }, [drawerId, state?.generated_at]);

  const d = job?.details || {};
  return <aside className={`drawer${drawerId ? ' open' : ''}`} aria-label="Job">
    {job ? <>
      <div className="drawer-head">
        <div className="drawer-title">
          {job.score != null ? <Score j={job} /> : null}
          <h3>{job.url ? <a href={job.url} target="_blank" rel="noopener" title="Open on Upwork">{job.title}</a> : job.title}</h3>
          <button className="drawer-close" onClick={closeDrawer} aria-label="Close">✕</button>
        </div>
        <div className="drawer-stage"><StageSelect j={job} /><DueChip j={job} /></div>
      </div>
      <div className="drawer-body" ref={bodyRef}>
        <h4>Next step</h4><NextStep key={`next-${job.id}`} j={job} />
        <h4>Tasks</h4><TasksBlock key={`tasks-${job.id}`} j={job} />
        {job.status === 'new' ? <><h4>Top slot</h4><BoostBlock d={d} /></> : null}
        <FactsHeading j={job} />
        {job.niche_fit != null ? <><h4>Score</h4><p className="note-sm" style={{ margin: 0, fontSize: 13 }}>fit {job.niche_fit} of 40 · client {job.client_trust ?? '?'} of 30 · deal {job.deal_quality ?? '?'} of 20 · fresh {job.recency ?? '?'} of 10</p></> : null}
        <h4>Files</h4><FilesChecklist j={job} />
        {d.description ? <details><summary><h4 style={{ display: 'inline' }}>The full posting</h4></summary><div className="posting">{d.description}</div></details> : null}
      </div>
      <div className="drawer-foot"><Link className="btn" href={`/job/${job.id}`} onClick={closeDrawer}>Open full page →</Link></div>
    </> : null}
  </aside>;
}

function FactsHeading({ j }: { j: any }) {
  const d = j.details || {}, c = j.client || {};
  const hasFacts = d.bid_avg != null || d.fetched_at || d.min_jss || (d.min_earnings && !/any/i.test(d.min_earnings)) ||
    (d.client_record || {}).spend_total || c.spent || c.country || d.client_timezone;
  return hasFacts ? <><h4>The deal</h4><Facts j={j} /></> : null;
}
