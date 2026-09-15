// ============================================================
// Types -- mirror app/schemas.py in the merged backend exactly.
// Keep these two in sync by hand; there's no shared codegen here.
// ============================================================

export type Decision = 'ALLOW' | 'REVIEW' | 'BLOCK';
export type RiskLevel = 'Normal' | 'Low' | 'Medium' | 'High' | 'Critical';

// ---------------------------------------------------------------------------
// KPIs / analytics
// ---------------------------------------------------------------------------

export interface KpiResponse {
  total_subscribers: number;
  total_packages: number;
  total_sessions: number;
  total_upload_gb: number;
  total_download_gb: number;
  total_usage_gb: number;
  average_risk: number;
  maximum_risk: number;
  active_days: number;
  sessions_per_day: number;
  block_count: number;
  review_count: number;
  allow_count: number;
}

export interface DailyPoint {
  date: string;
  total_sessions: number;
  average_risk: number;
  average_download_gb: number | null;
  average_upload_gb: number | null;
  average_total_usage_gb: number | null;
  total_duration_minutes: number | null;
  block_count: number;
  review_count: number;
}

export interface RiskBand {
  label: string;
  count: number;
  percentage: number;
}

export interface PackageStat {
  name: string;
  value: number;
  percentage: number;
}

export interface PackageStatsResponse {
  distribution: PackageStat[];
  usage: PackageStat[];
  usage_is_approximate: boolean;
}

export interface WindowSummary {
  label: string;
  date_from: string;
  date_to: string;
  days_with_data: number;
  total_subscribers: number;
  total_sessions: number;
  average_risk: number;
  maximum_risk: number;
  total_usage_gb: number;
  block_count: number;
  review_count: number;
}

export interface AnalyticsWindowsResponse {
  as_of_date: string;
  last_7_days: WindowSummary;
  last_30_days: WindowSummary;
}

export interface RuleTriggerStat {
  rule_id: string;
  feature: string;
  upper_limit: number;
  points: number;
  trigger_count: number;
  trigger_rate: number;
}

export interface RuleStatisticsResponse {
  date_from: string | null;
  date_to: string | null;
  total_rows: number;
  block_count: number;
  review_count: number;
  allow_count: number;
  rules: RuleTriggerStat[];
}

export interface SystemHealthResponse {
  database: 'connected' | 'unreachable';
  model_version: string;
  rule_engine_active_rules: number;
  websocket_connections: number;
  latest_session_date: string | null;
}

// ---------------------------------------------------------------------------
// Subscribers
// ---------------------------------------------------------------------------

export interface SubscriberRow {
  session_date: string;
  account_num: string | null;
  subscriber_id: string;
  risk_score_0_100: number;
  risk_level: RiskLevel;
  sessions_per_day: number;
  daily_usage_gb: number;
  history_days: number;
  rule_score: number | null;
  ml_score: number | null;
  final_score: number | null;
  decision: Decision | null;
  triggered_rules: string[];
}

export interface SubscriberListResponse {
  items: SubscriberRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SubscriberDetailPoint {
  session_date: string;
  total_input_gb: number | null;
  total_output_gb: number | null;
  risk_score_0_100: number;
  final_score: number | null;
  decision: Decision | null;
}

export interface SubscriberDetail {
  subscriber_id: string;
  account_num: string | null;
  latest_session_date: string;
  maximum_risk_score: number;
  average_risk_score: number;
  risk_level: RiskLevel;
  sessions_per_day: number;
  daily_usage_gb: number;
  average_session_usage_gb: number | null;
  total_duration_minutes: number | null;
  average_session_duration_minutes: number | null;
  total_input_gb: number | null;
  total_output_gb: number | null;
  offer_name: string | null;
  history_days: number;
  history: SubscriberDetailPoint[];
  latest_decision: Decision | null;
  latest_final_score: number | null;
  triggered_rules_latest: string[];
}

// ---------------------------------------------------------------------------
// Scoring (on-demand)
// ---------------------------------------------------------------------------

export interface ScoreRequest {
  sessions_per_day?: number;
  daily_usage_gb?: number;
  average_session_usage_gb?: number;
  total_duration_minutes?: number;
  average_session_duration_minutes?: number;
  total_input_gb?: number;
  total_output_gb?: number;
  offer_count?: number;
  offer_name?: string;
  Ratio?: number;
}

export interface ScoreResponse {
  risk_score_0_100: number;
  risk_level: string;
  anomaly_score: number;
  features_used: Record<string, number>;
  rule_score: number;
  ml_score: number;
  final_score: number;
  decision: Decision;
  triggered_rules: string[];
}

// ---------------------------------------------------------------------------
// WebSocket events -- mirror app/routers/ws.py + ingest_worker.py alerts
// ---------------------------------------------------------------------------

export type WsEventType = 'connected' | 'fraud_event';

export interface WsEvent {
  type: WsEventType;
  timestamp?: string;
  connections?: number;
  subscriber_id?: string;
  account_num?: string | null;
  session_date?: string;
  decision?: Decision;
  final_score?: number;
  triggered_rules?: string;
}

// ---------------------------------------------------------------------------
// Global filter state
// ---------------------------------------------------------------------------

export interface DateRange {
  dateFrom: string | null;
  dateTo: string | null;
}
