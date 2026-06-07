"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";
import { useCustomer } from "@/hooks/useCustomers";
import { downloadCarbonReport } from "@/lib/api/documents";

const numberFormat = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });

function formatNumber(value: number) {
  return numberFormat.format(value);
}

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const auth = useAuth();
  const { customer, shipments, carbonStats, loading, error } = useCustomer(params.id);
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Musteri detayi</p>
          <h1>{customer?.name ?? "Musteri"}</h1>
        </div>
        <div className="headerActions">
          <Link className="secondaryButton" href="/customers">
            Musteriler
          </Link>
          <select className="secondaryButton" value={period} onChange={(event) => setPeriod(event.target.value as "monthly" | "yearly")}>
            <option value="monthly">Aylik</option>
            <option value="yearly">Yillik</option>
          </select>
          <button
            className="secondaryButton"
            disabled={downloading}
            onClick={() => {
              setDownloading(true);
              void downloadCarbonReport(params.id, period).finally(() => setDownloading(false));
            }}
          >
            Karbon Raporu Indir
          </button>
        </div>
      </header>

      {error && <div className="errorBanner">{error}</div>}

      <section className="kpiGrid">
        <article className="kpi">
          <span>Toplam CO2</span>
          <strong>{loading ? "..." : `${formatNumber(carbonStats?.total_co2_kg ?? 0)} kg`}</strong>
          <small>Musteri bazli emisyon</small>
        </article>
        <article className="kpi">
          <span>Sevkiyat</span>
          <strong>{loading ? "..." : formatNumber(carbonStats?.shipment_count ?? shipments.length)}</strong>
          <small>Aktif sevkiyat kaydi</small>
        </article>
        <article className="kpi">
          <span>Ortalama CO2</span>
          <strong>{loading ? "..." : `${formatNumber(carbonStats?.average_co2_kg ?? 0)} kg`}</strong>
          <small>Sevkiyat basina</small>
        </article>
        <article className="kpi">
          <span>Risk</span>
          <strong>{customer?.risk_level ?? "-"}</strong>
          <small>{customer?.is_active ? "Aktif musteri" : "Pasif musteri"}</small>
        </article>
      </section>

      <section className="gridTwo">
        <article className="panel">
          <div className="sectionHead">
            <h2>Iletisim</h2>
            <span>{customer?.city ?? "-"}</span>
          </div>
          <div className="detailList">
            <span>E-posta</span>
            <strong>{customer?.email ?? "-"}</strong>
            <span>Telefon</span>
            <strong>{customer?.phone ?? "-"}</strong>
            <span>Vergi No</span>
            <strong>{customer?.tax_number ?? "-"}</strong>
            <span>Adres</span>
            <strong>{customer?.address ?? "-"}</strong>
          </div>
        </article>
        <article className="panel">
          <div className="sectionHead">
            <h2>Karbon Dagilimi</h2>
            <span>Arac tipi</span>
          </div>
          <div className="vehicleList">
            {(carbonStats?.by_vehicle ?? []).map((item) => (
              <article key={item.vehicle_type}>
                <div className="vehicleMeta">
                  <strong>{item.vehicle_type}</strong>
                  <span>{formatNumber(item.co2)} kg</span>
                </div>
              </article>
            ))}
            {carbonStats?.by_vehicle.length === 0 && <div className="emptyState">Karbon verisi yok.</div>}
          </div>
        </article>
      </section>

      <section className="panel tablePanel">
        <div className="sectionHead">
          <h2>Musteriye Ait Sevkiyat Listesi</h2>
          <span>{shipments.length} kayit</span>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Rota</th>
                <th>Yuk</th>
                <th>Tarih</th>
                <th>Arac</th>
                <th>CO2</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {shipments.map((shipment) => (
                <tr key={shipment.id}>
                  <td>
                    {shipment.origin} - {shipment.destination}
                  </td>
                  <td>
                    {shipment.cargo_type} / {formatNumber(shipment.tonnage)} ton
                  </td>
                  <td>{shipment.delivery_date}</td>
                  <td>{shipment.vehicle_type}</td>
                  <td>{formatNumber(shipment.co2_kg)} kg</td>
                  <td>{shipment.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {shipments.length === 0 && !loading && <div className="emptyState">Bu musteri icin sevkiyat bulunamadi.</div>}
      </section>
    </main>
  );
}
