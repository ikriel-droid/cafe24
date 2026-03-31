import httpx

from app.ai.openai_provider import OpenAIProvider
from app.models import Claim, ClaimCategory, ClaimMessage, ClaimStatus, ClaimUrgency, Policy


def build_claim(category: ClaimCategory = ClaimCategory.EXCHANGE) -> Claim:
    return Claim(
        merchant_id=1,
        order_no="CM-OPENAI-001",
        customer_name="김테스트",
        product_name="테스트 니트",
        category=category,
        status=ClaimStatus.OPEN,
        reason_text="사이즈가 맞지 않아 교환 원합니다.",
        urgency=ClaimUrgency.MEDIUM,
    )


def build_policy() -> Policy:
    return Policy(
        merchant_id=1,
        exchange_window_days=7,
        return_window_days=7,
        return_shipping_fee=3500,
        exchange_shipping_fee=6000,
        refund_rule_text="검수 후 2영업일 내 환불",
        exception_rule_text="오배송 및 불량은 판매자 부담",
    )


def test_openai_provider_uses_structured_outputs_for_standard_models(monkeypatch) -> None:
    request_payloads: list[dict] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, path, json=None):
            assert path == "responses"
            request_payloads.append(json)
            return httpx.Response(
                200,
                json={
                    "output_text": (
                        '{"category":"exchange","label":"exchange_request","urgency":"medium",'
                        '"confidence":0.93,"rationale":"사이즈 교환 요청으로 판단했습니다."}'
                    ),
                    "usage": {"input_tokens": 120, "output_tokens": 32, "total_tokens": 152},
                },
            )

    monkeypatch.setattr("app.ai.openai_provider.httpx.Client", FakeClient)

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
    )
    result = provider.classify_claim(build_claim(), [ClaimMessage(role="customer", body="교환 원해요.")])

    assert request_payloads
    assert request_payloads[0]["text"]["format"]["type"] == "json_schema"
    assert result.category == ClaimCategory.EXCHANGE
    assert result.metadata.provider_name == "openai_responses"
    assert result.metadata.usage.total_tokens == 152
    assert result.metadata.usage.estimated_cost_usd > 0


def test_openai_provider_uses_text_json_mode_for_pro_models(monkeypatch) -> None:
    request_payloads: list[dict] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, path, json=None):
            request_payloads.append(json)
            return httpx.Response(
                200,
                json={
                    "output_text": (
                        '{"draft_reply":"김테스트님, 안녕하세요. 주문번호 CM-OPENAI-001 건 확인했습니다. '
                        '교환은 7일 이내 접수 가능합니다. 감사합니다.",'
                        '"confidence":0.89,"rationale":"정책 기준을 반영했습니다."}'
                    ),
                    "usage": {"input_tokens": 200, "output_tokens": 48, "total_tokens": 248},
                },
            )

    monkeypatch.setattr("app.ai.openai_provider.httpx.Client", FakeClient)

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-5.4-pro",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
    )
    result = provider.draft_reply(
        build_claim(),
        build_policy(),
        [ClaimMessage(role="customer", body="교환 원해요.")],
    )

    assert request_payloads
    assert "text" not in request_payloads[0]
    assert result.draft_reply.startswith("김테스트님")
    assert result.metadata.model_name == "gpt-5.4-pro"
    assert result.metadata.fallback_used is False


def test_openai_provider_falls_back_to_mock_on_failure(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, path, json=None):
            return httpx.Response(500, text="upstream error")

    monkeypatch.setattr("app.ai.openai_provider.httpx.Client", FakeClient)

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-5.4",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
    )
    result = provider.classify_claim(build_claim(), [ClaimMessage(role="customer", body="교환 원해요.")])

    assert result.metadata.provider_name == "mock_rule_based"
    assert result.metadata.requested_provider_name == "openai_responses"
    assert result.metadata.fallback_used is True
    assert "status 500" in (result.metadata.fallback_reason or "")
