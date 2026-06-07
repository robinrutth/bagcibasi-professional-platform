"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Skeleton } from "@/components/dashboard/Skeleton";
import { formatNumber } from "@/components/dashboard/format";
import { useCarbonTrend } from "@/hooks/useCarbon";

type Period = "daily" | "weekly" | "monthly";

const periods: Array<{ value: Period; label: string }> = [
  { value: "daily", label: "Günlük" },
  { value: "weekly", label: "Haftalık" },
  { value: "monthly", label: "Aylık" },
];

export function CarbonTrendChart() {
  const [period, setPeriod] = useState<Period>("weekly");
  const { trend, loading, error } = useCarbonTrend(period);

  return (
    <section className="panel chartPanel">
      <div className="sectionHead">
        <h2>CO2 Trend</h2>
        <div className="segmentedControl" aria-label="Trend periyodu">
          {periods.map((item) => (
            <button className={period === item.value ? "active" : undefined} key={item.value} onClick={() => setPeriod(item.value)}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="errorBanner">{error}</div>}
      {loading ? (
        <div className="chartSkeleton">
          <Skeleton />
        </div>
      ) : trend.length === 0 ? (
        <div className="emptyState">Trend için henüz veri yok.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={trend} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#dce6e1" strokeDasharray="3 3" />
            <XAxis dataKey="period" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} tickFormatter={(value) => formatNumber(Number(value))} />
            <Tooltip formatter={(value) => [`${formatNumber(Number(value))} kg`, "CO2"]} labelFormatter={(label) => `Tarih: ${label}`} />
            <Line type="monotone" dataKey="co2" stroke="#16a34a" strokeWidth={3} dot={{ r: 4, fill: "#16a34a" }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
