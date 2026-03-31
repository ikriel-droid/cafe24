from __future__ import annotations

import json
import logging
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any

import httpx

from app.core.config import get_settings
from app.observability.policies import get_circuit_breaker_registry, get_rate_limiter
from app.observability.redaction import masking_rules_summary, redact_payload


logger = logging.getLogger("claimmate.observability")


class ObservabilityService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._reset_state()

    def reset(self) -> None:
        with self._lock:
            self._reset_state()

    def record_request(self, *, method: str, route: str, status_code: int, duration_ms: float) -> None:
        settings = get_settings()
        bucket_key = (method.upper(), route)
        with self._lock:
            self._request_totals["total_requests"] += 1
            if 400 <= status_code < 500:
                self._request_totals["client_errors"] += 1
            if status_code >= 500:
                self._request_totals["server_errors"] += 1
            if duration_ms >= settings.slow_request_threshold_ms:
                self._request_totals["slow_requests"] += 1

            route_bucket = self._request_routes.setdefault(
                bucket_key,
                {
                    "method": method.upper(),
                    "route": route,
                    "request_count": 0,
                    "error_count": 0,
                    "slow_count": 0,
                    "total_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "last_status_code": None,
                    "last_seen_at": None,
                },
            )
            route_bucket["request_count"] += 1
            if status_code >= 400:
                route_bucket["error_count"] += 1
            if duration_ms >= settings.slow_request_threshold_ms:
                route_bucket["slow_count"] += 1
            route_bucket["total_duration_ms"] += duration_ms
            route_bucket["max_duration_ms"] = max(route_bucket["max_duration_ms"], duration_ms)
            route_bucket["last_status_code"] = status_code
            route_bucket["last_seen_at"] = datetime.now(UTC)

    def record_webhook_event(
        self,
        *,
        event_type: str,
        status: str,
        duplicate: bool = False,
    ) -> None:
        with self._lock:
            self._webhook_totals["total_received"] += 1
            if duplicate:
                self._webhook_totals["duplicate_count"] += 1
            if status in {"failed", "dead_letter"}:
                self._webhook_totals["failed_count"] += 1

            bucket = self._webhook_events.setdefault(
                event_type,
                {
                    "event_type": event_type,
                    "count": 0,
                    "duplicate_count": 0,
                    "failed_count": 0,
                    "last_status": None,
                    "last_seen_at": None,
                },
            )
            bucket["count"] += 1
            if duplicate:
                bucket["duplicate_count"] += 1
            if status in {"failed", "dead_letter"}:
                bucket["failed_count"] += 1
            bucket["last_status"] = status
            bucket["last_seen_at"] = datetime.now(UTC)

    def record_job_event(self, *, job_type: str, status: str) -> None:
        with self._lock:
            self._job_totals["total_runs"] += 1
            if status == "succeeded":
                self._job_totals["succeeded"] += 1
            elif status == "retry_scheduled":
                self._job_totals["retry_scheduled"] += 1
            elif status == "dead_letter":
                self._job_totals["dead_letter"] += 1

            bucket = self._job_types.setdefault(
                job_type,
                {
                    "job_type": job_type,
                    "run_count": 0,
                    "success_count": 0,
                    "retry_scheduled_count": 0,
                    "dead_letter_count": 0,
                    "last_status": None,
                    "last_seen_at": None,
                },
            )
            bucket["run_count"] += 1
            if status == "succeeded":
                bucket["success_count"] += 1
            elif status == "retry_scheduled":
                bucket["retry_scheduled_count"] += 1
            elif status == "dead_letter":
                bucket["dead_letter_count"] += 1
            bucket["last_status"] = status
            bucket["last_seen_at"] = datetime.now(UTC)

    def record_error(
        self,
        *,
        component: str,
        message: str,
        payload: dict[str, Any] | None = None,
        severity: str = "error",
    ) -> None:
        settings = get_settings()
        event = {
            "occurred_at": datetime.now(UTC),
            "component": component,
            "severity": severity,
            "message": message,
            "payload_json": redact_payload(payload or {}),
        }
        with self._lock:
            self._recent_errors.appendleft(event)
            while len(self._recent_errors) > settings.observability_max_events:
                self._recent_errors.pop()

        logger.error(json.dumps({"type": "structured_error", **_serialize_log_payload(event)}, ensure_ascii=False))

    def dispatch_alert(
        self,
        *,
        severity: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        settings = get_settings()
        redacted_payload = redact_payload(payload or {})
        event = {
            "occurred_at": datetime.now(UTC),
            "severity": severity,
            "event_type": event_type,
            "message": message,
            "payload_json": redacted_payload,
            "channel": "local_log",
            "delivery_status": "recorded",
            "delivery_error": None,
        }

        if settings.observability_alert_webhook_url:
            headers = {"content-type": "application/json"}
            if settings.observability_alert_webhook_token:
                headers["authorization"] = f"Bearer {settings.observability_alert_webhook_token}"
            try:
                httpx.post(
                    settings.observability_alert_webhook_url,
                    json={
                        "source": "claimmate-ai",
                        "severity": severity,
                        "event_type": event_type,
                        "message": message,
                        "payload": redacted_payload,
                    },
                    headers=headers,
                    timeout=settings.observability_alert_timeout_seconds,
                ).raise_for_status()
                event["channel"] = "webhook"
                event["delivery_status"] = "sent"
            except Exception as exc:  # pragma: no cover - network failure is environment-specific
                event["channel"] = "webhook"
                event["delivery_status"] = "failed"
                event["delivery_error"] = str(exc)

        with self._lock:
            self._recent_alerts.appendleft(event)
            while len(self._recent_alerts) > settings.observability_max_events:
                self._recent_alerts.pop()

        logger.warning(json.dumps({"type": "ops_alert", **_serialize_log_payload(event)}, ensure_ascii=False))

    def snapshot(self) -> dict[str, Any]:
        settings = get_settings()
        rate_limit_policies = get_rate_limiter().snapshot(
            {
                "auth_login": (settings.auth_login_rate_limit_per_minute, 60),
                "cafe24_live_webhook": (settings.cafe24_webhook_rate_limit_per_minute, 60),
            }
        )
        circuit_breakers = get_circuit_breaker_registry().snapshot()

        with self._lock:
            request_routes = []
            for route_bucket in sorted(
                self._request_routes.values(),
                key=lambda item: (item["request_count"], item["max_duration_ms"]),
                reverse=True,
            ):
                request_routes.append(
                    {
                        **route_bucket,
                        "avg_duration_ms": round(
                            route_bucket["total_duration_ms"] / max(route_bucket["request_count"], 1),
                            2,
                        ),
                    }
                )
            webhook_events = sorted(self._webhook_events.values(), key=lambda item: item["count"], reverse=True)
            job_types = sorted(self._job_types.values(), key=lambda item: item["run_count"], reverse=True)
            recent_alerts = list(self._recent_alerts)
            recent_errors = list(self._recent_errors)

            return {
                "generated_at": datetime.now(UTC),
                "environment": settings.app_env,
                "app_name": settings.app_name,
                "uptime_seconds": int((datetime.now(UTC) - self._started_at).total_seconds()),
                "request_metrics": {
                    **self._request_totals,
                    "routes": request_routes,
                },
                "webhook_metrics": {
                    **self._webhook_totals,
                    "events": webhook_events,
                },
                "job_metrics": {
                    **self._job_totals,
                    "job_types": job_types,
                },
                "recent_alerts": recent_alerts,
                "recent_errors": recent_errors,
                "circuit_breakers": circuit_breakers,
                "rate_limit_policies": rate_limit_policies,
                "timeout_policies": [
                    {"target": "OpenAI Responses API", "timeout_seconds": settings.openai_timeout_seconds},
                    {"target": "Cafe24 API", "timeout_seconds": settings.cafe24_api_timeout_seconds},
                    {"target": "Reply delivery webhook", "timeout_seconds": settings.reply_delivery_timeout_seconds},
                    {"target": "Alert webhook", "timeout_seconds": settings.observability_alert_timeout_seconds},
                ],
                "masking_rules": masking_rules_summary(),
            }

    def _reset_state(self) -> None:
        self._started_at = datetime.now(UTC)
        self._request_totals = {"total_requests": 0, "client_errors": 0, "server_errors": 0, "slow_requests": 0}
        self._request_routes: dict[tuple[str, str], dict[str, Any]] = {}
        self._webhook_totals = {"total_received": 0, "duplicate_count": 0, "failed_count": 0}
        self._webhook_events: dict[str, dict[str, Any]] = {}
        self._job_totals = {"total_runs": 0, "succeeded": 0, "retry_scheduled": 0, "dead_letter": 0}
        self._job_types: dict[str, dict[str, Any]] = {}
        self._recent_alerts = deque()
        self._recent_errors = deque()


_observability_service = ObservabilityService()


def get_observability_service() -> ObservabilityService:
    return _observability_service


def reset_observability_service() -> None:
    _observability_service.reset()


def _serialize_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized
