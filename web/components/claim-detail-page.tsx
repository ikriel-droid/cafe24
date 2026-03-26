"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Claim, ClaimStatus, ClassificationResponse, DraftReplyResponse, SuggestedAction } from "@/lib/types";
import { Badge, categoryLabels, formatDate, statusLabels, urgencyLabels } from "@/components/ui";

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

export function ClaimDetailPage({ claimId }: { claimId: string }) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [internalNote, setInternalNote] = useState("");
  const [workingAction, setWorkingAction] = useState<string | null>(null);
  const [replyDraft, setReplyDraft] = useState("");

  async function loadClaim() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Claim>(`/api/claims/${claimId}`);
      setClaim(data);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "상세 정보를 불러오지 못했습니다.");
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
      setError(actionError instanceof Error ? actionError.message : "분류에 실패했습니다.");
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
      setNotice("답변 초안을 새로 생성했습니다.");
    } catch (actionError) {
      setNotice(null);
      setError(actionError instanceof Error ? actionError.message : "답변 생성에 실패했습니다.");
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleCopyReply() {
    if (!replyDraft.trim()) {
      setNotice(null);
      setError("복사할 답변 초안이 없습니다. 먼저 Re-generate Reply를 실행하거나 내용을 입력해 주세요.");
      return;
    }

    try {
      await copyText(replyDraft.trim());
      setError(null);
      setNotice("현재 편집 중인 답변 초안을 클립보드에 복사했습니다.");
    } catch (copyError) {
      setNotice(null);
      setError(copyError instanceof Error ? copyError.message : "답변 초안 복사에 실패했습니다.");
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

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  if (loading) {
    return <div className="loading-state">클레임 상세를 불러오는 중입니다.</div>;
  }

  if (error && !claim) {
    return <div className="error-state">{error}</div>;
  }

  if (!claim) {
    return <div className="empty-state">클레임을 찾을 수 없습니다.</div>;
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <Link href="/inbox" className="muted">
            ← Inbox
          </Link>
          <h2>{claim.order_no}</h2>
          <p>{claim.customer_name} 고객 문의를 요약, 분류, 답변 초안 기준으로 확인합니다.</p>
        </div>
      </header>

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
            <Badge tone={claim.urgency === "high" ? "danger" : claim.urgency === "medium" ? "accent" : "teal"}>
              긴급도 {urgencyLabels[claim.urgency]}
            </Badge>
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
            <h3>액션</h3>
            <p>상태 변경과 AI 재실행을 이 화면에서 바로 처리합니다.</p>
          </div>
          <div className="actions">
            <button className="button" onClick={() => handleStatusChange("approved")} disabled={!!workingAction}>
              Approve
            </button>
            <button className="button secondary" onClick={() => handleStatusChange("rejected")} disabled={!!workingAction}>
              Reject
            </button>
            <button className="button ghost" onClick={() => handleStatusChange("done")} disabled={!!workingAction}>
              Mark Done
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
            <p>Cafe24 mock webhook으로 자동 분류와 초안 생성이 되었는지 바로 확인합니다.</p>
          </div>
          {claim.automation.auto_triaged ? (
            <>
              <div className="status-line">
                <Badge tone="accent">자동 분류 완료</Badge>
                {claim.automation.reply_ready ? <Badge tone="teal">답변 초안 준비</Badge> : null}
                {claim.automation.source_event ? <Badge tone="neutral">{claim.automation.source_event}</Badge> : null}
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
              </div>
            </>
          ) : (
            <div className="empty-state inline-state">아직 webhook 기반 자동 triage 이력은 없습니다.</div>
          )}
        </div>

        <div className="card stack">
          <div>
            <h3>고객 메시지 타임라인</h3>
            <p>고객과 운영자 메시지를 시간순으로 확인합니다.</p>
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
            <p>판매자 정책을 반영한 답변 초안입니다.</p>
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
          <textarea
            className="textarea reply-editor"
            value={replyDraft}
            onChange={(event) => setReplyDraft(event.target.value)}
            placeholder="아직 답변 초안이 없습니다. Re-generate Reply를 실행해 주세요."
          />
          <p className="muted">{latestReply?.rationale ?? ""}</p>
          <div className="actions">
            <button className="button ghost" onClick={handleCopyReply} disabled={!replyDraft.trim() || !!workingAction}>
              Copy Reply
            </button>
            <button className="button secondary" onClick={handleResetReply} disabled={!hasGeneratedReply || !isReplyEdited || !!workingAction}>
              Reset To AI Draft
            </button>
          </div>
        </div>
      </section>

      <section className="card stack">
        <div>
          <h3>내부 처리 메모</h3>
          <p>고객에게 보이지 않는 운영 메모를 남겨 다음 담당자와 공유합니다.</p>
        </div>
        <textarea
          className="textarea reply-editor"
          value={internalNote}
          onChange={(event) => setInternalNote(event.target.value)}
          placeholder="예: 고객이 파손 사진 추가 전달 예정, 오늘 15시 이후 재회신"
        />
        <div className="actions">
          <button className="button secondary" onClick={handleAddInternalNote} disabled={!internalNote.trim() || !!workingAction}>
            Save Internal Note
          </button>
        </div>
      </section>

      <section className="card stack">
        <div>
          <h3>감사 로그</h3>
          <p>분류, 답변 생성, 상태 변경, 메모 저장 이력을 추적합니다.</p>
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
