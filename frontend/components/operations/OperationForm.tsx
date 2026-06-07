"use client";

import dynamic from "next/dynamic";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Icon, LeafletEvent, LeafletMouseEvent } from "leaflet";

import { QuoteResultBox } from "@/components/QuoteResultBox";
import { geocodeLocation, getRoute } from "@/lib/api/carbon";
import { apiRequest } from "@/lib/api/client";
import { useCustomers } from "@/hooks/useCustomers";
import { useVehicles } from "@/hooks/useShipments";
import type { EmissionCalculation, RouteResult, Shipment } from "@/types";

/**
 * Handles shipment creation and editing with route, capacity, carbon, and pricing inputs.
 * Props: editingShipment, submitError, submitting, onCancelEdit, and onSubmit.
 */

const MapContainer = dynamic(() => import("react-leaflet").then((mod) => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((mod) => mod.TileLayer), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then((mod) => mod.Marker), { ssr: false });
const Polyline = dynamic(() => import("react-leaflet").then((mod) => mod.Polyline), { ssr: false });
const MapClickHandler = dynamic(
  async () => {
    const { useMapEvents } = await import("react-leaflet");
    return function MapClickHandlerComponent({ onClick }: { onClick: (event: LeafletMouseEvent) => void }) {
      useMapEvents({ click: onClick });
      return null;
    };
  },
  { ssr: false },
);

const MapResizeHandler = dynamic(
  async () => {
    const { useMap } = await import("react-leaflet");
    return function MapResizeHandlerComponent() {
      const map = useMap();
      useEffect(() => {
        const timeout = window.setTimeout(() => {
          map.invalidateSize();
        }, 100);
        return () => window.clearTimeout(timeout);
      }, [map]);
      return null;
    };
  },
  { ssr: false },
);

const money = (value: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);

const number = (value: number) => new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);

type RoutePoint = { lat: number; lon: number };
type RouteField = "origin" | "destination";
type RoutePosition = [number, number];
type PricingPreview = { invoice_amount: number; distance_km: number; vehicle_type: string; pricing_type?: string; estimated_minutes?: number };
type LogisticsCalculationResponse = {
  pricing_type: string;
  pricing: { total_cost: number };
  sustainability: { total_emission_co2e: number };
  estimated_duration?: { hours: number; minutes: number };
};

const TURKEY_CENTER: [number, number] = [39, 35];
const VEHICLE_TYPE_OPTIONS = [
  { value: "panelvan", label: "Panelvan" },
  { value: "kamyonet", label: "Kamyonet" },
  { value: "kamyon", label: "Kamyon" },
  { value: "tir", label: "Tır" },
];
const FUEL_TYPE_OPTIONS = ["Dizel", "Benzin", "Elektrikli", "Biyodizel"];
const MANUAL_DISTANCE_MESSAGE = "Konum bulunamadı, mesafeyi manuel girin";

