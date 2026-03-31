from __future__ import annotations

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.openai_api_key:
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
            input_cost_per_1m_tokens=settings.openai_input_cost_per_1m_tokens,
            output_cost_per_1m_tokens=settings.openai_output_cost_per_1m_tokens,
        )
    return MockAIProvider()
