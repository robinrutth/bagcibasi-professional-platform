"use client";

import Link from "next/link";

import { TableSkeleton } from "@/components/dashboard/Skeleton";
import { formatNumber, statusClass, vehicleLabel } from "@/components/dashboard/format";
import { useShipments } from "@/hooks/useShipments";

export function RecentShipments() {
  const { shipments, loading, error } = useShipments({ limit: 5 });

  return (
    <section className="panel tablePanel dashboardWide">
      <div className="sectionHead">
        <h2>Son Sevkiyatlar</h2>
        <Link className="miniButton" href="/shipments">
          Tümünü Gör
        </Link>
      </div>
      {error && <div className="errorBanner">{error}</div>}
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Müşteri</th>
              <th>Rota</th>
              <th>Araç</th>
              <th>CO2</th>
              <th>Durum</th>
            </tr>
          </thead>
          {loading ? (
            <TableSkeleton rows={6} columns={6} />
          ) : (
            <tbody>
              {shipments.slice(0, 5).map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.id.slice(0, 8)}</td>
                  <td>{shipment.customer_name}</td>
                  <td>
                    {shipment.origin} - {shipment.destination}
                  </td>
                  <td>{vehicleLabel(shipment.vehicle_type)}</td>
                  <td>{formatNumber(shipment.co2_kg)} kg</td>
                  <td>
                    <span className={`badge ${statusClass(shipment.status)}`}>{shipment.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
      {shipments.length === 0 && !loading && <div className="emptyState">Gösterilecek sevkiyat bulunamadı.</div>}
    </section>
  );
}
