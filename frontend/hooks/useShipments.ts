"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { createShipment, deleteShipment, getShipment, getShipments, updateShipment } from "@/lib/api/shipments";
import { assignVehicle, completeVehicleDelivery, createVehicle, deleteVehicle, getVehicles, updateVehicle, updateVehicleStatus } from "@/lib/api/client";
import type { PaginatedResponse, Shipment, ShipmentCreate, ShipmentListParams, ShipmentUpdate, Vehicle, VehicleCreate, VehicleUpdate } from "@/types";

const emptyPage: PaginatedResponse<Shipment> = {
  items: [],
  total: 0,
  skip: 0,
  limit: 20,
};

function readableError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function isActiveShipment(shipment: Shipment) {
  return !shipment.status.toLocaleLowerCase("tr-TR").includes("teslim");
}

export function useShipments(params: ShipmentListParams = {}) {
  const stableParams = useMemo(() => params, [JSON.stringify(params)]);
  const [data, setData] = useState<PaginatedResponse<Shipment>>(emptyPage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getShipments(stableParams);
      setData(response);
    } catch (requestError) {
      setError(readableError(requestError, "Sevkiyatlar yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [stableParams]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(
    () => ({
      shipments: data.items,
      pagination: {
        total: data.total,
        skip: data.skip,
        limit: data.limit,
      },
      loading,
      error,
      reload,
    }),
    [data, error, loading, reload],
  );
}

export function useShipment(id?: string) {
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setShipment(await getShipment(id));
    } catch (requestError) {
      setError(readableError(requestError, "Sevkiyat kaydı yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(() => ({ shipment, loading, error, reload }), [error, loading, reload, shipment]);
}

export function useMutateShipment() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T>(action: () => Promise<T>) => {
    setLoading(true);
    setError(null);
    try {
      return await action();
    } catch (requestError) {
      const message = readableError(requestError, "Sevkiyat işlemi tamamlanamadı.");
      setError(message);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(
    () => ({
      loading,
      error,
      create: (data: ShipmentCreate) => run(() => createShipment(data)),
      update: (id: string, data: ShipmentUpdate) => run(() => updateShipment(id, data)),
      remove: (id: string) => run(() => deleteShipment(id)),
    }),
    [error, loading, run],
  );
}

export function useShipmentOperations(shipments: Shipment[], reload: () => Promise<void>) {
  const [editingShipment, setEditingShipment] = useState<Shipment | null>(null);
  const [shipmentError, setShipmentError] = useState<string | null>(null);
  const [shipmentSubmitting, setShipmentSubmitting] = useState(false);
  const [mapShipments, setMapShipments] = useState<Shipment[]>([]);

  useEffect(() => {
    let cancelled = false;
    getShipments({ limit: 100 })
      .then((response) => {
        if (!cancelled) setMapShipments(response.items.filter(isActiveShipment));
      })
      .catch(() => {
        if (!cancelled) setMapShipments(shipments.filter(isActiveShipment));
      });
    return () => {
      cancelled = true;
    };
  }, [shipments]);

  const submitShipment = useCallback(async (form: FormData, isDraft = false) => {
    const shipmentId = String(form.get("shipment_id") ?? "");
    const tonnage = Number(form.get("tonnage"));
    const weightKg = Number(form.get("weight_kg"));
    const desi = Number(form.get("desi"));
    const distanceKm = Number(form.get("distance_km"));
    const invoiceAmount = Number(form.get("invoice_amount"));
    const profitAmount = Number(form.get("profit_amount"));
    const co2Kg = Number(form.get("co2_kg"));
    const shipmentType = String(form.get("shipment_type") ?? "LTL");
    const payload: ShipmentCreate = {
      customer_name: String(form.get("customer_name") ?? "").trim(),
      origin: String(form.get("origin") ?? "").trim(),
      destination: String(form.get("destination") ?? "").trim(),
      vehicle_id: String(form.get("vehicle_id") ?? "") || null,
      vehicle_type: String(form.get("vehicle_type") ?? "kamyon"),
      cargo_type: String(form.get("cargo_type") ?? "").trim(),
      tonnage,
      weight_kg: Number.isFinite(weightKg) && weightKg > 0 ? weightKg : tonnage * 1000,
      desi: Number.isFinite(desi) && desi >= 0 ? desi : null,
      distance_km: Number.isFinite(distanceKm) && distanceKm > 0 ? distanceKm : null,
      delivery_date: String(form.get("delivery_date") ?? ""),
      invoice_amount: Number.isFinite(invoiceAmount) && invoiceAmount > 0 ? invoiceAmount : undefined,
      profit_amount: Number.isFinite(profitAmount) && profitAmount > 0 ? profitAmount : undefined,
      co2_kg: Number.isFinite(co2Kg) && co2Kg > 0 ? co2Kg : undefined,
      shipment_type: shipmentType,
      status: isDraft ? "Taslak" : "Hazırlanıyor",
    };
    setShipmentError(null);
    setShipmentSubmitting(true);
    try {
      if (shipmentId) {
        await updateShipment(shipmentId, { ...payload, distance_km: payload.distance_km ?? undefined });
      } else {
        const created = await createShipment(payload);
        if (payload.vehicle_id) await assignVehicle(payload.vehicle_id, { shipment_id: created.id, load_tons: payload.tonnage });
      }
      setEditingShipment(null);
      await reload();
    } catch (requestError) {
      setShipmentError(readableError(requestError, "Sevkiyat kaydedilemedi."));
    } finally {
      setShipmentSubmitting(false);
    }
  }, [reload]);

  const submitShipmentForm = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget as HTMLFormElement);
      const submitter = (event.nativeEvent as SubmitEvent)?.submitter as HTMLButtonElement | null;
      const isDraft = submitter?.name === "is_draft" ? submitter.value === "true" : false;
      await submitShipment(form, isDraft);
    },
    [submitShipment],
  );

  const removeShipment = useCallback(
    async (shipment: Shipment) => {
      if (!window.confirm(`${shipment.customer_name} sevkiyatı silinsin mi?`)) return;
      setShipmentError(null);
      try {
        await deleteShipment(shipment.id);
        if (shipment.vehicle_id) {
          try {
            const vehicleResponse = await getVehicles({});
            const vehicle = vehicleResponse.items?.find((v) => v.id === shipment.vehicle_id);

            if (vehicle) {
              const shipmentTonnage = shipment.tonnage ?? 0;
              const remainingLoad = (vehicle.current_load_tons ?? 0) - shipmentTonnage;

              if (remainingLoad <= 0) {
                await updateVehicleStatus(shipment.vehicle_id, "Bosta");
              } else {
                await updateVehicle(shipment.vehicle_id, {
                  current_load_tons: remainingLoad,
                });
              }
            }
          } catch {
            // Vehicle update failed, ignore silently
          }
        }
        setEditingShipment((current) => (current?.id === shipment.id ? null : current));
        await reload();
      } catch (requestError) {
        setShipmentError(readableError(requestError, "Sevkiyat silinemedi."));
      }
    },
    [reload],
  );

  const selectShipmentForEdit = useCallback((shipment: Shipment) => {
    setEditingShipment(shipment);
    setShipmentError(null);
    document.getElementById("operations")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return useMemo(
    () => ({
      editingShipment,
      shipmentError,
      shipmentSubmitting,
      mapShipments,
      submitShipment: submitShipmentForm,
      removeShipment,
      selectShipmentForEdit,
      cancelEdit: () => setEditingShipment(null),
    }),
    [editingShipment, mapShipments, removeShipment, selectShipmentForEdit, shipmentError, shipmentSubmitting, submitShipmentForm],
  );
}

export function useVehicles(params: { status?: string } = {}, options: { refetchInterval?: number } = {}) {
  const stableParams = useMemo(() => params, [JSON.stringify(params)]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await getVehicles(stableParams);
      setVehicles(response.items);
      setTotal(response.total);
    } catch (requestError) {
      setError(readableError(requestError, "Araçlar yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [stableParams]);

  useEffect(() => {
    setLoading(true);
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!options.refetchInterval) return;
    const interval = window.setInterval(() => void reload(), options.refetchInterval);
    return () => window.clearInterval(interval);
  }, [options.refetchInterval, reload]);

  return useMemo(() => ({ vehicles, total, loading, error, reload }), [error, loading, reload, total, vehicles]);
}

export function useMutateVehicle() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T>(action: () => Promise<T>) => {
    setLoading(true);
    setError(null);
    try {
      return await action();
    } catch (requestError) {
      const message = readableError(requestError, "Araç işlemi tamamlanamadı.");
      setError(message);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(
    () => ({
      loading,
      error,
      create: (data: VehicleCreate) => run(() => createVehicle(data)),
      update: (id: string, data: VehicleUpdate) => run(() => updateVehicle(id, data)),
      remove: (id: string) => run(() => deleteVehicle(id)),
      status: (id: string, nextStatus: string) => run(() => updateVehicleStatus(id, nextStatus)),
      assign: (id: string, shipmentId: string, loadTons: number) => run(() => assignVehicle(id, { shipment_id: shipmentId, load_tons: loadTons })),
      complete: (id: string) => run(() => completeVehicleDelivery(id)),
    }),
    [error, loading, run],
  );
}
