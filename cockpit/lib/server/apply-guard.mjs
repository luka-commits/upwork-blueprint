// Claude PreToolUse hook for cockpit application runs. The proposal tool groups
// preview and write actions behind one tool name, so the runtime narrows it to
// the documented create-preview action. Submission remains manual on Upwork.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const MANAGE = 'mcp__upwork__upwork__manage_proposals';

export function guardApplicationTool(event) {
  const deny = reason => ({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason } });
  const allow = () => ({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow' } });
  if (!event || typeof event !== 'object' || typeof event.tool_name !== 'string') {
    return deny('Invalid application-run hook input. Stop without changing Upwork.');
  }
  // An empty response leaves unrelated tools to Claude Code's normal
  // dontAsk/allowedTools/disallowedTools evaluation. Explicitly allowing them
  // here could broaden the run beyond its configured tool list.
  if (event.tool_name !== MANAGE) return {};
  if (!event.tool_input || typeof event.tool_input !== 'object' || event.tool_input.action !== 'create') {
    return deny('Application runs may only prepare a create preview. Handle invitations and submission manually on Upwork.');
  }
  return allow();
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let source = '';
  for await (const chunk of process.stdin) source += chunk;
  let result;
  try {
    result = guardApplicationTool(JSON.parse(source));
  } catch {
    result = guardApplicationTool(null);
  }
  process.stdout.write(JSON.stringify(result));
}
