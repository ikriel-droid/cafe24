from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ClaimCategory(str, Enum):
    DELIVERY = "delivery"
    CANCELLATION = "cancellation"
    EXCHANGE = "exchange"
    RETURN = "return"
    REFUND = "refund"
    DEFECT = "defect"
    MISDELIVERY = "misdelivery"
    OTHER = "other"


class ClaimStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DONE = "done"


class ClaimUrgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OperatorRole(str, Enum):
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"


class ReplyDeliveryChannel(str, Enum):
    MANUAL_HANDOFF = "manual_handoff"
    WEBHOOK = "webhook"


class ReplyDeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"


class BackgroundJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class MerchantDataOrigin(str, Enum):
    DEMO = "demo"
    LIVE = "live"


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mall_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    data_origin: Mapped[MerchantDataOrigin] = mapped_column(
        SqlEnum(MerchantDataOrigin, native_enum=False),
        nullable=False,
        default=MerchantDataOrigin.LIVE,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    policy: Mapped["Policy | None"] = relationship(back_populates="merchant", uselist=False)
    claims: Mapped[list["Claim"]] = relationship(back_populates="merchant")
    operators: Mapped[list["OperatorUser"]] = relationship(back_populates="merchant")
    cafe24_connection: Mapped["Cafe24Connection | None"] = relationship(back_populates="merchant", uselist=False)
    cafe24_webhook_deliveries: Mapped[list["Cafe24WebhookDelivery"]] = relationship(back_populates="merchant")
    cafe24_integration_events: Mapped[list["Cafe24IntegrationEvent"]] = relationship(back_populates="merchant")
    background_jobs: Mapped[list["BackgroundJob"]] = relationship(back_populates="merchant")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, unique=True)
    exchange_window_days: Mapped[int] = mapped_column(Integer, default=7)
    return_window_days: Mapped[int] = mapped_column(Integer, default=7)
    return_shipping_fee: Mapped[int] = mapped_column(Integer, default=3000)
    exchange_shipping_fee: Mapped[int] = mapped_column(Integer, default=6000)
    refund_rule_text: Mapped[str] = mapped_column(Text, default="")
    exception_rule_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="policy")


class OperatorUser(Base):
    __tablename__ = "operator_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[OperatorRole] = mapped_column(
        SqlEnum(OperatorRole, native_enum=False),
        nullable=False,
        default=OperatorRole.AGENT,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="operators")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ClaimCategory] = mapped_column(
        SqlEnum(ClaimCategory, native_enum=False),
        nullable=False,
        default=ClaimCategory.OTHER,
    )
    status: Mapped[ClaimStatus] = mapped_column(
        SqlEnum(ClaimStatus, native_enum=False),
        nullable=False,
        default=ClaimStatus.OPEN,
    )
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    urgency: Mapped[ClaimUrgency] = mapped_column(
        SqlEnum(ClaimUrgency, native_enum=False),
        nullable=False,
        default=ClaimUrgency.MEDIUM,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="claims")
    messages: Mapped[list["ClaimMessage"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by=lambda: (ClaimMessage.created_at, ClaimMessage.id),
    )
    suggested_actions: Mapped[list["SuggestedAction"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by=lambda: (SuggestedAction.created_at.desc(), SuggestedAction.id.desc()),
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by=lambda: (AuditLog.created_at.desc(), AuditLog.id.desc()),
    )
    reply_deliveries: Mapped[list["ReplyDelivery"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by=lambda: (ReplyDelivery.created_at.desc(), ReplyDelivery.id.desc()),
    )
    ai_invocations: Mapped[list["AIInvocationLog"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by=lambda: (AIInvocationLog.created_at.desc(), AIInvocationLog.id.desc()),
    )


class ClaimMessage(Base):
    __tablename__ = "claim_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="messages")


class SuggestedAction(Base):
    __tablename__ = "suggested_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_reply: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="suggested_actions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="audit_logs")


class ReplyDelivery(Base):
    __tablename__ = "reply_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    channel: Mapped[ReplyDeliveryChannel] = mapped_column(
        SqlEnum(ReplyDeliveryChannel, native_enum=False),
        nullable=False,
        default=ReplyDeliveryChannel.MANUAL_HANDOFF,
    )
    status: Mapped[ReplyDeliveryStatus] = mapped_column(
        SqlEnum(ReplyDeliveryStatus, native_enum=False),
        nullable=False,
        default=ReplyDeliveryStatus.SENT,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_handoff")
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reply_body: Mapped[str] = mapped_column(Text, nullable=False)
    external_delivery_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    claim: Mapped["Claim"] = relationship(back_populates="reply_deliveries")


class AIInvocationLog(Base):
    __tablename__ = "ai_invocation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_key: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    review_reasons_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    evaluation_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evaluation_checks_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="ai_invocations")


class Cafe24Connection(Base):
    __tablename__ = "cafe24_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, unique=True, index=True)
    mall_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Bearer")
    scopes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_token_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_result: Mapped[str] = mapped_column(String(64), nullable=False, default="not_started")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_batch_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    synced_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_claims: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="cafe24_connection")
    webhook_deliveries: Mapped[list["Cafe24WebhookDelivery"]] = relationship(back_populates="connection")
    integration_events: Mapped[list["Cafe24IntegrationEvent"]] = relationship(back_populates="connection")


class Cafe24WebhookDelivery(Base):
    __tablename__ = "cafe24_webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("cafe24_connections.id"), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="cafe24_webhook_deliveries")
    connection: Mapped["Cafe24Connection | None"] = relationship(back_populates="webhook_deliveries")


class Cafe24IntegrationEvent(Base):
    __tablename__ = "cafe24_integration_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("cafe24_connections.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_no: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchant: Mapped["Merchant"] = relationship(back_populates="cafe24_integration_events")
    connection: Mapped["Cafe24Connection | None"] = relationship(back_populates="integration_events")


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    queue_name: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[BackgroundJobStatus] = mapped_column(
        SqlEnum(BackgroundJobStatus, native_enum=False),
        nullable=False,
        default=BackgroundJobStatus.QUEUED,
        index=True,
    )
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="background_jobs")
