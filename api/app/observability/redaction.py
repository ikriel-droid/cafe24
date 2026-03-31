from __future__ import annotations

from typing import Any


REDACTED = "[redacted]"
MASKED = "[masked]"

_DIRECT_REDACT_KEYS = {
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "authorization",
    "password",
    "password_hash",
    "signature",
    "token",
    "secret",
}
_MASK_KEYS = {
    "customer_name",
    "email",
    "order_no",
    "destination",
}


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _redact_value(str(key), value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload


def masking_rules_summary() -> list[str]:
    return [
        "access_token, refresh_token, api_key, client_secret, authorization, password, signature는 완전 마스킹합니다.",
        "customer_name, email, order_no, destination은 식별이 어렵도록 부분 마스킹합니다.",
        "중첩 JSON payload도 같은 규칙으로 재귀 마스킹합니다.",
    ]


def _redact_value(key: str, value: Any) -> Any:
    normalized_key = key.lower()
    if normalized_key in _DIRECT_REDACT_KEYS or any(secret_key in normalized_key for secret_key in _DIRECT_REDACT_KEYS):
        return REDACTED
    if normalized_key in _MASK_KEYS:
        return _mask_identifier(value)
    if isinstance(value, dict):
        return {str(child_key): _redact_value(str(child_key), child_value) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [_redact_value(normalized_key, item) for item in value]
    return value


def _mask_identifier(value: Any) -> Any:
    if not isinstance(value, str):
        return MASKED

    normalized = value.strip()
    if not normalized:
        return value

    if "@" in normalized:
        local, _, domain = normalized.partition("@")
        if len(local) <= 2:
            return f"{local[:1]}***@{domain}"
        return f"{local[:2]}***@{domain}"

    if "-" in normalized and len(normalized) >= 6:
        return f"{normalized[:3]}***{normalized[-2:]}"

    if len(normalized) <= 2:
        return f"{normalized[:1]}*"

    return f"{normalized[:1]}{'*' * max(len(normalized) - 2, 1)}{normalized[-1:]}"
