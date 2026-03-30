from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.db.session import get_db
from app.integrations.cafe24.live_service import (
    build_live_status,
    connect_with_code,
    ingest_live_webhook,
    refresh_connection_token,
    resolve_webhook_merchant,
)
from app.integrations.cafe24.oauth_client import Cafe24OAuthClient
from app.integrations.cafe24.sync_service import Cafe24SyncService
from app.integrations.cafe24.webhooks import Cafe24WebhookHandler
from app.models import Claim, ClaimCategory, ClaimStatus
from app.schemas import (
    Cafe24IntegrationStatus,
    Cafe24MockWebhookRequest,
    Cafe24TokenRefreshResponse,
    Cafe24WebhookIngestResponse,
    ClaimDetail,
    ClaimListItem,
    ClaimNoteCreate,
    ClaimReplySend,
    ClaimStatusUpdate,
    ClassificationResponse,
    DashboardCafe24Overview,
    DashboardSummary,
    DraftReplyResponse,
    PolicyRead,
    PolicyUpdate,
)
from app.services.claim_service import (
    apply_mock_webhook_to_claim,
    add_claim_note,
    build_claim_automation_summary,
    classify_claim,
    get_default_merchant,
    generate_draft_reply,
    get_claim,
    get_dashboard_summary,
    get_policy,
    list_claims,
    send_claim_reply,
    update_claim_status,
    update_policy,
)
from app.core.config import get_settings

router = APIRouter()


def build_reason_preview(reason_text: str, limit: int = 90) -> str:
    normalized_reason = " ".join(reason_text.split())
    if len(normalized_reason) <= limit:
        return normalized_reason
    return f"{normalized_reason[:limit].rstrip()}..."


def build_claim_base_payload(claim: Claim) -> dict[str, object]:
    return {
        "id": claim.id,
        "order_no": claim.order_no,
        "customer_name": claim.customer_name,
        "product_name": claim.product_name,
        "reason_preview": build_reason_preview(claim.reason_text),
        "category": claim.category,
        "status": claim.status,
        "urgency": claim.urgency,
        "ai_label": claim.ai_label,
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
        "automation": build_claim_automation_summary(claim),
    }


def build_claim_detail_payload(claim: Claim) -> dict[str, object]:
    return {
        **build_claim_base_payload(claim),
        "merchant_id": claim.merchant_id,
        "reason_text": claim.reason_text,
        "messages": claim.messages,
        "suggested_actions": claim.suggested_actions,
        "audit_logs": claim.audit_logs,
    }


def build_cafe24_service(settings) -> Cafe24SyncService:
    return Cafe24SyncService(
        Cafe24OAuthClient(
            client_id=settings.cafe24_client_id or "",
            client_secret=settings.cafe24_client_secret or "",
            redirect_uri=settings.cafe24_redirect_uri or "",
            scopes=settings.cafe24_scopes,
            timeout_seconds=settings.cafe24_api_timeout_seconds,
        )
    )


def build_cafe24_webhook_handler(settings) -> Cafe24WebhookHandler:
    return Cafe24WebhookHandler(signing_secret=settings.cafe24_webhook_secret or "")


def resolve_merchant_id_from_state(state: str | None, fallback_merchant_id: int) -> int:
    if not state:
        return fallback_merchant_id
    tail = state.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else fallback_merchant_id


@router.get("/claims", response_model=list[ClaimListItem])
def claims_index(
    merchant_id: int | None = None,
    category: ClaimCategory | None = Query(default=None),
    status_value: ClaimStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    source_event: str | None = Query(default=None),
    auto_triaged: bool | None = Query(default=None),
    reply_ready: bool | None = Query(default=None),
    reply_sent: bool | None = Query(default=None),
    follow_up_needed: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ClaimListItem]:
    claims = list_claims(
        db,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=q,
        source_event=source_event,
        auto_triaged=auto_triaged,
        reply_ready=reply_ready,
        reply_sent=reply_sent,
        follow_up_needed=follow_up_needed,
    )
    return [ClaimListItem.model_validate(build_claim_base_payload(claim)) for claim in claims]


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def claims_detail(claim_id: int, db: Session = Depends(get_db)) -> ClaimDetail:
    return ClaimDetail.model_validate(build_claim_detail_payload(get_claim(db, claim_id)))


