"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/inbox", label: "Inbox" },
  { href: "/integrations/cafe24", label: "Cafe24" },
  { href: "/settings/policy", label: "Policy" },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-eyebrow">Cafe24 Ops</span>
        <h1>ClaimMate AI</h1>
        <p>취소, 교환, 반품, 환불, 배송 문의를 한 곳에서 빠르게 정리하는 로컬 MVP입니다.</p>
      </div>

      <nav className="nav-links">
        {links.map((link) => {
          const active = pathname.startsWith(link.href);
          return (
            <Link key={link.href} href={link.href} className={`nav-link ${active ? "active" : ""}`}>
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
