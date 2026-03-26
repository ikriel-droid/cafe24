from app.ai.mock_provider import MockAIProvider
from app.models import Claim, ClaimCategory, ClaimMessage, ClaimStatus, ClaimUrgency, Policy


def build_claim(reason_text: str, category: ClaimCategory = ClaimCategory.OTHER) -> Claim:
    return Claim(
        merchant_id=1,
        order_no="CM-TEST-001",
        customer_name="테스트고객",
        product_name="테스트 상품",
        category=category,
        status=ClaimStatus.OPEN,
        reason_text=reason_text,
        urgency=ClaimUrgency.MEDIUM,
    )


def test_mock_ai_classifies_damage_claim_as_defect() -> None:
    provider = MockAIProvider()
    claim = build_claim("상품이 파손되어 도착했고 빨리 교환 받고 싶어요.")
    messages = [ClaimMessage(role="customer", body="컵 손잡이가 깨졌습니다.")]

    result = provider.classify_claim(claim, messages)

    assert result.category == ClaimCategory.DEFECT
    assert result.urgency == ClaimUrgency.HIGH
    assert result.label == "damage_or_defect"


def test_mock_ai_generates_policy_aware_reply() -> None:
    provider = MockAIProvider()
    claim = build_claim("사이즈가 맞지 않아 교환 원합니다.", category=ClaimCategory.EXCHANGE)
    policy = Policy(
        merchant_id=1,
        exchange_window_days=7,
        return_window_days=7,
        return_shipping_fee=3500,
        exchange_shipping_fee=6000,
        refund_rule_text="검수 후 2영업일 내 환불",
        exception_rule_text="오배송/불량 시 판매자 부담",
    )
    messages = [ClaimMessage(role="customer", body="사이즈 M으로 교환하고 싶습니다.")]

    result = provider.draft_reply(claim, policy, messages)

    assert "7일" in result.draft_reply
    assert "6,000원" in result.draft_reply
    assert "교환" in result.draft_reply

