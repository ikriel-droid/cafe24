from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ClaimCategory, ClaimStatus, ClaimUrgency


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClaimMessageRead(ORMModel):
    id: int
    role: str
    body: str
    created_at: datetime


class SuggestedActionRead(ORMModel):
    id: int
    action_type: str
    draft_reply: str
    confidence: float
    rationale: str
    created_at: datetime


class AuditLogRead(ORMModel):
    id: int
    actor: str
    event_type: str
    payload_json: dict[str, Any] | None
    created_at: datetime


class ReplyDeliveryRead(ORMModel):
    id: int
    actor: str
    attempt_no: int
    channel: str
    status: str
    provider: str
    destination: str | None
    reply_body: str
    external_delivery_id: str | None
    request_payload_json: dict[str, Any] | None
    response_payload_json: dict[str, Any] | None
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AIUsageRead(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class AIEvaluationCheckRead(BaseModel):
    name: str
    passed: bool
    detail: str


class AIResultMetadataRead(BaseModel):
    provider_name: str
    requested_provider_name: str
    model_name: str
    prompt_key: str
    prompt_version: str
    fallback_used: bool
    fallback_reason: str | None
    review_required: bool
    review_reasons: list[str]
    evaluation_summary: str
    evaluation_checks: list[AIEvaluationCheckRead]
    usage: AIUsageRead


class AIInvocationLogRead(ORMModel):
    id: int
    action_type: str
    provider_name: str
    requested_provider_name: str
    model_name: str
    prompt_key: str
    prompt_version: str
    fallback_used: bool
    fallback_reason: str | None
    review_required: bool
    review_reasons_json: list[str] | None
    evaluation_summary: str
    evaluation_checks_json: list[dict[str, Any]] | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    response_json: dict[str, Any] | None
    created_at: datetime


class ClaimAutomationRead(BaseModel):
    auto_triaged: bool
    auto_triaged_at: datetime | None
    reply_ready: bool
    draft_reply_preview: str | None
    reply_sent: bool
    follow_up_needed: bool
    reply_sent_at: datetime | None
    reply_sent_by: str | None
    latest_delivery_status: str | None
    latest_delivery_channel: str | None
    latest_delivery_at: datetime | None
    latest_delivery_error: str | None
    latest_delivery_destination: str | None
    delivery_attempt_count: int
    can_retry_delivery: bool
    classification_confidence: float | None
    draft_reply_confidence: float | None
    source_event: str | None


class ClaimListItem(ORMModel):
    id: int
    order_no: str
    customer_name: str
    product_name: str
    reason_preview: str
    category: ClaimCategory
    status: ClaimStatus
    urgency: ClaimUrgency
    ai_label: str | None
    created_at: datetime
    updated_at: datetime
    automation: ClaimAutomationRead


class ClaimDetail(ClaimListItem):
    merchant_id: int
    reason_text: str
    messages: list[ClaimMessageRead]
    suggested_actions: list[SuggestedActionRead]
    audit_logs: list[AuditLogRead]
    reply_deliveries: list[ReplyDeliveryRead]
    ai_invocations: list[AIInvocationLogRead] = Field(default_factory=list)


class ClaimStatusUpdate(BaseModel):
    status: ClaimStatus
    actor: str = Field(default="merchant_operator")


class ClaimNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=1000)
    actor: str = Field(default="merchant_operator")


class ClaimReplySend(BaseModel):
    reply_body: str | None = Field(default=None, max_length=4000)
    actor: str = Field(default="merchant_operator")
    mark_done: bool = Field(default=True)


class ClaimReplyRetry(BaseModel):
    actor: str = Field(default="merchant_operator")
    mark_done: bool = Field(default=True)


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthSessionMerchant(BaseModel):
    id: int
    name: str
    mall_name: str


class AuthSessionResponse(BaseModel):
    user_id: int
    email: str
    name: str
    role: str
    merchant: AuthSessionMerchant


class PolicyRead(ORMModel):
    id: int
    merchant_id: int
    exchange_window_days: int
    return_window_days: int
    return_shipping_fee: int
    exchange_shipping_fee: int
    refund_rule_text: str
    exception_rule_text: str
    created_at: datetime
    updated_at: datetime


class PolicyUpdate(BaseModel):
    exchange_window_days: int = Field(ge=0)
    return_window_days: int = Field(ge=0)
    return_shipping_fee: int = Field(ge=0)
    exchange_shipping_fee: int = Field(ge=0)
    refund_rule_text: str
    exception_rule_text: str


class ClassificationResponse(BaseModel):
    claim_id: int
    category: ClaimCategory
    ai_label: str
    urgency: ClaimUrgency
    confidence: float
    rationale: str
    meta: AIResultMetadataRead


class DraftReplyResponse(BaseModel):
    claim_id: int
    draft_reply: str
    confidence: float
    rationale: str
    meta: AIResultMetadataRead


class Cafe24MockWebhookRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    order_no: str | None = Field(default=None, max_length=100)


class Cafe24TokenRefreshResponse(BaseModel):
    status: str
    refreshed_at: datetime
    access_token_expires_at: datetime | None


class Cafe24WebhookIngestResponse(BaseModel):
    status: str
    duplicate: bool
    dedupe_key: str
    event_type: str
    merchant_id: int
    job_id: int | None = None
    claim_id: int | None = None
    retry_count: int = 0
    failed_reason: str | None = None
    processed_at: datetime | None = None
    next_retry_at: datetime | None = None


class Cafe24ActivityEvent(BaseModel):
    occurred_at: datetime
    event_type: str
    status: str
    title: str
    detail: str
    batch_id: str | None
    claim_id: int | None = None
    order_no: str | None = None


