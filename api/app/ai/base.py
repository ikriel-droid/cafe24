from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.models import Claim, ClaimCategory, ClaimMessage, ClaimUrgency, Policy


@dataclass(slots=True)
class ClassificationResult:
    category: ClaimCategory
    label: str
    urgency: ClaimUrgency
    confidence: float
    rationale: str


@dataclass(slots=True)
class DraftReplyResult:
    draft_reply: str
    confidence: float
    rationale: str


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

