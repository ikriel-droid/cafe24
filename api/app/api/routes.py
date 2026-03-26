from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.db.session import get_db
from app.integrations.cafe24.oauth_client import Cafe24OAuthClient
from app.integrations.cafe24.sync_service import Cafe24SyncService
from app.models import ClaimCategory, ClaimStatus
from app.schemas import (
    Cafe24IntegrationStatus,
    Cafe24MockWebhookRequest,
    ClaimDetail,
    ClaimListItem,
    ClaimNoteCreate,
    ClaimStatusUpdate,
    ClassificationResponse,
    DashboardCafe24Overview,
    DashboardSummary,
    DraftReplyResponse,
    PolicyRead,
    PolicyUpdate,
)
from app.services.claim_service import (
    add_claim_note,
    classify_claim,
    get_default_merchant,
    generate_draft_reply,
    get_claim,
    get_dashboard_summary,
    get_policy,
    list_claims,
    update_claim_status,
    update_policy,
)
from app.core.config import get_settings

router = APIRouter()


def build_cafe24_service(settings) -> Cafe24SyncService:
    return Cafe24SyncService(
        Cafe24OAuthClient(
            client_id=settings.cafe24_client_id or "",
            client_secret=settings.cafe24_client_secret or "",
            redirect_uri=settings.cafe24_redirect_uri or "",
        )
    )


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
    db: Session = Depends(get_db),
) -> list[ClaimListItem]:
    claims = list_claims(
        db,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=q,
    )
    return [ClaimListItem.model_validate(claim) for claim in claims]


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def claims_detail(claim_id: int, db: Session = Depends(get_db)) -> ClaimDetail:
    return ClaimDetail.model_validate(get_claim(db, claim_id))


@router.patch("/claims/{claim_id}/status", response_model=ClaimDetail)
def claims_update_status(
    claim_id: int,
    payload: ClaimStatusUpdate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    claim = update_claim_status(db, claim_id, payload.status, payload.actor)
    return ClaimDetail.model_validate(claim)


@router.post("/claims/{claim_id}/notes", response_model=ClaimDetail)
def claims_add_note(
    claim_id: int,
    payload: ClaimNoteCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    claim = add_claim_note(db, claim_id, payload)
    return ClaimDetail.model_validate(claim)


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
    claims = list_claims(db, merchant_id=merchant.id)
    service = build_cafe24_service(settings)
    return Cafe24IntegrationStatus.model_validate(
        service.simulate_webhook(
            merchant,
            claims,
            settings,
            event_type=payload.event_type,
            order_no=payload.order_no,
        )
    )


@router.get("/integrations/cafe24/callback")
def cafe24_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    params: dict[str, str] = {}

    if error:
        params["oauth_result"] = "error"
        params["oauth_message"] = f"Cafe24 returned an OAuth error: {error}"
    elif code:
        params["oauth_result"] = "received"
        params["oauth_message"] = "Cafe24 OAuth callback placeholder received a code. Live token exchange is not enabled."
    else:
        params["oauth_result"] = "missing_code"
        params["oauth_message"] = "Cafe24 OAuth callback reached the local MVP, but no code parameter was provided."

    if state:
        params["oauth_state"] = state

    service = build_cafe24_service(settings)
    service.record_oauth_callback(
        merchant_id=resolve_merchant_id_from_state(state, settings.default_merchant_id),
        result=params["oauth_result"],
        message=params["oauth_message"],
        state=state,
    )

    destination = f"/integrations/cafe24/?{urlencode(params)}"
    return RedirectResponse(url=destination, status_code=307)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    merchant_id: int | None = None,
    category: ClaimCategory | None = Query(default=None),
    status_value: ClaimStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    summary = get_dashboard_summary(
        db,
        merchant_id=merchant_id,
        category=category,
        status_value=status_value,
        search_text=q,
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
