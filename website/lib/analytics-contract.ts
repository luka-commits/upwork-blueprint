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
  image?: string; fallback_image?: string; motif?: string;
  progress_text?: string; next_tier?: string;
  progress_to_next?: string | { text?: string; qualifying_weeks?: number; required_weeks?: number };
  rule?: string; requirement?: string; exact_rule?: string; next_rule?: string;
};
export type AnalyticsProgress = {
  score_history?: { week: string; value?: number | null; score?: number | null }[];
  biggest_change?: { kind?: string; direction?: string; key?: string; value?: number; previous?: number; name?: string; label?: string; text?: string; sentence?: string; change_text?: string; comparison_text?: string; delta_text?: string; evidence?: AnalyticsEvidence } | null;
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
