const WORKSPACES = {
  new: {
    mode: 'prepare',
    label: 'Application preparation',
    defaultView: 'work',
    tabs: [
      ['work', 'Preparation'],
      ['conversation', 'Conversation'],
      ['timeline', 'Timeline'],
    ],
  },
  applied: {
    mode: 'waiting',
    label: 'Waiting for the client',
    defaultView: 'work',
    tabs: [
      ['work', 'Overview'],
      ['materials', 'Materials'],
      ['conversation', 'Conversation'],
      ['timeline', 'Timeline'],
    ],
  },
  sales: {
    mode: 'sales',
    label: 'Sales workspace',
    defaultView: 'conversation',
    tabs: [
      ['conversation', 'Conversation'],
      ['work', 'Call and proposal'],
      ['materials', 'Application materials'],
      ['timeline', 'Timeline'],
    ],
  },
  won: {
    mode: 'delivery',
    label: 'Client delivery',
    defaultView: 'work',
    tabs: [
      ['work', 'Delivery'],
      ['conversation', 'Conversation'],
      ['timeline', 'Timeline'],
      ['materials', 'Sales history'],
    ],
  },
  closed: {
    mode: 'closed',
    label: 'Lead history',
    defaultView: 'timeline',
    tabs: [
      ['timeline', 'Timeline'],
      ['conversation', 'Conversation'],
      ['materials', 'Materials'],
    ],
  },
};

function copyWorkspace(workspace) {
  return {
    mode: workspace.mode,
    label: workspace.label,
    defaultView: workspace.defaultView,
    tabs: workspace.tabs.map(([key, label]) => ({ key, label })),
  };
}

export function leadWorkspace(status) {
  const normalized = String(status || '').trim().toLowerCase();
  const key = normalized === 'replied' || normalized === 'offer'
    ? 'sales'
    : Object.hasOwn(WORKSPACES, normalized) ? normalized : 'closed';
  return copyWorkspace(WORKSPACES[key]);
}

export function preparationProgress(files, hasValidVideo) {
  const names = new Set((Array.isArray(files) ? files : [])
    .map(file => typeof file === 'string' ? file : file?.name)
    .filter(Boolean));
  const items = [
    { key: 'pitch', label: 'Pitch page', ready: names.has('pitch.html') },
    { key: 'script', label: 'Loom script', ready: names.has('loom-script.md') },
    { key: 'video', label: 'Loom video', ready: hasValidVideo === true },
    { key: 'application', label: 'Application', ready: names.has('application.md') },
  ];
  return { ready: items.filter(item => item.ready).length, total: 4, items };
}

// A single priority keeps a blocked application from opening alongside its prerequisite.
export function nextPreparationMaterial(files, hasValidVideo) {
  return preparationProgress(files, hasValidVideo).items.find(item => !item.ready)?.key || 'application';
}