@router.patch("/claims/{claim_id}/status", response_model=ClaimDetail)
def claims_update_status(
    claim_id: int,
    payload: ClaimStatusUpdate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    claim = update_claim_status(db, claim_id, payload.status, payload.actor)
    return ClaimDetail.model_validate(build_claim_detail_payload(claim))


@router.post("/claims/{claim_id}/notes", response_model=ClaimDetail)
def claims_add_note(
    claim_id: int,
    payload: ClaimNoteCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    claim = add_claim_note(db, claim_id, payload)
    return ClaimDetail.model_validate(build_claim_detail_payload(claim))


@router.post("/claims/{claim_id}/send-reply", response_model=ClaimDetail)
def claims_send_reply(
    claim_id: int,
    payload: ClaimReplySend,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    claim = send_claim_reply(db, claim_id, payload)
    return ClaimDetail.model_validate(build_claim_detail_payload(claim))


@router.get("/policy", response_model=PolicyRead)
def policy_read(merchant_id: int | None = None, db: Session = Depends(get_db)) -> PolicyRead:
    return PolicyRead.model_validate(get_policy(db, merchant_id))


@router.put("/policy", response_model=PolicyRead)
def policy_update(
    payload: PolicyUpdate,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
) -> PolicyRead:
    return PolicyRead.model_validate(update_policy(db, payload, merchant_id))


@router.post("/claims/{claim_id}/classify", response_model=ClassificationResponse)
def claims_classify(claim_id: int, db: Session = Depends(get_db)) -> ClassificationResponse:
    result = classify_claim(db, claim_id)
    return ClassificationResponse(
        claim_id=claim_id,
        category=result.category,
        ai_label=result.label,
        urgency=result.urgency,
        confidence=result.confidence,
        rationale=result.rationale,
    )


@router.post("/claims/{claim_id}/draft-reply", response_model=DraftReplyResponse)
def claims_draft_reply(claim_id: int, db: Session = Depends(get_db)) -> DraftReplyResponse:
    result = generate_draft_reply(db, claim_id)
    return DraftReplyResponse(
        claim_id=claim_id,
        draft_reply=result.draft_reply,
        confidence=result.confidence,
        rationale=result.rationale,
    )


@router.get("/integrations/cafe24", response_model=Cafe24IntegrationStatus)
def cafe24_status(merchant_id: int | None = None, db: Session = Depends(get_db)) -> Cafe24IntegrationStatus:
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    live_status = build_live_status(db, merchant, claims, settings, service.oauth_client)
    if live_status is not None:
        return Cafe24IntegrationStatus.model_validate(live_status)
    return Cafe24IntegrationStatus.model_validate(service.get_status(merchant, claims, settings))


@router.post("/integrations/cafe24/mock-sync", response_model=Cafe24IntegrationStatus)
def cafe24_mock_sync(merchant_id: int | None = None, db: Session = Depends(get_db)) -> Cafe24IntegrationStatus:
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    return Cafe24IntegrationStatus.model_validate(service.run_mock_sync(merchant, claims, settings))


@router.post("/integrations/cafe24/clear-activity", response_model=Cafe24IntegrationStatus)
def cafe24_clear_activity(merchant_id: int | None = None, db: Session = Depends(get_db)) -> Cafe24IntegrationStatus:
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    service.clear_activity(merchant.id)
    return Cafe24IntegrationStatus.model_validate(service.get_status(merchant, claims, settings))


@router.post("/integrations/cafe24/mock-webhook", response_model=Cafe24IntegrationStatus)
def cafe24_mock_webhook(
    payload: Cafe24MockWebhookRequest,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
) -> Cafe24IntegrationStatus:
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    affected_claim = apply_mock_webhook_to_claim(
        db,
        merchant_id=merchant.id,
        event_type=payload.event_type,
        order_no=payload.order_no,
    )
    automation_summary: str | None = None
    if affected_claim is not None:
        latest_reply = next(
            (action for action in affected_claim.suggested_actions if action.action_type == "draft_reply"),
            None,
        )
        summary_parts: list[str] = []
        if affected_claim.ai_label:
            summary_parts.append(f"AI 분류: {affected_claim.ai_label} ({affected_claim.category.value})")
        if latest_reply is not None:
            summary_parts.append("답변 초안 생성 완료")
        if summary_parts:
            automation_summary = " / ".join(summary_parts)
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    return Cafe24IntegrationStatus.model_validate(
        service.simulate_webhook(
            merchant,
            claims,
            settings,
            event_type=payload.event_type,
            order_no=payload.order_no,
            claim_id=affected_claim.id if affected_claim else None,
            automation_summary=automation_summary,
        )
    )


@router.get("/integrations/cafe24/callback")
def cafe24_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    params: dict[str, str] = {}
    service = build_cafe24_service(settings)
    merchant_id = resolve_merchant_id_from_state(state, settings.default_merchant_id)

    if error:
        params["oauth_result"] = "error"
        params["oauth_message"] = f"Cafe24 returned an OAuth error: {error}"
    elif code:
        merchant = get_default_merchant(db, merchant_id)
        try:
            connect_with_code(db, merchant, service.oauth_client, settings, code)
            params["oauth_result"] = "connected"
            params["oauth_message"] = "Cafe24 OAuth token exchange completed and the connection was saved."
        except Exception as exc:
            params["oauth_result"] = "error"
            params["oauth_message"] = f"Cafe24 OAuth token exchange failed: {exc}"
    else:
        params["oauth_result"] = "missing_code"
        params["oauth_message"] = "Cafe24 OAuth callback reached the local MVP, but no code parameter was provided."

    if state:
        params["oauth_state"] = state

    service.record_oauth_callback(
        merchant_id=merchant_id,
        result=params["oauth_result"],
        message=params["oauth_message"],
        state=state,
    )

    destination = f"/integrations/cafe24/?{urlencode(params)}"
    return RedirectResponse(url=destination, status_code=307)


@router.post("/integrations/cafe24/refresh-token", response_model=Cafe24TokenRefreshResponse)
def cafe24_refresh_token(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
) -> Cafe24TokenRefreshResponse:
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    service = build_cafe24_service(settings)
    connection = refresh_connection_token(db, merchant, service.oauth_client, settings)
    return Cafe24TokenRefreshResponse(
        status="refreshed",
        refreshed_at=connection.last_token_refreshed_at or connection.updated_at,
        access_token_expires_at=connection.access_token_expires_at,
    )


@router.post("/integrations/cafe24/webhook/live", response_model=Cafe24WebhookIngestResponse, status_code=202)
async def cafe24_live_webhook(
    request: Request,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
) -> Cafe24WebhookIngestResponse:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 webhook payload must be valid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 webhook payload must be a JSON object.",
        )

    settings = get_settings()
    headers = {key.lower(): value for key, value in request.headers.items()}
    merchant = resolve_webhook_merchant(
        db,
        explicit_merchant_id=merchant_id,
        payload=payload,
        headers=headers,
    )
    handler = build_cafe24_webhook_handler(settings)
    delivery, duplicate = ingest_live_webhook(
        db,
        merchant,
        handler,
        headers=headers,
        body=raw_body,
        payload=payload,
    )
    return Cafe24WebhookIngestResponse(
        status="duplicate" if duplicate else delivery.status,
        duplicate=duplicate,
        dedupe_key=delivery.dedupe_key,
        event_type=delivery.event_type,
        merchant_id=merchant.id,
    )


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    merchant_id: int | None = None,
    category: ClaimCategory | None = Query(default=None),
    status_value: ClaimStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    source_event: str | None = Query(default=None),
    auto_triaged: bool | None = Query(default=None),
    reply_ready: bool | None = Query(default=None),
    reply_sent: bool | None = Query(default=None),
    follow_up_needed: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    summary = get_dashboard_summary(
        db,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=q,
        source_event=source_event,
        auto_triaged=auto_triaged,
        reply_ready=reply_ready,
        reply_sent=reply_sent,
        follow_up_needed=follow_up_needed,
    )
    settings = get_settings()
    merchant = get_default_merchant(db, merchant_id)
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    cafe24_status = service.get_status(merchant, claims, settings)
    latest_event = cafe24_status["recent_events"][0] if cafe24_status["recent_events"] else None

    return DashboardSummary(
        **summary.model_dump(exclude={"cafe24"}),
        cafe24=DashboardCafe24Overview(
            health_status=cafe24_status["health_status"],
            health_title=cafe24_status["health_title"],
            health_detail=cafe24_status["health_detail"],
            last_sync_result=cafe24_status["last_sync_result"],
            last_synced_at=cafe24_status["last_synced_at"],
            pending_webhooks=cafe24_status["pending_webhooks"],
            recent_activity_count=len(cafe24_status["recent_events"]),
            latest_event_title=latest_event["title"] if latest_event else None,
            latest_event_status=latest_event["status"] if latest_event else None,
            latest_event_occurred_at=latest_event["occurred_at"] if latest_event else None,
            next_action_type=cafe24_status["next_action_type"],
            next_action_label=cafe24_status["next_action_label"],
            next_action_href=cafe24_status["next_action_href"],
        ),
    )
