/** Analytics values and selections belong to the snapshot writer. The UI only
 * formats them and draws chart geometry. Fields are optional for older weeks. */
export type AnalyticsPeriod = string | { start?: string; end?: string };
export type AnalyticsEvidence = string[];
export type AnalyticsInsight = {
  kind?: string;
  text?: string;
  sentence?: string;
  action?: string;
  kpi?: string;
  observed?: number | null;
  expected?: number | null;
  n?: number;
  period?: AnalyticsPeriod;
  evidence?: AnalyticsEvidence;
  target?: { view: string; element: string };
};
export type AnalyticsScorecardRow = {
  key: string; group: 'top' | 'middle' | 'bottom'; name: string; stage_label?: string;
  period_label: string; period?: AnalyticsPeriod; currency?: string; value: number | null; state?: string;
  finished: { k: number | null; n: number | null }; pending: { n: number; until?: string | null };
  change: { previous_value: number | null; comparison_label: string; text?: string };
  series: { label: string; unit: string; points: (number | null)[] };
  target: { kind: 'habit' | 'ladder'; value: number | null; level: number | null; thresholds: number[] };
  next_action: { text: string; lead_filter: { kpi: string; lead_ids: string[] } } | null;
  split: Record<string, unknown>[]; focus: { reason: string } | null;
  market: { value: number; source: string | {label?: string; title?: string; url?: string} } | null;
  evidence?: string[]; insight?: string; counting?: string;
};
export type AnalyticsPresentation = {
  rank_progress?: { rank?: string; score?: number | null; next_rank?: string | null; next_threshold?: number | null; held_weeks?: number; required_weeks?: number; progress?: number };
  rank?: string | { rolling_score?: number | null; score?: number | null; name?: string; next_name?: string | null; next_threshold?: number | null; progress?: number | { percent?: number; current?: number; target?: number }; state?: string; weeks?: number };
  scorecard?: AnalyticsScorecardRow[];
  /** Exactly the writer-selected overview keys; the browser never ranks them. */
  number_keys?: string[];
  kpi_groups?: { top?: string[]; middle?: string[]; bottom?: string[] };
  number_groups?: Record<string, { label?: string; keys?: string[]; stood_out?: string | AnalyticsInsight[]; leak?: string | AnalyticsInsight | null }>;
  insights?: AnalyticsInsight[] | { top: AnalyticsInsight[]; all: AnalyticsInsight[] };
  insights_all?: AnalyticsInsight[];
  /** Writer-selected progress. No browser ranking or badge selection. */
  progress?: AnalyticsProgress;
  progress_strip?: AnalyticsProgress;
  biggest_change?: AnalyticsProgress['biggest_change'];
  biggest_gain?: AnalyticsProgress['biggest_change'];
  newest_badge?: AnalyticsBadge;
  score_history?: { week: string; value?: number | null; score?: number | null }[];
  goal_cards?: Record<string, any>[];
  focus?: { headline?: string; reason?: string };
  badges?: AnalyticsBadge[];
  goals_history?: Record<string, unknown>[];
  conversations?: AnalyticsConversations;
  conversation_patterns?: AnalyticsConversationPattern[];
  next_run_day?: string;
  next_run_on?: string;
};
export type AnalyticsCallCard = {
  lead_id: string;
  coach_read?: string | null;
  as_of?: string;
  reviewed_at?: string;
  generated_at?: string;
  next_message?: string | { text?: string; missing_inputs?: string[] } | null;
  next_message_state?: string;
  agreed_step?: AnalyticsCallCard['next_step'];
  coach_read_state?: string;
  coach_read_prompt?: string;
  source_prompt?: string;
  label?: string;
  date?: string;
  duration_min?: number;
  duration_minutes?: number;
  talk_share?: number;
  question_count?: number;
  questions?: { member?: number | null; client?: number | null };
  reviewable?: boolean;
  reason?: string;
  points?: { point: number; label?: string; state: string; quote?: string; reason?: string; definition?: string }[];
  moments?: { label?: string; quote: string; better_wording?: string; better?: string; better_line?: string }[];
  fix?: string;
  example?: string;
  next_step?: {
    quote?: string;
    action?: string;
    text?: string;
    owner?: string;
    when?: string;
    agreed?: boolean;
    agreement?: string;
  } | string;
};

