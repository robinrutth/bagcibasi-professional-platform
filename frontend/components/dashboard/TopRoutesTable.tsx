"use client";

import { useEffect, useState } from "react";

import { TableSkeleton } from "@/components/dashboard/Skeleton";
import { emissionClass, emissionLabel, formatNumber, vehicleLabel } from "@/components/dashboard/format";
import { getTopCarbonRoutes } from "@/lib/api/carbon";
import type { CarbonRoute } from "@/types";

export function TopRoutesTable() {
  const [routes, setRoutes] = useState<CarbonRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getTopCarbonRoutes()
      .then((response) => {
        if (mounted) setRoutes(response);
      })
      .catch((requestError: unknown) => {
        if (mounted) setError(requestError instanceof Error ? requestError.message : "Rota verisi yüklenemedi.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="panel tablePanel">
      <div className="sectionHead">
        <h2>En Kirletici Rotalar</h2>
        <span>{loading ? "Yükleniyor" : `${routes.length} rota`}</span>
      </div>
      {error && <div className="errorBanner">{error}</div>}
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Rota</th>
              <th>Araç Tipi</th>
              <th>CO2</th>
              <th>Emisyon Etiketi</th>
            </tr>
          </thead>
          {loading ? (
            <TableSkeleton rows={5} columns={4} />
          ) : (
            <tbody>
              {routes.map((route) => {
                const label = emissionLabel(route.co2);
                return (
                  <tr key={`${route.origin}-${route.destination}`}>
                    <td>
                      {route.origin} - {route.destination}
                    </td>
                    <td>{vehicleLabel(route.vehicle_type ?? "-")}</td>
                    <td>{formatNumber(route.co2)} kg</td>
                    <td>
                      <span className={`badge ${emissionClass(route.co2)}`}>{label}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </div>
      {routes.length === 0 && !loading && <div className="emptyState">Rota verisi bulunamadı.</div>}
    </section>
  );
}
