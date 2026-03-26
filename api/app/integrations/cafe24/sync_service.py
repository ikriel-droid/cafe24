from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Sequence

from app.core.config import Settings
from app.models import Claim, ClaimStatus, Merchant

from .oauth_client import Cafe24OAuthClient

MOCK_WEBHOOK_LABELS: dict[str, tuple[str, str]] = {
    "order.cancel.requested": ("주문 취소 요청", "고객이 주문 취소를 요청한 이벤트를 시뮬레이션합니다."),
    "claim.exchange.requested": ("교환 요청", "고객이 교환 접수를 남긴 이벤트를 시뮬레이션합니다."),
    "claim.return.requested": ("반품 요청", "고객이 반품 접수를 남긴 이벤트를 시뮬레이션합니다."),
    "delivery.delay.reported": ("배송 지연 알림", "배송 지연 이슈가 webhook으로 유입된 상황을 시뮬레이션합니다."),
}


@dataclass(slots=True)
class Cafe24ActivityEvent:
    occurred_at: datetime
    event_type: str
    status: str
    title: str
    detail: str
    batch_id: str | None = None


@dataclass(slots=True)
class Cafe24SyncSnapshot:
    last_synced_at: datetime | None = None
    last_sync_result: str = "not_started"
    last_sync_batch_id: str | None = None
    synced_orders: int = 0
    synced_claims: int = 0
    pending_webhooks: int = 0
    recent_events: list[Cafe24ActivityEvent] | None = None


