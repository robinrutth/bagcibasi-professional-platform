"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { CarbonTrendChart } from "@/components/dashboard/CarbonTrendChart";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { RecentShipments } from "@/components/dashboard/RecentShipments";
import { TopRoutesTable } from "@/components/dashboard/TopRoutesTable";
import { VehicleEmissionChart } from "@/components/dashboard/VehicleEmissionChart";
import { useAuth } from "@/hooks/useAuth";

export default function DashboardPage() {
  const router = useRouter();
  const auth = useAuth();

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Operasyon kontrol merkezi</p>
          <h1>Dashboard</h1>
        </div>
      </header>
      <KpiCards />
      <section className="dashboardGrid">
        <CarbonTrendChart />
        <VehicleEmissionChart />
        <TopRoutesTable />
        <RecentShipments />
      </section>
    </main>
  );
}