function vehicleFormValue(value?: string | null) {
  const normalized = (value ?? "")
    .toLocaleLowerCase("tr-TR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace("ı", "i")
    .replace("ğ", "g")
    .replace("ş", "s")
    .replace("ç", "c")
    .replace("ö", "o")
    .replace("ü", "u");
  if (normalized.includes("panelvan") || normalized.includes("hafif")) return "panelvan";
  if (normalized.includes("kamyonet") || normalized === "minivan") return "kamyonet";
  if (normalized.includes("tir") || normalized.includes("tır") || normalized.includes("t\u0131r")) return "tir";
  if (normalized.includes("elektrik")) return "elektrikli";
  return "kamyon";
}

function logisticsVehicleType(value?: string | null) {
  const normalized = value?.toLocaleLowerCase("tr-TR") ?? "";
  if (normalized.includes("panelvan")) return "Panelvan";
  if (normalized.includes("kamyonet") || normalized.includes("minivan")) return "Kamyonet";
  if (normalized.includes("tir") || normalized.includes("tÄ±r")) return "Tır";
  return "Kamyon";
}

function withTurkeyContext(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  const normalized = trimmed.toLocaleLowerCase("tr-TR");
  return normalized.includes("türkiye") || normalized.includes("turkiye") || normalized.includes("turkey") ? trimmed : `${trimmed}, Türkiye`;
}

function isRoutePoint(value: RoutePoint | null): value is RoutePoint {
  return Boolean(value && Number.isFinite(value.lat) && Number.isFinite(value.lon));
}

function isCoordinatePair(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number";
}

function geoJsonCoordinatesToPositions(coordinates: unknown): RoutePosition[] {
  if (!Array.isArray(coordinates)) return [];
  if (coordinates.every(isCoordinatePair)) return coordinates.map(([lon, lat]) => [lat, lon] as RoutePosition);
  return coordinates.flatMap((item) => geoJsonCoordinatesToPositions(item));
}

function decodePolyline(value: string): RoutePosition[] {
  let index = 0;
  let lat = 0;
  let lng = 0;
  const coordinates: RoutePosition[] = [];

  while (index < value.length) {
    let result = 0;
    let shift = 0;
    let byte: number;
    do {
      byte = value.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20 && index < value.length);
    lat += result & 1 ? ~(result >> 1) : result >> 1;

    result = 0;
    shift = 0;
    do {
      byte = value.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20 && index < value.length);
    lng += result & 1 ? ~(result >> 1) : result >> 1;

    coordinates.push([lat / 100000, lng / 100000]);
  }

  return coordinates;
}

function geometryToPositions(geometry: RouteResult["geometry"] | undefined): RoutePosition[] {
  if (!geometry) return [];
  if (typeof geometry === "string") return decodePolyline(geometry);
  if (Array.isArray(geometry)) return geoJsonCoordinatesToPositions(geometry);
  if ("type" in geometry && geometry.type === "Feature" && "geometry" in geometry) {
    return geometryToPositions(geometry.geometry as RouteResult["geometry"]);
  }
  if ("type" in geometry && geometry.type === "FeatureCollection" && "features" in geometry && Array.isArray(geometry.features)) {
    return geometry.features.flatMap((feature) => geometryToPositions(feature.geometry as RouteResult["geometry"]));
  }
  if ("coordinates" in geometry) return geoJsonCoordinatesToPositions(geometry.coordinates);
  return [];
}

function routeLine(route: RouteResult | null, origin: RoutePoint | null, destination: RoutePoint | null) {
  const geometry = route?.geometry;
  const routeGeometry = geometryToPositions(geometry);
  if (routeGeometry.length > 1) return routeGeometry;
  if (isRoutePoint(origin) && isRoutePoint(destination)) {
    return [
      [origin.lat, origin.lon],
      [destination.lat, destination.lon],
    ] as RoutePosition[];
  }
  return [];
}

async function reverseGeocode(point: RoutePoint) {
  const params = new URLSearchParams({
    lat: String(point.lat),
    lon: String(point.lon),
    format: "json",
    zoom: "10",
    addressdetails: "1",
  });
  const response = await fetch(`https://nominatim.openstreetmap.org/reverse?${params.toString()}`, {
    headers: { "Accept-Language": "tr" },
  });
  if (!response.ok) return "";
  const payload = await response.json();
  const address = payload.address ?? {};
  return address.city ?? address.province ?? address.state ?? address.town ?? address.county ?? address.state_district ?? payload.display_name?.split(",")[0] ?? "";
}

export function OperationForm({
  editingShipment,
  submitError,
  submitting = false,
  onCancelEdit,
  onSubmit,
}: {
  editingShipment?: Shipment | null;
  submitError?: string | null;
  submitting?: boolean;
  onCancelEdit?: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const searchParams = useSearchParams();
  const vehicleIdFromUrl = searchParams.get("vehicle_id") ?? "";
  const initialOrigin = editingShipment?.origin ?? "Manisa";
  const initialCustomerName = editingShipment?.customer_name ?? "";
  const initialDeliveryDate = (editingShipment?.delivery_date ?? new Date().toISOString()).slice(0, 10);
  const initialDestination = editingShipment?.destination ?? "İstanbul";
  const initialVehicleType = vehicleFormValue(editingShipment?.vehicle_type);
  const initialWeightKg = editingShipment?.weight_kg ?? 0;
  const initialDesi = editingShipment?.desi ?? 0;
  const initialDistanceKm = editingShipment?.distance_km ?? 0;
  const formRef = useRef<HTMLFormElement>(null);
  const desiFlashTimeoutRef = useRef<number | null>(null);
  const [distanceStatus, setDistanceStatus] = useState<string | null>(null);
  const [distanceLoading, setDistanceLoading] = useState(false);
  const [customerName, setCustomerName] = useState(initialCustomerName);
  const [deliveryDate, setDeliveryDate] = useState(initialDeliveryDate);
  const [origin, setOrigin] = useState(initialOrigin);
  const [destination, setDestination] = useState(initialDestination);
  const [originPoint, setOriginPoint] = useState<RoutePoint | null>(null);
  const [destinationPoint, setDestinationPoint] = useState<RoutePoint | null>(null);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [activeRouteField, setActiveRouteField] = useState<RouteField>("origin");
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [vehicleType, setVehicleType] = useState(initialVehicleType);
  const [shipmentType, setShipmentType] = useState<"LTL" | "FTL">("LTL");
  const [fuelType, setFuelType] = useState("Dizel");
  const [euroNorm, setEuroNorm] = useState("Euro 6");
  const [selectedVehicleId, setSelectedVehicleId] = useState(editingShipment?.vehicle_id ?? "");
  const [weightKg, setWeightKg] = useState(initialWeightKg);
  const [desi, setDesi] = useState(initialDesi);
  const [packageDimensions, setPackageDimensions] = useState({ width: "", length: "", height: "", quantity: "" });
  const [desiFlash, setDesiFlash] = useState(false);
  const [distanceKm, setDistanceKm] = useState(initialDistanceKm);
  const [pricingPreview, setPricingPreview] = useState<PricingPreview | null>(null);
  const [, setIsPricingLoading] = useState(false);
  const [emission, setEmission] = useState<EmissionCalculation | null>(null);
  type EmissionDetails = {
    co2_kg: number;
    methodology: string;
    calculation_type: string;
    emission_factor_source: string;
    fuel_consumed_liters: number;
    fuel_type: string;
    euro_norm: string;
    load_factor: number;
    load_ratio_percent: number;
    efficiency_metric: string;
    efficiency_value: number;
    distance_km: number;
    load_tons: number;
    scenario_multiplier: number;
  };
  type RouteOption = {
    title: string;
    metrics: { distance_km: number; duration_minutes: number; co2_emissions_kg: number; financial_cost_tl: number };
    emission_details?: EmissionDetails;
  };
  const [routeOptions, setRouteOptions] = useState<null | {
    GREENEST: RouteOption;
    CHEAPEST: RouteOption;
    BALANCED: RouteOption;
  }>(null);
  const [routeOptionsLoading, setRouteOptionsLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<"GREENEST" | "CHEAPEST" | "BALANCED" | null>(null);
  const [extraStops, setExtraStops] = useState<string[]>([]);
  const [extraStopPoints, setExtraStopPoints] = useState<Array<{lat: number; lon: number} | null>>([]);
  const [icons, setIcons] = useState<{ origin: Icon; destination: Icon } | null>(null);
  const routePositions = useMemo(() => routeLine(route, originPoint, destinationPoint), [destinationPoint, originPoint, route]);
  const { customers } = useCustomers();
  const isLTL = shipmentType === "LTL";
  const vehicleStatusFilter = isLTL ? undefined : "Bosta";
  const { vehicles: availableVehicles, loading: vehiclesLoading, reload: reloadVehicles } = useVehicles(
    vehicleStatusFilter ? { status: vehicleStatusFilter } : {},
    { refetchInterval: 30000 },
  );
  const compatibleVehicles = useMemo(() => {
    let filtered = vehicleType ? availableVehicles.filter((vehicle) => vehicleFormValue(vehicle.vehicle_type) === vehicleType) : availableVehicles;

    if (isLTL) {
      filtered = filtered.filter((vehicle) => vehicle.current_load_tons < vehicle.capacity_tons);
    }

    return filtered;
  }, [availableVehicles, vehicleType, isLTL]);
  const selectedVehicle = useMemo(() => availableVehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? null, [availableVehicles, selectedVehicleId]);
  const selectedVehicleUnavailable = Boolean(selectedVehicleId && !selectedVehicle && !vehiclesLoading) && !isLTL;
  const desiDerivedWeightKg = Number(desi) > 0 ? Number(desi) * 3 : 0;
  const effectiveWeightKg = Number(weightKg) > 0 ? Number(weightKg) : desiDerivedWeightKg;
  const chargeableWeight = Math.max(effectiveWeightKg, Number(desi) || 0);
  const selectedVehicleCapacity = selectedVehicle ? selectedVehicle.capacity_tons * 1000 : undefined;
  const hasCapacityWarning = chargeableWeight > 0 && typeof selectedVehicleCapacity === "number" && chargeableWeight > selectedVehicleCapacity;
  const hasSoftCapacityWarning = chargeableWeight > 0 && typeof selectedVehicleCapacity === "number" && chargeableWeight > selectedVehicleCapacity * 0.85 && !hasCapacityWarning;
  const hasLegalWeightBlock = chargeableWeight > 26000;
  const weightTonValue = effectiveWeightKg / 1000;

  useEffect(() => {
    setDistanceStatus(null);
    setCustomerName(initialCustomerName);
    setDeliveryDate(initialDeliveryDate);
    setOrigin(initialOrigin);
    setDestination(initialDestination);
    setOriginPoint(null);
    setDestinationPoint(null);
    setRoute(null);
    setCurrentStep(1);
    setVehicleType(initialVehicleType);
    setShipmentType("LTL");
    setFuelType("Dizel");
    setEuroNorm("Euro 6");
    setSelectedVehicleId(editingShipment?.vehicle_id ?? "");
    setWeightKg(initialWeightKg);
    setDesi(initialDesi);
    setPackageDimensions({ width: "", length: "", height: "", quantity: "" });
    setDesiFlash(false);
    setDistanceKm(initialDistanceKm);
    setPricingPreview(null);
    setIsPricingLoading(false);
    setEmission(null);
    setRouteOptions(null);
    setSelectedScenario(null);
    setExtraStops([]);
    setExtraStopPoints([]);
  }, [editingShipment?.id, editingShipment?.vehicle_id, initialCustomerName, initialDeliveryDate, initialDesi, initialDestination, initialDistanceKm, initialOrigin, initialVehicleType, initialWeightKg]);

  useEffect(() => {
    return () => {
      if (desiFlashTimeoutRef.current) window.clearTimeout(desiFlashTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    const width = Number(packageDimensions.width);
    const length = Number(packageDimensions.length);
    const height = Number(packageDimensions.height);
    const quantity = Number(packageDimensions.quantity);

    if (width <= 0 || length <= 0 || height <= 0 || quantity <= 0) return;

    const calculatedDesi = Number((((width * length * height) / 3000) * quantity).toFixed(2));
    setDesi(calculatedDesi);
    setDesiFlash(true);
    if (desiFlashTimeoutRef.current) window.clearTimeout(desiFlashTimeoutRef.current);
    desiFlashTimeoutRef.current = window.setTimeout(() => setDesiFlash(false), 1500);
  }, [packageDimensions]);

  useEffect(() => {
    if (!vehicleIdFromUrl || editingShipment) return;
    setSelectedVehicleId(vehicleIdFromUrl);
    void reloadVehicles();
  }, [editingShipment, reloadVehicles, vehicleIdFromUrl]);

  useEffect(() => {
    if (!selectedVehicle) return;
    setVehicleType(vehicleFormValue(selectedVehicle.vehicle_type));
  }, [selectedVehicle]);

  useEffect(() => {
    if (!selectedVehicleId) return;
    const selected = availableVehicles.find((vehicle) => vehicle.id === selectedVehicleId);
    if (selected && vehicleFormValue(selected.vehicle_type) !== vehicleType) setSelectedVehicleId("");
  }, [availableVehicles, selectedVehicleId, vehicleType]);

  useEffect(() => {
    let mounted = true;
    void import("leaflet").then((leaflet) => {
      if (!mounted) return;
      const markerIcon = leaflet.icon({
        iconUrl: "/marker-icon.png",
        shadowUrl: "/marker-shadow.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
      });
      setIcons({
        origin: markerIcon,
        destination: markerIcon,
      });
    });
    return () => {
      mounted = false;
    };
  }, []);

  const updatePricingPreview = useCallback(async () => {
    const safeWeightKg = effectiveWeightKg;
    const safeDesi = Number(desi) || 0;
    const safeDistanceKm = Number(distanceKm) || 0;

    if ((safeWeightKg <= 0 && safeDesi <= 0) || safeDistanceKm <= 0 || !vehicleType) {
      setPricingPreview(null);
      setIsPricingLoading(false);
      return;
    }

    setIsPricingLoading(true);
    try {
      const selectedVehicleType = logisticsVehicleType(vehicleType);
      const result = await apiRequest<LogisticsCalculationResponse>("/api/v1/carbon/logistics-calculate", {
        method: "POST",
        body: JSON.stringify({
          distance_km: safeDistanceKm,
          weight_kg: safeWeightKg,
          desi: safeDesi,
          vehicle_type: selectedVehicleType,
          fuel_type: fuelType,
          shipment_type: shipmentType,
        }),
      });
      setPricingPreview({
        invoice_amount: result.pricing.total_cost,
        distance_km: safeDistanceKm,
        vehicle_type: selectedVehicleType,
        pricing_type: result.pricing_type,
        estimated_minutes: result.estimated_duration?.minutes,
      });
      setEmission({
        vehicle_type: selectedVehicleType,
        distance_km: safeDistanceKm,
        weight_kg: safeWeightKg,
        carbon_emission: result.sustainability.total_emission_co2e,
        benchmark: { benchmark_co2: result.sustainability.total_emission_co2e, deviation_percent: 0, label: "lojistik" },
      });
    } catch {
      setPricingPreview(null);
      setEmission(null);
    } finally {
      setIsPricingLoading(false);
    }
  }, [effectiveWeightKg, desi, distanceKm, vehicleType, fuelType, shipmentType]);

  useEffect(() => {
    void updatePricingPreview();
  }, [updatePricingPreview]);

  useEffect(() => {
    const originValue = origin.trim();
    const destinationValue = destination.trim();
    if (originValue.length < 2 && destinationValue.length < 2) return;

    let cancelled = false;
    const timeout = window.setTimeout(() => {
      async function updateRoute() {
        setDistanceLoading(true);
        setDistanceStatus(null);
        try {
          if (originValue.length >= 2 && destinationValue.length >= 2) {
            const result = await getRoute(withTurkeyContext(originValue), withTurkeyContext(destinationValue));
            if (cancelled) return;
            setRoute(result);
            setOriginPoint(result.origin_coords);
            setDestinationPoint(result.destination_coords);
            if (result.distance_km) {
              setDistanceKm(Math.round(result.distance_km));
              setDistanceStatus(`Tahmini mesafe hesaplandı: ${number(result.distance_km)} km`);
            } else {
              setDistanceStatus(MANUAL_DISTANCE_MESSAGE);
            }
            return;
          }

          const field = originValue.length >= 2 ? "origin" : "destination";
          const result = await geocodeLocation(withTurkeyContext(field === "origin" ? originValue : destinationValue));
          if (cancelled) return;
          const point = result.lat !== null && result.lon !== null ? { lat: result.lat, lon: result.lon } : null;
          if (field === "origin") setOriginPoint(point);
          else setDestinationPoint(point);
        } catch {
          if (!cancelled) setDistanceStatus(MANUAL_DISTANCE_MESSAGE);
        } finally {
          if (!cancelled) setDistanceLoading(false);
        }
      }
      void updateRoute();
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [destination, origin]);

  async function updatePointFromMap(field: RouteField, point: RoutePoint) {
    if (field === "origin") setOriginPoint(point);
    else setDestinationPoint(point);
    try {
      const city = await reverseGeocode(point);
      if (!city) return;
      if (field === "origin") setOrigin(city);
      else setDestination(city);
    } catch {
      setDistanceStatus(MANUAL_DISTANCE_MESSAGE);
    }
  }

  function handleMapClick(event: LeafletMouseEvent) {
    void updatePointFromMap(activeRouteField, { lat: event.latlng.lat, lon: event.latlng.lng });
  }

  async function fetchRouteOptions() {
    if (!originPoint || !destinationPoint) return;
    setRouteOptionsLoading(true);
    setRouteOptions(null);
    setSelectedScenario(null);
    try {
      const vroomVehicleType = vehicleType === "tir" || vehicleType === "kamyon" ? "HEAVY_TRUCK" : "LIGHT_COMMERCIAL";
      const result = await apiRequest<{ options: typeof routeOptions }>("/api/v1/routing/optimize", {
        method: "POST",
        body: JSON.stringify({
          vehicle_type: vroomVehicleType,
          current_load_kg: effectiveWeightKg || 0,
          fuel_type: fuelType,
          euro_norm: euroNorm,
          capacity_tons: selectedVehicle ? selectedVehicle.capacity_tons : 20.0,
          locations: [
            [originPoint.lon, originPoint.lat],
            ...extraStopPoints
              .filter((p): p is {lat: number; lon: number} => p !== null)
              .map(p => [p.lon, p.lat]),
            [destinationPoint.lon, destinationPoint.lat],
          ],
        }),
      });
      setRouteOptions(result.options as typeof routeOptions);
    } catch {
      setRouteOptions(null);
    } finally {
      setRouteOptionsLoading(false);
    }
  }

  function handleMarkerDrag(field: RouteField) {
    return (event: LeafletEvent) => {
      const marker = event.target as { getLatLng: () => { lat: number; lng: number } };
      const latLng = marker.getLatLng();
      void updatePointFromMap(field, { lat: latLng.lat, lon: latLng.lng });
    };
  }


  function renderRouteMarkers() {
    if (!icons) return null;
    return (
      <>
        {isRoutePoint(originPoint) && (
          <Marker position={[originPoint.lat, originPoint.lon]} icon={icons.origin} draggable eventHandlers={{ dragend: handleMarkerDrag("origin") }} />
        )}
        {extraStopPoints.map((point, index) =>
          point ? (
            <Marker key={`stop-${index}`} position={[point.lat, point.lon]} icon={icons.destination} />
          ) : null
        )}
        {isRoutePoint(destinationPoint) && (
          <Marker position={[destinationPoint.lat, destinationPoint.lon]} icon={icons.destination} draggable eventHandlers={{ dragend: handleMarkerDrag("destination") }} />
        )}
      </>
    );
  }

  function updatePackageDimension(field: keyof typeof packageDimensions, value: string) {
    setPackageDimensions((current) => ({ ...current, [field]: value }));
  }

  function handleManualDesiChange(value: string) {
    const nextDesi = Number(value);
    setDesi(nextDesi);
    setDesiFlash(false);
    if (desiFlashTimeoutRef.current) window.clearTimeout(desiFlashTimeoutRef.current);
    setPackageDimensions({ width: "", length: "", height: "", quantity: "" });
  }

  function handleFormChange(event: FormEvent<HTMLFormElement>) {
    const target = event.target as HTMLInputElement | HTMLSelectElement;
    if (target.name === "weight_kg") setWeightKg(Number(target.value));
    if (target.name === "desi") setDesi(Number(target.value));
    if (target.name === "distance_km") setDistanceKm(Number(target.value));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    event.stopPropagation();

    const submitter = (event.nativeEvent as SubmitEvent)?.submitter as HTMLButtonElement | null;
    const isDraft = submitter?.value === "true";

    if (hasLegalWeightBlock) return;
    if (!isDraft && !isLTL && hasCapacityWarning) return;
    if (!isDraft && selectedVehicleUnavailable) return;

    await onSubmit(event);

    {
      setCurrentStep(1);
      setSelectedVehicleId("");
      setCustomerName("");
      setOrigin("Manisa");
      setDestination("İstanbul");
      setWeightKg(0);
      setDesi(0);
      setDistanceKm(0);
      setPricingPreview(null);
      setEmission(null);
      setRouteOptions(null);
      setSelectedScenario(null);
      setExtraStops([]);
      setExtraStopPoints([]);
      setRoute(null);
      setOriginPoint(null);
      setDestinationPoint(null);
      setShipmentType("LTL");
      setEuroNorm("Euro 6");
      setPackageDimensions({ width: "", length: "", height: "", quantity: "" });
      void reloadVehicles();
    }
  }

  async function calculateDistance(form: HTMLFormElement | null) {
    if (!form) return;
    const formData = new FormData(form);
    const formOrigin = String(formData.get("origin") ?? "").trim();
    const formDestination = String(formData.get("destination") ?? "").trim();
    if (formOrigin.length < 2 || formDestination.length < 2) return;

    setDistanceLoading(true);
    setDistanceStatus(null);
    try {
      const result = await getRoute(withTurkeyContext(formOrigin), withTurkeyContext(formDestination));
      setRoute(result);
      setOriginPoint(result.origin_coords);
      setDestinationPoint(result.destination_coords);
      if (result.distance_km) {
        setDistanceKm(Math.round(result.distance_km));
        setDistanceStatus(`Otomatik hesaplandı: ${number(result.distance_km)} km`);
      } else {
        setDistanceStatus(MANUAL_DISTANCE_MESSAGE);
      }
    } catch {
      setDistanceStatus(MANUAL_DISTANCE_MESSAGE);
    } finally {
      setDistanceLoading(false);
    }
  }

  return (
    <div className="panel">
      <div className="sectionHead">
        <h2>{editingShipment ? "Sevkiyat Güncelle" : "Akıllı Sevkiyat Oluştur"}</h2>
        <span>{editingShipment ? "Seçili operasyon formda" : "Müşteri, rota, araç ve yük bilgisi gir"}</span>
      </div>
      {submitError && <div className="errorBanner">{submitError}</div>}
      <form ref={formRef} className="shipmentForm" key={editingShipment?.id ?? "create-shipment"} noValidate onChange={handleFormChange} onSubmit={handleSubmit}>
        <input type="hidden" name="shipment_id" value={editingShipment?.id ?? ""} />
        <input type="hidden" name="vehicle_type" value={vehicleType} />
        <input type="hidden" name="shipment_type" value={shipmentType} />
        <input type="hidden" name="invoice_amount" value={
          selectedScenario && routeOptions
            ? routeOptions[selectedScenario].metrics.financial_cost_tl
            : pricingPreview?.invoice_amount ?? ""
        } />
        <input type="hidden" name="co2_kg" value={
          selectedScenario && routeOptions
            ? routeOptions[selectedScenario].metrics.co2_emissions_kg
            : emission?.carbon_emission ?? ""
        } />
        <input type="hidden" name="cargo_type" value={editingShipment?.cargo_type ?? "Genel"} />
        <input name="tonnage" type="hidden" value={weightTonValue || ""} readOnly />
        {/* wizard persisted fields */}
        <input type="hidden" name="customer_name" value={customerName} />
        <input type="hidden" name="origin" value={origin} />
        <input type="hidden" name="destination" value={destination} />
        <input type="hidden" name="desi" value={Number.isFinite(desi) && desi > 0 ? desi : ""} />
        <input type="hidden" name="weight_kg" value={Number.isFinite(weightKg) && weightKg > 0 ? weightKg : ""} />
        <input type="hidden" name="delivery_date" value={deliveryDate} />
        <input type="hidden" name="distance_km" value={
          selectedScenario && routeOptions
            ? routeOptions[selectedScenario].metrics.distance_km
            : Number.isFinite(distanceKm) && distanceKm > 0 ? distanceKm : ""
        } />
        <div className="routeResultCards" style={{ gridColumn: "1 / -1" }}>
          {[1, 2, 3].map((step) => (
            <article key={step} style={{ borderColor: currentStep === step ? "#16a34a" : undefined }}>
              <span>Adım {step}/3</span>
              <strong>{step === 1 ? "Yük Bilgileri" : step === 2 ? "Rota & Fiyat" : "Araç Seç & Operasyona Al"}</strong>
            </article>
          ))}
        </div>

        {currentStep === 1 && (
          <>
            <select value={customerName} onChange={(event) => setCustomerName(event.target.value)} style={{ width: "100%" }}>
              <option value="">Müşteri seçin</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.name}>
                  {customer.name}
                </option>
              ))}
            </select>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => setShipmentType("LTL")}
                style={{
                  padding: "8px 20px",
                  borderRadius: 6,
                  border: "2px solid",
                  borderColor: shipmentType === "LTL" ? "#16a34a" : "#d1d5db",
                  background: shipmentType === "LTL" ? "#16a34a" : "#ffffff",
                  color: shipmentType === "LTL" ? "#ffffff" : "#6b7280",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                LTL
              </button>
              <button
                type="button"
                onClick={() => setShipmentType("FTL")}
                style={{
                  padding: "8px 20px",
                  borderRadius: 6,
                  border: "2px solid",
                  borderColor: shipmentType === "FTL" ? "#16a34a" : "#d1d5db",
                  background: shipmentType === "FTL" ? "#16a34a" : "#ffffff",
                  color: shipmentType === "FTL" ? "#ffffff" : "#6b7280",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                FTL
              </button>
            </div>
            <div className="routePlanner">
              <div className="routeFields">
                <input
                  value={origin}
                  placeholder="Kalkış noktası"
                  onBlur={(event) => void calculateDistance(event.currentTarget.form)}
                  onChange={(event) => setOrigin(event.target.value)}
                  onFocus={() => setActiveRouteField("origin")}
                />
                {isLTL && extraStops.map((stop, index) => (
                  <div key={index} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      value={stop}
                      placeholder={`Durak ${index + 1}`}
                      onChange={(event) => {
                        const updated = [...extraStops];
                        updated[index] = event.target.value;
                        setExtraStops(updated);
                        const updatedPoints = [...extraStopPoints];
                        updatedPoints[index] = null;
                        setExtraStopPoints(updatedPoints);
                      }}
                      onBlur={async (event) => {
                        const value = event.target.value.trim();
                        if (value.length < 2) return;
                        try {
                          const result = await geocodeLocation(withTurkeyContext(value));
                          if (result.lat !== null && result.lon !== null) {
                            const updatedPoints = [...extraStopPoints];
                            updatedPoints[index] = { lat: result.lat, lon: result.lon };
                            setExtraStopPoints(updatedPoints);
                          }
                        } catch { /* ignore */ }
                      }}
                      style={{ flex: 1 }}
                    />
                    <button
                      type="button"
                      onClick={() => { setExtraStops(extraStops.filter((_, i) => i !== index)); setExtraStopPoints(extraStopPoints.filter((_, i) => i !== index)); }}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "1px solid #e5e7eb",
                        background: "#fff",
                        color: "#dc2626",
                        cursor: "pointer",
                        fontWeight: 700,
                        fontSize: 16,
                        flexShrink: 0
                      }}
                    >
                      ×
                    </button>
                  </div>
                ))}
                <input
                  value={destination}
                  placeholder="Varış noktası"
                  onBlur={(event) => void calculateDistance(event.currentTarget.form)}
                  onChange={(event) => setDestination(event.target.value)}
                  onFocus={() => setActiveRouteField("destination")}
                />
                {isLTL && (
                  <button
                    type="button"
                    onClick={() => { setExtraStops([...extraStops, ""]); setExtraStopPoints([...extraStopPoints, null]); }}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "2px dashed #16a34a",
                      background: "#f0fdf4",
                      color: "#16a34a",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontSize: 13,
                      textAlign: "left"
                    }}
                  >
                    + Durak Ekle
                  </button>
                )}
              </div>
              <div className="routeMap">
                <MapContainer center={TURKEY_CENTER} zoom={6} scrollWheelZoom={false} className="leafletMap">
                  <MapClickHandler onClick={handleMapClick} />
                  <MapResizeHandler />
                  <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  {routePositions.length > 1 && <Polyline positions={routePositions} pathOptions={{ color: "#16a34a", weight: 5 }} />}
                  {renderRouteMarkers()}
                </MapContainer>
              </div>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <strong style={{ display: "block", marginBottom: 8 }}>Kargo ölçüleri</strong>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
                <input type="number" min="0" step="0.01" value={packageDimensions.width} onChange={(event) => updatePackageDimension("width", event.target.value)} placeholder="En (cm)" />
                <input type="number" min="0" step="0.01" value={packageDimensions.length} onChange={(event) => updatePackageDimension("length", event.target.value)} placeholder="Boy (cm)" />
                <input type="number" min="0" step="0.01" value={packageDimensions.height} onChange={(event) => updatePackageDimension("height", event.target.value)} placeholder="Yükseklik (cm)" />
                <input type="number" min="1" step="1" value={packageDimensions.quantity} onChange={(event) => updatePackageDimension("quantity", event.target.value)} placeholder="Adet" />
              </div>
            </div>
            <input
              type="number"
              min="0"
              step="0.01"
              value={Number.isFinite(desi) && desi > 0 ? desi : ""}
              onChange={(event) => handleManualDesiChange(event.target.value)}
              placeholder="Desi"
              style={{ border: desiFlash ? "1px solid #4ade80" : undefined, background: desiFlash ? "#f0fdf4" : undefined }}
            />
            <input
              type="number"
              min="1"
              step="1"
              value={Number.isFinite(weightKg) && weightKg > 0 ? weightKg : ""}
              onChange={(event) => setWeightKg(Number(event.target.value))}
              placeholder={desiDerivedWeightKg > 0 ? `${number(desiDerivedWeightKg)} kg otomatik` : "Ağırlık (kg)"}
            />
            <input type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} />
            <button
              type="button"
              onClick={() => {
                if (!customerName || customerName.trim().length < 2) {
                  alert("Lütfen bir müşteri seçin");
                  return;
                }
                if (!origin || origin.trim().length < 2) {
                  alert("Lütfen kalkış noktası girin");
                  return;
                }
                if (!destination || destination.trim().length < 2) {
                  alert("Lütfen varış noktası girin");
                  return;
                }
                setCurrentStep(2);
              }}
            >
              Devam Et
            </button>
          </>
        )}

        {currentStep === 2 && (
          <>
            {shipmentType === "FTL" ? (
              <>
                <div style={{ gridColumn: "1 / -1" }}>
                  <h3 style={{ marginBottom: 16, fontSize: 16, fontWeight: 600 }}>Sefer Özeti</h3>
                  <div style={{
                    border: "2px solid #16a34a",
                    borderRadius: 12,
                    padding: 24,
                    background: "#f0fdf4",
                    display: "grid",
                    gridTemplateColumns: "repeat(2, 1fr)",
                    gap: 16
                  }}>
                    <div>
                      <span style={{ fontSize: 12, color: "#6b7280" }}>Tahmini Mesafe</span>
                      <strong style={{ display: "block", fontSize: 18 }}>
                        {distanceLoading ? <span className="tinySpinner" /> : distanceKm ? `${distanceKm} km` : "Hesaplanıyor"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 12, color: "#6b7280" }}>Tahmini Süre</span>
                      <strong style={{ display: "block", fontSize: 18 }}>
                        {route?.duration_minutes ? `${Math.floor(route.duration_minutes / 60)} saat ${Math.round(route.duration_minutes % 60)} dk` : "Hesaplanıyor"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 12, color: "#6b7280" }}>Tahmini CO₂</span>
                      <strong style={{ display: "block", fontSize: 18, color: "#16a34a" }}>
                        {emission ? `${emission.carbon_emission} kg` : "Hesaplanıyor"}
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 12, color: "#6b7280" }}>Kurumsal Teklif</span>
                      <strong style={{ display: "block", fontSize: 18 }}>
                        {pricingPreview ? money(pricingPreview.invoice_amount) : "Hesaplanıyor"}
                      </strong>
                    </div>
                  </div>
                </div>
                <select
                  value={vehicleType}
                  onChange={(event) => { setVehicleType(event.target.value); setSelectedVehicleId(""); }}
                >
                  {VEHICLE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <select value={fuelType} onChange={(event) => setFuelType(event.target.value)}>
                  {FUEL_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <select value={euroNorm} onChange={(event) => setEuroNorm(event.target.value)}>
                  {["Euro 3", "Euro 4", "Euro 5", "Euro 6"].map((norm) => (
                    <option key={norm} value={norm}>{norm}</option>
                  ))}
                </select>
                <button type="button" className="secondaryButton" onClick={() => setCurrentStep(1)}>Geri</button>
                <button type="button" onClick={() => setCurrentStep(3)}>Onayla ve Devam Et</button>
              </>
            ) : (
              <>
                <select
                  value={vehicleType}
                  onChange={(event) => { setVehicleType(event.target.value); setSelectedVehicleId(""); }}
                >
                  {VEHICLE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <select value={fuelType} onChange={(event) => setFuelType(event.target.value)}>
                  {FUEL_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <select value={euroNorm} onChange={(event) => setEuroNorm(event.target.value)}>
                  {["Euro 3", "Euro 4", "Euro 5", "Euro 6"].map((norm) => (
                    <option key={norm} value={norm}>{norm}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => void fetchRouteOptions()}
                  disabled={routeOptionsLoading || !originPoint || !destinationPoint}
                  style={{ gridColumn: "1 / -1" }}
                >
                  {routeOptionsLoading ? "Rotalar hesaplan\u0131yor..." : "Rota Se\u00E7eneklerini Getir"}
                </button>

                {routeOptions && (
                  <div style={{ gridColumn: "1 / -1", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
                    {(["GREENEST", "CHEAPEST", "BALANCED"] as const).map((key) => {
                      const option = routeOptions[key];
                      const isSelected = selectedScenario === key;
                      return (
                        <div
                          key={key}
                          onClick={() => setSelectedScenario(key)}
                          style={{
                            border: `2px solid ${isSelected ? "#16a34a" : "#e5e7eb"}`,
                            borderRadius: 12,
                            padding: 16,
                            cursor: "pointer",
                            background: isSelected ? "#f0fdf4" : "#ffffff",
                            transition: "all 0.15s",
                          }}
                        >
                          <div style={{ fontSize: 24, marginBottom: 8 }} aria-hidden="true">
                            {key === "GREENEST" ? "\u{1F33F}" : key === "CHEAPEST" ? "\u{1F4B0}" : "\u2696\uFE0F"}
                          </div>
                          <strong style={{ display: "block", marginBottom: 8, fontSize: 13 }}>{option.title}</strong>
                          <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.8 }}>
                            <div>{"\u{1F4CD}"} {option.metrics.distance_km} km</div>
                            <div>{"\u23F1"} {option.metrics.duration_minutes} dk</div>
                            <div>{"\u{1F331}"} {option.metrics.co2_emissions_kg} kg CO&#x2082;</div>
                            <div>{"\u{1F4B5}"} {option.metrics.financial_cost_tl} TL</div>
                          </div>
                          {option.emission_details && (
                            <div style={{
                              marginTop: 10,
                              padding: "6px 8px",
                              background: "#f0fdf4",
                              borderRadius: 6,
                              border: "1px solid #bbf7d0",
                              fontSize: 11,
                              color: "#15803d"
                            }}>
                              <div style={{ fontWeight: 700, marginBottom: 2 }}>&#x2713; ISO 14083:2023 Do&#x11F;ruland&#x131;</div>
                              <div>WTW &bull; {option.emission_details.fuel_type} &bull; {option.emission_details.euro_norm}</div>
                              <div>{option.emission_details.efficiency_value} gCO&#x2082;e/ton-km</div>
                            </div>
                          )}
                          {isSelected && (
                            <div style={{ marginTop: 10, color: "#16a34a", fontWeight: 700, fontSize: 13 }}>&#x2713; Se&#xe7;ildi</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {routeOptions && (
                  <button
                    type="button"
                    onClick={() => {
                      if (!selectedScenario) { alert("L\u00FCtfen bir rota se\u00E7in"); return; }
                      setCurrentStep(3);
                    }}
                    disabled={!selectedScenario}
                    style={{ gridColumn: "1 / -1" }}
                  >
                    Teklifi Onayla ve Devam Et
                  </button>
                )}

                <button type="button" className="secondaryButton" onClick={() => setCurrentStep(1)}>Geri</button>
              </>
            )}
          </>
        )}

        {currentStep === 3 && (
          <>
            <select name="vehicle_id" value={selectedVehicleId} onChange={(event) => setSelectedVehicleId(event.target.value)}>
              <option value="">{vehiclesLoading ? "Boşta araçlar yükleniyor" : "Boşta araç seçin"}</option>
              {compatibleVehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {vehicle.plate_number} - {vehicle.vehicle_type} ({number(vehicle.capacity_tons)} Ton)
                </option>
              ))}
            </select>
            <div className="quoteBox">
              {compatibleVehicles.length} uyumlu araç listeleniyor. Araç tipi: {VEHICLE_TYPE_OPTIONS.find((option) => option.value === vehicleType)?.label ?? vehicleType}
            </div>
            {selectedVehicleUnavailable && <strong style={{ color: "#dc2626" }}>Seçili araç artık müsait değil, lütfen başka bir araç seçin</strong>}
            {hasSoftCapacityWarning && <strong style={{ color: "#ca8a04" }}>Kapasite doluluğu yüksek: {number(chargeableWeight / 1000)} / {number((selectedVehicleCapacity ?? 0) / 1000)} ton</strong>}
            {hasCapacityWarning && <strong style={{ color: "#dc2626" }}>Seçtiğiniz aracın fiziksel kapasitesi bu yük için yetersiz.</strong>}
            {hasLegalWeightBlock && <strong style={{ color: "#dc2626" }}>Bu yük miktarı standart karayolu taşımacılığı yasal sınırlarını aşmaktadır. Lütfen sevkiyatı bölün.</strong>}
            <button type="button" className="secondaryButton" onClick={() => setCurrentStep(2)}>
              Geri
            </button>
            <button type="submit" name="is_draft" value="true" className="secondaryButton" disabled={submitting || distanceLoading || hasLegalWeightBlock}>
              {submitting ? "Kaydediliyor" : "Taslak Kaydet"}
            </button>
            <button type="submit" name="is_draft" value="false" disabled={submitting || !selectedVehicleId || distanceLoading || hasLegalWeightBlock || (!isLTL && hasCapacityWarning) || selectedVehicleUnavailable}>
              {submitting ? "Kaydediliyor" : "Operasyona Al"}
            </button>
            {editingShipment && (
              <button className="secondaryButton" type="button" onClick={onCancelEdit}>
                Vazgeç
              </button>
            )}
          </>
        )}


      </form>
      {(distanceLoading || distanceStatus) && (
        <div className={distanceStatus === MANUAL_DISTANCE_MESSAGE ? "errorBanner" : "quoteBox"}>
          {distanceLoading ? <span className="tinySpinner" aria-label="Hesaplanıyor" /> : distanceStatus}
        </div>
      )}
      {pricingPreview && (
        <QuoteResultBox distanceKm={pricingPreview.distance_km} invoiceAmount={pricingPreview.invoice_amount} formatNumber={number} formatMoney={money} />
      )}
    </div>
  );
}
