"use client";

import { useEffect, useState } from "react";
import { useAuthSession } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { AdminDiagnostics } from "@/lib/types";
import { Badge, formatDate } from "@/components/ui";

function toneForCircuitState(state: string) {
  if (state === "open") return "danger";
  if (state === "half_open") return "accent";
  return "teal";
}

function toneForSeverity(severity: string) {
  if (severity === "critical" || severity === "error") return "danger";
  if (severity === "warning") return "accent";
  return "neutral";
}

function formatSeconds(value: number) {
  if (value < 60) {
    return `${value}s`;
  }
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return `${minutes}m ${seconds}s`;
}

function stringifyPayload(payload: Record<string, unknown> | null) {
  if (!payload) {
    return "-";
  }
  return JSON.stringify(payload, null, 2);
}

export function AdminDiagnosticsPage() {
  const { session } = useAuthSession();
  const [diagnostics, setDiagnostics] = useState<AdminDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDiagnostics(isRefresh = false) {
    if (session.role !== "manager") {
      setDiagnostics(null);
      setLoading(false);
      return;
    }

    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const payload = await apiFetch<AdminDiagnostics>("/api/admin/diagnostics");
      setDiagnostics(payload);
    } catch (diagnosticsError) {
      setError(diagnosticsError instanceof Error ? diagnosticsError.message : "운영 진단 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadDiagnostics();
  }, [session.role]);

  if (session.role !== "manager") {
    return <div className="error-banner">운영 진단 페이지는 매니저 권한에서만 확인할 수 있습니다.</div>;
  }

  if (loading && !diagnostics) {
    return <div className="loading-state">운영 진단 데이터를 불러오는 중입니다.</div>;
  }

  if (error && !diagnostics) {
    return <div className="error-banner">{error}</div>;
  }

  if (!diagnostics) {
    return <div className="error-banner">운영 진단 데이터를 찾을 수 없습니다.</div>;
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <p className="brand-eyebrow">Operations</p>
          <h2>운영 진단</h2>
          <p>API, webhook, background job, 경보, 보호 정책을 한 화면에서 확인하는 관리자용 지원 페이지입니다.</p>
        </div>
        <div className="actions">
          <Badge tone="neutral">{diagnostics.environment}</Badge>
          <Badge tone="neutral">uptime {formatSeconds(diagnostics.uptime_seconds)}</Badge>
          <button className="button secondary" type="button" onClick={() => void loadDiagnostics(true)} disabled={refreshing}>
            {refreshing ? "새로고침 중..." : "새로고침"}
          </button>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="grid cols-3">
        <div className="card stack">
          <div>
            <h3>API 요청</h3>
            <p>{diagnostics.app_name}</p>
          </div>
          <div className="metric-value">{diagnostics.request_metrics.total_requests}</div>
          <p className="metric-caption">
            4xx {diagnostics.request_metrics.client_errors} / 5xx {diagnostics.request_metrics.server_errors} / slow{" "}
            {diagnostics.request_metrics.slow_requests}
          </p>
        </div>
        <div className="card stack">
          <div>
            <h3>Webhook 처리</h3>
            <p>중복과 실패 추이를 같이 봅니다.</p>
          </div>
          <div className="metric-value">{diagnostics.webhook_metrics.total_received}</div>
          <p className="metric-caption">
            duplicate {diagnostics.webhook_metrics.duplicate_count} / failed {diagnostics.webhook_metrics.failed_count}
          </p>
        </div>
        <div className="card stack">
          <div>
            <h3>Background Jobs</h3>
            <p>재시도와 dead letter까지 함께 봅니다.</p>
          </div>
          <div className="metric-value">{diagnostics.job_metrics.total_runs}</div>
          <p className="metric-caption">
            succeeded {diagnostics.job_metrics.succeeded} / retry {diagnostics.job_metrics.retry_scheduled} / dead letter{" "}
            {diagnostics.job_metrics.dead_letter}
          </p>
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>Cafe24 연동 상태</h3>
              <p>현재 연동 health와 최근 작업을 같이 봅니다.</p>
            </div>
            {diagnostics.cafe24 ? <Badge tone="teal">{diagnostics.cafe24.health_title}</Badge> : null}
          </header>
          {diagnostics.cafe24 ? (
            <>
              <p>{diagnostics.cafe24.health_detail}</p>
              <div className="summary-list">
                <div className="summary-row">
                  <span>마지막 sync</span>
                  <strong>{diagnostics.cafe24.last_synced_at ? formatDate(diagnostics.cafe24.last_synced_at) : "아직 없음"}</strong>
                </div>
                <div className="summary-row">
                  <span>pending webhook</span>
                  <strong>{diagnostics.cafe24.pending_webhooks}</strong>
                </div>
                <div className="summary-row">
                  <span>dead letter jobs</span>
                  <strong>{diagnostics.cafe24.dead_letter_jobs}</strong>
                </div>
              </div>
            </>
          ) : (
            <p className="muted">Cafe24 개요 데이터를 불러오지 못했습니다.</p>
          )}
        </div>

        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>보호 정책</h3>
              <p>rate limit, timeout, masking 규칙을 확인합니다.</p>
            </div>
            <Badge tone="neutral">{formatDate(diagnostics.generated_at)}</Badge>
          </header>
          <div className="resource-links">
            {diagnostics.rate_limit_policies.map((policy) => (
              <div className="resource-link" key={policy.scope}>
                <strong>{policy.scope}</strong>
                <span className="muted">
                  {policy.limit} req / {policy.window_seconds}s, active keys {policy.active_keys}
                </span>
              </div>
            ))}
            {diagnostics.timeout_policies.map((policy) => (
              <div className="resource-link" key={policy.target}>
                <strong>{policy.target}</strong>
                <span className="muted">timeout {policy.timeout_seconds}s</span>
              </div>
            ))}
          </div>
          <ul className="plain-list">
            {diagnostics.masking_rules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>Circuit Breakers</h3>
              <p>외부 호출 보호 상태를 확인합니다.</p>
            </div>
          </header>
          <div className="mini-activity-list">
            {diagnostics.circuit_breakers.length === 0 ? (
              <div className="mini-activity-item">
                <strong>아직 기록 없음</strong>
                <p className="muted">외부 호출이 발생하면 상태가 여기 쌓입니다.</p>
              </div>
            ) : (
              diagnostics.circuit_breakers.map((breaker) => (
                <div className="mini-activity-item" key={breaker.service_name}>
                  <div className="status-line">
                    <strong>{breaker.service_name}</strong>
                    <Badge tone={toneForCircuitState(breaker.state)}>{breaker.state}</Badge>
                  </div>
                  <p className="muted">
                    failures {breaker.failure_count}/{breaker.failure_threshold} / recovery {breaker.recovery_seconds}s
                  </p>
                  <p className="muted">
                    last failure {breaker.last_failure_at ? formatDate(breaker.last_failure_at) : "-"} / last success{" "}
                    {breaker.last_success_at ? formatDate(breaker.last_success_at) : "-"}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>Webhook / Job Breakdown</h3>
              <p>이벤트와 job 유형별 분포를 빠르게 봅니다.</p>
            </div>
          </header>
          <div className="summary-list">
            {diagnostics.webhook_metrics.events.slice(0, 6).map((event) => (
              <div className="summary-row" key={event.event_type}>
                <span>{event.event_type}</span>
                <strong>
                  {event.count} / failed {event.failed_count}
                </strong>
              </div>
            ))}
            {diagnostics.job_metrics.job_types.slice(0, 6).map((job) => (
              <div className="summary-row" key={job.job_type}>
                <span>{job.job_type}</span>
                <strong>
                  {job.run_count} / dead {job.dead_letter_count}
                </strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card stack">
        <header className="compact-header page-header">
          <div>
            <h3>최근 경보</h3>
            <p>alert webhook 연동 여부와 함께 최근 운영 경보를 봅니다.</p>
          </div>
        </header>
        <div className="mini-activity-list">
          {diagnostics.recent_alerts.length === 0 ? (
            <div className="mini-activity-item">
              <strong>최근 경보 없음</strong>
              <p className="muted">dead letter나 치명 오류가 발생하면 여기에 표시됩니다.</p>
            </div>
          ) : (
            diagnostics.recent_alerts.map((alert, index) => (
              <div className="mini-activity-item" key={`${alert.event_type}-${index}`}>
                <div className="status-line">
                  <Badge tone={toneForSeverity(alert.severity)}>{alert.severity}</Badge>
                  <Badge tone="neutral">{alert.channel}</Badge>
                  <Badge tone={alert.delivery_status === "sent" ? "teal" : alert.delivery_status === "failed" ? "danger" : "neutral"}>
                    {alert.delivery_status}
                  </Badge>
                </div>
                <strong>{alert.message}</strong>
                <p className="muted">
                  {alert.event_type} / {formatDate(alert.occurred_at)}
                </p>
                {alert.delivery_error ? <p className="muted">delivery error: {alert.delivery_error}</p> : null}
                <pre className="diagnostics-code">{stringifyPayload(alert.payload_json)}</pre>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>최근 에러</h3>
              <p>구조화된 에러 로그 일부만 노출합니다.</p>
            </div>
          </header>
          <div className="mini-activity-list">
            {diagnostics.recent_errors.length === 0 ? (
              <div className="mini-activity-item">
                <strong>최근 에러 없음</strong>
                <p className="muted">현재까지 심각한 런타임 오류는 기록되지 않았습니다.</p>
              </div>
            ) : (
              diagnostics.recent_errors.map((item, index) => (
                <div className="mini-activity-item" key={`${item.component}-${index}`}>
                  <div className="status-line">
                    <Badge tone={toneForSeverity(item.severity)}>{item.severity}</Badge>
                    <Badge tone="neutral">{item.component}</Badge>
                  </div>
                  <strong>{item.message}</strong>
                  <p className="muted">{formatDate(item.occurred_at)}</p>
                  <pre className="diagnostics-code">{stringifyPayload(item.payload_json)}</pre>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>API Route Metrics</h3>
              <p>요청 수와 느린 route를 함께 확인합니다.</p>
            </div>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Route</th>
                  <th>Count</th>
                  <th>Errors</th>
                  <th>Avg</th>
                  <th>Max</th>
                  <th>Last</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.request_metrics.routes.slice(0, 12).map((route) => (
                  <tr key={`${route.method}-${route.route}`}>
                    <td>
                      <strong>{route.method}</strong> {route.route}
                    </td>
                    <td>{route.request_count}</td>
                    <td>{route.error_count}</td>
                    <td>{route.avg_duration_ms.toFixed(1)}ms</td>
                    <td>{route.max_duration_ms.toFixed(1)}ms</td>
                    <td>{route.last_status_code ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>최근 Background Jobs</h3>
              <p>Cafe24 관련 최근 job 상태입니다.</p>
            </div>
          </header>
          <div className="mini-activity-list">
            {diagnostics.recent_jobs.map((job) => (
              <div className="mini-activity-item" key={job.id}>
                <div className="status-line">
                  <strong>{job.job_label}</strong>
                  <Badge tone={job.status === "succeeded" ? "teal" : job.status === "dead_letter" ? "danger" : "accent"}>
                    {job.status}
                  </Badge>
                </div>
                <p className="muted">
                  triggered by {job.triggered_by} / retry {job.retry_count}/{job.max_retries}
                </p>
                <p className="muted">
                  created {formatDate(job.created_at)}
                  {job.completed_at ? ` / completed ${formatDate(job.completed_at)}` : ""}
                </p>
                {job.error_message ? <p className="muted">error: {job.error_message}</p> : null}
              </div>
            ))}
          </div>
        </div>

        <div className="card stack">
          <header className="compact-header page-header">
            <div>
              <h3>최근 Cafe24 Activity</h3>
              <p>support 담당자가 상황을 복기할 때 보는 최근 이벤트입니다.</p>
            </div>
          </header>
          <div className="mini-activity-list">
            {diagnostics.recent_events.map((event, index) => (
              <div className="mini-activity-item" key={`${event.event_type}-${index}`}>
                <div className="status-line">
                  <strong>{event.title}</strong>
                  <Badge tone={event.status === "success" || event.status === "received" || event.status === "mock_completed" ? "teal" : "accent"}>
                    {event.status}
                  </Badge>
                </div>
                <p>{event.detail}</p>
                <p className="muted">
                  {formatDate(event.occurred_at)}
                  {event.order_no ? ` / ${event.order_no}` : ""}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