class BackgroundJobRead(BaseModel):
    id: int
    queue_name: str
    job_type: str
    job_label: str
    status: str
    triggered_by: str
    retry_count: int
    max_retries: int
    payload_json: dict[str, Any] | None = None
    result_json: dict[str, Any] | None = None
    result_preview: str | None = None
    error_message: str | None = None
    available_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BackgroundJobRunResponse(BaseModel):
    processed_job_ids: list[int]


class Cafe24IntegrationStatus(BaseModel):
    merchant_id: int
    mall_name: str
    connection_mode: str
    health_status: str
    health_title: str
    health_detail: str
    next_action_type: str
    next_action_label: str
    next_action_href: str | None
    connected: bool
    oauth_configured: bool
    webhook_endpoint_ready: bool
    authorize_url: str | None
    mall_id: str | None = None
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
    last_token_refreshed_at: datetime | None = None
    webhook_secret_configured: bool = False
    last_sync_result: str
    last_synced_at: datetime | None
    last_sync_batch_id: str | None
    synced_orders: int
    synced_claims: int
    pending_claims: int
    pending_webhooks: int
    failed_webhooks: int = 0
    retryable_webhooks: int = 0
    queued_jobs: int = 0
    running_jobs: int = 0
    scheduled_jobs: int = 0
    dead_letter_jobs: int = 0
    recent_jobs: list[BackgroundJobRead] = Field(default_factory=list)
    recent_events: list[Cafe24ActivityEvent]
    notes: list[str]


class DashboardCafe24Overview(BaseModel):
    health_status: str
    health_title: str
    health_detail: str
    last_sync_result: str
    last_synced_at: datetime | None
    pending_webhooks: int
    recent_activity_count: int
    queued_jobs: int
    running_jobs: int
    scheduled_jobs: int
    dead_letter_jobs: int
    latest_event_title: str | None
    latest_event_status: str | None
    latest_event_occurred_at: datetime | None
    next_action_type: str
    next_action_label: str
    next_action_href: str | None


class DiagnosticsRequestRouteRead(BaseModel):
    method: str
    route: str
    request_count: int
    error_count: int
    slow_count: int
    avg_duration_ms: float
    max_duration_ms: float
    last_status_code: int | None
    last_seen_at: datetime | None


class DiagnosticsRequestMetricsRead(BaseModel):
    total_requests: int
    client_errors: int
    server_errors: int
    slow_requests: int
    routes: list[DiagnosticsRequestRouteRead] = Field(default_factory=list)


class DiagnosticsWebhookEventRead(BaseModel):
    event_type: str
    count: int
    duplicate_count: int
    failed_count: int
    last_status: str | None
    last_seen_at: datetime | None


class DiagnosticsWebhookMetricsRead(BaseModel):
    total_received: int
    duplicate_count: int
    failed_count: int
    events: list[DiagnosticsWebhookEventRead] = Field(default_factory=list)


class DiagnosticsJobTypeRead(BaseModel):
    job_type: str
    run_count: int
    success_count: int
    retry_scheduled_count: int
    dead_letter_count: int
    last_status: str | None
    last_seen_at: datetime | None


class DiagnosticsJobMetricsRead(BaseModel):
    total_runs: int
    succeeded: int
    retry_scheduled: int
    dead_letter: int
    job_types: list[DiagnosticsJobTypeRead] = Field(default_factory=list)


class DiagnosticsAlertRead(BaseModel):
    occurred_at: datetime
    severity: str
    event_type: str
    message: str
    payload_json: dict[str, Any] | None
    channel: str
    delivery_status: str
    delivery_error: str | None


class DiagnosticsErrorRead(BaseModel):
    occurred_at: datetime
    component: str
    severity: str
    message: str
    payload_json: dict[str, Any] | None


class DiagnosticsCircuitBreakerRead(BaseModel):
    service_name: str
    state: str
    failure_count: int
    failure_threshold: int
    recovery_seconds: int
    opened_at: datetime | None
    last_failure_at: datetime | None
    last_success_at: datetime | None


class DiagnosticsRateLimitPolicyRead(BaseModel):
    scope: str
    limit: int
    window_seconds: int
    active_keys: int


class DiagnosticsTimeoutPolicyRead(BaseModel):
    target: str
    timeout_seconds: int


class AdminDiagnosticsRead(BaseModel):
    generated_at: datetime
    app_name: str
    environment: str
    uptime_seconds: int
    request_metrics: DiagnosticsRequestMetricsRead
    webhook_metrics: DiagnosticsWebhookMetricsRead
    job_metrics: DiagnosticsJobMetricsRead
    recent_alerts: list[DiagnosticsAlertRead] = Field(default_factory=list)
    recent_errors: list[DiagnosticsErrorRead] = Field(default_factory=list)
    circuit_breakers: list[DiagnosticsCircuitBreakerRead] = Field(default_factory=list)
    rate_limit_policies: list[DiagnosticsRateLimitPolicyRead] = Field(default_factory=list)
    timeout_policies: list[DiagnosticsTimeoutPolicyRead] = Field(default_factory=list)
    masking_rules: list[str] = Field(default_factory=list)
    cafe24: DashboardCafe24Overview | None = None
    recent_jobs: list[BackgroundJobRead] = Field(default_factory=list)
    recent_events: list[Cafe24ActivityEvent] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    total_claims: int
    open_claims: int
    in_review_claims: int
    approved_claims: int
    rejected_claims: int
    done_claims: int
    high_urgency_claims: int
    auto_triaged_claims: int
    reply_ready_claims: int
    reply_sent_claims: int
    follow_up_needed_claims: int
    by_category: dict[str, int]
    cafe24: DashboardCafe24Overview | None = None
