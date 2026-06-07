from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import logging
from math import atan2, cos, radians, sin, sqrt
import os
import time
from typing import Literal
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmissionFactor, Shipment


OLD_DEFAULT_EMISSION_FACTORS: dict[str, dict[str, float | str]] = {
    "truck": {
        "co2_per_km": 0.27,
        "co2_per_kg_km": 0.00015,
        "description": "Heavy-duty road freight estimate based on IPCC/EEA-style tank-to-wheel factors.",
    },
    "minivan": {
        "co2_per_km": 0.18,
        "co2_per_kg_km": 0.00010,
        "description": "Light commercial vehicle estimate for urban and regional deliveries.",
    },
    "motorcycle": {
        "co2_per_km": 0.10,
        "co2_per_kg_km": 0.00005,
        "description": "Motorcycle courier estimate for lightweight deliveries.",
    },
    "electric": {
        "co2_per_km": 0.05,
        "co2_per_kg_km": 0.00002,
        "description": "Electric vehicle estimate using grid-adjusted operational emissions.",
    },
    "bicycle": {
        "co2_per_km": 0.00,
        "co2_per_kg_km": 0.00000,
        "description": "Human-powered bicycle delivery with no direct CO2 emissions.",
    },
}

VEHICLE_ALIASES = {
    "truck": "truck",
    "kamyon": "truck",
    "tir": "truck",
    "tır": "truck",
    "tä±r": "truck",
    "minivan": "minivan",
    "kamyonet": "minivan",
    "motorcycle": "motorcycle",
    "motokurye": "motorcycle",
    "motosiklet": "motorcycle",
    "electric": "electric",
    "elektrikli arac": "electric",
    "elektrikli araç": "electric",
    "elektrikli araã§": "electric",
    "bicycle": "bicycle",
    "bisiklet": "bicycle",
}

DEFAULT_EMISSION_FACTORS: dict[str, dict[str, float | str]] = {
    "panelvan": {
        "co2_per_km": 0.15,
        "co2_per_kg_km": 0.00008,
        "description": "Panelvan light commercial delivery estimate.",
    },
    "kamyonet": {
        "co2_per_km": 0.18,
        "co2_per_kg_km": 0.00010,
        "description": "Kamyonet urban and regional delivery estimate.",
    },
    "kamyon": {
        "co2_per_km": 0.27,
        "co2_per_kg_km": 0.00015,
        "description": "Kamyon heavy-duty road freight estimate.",
    },
    "tir": {
        "co2_per_km": 0.32,
        "co2_per_kg_km": 0.00018,
        "description": "Tir long-haul freight estimate.",
    },
    "elektrikli": {
        "co2_per_km": 0.05,
        "co2_per_kg_km": 0.00002,
        "description": "Elektrikli arac grid-adjusted operational emissions estimate.",
    },
}

VEHICLE_ALIASES = {
    "panelvan": "panelvan",
    "hafif ticari": "panelvan",
    "minivan": "kamyonet",
    "kamyonet": "kamyonet",
    "truck": "kamyon",
    "kamyon": "kamyon",
    "tir": "tir",
    "tır": "tir",
    "electric": "elektrikli",
    "elektrikli": "elektrikli",
    "elektrikli arac": "elektrikli",
    "elektrikli araç": "elektrikli",
}

BENCHMARK_CO2_PER_KM = 0.35
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "BagcibasiLojistik/1.0 (contact@bagcibasi.com)"
ROAD_DISTANCE_FACTOR = 1.25
ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
_GEOCODE_CACHE: dict[str, dict[str, float] | None] = {}
_LAST_GEOCODE_REQUEST_AT = 0.0
logger = logging.getLogger(__name__)


def normalize_vehicle_type(vehicle_type: str) -> str:
    key = vehicle_type.strip().lower()
    normalized = VEHICLE_ALIASES.get(key)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Desteklenmeyen araç tipi. truck, minivan, motorcycle, electric veya bicycle kullanın.",
        )
    return normalized


def seed_default_emission_factors(db: Session) -> None:
    obsolete = {"truck", "minivan", "motorcycle", "electric", "bicycle"}
    for factor in db.scalars(select(EmissionFactor).where(EmissionFactor.vehicle_type.in_(obsolete))).all():
        db.delete(factor)
    for vehicle_type, values in DEFAULT_EMISSION_FACTORS.items():
        factor = db.scalar(select(EmissionFactor).where(EmissionFactor.vehicle_type == vehicle_type))
        if factor:
            factor.co2_per_km = float(values["co2_per_km"])
            factor.co2_per_kg_km = float(values["co2_per_kg_km"])
            factor.description = str(values["description"])
            continue
        db.add(
            EmissionFactor(
                vehicle_type=vehicle_type,
                co2_per_km=float(values["co2_per_km"]),
                co2_per_kg_km=float(values["co2_per_kg_km"]),
                description=str(values["description"]),
            )
        )


