from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.models import Claim, ClaimMessage, Policy


CLASSIFICATION_PROMPT_KEY = "claim_classification"
CLASSIFICATION_PROMPT_VERSION = "claimmate-classification-v1"
DRAFT_REPLY_PROMPT_KEY = "claim_draft_reply"
DRAFT_REPLY_PROMPT_VERSION = "claimmate-draft-reply-v1"


@dataclass(slots=True)
class PromptBundle:
    prompt_key: str
    prompt_version: str
    developer_message: str
    user_message: str


def _format_messages(messages: Sequence[ClaimMessage]) -> str:
    if not messages:
        return "- 메시지 없음"
    return "\n".join(f"- {message.role}: {message.body.strip()}" for message in messages if message.body.strip())


def _policy_summary(policy: Policy) -> str:
    return "\n".join(
        [
            f"- 교환 가능 기간: 배송 완료 후 {policy.exchange_window_days}일",
            f"- 반품 가능 기간: 배송 완료 후 {policy.return_window_days}일",
            f"- 반품 배송비: {policy.return_shipping_fee:,}원",
            f"- 교환 배송비: {policy.exchange_shipping_fee:,}원",
            f"- 환불 정책: {policy.refund_rule_text.strip()}",
            f"- 예외 정책: {policy.exception_rule_text.strip()}",
        ]
    )


def build_classification_prompt(claim: Claim, messages: Sequence[ClaimMessage]) -> PromptBundle:
    developer_message = (
        "You are ClaimMate AI for Korean Cafe24 merchants. "
        "Classify a merchant claim into one of these exact categories: "
        "delivery, cancellation, exchange, return, refund, defect, misdelivery, other. "
        "Also choose one urgency: low, medium, high. "
        "Keep the label concise, snake_case, and operational. "
        "Base the answer on the customer issue only. "
        "If damaged, broken, defective, or wrong item is reported, urgency should lean higher. "
        "Return JSON only."
    )
    user_message = "\n".join(
        [
            f"주문번호: {claim.order_no}",
            f"고객명: {claim.customer_name}",
            f"상품명: {claim.product_name}",
            f"현재 카테고리: {claim.category.value}",
            f"현재 상태: {claim.status.value}",
            f"문의 본문: {claim.reason_text.strip()}",
            "메시지 타임라인:",
            _format_messages(messages),
            "",
            "JSON schema:",
            '{"category":"delivery|cancellation|exchange|return|refund|defect|misdelivery|other",'
            '"label":"snake_case_label","urgency":"low|medium|high","confidence":0.0,"rationale":"string"}',
        ]
    )
    return PromptBundle(
        prompt_key=CLASSIFICATION_PROMPT_KEY,
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        developer_message=developer_message,
        user_message=user_message,
    )


def build_draft_reply_prompt(claim: Claim, policy: Policy, messages: Sequence[ClaimMessage]) -> PromptBundle:
    developer_message = (
        "You draft Korean customer-service replies for Cafe24 merchants. "
        "Write polite, concise Korean. "
        "Reflect the merchant policy when it is relevant. "
        "Mention the order number naturally. "
        "Do not promise anything outside the provided policy. "
        "If the case is risky or incomplete, acknowledge review and avoid overcommitting. "
        "Return JSON only."
    )
    user_message = "\n".join(
        [
            f"주문번호: {claim.order_no}",
            f"고객명: {claim.customer_name}",
            f"상품명: {claim.product_name}",
            f"클레임 카테고리: {claim.category.value}",
            f"긴급도: {claim.urgency.value}",
            f"문의 본문: {claim.reason_text.strip()}",
            "메시지 타임라인:",
            _format_messages(messages),
            "",
            "merchant policy:",
            _policy_summary(policy),
            "",
            "JSON schema:",
            '{"draft_reply":"korean_reply","confidence":0.0,"rationale":"string"}',
        ]
    )
    return PromptBundle(
        prompt_key=DRAFT_REPLY_PROMPT_KEY,
        prompt_version=DRAFT_REPLY_PROMPT_VERSION,
        developer_message=developer_message,
        user_message=user_message,
    )
