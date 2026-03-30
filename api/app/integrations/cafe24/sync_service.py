from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Cafe24IntegrationEvent, Claim, ClaimStatus, Merchant

from .live_service import ensure_utc, get_or_create_connection
from .oauth_client import Cafe24OAuthClient

MOCK_WEBHOOK_LABELS: dict[str, tuple[str, str]] = {
    "order.cancel.requested": ("주문 취소 요청", "고객의 주문 취소 요청 이벤트를 로컬 기준으로 기록했습니다."),
    "claim.exchange.requested": ("교환 요청", "고객의 교환 접수 이벤트를 로컬 기준으로 기록했습니다."),
    "claim.return.requested": ("반품 요청", "고객의 반품 접수 이벤트를 로컬 기준으로 기록했습니다."),
    "delivery.delay.reported": ("배송 지연 알림", "배송 지연 이벤트를 로컬 기준으로 기록했습니다."),
}


class Cafe24SyncService:
    def __init__(self, oauth_client: Cafe24OAuthClient) -> None:
        self.oauth_client = oauth_client

    @classmethod
    def reset_state(cls) -> None:
        # DB-backed service keeps state in the database, so there is no in-memory snapshot to reset.
        return None

    def _append_event(
        self,
        session: Session,
        merchant: Merchant,
        *,
        event_type: str,
        status: str,
        title: str,
        detail: str,
        batch_id: str | None = None,
        claim_id: int | None = None,
        order_no: str | None = None,
    ) -> Cafe24IntegrationEvent:
        connection = get_or_create_connection(session, merchant)
        event = Cafe24IntegrationEvent(
            merchant_id=merchant.id,
            connection_id=connection.id,
            event_type=event_type,
            status=status,
            title=title,
            detail=detail,
            batch_id=batch_id,
            claim_id=claim_id,
            order_no=order_no,
            occurred_at=datetime.now(UTC),
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    def clear_activity(self, session: Session, merchant_id: int) -> None:
        session.execute(delete(Cafe24IntegrationEvent).where(Cafe24IntegrationEvent.merchant_id == merchant_id))
        session.commit()

    def _get_events(self, session: Session, merchant_id: int, limit: int = 8) -> list[Cafe24IntegrationEvent]:
        return list(
            session.scalars(
                select(Cafe24IntegrationEvent)
                .where(Cafe24IntegrationEvent.merchant_id == merchant_id)
                .order_by(Cafe24IntegrationEvent.occurred_at.desc(), Cafe24IntegrationEvent.id.desc())
                .limit(limit)
            )
        )

    def _build_health_summary(
        self,
        *,
        connection_last_sync_result: str,
        oauth_configured: bool,
        pending_claims: int,
        pending_webhooks: int,
    ) -> tuple[str, str, str]:
        if connection_last_sync_result == "not_started":
            return (
                "attention",
                "Mock Sync 대기",
                "아직 Cafe24 Mock Sync를 실행하지 않았습니다. 먼저 한 번 실행해서 로컬 연동 흐름을 확인해 주세요.",
            )

        if not oauth_configured:
            return (
                "setup_needed",
                "OAuth env 미설정",
                "Mock Sync는 가능하지만 Cafe24 OAuth preview는 비활성화되어 있습니다. env를 채우면 연결 테스트가 가능합니다.",
            )

        if pending_webhooks >= 5:
            return (
                "attention",
                "Webhook 확인 필요",
                f"대기 중인 mock webhook이 {pending_webhooks}건입니다. activity 흐름을 다시 확인해 주세요.",
            )

        if pending_claims >= 8:
            return (
                "attention",
                "처리 대기 문의 많음",
                f"현재 처리 대기 클레임이 {pending_claims}건입니다. 인박스 우선순위를 먼저 확인해 주세요.",
            )

        return (
            "healthy",
            "Mock 상태 양호",
            "최근 Mock Sync가 완료되었고 현재 대기 상태도 안정적입니다.",
        )

    def _build_next_action(
        self,
        *,
        connection_last_sync_result: str,
        oauth_configured: bool,
        pending_claims: int,
        pending_webhooks: int,
    ) -> tuple[str, str, str | None]:
        if connection_last_sync_result == "not_started":
            return ("mock_sync", "Run Mock Sync", None)

        if not oauth_configured:
            return ("open_link", "Review OAuth Setup", "/integrations/cafe24")

        if pending_webhooks >= 5:
            return ("open_link", "Review Activity", "/integrations/cafe24")

        if pending_claims >= 8:
            return ("open_link", "Open Inbox", "/inbox")

        return ("open_link", "Open Cafe24 Console", "/integrations/cafe24")

    def get_status(
        self,
        session: Session,
        merchant: Merchant,
        claims: Sequence[Claim],
        settings: Settings,
    ) -> dict[str, object]:
        connection = get_or_create_connection(session, merchant)
        oauth_configured = bool(
            settings.cafe24_client_id and settings.cafe24_client_secret and settings.cafe24_redirect_uri
        )
        pending_claims = sum(claim.status in {ClaimStatus.OPEN, ClaimStatus.IN_REVIEW} for claim in claims)
        recent_events = self._get_events(session, merchant.id, limit=8)
        pending_webhooks = sum(
            event.event_type == "mock_webhook" and event.status in {"received", "failed"} for event in recent_events
        )

        health_status, health_title, health_detail = self._build_health_summary(
            connection_last_sync_result=connection.last_sync_result,
            oauth_configured=oauth_configured,
            pending_claims=pending_claims,
            pending_webhooks=pending_webhooks,
        )
        next_action_type, next_action_label, next_action_href = self._build_next_action(
            connection_last_sync_result=connection.last_sync_result,
            oauth_configured=oauth_configured,
            pending_claims=pending_claims,
            pending_webhooks=pending_webhooks,
        )
        authorize_url = (
            self.oauth_client.build_authorize_url(connection.mall_id, state=f"claimmate-local-{merchant.id}")
            if oauth_configured
            else None
        )

        return {
            "merchant_id": merchant.id,
            "mall_name": merchant.mall_name,
            "connection_mode": "offline_mock",
            "health_status": health_status,
            "health_title": health_title,
            "health_detail": health_detail,
            "next_action_type": next_action_type,
            "next_action_label": next_action_label,
            "next_action_href": next_action_href,
            "connected": False,
            "oauth_configured": oauth_configured,
            "webhook_endpoint_ready": True,
            "authorize_url": authorize_url,
            "mall_id": connection.mall_id,
            "access_token_expires_at": None,
            "refresh_token_expires_at": None,
            "last_token_refreshed_at": None,
            "webhook_secret_configured": False,
            "last_sync_result": connection.last_sync_result,
            "last_synced_at": ensure_utc(connection.last_synced_at),
            "last_sync_batch_id": connection.last_sync_batch_id,
            "synced_orders": connection.synced_orders,
            "synced_claims": connection.synced_claims,
            "pending_claims": pending_claims,
            "pending_webhooks": pending_webhooks,
            "failed_webhooks": 0,
            "retryable_webhooks": 0,
            "recent_events": [
                {
                    "occurred_at": ensure_utc(event.occurred_at) or datetime.now(UTC),
                    "event_type": event.event_type,
                    "status": event.status,
                    "title": event.title,
                    "detail": event.detail,
                    "batch_id": event.batch_id,
                    "claim_id": event.claim_id,
                    "order_no": event.order_no,
                }
                for event in recent_events
            ],
            "notes": [
                "Mock Sync는 로컬 클레임 데이터를 기준으로 Cafe24 운영 흐름을 재현합니다.",
                "Mock webhook과 OAuth callback activity도 DB에 저장되어 상태가 유지됩니다.",
                "실제 Cafe24 API 호출 없이도 인박스 / 대시보드 / 콘솔 흐름을 검증할 수 있습니다.",
            ],
        }

    def run_mock_sync(
        self,
        session: Session,
        merchant: Merchant,
        claims: Sequence[Claim],
        settings: Settings,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        pending_claims = sum(claim.status in {ClaimStatus.OPEN, ClaimStatus.IN_REVIEW} for claim in claims)
        connection = get_or_create_connection(session, merchant)
        connection.last_synced_at = now
        connection.last_sync_result = "mock_completed"
        connection.last_sync_batch_id = f"mock-{merchant.id}-{int(now.timestamp())}"
        connection.synced_orders = len(claims) + 4
        connection.synced_claims = len(claims)
        session.add(connection)
        session.commit()
        session.refresh(connection)

        self._append_event(
            session,
            merchant,
            event_type="mock_sync",
            status="success",
            title="Cafe24 Mock Sync 완료",
            detail=f"주문 {connection.synced_orders}건과 클레임 {connection.synced_claims}건을 로컬 기준으로 갱신했습니다.",
            batch_id=connection.last_sync_batch_id,
        )
        return self.get_status(session, merchant, claims, settings)

    def simulate_webhook(
        self,
        session: Session,
        merchant: Merchant,
        claims: Sequence[Claim],
        settings: Settings,
        event_type: str,
        order_no: str | None = None,
        claim_id: int | None = None,
        automation_summary: str | None = None,
    ) -> dict[str, object]:
        title, description = MOCK_WEBHOOK_LABELS.get(
            event_type,
            ("기타 Cafe24 webhook", "정의되지 않은 webhook 이벤트를 로컬 placeholder로 기록했습니다."),
        )
        detail_suffix = f" 주문번호: {order_no}." if order_no else ""
        if automation_summary:
            detail_suffix += f" {automation_summary}."

        self._append_event(
            session,
            merchant,
            event_type="mock_webhook",
            status="received",
            title=f"{title} webhook received",
            detail=f"{description}{detail_suffix}",
            claim_id=claim_id,
            order_no=order_no,
        )
        return self.get_status(session, merchant, claims, settings)

    def record_oauth_callback(
        self,
        session: Session,
        merchant: Merchant,
        *,
        result: str,
        message: str,
        state: str | None = None,
    ) -> None:
        title = "Cafe24 OAuth callback 수신" if result == "received" else "Cafe24 OAuth callback 결과"
        detail = f"{message}{f' (state: {state})' if state else ''}"
        self._append_event(
            session,
            merchant,
            event_type="oauth_callback",
            status=result,
            title=title,
            detail=detail,
        )
