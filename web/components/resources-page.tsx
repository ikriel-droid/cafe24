"use client";

import Link from "next/link";
import { useAuthSession } from "@/components/app-shell";
import { Badge } from "@/components/ui";

const productDocs = [
  {
    title: "Merchant Onboarding Guide",
    summary: "신규 머천트 베타 시작 전에 확인해야 할 순서와 완료 기준입니다.",
    path: "MERCHANT_ONBOARDING_GUIDE.md",
  },
  {
    title: "Installation Guide",
    summary: "로컬 평가 설치와 호스팅 환경 준비 순서를 정리한 문서입니다.",
    path: "INSTALLATION_GUIDE.md",
  },
  {
    title: "Operations Guide",
    summary: "일일 운영 루틴, 인수인계, 에스컬레이션 기준을 모은 문서입니다.",
    path: "OPERATIONS_GUIDE.md",
  },
  {
    title: "Pricing And Packaging",
    summary: "초기 상품 구간과 가격 설계 기준을 정리한 문서입니다.",
    path: "PRICING_AND_PACKAGING.md",
  },
  {
    title: "Usage Metering Plan",
    summary: "청구와 원가 추적에 필요한 usage event 설계를 정리한 문서입니다.",
    path: "USAGE_METERING_PLAN.md",
  },
  {
    title: "Privacy And Retention Policy",
    summary: "보관, 마스킹, 삭제 원칙을 정리한 문서입니다.",
    path: "PRIVACY_AND_RETENTION_POLICY.md",
  },
  {
    title: "Beta Validation Plan",
    summary: "베타 고객 검증 목표, 성공 지표, 리뷰 주기를 정리한 문서입니다.",
    path: "BETA_VALIDATION_PLAN.md",
  },
];

const inAppLinks = [
  {
    title: "온보딩",
    summary: "베타 시작 전 readiness를 체크리스트로 점검합니다.",
    href: "/onboarding",
  },
  {
    title: "Cafe24 연동",
    summary: "OAuth, webhook, live sync 상태를 확인합니다.",
    href: "/integrations/cafe24",
  },
  {
    title: "정책 설정",
    summary: "교환, 반품, 환불, 예외 정책을 실제 고객사 기준으로 맞춥니다.",
    href: "/settings/policy",
  },
  {
    title: "운영 진단",
    summary: "alert, masking, circuit breaker, request metric을 확인합니다.",
    href: "/admin/diagnostics",
  },
];

export function ResourcesPage() {
  const { session } = useAuthSession();

  if (session.role !== "manager") {
    return <div className="error-banner">런치 킷은 매니저 권한에서만 확인할 수 있습니다.</div>;
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <p className="brand-eyebrow">Optional Polish</p>
          <h2>런치 킷</h2>
          <p>고객사 베타 준비, 내부 운영 정리, 상업화 논의를 한 곳에서 보게 하는 manager용 자료 허브입니다.</p>
        </div>
        <div className="actions">
          <Badge tone="neutral">{productDocs.length} docs</Badge>
          <Badge tone="teal">{inAppLinks.length} in-app links</Badge>
        </div>
      </header>

      <section className="grid cols-3">
        <div className="card stack">
          <h3>현재 머천트</h3>
          <div className="metric-value">{session.merchant.mall_name}</div>
          <p className="metric-caption">{session.email}</p>
        </div>
        <div className="card stack">
          <h3>추천 시작점</h3>
          <div className="metric-value">/onboarding</div>
          <p className="metric-caption">상태 점검과 blocker 정리에 가장 먼저 쓰는 화면</p>
        </div>
        <div className="card stack">
          <h3>런치 패킷</h3>
          <div className="metric-value">{productDocs.length}</div>
          <p className="metric-caption">가격, 프라이버시, 베타 검증까지 포함한 문서 세트</p>
        </div>
      </section>

      <section className="card stack">
        <header className="compact-header page-header">
          <div>
            <h3>바로 가기</h3>
            <p>운영자가 베타 시작 전에 가장 많이 오가는 화면을 묶어뒀습니다.</p>
          </div>
        </header>
        <div className="resource-links">
          {inAppLinks.map((item) => (
            <Link key={item.href} className="resource-link" href={item.href}>
              <strong>{item.title}</strong>
              <span>{item.summary}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card stack">
        <header className="compact-header page-header">
          <div>
            <h3>상업화 문서</h3>
            <p>리포지토리 안에 있는 실제 문서 파일 기준으로 정리했습니다.</p>
          </div>
        </header>
        <div className="resource-links">
          {productDocs.map((doc) => (
            <div key={doc.path} className="resource-link">
              <div className="status-line">
                <strong>{doc.title}</strong>
                <Badge tone="accent">repo doc</Badge>
              </div>
              <span>{doc.summary}</span>
              <code className="path-chip">{doc.path}</code>
            </div>
          ))}
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <h3>권장 베타 시작 순서</h3>
          <ol className="plain-list ordered-list">
            <li>온보딩에서 blocker를 먼저 정리합니다.</li>
            <li>Cafe24 live sync와 webhook health를 확인합니다.</li>
            <li>정책 설정과 reply delivery 방식을 다시 점검합니다.</li>
            <li>운영 진단에서 alert와 masking 상태를 확인합니다.</li>
            <li>가격, usage, privacy 문서를 기준으로 내부 설명 자료를 맞춥니다.</li>
          </ol>
        </div>
        <div className="card stack">
          <h3>주의할 점</h3>
          <ul className="plain-list">
            <li>문서는 준비됐지만 법무 검토와 실제 계약 문안은 별도 승인 절차가 필요합니다.</li>
            <li>가격과 usage 과금은 고객사 인터뷰 없이 바로 확정하지 않는 편이 안전합니다.</li>
            <li>베타 시작 전에는 최소 한 번 실제 claim 처리 시나리오를 운영자가 직접 끝까지 확인해야 합니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
