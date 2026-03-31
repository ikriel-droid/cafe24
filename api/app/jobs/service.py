from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory, session_scope
from app.integrations.cafe24.live_service import (
    process_live_webhook_delivery,
    retry_failed_webhooks,
    run_live_sync,
)
from app.integrations.cafe24.oauth_client import Cafe24OAuthClient
from app.integrations.cafe24.sync_service import Cafe24SyncService
from app.models import (
    BackgroundJob,
    BackgroundJobStatus,
    Cafe24WebhookDelivery,
    Claim,
    Merchant,
)
from app.observability.service import get_observability_service
from app.services.claim_service import (
    apply_mock_webhook_to_claim,
    list_claims,
)

try:
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - import fallback for environments without redis installed yet
    redis = None

    class RedisError(Exception):
        pass


class JobHandler(Protocol):
    def __call__(self, session: Session, job: BackgroundJob) -> dict[str, Any] | None: ...


QUEUE_KEY = "claimmate:jobs:ready"
JOB_TYPE_PREFIX = "cafe24."


def build_cafe24_service(settings: Settings) -> Cafe24SyncService:
    return Cafe24SyncService(
        Cafe24OAuthClient(
            client_id=settings.cafe24_client_id or "",
            client_secret=settings.cafe24_client_secret or "",
            redirect_uri=settings.cafe24_redirect_uri or "",
            scopes=settings.cafe24_scopes,
            timeout_seconds=settings.cafe24_api_timeout_seconds,
        )
    )


def _create_redis_client(settings: Settings):
    if redis is None:
        return None

    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def push_job_to_queue(job_id: int, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    client = _create_redis_client(settings)
    if client is None:
        return
    try:
        client.rpush(QUEUE_KEY, str(job_id))
    except RedisError:
        return


def pop_queued_job_ids(limit: int, settings: Settings | None = None) -> list[int]:
    settings = settings or get_settings()
    client = _create_redis_client(settings)
    if client is None:
        return []

    popped_ids: list[int] = []
    try:
        for _ in range(limit):
            value = client.lpop(QUEUE_KEY)
            if value is None:
                break
            if str(value).isdigit():
                popped_ids.append(int(value))
    except RedisError:
        return popped_ids
    return popped_ids


def list_background_jobs(
    session: Session,
    merchant_id: int,
    *,
    limit: int = 10,
    job_type_prefix: str = JOB_TYPE_PREFIX,
) -> list[BackgroundJob]:
    query = (
        select(BackgroundJob)
        .where(
            BackgroundJob.merchant_id == merchant_id,
            BackgroundJob.job_type.like(f"{job_type_prefix}%"),
        )
        .order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())
        .limit(limit)
    )
    return list(session.scalars(query))


def get_background_job(session: Session, merchant_id: int, job_id: int) -> BackgroundJob:
    job = session.get(BackgroundJob, job_id)
    if job is None or job.merchant_id != merchant_id:
        raise ValueError("Background job not found.")
    return job


def get_background_job_counts(
    session: Session,
    merchant_id: int,
    *,
    job_type_prefix: str = JOB_TYPE_PREFIX,
) -> dict[str, int]:
    rows = session.execute(
        select(BackgroundJob.status, func.count(BackgroundJob.id))
        .where(
            BackgroundJob.merchant_id == merchant_id,
            BackgroundJob.job_type.like(f"{job_type_prefix}%"),
        )
        .group_by(BackgroundJob.status)
    ).all()
    counts = {
        "queued_jobs": 0,
        "running_jobs": 0,
        "scheduled_jobs": 0,
        "dead_letter_jobs": 0,
        "succeeded_jobs": 0,
    }
    for status_value, count in rows:
        normalized_status = status_value.value if isinstance(status_value, BackgroundJobStatus) else str(status_value)
        if normalized_status == BackgroundJobStatus.QUEUED.value:
            counts["queued_jobs"] = count
        elif normalized_status == BackgroundJobStatus.RUNNING.value:
            counts["running_jobs"] = count
        elif normalized_status == BackgroundJobStatus.RETRY_SCHEDULED.value:
            counts["scheduled_jobs"] = count
        elif normalized_status == BackgroundJobStatus.DEAD_LETTER.value:
            counts["dead_letter_jobs"] = count
        elif normalized_status == BackgroundJobStatus.SUCCEEDED.value:
            counts["succeeded_jobs"] = count
    return counts


