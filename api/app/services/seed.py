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
        "product_name": "에어핏 데님 팬츠",
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "사이즈가 맞지 않아 교환 원합니다.",
        "messages": [
            ("customer", "사이즈가 맞지 않아 교환 원합니다."),
            ("operator", "원하시는 사이즈를 알려주시면 교환 가능 여부를 바로 확인해드리겠습니다."),
        ],
    },
    {
        "order_no": "CM-240301-002",
        "customer_name": "박서준",
        "product_name": "모던 세라믹 머그컵 2P",
        "category": ClaimCategory.DEFECT,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "상품이 파손되어 도착했습니다.",
        "messages": [
            ("customer", "박스를 열어보니 컵 손잡이가 깨져 있었습니다."),
            ("customer", "상품이 파손되어 도착했습니다."),
        ],
    },
    {
        "order_no": "CM-240301-003",
        "customer_name": "이하늘",
        "product_name": "코튼 릴렉스 셔츠",
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
        "product_name": "하프문 니트 가디건",
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
        "customer_name": "오서윤",
        "product_name": "데일리 워크백",
        "category": ClaimCategory.DELIVERY,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "배송은 언제 오나요?",
        "messages": [
            ("customer", "송장번호는 있는데 배송이 멈춘 것 같아요."),
        ],
    },
    {
        "order_no": "CM-240301-007",
        "customer_name": "신예림",
        "product_name": "플로우 요가 매트",
        "category": ClaimCategory.RETURN,
        "status": ClaimStatus.APPROVED,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "단순 변심으로 반품 원합니다.",
        "messages": [
            ("customer", "생각보다 색감이 진해서 반품 원합니다."),
        ],
    },
    {
        "order_no": "CM-240301-008",
        "customer_name": "장하준",
        "product_name": "리브드 니트",
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "색상을 다른 것으로 교환하고 싶습니다.",
        "messages": [
            ("customer", "같은 상품 다른 컬러로 교환 가능한가요?"),
        ],
    },
    {
        "order_no": "CM-240301-009",
        "customer_name": "송가은",
        "product_name": "미니 가습기",
        "category": ClaimCategory.DEFECT,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "전원이 들어오지 않는 불량 같습니다.",
        "messages": [
            ("customer", "전원이 들어오지 않고 작동이 안 됩니다. 빨리 확인 부탁드려요."),
        ],
    },
    {
        "order_no": "CM-240301-010",
        "customer_name": "한도윤",
        "product_name": "실리콘 이유식 용기",
        "category": ClaimCategory.REFUND,
        "status": ClaimStatus.DONE,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "환불이 완료되었는지 확인 부탁드립니다.",
        "messages": [
            ("customer", "반품 완료라고 들었는데 카드 취소가 아직 안 보여요."),
        ],
    },
    {
        "order_no": "CM-240301-011",
        "customer_name": "임세린",
        "product_name": "와이드 진청 팬츠",
        "category": ClaimCategory.OTHER,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "주문 옵션 확인 부탁드립니다.",
        "messages": [
            ("customer", "주문한 옵션이 맞게 들어가는지 다시 한 번 확인 가능할까요?"),
        ],
    },
    {
        "order_no": "CM-240301-012",
        "customer_name": "조현우",
        "product_name": "스웨트 백팩",
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
        refund_rule_text="반품 상품이 물류센터에 입고되고 검수가 완료되면 2영업일 이내 환불 처리됩니다.",
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
