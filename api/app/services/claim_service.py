from __future__ import annotations

from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import ClassificationResult, DraftReplyResult
from app.ai.factory import get_ai_provider
from app.core.config import get_settings
from app.models import AuditLog, Claim, ClaimCategory, ClaimStatus, Merchant, Policy, SuggestedAction
from app.schemas import ClaimNoteCreate, DashboardSummary, PolicyUpdate


def get_default_merchant(session: Session, merchant_id: int | None = None) -> Merchant:
    settings = get_settings()
    target_merchant_id = merchant_id if merchant_id is not None else settings.default_merchant_id
    merchant = session.get(Merchant, target_merchant_id)
    if merchant is None and merchant_id is None:
        merchant = session.scalar(select(Merchant).limit(1))
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found.")
    return merchant


def get_policy(session: Session, merchant_id: int | None = None) -> Policy:
    merchant = get_default_merchant(session, merchant_id)
    policy = session.scalar(select(Policy).where(Policy.merchant_id == merchant.id))
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")
    return policy


def update_policy(session: Session, payload: PolicyUpdate, merchant_id: int | None = None) -> Policy:
    policy = get_policy(session, merchant_id)
    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def list_claims(
    session: Session,
    merchant_id: int | None = None,
    category: ClaimCategory | None = None,
    status_value: ClaimStatus | None = None,
    search_text: str | None = None,
) -> list[Claim]:
    merchant = get_default_merchant(session, merchant_id)
    query = select(Claim).where(Claim.merchant_id == merchant.id).order_by(Claim.created_at.desc())
    if category:
        query = query.where(Claim.category == category)
    if status_value:
        query = query.where(Claim.status == status_value)
    if search_text:
        normalized_search = search_text.strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.where(
                or_(
                    Claim.order_no.ilike(pattern),
                    Claim.customer_name.ilike(pattern),
                    Claim.product_name.ilike(pattern),
                    Claim.reason_text.ilike(pattern),
                )
            )
    return list(session.scalars(query))


def get_claim(session: Session, claim_id: int) -> Claim:
    query = (
        select(Claim)
        .where(Claim.id == claim_id)
        .options(
            selectinload(Claim.messages),
            selectinload(Claim.suggested_actions),
            selectinload(Claim.audit_logs),
        )
    )
    claim = session.scalar(query)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return claim


def record_audit_log(
    session: Session,
    claim_id: int,
    actor: str,
    event_type: str,
    payload_json: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            claim_id=claim_id,
            actor=actor,
            event_type=event_type,
            payload_json=payload_json,
        )
    )


def update_claim_status(session: Session, claim_id: int, status_value: ClaimStatus, actor: str) -> Claim:
    claim = get_claim(session, claim_id)
    claim.status = status_value
    record_audit_log(
        session,
        claim_id=claim.id,
        actor=actor,
        event_type="status_changed",
        payload_json={"status": status_value.value},
    )
    session.add(claim)
    session.commit()
    session.expire_all()
    return get_claim(session, claim_id)


def add_claim_note(session: Session, claim_id: int, payload: ClaimNoteCreate) -> Claim:
    claim = get_claim(session, claim_id)
    note_text = payload.note.strip()
    if not note_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Note cannot be empty.")

    record_audit_log(
        session,
        claim_id=claim.id,
        actor=payload.actor,
        event_type="internal_note_added",
        payload_json={"note": note_text},
    )
    session.commit()
    session.expire_all()
    return get_claim(session, claim_id)


def classify_claim(session: Session, claim_id: int) -> ClassificationResult:
    claim = get_claim(session, claim_id)
    provider = get_ai_provider()
    result = provider.classify_claim(claim, claim.messages)

    claim.category = result.category
    claim.ai_label = result.label
    claim.urgency = result.urgency
    session.add(claim)
    session.add(
        SuggestedAction(
            claim_id=claim.id,
            action_type="classification",
            draft_reply=f"category={result.category.value}; label={result.label}; urgency={result.urgency.value}",
            confidence=result.confidence,
            rationale=result.rationale,
        )
    )
    record_audit_log(
        session,
        claim_id=claim.id,
        actor="ai_mock_or_placeholder",
        event_type="claim_classified",
        payload_json={
            "category": result.category.value,
            "label": result.label,
            "urgency": result.urgency.value,
            "confidence": result.confidence,
        },
    )
    session.commit()
    return result


def generate_draft_reply(session: Session, claim_id: int) -> DraftReplyResult:
    claim = get_claim(session, claim_id)
    policy = get_policy(session, claim.merchant_id)
    provider = get_ai_provider()
    result = provider.draft_reply(claim, policy, claim.messages)

    session.add(
        SuggestedAction(
            claim_id=claim.id,
            action_type="draft_reply",
            draft_reply=result.draft_reply,
            confidence=result.confidence,
            rationale=result.rationale,
        )
    )
    record_audit_log(
        session,
        claim_id=claim.id,
        actor="ai_mock_or_placeholder",
        event_type="draft_reply_generated",
        payload_json={"confidence": result.confidence},
    )
    session.commit()
    return result


def get_dashboard_summary(
    session: Session,
    merchant_id: int | None = None,
    category: ClaimCategory | None = None,
    status_value: ClaimStatus | None = None,
    search_text: str | None = None,
) -> DashboardSummary:
    claims = list_claims(
        session,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=search_text,
    )
    by_category_counter = Counter(claim.category.value for claim in claims)

    return DashboardSummary(
        total_claims=len(claims),
        open_claims=sum(claim.status == ClaimStatus.OPEN for claim in claims),
        in_review_claims=sum(claim.status == ClaimStatus.IN_REVIEW for claim in claims),
        approved_claims=sum(claim.status == ClaimStatus.APPROVED for claim in claims),
        rejected_claims=sum(claim.status == ClaimStatus.REJECTED for claim in claims),
        done_claims=sum(claim.status == ClaimStatus.DONE for claim in claims),
        high_urgency_claims=sum(claim.urgency.value == "high" for claim in claims),
        by_category=dict(sorted(by_category_counter.items())),
    )
