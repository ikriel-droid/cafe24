from __future__ import annotations

from typing import Sequence

from app.ai.base import AIProvider, AIResultMetadata, AIUsage, ClassificationResult, DraftReplyResult
from app.ai.prompts import (
    CLASSIFICATION_PROMPT_KEY,
    CLASSIFICATION_PROMPT_VERSION,
    DRAFT_REPLY_PROMPT_KEY,
    DRAFT_REPLY_PROMPT_VERSION,
)
from app.models import Claim, ClaimCategory, ClaimMessage, ClaimUrgency, Policy


class MockAIProvider(AIProvider):
    provider_name = "mock_rule_based"
    model_name = "offline-rules-v1"

    def classify_claim(self, claim: Claim, messages: Sequence[ClaimMessage]) -> ClassificationResult:
        combined_text = " ".join([claim.reason_text, *[message.body for message in messages]]).lower()

        rules: list[tuple[list[str], ClaimCategory, str, ClaimUrgency, float, str]] = [
            (
                ["파손", "깨짐", "불량", "고장", "찢어"],
                ClaimCategory.DEFECT,
                "damage_or_defect",
                ClaimUrgency.HIGH,
                0.96,
                "파손 또는 불량 관련 표현이 포함되어 있어 긴급 검토가 필요한 클레임으로 판단했습니다.",
            ),
            (
                ["오배송", "잘못 배송", "다른 상품", "다른 색상", "다른 사이즈"],
                ClaimCategory.MISDELIVERY,
                "misdelivery_detected",
                ClaimUrgency.HIGH,
                0.95,
                "오배송을 시사하는 표현이 있어 즉시 확인이 필요한 건으로 분류했습니다.",
            ),
            (
                ["교환", "사이즈", "색상 변경"],
                ClaimCategory.EXCHANGE,
                "exchange_request",
                ClaimUrgency.MEDIUM,
                0.91,
                "사이즈 또는 색상 변경 요청이 포함되어 있어 교환 요청으로 분류했습니다.",
            ),
            (
                ["반품", "변심", "회수"],
                ClaimCategory.RETURN,
                "return_request",
                ClaimUrgency.MEDIUM,
                0.9,
                "반품 또는 단순 변심 관련 문의로 판단했습니다.",
            ),
            (
                ["환불", "결제 취소", "카드 취소"],
                ClaimCategory.REFUND,
                "refund_status_request",
                ClaimUrgency.MEDIUM,
                0.88,
                "환불 처리 상태를 묻는 문의로 분류했습니다.",
            ),
            (
                ["취소", "주문 취소"],
                ClaimCategory.CANCELLATION,
                "cancellation_request",
                ClaimUrgency.MEDIUM,
                0.87,
                "주문 취소 의사가 명확해 취소 요청으로 분류했습니다.",
            ),
            (
                ["배송", "언제", "출고", "송장"],
                ClaimCategory.DELIVERY,
                "delivery_inquiry",
                ClaimUrgency.LOW,
                0.84,
                "배송 상태를 묻는 표현이 포함되어 있어 배송 문의로 분류했습니다.",
            ),
        ]

        for keywords, category, label, urgency, confidence, rationale in rules:
            if any(keyword in combined_text for keyword in keywords):
                if any(keyword in combined_text for keyword in ["급", "빨리", "오늘", "당장"]):
                    urgency = ClaimUrgency.HIGH if urgency != ClaimUrgency.HIGH else urgency
                return ClassificationResult(
                    category=category,
                    label=label,
                    urgency=urgency,
                    confidence=confidence,
                    rationale=rationale,
                    metadata=AIResultMetadata(
                        provider_name=self.provider_name,
                        requested_provider_name=self.provider_name,
                        model_name=self.model_name,
                        prompt_key=CLASSIFICATION_PROMPT_KEY,
                        prompt_version=CLASSIFICATION_PROMPT_VERSION,
                        usage=AIUsage(),
                    ),
                )

        return ClassificationResult(
            category=ClaimCategory.OTHER,
            label="general_inquiry",
            urgency=ClaimUrgency.LOW,
            confidence=0.68,
            rationale="명확한 분류 신호가 부족해 일반 문의로 분류했습니다.",
            metadata=AIResultMetadata(
                provider_name=self.provider_name,
                requested_provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_key=CLASSIFICATION_PROMPT_KEY,
                prompt_version=CLASSIFICATION_PROMPT_VERSION,
                usage=AIUsage(),
            ),
        )

    def draft_reply(
        self,
        claim: Claim,
        policy: Policy,
        messages: Sequence[ClaimMessage],
    ) -> DraftReplyResult:
        greeting = f"{claim.customer_name}님, 안녕하세요. ClaimMate AI 데모 상담 도우미입니다."
        order_line = f"주문번호 {claim.order_no} 건 확인했습니다."

        category_templates: dict[ClaimCategory, str] = {
            ClaimCategory.EXCHANGE: (
                f"교환은 배송 완료 후 {policy.exchange_window_days}일 이내 접수 가능하며, "
                f"단순 변심 교환 시 왕복 배송비 {policy.exchange_shipping_fee:,}원이 안내됩니다. "
                "원하시는 사이즈나 옵션을 남겨주시면 확인 후 절차를 안내드리겠습니다."
            ),
            ClaimCategory.RETURN: (
                f"반품은 배송 완료 후 {policy.return_window_days}일 이내 접수 가능하며, "
                f"단순 변심 반품 시 반품 배송비 {policy.return_shipping_fee:,}원이 발생할 수 있습니다. "
                f"환불 기준은 다음 정책을 따릅니다: {policy.refund_rule_text}"
            ),
            ClaimCategory.REFUND: (
                f"환불 처리 상태를 확인 중이며, 현재 환불 정책은 다음과 같습니다: {policy.refund_rule_text} "
                "검수 또는 승인 상태를 확인한 뒤 다시 안내드리겠습니다."
            ),
            ClaimCategory.CANCELLATION: (
                "출고 전 주문이면 취소 가능 여부를 우선 확인하겠습니다. "
                "이미 출고된 경우에는 반품 절차로 전환될 수 있으며, 확인 후 가장 빠른 처리 방안을 안내드리겠습니다."
            ),
            ClaimCategory.DELIVERY: (
                "배송 흐름을 확인 중이며 출고 및 배송 이동 상태를 조회한 뒤 다시 안내드리겠습니다. "
                "송장 반영 지연이 있는 경우에는 택배사 이동 정보도 함께 확인하겠습니다."
            ),
            ClaimCategory.DEFECT: (
                "불편을 드려 죄송합니다. 파손 또는 불량으로 확인되면 추가 배송비 없이 교환 또는 환불 우선 처리하겠습니다. "
                f"예외 정책은 다음과 같습니다: {policy.exception_rule_text}"
            ),
            ClaimCategory.MISDELIVERY: (
                "오배송 여부를 우선 확인하겠습니다. 오배송으로 확인되면 추가 배송비 없이 회수 및 재발송 절차를 안내드리겠습니다. "
                f"예외 처리 기준은 다음과 같습니다: {policy.exception_rule_text}"
            ),
            ClaimCategory.OTHER: (
                "문의 내용을 확인 중이며, 필요한 주문 정보와 처리 기준을 확인한 뒤 가장 적절한 답변을 안내드리겠습니다."
            ),
        }

        message_hint = ""
        if messages:
            last_message = messages[-1].body.strip()
            if last_message:
                message_hint = f" 고객님께서 남겨주신 최근 메시지 \"{last_message}\"도 함께 반영해 확인하겠습니다."

        draft_reply = " ".join(
            [
                greeting,
                order_line,
                category_templates.get(claim.category, category_templates[ClaimCategory.OTHER]),
                message_hint,
                "확인 후 가능한 가장 빠르게 다시 안내드리겠습니다. 감사합니다.",
            ]
        ).strip()

        return DraftReplyResult(
            draft_reply=draft_reply,
            confidence=0.86,
            rationale="규칙 기반 정책 템플릿과 최근 메시지를 결합해 답변 초안을 생성했습니다.",
            metadata=AIResultMetadata(
                provider_name=self.provider_name,
                requested_provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_key=DRAFT_REPLY_PROMPT_KEY,
                prompt_version=DRAFT_REPLY_PROMPT_VERSION,
                usage=AIUsage(),
            ),
        )
