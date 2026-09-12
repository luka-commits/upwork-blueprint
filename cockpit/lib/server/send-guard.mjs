// Claude PreToolUse hook. No model-produced message text reaches Upwork.
// Contract: https://code.claude.com/docs/en/hooks#pretooluse-decision-control
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function approvalHash(record) {
  const { written_at, job_id, room_id, text, draft, draft_set, known_message_ids } = record;
  return crypto.createHash('sha256').update(JSON.stringify({ written_at, job_id, room_id, text, draft, draft_set, known_message_ids })).digest('hex');
}

export function guardSendTool(event, { folder, hash, attempts }) {
  const deny = reason => ({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason } });
  const allow = updatedInput => ({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow', ...(updatedInput ? { updatedInput } : {}) } });
  try {
    const outbox = JSON.parse(fs.readFileSync(path.join(folder, 'outbox.json'), 'utf-8'));
    if (!hash || approvalHash(outbox) !== hash) return deny('The approved outbox changed. Stop without sending.');
    const tool = event.tool_name, input = event.tool_input || {};
    if (tool === 'mcp__upwork__upwork__send_message') {
      const keys = ['text', 'message'].filter(key => Object.hasOwn(input, key));
      if (input.action !== 'send' || input.room_id !== outbox.room_id || !input.org_uid || keys.length !== 1
          || Object.keys(input).some(key => !['action', 'org_uid', 'room_id', 'text', 'message'].includes(key))) {
        return deny('Unexpected message schema, room or action. Stop and inspect the connector; do not send.');
      }
      fs.mkdirSync(attempts, { recursive: true });
      try { fs.writeFileSync(path.join(attempts, hash), new Date().toISOString(), { flag: 'wx', mode: 0o600 }); }
      catch { return deny('This approval was already attempted. Check Upwork; never retry automatically.'); }
      return allow({ ...input, [keys[0]]: outbox.text });
    }
    if (tool === 'Write' && path.resolve(input.file_path || '') === path.join(folder, '.thread-confirm.json')) return allow();
    if (tool === 'Read') return allow();
    if (tool === 'mcp__upwork__upwork__list_accounts') return allow();
    if (tool === 'mcp__upwork__upwork__get_messages' && input.action === 'list_messages' && input.room_id === outbox.room_id) return allow();
    if (tool === 'Bash') {
      const escape = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const job = escape(outbox.job_id), room = escape(outbox.room_id);
      const confirm = new RegExp(`^python3 code/threads\\.py confirm ${job} --room (?:${room}|"${room}"|'${room}') --awaiting them$`);
      if (confirm.test(input.command) || input.command === `python3 code/pipeline.py follow-up ${outbox.job_id} sent`
          || input.command === 'python3 code/pipeline.py prune') return allow();
    }
    return deny('The reply sender may only send the frozen approval and save its confirmation.');
  } catch { return deny('The approved send state is unreadable. Stop without sending.'); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let source = '';
  for await (const chunk of process.stdin) source += chunk;
  let result;
  try {
    result = guardSendTool(JSON.parse(source), { folder: process.env.BLUEPRINT_SEND_FOLDER,
      hash: process.env.BLUEPRINT_SEND_HASH, attempts: process.env.BLUEPRINT_SEND_ATTEMPTS });
  } catch {
    result = { hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: 'Invalid hook input. Nothing may be sent.' } };
  }
  process.stdout.write(JSON.stringify(result));
}
