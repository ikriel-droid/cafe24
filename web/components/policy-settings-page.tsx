"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Policy } from "@/lib/types";

type PolicyForm = {
  exchange_window_days: number;
  return_window_days: number;
  return_shipping_fee: number;
  exchange_shipping_fee: number;
  refund_rule_text: string;
  exception_rule_text: string;
};

const emptyForm: PolicyForm = {
  exchange_window_days: 7,
  return_window_days: 7,
  return_shipping_fee: 3500,
  exchange_shipping_fee: 6000,
  refund_rule_text: "",
  exception_rule_text: "",
};

export function PolicySettingsPage() {
  const [form, setForm] = useState<PolicyForm>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPolicy() {
      setLoading(true);
      setError(null);
      try {
        const policy = await apiFetch<Policy>("/api/policy");
        if (!cancelled) {
          setForm({
            exchange_window_days: policy.exchange_window_days,
            return_window_days: policy.return_window_days,
            return_shipping_fee: policy.return_shipping_fee,
            exchange_shipping_fee: policy.exchange_shipping_fee,
            refund_rule_text: policy.refund_rule_text,
            exception_rule_text: policy.exception_rule_text,
          });
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "정책을 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadPolicy();
    return () => {
      cancelled = true;
    };
  }, []);

  function updateField<K extends keyof PolicyForm>(field: K, value: PolicyForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);

    try {
      await apiFetch<Policy>("/api/policy", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setMessage("정책을 저장했습니다.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "정책 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div>
          <h2>Merchant Policy</h2>
          <p>AI 답변 초안이 참고하는 교환, 반품, 환불 정책을 이 화면에서 수정합니다.</p>
        </div>
      </header>

      <section className="card">
        {loading ? <div className="loading-state">정책을 불러오는 중입니다.</div> : null}
        {error ? <div className="error-state">{error}</div> : null}

        {!loading ? (
          <form className="stack" onSubmit={handleSubmit}>
            <div className="grid cols-2">
              <div className="stack">
                <label htmlFor="exchange_window_days">교환 가능 기간(일)</label>
                <input
                  id="exchange_window_days"
                  type="number"
                  value={form.exchange_window_days}
                  onChange={(event) => updateField("exchange_window_days", Number(event.target.value))}
                />
              </div>
              <div className="stack">
                <label htmlFor="return_window_days">반품 가능 기간(일)</label>
                <input
                  id="return_window_days"
                  type="number"
                  value={form.return_window_days}
                  onChange={(event) => updateField("return_window_days", Number(event.target.value))}
                />
              </div>
              <div className="stack">
                <label htmlFor="return_shipping_fee">반품 배송비</label>
                <input
                  id="return_shipping_fee"
                  type="number"
                  value={form.return_shipping_fee}
                  onChange={(event) => updateField("return_shipping_fee", Number(event.target.value))}
                />
              </div>
              <div className="stack">
                <label htmlFor="exchange_shipping_fee">교환 배송비</label>
                <input
                  id="exchange_shipping_fee"
                  type="number"
                  value={form.exchange_shipping_fee}
                  onChange={(event) => updateField("exchange_shipping_fee", Number(event.target.value))}
                />
              </div>
            </div>

            <div className="stack">
              <label htmlFor="refund_rule_text">환불 정책</label>
              <textarea
                id="refund_rule_text"
                className="textarea"
                value={form.refund_rule_text}
                onChange={(event) => updateField("refund_rule_text", event.target.value)}
              />
            </div>

            <div className="stack">
              <label htmlFor="exception_rule_text">예외 처리 정책</label>
              <textarea
                id="exception_rule_text"
                className="textarea"
                value={form.exception_rule_text}
                onChange={(event) => updateField("exception_rule_text", event.target.value)}
              />
            </div>

            <div className="actions">
              <button className="button" type="submit" disabled={saving}>
                Save Policy
              </button>
              {message ? <span className="muted">{message}</span> : null}
            </div>
          </form>
        ) : null}
      </section>
    </div>
  );
}
