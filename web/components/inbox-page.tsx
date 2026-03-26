"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import {
  Cafe24IntegrationStatus,
  Claim,
  ClaimCategory,
  ClaimStatus,
  DashboardCafe24Overview,
  DashboardSummary,
} from "@/lib/types";
import { Badge, categoryLabels, formatDate, statusLabels, urgencyLabels } from "@/components/ui";

const categoryOptions: Array<{ value: "" | ClaimCategory; label: string }> = [
  { value: "", label: "전체 카테고리" },
  { value: "delivery", label: "배송" },
  { value: "cancellation", label: "취소" },
  { value: "exchange", label: "교환" },
  { value: "return", label: "반품" },
  { value: "refund", label: "환불" },
  { value: "defect", label: "파손/불량" },
  { value: "misdelivery", label: "오배송" },
  { value: "other", label: "기타" },
];

const statusOptions: Array<{ value: "" | ClaimStatus; label: string }> = [
  { value: "", label: "전체 상태" },
  { value: "open", label: "접수" },
  { value: "in_review", label: "검토중" },
  { value: "approved", label: "승인" },
  { value: "rejected", label: "반려" },
  { value: "done", label: "완료" },
];

type SortOption = "priority" | "newest" | "oldest" | "customer";

const sortOptions: Array<{ value: SortOption; label: string }> = [
  { value: "priority", label: "우선순위" },
  { value: "newest", label: "최신순" },
  { value: "oldest", label: "오래된순" },
  { value: "customer", label: "고객명" },
];

const urgencyRank: Record<Claim["urgency"], number> = {
  high: 3,
  medium: 2,
  low: 1,
};

const statusRank: Record<ClaimStatus, number> = {
  open: 4,
  in_review: 3,
  approved: 2,
  rejected: 1,
  done: 0,
};

function toneForUrgency(urgency: Claim["urgency"]) {
  if (urgency === "high") return "danger";
  if (urgency === "medium") return "accent";
  return "teal";
}

function toneForSyncResult(status: Cafe24IntegrationStatus | null) {
  if (!status) return "neutral";
  if (status.last_sync_result === "mock_completed") return "teal";
  return "accent";
}

function toneForHealthStatus(status: string) {
  if (status === "healthy") return "teal";
  if (status === "setup_needed") return "accent";
  if (status === "attention") return "danger";
  return "neutral";
}

function toneForActivityStatus(status: string) {
  if (status === "success" || status === "received" || status === "mock_completed") return "teal";
  if (status === "error" || status === "failed") return "danger";
  return "accent";
}

function buildCafe24Overview(status: Cafe24IntegrationStatus): DashboardCafe24Overview {
  const latestEvent = status.recent_events[0];
  return {
    health_status: status.health_status,
    health_title: status.health_title,
    health_detail: status.health_detail,
    last_sync_result: status.last_sync_result,
    last_synced_at: status.last_synced_at,
    pending_webhooks: status.pending_webhooks,
    recent_activity_count: status.recent_events.length,
    latest_event_title: latestEvent?.title ?? null,
    latest_event_status: latestEvent?.status ?? null,
    latest_event_occurred_at: latestEvent?.occurred_at ?? null,
    next_action_type: status.next_action_type,
    next_action_label: status.next_action_label,
    next_action_href: status.next_action_href,
  };
}

function compareClaims(a: Claim, b: Claim, sortBy: SortOption) {
  if (sortBy === "customer") {
    return a.customer_name.localeCompare(b.customer_name, "ko-KR");
  }

  if (sortBy === "oldest") {
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  }

  if (sortBy === "newest") {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  }

  const statusDifference = statusRank[b.status] - statusRank[a.status];
  if (statusDifference !== 0) {
    return statusDifference;
  }

  const urgencyDifference = urgencyRank[b.urgency] - urgencyRank[a.urgency];
  if (urgencyDifference !== 0) {
    return urgencyDifference;
  }

  return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
}

