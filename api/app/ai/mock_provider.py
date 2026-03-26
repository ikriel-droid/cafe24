from __future__ import annotations

from typing import Sequence

from app.ai.base import AIProvider, ClassificationResult, DraftReplyResult
from app.models import Claim, ClaimCategory, ClaimMessage, ClaimUrgency, Policy


class MockAIProvider(AIProvider):
    def classify_claim(self, claim: Claim, messages: Sequence[ClaimMessage]) -> ClassificationResult:
        combined_text = " ".join([claim.reason_text, *[message.body for message in messages]]).lower()

        rules: list[tuple[list[str], ClaimCategory, str, ClaimUrgency, float, str]] = [
            (
                ["파손", "깨졌", "불량", "고장", "찢어"],
                ClaimCategory.DEFECT,
                "damage_or_defect",
                ClaimUrgency.HIGH,
                0.96,
                "파손 또는 불량 관련 키워드가 포함되어 있어 긴급 대응이 필요한 하자 클레임으로 분류했습니다.",
            ),
            (
                ["오배송", "잘못 배송", "다른 상품", "다른 색상", "다른 사이즈"],
                ClaimCategory.MISDELIVERY,
                "misdelivery_detected",
                ClaimUrgency.HIGH,
                0.95,
                "오배송을 시사하는 표현이 확인되어 재배송 또는 즉시 확인이 필요한 건으로 판단했습니다.",
            ),
            (
                ["교환", "사이즈", "색상 변경"],
                ClaimCategory.EXCHANGE,
                "exchange_request",
                ClaimUrgency.MEDIUM,
                0.91,
                "사이즈 또는 색상 변경 요청이 포함되어 교환 요청으로 분류했습니다.",
            ),
            (
                ["반품", "변심", "회수"],
                ClaimCategory.RETURN,
                "return_request",
                ClaimUrgency.MEDIUM,
                0.9,
                "반품 또는 단순 변심 관련 문맥이 확인되어 반품 처리 문의로 보았습니다.",
            ),
            (
                ["환불", "결제 취소", "카드 취소"],
                ClaimCategory.REFUND,
                "refund_status_request",
                ClaimUrgency.MEDIUM,
                0.88,
                "환불 상태 또는 처리 일정을 묻는 내용이어서 환불 문의로 분류했습니다.",
            ),
            (
                ["취소", "주문 취소"],
                ClaimCategory.CANCELLATION,
                "cancellation_request",
                ClaimUrgency.MEDIUM,
                0.87,
                "주문 취소 의사가 명시되어 취소 요청으로 분류했습니다.",
            ),
            (
                ["배송", "언제 오", "출고", "송장"],
                ClaimCategory.DELIVERY,
                "delivery_inquiry",
                ClaimUrgency.LOW,
                0.84,
                "배송 상태를 묻는 표현이 포함되어 배송 문의로 분류했습니다.",
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
                )

        return ClassificationResult(
            category=ClaimCategory.OTHER,
            label="general_inquiry",
            urgency=ClaimUrgency.LOW,
            confidence=0.68,
            rationale="명확한 카테고리 키워드가 부족해 일반 문의로 분류했습니다.",
        )

    def draft_reply(
        self,
        claim: Claim,
        policy: Policy,
        messages: Sequence[ClaimMessage],
    ) -> DraftReplyResult:
        customer_name = claim.customer_name
        greeting = f"{customer_name}님, 안녕하세요. ClaimMate AI 데모 상담 도우미입니다."
        order_line = f"주문번호 {claim.order_no} 건 확인했습니다."

        category_templates: dict[ClaimCategory, str] = {
            ClaimCategory.EXCHANGE: (
                f"교환은 수령일 기준 {policy.exchange_window_days}일 이내 접수 가능하며, "
                f"단순 변심 교환 시 왕복 배송비 {policy.exchange_shipping_fee:,}원이 안내됩니다. "
                "원하시는 사이즈 또는 옵션을 남겨주시면 절차를 바로 도와드리겠습니다."
            ),
            ClaimCategory.RETURN: (
                f"반품은 수령일 기준 {policy.return_window_days}일 이내 접수 가능하며, "
                f"단순 변심 반품 시 배송비 {policy.return_shipping_fee:,}원이 발생할 수 있습니다. "
                f"환불 정책은 다음 기준으로 처리됩니다: {policy.refund_rule_text}"
            ),
            ClaimCategory.REFUND: (
                f"환불 진행 상태를 확인 중입니다. 내부 기준은 다음과 같습니다: {policy.refund_rule_text} "
                "회수 또는 검수 상태를 확인한 뒤 바로 다시 안내드리겠습니다."
            ),
            ClaimCategory.CANCELLATION: (
                "출고 전 주문이면 즉시 취소 가능 여부를 우선 확인하겠습니다. "
                "이미 출고된 경우에는 반품 접수로 전환될 수 있으며 확인 후 가장 빠른 처리 방안을 안내드리겠습니다."
            ),
            ClaimCategory.DELIVERY: (
                "배송 흐름을 확인 중이며 출고 및 택배 이동 상태를 조회해 다시 안내드리겠습니다. "
                "송장 반영 지연이 있는 경우도 함께 확인하겠습니다."
            ),
            ClaimCategory.DEFECT: (
                "불편을 드려 죄송합니다. 파손 또는 불량으로 확인되면 추가 배송비 없이 교환 또는 환불을 우선 처리합니다. "
                f"예외 정책은 다음 기준을 따릅니다: {policy.exception_rule_text}"
            ),
            ClaimCategory.MISDELIVERY: (
                "오배송 여부를 우선 확인하겠습니다. 오배송으로 확인되면 추가 배송비 없이 재배송 또는 회수 절차를 진행하겠습니다. "
                f"예외 처리 기준은 다음과 같습니다: {policy.exception_rule_text}"
            ),
            ClaimCategory.OTHER: (
                "문의 내용을 확인 중이며 필요한 주문 정보를 점검한 뒤 가장 적절한 처리 방안을 안내드리겠습니다."
            ),
        }

        message_hint = ""
        if messages:
            last_message = messages[-1].body
            message_hint = f" 고객님 메시지 기준으로는 '{last_message}' 요청을 우선 반영하겠습니다."

        draft_reply = " ".join(
            [
                greeting,
                order_line,
                category_templates.get(claim.category, category_templates[ClaimCategory.OTHER]),
                message_hint,
                "확인 후 가능한 가장 빠르게 후속 안내드리겠습니다. 감사합니다.",
            ]
        ).strip()

        return DraftReplyResult(
            draft_reply=draft_reply,
            confidence=0.86,
            rationale="클레임 카테고리와 판매자 정책을 결합한 규칙 기반 응답 초안을 생성했습니다.",
        )

