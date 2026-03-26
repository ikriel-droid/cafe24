from __future__ import annotations

from typing import Sequence

from app.ai.base import AIProvider, ClassificationResult, DraftReplyResult
from app.ai.mock_provider import MockAIProvider
from app.models import Claim, ClaimMessage, Policy


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._fallback = MockAIProvider()

    def classify_claim(self, claim: Claim, messages: Sequence[ClaimMessage]) -> ClassificationResult:
        # TODO: Replace this placeholder with a real OpenAI completion call once live integration is allowed.
        result = self._fallback.classify_claim(claim, messages)
        result.rationale = (
            f"OpenAI provider placeholder active for model {self.model}. "
            f"Falling back to deterministic mock classification. {result.rationale}"
        )
        return result

    def draft_reply(
        self,
        claim: Claim,
        policy: Policy,
        messages: Sequence[ClaimMessage],
    ) -> DraftReplyResult:
        # TODO: Replace this placeholder with a real OpenAI completion call once live integration is allowed.
        result = self._fallback.draft_reply(claim, policy, messages)
        result.rationale = (
            f"OpenAI provider placeholder active for model {self.model}. "
            f"Falling back to deterministic mock draft generation. {result.rationale}"
        )
        return result

