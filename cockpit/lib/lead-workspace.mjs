const WORKSPACES = {
  new: {
    mode: 'prepare',
    label: 'Application preparation',
    defaultView: 'work',
    layout: { context: 'job', contextOpen: true, tools: false, toolsOpen: false },
    tabs: [
      ['work', 'Preparation'],
    ],
  },
  applied: {
    mode: 'waiting',
    label: 'Waiting for the client',
    defaultView: 'work',
    layout: { context: 'job', contextOpen: true, tools: false, toolsOpen: false },
    tabs: [
      ['work', 'Overview'],
      ['materials', 'Materials'],
    ],
  },
  sales: {
    mode: 'sales',
    label: 'Sales workspace',
    defaultView: 'conversation',
    layout: { context: 'job', contextOpen: true, tools: true, toolsOpen: true },
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
    layout: { context: 'project', contextOpen: false, tools: false, toolsOpen: false },
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
    layout: { context: 'job', contextOpen: false, tools: false, toolsOpen: false },
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
    layout: { ...workspace.layout },
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
    { key: 'pitch', label: 'Pitch page and Loom script', ready: names.has('pitch.html') && names.has('loom-script.md') },
    { key: 'application', label: 'Loom video and application', ready: hasValidVideo === true && names.has('application.md') },
  ];
  return { ready: items.filter(item => item.ready).length, total: 2, items };
}

// A single priority keeps a blocked application from opening alongside its prerequisite.
export function nextPreparationMaterial(files, hasValidVideo) {
  return preparationProgress(files, hasValidVideo).items.find(item => !item.ready)?.key || 'application';
}
