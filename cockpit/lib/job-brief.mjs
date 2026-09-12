const ACTION = /\b(build|set up|create|configure|connect|integrate|automate|fix|design|develop|implement|debug|review|map|test|document|train|sync|route|handle|notify|revoke|restore|track|analyse|analyze)\b/i;
const REQUIREMENT = /\b(must|mandatory|required|non-negotiable|do not apply|proven experience|should have|you should have|looking for someone experienced)\b/i;

function clean(value) {
  return String(value || '')
    .replace(/<\/?untrusted_participant_content>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function list(value, limit) {
  return Array.isArray(value) ? value.map(clean).filter(Boolean).slice(0, limit) : [];
}

function segments(value) {
  return String(value || '')
    .replace(/<\/?untrusted_participant_content>/g, '')
    .replace(/[•●▪]/g, '\n')
    .split(/\n+|(?<=[.!?])\s+(?=[A-Z])/)
    .map(line => clean(line).replace(/^(?:scope|tasks include|deliverables|what you(?:'ll| will) build)\s*:\s*/i, ''))
    .filter(line => line.length >= 20);
}

export function deriveJobBrief(job) {
  const details = job?.details || {};
  const saved = details.brief || {};
  const savedOutcome = clean(saved.outcome);
  const savedScope = list(saved.scope, 6);
  const savedRequirements = list(saved.requirements, 4);
  if (savedOutcome || savedScope.length || savedRequirements.length) {
    return { outcome: savedOutcome, scope: savedScope, requirements: savedRequirements };
  }

  const parts = segments(details.description);
  const outcome = clean(job?.summary) || parts[0] || '';
  const candidates = job?.summary ? parts.slice(1) : parts;
  const requirements = candidates.filter(line => REQUIREMENT.test(line)).slice(0, 3);
  let scope = candidates.filter(line => ACTION.test(line) && !REQUIREMENT.test(line)).slice(0, 5);
  if (!scope.length) scope = candidates.filter(line => !REQUIREMENT.test(line)).slice(0, 3);

  return { outcome, scope, requirements };
}