export function InboxPage() {
  const router = useRouter();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [syncStatus, setSyncStatus] = useState<Cafe24IntegrationStatus | null>(null);
  const [category, setCategory] = useState<"" | ClaimCategory>("");
  const [status, setStatus] = useState<"" | ClaimStatus>("");
  const [sortBy, setSortBy] = useState<SortOption>("priority");
  const [searchText, setSearchText] = useState("");
  const [isInitialized, setIsInitialized] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncWorking, setSyncWorking] = useState(false);
  const deferredSearchText = useDeferredValue(searchText);
  const sortedClaims = [...claims].sort((left, right) => compareClaims(left, right, sortBy));

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const nextCategory = params.get("category");
    const nextStatus = params.get("status");
    const nextSort = params.get("sort");

    setCategory(categoryOptions.some((option) => option.value === nextCategory) ? (nextCategory as ClaimCategory) : "");
    setStatus(statusOptions.some((option) => option.value === nextStatus) ? (nextStatus as ClaimStatus) : "");
    setSortBy(sortOptions.some((option) => option.value === nextSort) ? (nextSort as SortOption) : "priority");
    setSearchText(params.get("q") ?? "");
    setIsInitialized(true);
  }, []);

  useEffect(() => {
    if (!isInitialized) {
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      setSyncError(null);

      const search = new URLSearchParams();
      if (category) search.set("category", category);
      if (status) search.set("status", status);
      if (deferredSearchText.trim()) search.set("q", deferredSearchText.trim());

      const queryString = search.toString();
      const claimsPath = queryString ? `/api/claims?${queryString}` : "/api/claims";
      const summaryPath = queryString ? `/api/dashboard/summary?${queryString}` : "/api/dashboard/summary";

      try {
        const [claimsResult, summaryResult, syncResult] = await Promise.allSettled([
          apiFetch<Claim[]>(claimsPath),
          apiFetch<DashboardSummary>(summaryPath),
          apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24"),
        ]);

        if (claimsResult.status !== "fulfilled" || summaryResult.status !== "fulfilled") {
          throw new Error("목록을 불러오지 못했습니다.");
        }

        if (!cancelled) {
          setClaims(claimsResult.value);
          if (syncResult.status === "fulfilled") {
            setSyncStatus(syncResult.value);
            setSummary({
              ...summaryResult.value,
              cafe24: buildCafe24Overview(syncResult.value),
            });
          } else {
            setSummary(summaryResult.value);
            setSyncStatus(null);
            setSyncError("Cafe24 sync 상태를 잠시 후 다시 확인해 주세요.");
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "목록을 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [category, status, deferredSearchText, isInitialized]);

  useEffect(() => {
    if (!isInitialized) {
      return;
    }

    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    if (sortBy !== "priority") params.set("sort", sortBy);
    if (searchText.trim()) params.set("q", searchText.trim());

    const query = params.toString();
    const nextUrl = query ? `/inbox?${query}` : "/inbox";
    window.history.replaceState(null, "", nextUrl);
  }, [category, status, sortBy, searchText, isInitialized]);

  async function handleRunMockSync() {
    setSyncWorking(true);
    setSyncError(null);
    try {
      const data = await apiFetch<Cafe24IntegrationStatus>("/api/integrations/cafe24/mock-sync", {
        method: "POST",
      });
      setSyncStatus(data);
      setSummary((current) => (current ? { ...current, cafe24: buildCafe24Overview(data) } : current));
    } catch (loadError) {
      setSyncError(loadError instanceof Error ? loadError.message : "Cafe24 Mock Sync 실행에 실패했습니다.");
    } finally {
      setSyncWorking(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <h2>Claim Inbox</h2>
          <p>카페24 운영자가 처리할 클레임을 카테고리, 상태, 긴급도 기준으로 빠르게 정리합니다.</p>
        </div>
      </header>

      {syncStatus ? (
        <section className="card stack">
          <div className="page-header compact-header">
            <div>
              <h3>Cafe24 Mock Sync</h3>
              <p>인박스에서 바로 연동 상태를 확인하고 필요하면 mock sync를 다시 실행할 수 있습니다.</p>
            </div>
            <div className="actions">
              <Badge tone={toneForSyncResult(syncStatus)}>
                {syncStatus.last_sync_result === "mock_completed" ? "Mock Sync 완료" : "Sync 대기"}
              </Badge>
              <Link href="/integrations/cafe24" className="button ghost">
                Open Cafe24 Console
              </Link>
              <button className="button" type="button" onClick={handleRunMockSync} disabled={syncWorking}>
                Run Mock Sync
              </button>
            </div>
          </div>
          <div className="grid cols-3">
            <div className="summary-row tile-row">
              <span className="muted">마지막 Sync</span>
              <strong>{syncStatus.last_synced_at ? formatDate(syncStatus.last_synced_at) : "아직 없음"}</strong>
            </div>
            <div className="summary-row tile-row">
              <span className="muted">Pending Webhook</span>
              <strong>{syncStatus.pending_webhooks}</strong>
            </div>
            <div className="summary-row tile-row">
              <span className="muted">Batch ID</span>
              <strong>{syncStatus.last_sync_batch_id ?? "-"}</strong>
            </div>
          </div>
          <div className="category-summary">
            <Badge tone="neutral">Mall {syncStatus.mall_name}</Badge>
            <Badge tone="neutral">Synced Orders {syncStatus.synced_orders}</Badge>
            <Badge tone="neutral">Synced Claims {syncStatus.synced_claims}</Badge>
            <Badge tone="accent">Pending Claims {syncStatus.pending_claims}</Badge>
          </div>
          <div className="health-banner">
            <div className="actions">
              <Badge tone={toneForHealthStatus(syncStatus.health_status)}>{syncStatus.health_title}</Badge>
              <span className="muted">status: {syncStatus.health_status}</span>
            </div>
            <p>{syncStatus.health_detail}</p>
            <div className="actions">
              <span className="muted">Next</span>
              {syncStatus.next_action_type === "mock_sync" ? (
                <button className="button secondary" type="button" onClick={handleRunMockSync} disabled={syncWorking}>
                  {syncStatus.next_action_label}
                </button>
              ) : syncStatus.next_action_href ? (
                <Link href={syncStatus.next_action_href} className="button secondary">
                  {syncStatus.next_action_label}
                </Link>
              ) : null}
            </div>
          </div>
          {syncStatus.recent_events.length > 0 ? (
            <div className="mini-activity-list">
              {syncStatus.recent_events.slice(0, 2).map((event) => (
                <div key={`${event.event_type}-${event.occurred_at}`} className="mini-activity-item">
                  <div className="actions">
                    <strong>{event.title}</strong>
                    <Badge tone={toneForActivityStatus(event.status)}>{event.status}</Badge>
                  </div>
                  <p>{event.detail}</p>
                  <p className="muted">{formatDate(event.occurred_at)}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state inline-state">아직 표시할 Cafe24 activity가 없습니다.</div>
          )}
          {syncError ? <div className="error-state inline-state">{syncError}</div> : null}
        </section>
      ) : null}

      {!syncStatus && syncError ? <div className="error-state inline-state">{syncError}</div> : null}

      {summary ? (
        <section className="grid cols-3">
          <div className="card">
            <p>전체 클레임</p>
            <div className="metric-value">{summary.total_claims}</div>
          </div>
          <div className="card">
            <p>접수 + 검토중</p>
            <div className="metric-value">{summary.open_claims + summary.in_review_claims}</div>
          </div>
          <div className="card">
            <p>높은 긴급도</p>
            <div className="metric-value">{summary.high_urgency_claims}</div>
          </div>
          {summary.cafe24 ? (
            <div className="card">
              <p>Cafe24 Health</p>
              <div className="actions">
                <Badge tone={toneForHealthStatus(summary.cafe24.health_status)}>{summary.cafe24.health_title}</Badge>
              </div>
              <p className="metric-caption">{summary.cafe24.health_detail}</p>
              <p className="metric-caption">
                {summary.cafe24.last_synced_at ? formatDate(summary.cafe24.last_synced_at) : "아직 sync 없음"} · pending webhook{" "}
                {summary.cafe24.pending_webhooks} · activity {summary.cafe24.recent_activity_count}
              </p>
              {summary.cafe24.latest_event_title ? (
                <div className="actions">
                  <Badge tone={toneForActivityStatus(summary.cafe24.latest_event_status ?? "neutral")}>
                    {summary.cafe24.latest_event_status ?? "event"}
                  </Badge>
                  <span className="muted">
                    {summary.cafe24.latest_event_title}
                    {summary.cafe24.latest_event_occurred_at ? ` · ${formatDate(summary.cafe24.latest_event_occurred_at)}` : ""}
                  </span>
                </div>
              ) : null}
              <div className="actions">
                {summary.cafe24.next_action_type === "mock_sync" ? (
                  <button className="button secondary" type="button" onClick={handleRunMockSync} disabled={syncWorking}>
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
      ) : null}

      <section className="card">
        <div className="toolbar">
          <div className="field search-field">
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="주문번호, 고객명, 상품명, 문의 내용을 검색하세요"
            />
          </div>
          <div className="field">
            <select value={category} onChange={(event) => setCategory(event.target.value as "" | ClaimCategory)}>
              {categoryOptions.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <select value={status} onChange={(event) => setStatus(event.target.value as "" | ClaimStatus)}>
              {statusOptions.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field compact-field">
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortOption)}>
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <button
            className="button ghost"
            type="button"
            onClick={() => {
              setSearchText("");
              setCategory("");
              setStatus("");
              setSortBy("priority");
            }}
          >
            필터 초기화
          </button>
        </div>

        {loading ? <div className="loading-state">클레임 목록을 불러오는 중입니다.</div> : null}
        {error ? <div className="error-state">{error}</div> : null}

        {summary && Object.keys(summary.by_category).length > 0 ? (
          <div className="category-summary">
            {Object.entries(summary.by_category).map(([key, count]) => {
              const label = categoryLabels[key as ClaimCategory] ?? key;
              return (
                <Badge key={key} tone="neutral">
                  {label} {count}
                </Badge>
              );
            })}
          </div>
        ) : null}

        {!loading && !error ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>주문번호</th>
                  <th>고객</th>
                  <th>상품</th>
                  <th>카테고리</th>
                  <th>상태</th>
                  <th>긴급도</th>
                  <th>접수일</th>
                </tr>
              </thead>
              <tbody>
                {sortedClaims.map((claim) => (
                  <tr key={claim.id} onClick={() => router.push(`/claims/${claim.id}`)}>
                    <td>{claim.order_no}</td>
                    <td>{claim.customer_name}</td>
                    <td>{claim.product_name}</td>
                    <td>
                      <Badge tone="neutral">{categoryLabels[claim.category]}</Badge>
                    </td>
                    <td>
                      <Badge tone="teal">{statusLabels[claim.status]}</Badge>
                    </td>
                    <td>
                      <Badge tone={toneForUrgency(claim.urgency)}>{urgencyLabels[claim.urgency]}</Badge>
                    </td>
                    <td>{formatDate(claim.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sortedClaims.length === 0 ? <div className="empty-state">조건에 맞는 클레임이 없습니다.</div> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
