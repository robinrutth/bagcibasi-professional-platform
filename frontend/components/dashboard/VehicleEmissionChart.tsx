"use client";

import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Legend } from "recharts";

import { Skeleton } from "@/components/dashboard/Skeleton";
import { formatNumber, vehicleLabel } from "@/components/dashboard/format";
import { getCarbonByVehicle } from "@/lib/api/carbon";
import type { CarbonVehicleDistribution } from "@/types";

const colors = ["#16a34a", "#0f766e", "#65a30d", "#2563eb", "#ca8a04", "#dc2626"];

export function VehicleEmissionChart() {
  const [data, setData] = useState<CarbonVehicleDistribution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getCarbonByVehicle()
      .then((response) => {
        if (mounted) setData(response);
      })
      .catch((requestError: unknown) => {
        if (mounted) setError(requestError instanceof Error ? requestError.message : "Araç dağılımı yüklenemedi.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="panel chartPanel">
      <div className="sectionHead">
        <h2>Araç Tipi Dağılımı</h2>
        <span>{loading ? "Yükleniyor" : `${data.length} tip`}</span>
      </div>
      {error && <div className="errorBanner">{error}</div>}
      {loading ? (
        <div className="chartSkeleton">
          <Skeleton />
        </div>
      ) : data.length === 0 ? (
        <div className="emptyState">Araç tipi için emisyon verisi yok.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie data={data} dataKey="co2" nameKey="vehicle_type" innerRadius={70} outerRadius={112} paddingAngle={3}>
              {data.map((entry, index) => (
                <Cell key={entry.vehicle_type} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => [`${formatNumber(Number(value))} kg`, "CO2"]} labelFormatter={(label) => vehicleLabel(String(label))} />
            <Legend formatter={(value) => vehicleLabel(String(value))} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
