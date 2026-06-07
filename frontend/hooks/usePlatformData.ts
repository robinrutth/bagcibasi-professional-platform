"use client";

import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/services/api/client";
import { Carbon, DashboardSummary, Finance, LiveMap, Shipment, VehicleListResponse } from "@/types";

const fallbackDashboard: DashboardSummary = {
  total_revenue: 0,
  total_profit: 0,
  active_operations: 0,
  delivery_success_rate: 0,
  total_co2_kg: 0,
  risky_operations: 0,
};

const fallbackFinance: Finance = {
  current_cash: 0,
  pending_collections: 0,
  projected_outflow: 0,
  projected_cash_15_days: 0,
  total_profit: 0,
  ai_warning: "",
};

const fallbackCarbon: Carbon = {
  total_co2_kg: 0,
  highest_emission_route: null,
  optimization_note: "",
};

const fallbackLiveMap: LiveMap = {
  vehicles: [],
  depots: [],
  heatmap: [],
  traffic_note: "",
};

export function usePlatformData(accessToken: string, refreshAccessToken: () => Promise<string>) {
  const [dashboard, setDashboard] = useState<DashboardSummary>(fallbackDashboard);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [finance, setFinance] = useState<Finance>(fallbackFinance);
  const [carbon, setCarbon] = useState<Carbon>(fallbackCarbon);
  const [liveMap, setLiveMap] = useState<LiveMap>(fallbackLiveMap);
  const [loading, setLoading] = useState(false);

  const loadWithToken = useCallback(async (token: string) => {
    const safeGet = async <T,>(path: string, fallback: T) => {
      try {
        return await apiGet<T>(path, token);
      } catch {
        return fallback;
      }
    };
    const [d, s, f, c, l, v] = await Promise.all([
      safeGet<DashboardSummary>("/api/dashboard", fallbackDashboard),
      safeGet<Shipment[]>("/api/shipments", []),
      safeGet<Finance>("/api/finance", fallbackFinance),
      safeGet<Carbon>("/api/carbon", fallbackCarbon),
      safeGet<LiveMap>("/api/live-map", fallbackLiveMap),
      safeGet<VehicleListResponse>("/api/v1/vehicles", { items: [], total: 0 }),
    ]);
    setDashboard(d);
    setShipments(s);
    setFinance(f);
    setCarbon(c);
    setLiveMap({
      ...l,
      vehicles: v.items.length
        ? v.items.map((vehicle) => ({
            plate: vehicle.plate_number,
            driver: vehicle.driver_name ?? "Atanmamış",
            vehicle_type: vehicle.vehicle_type,
            status: vehicle.status,
            route: vehicle.current_shipment_id ? `Sevkiyat ${vehicle.current_shipment_id.slice(0, 8)}` : "Sevkiyat yok",
            progress: vehicle.status === "Yolda" ? 72 : vehicle.status === "Yukleniyor" ? 22 : 0,
            lat: vehicle.current_lat ?? 39,
            lng: vehicle.current_lng ?? 35,
            risk_level: vehicle.status === "Bakimda" ? "Yüksek" : vehicle.status === "Yukleniyor" ? "Orta" : "Düşük",
          }))
        : l.vehicles,
    });
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      await loadWithToken(accessToken);
    } catch {
      const newToken = await refreshAccessToken();
      await loadWithToken(newToken);
    } finally {
      setLoading(false);
    }
  }, [accessToken, loadWithToken, refreshAccessToken]);

  useEffect(() => {
    if (!accessToken) return;
    void reload();
  }, [accessToken, reload]);

  return { dashboard, shipments, finance, carbon, liveMap, loading, reload };
}
