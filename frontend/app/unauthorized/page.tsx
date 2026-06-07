"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { usePermissions } from "@/hooks/usePermissions";
import { hasPermission, type Role } from "@/lib/permissions";

type AccessiblePage = {
  href: string;
  label: string;
  permission: string;
  allowedRoles?: Role[];
};

const accessiblePages: AccessiblePage[] = [
  { href: "/dashboard", label: "Dashboard", permission: "shipments.read" },
  { href: "/", label: "Sevkiyatlar", permission: "shipments.read" },
  { href: "/customers", label: "Müşteriler", permission: "customers.read" },
  { href: "/reports", label: "Raporlar", permission: "reports.read", allowedRoles: ["admin", "manager", "viewer"] },
  { href: "/settings", label: "Ayarlar", permission: "settings.read" },
];

export default function UnauthorizedPage() {
  const router = useRouter();
  const { role } = usePermissions();
  const pages = accessiblePages.filter((page) => hasPermission(role, page.permission) || (role ? page.allowedRoles?.includes(role) : false));

  return (
    <main className="loginPage">
      <section className="loginCard">
        <p className="eyebrow">Erişim engellendi</p>
        <h1>Bu sayfa için yetkiniz yok</h1>
        <p className="panelNote">
          Mevcut rolünüz {role ?? "bilinmiyor"}. Frontend sizi doğru alana yönlendirir; asıl yetki kontrolü backend tarafında korunur.
        </p>
        <div className="userList">
          {pages.map((page) => (
            <Link className="secondaryButton" href={page.href} key={page.href}>
              {page.label}
            </Link>
          ))}
        </div>
        {pages.length === 0 && <div className="emptyState">Bu rol için görüntülenebilir sayfa bulunamadı.</div>}
        <button className="wideButton" onClick={() => router.back()}>
          Geri dön
        </button>
      </section>
    </main>
  );
}
