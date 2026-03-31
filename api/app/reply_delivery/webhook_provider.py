from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.models import ReplyDeliveryChannel, ReplyDeliveryStatus
from app.observability.policies import get_circuit_breaker_registry
from app.observability.service import get_observability_service
from app.reply_delivery.base import ReplyDeliveryError, ReplyDeliveryProvider, ReplyDeliveryRequest, ReplyDeliveryResult


class WebhookReplyDeliveryProvider(ReplyDeliveryProvider):
    def __init__(self, webhook_url: str, token: str | None = None, timeout_seconds: int = 10) -> None:
        self.webhook_url = webhook_url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def send_reply(self, request: ReplyDeliveryRequest) -> ReplyDeliveryResult:
        payload = self._build_payload(request)
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"

        try:
            response = get_circuit_breaker_registry().execute(
                "reply_delivery_webhook",
                "send_reply",
                lambda: self._send_http_request(payload, headers),
            )
        except Exception as exc:
            get_observability_service().record_error(
                component="reply_delivery_webhook",
                message=str(exc),
                payload={"claim_id": request.claim.id, "webhook_url": self.webhook_url},
                severity="warning",
            )
            raise ReplyDeliveryError(
                f"Reply delivery webhook request failed: {exc}",
                channel=ReplyDeliveryChannel.WEBHOOK,
                provider="reply_delivery_webhook",
                destination=self.webhook_url,
                request_payload=payload,
            ) from exc

        response_payload = self._safe_json(response)
        if response.is_error:
            raise ReplyDeliveryError(
                f"Reply delivery webhook returned HTTP {response.status_code}.",
                channel=ReplyDeliveryChannel.WEBHOOK,
                provider="reply_delivery_webhook",
                destination=self.webhook_url,
                request_payload=payload,
                response_payload=response_payload,
            )

        external_delivery_id = None
        if isinstance(response_payload, dict):
            for key in ("delivery_id", "message_id", "id"):
                value = response_payload.get(key)
                if isinstance(value, str) and value.strip():
                    external_delivery_id = value.strip()
                    break

        return ReplyDeliveryResult(
            channel=ReplyDeliveryChannel.WEBHOOK,
            status=ReplyDeliveryStatus.SENT,
            provider="reply_delivery_webhook",
            destination=self.webhook_url,
            external_delivery_id=external_delivery_id,
            request_payload=payload,
            response_payload=response_payload,
            sent_at=datetime.now(UTC),
        )

    def _send_http_request(self, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(self.webhook_url, json=payload, headers=headers)

    def _build_payload(self, request: ReplyDeliveryRequest) -> dict[str, Any]:
        claim = request.claim
        return {
            "claim_id": claim.id,
            "merchant_id": claim.merchant_id,
            "order_no": claim.order_no,
            "customer_name": claim.customer_name,
            "product_name": claim.product_name,
            "category": claim.category.value,
            "status": claim.status.value,
            "ai_label": claim.ai_label,
            "actor": request.actor,
            "attempt_no": request.attempt_no,
            "reply_body": request.reply_body,
        }

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return {"status_code": response.status_code, "body": text[:500]}

        if isinstance(payload, dict):
            payload.setdefault("status_code", response.status_code)
            return payload
        return {"status_code": response.status_code, "body": payload}
