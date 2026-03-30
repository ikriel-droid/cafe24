from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass


class Cafe24WebhookVerificationError(Exception):
    pass


@dataclass(slots=True)
class Cafe24WebhookEnvelope:
    event_type: str
    dedupe_key: str
    external_event_id: str | None
    signature: str | None


class Cafe24WebhookHandler:
    signature_headers = (
        "x-cafe24-signature",
        "x-cafe24-webhook-signature",
        "x-cafe24-hmac-sha256",
    )
    delivery_id_headers = ("x-cafe24-delivery-id", "x-cafe24-event-id", "x-request-id")
    event_type_headers = ("x-cafe24-event-type", "x-cafe24-event")

    def __init__(self, signing_secret: str = "") -> None:
        self.signing_secret = signing_secret

    def verify_signature(self, headers: dict[str, str], body: bytes) -> bool:
        signature = self._extract_header(headers, self.signature_headers)
        if not self.signing_secret or not signature:
            return False
        expected = base64.b64encode(
            hmac.new(self.signing_secret.encode("utf-8"), body, hashlib.sha256).digest()
        ).decode("utf-8")
        return hmac.compare_digest(signature, expected)

    def build_envelope(self, headers: dict[str, str], body: bytes, payload: dict[str, object]) -> Cafe24WebhookEnvelope:
        signature = self._extract_header(headers, self.signature_headers)
        event_type = self._extract_event_type(headers, payload)
        external_event_id = self._extract_header(headers, self.delivery_id_headers)
        body_hash = hashlib.sha256(body).hexdigest()
        dedupe_key = f"{event_type}:{external_event_id or body_hash}"
        return Cafe24WebhookEnvelope(
            event_type=event_type,
            dedupe_key=dedupe_key,
            external_event_id=external_event_id,
            signature=signature,
        )

    def handle_event(self, payload: dict[str, object]) -> dict[str, object]:
        # TODO: Route webhook events into sync jobs or domain events when live integration is allowed.
        return {
            "status": "accepted",
            "message": "Cafe24 webhook placeholder received payload.",
            "payload_keys": sorted(payload.keys()),
        }

    def require_valid_signature(self, headers: dict[str, str], body: bytes) -> None:
        if not self.verify_signature(headers, body):
            raise Cafe24WebhookVerificationError("Cafe24 webhook signature verification failed.")

    def _extract_event_type(self, headers: dict[str, str], payload: dict[str, object]) -> str:
        header_value = self._extract_header(headers, self.event_type_headers)
        if header_value:
            return header_value
        for candidate in ("event_type", "event", "type"):
            value = payload.get(candidate)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "unknown"

    @staticmethod
    def _extract_header(headers: dict[str, str], candidates: tuple[str, ...]) -> str | None:
        lowered = {key.lower(): value for key, value in headers.items()}
        for key in candidates:
            value = lowered.get(key)
            if value:
                return value.strip()
        return None
