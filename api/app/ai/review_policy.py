from __future__ import annotations

from app.ai.base import AIEvaluationCheck, AIResultMetadata, ClassificationResult, DraftReplyResult
from app.models import Claim, ClaimCategory, Policy


HIGH_RISK_CATEGORIES = {
    ClaimCategory.DEFECT,
    ClaimCategory.MISDELIVERY,
    ClaimCategory.REFUND,
}
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.8
DRAFT_CONFIDENCE_THRESHOLD = 0.84


def _finalize_metadata(
    metadata: AIResultMetadata,
    *,
    checks: list[AIEvaluationCheck],
    review_reasons: list[str],
) -> None:
    passed = sum(1 for check in checks if check.passed)
    metadata.evaluation_checks = checks
    metadata.review_reasons = review_reasons
    metadata.review_required = bool(review_reasons)
    metadata.evaluation_summary = (
        f"checks_passed={passed}/{len(checks)}; "
        f"review_required={'yes' if metadata.review_required else 'no'}"
    )


def apply_classification_review_policy(claim: Claim, result: ClassificationResult) -> ClassificationResult:
    checks = [
        AIEvaluationCheck(
            name="confidence_threshold",
            passed=result.confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD,
            detail=f"confidence={result.confidence:.2f}, threshold={CLASSIFICATION_CONFIDENCE_THRESHOLD:.2f}",
        ),
        AIEvaluationCheck(
            name="label_present",
            passed=bool(result.label.strip()),
            detail="AI label must be non-empty.",
        ),
        AIEvaluationCheck(
            name="rationale_present",
            passed=bool(result.rationale.strip()),
            detail="Classification rationale must be non-empty.",
        ),
        AIEvaluationCheck(
            name="category_known",
            passed=result.category in set(ClaimCategory),
            detail="Classification category must match the supported enum set.",
        ),
    ]

    review_reasons: list[str] = []
    if result.metadata.fallback_used:
        review_reasons.append("fallback_used")
    if result.confidence < CLASSIFICATION_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_classification_confidence")
    if result.category in HIGH_RISK_CATEGORIES or result.urgency.value == "high":
        review_reasons.append("high_risk_claim")

    _finalize_metadata(result.metadata, checks=checks, review_reasons=review_reasons)
    return result


def _reply_requires_policy_reference(claim: Claim) -> bool:
    return claim.category in {ClaimCategory.EXCHANGE, ClaimCategory.RETURN, ClaimCategory.REFUND}


def _has_policy_reference(claim: Claim, policy: Policy, draft_reply: str) -> bool:
    if claim.category == ClaimCategory.EXCHANGE:
        return str(policy.exchange_window_days) in draft_reply or f"{policy.exchange_shipping_fee:,}" in draft_reply
    if claim.category == ClaimCategory.RETURN:
        return str(policy.return_window_days) in draft_reply or f"{policy.return_shipping_fee:,}" in draft_reply
    if claim.category == ClaimCategory.REFUND:
        return bool(policy.refund_rule_text.strip()) and policy.refund_rule_text.strip()[:8] in draft_reply
    return True


def apply_draft_review_policy(claim: Claim, policy: Policy, result: DraftReplyResult) -> DraftReplyResult:
    draft_reply = result.draft_reply.strip()
    checks = [
        AIEvaluationCheck(
            name="confidence_threshold",
            passed=result.confidence >= DRAFT_CONFIDENCE_THRESHOLD,
            detail=f"confidence={result.confidence:.2f}, threshold={DRAFT_CONFIDENCE_THRESHOLD:.2f}",
        ),
        AIEvaluationCheck(
            name="mentions_order_no",
            passed=claim.order_no in draft_reply,
            detail="Draft should reference the order number for operator traceability.",
        ),
        AIEvaluationCheck(
            name="mentions_customer_name",
            passed=claim.customer_name in draft_reply,
            detail="Draft should address the customer by name.",
        ),
        AIEvaluationCheck(
            name="policy_reference",
            passed=not _reply_requires_policy_reference(claim) or _has_policy_reference(claim, policy, draft_reply),
            detail="Exchange/return/refund drafts should include a relevant policy detail.",
        ),
        AIEvaluationCheck(
            name="polite_closure",
            passed=("감사" in draft_reply) or ("도와" in draft_reply) or ("안내" in draft_reply),
            detail="Draft should include a polite service-oriented closing or guidance phrase.",
        ),
    ]

    review_reasons: list[str] = []
    if result.metadata.fallback_used:
        review_reasons.append("fallback_used")
    if result.confidence < DRAFT_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_draft_confidence")
    if not checks[1].passed:
        review_reasons.append("missing_order_reference")
    if not checks[2].passed:
        review_reasons.append("missing_customer_reference")
    if not checks[3].passed:
        review_reasons.append("missing_policy_reference")
    if claim.category in HIGH_RISK_CATEGORIES or claim.urgency.value == "high":
        review_reasons.append("high_risk_claim")

    _finalize_metadata(result.metadata, checks=checks, review_reasons=review_reasons)
    return result