def get_emission_factor(db: Session, vehicle_type: str) -> EmissionFactor:
    normalized = normalize_vehicle_type(vehicle_type)
    factor = db.scalar(select(EmissionFactor).where(EmissionFactor.vehicle_type == normalized))
    if not factor:
        values = DEFAULT_EMISSION_FACTORS[normalized]
        factor = EmissionFactor(
            vehicle_type=normalized,
            co2_per_km=float(values["co2_per_km"]),
            co2_per_kg_km=float(values["co2_per_kg_km"]),
            description=str(values["description"]),
        )
        db.add(factor)
        db.flush()
    return factor


def _location_query(location_name: str) -> str:
    value = location_name.strip()
    return value if "türkiye" in value.lower() or "turkiye" in value.lower() or "turkey" in value.lower() else f"{value}, Türkiye"


def _nominatim_priority(row: dict) -> int:
    address = row.get("address") or {}
    if address.get("state_district"):
        return 0
    if address.get("city") or address.get("town"):
        return 1
    if address.get("village"):
        return 2
    return 3


def _nominatim_importance(row: dict) -> float:
    try:
        return float(row.get("importance") or 0)
    except (TypeError, ValueError):
        return 0.0


def _best_nominatim_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return sorted(rows, key=lambda row: (_nominatim_priority(row), -_nominatim_importance(row)))[0]


def get_coordinates(location_name: str) -> dict[str, float] | None:
    global _LAST_GEOCODE_REQUEST_AT
    normalized = location_name.strip().lower()
    if not normalized:
        return None
    if normalized in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[normalized]

    elapsed = time.monotonic() - _LAST_GEOCODE_REQUEST_AT
    if _LAST_GEOCODE_REQUEST_AT and elapsed < 1:
        time.sleep(1 - elapsed)

    params = urlencode(
        {
            "q": _location_query(location_name),
            "countrycodes": "tr",
            "format": "json",
            "limit": 10,
            "addressdetails": 1,
            "featuretype": "city,town,village,district",
            "bounded": 0,
        }
    )
    request = Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": NOMINATIM_USER_AGENT})
    try:
        with urlopen(request, timeout=5) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        logger.warning("Nominatim geocoding failed for %s: %s", location_name, exc)
        _GEOCODE_CACHE[normalized] = None
        _LAST_GEOCODE_REQUEST_AT = time.monotonic()
        return None

    _LAST_GEOCODE_REQUEST_AT = time.monotonic()
    selected = _best_nominatim_row(rows)
    if not selected:
        _GEOCODE_CACHE[normalized] = None
        return None

    coords = {"lat": float(selected["lat"]), "lon": float(selected["lon"])}
    _GEOCODE_CACHE[normalized] = coords
    return coords


def haversine_distance_km(origin_coords: dict[str, float], destination_coords: dict[str, float]) -> float:
    radius = 6371
    d_lat = radians(destination_coords["lat"] - origin_coords["lat"])
    d_lon = radians(destination_coords["lon"] - origin_coords["lon"])
    lat1 = radians(origin_coords["lat"])
    lat2 = radians(destination_coords["lat"])
    calc = sin(d_lat / 2) ** 2 + sin(d_lon / 2) ** 2 * cos(lat1) * cos(lat2)
    return radius * 2 * atan2(sqrt(calc), sqrt(1 - calc))


def calculate_distance_km(origin: str, destination: str) -> float | None:
    origin_coords = get_coordinates(origin)
    destination_coords = get_coordinates(destination)
    if not origin_coords or not destination_coords:
        return None
    return round(haversine_distance_km(origin_coords, destination_coords) * ROAD_DISTANCE_FACTOR, 2)


