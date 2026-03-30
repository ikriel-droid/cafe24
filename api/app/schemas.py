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


class DraftReplyResponse(BaseModel):
    claim_id: int
    draft_reply: str
    confidence: float
    rationale: str


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
