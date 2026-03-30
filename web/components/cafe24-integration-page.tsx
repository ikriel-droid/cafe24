"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Cafe24IntegrationStatus } from "@/lib/types";
import { Badge, formatDate } from "@/components/ui";

function toneForResult(status: Cafe24IntegrationStatus | null) {
  if (!status) {
    return "neutral";
  }

  if (status.last_sync_result === "mock_completed" || status.last_sync_result === "live_completed") {
    return "teal";
  }

  return "accent";
}

function toneForHealthStatus(status: string) {
  if (status === "healthy") return "teal";
  if (status === "setup_needed") return "accent";
  if (status === "attention") return "danger";
  return "neutral";
}

function toneForJobStatus(status: string) {
  if (status === "succeeded") return "teal";
  if (status === "queued" || status === "running" || status === "retry_scheduled") return "accent";
  if (status === "dead_letter") return "danger";
  return "neutral";
}

function buildCallbackSimulationHref(merchantId: number, mode: "success" | "error") {
  const params = new URLSearchParams({
    state: `claimmate-local-${merchantId}`,
  });

  if (mode === "success") {
    params.set("code", "demo-code");
  } else {
    params.set("error", "access_denied");
  }

  return `/api/integrations/cafe24/callback?${params.toString()}`;
}

export function Cafe24IntegrationPage() {
  const [status, setStatus] = useState<Cafe24IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activityFilter, setActivityFilter] = useState<"all" | "mock_sync" | "oauth_callback" | "mock_webhook">(
    "all"
  );
  const [webhookType, setWebhookType] = useState("claim.return.requested");
  const [webhookOrderNo, setWebhookOrderNo] = useState("");

  const webhookOptions = [
    { value: "claim.return.requested", label: "반품 요청" },
    { value: "claim.exchange.requested", label: "교환 요청" },
    { value: "order.cancel.requested", label: "주문 취소 요청" },
    { value: "delivery.delay.reported", label: "배송 지연 알림" },
  ];

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthResult = params.get("oauth_result");
    const oauthMessage = params.get("oauth_message");
    const oauthState = params.get("oauth_state");

    if (!oauthResult || !oauthMessage) {
      return;
    }

    const message = oauthState ? `${oauthMessage} (state: ${oauthState})` : oauthMessage;
    if (oauthResult === "error" || oauthResult === "missing_code") {
      setError(message);
      setNotice(null);
    } else {
      setNotice(message);
      setError(null);
    }

    const cleanedUrl = `${window.location.pathname}${window.location.hash}`;
    window.history.replaceState(null, "", cleanedUrl);
  }, []);

  async function loadStatus() {
    setLoading(true);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24");
      setStatus(data);
    } catch (loadError) {
      setError((current) => current ?? (loadError instanceof Error ? loadError.message : "Cafe24 상태를 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  const hasActiveJobs = Boolean(status && (status.queued_jobs > 0 || status.running_jobs > 0 || status.scheduled_jobs > 0));

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }

    const timer = window.setTimeout(() => {
      void loadStatus();
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [hasActiveJobs, status?.queued_jobs, status?.running_jobs, status?.scheduled_jobs]);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const filteredEvents =
    status?.recent_events.filter((event) => activityFilter === "all" || event.event_type === activityFilter) ?? [];

  async function handleMockSync() {
    setWorking(true);
    setError(null);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/mock-sync", {
        method: "POST",
      });
      setStatus(data);
      setNotice("Cafe24 Mock Sync를 실행했습니다.");
    } catch (syncError) {
      setNotice(null);
      setError(syncError instanceof Error ? syncError.message : "Cafe24 Mock Sync 실행에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  async function handleLiveSync() {
    setWorking(true);
    setError(null);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/live-sync", {
        method: "POST",
      });
      setStatus(data);
      setNotice("Cafe24 Live Sync를 실행했습니다.");
    } catch (syncError) {
      setNotice(null);
      setError(syncError instanceof Error ? syncError.message : "Cafe24 Live Sync 실행에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  async function handleRetryFailedWebhooks() {
    setWorking(true);
    setError(null);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/webhook/live/retry-failed", {
        method: "POST",
      });
      setStatus(data);
      setNotice("실패한 Cafe24 webhook 재처리를 실행했습니다.");
    } catch (retryError) {
      setNotice(null);
      setError(retryError instanceof Error ? retryError.message : "Cafe24 webhook 재처리에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  async function handleRunWorkerNow() {
    setWorking(true);
    setError(null);

    try {
      await apiFetch<{ processed_job_ids: number[] }>("/api/jobs/process-pending", {
        method: "POST",
      });
      await loadStatus();
      setNotice("Background worker를 즉시 한 번 실행했습니다.");
    } catch (workerError) {
      setNotice(null);
      setError(workerError instanceof Error ? workerError.message : "Background worker 실행에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  async function handleClearActivity() {
    setWorking(true);
    setError(null);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/clear-activity", {
        method: "POST",
      });
      setStatus(data);
      setNotice("Cafe24 activity 이력을 비웠습니다.");
    } catch (clearError) {
      setNotice(null);
      setError(clearError instanceof Error ? clearError.message : "Cafe24 activity 초기화에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  async function handleMockWebhook() {
    setWorking(true);
    setError(null);

    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/mock-webhook", {
        method: "POST",
        body: JSON.stringify({
          event_type: webhookType,
          order_no: webhookOrderNo.trim() || null,
        }),
      });
      setStatus(data);
      setNotice("Cafe24 mock webhook을 기록했습니다.");
      setWebhookOrderNo("");
    } catch (webhookError) {
      setNotice(null);
      setError(webhookError instanceof Error ? webhookError.message : "Cafe24 mock webhook 기록에 실패했습니다.");
    } finally {
      setWorking(false);
    }
  }

  function renderNextAction() {
    if (!status) {
      return null;
    }

    if (status.next_action_type === "mock_sync") {
      return (
        <button className="button" onClick={handleMockSync} disabled={working}>
          {status.next_action_label}
        </button>
      );
    }

    if (status.next_action_type === "live_sync") {
      return (
        <button className="button" onClick={handleLiveSync} disabled={working}>
          {status.next_action_label}
        </button>
      );
    }

    if (status.next_action_type === "retry_failed_webhooks") {
      return (
        <button className="button" onClick={handleRetryFailedWebhooks} disabled={working}>
          {status.next_action_label}
        </button>
      );
    }

    if (status.next_action_href) {
      return (
        <Link className="button" href={status.next_action_href}>
          {status.next_action_label}
        </Link>
      );
    }

    return null;
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <h2>Cafe24 Integration</h2>
          <p>실제 네트워크 연결 없이 OAuth, webhook, sync 경계를 로컬에서 검증하는 화면입니다.</p>
        </div>
      </header>

      {notice ? <div className="success-state">{notice}</div> : null}
      {error ? <div className="error-state">{error}</div> : null}
      {loading ? <div className="loading-state">Cafe24 통합 상태를 불러오는 중입니다.</div> : null}

      {status ? (
        <>
          <section className="grid cols-3">
            <div className="card">
              <p>연동 Health</p>
              <div className="metric-value">{status.health_title}</div>
              <p className="metric-caption">{status.connection_mode}</p>
            </div>
            <div className="card">
              <p>동기화된 클레임</p>
              <div className="metric-value">{status.synced_claims}</div>
            </div>
            <div className="card">
              <p>대기 중 문의</p>
              <div className="metric-value">{status.pending_claims}</div>
            </div>
            <div className="card">
              <p>Background Jobs</p>
              <div className="metric-value">{status.queued_jobs + status.running_jobs + status.scheduled_jobs}</div>
              <p className="metric-caption">queued {status.queued_jobs} / running {status.running_jobs} / retry {status.scheduled_jobs}</p>
            </div>
          </section>

          <section className="grid cols-2">
            <div className="card stack">
              <div>
                <h3>연결 상태</h3>
                <p>{status.mall_name} 몰 기준으로 현재 Cafe24 연동 경계를 표시합니다.</p>
              </div>
              <div className="health-banner">
                <div className="actions">
                  <Badge tone={toneForHealthStatus(status.health_status)}>{status.health_title}</Badge>
                  <span className="muted">status: {status.health_status}</span>
                </div>
                <p>{status.health_detail}</p>
                <div className="actions">
                  <span className="muted">추천 다음 단계</span>
                  {renderNextAction()}
                </div>
              </div>
              <div className="summary-list">
                <div className="summary-row">
                  <span className="muted">Mall ID</span>
                  <strong>{status.mall_name}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">OAuth 설정</span>
                  <strong>{status.oauth_configured ? "준비됨" : "미설정"}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">Webhook 핸들러</span>
                  <strong>{status.webhook_endpoint_ready ? "준비됨" : "placeholder"}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">마지막 Sync</span>
                  <strong>{status.last_synced_at ? formatDate(status.last_synced_at) : "아직 없음"}</strong>
                </div>
              </div>
              <div className="actions">
                <Badge tone={toneForResult(status)}>
                  {status.last_sync_result === "mock_completed" ? "Mock Sync 완료" : "Sync 대기"}
                </Badge>
                {status.authorize_url ? (
                  <a className="button ghost" href={status.authorize_url} target="_blank" rel="noreferrer">
                    Preview OAuth URL
                  </a>
                ) : (
                  <span className="muted">OAuth env를 채우면 authorize URL 미리보기를 확인할 수 있습니다.</span>
                )}
                <button className="button ghost" type="button" onClick={handleRunWorkerNow} disabled={working}>
                  Run Worker Now
                </button>
              </div>
            </div>

            <div className="card stack">
              <div>
                <h3>Mock Sync</h3>
                <p>주문 데이터와 시드 클레임 데이터를 기준으로 Cafe24 연결 흐름을 시뮬레이션합니다.</p>
              </div>
              <div className="summary-list">
                <div className="summary-row">
                  <span className="muted">주문 동기화</span>
                  <strong>{status.synced_orders}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">클레임 동기화</span>
                  <strong>{status.synced_claims}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">대기 Webhook</span>
                  <strong>{status.pending_webhooks}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">Batch ID</span>
                  <strong>{status.last_sync_batch_id ?? "-"}</strong>
                </div>
              </div>
              <div className="actions">
                <button className="button" onClick={handleMockSync} disabled={working}>
                  Run Mock Sync
                </button>
              </div>
            </div>
          </section>

          <section className="card stack">
            <div>
              <h3>다음 연결 지점</h3>
              <p>실제 Cafe24 연동 작업이 붙을 위치를 메모 형태로 정리해둔 영역입니다.</p>
            </div>
            <ul className="plain-list">
              {status.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </section>

          <section className="card stack">
            <div>
              <h3>Offline OAuth Test</h3>
              <p>실제 Cafe24 연결 없이 callback placeholder 흐름을 바로 테스트합니다.</p>
            </div>
            <div className="category-summary">
              <Badge tone="neutral">State claimmate-local-{status.merchant_id}</Badge>
              <Badge tone="neutral">Callback /api/integrations/cafe24/callback</Badge>
            </div>
            <div className="actions">
              <a className="button" href={buildCallbackSimulationHref(status.merchant_id, "success")}>
                Simulate Success
              </a>
              <a className="button secondary" href={buildCallbackSimulationHref(status.merchant_id, "error")}>
                Simulate Error
              </a>
            </div>
            <p className="muted">결과는 상단 notice와 최근 activity에 바로 반영됩니다.</p>
          </section>

          <section className="card stack">
            <div>
              <h3>Mock Webhook Test</h3>
              <p>실제 Cafe24 webhook 대신 이벤트를 수동으로 넣어 pending webhook과 activity 흐름을 확인합니다.</p>
            </div>
            <div className="toolbar">
              <div className="field">
                <select value={webhookType} onChange={(event) => setWebhookType(event.target.value)}>
                  {webhookOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <input
                  value={webhookOrderNo}
                  onChange={(event) => setWebhookOrderNo(event.target.value)}
                  placeholder="선택 입력: 주문번호"
                />
              </div>
              <button className="button" type="button" onClick={handleMockWebhook} disabled={working}>
                Send Mock Webhook
              </button>
            </div>
            <p className="muted">webhook 요청은 먼저 job queue에 들어가고, worker가 처리한 뒤 pending webhook 수치와 최근 activity가 갱신됩니다.</p>
          </section>

          <section className="card stack">
            <div>
              <h3>Background Jobs</h3>
              <p>sync, webhook, retry 작업이 Redis 기반 queue를 통해 처리되고 있는지 여기서 바로 추적합니다.</p>
            </div>
            <div className="summary-list">
              <div className="summary-row">
                <span className="muted">Queued</span>
                <strong>{status.queued_jobs}</strong>
              </div>
              <div className="summary-row">
                <span className="muted">Running</span>
                <strong>{status.running_jobs}</strong>
              </div>
              <div className="summary-row">
                <span className="muted">Retry Scheduled</span>
                <strong>{status.scheduled_jobs}</strong>
              </div>
              <div className="summary-row">
                <span className="muted">Dead Letter</span>
                <strong>{status.dead_letter_jobs}</strong>
              </div>
            </div>
            {status.recent_jobs.length > 0 ? (
              <div className="timeline">
                {status.recent_jobs.map((job) => (
                  <div key={job.id} className="timeline-item">
                    <div className="actions">
                      <strong>
                        #{job.id} {job.job_label}
                      </strong>
                      <Badge tone={toneForJobStatus(job.status)}>{job.status}</Badge>
                    </div>
                    <p className="timeline-meta">
                      triggered by {job.triggered_by} / retry {job.retry_count} of {job.max_retries}
                    </p>
                    {job.result_preview ? <p>{job.result_preview}</p> : null}
                    {job.error_message ? <p className="timeline-meta">{job.error_message}</p> : null}
                    <div className="actions">
                      {job.started_at ? <span className="muted">started {formatDate(job.started_at)}</span> : null}
                      {job.completed_at ? <span className="muted">completed {formatDate(job.completed_at)}</span> : null}
                      {!job.completed_at && job.available_at ? <span className="muted">next run {formatDate(job.available_at)}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">아직 기록된 background job이 없습니다.</div>
            )}
          </section>

          <section className="card stack">
            <div>
              <h3>최근 Activity</h3>
              <p>Mock Sync, OAuth callback, webhook placeholder가 만든 최근 이벤트를 기록합니다.</p>
            </div>
            <div className="actions">
              <select
                className="control-select"
                value={activityFilter}
                onChange={(event) =>
                  setActivityFilter(event.target.value as "all" | "mock_sync" | "oauth_callback" | "mock_webhook")
                }
              >
                <option value="all">전체 이벤트</option>
                <option value="mock_sync">Mock Sync</option>
                <option value="oauth_callback">OAuth Callback</option>
                <option value="mock_webhook">Mock Webhook</option>
              </select>
              <button className="button ghost" onClick={handleClearActivity} disabled={working || status.recent_events.length === 0}>
                Clear Activity
              </button>
            </div>
            {filteredEvents.length > 0 ? (
              <div className="timeline">
                {filteredEvents.map((event) => (
                  <div key={`${event.event_type}-${event.occurred_at}-${event.batch_id ?? "none"}`} className="timeline-item">
                    <div className="actions">
                      <strong>{event.title}</strong>
                      <Badge tone={event.status === "success" || event.status === "received" || event.status === "mock_completed" ? "teal" : "accent"}>
                        {event.status}
                      </Badge>
                    </div>
                    <p>{event.detail}</p>
                    <p className="muted">{formatDate(event.occurred_at)}</p>
                    <div className="actions">
                      {event.order_no ? <span className="muted">order: {event.order_no}</span> : null}
                      {event.batch_id ? <span className="muted">batch_id: {event.batch_id}</span> : null}
                      {event.claim_id ? (
                        <Link href={`/claims/${event.claim_id}`} className="button ghost">
                          Open Claim
                        </Link>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                {status.recent_events.length === 0 ? "아직 기록된 Cafe24 activity가 없습니다." : "선택한 필터에 맞는 activity가 없습니다."}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
