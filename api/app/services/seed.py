from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AuditLog,
    Claim,
    ClaimCategory,
    ClaimMessage,
    ClaimStatus,
    ClaimUrgency,
    Merchant,
    MerchantDataOrigin,
    OperatorRole,
    OperatorUser,
    Policy,
)


ALPHA_CLAIMS = [
    {
        "order_no": "CM-240301-001",
        "customer_name": "김민지",
        "product_name": "레이어드 카디건",
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
        "messages": [("customer", "반품은 보냈는데 환불은 언제 처리되나요?")],
    },
    {
        "order_no": "CM-240301-004",
        "customer_name": "정도윤",
        "product_name": "루미 텀블러 500ml",
        "category": ClaimCategory.MISDELIVERY,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "오배송된 것 같습니다.",
        "messages": [("customer", "주문한 색상과 다른 상품이 왔어요.")],
    },
    {
        "order_no": "CM-240301-005",
        "customer_name": "최예린",
        "product_name": "소프트 울 가디건",
        "category": ClaimCategory.CANCELLATION,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "배송 전이면 주문 취소 부탁드립니다.",
        "messages": [("customer", "색상을 잘못 주문해서 배송 전이면 주문 취소 부탁드립니다.")],
    },
    {
        "order_no": "CM-240301-006",
        "customer_name": "강서연",
        "product_name": "데일리 캔버스백",
        "category": ClaimCategory.DELIVERY,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "배송은 언제 오나요?",
        "messages": [("customer", "운송장번호는 있는데 배송이 멈춘 것 같아요.")],
    },
    {
        "order_no": "CM-240301-007",
        "customer_name": "유예림",
        "product_name": "플로럴 욕실 매트",
        "category": ClaimCategory.RETURN,
        "status": ClaimStatus.APPROVED,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "단순 변심으로 반품 원합니다.",
        "messages": [("customer", "생각보다 색감이 진해서 반품 원합니다.")],
    },
    {
        "order_no": "CM-240301-008",
        "customer_name": "노하준",
        "product_name": "리브 니트",
        "category": ClaimCategory.EXCHANGE,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "색상을 다른 것으로 교환하고 싶습니다.",
        "messages": [("customer", "같은 상품 다른 컬러로 교환 가능한가요?")],
    },
    {
        "order_no": "CM-240301-009",
        "customer_name": "송은지",
        "product_name": "미니 가습기",
        "category": ClaimCategory.DEFECT,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.HIGH,
        "reason_text": "전원이 들어오지 않는 불량 같습니다.",
        "messages": [("customer", "전원이 들어오지 않고 작동하지 않습니다. 빨리 확인 부탁드려요.")],
    },
    {
        "order_no": "CM-240301-010",
        "customer_name": "신도윤",
        "product_name": "실리콘 이유식 용기",
        "category": ClaimCategory.REFUND,
        "status": ClaimStatus.DONE,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "환불이 완료되었는지 확인 부탁드립니다.",
        "messages": [("customer", "반품 완료라고 떴는데 카드 취소가 아직 안 보여요.")],
    },
    {
        "order_no": "CM-240301-011",
        "customer_name": "안세리",
        "product_name": "다크브라운 진청 셔츠",
        "category": ClaimCategory.OTHER,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.LOW,
        "reason_text": "주문 옵션 확인 부탁드립니다.",
        "messages": [("customer", "주문한 옵션이 맞게 들어갔는지 다시 한 번 확인 가능할까요?")],
    },
    {
        "order_no": "CM-240301-012",
        "customer_name": "조현우",
        "product_name": "스웨이드 백팩",
        "category": ClaimCategory.MISDELIVERY,
        "status": ClaimStatus.REJECTED,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "주문한 제품과 다른 사이즈가 왔습니다.",
        "messages": [("customer", "주문한 제품과 다른 사이즈가 와서 확인 부탁드립니다.")],
    },
]


