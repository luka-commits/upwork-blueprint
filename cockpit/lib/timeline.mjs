const list = value => Array.isArray(value) ? value.filter(item => item && typeof item === 'object') : [];
const time = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : -Infinity;
const newestFirst = (a, b) => time(b.at) - time(a.at);

// Reading projection only. Full records stay in the pipeline and job files.
export function timelineView(job = {}) {
  const updates = [], activity = [];
  if (job.found_at) updates.push({ id: 'saved', at: job.found_at, kind: 'saved' });
  let previous = job.found_at ? 'new' : null;
  for (const [index, event] of list(job.history).entries()) {
    if (!event.status || event.status === previous) continue;
    previous = event.status;
    updates.push({ id: `stage-${index}`, at: event.at, kind: 'status', status: event.status });
  }
  for (const [index, note] of list(job.log).entries()) {
    if (typeof note.text === 'string' && note.text.trim()) updates.push({ id: `note-${index}`, at: note.at, kind: 'note', text: note.text });
  }
  for (const file of list(job.files)) {
    if (typeof file.name === 'string' && file.name) activity.push({ id: `file-${file.name}`, at: file.at, kind: 'file', name: file.name });
  }
  for (const [index, task] of list(job.tasks).entries()) {
    if (typeof task.text !== 'string' || !task.text.trim()) continue;
    // One row per task, retaining both dates when the task is complete.
    activity.push({ id: `task-${task.id ?? index}`, at: task.done_at || task.created_at, kind: 'task', text: task.text,
      done: !!task.done_at, created_at: task.created_at });
  }
  updates.sort(newestFirst);
  activity.sort(newestFirst);
  return { recent: updates.slice(0, 5), earlier: updates.slice(5), activity };
}
