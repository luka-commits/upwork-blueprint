/** Analytics values and selections belong to the snapshot writer. The UI only
 * formats them and draws chart geometry. Fields are optional for older weeks. */
export type AnalyticsPeriod = string | { start?: string; end?: string };
export type AnalyticsEvidence = string[];
export type AnalyticsFunnelStage = {
  key: string;
  label: string;
  count?: number;
  k?: number;
  n?: number;
  value?: number | null;
  loss?: number | null;
  loss_label?: string;
  period?: AnalyticsPeriod;
  evidence?: AnalyticsEvidence;
  focus?: boolean;
  observation_only?: boolean;
  observed_at?: string;
};
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
  funnel?: { outbound: AnalyticsFunnelStage[]; inbound: AnalyticsFunnelStage[] };
  money_chart?: {
    won: { week: string; value: number | null; evidence?: AnalyticsEvidence; period?: AnalyticsPeriod; currency?: string }[];
    forecast: { week: string; value: number | null; evidence?: AnalyticsEvidence; period?: AnalyticsPeriod; currency?: string }[];
    baseline?: number | { value: number | null; period?: AnalyticsPeriod } | null;
    currency?: string;
    period?: AnalyticsPeriod;
    forecast_label?: string;
  };
  voyage?: Record<string, unknown>;
  next_run_day?: string;
  next_run_on?: string;
};
export type AnalyticsCallCard = {
  lead_id: string;
  coach_read?: string | null;
  coach_read_state?: string;
  coach_read_prompt?: string;
  label?: string;
  date?: string;
  duration_min?: number;
  duration_minutes?: number;
  talk_share?: number;
  question_count?: number;
  questions?: { member?: number | null; client?: number | null };
  reviewable?: boolean;
  reason?: string;
  points?: { point: number; label?: string; state: string; quote?: string; reason?: string }[];
  moments?: { label?: string; quote: string; better_wording?: string; better?: string; better_line?: string }[];
  fix?: string;
  example?: string;
  next_step?: {
    action?: string;
    text?: string;
    owner?: string;
    when?: string;
    agreed?: boolean;
    agreement?: string;
  } | string;
};
