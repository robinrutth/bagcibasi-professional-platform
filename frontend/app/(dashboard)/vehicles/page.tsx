"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";
import { useMutateVehicle, useShipments, useVehicles } from "@/hooks/useShipments";
import { assignVehicle } from "@/lib/api/client";
import { getShipments, updateShipment } from "@/lib/api/shipments";
import type { Shipment, VehicleCreate } from "@/types";

const statusLabels: Record<string, string> = { Bosta: "Bosta", Yukleniyor: "Yukleniyor", Yolda: "Yolda", Bakimda: "Bakimda" };
const statusClass: Record<string, string> = { Bosta: "success", Yukleniyor: "warning", Yolda: "success", Bakimda: "danger" };
const vehicleTypeOptions = ["Kamyon", "Tir", "Kamyonet", "Panelvan"];
const vehicleCapacityDefaults: Record<string, number> = {
  Kamyon: 22,
  Tir: 26,
  Kamyonet: 3.5,
  Panelvan: 1.5,
};

function number(value: number) {
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);
}

export default function VehiclesPage() {
  const router = useRouter();
  const auth = useAuth();
  const [statusFilter, setStatusFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [capacityTons, setCapacityTons] = useState("");
  const [assignModal, setAssignModal] = useState<string | null>(null);
  const [draftShipments, setDraftShipments] = useState<Shipment[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState("");
  const [assigning, setAssigning] = useState(false);
  const { vehicles, loading, error, reload } = useVehicles(statusFilter ? { status: statusFilter } : {}, { refetchInterval: 30000 });
  const { shipments, reload: reloadShipments } = useShipments({ limit: 100 });
  const mutate = useMutateVehicle();

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  if (!auth.ready || !auth.isAuthenticated) return null;

  async function submitVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: VehicleCreate = {
      plate_number: String(form.get("plate_number") ?? "").trim(),
      vehicle_type: String(form.get("vehicle_type") ?? "").trim(),
      capacity_tons: Number(form.get("capacity_tons")),
      current_load_tons: 0,
      driver_name: String(form.get("driver_name") ?? "").trim(),
      driver_phone: String(form.get("driver_phone") ?? "").trim(),
      status: "Bosta",
      current_lat: Number(form.get("current_lat")),
      current_lng: Number(form.get("current_lng")),
      current_shipment_id: null,
      notes: String(form.get("notes") ?? "").trim(),
    };
    await mutate.create(payload);
    setShowModal(false);
    setCapacityTons("");
    await reload();
  }

  async function openAssignModal(vehicleId: string) {
    setAssignModal(vehicleId);
    setSelectedShipmentId("");
    setDraftShipments([]);
    try {
      const response = await getShipments({ status: "Taslak", limit: 100 });
      setDraftShipments(response.items || []);
    } catch {
      setDraftShipments([]);
    }
  }

  async function confirmAssign() {
    if (!assignModal || !selectedShipmentId) return;
    setAssigning(true);
    try {
      const shipment = draftShipments.find((s) => s.id === selectedShipmentId);
      const shipmentTonnage = shipment?.tonnage ?? 0;
      await assignVehicle(assignModal, {
        shipment_id: selectedShipmentId,
        load_tons: shipmentTonnage,
      });
      await updateShipment(selectedShipmentId, { status: "Hazırlanıyor" });
      setAssignModal(null);
      setDraftShipments([]);
      setSelectedShipmentId("");
      await new Promise((resolve) => setTimeout(resolve, 500));
      await reload();
      await reloadShipments();
    } catch (err) {
      alert("Atama başarısız: " + (err instanceof Error ? err.message : "Hata"));
    } finally {
      setAssigning(false);
    }
  }

  function handleVehicleTypeChange(vehicleType: string) {
    const defaultCapacity = vehicleCapacityDefaults[vehicleType];
    if (typeof defaultCapacity === "number") setCapacityTons(String(defaultCapacity));
  }

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Filo operasyonlari</p>
          <h1>Araclarim</h1>
        </div>
        <button className="primaryButton" type="button" onClick={() => setShowModal(true)}>
          Yeni Arac Ekle
        </button>
      </header>

      {error && <div className="errorBanner">{error}</div>}

      <section className="panel">
        <div className="fleetToolbar">
          <select className="formControl" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Tum durumlar</option>
            <option value="Bosta">Bosta</option>
            <option value="Yukleniyor">Yukleniyor</option>
            <option value="Yolda">Yolda</option>
            <option value="Bakimda">Bakimda</option>
          </select>
          <span>{loading ? "Yukleniyor" : `${vehicles.length} arac`}</span>
        </div>
      </section>

      <section className="panel">
        <div className="vehicleList">
          {!loading && vehicles.length === 0 && <div className="emptyState">Bu kriterlere uygun arac bulunmuyor.</div>}
          {vehicles.map((vehicle) => {
            const percent = vehicle.capacity_tons > 0 ? Math.round((vehicle.current_load_tons / vehicle.capacity_tons) * 100) : 0;
            return (
              <article className="z-10" key={vehicle.id}>
                <div>
                  <strong>{vehicle.plate_number}</strong>
                  <span>{vehicle.vehicle_type}</span>
                </div>
                <div className="vehicleDriverInfo">
                  <span>{vehicle.driver_name || "Surucu atanmamis"}</span>
                  <span>{vehicle.driver_phone || "Telefon yok"}</span>
                </div>
                <small>
                  {number(vehicle.current_load_tons)}/{number(vehicle.capacity_tons)} ton (%{percent})
                </small>
                <div
                  style={{
                    width: "100%",
                    height: 8,
                    background: "#e5e7eb",
                    borderRadius: 4,
                    margin: "4px 0",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(percent, 100)}%`,
                      height: "100%",
                      borderRadius: 4,
                      background: percent >= 90 ? "#dc2626" : percent >= 60 ? "#f59e0b" : "#16a34a",
                      transition: "width 0.3s",
                    }}
                  />
                </div>
                {vehicle.status === "Yukleniyor" &&
                  (() => {
                    const vehicleShipments = shipments.filter(
                      (s) => s.vehicle_id != null && String(s.vehicle_id).trim() === String(vehicle.id).trim() && s.status === "Hazırlanıyor",
                    );
                    return vehicleShipments.length > 0 ? (
                      <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
                        <strong style={{ color: "#374151" }}>Yükler:</strong>
                        {vehicleShipments.map((s) => (
                          <div key={s.id} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                            <span>{s.customer_name}</span>
                            <span style={{ color: "#16a34a", fontWeight: 600 }}>{number(s.tonnage)} ton</span>
                          </div>
                        ))}
                      </div>
                    ) : null;
                  })()}
                <div className="vehicleMeta">
                  <span className={`badge ${statusClass[vehicle.status] ?? "success"}`}>{statusLabels[vehicle.status] ?? vehicle.status}</span>
                </div>
                <small>Mevcut sevkiyat: {vehicle.current_shipment_id ?? "Yok"}</small>
                <div className="fleetActions">
                  {(vehicle.status === "Bosta" || vehicle.status === "Yukleniyor") && (
                    <button className="primaryButton" type="button" onClick={() => void openAssignModal(vehicle.id)}>
                      Sevkiyat Ata
                    </button>
                  )}
                  {vehicle.status === "Yolda" && (
                    <button
                      className="primaryButton"
                      type="button"
                      onClick={async () => {
                        try {
                          await mutate.complete(vehicle.id);
                          if (vehicle.current_shipment_id) {
                            await updateShipment(vehicle.current_shipment_id, {
                              status: "Tamamlandı",
                            });
                          }
                          await reload();
                        } catch (err) {
                          alert("İşlem başarısız: " + (err instanceof Error ? err.message : "Hata"));
                        }
                      }}
                    >
                      Teslim Tamamla
                    </button>
                  )}
                  <select className="formControl" value={vehicle.status} onChange={(event) => mutate.status(vehicle.id, event.target.value).then(reload)}>
                    <option value="Bosta">Bosta</option>
                    <option value="Yukleniyor">Yukleniyor</option>
                    <option value="Yolda">Yolda</option>
                    <option value="Bakimda">Bakimda</option>
                  </select>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {showModal && (
        <div className="modalBackdrop z-50" role="presentation">
          <form className="modalPanel customerForm z-[9999]" onSubmit={(event) => void submitVehicle(event)}>
            <div className="sectionHead">
              <h2>Yeni Arac</h2>
              <button className="secondaryButton" type="button" onClick={() => setShowModal(false)}>
                Kapat
              </button>
            </div>
            <input className="formControl" name="plate_number" placeholder="Plaka" required />
            <select className="formControl" name="vehicle_type" defaultValue="" onChange={(event) => handleVehicleTypeChange(event.target.value)} required>
              <option value="" disabled>
                Arac tipi secin
              </option>
              {vehicleTypeOptions.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <input
              className="formControl"
              name="capacity_tons"
              type="number"
              step="0.1"
              min="0.1"
              value={capacityTons}
              onChange={(event) => setCapacityTons(event.target.value)}
              placeholder="Kapasite (ton)"
              required
            />
            <input className="formControl" name="driver_name" placeholder="Surucu adi" />
            <input className="formControl" name="driver_phone" placeholder="Surucu telefon" />
            <input className="formControl" name="current_lat" type="number" step="0.000001" defaultValue="39" placeholder="Enlem" />
            <input className="formControl" name="current_lng" type="number" step="0.000001" defaultValue="35" placeholder="Boylam" />
            <textarea className="formControl" name="notes" placeholder="Notlar" />
            <button className="primaryButton" type="submit" disabled={mutate.loading}>
              {mutate.loading ? "Kaydediliyor" : "Kaydet"}
            </button>
          </form>
        </div>
      )}
      {assignModal && (
        <div className="modalBackdrop" role="presentation">
          <div className="modalPanel">
            <div className="sectionHead">
              <h2>Taslak Sevkiyat Seç</h2>
              <button className="secondaryButton" type="button" onClick={() => setAssignModal(null)}>
                Kapat
              </button>
            </div>
            {draftShipments.length === 0 ? (
              <p style={{ color: "#6b7280", padding: "1rem 0" }}>Atanabilir taslak sevkiyat bulunamadı.</p>
            ) : (
              <select
                className="formControl"
                value={selectedShipmentId}
                onChange={(e) => setSelectedShipmentId(e.target.value)}
                style={{ width: "100%", marginBottom: "1rem" }}
              >
                <option value="">Sevkiyat seçin</option>
                {draftShipments.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.customer_name} — {s.origin} → {s.destination} ({s.tonnage} ton)
                  </option>
                ))}
              </select>
            )}
            <button
              className="primaryButton"
              type="button"
              disabled={!selectedShipmentId || assigning}
              onClick={() => void confirmAssign()}
              style={{ width: "100%" }}
            >
              {assigning ? "Atanıyor..." : "Ata"}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
