from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx


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

    def _request_tokens(self, mall_id: str, payload: dict[str, str]) -> Cafe24OAuthTokens:
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
            refresh_token_expires_at=_parse_expiry(data, "refresh_token_expires_at", "refresh_expires_at", "refresh_token_expires_in"),
            scopes=_parse_scopes(data.get("scope") or data.get("scopes")),
            raw_response=data,
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
