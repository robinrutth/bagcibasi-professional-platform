"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import type { DivIcon } from "leaflet";

import { geocodeLocation } from "@/lib/api/carbon";
import { isActiveShipment } from "@/hooks/useShipments";
import type { Shipment } from "@/types";

/**
 * Shows active shipment origins and destinations on the live logistics map.
 * Props: shipments.
 */

const MapComponent = dynamic(() => import("react-leaflet").then((mod) => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((mod) => mod.TileLayer), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then((mod) => mod.Marker), { ssr: false });
const Tooltip = dynamic(() => import("react-leaflet").then((mod) => mod.Tooltip), { ssr: false });

type ShipmentMapPin = {
  id: string;
  kind: "origin" | "destination";
  lat: number;
  lon: number;
  shipment: Shipment;
};

const TURKEY_CENTER: [number, number] = [39, 35];

export function LiveShipmentMap({ shipments }: { shipments: Shipment[] }) {
  const [pins, setPins] = useState<ShipmentMapPin[]>([]);
  const [icons, setIcons] = useState<{ origin: DivIcon; destination: DivIcon } | null>(null);

  useEffect(() => {
    let mounted = true;
    void import("leaflet").then((leaflet) => {
      if (!mounted) return;
      setIcons({
        origin: leaflet.divIcon({ className: "routeMarker routeMarkerOrigin", html: "<span>A</span>", iconSize: [32, 32], iconAnchor: [16, 32] }),
        destination: leaflet.divIcon({ className: "routeMarker routeMarkerDestination", html: "<span>B</span>", iconSize: [32, 32], iconAnchor: [16, 32] }),
      });
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadPins() {
      const active = shipments.filter(isActiveShipment).slice(0, 30);
      const resolved = await Promise.all(
        active.flatMap((shipment) => [
          geocodeLocation(shipment.origin)
            .then((coords) => (coords.lat !== null && coords.lon !== null ? { id: `${shipment.id}-origin`, kind: "origin" as const, lat: coords.lat, lon: coords.lon, shipment } : null))
            .catch(() => null),
          geocodeLocation(shipment.destination)
            .then((coords) =>
              coords.lat !== null && coords.lon !== null ? { id: `${shipment.id}-destination`, kind: "destination" as const, lat: coords.lat, lon: coords.lon, shipment } : null,
            )
            .catch(() => null),
        ]),
      );
      if (!cancelled) setPins(resolved.filter((pin): pin is ShipmentMapPin => Boolean(pin)));
    }
    void loadPins();
    return () => {
      cancelled = true;
    };
  }, [shipments]);

  return (
    <MapComponent center={TURKEY_CENTER} zoom={6} scrollWheelZoom={false} className="leafletMap">
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {icons &&
        pins.map((pin) => (
          <Marker key={pin.id} position={[pin.lat, pin.lon]} icon={pin.kind === "origin" ? icons.origin : icons.destination}>
            <Tooltip>
              <strong>{pin.shipment.customer_name}</strong>
              <span>
                {pin.shipment.origin} - {pin.shipment.destination}
              </span>
              <span>{pin.shipment.vehicle_type}</span>
              <span>{pin.shipment.status}</span>
            </Tooltip>
          </Marker>
        ))}
    </MapComponent>
  );
}
