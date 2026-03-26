from __future__ import annotations

from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import ClassificationResult, DraftReplyResult
from app.ai.factory import get_ai_provider
from app.core.config import get_settings
from app.models import (
    AuditLog,
    Claim,
    ClaimCategory,
    ClaimMessage,
    ClaimStatus,
    ClaimUrgency,
    Merchant,
    Policy,
    SuggestedAction,
)
from app.schemas import ClaimNoteCreate, DashboardSummary, PolicyUpdate


MOCK_WEBHOOK_RULES: dict[str, dict[str, object]] = {
    "order.cancel.requested": {
        "category": ClaimCategory.CANCELLATION,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "message": "Cafe24 mock webhook으로 주문 취소 요청이 접수되었습니다.",
    },
    "claim.exchange.requested": {
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.MEDIUM,
        "message": "Cafe24 mock webhook으로 교환 요청이 접수되었습니다.",
    },
    "claim.return.requested": {
        "category": ClaimCategory.RETURN,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.MEDIUM,
        "message": "Cafe24 mock webhook으로 반품 요청이 접수되었습니다.",
    },
    "delivery.delay.reported": {
        "category": ClaimCategory.DELIVERY,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "message": "Cafe24 mock webhook으로 배송 지연 이슈가 접수되었습니다.",
    },
}


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
    auto_triaged: bool | None = None,
    reply_ready: bool | None = None,
) -> list[Claim]:
    merchant = get_default_merchant(session, merchant_id)
    query = (
        select(Claim)
        .where(Claim.merchant_id == merchant.id)
        .options(
            selectinload(Claim.suggested_actions),
            selectinload(Claim.audit_logs),
        )
        .order_by(Claim.created_at.desc())
    )
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
    claims = list(session.scalars(query))

    if auto_triaged is None and reply_ready is None:
        return claims

    filtered_claims: list[Claim] = []
    for claim in claims:
        automation = build_claim_automation_summary(claim)
        if auto_triaged is not None and automation["auto_triaged"] is not auto_triaged:
            continue
        if reply_ready is not None and automation["reply_ready"] is not reply_ready:
            continue
        filtered_claims.append(claim)
    return filtered_claims


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


def build_claim_automation_summary(claim: Claim) -> dict[str, object]:
    auto_triage_log = next(
        (log for log in claim.audit_logs if log.event_type == "cafe24_mock_webhook_auto_triaged"),
        None,
    )
    latest_reply = next(
        (action for action in claim.suggested_actions if action.action_type == "draft_reply"),
        None,
    )
    payload = auto_triage_log.payload_json if auto_triage_log else None

    classification_confidence = None
    draft_reply_confidence = None
    source_event = None
    if isinstance(payload, dict):
        classification_value = payload.get("classification_confidence")
        draft_value = payload.get("draft_confidence")
        source_value = payload.get("source_event")
        if isinstance(classification_value, (int, float)):
            classification_confidence = float(classification_value)
        if isinstance(draft_value, (int, float)):
            draft_reply_confidence = float(draft_value)
        if isinstance(source_value, str):
            source_event = source_value

    return {
        "auto_triaged": auto_triage_log is not None,
        "auto_triaged_at": auto_triage_log.created_at if auto_triage_log else None,
        "reply_ready": latest_reply is not None and bool(latest_reply.draft_reply.strip()),
        "classification_confidence": classification_confidence,
        "draft_reply_confidence": draft_reply_confidence,
        "source_event": source_event,
    }


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


def apply_mock_webhook_to_claim(
    session: Session,
    merchant_id: int,
    event_type: str,
    order_no: str | None = None,
) -> Claim | None:
    if not order_no:
        return None

    rule = MOCK_WEBHOOK_RULES.get(event_type)
    if rule is None:
        return None

    query = select(Claim).where(Claim.merchant_id == merchant_id, Claim.order_no == order_no)
    claim = session.scalar(query)
    if claim is None:
        return None

    previous_category = claim.category.value
    previous_status = claim.status.value
    previous_urgency = claim.urgency.value

    claim.category = rule["category"]
    claim.status = rule["status"]
    claim.urgency = rule["urgency"]

    session.add(
        ClaimMessage(
            claim_id=claim.id,
            role="system",
            body=f"{rule['message']} 주문번호 {claim.order_no} 기준으로 운영 검토가 필요합니다.",
        )
    )
    record_audit_log(
        session,
        claim_id=claim.id,
        actor="cafe24_mock_webhook",
        event_type="cafe24_mock_webhook_received",
        payload_json={
            "event_type": event_type,
            "order_no": claim.order_no,
            "previous_category": previous_category,
            "previous_status": previous_status,
            "previous_urgency": previous_urgency,
            "next_category": claim.category.value,
            "next_status": claim.status.value,
            "next_urgency": claim.urgency.value,
        },
    )
    session.add(claim)
    session.commit()

    classification = classify_claim(session, claim.id)
    draft_reply = generate_draft_reply(session, claim.id)

    record_audit_log(
        session,
        claim_id=claim.id,
        actor="cafe24_mock_webhook",
        event_type="cafe24_mock_webhook_auto_triaged",
        payload_json={
            "category": classification.category.value,
            "ai_label": classification.label,
            "urgency": classification.urgency.value,
            "classification_confidence": classification.confidence,
            "draft_confidence": draft_reply.confidence,
            "source_event": event_type,
        },
    )
    session.commit()
    session.expire_all()
    return get_claim(session, claim.id)


def get_dashboard_summary(
    session: Session,
    merchant_id: int | None = None,
    category: ClaimCategory | None = None,
    status_value: ClaimStatus | None = None,
    search_text: str | None = None,
    auto_triaged: bool | None = None,
    reply_ready: bool | None = None,
) -> DashboardSummary:
    claims = list_claims(
        session,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=search_text,
        auto_triaged=auto_triaged,
        reply_ready=reply_ready,
    )
    by_category_counter = Counter(claim.category.value for claim in claims)
    automation_summaries = [build_claim_automation_summary(claim) for claim in claims]

    return DashboardSummary(
        total_claims=len(claims),
        open_claims=sum(claim.status == ClaimStatus.OPEN for claim in claims),
        in_review_claims=sum(claim.status == ClaimStatus.IN_REVIEW for claim in claims),
        approved_claims=sum(claim.status == ClaimStatus.APPROVED for claim in claims),
        rejected_claims=sum(claim.status == ClaimStatus.REJECTED for claim in claims),
        done_claims=sum(claim.status == ClaimStatus.DONE for claim in claims),
        high_urgency_claims=sum(claim.urgency.value == "high" for claim in claims),
        auto_triaged_claims=sum(summary["auto_triaged"] is True for summary in automation_summaries),
        reply_ready_claims=sum(summary["reply_ready"] is True for summary in automation_summaries),
        by_category=dict(sorted(by_category_counter.items())),
    )