def get_route_info(origin_coords: dict[str, float], destination_coords: dict[str, float]) -> dict | None:
    if not origin_coords or not destination_coords:
        return None

    fallback_distance = round(haversine_distance_km(origin_coords, destination_coords) * ROAD_DISTANCE_FACTOR, 2)
    fallback = {
        "distance_km": fallback_distance,
        "duration_minutes": round((fallback_distance / 70) * 60, 1) if fallback_distance else None,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [origin_coords["lon"], origin_coords["lat"]],
                [destination_coords["lon"], destination_coords["lat"]],
            ],
        },
    }

    api_key = os.getenv("ORS_API_KEY") or get_settings().ors_api_key
    if not api_key:
        return fallback

    body = json.dumps(
        {
            "coordinates": [
                [origin_coords["lon"], origin_coords["lat"]],
                [destination_coords["lon"], destination_coords["lat"]],
            ],
            "instructions": False,
        }
    ).encode("utf-8")
    request = Request(
        ORS_DIRECTIONS_URL,
        data=body,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, application/geo+json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        logger.warning("ORS route calculation failed, falling back to haversine: %s", exc)
        return fallback

    try:
        if payload.get("features"):
            feature = payload["features"][0]
            summary = feature["properties"]["summary"]
            geometry = feature.get("geometry") or fallback["geometry"]
        else:
            route = payload["routes"][0]
            summary = route["summary"]
            geometry = route.get("geometry") or fallback["geometry"]
        return {
            "distance_km": round(float(summary["distance"]) / 1000, 2),
            "duration_minutes": round(float(summary["duration"]) / 60, 1),
            "geometry": geometry,
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("ORS route payload could not be parsed, falling back to haversine: %s", exc)
        return fallback


def calculate_emission(
    db: Session,
    vehicle_type: str,
    distance_km: float | None,
    weight_kg: float,
    origin: str | None = None,
    destination: str | None = None,
) -> float:
    if (distance_km is None or distance_km == 0) and origin and destination:
        calculated_distance = calculate_distance_km(origin, destination)
        if calculated_distance is not None:
            logger.info("Carbon distance auto-calculated for %s -> %s: %.2f km", origin, destination, calculated_distance)
            distance_km = calculated_distance
    distance_km = distance_km or 0
    if distance_km < 0 or weight_kg < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mesafe ve ağırlık negatif olamaz.")
    factor = get_emission_factor(db, vehicle_type)
    co2 = distance_km * factor.co2_per_km + weight_kg * distance_km * factor.co2_per_kg_km
    return round(co2, 4)


def compare_with_benchmark(actual_co2: float, distance_km: float) -> dict:
    benchmark_co2 = round(max(distance_km, 0) * BENCHMARK_CO2_PER_KM, 4)
    if benchmark_co2 == 0:
        deviation_percent = 0.0
    else:
        deviation_percent = round(((actual_co2 - benchmark_co2) / benchmark_co2) * 100, 2)

    if actual_co2 <= benchmark_co2 * 0.9:
        label = "yeşil"
    elif actual_co2 <= benchmark_co2 * 1.1:
        label = "orta"
    else:
        label = "yüksek"
    return {
        "benchmark_co2": benchmark_co2,
        "deviation_percent": deviation_percent,
        "label": label,
    }


def _shipment_query(start_date: date | None = None, end_date: date | None = None):
    statement = select(Shipment).where(Shipment.is_deleted.is_(False))
    if start_date:
        statement = statement.where(Shipment.delivery_date >= start_date)
    if end_date:
        statement = statement.where(Shipment.delivery_date <= end_date)
    return statement


def _period_key(value: date, period: Literal["daily", "weekly", "monthly"]) -> str:
    if period == "weekly":
        iso = value.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if period == "monthly":
        return value.strftime("%Y-%m")
    return value.isoformat()


def get_carbon_summary(
    db: Session,
    filters: dict | None = None,
    period: Literal["daily", "weekly", "monthly"] = "daily",
) -> dict:
    filters = filters or {}
    shipments = list(db.scalars(_shipment_query(filters.get("start_date"), filters.get("end_date"))).all())
    total = round(sum(row.co2_kg or 0 for row in shipments), 4)
    return {
        "total_co2": total,
        "by_vehicle": get_vehicle_distribution_from_shipments(shipments),
        "trend": get_trend_from_shipments(shipments, period),
        "top_routes": get_top_routes_from_shipments(shipments),
    }


def get_vehicle_distribution_from_shipments(shipments: list[Shipment]) -> list[dict]:
    grouped: dict[str, float] = defaultdict(float)
    for shipment in shipments:
        grouped[normalize_vehicle_type(shipment.vehicle_type)] += shipment.co2_kg or 0
    return [
        {"vehicle_type": vehicle_type, "co2": round(co2, 4)}
        for vehicle_type, co2 in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def get_trend_from_shipments(shipments: list[Shipment], period: Literal["daily", "weekly", "monthly"]) -> list[dict]:
    grouped: dict[str, float] = defaultdict(float)
    for shipment in shipments:
        grouped[_period_key(shipment.delivery_date, period)] += shipment.co2_kg or 0
    return [{"period": key, "co2": round(grouped[key], 4)} for key in sorted(grouped)]


def get_top_routes_from_shipments(shipments: list[Shipment], limit: int = 5) -> list[dict]:
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(lambda: {"co2": 0.0, "shipment_count": 0, "vehicles": defaultdict(float)})
    for shipment in shipments:
        key = (shipment.origin, shipment.destination)
        grouped[key]["co2"] = float(grouped[key]["co2"]) + (shipment.co2_kg or 0)
        grouped[key]["shipment_count"] = int(grouped[key]["shipment_count"]) + 1
        vehicles = grouped[key]["vehicles"]
        vehicles[normalize_vehicle_type(shipment.vehicle_type)] += shipment.co2_kg or 0
    rows = sorted(grouped.items(), key=lambda item: float(item[1]["co2"]), reverse=True)[:limit]
    return [
        {
            "origin": origin,
            "destination": destination,
            "vehicle_type": max(values["vehicles"].items(), key=lambda item: item[1])[0] if values["vehicles"] else None,
            "co2": round(float(values["co2"]), 4),
            "shipment_count": int(values["shipment_count"]),
        }
        for (origin, destination), values in rows
    ]
