from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Cafe24Connection, Cafe24WebhookDelivery, Claim, ClaimStatus, Merchant

from .oauth_client import Cafe24OAuthClient, Cafe24OAuthTokens
from .webhooks import Cafe24WebhookHandler, Cafe24WebhookVerificationError


def has_live_configuration(settings: Settings) -> bool:
    return bool(settings.cafe24_client_id and settings.cafe24_client_secret and settings.cafe24_redirect_uri)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_connection(session: Session, merchant_id: int) -> Cafe24Connection | None:
    return session.scalar(select(Cafe24Connection).where(Cafe24Connection.merchant_id == merchant_id))


def get_or_create_connection(session: Session, merchant: Merchant) -> Cafe24Connection:
    connection = get_connection(session, merchant.id)
    if connection is not None:
        return connection

    connection = Cafe24Connection(
        merchant_id=merchant.id,
        mall_id=merchant.mall_name,
    )
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def store_tokens(
    session: Session,
    merchant: Merchant,
    connection: Cafe24Connection,
    tokens: Cafe24OAuthTokens,
    *,
    mark_connected: bool,
) -> Cafe24Connection:
    now = datetime.now(UTC)
    connection.mall_id = connection.mall_id or merchant.mall_name
    connection.access_token = tokens.access_token
    connection.refresh_token = tokens.refresh_token or connection.refresh_token
    connection.token_type = tokens.token_type
    connection.scopes_json = tokens.scopes
    connection.access_token_expires_at = tokens.access_token_expires_at
    connection.refresh_token_expires_at = tokens.refresh_token_expires_at
    if mark_connected and connection.connected_at is None:
        connection.connected_at = now
    connection.last_token_refreshed_at = now
    if connection.last_sync_result == "not_started":
        connection.last_sync_result = "oauth_connected"
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def connect_with_code(
    session: Session,
    merchant: Merchant,
    oauth_client: Cafe24OAuthClient,
    settings: Settings,
    code: str,
) -> Cafe24Connection:
    if not has_live_configuration(settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 OAuth environment variables are not configured.",
        )

    connection = get_or_create_connection(session, merchant)
    tokens = oauth_client.exchange_code(connection.mall_id, code)
    return store_tokens(session, merchant, connection, tokens, mark_connected=True)


def refresh_connection_token(
    session: Session,
    merchant: Merchant,
    oauth_client: Cafe24OAuthClient,
    settings: Settings,
) -> Cafe24Connection:
    if not has_live_configuration(settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 OAuth environment variables are not configured.",
        )

    connection = get_connection(session, merchant.id)
    if connection is None or not connection.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cafe24 refresh token is not available for this merchant.",
        )

    tokens = oauth_client.refresh_access_token(connection.mall_id, connection.refresh_token)
    return store_tokens(session, merchant, connection, tokens, mark_connected=False)


def resolve_webhook_merchant(
    session: Session,
    *,
    explicit_merchant_id: int | None,
    payload: dict[str, object],
    headers: dict[str, str],
) -> Merchant:
    if explicit_merchant_id is not None:
        merchant = session.get(Merchant, explicit_merchant_id)
        if merchant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found.")
        return merchant

    mall_id_candidates = [
        headers.get("x-cafe24-mall-id"),
        headers.get("x-cafe24-shop-id"),
        payload.get("mall_id"),
        payload.get("mallId"),
    ]
    mall_id = next((str(value).strip() for value in mall_id_candidates if isinstance(value, str) and value.strip()), None)
    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 webhook merchant context is missing. Provide merchant_id or mall_id.",
        )

    merchant = session.scalar(select(Merchant).where(Merchant.mall_name == mall_id))
    if merchant is None:
        connection = session.scalar(select(Cafe24Connection).where(Cafe24Connection.mall_id == mall_id))
        merchant = connection.merchant if connection is not None else None
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found for mall_id.")
    return merchant