class Cafe24SyncService:
    _snapshots: ClassVar[dict[int, Cafe24SyncSnapshot]] = {}

    def __init__(self, oauth_client: Cafe24OAuthClient) -> None:
        self.oauth_client = oauth_client

    @classmethod
    def reset_state(cls) -> None:
        cls._snapshots.clear()

    def _get_snapshot(self, merchant_id: int) -> Cafe24SyncSnapshot:
        snapshot = self._snapshots.get(merchant_id)
        if snapshot is None:
            snapshot = Cafe24SyncSnapshot(recent_events=[])
            self._snapshots[merchant_id] = snapshot
        elif snapshot.recent_events is None:
            snapshot.recent_events = []
        return snapshot

    def _append_event(self, merchant_id: int, event: Cafe24ActivityEvent) -> None:
        snapshot = self._get_snapshot(merchant_id)
        snapshot.recent_events.insert(0, event)
        snapshot.recent_events = snapshot.recent_events[:8]

    def clear_activity(self, merchant_id: int) -> None:
        snapshot = self._get_snapshot(merchant_id)
        snapshot.recent_events = []

    def _build_health_summary(
        self,
        snapshot: Cafe24SyncSnapshot,
        oauth_configured: bool,
        pending_claims: int,
    ) -> tuple[str, str, str]:
        if snapshot.last_sync_result == "not_started":
            return (
                "attention",
                "Mock Sync 대기",
                "아직 Cafe24 Mock Sync를 실행하지 않았습니다. 먼저 한 번 실행해 로컬 연동 흐름을 확인해 주세요.",
            )

        if not oauth_configured:
            return (
                "setup_needed",
                "OAuth env 미설정",
                "Mock Sync는 가능하지만 Cafe24 OAuth preview는 비활성화되어 있습니다. env를 채우면 연결 테스트가 완성됩니다.",
            )

        if snapshot.pending_webhooks >= 5:
            return (
                "attention",
                "Webhook 확인 필요",
                f"대기 중인 webhook이 {snapshot.pending_webhooks}건입니다. mock sync 또는 activity 흐름을 다시 확인해 주세요.",
            )

        if pending_claims >= 8:
            return (
                "attention",
                "처리 대기 문의 많음",
                f"현재 처리 대기 클레임이 {pending_claims}건입니다. 인박스에서 우선순위를 먼저 확인해 주세요.",
            )

        return (
            "healthy",
            "Mock 상태 양호",
            "최근 Mock Sync가 완료되었고 현재 대기 상태도 안정적입니다.",
        )

    def _build_next_action(
        self,
        snapshot: Cafe24SyncSnapshot,
        oauth_configured: bool,
        pending_claims: int,
    ) -> tuple[str, str, str | None]:
        if snapshot.last_sync_result == "not_started":
            return ("mock_sync", "Run Mock Sync", None)

        if not oauth_configured:
            return ("open_link", "Review OAuth Setup", "/integrations/cafe24")

        if snapshot.pending_webhooks >= 5:
            return ("open_link", "Review Activity", "/integrations/cafe24")

        if pending_claims >= 8:
            return ("open_link", "Open Inbox", "/inbox")

        return ("open_link", "Open Cafe24 Console", "/integrations/cafe24")

    def get_status(self, merchant: Merchant, claims: Sequence[Claim], settings: Settings) -> dict[str, object]:
        snapshot = self._get_snapshot(merchant.id)
        oauth_configured = bool(
            settings.cafe24_client_id and settings.cafe24_client_secret and settings.cafe24_redirect_uri
        )
        pending_claims = sum(claim.status in {ClaimStatus.OPEN, ClaimStatus.IN_REVIEW} for claim in claims)
        health_status, health_title, health_detail = self._build_health_summary(
            snapshot,
            oauth_configured,
            pending_claims,
        )
        next_action_type, next_action_label, next_action_href = self._build_next_action(
            snapshot,
            oauth_configured,
            pending_claims,
        )
        authorize_url = (
            self.oauth_client.build_authorize_url(merchant.mall_name, state=f"claimmate-local-{merchant.id}")
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
            "last_sync_result": snapshot.last_sync_result,
            "last_synced_at": snapshot.last_synced_at,
            "last_sync_batch_id": snapshot.last_sync_batch_id,
            "synced_orders": snapshot.synced_orders,
            "synced_claims": snapshot.synced_claims,
            "pending_claims": pending_claims,
            "pending_webhooks": snapshot.pending_webhooks,
            "recent_events": [
                {
                    "occurred_at": event.occurred_at,
                    "event_type": event.event_type,
                    "status": event.status,
                    "title": event.title,
                    "detail": event.detail,
                    "batch_id": event.batch_id,
                }
                for event in snapshot.recent_events or []
            ],
            "notes": [
                "Mock Sync uses seeded local claims and does not call Cafe24.",
                "Mock webhook simulation lets you test pending webhook backlog without network access.",
                "OAuth and webhook wiring stay as placeholders until live API work starts.",
                "Use this screen to validate the future Cafe24 integration flow before real credentials arrive.",
            ],
        }

    def run_mock_sync(self, merchant: Merchant, claims: Sequence[Claim], settings: Settings) -> dict[str, object]:
        pending_claims = sum(claim.status in {ClaimStatus.OPEN, ClaimStatus.IN_REVIEW} for claim in claims)
        now = datetime.now(timezone.utc)
        snapshot = self._get_snapshot(merchant.id)
        snapshot.last_synced_at = now
        snapshot.last_sync_result = "mock_completed"
        snapshot.last_sync_batch_id = f"mock-{merchant.id}-{int(now.timestamp())}"
        snapshot.synced_orders = len(claims) + 4
        snapshot.synced_claims = len(claims)
        snapshot.pending_webhooks = max(pending_claims // 2, 0)
        self._append_event(
            merchant.id,
            Cafe24ActivityEvent(
                occurred_at=now,
                event_type="mock_sync",
                status="success",
                title="Cafe24 Mock Sync completed",
                detail=f"{snapshot.synced_orders} orders and {snapshot.synced_claims} claims were refreshed locally.",
                batch_id=snapshot.last_sync_batch_id,
            ),
        )
        return self.get_status(merchant, claims, settings)

    def simulate_webhook(
        self,
        merchant: Merchant,
        claims: Sequence[Claim],
        settings: Settings,
        event_type: str,
        order_no: str | None = None,
    ) -> dict[str, object]:
        snapshot = self._get_snapshot(merchant.id)
        title, description = MOCK_WEBHOOK_LABELS.get(
            event_type,
            ("기타 Cafe24 webhook", "정의되지 않은 webhook 이벤트를 로컬 placeholder로 기록합니다."),
        )
        snapshot.pending_webhooks += 1
        self._append_event(
            merchant.id,
            Cafe24ActivityEvent(
                occurred_at=datetime.now(timezone.utc),
                event_type="mock_webhook",
                status="received",
                title=f"{title} webhook received",
                detail=f"{description}{f' 주문번호: {order_no}.' if order_no else ''}",
            ),
        )
        return self.get_status(merchant, claims, settings)

    def record_oauth_callback(
        self,
        merchant_id: int,
        result: str,
        message: str,
        state: str | None = None,
    ) -> None:
        title = "Cafe24 OAuth callback received" if result == "received" else "Cafe24 OAuth callback issue"
        detail = f"{message}{f' (state: {state})' if state else ''}"
        self._append_event(
            merchant_id,
            Cafe24ActivityEvent(
                occurred_at=datetime.now(timezone.utc),
                event_type="oauth_callback",
                status=result,
                title=title,
                detail=detail,
            ),
        )
