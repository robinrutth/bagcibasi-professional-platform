"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { TableSkeleton } from "@/components/dashboard/Skeleton";
import { emissionClass, emissionLabel, formatNumber, vehicleLabel } from "@/components/dashboard/format";
import { useAuth } from "@/hooks/useAuth";
import { useCarbonSummary } from "@/hooks/useCarbon";
import { useCustomers } from "@/hooks/useCustomers";
import { useShipments } from "@/hooks/useShipments";
import { exportCarbonExcel, exportCarbonPdf, exportShipmentsCSV, exportShipmentsExcel } from "@/lib/api/exports";
import type { ShipmentExportFilters } from "@/types";

function defaultStartDate() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

function defaultEndDate() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const router = useRouter();
  const auth = useAuth();
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(defaultEndDate);
  const [vehicleType, setVehicleType] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [exporting, setExporting] = useState<"csv" | "excel" | "carbon" | "cbam_pdf" | null>(null);
  const { shipments, loading: shipmentsLoading, error: shipmentsError } = useShipments({ limit: 100, customer_id: customerId || undefined });
  const { customers, loading: customersLoading } = useCustomers({ limit: 100, is_active: true });
  const { summary, loading: summaryLoading, error: summaryError } = useCarbonSummary({ start_date: startDate, end_date: endDate });

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  const vehicleOptions = useMemo(() => Array.from(new Set(shipments.map((shipment) => shipment.vehicle_type))).sort(), [shipments]);
  const filteredShipments = useMemo(
    () =>
      shipments.filter((shipment) => {
        const deliveryDate = shipment.delivery_date.slice(0, 10);
        const matchesDate = (!startDate || deliveryDate >= startDate) && (!endDate || deliveryDate <= endDate);
        const matchesVehicle = !vehicleType || shipment.vehicle_type === vehicleType;
        return matchesDate && matchesVehicle;
      }),
    [endDate, shipments, startDate, vehicleType],
  );
  const filteredCo2 = filteredShipments.reduce((total, shipment) => total + shipment.co2_kg, 0);
  const filteredAverage = filteredShipments.length > 0 ? filteredCo2 / filteredShipments.length : 0;
  const loading = shipmentsLoading || customersLoading || summaryLoading;
  const error = shipmentsError ?? summaryError;
  const exportFilters: ShipmentExportFilters = {
    start_date: startDate,
    end_date: endDate,
    vehicle_type: vehicleType || undefined,
    customer_id: customerId || undefined,
  };

  async function runExport(type: "csv" | "excel" | "carbon" | "cbam_pdf") {
    setExporting(type);
    try {
      if (type === "csv") await exportShipmentsCSV(exportFilters);
      if (type === "excel") await exportShipmentsExcel(exportFilters);
      if (type === "carbon") await exportCarbonExcel("monthly", customerId || undefined);
      if (type === "cbam_pdf") await exportCarbonPdf("monthly", customerId || undefined);
    } finally {
      setExporting(null);
    }
  }

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Karbon ve operasyon raporlama</p>
          <h1>Raporlar</h1>
        </div>
      </header>
      {error && <div className="errorBanner">{error}</div>}
      <section className="panel reportFilters">
        <label>
          <span>Baslangic</span>
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label>
          <span>Bitis</span>
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
        <label>
          <span>Arac Tipi</span>
          <select value={vehicleType} onChange={(event) => setVehicleType(event.target.value)}>
            <option value="">Tum araclar</option>
            {vehicleOptions.map((option) => (
              <option value={option} key={option}>
                {vehicleLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Musteri</span>
          <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
            <option value="">Tum musteriler</option>
            {customers.map((customer) => (
              <option value={customer.id} key={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </label>
        <div className="reportActions">
          <button className="secondaryButton" type="button" disabled={Boolean(exporting)} onClick={() => void runExport("cbam_pdf")}>
            {exporting === "cbam_pdf" ? <span className="tinySpinner" aria-label="Indiriliyor" /> : "ISO 14083 PDF"}
          </button>
          <button className="secondaryButton" type="button" disabled={Boolean(exporting)} onClick={() => void runExport("csv")}>
            {exporting === "csv" ? <span className="tinySpinner" aria-label="Indiriliyor" /> : "CSV indir"}
          </button>
          <button className="secondaryButton" type="button" disabled={Boolean(exporting)} onClick={() => void runExport("excel")}>
            {exporting === "excel" ? <span className="tinySpinner" aria-label="Indiriliyor" /> : "Excel indir"}
          </button>
          <button
            className="secondaryButton"
            style={{ background: "#16a34a", color: "#fff", padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer", fontWeight: 600 }}
            type="button"
            disabled={Boolean(exporting)}
            onClick={() => void runExport("carbon")}
          >
            {exporting === "carbon" ? <span className="tinySpinner" aria-label="Indiriliyor" /> : "CBAM Raporu (Excel)"}
          </button>
        </div>
      </section>

      <section className="kpiGrid">
        <article className="kpi">
          <span>Filtrelenmis CO2</span>
          <strong>{loading ? "..." : `${formatNumber(filteredCo2)} kg`}</strong>
          <small>Sevkiyat bazli hesap</small>
        </article>
        <article className="kpi">
          <span>Sevkiyat Sayisi</span>
          <strong>{loading ? "..." : formatNumber(filteredShipments.length)}</strong>
          <small>Secili aralik</small>
        </article>
        <article className="kpi">
          <span>Ortalama CO2</span>
          <strong>{loading ? "..." : `${formatNumber(filteredAverage)} kg`}</strong>
          <small className={`badge ${emissionClass(filteredAverage)}`}>{emissionLabel(filteredAverage)}</small>
        </article>
        <article className="kpi">
          <span>API Toplam CO2</span>
          <strong>{summaryLoading ? "..." : `${formatNumber(summary.total_co2)} kg`}</strong>
          <small>Tarih araligi ozeti</small>
        </article>
      </section>

      <section className="panel tablePanel">
        <div className="sectionHead">
          <h2>Filtrelenmis CO2 Ozeti</h2>
          <span>{loading ? "Yukleniyor" : `${filteredShipments.length} kayit`}</span>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Musteri</th>
                <th>Rota</th>
                <th>Arac</th>
                <th>Tarih</th>
                <th>CO2</th>
                <th>Etiket</th>
              </tr>
            </thead>
            {loading ? (
              <TableSkeleton rows={8} columns={6} />
            ) : (
              <tbody>
                {filteredShipments.map((shipment) => (
                  <tr key={shipment.id}>
                    <td>{shipment.customer_name}</td>
                    <td>
                      {shipment.origin} - {shipment.destination}
                    </td>
                    <td>{vehicleLabel(shipment.vehicle_type)}</td>
                    <td>{shipment.delivery_date}</td>
                    <td>{formatNumber(shipment.co2_kg)} kg</td>
                    <td>
                      <span className={`badge ${emissionClass(shipment.co2_kg)}`}>{emissionLabel(shipment.co2_kg)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </div>
        {filteredShipments.length === 0 && !loading && <div className="emptyState">Filtreye uygun veri bulunamadi.</div>}
      </section>
    </main>
  );
}
