"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AiAnalysisPanel } from "@/components/AiAnalysisPanel";
import { DashboardKpi } from "@/components/DashboardKpi";
import { LiveShipmentMap } from "@/components/LiveShipmentMap";
import { OperationForm } from "@/components/OperationForm";
import { ShipmentTable } from "@/components/ShipmentTable";
import { RiskPanel } from "@/components/dashboard/RiskPanel";
import { FinanceSection } from "@/components/finance/FinanceSection";
import { useAuth } from "@/hooks/useAuth";
import { usePermissions } from "@/hooks/usePermissions";
import { usePlatformData } from "@/hooks/usePlatformData";
import { isActiveShipment, useShipmentOperations } from "@/hooks/useShipments";
import { useQuote } from "@/hooks/useQuote";

/**
 * Coordinates authenticated dashboard data and composes the home page sections.
 * Props: none.
 */
export function HomeContainer() {
  const router = useRouter();
  const auth = useAuth();
  const permissions = usePermissions();
  const { dashboard, shipments, finance, carbon, liveMap, reload } = usePlatformData(auth.accessToken, auth.refresh);
  const quote = useQuote(auth.accessToken);
  const shipmentOps = useShipmentOperations(shipments, reload);

  useEffect(() => {
    if (!auth.ready) return;
    if (!auth.isAuthenticated) router.replace("/login");
  }, [auth.ready, auth.isAuthenticated, router]);

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">BL</div>
          <div>
            <strong>Bağcıbaşı</strong>
            <span>AI Logistics Platform</span>
          </div>
        </div>
        <nav>
          <a href="#dashboard">Yönetici</a>
          {permissions.can("customers.read") && <Link href="/customers">Müşteriler</Link>}
          <a href="#operations">Operasyon</a>
          <Link href="/vehicles">Filo</Link>
          <a href="#live-map">Canlı Harita</a>
          <a href="#finance">Finans</a>
          <a href="#carbon">Karbon & ESG</a>
          <a href="#ai">AI Merkezi</a>
          {permissions.role === "admin" && <Link href="/settings">Ayarlar</Link>}
        </nav>
        <div className="connection">{auth.user?.full_name}</div>
        <button className="wideButton" onClick={() => auth.logout().then(() => router.replace("/login"))}>
          Çıkış Yap
        </button>
      </aside>

      <section className="content">
        <header className="hero" id="dashboard">
          <div>
            <p className="eyebrow">Kurumsal kontrol merkezi</p>
            <h1>Bağcıbaşı Logistics AI Platform</h1>
            <p>PostgreSQL, FastAPI ve Next.js tabanlı profesyonel lojistik operasyon sistemi.</p>
          </div>
          <div className="heroPanel">
            <span>AI önerisi</span>
            <strong>Manisa - İstanbul hattında maliyet ve karbon optimizasyonu takip edilmeli.</strong>
          </div>
        </header>

        <DashboardKpi dashboard={dashboard} />

        <section className="gridTwo" id="operations">
          {permissions.can("shipments.*") ? (
            <OperationForm
              editingShipment={shipmentOps.editingShipment}
              submitError={shipmentOps.shipmentError}
              submitting={shipmentOps.shipmentSubmitting}
              onCancelEdit={shipmentOps.cancelEdit}
              onSubmit={shipmentOps.submitShipment}
            />
          ) : (
            <div className="panel">
              <div className="sectionHead">
                <h2>Operasyon Yetkisi</h2>
                <span>{permissions.role}</span>
              </div>
              <p className="panelNote">Bu rol yeni sevkiyat oluşturamaz. Size açık sevkiyatlar listede görünür.</p>
            </div>
          )}
          <RiskPanel shipments={shipments} />
        </section>

        <ShipmentTable
          shipments={shipments}
          canManage={permissions.can("shipments.*")}
          onEdit={shipmentOps.selectShipmentForEdit}
          onDelete={shipmentOps.removeShipment}
          onImported={reload}
        />

        <section className="gridTwo" id="live-map">
          <div className="panel mapPanel">
            <div className="sectionHead">
              <h2>Canlı Harita Sistemi</h2>
              <span>Araç, depo, rota ve yoğunluk</span>
            </div>
            <div className="mapCanvas" aria-label="Türkiye canlı lojistik haritası">
              <LiveShipmentMap shipments={shipmentOps.mapShipments.length ? shipmentOps.mapShipments : shipments.filter(isActiveShipment)} />
            </div>
            <p className="panelNote">{liveMap.traffic_note}</p>
          </div>
          <div className="panel">
            <div className="sectionHead">
              <h2>Araç Takibi</h2>
              <span>{liveMap.vehicles.length} aktif araç</span>
            </div>
            <div className="vehicleList">
              {liveMap.vehicles.map((vehicle) => (
                <article key={vehicle.plate}>
                  <div>
                    <strong>{vehicle.plate}</strong>
                    <span>
                      {vehicle.vehicle_type} · {vehicle.driver}
                    </span>
                  </div>
                  <div className="progressTrack">
                    <div style={{ width: `${vehicle.progress}%` }} />
                  </div>
                  <div className="vehicleMeta">
                    <span>{vehicle.route}</span>
                    <span className={`badge ${vehicle.risk_level === "Yüksek" ? "danger" : vehicle.risk_level === "Orta" ? "warning" : "success"}`}>{vehicle.risk_level}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <FinanceSection finance={finance} carbon={carbon} />
        <AiAnalysisPanel prompt={quote.prompt} setPrompt={quote.setPrompt} result={quote.result} loading={quote.loading} error={quote.error} run={quote.run} />
      </section>
    </main>
  );
}