def ingest_live_webhook(
    session: Session,
    merchant: Merchant,
    handler: Cafe24WebhookHandler,
    *,
    headers: dict[str, str],
    body: bytes,
    payload: dict[str, object],
) -> tuple[Cafe24WebhookDelivery, bool]:
    if not handler.signing_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cafe24 webhook secret is not configured.",
        )

    try:
        handler.require_valid_signature(headers, body)
    except Cafe24WebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    connection = get_or_create_connection(session, merchant)
    envelope = handler.build_envelope(headers, body, payload)
    existing = session.scalar(
        select(Cafe24WebhookDelivery).where(Cafe24WebhookDelivery.dedupe_key == envelope.dedupe_key)
    )
    if existing is not None:
        return existing, True

    delivery = Cafe24WebhookDelivery(
        merchant_id=merchant.id,
        connection_id=connection.id,
        dedupe_key=envelope.dedupe_key,
        external_event_id=envelope.external_event_id,
        event_type=envelope.event_type,
        signature=envelope.signature,
        status="received",
        payload_json=payload,
        received_at=datetime.now(UTC),
    )
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    return delivery, False


def build_live_status(
    session: Session,
    merchant: Merchant,
    claims: list[Claim],
    settings: Settings,
    oauth_client: Cafe24OAuthClient,
) -> dict[str, object] | None:
    connection = get_connection(session, merchant.id)
    if connection is None and not has_live_configuration(settings):
        return None

    connection = connection or get_or_create_connection(session, merchant)
    now = datetime.now(UTC)
    connected_at = ensure_utc(connection.connected_at)
    last_token_refreshed_at = ensure_utc(connection.last_token_refreshed_at)
    access_token_expires_at = ensure_utc(connection.access_token_expires_at)
    refresh_token_expires_at = ensure_utc(connection.refresh_token_expires_at)
    connected = bool(connection.access_token and connected_at)
    pending_claims = sum(claim.status in {ClaimStatus.OPEN, ClaimStatus.IN_REVIEW} for claim in claims)
    recent_deliveries = list(
        session.scalars(
            select(Cafe24WebhookDelivery)
            .where(Cafe24WebhookDelivery.merchant_id == merchant.id)
            .order_by(Cafe24WebhookDelivery.received_at.desc())
            .limit(5)
        )
    )
    pending_webhooks = sum(delivery.processed_at is None for delivery in recent_deliveries)
    webhook_secret_configured = bool(settings.cafe24_webhook_secret)

    recent_events: list[dict[str, object]] = []
    if connected_at is not None:
        recent_events.append(
            {
                "occurred_at": connected_at,
                "event_type": "oauth_connected",
                "status": "success",
                "title": "Cafe24 OAuth connected",
                "detail": f"Cafe24 mall {connection.mall_id} 연결과 access token 저장이 완료되었습니다.",
                "batch_id": None,
                "claim_id": None,
                "order_no": None,
            }
        )
    if last_token_refreshed_at and last_token_refreshed_at != connected_at:
        recent_events.append(
            {
                "occurred_at": last_token_refreshed_at,
                "event_type": "token_refreshed",
                "status": "success",
                "title": "Cafe24 access token refreshed",
                "detail": "저장된 Cafe24 refresh token으로 access token을 갱신했습니다.",
                "batch_id": None,
                "claim_id": None,
                "order_no": None,
            }
        )
    for delivery in recent_deliveries:
        recent_events.append(
            {
                "occurred_at": ensure_utc(delivery.received_at) or now,
                "event_type": "live_webhook",
                "status": delivery.status,
                "title": f"{delivery.event_type} webhook received",
                "detail": f"dedupe_key={delivery.dedupe_key}",
                "batch_id": None,
                "claim_id": None,
                "order_no": None,
            }
        )
    event_priority = {
        "live_webhook": 3,
        "token_refreshed": 2,
        "oauth_connected": 1,
    }
    recent_events.sort(
        key=lambda item: (item["occurred_at"], event_priority.get(str(item["event_type"]), 0)),
        reverse=True,
    )

    access_token_expired = bool(access_token_expires_at and access_token_expires_at <= now)
    refresh_recommended = bool(
        access_token_expires_at and access_token_expires_at > now and access_token_expires_at <= now + timedelta(hours=24)
    )

    if not connected:
        health_status = "setup_needed"
        health_title = "OAuth 연결 필요"
        health_detail = "Cafe24 client 설정은 준비됐지만 아직 실제 OAuth 연결이 완료되지 않았습니다."
        next_action_type = "open_link"
        next_action_label = "Connect Cafe24"
        next_action_href = "/integrations/cafe24"
    elif access_token_expired and not connection.refresh_token:
        health_status = "attention"
        health_title = "Token 만료"
        health_detail = "Access token이 만료됐고 refresh token이 없어 다시 OAuth 연결이 필요합니다."
        next_action_type = "open_link"
        next_action_label = "Reconnect Cafe24"
        next_action_href = "/integrations/cafe24"
    elif access_token_expired or refresh_recommended:
        health_status = "setup_needed"
        health_title = "Token 갱신 권장"
        health_detail = "저장된 refresh token으로 access token을 갱신해 두는 편이 좋습니다."
        next_action_type = "open_link"
        next_action_label = "Refresh Token"
        next_action_href = "/integrations/cafe24"
    elif not webhook_secret_configured:
        health_status = "setup_needed"
        health_title = "Webhook secret 미설정"
        health_detail = "실제 webhook 서명 검증을 위해 CAFE24_WEBHOOK_SECRET 설정이 필요합니다."
        next_action_type = "open_link"
        next_action_label = "Review Webhook Setup"
        next_action_href = "/integrations/cafe24"
    elif pending_webhooks >= 5:
        health_status = "attention"
        health_title = "Webhook 적체 확인 필요"
        health_detail = f"미처리 Cafe24 webhook이 {pending_webhooks}건 쌓여 있습니다."
        next_action_type = "open_link"
        next_action_label = "Open Cafe24 Console"
        next_action_href = "/integrations/cafe24"
    else:
        health_status = "healthy"
        health_title = "Live connection healthy"
        health_detail = "Cafe24 OAuth 토큰과 webhook 서명 검증 설정이 준비된 상태입니다."
        next_action_type = "open_link"
        next_action_label = "Open Cafe24 Console"
        next_action_href = "/integrations/cafe24"

    authorize_url = (
        oauth_client.build_authorize_url(connection.mall_id, state=f"claimmate-live-{merchant.id}")
        if has_live_configuration(settings)
        else None
    )

    return {
        "merchant_id": merchant.id,
        "mall_name": merchant.mall_name,
        "connection_mode": "live_connected" if connected else "live_ready",
        "health_status": health_status,
        "health_title": health_title,
        "health_detail": health_detail,
        "next_action_type": next_action_type,
        "next_action_label": next_action_label,
        "next_action_href": next_action_href,
        "connected": connected,
        "oauth_configured": has_live_configuration(settings),
        "webhook_endpoint_ready": webhook_secret_configured,
        "authorize_url": authorize_url,
        "mall_id": connection.mall_id,
        "access_token_expires_at": access_token_expires_at,
        "refresh_token_expires_at": refresh_token_expires_at,
        "last_token_refreshed_at": last_token_refreshed_at,
        "webhook_secret_configured": webhook_secret_configured,
        "last_sync_result": connection.last_sync_result,
        "last_synced_at": connection.last_synced_at,
        "last_sync_batch_id": connection.last_sync_batch_id,
        "synced_orders": connection.synced_orders,
        "synced_claims": connection.synced_claims,
        "pending_claims": pending_claims,
        "pending_webhooks": pending_webhooks,
        "recent_events": recent_events[:8],
        "notes": [
            "Cafe24 OAuth callback은 실제 token exchange를 수행하도록 연결했습니다.",
            "Webhook endpoint는 서명 검증과 dedupe 처리까지 수행합니다.",
            "주문 / 배송 / 클레임 실제 sync는 아직 구현 중입니다.",
        ],
    }
