"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/hooks/useAuth";
import { usePermissions } from "@/hooks/usePermissions";
import type { Role } from "@/lib/permissions";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  permission: string;
  allowedRoles?: Role[];
};

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Kontrol Paneli", icon: "D", permission: "shipments.read" },
  { href: "/shipments", label: "Sevkiyatlar", icon: "S", permission: "shipments.read" },
  { href: "/vehicles", label: "Filo", icon: "F", permission: "vehicles.read", allowedRoles: ["admin", "manager", "driver", "viewer"] },
  { href: "/customers", label: "Müşteriler", icon: "C", permission: "customers.read" },
  { href: "/reports", label: "Raporlar", icon: "R", permission: "reports.read", allowedRoles: ["admin", "manager", "viewer"] },
  { href: "/settings", label: "Ayarlar", icon: "A", permission: "settings.read" },
];

export function DashboardShell({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  const auth = useAuth();
  const permissions = usePermissions();
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await auth.logout();
    router.replace("/login");
  }

  return (
    <main className="appShell">
      <aside className="appSidebar">
        <Link className="brand sidebarBrand" href="/dashboard">
          <div className="brandMark">BL</div>
          <div>
            <strong>Bağcıbaşı</strong>
            <span>Green Logistics</span>
          </div>
        </Link>
        <nav className="sideNav" aria-label="Ana navigasyon">
          {navItems
            .filter((item) => permissions.can(item.permission) || (permissions.role ? item.allowedRoles?.includes(permissions.role) : false))
            .map((item) => (
              <Link
                className={pathname.startsWith(item.href) && item.href !== "/dashboard" ? "active" : pathname === item.href ? "active" : undefined}
                href={item.href}
                key={item.href}
              >
                <span className="navIcon">{item.icon}</span>
                {item.label}
              </Link>
            ))}
        </nav>
      </aside>
      <section className="appMain">
        <header className="dashboardHeader">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
          </div>
          <div className="headerUser">
            <span>{auth.user?.full_name ?? auth.user?.username}</span>
            <button className="secondaryButton" onClick={() => void logout()}>
              Çıkış Yap
            </button>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}
