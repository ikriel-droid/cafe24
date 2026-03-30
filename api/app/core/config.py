from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ClaimMate AI API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./claimmate.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
    default_merchant_id: int = 1
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cafe24_client_id: str | None = None
    cafe24_client_secret: str | None = None
    cafe24_redirect_uri: str | None = None
    cafe24_webhook_secret: str | None = None
    cafe24_scopes: Annotated[list[str], NoDecode] = []
    cafe24_api_timeout_seconds: int = 15
    reply_delivery_mode: str = "manual_handoff"
    reply_delivery_webhook_url: str | None = None
    reply_delivery_webhook_token: str | None = None
    reply_delivery_timeout_seconds: int = 10
    reply_delivery_manual_channel_label: str = "Cafe24 Admin Manual Handoff"
    seed_demo_data: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        if value is None:
            return "sqlite:///./claimmate.db"
        normalized = value.strip()
        return normalized or "sqlite:///./claimmate.db"

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "cafe24_client_id",
        "cafe24_client_secret",
        "cafe24_redirect_uri",
        "cafe24_webhook_secret",
        "reply_delivery_webhook_url",
        "reply_delivery_webhook_token",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("reply_delivery_mode", mode="before")
    @classmethod
    def normalize_reply_delivery_mode(cls, value: str | None) -> str:
        if value is None:
            return "manual_handoff"
        normalized = value.strip().lower()
        return normalized or "manual_handoff"

    @field_validator("cors_origins", "cafe24_scopes", mode="before")
    @classmethod
    def parse_csv_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        value = value.strip()
        if value.startswith("["):
            return json.loads(value)
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
