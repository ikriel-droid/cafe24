from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(slots=True)
class Cafe24OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int


class Cafe24OAuthClient:
    def __init__(self, client_id: str = "", client_secret: str = "", redirect_uri: str = "") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorize_url(self, mall_id: str, state: str) -> str:
        # TODO: Attach the real Cafe24 authorization endpoint and scopes here.
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "state": state,
        }
        if self.redirect_uri:
            params["redirect_uri"] = self.redirect_uri
        return f"https://{mall_id}.cafe24api.com/api/v2/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> Cafe24OAuthTokens:
        # TODO: Replace this placeholder with a real token exchange request when live API work starts.
        raise NotImplementedError("Cafe24 OAuth token exchange is not implemented in the local MVP.")
