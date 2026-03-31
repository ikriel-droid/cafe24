"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthSession } from "@/components/app-shell";
import type { OperatorRole } from "@/lib/types";

const roleLabels: Record<OperatorRole, string> = {
  manager: "매니저",
  agent: "상담사",
  viewer: "뷰어",
};

const links: Array<{
  href: string;
  label: string;
  allowedRoles?: OperatorRole[];
}> = [
  { href: "/dashboard", label: "대시보드" },
  { href: "/inbox", label: "인박스" },
  { href: "/integrations/cafe24", label: "Cafe24 연동", allowedRoles: ["manager"] },
  { href: "/settings/policy", label: "정책 설정", allowedRoles: ["manager"] },
  { href: "/admin/diagnostics", label: "운영 진단", allowedRoles: ["manager"] },
];

function canAccess(role: OperatorRole, allowedRoles?: OperatorRole[]) {
  return !allowedRoles || allowedRoles.includes(role);
}

export function Navigation() {
  const pathname = usePathname();
  const { session, logout } = useAuthSession();

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-eyebrow">Cafe24 Ops</span>
        <h1>ClaimMate AI</h1>
        <p>취소, 교환, 반품, 환불, 배송 문의를 한 화면에서 분류하고 처리하는 운영 워크스페이스입니다.</p>
      </div>

      <div className="sidebar-session">
        <div className="sidebar-session-top">
          <strong>{session.name}</strong>
          <span className="sidebar-role">{roleLabels[session.role]}</span>
        </div>
        <p>{session.merchant.mall_name}</p>
        <p className="sidebar-helper">{session.email}</p>
      </div>

      <nav className="nav-links">
        {links
          .filter((link) => canAccess(session.role, link.allowedRoles))
          .map((link) => {
            const active = pathname.startsWith(link.href);
            return (
              <Link key={link.href} href={link.href} className={`nav-link ${active ? "active" : ""}`}>
                {link.label}
              </Link>
            );
          })}
      </nav>

      <div className="sidebar-actions">
        <button className="button ghost" type="button" onClick={() => void logout()}>
          로그아웃
        </button>
        <p className="sidebar-footnote">
          {session.role === "viewer"
            ? "뷰어 권한은 읽기 전용입니다."
            : session.role === "agent"
              ? "상담사 권한은 클레임 처리와 답변 발송까지 가능합니다."
              : "매니저 권한은 정책과 Cafe24 연동 설정, 운영 진단까지 관리할 수 있습니다."}
        </p>
      </div>
    </aside>
  );
}
