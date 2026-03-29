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

export interface ClaimAutomation {
  auto_triaged: boolean;
  auto_triaged_at: string | null;
  reply_ready: boolean;
  draft_reply_preview: string | null;
  reply_sent: boolean;
  follow_up_needed: boolean;
  reply_sent_at: string | null;
  reply_sent_by: string | null;
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
  latest_event_title: string | null;
  latest_event_status: string | null;
  latest_event_occurred_at: string | null;
  next_action_type: string;
  next_action_label: string;
  next_action_href: string | null;
}

export interface ClassificationResponse {
  claim_id: number;
  category: ClaimCategory;
  ai_label: string;
  urgency: ClaimUrgency;
  confidence: number;
  rationale: string;
}

export interface DraftReplyResponse {
  claim_id: number;
  draft_reply: string;
  confidence: number;
  rationale: string;
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
  recent_events: Cafe24ActivityEvent[];
  notes: string[];
}
