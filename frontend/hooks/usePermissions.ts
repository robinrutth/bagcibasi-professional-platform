"use client";

import { useMemo } from "react";

import { useAuth } from "@/hooks/useAuth";
import { getRoleFromJwt, hasPermission, type Role } from "@/lib/permissions";

export function usePermissions() {
  const { accessToken, role: authRole, user } = useAuth();
  const role = useMemo<Role | null>(() => authRole ?? getRoleFromJwt(accessToken), [accessToken, authRole]);
  const effectiveRole = role ?? (user?.role as Role | undefined) ?? null;

  return useMemo(
    () => ({
      role: effectiveRole,
      can: (permission: string) => hasPermission(effectiveRole, permission),
      canAny: (permissions: string[]) => permissions.some((permission) => hasPermission(effectiveRole, permission)),
      canAll: (permissions: string[]) => permissions.every((permission) => hasPermission(effectiveRole, permission)),
    }),
    [effectiveRole],
  );
}
