import type { ReactNode } from "react";
import type { ClaimCategory, ClaimStatus, ClaimUrgency } from "@/lib/types";

export const categoryLabels: Record<ClaimCategory, string> = {
  delivery: "배송",
  cancellation: "취소",
  exchange: "교환",
  return: "반품",
  refund: "환불",
  defect: "파손/불량",
  misdelivery: "오배송",
  other: "기타",
};

export const statusLabels: Record<ClaimStatus, string> = {
  open: "접수",
  in_review: "검토 중",
  approved: "승인",
  rejected: "반려",
  done: "완료",
};

export const urgencyLabels: Record<ClaimUrgency, string> = {
  low: "낮음",
  medium: "중간",
  high: "높음",
};

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatAutomationSourceEvent(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const sourceEventLabels: Record<string, string> = {
    "claim.exchange.requested": "교환 요청 webhook",
    "claim.return.requested": "반품 요청 webhook",
    "claim.refund.requested": "환불 요청 webhook",
    "claim.cancellation.requested": "취소 요청 webhook",
    "order.cancel.requested": "주문 취소 webhook",
    "delivery.delay.reported": "배송 지연 알림 webhook",
    "order.payment.awaiting": "결제 대기 webhook",
    manual_classify: "수동 분류",
    manual_draft_reply: "수동 답변 생성",
  };

  if (sourceEventLabels[value]) {
    return sourceEventLabels[value];
  }

  return value.replace(/[._]/g, " ");
}

export function formatReplyDeliveryChannel(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const channelLabels: Record<string, string> = {
    manual_handoff: "수동 전달",
    webhook: "Webhook 발송",
  };

  return channelLabels[value] ?? value.replace(/_/g, " ");
}

export function formatReplyDeliveryStatus(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const deliveryStatusLabels: Record<string, string> = {
    sent: "발송 성공",
    failed: "발송 실패",
  };

  return deliveryStatusLabels[value] ?? value.replace(/_/g, " ");
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "teal" | "accent" | "danger";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