BETA_CLAIMS = [
    {
        "order_no": "BT-240301-001",
        "customer_name": "한지우",
        "product_name": "린넨 와이드 팬츠",
        "category": ClaimCategory.RETURN,
        "status": ClaimStatus.OPEN,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "핏이 생각보다 커서 반품 원합니다.",
        "messages": [("customer", "핏이 생각보다 커서 반품 원합니다.")],
    },
    {
        "order_no": "BT-240301-002",
        "customer_name": "문서윤",
        "product_name": "데님 오버셔츠",
        "category": ClaimCategory.DELIVERY,
        "status": ClaimStatus.IN_REVIEW,
        "urgency": ClaimUrgency.MEDIUM,
        "reason_text": "배송 지연 문의드립니다.",
        "messages": [("customer", "배송 지연 문의드립니다.")],
    },
]


def seed_claims(session: Session, merchant: Merchant, claims: list[dict[str, object]]) -> None:
    for item in claims:
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


def seed_operators(session: Session, merchant: Merchant, operators: list[dict[str, str]]) -> None:
    for operator in operators:
        session.add(
            OperatorUser(
                merchant_id=merchant.id,
                email=operator["email"].lower(),
                name=operator["name"],
                role=OperatorRole(operator["role"]),
                password_hash=hash_password(operator["password"]),
                is_active=True,
            )
        )


def seed_demo_data(session: Session) -> None:
    demo_merchant_exists = session.scalar(
        select(Merchant.id).where(Merchant.data_origin == MerchantDataOrigin.DEMO).limit(1)
    )
    if demo_merchant_exists:
        return

    alpha_merchant = Merchant(
        name="알파스토어 운영팀",
        mall_name="alpha-seller",
        data_origin=MerchantDataOrigin.DEMO,
    )
    session.add(alpha_merchant)
    session.flush()

    session.add(
        Policy(
            merchant_id=alpha_merchant.id,
            exchange_window_days=7,
            return_window_days=7,
            return_shipping_fee=3500,
            exchange_shipping_fee=6000,
            refund_rule_text="반품 상품이 물류센터에 입고되고 검수가 완료되면 2영업일 이내 환불 처리합니다.",
            exception_rule_text="오배송 또는 파손/불량이 확인되면 판매자 부담으로 우선 처리합니다.",
        )
    )
    seed_claims(session, alpha_merchant, ALPHA_CLAIMS)
    seed_operators(
        session,
        alpha_merchant,
        [
            {
                "email": "manager@alpha-seller.local",
                "name": "알파 매니저",
                "role": "manager",
                "password": "demo1234",
            },
            {
                "email": "agent@alpha-seller.local",
                "name": "알파 상담원",
                "role": "agent",
                "password": "demo1234",
            },
            {
                "email": "viewer@alpha-seller.local",
                "name": "알파 뷰어",
                "role": "viewer",
                "password": "demo1234",
            },
        ],
    )

    beta_merchant = Merchant(
        name="베타셀렉트 운영팀",
        mall_name="beta-select",
        data_origin=MerchantDataOrigin.DEMO,
    )
    session.add(beta_merchant)
    session.flush()

    session.add(
        Policy(
            merchant_id=beta_merchant.id,
            exchange_window_days=5,
            return_window_days=5,
            return_shipping_fee=3000,
            exchange_shipping_fee=5500,
            refund_rule_text="베타셀렉트는 검수 완료 후 1영업일 내 환불을 진행합니다.",
            exception_rule_text="오배송 및 초기 불량은 판매자 부담으로 즉시 처리합니다.",
        )
    )
    seed_claims(session, beta_merchant, BETA_CLAIMS)
    seed_operators(
        session,
        beta_merchant,
        [
            {
                "email": "manager@beta-select.local",
                "name": "베타 매니저",
                "role": "manager",
                "password": "demo1234",
            }
        ],
    )

    session.commit()