def enqueue_background_job(
    session: Session,
    *,
    merchant_id: int,
    job_type: str,
    payload_json: dict[str, Any] | None,
    triggered_by: str,
    queue_name: str = "default",
    max_retries: int = 3,
) -> BackgroundJob:
    job = BackgroundJob(
        merchant_id=merchant_id,
        queue_name=queue_name,
        job_type=job_type,
        status=BackgroundJobStatus.QUEUED,
        triggered_by=triggered_by,
        payload_json=payload_json,
        retry_count=0,
        max_retries=max_retries,
        available_at=datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    push_job_to_queue(job.id)
    return job


def _retry_delay_seconds(retry_count: int, settings: Settings) -> int:
    base = max(settings.background_job_retry_base_seconds, 0)
    maximum = max(settings.background_job_retry_max_seconds, base)
    delay = base * (2 ** max(retry_count - 1, 0))
    return min(delay, maximum)


def promote_due_jobs(limit: int | None = None, settings: Settings | None = None) -> list[int]:
    settings = settings or get_settings()
    limit = limit or settings.background_job_batch_size
    now = datetime.now(UTC)
    promoted_ids: list[int] = []

    with session_scope() as session:
        jobs = list(
            session.scalars(
                select(BackgroundJob)
                .where(
                    BackgroundJob.status == BackgroundJobStatus.RETRY_SCHEDULED,
                    BackgroundJob.available_at.is_not(None),
                    BackgroundJob.available_at <= now,
                )
                .order_by(BackgroundJob.available_at.asc(), BackgroundJob.id.asc())
                .limit(limit)
            )
        )
        for job in jobs:
            job.status = BackgroundJobStatus.QUEUED
            session.add(job)
            promoted_ids.append(job.id)

    for job_id in promoted_ids:
        push_job_to_queue(job_id, settings)
    return promoted_ids


def _fallback_queued_job_ids(limit: int, excluded_ids: set[int]) -> list[int]:
    with session_scope() as session:
        query: Select[tuple[int]] = (
            select(BackgroundJob.id)
            .where(BackgroundJob.status == BackgroundJobStatus.QUEUED)
            .order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc())
            .limit(limit + len(excluded_ids))
        )
        job_ids = [job_id for job_id in session.scalars(query) if job_id not in excluded_ids]
    return job_ids[:limit]


def process_background_job(job_id: int, settings: Settings | None = None) -> BackgroundJob | None:
    settings = settings or get_settings()
    observability = get_observability_service()
    session = get_session_factory()()
    try:
        job = session.get(BackgroundJob, job_id)
        if job is None or job.status != BackgroundJobStatus.QUEUED:
            return job

        job.status = BackgroundJobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.error_message = None
        session.add(job)
        session.commit()
        session.refresh(job)

        handler = JOB_HANDLERS.get(job.job_type)
        if handler is None:
            raise ValueError(f"Unsupported background job type: {job.job_type}")

        result = handler(session, job) or {}
        job.status = BackgroundJobStatus.SUCCEEDED
        job.result_json = result
        job.error_message = None
        job.completed_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        session.refresh(job)
        observability.record_job_event(job_type=job.job_type, status=job.status.value)
        if job.job_type == "cafe24.live_webhook_delivery":
            event_type = result.get("event_type") if isinstance(result, dict) else None
            if isinstance(event_type, str) and event_type:
                observability.record_webhook_event(event_type=event_type, status="processed")
        return job
    except Exception as exc:
        observability.record_error(
            component="background_job",
            message=str(exc),
            payload={"job_id": job_id},
            severity="warning",
        )
        session.rollback()
        retry_session = get_session_factory()()
        try:
            job = retry_session.get(BackgroundJob, job_id)
            if job is None:
                return None
            job.retry_count += 1
            job.error_message = str(exc)
            if job.retry_count >= job.max_retries:
                job.status = BackgroundJobStatus.DEAD_LETTER
                job.completed_at = datetime.now(UTC)
                job.available_at = None
                observability.dispatch_alert(
                    severity="critical",
                    event_type="background_job_dead_letter",
                    message=f"Background job moved to dead letter: {job.job_type}",
                    payload={
                        "job_id": job.id,
                        "job_type": job.job_type,
                        "retry_count": job.retry_count,
                        "error_message": str(exc),
                    },
                )
            else:
                job.status = BackgroundJobStatus.RETRY_SCHEDULED
                delay_seconds = _retry_delay_seconds(job.retry_count, settings)
                job.available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
                job.completed_at = None
            retry_session.add(job)
            retry_session.commit()
            retry_session.refresh(job)
            observability.record_job_event(job_type=job.job_type, status=job.status.value)
            return job
        finally:
            retry_session.close()
    finally:
        session.close()


