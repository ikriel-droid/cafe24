from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.observability.policies import get_circuit_breaker_registry


@dataclass(slots=True)
class Cafe24OAuthTokens:
    access_token: str
    refresh_token: str | None
    token_type: str
    access_token_expires_at: datetime | None
    refresh_token_expires_at: datetime | None
    scopes: list[str]
    raw_response: dict[str, Any]


class Cafe24OAuthClient:
    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        redirect_uri: str = "",
        scopes: list[str] | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []
        self.timeout_seconds = timeout_seconds

    def build_authorize_url(self, mall_id: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "state": state,
        }
        if self.redirect_uri:
            params["redirect_uri"] = self.redirect_uri
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        return f"https://{mall_id}.cafe24api.com/api/v2/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, mall_id: str, code: str) -> Cafe24OAuthTokens:
        return self._request_tokens(
            mall_id,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
        )

    def refresh_access_token(self, mall_id: str, refresh_token: str) -> Cafe24OAuthTokens:
        return self._request_tokens(
            mall_id,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )

    def list_orders(self, mall_id: str, access_token: str, *, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request_json(
            "GET",
            f"https://{mall_id}.cafe24api.com/api/v2/admin/orders",
            access_token=access_token,
            params={"limit": str(limit)},
        )
        return _extract_collection(data, "orders")

    def list_order_shipments(self, mall_id: str, access_token: str, order_id: str) -> list[dict[str, Any]]:
        data = self._request_json(
            "GET",
            f"https://{mall_id}.cafe24api.com/api/v2/admin/orders/{order_id}/shipments",
            access_token=access_token,
        )
        return _extract_collection(data, "shipments")

    def _request_tokens(self, mall_id: str, payload: dict[str, str]) -> Cafe24OAuthTokens:
        def perform_request() -> Cafe24OAuthTokens:
            response = httpx.post(
                f"https://{mall_id}.cafe24api.com/api/v2/oauth/token",
                data=payload,
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            return Cafe24OAuthTokens(
                access_token=str(data["access_token"]),
                refresh_token=str(data["refresh_token"]) if data.get("refresh_token") else None,
                token_type=str(data.get("token_type") or "Bearer"),
                access_token_expires_at=_parse_expiry(data, "access_token_expires_at", "expires_at", "expires_in"),
                refresh_token_expires_at=_parse_expiry(
                    data,
                    "refresh_token_expires_at",
                    "refresh_expires_at",
                    "refresh_token_expires_in",
                ),
                scopes=_parse_scopes(data.get("scope") or data.get("scopes")),
                raw_response=data,
            )

        return get_circuit_breaker_registry().execute(
            "cafe24_api",
            "oauth_token",
            perform_request,
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        access_token: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        def perform_request() -> dict[str, Any] | list[dict[str, Any]]:
            response = httpx.request(
                method=method,
                url=url,
                params=params,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return {}

        return get_circuit_breaker_registry().execute(
            "cafe24_api",
            f"{method.lower()}:{url}",
            perform_request,
        )


def _parse_scopes(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).replace(",", " ")
    return [item.strip() for item in normalized.split() if item.strip()]


def _parse_expiry(payload: dict[str, Any], *candidate_keys: str) -> datetime | None:
    for key in candidate_keys:
        value = payload.get(key)
        if value in {None, ""}:
            continue
        if isinstance(value, (int, float)):
            if key.endswith("_in"):
                return datetime.now(UTC) + timedelta(seconds=int(value))
            return datetime.fromtimestamp(float(value), tz=UTC)
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                continue
            if normalized.isdigit():
                if key.endswith("_in"):
                    return datetime.now(UTC) + timedelta(seconds=int(normalized))
                return datetime.fromtimestamp(float(normalized), tz=UTC)
            try:
                return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _extract_collection(payload: dict[str, Any] | list[dict[str, Any]], preferred_key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    candidates = [preferred_key, "orders", "shipments", "items", "results", "data"]
    for key in candidates:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []
