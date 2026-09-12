'use client';

import Link from 'next/link';
import { useCockpit } from '@/lib/context';
import { LABEL, short, taskItems, todayIso } from '@/lib/model';

export default function TasksPage() {
  const { state, move, post } = useCockpit();
  if (!state) return <p className="empty">Loading.</p>;
  const today = todayIso();
  const items = taskItems(state.jobs || []).sort((a, b) => String(a.due || '9999').localeCompare(String(b.due || '9999')));
  const groups: [string, (item: any) => boolean][] = [
    ['Overdue', item => item.due && item.due < today],
    ['Today', item => item.due === today],
    ['Coming up', item => item.due && item.due > today],
    ['No date', item => !item.due],
  ];

  return <div className="task-page">
    {groups.map(([name, test]) => {
      const list = items.filter(test);
      return list.length ? <section className="task-group" key={name}>
        <h3>{name} · {list.length}</h3>
        {list.map((item: any) => <TaskRow key={`${item.kind}-${item.j.id}-${item.t?.id || ''}`} item={item} move={move} post={post} />)}
      </section> : null;
    })}
    {!items.length ? <p className="empty">Nothing to do. Add tasks from any job or client, follow-ups land here on their own.</p> : null}
    <p className="note-sm">Tasks live on a job or a client: add them in the side panel or on the full page. A ticked follow-up sets the next one three days out.</p>
  </div>;
}

function TaskRow({ item, move, post }: { item: any; move: any; post: any }) {
  const kind = item.j.status === 'won' ? <span className="kind client">Client</span> : <span className="kind">{LABEL[item.j.status]}</span>;
  if (item.kind === 'follow') return <div className="task-row">
    <input type="checkbox" onChange={() => move(item.j.id, item.j.status, '+3d')} aria-label="Followed up" />
    <div>Follow up on the application<span className="job"><Link href={`/job/${item.j.id}`}>{item.j.title}</Link></span></div>
    {kind}<span className="note-sm">{short(item.due)}</span>
  </div>;
  return <div className="task-row">
    <input type="checkbox" onChange={() => post('/api/task', { id: item.j.id, action: 'done', task: item.t.id })} aria-label="Done" />
    <div>{item.t.text}<span className="job"><Link href={`/job/${item.j.id}`}>{item.j.title}</Link></span></div>
    {kind}<span className="note-sm">{item.due ? short(item.due) : ''}</span>
  </div>;
}