def run_background_job_tick(limit: int | None = None, settings: Settings | None = None) -> list[int]:
    settings = settings or get_settings()
    limit = limit or settings.background_job_batch_size

    promote_due_jobs(limit=limit, settings=settings)
    queued_ids = pop_queued_job_ids(limit=limit, settings=settings)
    excluded = set(queued_ids)
    if len(queued_ids) < limit:
        queued_ids.extend(_fallback_queued_job_ids(limit - len(queued_ids), excluded))

    processed_ids: list[int] = []
    for job_id in queued_ids:
        processed = process_background_job(job_id, settings=settings)
        if processed is not None:
            processed_ids.append(job_id)
    return processed_ids


def build_job_label(job_type: str) -> str:
    labels = {
        "cafe24.mock_sync": "Mock Sync",
        "cafe24.live_sync": "Live Sync",
        "cafe24.mock_webhook": "Mock Webhook",
        "cafe24.live_webhook_delivery": "Live Webhook",
        "cafe24.retry_failed_webhooks": "Retry Failed Webhooks",
    }
    return labels.get(job_type, job_type)


def _build_job_result_preview(job: BackgroundJob) -> str | None:
    result = job.result_json
    if not isinstance(result, dict):
        return None
    preview_parts: list[str] = []
    for key in ("last_sync_result", "event_type", "order_no", "claim_id", "processed"):
        value = result.get(key)
        if value is None:
            continue
        preview_parts.append(f"{key}={value}")
    return " / ".join(preview_parts) if preview_parts else None


