from __future__ import annotations


class Cafe24WebhookHandler:
    def verify_signature(self, headers: dict[str, str], body: bytes) -> bool:
        # TODO: Validate Cafe24 webhook signatures once the integration is connected.
        return True

    def handle_event(self, payload: dict[str, object]) -> dict[str, object]:
        # TODO: Route webhook events into sync jobs or domain events when live integration is allowed.
        return {
            "status": "accepted",
            "message": "Cafe24 webhook placeholder received payload.",
            "payload_keys": sorted(payload.keys()),
        }

