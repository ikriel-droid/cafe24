from __future__ import annotations

from datetime import UTC, datetime

from app.models import ReplyDeliveryChannel, ReplyDeliveryStatus
from app.reply_delivery.base import ReplyDeliveryProvider, ReplyDeliveryRequest, ReplyDeliveryResult


class ManualHandoffReplyDeliveryProvider(ReplyDeliveryProvider):
    def __init__(self, channel_label: str) -> None:
        self.channel_label = channel_label or "Cafe24 Admin Manual Handoff"

    def send_reply(self, request: ReplyDeliveryRequest) -> ReplyDeliveryResult:
        return ReplyDeliveryResult(
            channel=ReplyDeliveryChannel.MANUAL_HANDOFF,
            status=ReplyDeliveryStatus.SENT,
            provider="manual_handoff",
            destination=self.channel_label,
            external_delivery_id=None,
            request_payload={
                "claim_id": request.claim.id,
                "order_no": request.claim.order_no,
                "attempt_no": request.attempt_no,
                "mode": "manual_handoff",
            },
            response_payload={
                "status": "recorded",
                "message": "Operator confirmed manual handoff through the merchant support channel.",
            },
            sent_at=datetime.now(UTC),
        )
