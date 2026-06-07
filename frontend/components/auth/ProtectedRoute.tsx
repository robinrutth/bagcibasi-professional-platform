"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/hooks/useAuth";
import { usePermissions } from "@/hooks/usePermissions";

export function ProtectedRoute({
  children,
  requiredPermission,
}: {
  children: ReactNode;
  requiredPermission?: string;
}) {
  const auth = useAuth();
  const permissions = usePermissions();
  const router = useRouter();

  useEffect(() => {
    if (!auth.ready) return;
    if (!auth.isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (requiredPermission && !permissions.can(requiredPermission)) {
      router.replace("/unauthorized");
    }
  }, [auth.isAuthenticated, auth.ready, permissions, requiredPermission, router]);

  if (!auth.ready) {
    return (
      <main className="centerState">
        <span className="loadingSpinner" aria-label="Yükleniyor" />
      </main>
    );
  }

  if (!auth.isAuthenticated || (requiredPermission && !permissions.can(requiredPermission))) return null;

  return children;
}
