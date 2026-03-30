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
    ReplyDelivery,
    ReplyDeliveryStatus,
    SuggestedAction,
)
from app.reply_delivery.base import ReplyDeliveryError, ReplyDeliveryRequest
from app.reply_delivery.factory import get_reply_delivery_provider
from app.schemas import ClaimNoteCreate, ClaimReplyRetry, ClaimReplySend, DashboardSummary, PolicyUpdate


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
    source_event: str | None = None,
    auto_triaged: bool | None = None,
    reply_ready: bool | None = None,
    reply_sent: bool | None = None,
    follow_up_needed: bool | None = None,
) -> list[Claim]:
    merchant = get_default_merchant(session, merchant_id)
    query = (
        select(Claim)
        .where(Claim.merchant_id == merchant.id)
        .options(
            selectinload(Claim.suggested_actions),
            selectinload(Claim.audit_logs),
            selectinload(Claim.reply_deliveries),
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

    if (
        auto_triaged is None
        and reply_ready is None
        and reply_sent is None
        and follow_up_needed is None
        and source_event is None
    ):
        return claims

    filtered_claims: list[Claim] = []
    for claim in claims:
        automation = build_claim_automation_summary(claim)
        if source_event is not None and automation["source_event"] != source_event:
            continue
        if auto_triaged is not None and automation["auto_triaged"] != auto_triaged:
            continue
        if reply_ready is not None and automation["reply_ready"] != reply_ready:
            continue
        if reply_sent is not None and automation["reply_sent"] != reply_sent:
            continue
        if follow_up_needed is not None and automation["follow_up_needed"] != follow_up_needed:
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
            selectinload(Claim.reply_deliveries),
        )
    )
    claim = session.scalar(query)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return claim


