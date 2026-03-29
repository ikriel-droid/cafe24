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
  const [automationWorkingId, setAutomationWorkingId] = useState<number | null>(null);
  const [followUpWorkingId, setFollowUpWorkingId] = useState<number | null>(null);
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

  const automationQueue = useMemo(() => {
    return claims
      .filter(
        (claim) =>
          (claim.status === "open" || claim.status === "in_review") &&
          claim.automation.auto_triaged &&
          claim.automation.reply_ready &&
          !claim.automation.reply_sent,
      )
      .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime())
      .slice(0, 4);
  }, [claims]);

  const followUpQueue = useMemo(() => {
    return claims
      .filter((claim) => claim.automation.follow_up_needed)
      .sort((left, right) => {
        const rightTime = right.automation.reply_sent_at ? new Date(right.automation.reply_sent_at).getTime() : 0;
        const leftTime = left.automation.reply_sent_at ? new Date(left.automation.reply_sent_at).getTime() : 0;
        return rightTime - leftTime;
      })
      .slice(0, 4);
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

  async function handleQuickSendDraft(claimId: number) {
    setAutomationWorkingId(claimId);
    setError(null);

    try {
      await apiFetch<Claim>(`/api/claims/${claimId}/send-reply`, {
        method: "POST",
        body: JSON.stringify({ actor: "dashboard_operator", mark_done: true }),
      });
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "자동화 큐 발송 처리에 실패했습니다.");
    } finally {
      setAutomationWorkingId(null);
    }
  }

  async function handleQuickFollowUpDone(claimId: number) {
    setFollowUpWorkingId(claimId);
    setError(null);

    try {
      await apiFetch<Claim>(`/api/claims/${claimId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "done", actor: "dashboard_operator" }),
      });
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "후속 확인 완료 처리에 실패했습니다.");
    } finally {
      setFollowUpWorkingId(null);
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <h2>운영 대시보드</h2>
          <p>지금 바로 처리할 건, 자동화 큐, 답변 후 후속 확인까지 한 번에 보는 시작 화면입니다.</p>
        </div>
        <div className="actions">
          <Link href="/inbox?sort=priority" className="button">
            우선순위 인박스
          </Link>
          <Link href="/settings/policy" className="button secondary">
            정책 설정
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
              <p className="metric-caption">현재 추적 중인 전체 클레임 수입니다.</p>
            </div>
            <div className="card">
              <p>바로 처리할 건</p>
              <div className="metric-value">{summary.open_claims + summary.in_review_claims}</div>
              <p className="metric-caption">접수와 검토 중 상태를 합친 운영 큐입니다.</p>
            </div>
            <div className="card">
              <p>높은 긴급도</p>
              <div className="metric-value">{summary.high_urgency_claims}</div>
              <p className="metric-caption">우선 확인이 필요한 고긴급 문의입니다.</p>
            </div>
            <div className="card">
              <p>자동 triage 완료</p>
              <div className="metric-value">{summary.auto_triaged_claims}</div>
              <p className="metric-caption">Cafe24 webhook 기준 자동 분류가 끝난 건입니다.</p>
              <div className="actions">
                <Link href="/inbox?sort=priority&auto_triaged=true" className="button ghost">
                  자동 분류 보기
                </Link>
              </div>
            </div>
            <div className="card">
              <p>답변 초안 준비</p>
              <div className="metric-value">{summary.reply_ready_claims}</div>
              <p className="metric-caption">검토 후 바로 발송할 수 있는 초안이 있습니다.</p>
              <div className="actions">
                <Link href="/inbox?sort=priority&reply_ready=true" className="button ghost">
                  초안 준비 보기
                </Link>
              </div>
            </div>
            <div className="card">
              <p>답변 발송 완료</p>
              <div className="metric-value">{summary.reply_sent_claims}</div>
              <p className="metric-caption">답변 발송 로그까지 기록된 클레임입니다.</p>
              <div className="actions">
                <Link href="/inbox?sort=priority&reply_sent=true" className="button ghost">
                  발송 완료 보기
                </Link>
              </div>
            </div>
            <div className="card">
              <p>후속 확인 필요</p>
              <div className="metric-value">{summary.follow_up_needed_claims}</div>
              <p className="metric-caption">답변은 보냈지만 아직 닫히지 않아 재확인이 필요한 건입니다.</p>
              <div className="actions">
                <Link href="/inbox?sort=priority&follow_up_needed=true" className="button ghost">
                  후속 확인 보기
                </Link>
              </div>
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
                <p>긴급도와 현재 상태 기준으로 먼저 봐야 할 클레임입니다.</p>
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
                <div className="empty-state inline-state">지금 바로 처리할 클레임이 없습니다.</div>
              )}
            </div>

            <div className="card stack">
              <div>
                <h3>자동화 큐</h3>
                <p>자동 분류와 초안이 준비된 건을 여기서 바로 발송까지 이어갈 수 있습니다.</p>
              </div>
              {automationQueue.length > 0 ? (
                <div className="timeline">
                  {automationQueue.map((claim) => (
                    <div key={claim.id} className="timeline-item">
                      <div className="actions">
                        <strong>
                          {claim.order_no} / {claim.customer_name}
                        </strong>
                        <Badge tone="accent">자동 분류</Badge>
                      </div>
                      <p>{claim.product_name}</p>
                      <div className="actions">
                        <Badge tone="teal">답변 초안 준비</Badge>
                        <Badge tone="neutral">{categoryLabels[claim.category]}</Badge>
                      </div>
                      <p className="muted">
                        분류 {Math.round((claim.automation.classification_confidence ?? 0) * 100)}% / 답변{" "}
                        {Math.round((claim.automation.draft_reply_confidence ?? 0) * 100)}%
                      </p>
                      <div className="actions">
                        <Link href={`/claims/${claim.id}`} className="button ghost">
                          Open Claim
                        </Link>
                        <button
                          className="button"
                          type="button"
                          onClick={() => handleQuickSendDraft(claim.id)}
                          disabled={automationWorkingId === claim.id}
                        >
                          {automationWorkingId === claim.id ? "처리 중..." : "Send Draft + Done"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state inline-state">지금 자동화 큐에 남아 있는 클레임이 없습니다.</div>
              )}
            </div>
          </section>

          <section className="grid cols-2">
            <div className="card stack">
              <div>
                <h3>발송 후 후속 확인</h3>
                <p>답변은 보냈지만 아직 완료 처리되지 않아 다시 확인할 건입니다.</p>
              </div>
              {followUpQueue.length > 0 ? (
                <div className="timeline">
                  {followUpQueue.map((claim) => (
                    <div key={claim.id} className="timeline-item">
                      <div className="actions">
                        <strong>
                          {claim.order_no} / {claim.customer_name}
                        </strong>
                        <Badge tone="danger">후속 확인 필요</Badge>
                      </div>
                      <p>{claim.product_name}</p>
                      <div className="actions">
                        <Badge tone="teal">{statusLabels[claim.status]}</Badge>
                        <span className="muted">
                          {claim.automation.reply_sent_at ? formatDate(claim.automation.reply_sent_at) : "-"} /{" "}
                          {claim.automation.reply_sent_by ?? "-"}
                        </span>
                      </div>
                      <div className="actions">
                        <Link href={`/claims/${claim.id}`} className="button ghost">
                          Open Claim
                        </Link>
                        <button
                          className="button"
                          type="button"
                          onClick={() => handleQuickFollowUpDone(claim.id)}
                          disabled={followUpWorkingId === claim.id}
                        >
                          {followUpWorkingId === claim.id ? "처리 중..." : "Follow-up Done"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state inline-state">지금 후속 확인이 필요한 클레임이 없습니다.</div>
              )}
            </div>

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
          </section>

          <section className="card stack">
            <div>
              <h3>바로 가기</h3>
              <p>운영자가 자주 여는 화면을 빠르게 열 수 있게 묶었습니다.</p>
            </div>
            <div className="resource-links">
              <Link href="/inbox?sort=priority" className="resource-link">
                <strong>우선순위 인박스 열기</strong>
                <p>긴급도와 상태 기준으로 먼저 처리할 문의를 확인합니다.</p>
              </Link>
              <Link href="/inbox?sort=priority&auto_triaged=true&reply_ready=true" className="resource-link">
                <strong>자동화 큐 열기</strong>
                <p>자동 분류와 초안이 준비됐지만 아직 발송 전인 건만 모아 봅니다.</p>
              </Link>
              <Link href="/inbox?sort=priority&follow_up_needed=true" className="resource-link">
                <strong>후속 확인 큐 열기</strong>
                <p>답변 발송 후 완료 처리되지 않은 건만 다시 확인합니다.</p>
              </Link>
              <Link href="/inbox?sort=priority&reply_sent=true" className="resource-link">
                <strong>발송 완료 인박스 열기</strong>
                <p>답변 발송 기록이 남은 클레임 전체를 다시 점검합니다.</p>
              </Link>
              <Link href="/settings/policy" className="resource-link">
                <strong>정책 설정</strong>
                <p>교환, 반품, 환불 정책을 수정해서 답변 초안을 매장 정책에 맞춥니다.</p>
              </Link>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
