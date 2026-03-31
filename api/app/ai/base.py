from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from app.models import Claim, ClaimCategory, ClaimMessage, ClaimUrgency, Policy


@dataclass(slots=True)
class AIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(slots=True)
class AIEvaluationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(slots=True)
class AIResultMetadata:
    provider_name: str
    requested_provider_name: str
    model_name: str
    prompt_key: str
    prompt_version: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    evaluation_summary: str = ""
    evaluation_checks: list[AIEvaluationCheck] = field(default_factory=list)
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass(slots=True)
class ClassificationResult:
    category: ClaimCategory
    label: str
    urgency: ClaimUrgency
    confidence: float
    rationale: str
    metadata: AIResultMetadata


@dataclass(slots=True)
class DraftReplyResult:
    draft_reply: str
    confidence: float
    rationale: str
    metadata: AIResultMetadata


class AIProvider(Protocol):
    def classify_claim(self, claim: Claim, messages: Sequence[ClaimMessage]) -> ClassificationResult:
        ...

    def draft_reply(
        self,
        claim: Claim,
        policy: Policy,
        messages: Sequence[ClaimMessage],
    ) -> DraftReplyResult:
        ...
