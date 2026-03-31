from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AuditLog,
    BackgroundJob,
    Cafe24Connection,
    Cafe24IntegrationEvent,
    Cafe24WebhookDelivery,
    Claim,
    ClaimMessage,
    Merchant,
    MerchantDataOrigin,
    OperatorUser,
    Policy,
    ReplyDelivery,
    SuggestedAction,
)
from app.services.seed import seed_demo_data


def list_demo_merchant_ids(session: Session) -> list[int]:
    return list(
        session.scalars(
            select(Merchant.id).where(Merchant.data_origin == MerchantDataOrigin.DEMO).order_by(Merchant.id.asc())
        )
    )


def delete_demo_data(session: Session) -> dict[str, int]:
    merchant_ids = list_demo_merchant_ids(session)
    if not merchant_ids:
        return {"deleted_demo_merchants": 0, "deleted_demo_claims": 0}

    claim_ids = list(session.scalars(select(Claim.id).where(Claim.merchant_id.in_(merchant_ids))))

    if claim_ids:
        session.execute(delete(ReplyDelivery).where(ReplyDelivery.claim_id.in_(claim_ids)))
        session.execute(delete(AuditLog).where(AuditLog.claim_id.in_(claim_ids)))
        session.execute(delete(SuggestedAction).where(SuggestedAction.claim_id.in_(claim_ids)))
        session.execute(delete(ClaimMessage).where(ClaimMessage.claim_id.in_(claim_ids)))

    session.execute(delete(BackgroundJob).where(BackgroundJob.merchant_id.in_(merchant_ids)))
    session.execute(delete(Cafe24IntegrationEvent).where(Cafe24IntegrationEvent.merchant_id.in_(merchant_ids)))
    session.execute(delete(Cafe24WebhookDelivery).where(Cafe24WebhookDelivery.merchant_id.in_(merchant_ids)))
    session.execute(delete(Cafe24Connection).where(Cafe24Connection.merchant_id.in_(merchant_ids)))
    session.execute(delete(OperatorUser).where(OperatorUser.merchant_id.in_(merchant_ids)))
    session.execute(delete(Policy).where(Policy.merchant_id.in_(merchant_ids)))
    session.execute(delete(Claim).where(Claim.merchant_id.in_(merchant_ids)))
    session.execute(delete(Merchant).where(Merchant.id.in_(merchant_ids)))
    session.commit()

    return {
        "deleted_demo_merchants": len(merchant_ids),
        "deleted_demo_claims": len(claim_ids),
    }


def reset_demo_data(session: Session, *, allow_in_production: bool = False) -> dict[str, int]:
    settings = get_settings()
    if settings.app_env == "production" and not allow_in_production:
        raise RuntimeError("Demo data reset is blocked in production environments.")

    deleted_summary = delete_demo_data(session)
    seed_demo_data(session)
    return {
        **deleted_summary,
        "reseeded_demo_merchants": len(list_demo_merchant_ids(session)),
    }


def soft_delete_claim(
    session: Session,
    claim_id: int,
    *,
    actor: str,
    reason: str,
    retain_days: int | None = None,
) -> Claim:
    claim = session.scalar(select(Claim).where(Claim.id == claim_id, Claim.deleted_at.is_(None)))
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    retention_days = retain_days if retain_days is not None else get_settings().claim_retention_days
    now = datetime.now(UTC)
    claim.deleted_at = now
    claim.deleted_by = actor
    claim.delete_reason = reason.strip() or "soft_deleted"
    claim.retention_until = now + timedelta(days=retention_days)
    session.add(claim)
    session.add(
        AuditLog(
            claim_id=claim.id,
            actor=actor,
            event_type="claim_soft_deleted",
            payload_json={
                "reason": claim.delete_reason,
                "retention_until": claim.retention_until.isoformat() if claim.retention_until else None,
            },
        )
    )
    session.commit()
    session.refresh(claim)
    return claim


def purge_soft_deleted_claims(session: Session, *, now: datetime | None = None) -> int:
    current_time = now or datetime.now(UTC)
    claim_ids = list(
        session.scalars(
            select(Claim.id).where(
                Claim.deleted_at.is_not(None),
                Claim.retention_until.is_not(None),
                Claim.retention_until <= current_time,
            )
        )
    )
    if not claim_ids:
        return 0

    session.execute(delete(ReplyDelivery).where(ReplyDelivery.claim_id.in_(claim_ids)))
    session.execute(delete(AuditLog).where(AuditLog.claim_id.in_(claim_ids)))
    session.execute(delete(SuggestedAction).where(SuggestedAction.claim_id.in_(claim_ids)))
    session.execute(delete(ClaimMessage).where(ClaimMessage.claim_id.in_(claim_ids)))
    session.execute(delete(Claim).where(Claim.id.in_(claim_ids)))
    session.commit()
    return len(claim_ids)
