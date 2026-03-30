"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Claim, ClaimStatus, ClassificationResponse, DraftReplyResponse, SuggestedAction } from "@/lib/types";
import {
  Badge,
  categoryLabels,
  formatAutomationSourceEvent,
  formatDate,
  formatReplyDeliveryChannel,
  formatReplyDeliveryStatus,
  statusLabels,
  urgencyLabels,
} from "@/components/ui";

function findLatestSuggestion(actions: SuggestedAction[] | undefined, actionType: string) {
  return actions?.find((action) => action.action_type === actionType) ?? null;
}

function formatAuditPayload(payload: Record<string, unknown> | null | undefined) {
  if (!payload) {
    return null;
  }

  return Object.entries(payload)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" / ");
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-";
  }

  return `${Math.round(value * 100)}%`;
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const helper = document.createElement("textarea");
  helper.value = value;
  helper.setAttribute("readonly", "true");
  helper.style.position = "absolute";
  helper.style.left = "-9999px";
  document.body.appendChild(helper);
  helper.select();
  document.execCommand("copy");
  document.body.removeChild(helper);
}

function toneForUrgency(urgency: Claim["urgency"]) {
  if (urgency === "high") return "danger";
  if (urgency === "medium") return "accent";
  return "teal";
}

function toneForDeliveryStatus(status: string | null | undefined) {
  if (status === "failed") return "danger";
  if (status === "sent") return "teal";
  return "neutral";
}

