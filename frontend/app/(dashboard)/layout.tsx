"use client";

import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/DashboardShell";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <DashboardShell eyebrow="Vorxa" title="">
      {children}
    </DashboardShell>
  );
}
