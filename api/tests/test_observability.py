import pytest

from app.core.config import get_settings
from app.observability.policies import (
    CircuitBreakerOpenError,
    RateLimitExceededError,
    get_circuit_breaker_registry,
    get_rate_limiter,
    reset_resilience_state,
)
from app.observability.redaction import redact_payload
from app.observability.service import get_observability_service, reset_observability_service


def setup_function() -> None:
    get_settings.cache_clear()
    reset_resilience_state()
    reset_observability_service()


def test_redact_payload_masks_nested_sensitive_fields() -> None:
    payload = {
        "access_token": "secret-token",
        "authorization": "Bearer abc123",
        "customer_name": "홍길동",
        "email": "manager@example.com",
        "nested": {
            "refresh_token": "refresh-secret",
            "order_no": "CM-240301-001",
        },
    }

    redacted = redact_payload(payload)

    assert redacted["access_token"] == "[redacted]"
    assert redacted["authorization"] == "[redacted]"
    assert redacted["customer_name"] != "홍길동"
    assert redacted["email"] != "manager@example.com"
    assert redacted["nested"]["refresh_token"] == "[redacted]"
    assert redacted["nested"]["order_no"] != "CM-240301-001"


def test_alert_dispatch_supports_webhook_channel_and_masks_payload(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ALERT_WEBHOOK_URL", "https://alerts.test/ingest")
    monkeypatch.setenv("OBSERVABILITY_ALERT_WEBHOOK_TOKEN", "secret-alert-token")
    get_settings.cache_clear()
    reset_observability_service()

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.observability.service.httpx.post", fake_post)

    service = get_observability_service()
    service.dispatch_alert(
        severity="warning",
        event_type="test_alert",
        message="test alert message",
        payload={"authorization": "Bearer abc", "customer_name": "홍길동"},
    )

    assert captured["url"] == "https://alerts.test/ingest"
    assert captured["headers"]["authorization"] == "Bearer secret-alert-token"
    assert captured["json"]["payload"]["authorization"] == "[redacted]"
    assert captured["json"]["payload"]["customer_name"] != "홍길동"

    snapshot = service.snapshot()
    assert snapshot["recent_alerts"][0]["channel"] == "webhook"
    assert snapshot["recent_alerts"][0]["delivery_status"] == "sent"


def test_rate_limiter_and_circuit_breaker_track_protection_state() -> None:
    limiter = get_rate_limiter()
    limiter.check(scope="auth_login", key="127.0.0.1", limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        limiter.check(scope="auth_login", key="127.0.0.1", limit=1, window_seconds=60)

    registry = get_circuit_breaker_registry()

    with pytest.raises(RuntimeError):
        registry.execute(
            "external_service",
            "call",
            lambda: (_ for _ in ()).throw(RuntimeError("boom-1")),
            failure_threshold=2,
            recovery_seconds=30,
        )
    with pytest.raises(RuntimeError):
        registry.execute(
            "external_service",
            "call",
            lambda: (_ for _ in ()).throw(RuntimeError("boom-2")),
            failure_threshold=2,
            recovery_seconds=30,
        )
    with pytest.raises(CircuitBreakerOpenError):
        registry.execute(
            "external_service",
            "call",
            lambda: "should not run",
            failure_threshold=2,
            recovery_seconds=30,
        )

    snapshot = registry.snapshot()
    assert snapshot[0]["service_name"] == "external_service"
    assert snapshot[0]["state"] == "open"
    assert snapshot[0]["failure_count"] == 2
