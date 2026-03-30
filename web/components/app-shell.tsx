"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { API_BASE_URL, apiFetch } from "@/lib/api";
import type { AuthSession } from "@/lib/types";
import { Navigation } from "@/components/navigation";

type AuthContextValue = {
  session: AuthSession;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthSession() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuthSession must be used within AppShell.");
  }
  return value;
}

async function fetchSession(): Promise<AuthSession | null> {
  const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
    credentials: "include",
    cache: "no-store",
  });

  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as AuthSession;
}

function LoginPanel({ onSuccess }: { onSuccess: (session: AuthSession) => void }) {
  const [email, setEmail] = useState("manager@alpha-seller.local");
  const [password, setPassword] = useState("demo1234");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const session = await apiFetch<AuthSession>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      onSuccess(session);
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "로그인에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  const quickAccounts = [
    { label: "알파 매니저", email: "manager@alpha-seller.local" },
    { label: "알파 상담원", email: "agent@alpha-seller.local" },
    { label: "알파 뷰어", email: "viewer@alpha-seller.local" },
    { label: "베타 매니저", email: "manager@beta-select.local" },
  ];

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="stack">
          <div>
            <p className="brand-eyebrow">ClaimMate Access</p>
            <h2>운영자 로그인</h2>
            <p>운영자 계정으로 로그인하면 merchant별 인박스, 정책, 연동 상태만 분리해서 볼 수 있습니다.</p>
          </div>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="stack">
              <span className="muted">Email</span>
              <input className="input" value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="stack">
              <span className="muted">Password</span>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error ? <div className="error-banner">{error}</div> : null}
            <button className="button" type="submit" disabled={submitting}>
              {submitting ? "로그인 중..." : "로그인"}
            </button>
          </form>

          <div className="stack">
            <strong>빠른 데모 계정</strong>
            <div className="toggle-strip">
              {quickAccounts.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  className={`toggle-chip ${email === account.email ? "active" : ""}`}
                  onClick={() => {
                    setEmail(account.email);
                    setPassword("demo1234");
                  }}
                >
                  {account.label}
                </button>
              ))}
            </div>
            <p className="muted">모든 데모 계정 비밀번호는 `demo1234` 입니다.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshSession() {
    setLoading(true);
    setError(null);
    try {
      const nextSession = await fetchSession();
      setSession(nextSession);
    } catch (sessionError) {
      setSession(null);
      setError(sessionError instanceof Error ? sessionError.message : "세션을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await apiFetch<void>("/api/auth/logout", { method: "POST" });
    setSession(null);
  }

  useEffect(() => {
    void refreshSession();
  }, []);

  const contextValue = useMemo(() => {
    if (!session) {
      return null;
    }
    return { session, logout, refreshSession };
  }, [session]);

  if (loading) {
    return <div className="loading-state page-centered">세션을 확인하는 중입니다.</div>;
  }

  if (!session) {
    return (
      <>
        {error ? <div className="error-banner global-banner">{error}</div> : null}
        <LoginPanel
          onSuccess={(nextSession) => {
            setSession(nextSession);
            setError(null);
          }}
        />
      </>
    );
  }

  return (
    <AuthContext.Provider value={contextValue}>
      <div className="app-shell">
        <Navigation />
        <main className="content">{children}</main>
      </div>
    </AuthContext.Provider>
  );
}