def serialize_background_job(job: BackgroundJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "queue_name": job.queue_name,
        "job_type": job.job_type,
        "job_label": build_job_label(job.job_type),
        "status": job.status.value,
        "triggered_by": job.triggered_by,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "payload_json": job.payload_json,
        "result_json": job.result_json,
        "result_preview": _build_job_result_preview(job),
        "error_message": job.error_message,
        "available_at": job.available_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _build_mock_webhook_automation_summary(claim: Claim | None) -> str | None:
    if claim is None:
        return None

    latest_reply = next(
        (action for action in claim.suggested_actions if action.action_type == "draft_reply"),
        None,
    )
    summary_parts: list[str] = []
    if claim.ai_label:
        summary_parts.append(f"AI 분류: {claim.ai_label} ({claim.category.value})")
    if latest_reply is not None:
        summary_parts.append("답변 초안 생성 완료")
    return " / ".join(summary_parts) if summary_parts else None


def _handle_mock_sync(session: Session, job: BackgroundJob) -> dict[str, Any]:
    settings = get_settings()
    merchant = session.get(Merchant, job.merchant_id)
    if merchant is None:
        raise ValueError("Merchant not found for mock sync job.")
    claims = list_claims(session, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    status_payload = service.run_mock_sync(session, merchant, claims, settings)
    return {
        "last_sync_result": status_payload["last_sync_result"],
        "last_sync_batch_id": status_payload["last_sync_batch_id"],
        "synced_claims": status_payload["synced_claims"],
    }


def _handle_live_sync(session: Session, job: BackgroundJob) -> dict[str, Any]:
    settings = get_settings()
    merchant = session.get(Merchant, job.merchant_id)
    if merchant is None:
        raise ValueError("Merchant not found for live sync job.")
    service = build_cafe24_service(settings)
    limit = 20
    if isinstance(job.payload_json, dict):
        raw_limit = job.payload_json.get("limit")
        if isinstance(raw_limit, int):
            limit = raw_limit
    connection = run_live_sync(session, merchant, service.oauth_client, settings, limit=limit)
    return {
        "last_sync_result": connection.last_sync_result,
        "last_sync_batch_id": connection.last_sync_batch_id,
        "synced_orders": connection.synced_orders,
        "synced_claims": connection.synced_claims,
    }


def _handle_mock_webhook(session: Session, job: BackgroundJob) -> dict[str, Any]:
    settings = get_settings()
    merchant = session.get(Merchant, job.merchant_id)
    if merchant is None:
        raise ValueError("Merchant not found for mock webhook job.")
    payload = job.payload_json or {}
    event_type = str(payload.get("event_type") or "")
    order_no_value = payload.get("order_no")
    order_no = str(order_no_value) if isinstance(order_no_value, str) and order_no_value.strip() else None
    affected_claim = apply_mock_webhook_to_claim(
        session,
        merchant_id=merchant.id,
        event_type=event_type,
        order_no=order_no,
    )
    claims = list_claims(session, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    service.simulate_webhook(
        session,
        merchant,
        claims,
        settings,
        event_type=event_type,
        order_no=order_no,
        claim_id=affected_claim.id if affected_claim is not None else None,
        automation_summary=_build_mock_webhook_automation_summary(affected_claim),
    )
    return {
        "event_type": event_type,
        "order_no": order_no,
        "claim_id": affected_claim.id if affected_claim is not None else None,
    }


def _handle_live_webhook_delivery(session: Session, job: BackgroundJob) -> dict[str, Any]:
    payload = job.payload_json or {}
    delivery_id = payload.get("delivery_id")
    if not isinstance(delivery_id, int):
        raise ValueError("delivery_id is required for live webhook jobs.")

    delivery = session.get(Cafe24WebhookDelivery, delivery_id)
    if delivery is None:
        raise ValueError("Webhook delivery not found.")

    claim = process_live_webhook_delivery(session, delivery)
    session.refresh(delivery)
    if delivery.status in {"failed", "dead_letter"}:
        raise ValueError(delivery.failed_reason or "Cafe24 live webhook processing failed.")

    return {
        "delivery_id": delivery.id,
        "event_type": delivery.event_type,
        "claim_id": claim.id if claim is not None else None,
        "processed": True,
    }


def _handle_retry_failed_webhooks(session: Session, job: BackgroundJob) -> dict[str, Any]:
    merchant = session.get(Merchant, job.merchant_id)
    if merchant is None:
        raise ValueError("Merchant not found for retry job.")
    payload = job.payload_json or {}
    limit = payload.get("limit") if isinstance(payload.get("limit"), int) else 10
    deliveries = retry_failed_webhooks(session, merchant, limit=limit)
    remaining_failed = session.scalar(
        select(func.count(Cafe24WebhookDelivery.id)).where(
            Cafe24WebhookDelivery.merchant_id == merchant.id,
            Cafe24WebhookDelivery.status.in_(("failed", "dead_letter")),
        )
    )
    return {
        "processed": len(deliveries),
        "remaining_failed": remaining_failed or 0,
    }


JOB_HANDLERS: dict[str, JobHandler] = {
    "cafe24.mock_sync": _handle_mock_sync,
    "cafe24.live_sync": _handle_live_sync,
    "cafe24.mock_webhook": _handle_mock_webhook,
    "cafe24.live_webhook_delivery": _handle_live_webhook_delivery,
    "cafe24.retry_failed_webhooks": _handle_retry_failed_webhooks,
}
