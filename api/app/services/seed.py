from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Claim,
    ClaimCategory,
    ClaimMessage,
    ClaimStatus,
    ClaimUrgency,
    Merchant,
    Policy,
)


DEMO_CLAIMS = [
    {
        "order_no": "CM-240301-001",
        "customer_name": "김민지",
        "product_name": "에어핏 데님 재킷",
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "사이즈가 맞지 않아 교환 원합니다.",
        "messages": [
            ("customer", "사이즈가 맞지 않아 교환 원합니다."),
            ("operator", "원하시는 사이즈를 알려주시면 확인 도와드리겠습니다."),
        ],
    },
    {
        "order_no": "CM-240301-002",
        "customer_name": "박서준",
        "product_name": "모던 세라믹 머그 2P",
        "category": ClaimCategory.DEFECT,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "상품이 파손되어 도착했습니다.",
        "messages": [
            ("customer", "박스를 열어보니 컵 손잡이가 깨져 있습니다."),
            ("customer", "상품이 파손되어 도착했습니다."),
        ],
    },
    {
        "order_no": "CM-240301-003",
        "customer_name": "이하은",
        "product_name": "코튼 릴렉스 팬츠",
        "category": ClaimCategory.REFUND,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "환불은 언제 처리되나요?",
        "messages": [
            ("customer", "반품은 보냈는데 환불은 언제 처리되나요?"),
        ],
    },
    {
        "order_no": "CM-240301-004",
        "customer_name": "정도윤",
        "product_name": "루나 텀블러 500ml",
        "category": ClaimCategory.MISDELIVERY,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "오배송된 것 같습니다.",
        "messages": [
            ("customer", "주문한 색상과 다른 상품이 왔어요."),
        ],
    },
    {
        "order_no": "CM-240301-005",
        "customer_name": "최지우",
        "product_name": "소프트 니트 가디건",
        "category": ClaimCategory.CANCELLATION,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "배송 전이면 주문 취소 부탁드립니다.",
        "messages": [
            ("customer", "색상을 잘못 주문해서 배송 전이면 주문 취소 부탁드립니다."),
        ],
    },
    {
        "order_no": "CM-240301-006",
        "customer_name": "윤서하",
        "product_name": "데일리 러닝화",
        "category": ClaimCategory.DELIVERY,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "배송이 언제 오나요?",
        "messages": [
            ("customer", "송장번호는 떴는데 배송이 멈춘 것 같아요."),
        ],
    },
    {
        "order_no": "CM-240301-007",
        "customer_name": "한예슬",
        "product_name": "플로우 요가매트",
        "category": ClaimCategory.RETURN,
        "status": ClaimStatus.APPROVED,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "단순 변심으로 반품 원합니다.",
        "messages": [
            ("customer", "색감이 생각보다 달라서 반품 원합니다."),
        ],
    },
    {
        "order_no": "CM-240301-008",
        "customer_name": "송준호",
        "product_name": "클래식 셔츠",
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "색상을 다른 것으로 교환하고 싶습니다.",
        "messages": [
            ("customer", "같은 상품 네이비로 교환 가능한가요?"),
        ],
    },
    {
        "order_no": "CM-240301-009",
        "customer_name": "서가은",
        "product_name": "미니 가습기",
        "category": ClaimCategory.DEFECT,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "전원이 들어오지 않는 불량 같습니다.",
        "messages": [
            ("customer", "전원이 들어오지 않고 냄새가 납니다. 빨리 확인 부탁드려요."),
        ],
    },
    {
        "order_no": "CM-240301-010",
        "customer_name": "임도현",
        "product_name": "실리콘 도시락통",
        "category": ClaimCategory.REFUND,
        "status": ClaimStatus.DONE,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "환불이 완료되었는지 확인 부탁드립니다.",
        "messages": [
            ("customer", "반품 택배는 도착했다고 하는데 카드 취소가 안 보여요."),
        ],
    },
    {
        "order_no": "CM-240301-011",
        "customer_name": "오세린",
        "product_name": "라이트 후드 집업",
        "category": ClaimCategory.OTHER,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "주문 옵션 확인 부탁드립니다.",
        "messages": [
            ("customer", "주문한 옵션이 맞게 들어갔는지 다시 한번 확인 가능할까요?"),
        ],
    },
    {
        "order_no": "CM-240301-012",
        "customer_name": "조현우",
        "product_name": "올데이 백팩",
        "category": ClaimCategory.MISDELIVERY,
        "status": ClaimStatus.REJECTED,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "주문한 제품과 다른 사이즈가 왔습니다.",
        "messages": [
            ("customer", "주문한 제품과 다른 사이즈가 와서 확인 부탁드립니다."),
        ],
    },
]


def seed_demo_data(session: Session) -> None:
    merchant_exists = session.scalar(select(Merchant.id).limit(1))
    if merchant_exists:
        return

    merchant = Merchant(name="알파셀러 운영팀", mall_name="alpha-seller")
    session.add(merchant)
    session.flush()

    policy = Policy(
        merchant_id=merchant.id,
        exchange_window_days=7,
        return_window_days=7,
        return_shipping_fee=3500,
        exchange_shipping_fee=6000,
        refund_rule_text="반품 상품이 물류센터에 도착하고 검수가 완료되면 2영업일 이내 환불 처리합니다.",
        exception_rule_text="오배송 또는 파손/불량이 확인되면 판매자 부담으로 우선 처리합니다.",
    )
    session.add(policy)
    session.flush()

    for item in DEMO_CLAIMS:
        claim = Claim(
            merchant_id=merchant.id,
            order_no=item["order_no"],
            customer_name=item["customer_name"],
            product_name=item["product_name"],
            category=item["category"],
            status=item["status"],
            reason_text=item["reason_text"],
            urgency=item["urgency"],
            ai_label=None,
        )
        session.add(claim)
        session.flush()

        for role, body in item["messages"]:
            session.add(ClaimMessage(claim_id=claim.id, role=role, body=body))

        session.add(
            AuditLog(
                claim_id=claim.id,
                actor="system_seed",
                event_type="claim_seeded",
                payload_json={"status": claim.status.value, "category": claim.category.value},
            )
        )

    session.commit()