def build_claim_automation_summary(claim: Claim) -> dict[str, object]:
    auto_triage_log = next(
        (
            log
            for log in claim.audit_logs
            if log.event_type
            in {
                "cafe24_mock_webhook_auto_triaged",
                "cafe24_live_sync_auto_triaged",
                "cafe24_live_webhook_auto_triaged",
            }
        ),
        None,
    )
    latest_reply = next(
        (action for action in claim.suggested_actions if action.action_type == "draft_reply"),
        None,
    )
    latest_delivery = claim.reply_deliveries[0] if claim.reply_deliveries else None
    latest_successful_delivery = next(
        (delivery for delivery in claim.reply_deliveries if delivery.status == ReplyDeliveryStatus.SENT),
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

    follow_up_needed = latest_successful_delivery is not None and claim.status != ClaimStatus.DONE
    draft_reply_preview = None
    if latest_reply is not None:
        normalized_reply = latest_reply.draft_reply.strip().replace("\r\n", "\n").replace("\n", " ")
        if normalized_reply:
            draft_reply_preview = normalized_reply[:120].rstrip()
            if len(normalized_reply) > 120:
                draft_reply_preview = f"{draft_reply_preview}..."

    return {
        "auto_triaged": auto_triage_log is not None,
        "auto_triaged_at": auto_triage_log.created_at if auto_triage_log else None,
        "reply_ready": latest_reply is not None and bool(latest_reply.draft_reply.strip()),
        "draft_reply_preview": draft_reply_preview,
        "reply_sent": latest_successful_delivery is not None,
        "follow_up_needed": follow_up_needed,
        "reply_sent_at": latest_successful_delivery.sent_at if latest_successful_delivery else None,
        "reply_sent_by": latest_successful_delivery.actor if latest_successful_delivery else None,
        "latest_delivery_status": latest_delivery.status.value if latest_delivery else None,
        "latest_delivery_channel": latest_delivery.channel.value if latest_delivery else None,
        "latest_delivery_at": (latest_delivery.sent_at or latest_delivery.created_at) if latest_delivery else None,
        "latest_delivery_error": latest_delivery.error_message if latest_delivery else None,
        "latest_delivery_destination": latest_delivery.destination if latest_delivery else None,
        "delivery_attempt_count": len(claim.reply_deliveries),
        "can_retry_delivery": latest_delivery is not None and latest_delivery.status == ReplyDeliveryStatus.FAILED,
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


def get_next_reply_delivery_attempt_no(claim: Claim) -> int:
    latest_attempt_no = claim.reply_deliveries[0].attempt_no if claim.reply_deliveries else 0
    return latest_attempt_no + 1


def record_reply_delivery(
    session: Session,
    claim: Claim,
    *,
    actor: str,
    attempt_no: int,
    channel,
    status,
    provider: str,
    reply_body: str,
    destination: str | None,
    external_delivery_id: str | None = None,
    request_payload_json: dict[str, object] | None = None,
    response_payload_json: dict[str, object] | None = None,
    error_message: str | None = None,
    sent_at=None,
) -> ReplyDelivery:
    delivery = ReplyDelivery(
        claim_id=claim.id,
        actor=actor,
        attempt_no=attempt_no,
        channel=channel,
        status=status,
        provider=provider,
        destination=destination,
        reply_body=reply_body,
        external_delivery_id=external_delivery_id,
        request_payload_json=request_payload_json,
        response_payload_json=response_payload_json,
        error_message=error_message,
        sent_at=sent_at,
    )
    session.add(delivery)
    return delivery


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


def send_claim_reply(session: Session, claim_id: int, payload: ClaimReplySend) -> Claim:
    claim = get_claim(session, claim_id)
    latest_reply = next(
        (action for action in claim.suggested_actions if action.action_type == "draft_reply"),
        None,
    )

    reply_body = payload.reply_body.strip() if payload.reply_body else ""
    if not reply_body and latest_reply is not None:
        reply_body = latest_reply.draft_reply.strip()
    if not reply_body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reply body cannot be empty.")

    attempt_no = get_next_reply_delivery_attempt_no(claim)
    provider = get_reply_delivery_provider()

    try:
        delivery_result = provider.send_reply(
            ReplyDeliveryRequest(
                claim=claim,
                actor=payload.actor,
                reply_body=reply_body,
                attempt_no=attempt_no,
            )
        )
    except ReplyDeliveryError as exc:
        record_reply_delivery(
            session,
            claim,
            actor=payload.actor,
            attempt_no=attempt_no,
            channel=exc.channel,
            status=ReplyDeliveryStatus.FAILED,
            provider=exc.provider,
            reply_body=reply_body,
            destination=exc.destination,
            request_payload_json=exc.request_payload,
            response_payload_json=exc.response_payload,
            error_message=str(exc),
        )
        record_audit_log(
            session,
            claim_id=claim.id,
            actor=payload.actor,
            event_type="reply_delivery_failed",
            payload_json={
                "attempt_no": attempt_no,
                "channel": exc.channel.value,
                "provider": exc.provider,
                "destination": exc.destination,
                "error": str(exc),
            },
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    record_reply_delivery(
        session,
        claim,
        actor=payload.actor,
        attempt_no=attempt_no,
        channel=delivery_result.channel,
        status=delivery_result.status,
        provider=delivery_result.provider,
        reply_body=reply_body,
        destination=delivery_result.destination,
        external_delivery_id=delivery_result.external_delivery_id,
        request_payload_json=delivery_result.request_payload,
        response_payload_json=delivery_result.response_payload,
        sent_at=delivery_result.sent_at,
    )

    session.add(
        ClaimMessage(
            claim_id=claim.id,
            role="merchant",
            body=reply_body,
        )
    )

    if payload.mark_done:
        claim.status = ClaimStatus.DONE
        session.add(claim)

    record_audit_log(
        session,
        claim_id=claim.id,
        actor=payload.actor,
        event_type="reply_resent" if attempt_no > 1 else "reply_sent",
        payload_json={
            "attempt_no": attempt_no,
            "channel": delivery_result.channel.value,
            "provider": delivery_result.provider,
            "destination": delivery_result.destination,
            "external_delivery_id": delivery_result.external_delivery_id,
            "mark_done": payload.mark_done,
            "status": claim.status.value,
            "source": "manual_edit" if payload.reply_body else "latest_draft",
            "reply_preview": reply_body[:140],
        },
    )
    session.commit()
    session.expire_all()
    return get_claim(session, claim_id)


def retry_failed_claim_reply(session: Session, claim_id: int, payload: ClaimReplyRetry) -> Claim:
    claim = get_claim(session, claim_id)
    failed_delivery = next(
        (delivery for delivery in claim.reply_deliveries if delivery.status == ReplyDeliveryStatus.FAILED),
        None,
    )
    if failed_delivery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No failed reply delivery attempt is available for retry.",
        )

    return send_claim_reply(
        session,
        claim_id,
        ClaimReplySend(
            reply_body=failed_delivery.reply_body,
            actor=payload.actor,
            mark_done=payload.mark_done,
        ),
    )


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


def apply_live_webhook_to_claim(
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
            body=f"Cafe24 live webhook으로 {claim.order_no} 주문의 {event_type} 이벤트를 접수했습니다.",
        )
    )
    record_audit_log(
        session,
        claim_id=claim.id,
        actor="cafe24_live_webhook",
        event_type="cafe24_live_webhook_received",
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
        actor="cafe24_live_webhook",
        event_type="cafe24_live_webhook_auto_triaged",
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
    source_event: str | None = None,
    auto_triaged: bool | None = None,
    reply_ready: bool | None = None,
    reply_sent: bool | None = None,
    follow_up_needed: bool | None = None,
) -> DashboardSummary:
    claims = list_claims(
        session,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=search_text,
        source_event=source_event,
        auto_triaged=auto_triaged,
        reply_ready=reply_ready,
        reply_sent=reply_sent,
        follow_up_needed=follow_up_needed,
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
        reply_sent_claims=sum(summary["reply_sent"] is True for summary in automation_summaries),
        follow_up_needed_claims=sum(summary["follow_up_needed"] is True for summary in automation_summaries),
        by_category=dict(sorted(by_category_counter.items())),
    )
