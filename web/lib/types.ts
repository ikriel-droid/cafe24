export type ClaimCategory =
  | "delivery"
  | "cancellation"
  | "exchange"
  | "return"
  | "refund"
  | "defect"
  | "misdelivery"
  | "other";

export type ClaimStatus = "open" | "in_review" | "approved" | "rejected" | "done";
export type ClaimUrgency = "low" | "medium" | "high";
export type OperatorRole = "manager" | "agent" | "viewer";

export interface AuthMerchant {
  id: number;
  name: string;
  mall_name: string;
}

export interface AuthSession {
  user_id: number;
  email: string;
  name: string;
  role: OperatorRole;
  merchant: AuthMerchant;
}

export interface ClaimMessage {
  id: number;
  role: string;
  body: string;
  created_at: string;
}

export interface SuggestedAction {
  id: number;
  action_type: string;
  draft_reply: string;
  confidence: number;
  rationale: string;
  created_at: string;
}

export interface AuditLog {
  id: number;
  actor: string;
  event_type: string;
  payload_json: Record<string, unknown> | null;
  created_at: string;
}

export interface ReplyDelivery {
  id: number;
  actor: string;
  attempt_no: number;
  channel: string;
  status: string;
  provider: string;
  destination: string | null;
  reply_body: string;
  external_delivery_id: string | null;
  request_payload_json: Record<string, unknown> | null;
  response_payload_json: Record<string, unknown> | null;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface AIEvaluationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface AIResultMetadata {
  provider_name: string;
  requested_provider_name: string;
  model_name: string;
  prompt_key: string;
  prompt_version: string;
  fallback_used: boolean;
  fallback_reason: string | null;
  review_required: boolean;
  review_reasons: string[];
  evaluation_summary: string;
  evaluation_checks: AIEvaluationCheck[];
  usage: AIUsage;
}

export interface AIInvocationLog {
  id: number;
  action_type: string;
  provider_name: string;
  requested_provider_name: string;
  model_name: string;
  prompt_key: string;
  prompt_version: string;
  fallback_used: boolean;
  fallback_reason: string | null;
  review_required: boolean;
  review_reasons_json: string[] | null;
  evaluation_summary: string;
  evaluation_checks_json: Array<Record<string, unknown>> | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  response_json: Record<string, unknown> | null;
  created_at: string;
}

export interface ClaimAutomation {
  auto_triaged: boolean;
  auto_triaged_at: string | null;
  reply_ready: boolean;
  draft_reply_preview: string | null;
  reply_sent: boolean;
  follow_up_needed: boolean;
  reply_sent_at: string | null;
  reply_sent_by: string | null;
  latest_delivery_status: string | null;
  latest_delivery_channel: string | null;
  latest_delivery_at: string | null;
  latest_delivery_error: string | null;
  latest_delivery_destination: string | null;
  delivery_attempt_count: number;
  can_retry_delivery: boolean;
  classification_confidence: number | null;
  draft_reply_confidence: number | null;
  source_event: string | null;
}

export interface Claim {
  id: number;
  merchant_id?: number;
  order_no: string;
  customer_name: string;
  product_name: string;
  reason_preview?: string;
  category: ClaimCategory;
  status: ClaimStatus;
  urgency: ClaimUrgency;
  ai_label: string | null;
  automation: ClaimAutomation;
  reason_text?: string;
  created_at: string;
  updated_at: string;
  messages?: ClaimMessage[];
  suggested_actions?: SuggestedAction[];
  audit_logs?: AuditLog[];
  reply_deliveries?: ReplyDelivery[];
  ai_invocations?: AIInvocationLog[];
}

export interface Policy {
  id: number;
  merchant_id: number;
  exchange_window_days: number;
  return_window_days: number;
  return_shipping_fee: number;
  exchange_shipping_fee: number;
  refund_rule_text: string;
  exception_rule_text: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  total_claims: number;
  open_claims: number;
  in_review_claims: number;
  approved_claims: number;
  rejected_claims: number;
  done_claims: number;
  high_urgency_claims: number;
  auto_triaged_claims: number;
  reply_ready_claims: number;
  reply_sent_claims: number;
  follow_up_needed_claims: number;
  by_category: Record<string, number>;
  cafe24: DashboardCafe24Overview | null;
}

export interface DashboardCafe24Overview {
  health_status: string;
  health_title: string;
  health_detail: string;
  last_sync_result: string;
  last_synced_at: string | null;
  pending_webhooks: number;
  recent_activity_count: number;
  queued_jobs: number;
  running_jobs: number;
  scheduled_jobs: number;
  dead_letter_jobs: number;
  latest_event_title: string | null;
  latest_event_status: string | null;
  latest_event_occurred_at: string | null;
  next_action_type: string;
  next_action_label: string;
  next_action_href: string | null;
}

export interface DiagnosticsRequestRoute {
  method: string;
  route: string;
  request_count: number;
  error_count: number;
  slow_count: number;
  avg_duration_ms: number;
  max_duration_ms: number;
  last_status_code: number | null;
  last_seen_at: string | null;
}

export interface DiagnosticsRequestMetrics {
  total_requests: number;
  client_errors: number;
  server_errors: number;
  slow_requests: number;
  routes: DiagnosticsRequestRoute[];
}

export interface DiagnosticsWebhookEvent {
  event_type: string;
  count: number;
  duplicate_count: number;
  failed_count: number;
  last_status: string | null;
  last_seen_at: string | null;
}

export interface DiagnosticsWebhookMetrics {
  total_received: number;
  duplicate_count: number;
  failed_count: number;
  events: DiagnosticsWebhookEvent[];
}

export interface DiagnosticsJobType {
  job_type: string;
  run_count: number;
  success_count: number;
  retry_scheduled_count: number;
  dead_letter_count: number;
  last_status: string | null;
  last_seen_at: string | null;
}

export interface DiagnosticsJobMetrics {
  total_runs: number;
  succeeded: number;
  retry_scheduled: number;
  dead_letter: number;
  job_types: DiagnosticsJobType[];
}

export interface DiagnosticsAlert {
  occurred_at: string;
  severity: string;
  event_type: string;
  message: string;
  payload_json: Record<string, unknown> | null;
  channel: string;
  delivery_status: string;
  delivery_error: string | null;
}

export interface DiagnosticsError {
  occurred_at: string;
  component: string;
  severity: string;
  message: string;
  payload_json: Record<string, unknown> | null;
}

export interface DiagnosticsCircuitBreaker {
  service_name: string;
  state: string;
  failure_count: number;
  failure_threshold: number;
  recovery_seconds: number;
  opened_at: string | null;
  last_failure_at: string | null;
  last_success_at: string | null;
}

export interface DiagnosticsRateLimitPolicy {
  scope: string;
  limit: number;
  window_seconds: number;
  active_keys: number;
}

export interface DiagnosticsTimeoutPolicy {
  target: string;
  timeout_seconds: number;
}

export interface AdminDiagnostics {
  generated_at: string;
  app_name: string;
  environment: string;
  uptime_seconds: number;
  request_metrics: DiagnosticsRequestMetrics;
  webhook_metrics: DiagnosticsWebhookMetrics;
  job_metrics: DiagnosticsJobMetrics;
  recent_alerts: DiagnosticsAlert[];
  recent_errors: DiagnosticsError[];
  circuit_breakers: DiagnosticsCircuitBreaker[];
  rate_limit_policies: DiagnosticsRateLimitPolicy[];
  timeout_policies: DiagnosticsTimeoutPolicy[];
  masking_rules: string[];
  cafe24: DashboardCafe24Overview | null;
  recent_jobs: BackgroundJob[];
  recent_events: Cafe24ActivityEvent[];
}

export interface ClassificationResponse {
  claim_id: number;
  category: ClaimCategory;
  ai_label: string;
  urgency: ClaimUrgency;
  confidence: number;
  rationale: string;
  meta: AIResultMetadata;
}

export interface DraftReplyResponse {
  claim_id: number;
  draft_reply: string;
  confidence: number;
  rationale: string;
  meta: AIResultMetadata;
}

export interface Cafe24ActivityEvent {
  occurred_at: string;
  event_type: string;
  status: string;
  title: string;
  detail: string;
  batch_id: string | null;
  claim_id: number | null;
  order_no: string | null;
}

export interface BackgroundJob {
  id: number;
  queue_name: string;
  job_type: string;
  job_label: string;
  status: string;
  triggered_by: string;
  retry_count: number;
  max_retries: number;
  payload_json: Record<string, unknown> | null;
  result_json: Record<string, unknown> | null;
  result_preview: string | null;
  error_message: string | null;
  available_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Cafe24IntegrationStatus {
  merchant_id: number;
  mall_name: string;
  connection_mode: string;
  health_status: string;
  health_title: string;
  health_detail: string;
  next_action_type: string;
  next_action_label: string;
  next_action_href: string | null;
  connected: boolean;
  oauth_configured: boolean;
  webhook_endpoint_ready: boolean;
  authorize_url: string | null;
  last_sync_result: string;
  last_synced_at: string | null;
  last_sync_batch_id: string | null;
  synced_orders: number;
  synced_claims: number;
  pending_claims: number;
  pending_webhooks: number;
  queued_jobs: number;
  running_jobs: number;
  scheduled_jobs: number;
  dead_letter_jobs: number;
  recent_events: Cafe24ActivityEvent[];
  recent_jobs: BackgroundJob[];
  notes: string[];
}
