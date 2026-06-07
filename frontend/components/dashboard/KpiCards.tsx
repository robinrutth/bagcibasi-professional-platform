"use client";

import { useMemo } from "react";

import { Skeleton } from "@/components/dashboard/Skeleton";
import { emissionClass, emissionLabel, formatNumber } from "@/components/dashboard/format";
import { useCarbonSummary } from "@/hooks/useCarbon";
import { useCustomers } from "@/hooks/useCustomers";
import { useShipments } from "@/hooks/useShipments";

function currentMonthRange(offset = 0) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const end = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  };
}

function trendPercent(current: number, previous: number) {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

function KpiCard({
  icon,
  title,
  value,
  detail,
  trend,
  loading,
  badge,
}: {
  icon: string;
  title: string;
  value: string;
  detail: string;
  trend?: number;
  loading: boolean;
  badge?: "success" | "warning" | "danger";
}) {
  const isPositive = (trend ?? 0) >= 0;
  return (
    <article className="kpi kpiCard">
      <div className="kpiTop">
        <span className="kpiIcon">{icon}</span>
        {trend !== undefined && !loading && (
          <small className={`trend ${isPositive ? "trendUp" : "trendDown"}`}>{isPositive ? "↑" : "↓"} {formatNumber(Math.abs(trend))}%</small>
        )}
      </div>
      <span>{title}</span>
      {loading ? <Skeleton className="skeletonValue" /> : <strong>{value}</strong>}
      {loading ? <Skeleton className="skeletonText" /> : <small className={badge ? `badge ${badge}` : undefined}>{detail}</small>}
      {!loading && title === "Bu Ay CO2" && (
        <span
          style={{
            color: "#16a34a",
            fontSize: 12,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          ↓ Önceki aya göre daha iyi
        </span>
      )}
    </article>
  );
}

export function KpiCards() {
  const { shipments, pagination, loading: shipmentsLoading } = useShipments({ limit: 100 });
  const { pagination: customerPagination, loading: customersLoading } = useCustomers({ limit: 1, is_active: true });
  const { summary: currentMonth, loading: currentLoading } = useCarbonSummary(currentMonthRange());
  const { summary: previousMonth, loading: previousLoading } = useCarbonSummary(currentMonthRange(-1));

  const activeShipmentCount = useMemo(
    () => shipments.filter((shipment) => !shipment.status.toLocaleLowerCase("tr-TR").includes("teslim")).length,
    [shipments],
  );
  const averageEmission = activeShipmentCount > 0 ? currentMonth.total_co2 / activeShipmentCount : 0;
  const percent = trendPercent(currentMonth.total_co2, previousMonth.total_co2);

  return (
    <section className="kpiGrid">
      <KpiCard
        icon="S"
        title="Aktif Sevkiyat"
        value={formatNumber(activeShipmentCount)}
        detail={`${formatNumber(pagination.total)} toplam kayıt`}
        loading={shipmentsLoading}
      />
      <KpiCard
        icon="CO2"
        title="Bu Ay CO2"
        value={`${formatNumber(currentMonth.total_co2)} kg`}
        detail="Önceki aya göre"
        trend={percent}
        loading={currentLoading || previousLoading}
      />
      <KpiCard
        icon="E"
        title="Ortalama Etiket"
        value={emissionLabel(averageEmission)}
        detail={`${formatNumber(averageEmission)} kg / aktif`}
        badge={emissionClass(averageEmission) as "success" | "warning" | "danger"}
        loading={shipmentsLoading || currentLoading}
      />
      <KpiCard
        icon="M"
        title="Aktif Müşteri"
        value={formatNumber(customerPagination.total)}
        detail="CRM kaydı"
        loading={customersLoading}
      />
    </section>
  );
}
