"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Cafe24IntegrationStatus, Claim, DashboardSummary, Policy } from "@/lib/types";
import { Badge, categoryLabels, formatDate, statusLabels, urgencyLabels } from "@/components/ui";

const urgencyRank: Record<Claim["urgency"], number> = {
  high: 3,
  medium: 2,
  low: 1,
};

function toneForUrgency(urgency: Claim["urgency"]) {
  if (urgency === "high") return "danger";
  if (urgency === "medium") return "accent";
  return "teal";
}

function toneForHealthStatus(status: string) {
  if (status === "healthy") return "teal";
  if (status === "setup_needed") return "accent";
  if (status === "attention") return "danger";
  return "neutral";
}

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    setLoading(true);
    setError(null);

    try {
      const [summaryResult, claimsResult, policyResult] = await Promise.all([
        apiFetch<DashboardSummary>("/api/dashboard/summary"),
        apiFetch<Claim[]>("/api/claims"),
        apiFetch<Policy>("/api/policy"),
      ]);

      setSummary(summaryResult);
      setClaims(claimsResult);
      setPolicy(policyResult);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "대시보드 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const queueClaims = useMemo(() => {
    return [...claims]
      .filter((claim) => claim.status === "open" || claim.status === "in_review")
      .sort((left, right) => {
        const urgencyDifference = urgencyRank[right.urgency] - urgencyRank[left.urgency];
        if (urgencyDifference !== 0) {
          return urgencyDifference;
        }

        return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
      })
      .slice(0, 5);
  }, [claims]);

  async function handleRunMockSync() {
    setWorking(true);
    setError(null);

    try {
      await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/mock-sync", { method: "POST" });
      await loadDashboard();
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "Cafe24 Mock Sync 실행에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <h2>운영 대시보드</h2>
          <p>오늘 처리할 클레임, 정책 요약, Cafe24 상태를 한 번에 보는 시작 화면입니다.</p>
        </div>
        <div className="actions">
          <Link href="/inbox?sort=priority" className="button">
            우선순위 인박스
          </Link>
          <Link href="/settings/policy" className="button secondary">
            정책 확인
          </Link>
        </div>
      </header>

      {loading ? <div className="loading-state">대시보드를 준비하는 중입니다.</div> : null}
      {error ? <div className="error-state">{error}</div> : null}

      {summary ? (
        <>
          <section className="grid cols-3">
            <div className="card">
              <p>전체 클레임</p>
              <div className="metric-value">{summary.total_claims}</div>
              <p className="metric-caption">데모 데이터 기준 현재 누적 건수</p>
            </div>
            <div className="card">
              <p>바로 처리할 건</p>
              <div className="metric-value">{summary.open_claims + summary.in_review_claims}</div>
              <p className="metric-caption">접수 + 검토 중 합계</p>
            </div>
            <div className="card">
              <p>높은 긴급도</p>
              <div className="metric-value">{summary.high_urgency_claims}</div>
              <p className="metric-caption">즉시 확인이 필요한 문의</p>
            </div>
            {summary.cafe24 ? (
              <div className="card">
                <p>Cafe24 Health</p>
                <div className="actions">
                  <Badge tone={toneForHealthStatus(summary.cafe24.health_status)}>{summary.cafe24.health_title}</Badge>
                </div>
                <p className="metric-caption">{summary.cafe24.health_detail}</p>
                <p className="metric-caption">
                  {summary.cafe24.last_synced_at ? formatDate(summary.cafe24.last_synced_at) : "아직 sync 없음"} / pending webhook{" "}
                  {summary.cafe24.pending_webhooks}
                </p>
                <div className="actions">
                  {summary.cafe24.next_action_type === "mock_sync" ? (
                    <button className="button secondary" type="button" onClick={handleRunMockSync} disabled={working}>
                      {summary.cafe24.next_action_label}
                    </button>
                  ) : summary.cafe24.next_action_href ? (
                    <Link href={summary.cafe24.next_action_href} className="button secondary">
                      {summary.cafe24.next_action_label}
                    </Link>
                  ) : null}
                </div>
              </div>
            ) : null}
          </section>

          <section className="grid cols-2">
            <div className="card stack">
              <div>
                <h3>우선 처리 큐</h3>
                <p>긴급도와 접수 상태를 기준으로 지금 먼저 볼 문의를 모았습니다.</p>
              </div>
              {queueClaims.length > 0 ? (
                <div className="timeline">
                  {queueClaims.map((claim) => (
                    <Link key={claim.id} href={`/claims/${claim.id}`} className="timeline-item">
                      <div className="actions">
                        <strong>
                          {claim.order_no} / {claim.customer_name}
                        </strong>
                        <Badge tone={toneForUrgency(claim.urgency)}>{urgencyLabels[claim.urgency]}</Badge>
                      </div>
                      <p>{claim.product_name}</p>
                      <div className="actions">
                        <Badge tone="neutral">{categoryLabels[claim.category]}</Badge>
                        <Badge tone="teal">{statusLabels[claim.status]}</Badge>
                      </div>
                      <p className="muted">{formatDate(claim.created_at)}</p>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="empty-state inline-state">현재 바로 처리할 클레임이 없습니다.</div>
              )}
            </div>

            <div className="card stack">
              <div>
                <h3>카테고리 분포</h3>
                <p>어떤 유형의 문의가 몰려 있는지 빠르게 확인할 수 있습니다.</p>
              </div>
              <div className="category-summary">
                {Object.entries(summary.by_category).map(([key, count]) => (
                  <Badge key={key} tone="neutral">
                    {categoryLabels[key as keyof typeof categoryLabels] ?? key} {count}
                  </Badge>
                ))}
              </div>
              <div className="summary-list">
                <div className="summary-row">
                  <span className="muted">승인</span>
                  <strong>{summary.approved_claims}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">반려</span>
                  <strong>{summary.rejected_claims}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">완료</span>
                  <strong>{summary.done_claims}</strong>
                </div>
              </div>
            </div>
          </section>

          <section className="grid cols-2">
            <div className="card stack">
              <div>
                <h3>운영 정책 스냅샷</h3>
                <p>답변 초안 생성에 반영되는 현재 기본 정책입니다.</p>
              </div>
              {policy ? (
                <>
                  <div className="summary-list">
                    <div className="summary-row">
                      <span className="muted">교환 가능 기간</span>
                      <strong>{policy.exchange_window_days}일</strong>
                    </div>
                    <div className="summary-row">
                      <span className="muted">반품 가능 기간</span>
                      <strong>{policy.return_window_days}일</strong>
                    </div>
                    <div className="summary-row">
                      <span className="muted">교환 배송비</span>
                      <strong>{policy.exchange_shipping_fee.toLocaleString("ko-KR")}원</strong>
                    </div>
                    <div className="summary-row">
                      <span className="muted">반품 배송비</span>
                      <strong>{policy.return_shipping_fee.toLocaleString("ko-KR")}원</strong>
                    </div>
                  </div>
                  <div className="tile-row">
                    <strong>환불 정책</strong>
                    <p>{policy.refund_rule_text}</p>
                  </div>
                </>
              ) : (
                <div className="empty-state inline-state">정책 정보를 아직 불러오지 못했습니다.</div>
              )}
            </div>

            <div className="card stack">
              <div>
                <h3>바로 가기</h3>
                <p>운영자가 자주 여는 작업으로 바로 이동합니다.</p>
              </div>
              <div className="resource-links">
                <Link href="/inbox?sort=priority" className="resource-link">
                  <strong>우선순위 인박스 열기</strong>
                  <p>긴급도와 상태 기준으로 바로 처리할 문의를 확인합니다.</p>
                </Link>
                <Link href="/integrations/cafe24" className="resource-link">
                  <strong>Cafe24 콘솔 열기</strong>
                  <p>Mock Sync, OAuth placeholder, activity 상태를 점검합니다.</p>
                </Link>
                <Link href="/settings/policy" className="resource-link">
                  <strong>정책 수정</strong>
                  <p>교환/반품/환불 정책을 조정해 답변 초안을 매장 정책에 맞춥니다.</p>
                </Link>
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
