const plans = {
  'find-jobs': [
    ['Load your search strategy', /Read.*(?:context\/me|profile\.md|find-jobs\.md)/i],
    ['Search Upwork for matching work', /find_jobs/i],
    ['Read and score the strongest jobs', /(?:jobs\.py detail|pipeline\.py assess|details\/)/i],
    ['Save the best leads to your pipeline', /pipeline\.py add/i],
    ['Check the finished shortlist', /(?:pipeline\.py summary|pipeline\.py prune)/i],
  ],
  sync: [
    ['Connect to your Upwork account', /list_accounts/i],
    ['Read proposals and conversations', /(?:list_freelancer_proposals|get_messages|list_offers|list_contracts)/i],
    ['Match Upwork activity to your leads', /(?:threads\.py|pipeline\.py get)/i],
    ['Update stages and saved messages', /(?:pipeline\.py (?:set|observe)|threads\.py confirm)/i],
    ['Check the refreshed pipeline', /(?:pipeline\.py summary|pipeline\.py prune)/i],
  ],
  'pitch-page': [
    ['Check this job and publishing setup', /(?:preflight\.py|pipeline\.py get)/i],
    ['Match the job to your services and proof', /Read.*(?:context\/(?:me|proof)\.md|upwork-copy|tool-knowledge)|(?:get_profile|find_jobs)/i],
    ['Shape the page and Loom story', /Read.*(?:code\/pitch|pitch-graph|logos)|Glob.*(?:code\/pitch|logos)/i],
    ['Build the pitch page and Loom script', /Bash.*(?:code\/pitch\/generate\.py|code\/pitch\.py|lead-magnet\/scripts\/demo\.py\s+jobs\/)|(?:Write|Edit).*?(?:jobs\/\d+\/|pitch\.html|loom-script\.md)/i],
    ['Publish the client-ready link', /Bash.*(?:pitch_deploy\.py|vercel)|pipeline\.py pitch-url/i],
    ['Check the page and application handoff', /Bash.*(?:check_repo|test_|render|screenshot|verify)|Read.*(?:pitch\.html|loom-script\.md)$/i],
  ],
  apply: [
    ['Check the pitch page and Loom video', /(?:pipeline\.py get|funnel\.py ready|pitch\.html|loom-script\.md)/i],
    ['Match the job to your strongest proof', /Read.*(?:context\/(?:me|proof)\.md|upwork-copy|tool-knowledge)|get_profile/i],
    ['Review the Loom when enabled', /(?:funnel\.py transcript loom|loom-review)/i],
    ['Write the short application', /(?:Write|Edit).*application\.md|funnel\.py application/i],
    ['Prepare the Upwork handoff', /manage_proposals|proposal preview/i],
    ['Check every application field', /(?:pipeline\.py prune|check_repo|application\.md$)/i],
  ],
  reply: [
    ['Read the latest conversation', /(?:thread\.json|pipeline\.py get)/i],
    ['Match the reply to your voice and proof', /Read.*(?:context\/(?:me|proof)\.md|upwork-copy)/i],
    ['Draft the strongest reply options', /(?:Write|Edit).*replies\.json/i],
    ['Check that nothing unsupported slipped in', /(?:replies\.py|check_repo|pipeline\.py prune)/i],
  ],
  'lead-magnet': [
    ['Check the website and provider access', /(?:preflight|lead-magnet-source|pipeline\.py get)/i],
    ['Collect website and Google evidence', /(?:firecrawl|apify|dataforseo|pull_)/i],
    ['Find the highest-value SEO gaps', /(?:audit|score|analysis)/i],
    ['Build the client-ready audit', /(?:build\.py|lead-magnet\.html)/i],
    ['Publish the audit link', /(?:vercel|lead-magnet-url)/i],
    ['Check the finished audit', /(?:verify|check|screenshot|render)/i],
  ],
  'follow-up': [
    ['Load active conversations', /(?:list_accounts|list_freelancer_proposals|get_messages)/i],
    ['Find leads worth following up', /(?:follow-up|thread\.json|pipeline\.py list)/i],
    ['Choose timing from each conversation', /(?:upwork-follow-up|follow_up_plan)/i],
    ['Save the follow-up plan', /pipeline\.py follow-up.*plan/i],
    ['Check today\'s queue', /(?:follow-ups\.md|pipeline\.py prune)/i],
  ],
  inbox: [
    ['Connect to your Upwork inbox', /list_accounts/i],
    ['Read the latest client messages', /get_messages/i],
    ['Match replies to the right leads', /(?:threads\.py|pipeline\.py)/i],
    ['Check the updated inbox', /pipeline\.py prune/i],
  ],
  'send-reply': [
    ['Lock the exact reply you approved', /outbox\.json/i],
    ['Send it once to this conversation', /send_message/i],
    ['Confirm the exact message landed', /get_messages/i],
    ['Save the confirmed conversation', /(?:threads\.py confirm|pipeline\.py follow-up|pipeline\.py prune)/i],
  ],
  'call-prep': [
    ['Read the job and conversation', /(?:pipeline\.py get|thread\.json|get_messages)/i],
    ['Match the call to your proof', /Read.*context\/(?:me|proof)\.md/i],
    ['Build the questions and decision path', /(?:call-prep|Write.*call-prep\.md)/i],
    ['Check the call brief', /(?:check|prune|call-prep\.md$)/i],
  ],
  status: [
    ['Read your current pipeline', /pipeline\.py (?:summary|list)/i],
    ['Find the next useful actions', /(?:funnel\.py|status)/i],
    ['Save the concise status', /(?:data\/status\.md|pipeline\.py prune)/i],
  ],
};

const fallback = [
  ['Prepare the run', /Read|Glob|Grep/i],
  ['Do the requested work', /Write|Edit|Bash|mcp__/i],
  ['Check the result', /check|verify|test|prune/i],
];

export function runPlan(command) {
  return (plans[command] || fallback).map(([label]) => label);
}

export function advanceRunStep(command, current, event) {
  const plan = plans[command] || fallback;
  const activity = `${event?.text || ''} ${event?.detail || ''}`;
  let matched = current;
  for (let index = 0; index < plan.length; index += 1) {
    if (plan[index][1].test(activity)) {
      matched = Math.max(matched, index);
      break;
    }
  }
  return matched;
}

export function runProgress(command, step, done = false) {
  const total = runPlan(command).length;
  if (done) return 100;
  const safe = Math.max(0, Math.min(Number.isInteger(step) ? step : 0, total - 1));
  return Math.round(((safe + 0.45) / total) * 100);
}
