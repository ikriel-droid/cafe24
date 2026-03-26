import type { ReactNode } from "react";
import { ClaimCategory, ClaimStatus, ClaimUrgency } from "@/lib/types";

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
  in_review: "검토중",
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

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "teal" | "accent" | "danger";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