export function ClaimDetailPage({ claimId }: { claimId: string }) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [internalNote, setInternalNote] = useState("");
  const [workingAction, setWorkingAction] = useState<string | null>(null);
  const [replyDraft, setReplyDraft] = useState("");
  const [closeAfterSend, setCloseAfterSend] = useState(true);

  async function loadClaim() {
    setLoading(true);
    setError(null);

    try {
      const data = await apiFetch<Claim>(`/api/claims/${claimId}`);
      setClaim(data);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "클레임 상세 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadClaim();
  }, [claimId]);

  const latestClassification = findLatestSuggestion(claim?.suggested_actions, "classification");
  const latestReply = findLatestSuggestion(claim?.suggested_actions, "draft_reply");
  const hasGeneratedReply = Boolean(latestReply?.draft_reply);
  const isReplyEdited = hasGeneratedReply && replyDraft !== (latestReply?.draft_reply ?? "");

  useEffect(() => {
    setReplyDraft(latestReply?.draft_reply ?? "");
  }, [latestReply?.id, latestReply?.draft_reply]);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function handleStatusChange(status: ClaimStatus) {
    setWorkingAction(status);

    try {
      const data = await apiFetch<Claim>(`/api/claims/${claimId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status, actor: "web_operator" }),
      });

      setClaim(data);
      setError(null);
      setNotice(`상태가 ${statusLabels[status]}로 변경되었습니다.`);
    } catch (actionError) {
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "상태 변경에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleClassify() {
    setWorkingAction("classify");

    try {
      await apiFetch<ClassificationResponse>(`/api/claims/${claimId}/classify`, { method: "POST" });
      await loadClaim();
      setError(null);
      setNotice("AI 분류를 다시 실행했습니다.");
    } catch (actionError) {
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "분류 실행에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleDraftReply() {
    setWorkingAction("draft-reply");

    try {
      await apiFetch<DraftReplyResponse>(`/api/claims/${claimId}/draft-reply`, { method: "POST" });
      await loadClaim();
      setError(null);
      setNotice("답변 초안을 다시 생성했습니다.");
    } catch (actionError) {
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "답변 초안 생성에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleSendReply() {
    if (!replyDraft.trim()) {
      setNotice(null);
      setError("보낼 답변 초안이 없습니다. 먼저 초안을 생성하거나 내용을 입력해 주세요.");
      return;
    }

    setWorkingAction("send-reply");

    try {
      const payload =
        isReplyEdited || !hasGeneratedReply
          ? { reply_body: replyDraft.trim(), actor: "web_operator", mark_done: closeAfterSend }
          : { actor: "web_operator", mark_done: closeAfterSend };

      const data = await apiFetch<Claim>(`/api/claims/${claimId}/send-reply`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setClaim(data);
      setError(null);
      setNotice(
        closeAfterSend
          ? "답변을 발송하고 클레임을 완료 상태로 반영했습니다."
          : "답변을 발송했고, 클레임은 현재 상태로 유지했습니다.",
      );
    } catch (actionError) {
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "답변 발송 처리에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleRetryFailedDelivery() {
    setWorkingAction("retry-delivery");

    try {
      const data = await apiFetch<Claim>(`/api/claims/${claimId}/retry-reply-delivery`, {
        method: "POST",
        body: JSON.stringify({ actor: "web_operator", mark_done: closeAfterSend }),
      });

      setClaim(data);
      setError(null);
      setNotice("실패한 발송을 다시 시도했습니다.");
    } catch (actionError) {
      await loadClaim();
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "발송 재시도에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleCopyReply() {
    if (!replyDraft.trim()) {
      setNotice(null);
      setError("복사할 답변 초안이 없습니다. 먼저 초안을 생성하거나 내용을 입력해 주세요.");
      return;
    }

    try {
      await copyText(replyDraft.trim());
      setError(null);
      setNotice("현재 편집 중인 답변 초안을 클립보드에 복사했습니다.");
    } catch (copyError) {
      setNotice(null);
      setError(copyError instanceof Error ? copyError.message : "답변 복사에 실패했습니다.");
    }
  }

  function handleResetReply() {
    setReplyDraft(latestReply?.draft_reply ?? "");
    setError(null);
    setNotice("AI가 생성한 원본 초안으로 되돌렸습니다.");
  }

  async function handleAddInternalNote() {
    const trimmedNote = internalNote.trim();
    if (!trimmedNote) {
      setNotice(null);
      setError("내부 메모 내용을 입력해 주세요.");
      return;
    }

    setWorkingAction("add-note");

    try {
      const data = await apiFetch<Claim>(`/api/claims/${claimId}/notes`, {
        method: "POST",
        body: JSON.stringify({ note: trimmedNote, actor: "web_operator" }),
      });

      setClaim(data);
      setInternalNote("");
      setError(null);
      setNotice("내부 메모를 저장했습니다.");
    } catch (noteError) {
      setNotice(null);
      setError(noteError instanceof Error ? noteError.message : "내부 메모 저장에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  if (loading) {
    return <div className="loading-state">클레임 상세 정보를 불러오는 중입니다.</div>;
  }

  if (error && !claim) {
    return <div className="error-state">{error}</div>;
  }

  if (!claim) {
    return <div className="empty-state">해당 클레임을 찾을 수 없습니다.</div>;
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <Link href="/inbox" className="muted">
            ← Inbox
          </Link>
          <h2>{claim.order_no}</h2>
          <p>{claim.customer_name} 고객 문의를 검토하고, 답변 생성과 상태 변경까지 바로 처리할 수 있습니다.</p>
        </div>
      </header>

      {claim.automation.follow_up_needed ? (
        <section className="health-banner">
          <div className="actions">
            <Badge tone="danger">후속 확인 필요</Badge>
            <span className="muted">
              {claim.automation.reply_sent_at ? formatDate(claim.automation.reply_sent_at) : "-"} /{" "}
              {claim.automation.reply_sent_by ?? "-"}
            </span>
          </div>
          <p>답변은 발송됐지만 아직 완료 처리되지 않았습니다. 고객 회신 여부나 추가 작업을 확인한 뒤 마감해 주세요.</p>
          <div className="actions">
            <button className="button" onClick={() => handleStatusChange("done")} disabled={!!workingAction}>
              Follow-up Done
            </button>
          </div>
        </section>
      ) : null}

      {notice ? <div className="success-state">{notice}</div> : null}
      {error ? <div className="error-state">{error}</div> : null}

      <section className="grid cols-2">
        <div className="card stack">
          <div>
            <h3>클레임 요약</h3>
            <p>{claim.product_name}</p>
          </div>
          <div className="status-line">
            <Badge tone="neutral">{categoryLabels[claim.category]}</Badge>
            <Badge tone="teal">{statusLabels[claim.status]}</Badge>
            <Badge tone={toneForUrgency(claim.urgency)}>긴급도 {urgencyLabels[claim.urgency]}</Badge>
          </div>
          <div className="summary-list">
            <div className="summary-row">
              <span className="muted">고객명</span>
              <strong>{claim.customer_name}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">접수일</span>
              <strong>{formatDate(claim.created_at)}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">AI 라벨</span>
              <strong>{claim.ai_label ?? "미분류"}</strong>
            </div>
          </div>
          <div>
            <h4>문의 요약</h4>
            <p>{claim.reason_text}</p>
          </div>
        </div>

        <div className="card stack">
          <div>
            <h3>운영 액션</h3>
            <p>상태 변경, AI 재실행, 답변 발송까지 이 화면에서 바로 처리할 수 있습니다.</p>
          </div>
          <div className="actions">
            <button className="button" onClick={() => handleStatusChange("approved")} disabled={!!workingAction}>
              Approve
            </button>
            <button className="button secondary" onClick={() => handleStatusChange("rejected")} disabled={!!workingAction}>
              Reject
            </button>
            <button className="button ghost" onClick={() => handleStatusChange("done")} disabled={!!workingAction}>
              {claim.automation.follow_up_needed ? "Follow-up Done" : "Mark Done"}
            </button>
          </div>
          <div className="actions">
            <button className="button" onClick={handleClassify} disabled={!!workingAction}>
              Re-run Classify
            </button>
            <button className="button secondary" onClick={handleDraftReply} disabled={!!workingAction}>
              Re-generate Reply
            </button>
          </div>
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <div>
            <h3>자동 triage 요약</h3>
            <p>Cafe24 webhook 기반 자동 분류와 답변 초안 준비 상태를 바로 확인합니다.</p>
          </div>
          {claim.automation.auto_triaged ? (
            <>
              <div className="status-line">
                <Badge tone="accent">자동 분류 완료</Badge>
                {claim.automation.reply_ready ? <Badge tone="teal">답변 초안 준비</Badge> : null}
                {claim.automation.reply_sent ? <Badge tone="neutral">답변 발송됨</Badge> : null}
                {claim.automation.follow_up_needed ? <Badge tone="danger">후속 확인 필요</Badge> : null}
                {claim.automation.source_event ? (
                  <Badge tone="neutral">{formatAutomationSourceEvent(claim.automation.source_event)}</Badge>
                ) : null}
              </div>
              <div className="summary-list">
                <div className="summary-row">
                  <span className="muted">자동 처리 시각</span>
                  <strong>{claim.automation.auto_triaged_at ? formatDate(claim.automation.auto_triaged_at) : "-"}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">분류 신뢰도</span>
                  <strong>{formatPercent(claim.automation.classification_confidence)}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">답변 신뢰도</span>
                  <strong>{formatPercent(claim.automation.draft_reply_confidence)}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">답변 발송 시각</span>
                  <strong>{claim.automation.reply_sent_at ? formatDate(claim.automation.reply_sent_at) : "-"}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">답변 담당자</span>
                  <strong>{claim.automation.reply_sent_by ?? "-"}</strong>
                </div>
                <div className="summary-row">
                  <span className="muted">후속 확인</span>
                  <strong>{claim.automation.follow_up_needed ? "필요" : "없음"}</strong>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state inline-state">아직 webhook 기반 자동 triage 이력이 없습니다.</div>
          )}
        </div>

        <div className="card stack">
          <div>
            <h3>고객 메시지 타임라인</h3>
            <p>고객과 운영자, 시스템 메시지를 시간순으로 확인합니다.</p>
          </div>
          <div className="timeline">
            {claim.messages?.map((message) => (
              <div key={message.id} className="timeline-item">
                <strong>{message.role === "customer" ? "고객" : message.role === "system" ? "시스템" : "운영자"}</strong>
                <p>{message.body}</p>
                <p className="muted">{formatDate(message.created_at)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid cols-2">
        <div className="card stack">
          <div>
            <h3>AI 분류</h3>
            <p>가장 최근 분류 결과와 근거입니다.</p>
          </div>
          <div className="summary-list">
            <div className="summary-row">
              <span className="muted">현재 카테고리</span>
              <strong>{categoryLabels[claim.category]}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">AI 라벨</span>
              <strong>{claim.ai_label ?? "미분류"}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">신뢰도</span>
              <strong>{latestClassification ? formatPercent(latestClassification.confidence) : "-"}</strong>
            </div>
          </div>
          <p>{latestClassification?.rationale ?? "아직 분류 이력이 없습니다. Re-run Classify를 실행해 주세요."}</p>
        </div>

        <div className="card stack">
          <div>
            <h3>추천 답변</h3>
            <p>매장 정책을 반영한 답변 초안입니다. 편집 후 바로 발송 처리할 수 있습니다.</p>
          </div>
          <div className="summary-list">
            <div className="summary-row">
              <span className="muted">신뢰도</span>
              <strong>{latestReply ? formatPercent(latestReply.confidence) : "-"}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">편집 상태</span>
              <strong>{isReplyEdited ? "수정됨" : "AI 초안"}</strong>
            </div>
          </div>
          <div className="summary-list">
            <div className="summary-row">
              <span className="muted">발송 채널</span>
              <strong>{formatReplyDeliveryChannel(claim.automation.latest_delivery_channel) ?? "미정"}</strong>
            </div>
            <div className="summary-row">
              <span className="muted">최근 발송 결과</span>
              <strong>{formatReplyDeliveryStatus(claim.automation.latest_delivery_status) ?? "없음"}</strong>
            </div>
          </div>
          <textarea
            className="textarea reply-editor"
            value={replyDraft}
            onChange={(event) => setReplyDraft(event.target.value)}
            placeholder="아직 답변 초안이 없습니다. Re-generate Reply를 먼저 실행해 주세요."
          />
          <p className="muted">{latestReply?.rationale ?? ""}</p>
          <div className="actions">
            <label className="inline-checkbox">
              <input
                type="checkbox"
                checked={closeAfterSend}
                onChange={(event) => setCloseAfterSend(event.target.checked)}
                disabled={!!workingAction}
              />
              <span>발송 후 완료 처리</span>
            </label>
          </div>
          <div className="actions">
            <button className="button" onClick={handleSendReply} disabled={!replyDraft.trim() || !!workingAction}>
              {claim.automation.reply_sent ? "Resend Reply" : closeAfterSend ? "Send Reply + Done" : "Send Reply"}
            </button>
            {claim.automation.can_retry_delivery ? (
              <button className="button secondary" onClick={handleRetryFailedDelivery} disabled={!!workingAction}>
                Retry Failed Delivery
              </button>
            ) : null}
            <button className="button ghost" onClick={handleCopyReply} disabled={!replyDraft.trim() || !!workingAction}>
              Copy Reply
            </button>
            <button
              className="button secondary"
              onClick={handleResetReply}
              disabled={!hasGeneratedReply || !isReplyEdited || !!workingAction}
            >
              Reset To AI Draft
            </button>
          </div>
        </div>
      </section>

      <section className="card stack">
        <div>
          <h3>내부 처리 메모</h3>
          <p>고객에게는 보이지 않는 운영 메모를 남겨 다음 담당자와 공유합니다.</p>
        </div>
        <textarea
          className="textarea reply-editor"
          value={internalNote}
          onChange={(event) => setInternalNote(event.target.value)}
          placeholder="예: 고객이 추가 사진 전달 예정, 오늘 15시 이후 재확인 예정"
        />
        <div className="actions">
          <button className="button secondary" onClick={handleAddInternalNote} disabled={!internalNote.trim() || !!workingAction}>
            Save Internal Note
          </button>
        </div>
      </section>

      <section className="card stack">
        <div>
          <h3>발송 이력</h3>
          <p>각 발송 시도의 채널, 결과, 오류를 확인합니다.</p>
        </div>
        {claim.reply_deliveries && claim.reply_deliveries.length > 0 ? (
          <div className="timeline">
            {claim.reply_deliveries.map((delivery) => (
              <div key={delivery.id} className="timeline-item">
                <div className="actions">
                  <strong>
                    Attempt {delivery.attempt_no} / {formatReplyDeliveryChannel(delivery.channel) ?? delivery.channel}
                  </strong>
                  <Badge tone={toneForDeliveryStatus(delivery.status)}>
                    {formatReplyDeliveryStatus(delivery.status) ?? delivery.status}
                  </Badge>
                </div>
                <p className="timeline-meta">
                  {delivery.destination ?? "-"} / {delivery.actor} / {delivery.sent_at ? formatDate(delivery.sent_at) : "-"}
                </p>
                {delivery.error_message ? <p>{delivery.error_message}</p> : null}
                {delivery.external_delivery_id ? <p className="timeline-meta">Delivery ID: {delivery.external_delivery_id}</p> : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state inline-state">아직 발송 이력이 없습니다.</div>
        )}
      </section>

      <section className="card stack">
        <div>
          <h3>감사 로그</h3>
          <p>분류, 답변 생성, 발송 처리, 상태 변경, 메모 저장 이력을 시간순으로 확인합니다.</p>
        </div>
        <div className="timeline">
          {claim.audit_logs?.map((log) => {
            const payloadText = formatAuditPayload(log.payload_json);

            return (
              <div key={log.id} className="timeline-item">
                <strong>{log.event_type}</strong>
                <p>{log.actor}</p>
                {payloadText ? <p className="timeline-meta">{payloadText}</p> : null}
                <p className="muted">{formatDate(log.created_at)}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