export type AnalyticsBadge = {
  name?: string; badge?: string; tier?: string; short?: string;
  earned?: boolean; locked?: boolean; earned_week?: string; week?: string; as_of_week?: string; as_of?: string; earned_at?: string;
  progress?: number | { percent?: number; current?: number; target?: number };
  image?: string; fallback_image?: string; motif?: string;
  progress_text?: string; next_tier?: string;
  progress_to_next?: string | { text?: string; qualifying_weeks?: number; required_weeks?: number };
  rule?: string; requirement?: string; exact_rule?: string; next_rule?: string;
};
export type AnalyticsProgress = {
  score_history?: { week: string; value?: number | null; score?: number | null }[];
  biggest_change?: { kind?: string; direction?: string; key?: string; value?: number; previous?: number | null; unit?: string; name?: string; label?: string; text?: string; sentence?: string; change_text?: string; comparison_text?: string; delta_text?: string; evidence?: AnalyticsEvidence } | null;
  newest_badge?: AnalyticsBadge | null;
  badges?: AnalyticsBadge[];
};
export type AnalyticsConversationPattern = {
  text?: string; sentence?: string; read?: string; quote?: string;
  quotes?: (string | { quote?: string; text?: string; lead_id?: string })[];
};
export type AnalyticsConversations = {
  sections?: { applications?: Record<string, any>[]; chats?: Record<string, any>[]; calls?: AnalyticsCallCard[]; proposals?: Record<string, any>[] };
  patterns?: AnalyticsConversationPattern[];
  applications?: Record<string, any>[];
  chats?: Record<string, any>[];
  calls?: AnalyticsCallCard[];
  proposals?: Record<string, any>[];
};

/** Translate member copy; unsafe quoted spans are omitted without changing source words. */
export const ANALYTICS_FIELD_LABELS: Record<string, string> = {
  reply_rate: 'Reply rate', reply_to_call: 'Call rate', booked_to_held: 'Show-up rate',
  held_to_proposal: 'Held call to proposal', proposal_to_won: 'Win rate',
  invite_to_call: 'Invite to call', offer_to_contract: 'Offer to contract',
  weekly_volume: 'Weekly applications', speed_10min: 'Applied within 10 minutes',
  first_reply: 'First reply', follow_ups_on_time: 'Follow-ups on their due day',
  proposal_on_time: 'Proposal within 30 minutes', job_fit: 'Jobs that fit your lane and rate',
  won_value: 'New contract value', value_per_100_connects: 'Contract value per 100 Connects',
  application_review: 'Application review', conversation_review: 'Conversation review',
  call_review: 'Call review', proposal_review: 'Proposal review', call_to_won: 'Call to won',
  goal_effect: 'Goal results', goal_done: 'Goals carried out', lost_reasons: 'Reasons deals ended',
  done_k: 'Times carried out', done_n: 'Opportunities', goal_id: 'Goal',
  evidence_lead_ids: 'Source leads', lead_id: 'Lead', review_on: 'Review date',
  decision_date: 'Decision date', next_message: 'Next message', next_step: 'Next step',
  coach_read: "Coach's read", coach_example: 'Example', source_prompt: 'Source needed',
  call_held_at: 'Call held time', call_end_at: 'Call end time', proposal_sent_at: 'Proposal sent time',
  applied_at: 'Application time', replied_at: 'Reply time', call_booked_at: 'Call booking time',
  won_at: 'Contract time', entry_period: 'Counting period', horizon_days: 'Days allowed for a result',
  baseline_phase: 'Building your baseline', pending_n: 'Still waiting', unknown_n: 'Unknown count',
  last_writer: 'Last writer', answered_question: "Answered the client's question",
  qualifying_question: 'Qualifying question', call_proposal: 'Call proposal when useful',
  call_times: 'Call times', not_needed: 'Not needed', unreviewable: 'Cannot check yet',
};
export function analyticsMemberText(value: unknown): string {
  const text = value == null ? 'unknown' : typeof value === 'object'
    ? String((value as any).text || (value as any).label || (value as any).reason || 'unknown') : String(value);
  const translate = (part: string) => part.replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, key => ANALYTICS_FIELD_LABELS[key] || key.replace(/_/g, ' '))
    .replace(/Writer['’]s comparison not supplied/gi, 'Comparison unavailable')
    .replace(/\bSYNTHETIC\b/gi, 'example').replace(/saved review/gi, 'review')
    .replace(/Writer['’]s/gi, 'Review').replace(/\bWilson lower bound\b/gi, 'lower end of the measured range').replace(/\bWilson(?: interval)?\b/gi, 'measured range')
    .replace(/\bdenominator\b/gi, 'finished cases').replace(/\bmature\b/gi, 'finished')
    .replace(/(-?\d+\.\d+)\s*%/g, (_, n) => `${Math.round(Number(n))}%`)
    .replace(/\b(-?\d+\.\d{3,})\b/g, (_, n) => new Intl.NumberFormat('en-US', {maximumFractionDigits: 1}).format(Number(n)))
    .replace(/not supplied/gi, 'unavailable').replace(/undecided/gi, 'Not clear yet')
    .replace(/eligible/gi, 'fitting').replace(/cohorts/gi, 'groups').replace(/cohort/gi, 'group')
    .replace(/Execution and effect apart/gi, 'What you did and what changed')
    .replace(/unreviewable/gi, 'Cannot check yet').replace(/stage starts/gi, 'next fitting opportunity comes up').replace(/\s*—\s*/g, ', ');
  return text.split(/(“[^”]*”|"[^"]*")/g).map((part,index)=>index % 2
    ? translate(part)===part ? part : 'Quote unavailable in this view.'
    : translate(part)).join('');
}
