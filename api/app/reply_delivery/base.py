from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from app.models import Claim, ReplyDeliveryChannel, ReplyDeliveryStatus


@dataclass(slots=True)
class ReplyDeliveryRequest:
    claim: Claim
    actor: str
    reply_body: str
    attempt_no: int


@dataclass(slots=True)
class ReplyDeliveryResult:
    channel: ReplyDeliveryChannel
    status: ReplyDeliveryStatus
    provider: str
    destination: str | None
    external_delivery_id: str | None
    request_payload: dict[str, Any] | None
    response_payload: dict[str, Any] | None
    sent_at: datetime


class ReplyDeliveryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        channel: ReplyDeliveryChannel,
        provider: str,
        destination: str | None = None,
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.channel = channel
        self.provider = provider
        self.destination = destination
        self.request_payload = request_payload
        self.response_payload = response_payload
        self.failed_at = datetime.now(UTC)


class ReplyDeliveryProvider(Protocol):
    def send_reply(self, request: ReplyDeliveryRequest) -> ReplyDeliveryResult:
        ...
