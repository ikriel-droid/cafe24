"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuthSession } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { AdminDiagnostics, Cafe24IntegrationStatus, Policy } from "@/lib/types";
import { Badge, formatDate } from "@/components/ui";

type OnboardingSnapshot = {
  integration: Cafe24IntegrationStatus;
  policy: Policy;
  diagnostics: AdminDiagnostics;
};

function toneForReady(ready: boolean) {
  return ready ? "teal" : "accent";
}

export function OnboardingPage() {
  const { session } = useAuthSession();
  const [snapshot, setSnapshot] = useState<OnboardingSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session.role !== "manager") {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function loadSnapshot() {
      setLoading(true);
      setError(null);
      try {
        const [integration, policy, diagnostics] = await Promise.all([
          apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24"),
          apiFetch<Policy>("/api/policy"),
          apiFetch<AdminDiagnostics>("/api/admin/diagnostics"),
        ]);
        if (!cancelled) {
          setSnapshot({ integration, policy, diagnostics });
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "온보딩 상태를 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [session.role]);

  const steps = useMemo(() => {
    if (!snapshot) {
      return [];
    }

    const policyConfigured =
      snapshot.policy.refund_rule_text.trim().length > 0 && snapshot.policy.exception_rule_text.trim().length > 0;
    const observabilityReady =
      snapshot.diagnostics.rate_limit_policies.length > 0 && snapshot.diagnostics.masking_rules.length > 0;
    const liveSyncReady = snapshot.integration.last_sync_result === "live_completed";
    const betaReady =
      snapshot.integration.connected &&
      liveSyncReady &&
      policyConfigured &&
      observabilityReady &&
      snapshot.integration.webhook_endpoint_ready;

    return [
      {
        title: "운영자 계정 확인",
        ready: true,
        detail: `${session.name} (${session.email}) / ${session.merchant.mall_name}`,
        href: "/dashboard",
        action: "운영 화면 열기",
      },
      {
        title: "Cafe24 OAuth 연결",
        ready: snapshot.integration.connected,
        detail: snapshot.integration.connected
          ? `연결 완료 / 최근 sync 결과 ${snapshot.integration.last_sync_result}`
          : "아직 실제 Cafe24 OAuth 연결이 완료되지 않았습니다.",
        href: "/integrations/cafe24",
        action: "Cafe24 연동 설정",
      },
      {
        title: "첫 Live Sync 완료",
        ready: liveSyncReady,
        detail: liveSyncReady
          ? `마지막 sync ${snapshot.integration.last_synced_at ? formatDate(snapshot.integration.last_synced_at) : "-"}`
          : "실제 주문 / 배송 / 클레임 데이터를 한 번 이상 가져와야 합니다.",
        href: "/integrations/cafe24",
        action: "Live Sync 실행",
      },
      {
        title: "운영 정책 입력",
        ready: policyConfigured,
        detail: `교환 ${snapshot.policy.exchange_window_days}일 / 반품 ${snapshot.policy.return_window_days}일 / 반품 배송비 ${snapshot.policy.return_shipping_fee}원`,
        href: "/settings/policy",
        action: "정책 설정 열기",
      },
      {
        title: "운영 진단 준비",
        ready: observabilityReady,
        detail: `rate limit ${snapshot.diagnostics.rate_limit_policies.length}개 / masking rule ${snapshot.diagnostics.masking_rules.length}개`,
        href: "/admin/diagnostics",
        action: "운영 진단 열기",
      },
      {
        title: "베타 시작 가능",
        ready: betaReady,
        detail: betaReady
          ? "베타 고객 검증을 시작할 수 있는 최소 조건이 충족됐습니다."
          : "OAuth, live sync, 정책, 운영 진단 항목을 먼저 채워야 합니다.",
        href: "/integrations/cafe24",
        action: "미완료 항목 정리",
      },
    ];
  }, [session, snapshot]);

  if (session.role !== "manager") {
    return <div className="error-banner">온보딩 화면은 매니저 권한에서만 확인할 수 있습니다.</div>;
  }

  if (loading) {
    return <div className="loading-state">온보딩 준비 상태를 불러오는 중입니다.</div>;
  }

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (!snapshot) {
    return <div className="error-banner">온보딩 데이터를 불러오지 못했습니다.</div>;
  }

  const completedCount = steps.filter((step) => step.ready).length;

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <p className="brand-eyebrow">Commercial</p>
          <h2>머천트 온보딩</h2>
          <p>실제 고객사 베타 시작 전에 확인해야 하는 운영 준비 항목을 한 화면에 모았습니다.</p>
        </div>
        <div className="actions">
          <Badge tone="neutral">
            {completedCount} / {steps.length} 완료
          </Badge>
          <Badge tone={completedCount === steps.length ? "teal" : "accent"}>
            {completedCount === steps.length ? "베타 시작 가능" : "준비 필요"}
          </Badge>
        </div>
      </header>

      <section className="grid cols-3">
        <div className="card stack">
          <h3>현재 머천트</h3>
          <div className="metric-value">{session.merchant.mall_name}</div>
          <p className="metric-caption">{session.email}</p>
        </div>
        <div className="card stack">
          <h3>Cafe24 상태</h3>
          <div className="metric-value">{snapshot.integration.connected ? "연결됨" : "대기"}</div>
          <p className="metric-caption">{snapshot.integration.health_title}</p>
        </div>
        <div className="card stack">
          <h3>운영 진단</h3>
          <div className="metric-value">{snapshot.diagnostics.recent_alerts.length}</div>
          <p className="metric-caption">최근 alert / 5xx는 운영 진단 페이지에서 확인</p>
        </div>
      </section>

      <section className="card stack">
        <header className="compact-header page-header">
          <div>
            <h3>온보딩 체크리스트</h3>
            <p>각 항목은 바로 연결되는 운영 페이지가 있습니다.</p>
          </div>
        </header>
        <div className="mini-activity-list">
          {steps.map((step) => (
            <div key={step.title} className="mini-activity-item">
              <div className="status-line">
                <strong>{step.title}</strong>
                <Badge tone={toneForReady(step.ready)}>{step.ready ? "완료" : "미완료"}</Badge>
              </div>
              <p>{step.detail}</p>
              <div className="actions">
                <Link className="button secondary" href={step.href}>
                  {step.action}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <h3>베타 시작 조건</h3>
          <ul className="plain-list">
            <li>Cafe24 OAuth 연결 완료</li>
            <li>첫 Live Sync 완료</li>
            <li>환불 / 예외 정책 입력 완료</li>
            <li>운영 진단 페이지에서 rate limit / masking 확인</li>
            <li>manager 계정으로 운영자 인수인계 가능</li>
          </ul>
        </div>

        <div className="card stack">
          <h3>추천 다음 액션</h3>
          <div className="resource-links">
            <Link className="resource-link" href="/integrations/cafe24">
              <strong>Cafe24 연동</strong>
              <span>OAuth, webhook, live sync 상태를 먼저 고정합니다.</span>
            </Link>
            <Link className="resource-link" href="/settings/policy">
              <strong>정책 설정</strong>
              <span>교환 / 반품 / 환불 정책 문구를 베타 고객사 기준으로 맞춥니다.</span>
            </Link>
            <Link className="resource-link" href="/admin/diagnostics">
              <strong>운영 진단</strong>
              <span>알림, masking, circuit breaker, request metrics를 최종 확인합니다.</span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
